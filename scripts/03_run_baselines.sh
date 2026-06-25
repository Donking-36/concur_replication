#!/usr/bin/env bash
set -euo pipefail

source /data/3.8T-1/yue/concur_qwen_repro/scripts/env.sh

PY="$CONCUR_ROOT/envs/sglang/bin/python"
"$PY" -m concur_repro.run_experiment --config "$CONCUR_REPRO_ROOT/configs/experiments/baseline_no_control_b8.yaml"
"$PY" -m concur_repro.run_experiment --config "$CONCUR_REPRO_ROOT/configs/experiments/request_cap_1_b8.yaml"
"$PY" -m concur_repro.run_experiment --config "$CONCUR_REPRO_ROOT/configs/experiments/request_cap_2_b8.yaml"
"$PY" -m concur_repro.run_experiment --config "$CONCUR_REPRO_ROOT/configs/experiments/request_cap_4_b8.yaml"
"$PY" -m concur_repro.run_experiment --config "$CONCUR_REPRO_ROOT/configs/experiments/request_cap_8_b8.yaml"
