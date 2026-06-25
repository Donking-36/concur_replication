from __future__ import annotations

from pathlib import Path
from typing import Any
import json


try:
    import yaml
except Exception:  # pragma: no cover - fallback for stripped environments
    yaml = None


ROOT = Path("/data/3.8T-1/yue").resolve()
REPRO_ROOT = ROOT / "concur_qwen_repro"


def assert_under_root(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved != ROOT and ROOT not in resolved.parents:
        raise ValueError(f"path outside allowed root: {resolved}")
    return resolved


def read_config(path: str | Path) -> dict[str, Any]:
    cfg_path = assert_under_root(Path(path))
    text = cfg_path.read_text(encoding="utf-8-sig")
    if cfg_path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        if yaml is None:
            raise RuntimeError("PyYAML is required for YAML config files")
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"config must be a mapping: {cfg_path}")
    return data


def write_config(path: str | Path, data: dict[str, Any]) -> None:
    out = assert_under_root(Path(path))
    out.parent.mkdir(parents=True, exist_ok=True)
    if yaml is None:
        out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    out.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def append_jsonl(path: str | Path, row: dict[str, Any]) -> None:
    out = assert_under_root(Path(path))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def now_ts() -> float:
    import time

    return time.time()

