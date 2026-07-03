# Latest Status

Last updated: 2026-07-03 23:56 Asia/Shanghai

- Phase: P5/P6/P7/P8 requirements from the server-side next-step plan are complete and ready for final git review, commit, and push.
- GPU cleanup: the stale repository-owned SGLang server from `20260703-140646-sglang_server-Qwen3-32B-gpu0` was stopped earlier; after the final P6 run, the active repository-owned server from `20260703-215102-sglang_server-Qwen3-32B-gpu0` was also stopped. GPU0 now has no compute process from this repo. GPU3 still has another user's reserve process and was not touched.
- Queue state: `experiment_queue.yaml` has `pending: []` and `running: null`. The original b8-long prompt-length failure is recorded under `failed`; the remaining original b8-long variants are marked `skipped` after the ctxfit downgrade.
- Completed v2 b8 repeated trials: 15 successful Qwen3-32B BF16 runs, covering 5 controllers x 3 seeds.
- Completed P6 pressure runs: b8-long ctxfit, b12 medium, and b16 medium. b16 `concur_dynamic_v2` finished successfully with latency `341.366s`.
- Generated final v2 tables:
  `outputs/tables/v2_b8_repeated_trials.csv`,
  `outputs/tables/v2_b8_repeated_trials_summary.csv`,
  `outputs/tables/v2_pressure_runs.csv`, and
  `outputs/tables/v2_pressure_runs_summary.csv`.
- Generated final v2 figures:
  `outputs/figures/v2_latency_mean_std.png`,
  `outputs/figures/v2_scheduler_token_usage_by_controller.png`,
  `outputs/figures/v2_queue_depth_by_controller.png`,
  `outputs/figures/v2_cached_token_ratio_by_controller.png`,
  `outputs/figures/v2_dynamic_window_timeseries.png`, and
  `outputs/figures/v2_fixed_vs_dynamic_latency.png`.
- Generated final reports:
  `outputs/reports/v2_b8_repeated_trials.md` and
  `outputs/reports/qwen_single_gpu_report_v2.md`.
- Validation: `python -m py_compile src/concur_repro/analyze.py` passed; `python -m concur_repro.analyze` regenerated all tables, figures, and reports successfully.
- Main finding: `prefix_stable_v2` materially improves exact cached-token ratio, and `concur_dynamic_v2` now logs periodic exact-feedback controller events. It does not consistently beat fixed-window latency; fixed_window_4 is best on b8/b12, while dynamic_v2 is best among tested b16 controllers.
- Next action: perform final `git status --short` review, commit the relevant code/config/table/figure/report/log artifacts, and push to `origin/main`.
