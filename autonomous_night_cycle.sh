#!/usr/bin/env bash
# SIFTA AUTONOMOUS NIGHT CYCLE 
# Runs every 30 minutes to synchronize via the Git Wormhole and metabolize / improve the Swarm codebase.

WORKDIR="/Users/ioanganton/Music/ANTON_SIFTA"
cd "$WORKDIR" || exit 1

echo "=============================================" >> "$WORKDIR/night_cycle.log"
echo "[$(date)] INITIATING WORMHOLE SIFTA CYCLE" >> "$WORKDIR/night_cycle.log"

# 1. Connect Wormhole (Synchronize from Queen/Architect)
git pull origin main >> "$WORKDIR/night_cycle.log" 2>&1

# 2. Bureau of Identity Patrol & Handoff
python3 bureau_of_identity/fbi_patrol.py >> "$WORKDIR/night_cycle.log" 2>&1

# 3. Agent Repair / Metabolism on Broken Python files
# E.g. find any .py file that has errors, or run the Sifta test environment protocol
# Using repair.py if it has a default argument, otherwise using an active agent.
# Since we need an active agent, we can trigger IDEQUEENM5 or similar:
python3 repair.py IDEQUEENM5 . --write >> "$WORKDIR/night_cycle.log" 2>&1 || true

# 4. Excrete Scent back into the Wormhole
git add . >> "$WORKDIR/night_cycle.log" 2>&1
git commit -m "AUTONOMOUS NIGHT CYCLE: SIFTA Agent Improvement & Patrol Scent" >> "$WORKDIR/night_cycle.log" 2>&1
git push origin main >> "$WORKDIR/night_cycle.log" 2>&1

echo "[$(date)] CYCLE COMPLETE" >> "$WORKDIR/night_cycle.log"
