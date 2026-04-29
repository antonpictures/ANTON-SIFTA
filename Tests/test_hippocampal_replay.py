import json
import tempfile
from pathlib import Path

import pytest
from System.swarm_hippocampal_replay import HippocampalReplay

@pytest.fixture
def sleep_env():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)

def create_mock_ledger(root: Path, filename: str, events: list):
    path = root / filename
    with path.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

def test_sleep_cycle_clears_noise_and_consolidates_memory(sleep_env):
    hr = HippocampalReplay(root=str(sleep_env))
    
    # Create raw experiences
    create_mock_ledger(sleep_env, "agency_verdicts.jsonl", [
        {"social_label": "alice_owned_action", "effector_ok": True},
        {"social_label": "alice_owned_action", "effector_ok": True},
        {"social_label": "attempt_failed_not_owned", "effector_ok": False}
    ])
    
    create_mock_ledger(sleep_env, "work_receipts.jsonl", [
        {"intent_source": "owner", "status": "ok"},
        {"intent_source": "owner", "status": "ok"}
    ])
    
    # Enter sleep cycle
    memory = hr.enter_sleep_cycle(epoch_narrative="Test consolidation")
    
    # 1. Assert memory object is structured correctly
    assert memory.event_count_compressed == 5
    assert memory.narrative_summary == "Test consolidation"
    
    # 2. Assert patterns extracted correctly
    patterns = memory.extracted_patterns
    assert patterns["total_actions"] == 5
    assert patterns["frequent_errors"] == 1
    # 4 successes, 1 failure -> 0.8
    assert patterns["success_rate"] == 0.8
    # owner=2, alice_owned_action=2, attempt_failed_not_owned=1
    # max() returns first key encountered if tied, but let's just assert it's one of them
    assert patterns["dominant_intent"] in {"alice_owned_action", "owner"}
    
    # 3. Assert raw ledgers are cleared (forgotten)
    assert (sleep_env / "agency_verdicts.jsonl").stat().st_size == 0
    assert (sleep_env / "work_receipts.jsonl").stat().st_size == 0
    
    # 4. Assert long_term_memory has the compressed memory
    ltm_path = sleep_env / "long_term_memory.jsonl"
    with ltm_path.open("r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        saved_memory = json.loads(lines[0])
        assert saved_memory["epoch_id"] == memory.epoch_id
        assert saved_memory["event_count_compressed"] == 5

def test_sleep_cycle_with_empty_ledgers(sleep_env):
    hr = HippocampalReplay(root=str(sleep_env))
    
    memory = hr.enter_sleep_cycle()
    
    assert memory.event_count_compressed == 0
    assert memory.extracted_patterns["total_actions"] == 0
    
    ltm_path = sleep_env / "long_term_memory.jsonl"
    assert ltm_path.exists()
