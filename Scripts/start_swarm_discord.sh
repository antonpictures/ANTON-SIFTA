#!/bin/bash
# start_swarm_discord.sh — Boot the SIFTA Discord Channel

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

python3 discord_swarm.py
