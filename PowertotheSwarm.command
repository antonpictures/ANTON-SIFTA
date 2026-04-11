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
pip3 install -q -r requirements.txt

echo "  [BOOT] Starting SIFTA Command Interface on http://127.0.0.1:7433"
echo ""

# Open browser after 2-second delay (in background)
(sleep 2 && open "http://127.0.0.1:7433") &

# Launch Hermes Kernel (Async background orchestrator)
echo "  [BOOT] Igniting Hermes Cognitive Kernel in background..."
python3 hermes_kernel.py &
HERMES_PID=$!

# Launch the server (blocking)
python3 server.py

# Cleanup when server exits
kill $HERMES_PID >/dev/null 2>&1
