# Qwen CONCUR Innovation Report

## 1. Goal

Evaluate lightweight scheduling innovations on top of the completed Qwen3-32B single-GPU v2 reproduction. Round 1 covers `concur_cache_aware_v1` and `phase_window_v1`; round 2 covers `tail_open_v1` and `cache_gate_v1`.

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

## 5. Round 2 Additions

`tail_open_v1` keeps a fixed-window-4 style early phase and opens admission later based on progress or finished-agent ratio. `cache_gate_v1` uses exact SGLang metrics with a fixed-window-4 safety floor and only grows when cache and queue health permit.

## 6. Experiment Matrix

Innovation runs are stored in the configured innovation output root; tables, figures, and this report are generated into the corresponding `tables`, `figures`, and `reports` directories.

## 7. Results

| scenario | controller | n | latency_mean_s | latency_std_s | max_queue_req_mean | cached_ratio_mean |
| --- | --- | --- | --- | --- | --- | --- |
| b12_medium | cache_gate_v1 | 1 | 209.978 | 0.000 | 6.000 | 0.407 |
| b12_medium | tail_open_v1 | 1 | 228.594 | 0.000 | 6.000 | 0.341 |
| b16_medium | cache_gate_v1 | 1 | 265.467 | 0.000 | 6.000 | 0.491 |
| b16_medium | tail_open_v1 | 1 | 285.629 | 0.000 | 6.000 | 0.403 |
| b8 | cache_gate_v1 | 3 | 113.486 | 2.637 | 4.000 | 0.645 |
| b8 | tail_open_v1 | 3 | 118.855 | 5.759 | 5.000 | 0.579 |

## 8. Success Criteria

- `concur_cache_aware_v1`: lower b8 queue pressure than `concur_dynamic_v2` while keeping latency interpretable.
- `phase_window_v1`: cached ratio above fixed_window_8 and latency below request_cap_4 on b8, if possible.
- `tail_open_v1`: keep fixed-window-4 cache behavior early, then reduce tail latency by opening admission later.
- `cache_gate_v1`: use exact metrics with a fixed-window-4 safety floor and grow only when cache/queue health permits.

## 9. Findings Against Criteria

- Best available b8 innovation in this report is `cache_gate_v1` at `113.486s`; compared with `fixed_window_4` `117.285s`, it is `3.2% faster`.
- `tail_open_v1` tests the fixed-window tail-opening hypothesis: latency `118.855s` vs `fixed_window_4` `117.285s`, cached ratio `0.579` vs `0.663`.
- `cache_gate_v1` tests a cache-aware safety floor: latency `113.486s` vs `concur_dynamic_v2` `188.693s`, queue mean `4.000` vs `76.000`.
- `b12_medium` best innovation is `cache_gate_v1` at `209.978s`; it does not beat the best v2 baseline `fixed_window_4` at `174.931s`.
- `b12_medium` best innovation vs `concur_dynamic_v2`: `209.978s` vs `212.756s` (`1.3% faster`).
- `b16_medium` best innovation is `cache_gate_v1` at `265.467s`; it beats the best v2 baseline `concur_dynamic_v2` at `341.366s`.
- `b16_medium` best innovation vs `concur_dynamic_v2`: `265.467s` vs `341.366s` (`22.2% faster`).

## 10. Failures and Limitations

- All successful innovation runs discovered in this report are summarized: 10 success rows.
- b12, b16, and b8-long ctxfit innovation scenarios currently have one seed each; treat those results as directional until repeated.
- Claims remain limited to single-GPU Qwen3-32B BF16 on SGLang with this local harness.

## 11. Recommendation

Select claims from the rows actually present in this report. Treat b12/b16 single-seed results as directional, and keep the strongest repeated b8 result as the primary evidence.
