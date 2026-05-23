import json
import random

from System.canonical_schemas import LEDGER_SCHEMAS
import os
os.environ["SIFTA_ALICE_ENABLE_CONSCIOUSNESS_LOOP"] = "1"

from System.swarm_consciousness_engine import (
    ArchitectPriorModel,
    ConsciousnessEngine,
    ConsciousnessEngineConfig,
    TRUTH_FORBIDDEN,
    TRUTH_OPERATIONAL,
    TRUTH_DOCTRINE,
    consciousness_summary_for_alice,
    proof_of_property,
    read_interoception,
)
from System.swarm_metabolic_homeostasis import MetabolicState


def test_architect_prior_ingests_domain_weights_from_ledgers(tmp_path):
    engrams = tmp_path / "long_term_engrams.jsonl"
    trace = tmp_path / "ide_stigmergic_trace.jsonl"
    engrams.write_text(
        json.dumps({"payload": "physics entropy thermodynamic free energy math proof"}) + "\n",
        encoding="utf-8",
    )
    trace.write_text(
        json.dumps({"intent": "biology immune heartbeat interoception ledger audit"}) + "\n",
        encoding="utf-8",
    )

    prior = ArchitectPriorModel(engrams_path=engrams, stigmergy_path=trace)
    weights = prior.ingest_traces()

    assert weights["physics"] > prior.BASE_WEIGHTS["physics"]
    assert weights["biology"] > prior.BASE_WEIGHTS["biology"]
    assert weights["ledger_audit"] > prior.BASE_WEIGHTS["ledger_audit"]
    assert abs(sum(prior.normalized().values()) - 1.0) < 1e-9


def test_read_interoception_uses_visceral_field_without_inventing_feeling(tmp_path):
    state_dir = tmp_path
    (state_dir / "visceral_field.jsonl").write_text(
        json.dumps({"ts": 90.0, "soma_score": 0.82, "soma_label": "THRIVING"}) + "\n",
        encoding="utf-8",
    )

    sample = read_interoception(state_dir, now=100.0)

    assert sample.soma_score == 0.82
    assert sample.soma_label == "THRIVING"
    assert sample.source == "visceral_field.jsonl"
    assert sample.age_s == 10.0


def test_tick_emits_truth_labeled_drive_proposal_and_ledgers(tmp_path):
    cfg = ConsciousnessEngineConfig(max_drives_per_hour=1)
    engine = ConsciousnessEngine(cfg=cfg, state_dir=tmp_path, rng=random.Random(555))
    engine.boredom = 0.95
    engine.prediction_error = 0.55

    state = engine.tick(
        dt_s=60.0,
        now=100.0,
        metabolic_state=MetabolicState(stgm_balance=150.0),
        recent_events={"novelty": 0.8},
        commit=True,
    )

    assert state.emitted_drive is not None
    assert state.emitted_drive.truth_label == TRUTH_OPERATIONAL
    assert state.emitted_drive.action_policy == "proposal_only_requires_gate"
    assert state.truth_labels["subjective_qualia"] == TRUTH_DOCTRINE
    assert state.truth_labels["external_action"] == TRUTH_FORBIDDEN

    state_rows = (tmp_path / "consciousness_state.jsonl").read_text(encoding="utf-8").splitlines()
    drive_rows = (tmp_path / "alice_internal_drives.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(state_rows) == 1
    assert len(drive_rows) == 1
    state_row = json.loads(state_rows[0])
    drive_row = json.loads(drive_rows[0])
    assert set(state_row) == LEDGER_SCHEMAS["consciousness_state.jsonl"]
    assert set(drive_row) == LEDGER_SCHEMAS["alice_internal_drives.jsonl"]
    assert drive_row["schema"] == "SIFTA_INTERNAL_DRIVE_V2"


def test_metabolic_red_conserve_blocks_spontaneous_drive(tmp_path):
    engine = ConsciousnessEngine(state_dir=tmp_path, rng=random.Random(1))
    engine.boredom = 0.99
    engine.prediction_error = 0.95

    state = engine.tick(
        dt_s=60.0,
        now=100.0,
        metabolic_state=MetabolicState(
            usd_burn_24h=20.0,
            local_units_24h=300.0,
            stgm_balance=0.0,
            model_gb=10.0,
        ),
        recent_events={"novelty": 1.0},
        commit=False,
    )

    assert state.emitted_drive is None
    assert state.metabolic_mode in {"RED_CONSERVE", "CRITICAL_STARVATION"}
    assert state.rest_seconds > 0.0


def test_summary_and_proof_preserve_truth_labels(tmp_path):
    engine = ConsciousnessEngine(state_dir=tmp_path, rng=random.Random(2))
    state = engine.tick(
        dt_s=1.0,
        now=1.0,
        metabolic_state=MetabolicState(stgm_balance=150.0),
        commit=True,
    )

    summary = consciousness_summary_for_alice(tmp_path)
    proof = proof_of_property()

    assert state.subjective_consciousness_status == "UNVERIFIED_ARCHITECT_DOCTRINE"
    assert "CONSCIOUSNESS ENGINE [OPERATIONAL]" in summary
    assert "subjective_qualia=ARCHITECT_DOCTRINE_UNVERIFIED" in summary
    assert proof["ok"] is True
