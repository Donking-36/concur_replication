#!/usr/bin/env bash
set -euo pipefail

source /data/3.8T-1/yue/concur_qwen_repro/scripts/env.sh

RUN_DIR="${1:-$(cat "$CONCUR_REPRO_ROOT/outputs/reports/latest_sglang_server_run_dir.txt")}"
PID_FILE="$RUN_DIR/sglang_server.pid"
if [[ ! -f "$PID_FILE" ]]; then
  echo "missing pid file: $PID_FILE" >&2
  exit 2
fi

PID="$(cat "$PID_FILE")"
if [[ ! "$PID" =~ ^[0-9]+$ ]]; then
  echo "invalid pid: $PID" >&2
  exit 2
fi

if [[ -d "/proc/$PID" ]]; then
  kill "$PID"
  for _ in $(seq 1 30); do
    if [[ ! -d "/proc/$PID" ]]; then
      break
    fi
    sleep 1
  done
fi

nvidia-smi > "$RUN_DIR/nvidia_smi_after_stop.txt" 2>&1 || true
echo "stopped pid $PID from $RUN_DIR"
