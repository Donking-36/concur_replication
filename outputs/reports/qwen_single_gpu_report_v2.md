# CONCUR Qwen Single-GPU Reproduction Report v2

## 1. Scope

This report covers the Qwen3-32B BF16 single-GPU reproduction in `/data/3.8T-1/yue/concur_qwen_repro`. The goal is a scaled, instrumented reproduction on one RTX PRO 6000-class GPU with SGLang TP=1, not a numerical reproduction of the paper's multi-H100 setup.

## 2. What Was Already Completed Before v2

The previous version already provided a working harness, SGLang launch script, Qwen3-32B smoke run, a v1 b8 controller sweep, exact SGLang request/scheduler log parsers, and an initial report. Those v1 results established that no-control can drive scheduler `token_usage` near 0.97 on a single GPU.

## 3. Why v2 Was Needed

The v1 prompt changed a `Step:` header near the front of every prompt, so later steps were not stable-prefix extensions of earlier steps. Exact SGLang cached-token ratios were very low, so the old cache-hit proxy could not be treated as a real hit rate. The original dynamic controller also updated only around admission events, not on a periodic exact-metric feedback loop.

## 4. Hardware and Software

- Model: `/data/3.8T-1/yue/models/Qwen3-32B`
- Precision: BF16
- Serving: SGLang OpenAI-compatible server, tensor parallel size 1
- GPU policy: one GPU only; no other users' processes were killed
- Main outputs: `outputs/runs`, `outputs/tables`, `outputs/figures`, and `outputs/reports`

## 5. Workload v1 vs Prefix-Stable Workload v2

Old v1 b8 exact cached-token ratio mean across parsed successful b8 runs: `0.0019`.
New prefix_stable_v2 b8 mean cached-token ratio across controllers: `0.2731`.

The v2 workload keeps earlier observation lines append-only, which makes later steps stable-prefix extensions of earlier prompts. This produced materially higher exact cached-token ratios for fixed-window-4 in particular, while aggressive/no-control schedules still show lower average ratios because more agents compete for cache residency.

## 6. Controllers

v2 evaluates `no_control`, `request_cap_4`, `request_cap_8` where applicable, `fixed_window_4`, `fixed_window_8`, and `concur_dynamic_v2`. The dynamic v2 controller reads exact SGLang scheduler/request-tail snapshots when fresh, writes periodic controller events, and changes only future admission; it does not preempt already-active agents.

## 7. Exact Metrics and Remaining Proxies

Exact metrics come from SGLang request metric logs and scheduler stderr lines: cached tokens, prompt tokens, request latency, `token_usage`, `queue_req`, and `pending_token`. Harness-level GPU/context-growth signals remain proxies and are not used as proof of real cache hit rate.

## 8. b8 Repeated Trials

| controller | n | latency_mean_s | latency_std_s | max_token_usage_mean | max_queue_req_mean | cached_ratio_mean |
| --- | --- | --- | --- | --- | --- | --- |
| no_control | 3 | 219.050 | 94.628 | 0.957 | 116.000 | 0.157 |
| request_cap_4 | 3 | 183.493 | 2.870 | 0.920 | 2.333 | 0.160 |
| fixed_window_4 | 3 | 117.285 | 2.629 | 0.967 | 1.667 | 0.663 |
| fixed_window_8 | 3 | 163.914 | 1.345 | 0.957 | 6.000 | 0.203 |
| concur_dynamic_v2 | 3 | 188.693 | 31.651 | 0.970 | 76.000 | 0.182 |

Best b8 mean latency: `fixed_window_4` at `117.285` seconds. `concur_dynamic_v2` did not beat the best fixed-window setting on b8; fixed_window_4 is the latency winner in this repeated set.

## 9. Higher-Pressure Runs

| scenario | controller | n | latency_s | max_token_usage | max_queue_req | cached_ratio |
| --- | --- | --- | --- | --- | --- | --- |
| b12_medium | concur_dynamic_v2 | 1 | 212.756 | 0.970 | 6.000 | 0.393 |
| b12_medium | fixed_window_4 | 1 | 174.931 | 0.970 | 1.000 | 0.670 |
| b12_medium | fixed_window_8 | 1 | 224.328 | 0.970 | 6.000 | 0.342 |
| b12_medium | no_control | 1 | 273.727 | 1.000 | 10.000 | 0.064 |
| b12_medium | request_cap_4 | 1 | 297.785 | 0.950 | 2.000 | 0.047 |
| b12_medium | request_cap_8 | 1 | 280.767 | 0.980 | 6.000 | 0.044 |
| b16_medium | concur_dynamic_v2 | 1 | 341.366 | 0.970 | 6.000 | 0.200 |
| b16_medium | fixed_window_8 | 1 | 349.699 | 0.990 | 6.000 | 0.161 |
| b16_medium | no_control | 1 | 376.182 | 0.990 | 14.000 | 0.027 |
| b8_long_ctxfit | concur_dynamic_v2 | 1 | 614.953 | 0.980 | 7.000 | 0.043 |
| b8_long_ctxfit | fixed_window_4 | 1 | 536.615 | 0.980 | 3.000 | 0.267 |
| b8_long_ctxfit | fixed_window_8 | 1 | 614.365 | 0.980 | 7.000 | 0.052 |
| b8_long_ctxfit | no_control | 1 | 616.115 | 0.980 | 7.000 | 0.048 |

Best b8-long ctxfit latency: `fixed_window_4` at `536.615` seconds.
Best b12 latency: `fixed_window_4` at `174.931` seconds.
Best b16 latency among tested controllers: `concur_dynamic_v2` at `341.366` seconds.

## 10. Results Against CONCUR Success Criteria

The prefix-stable workload criterion is met: v2 exact cached-token ratios are far above the old low-ratio v1 baseline. The dynamic-v2 periodic-feedback criterion is also met: dynamic runs have tens to hundreds of controller events, not one event per agent. The latency criterion is mixed: dynamic v2 is not consistently best on b8 or b12, but it beats no-control on b12/b16 and beats fixed_window_8 in the tested b16 pressure run.

Dynamic v2 periodic event summary:

| scenario | seed | latency_s | events | exact_events | W_min_seen | W_max_seen | W_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b12_medium | 0 | 212.756 | 118 | 118 | 1.000 | 8.000 | 6.873 |
| b16_medium | 0 | 341.366 | 184 | 184 | 1.000 | 8.000 | 7.293 |
| b8 | 0 | 225.036 | 122 | 122 | 1.000 | 8.000 | 5.418 |
| b8 | 1 | 173.870 | 96 | 96 | 1.000 | 8.000 | 3.990 |
| b8 | 2 | 167.174 | 93 | 93 | 2.000 | 8.000 | 4.516 |
| b8_long_ctxfit | 0 | 614.953 | 311 | 311 | 4.000 | 8.000 | 7.839 |

## 11. Differences from Paper

This is a single-GPU Qwen3-32B BF16 reproduction on SGLang, while the paper evaluates a larger distributed setting. The controller and workload are scaled to a local 8-16 agent harness; results should be interpreted as reproduction evidence for trends and instrumentation, not as paper-number replication.

## 12. Failures and Limitations

The original b8-long configuration with 384 observation tokens per step exceeded the configured 40960-token context limit. It was recorded as a failed/unsupported configuration and replaced by the ctxfit version with 320 observation tokens per step.

Remaining limitations: shared-server variance is visible, especially in seed0 no-control; exact request-to-agent mapping is timestamp-based where SGLang does not retain arbitrary metadata; dynamic v2 still uses a simple heuristic control law rather than a tuned controller; and not all high-pressure combinations were repeated across three seeds.

## 13. Next Steps

Recommended follow-up work is to repeat b12/b16 pressure scenarios across seeds, tune dynamic-v2 thresholds against exact metrics, test a smaller `W_max`/larger `alpha` grid, and compare against a multi-GPU serving setup if hardware is available.

## Artifact Index

- `outputs/tables/v2_b8_repeated_trials.csv`
- `outputs/tables/v2_b8_repeated_trials_summary.csv`
- `outputs/tables/v2_pressure_runs.csv`
- `outputs/tables/v2_pressure_runs_summary.csv`
- `outputs/figures/v2_latency_mean_std.png`
- `outputs/figures/v2_scheduler_token_usage_by_controller.png`
- `outputs/figures/v2_queue_depth_by_controller.png`
- `outputs/figures/v2_cached_token_ratio_by_controller.png`
- `outputs/figures/v2_dynamic_window_timeseries.png`
- `outputs/figures/v2_fixed_vs_dynamic_latency.png`
