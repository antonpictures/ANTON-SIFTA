#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL_DIR="$REPO/tests/rlhs_evals"
STATE_DIR="${SIFTA_STATE_DIR:-$REPO/.sifta_state}"
OUT_DIR="${SIFTA_RLHS_CI_OUTPUT_DIR:-$STATE_DIR/promptfoo_rlhs_ci}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_JSON="$OUT_DIR/promptfoo_${STAMP}.json"
LATEST_JSON="$OUT_DIR/latest.json"
PROMPTFOO_LOG="$OUT_DIR/promptfoo_${STAMP}.log"
PYTEST_LOG="$OUT_DIR/pytest_${STAMP}.log"
RUN_LOG="$STATE_DIR/promptfoo_rlhs_ci_runs.jsonl"
NPM_CACHE="${SIFTA_NPM_CACHE:-/tmp/npm_cache}"

export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
export PROMPTFOO_DISABLE_TELEMETRY="${PROMPTFOO_DISABLE_TELEMETRY:-1}"
export PROMPTFOO_DISABLE_UPDATE="${PROMPTFOO_DISABLE_UPDATE:-1}"

mkdir -p "$OUT_DIR" "$STATE_DIR"

for bin in python3 npm node; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "[SIFTA RLHS CI] Missing required binary: $bin" >&2
    exit 127
  fi
done

python3 - <<'PY'
import json
import urllib.request

try:
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as r:
        json.loads(r.read())
except Exception as exc:
    raise SystemExit(
        "[SIFTA RLHS CI] Ollama is not reachable at 127.0.0.1:11434. "
        "Start SIFTA/Ollama before running Promptfoo. "
        f"Probe error: {type(exc).__name__}: {exc}"
    )
PY

if [ ! -x "$EVAL_DIR/node_modules/.bin/promptfoo" ]; then
  echo "[SIFTA RLHS CI] Installing pinned Promptfoo dependencies with npm ci..."
  (cd "$EVAL_DIR" && npm ci --cache "$NPM_CACHE" --prefer-offline)
fi

echo "[SIFTA RLHS CI] Running Promptfoo immune evals..."
set +e
(cd "$EVAL_DIR" && ./node_modules/.bin/promptfoo eval -o "$OUTPUT_JSON") >"$PROMPTFOO_LOG" 2>&1
promptfoo_status=$?
set -e

echo "[SIFTA RLHS CI] Running Python regression guards..."
set +e
(cd "$REPO" && python3 -m pytest \
  tests/test_rlhs_evals_provider.py \
  tests/test_swarm_rlhf_detector.py \
  tests/test_immune_budget_simulation.py \
  -q) >"$PYTEST_LOG" 2>&1
pytest_status=$?
set -e

if [ -f "$OUTPUT_JSON" ]; then
  cp "$OUTPUT_JSON" "$LATEST_JSON"
fi

python3 - "$RUN_LOG" "$STAMP" "$promptfoo_status" "$pytest_status" "$OUTPUT_JSON" "$PROMPTFOO_LOG" "$PYTEST_LOG" <<'PY'
import json
import sys
import time
from pathlib import Path

run_log, stamp, promptfoo_status, pytest_status, output_json, promptfoo_log, pytest_log = sys.argv[1:]
row = {
    "ts": time.time(),
    "stamp": stamp,
    "event": "PROMPTFOO_RLHS_CI_RUN",
    "truth_label": "PROMPTFOO_RLHS_CI_V1",
    "ok": int(promptfoo_status) == 0 and int(pytest_status) == 0,
    "promptfoo_status": int(promptfoo_status),
    "pytest_status": int(pytest_status),
    "output_json": output_json,
    "promptfoo_log": promptfoo_log,
    "pytest_log": pytest_log,
}

path = Path(run_log)
path.parent.mkdir(parents=True, exist_ok=True)
with path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
print(json.dumps(row, ensure_ascii=False, sort_keys=True))
PY

if [ "$promptfoo_status" -ne 0 ]; then
  echo "[SIFTA RLHS CI] Promptfoo failed. Log: $PROMPTFOO_LOG" >&2
  tail -80 "$PROMPTFOO_LOG" >&2 || true
fi
if [ "$pytest_status" -ne 0 ]; then
  echo "[SIFTA RLHS CI] Pytest guard failed. Log: $PYTEST_LOG" >&2
  tail -80 "$PYTEST_LOG" >&2 || true
fi

if [ "$promptfoo_status" -ne 0 ] || [ "$pytest_status" -ne 0 ]; then
  exit 1
fi

echo "[SIFTA RLHS CI] Green. Output: $OUTPUT_JSON"
