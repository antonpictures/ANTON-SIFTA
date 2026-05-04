#!/usr/bin/env python3
import json
import time
from pathlib import Path
from System.swarm_lora_crystallizer import LoRACrystallizationEngine

def test_lora_crystallizer_dataset_and_bake(tmp_path: Path):
    engine = LoRACrystallizationEngine(state_dir=tmp_path)
    
    # 1. Mock crystallized skills
    engine.compression_db.parent.mkdir(parents=True, exist_ok=True)
    mock_skills = {
        "PRIM_A": {
            "id": "PRIM_A",
            "pattern_signature": "TaskA|M5",
            "stability": 0.95,
            "usage_count": 100,
            "example_payload": {"action": "jump", "distance": 10}
        },
        "PRIM_B": {
            "id": "PRIM_B",
            "pattern_signature": "TaskB|M5",
            "stability": 0.5,  # should be ignored
            "usage_count": 2,
            "example_payload": {}
        }
    }
    engine.compression_db.write_text(json.dumps(mock_skills))
    
    # 2. Prepare dataset
    ds_path = engine.prepare_sft_dataset(stability_threshold=0.8)
    assert ds_path is not None
    assert ds_path.exists()
    
    # Verify dataset contents
    lines = ds_path.read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert "TaskA|M5" in row["text"]
    assert "jump" in row["text"]
    
    # 3. Trigger bake
    receipt = engine.trigger_lora_bake(ds_path)
    assert receipt["status"] == "BAKED"
    assert receipt["dataset_file"] == ds_path.name
    
    # Verify adapter was created
    adapter_dir = engine.adapter_dir / receipt["adapter_id"]
    assert adapter_dir.exists()
    assert (adapter_dir / "adapters.safetensors").exists()
    assert (adapter_dir / "adapter_config.json").exists()
    
    # Verify trace log
    trace_text = engine.stigmergic_trace.read_text()
    assert "LORA_ADAPTER_CREATED" in trace_text
