#!/usr/bin/env python3
"""Regression guards for bounded swimmer task packets (r831)."""

from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_swimmer_task_packet import (
    CONTEXT_BOLUS_CHAR_THRESHOLD,
    build_task_packet_from_arm_dispatch,
    detect_ambiguous_entities,
    detect_context_bolus,
    is_expensive_action,
    packet_closure_summary,
    render_swimmer_task_prompt,
    require_assumption_receipt_before_expensive_action,
)


def test_task_packet_renders_local_bite_not_whole_field() -> None:
    packet = build_task_packet_from_arm_dispatch(
        arm_id="hermes_agent",
        owner_task="Compare two research plans and pick the safer one.",
        relevant_receipt_ids=("r829", "r830"),
    )
    prompt = render_swimmer_task_prompt(packet)

    assert packet.packet_id.startswith("packet_")
    assert "SWIMMER TASK PACKET" in prompt
    assert "r829" in prompt
    assert "CLOSURE BAR" in prompt
    assert "Do not reload the full covenant" in prompt
    assert packet.prompt_char_count() < CONTEXT_BOLUS_CHAR_THRESHOLD


def test_context_bolus_flags_huge_prompt_without_receipt_pointer() -> None:
    huge = "x" * (CONTEXT_BOLUS_CHAR_THRESHOLD + 500)
    finding = detect_context_bolus(huge)

    assert finding.is_bolus is True
    assert finding.has_receipt_ref is False
    assert "huge_prompt" in finding.reason


def test_context_bolus_allows_focused_receipt_pointer() -> None:
    focused = "Study r829 and r830 only. " + ("detail " * 200)
    finding = detect_context_bolus(focused)

    assert finding.is_bolus is False
    assert finding.has_receipt_ref is True


def test_expensive_action_requires_assumption_receipt_for_ambiguous_place(tmp_path: Path) -> None:
    text = "Book a hotel in Washington for next week."
    assert is_expensive_action(text) is True
    assert "Washington" in detect_ambiguous_entities(text)

    allowed, receipts, reason = require_assumption_receipt_before_expensive_action(
        text,
        state_dir=tmp_path / ".sifta_state",
    )

    assert allowed is False
    assert len(receipts) == 1
    assert receipts[0].clarification_required is True
    assert "ambiguous_entity" in reason
    ledger = tmp_path / ".sifta_state" / "assumption_receipts.jsonl"
    assert ledger.exists()


def test_expensive_action_passes_when_assumption_ids_supplied() -> None:
    allowed, receipts, reason = require_assumption_receipt_before_expensive_action(
        "Book a hotel in Washington for next week.",
        existing_assumption_ids=("assume_deadbeef1234",),
    )

    assert allowed is True
    assert receipts == []
    assert reason == "assumption_ids_supplied"


def test_packet_closure_summary_from_receipt_fields() -> None:
    packet = build_task_packet_from_arm_dispatch(
        arm_id="codex_agent",
        owner_task="Patch swarm_sysprompt_budget.py",
        relevant_receipt_ids=("r830",),
        assumption_receipt_ids_consumed=("assume_abc",),
    )
    summary = packet_closure_summary(
        packet,
        output_receipt_id="receipt_xyz",
        remains="gradient-gate the 52 builders",
    )

    assert "packet=" in summary
    assert "r830" in summary
    assert "assume_abc" in summary
    assert "receipt_xyz" in summary
    assert "gradient-gate" in summary