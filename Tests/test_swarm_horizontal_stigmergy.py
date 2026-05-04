#!/usr/bin/env python3
import json
import time
from pathlib import Path
from System.swarm_horizontal_stigmergy import HorizontalStigmergyEngine

def test_export_import_boundary_engrams(tmp_path: Path):
    engine = HorizontalStigmergyEngine(state_dir=tmp_path)
    
    # 1. Mock crystallized skills
    skills_db = engine.compression_db
    skills_db.parent.mkdir(parents=True, exist_ok=True)
    mock_skills = {
        "PRIM_A": {
            "id": "PRIM_A",
            "pattern_signature": "TaskA|M5",
            "stability": 0.9,
            "usage_count": 10,
            "example_payload": {"foo": "bar"}
        },
        "PRIM_B": {
            "id": "PRIM_B",
            "pattern_signature": "TaskB|M5",
            "stability": 0.5,  # should not export
            "usage_count": 2,
            "example_payload": {}
        }
    }
    skills_db.write_text(json.dumps(mock_skills))
    
    # 2. Export
    exported = engine.export_stable_skills(stability_threshold=0.8)
    assert exported == 1
    
    # 3. Import (should be 0 since node_serial matches)
    imported = engine.import_foreign_engrams()
    assert imported == 0
    
    # 4. Mock foreign engram
    foreign_row = {
        "kind": "boundary_engram",
        "schema_version": "event101.horizontal_stigmergy.v1",
        "boundary_id": "mock_foreign_123",
        "ts": time.time(),
        "node_serial": "FOREIGN_SERIAL_XYZ",
        "source_type": "skill_primitive",
        "signature": "TaskC|M1",
        "stability": 0.95,
        "usage_count": 50,
        "payload": {},
        "truth_label": "BOUNDARY_SUMMARY"
    }
    with engine.boundary_ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(foreign_row) + "\n")
        
    # 5. Import again (should grab the foreign engram)
    imported_now = engine.import_foreign_engrams()
    assert imported_now == 1
    
    # Verify cache
    cache = json.loads(engine.foreign_cache.read_text())
    assert "TaskC|M1" in cache
