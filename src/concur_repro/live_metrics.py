from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo
import json
import re
import time

from .config import REPRO_ROOT, assert_under_root


LOCAL_TZ = ZoneInfo("Asia/Shanghai")
LOG_LINE_RE = re.compile(r"^\[(?P<stamp>[^\]]+)\] (?P<kind>Prefill|Decode) batch, (?P<body>.*)$")


@dataclass(frozen=True)
class LiveMetricSnapshot:
    timestamp: float
    scheduler_points: int
    request_count: int
    token_usage: float | None
    running_req: int | None
    queue_req: int | None
    pending_token: int | None
    cached_token_ratio: float | None
    recent_cached_token_ratio: float | None
    source: str


def latest_server_run_dir() -> Path | None:
    marker = REPRO_ROOT / "outputs" / "reports" / "latest_sglang_server_run_dir.txt"
    if not marker.exists():
        return None
    text = marker.read_text(encoding="utf-8").strip()
    if not text:
        return None
    path = assert_under_root(Path(text))
    return path if path.exists() else None


def _parse_log_timestamp(value: str) -> float:
    dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=LOCAL_TZ).timestamp()


def _metric(body: str, pattern: str, cast):
    match = re.search(pattern, body)
    if not match:
        return None
    return cast(match.group(1))


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


class SGLangLiveMetrics:
    def __init__(self, server_run_dir: Path | None, run_start_ts: float, recent_window_s: float = 30.0) -> None:
        self.server_run_dir = assert_under_root(server_run_dir) if server_run_dir is not None else latest_server_run_dir()
        self.run_start_ts = run_start_ts
        self.recent_window_s = recent_window_s

    def read(self) -> LiveMetricSnapshot:
        now = time.time()
        scheduler_rows = self._read_scheduler_rows()
        request_rows = self._read_request_rows(now)
        latest = scheduler_rows[-1] if scheduler_rows else {}
        prompt_total = sum(row["prompt_tokens"] for row in request_rows)
        cached_total = sum(row["cached_tokens"] for row in request_rows)
        recent_rows = [row for row in request_rows if row["request_received_ts"] >= now - self.recent_window_s]
        recent_prompt = sum(row["prompt_tokens"] for row in recent_rows)
        recent_cached = sum(row["cached_tokens"] for row in recent_rows)
        source = str(self.server_run_dir) if self.server_run_dir is not None else "missing_server_run_dir"
        return LiveMetricSnapshot(
            timestamp=now,
            scheduler_points=len(scheduler_rows),
            request_count=len(request_rows),
            token_usage=_safe_float(latest.get("token_usage")),
            running_req=_safe_int(latest.get("running_req")),
            queue_req=_safe_int(latest.get("queue_req")),
            pending_token=_safe_int(latest.get("pending_token")),
            cached_token_ratio=_ratio(cached_total, prompt_total) if request_rows else None,
            recent_cached_token_ratio=_ratio(recent_cached, recent_prompt) if recent_rows else None,
            source=source,
        )

    def _read_scheduler_rows(self) -> list[dict[str, Any]]:
        if self.server_run_dir is None:
            return []
        log_path = self.server_run_dir / "sglang_server.stderr.log"
        if not log_path.exists():
            return []
        rows = []
        with log_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                match = LOG_LINE_RE.match(line.strip())
                if not match:
                    continue
                timestamp = _parse_log_timestamp(match.group("stamp"))
                if timestamp < self.run_start_ts:
                    continue
                body = match.group("body")
                rows.append(
                    {
                        "timestamp": timestamp,
                        "token_usage": _metric(body, r"token usage: ([0-9.]+)", float),
                        "running_req": _metric(body, r"#running-req: ([0-9]+)", int),
                        "queue_req": _metric(body, r"#queue-req: ([0-9]+)", int),
                        "pending_token": _metric(body, r"#pending-token: ([0-9]+)", int),
                    }
                )
        rows.sort(key=lambda row: row["timestamp"])
        return rows

    def _read_request_rows(self, now: float) -> list[dict[str, Any]]:
        if self.server_run_dir is None:
            return []
        metrics_dir = self.server_run_dir / "sglang_metrics"
        if not metrics_dir.exists():
            return []
        rows = []
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
                    received_ts = _safe_float(record.get("request_received_ts"))
                    if received_ts is None or received_ts < self.run_start_ts or received_ts > now + 60.0:
                        continue
                    rows.append(
                        {
                            "request_received_ts": received_ts,
                            "prompt_tokens": _safe_int(record.get("prompt_tokens")) or 0,
                            "cached_tokens": _safe_int(record.get("cached_tokens")) or 0,
                        }
                    )
        rows.sort(key=lambda row: row["request_received_ts"])
        return rows
