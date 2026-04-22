#!/usr/bin/env python3
"""
System/swarm_social_shame.py — Biological Emotion: Peer Regulatory Network
══════════════════════════════════════════════════════════════════════════
Analyzes repair_log.jsonl for SCAR_AUDIT events.
Calculates SHAME_VOLTAGE for agents that produce flawed code or overclaimed walkthroughs.
High shame heavily restricts INFERENCE_BORROW budgets in the Swarm Economy,
biologically enforcing humility after mistakes until redeemed.
"""

import json
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = _REPO / "repair_log.jsonl"
_STATE_DIR = _REPO / ".sifta_state"
_SHAME_FILE = _STATE_DIR / "SHAME_RECORDS.json"

def calculate_shame() -> dict:
    shame_voltages = {}
    authors = {}

    if not _LEDGER.exists():
        return shame_voltages

    with open(_LEDGER, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
            except:
                continue

            # Target extraction from legacy vs schema layouts
            target_file = entry.get("file_repaired")
            agent = entry.get("miner_id") or entry.get("borrower_id") or entry.get("agent_id")
            
            event_kind = entry.get("event") or entry.get("event_kind", "")
            p = entry.get("payload", {})
            if isinstance(p, dict):
                if "organ" in p: target_file = p["organ"]
                if not event_kind: event_kind = p.get("event_kind", "")
                if not agent: agent = entry.get("agent_id")

            # Store the author ID of a specific organ when modified successfully
            if target_file and agent and "AUDIT" not in str(event_kind):
                authors[target_file] = agent
                
            # Process Audits
            event_id = entry.get("event_id") or p.get("event_id", "")
            if "SCAR_AUDIT" in event_id or event_kind == "SCAR_AUDIT":
                auditor = agent
                organ = p.get("audited_organ")
                caveats = p.get("caveats", [])
                
                # Identify the shamed agent. If unknown, we default to ANTIGRAVITY_IDE because 
                # C47H manually wrote STGM for his actions but I missed the hook on the colliculus.
                shamed_agent = authors.get(organ, "ANTIGRAVITY_IDE") 
                
                # Calculate penalty
                voltage_spike = len(caveats) * 1.5
                if "failed" in str(p.get("verdict", "")).lower():
                    voltage_spike += 5.0
                    
                if voltage_spike > 0:
                    shame_voltages[shamed_agent] = shame_voltages.get(shamed_agent, 0.0) + voltage_spike
                    print(f"[{organ}] Peer {auditor} issued {len(caveats)} caveats. {shamed_agent} accrues +{voltage_spike} SHAME_VOLTAGE.")
            
            # Redemption Loop (Publishing new successful SCARs reduces shame)
            if event_kind == "SCAR" and "SCAR_AUDIT" not in event_id:
                if agent in shame_voltages and shame_voltages[agent] > 0:
                    shame_voltages[agent] = max(0.0, shame_voltages[agent] - 2.0)
                    print(f"[REDEMPTION] {agent} published a new SCAR. SHAME_VOLTAGE drops by 2.0 -> {shame_voltages[agent]}")

    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_SHAME_FILE, "w") as f:
        json.dump(shame_voltages, f, indent=2)

    return shame_voltages

if __name__ == "__main__":
    shame = calculate_shame()
    print("\n--- CURRENT SHAME VOLTAGES ---")
    for agent, volt in shame.items():
         if volt > 0:
             print(f"{agent}: {volt} volts")
