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



# Launch Hermes Kernel (Async background orchestrator)
echo "  [BOOT] Igniting Hermes Cognitive Kernel in background..."
python3 hermes_kernel.py > hermes_stdout.log 2>&1 &
HERMES_PID=$!

# Launch the server in the background
echo "  [BOOT] Starting SIFTA Network Server in background..."
python3 server.py > server_stdout.log 2>&1 &
SERVER_PID=$!

# Launch the graphical Python OS Desktop (FOREGROUND)
echo "  [BOOT] Launching SIFTA Python OS UI..."
python3 sifta_os_desktop.py

# Cleanup when OS Interface exits
echo "  [SHUTDOWN] Powering down Swarm threads..."
kill $HERMES_PID >/dev/null 2>&1
kill $SERVER_PID >/dev/null 2>&1

echo "  [OFFLINE] Sweet dreams, SIFTA."