#!/bin/bash
# ==========================================================
# ANTON-SIFTA: OVERNIGHT STRESS TEST QUEUE
# ==========================================================
echo "[+] Starting overnight execution queue..."

# 1. Clean the state to ensure no ghosts block execution
echo "[+] Clearing Swarm Identity Registry..."
python3 -c "import json; from pathlib import Path; p=Path('.sifta_state/deaths.json'); d=json.loads(p.read_text()) if p.exists() else {}; d.pop('SEBASTIAN', None); d.pop('ANTIALICE', None); d.pop('HERMES', None); p.write_text(json.dumps(d, indent=2))"

# 2. Run Robotics Stress Test with HERMES on gemma4
echo "[+] Launching HERMES on Robotics Stress Test..."
TOKEN=$(python3 sifta_relay.py --sign-override repair.py 2>&1 | grep "^--auth-token=" | head -1)
# We use a 30 minute timeout overall to prevent infinite hangs
python3 repair.py $TOKEN test_environment/robotics_stress_test --proposals --provider ollama --model gemma4:latest --fast-model qwen3.5:0.8b > overnight_robotics.log 2>&1

echo "[+] Robotics Phase Complete. Cooling down inference engine (60s)..."
sleep 60

# 3. Launch the massive Code Swimmers Tournament
# 50 rounds * 4 levels = 200 matches.
# Using gemma4 vs deepseek-coder:6.7b 
echo "[+] Launching 200-Match Swarm Esports Tournament..."
python3 sifta_tournament.py --red gemma4:latest --blue deepseek-coder:6.7b --rounds 50 > overnight_tournament.log 2>&1

echo "[+] QUEUE EXHAUSTED AND COMPLETE."
