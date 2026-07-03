#!/usr/bin/env bash
set -euo pipefail

export CONCUR_ROOT=/data/3.8T-1/yue
export CONCUR_REPRO_ROOT=/data/3.8T-1/yue/concur_qwen_repro
export HOME=/data/3.8T-1/yue
export TMPDIR=/data/3.8T-1/yue/.tmp
export XDG_CACHE_HOME=/data/3.8T-1/yue/.cache
export HF_HOME=/data/3.8T-1/yue/.cache/huggingface
export HUGGINGFACE_HUB_CACHE=/data/3.8T-1/yue/.cache/huggingface/hub
export TRANSFORMERS_CACHE=/data/3.8T-1/yue/.cache/huggingface/transformers
export TORCH_HOME=/data/3.8T-1/yue/.cache/torch
export PIP_CACHE_DIR=/data/3.8T-1/yue/.cache/pip
export UV_CACHE_DIR=/data/3.8T-1/yue/.cache/uv
export CONDA_PKGS_DIRS=/data/3.8T-1/yue/.cache/conda_pkgs
export PYTHONPYCACHEPREFIX=/data/3.8T-1/yue/.cache/pycache
export PYTHONUNBUFFERED=1
export PATH=/data/3.8T-1/yue/envs/sglang/bin:$PATH

mkdir -p \
  "$TMPDIR" \
  "$XDG_CACHE_HOME" \
  "$HF_HOME" \
  "$HUGGINGFACE_HUB_CACHE" \
  "$TRANSFORMERS_CACHE" \
  "$TORCH_HOME" \
  "$PIP_CACHE_DIR" \
  "$UV_CACHE_DIR" \
  "$CONDA_PKGS_DIRS" \
  "$PYTHONPYCACHEPREFIX" \
  "$CONCUR_REPRO_ROOT/outputs/runs" \
  "$CONCUR_REPRO_ROOT/outputs/innovation/runs" \
  "$CONCUR_REPRO_ROOT/outputs/innovation/reports" \
  "$CONCUR_REPRO_ROOT/outputs/innovation/figures" \
  "$CONCUR_REPRO_ROOT/outputs/innovation/tables" \
  "$CONCUR_REPRO_ROOT/outputs/reports" \
  "$CONCUR_REPRO_ROOT/outputs/figures" \
  "$CONCUR_REPRO_ROOT/outputs/tables"

cd "$CONCUR_ROOT"

if [[ "$(pwd)" != "$CONCUR_ROOT" ]]; then
  echo "ERROR: pwd is not $CONCUR_ROOT" >&2
  exit 2
fi

export PYTHONPATH="$CONCUR_REPRO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
