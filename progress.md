# Progress

## 2026-06-23 P0

- Created `/data/3.8T-1/yue/concur_qwen_repro` with the required config, source, script, run, report, figure, and table directories.
- Added common environment boundary script at `scripts/env.sh`.
- Added filesystem boundary checker and environment report script.
- Local Qwen3-32B weights are present at `/data/3.8T-1/yue/models/Qwen3-32B` (~62G).
- Direct `nvidia-smi` is available with approval; GPU 0 and GPU 2 were mostly idle at the first check, while GPU 1 and GPU 3 had active Python compute processes.
- Existing `envs/sglang` Python 3.12 environment is incomplete for real serving: `torch`, `sglang`, and `transformers` are not installed.

Current phase: P0 environment boundary and P1 engineering pipeline scaffolding.

## 2026-06-23 P1 engineering smoke

- Ran mock pipeline smoke: `20260623-184136-no_control-mock-pipeline-b2`.
- Produced `agent_events.jsonl`, `controller_events.jsonl`, `serving_metrics.jsonl`, `gpu_metrics.csv`, `context_growth.csv`, and `summary.json`.
- Generated preliminary table and figures from mock output. These are excluded from Qwen performance claims.

## 2026-06-23 P2 real Qwen serving

- Repaired the local `/data/3.8T-1/yue/envs/sglang` environment for real serving:
  `torch 2.11.0+cu130`, `sglang 0.5.13.post1`, `transformers 5.8.1`,
  `pandas 3.0.3`, and `matplotlib 3.11.0`.
- Added the local venv `bin` directory to `PATH` in `scripts/env.sh` so FlashInfer can find `ninja`.
- Hardened `scripts/01_launch_sglang.sh` to retain startup failure logs, end-state GPU snapshots, PID files, and detached server logs.
- Served Qwen3-32B BF16 on GPU 0 with SGLang TP=1 from run
  `20260623-220614-sglang_server-Qwen3-32B-gpu0`.
- Confirmed real Qwen smoke success:
  `20260623-221042-no_control-Qwen3-32B-BF16-b2`, 2 agents x 2 steps,
  latency `3.9928863539826125` seconds.
- Retained failed earlier smoke
  `20260623-220318-no_control-Qwen3-32B-BF16-b2` for connection-refused diagnosis.

## 2026-06-23 P3 Qwen3-32B b8 sweep

- Completed one real BF16 Qwen3-32B run for each required b8 strategy and added extra sweep points.
- No-control: `20260623-221314-no_control-Qwen3-32B-b8`, latency `181.51342870807275` seconds.
- Request caps:
  `request_cap_1` latency `335.31575924903154` seconds,
  `request_cap_2` latency `238.07252060389146` seconds,
  `request_cap_4` latency `195.78105898504145` seconds,
  `request_cap_8` latency `181.93129083397798` seconds.
- Fixed windows:
  `fixed_window_2` latency `251.80036693695` seconds,
  `fixed_window_4` latency `200.24444863805547` seconds,
  `fixed_window_8` latency `182.33982133702375` seconds,
  `fixed_window_16_effective_8` latency `181.9183734988328` seconds.
- Dynamic CONCUR: `20260623-222503-concur_dynamic-Qwen3-32B-b8`,
  latency `200.29479524795897` seconds.
- Patched result metadata so summaries and tables include `controller_label`,
  `request_cap`, configured/effective fixed windows, and dynamic window settings.
- Regenerated required artifacts:
  `outputs/tables/end_to_end_latency_table.csv`,
  `outputs/figures/kv_usage_timeseries.png`,
  `outputs/figures/cache_hit_rate_timeseries.png`,
  `outputs/figures/window_timeseries.png`,
  `outputs/figures/fixed_vs_dynamic_latency.png`,
  `outputs/figures/prefill_recompute_overhead.png`, and
  `outputs/reports/qwen_single_gpu_report.md`.

## 2026-06-23 P4 exact SGLang log metrics

- Added structured parsing for retained SGLang request metric logs and scheduler stderr pressure lines.
- Generated exact request metric artifacts:
  `outputs/tables/sglang_request_metrics_by_run.csv` and
  `outputs/tables/sglang_request_summary_by_run.csv`.
- Generated exact scheduler pressure artifacts:
  `outputs/tables/sglang_scheduler_pressure_by_run.csv` and
  `outputs/tables/sglang_scheduler_summary_by_run.csv`.
- Generated exact scheduler figures:
  `outputs/figures/sglang_token_usage_timeseries.png` and
  `outputs/figures/sglang_queue_req_timeseries.png`.
- Updated `outputs/reports/qwen_single_gpu_report.md`,
  `outputs/reports/metrics_definition.md`, and
  `outputs/reports/proxy_metric_explanation.md` to distinguish exact SGLang log signals from remaining block-level cache internals.
- Added report findings for the task success criteria. The single b8 run shows baseline and aggressive-window pressure (`max_token_usage=0.97`, queue depth `6`), request-cap instability, conservative/aggressive fixed-window behavior, and a mixed CONCUR outcome: dynamic reduced max token pressure to `0.93` but did not beat no-control latency in this single-run setting.
