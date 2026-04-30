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
echo "[SETUP] Clearing ports 7434 and 3001..."
lsof -ti:7434 | xargs kill -9 2>/dev/null || true
lsof -ti:3001 | xargs kill -9 2>/dev/null || true
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
