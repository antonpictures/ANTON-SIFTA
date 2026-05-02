# System/swarm_novelty_metabolic_gate.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class NoveltyGateFrame:
    novelty_score: float
    phase: str
    td_bias: float
    attention_gain: float
    explore_bias: float
    consolidate_bias: float
    
    def as_dict(self) -> Dict[str, Any]:
        return {
            "novelty_score": self.novelty_score,
            "phase": self.phase,
            "td_bias": self.td_bias,
            "attention_gain": self.attention_gain,
            "explore_bias": self.explore_bias,
            "consolidate_bias": self.consolidate_bias,
        }

def compute_novelty_gate(novelty_map_row: Optional[Dict[str, Any]]) -> NoveltyGateFrame:
    """
    Translates the Hippocampal Novelty Map into metabolic/value signals.
    """
    if not novelty_map_row:
        return NoveltyGateFrame(
            novelty_score=0.0,
            phase="NO_MEMORY",
            td_bias=0.0,
            attention_gain=1.0,
            explore_bias=1.0,
            consolidate_bias=1.0,
        )
    
    score = novelty_map_row.get("novelty_score", 0.0)
    phase = novelty_map_row.get("phase", "NO_MEMORY")
    drive_bias = novelty_map_row.get("drive_bias", {})
    
    # Orienting reflex / td_value modulation
    # High novelty -> higher positive TD bias (surprise is rewarding for exploration)
    # Low novelty (FAMILIAR) -> negative TD bias (boredom)
    if phase == "NOVEL":
        td_bias = 0.5 * score
        attention_gain = 1.2 + (0.3 * score)
    elif phase == "FAMILIAR":
        td_bias = -0.2 * (1.0 - score)
        attention_gain = 0.8
    else:
        td_bias = 0.0
        attention_gain = 1.0
        
    return NoveltyGateFrame(
        novelty_score=score,
        phase=phase,
        td_bias=round(td_bias, 4),
        attention_gain=round(attention_gain, 4),
        explore_bias=drive_bias.get("explore", 1.0),
        consolidate_bias=drive_bias.get("consolidate", 1.0),
    )
