#!/usr/bin/env bash
set -euo pipefail

source /data/3.8T-1/yue/concur_qwen_repro/scripts/env.sh

GPU_ID="${1:-0}"
OUT="$CONCUR_REPRO_ROOT/outputs/reports/torch_single_gpu_check_gpu${GPU_ID}.txt"
export CUDA_VISIBLE_DEVICES="$GPU_ID"

"$CONCUR_ROOT/envs/sglang/bin/python" - <<'PY' > "$OUT"
import os
import torch

print("CUDA_VISIBLE_DEVICES", os.environ.get("CUDA_VISIBLE_DEVICES"))
print("torch_version", torch.__version__)
print("cuda_available", torch.cuda.is_available())
print("device_count", torch.cuda.device_count())
print("device_name", torch.cuda.get_device_name(0) if torch.cuda.is_available() and torch.cuda.device_count() else None)
if torch.cuda.device_count() != 1:
    raise SystemExit(3)
PY

cat "$OUT"
