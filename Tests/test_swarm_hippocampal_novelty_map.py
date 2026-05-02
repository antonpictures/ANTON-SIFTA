# tests/test_swarm_hippocampal_novelty_map.py

import json
from pathlib import Path
from System.swarm_hippocampal_novelty_map import compute_novelty, write_novelty_map

def test_hippocampal_empty_state_is_no_memory(tmp_path: Path):
    row = compute_novelty(tmp_path)
    assert row["phase"] == "NO_MEMORY"
    assert row["novelty_score"] == 0.0

def test_hippocampal_repeated_ticks_is_familiar(tmp_path: Path):
    body = tmp_path / "body_brain_memory.jsonl"
    body.parent.mkdir(parents=True, exist_ok=True)
    # Write identical rows
    with body.open("w") as f:
        for _ in range(10):
            f.write(json.dumps({"action": "standby"}) + "\n")
            
    row = compute_novelty(tmp_path)
    assert row["phase"] == "FAMILIAR"
    assert row["novelty_score"] < 0.25

def test_hippocampal_diverse_ticks_is_novel(tmp_path: Path):
    body = tmp_path / "body_brain_memory.jsonl"
    body.parent.mkdir(parents=True, exist_ok=True)
    # Write unique rows
    with body.open("w") as f:
        for i in range(10):
            f.write(json.dumps({"action": f"explore_{i}"}) + "\n")
            
    row = compute_novelty(tmp_path)
    assert row["phase"] == "NOVEL"
    assert row["novelty_score"] > 0.72

def test_hippocampal_write_path_smoke_test(tmp_path: Path):
    row = write_novelty_map(tmp_path)
    assert (tmp_path / "hippocampal_novelty_map.jsonl").exists()
    assert row["truth_label"] == "SIMULATED_HIPPOCAMPAL_NOVELTY"
