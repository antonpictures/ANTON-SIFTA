#!/usr/bin/env bash
# scripts/stop_codex_relay.sh — stop the detached codex relay started by
# scripts/start_codex_relay.sh. Sends SIGTERM, waits 5 s, escalates to
# SIGKILL if the daemon refuses to die.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$REPO_ROOT/.sifta_state/codex_relay.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "[*] No PID file at $PID_FILE — nothing to stop."
    exit 0
fi

PID="$(cat "$PID_FILE")"
if ! kill -0 "$PID" 2>/dev/null; then
    echo "[*] PID $PID already gone. Cleaning up stale PID file."
    rm -f "$PID_FILE"
    exit 0
fi

echo "[*] Sending SIGTERM to codex relay PID $PID..."
kill -TERM "$PID" 2>/dev/null || true

for i in 1 2 3 4 5; do
    sleep 1
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "[+] Codex relay PID $PID stopped cleanly."
        rm -f "$PID_FILE"
        exit 0
    fi
done

echo "[!] PID $PID did not exit on SIGTERM. Sending SIGKILL."
kill -KILL "$PID" 2>/dev/null || true
rm -f "$PID_FILE"
echo "[+] Codex relay PID $PID killed."
