#!/usr/bin/env bash
set -euo pipefail

source /data/3.8T-1/yue/concur_qwen_repro/scripts/env.sh

PY="$CONCUR_ROOT/envs/sglang/bin/python"
"$PY" -m concur_repro.run_experiment --config "$CONCUR_REPRO_ROOT/configs/experiments/fixed_window_2_b8.yaml"
"$PY" -m concur_repro.run_experiment --config "$CONCUR_REPRO_ROOT/configs/experiments/fixed_window_4_b8.yaml"
"$PY" -m concur_repro.run_experiment --config "$CONCUR_REPRO_ROOT/configs/experiments/fixed_window_8_b8.yaml"
"$PY" -m concur_repro.run_experiment --config "$CONCUR_REPRO_ROOT/configs/experiments/fixed_window_16_b8.yaml"
