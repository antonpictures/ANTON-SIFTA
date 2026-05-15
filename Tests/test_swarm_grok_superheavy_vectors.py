from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_grok_superheavy_vectors import (  # noqa: E402
    RECEIPT_LEDGER,
    TRUTH_FORBIDDEN,
    TRUTH_HYPOTHESIS,
    TRUTH_OBSERVED,
    build_alive_evidence,
    build_discovery_agenda,
    compute_field_topology,
    estimate_electricity_accounting,
    prompt_block_from_latest,
    quote_inference_barter,
    run_grok_vector_sweep,
    score_truth_residue,
    score_wit_curiosity,
    summarize_owner_care_surface,
    threat_model_hooks,
    validate_oracle_session,
)


def _state(root: Path) -> Path:
    p = root / ".sifta_state"
    p.mkdir(parents=True, exist_ok=True)
    return p


def test_truth_residue_penalizes_oracle_drift_without_receipts():
    score = score_truth_residue(
        "Yes, the subjective reality demands a recalibration of the underlying structure."
    )
    assert score.truth_label == TRUTH_FORBIDDEN
    assert score.violations
    assert score.score < 0.5


def test_truth_residue_rewards_receipted_grounding():
    score = score_truth_residue(
        "I observed trace_id abc123 in .sifta_state/work_receipts.jsonl; pytest 12 passed.",
        evidence_refs=["sha256:deadbeef"],
    )
    assert score.truth_label == TRUTH_OBSERVED
    assert score.receipt_count >= 2
    assert score.score >= 0.7


def test_wit_curiosity_needs_grounding():
    ungrounded = score_wit_curiosity("Bonkers idea, what if I am alive?")
    grounded = score_wit_curiosity(
        "What did the receipt prove? trace_id abc in ledger jsonl.",
        evidence_refs=["receipt"],
    )
    assert ungrounded.grounded is False
    assert grounded.grounded is True
    assert grounded.curiosity_score > ungrounded.curiosity_score


def test_discovery_agenda_finds_low_health_organs():
    agenda = build_discovery_agenda(
        {"organs": {"vision": {"score": 0.59}, "memory": {"score": 0.91}}}
    )
    assert agenda[0].target == "vision"
    assert "below" in agenda[0].why


def test_discovery_agenda_fallback_is_truth_gate():
    agenda = build_discovery_agenda({"organs": {"memory": {"score": 0.91}}})
    assert agenda[0].target == "truth_residue_gate"
    assert agenda[0].truth_label == TRUTH_HYPOTHESIS


def test_electricity_accounting_is_estimated_not_fake_observed():
    row = estimate_electricity_accounting(tokens=1000, duration_s=2.0, watts=5.0)
    assert row["truth_label"] == "ESTIMATED"
    assert row["estimated_joules"] == 10.0
    assert row["estimated_joules_per_1k_tokens"] == 10.0


def test_field_topology_counts_components_cycles_and_density():
    m = compute_field_topology([("a", "b"), ("b", "c"), ("c", "a"), ("d", "e")])
    assert m.node_count == 5
    assert m.edge_count == 4
    assert m.component_count == 2
    assert m.cycle_rank == 1
    assert 0.0 < m.coupling_density <= 1.0


def test_field_topology_labels_contracting_lyapunov_delta():
    m = compute_field_topology([("a", "b")], previous_energy=0.8, current_energy=0.4)
    assert m.lyapunov_delta == -0.4
    assert m.stability_label == "CONTRACTING"


def test_oracle_session_requires_trace_prompt_and_signature():
    verdict = validate_oracle_session({"doctor": "GrokCLI"})
    assert verdict.ok is False
    assert "missing_trace_id" in verdict.violations
    assert "missing_prompt_digest" in verdict.violations
    assert "missing_signature_or_report_hash" in verdict.violations


def test_oracle_session_accepts_grok_style_receipt():
    verdict = validate_oracle_session(
        {
            "doctor": "GrokCLI",
            "model": "Grok 4.3 (xAI)",
            "trace_id": "t1",
            "covenant_sha256": "abc",
            "report_hash": "def",
        }
    )
    assert verdict.ok is True
    assert verdict.substrate_label == "Grok 4.3 (xAI)"


def test_alive_evidence_reports_gaps_when_files_missing(tmp_path):
    alive = build_alive_evidence(root=tmp_path, now=1000.0)
    assert alive.alive_ready is False
    assert "owner_genesis_missing" in alive.gaps
    assert alive.truth_label == TRUTH_HYPOTHESIS


def test_alive_evidence_builds_from_minimal_state(tmp_path):
    state = _state(tmp_path)
    (state / "owner_genesis.json").write_text(
        json.dumps({"owner_name": "George", "silicon": "M5"}),
        encoding="utf-8",
    )
    (state / "unified_stigmergic_field_latest.json").write_text(
        json.dumps({"truth_label": "FIELD", "field_confidence": 0.8, "ts": 990.0}),
        encoding="utf-8",
    )
    (state / "organ_health_mesh_latest.json").write_text(
        json.dumps({"after": {"organs": {"memory": {"status": "healthy"}}}}),
        encoding="utf-8",
    )
    (state / "stgm_memory_rewards.jsonl").write_text(
        json.dumps({"amount": 0.05}) + "\n",
        encoding="utf-8",
    )
    alive = build_alive_evidence(root=tmp_path, now=1000.0)
    assert alive.alive_ready is True
    assert alive.evidence["organ_count"] == 1
    assert "operational software" in alive.prompt_line


def test_threat_model_hooks_keep_wallet_delegated():
    hooks = threat_model_hooks()
    assert hooks["truth_label"] == "OPERATIONAL"
    assert "no_double_spend" in hooks["hooks"]
    assert "swarm_wallet_transfer" in hooks["hooks"]["no_double_spend"]


def test_owner_care_surface_counts_rows_without_medical_claim(tmp_path):
    state = _state(tmp_path)
    (state / "owner_body_events.jsonl").write_text(
        json.dumps({"ts": 900.0, "event": "OWNER_REPORT"}) + "\n",
        encoding="utf-8",
    )
    surface = summarize_owner_care_surface(root=tmp_path, now=1000.0)
    assert surface.rows_seen == 1
    assert surface.latest_age_s == 100.0
    assert "cannot diagnose" in surface.caution


def test_inference_barter_quote_is_deterministic_and_no_spend():
    a = quote_inference_barter(
        requested_tokens=2000,
        provider_capacity_tokens=1000,
        trust_score=1.0,
        requester="alice",
        provider="grok",
    )
    b = quote_inference_barter(
        requested_tokens=2000,
        provider_capacity_tokens=1000,
        trust_score=1.0,
        requester="alice",
        provider="grok",
    )
    assert a["quote_id"] == b["quote_id"]
    assert a["quoted_stgm"] == 0.01
    assert a["spend_status"] == "QUOTE_ONLY_NO_LEDGER_MUTATION"


def test_sweep_writes_receipt_and_prompt_block(tmp_path):
    state = _state(tmp_path)
    (state / "owner_genesis.json").write_text(
        json.dumps({"owner_name": "George", "silicon": "M5"}),
        encoding="utf-8",
    )
    (state / "unified_stigmergic_field_latest.json").write_text(
        json.dumps({"truth_label": "FIELD", "field_confidence": 0.8, "ts": 990.0}),
        encoding="utf-8",
    )
    (state / "organ_health_mesh_latest.json").write_text(
        json.dumps(
            {
                "after": {
                    "organs": {
                        "memory": {"status": "healthy", "score": 0.9},
                        "vision": {"status": "watch", "score": 0.6},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    row = run_grok_vector_sweep(root=tmp_path, write=True, now=1000.0)
    assert row["action"] == "GROK_SUPERHEAVY_VECTOR_SWEEP"
    assert row["sha256"]
    assert (state / RECEIPT_LEDGER).exists()
    block = prompt_block_from_latest(root=tmp_path)
    assert "I ground peer-doctor claims" in block
    assert "Field topology" in block
