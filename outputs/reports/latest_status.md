# Latest Status

Last updated: 2026-06-23 23:31 Asia/Shanghai

- Phase: P3 real Qwen3-32B BF16 single-GPU sweep completed.
- Local `torch`, `sglang`, and `transformers` environment is repaired under `/data/3.8T-1/yue/envs/sglang`.
- Qwen3-32B BF16 served successfully with SGLang TP=1 on GPU 0.
- Mock run: `outputs/runs/20260623-184136-no_control-mock-pipeline-b2`.
- Real Qwen smoke: `outputs/runs/20260623-221042-no_control-Qwen3-32B-BF16-b2`.
- Completed b8 strategies: no-control, request caps 1/2/4/8, fixed windows 2/4/8/16-clamped-to-8, and CONCUR dynamic.
- Table: `outputs/tables/end_to_end_latency_table.csv`.
- Exact SGLang log metric tables: `outputs/tables/sglang_request_summary_by_run.csv` and `outputs/tables/sglang_scheduler_summary_by_run.csv`.
- Exact SGLang figures: `outputs/figures/sglang_token_usage_timeseries.png` and `outputs/figures/sglang_queue_req_timeseries.png`.
- Finding: the single b8 sweep reproduces pressure and controller tradeoffs, but not the ideal `CONCUR latency < no_control` trend; CONCUR dynamic reduced max scheduler token usage versus no-control while landing near fixed-window 4 latency.
- Report: `outputs/reports/qwen_single_gpu_report.md`.
- SGLang server stopped after the sweep; GPU 0 returned to 17 MiB used in the final `nvidia-smi` check.
- Next action: optional repeated trials or block-level cache instrumentation if stable SGLang fields are available.
