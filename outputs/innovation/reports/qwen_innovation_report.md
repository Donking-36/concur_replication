# Qwen CONCUR Innovation Report

## 1. Goal

Evaluate two lightweight scheduling innovations on top of the completed Qwen3-32B single-GPU v2 reproduction: `concur_cache_aware_v1` and `phase_window_v1`.

## 2. Baseline from v2 Reproduction

| controller | n | latency_mean_s | latency_std_s | max_queue_req_mean | cached_ratio_mean |
| --- | --- | --- | --- | --- | --- |
| no_control | 3 | 219.04972305232513 | 94.62776174904342 | 116.0 | 0.15710226857201792 |
| request_cap_4 | 3 | 183.4931668836507 | 2.87037449053534 | 2.3333333333333335 | 0.16007061851228982 |
| fixed_window_4 | 3 | 117.28452502732883 | 2.6290258929737407 | 1.6666666666666667 | 0.6633478082782766 |
| fixed_window_8 | 3 | 163.91371607999704 | 1.3445238041272476 | 6.0 | 0.20288050352169903 |
| concur_dynamic_v2 | 3 | 188.6933295310082 | 31.651313162002616 | 76.0 | 0.18213946823437965 |

## 3. Innovation A: Cache-Aware Hysteresis Controller

Uses exact SGLang scheduler/request metrics, an EWMA of cached-token ratio, queue/pending-token guards, and cooldown to reduce queue spikes from the previous dynamic controller.

## 4. Innovation B: Warmup-Then-Open Phase Window

Uses harness progress only: admit a small initial window to build prefix cache, then ramp admission wider after early steps complete.

## 5. Experiment Matrix

Innovation runs are stored separately under `outputs/innovation/runs`; tables, figures, and this report are under `outputs/innovation/`.

## 6. Results

| scenario | controller | n | latency_mean_s | latency_std_s | max_queue_req_mean | cached_ratio_mean |
| --- | --- | --- | --- | --- | --- | --- |
| b12_medium | concur_cache_aware_v1 | 1 | 223.853 | 0.000 | 6.000 | 0.347 |
| b12_medium | phase_window_v1 | 1 | 216.478 | 0.000 | 6.000 | 0.380 |
| b16_medium | concur_cache_aware_v1 | 1 | 289.608 | 0.000 | 6.000 | 0.406 |
| b16_medium | phase_window_v1 | 1 | 294.785 | 0.000 | 6.000 | 0.355 |
| b8 | concur_cache_aware_v1 | 3 | 111.392 | 2.994 | 3.333 | 0.666 |
| b8 | phase_window_v1 | 3 | 143.415 | 7.423 | 6.000 | 0.409 |
| b8_long_ctxfit | concur_cache_aware_v1 | 1 | 504.290 | 0.000 | 6.000 | 0.312 |
| b8_long_ctxfit | phase_window_v1 | 1 | 591.521 | 0.000 | 7.000 | 0.102 |

## 7. Success Criteria

- `concur_cache_aware_v1`: lower b8 queue pressure than `concur_dynamic_v2` while keeping latency interpretable.
- `phase_window_v1`: cached ratio above fixed_window_8 and latency below request_cap_4 on b8, if possible.

## 8. Findings Against Criteria

- `concur_cache_aware_v1` meets the b8 queue-pressure target versus `concur_dynamic_v2`: max_queue_req mean `3.333` vs `76.000`, latency `111.392s` vs `188.693s`.
- On repeated b8, `concur_cache_aware_v1` is the observed latency winner: `111.392s` mean, `5.0% faster` than `fixed_window_4` (`117.285s`), with similar exact cache ratio `0.666` vs `0.663`.
- `phase_window_v1` meets its b8 directional criterion: exact cache ratio `0.409` vs `fixed_window_8` `0.203`, and latency `143.415s` vs `request_cap_4` `183.493s`. It remains slower than `concur_cache_aware_v1` and `fixed_window_4` on b8.
- `b8_long_ctxfit` best innovation is `concur_cache_aware_v1` at `504.290s`; it beats the best v2 baseline `fixed_window_4` at `536.615s`.
- `b8_long_ctxfit` best innovation vs `concur_dynamic_v2`: `504.290s` vs `614.953s` (`18.0% faster`).
- `b12_medium` best innovation is `phase_window_v1` at `216.478s`; it does not beat the best v2 baseline `fixed_window_4` at `174.931s`.
- `b12_medium` best innovation vs `concur_dynamic_v2`: `216.478s` vs `212.756s` (`1.7% slower`).
- `b16_medium` best innovation is `concur_cache_aware_v1` at `289.608s`; it beats the best v2 baseline `concur_dynamic_v2` at `341.366s`.
- `b16_medium` best innovation vs `concur_dynamic_v2`: `289.608s` vs `341.366s` (`15.2% faster`).

## 9. Failures and Limitations

- All queued innovation runs completed successfully: 12 done, 0 failed.
- b12, b16, and b8-long ctxfit innovation scenarios currently have one seed each; treat those results as directional until repeated.
- Claims remain limited to single-GPU Qwen3-32B BF16 on SGLang with this local harness.

## 10. Recommendation

`concur_cache_aware_v1` is the leading innovation candidate for b8 and b16. Keep `phase_window_v1` as a low-instrumentation baseline, but do not claim it is the latency winner. Next tuning should target the cache-aware queue/pending-token guard under b12 and long-context pressure, then repeat b12/b16/long scenarios across seeds.
