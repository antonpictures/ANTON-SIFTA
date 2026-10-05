#!/bin/bash
# start_swarm_whatsapp.sh — Boot the SIFTA WhatsApp Swarm Voice
#
# Run this once. Scan QR with your phone. Done forever.
# The Swarm will then respond to your WhatsApp messages.

set -e

if [ -d "/opt/homebrew/bin" ]; then
  export PATH="/opt/homebrew/bin:$PATH"
fi
NODE="${NODE:-$(command -v node)}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BRIDGE_DIR="$REPO_DIR/Network/whatsapp_bridge"
cd "$REPO_DIR"

if [ -z "$NODE" ]; then
  echo "[ERROR] node not found on PATH"
  exit 1
fi
if [ ! -f "$BRIDGE_DIR/bridge.js" ]; then
  echo "[ERROR] Missing bridge.js at $BRIDGE_DIR"
  exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   SIFTA SWARM — WhatsApp Voice Channel       ║"
echo "║   Booting both servers...                    ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ─── 1. Install Baileys bridge deps if needed ─────────────────────────────
if [ ! -d "$BRIDGE_DIR/node_modules" ]; then
  echo "[SETUP] Installing Baileys bridge dependencies..."
  cd "$BRIDGE_DIR"
  npm install
  cd "$REPO_DIR"
  echo "[SETUP] Done."
fi

# ─── Kill any ghost processes on local bridge ports ──────────────────────
echo "[SETUP] Clearing the kernel port 7434 and the bridge port 3010..."
lsof -ti:7434 | xargs kill -9 2>/dev/null || true
# 3010, not 3001. The old line killed whatever held 3001 -- and nginx serves a
# website there (servers/stigmergicode.conf). A start script must never take the web
# server down to make room for itself, so it checks what it is about to kill.
for PID in $(lsof -ti:3010 2>/dev/null); do
  if ps -o command= -p "$PID" 2>/dev/null | grep -qi nginx; then
    echo "[REFUSED] 3010 is held by nginx; not killing a web server"
  else
    kill -9 "$PID" 2>/dev/null || true
  fi
done
sleep 1

# ─── 2. Start SIFTA Python Swarm Voice server in background ───────────────
echo "[1/2] Starting SIFTA Swarm Voice server (port 7434)..."
PYTHONPATH="$REPO_DIR" python3 scripts/whatsapp_alice_server.py &
SIFTA_PID=$!
sleep 1

# ─── 3. Start Baileys WhatsApp Bridge ─────────────────────────────────────
echo "[2/2] Starting WhatsApp Bridge (Baileys)..."
echo "      → Open WhatsApp on your phone"
echo "      → Tap 'Linked Devices' → 'Link a Device'"
echo "      → Scan the QR code below"
echo ""
cd "$BRIDGE_DIR"
$NODE bridge.js

# ─── Cleanup on exit ──────────────────────────────────────────────────────
kill $SIFTA_PID 2>/dev/null
echo ""
echo "[🌊 SWARM] Bridge stopped. Goodbye, Architect."
