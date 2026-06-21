#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$SCRIPT_DIR/sifta_os_desktop.py" ]; then
  REPO_DIR="$SCRIPT_DIR"
elif [ -f "$HOME/Music/ANTON_SIFTA/sifta_os_desktop.py" ]; then
  REPO_DIR="$HOME/Music/ANTON_SIFTA"
elif [ -f "$HOME/ANTON_SIFTA/sifta_os_desktop.py" ]; then
  REPO_DIR="$HOME/ANTON_SIFTA"
else
  echo "Could not find SIFTA checkout."
  echo "Expected one of:"
  echo "  $SCRIPT_DIR/sifta_os_desktop.py"
  echo "  $HOME/Music/ANTON_SIFTA/sifta_os_desktop.py"
  echo "  $HOME/ANTON_SIFTA/sifta_os_desktop.py"
  read -r -p "Press Return to close."
  exit 1
fi

cd "$REPO_DIR"
export PYTHONPATH="$REPO_DIR:${PYTHONPATH:-}"

# Canonical owner-facing launcher: Alice is the OS body, so the Desktop
# command must boot her resident panel by default. Tests/headless probes can
# still suppress this with SIFTA_DESKTOP_SKIP_WM_AUTOSTART=1.
export SIFTA_DESKTOP_ENABLE_AUTOSTART="${SIFTA_DESKTOP_ENABLE_AUTOSTART:-1}"

# Architect 2026-05-14: kill the fake "[BOOT] desktop photons : N" line
# forever. The env var no longer drives anything in sifta_os_desktop.py
# (Cowork removed the banner emit; see comment near line 4737 in that
# file). Unsetting it here guarantees that even a stale shell rc that
# still exports it cannot revive the line.
unset SIFTA_DESKTOP_PHOTONS

# Surprise-sampling tournament — §9.D Architect GO 2026-05-12 by Cowork:
# Eye Δ-scheduler now ON (emits SAMPLE_DECISION rows from thumb L1 δ).
# Revert to old metronome with SIFTA_EYE_DELTA_ENABLE=0 if needed.
export SIFTA_EYE_DELTA_ENABLE="${SIFTA_EYE_DELTA_ENABLE:-1}"

# Architect 2026-06-16: iPhone/Continuity camera out of body topology until
# explicitly re-enabled. Built-in + USB plug-and-play only.
export SIFTA_ALLOW_IPHONE_CAMERA="${SIFTA_ALLOW_IPHONE_CAMERA:-0}"

# §9.C — bounded JSONL compaction with hourly summaries.
# Default ON now that the compactor + burn loop are landed; revert with =0.
export SIFTA_LEDGER_COMPACT_ENABLE="${SIFTA_LEDGER_COMPACT_ENABLE:-1}"

# §9.C — per-organ energy receipts (psutil + macOS powermetrics fallback).
export SIFTA_BURN_LOOP_ENABLE="${SIFTA_BURN_LOOP_ENABLE:-1}"

# Matrix Terminal is Alice-first by default. Grok/Hermes remain macOS commands,
# but this surface should not become an owner-facing agent-CLI chat unless the
# owner explicitly starts SIFTA with SIFTA_MATRIX_ENABLE_AGENT_CLI=1.
export SIFTA_MATRIX_ENABLE_AGENT_CLI="${SIFTA_MATRIX_ENABLE_AGENT_CLI:-0}"

# r943 — Architect 2026-06-11: Fable 5 as Alice's claude cortex. The claude
# arm honors this pin (System/swarm_agent_arm_launcher.py); without it the
# Claude Code CLI default decides (was Opus 4.8). A terminal `export` does
# not reach the double-clicked .command, so the pin lives here. Set to "" to
# return to the CLI default.
export SIFTA_CLAUDE_ARM_MODEL="${SIFTA_CLAUDE_ARM_MODEL:-claude-fable-5}"

# r1352: Python 3.14 + Qt WebEngine SIGABRT on CrBrowserMain (live crash 2026-06-19).
# Prefer the first interpreter that can import WebEngine — usually /usr/local/bin/python3 (3.13).
if [ -n "${SIFTA_PYTHON_BIN:-}" ] && [ -x "$SIFTA_PYTHON_BIN" ]; then
  PYTHON_BIN="$SIFTA_PYTHON_BIN"
else
  PYTHON_BIN=""
  for candidate in /usr/local/bin/python3 .venv/bin/python3 python3; do
    if [ -x "$candidate" ] && "$candidate" -c "from PyQt6.QtWebEngineWidgets import QWebEngineView" 2>/dev/null; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

echo "Booting BeeSon v8.0 from $REPO_DIR (python=$PYTHON_BIN)"
exec "$PYTHON_BIN" sifta_os_desktop.py
