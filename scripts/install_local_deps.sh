#!/usr/bin/env bash
set -euo pipefail

source /data/3.8T-1/yue/concur_qwen_repro/scripts/env.sh

PY="$CONCUR_ROOT/envs/sglang/bin/python"
PIP="$CONCUR_ROOT/envs/sglang/bin/pip"

if [[ ! -x "$PY" || ! -x "$PIP" ]]; then
  echo "missing local Python or pip under $CONCUR_ROOT/envs/sglang" >&2
  exit 2
fi

"$PIP" install --upgrade pip setuptools wheel
"$PIP" install -r "$CONCUR_REPRO_ROOT/requirements.txt"

"$PY" - <<'PY'
mods = ["torch", "sglang", "transformers", "pandas", "matplotlib"]
for mod in mods:
    m = __import__(mod)
    print(mod, getattr(m, "__version__", "unknown"))
PY
