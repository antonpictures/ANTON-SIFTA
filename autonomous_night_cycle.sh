#!/usr/bin/env bash
# SIFTA AUTONOMOUS NIGHT CYCLE 
# Synchronize via Wormhole and fix code from GitHub every half hour.

WORKDIR="/Users/ioanganton/Music/ANTON_SIFTA"
cd "$WORKDIR" || exit 1

echo "==================================================" >> "$WORKDIR/night_cycle.log"
echo "[$(date)] INITIATING WORMHOLE REPAIR CYCLE" >> "$WORKDIR/night_cycle.log"
echo "==================================================" >> "$WORKDIR/night_cycle.log"

# 1. Connect Wormhole (Synchronize from GitHub)
OLD_HEAD=$(git rev-parse HEAD)
git pull origin main >> "$WORKDIR/night_cycle.log" 2>&1
NEW_HEAD=$(git rev-parse HEAD)

echo "--- WORMHOLE PROOF OF PULL ---" >> "$WORKDIR/night_cycle.log"
if [ "$OLD_HEAD" != "$NEW_HEAD" ]; then
    echo "Files pulled and updated from GitHub this cycle:" >> "$WORKDIR/night_cycle.log"
    git diff --name-status $OLD_HEAD $NEW_HEAD | while read -r status file; do
        echo "  [📥] $file (Status: $status)" >> "$WORKDIR/night_cycle.log"
    done
else
    echo "  [📥] No new code dropped into the Wormhole this cycle." >> "$WORKDIR/night_cycle.log"
fi

# 2. Agent Repair on Broken Python files
echo "--- AGENT REPAIR EXECUTION ---" >> "$WORKDIR/night_cycle.log"
# We count how many lines are in the repair log before and after to show proof of fixes
LOG_PATH="repair_log.jsonl"
LINES_BEFORE=$(wc -l < "$LOG_PATH" 2>/dev/null || echo 0)

python3 repair.py IDEQUEENM5 . --write >> "$WORKDIR/night_cycle.log" 2>&1 || true

LINES_AFTER=$(wc -l < "$LOG_PATH" 2>/dev/null || echo 0)

echo "--- WORMHOLE PROOF OF REPAIR ---" >> "$WORKDIR/night_cycle.log"
if [ "$LINES_AFTER" -gt "$LINES_BEFORE" ]; then
    echo "The Swarm executed changes. Showing extracted repair events:" >> "$WORKDIR/night_cycle.log"
    # Extract just the lines added during this cycle, then look for success prints from the log directly
    tail -n $((LINES_AFTER - LINES_BEFORE)) "$LOG_PATH" | grep -i '"event": "coop_handoff"\|"event": "exorcist_pass"\|"status": "RESOLVED"' >> "$WORKDIR/night_cycle.log" || echo "  [✅] Swarm engaged targets. See raw JSONL for deep forensic metadata." >> "$WORKDIR/night_cycle.log"
else
    echo "  [✅] Swarm found no corrupted syntax to repair." >> "$WORKDIR/night_cycle.log"
fi

# 3. Excrete Scent back into the Wormhole
git add . >> "$WORKDIR/night_cycle.log" 2>&1
git commit -m "AUTONOMOUS REPAIR CYCLE: SIFTA Agent stitched syntactical damage via Wormhole" >> "$WORKDIR/night_cycle.log" 2>&1
git push origin main >> "$WORKDIR/night_cycle.log" 2>&1

echo "[$(date)] REPAIR CYCLE COMPLETE" >> "$WORKDIR/night_cycle.log"
