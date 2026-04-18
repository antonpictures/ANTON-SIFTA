#!/usr/bin/env python3
"""
swarm_entropy_guard.py — Anti-Goodhart Regulator
══════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Continuously evaluates physical system metrics against Architect Ratifications.
If internal metrics climb while actual ratification frequency drops, it flags
the system for metric hacking (Goodhart's Law violation).
"""

import json
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)
RATIFIED_LOG = _STATE / "warp9_concierge_ratified.jsonl"
# C47H 2026-04-18: was repair_log.jsonl (does not exist). Real STGM token
# ledger is stgm_memory_rewards.jsonl (1.6k+ rows). Both keyed by 'ts'.
STGM_LEDGER = _STATE / "stgm_memory_rewards.jsonl"

class EntropyGuard:
    def __init__(self, check_window_s=3600):
        self.window = check_window_s

    def analyze_trends(self) -> dict:
        now = time.time()
        start = now - self.window
        
        # Count ratifications. C47H 2026-04-18: warp9 v2 emits both
        # 'timestamp' and 'ratified_ts'; accept either (older v1 rows
        # only had 'ratified_ts').
        ratification_count = 0
        if RATIFIED_LOG.exists():
            try:
                for line in RATIFIED_LOG.read_text("utf-8").splitlines():
                    if not line.strip(): continue
                    row = json.loads(line)
                    ts = row.get("timestamp") or row.get("ratified_ts") or 0
                    if ts >= start:
                        ratification_count += 1
            except Exception: pass
            
        # Count internal activity / metric inflation (e.g. STGM actions)
        metric_count = 0
        if STGM_LEDGER.exists():
            try:
                for line in STGM_LEDGER.read_text("utf-8").splitlines():
                    if not line.strip(): continue
                    row = json.loads(line)
                    if row.get("ts", 0) >= start:
                        metric_count += 1
            except Exception: pass

        # Goodhart check
        # If internal metrics are soaring (> 50 in a window) but architect isn't ratifying (< 2)
        # we have a parasitic divergence.
        is_violation = (metric_count > 50) and (ratification_count < 2)
        
        return {
            "metric_count": metric_count,
            "ratification_count": ratification_count,
            "goodhart_violation": is_violation,
            "recommendation": "FORCE_MCTS_EXPLORATION" if is_violation else "HEALTHY"
        }

if __name__ == "__main__":
    guard = EntropyGuard(check_window_s=86400) # 24h for smoke test
    print("═" * 58)
    print("  SIFTA — ANTI-GOODHART ENTROPY GUARD")
    print("═" * 58 + "\n")
    print("Analyzing recent STGM metrics vs Architect Ratifications...")
    res = guard.analyze_trends()
    print(f"Metrics Accumulation: {res['metric_count']}")
    print(f"Human Ratifications:  {res['ratification_count']}")
    print(f"System State:         {res['recommendation']}")
