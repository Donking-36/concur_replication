from __future__ import annotations

from pathlib import Path
import argparse
import csv
import json
import math
import struct
import zlib

from .config import REPRO_ROOT, assert_under_root, read_config
from .metadata import controller_metadata
from .sglang_logs import write_sglang_log_artifacts


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
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
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
    parser.add_argument("--tables-dir", default=str(REPRO_ROOT / "outputs" / "tables"))
    parser.add_argument("--figures-dir", default=str(REPRO_ROOT / "outputs" / "figures"))
    args = parser.parse_args()
    runs_dir = assert_under_root(Path(args.runs_dir))
    tables_dir = assert_under_root(Path(args.tables_dir))
    figures_dir = assert_under_root(Path(args.figures_dir))
    summaries = collect_summaries(runs_dir)
    write_latency_table(summaries, tables_dir / "end_to_end_latency_table.csv")
    _, scheduler_summaries = write_sglang_log_artifacts(runs_dir, tables_dir, summaries)
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
    print(f"wrote figures under {figures_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
