from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, quantiles
from typing import Any
from zoneinfo import ZoneInfo
import csv
import json
import re

from .config import assert_under_root


LOCAL_TZ = ZoneInfo("Asia/Shanghai")
LOG_LINE_RE = re.compile(r"^\[(?P<stamp>[^\]]+)\] (?P<kind>Prefill|Decode) batch, (?P<body>.*)$")


@dataclass(frozen=True)
class RunWindow:
    run_id: str
    controller_label: str
    run_dir: Path
    start_ts: float
    end_ts: float


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _ratio(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    if len(values) < 20:
        return max(values)
    return quantiles(values, n=20)[18]


def _csv_value(value: Any) -> Any:
    return "" if value is None else value


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    out = assert_under_root(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _parse_log_timestamp(value: str) -> float:
    dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=LOCAL_TZ).timestamp()


def _parse_metric_value(body: str, pattern: str, cast):
    match = re.search(pattern, body)
    if not match:
        return None
    return cast(match.group(1))


def collect_run_windows(summaries: list[dict[str, Any]]) -> list[RunWindow]:
    windows: list[RunWindow] = []
    for summary in summaries:
        if summary.get("backend") != "openai" or summary.get("status") != "success":
            continue
        run_dir = Path(str(summary.get("run_dir") or ""))
        events_path = run_dir / "agent_events.jsonl"
        if not events_path.exists():
            continue
        starts: list[float] = []
        ends: list[float] = []
        with events_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                ts = _to_float(row.get("timestamp"))
                if ts is None:
                    continue
                if row.get("event") == "generation_start":
                    starts.append(ts)
                elif row.get("event") == "generation_end":
                    ends.append(ts)
        if not starts or not ends:
            continue
        windows.append(
            RunWindow(
                run_id=str(summary.get("run_id") or run_dir.name),
                controller_label=str(summary.get("controller_label") or summary.get("strategy") or ""),
                run_dir=run_dir,
                start_ts=min(starts) - 1.0,
                end_ts=max(ends) + 1.0,
            )
        )
    return sorted(windows, key=lambda window: window.start_ts)


def collect_server_dirs(runs_dir: Path) -> list[Path]:
    server_dirs = []
    for run_dir in sorted(assert_under_root(runs_dir).glob("*sglang_server*")):
        if (run_dir / "sglang_server.stderr.log").exists() or (run_dir / "sglang_metrics").exists():
            server_dirs.append(run_dir)
    return server_dirs


def _find_window(windows: list[RunWindow], timestamp: float | None) -> RunWindow | None:
    if timestamp is None:
        return None
    for window in windows:
        if window.start_ts <= timestamp <= window.end_ts:
            return window
    return None


def parse_request_metric_rows(server_dirs: list[Path], windows: list[RunWindow]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for server_dir in server_dirs:
        metrics_dir = server_dir / "sglang_metrics"
        for path in sorted(metrics_dir.glob("*.log")):
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    request_received_ts = _to_float(record.get("request_received_ts"))
                    request_finished_ts = _to_float(record.get("request_finished_ts"))
                    window = _find_window(windows, request_received_ts)
                    if window is None:
                        continue
                    request_parameters = {}
                    params_text = record.get("request_parameters")
                    if isinstance(params_text, str):
                        try:
                            request_parameters = json.loads(params_text)
                        except json.JSONDecodeError:
                            request_parameters = {}
                    sampling_params = request_parameters.get("sampling_params") if isinstance(request_parameters, dict) else {}
                    cached_details = record.get("cached_tokens_details") or {}
                    if not isinstance(cached_details, dict):
                        cached_details = {}
                    prompt_tokens = _to_int(record.get("prompt_tokens"))
                    cached_tokens = _to_int(record.get("cached_tokens")) or 0
                    rows.append(
                        {
                            "run_id": window.run_id,
                            "controller_label": window.controller_label,
                            "server_run_id": server_dir.name,
                            "request_id": record.get("id"),
                            "request_received_ts": request_received_ts,
                            "request_finished_ts": request_finished_ts,
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": _to_int(record.get("completion_tokens")),
                            "cached_tokens": cached_tokens,
                            "cached_tokens_device": _to_int(cached_details.get("device")),
                            "cached_tokens_host": _to_int(cached_details.get("host")),
                            "cached_token_ratio": _ratio(cached_tokens, prompt_tokens),
                            "queue_time_s": _to_float(record.get("queue_time")),
                            "e2e_latency_s": _to_float(record.get("e2e_latency")),
                            "decode_throughput_tokens_s": _to_float(record.get("decode_throughput")),
                            "max_new_tokens": sampling_params.get("max_new_tokens") if isinstance(sampling_params, dict) else None,
                            "finish_reason_type": (record.get("finish_reason") or {}).get("type") if isinstance(record.get("finish_reason"), dict) else None,
                            "metric_file": str(path),
                        }
                    )
    return rows


def summarize_request_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["run_id"]), []).append(row)
    summaries = []
    for run_id, run_rows in sorted(grouped.items()):
        prompt_tokens = [int(row["prompt_tokens"]) for row in run_rows if row.get("prompt_tokens") not in (None, "")]
        completion_tokens = [int(row["completion_tokens"]) for row in run_rows if row.get("completion_tokens") not in (None, "")]
        cached_tokens = [int(row["cached_tokens"]) for row in run_rows if row.get("cached_tokens") not in (None, "")]
        queue_times = [float(row["queue_time_s"]) for row in run_rows if row.get("queue_time_s") not in (None, "")]
        latencies = [float(row["e2e_latency_s"]) for row in run_rows if row.get("e2e_latency_s") not in (None, "")]
        decode_throughputs = [float(row["decode_throughput_tokens_s"]) for row in run_rows if row.get("decode_throughput_tokens_s") not in (None, "")]
        total_prompt = sum(prompt_tokens)
        total_cached = sum(cached_tokens)
        summaries.append(
            {
                "run_id": run_id,
                "controller_label": str(run_rows[0].get("controller_label") or ""),
                "request_count": len(run_rows),
                "prompt_tokens_total": total_prompt,
                "completion_tokens_total": sum(completion_tokens),
                "cached_tokens_total": total_cached,
                "cached_token_ratio_total": _ratio(total_cached, total_prompt),
                "mean_queue_time_s": mean(queue_times) if queue_times else None,
                "max_queue_time_s": max(queue_times) if queue_times else None,
                "mean_e2e_latency_s": mean(latencies) if latencies else None,
                "p95_e2e_latency_s": _p95(latencies),
                "mean_decode_throughput_tokens_s": mean(decode_throughputs) if decode_throughputs else None,
                "max_cached_tokens": max(cached_tokens) if cached_tokens else None,
            }
        )
    return summaries


def parse_scheduler_rows(server_dirs: list[Path], windows: list[RunWindow]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for server_dir in server_dirs:
        log_path = server_dir / "sglang_server.stderr.log"
        if not log_path.exists():
            continue
        with log_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                match = LOG_LINE_RE.match(line.strip())
                if not match:
                    continue
                timestamp = _parse_log_timestamp(match.group("stamp"))
                window = _find_window(windows, timestamp)
                if window is None:
                    continue
                body = match.group("body")
                rows.append(
                    {
                        "run_id": window.run_id,
                        "controller_label": window.controller_label,
                        "server_run_id": server_dir.name,
                        "timestamp": timestamp,
                        "elapsed_s": timestamp - window.start_ts,
                        "batch_type": match.group("kind").lower(),
                        "new_seq": _parse_metric_value(body, r"#new-seq: ([0-9]+)", int),
                        "new_token": _parse_metric_value(body, r"#new-token: ([0-9]+)", int),
                        "cached_token": _parse_metric_value(body, r"#cached-token: ([0-9]+)", int),
                        "token": _parse_metric_value(body, r"#token: ([0-9]+)", int),
                        "token_usage": _parse_metric_value(body, r"token usage: ([0-9.]+)", float),
                        "running_req": _parse_metric_value(body, r"#running-req: ([0-9]+)", int),
                        "queue_req": _parse_metric_value(body, r"#queue-req: ([0-9]+)", int),
                        "pending_token": _parse_metric_value(body, r"#pending-token: ([0-9]+)", int),
                        "input_throughput_tokens_s": _parse_metric_value(body, r"input throughput \(token/s\): ([0-9.]+)", float),
                        "gen_throughput_tokens_s": _parse_metric_value(body, r"gen throughput \(token/s\): ([0-9.]+)", float),
                    }
                )
    return rows


def summarize_scheduler_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["run_id"]), []).append(row)
    summaries = []
    for run_id, run_rows in sorted(grouped.items()):
        token_usages = [float(row["token_usage"]) for row in run_rows if row.get("token_usage") is not None]
        running_reqs = [int(row["running_req"]) for row in run_rows if row.get("running_req") is not None]
        queue_reqs = [int(row["queue_req"]) for row in run_rows if row.get("queue_req") is not None]
        pending_tokens = [int(row["pending_token"]) for row in run_rows if row.get("pending_token") is not None]
        prefill_rows = [row for row in run_rows if row.get("batch_type") == "prefill"]
        decode_rows = [row for row in run_rows if row.get("batch_type") == "decode"]
        input_throughputs = [float(row["input_throughput_tokens_s"]) for row in run_rows if row.get("input_throughput_tokens_s") is not None]
        gen_throughputs = [float(row["gen_throughput_tokens_s"]) for row in run_rows if row.get("gen_throughput_tokens_s") is not None]
        summaries.append(
            {
                "run_id": run_id,
                "controller_label": str(run_rows[0].get("controller_label") or ""),
                "scheduler_points": len(run_rows),
                "prefill_batches": len(prefill_rows),
                "decode_batches": len(decode_rows),
                "max_token_usage": max(token_usages) if token_usages else None,
                "mean_token_usage": mean(token_usages) if token_usages else None,
                "max_running_req": max(running_reqs) if running_reqs else None,
                "max_queue_req": max(queue_reqs) if queue_reqs else None,
                "max_pending_token": max(pending_tokens) if pending_tokens else None,
                "prefill_new_tokens_total": sum(int(row["new_token"]) for row in prefill_rows if row.get("new_token") is not None),
                "prefill_cached_tokens_total": sum(int(row["cached_token"]) for row in prefill_rows if row.get("cached_token") is not None),
                "max_input_throughput_tokens_s": max(input_throughputs) if input_throughputs else None,
                "max_gen_throughput_tokens_s": max(gen_throughputs) if gen_throughputs else None,
            }
        )
    return summaries


def write_sglang_log_artifacts(
    runs_dir: Path,
    tables_dir: Path,
    summaries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    windows = collect_run_windows(summaries)
    server_dirs = collect_server_dirs(runs_dir)
    request_rows = parse_request_metric_rows(server_dirs, windows)
    request_summaries = summarize_request_rows(request_rows)
    scheduler_rows = parse_scheduler_rows(server_dirs, windows)
    scheduler_summaries = summarize_scheduler_rows(scheduler_rows)
    _write_csv(
        tables_dir / "sglang_request_metrics_by_run.csv",
        [
            "run_id",
            "controller_label",
            "server_run_id",
            "request_id",
            "request_received_ts",
            "request_finished_ts",
            "prompt_tokens",
            "completion_tokens",
            "cached_tokens",
            "cached_tokens_device",
            "cached_tokens_host",
            "cached_token_ratio",
            "queue_time_s",
            "e2e_latency_s",
            "decode_throughput_tokens_s",
            "max_new_tokens",
            "finish_reason_type",
            "metric_file",
        ],
        request_rows,
    )
    _write_csv(
        tables_dir / "sglang_request_summary_by_run.csv",
        [
            "run_id",
            "controller_label",
            "request_count",
            "prompt_tokens_total",
            "completion_tokens_total",
            "cached_tokens_total",
            "cached_token_ratio_total",
            "mean_queue_time_s",
            "max_queue_time_s",
            "mean_e2e_latency_s",
            "p95_e2e_latency_s",
            "mean_decode_throughput_tokens_s",
            "max_cached_tokens",
        ],
        request_summaries,
    )
    _write_csv(
        tables_dir / "sglang_scheduler_pressure_by_run.csv",
        [
            "run_id",
            "controller_label",
            "server_run_id",
            "timestamp",
            "elapsed_s",
            "batch_type",
            "new_seq",
            "new_token",
            "cached_token",
            "token",
            "token_usage",
            "running_req",
            "queue_req",
            "pending_token",
            "input_throughput_tokens_s",
            "gen_throughput_tokens_s",
        ],
        scheduler_rows,
    )
    _write_csv(
        tables_dir / "sglang_scheduler_summary_by_run.csv",
        [
            "run_id",
            "controller_label",
            "scheduler_points",
            "prefill_batches",
            "decode_batches",
            "max_token_usage",
            "mean_token_usage",
            "max_running_req",
            "max_queue_req",
            "max_pending_token",
            "prefill_new_tokens_total",
            "prefill_cached_tokens_total",
            "max_input_throughput_tokens_s",
            "max_gen_throughput_tokens_s",
        ],
        scheduler_summaries,
    )
    return request_summaries, scheduler_summaries
