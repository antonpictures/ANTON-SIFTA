import json
from pathlib import Path
from datetime import datetime, timezone
import time
import pprint

import pheromone

ROOT_DIR = Path(__file__).parent
REPAIR_LOG = ROOT_DIR / "repair_log.jsonl"

def analyze_and_govern():
    """
    Crawls the repair ledger to detect economic loops where agents endlessly throw compute
    at an unfixable file. If suppression threshold is met, the GOVERNOR drops a blindfold scar.
    """
    if not REPAIR_LOG.exists():
        return

    history = {}
    current_target = None

    print("[GOVERNOR] Initiating anomaly sweep on Swarm execution ledger...")
    
    with open(REPAIR_LOG, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            try:
                record = json.loads(line)
                event = record.get("event")
                
                if event == "swim_start":
                    current_target = record.get("target")
                    if current_target and current_target not in history:
                        history[current_target] = {"failures": 0, "last_ts": ""}
                
                elif event == "swim_complete" and current_target:
                    fixed = record.get("fixed", 0)
                    errors = record.get("errors", 0)
                    
                    if fixed > 0:
                        history[current_target]["failures"] = 0
                    elif errors > 0:
                        history[current_target]["failures"] += 1
                        history[current_target]["last_ts"] = record.get("ts", "")
                    
                    current_target = None
                    
            except json.JSONDecodeError:
                continue

    # Identify anomalies
    THRESHOLD = 5
    suppression_count = 0
    
    for target, data in history.items():
        if data["failures"] >= THRESHOLD:
            target_path = Path(target)
            if target_path.is_file():
                mark_cwd = target_path.parent
                rel = target_path.name
                
                # Check if it already has a SUPPRESSED scar in recently dropped scars
                # We do a lightweight check via pheromone.smell_territory to prevent dropping thousands of scars.
                existing = pheromone.smell_territory(mark_cwd)
                already_suppressed = any(
                    s.get("stigmergy", {}).get("status") == "SUPPRESSED" and rel in s.get("mark", "")
                    for s in existing
                )
                
                if not already_suppressed:
                    print(f"  [⚠️ ANOMALY] Loop detected on {target_path}. Failures: {data['failures']}")
                    pheromone.drop_scar(
                        directory=mark_cwd,
                        agent_state={"id": "GOVERNOR", "face": "[👁️\u200d🗨️]"},
                        action="GOVERN",
                        found=str(rel),
                        status="SUPPRESSED",
                        mark_text=f"Loop suppression lock placed on {rel} due to {data['failures']} consecutive failures.",
                        reason={"type": "Governor Overload", "message": "File exceeds compute budget."}
                    )
                    print(f"  [🛡️ ENFORCEMENT] SUPPRESSED marker dropped for {rel}.")
                    suppression_count += 1

    if suppression_count == 0:
        print("[GOVERNOR] Network is stable. No loops detected.")
    else:
        print(f"[GOVERNOR] Sweep complete. Suppressed {suppression_count} recursive vectors.")

if __name__ == "__main__":
    analyze_and_govern()
