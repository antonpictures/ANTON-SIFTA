#!/bin/bash
# start_swarm_whatsapp.sh — Boot the SIFTA WhatsApp Swarm Voice
#
# Run this once. Scan QR with your phone. Done forever.
# The Swarm will then respond to your WhatsApp messages.

set -e

export PATH="/opt/homebrew/Cellar/node/25.4.0/bin:$PATH"
NODE="/opt/homebrew/Cellar/node/25.4.0/bin/node"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   SIFTA SWARM — WhatsApp Voice Channel       ║"
echo "║   Booting both servers...                    ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ─── 1. Install Baileys bridge deps if needed ─────────────────────────────
if [ ! -d "whatsapp_bridge/node_modules" ]; then
  echo "[SETUP] Installing Baileys bridge dependencies..."
  cd whatsapp_bridge
  npm install
  cd ..
  echo "[SETUP] Done."
fi

# ─── Kill any ghost processes on port 7434 ───────────────────────────────
echo "[SETUP] Clearing port 7434..."
lsof -ti:7434 | xargs kill -9 2>/dev/null || true
sleep 1

# ─── 2. Start SIFTA Python Swarm Voice server in background ───────────────
echo "[1/2] Starting SIFTA Swarm Voice server (port 7434)..."
python3 whatsapp_swarm.py &
SIFTA_PID=$!
sleep 1

# ─── 3. Start Baileys WhatsApp Bridge ─────────────────────────────────────
echo "[2/2] Starting WhatsApp Bridge (Baileys)..."
echo "      → Open WhatsApp on your phone"
echo "      → Tap 'Linked Devices' → 'Link a Device'"
echo "      → Scan the QR code below"
echo ""
cd whatsapp_bridge
$NODE bridge.js

# ─── Cleanup on exit ──────────────────────────────────────────────────────
kill $SIFTA_PID 2>/dev/null
echo ""
echo "[🌊 SWARM] Bridge stopped. Goodbye, Architect."
