# v2 b8 Repeated Trials

Source CSVs:

- `outputs/tables/v2_b8_repeated_trials.csv`
- `outputs/tables/v2_b8_repeated_trials_summary.csv`

## Summary

| controller | n | latency_mean_s | latency_std_s | latency_min_s | latency_max_s | max_token_usage_mean | max_queue_req_mean | cached_token_ratio_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Per-Run Detail

| controller | seed | latency_s | max_token_usage | max_queue_req | max_pending_token | cached_token_ratio_total | controller_events | window_min | window_max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Notes: these rows include Qwen3-32B BF16 `prefix_stable_v2` runs with 8 agents, 8 steps, 256 observation tokens per step, and 64 max new tokens. Exact cache and scheduler fields come from SGLang logs when available.
