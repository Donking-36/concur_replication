#!/usr/bin/env bash
set -euo pipefail

source /data/3.8T-1/yue/concur_qwen_repro/scripts/env.sh

MAX_ITEMS="${MAX_ITEMS:-0}"
GPU_ID="${GPU_ID:-auto}"
GPU_MAX_USED_MIB="${GPU_MAX_USED_MIB:-2000}"
GPU_MAX_UTIL_PCT="${GPU_MAX_UTIL_PCT:-5}"
GPU_IDLE_CONFIRMATIONS="${GPU_IDLE_CONFIRMATIONS:-2}"
GPU_WAIT_TIMEOUT_S="${GPU_WAIT_TIMEOUT_S:-21600}"
GPU_POLL_S="${GPU_POLL_S:-300}"
WATCHDOG_TIMEOUT_S="${WATCHDOG_TIMEOUT_S:-7200}"
SERVER_PORT="${SERVER_PORT:-30000}"
MODEL_PATH="${MODEL_PATH:-$CONCUR_ROOT/models/Qwen3-32B}"
SERVER_LAUNCH_TIMEOUT_S="${SERVER_LAUNCH_TIMEOUT_S:-1800}"

"$CONCUR_ROOT/envs/sglang/bin/python" -m concur_repro.queue_runner \
  --max-items "$MAX_ITEMS" \
  --gpu-id "$GPU_ID" \
  --gpu-max-used-mib "$GPU_MAX_USED_MIB" \
  --gpu-max-util-pct "$GPU_MAX_UTIL_PCT" \
  --gpu-idle-confirmations "$GPU_IDLE_CONFIRMATIONS" \
  --gpu-wait-timeout-s "$GPU_WAIT_TIMEOUT_S" \
  --gpu-poll-s "$GPU_POLL_S" \
  --watchdog-timeout-s "$WATCHDOG_TIMEOUT_S" \
  --server-port "$SERVER_PORT" \
  --model-path "$MODEL_PATH" \
  --server-launch-timeout-s "$SERVER_LAUNCH_TIMEOUT_S"
