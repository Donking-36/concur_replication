#!/usr/bin/env bash
set -euo pipefail

source /data/3.8T-1/yue/concur_qwen_repro/scripts/env.sh

export QUEUE_PATH="$CONCUR_REPRO_ROOT/experiment_queue_innovation.yaml"
export MAX_ITEMS="${MAX_ITEMS:-0}"
export GPU_ID="${GPU_ID:-auto}"
export GPU_MAX_USED_MIB="${GPU_MAX_USED_MIB:-2000}"
export GPU_MAX_UTIL_PCT="${GPU_MAX_UTIL_PCT:-5}"
export GPU_IDLE_CONFIRMATIONS="${GPU_IDLE_CONFIRMATIONS:-2}"
export GPU_WAIT_TIMEOUT_S="${GPU_WAIT_TIMEOUT_S:-21600}"
export GPU_POLL_S="${GPU_POLL_S:-300}"
export WATCHDOG_TIMEOUT_S="${WATCHDOG_TIMEOUT_S:-7200}"
export SERVER_PORT="${SERVER_PORT:-30000}"
export MODEL_PATH="${MODEL_PATH:-$CONCUR_ROOT/models/Qwen3-32B}"
export SERVER_LAUNCH_TIMEOUT_S="${SERVER_LAUNCH_TIMEOUT_S:-1800}"

bash "$CONCUR_REPRO_ROOT/scripts/08_run_queue.sh"
