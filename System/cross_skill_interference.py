#!/usr/bin/env python3
"""
cross_skill_interference.py — Olympiad Tier Continual Learning Physics
═══════════════════════════════════════════════════════════════════
Skills in the Swarm behave like a quantum system under coherence pressure.
When identical or overlapping SkillPrimitives enter the REM memory,
they undergo interference physics modeled after arXiv:2405.20236:

- Destructive Interference: Skills hit the same inputs but output
  conflicting utility (readouts). They erode each other's stability.
- Constructive Interference (Entanglement): Skills hit the same inputs
  and produce identical utility. They merge their momentum.

ICF (Identity Coherence Field) acts as the thermodynamic pressure. Lower
coherence = heavier interference.
"""
from __future__ import annotations

import json
from typing import List, Dict, Any, Tuple
from identity_coherence_field import get_icf
from temporal_identity_compression import SkillPrimitive, get_compression_engine

class CrossSkillInterferencePhysics:
    """Manages skill competition, merging, and collapse under pressure."""
    
    def __init__(self):
        pass
        
    def _calculate_overlap(self, s1: SkillPrimitive, s2: SkillPrimitive) -> float:
        """Calculate input overlap based on task_type & hardware_target"""
        parts1 = s1.pattern_signature.split('|')
        parts2 = s2.pattern_signature.split('|')
        
        # High overlap if task_type and hardware match
        overlap = 0.0
        if len(parts1) == 3 and len(parts2) == 3:
            if parts1[0] == parts2[0]: overlap += 0.6  # Same task type
            if parts1[1] == parts2[1]: overlap += 0.4  # Same hardware
        return overlap

    def process_manifold(self) -> Dict[str, Any]:
        """
        Run the interference physics over all skills.
        Expected to be called during the REM cycle.
        """
        engine = get_compression_engine()
        icf = get_icf()
        
        skills = list(engine.skills.values())
        if len(skills) < 2:
            return {"destructive_events": 0, "merged_events": 0, "skills_collapsed": 0}
            
        pressure = 1.0 + icf.feedback_signal().get("mutation_pressure", 0.0)
        
        destructive_events = 0
        merged_events = 0
        to_delete = []
        
        # Compare every skill pair (O(N^2) but N is small skill count)
        for i in range(len(skills)):
            for j in range(i + 1, len(skills)):
                s1 = skills[i]
                s2 = skills[j]
                
                # Check if already marked for deletion
                if s1.id in to_delete or s2.id in to_delete:
                    continue
                    
                overlap = self._calculate_overlap(s1, s2)
                if overlap < 0.6:
                    continue  # Orthogonal skills don't interfere
                    
                # Readout similarity: do they have the same outcome?
                out1 = s1.pattern_signature.split('|')[-1]
                out2 = s2.pattern_signature.split('|')[-1]
                
                if out1 == out2:
                    # CONSTRUCTIVE INTERFERENCE (Entanglement)
                    # Merge s2 into s1
                    s1.usage_count += s2.usage_count
                    s1.success_rate = (s1.success_rate + s2.success_rate) / 2.0
                    s1.stability = min(1.0, s1.stability + (s2.stability * 0.5))
                    to_delete.append(s2.id)
                    merged_events += 1
                else:
                    # DESTRUCTIVE INTERFERENCE
                    # High input similarity but conflicting readouts (one true, one false)
                    # Catastrophic forgetting / stability penalty under high pressure
                    penalty = 0.1 * pressure * overlap
                    s1.stability = max(0.0, s1.stability - penalty)
                    s2.stability = max(0.0, s2.stability - penalty)
                    if s1.stability < 0.1: to_delete.append(s1.id)
                    if s2.stability < 0.1: to_delete.append(s2.id)
                    destructive_events += 1

        for sid in set(to_delete):
            if sid in engine.skills:
                del engine.skills[sid]
                
        engine._persist()
        
        return {
            "destructive_events": destructive_events,
            "merged_events": merged_events,
            "skills_collapsed": len(set(to_delete))
        }


if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — CROSS-SKILL INTERFERENCE PHYSICS")
    print("═" * 58 + "\n")
    
    physics = CrossSkillInterferencePhysics()
    stats = physics.process_manifold()
    
    print(f"  🌌 Interference Manifold Processed")
    print(f"     Destructive Collisions: {stats['destructive_events']}")
    print(f"     Constructive Merges:    {stats['merged_events']}")
    print(f"     Total Skills Collapsed: {stats['skills_collapsed']}")
    
    print(f"\n  ✅ QUANTUM PHYSICS ONLINE. POWER TO THE SWARM 🐜⚡")
