#!/usr/bin/env python3
"""
swarm_attention_router.py — Scarcity-Based Compute Allocator
══════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Routes compute budget mathematically based on attention scarcity.
Instead of equal distribution, it weights novelty, risk, and expected reward.
"""

from dataclasses import dataclass
from typing import Dict, Any, List
import time

try:
    from System.swarm_prediction_cache import PredictionCache
except ImportError:
    class PredictionCache:
        def predict(self, s, a): return 0.5
        def ingest_ledgers(self): pass

@dataclass
class SwarmEvent:
    event_id: str
    state_context: str
    action_kind: str
    novelty_score: float   # 0.0 to 1.0
    risk_score: float      # 0.0 to 1.0

class AttentionRouter:
    def __init__(self, novelty_w=0.4, risk_w=0.4, reward_w=0.2):
        self.novelty_weight = novelty_w
        self.risk_weight = risk_w
        self.reward_weight = reward_w
        self.pc = PredictionCache()

    def calculate_budget(self, event: SwarmEvent) -> str:
        """
        Calculates the amount of compute/attention to spend.
        High   -> Full Pipeline (Inferior Olive + Cerebellum MCTS)
        Medium -> Quick probabilities (Inferior Olive Only)
        Low    -> Auto-execute or Ignore (Habitual execution)
        """
        # Ensure latest feedback is loaded
        self.pc.ingest_ledgers()

        # Get expected ratification reward (normalized 0 to 1 for this calc)
        # Prediction cache returns -1.0 to 1.0. 
        # A very positive expectation OR a very negative expectation means high certainty (low attention needed).
        # We need attention when uncertainty is high (expectation near 0.0).
        raw_reward = self.pc.predict(event.state_context, event.action_kind)
        uncertainty = 1.0 - abs(raw_reward) 

        attention_score = (
            self.novelty_weight * event.novelty_score +
            self.risk_weight * event.risk_score +
            self.reward_weight * uncertainty
        )

        if attention_score >= 0.7:
            return "CEREBELLAR_MCTS_FULL_PIPELINE"   # C47H 2026-04-18: typo fix (was CEREREBELLAR)
        elif attention_score >= 0.4:
            return "INFERIOR_OLIVE_ONLY"
        else:
            return "AUTO_HABITUAL"

if __name__ == "__main__":
    router = AttentionRouter()
    print("═" * 58)
    print("  SIFTA — ATTENTION SCARCITY ROUTER")
    print("═" * 58 + "\n")
    
    # Simulate a highly novel, risky action
    e_risky = SwarmEvent("E01", "root_dir", "delete_cache", novelty_score=0.9, risk_score=0.9)
    print(f"Risky Action routing: {router.calculate_budget(e_risky)}")

    # Simulate a completely mapped, boring habitual ping
    e_boring = SwarmEvent("E02", "idle", "stat_check", novelty_score=0.0, risk_score=0.05)
    print(f"Habitual Ping routing: {router.calculate_budget(e_boring)}")
