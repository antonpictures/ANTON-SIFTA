import json
from pathlib import Path

from System.swarm_interaction_borg import (
    NASH_SOLVER_FOR_TALK,
    coach_decompose_task,
    credit_assign_doctor,
    infer_interaction_mode,
    remember_interaction_turn,
    talk_coordination_policy,
)
from System.stigmergic_memory_bus import INTERACTION_MODES, StigmergicMemoryBus


def test_infer_interaction_modes():
    assert infer_interaction_mode("cowatch youtube", app_context="fiction_lane") == "FICTION_COWATCH"
    assert infer_interaction_mode("yield left at the aisle", app_context="talk") == "YIELD_LEFT"
    assert infer_interaction_mode("George, what time is it?", app_context="talk_to_alice") == "DYAD_GEORGE_ALICE"


def test_remember_interaction_turn_writes_ledger_and_receipt(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    ledger = state / "memory_ledger.jsonl"
    monkeypatch.setattr("System.stigmergic_memory_bus.LEDGER_DIR", state)
    monkeypatch.setattr("System.stigmergic_memory_bus.LEDGER_FILE", ledger)
    monkeypatch.setattr("System.stigmergic_memory_bus.STGM_LOG_FILE", state / "stgm_memory_rewards.jsonl")
    monkeypatch.setattr(
        "System.stigmergic_memory_bus.MEMORY_EPISTEMOLOGY_AUDIT",
        state / "memory_epistemology_audit.jsonl",
    )

    receipt = remember_interaction_turn(
        "George, remember we ship pytest before praise.",
        architect_id="TEST_ARCH",
        app_context="talk_to_alice",
        role="user",
        state_dir=state,
        force=True,
    )
    assert receipt is not None
    assert receipt["interaction_mode"] == "DYAD_GEORGE_ALICE"

    raw = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert raw["interaction_mode"] == "DYAD_GEORGE_ALICE"
    assert raw["epistemic_label"] in ("HYPOTHESIS", "OBSERVED", "BELIEF")

    receipts = (state / "borg_interaction_receipts.jsonl").read_text(encoding="utf-8").strip()
    assert "SWARM_INTERACTION_BORG_V1" in receipts


def test_remember_skips_noise(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    ledger = state / "memory_ledger.jsonl"
    monkeypatch.setattr("System.stigmergic_memory_bus.LEDGER_DIR", state)
    monkeypatch.setattr("System.stigmergic_memory_bus.LEDGER_FILE", ledger)

    out = remember_interaction_turn("hello", app_context="talk_to_alice", role="user", state_dir=state)
    assert out is None
    assert not ledger.exists()


def test_credit_assign_doctor_key(tmp_path):
    row = credit_assign_doctor(
        organ_id="cursor_m5",
        trace_id="abc123",
        source_ledger="ide_stigmergic_trace",
        tick_id=42,
        amount_stgm=0.15,
        reason="MEMORY_RECALL",
        doctor_label="CG55M@cursor",
        state_dir=tmp_path,
    )
    assert len(row["economic_attribution_key"]) == 64
    assert row["doctor_label"] == "CG55M@cursor"
    log = (tmp_path / "borg_credit_attribution.jsonl").read_text(encoding="utf-8")
    assert "cursor_m5" in log


def test_coach_decompose_task(tmp_path):
    plan = coach_decompose_task(
        "Ship memory epistemology slice",
        [
            {"name": "labels", "pytest_target": "tests/test_memory_epistemology.py"},
            {"name": "hybrid recall", "pytest_target": "tests/test_hybrid_recall.py"},
        ],
        state_dir=tmp_path,
    )
    assert plan["plan_id"]
    assert len(plan["sub_skills"]) == 2
    body = (tmp_path / "hippocampus_coach_tasks.jsonl").read_text(encoding="utf-8")
    assert "pytest_gate" in body


def test_talk_policy_no_nash():
    pol = talk_coordination_policy()
    assert pol["nash_solver_for_talk"] is False
    assert NASH_SOLVER_FOR_TALK is False


def test_bus_interaction_mode_field(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    ledger = state / "memory_ledger.jsonl"
    monkeypatch.setattr("System.stigmergic_memory_bus.LEDGER_DIR", state)
    monkeypatch.setattr("System.stigmergic_memory_bus.LEDGER_FILE", ledger)
    monkeypatch.setattr("System.stigmergic_memory_bus.STGM_LOG_FILE", state / "stgm.jsonl")
    monkeypatch.setattr(
        "System.stigmergic_memory_bus.MEMORY_EPISTEMOLOGY_AUDIT",
        state / "audit.jsonl",
    )
    monkeypatch.setattr(
        "System.lagrangian_constraint_manifold._DUAL_STATE_PATH",
        state / "lagrangian_multipliers.json",
    )
    monkeypatch.setattr(
        "System.lagrangian_constraint_manifold._RESIDUE_LOG_PATH",
        state / "constraint_residues.jsonl",
    )
    monkeypatch.setattr(
        "System.proof_of_useful_work.issue_work_receipt",
        lambda *args, **kwargs: None,
    )

    bus = StigmergicMemoryBus(architect_id="T")
    trace = bus.remember(
        "background show dialogue",
        "fiction_cowatch",
        epistemic_label="FICTION",
        interaction_mode="FICTION_COWATCH",
    )
    assert trace.interaction_mode == "FICTION_COWATCH"
    assert "FICTION_COWATCH" in INTERACTION_MODES
