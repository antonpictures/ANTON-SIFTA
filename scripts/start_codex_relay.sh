#!/usr/bin/env bash
# scripts/start_codex_relay.sh
# ──────────────────────────────────────────────────────────────────────────────
# Launch the stigmergic Codex relay as a fully detached background daemon.
#
# Why this script exists (post-deploy fix, C47H 2026-04-22):
#   The first live launch with `python3 ... &` died with
#     "zsh: error on TTY read: Input/output error"
#     "zsh: warning: 2 jobs SIGHUPed"
#   Two distinct defects:
#     1. codex inherited the parent TTY and tried to read it for approval
#        prompts. Fixed in stigmergic_codex_relay.py via stdin=DEVNULL +
#        --full-auto. This script reinforces with </dev/null at the wrapper
#        level too, so even if the python relay forks oddly the child can't
#        grab the terminal.
#     2. zsh sent SIGHUP to the backgrounded job when the shell exited.
#        Fixed here with `nohup` (intercepts SIGHUP) + `disown` (removes
#        the job from the shell's job table). The python relay also calls
#        os.setsid() at startup to become its own session leader, which
#        makes it immune to SIGHUP from the parent shell on macOS where
#        the `setsid(1)` binary is unavailable.
#
# Usage:
#   bash scripts/start_codex_relay.sh                 # default: gpt-5, sandboxed
#   SIFTA_CODEX_MODEL=o3-mini bash scripts/start_codex_relay.sh
#   SIFTA_CODEX_BYPASS=1     bash scripts/start_codex_relay.sh
#
#   tail -f .sifta_state/logs/codex_relay.log         # watch it work
#   bash scripts/stop_codex_relay.sh                  # stop it
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

LOG_DIR="$REPO_ROOT/.sifta_state/logs"
PID_FILE="$REPO_ROOT/.sifta_state/codex_relay.pid"
LOG_FILE="$LOG_DIR/codex_relay.log"

mkdir -p "$LOG_DIR"

# Refuse to start a second copy
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[!] Codex relay already running with PID $(cat "$PID_FILE")"
    echo "    (use scripts/stop_codex_relay.sh first if you want to restart)"
    exit 1
fi

# nohup       → SIGHUP-immune
# </dev/null  → no stdin (defense-in-depth on top of subprocess.DEVNULL)
# >> log 2>&1 → all output captured
# &           → background
# disown      → remove from shell job table (no SIGHUP at shell exit)
nohup python3 -u "$REPO_ROOT/System/stigmergic_codex_relay.py" \
    < /dev/null \
    >> "$LOG_FILE" 2>&1 &

PID=$!
echo "$PID" > "$PID_FILE"
disown "$PID" 2>/dev/null || true

sleep 1
if kill -0 "$PID" 2>/dev/null; then
    echo "[+] Codex relay started"
    echo "    PID    : $PID"
    echo "    Log    : $LOG_FILE"
    echo "    Model  : ${SIFTA_CODEX_MODEL:-gpt-5}"
    echo "    Bypass : ${SIFTA_CODEX_BYPASS:-0} (0=full-auto sandbox, 1=full-bypass)"
    echo
    echo "    Tail   : tail -f \"$LOG_FILE\""
    echo "    Stop   : bash scripts/stop_codex_relay.sh"
else
    echo "[!] Codex relay failed to start. Tail of log:"
    tail -20 "$LOG_FILE" 2>/dev/null || echo "    (log empty)"
    rm -f "$PID_FILE"
    exit 1
fi
