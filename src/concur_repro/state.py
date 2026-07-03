from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import json
import os

from .config import REPRO_ROOT, assert_under_root

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


LOCAL_TZ = ZoneInfo("Asia/Shanghai")
REPORTS_DIR = REPRO_ROOT / "outputs" / "reports"
HEARTBEAT_PATH = REPORTS_DIR / "heartbeat.json"
RUN_LOCK_PATH = REPORTS_DIR / "run_lock.json"
ACTIVE_RUN_PATH = REPORTS_DIR / "active_run.json"
LEGACY_HEARTBEAT_PATH = REPRO_ROOT / "heartbeat.json"
LEGACY_RUN_LOCK_PATH = REPRO_ROOT / "run_lock.json"
LEGACY_ACTIVE_RUN_PATH = REPRO_ROOT / "active_run.json"
QUEUE_PATH = assert_under_root(Path(os.environ.get("CONCUR_QUEUE_PATH", str(REPRO_ROOT / "experiment_queue.yaml"))))
EXECUTION_LOG_PATH = REPRO_ROOT / "outputs" / "reports" / "codex_execution_log.md"


def now_iso() -> str:
    return datetime.now(LOCAL_TZ).isoformat(timespec="seconds")


def atomic_write_text(path: str | Path, text: str) -> None:
    out = assert_under_root(Path(path))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, out)


def atomic_write_json(path: str | Path, data: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def atomic_write_json_many(paths: list[str | Path], data: dict[str, Any]) -> None:
    for path in paths:
        atomic_write_json(path, data)


def atomic_write_yaml(path: str | Path, data: dict[str, Any]) -> None:
    if yaml is None:
        atomic_write_json(path, data)
        return
    atomic_write_text(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def append_execution_log(message: str, *, phase: str | None = None, run_id: str | None = None) -> None:
    prefix = f"- {now_iso()}"
    parts = []
    if phase:
        parts.append(f"阶段={phase}")
    if run_id:
        parts.append(f"run={run_id}")
    if parts:
        prefix += " " + " ".join(parts)
    out = assert_under_root(EXECUTION_LOG_PATH)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(f"{prefix}：{message}\n")


def update_heartbeat(*, active: bool, phase: str, message: str, run_id: str | None = None) -> None:
    data = {
        "active": active,
        "last_update": now_iso(),
        "phase": phase,
        "message": message,
        "run_id": run_id,
    }
    atomic_write_json_many([HEARTBEAT_PATH, LEGACY_HEARTBEAT_PATH], data)


def update_run_lock(*, locked: bool, phase: str, reason: str, run_id: str | None = None) -> None:
    data = {
        "locked": locked,
        "owner": "codex",
        "phase": phase,
        "reason": reason,
        "run_id": run_id,
        "updated_at": now_iso(),
    }
    atomic_write_json_many([RUN_LOCK_PATH, LEGACY_RUN_LOCK_PATH], data)


def update_active_run(
    *,
    active: bool,
    phase: str,
    run_id: str | None = None,
    run_dir: str | None = None,
    config_path: str | None = None,
    started_at: str | None = None,
) -> None:
    data = {
        "active": active,
        "phase": phase,
        "run_id": run_id,
        "run_dir": run_dir,
        "config_path": config_path,
        "started_at": started_at,
        "updated_at": now_iso(),
    }
    atomic_write_json_many([ACTIVE_RUN_PATH, LEGACY_ACTIVE_RUN_PATH], data)


def read_queue() -> dict[str, Any]:
    if not QUEUE_PATH.exists():
        return {"pending": [], "running": None, "done": [], "failed": []}
    text = QUEUE_PATH.read_text(encoding="utf-8")
    if yaml is None:
        data = json.loads(text)
    else:
        data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("pending", [])
    data.setdefault("running", None)
    data.setdefault("done", [])
    data.setdefault("failed", [])
    return data


def write_queue(data: dict[str, Any]) -> None:
    data.setdefault("pending", [])
    data.setdefault("running", None)
    data.setdefault("done", [])
    data.setdefault("failed", [])
    data["updated_at"] = now_iso()
    atomic_write_yaml(QUEUE_PATH, data)


def set_queue_running(item: dict[str, Any] | None) -> None:
    queue = read_queue()
    queue["running"] = item
    write_queue(queue)


def update_queue_running_fields(fields: dict[str, Any]) -> None:
    queue = read_queue()
    item = queue.get("running")
    if isinstance(item, dict):
        merged = dict(item)
        merged.update(fields)
        queue["running"] = merged
    else:
        queue["running"] = dict(fields)
    write_queue(queue)


def queue_start_next() -> dict[str, Any] | None:
    queue = read_queue()
    running = queue.get("running")
    if isinstance(running, dict):
        return running
    pending = list(queue.get("pending") or [])
    if not pending:
        queue["running"] = None
        write_queue(queue)
        return None
    item = pending.pop(0)
    item = dict(item)
    item["started_at"] = now_iso()
    queue["pending"] = pending
    queue["running"] = item
    write_queue(queue)
    return item


def queue_finish_running(status: str, status_note: str, run_id: str | None = None) -> None:
    queue = read_queue()
    item = queue.get("running")
    if isinstance(item, dict):
        done_item = dict(item)
    else:
        done_item = {"name": "unknown"}
    done_item["finished_at"] = now_iso()
    done_item["status_note"] = status_note
    if run_id:
        done_item["run_id"] = run_id
    queue["running"] = None
    target = "done" if status == "done" else "failed"
    queue.setdefault(target, [])
    queue[target].append(done_item)
    write_queue(queue)
