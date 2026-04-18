#!/bin/bash
# ════════════════════════════════════════════════════════
#  ANTON-SIFTA — Power to the Swarm
#  Boot sequence for the Command Interface
# ════════════════════════════════════════════════════════
cd "$(dirname "$0")"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║     ANTON-SIFTA // POWER TO THE SWARM   ║"
echo "  ║        Initializing Boot Sequence...     ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# Check Python3
if ! command -v python3 &>/dev/null; then
    echo "  [ERROR] python3 not found. Install it first."
    read -p "  Press any key to exit..."
    exit 1
fi

# Install/upgrade dependencies
echo "  [BOOT] Checking dependencies..."
python3 -m pip install -q -r requirements.txt

# ── C47H 2026-04-18 (Architect-ratified surgical revert): ────────────────────
# The previous bootloader spawned `hermes_kernel.py` and `server.py` in the
# background, but neither file exists in this repo. They printed cheerful
# "Igniting..." lines and then silently filled `hermes_stdout.log` and
# `server_stdout.log` with "[Errno 2] No such file or directory" forever.
# SIFTA is an honest OS — it doesn't lie to its nodes about what's running.
# The desktop UI below is the entire boot sequence. Future background services
# (relay, kernel daemon, etc.) get added back here only when their files exist.
# ─────────────────────────────────────────────────────────────────────────────

# Launch the graphical Python OS Desktop (FOREGROUND)
echo "  [BOOT] Launching SIFTA Python OS UI..."
python3 sifta_os_desktop.py

echo "  [OFFLINE] Sweet dreams, SIFTA."