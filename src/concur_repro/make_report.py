from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .analyze import collect_summaries
from .config import REPRO_ROOT, assert_under_root


def read_text(path: Path, default: str = "") -> str:
    return path.read_text(encoding="utf-8") if path.exists() else default


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def fmt_float(value: str | None, digits: int = 3) -> str:
    if value in (None, ""):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_metric(value: str | None, digits: int = 3, suffix: str = "") -> str:
    text = fmt_float(value, digits)
    return f"`{text}{suffix}`" if text else "`n/a`"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPRO_ROOT / "outputs" / "reports" / "qwen_single_gpu_report.md"))
    args = parser.parse_args()
    out = assert_under_root(Path(args.out))
    runs_dir = REPRO_ROOT / "outputs" / "runs"
    summaries = collect_summaries(runs_dir)
    env_report = read_text(REPRO_ROOT / "outputs" / "reports" / "env_report.txt")
    scheduler_summaries = {
        row["run_id"]: row
        for row in read_csv_rows(REPRO_ROOT / "outputs" / "tables" / "sglang_scheduler_summary_by_run.csv")
    }
    request_summaries = {
        row["run_id"]: row
        for row in read_csv_rows(REPRO_ROOT / "outputs" / "tables" / "sglang_request_summary_by_run.csv")
    }
    rows = []
    exact_rows = []
    by_controller = {}
    for s in summaries:
        status = s.get("status", "")
        latency = s.get("end_to_end_batch_latency_s")
        latency_text = f"{float(latency):.3f}" if latency is not None else ""
        rows.append(
            "| {run_id} | {status} | {backend} | {controller} | {num_agents} | {num_steps} | {latency} | {excluded} |".format(
                run_id=s.get("run_id", ""),
                status=status,
                backend=s.get("backend", ""),
                controller=s.get("controller_label") or s.get("strategy", ""),
                num_agents=s.get("num_agents", ""),
                num_steps=s.get("num_steps", ""),
                latency=latency_text,
                excluded=s.get("mock_result_excluded_from_qwen_claims", ""),
            )
        )
        if s.get("backend") == "openai" and s.get("status") == "success":
            by_controller[str(s.get("controller_label") or s.get("strategy") or "")] = s
        if s.get("backend") == "openai" and s.get("status") == "success":
            scheduler = scheduler_summaries.get(str(s.get("run_id"))) or {}
            request = request_summaries.get(str(s.get("run_id"))) or {}
            exact_rows.append(
                "| {controller} | {requests} | {max_token_usage} | {max_queue_req} | {max_pending_token} | {cached_ratio} | {p95_request_latency} |".format(
                    controller=s.get("controller_label") or s.get("strategy", ""),
                    requests=request.get("request_count", ""),
                    max_token_usage=fmt_float(scheduler.get("max_token_usage"), 2),
                    max_queue_req=scheduler.get("max_queue_req", ""),
                    max_pending_token=scheduler.get("max_pending_token", ""),
                    cached_ratio=fmt_float(request.get("cached_token_ratio_total"), 4),
                    p95_request_latency=fmt_float(request.get("p95_e2e_latency_s"), 3),
                )
            )
    def run_for(controller: str) -> dict:
        return by_controller.get(controller, {})

    def scheduler_for(controller: str) -> dict[str, str]:
        run = run_for(controller)
        return scheduler_summaries.get(str(run.get("run_id")), {})

    def latency_for(controller: str) -> str | None:
        value = run_for(controller).get("end_to_end_batch_latency_s")
        return str(value) if value not in (None, "") else None

    def sched_value(controller: str, field: str) -> str | None:
        value = scheduler_for(controller).get(field)
        return value if value not in (None, "") else None

    report = f"""# CONCUR Qwen Single-GPU Reproduction Report

## 1. Scope

- Qwen only, no DeepSeek.
- Single RTX PRO 6000 GPU.
- Tensor parallel size target: TP=1.
- This report separates real Qwen runs from mock engineering-validation runs.

## 2. Hardware and Software

Environment snapshot is recorded in `outputs/reports/env_report.txt`.

```text
{env_report[:4000]}
```

## 3. Model

- Primary candidate: `/data/3.8T-1/yue/models/Qwen3-32B`.
- Precision used for real runs: BF16.
- Qwen3-32B BF16 served successfully on one visible GPU with SGLang TP=1; no quantized or smaller-Qwen fallback was needed for the completed real runs.

## 4. Workload

Synthetic agentic workload:

- Each agent alternates LLM generation, synthetic tool wait, and synthetic observation append.
- Context length proxy grows monotonically by step.
- Agent observations and tool wait durations differ by agent and step.

## 5. Strategies

- `no_control`
- `request_cap`
- `fixed_window`
- `concur_dynamic`

## 6. Metrics

The local SGLang/Torch environment is repaired and real Qwen requests are served. Current structured harness outputs record:

- End-to-end batch latency.
- Mean and p95 agent latency.
- GPU metrics from `nvidia-smi` where available.
- Proxy KV cache usage, hit rate, prefill tokens, and recompute prefill tokens.

SGLang log parsing now additionally records exact server-emitted request and scheduler signals:

- Per-request prompt tokens, completion tokens, cached tokens, queue time, and request latency.
- Scheduler token usage, running request count, queued request count, pending tokens, prefill batches, and decode batches.
- Exact SGLang token usage and queue-depth figures generated from scheduler logs.

The remaining gap is block-level cache allocation, eviction, and HiCache internals; generated KV/hit-rate figures still include proxy fields where the harness does not receive exact block-level values.

See `outputs/reports/metrics_definition.md` and `outputs/reports/proxy_metric_explanation.md`.

## 7. Results

| run_id | status | backend | controller | agents | steps | latency_s | mock_excluded |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
{chr(10).join(rows) if rows else '| no runs yet | | | | | | |'}

## 7.1 Exact SGLang Log Metrics

| controller | requests | max_token_usage | max_queue_req | max_pending_token | cached_token_ratio | p95_request_latency_s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(exact_rows) if exact_rows else '| no exact SGLang rows | | | | | | |'}

## 7.2 Findings Against Success Criteria

- Context growth: every successful real run includes `context_growth.csv`, and the b8 workload uses 8 agents x 8 steps with 256 observation tokens appended per step.
- Baseline KV pressure: no-control b8 reached max SGLang scheduler token usage {fmt_metric(sched_value("no_control", "max_token_usage"), 2)}, max queue depth `{sched_value("no_control", "max_queue_req") or "n/a"}`, and max pending tokens `{sched_value("no_control", "max_pending_token") or "n/a"}`.
- Request-level cap is not a stable solution: `request_cap_1` and `request_cap_2` reduced scheduler pressure but worsened end-to-end latency to {fmt_metric(latency_for("request_cap_1"), 3, "s")} and {fmt_metric(latency_for("request_cap_2"), 3, "s")}; `request_cap_8` returned to no-control-like pressure with max token usage {fmt_metric(sched_value("request_cap_8", "max_token_usage"), 2)}.
- Fixed agent windows show both modes: conservative `fixed_window_2` reduced max token usage to {fmt_metric(sched_value("fixed_window_2", "max_token_usage"), 2)} but slowed completion to {fmt_metric(latency_for("fixed_window_2"), 3, "s")}; aggressive `fixed_window_8` matched no-control-like max token usage {fmt_metric(sched_value("fixed_window_8", "max_token_usage"), 2)} and queue depth `{sched_value("fixed_window_8", "max_queue_req") or "n/a"}`.
- CONCUR dynamic completed the b8 run at {fmt_metric(latency_for("concur_dynamic"), 3, "s")}, close to `fixed_window_4` ({fmt_metric(latency_for("fixed_window_4"), 3, "s")}) and better than conservative fixed/request-cap settings, but it did not beat the no-control/aggressive-window latency in this single-run b8 measurement.
- CONCUR dynamic changed scheduler cache/token pressure under load: max token usage was {fmt_metric(sched_value("concur_dynamic", "max_token_usage"), 2)} versus no-control {fmt_metric(sched_value("no_control", "max_token_usage"), 2)}, while allowing max running requests `{sched_value("concur_dynamic", "max_running_req") or "n/a"}` and max queue depth `{sched_value("concur_dynamic", "max_queue_req") or "n/a"}`.
- The ideal paper trend `CONCUR latency < no_control` was not reproduced on this single RTX PRO 6000 b8 run. The report should therefore be read as a single-GPU scaled Qwen reproduction with mixed latency outcome, not a numeric replication of the paper.

Artifacts:

- `outputs/tables/end_to_end_latency_table.csv`
- `outputs/tables/sglang_request_metrics_by_run.csv`
- `outputs/tables/sglang_request_summary_by_run.csv`
- `outputs/tables/sglang_scheduler_pressure_by_run.csv`
- `outputs/tables/sglang_scheduler_summary_by_run.csv`
- `outputs/figures/kv_usage_timeseries.png`
- `outputs/figures/cache_hit_rate_timeseries.png`
- `outputs/figures/sglang_token_usage_timeseries.png`
- `outputs/figures/sglang_queue_req_timeseries.png`
- `outputs/figures/window_timeseries.png`
- `outputs/figures/fixed_vs_dynamic_latency.png`
- `outputs/figures/prefill_recompute_overhead.png`

## 8. Difference from Paper

- Hardware is RTX PRO 6000 single-GPU instead of H100 multi-GPU.
- TP is fixed to 1 instead of paper-scale multi-GPU TP settings.
- Any mock run is pipeline validation only and not a Qwen or paper-scale result.
- Quantized or smaller-Qwen fallback was not needed for the completed real Qwen3-32B BF16 runs.

## 9. Failures and Limitations

- The initial local `/data/3.8T-1/yue/envs/sglang` environment lacked required packages; it has since been repaired for the reported runs.
- An earlier Qwen smoke run failed with connection refused before the final server lifecycle fix; the failed run is retained in `outputs/runs`.
- Exact SGLang request and scheduler log metrics are normalized into CSVs. Block-level cache allocation, eviction, and HiCache internals are not yet captured.
- Results are single-run measurements on a shared machine, not a statistical paper-scale reproduction.

## 10. Next Steps

- Add repeated trials for the best fixed-window and dynamic settings if GPU time permits.
- Add block-level cache allocation or eviction metrics if SGLang exposes them in a stable endpoint or log format.
- Keep mock runs excluded from Qwen performance claims.
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
