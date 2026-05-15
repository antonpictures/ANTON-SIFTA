#!/usr/bin/env bash
set -euo pipefail

FULL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --full) FULL=1 ;;
    -h|--help)
      echo "Usage: bash scripts/beeson_smoke_test.sh [--full]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
  shift
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if [[ -d ".venv" ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

PYTHON_BIN="${PYTHON:-python3}"
export PYTHONPATH="$REPO_DIR:${PYTHONPATH:-}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"

echo "[beeson-smoke] compile core boot/runtime surfaces"
"$PYTHON_BIN" -m py_compile \
  sifta_os_desktop.py \
  Applications/sifta_alice_widget.py \
  Applications/sifta_what_alice_sees_widget.py \
  Applications/sifta_talk_to_alice_widget.py \
  Applications/sifta_epr_stigmergic_widget.py \
  Applications/sifta_double_slit_stigmergic.py \
  System/sifta_swimmer_wallpaper_field.py \
  System/stigmergic_field.py \
  System/swarm_kernel_process_table.py \
  System/swarm_field_primary_pde.py \
  System/swarm_action_pathsum.py \
  System/swarm_turing_pattern.py \
  System/swarm_active_matter_field.py

FOCUSED_TESTS=(
  tests/test_inference_settings.py
  tests/test_swarm_primary_cortex_switcher.py
  tests/test_swarm_kernel_process_table.py
  tests/test_swarm_media_ingress_gate.py
  tests/test_swarm_action_pathsum.py
  tests/test_three_directives.py
  tests/test_sifta_swimmer_wallpaper_field.py
  tests/test_sifta_desktop_module_shape.py::test_beeson_alice_eye_chrome_defaults_are_low_stress
)

if [[ "$FULL" == "1" ]]; then
  FOCUSED_TESTS+=(tests/test_sifta_desktop_module_shape.py)
fi

echo "[beeson-smoke] pytest focused release gate"
"$PYTHON_BIN" -m pytest -q "${FOCUSED_TESTS[@]}"

mkdir -p .sifta_state
"$PYTHON_BIN" - <<'PY'
from __future__ import annotations
import json, time, uuid
from pathlib import Path

row = {
    "ts": time.time(),
    "trace_id": str(uuid.uuid4()),
    "kind": "BEESON_V8_SMOKE_RECEIPT",
    "status": "PASS",
    "scope": "focused_release_gate",
}
path = Path(".sifta_state/beeson_v8_smoke_receipts.jsonl")
with path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row, sort_keys=True) + "\n")
print(f"[beeson-smoke] receipt {row['trace_id']} -> {path}")
PY

echo "[beeson-smoke] PASS"
