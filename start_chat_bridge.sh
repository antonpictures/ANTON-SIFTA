#!/bin/bash
# start_chat_bridge.sh — StigmergiCode web chat entity voice
# Starts the FastAPI bridge that connects stigmergicode.com to M1THER Ollama.
# Logs to .sifta_state/chat_bridge.log
# WhatsApp bridge runs separately — this is the WEB chat only.

cd "$(dirname "$0")"
export PATH="$PATH:/Users/ioanganton/Library/Python/3.9/bin"

# Kill any existing instance
pkill -f stigmergi_chat_bridge 2>/dev/null || true
sleep 1

echo "[🌐] SIFTA Chat Bridge starting — port 8090 → M1THER Ollama"
nohup python3 stigmergi_chat_bridge.py > .sifta_state/chat_bridge.log 2>&1 &
echo "[✅] Chat Bridge PID: $!"
