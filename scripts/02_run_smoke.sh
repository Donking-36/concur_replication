#!/usr/bin/env bash
set -euo pipefail

source /data/3.8T-1/yue/concur_qwen_repro/scripts/env.sh

PY="$CONCUR_ROOT/envs/sglang/bin/python"
CONFIG="${1:-$CONCUR_REPRO_ROOT/configs/experiments/smoke_mock.yaml}"

"$PY" -m concur_repro.run_experiment --config "$CONFIG"
