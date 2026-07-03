# v2 b8 Repeated Trials

Source CSVs:

- `outputs/tables/v2_b8_repeated_trials.csv`
- `outputs/tables/v2_b8_repeated_trials_summary.csv`

## Summary

| controller | n | latency_mean_s | latency_std_s | latency_min_s | latency_max_s | max_token_usage_mean | max_queue_req_mean | cached_token_ratio_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| no_control | 3 | 219.050 | 94.628 | 162.948 | 328.303 | 0.957 | 116.000 | 0.157 |
| request_cap_4 | 3 | 183.493 | 2.870 | 181.567 | 186.792 | 0.920 | 2.333 | 0.160 |
| fixed_window_4 | 3 | 117.285 | 2.629 | 115.472 | 120.300 | 0.967 | 1.667 | 0.663 |
| fixed_window_8 | 3 | 163.914 | 1.345 | 162.848 | 165.424 | 0.957 | 6.000 | 0.203 |
| concur_dynamic_v2 | 3 | 188.693 | 31.651 | 167.174 | 225.036 | 0.970 | 76.000 | 0.182 |

## Per-Run Detail

| controller | seed | latency_s | max_token_usage | max_queue_req | max_pending_token | cached_token_ratio_total | controller_events | window_min | window_max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| no_control | 0 | 328.303 | 0.970 | 336 | 159879 | 0.078 | 8 | 8.000 | 8.000 |
| no_control | 1 | 162.948 | 0.970 | 6 | 135500 | 0.208 | 8 | 8.000 | 8.000 |
| no_control | 2 | 165.898 | 0.930 | 6 | 126811 | 0.185 | 8 | 8.000 | 8.000 |
| request_cap_4 | 0 | 186.792 | 0.920 | 3 | 65056 | 0.137 | 8 | 8.000 | 8.000 |
| request_cap_4 | 1 | 181.567 | 0.920 | 2 | 56928 | 0.172 | 8 | 8.000 | 8.000 |
| request_cap_4 | 2 | 182.120 | 0.920 | 2 | 56914 | 0.172 | 8 | 8.000 | 8.000 |
| fixed_window_4 | 0 | 115.472 | 0.960 | 1 | 20368 | 0.680 | 8 | 4.000 | 4.000 |
| fixed_window_4 | 1 | 120.300 | 0.970 | 2 | 44177 | 0.657 | 8 | 4.000 | 4.000 |
| fixed_window_4 | 2 | 116.082 | 0.970 | 2 | 26683 | 0.653 | 8 | 4.000 | 4.000 |
| fixed_window_8 | 0 | 165.424 | 0.970 | 6 | 115568 | 0.189 | 8 | 8.000 | 8.000 |
| fixed_window_8 | 1 | 162.848 | 0.970 | 6 | 135500 | 0.208 | 8 | 8.000 | 8.000 |
| fixed_window_8 | 2 | 163.469 | 0.930 | 6 | 126819 | 0.212 | 8 | 8.000 | 8.000 |
| concur_dynamic_v2 | 0 | 225.036 | 0.970 | 218 | 131652 | 0.190 | 122 | 1.000 | 8.000 |
| concur_dynamic_v2 | 1 | 173.870 | 0.970 | 5 | 115118 | 0.150 | 96 | 1.000 | 8.000 |
| concur_dynamic_v2 | 2 | 167.174 | 0.970 | 5 | 106437 | 0.206 | 93 | 2.000 | 8.000 |

Notes: these rows include Qwen3-32B BF16 `prefix_stable_v2` runs with 8 agents, 8 steps, 256 observation tokens per step, and 64 max new tokens. Exact cache and scheduler fields come from SGLang logs when available.
