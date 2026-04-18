#!/bin/bash
# start_swarm_telegram.sh — Boot the SIFTA Telegram Channel

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

python3 telegram_swarm.py
