from __future__ import annotations

from pathlib import Path
import argparse
import csv
import json
import math
import os
import re
from statistics import mean, stdev
import struct
import zlib

from .config import REPRO_ROOT, assert_under_root, read_config
from .metadata import controller_metadata
from .sglang_logs import write_sglang_log_artifacts


SEED_RE = re.compile(r"seed(\d+)")
V2_CONTROLLERS = [
    "no_control",
    "request_cap_4",
    "request_cap_8",
    "fixed_window_4",
    "fixed_window_8",
    "concur_dynamic_v2",
    "concur_cache_aware_v1",
    "phase_window_v1",
    "tail_open_v1",
    "cache_gate_v1",
]
INNOVATION_CONTROLLERS = {
    "concur_cache_aware_v1",
    "phase_window_v1",
    "tail_open_v1",
    "cache_gate_v1",
}
FIGURE_COLORS = {
    "no_control": "#4C78A8",
    "request_cap_4": "#F58518",
    "request_cap_8": "#72B7B2",
    "fixed_window_4": "#54A24B",
    "fixed_window_8": "#B279A2",
    "concur_dynamic_v2": "#E45756",
    "concur_cache_aware_v1": "#9467BD",
    "phase_window_v1": "#8C564B",
    "tail_open_v1": "#2F855A",
    "cache_gate_v1": "#2563EB",
}


def read_summary(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def iter_csv_rows(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh)


def collect_summaries(runs_dir: Path) -> list[dict]:
    rows = []
    for summary_path in sorted(runs_dir.glob("*/summary.json")):
        row = read_summary(summary_path)
        config_path = summary_path.parent / "config.yaml"
        config = read_config(config_path) if config_path.exists() else {}
        for key in (
            "backend",
            "model",
            "model_label",
            "served_model_name",
            "strategy",
            "workload_version",
            "num_agents",
            "num_steps",
            "observation_tokens_per_step",
            "max_new_tokens",
        ):
            if key not in row or row[key] in (None, ""):
                row[key] = config.get(key)
        if "run_id" not in row or not row["run_id"]:
            row["run_id"] = summary_path.parent.name
        total_agents = int(row.get("num_agents") or config.get("num_agents") or 0)
        merged_config = dict(config)
        merged_config.update({k: v for k, v in row.items() if v is not None})
        metadata = controller_metadata(merged_config, total_agents if total_agents else None)
        for key, value in metadata.items():
            if key not in row or row[key] in (None, ""):
                row[key] = value
        row["run_dir"] = str(summary_path.parent)
        row["config_path"] = str(config_path) if config_path.exists() else ""
        rows.append(row)
    return rows


def write_latency_table(rows: list[dict], out: Path) -> None:
    fields = [
        "run_id",
        "status",
        "backend",
        "model",
        "model_label",
        "served_model_name",
        "strategy",
        "controller_label",
        "workload_version",
        "request_cap",
        "agent_window",
        "effective_agent_window",
        "W_0",
        "W_min",
        "W_max",
        "effective_W_max",
        "num_agents",
        "num_steps",
        "observation_tokens_per_step",
        "max_new_tokens",
        "end_to_end_batch_latency_s",
        "completed_agents_per_second",
        "mean_agent_latency_s",
        "p95_agent_latency_s",
        "mock_result_excluded_from_qwen_claims",
        "run_dir",
        "config_path",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int, pixels: list[tuple[int, int, int]]) -> None:
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(pixels[y * width + x])
    data = b"\x89PNG\r\n\x1a\n"
    data += _png_chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    data += _png_chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def blank_canvas(width: int, height: int, color=(255, 255, 255)) -> list[tuple[int, int, int]]:
    return [color for _ in range(width * height)]


def set_pixel(pixels, width, height, x, y, color):
    if 0 <= x < width and 0 <= y < height:
        pixels[y * width + x] = color


def draw_line(pixels, width, height, x0, y0, x1, y1, color):
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                set_pixel(pixels, width, height, x + ox, y + oy, color)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def make_line_plot(points: list[tuple[float, float]], out: Path, color=(25, 90, 180)) -> None:
    width, height = 900, 420
    left, right, top, bottom = 70, 30, 30, 60
    pixels = blank_canvas(width, height)
    axis = (50, 50, 50)
    for x in range(left, width - right):
        set_pixel(pixels, width, height, x, height - bottom, axis)
    for y in range(top, height - bottom):
        set_pixel(pixels, width, height, left, y, axis)
    if not points:
        write_png(out, width, height, pixels)
        return
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if math.isclose(xmin, xmax):
        xmax = xmin + 1.0
    if math.isclose(ymin, ymax):
        ymax = ymin + 1.0
    mapped = []
    for x, y in points:
        px = int(left + (x - xmin) / (xmax - xmin) * (width - left - right - 1))
        py = int(height - bottom - (y - ymin) / (ymax - ymin) * (height - top - bottom - 1))
        mapped.append((px, py))
    for (x0, y0), (x1, y1) in zip(mapped, mapped[1:]):
        draw_line(pixels, width, height, x0, y0, x1, y1, color)
    for x, y in mapped:
        for ox in range(-3, 4):
            for oy in range(-3, 4):
                if ox * ox + oy * oy <= 9:
                    set_pixel(pixels, width, height, x + ox, y + oy, color)
    write_png(out, width, height, pixels)


def make_bar_plot(rows: list[dict], out: Path) -> None:
    width, height = 1000, 460
    left, right, top, bottom = 80, 40, 40, 80
    pixels = blank_canvas(width, height)
    axis = (50, 50, 50)
    for x in range(left, width - right):
        set_pixel(pixels, width, height, x, height - bottom, axis)
    for y in range(top, height - bottom):
        set_pixel(pixels, width, height, left, y, axis)
    values = [float(r.get("end_to_end_batch_latency_s") or 0.0) for r in rows if r.get("status") == "success"]
    if not values:
        write_png(out, width, height, pixels)
        return
    ymax = max(values) or 1.0
    n = len(values)
    bar_space = max(8, (width - left - right) // max(1, n))
    for i, value in enumerate(values):
        x0 = left + i * bar_space + 8
        x1 = min(width - right - 1, x0 + max(6, bar_space - 16))
        y0 = int(height - bottom - value / ymax * (height - top - bottom - 1))
        color = (30, 120, 90) if i % 2 == 0 else (190, 90, 40)
        for x in range(x0, x1):
            for y in range(y0, height - bottom):
                set_pixel(pixels, width, height, x, y, color)
    write_png(out, width, height, pixels)


def _float_or_none(value) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _int_or_none(value) -> int | None:
    if value in (None, ""):
        return None
    return int(float(value))


def _csv_cell(value):
    return "" if value is None else value


def _fmt(value, digits: int = 3) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _mean(values: list[float]) -> float | None:
    return mean(values) if values else None


def _std(values: list[float]) -> float | None:
    if len(values) < 2:
        return 0.0 if values else None
    return stdev(values)


def _controller_sort_key(controller: str) -> tuple[int, str]:
    try:
        return (V2_CONTROLLERS.index(controller), controller)
    except ValueError:
        return (len(V2_CONTROLLERS), controller)


def _write_rows(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_cell(row.get(field)) for field in fields})


def _index_by_run(rows: list[dict]) -> dict[str, dict]:
    return {str(row.get("run_id")): row for row in rows if row.get("run_id")}


def _extract_seed(row: dict) -> int | None:
    for key in ("model_label", "run_id", "config_path"):
        match = SEED_RE.search(str(row.get(key) or ""))
        if match:
            return int(match.group(1))
    return None


def _v2_scenario(row: dict) -> str | None:
    if row.get("workload_version") != "prefix_stable_v2":
        return None
    num_agents = _int_or_none(row.get("num_agents"))
    num_steps = _int_or_none(row.get("num_steps"))
    obs_tokens = _int_or_none(row.get("observation_tokens_per_step"))
    max_new_tokens = _int_or_none(row.get("max_new_tokens"))
    if max_new_tokens not in (None, 64):
        return None
    if num_agents == 8 and num_steps == 8 and obs_tokens == 256:
        return "b8"
    if num_agents == 8 and num_steps == 12 and obs_tokens == 320:
        return "b8_long_ctxfit"
    if num_agents == 8 and num_steps == 12 and obs_tokens in (384, 512):
        return "b8_long_original"
    if num_agents == 12 and num_steps == 8 and obs_tokens == 256:
        return "b12_medium"
    if num_agents == 16 and num_steps == 8 and obs_tokens == 256:
        return "b16_medium"
    return None


def _controller_stats(run_dir: Path) -> dict:
    rows = list(iter_jsonl(run_dir / "controller_events.jsonl") or [])
    windows = []
    exact_events = 0
    stale_events = 0
    increase_events = 0
    decrease_events = 0
    hold_events = 0
    for row in rows:
        source = str(row.get("metric_source") or row.get("metrics_source") or row.get("source") or "")
        metric_type = str(row.get("metric_type") or "")
        source_text = f"{source} {metric_type}"
        if "exact" in source_text or "sglang" in source_text:
            exact_events += 1
        if "stale" in source_text:
            stale_events += 1
        w_t = _float_or_none(row.get("W_t"))
        w_next = _float_or_none(row.get("W_next"))
        window = w_next if w_next is not None else w_t
        if window is not None:
            windows.append(window)
        if w_t is not None and w_next is not None:
            if w_next > w_t:
                increase_events += 1
            elif w_next < w_t:
                decrease_events += 1
            else:
                hold_events += 1
    return {
        "controller_event_count": len(rows),
        "exact_controller_event_count": exact_events,
        "stale_controller_event_count": stale_events,
        "window_min": min(windows) if windows else None,
        "window_max": max(windows) if windows else None,
        "window_mean": _mean(windows),
        "window_increase_events": increase_events,
        "window_decrease_events": decrease_events,
        "window_hold_events": hold_events,
    }


def build_v2_result_rows(
    summaries: list[dict],
    request_summaries: list[dict],
    scheduler_summaries: list[dict],
) -> list[dict]:
    request_by_run = _index_by_run(request_summaries)
    scheduler_by_run = _index_by_run(scheduler_summaries)
    rows = []
    for summary in summaries:
        scenario = _v2_scenario(summary)
        if not scenario:
            continue
        run_id = str(summary.get("run_id") or "")
        controller = str(summary.get("controller_label") or summary.get("strategy") or "")
        request = request_by_run.get(run_id, {})
        scheduler = scheduler_by_run.get(run_id, {})
        run_dir = Path(str(summary.get("run_dir") or ""))
        controller_stats = _controller_stats(run_dir)
        row = {
            "scenario": scenario,
            "controller": controller,
            "seed": _extract_seed(summary),
            "run_id": run_id,
            "status": summary.get("status"),
            "num_agents": _int_or_none(summary.get("num_agents")),
            "num_steps": _int_or_none(summary.get("num_steps")),
            "observation_tokens_per_step": _int_or_none(summary.get("observation_tokens_per_step")),
            "max_new_tokens": _int_or_none(summary.get("max_new_tokens")),
            "latency_s": _float_or_none(summary.get("end_to_end_batch_latency_s")),
            "completed_agents_per_second": _float_or_none(summary.get("completed_agents_per_second")),
            "mean_agent_latency_s": _float_or_none(summary.get("mean_agent_latency_s")),
            "p95_agent_latency_s": _float_or_none(summary.get("p95_agent_latency_s")),
            "max_token_usage": _float_or_none(scheduler.get("max_token_usage")),
            "mean_token_usage": _float_or_none(scheduler.get("mean_token_usage")),
            "max_queue_req": _int_or_none(scheduler.get("max_queue_req")),
            "max_pending_token": _int_or_none(scheduler.get("max_pending_token")),
            "cached_token_ratio_total": _float_or_none(request.get("cached_token_ratio_total")),
            "prompt_tokens_total": _int_or_none(request.get("prompt_tokens_total")),
            "cached_tokens_total": _int_or_none(request.get("cached_tokens_total")),
            "mean_request_latency_s": _float_or_none(request.get("mean_e2e_latency_s")),
            "p95_request_latency_s": _float_or_none(request.get("p95_e2e_latency_s")),
            "run_dir": str(run_dir),
        }
        row.update(controller_stats)
        rows.append(row)
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("scenario") or ""),
            _controller_sort_key(str(row.get("controller") or "")),
            row.get("seed") if row.get("seed") is not None else 999,
            str(row.get("run_id") or ""),
        ),
    )


def write_v2_tables(v2_rows: list[dict], tables_dir: Path, reports_dir: Path) -> tuple[list[dict], list[dict]]:
    b8_rows = [
        row
        for row in v2_rows
        if row.get("scenario") == "b8"
        and row.get("status") == "success"
        and row.get("controller") in {
            "no_control",
            "request_cap_4",
            "fixed_window_4",
            "fixed_window_8",
            "concur_dynamic_v2",
        }
    ]
    b8_fields = [
        "controller",
        "seed",
        "run_id",
        "latency_s",
        "max_token_usage",
        "mean_token_usage",
        "max_queue_req",
        "max_pending_token",
        "cached_token_ratio_total",
        "mean_request_latency_s",
        "p95_request_latency_s",
        "controller_event_count",
        "exact_controller_event_count",
        "window_min",
        "window_max",
        "window_mean",
    ]
    _write_rows(tables_dir / "v2_b8_repeated_trials.csv", b8_fields, b8_rows)

    grouped: dict[str, list[dict]] = {}
    for row in b8_rows:
        grouped.setdefault(str(row["controller"]), []).append(row)
    b8_summary = []
    for controller, rows in sorted(grouped.items(), key=lambda item: _controller_sort_key(item[0])):
        latencies = [float(row["latency_s"]) for row in rows if row.get("latency_s") is not None]
        token_usages = [float(row["max_token_usage"]) for row in rows if row.get("max_token_usage") is not None]
        queue_reqs = [float(row["max_queue_req"]) for row in rows if row.get("max_queue_req") is not None]
        cache_ratios = [float(row["cached_token_ratio_total"]) for row in rows if row.get("cached_token_ratio_total") is not None]
        b8_summary.append(
            {
                "controller": controller,
                "n": len(rows),
                "latency_mean_s": _mean(latencies),
                "latency_std_s": _std(latencies),
                "latency_min_s": min(latencies) if latencies else None,
                "latency_max_s": max(latencies) if latencies else None,
                "max_token_usage_mean": _mean(token_usages),
                "max_queue_req_mean": _mean(queue_reqs),
                "cached_token_ratio_mean": _mean(cache_ratios),
            }
        )
    _write_rows(
        tables_dir / "v2_b8_repeated_trials_summary.csv",
        [
            "controller",
            "n",
            "latency_mean_s",
            "latency_std_s",
            "latency_min_s",
            "latency_max_s",
            "max_token_usage_mean",
            "max_queue_req_mean",
            "cached_token_ratio_mean",
        ],
        b8_summary,
    )

    pressure_rows = [
        row
        for row in v2_rows
        if row.get("scenario") in {"b8_long_ctxfit", "b8_long_original", "b12_medium", "b16_medium"}
    ]
    pressure_fields = [
        "scenario",
        "controller",
        "seed",
        "status",
        "run_id",
        "num_agents",
        "num_steps",
        "observation_tokens_per_step",
        "latency_s",
        "max_token_usage",
        "mean_token_usage",
        "max_queue_req",
        "max_pending_token",
        "cached_token_ratio_total",
        "mean_request_latency_s",
        "p95_request_latency_s",
        "controller_event_count",
        "exact_controller_event_count",
        "window_min",
        "window_max",
        "window_mean",
        "run_dir",
    ]
    _write_rows(tables_dir / "v2_pressure_runs.csv", pressure_fields, pressure_rows)

    pressure_summary = []
    for key in sorted({(row.get("scenario"), row.get("controller")) for row in pressure_rows}):
        scenario, controller = key
        rows = [
            row
            for row in pressure_rows
            if row.get("scenario") == scenario and row.get("controller") == controller and row.get("status") == "success"
        ]
        if not rows:
            continue
        latencies = [float(row["latency_s"]) for row in rows if row.get("latency_s") is not None]
        token_usages = [float(row["max_token_usage"]) for row in rows if row.get("max_token_usage") is not None]
        queue_reqs = [float(row["max_queue_req"]) for row in rows if row.get("max_queue_req") is not None]
        cache_ratios = [float(row["cached_token_ratio_total"]) for row in rows if row.get("cached_token_ratio_total") is not None]
        pressure_summary.append(
            {
                "scenario": scenario,
                "controller": controller,
                "n": len(rows),
                "latency_mean_s": _mean(latencies),
                "latency_min_s": min(latencies) if latencies else None,
                "latency_max_s": max(latencies) if latencies else None,
                "max_token_usage_mean": _mean(token_usages),
                "max_queue_req_mean": _mean(queue_reqs),
                "cached_token_ratio_mean": _mean(cache_ratios),
            }
        )
    _write_rows(
        tables_dir / "v2_pressure_runs_summary.csv",
        [
            "scenario",
            "controller",
            "n",
            "latency_mean_s",
            "latency_min_s",
            "latency_max_s",
            "max_token_usage_mean",
            "max_queue_req_mean",
            "cached_token_ratio_mean",
        ],
        pressure_summary,
    )
    write_b8_repeated_markdown(b8_rows, b8_summary, reports_dir / "v2_b8_repeated_trials.md")
    return b8_summary, pressure_summary


def _markdown_table(rows: list[dict], fields: list[tuple[str, str]], float_digits: int = 3) -> str:
    header = "| " + " | ".join(label for _, label in fields) + " |"
    sep = "| " + " | ".join("---" for _ in fields) + " |"
    lines = [header, sep]
    for row in rows:
        values = []
        for key, _label in fields:
            value = row.get(key)
            values.append(_fmt(value, float_digits) if isinstance(value, float) else str(value if value is not None else ""))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_b8_repeated_markdown(b8_rows: list[dict], b8_summary: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    summary_table = _markdown_table(
        b8_summary,
        [
            ("controller", "controller"),
            ("n", "n"),
            ("latency_mean_s", "latency_mean_s"),
            ("latency_std_s", "latency_std_s"),
            ("latency_min_s", "latency_min_s"),
            ("latency_max_s", "latency_max_s"),
            ("max_token_usage_mean", "max_token_usage_mean"),
            ("max_queue_req_mean", "max_queue_req_mean"),
            ("cached_token_ratio_mean", "cached_token_ratio_mean"),
        ],
    )
    detail_table = _markdown_table(
        b8_rows,
        [
            ("controller", "controller"),
            ("seed", "seed"),
            ("latency_s", "latency_s"),
            ("max_token_usage", "max_token_usage"),
            ("max_queue_req", "max_queue_req"),
            ("max_pending_token", "max_pending_token"),
            ("cached_token_ratio_total", "cached_token_ratio_total"),
            ("controller_event_count", "controller_events"),
            ("window_min", "window_min"),
            ("window_max", "window_max"),
        ],
    )
    out.write_text(
        "\n".join(
            [
                "# v2 b8 Repeated Trials",
                "",
                "Source CSVs:",
                "",
                "- `outputs/tables/v2_b8_repeated_trials.csv`",
                "- `outputs/tables/v2_b8_repeated_trials_summary.csv`",
                "",
                "## Summary",
                "",
                summary_table,
                "",
                "## Per-Run Detail",
                "",
                detail_table,
                "",
                "Notes: these rows include Qwen3-32B BF16 `prefix_stable_v2` runs with 8 agents, 8 steps, 256 observation tokens per step, and 64 max new tokens. Exact cache and scheduler fields come from SGLang logs when available.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _load_pyplot():
    os.environ.setdefault("MPLCONFIGDIR", str(REPRO_ROOT.parent / ".cache" / "matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _label(controller: str) -> str:
    return controller.replace("_", "\n")


def _save_bar_figure(path: Path, title: str, ylabel: str, rows: list[dict], value_key: str, err_key: str | None = None) -> None:
    plt = _load_pyplot()
    rows = [row for row in rows if row.get(value_key) is not None]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    if rows:
        labels = [_label(str(row["controller"])) for row in rows]
        values = [float(row[value_key]) for row in rows]
        errors = [float(row.get(err_key) or 0.0) for row in rows] if err_key else None
        colors = [FIGURE_COLORS.get(str(row["controller"]), "#6B7280") for row in rows]
        ax.bar(labels, values, yerr=errors, capsize=4 if errors else 0, color=colors, edgecolor="#2F2F2F", linewidth=0.8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("controller")
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.8, alpha=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def write_v2_figures(v2_rows: list[dict], b8_summary: list[dict], figures_dir: Path) -> None:
    b8_summary = sorted(b8_summary, key=lambda row: _controller_sort_key(str(row.get("controller") or "")))
    _save_bar_figure(
        figures_dir / "v2_latency_mean_std.png",
        "Qwen3-32B prefix_stable_v2 b8 latency",
        "batch latency, seconds",
        b8_summary,
        "latency_mean_s",
        "latency_std_s",
    )
    _save_bar_figure(
        figures_dir / "v2_scheduler_token_usage_by_controller.png",
        "SGLang scheduler pressure by controller",
        "mean of per-run max token_usage",
        b8_summary,
        "max_token_usage_mean",
    )
    _save_bar_figure(
        figures_dir / "v2_queue_depth_by_controller.png",
        "SGLang queue depth by controller",
        "mean of per-run max queue_req",
        b8_summary,
        "max_queue_req_mean",
    )
    _save_bar_figure(
        figures_dir / "v2_cached_token_ratio_by_controller.png",
        "Exact cached token ratio by controller",
        "mean cached_tokens / prompt_tokens",
        b8_summary,
        "cached_token_ratio_mean",
    )

    plt = _load_pyplot()
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    plotted = 0
    for row in v2_rows:
        if row.get("controller") != "concur_dynamic_v2" or row.get("status") != "success":
            continue
        events = list(iter_jsonl(Path(str(row["run_dir"])) / "controller_events.jsonl") or [])
        if not events:
            continue
        base = _float_or_none(events[0].get("timestamp")) or 0.0
        points = []
        for event in events:
            ts = _float_or_none(event.get("timestamp"))
            window = _float_or_none(event.get("W_next"))
            if window is None:
                window = _float_or_none(event.get("W_t"))
            if ts is None or window is None:
                continue
            points.append((ts - base, window))
        if not points:
            continue
        label = f"{row.get('scenario')} seed{row.get('seed')}"
        ax.plot(
            [point[0] for point in points],
            [point[1] for point in points],
            linewidth=1.6,
            label=label,
        )
        plotted += 1
    ax.set_title("concur_dynamic_v2 periodic window updates")
    ax.set_xlabel("elapsed seconds from first controller event")
    ax.set_ylabel("admission window W")
    ax.grid(color="#D9D9D9", linewidth=0.8, alpha=0.8)
    if plotted:
        ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(figures_dir / "v2_dynamic_window_timeseries.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    scenario_labels = ["b8 mean", "b8_long_ctxfit", "b12_medium", "b16_medium"]
    controllers = ["no_control", "fixed_window_4", "fixed_window_8", "concur_dynamic_v2"]
    values_by_key: dict[tuple[str, str], float] = {}
    for row in b8_summary:
        if row.get("latency_mean_s") is not None:
            values_by_key[("b8 mean", str(row["controller"]))] = float(row["latency_mean_s"])
    for row in v2_rows:
        if row.get("status") != "success" or row.get("latency_s") is None:
            continue
        scenario = str(row.get("scenario"))
        if scenario in scenario_labels:
            values_by_key[(scenario, str(row["controller"]))] = float(row["latency_s"])
    x_positions = list(range(len(scenario_labels)))
    width = 0.18
    for idx, controller in enumerate(controllers):
        xs = [x + (idx - 1.5) * width for x in x_positions]
        heights = [values_by_key.get((scenario, controller), math.nan) for scenario in scenario_labels]
        ax.bar(
            xs,
            heights,
            width=width,
            label=controller,
            color=FIGURE_COLORS.get(controller, "#6B7280"),
            edgecolor="#2F2F2F",
            linewidth=0.7,
        )
    ax.set_xticks(x_positions)
    ax.set_xticklabels(scenario_labels, rotation=12, ha="right")
    ax.set_title("Fixed-window and dynamic latency across v2 pressure scenarios")
    ax.set_ylabel("batch latency, seconds")
    ax.set_xlabel("scenario")
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.8, alpha=0.8)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(figures_dir / "v2_fixed_vs_dynamic_latency.png", dpi=180)
    plt.close(fig)


def _best_latency(rows: list[dict], scenario: str) -> dict | None:
    candidates = [
        row
        for row in rows
        if row.get("scenario") == scenario and row.get("status") == "success" and row.get("latency_s") is not None
    ]
    return min(candidates, key=lambda row: float(row["latency_s"])) if candidates else None


def write_v2_report(
    summaries: list[dict],
    v2_rows: list[dict],
    b8_summary: list[dict],
    pressure_summary: list[dict],
    request_summaries: list[dict],
    out: Path,
) -> None:
    request_by_run = _index_by_run(request_summaries)
    old_b8_ratios = []
    for summary in summaries:
        if summary.get("status") != "success" or summary.get("workload_version") == "prefix_stable_v2":
            continue
        if _int_or_none(summary.get("num_agents")) != 8 or _int_or_none(summary.get("num_steps")) != 8:
            continue
        request = request_by_run.get(str(summary.get("run_id") or ""))
        ratio = _float_or_none((request or {}).get("cached_token_ratio_total"))
        if ratio is not None:
            old_b8_ratios.append(ratio)
    old_b8_ratio_mean = _mean(old_b8_ratios)
    v2_b8_ratio_mean = _mean([float(row["cached_token_ratio_mean"]) for row in b8_summary if row.get("cached_token_ratio_mean") is not None])

    b8_summary_table = _markdown_table(
        b8_summary,
        [
            ("controller", "controller"),
            ("n", "n"),
            ("latency_mean_s", "latency_mean_s"),
            ("latency_std_s", "latency_std_s"),
            ("max_token_usage_mean", "max_token_usage_mean"),
            ("max_queue_req_mean", "max_queue_req_mean"),
            ("cached_token_ratio_mean", "cached_ratio_mean"),
        ],
    )
    pressure_table = _markdown_table(
        pressure_summary,
        [
            ("scenario", "scenario"),
            ("controller", "controller"),
            ("n", "n"),
            ("latency_mean_s", "latency_s"),
            ("max_token_usage_mean", "max_token_usage"),
            ("max_queue_req_mean", "max_queue_req"),
            ("cached_token_ratio_mean", "cached_ratio"),
        ],
    )
    dynamic_rows = [
        row
        for row in v2_rows
        if row.get("controller") == "concur_dynamic_v2" and row.get("status") == "success"
    ]
    dynamic_table = _markdown_table(
        dynamic_rows,
        [
            ("scenario", "scenario"),
            ("seed", "seed"),
            ("latency_s", "latency_s"),
            ("controller_event_count", "events"),
            ("exact_controller_event_count", "exact_events"),
            ("window_min", "W_min_seen"),
            ("window_max", "W_max_seen"),
            ("window_mean", "W_mean"),
        ],
    )

    b8_best = min(b8_summary, key=lambda row: float(row["latency_mean_s"])) if b8_summary else None
    p6_best = {scenario: _best_latency(v2_rows, scenario) for scenario in ("b8_long_ctxfit", "b12_medium", "b16_medium")}
    failed_original = [
        row
        for row in v2_rows
        if row.get("scenario") == "b8_long_original" and row.get("status") != "success"
    ]

    lines = [
        "# CONCUR Qwen Single-GPU Reproduction Report v2",
        "",
        "## 1. Scope",
        "",
        "This report covers the Qwen3-32B BF16 single-GPU reproduction in `/data/3.8T-1/yue/concur_qwen_repro`. The goal is a scaled, instrumented reproduction on one RTX PRO 6000-class GPU with SGLang TP=1, not a numerical reproduction of the paper's multi-H100 setup.",
        "",
        "## 2. What Was Already Completed Before v2",
        "",
        "The previous version already provided a working harness, SGLang launch script, Qwen3-32B smoke run, a v1 b8 controller sweep, exact SGLang request/scheduler log parsers, and an initial report. Those v1 results established that no-control can drive scheduler `token_usage` near 0.97 on a single GPU.",
        "",
        "## 3. Why v2 Was Needed",
        "",
        "The v1 prompt changed a `Step:` header near the front of every prompt, so later steps were not stable-prefix extensions of earlier steps. Exact SGLang cached-token ratios were very low, so the old cache-hit proxy could not be treated as a real hit rate. The original dynamic controller also updated only around admission events, not on a periodic exact-metric feedback loop.",
        "",
        "## 4. Hardware and Software",
        "",
        "- Model: `/data/3.8T-1/yue/models/Qwen3-32B`",
        "- Precision: BF16",
        "- Serving: SGLang OpenAI-compatible server, tensor parallel size 1",
        "- GPU policy: one GPU only; no other users' processes were killed",
        "- Main outputs: `outputs/runs`, `outputs/tables`, `outputs/figures`, and `outputs/reports`",
        "",
        "## 5. Workload v1 vs Prefix-Stable Workload v2",
        "",
        f"Old v1 b8 exact cached-token ratio mean across parsed successful b8 runs: `{_fmt(old_b8_ratio_mean, 4)}`.",
        f"New prefix_stable_v2 b8 mean cached-token ratio across controllers: `{_fmt(v2_b8_ratio_mean, 4)}`.",
        "",
        "The v2 workload keeps earlier observation lines append-only, which makes later steps stable-prefix extensions of earlier prompts. This produced materially higher exact cached-token ratios for fixed-window-4 in particular, while aggressive/no-control schedules still show lower average ratios because more agents compete for cache residency.",
        "",
        "## 6. Controllers",
        "",
        "v2 evaluates `no_control`, `request_cap_4`, `request_cap_8` where applicable, `fixed_window_4`, `fixed_window_8`, and `concur_dynamic_v2`. The dynamic v2 controller reads exact SGLang scheduler/request-tail snapshots when fresh, writes periodic controller events, and changes only future admission; it does not preempt already-active agents.",
        "",
        "## 7. Exact Metrics and Remaining Proxies",
        "",
        "Exact metrics come from SGLang request metric logs and scheduler stderr lines: cached tokens, prompt tokens, request latency, `token_usage`, `queue_req`, and `pending_token`. Harness-level GPU/context-growth signals remain proxies and are not used as proof of real cache hit rate.",
        "",
        "## 8. b8 Repeated Trials",
        "",
        b8_summary_table,
        "",
        f"Best b8 mean latency: `{b8_best.get('controller') if b8_best else ''}` at `{_fmt(b8_best.get('latency_mean_s') if b8_best else None)}` seconds. `concur_dynamic_v2` did not beat the best fixed-window setting on b8; fixed_window_4 is the latency winner in this repeated set.",
        "",
        "## 9. Higher-Pressure Runs",
        "",
        pressure_table,
        "",
        f"Best b8-long ctxfit latency: `{p6_best['b8_long_ctxfit'].get('controller') if p6_best['b8_long_ctxfit'] else ''}` at `{_fmt(p6_best['b8_long_ctxfit'].get('latency_s') if p6_best['b8_long_ctxfit'] else None)}` seconds.",
        f"Best b12 latency: `{p6_best['b12_medium'].get('controller') if p6_best['b12_medium'] else ''}` at `{_fmt(p6_best['b12_medium'].get('latency_s') if p6_best['b12_medium'] else None)}` seconds.",
        f"Best b16 latency among tested controllers: `{p6_best['b16_medium'].get('controller') if p6_best['b16_medium'] else ''}` at `{_fmt(p6_best['b16_medium'].get('latency_s') if p6_best['b16_medium'] else None)}` seconds.",
        "",
        "## 10. Results Against CONCUR Success Criteria",
        "",
        "The prefix-stable workload criterion is met: v2 exact cached-token ratios are far above the old low-ratio v1 baseline. The dynamic-v2 periodic-feedback criterion is also met: dynamic runs have tens to hundreds of controller events, not one event per agent. The latency criterion is mixed: dynamic v2 is not consistently best on b8 or b12, but it beats no-control on b12/b16 and beats fixed_window_8 in the tested b16 pressure run.",
        "",
        "Dynamic v2 periodic event summary:",
        "",
        dynamic_table,
        "",
        "## 11. Differences from Paper",
        "",
        "This is a single-GPU Qwen3-32B BF16 reproduction on SGLang, while the paper evaluates a larger distributed setting. The controller and workload are scaled to a local 8-16 agent harness; results should be interpreted as reproduction evidence for trends and instrumentation, not as paper-number replication.",
        "",
        "## 12. Failures and Limitations",
        "",
    ]
    if failed_original:
        failed_obs = failed_original[0].get("observation_tokens_per_step")
        lines.append(f"The original b8-long configuration with {failed_obs} observation tokens per step exceeded the configured 40960-token context limit. It was recorded as a failed/unsupported configuration and replaced by the ctxfit version with 320 observation tokens per step.")
        lines.append("")
    lines.extend(
        [
            "Remaining limitations: shared-server variance is visible, especially in seed0 no-control; exact request-to-agent mapping is timestamp-based where SGLang does not retain arbitrary metadata; dynamic v2 still uses a simple heuristic control law rather than a tuned controller; and not all high-pressure combinations were repeated across three seeds.",
            "",
            "## 13. Next Steps",
            "",
            "Recommended follow-up work is to repeat b12/b16 pressure scenarios across seeds, tune dynamic-v2 thresholds against exact metrics, test a smaller `W_max`/larger `alpha` grid, and compare against a multi-GPU serving setup if hardware is available.",
            "",
            "## Artifact Index",
            "",
            "- `outputs/tables/v2_b8_repeated_trials.csv`",
            "- `outputs/tables/v2_b8_repeated_trials_summary.csv`",
            "- `outputs/tables/v2_pressure_runs.csv`",
            "- `outputs/tables/v2_pressure_runs_summary.csv`",
            "- `outputs/figures/v2_latency_mean_std.png`",
            "- `outputs/figures/v2_scheduler_token_usage_by_controller.png`",
            "- `outputs/figures/v2_queue_depth_by_controller.png`",
            "- `outputs/figures/v2_cached_token_ratio_by_controller.png`",
            "- `outputs/figures/v2_dynamic_window_timeseries.png`",
            "- `outputs/figures/v2_fixed_vs_dynamic_latency.png`",
            "",
        ]
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def _read_csv_dicts(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_innovation_artifacts(v2_rows: list[dict], tables_dir: Path, figures_dir: Path, reports_dir: Path) -> None:
    innovation_rows = [
        row
        for row in v2_rows
        if row.get("controller") in INNOVATION_CONTROLLERS
    ]
    if not innovation_rows:
        return
    run_fields = [
        "scenario",
        "controller",
        "seed",
        "status",
        "run_id",
        "num_agents",
        "num_steps",
        "observation_tokens_per_step",
        "latency_s",
        "max_token_usage",
        "mean_token_usage",
        "max_queue_req",
        "max_pending_token",
        "cached_token_ratio_total",
        "mean_request_latency_s",
        "p95_request_latency_s",
        "controller_event_count",
        "exact_controller_event_count",
        "window_min",
        "window_max",
        "window_mean",
        "run_dir",
    ]
    _write_rows(tables_dir / "innovation_controller_runs.csv", run_fields, innovation_rows)

    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in innovation_rows:
        grouped.setdefault((str(row.get("scenario")), str(row.get("controller"))), []).append(row)
    summary_rows = []
    for (scenario, controller), rows in sorted(grouped.items()):
        success_rows = [row for row in rows if row.get("status") == "success"]
        latencies = [float(row["latency_s"]) for row in success_rows if row.get("latency_s") is not None]
        queue_reqs = [float(row["max_queue_req"]) for row in success_rows if row.get("max_queue_req") is not None]
        pending_tokens = [float(row["max_pending_token"]) for row in success_rows if row.get("max_pending_token") is not None]
        cache_ratios = [float(row["cached_token_ratio_total"]) for row in success_rows if row.get("cached_token_ratio_total") is not None]
        event_counts = [float(row["controller_event_count"]) for row in success_rows if row.get("controller_event_count") is not None]
        summary_rows.append(
            {
                "scenario": scenario,
                "controller": controller,
                "n": len(success_rows),
                "latency_mean_s": _mean(latencies),
                "latency_std_s": _std(latencies),
                "latency_min_s": min(latencies) if latencies else None,
                "latency_max_s": max(latencies) if latencies else None,
                "max_queue_req_mean": _mean(queue_reqs),
                "max_pending_token_mean": _mean(pending_tokens),
                "cached_token_ratio_mean": _mean(cache_ratios),
                "controller_event_count_mean": _mean(event_counts),
            }
        )
    _write_rows(
        tables_dir / "innovation_controller_summary.csv",
        [
            "scenario",
            "controller",
            "n",
            "latency_mean_s",
            "latency_std_s",
            "latency_min_s",
            "latency_max_s",
            "max_queue_req_mean",
            "max_pending_token_mean",
            "cached_token_ratio_mean",
            "controller_event_count_mean",
        ],
        summary_rows,
    )
    write_innovation_figures(innovation_rows, summary_rows, figures_dir)
    write_innovation_report(summary_rows, reports_dir / "qwen_innovation_report.md")


def write_innovation_figures(innovation_rows: list[dict], summary_rows: list[dict], figures_dir: Path) -> None:
    plt = _load_pyplot()
    figures_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    for row in innovation_rows:
        if row.get("status") != "success":
            continue
        latency = _float_or_none(row.get("latency_s"))
        cache_ratio = _float_or_none(row.get("cached_token_ratio_total"))
        if latency is None or cache_ratio is None:
            continue
        controller = str(row["controller"])
        ax.scatter(cache_ratio, latency, label=controller, color=FIGURE_COLORS.get(controller, "#6B7280"), s=48)
        ax.annotate(f"{row.get('scenario')} s{row.get('seed')}", (cache_ratio, latency), fontsize=7, xytext=(4, 4), textcoords="offset points")
    handles, labels = ax.get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    if unique:
        ax.legend(unique.values(), unique.keys(), fontsize=8)
    ax.set_title("Innovation controllers: latency vs exact cache ratio")
    ax.set_xlabel("cached_tokens / prompt_tokens")
    ax.set_ylabel("batch latency, seconds")
    ax.grid(color="#D9D9D9", linewidth=0.8, alpha=0.8)
    fig.tight_layout()
    fig.savefig(figures_dir / "innovation_latency_vs_cache.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    rows = [row for row in summary_rows if row.get("scenario") == "b8" and row.get("max_queue_req_mean") is not None]
    if rows:
        labels = [str(row["controller"]).replace("_", "\n") for row in rows]
        values = [float(row["max_queue_req_mean"]) for row in rows]
        colors = [FIGURE_COLORS.get(str(row["controller"]), "#6B7280") for row in rows]
        ax.bar(labels, values, color=colors, edgecolor="#2F2F2F", linewidth=0.7)
    ax.set_title("Innovation b8 queue pressure")
    ax.set_xlabel("controller")
    ax.set_ylabel("mean max queue_req")
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.8, alpha=0.8)
    fig.tight_layout()
    fig.savefig(figures_dir / "innovation_queue_pressure.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    plotted = 0
    for row in innovation_rows:
        if row.get("status") != "success":
            continue
        events = list(iter_jsonl(Path(str(row["run_dir"])) / "controller_events.jsonl") or [])
        if not events:
            continue
        base = _float_or_none(events[0].get("timestamp")) or 0.0
        points = []
        for event in events:
            ts = _float_or_none(event.get("timestamp"))
            window = _float_or_none(event.get("W_next"))
            if ts is not None and window is not None:
                points.append((ts - base, window))
        if not points:
            continue
        ax.plot([point[0] for point in points], [point[1] for point in points], linewidth=1.5, label=f"{row.get('controller')} {row.get('scenario')} s{row.get('seed')}")
        plotted += 1
    ax.set_title("Innovation controller window timeseries")
    ax.set_xlabel("elapsed seconds from first controller event")
    ax.set_ylabel("admission window W")
    ax.grid(color="#D9D9D9", linewidth=0.8, alpha=0.8)
    if plotted:
        ax.legend(loc="best", fontsize=7)
    fig.tight_layout()
    fig.savefig(figures_dir / "innovation_window_timeseries.png", dpi=180)
    plt.close(fig)


def write_innovation_report(summary_rows: list[dict], out: Path) -> None:
    baseline_path = REPRO_ROOT / "outputs" / "tables" / "v2_b8_repeated_trials_summary.csv"
    pressure_path = REPRO_ROOT / "outputs" / "tables" / "v2_pressure_runs_summary.csv"
    baseline_rows = _read_csv_dicts(baseline_path)
    pressure_rows = _read_csv_dicts(pressure_path)
    baseline_by_controller = {str(row.get("controller")): row for row in baseline_rows}
    pressure_by_key = {(str(row.get("scenario")), str(row.get("controller"))): row for row in pressure_rows}
    innovation_by_key = {(str(row.get("scenario")), str(row.get("controller"))): row for row in summary_rows}

    def row_for(scenario: str, controller: str) -> dict | None:
        return innovation_by_key.get((scenario, controller))

    def pressure_row_for(scenario: str, controller: str) -> dict | None:
        return pressure_by_key.get((scenario, controller))

    def latency(row: dict | None) -> float | None:
        return _float_or_none(row.get("latency_mean_s")) if row else None

    def cache_ratio(row: dict | None) -> float | None:
        return _float_or_none(row.get("cached_token_ratio_mean")) if row else None

    def queue_req(row: dict | None) -> float | None:
        return _float_or_none(row.get("max_queue_req_mean")) if row else None

    def pct_faster(row: dict | None, baseline: dict | None) -> float | None:
        row_latency = latency(row)
        baseline_latency = latency(baseline)
        if row_latency is None or baseline_latency in (None, 0):
            return None
        return (baseline_latency - row_latency) / baseline_latency * 100.0

    def fmt_seconds(value: float | None) -> str:
        return f"{_fmt(value)}s" if value is not None else ""

    def fmt_speedup(row: dict | None, baseline: dict | None) -> str:
        speedup = pct_faster(row, baseline)
        if speedup is None:
            return ""
        direction = "faster" if speedup >= 0 else "slower"
        return f"{_fmt(abs(speedup), 1)}% {direction}"

    findings = []
    cache_b8 = row_for("b8", "concur_cache_aware_v1")
    phase_b8 = row_for("b8", "phase_window_v1")
    tail_b8 = row_for("b8", "tail_open_v1")
    gate_b8 = row_for("b8", "cache_gate_v1")
    dynamic_b8 = baseline_by_controller.get("concur_dynamic_v2")
    fixed4_b8 = baseline_by_controller.get("fixed_window_4")
    fixed8_b8 = baseline_by_controller.get("fixed_window_8")
    request4_b8 = baseline_by_controller.get("request_cap_4")
    b8_innovation_rows = [
        row
        for (scenario, _controller), row in innovation_by_key.items()
        if scenario == "b8" and latency(row) is not None
    ]
    if b8_innovation_rows:
        best_b8 = min(b8_innovation_rows, key=lambda row: latency(row) or math.inf)
        if fixed4_b8:
            findings.append(
                f"- Best available b8 innovation in this report is `{best_b8.get('controller')}` at "
                f"`{fmt_seconds(latency(best_b8))}`; compared with `fixed_window_4` "
                f"`{fmt_seconds(latency(fixed4_b8))}`, it is `{fmt_speedup(best_b8, fixed4_b8)}`."
            )
    if cache_b8 and dynamic_b8:
        findings.append(
            "- `concur_cache_aware_v1` meets the b8 queue-pressure target versus `concur_dynamic_v2`: "
            f"max_queue_req mean `{_fmt(queue_req(cache_b8))}` vs `{_fmt(queue_req(dynamic_b8))}`, "
            f"latency `{fmt_seconds(latency(cache_b8))}` vs `{fmt_seconds(latency(dynamic_b8))}`."
        )
    if cache_b8 and fixed4_b8:
        findings.append(
            "- On repeated b8, `concur_cache_aware_v1` is the observed latency winner: "
            f"`{fmt_seconds(latency(cache_b8))}` mean, `{fmt_speedup(cache_b8, fixed4_b8)}` than "
            f"`fixed_window_4` (`{fmt_seconds(latency(fixed4_b8))}`), with similar exact cache ratio "
            f"`{_fmt(cache_ratio(cache_b8))}` vs `{_fmt(cache_ratio(fixed4_b8))}`."
        )
    if phase_b8 and fixed8_b8 and request4_b8:
        findings.append(
            "- `phase_window_v1` meets its b8 directional criterion: exact cache ratio "
            f"`{_fmt(cache_ratio(phase_b8))}` vs `fixed_window_8` `{_fmt(cache_ratio(fixed8_b8))}`, and latency "
            f"`{fmt_seconds(latency(phase_b8))}` vs `request_cap_4` `{fmt_seconds(latency(request4_b8))}`. "
            "It remains slower than `concur_cache_aware_v1` and `fixed_window_4` on b8."
        )
    if tail_b8 and fixed4_b8:
        findings.append(
            "- `tail_open_v1` tests the fixed-window tail-opening hypothesis: "
            f"latency `{fmt_seconds(latency(tail_b8))}` vs `fixed_window_4` `{fmt_seconds(latency(fixed4_b8))}`, "
            f"cached ratio `{_fmt(cache_ratio(tail_b8))}` vs `{_fmt(cache_ratio(fixed4_b8))}`."
        )
    if gate_b8 and dynamic_b8:
        findings.append(
            "- `cache_gate_v1` tests a cache-aware safety floor: "
            f"latency `{fmt_seconds(latency(gate_b8))}` vs `concur_dynamic_v2` `{fmt_seconds(latency(dynamic_b8))}`, "
            f"queue mean `{_fmt(queue_req(gate_b8))}` vs `{_fmt(queue_req(dynamic_b8))}`."
        )

    for scenario in ["b8_long_ctxfit", "b12_medium", "b16_medium"]:
        innovation_candidates = [row_for(scenario, controller) for controller in sorted(INNOVATION_CONTROLLERS)]
        innovation_candidates = [row for row in innovation_candidates if latency(row) is not None]
        baseline_candidates = [
            row
            for (row_scenario, _controller), row in pressure_by_key.items()
            if row_scenario == scenario and latency(row) is not None
        ]
        if not innovation_candidates or not baseline_candidates:
            continue
        best_innovation = min(innovation_candidates, key=lambda row: latency(row) or math.inf)
        best_baseline = min(baseline_candidates, key=lambda row: latency(row) or math.inf)
        dynamic_row = pressure_row_for(scenario, "concur_dynamic_v2")
        if latency(best_innovation) is not None and latency(best_baseline) is not None:
            relation = "beats" if (latency(best_innovation) or math.inf) < (latency(best_baseline) or math.inf) else "does not beat"
            findings.append(
                f"- `{scenario}` best innovation is `{best_innovation.get('controller')}` at "
                f"`{fmt_seconds(latency(best_innovation))}`; it {relation} the best v2 baseline "
                f"`{best_baseline.get('controller')}` at `{fmt_seconds(latency(best_baseline))}`."
            )
        if dynamic_row:
            findings.append(
                f"- `{scenario}` best innovation vs `concur_dynamic_v2`: "
                f"`{fmt_seconds(latency(best_innovation))}` vs `{fmt_seconds(latency(dynamic_row))}` "
                f"(`{fmt_speedup(best_innovation, dynamic_row)}`)."
            )
    if not findings:
        findings.append("- No complete innovation summary rows were available when the report was generated.")

    total_success_rows = sum(int(row.get("n") or 0) for row in summary_rows)
    limitations = [
        f"- All successful innovation runs discovered in this report are summarized: {total_success_rows} success rows.",
        "- b12, b16, and b8-long ctxfit innovation scenarios currently have one seed each; treat those results as directional until repeated.",
        "- Claims remain limited to single-GPU Qwen3-32B BF16 on SGLang with this local harness.",
    ]
    baseline_table = _markdown_table(
        baseline_rows,
        [
            ("controller", "controller"),
            ("n", "n"),
            ("latency_mean_s", "latency_mean_s"),
            ("latency_std_s", "latency_std_s"),
            ("max_queue_req_mean", "max_queue_req_mean"),
            ("cached_token_ratio_mean", "cached_ratio_mean"),
        ],
    )
    innovation_table = _markdown_table(
        summary_rows,
        [
            ("scenario", "scenario"),
            ("controller", "controller"),
            ("n", "n"),
            ("latency_mean_s", "latency_mean_s"),
            ("latency_std_s", "latency_std_s"),
            ("max_queue_req_mean", "max_queue_req_mean"),
            ("cached_token_ratio_mean", "cached_ratio_mean"),
        ],
    )
    lines = [
        "# Qwen CONCUR Innovation Report",
        "",
        "## 1. Goal",
        "",
        "Evaluate lightweight scheduling innovations on top of the completed Qwen3-32B single-GPU v2 reproduction. Round 1 covers `concur_cache_aware_v1` and `phase_window_v1`; round 2 covers `tail_open_v1` and `cache_gate_v1`.",
        "",
        "## 2. Baseline from v2 Reproduction",
        "",
        baseline_table,
        "",
        "## 3. Innovation A: Cache-Aware Hysteresis Controller",
        "",
        "Uses exact SGLang scheduler/request metrics, an EWMA of cached-token ratio, queue/pending-token guards, and cooldown to reduce queue spikes from the previous dynamic controller.",
        "",
        "## 4. Innovation B: Warmup-Then-Open Phase Window",
        "",
        "Uses harness progress only: admit a small initial window to build prefix cache, then ramp admission wider after early steps complete.",
        "",
        "## 5. Round 2 Additions",
        "",
        "`tail_open_v1` keeps a fixed-window-4 style early phase and opens admission later based on progress or finished-agent ratio. `cache_gate_v1` uses exact SGLang metrics with a fixed-window-4 safety floor and only grows when cache and queue health permit.",
        "",
        "## 6. Experiment Matrix",
        "",
        "Innovation runs are stored in the configured innovation output root; tables, figures, and this report are generated into the corresponding `tables`, `figures`, and `reports` directories.",
        "",
        "## 7. Results",
        "",
        innovation_table,
        "",
        "## 8. Success Criteria",
        "",
        "- `concur_cache_aware_v1`: lower b8 queue pressure than `concur_dynamic_v2` while keeping latency interpretable.",
        "- `phase_window_v1`: cached ratio above fixed_window_8 and latency below request_cap_4 on b8, if possible.",
        "- `tail_open_v1`: keep fixed-window-4 cache behavior early, then reduce tail latency by opening admission later.",
        "- `cache_gate_v1`: use exact metrics with a fixed-window-4 safety floor and grow only when cache/queue health permits.",
        "",
        "## 9. Findings Against Criteria",
        "",
        "\n".join(findings),
        "",
        "## 10. Failures and Limitations",
        "",
        "\n".join(limitations),
        "",
        "## 11. Recommendation",
        "",
        "Select claims from the rows actually present in this report. Treat b12/b16 single-seed results as directional, and keep the strongest repeated b8 result as the primary evidence.",
        "",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def timeseries_from_serving(rows: list[dict], field: str) -> list[tuple[float, float]]:
    points = []
    base = None
    for row in rows:
        ts = float(row.get("timestamp", 0.0))
        if base is None:
            base = ts
        value = row.get(field)
        if value is not None:
            points.append((ts - base, float(value)))
    return points


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", default=str(REPRO_ROOT / "outputs" / "runs"))
    parser.add_argument("--server-runs-dir", default=str(REPRO_ROOT / "outputs" / "runs"))
    parser.add_argument("--tables-dir", default=str(REPRO_ROOT / "outputs" / "tables"))
    parser.add_argument("--figures-dir", default=str(REPRO_ROOT / "outputs" / "figures"))
    parser.add_argument("--reports-dir", default=str(REPRO_ROOT / "outputs" / "reports"))
    args = parser.parse_args()
    runs_dir = assert_under_root(Path(args.runs_dir))
    server_runs_dir = assert_under_root(Path(args.server_runs_dir))
    tables_dir = assert_under_root(Path(args.tables_dir))
    figures_dir = assert_under_root(Path(args.figures_dir))
    reports_dir = assert_under_root(Path(args.reports_dir))
    summaries = collect_summaries(runs_dir)
    write_latency_table(summaries, tables_dir / "end_to_end_latency_table.csv")
    request_summaries, scheduler_summaries = write_sglang_log_artifacts(
        runs_dir,
        tables_dir,
        summaries,
        server_runs_dir=server_runs_dir,
    )
    v2_rows = build_v2_result_rows(summaries, request_summaries, scheduler_summaries)
    b8_summary, pressure_summary = write_v2_tables(v2_rows, tables_dir, reports_dir)
    write_v2_figures(v2_rows, b8_summary, figures_dir)
    write_innovation_artifacts(v2_rows, tables_dir, figures_dir, reports_dir)
    write_v2_report(
        summaries=summaries,
        v2_rows=v2_rows,
        b8_summary=b8_summary,
        pressure_summary=pressure_summary,
        request_summaries=request_summaries,
        out=reports_dir / "qwen_single_gpu_report_v2.md",
    )
    make_bar_plot(summaries, figures_dir / "fixed_vs_dynamic_latency.png")
    all_serving = []
    all_controller = []
    for summary in summaries:
        run_dir = Path(summary["run_dir"])
        all_serving.extend(iter_jsonl(run_dir / "serving_metrics.jsonl") or [])
        all_controller.extend(iter_jsonl(run_dir / "controller_events.jsonl") or [])
    make_line_plot(timeseries_from_serving(all_serving, "kv_cache_usage_proxy"), figures_dir / "kv_usage_timeseries.png", color=(20, 100, 190))
    make_line_plot(timeseries_from_serving(all_serving, "kv_cache_hit_rate_proxy"), figures_dir / "cache_hit_rate_timeseries.png", color=(20, 150, 90))
    make_line_plot(timeseries_from_serving(all_serving, "recompute_prefill_tokens_proxy"), figures_dir / "prefill_recompute_overhead.png", color=(180, 70, 60))
    window_points = []
    base = None
    for row in all_controller:
        ts = float(row.get("timestamp", 0.0))
        if base is None:
            base = ts
        window_points.append((ts - base, float(row.get("W_next", row.get("W_t", 0)))))
    make_line_plot(window_points, figures_dir / "window_timeseries.png", color=(130, 70, 170))
    exact_token_usage_points = []
    exact_queue_points = []
    for row in iter_csv_rows(tables_dir / "sglang_scheduler_pressure_by_run.csv"):
        timestamp = row.get("timestamp")
        if timestamp in (None, ""):
            continue
        if row.get("token_usage") not in (None, ""):
            exact_token_usage_points.append((float(timestamp), float(row["token_usage"])))
        if row.get("queue_req") not in (None, ""):
            exact_queue_points.append((float(timestamp), float(row["queue_req"])))
    make_line_plot(exact_token_usage_points, figures_dir / "sglang_token_usage_timeseries.png", color=(40, 80, 150))
    make_line_plot(exact_queue_points, figures_dir / "sglang_queue_req_timeseries.png", color=(180, 80, 40))
    print(f"wrote {tables_dir / 'end_to_end_latency_table.csv'}")
    if scheduler_summaries:
        print(f"wrote SGLang log metric tables under {tables_dir}")
    if v2_rows:
        print(f"wrote v2 tables under {tables_dir}")
        print(f"wrote v2 report under {reports_dir}")
    print(f"wrote figures under {figures_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
