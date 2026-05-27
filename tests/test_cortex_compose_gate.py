"""Tests for swarm_cortex_compose_gate — tasks #61 + #62."""

from __future__ import annotations

import json

import pytest

from System.swarm_cortex_compose_gate import (
    ComposeDecision,
    DispatchApproval,
    compose_dispatch,
    format_for_review,
    record_approval,
    get_pending_compose,
    COMPOSE_LEDGER,
    APPROVAL_LEDGER,
)


@pytest.fixture(autouse=True)
def _patch_ledgers(tmp_path, monkeypatch):
    compose = tmp_path / "alice_compose_decisions.jsonl"
    approval = tmp_path / "dispatch_approvals.jsonl"
    monkeypatch.setattr("System.swarm_cortex_compose_gate.COMPOSE_LEDGER", compose)
    monkeypatch.setattr("System.swarm_cortex_compose_gate.APPROVAL_LEDGER", approval)
    return compose, approval


class TestComposeDispatch:
    def test_creates_dispatch_draft(self):
        decision = compose_dispatch(
            "Alice, ask Grok to code the tournament",
            task_anchors=["#46", "#50", "#55"],
            source_section="§17-§21",
        )
        assert decision.status == "DISPATCH_DRAFT"
        assert decision.compose_id
        assert "#46" in decision.task_anchors
        assert "§17-§21" in decision.proposed_payload

    def test_empty_text_is_field_failure(self):
        decision = compose_dispatch("")
        assert decision.status == "FIELD_FAILURE"
        assert decision.field_failure == "empty_user_text"

    def test_writes_to_ledger(self, _patch_ledgers):
        compose_ledger, _ = _patch_ledgers
        compose_dispatch(
            "Code the tasks",
            task_anchors=["#46"],
        )
        lines = compose_ledger.read_text().strip().split("\n")
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["status"] == "DISPATCH_DRAFT"

    def test_includes_receipt_requirements(self):
        decision = compose_dispatch(
            "Code tournament",
            task_anchors=["#46"],
        )
        assert "py_compile" in decision.proposed_payload
        assert "pytest" in decision.proposed_payload
        assert "work_receipt" in decision.proposed_payload


class TestFormatForReview:
    def test_draft_format_includes_anchors(self):
        decision = compose_dispatch(
            "Code tasks",
            task_anchors=["#46", "#50"],
        )
        review = format_for_review(decision)
        assert "DISPATCH_DRAFT" in review
        assert "#46" in review
        assert "George, approve dispatch?" in review

    def test_field_failure_format(self):
        decision = compose_dispatch("")
        review = format_for_review(decision)
        assert "FIELD_FAILURE" in review


class TestRecordApproval:
    def test_records_approval(self, _patch_ledgers):
        _, approval_ledger = _patch_ledgers
        approval = record_approval(
            "compose-123",
            approved=True,
            reviewer="architect",
            notes="looks good",
        )
        assert approval.approved is True
        assert approval.compose_id == "compose-123"

        lines = approval_ledger.read_text().strip().split("\n")
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["approved"] is True

    def test_records_rejection(self, _patch_ledgers):
        _, approval_ledger = _patch_ledgers
        approval = record_approval(
            "compose-456",
            approved=False,
            reviewer="architect",
            notes="needs more tasks",
        )
        assert approval.approved is False


class TestGetPendingCompose:
    def test_returns_latest_draft(self, _patch_ledgers):
        compose_dispatch("First task", task_anchors=["#46"])
        compose_dispatch("Second task", task_anchors=["#50"])
        pending = get_pending_compose()
        assert pending is not None
        assert "#50" in pending.task_anchors

    def test_returns_none_when_empty(self, _patch_ledgers):
        assert get_pending_compose() is None
