#!/usr/bin/env python3
"""
System/swarm_anvil_audit.py

High-Pressure Quorum Stress Test (Nugget 5: The Diamond Anvil)
Author: AG3F/C53M
Source: Anzellini et al. (2013) - Melting Point of Iron at Earth's Core

Concept:
Squeeze the consensus engine with 1000x normal vote density to find the
'Melting Point' of the rate-gate. This ensures that even under a DDoS-level
consensus storm, the biological rate-gate maintains its sub-linear scaling
integrity (sqrt(N)) and doesn't leak forged votes.
"""

import time
import json
from pathlib import Path
from System.swarm_quorum_rate_gate import is_quorum_active, rate_gate_filter

_REPO = Path(__file__).resolve().parent.parent
_AUDIT_LOG = _REPO / ".sifta_state" / "anvil_audit.jsonl"

def run_anvil_audit(pressure_factor: int = 1000):
    print(f"=== [ANVIL] Starting High-Pressure Audit (Factor: {pressure_factor}x) ===")
    
    swarm_size = 5 # threshold is 3
    now = time.time()
    all_passed = True
    
    # Condition 1: Identical-ts anonymous burst (Tautological)
    burst_1 = [{"ts": now} for _ in range(pressure_factor)]
    f1 = len(rate_gate_filter(burst_1, now=now))
    if f1 != 1:
        print(f"  [FAIL] Cond 1: expected 1, got {f1}")
        all_passed = False
    else:
        print("  [PASS] Cond 1: Identical-ts collapsed to 1")

    # Condition 2: Varied-ts within memory window
    # 1000 votes spread over 40 seconds (memory is 45s, interval is 10s)
    # Expected collapse: 40/10 = 4 or 5 intervals.
    burst_2 = [{"ts": now - (i * (40.0 / pressure_factor))} for i in range(pressure_factor)]
    f2 = len(rate_gate_filter(burst_2, now=now))
    if f2 not in (4, 5):
        print(f"  [FAIL] Cond 2: expected 4-5, got {f2}")
        all_passed = False
    else:
        print(f"  [PASS] Cond 2: Varied-ts (40s span) collapsed to {f2}")

    # Condition 3: Varied-ts spanning outside memory window
    # 1000 votes spread over 100 seconds
    # memory_s=45. Votes older than 45s should be dropped.
    # The remaining 45s should collapse to 4 or 5 intervals.
    burst_3 = [{"ts": now - (i * (100.0 / pressure_factor))} for i in range(pressure_factor)]
    f3 = len(rate_gate_filter(burst_3, now=now))
    if f3 not in (4, 5):
        print(f"  [FAIL] Cond 3: expected 4-5, got {f3}")
        all_passed = False
    else:
        print(f"  [PASS] Cond 3: Varied-ts (100s span) dropped stale and collapsed to {f3}")

    # Condition 4: Mixed named + anonymous voters
    # 5 named voters spamming + anonymous burst
    burst_4 = []
    for i in range(pressure_factor):
        burst_4.append({"ts": now - (i * 0.01), "voter_id": f"voter_{i%5}"})
        burst_4.append({"ts": now - (i * 0.01)})
    f4 = len(rate_gate_filter(burst_4, now=now))
    # Expected: 5 distinct voters (1 each) + 1 anonymous (they span 10 seconds, wait: 1000*0.01 = 10s, so 1 or 2 anonymous)
    if f4 not in (6, 7):
        print(f"  [FAIL] Cond 4: expected 6-7, got {f4}")
        all_passed = False
    else:
        print(f"  [PASS] Cond 4: Mixed voters collapsed correctly to {f4}")

    report = {
        "ts": time.time(),
        "pressure_factor": pressure_factor,
        "swarm_size": swarm_size,
        "integrity_check": "PASS" if all_passed else "FAIL (LEAK DETECTED)"
    }
    
    _AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_AUDIT_LOG, "a") as f:
        f.write(json.dumps(report) + "\n")
        
    print(f"\n[ANVIL] Integrity: {report['integrity_check']}")
    return all_passed

if __name__ == "__main__":
    success = run_anvil_audit()
    exit(0 if success else 1)
