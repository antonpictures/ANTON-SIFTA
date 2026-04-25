#!/usr/bin/env python3
"""
scripts/execute_epigenetic_cycle.py

Gap 3: End-to-end first cycle (proof in production)

This script manually forces the epigenetic consolidation cycle:
1. Compiles the corpus (swarm_corpus_builder)
2. Trains the LoRA adapter (swarm_epigenetic_trainer)
3. Computes pheromone strength (swarm_adapter_pheromone_scorer) - this is done automatically inside the trainer now.
4. Registers the adapter (swarm_stigmergic_weight_ecology) - this is done automatically inside the trainer now.
5. Builds the merge recipe (swarm_stigmergic_weight_ecology plan)
"""

import time
import json
from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_corpus_builder import build_hf_corpus
from System.swarm_epigenetic_trainer import train_adapter
from System.swarm_stigmergic_weight_ecology import (
    plan_from_registry,
    ADAPTER_REGISTRY,
    MERGE_PLAN_LEDGER,
    MERGE_RECIPE_PATH,
    REPLAY_EVAL_LEDGER,
)

def main():
    print("==============================================")
    print(" SIFTA EPIGENETIC CONSOLIDATION CYCLE: START")
    print("==============================================")
    
    # Step 1: Build Corpus
    print("\n[Step 1] Compiling Somatic Corpus...")
    corpus_path = build_hf_corpus()
    
    # Step 2 & 3 & 4: Train Adapter, Score Pheromone, Register
    print("\n[Step 2-4] Training Epigenetic Adapter, Scoring Pheromone, Registering...")
    ts = int(time.time())
    adapter_name = f"alice_epigenetic_adapter_{ts}"
    
    try:
        # Defaulting to an ungated Qwen model for the test run so it doesn't crash on auth or memory
        # In actual production, this would be the specific model deployed on the node
        base_model_id = "Qwen/Qwen1.5-0.5B-Chat" 
        output_dir = train_adapter(base_model_id=base_model_id, output_name=adapter_name)
    except Exception as e:
        print(f"\n[!] Training failed: {e}")
        return
        
    # Step 5: Build Merge Plan
    print("\n[Step 5] Building Epigenetic Merge Plan...")
    try:
        plan = plan_from_registry(
            registry_path=ADAPTER_REGISTRY,
            ledger_path=MERGE_PLAN_LEDGER,
            recipe_path=MERGE_RECIPE_PATH,
            base_model=base_model_id,
            replay_ledger_path=REPLAY_EVAL_LEDGER,
        )
        print("\n=== MERGE PLAN GENERATED ===")
        print(f"Selected Adapters: {[s['adapter_id'] for s in plan['selected']]}")
        print(f"Rejected Adapters: {[s['adapter_id'] for s in plan['rejected']]}")
        print(f"Plan SHA256: {plan['plan_sha256']}")
        print(f"Recipe written to: {MERGE_RECIPE_PATH}")
    except Exception as e:
        print(f"\n[!] Planning failed: {e}")
        return

    print("\n==============================================")
    print(" SIFTA EPIGENETIC CONSOLIDATION CYCLE: COMPLETE")
    print("==============================================")

if __name__ == "__main__":
    main()
