# Current Results Audit

Last updated: 2026-06-26 02:35 Asia/Shanghai

## Scope

This audit covers the existing v1 Qwen3-32B BF16 single-GPU results before the v2 workload and controller experiments.

## Existing Valid Results

- Real model: `/data/3.8T-1/yue/models/Qwen3-32B`.
- Serving: SGLang, single visible GPU, `tensor_parallel_size=1`.
- Completed v1 b8 sweep: `no_control`, `request_cap_1/2/4/8`, `fixed_window_2/4/8/16_effective_8`, `concur_dynamic`.
- Old no-control b8 latency: about `181.513s`.
- Old `concur_dynamic` b8 latency: about `200.295s`.
- Exact scheduler metrics show no-control b8 reached `max_token_usage=0.97`, `max_queue_req=6`, and `max_pending_token=115056`.

## Credibility Gaps To Fix

- The v1 prompt starts each step with `Step: {step}` before the previous observations. This means later requests do not preserve the previous request as a stable byte prefix. Exact SGLang `cached_token_ratio_total` is therefore very low in the v1 b8 runs, around `0.0013` to `0.0059`.
- The old `concur_dynamic` controller only updates near agent admission. Its `controller_events.jsonl` cannot demonstrate periodic feedback control over the whole run.
- Existing exact SGLang request rows are attributed to runs by timestamp, but not yet mapped back to `agent_id` and `step`; v2 analysis adds best-effort timestamp mapping.

## v2 Acceptance Criteria

- `prefix_stable_v2` must show a materially higher exact SGLang cached-token ratio than old v1 under the same or comparable b2/b8 setup.
- `concur_dynamic_v2` must write periodic `controller_events` with `metric_type=exact_sglang_log`, with event count roughly tracking `run_duration / update_interval_s` plus admission events.
- Reports must keep old v1, new v2, exact metrics, and proxy metrics separate.
- If v2 CONCUR still does not beat no-control latency, the report must say so and separately report changes in token pressure, queue depth, pending tokens, and cached-token ratio.
