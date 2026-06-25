#!/usr/bin/env bash
set -euo pipefail

source /data/3.8T-1/yue/concur_qwen_repro/scripts/env.sh

REPORT_DIR="$CONCUR_REPRO_ROOT/outputs/reports"
PY="$CONCUR_ROOT/envs/sglang/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

"$PY" "$CONCUR_REPRO_ROOT/src/tools/filesystem_boundary_check.py" \
  > "$REPORT_DIR/filesystem_boundary_check.txt"

{
  echo "# Environment Report"
  echo
  echo "timestamp: $(date -Is)"
  echo "pwd: $(pwd)"
  echo "CONCUR_ROOT: $CONCUR_ROOT"
  echo "CONCUR_REPRO_ROOT: $CONCUR_REPRO_ROOT"
  echo "python: $PY"
  "$PY" --version || true
  echo
  echo "## Boundary Check"
  cat "$REPORT_DIR/filesystem_boundary_check.txt"
  echo
  echo "## Python Packages"
  "$PY" - <<'PY' || true
mods = ["torch", "sglang", "transformers", "yaml", "httpx", "aiohttp", "pandas", "matplotlib"]
for mod in mods:
    try:
        m = __import__(mod)
        print(f"{mod}: {getattr(m, '__version__', 'unknown')}")
    except Exception as exc:
        print(f"{mod}: IMPORT_ERROR {type(exc).__name__}: {str(exc)[:160]}")
PY
  echo
  echo "## Model Paths"
  if [[ -d "$CONCUR_ROOT/models/Qwen3-32B" ]]; then
    du -sh "$CONCUR_ROOT/models/Qwen3-32B" || true
    ls "$CONCUR_ROOT/models/Qwen3-32B/config.json" "$CONCUR_ROOT/models/Qwen3-32B/tokenizer.json" 2>/dev/null || true
  else
    echo "models/Qwen3-32B: missing"
  fi
  echo
  echo "## NVIDIA SMI"
  nvidia-smi || true
  echo
  echo "## NVIDIA PMON"
  nvidia-smi pmon -c 1 || true
} > "$REPORT_DIR/env_report.txt"

echo "wrote $REPORT_DIR/filesystem_boundary_check.txt"
echo "wrote $REPORT_DIR/env_report.txt"
