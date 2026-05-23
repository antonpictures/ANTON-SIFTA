# tests/test_swarm_orienting_reflex.py

import json
from pathlib import Path
from System.swarm_orienting_reflex import compute_orienting_reflex, write_orienting_reflex

def test_orienting_reflex_empty(tmp_path: Path):
    row = compute_orienting_reflex(tmp_path)
    assert row["novelty_score"] == 0.0
    assert row["integrated_salience"] == 0.0
    assert row["orient_trigger"] is False
    assert row["orienting_intensity"] == 0.0
    assert row["command"]["attention_gain"] == 1.0

def test_orienting_reflex_high_signals(tmp_path: Path):
    novelty_path = tmp_path / "hippocampal_novelty_map.jsonl"
    novelty_path.write_text(json.dumps({"novelty_score": 0.9}))
    
    colliculus_path = tmp_path / "superior_colliculus.jsonl"
    colliculus_path.write_text(json.dumps({"integrated_salience": 0.8}))
    
    row = compute_orienting_reflex(tmp_path)
    assert row["novelty_score"] == 0.9
    assert row["integrated_salience"] == 0.8
    assert row["orient_trigger"] is True
    assert row["orienting_intensity"] > 0.6
    assert row["command"]["attention_gain"] > 1.0
    assert row["truth_label"] == "SIMULATED_ORIENTING_REFLEX"

def test_orienting_reflex_write(tmp_path: Path):
    row = write_orienting_reflex(tmp_path)
    assert (tmp_path / "orienting_reflex.jsonl").exists()
    assert "trace_id" in row
