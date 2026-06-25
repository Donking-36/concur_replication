# Proxy Metric Explanation

The local SGLang/Torch environment is repaired and real Qwen requests are served. SGLang request and scheduler log metrics are now normalized into exact CSV artifacts for prompt tokens, cached tokens, request latency, token usage, queue depth, and pending tokens. The proxy fields below remain for harness-level KV/cache figures where block-level SGLang cache allocation and eviction data are not available.

Current proxy:

- `kv_cache_usage_proxy = min(1, context_tokens_proxy / kv_proxy_budget_tokens)`.
- `kv_cache_hit_rate_proxy = 1` after an agent has completed at least one previous step while its context is treated as resident; otherwise `0`.
- `recompute_prefill_tokens_proxy = prefill_tokens` when `kv_cache_hit_rate_proxy == 0`, else `0`.

Why this is useful:

- The workload grows context monotonically by agent step.
- More active agents and longer observations increase the context pressure proxy.
- Fixed and dynamic agent windows can be compared against the same configured proxy budget.

Limitations:

- This does not measure actual SGLang block allocation, eviction, HiCache behavior, or true prefix cache hit rate.
- Exact SGLang log tables now augment the proxy figures for request cached-token counts and scheduler pressure, but they still do not expose block-level cache internals.
