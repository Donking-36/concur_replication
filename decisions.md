# Decisions

## 2026-06-23

- Keep all code, caches, logs, reports, and temporary files under `/data/3.8T-1/yue`.
- Use `/data/3.8T-1/yue/models/Qwen3-32B` as the first model candidate because full local weights already exist.
- Do not run real model experiments until `torch`, `sglang`, and `transformers` are available in the local environment and Torch reports exactly one visible GPU.
- Allow explicit mock runs only to validate harness behavior and output schemas. Mock runs must be labelled as pipeline validation and excluded from Qwen performance claims.
- Use Qwen3-32B BF16 for reported real runs. No quantized or smaller-Qwen fallback was needed after the local environment and SGLang launch lifecycle were fixed.
- Keep all real experiments on one visible GPU with `CUDA_VISIBLE_DEVICES=0` and SGLang tensor parallel size 1.
- Record both configured and effective controller parameters. For example, `fixed_window=16` with `num_agents=8` is reported as `fixed_window_16_effective_8`.
- Treat harness KV/cache figures as proxy metrics until exact SGLang server metrics are parsed into structured analysis artifacts.

## 2026-06-26

- Keep old v1 run directories unchanged; v2 work adds new configs, state files, tables, and reports.
- Use `prefix_stable_v2` as the workload credibility fix and compare exact SGLang cached-token ratio against v1 before expanding.
- Use `concur_dynamic_v2` as the periodic-feedback controller; controller events must include exact scheduler/request metrics, not only proxy admission events.
- Do not kill other users' `sglang::scheduler` processes even when they block GPU availability.
- Keep queue, heartbeat, active-run, and lock updates atomic under `/data/3.8T-1/yue/concur_qwen_repro`.

## 2026-06-29

- Treat `outputs/reports/heartbeat.json`, `outputs/reports/run_lock.json`, and `outputs/reports/active_run.json` as the primary long-running state files; keep root-level copies synchronized for compatibility with earlier recovery code.
- Require both low GPU memory and low GPU utilization before launching Qwen3-32B BF16, with two consecutive idle confirmations by default.
- If a queue wait is interrupted before any experiment run starts, restore the item to `pending` rather than marking it failed.
- Do not reuse a recorded SGLang server unless it is the current repository-owned process and passes the health check; avoid accidentally attaching experiments to another user's service.

## 2026-07-03

- Stop only repository-owned SGLang processes after confirming the PID, user, command line, model path, and run directory. GPU3's other-user reserve process was not touched.
- Treat the original b8-long context-length failure as a recorded limitation instead of retrying the same unsafe prompt length. Use the ctxfit variant with 320 observation tokens per step for P6 b8-long.
- Use the generated `v2_*` CSVs and matplotlib figures as the final v2 reporting surface. Keep the older self-drawn PNG outputs for compatibility, but do not use them as the primary report figures.
- Report `concur_dynamic_v2` honestly: it satisfies periodic exact-feedback instrumentation and improves some pressure scenarios, but fixed_window_4 is still the best b8/b12 latency controller in these runs.
