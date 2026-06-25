#!/usr/bin/env bash
set -euo pipefail

source /data/3.8T-1/yue/concur_qwen_repro/scripts/env.sh

GPU_ID="${1:-0}"
PORT="${2:-30000}"
MODEL_PATH="${3:-$CONCUR_ROOT/models/Qwen3-32B}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen3-32b}"
DTYPE="${DTYPE:-bfloat16}"
MEM_FRACTION_STATIC="${MEM_FRACTION_STATIC:-0.82}"
READY_TIMEOUT_S="${READY_TIMEOUT_S:-1200}"

STAMP="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$CONCUR_REPRO_ROOT/outputs/runs/${STAMP}-sglang_server-Qwen3-32B-gpu${GPU_ID}"
mkdir -p "$RUN_DIR/sglang_metrics"

export CUDA_VISIBLE_DEVICES="$GPU_ID"

nvidia-smi > "$RUN_DIR/nvidia_smi_start.txt" 2>&1 || true
nvidia-smi pmon -c 1 > "$RUN_DIR/nvidia_smi_pmon_start.txt" 2>&1 || true

"$CONCUR_ROOT/envs/sglang/bin/python" - <<'PY' > "$RUN_DIR/torch_visible_devices.txt"
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

CMD=(
  "$CONCUR_ROOT/envs/sglang/bin/python" -m sglang.launch_server
  --model-path "$MODEL_PATH"
  --host 127.0.0.1
  --port "$PORT"
  --dtype "$DTYPE"
  --tensor-parallel-size 1
  --served-model-name "$SERVED_MODEL_NAME"
  --trust-remote-code
  --mem-fraction-static "$MEM_FRACTION_STATIC"
  --enable-metrics
  --enable-cache-report
  --log-requests
  --log-requests-level 1
  --log-requests-format json
  --log-requests-target "$RUN_DIR/sglang_requests.jsonl"
  --export-metrics-to-file
  --export-metrics-to-file-dir "$RUN_DIR/sglang_metrics"
)

printf '%q ' "${CMD[@]}" > "$RUN_DIR/command.txt"
printf '\n' >> "$RUN_DIR/command.txt"
env | sort > "$RUN_DIR/env.txt"

PID_FILE="$RUN_DIR/sglang_server.pid"
setsid bash -c 'echo "$$" > "$1"; shift; exec "$@"' \
  _ "$PID_FILE" "${CMD[@]}" \
  > "$RUN_DIR/sglang_server.stdout.log" \
  2> "$RUN_DIR/sglang_server.stderr.log" \
  < /dev/null &
LAUNCH_WRAPPER_PID="$!"
disown "$LAUNCH_WRAPPER_PID" 2>/dev/null || true

for _ in $(seq 1 50); do
  if [[ -s "$PID_FILE" ]]; then
    break
  fi
  sleep 0.1
done

if [[ ! -s "$PID_FILE" ]]; then
  echo "server pid file was not written" > "$RUN_DIR/failure_reason.md"
  exit 2
fi

SERVER_PID="$(cat "$PID_FILE")"
echo "$RUN_DIR" > "$CONCUR_REPRO_ROOT/outputs/reports/latest_sglang_server_run_dir.txt"

set +e
"$CONCUR_ROOT/envs/sglang/bin/python" - "$PORT" "$RUN_DIR/health_check.json" "$READY_TIMEOUT_S" "$SERVER_PID" <<'PY'
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
import os

port = int(sys.argv[1])
out = Path(sys.argv[2])
timeout_s = int(sys.argv[3])
pid = int(sys.argv[4])
base = f"http://127.0.0.1:{port}"
started = time.time()
last_error = None
while time.time() - started < timeout_s:
    if not Path(f"/proc/{pid}").exists():
        out.write_text(json.dumps({"ok": False, "error": "server process exited", "pid": pid}, indent=2) + "\n")
        raise SystemExit(2)
    try:
        req = urllib.request.Request(f"{base}/v1/chat/completions", data=json.dumps({
            "model": "qwen3-32b",
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "temperature": 0,
            "max_tokens": 4,
            "stream": False,
        }).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
        out.write_text(json.dumps({
            "ok": True,
            "base_url": base,
            "pid": pid,
            "latency_s": time.time() - started,
            "response": json.loads(body),
        }, indent=2) + "\n")
        raise SystemExit(0)
    except Exception as exc:
        last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(5)
out.write_text(json.dumps({"ok": False, "error": last_error, "pid": pid, "base_url": base}, indent=2) + "\n")
raise SystemExit(1)
PY
HEALTH_STATUS="$?"
set -e

nvidia-smi > "$RUN_DIR/nvidia_smi_end.txt" 2>&1 || true

if [[ "$HEALTH_STATUS" != "0" ]]; then
  {
    echo "# Failure Reason"
    echo
    echo "- stage: sglang_server_startup"
    echo "- health_status: $HEALTH_STATUS"
    echo "- health_check: $RUN_DIR/health_check.json"
    echo
    echo "## stderr tail"
    echo
    tail -n 80 "$RUN_DIR/sglang_server.stderr.log" || true
  } > "$RUN_DIR/failure_reason.md"
  exit "$HEALTH_STATUS"
fi

echo "server_run_dir=$RUN_DIR"
echo "server_pid=$SERVER_PID"
echo "base_url=http://127.0.0.1:$PORT"
