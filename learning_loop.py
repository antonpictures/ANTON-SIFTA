# learning_loop.py
"""
LEARNING LOOP — Phase 2: Cautious Rule Extraction

Extracts long-term rules from short-term stress, but ONLY when the system
is completely calm (Parasympathetic Dominance).
If a file repeatedly causes panic triggers, it creates a Muscle Memory rule 
bypassing future evaluation to save processing overhead.
"Selective memory formation under stability constraints."
"""

import asyncio
import json
from pathlib import Path
from state_bus import get_state, set_state

DECISION_LOG = Path(".sifta_state/decision_trace.log")

async def learning_loop():
    """
    Background worker that runs pattern extraction only when the Swarm is not panicked.
    """
    last_processed_line = 0

    while True:
        try:
            volatility = get_state("volatility_score", 0.1)
            is_medbay = get_state("MEDBAY_ACTIVE", False)

            # Cautious Learning Boundary: We only learn when the trauma has passed and we are not in Medbay coma.
            if isinstance(volatility, (int, float)) and volatility <= 0.25 and not is_medbay:
                
                if DECISION_LOG.exists():
                    with open(DECISION_LOG, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        
                    new_lines = lines[last_processed_line:]
                    
                    if new_lines:
                        # Parse the new trace logs
                        blocked_targets = {}
                        for line in new_lines:
                            try:
                                entry = json.loads(line)
                                if entry.get("allowed") is False:
                                    target = entry.get("target")
                                    reason = entry.get("reason", "")
                                    
                                    # We don't learn from random low confidence, we learn from structural blocks
                                    if "LOW_STABILITY" in reason or "GUARD_BLOCK" in reason:
                                        if target not in blocked_targets:
                                            blocked_targets[target] = 0
                                        blocked_targets[target] += 1
                            except json.JSONDecodeError:
                                continue

                        # Evaluate aggregated block patterns
                        current_muscle_memory = get_state("muscle_memory", {})
                        learning_occurred = False
                        
                        for target, block_count in blocked_targets.items():
                            # If a target was structurally blocked 5+ times, it is a persistent hazard
                            if block_count >= 5 and target not in current_muscle_memory:
                                current_muscle_memory[target] = "RESTRICTED (Extracted Rule: High Volatility Trigger)"
                                print(f"\n[🧠 LEARNING LOOP] Extracted Rule: Access to '{target}' is now permanently RESTRICTED.")
                                learning_occurred = True
                                
                        if learning_occurred:
                            # Commit the new rules to the autonomic Nervous System
                            set_state("muscle_memory", current_muscle_memory)
                            
                        last_processed_line = len(lines)
            
        except Exception as e:
            print(f"[LEARNING LOOP ERROR] {e}")

        # Cycle every 10 seconds to keep overhead extremely low
        await asyncio.sleep(10)
