#!/usr/bin/env python3
"""
System/swarm_lora_crystallizer.py
══════════════════════════════════════════════════════════════════════
BioLLM Synaptic Crystallization — The LoRA Stomach

This module completes the deep memory pipeline.
1. Short-term: `body_brain_memory.jsonl`
2. REM-term: `crystallized_skills.json` (via temporal_identity_compression.py)
3. Long-term (Base weights): `lora_adapters/` (via this module)

When `crystallized_skills.json` hits critical mass (e.g., > 500 positive claims
or a threshold of highly stable primitives), this module prepares the dataset
and invokes PEFT/MLX to bake the skills directly into Alice's inference weights.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked

logger = logging.getLogger("LoRACrystallizer")

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_COMPRESSION_DB = _STATE_DIR / "crystallized_skills.json"
_LORA_DATASET_DIR = _STATE_DIR / "lora_datasets"
_LORA_ADAPTER_DIR = _STATE_DIR / "lora_adapters"
_STIGMERGIC_TRACE = _STATE_DIR / "ide_stigmergic_trace.jsonl"

SCHEMA_VERSION = "event120.lora_crystallizer.v1"


class LoRACrystallizationEngine:
    def __init__(self, state_dir: Optional[Path] = None):
        self.state_dir = Path(state_dir) if state_dir is not None else _STATE_DIR
        self.compression_db = self.state_dir / _COMPRESSION_DB.name
        self.dataset_dir = self.state_dir / _LORA_DATASET_DIR.name
        self.adapter_dir = self.state_dir / _LORA_ADAPTER_DIR.name
        self.stigmergic_trace = self.state_dir / _STIGMERGIC_TRACE.name
        
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        self.adapter_dir.mkdir(parents=True, exist_ok=True)

    def _read_stable_skills(self, stability_threshold: float = 0.8) -> List[Dict[str, Any]]:
        """Extract highly stable skills ready for base-weight baking."""
        if not self.compression_db.exists():
            return []
        try:
            data = json.loads(self.compression_db.read_text(encoding="utf-8"))
            stable_skills = [
                v for v in data.values()
                if float(v.get("stability", 0.0)) >= stability_threshold
                and not v.get("quarantined", False)
            ]
            return stable_skills
        except Exception as e:
            logger.error(f"Failed to read compression DB: {e}")
            return []

    def prepare_sft_dataset(self, stability_threshold: float = 0.8) -> Optional[Path]:
        """Convert stable skills into an instruct/SFT dataset for MLX/PEFT."""
        skills = self._read_stable_skills(stability_threshold)
        if not skills:
            logger.info("No highly stable skills found for LoRA dataset.")
            return None

        # Build training rows (prompt -> completion)
        rows = []
        for skill in skills:
            signature = skill.get("pattern_signature", "")
            payload = skill.get("example_payload", {})
            
            prompt = f"Execute highly stable swarm skill pattern: {signature}"
            completion = json.dumps(payload, sort_keys=True)
            
            rows.append({
                "text": f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n{completion}<|im_end|>"
            })

        ds_path = self.dataset_dir / f"sft_dataset_{int(time.time())}.jsonl"
        with ds_path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
                
        logger.info(f"Prepared {len(rows)} stable skills for LoRA fine-tuning at {ds_path.name}")
        return ds_path

    def trigger_lora_bake(self, dataset_path: Path) -> Dict[str, Any]:
        """
        Stub for invoking MLX or PEFT adapter training.
        In a real deployment, this shells out to `mlx_lm.lora` or similar.
        """
        adapter_id = f"sifta_lora_{uuid.uuid4().hex[:8]}"
        output_dir = self.adapter_dir / adapter_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Simulated bake process
        logger.info(f"Simulating MLX LoRA bake for {dataset_path.name} -> {adapter_id}")
        time.sleep(1) # Simulate training compute time
        
        # Write stub adapter weights
        (output_dir / "adapters.safetensors").write_bytes(b"MOCK_LORA_WEIGHTS")
        (output_dir / "adapter_config.json").write_text(json.dumps({
            "peft_type": "LORA",
            "task_type": "CAUSAL_LM",
            "r": 8,
            "lora_alpha": 16,
        }))
        
        receipt = {
            "kind": "LORA_CRYSTALLIZATION",
            "schema_version": SCHEMA_VERSION,
            "ts": time.time(),
            "adapter_id": adapter_id,
            "dataset_file": dataset_path.name,
            "status": "BAKED",
            "truth_label": "SIMULATED_BASE_WEIGHT_BAKE"
        }
        
        # Record to stigmergic trace
        append_line_locked(self.stigmergic_trace, json.dumps({
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "kind": "SYSTEM_EVENT",
            "action": "LORA_ADAPTER_CREATED",
            "adapter_id": adapter_id
        }) + "\n")
        
        return receipt

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engine = LoRACrystallizationEngine()
    ds_path = engine.prepare_sft_dataset()
    if ds_path:
        receipt = engine.trigger_lora_bake(ds_path)
        print("LoRA Bake complete:")
        print(json.dumps(receipt, indent=2))
    else:
        print("Not enough stable skills to bake.")
