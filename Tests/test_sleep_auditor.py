import json
import tempfile
from pathlib import Path

import pytest
from System.swarm_sleep_auditor import SleepAuditor
from System.swarm_hippocampal_replay import HippocampalReplay

@pytest.fixture
def neuro_env():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)

def create_mock_ledger(root: Path, filename: str, events: list):
    path = root / filename
    with path.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

def test_sleep_auditor_proves_consolidation(neuro_env):
    # Setup the environment
    hr = HippocampalReplay(root=str(neuro_env))
    auditor = SleepAuditor(root=str(neuro_env))
    
    # 1. Fill the raw ledgers with heavy noise (simulated daily experiences)
    create_mock_ledger(neuro_env, "work_receipts.jsonl", [{"id": i, "status": "ok"} for i in range(50)])
    create_mock_ledger(neuro_env, "agency_verdicts.jsonl", [{"id": i, "social_label": "alice_owned_action"} for i in range(50)])
    
    # 2. Measure PRE-SLEEP state
    pre_metrics = auditor.measure_pre_sleep()
    assert pre_metrics["event_count"] == 100
    assert pre_metrics["total_bytes"] > 0
    assert pre_metrics["ltm_bytes"] == 0
    
    # 3. Trigger Biological Sleep Cycle
    consolidated_memory = hr.enter_sleep_cycle(epoch_narrative="Audited test sleep")
    
    # 4. Measure POST-SLEEP state and verify
    report = auditor.audit_post_sleep(pre_metrics, consolidated_memory)
    
    # Audit assertions
    assert report.glymphatic_cleanup_ok is True, "Failed to delete metabolic noise"
    assert report.synaptic_homeostasis_ok is True, "Failed to prune events"
    assert report.noise_deleted == pre_metrics["total_bytes"], "Ledgers were not fully cleared"
    
    # Identity preservation (from 100 events, it should extract a few core patterns)
    assert report.identity_facts_preserved > 0, "No identity facts extracted"
    
    # Compression ratio (100 raw JSON objects compressed into 1 dense narrative object should yield a high ratio)
    assert report.receipt_compression_ratio > 1.0, "Sleep did not compress data effectively"
    assert report.post_sleep_bytes == 0, "Raw ledgers should be empty post-sleep"
    
    # Long Term Memory Integrity
    assert report.post_sleep_integrity_hash != "", "LTM hash missing"

def test_sleep_auditor_handles_empty_sleep(neuro_env):
    hr = HippocampalReplay(root=str(neuro_env))
    auditor = SleepAuditor(root=str(neuro_env))
    
    pre_metrics = auditor.measure_pre_sleep()
    assert pre_metrics["event_count"] == 0
    
    memory = hr.enter_sleep_cycle()
    report = auditor.audit_post_sleep(pre_metrics, memory)
    
    assert report.glymphatic_cleanup_ok is True
    assert report.synaptic_homeostasis_ok is True
    assert report.noise_deleted == 0
    assert report.receipt_compression_ratio == 1.0
