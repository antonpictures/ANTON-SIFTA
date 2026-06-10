#!/usr/bin/env python3
"""Tests for Plan A3 self-surgeon v0."""

import json
import time

from System.swarm_self_surgeon import (
    DOCTOR,
    DISEASE_CLASS,
    draft_plan_from_disease,
    find_actionable_diseases,
    is_misfiring_cue_disease,
    propose_patch,
    run_self_surgeon_cycle,
    swimmer_quorum_vote,
)


def test_is_misfiring_cue_disease_detects_tracker_row():
    row = {"disease": "browser_history_over_current_page", "detail": "recall cue fired on live page"}
    assert is_misfiring_cue_disease(row) is True


def test_find_actionable_diseases_reads_tracker_ledger(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    disease = {
        "ts": time.time(),
        "disease": DISEASE_CLASS,
        "detail": "watched_memory recall regex too broad",
    }
    with (state / "stigmergic_deterministic_tracker.jsonl").open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(disease) + "\n")
    found = find_actionable_diseases(state_dir=state)
    assert len(found) == 1
    assert found[0]["disease"] == DISEASE_CLASS


def test_draft_plan_records_receipts():
    plan = draft_plan_from_disease(
        {"disease": DISEASE_CLASS, "detail": "cue regex misfired on current-page turn"}
    )
    assert "misfiring cue regex" in plan.objective.lower()
    assert len(plan.receipts) >= 2


def test_quorum_approves_when_tests_green():
    patch = {"patch_id": "p1", "python_snippet": "pass\n"}
    quorum = swimmer_quorum_vote(patch=patch, test_result={"ok": True})
    assert quorum["quorum_met"] is True


def test_self_surgeon_cycle_writes_plan_and_cycle_ledger(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    disease = {
        "ts": time.time(),
        "disease": DISEASE_CLASS,
        "detail": "recall cue regex fired instead of cortex",
        "_source_ledger": "stigmergic_deterministic_tracker.jsonl",
    }

    monkeypatch.setattr(
        "System.swarm_self_surgeon.run_named_tests",
        lambda *a, **k: {"ok": True, "returncode": 0, "stdout": "5 passed", "stderr": "", "tests": []},
    )
    monkeypatch.setattr(
        "System.swarm_self_surgeon.write_self_surgeon_receipt",
        lambda **k: {"work_receipts.jsonl": "ok"},
    )

    cycle = run_self_surgeon_cycle(disease_row=disease, state_dir=state)
    assert cycle["ok"] is True
    assert cycle["doctor"] == DOCTOR
    assert (state / "self_code_plans.jsonl").exists()
    assert (state / "self_surgeon_cycles.jsonl").exists()
    assert (state / "self_surgeon_patch_plans.jsonl").exists()