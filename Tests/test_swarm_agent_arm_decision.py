#!/usr/bin/env python3
"""Regression guards for Alice's agent-arm decision habit."""

from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_agent_arm_decision import (
    agent_arm_decision_for_turn,
    format_agent_arm_prepass_context,
    run_agent_arm_decision_prepass,
    schedule_async_agent_arm_prepass,
    summary_for_prompt,
)


def test_research_task_selects_hermes_without_owner_naming_it() -> None:
    decision = agent_arm_decision_for_turn(
        "Compare these two research plans and tell me which one is safer."
    )

    assert decision is not None
    assert decision.arm_id == "hermes_agent"
    assert "Evidence-only pass" in decision.prompt
    assert "Hermes" not in decision.prompt


def test_status_question_does_not_fire_arm_prepass() -> None:
    assert agent_arm_decision_for_turn("What is Hermes and what is its current receipt status?") is None


def test_direct_effector_turn_does_not_fire_arm_prepass() -> None:
    assert agent_arm_decision_for_turn("Send WhatsApp to Vitaliy saying hello") is None


def test_explicit_codex_code_task_can_select_codex() -> None:
    decision = agent_arm_decision_for_turn("Use Codex to review this code patch for bugs.")

    assert decision is not None
    assert decision.arm_id == "codex_agent"
    assert decision.timeout_s == 150


def test_code_task_selects_codex_without_owner_naming_it() -> None:
    decision = agent_arm_decision_for_turn(
        "Review this repo patch and identify the test risk in the tool router code."
    )

    assert decision is not None
    assert decision.arm_id == "codex_agent"
    assert "Codex" not in decision.prompt


def test_short_extraction_task_selects_corvid_without_owner_naming_it() -> None:
    decision = agent_arm_decision_for_turn(
        "Summarize this router log and extract the next action for Alice."
    )

    assert decision is not None
    assert decision.arm_id == "corvid_scout"
    assert decision.timeout_s == 30


def test_decision_prompt_carries_registry_organ_hints() -> None:
    decision = agent_arm_decision_for_turn(
        "Compare organ registry health scoring strategies for agent arms."
    )

    assert decision is not None
    assert "Registry organ hints:" in decision.prompt


def test_prepass_executes_router_tool(monkeypatch) -> None:
    from System import swarm_agent_arm_decision as decision_mod

    class FakeResult:
        tool_name = "agent_arm_research"
        executed = True
        status = "EXECUTED"
        feedback_for_alice = "agent_arm_research evidence captured"
        result = {
            "status": "EVIDENCE_CAPTURED",
            "receipt_id": "receipt-123",
            "arm_id": "hermes_agent",
        }

    seen = {}

    def fake_execute(call, *, owner_present=False, autonomous=True):
        seen["tool_name"] = call.tool_name
        seen["params"] = call.params
        seen["owner_present"] = owner_present
        seen["autonomous"] = autonomous
        return FakeResult()

    monkeypatch.setattr("System.swarm_tool_router.execute_tool_call", fake_execute)
    decision, result = decision_mod.run_agent_arm_decision_prepass(
        "Research the safest way to wire this feature.",
        owner_present=True,
    )

    assert decision is not None
    assert result is not None
    assert seen["tool_name"] == "agent_arm_research"
    assert seen["params"]["arm"] == "hermes_agent"
    assert seen["params"]["cost_justification"]
    assert seen["owner_present"] is True
    assert seen["autonomous"] is True


def test_prepass_context_carries_receipt() -> None:
    class FakeResult:
        status = "EXECUTED"
        feedback_for_alice = "evidence body"
        result = {"status": "EVIDENCE_CAPTURED", "receipt_id": "receipt-abc"}

    decision = agent_arm_decision_for_turn("Plan a safer rollout path.")
    assert decision is not None
    context = format_agent_arm_prepass_context(decision, FakeResult())

    assert "AGENT ARM DECISION PREPASS" in context
    assert "selected_arm=hermes_agent" in context
    assert "receipt-abc" in context
    assert "evidence body" in context


def test_async_prepass_schedules_without_running_when_thread_disabled(tmp_path: Path) -> None:
    job = schedule_async_agent_arm_prepass(
        "Compare safer research strategies for async evidence.",
        state_dir=tmp_path,
        start_thread=False,
    )

    assert job is not None
    assert job.status == "SCHEDULED"
    assert job.decision.arm_id == "hermes_agent"
    rows = (tmp_path / "agent_arm_async_evidence.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    assert "AGENT_ARM_ASYNC_SCHEDULED" in rows[0]


def test_async_prepass_run_inline_writes_prompt_summary(tmp_path: Path) -> None:
    class FakeResult:
        executed = True
        status = "EXECUTED"
        feedback_for_alice = "async arm evidence body"
        result = {
            "status": "EVIDENCE_CAPTURED",
            "receipt_id": "async-receipt-1",
            "artifact_path": ".sifta_state/agent_arm_receipts.jsonl",
        }

    def fake_executor(decision, owner_present):
        assert decision.arm_id == "hermes_agent"
        assert owner_present is True
        return FakeResult()

    job = schedule_async_agent_arm_prepass(
        "Plan the safest way to compare rollout paths.",
        state_dir=tmp_path,
        executor=fake_executor,
        run_inline=True,
    )

    assert job is not None
    prompt = summary_for_prompt(state_dir=tmp_path)
    assert "ASYNC AGENT ARM EVIDENCE BUFFER" in prompt
    assert "async-receipt-1" in prompt
    assert "async arm evidence body" in prompt


def test_async_prepass_labels_timeout_output_as_partial_evidence(tmp_path: Path) -> None:
    class FakeResult:
        executed = False
        status = "EXEC_FAILED_TIMEOUT"
        feedback_for_alice = "arm timed out but returned partial evidence tail"
        result = {"status": "TIMEOUT", "receipt_id": "partial-receipt-1"}

    def fake_executor(decision, owner_present):
        return FakeResult()

    schedule_async_agent_arm_prepass(
        "Compare evidence handling strategies for timeout cases.",
        state_dir=tmp_path,
        executor=fake_executor,
        run_inline=True,
    )

    prompt = summary_for_prompt(state_dir=tmp_path)
    assert "status=PARTIAL_EVIDENCE" in prompt
    assert "partial-receipt-1" in prompt


def test_async_prepass_deduplicates_recent_same_turn(tmp_path: Path) -> None:
    text = "Compare safer implementation strategies for duplicate suppression."
    first = schedule_async_agent_arm_prepass(text, state_dir=tmp_path, start_thread=False)
    second = schedule_async_agent_arm_prepass(text, state_dir=tmp_path, start_thread=False)

    assert first is not None
    assert second is not None
    assert second.status == "DUPLICATE_RECENT"
    assert second.duplicate_of == first.job_id
    rows = (tmp_path / "agent_arm_async_evidence.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
