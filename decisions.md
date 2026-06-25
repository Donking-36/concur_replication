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
