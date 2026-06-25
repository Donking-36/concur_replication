# Metrics Definition

## Latency

- `end_to_end_batch_latency_s`: wall-clock time from scheduling all agents to all agents finished.
- `completed_agents_per_second`: completed agents divided by end-to-end batch latency.
- `mean_agent_latency_s`: mean per-agent wall-clock time.
- `p95_agent_latency_s`: p95 per-agent wall-clock time when at least 20 agents are present; otherwise max observed agent latency.

## Workload

- `context_tokens_proxy`: approximate prompt tokens based on character length when a tokenizer is not available.
- `observation_tokens_proxy`: configured synthetic observation token count appended after each step.

## Serving

The harness records exact OpenAI-compatible API usage fields when the serving backend returns them. If SGLang exposes more detailed metrics, they should be copied into `serving_metrics.jsonl` with exact field names.

Required fields or proxy replacements:

- `kv_cache_usage` or `kv_cache_usage_proxy`
- `kv_cache_hit_rate` or `kv_cache_hit_rate_proxy`
- `prefill_tokens`
- `decode_tokens`
- `recompute_prefill_tokens` or `recompute_prefill_tokens_proxy`
- `generation_latency_s`

## Exact SGLang Log Metrics

Structured SGLang log artifacts are generated from the retained server run logs:

- `outputs/tables/sglang_request_metrics_by_run.csv`: per-request prompt tokens, completion tokens, cached tokens, queue time, request latency, and decode throughput attributed to experiment windows by timestamp.
- `outputs/tables/sglang_request_summary_by_run.csv`: per-run totals and request latency summaries from SGLang request metric logs.
- `outputs/tables/sglang_scheduler_pressure_by_run.csv`: scheduler prefill/decode rows parsed from `sglang_server.stderr.log`, including token usage, running requests, queued requests, and pending tokens.
- `outputs/tables/sglang_scheduler_summary_by_run.csv`: per-run scheduler pressure summary.
- `outputs/figures/sglang_token_usage_timeseries.png` and `outputs/figures/sglang_queue_req_timeseries.png`: exact scheduler log time-series figures.

These exact artifacts do not include block-level cache allocation, eviction, or HiCache internals.

## Controller

Each controller update records:

- `W_t`
- `W_next`
- `U_t`
- `H_t`
- `active_agents`
- `pending_agents`
- `finished_agents`
- `action`
- `reason`
