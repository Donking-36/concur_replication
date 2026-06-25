# CONCUR Qwen Single-GPU Reproduction

This workspace implements the Qwen-only, single-GPU CONCUR reproduction under:

`/data/3.8T-1/yue/concur_qwen_repro`

Hard boundary: every script sets `HOME`, caches, temp files, logs, run outputs, and reports under `/data/3.8T-1/yue`.

Current scope:

- Qwen only; no DeepSeek.
- One RTX PRO 6000 GPU with `CUDA_VISIBLE_DEVICES=<one id>`.
- SGLang tensor parallel size must remain 1.
- Strategies: `no_control`, `request_cap`, `fixed_window`, `concur_dynamic`.

Main entry points:

- `scripts/00_env_check.sh`
- `scripts/01_launch_sglang.sh`
- `scripts/02_run_smoke.sh`
- `scripts/03_run_baselines.sh`
- `scripts/04_run_concur.sh`
- `scripts/05_run_fixed_windows.sh`
- `scripts/06_plot_results.sh`
- `scripts/07_make_report.sh`

The mock smoke config is only for validating the engineering pipeline when GPU or SGLang dependencies are unavailable. It is never counted as a Qwen performance result.
