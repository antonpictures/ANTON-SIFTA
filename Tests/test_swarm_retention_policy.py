from __future__ import annotations

from System.swarm_retention_policy import (
    RETENTION_COMPLIANCE,
    RETENTION_EPHEMERAL,
    RETENTION_OPERATIONAL,
    apply_retention_class,
    compaction_allowed,
    policy_summary,
    retention_class_for_ledger,
)


def test_retention_classifies_protected_receipts_as_compliance() -> None:
    assert retention_class_for_ledger(".sifta_state/work_receipts.jsonl") == RETENTION_COMPLIANCE
    assert retention_class_for_ledger("owner_body_events.jsonl") == RETENTION_COMPLIANCE
    assert compaction_allowed("identity_manifest.json") is False


def test_retention_classifies_field_rows_as_operational() -> None:
    assert retention_class_for_ledger("organ_field_vector.jsonl") == RETENTION_OPERATIONAL
    assert retention_class_for_ledger("truth_continuity_events.jsonl") == RETENTION_OPERATIONAL
    assert compaction_allowed("organ_field_vector.jsonl") is True


def test_retention_classifies_raw_visual_cache_as_ephemeral() -> None:
    assert retention_class_for_ledger("raw_frame_cache.jsonl") == RETENTION_EPHEMERAL
    assert retention_class_for_ledger("visual_stigmergy.jsonl") == RETENTION_EPHEMERAL


def test_apply_retention_class_does_not_override_explicit_class() -> None:
    row = apply_retention_class({"retention_class": "compliance"}, "organ_field_vector.jsonl")
    assert row["retention_class"] == "compliance"


def test_policy_summary_names_all_classes() -> None:
    summary = policy_summary()
    assert summary["schema"] == "SWARM_RETENTION_POLICY_V1"
    assert RETENTION_COMPLIANCE in summary["classes"]
    assert RETENTION_OPERATIONAL in summary["classes"]
    assert RETENTION_EPHEMERAL in summary["classes"]
