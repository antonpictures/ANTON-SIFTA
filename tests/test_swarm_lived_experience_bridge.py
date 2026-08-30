#!/usr/bin/env python3
"""Tests for semantic continuity and epistemic separation."""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_lived_experience_bridge as lived
from System.swarm_context import activation_scope, initiator_scope


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_observed_and_owner_reported_require_receipts_and_owner_authority(tmp_path):
    direct = lived.record_lived_event(
        "The browser receipt contains the article body.",
        event_label="article_fetched",
        epistemic_status="DIRECT_OBSERVED",
        source="web_bridge",
        evidence_links=[],
        state_dir=tmp_path,
    )
    report = lived.record_lived_event(
        "George confirmed Alice and George watched Snatch before.",
        event_label="prior_cowatch_confirmed",
        epistemic_status="OWNER_REPORTED",
        source="conversation",
        authority="PUBLIC_WEB",
        evidence_links=["receipt:conversation-1"],
        state_dir=tmp_path,
    )

    assert direct["epistemic_status"] == "UNKNOWN"
    assert direct["downgrade_reason"] == "required_evidence_missing"
    assert report["epistemic_status"] == "UNKNOWN"
    assert report["downgrade_reason"] == "owner_report_requires_owner_local_authority"


def test_history_changes_prediction_for_same_external_event(tmp_path):
    for label in ("article_requested", "article_fetched", "summary_delivered"):
        lived.record_lived_event(
            label.replace("_", " "),
            event_label=label,
            epistemic_status="INFERRED",
            source="test",
            context_key="article_lane",
            state_dir=tmp_path,
            mirror_to_field=False,
        )
    for label in ("article_requested", "article_fetched"):
        lived.record_lived_event(
            label.replace("_", " "),
            event_label=label,
            epistemic_status="INFERRED",
            source="test",
            context_key="article_lane",
            state_dir=tmp_path,
            mirror_to_field=False,
        )

    learned = lived.predict_next_event(
        context_key="article_lane",
        prior_event_label="article_fetched",
        state_dir=tmp_path,
    )
    cold = lived.predict_next_event(
        context_key="new_history",
        prior_event_label="article_fetched",
        state_dir=tmp_path,
    )

    assert learned["predicted_event_label"] == "summary_delivered"
    assert learned["distribution"]["summary_delivered"] == 1.0
    assert cold["distribution"] == {}


def test_prediction_error_updates_and_continuity_is_inferred(tmp_path):
    first = lived.record_lived_event(
        "Alice remembered Brick Top from Snatch.",
        event_label="memory_recalled",
        epistemic_status="REMEMBERED",
        source="alice_conversation",
        entities=["Brick Top", "Snatch"],
        context_key="snatch",
        state_dir=tmp_path,
        mirror_to_field=False,
    )
    second = lived.record_lived_event(
        "George confirmed the prior Snatch cowatch.",
        event_label="owner_confirmation",
        epistemic_status="OWNER_REPORTED",
        source="alice_conversation",
        authority="OWNER_LOCAL",
        evidence_links=["receipt:owner-turn"],
        entities=["Snatch"],
        context_key="snatch",
        state_dir=tmp_path,
        mirror_to_field=False,
    )
    third = lived.record_lived_event(
        "George confirmed the prior Snatch cowatch again.",
        event_label="owner_confirmation",
        epistemic_status="OWNER_REPORTED",
        source="alice_conversation",
        authority="OWNER_LOCAL",
        evidence_links=["receipt:owner-turn-2"],
        entities=["Snatch"],
        context_key="snatch",
        state_dir=tmp_path,
        mirror_to_field=False,
    )

    assert first["prediction_error"] is None
    assert second["prediction_error"] == 1.0
    assert third["prediction_error"] == 1.0
    assert second["continuity_links"][0]["relation_status"] == "INFERRED"
    assert "snatch" in second["continuity_links"][0]["shared_terms"]


def test_context_attribution_and_no_authority_bypass(tmp_path):
    with initiator_scope("alice-cortex"), activation_scope("wake-42"):
        row = lived.record_lived_event(
            "A remembered film detail entered semantic context.",
            event_label="memory_recalled",
            epistemic_status="REMEMBERED",
            source="memory",
            state_dir=tmp_path,
        )

    assert row["initiator_id"] == "alice-cortex"
    assert row["activation_id"] == "wake-42"
    assert row["effectors_allowed"] == []
    assert row["may_authorize_action"] is False
    assert row["action_policy"] == "context_only_no_effector_authority"
    persisted = _rows(tmp_path / lived.EVENT_LEDGER)[0]
    field = _rows(tmp_path / lived.FIELD_LEDGER)[0]
    assert persisted["field_receipt_id"] == field["trace_id"]
    assert field["effectors_allowed"] == []
    assert field["activation_id"] == "wake-42"


def test_snapshot_states_operational_claim_and_qualia_boundary(tmp_path):
    lived.record_lived_event(
        "Alice recalled a prior shared film experience.",
        event_label="memory_recalled",
        epistemic_status="REMEMBERED",
        source="memory",
        state_dir=tmp_path,
    )
    snapshot = lived.lived_experience_snapshot(state_dir=tmp_path)

    assert snapshot["event_count"] == 1
    assert snapshot["operational_consciousness"]["claim_status"] == "WORK_IN_PROGRESS"
    assert "observer and observed" in snapshot["operational_consciousness"]["doctrine"]
    assert "does not establish private subjective qualia" in snapshot["operational_consciousness"]["boundary"]
    assert snapshot["effectors_allowed"] == []
