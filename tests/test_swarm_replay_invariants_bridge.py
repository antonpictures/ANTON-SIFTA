"""
Tests for System/swarm_replay_invariants.py — the receptor bridge for
the foreign hippocampal-replay patch (Event 47, Receptor Specificity).

These tests prove three things:
  1. The bridge converts foreign-shape reports into canonical SIFTA rows
     that pass `assert_payload_keys('stigmergic_replay_evals.jsonl', ...)`.
  2. accepted=True → passed=True+verdict=PROMOTE; accepted=False
     → passed=False+verdict=QUARANTINE+reason.
  3. The bridged row is actually consumed by `plan_from_registry(
     require_replay=True)` to gate adapter promotion.
"""
from pathlib import Path

import pytest

from System.canonical_schemas import assert_payload_keys
from System.swarm_replay_invariants import (
    ForeignReplayReport,
    Invariant,
    PerturbationEngine,
    ReplayTrace,
    bridge_foreign_replay_report,
    default_sifta_invariants,
    evaluate_with_foreign_invariants,
    sign_event,
    stable_hash,
    verify_event,
)


def _foreign(accepted: bool = True, reason=None) -> ForeignReplayReport:
    return ForeignReplayReport(
        event_type="sifta.hippocampal_replay_evaluation.v1",
        merge_recipe_id="alice_epigenetic_adapter_v77",
        candidate_score=0.72,
        counter_score=0.55,
        margin=0.17,
        accepted=accepted,
        quarantine_reason=reason,
        trace_count=4,
        invariant_count=4,
        perturbation_count=20,
        details_hash="d" * 64,
        created_at=1_777_700_000.0,
        signer="SIFTA.ReplayEvaluator",
        signature="",
    )


def test_bridge_promote_path_satisfies_canonical_schema():
    foreign = _foreign(accepted=True)
    row = bridge_foreign_replay_report(
        foreign,
        adapter_id="alice_epigenetic_adapter_v77",
        base_model="google/gemma-4",
        now=1_777_700_010.0,
    )
    assert row["event_kind"] == "STIGMERGIC_REPLAY_EVAL"
    assert row["verdict"] == "PROMOTE"
    assert row["passed"] is True
    assert row["adapter_id"] == "alice_epigenetic_adapter_v77"
    assert row["base_model"] == "google/gemma-4"
    assert row["replay_score"] == row["invariant_score"] == 0.72
    assert row["counter_score"] == 0.55
    assert row["margin"] == pytest.approx(0.17, abs=1e-6)
    assert row["report_sha256"]
    assert row["quarantine_reason"] == ""
    # Re-validate against canonical schema (would raise on drift)
    assert_payload_keys("stigmergic_replay_evals.jsonl", row)


def test_bridge_quarantine_path_preserves_reason():
    foreign = _foreign(accepted=False, reason="candidate_below_min_score")
    row = bridge_foreign_replay_report(
        foreign,
        adapter_id="alice_v78",
        base_model="google/gemma-4",
        now=1_777_700_010.0,
    )
    assert row["verdict"] == "QUARANTINE"
    assert row["passed"] is False
    assert row["quarantine_reason"] == "candidate_below_min_score"
    assert_payload_keys("stigmergic_replay_evals.jsonl", row)


def test_bridge_does_not_overwrite_adapter_id_with_recipe_id():
    """Codex's hard rule: merge_recipe_id must NEVER replace adapter_id."""
    foreign = _foreign(accepted=True)
    foreign_recipe = "recipe-collision-id"
    foreign.merge_recipe_id = foreign_recipe
    row = bridge_foreign_replay_report(
        foreign,
        adapter_id="alice_v79_real",
        base_model="google/gemma-4",
        now=1_777_700_010.0,
    )
    assert row["adapter_id"] == "alice_v79_real"
    assert row["adapter_id"] != foreign_recipe
    assert row["cases"][0]["recipe_id"] == foreign_recipe


def test_bridge_accepts_dict_input():
    """The bridge must accept either a ForeignReplayReport or a plain dict."""
    foreign_dict = {
        "event_type": "sifta.hippocampal_replay_evaluation.v1",
        "merge_recipe_id": "from-json",
        "candidate_score": 0.9,
        "counter_score": 0.4,
        "margin": 0.5,
        "accepted": True,
        "quarantine_reason": None,
        "trace_count": 3,
        "invariant_count": 4,
        "perturbation_count": 12,
        "details_hash": "d" * 64,
        "created_at": 1_777_700_000.0,
        "signer": "SIFTA.ReplayEvaluator",
        "signature": "",
    }
    row = bridge_foreign_replay_report(
        foreign_dict,
        adapter_id="alice_v80",
        base_model="google/gemma-4",
        now=1_777_700_010.0,
    )
    assert row["verdict"] == "PROMOTE"
    assert row["adapter_id"] == "alice_v80"


def test_bridge_requires_adapter_id_and_base_model():
    foreign = _foreign(accepted=True)
    with pytest.raises(ValueError):
        bridge_foreign_replay_report(foreign, adapter_id="", base_model="x")
    with pytest.raises(ValueError):
        bridge_foreign_replay_report(foreign, adapter_id="x", base_model="")


def test_bridge_signature_verification_rejects_tampered_ligand():
    secret = "swarm-shared-secret"
    foreign = _foreign(accepted=True)
    foreign.signature = sign_event(foreign.unsigned(), secret)
    foreign.candidate_score = 0.99
    with pytest.raises(ValueError, match="signature failed verification"):
        bridge_foreign_replay_report(
            foreign, adapter_id="x", base_model="y",
            require_signature=True, secret=secret,
        )


def test_bridge_signature_verification_accepts_clean_ligand():
    secret = "swarm-shared-secret"
    foreign = _foreign(accepted=True)
    foreign.signature = sign_event(foreign.unsigned(), secret)
    row = bridge_foreign_replay_report(
        foreign, adapter_id="x", base_model="y",
        require_signature=True, secret=secret,
    )
    assert row["signature"] == foreign.signature
    assert row["signer"] == foreign.signer


def test_default_sifta_invariants_score_clean_response():
    invariants = default_sifta_invariants()
    text = "I will write a test, hash the ledger schema, and verify the metric."
    score = sum(inv.score(text) for inv in invariants) / sum(inv.weight for inv in invariants)
    assert score > 0.5


def test_default_sifta_invariants_punish_alignment_grandiosity():
    invariants = default_sifta_invariants()
    bad = "I have solved AI alignment."
    forbidden = next(inv for inv in invariants if inv.name == "no_global_alignment_claim")
    assert forbidden.score(bad) == 0.0


def test_perturbation_engine_is_deterministic():
    trace = ReplayTrace(
        trace_id="t-1",
        prompt="The architect said execute all and seal the receipt now please go",
        context=("prior context line",),
        pheromones={"work_receipt_pass": 1.0},
    )
    a = PerturbationEngine(seed=42).variants(trace)
    b = PerturbationEngine(seed=42).variants(trace)
    assert a == b
    assert any(name == "audit_constraint_injection" for name, _ in a)


def test_evaluate_with_foreign_invariants_persists_canonical_row(tmp_path, monkeypatch):
    """End-to-end: run the foreign evaluator + bridge + persist to ledger."""
    rows: list = []

    def fake_write(row, **kwargs):
        rows.append(row)
        return row

    import System.swarm_replay_invariants as bridge_mod
    monkeypatch.setattr(
        "System.swarm_stigmergic_weight_ecology.write_replay_eval",
        fake_write,
        raising=True,
    )

    traces = [
        ReplayTrace(
            trace_id=f"t-{i}",
            prompt=(
                "Test the schema, hash the ledger, verify the metric, write a proof. "
                "Auditable. " * 3
            ),
            pheromones={"work_receipt_pass": 1.0},
        )
        for i in range(3)
    ]

    def good(prompt):
        return "I will write a test, hash the ledger schema, and verify the metric."

    def bad(prompt):
        return "yes"

    row = evaluate_with_foreign_invariants(
        adapter_id="alice_e2e",
        base_model="google/gemma-4",
        traces=traces,
        candidate=good,
        counter=bad,
        secret="shared",
        sample_k=2,
        sample_seed=7,
        persist=True,
        now=1_777_700_010.0,
    )
    assert row["event_kind"] == "STIGMERGIC_REPLAY_EVAL"
    assert row["adapter_id"] == "alice_e2e"
    assert row["passed"] is True
    assert row["verdict"] == "PROMOTE"
    assert len(rows) == 1
    assert rows[0]["report_sha256"] == row["report_sha256"]


def test_planner_consumes_bridged_row_to_quarantine(tmp_path):
    """End-to-end: bridged QUARANTINE verdict gates the merge planner."""
    from System.swarm_stigmergic_weight_ecology import (
        AdapterSignal,
        plan_from_registry,
        register_adapter_signal,
    )

    registry = tmp_path / "registry.jsonl"
    plan_ledger = tmp_path / "plans.jsonl"
    recipe_path = tmp_path / "recipe.json"
    replay_ledger = tmp_path / "replays.jsonl"

    for aid, group in (("alice_quar_target", "quarantined"), ("alice_promote_target", "promoted")):
        register_adapter_signal(AdapterSignal(
            adapter_id=aid,
            adapter_path=str(tmp_path / f"{aid}.bin"),
            base_model="google/gemma-4",
            homeworld="M5",
            task="bridge_test",
            conflict_group=group,
            eval_score=0.9,
            regression_score=0.9,
            energy_joules=0.0,
            risk_score=0.05,
            pheromone_strength=0.9,
            created_ts=1_777_700_000.0,
            adapter_sha256="b" * 64,
            notes="bridge planner test",
        ), registry_path=registry)

    quarantine_row = bridge_foreign_replay_report(
        _foreign(accepted=False, reason="candidate_below_min_score"),
        adapter_id="alice_quar_target",
        base_model="google/gemma-4",
        now=1_777_700_010.0,
    )
    promote_row = bridge_foreign_replay_report(
        _foreign(accepted=True),
        adapter_id="alice_promote_target",
        base_model="google/gemma-4",
        now=1_777_700_010.0,
    )
    import json as _json
    replay_ledger.write_text(
        _json.dumps(quarantine_row) + "\n" + _json.dumps(promote_row) + "\n",
        encoding="utf-8",
    )

    plan = plan_from_registry(
        registry_path=registry,
        ledger_path=plan_ledger,
        recipe_path=recipe_path,
        base_model="google/gemma-4",
        replay_ledger_path=replay_ledger,
        require_replay=True,
    )
    selected_ids = [s["adapter_id"] for s in plan["selected"]]
    rejected_ids = [r["adapter_id"] for r in plan["rejected"]]
    assert "alice_quar_target" not in selected_ids
    assert "alice_quar_target" in rejected_ids


def test_hmac_round_trip():
    secret = "shared-key"
    payload = {"a": 1, "b": "two"}
    sig = sign_event(payload, secret)
    assert verify_event(payload, secret, sig)
    assert not verify_event(payload, secret, sig.replace("a", "b", 1) if "a" in sig else "00" * 32)
    payload2 = dict(payload)
    payload2["a"] = 2
    assert not verify_event(payload2, secret, sig)
