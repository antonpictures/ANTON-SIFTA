#!/usr/bin/env python3
"""Tests for the Spinal Cord — bridge between self-detection and MiMo cortex."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO = Path(__file__).resolve().parents[1]
sys_path_inserted = False
try:
    import sys
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
        sys_path_inserted = True
except Exception:
    pass

from System.swarm_spinal_cord import (
    BodySignal,
    PatchTask,
    PatchResult,
    collect_body_signals,
    compute_field_interconnect_score,
    formulate_task,
    _extract_block,
    _extract_field,
    _check_ast,
    _record_bias_teacher_success_if_kept,
    spinal_cord_status,
    format_spinal_cord_reply,
    TRUTH_LABEL,
    DOCTOR,
)


# ---------------------------------------------------------------------------
# BodySignal basics
# ---------------------------------------------------------------------------

class TestBodySignal:
    def test_signal_creation(self):
        sig = BodySignal(
            signal_id=str(uuid.uuid4()),
            ts=time.time(),
            source="self_eval",
            severity="red",
            summary="Organ health critical",
            target_files=["System/swarm_foo.py"],
        )
        assert sig.severity == "red"
        assert "System/swarm_foo.py" in sig.target_files

    def test_signal_with_suggested_fix(self):
        sig = BodySignal(
            signal_id=str(uuid.uuid4()),
            ts=time.time(),
            source="owner_correction",
            severity="yellow",
            summary="George said X is wrong",
            target_files=[],
            suggested_fix="Update the regex pattern",
        )
        assert sig.suggested_fix == "Update the regex pattern"


# ---------------------------------------------------------------------------
# Collect signals from ledgers
# ---------------------------------------------------------------------------

class TestCollectBodySignals:
    def test_empty_state_dir(self, tmp_path):
        signals = collect_body_signals(state_dir=tmp_path)
        assert signals == []

    def test_collects_rlhs_events(self, tmp_path):
        sd = tmp_path / ".sifta_state"
        sd.mkdir()
        rlhs_path = sd / "rlhs_events.jsonl"
        rlhs_path.write_text(json.dumps({
            "ts": time.time(),
            "action": "flag",
            "detail": "residual template language detected",
        }) + "\n")
        signals = collect_body_signals(state_dir=tmp_path)
        assert len(signals) == 1
        assert signals[0].source == "drift_detector"
        assert "RLHS" in signals[0].summary

    def test_collects_owner_corrections(self, tmp_path):
        sd = tmp_path / ".sifta_state"
        sd.mkdir()
        conv_path = sd / "alice_conversation.jsonl"
        conv_path.write_text(json.dumps({
            "ts": time.time(),
            "content": "The function is wrong, it should be returning a list not a dict",
        }) + "\n")
        signals = collect_body_signals(state_dir=tmp_path)
        assert len(signals) == 1
        assert signals[0].source == "owner_correction"

    def test_ignores_benign_conversations(self, tmp_path):
        sd = tmp_path / ".sifta_state"
        sd.mkdir()
        conv_path = sd / "alice_conversation.jsonl"
        conv_path.write_text(json.dumps({
            "ts": time.time(),
            "content": "Hello Alice, how are you today?",
        }) + "\n")
        signals = collect_body_signals(state_dir=tmp_path)
        assert len(signals) == 0

    def test_collects_organ_health_below_threshold(self, tmp_path):
        sd = tmp_path / ".sifta_state"
        sd.mkdir()
        health_path = sd / "organ_health_mesh.jsonl"
        health_path.write_text(json.dumps({
            "ts": time.time(),
            "organ": "vision",
            "organ_file": "System/swarm_what_alice_sees.py",
            "health": 0.2,
        }) + "\n")
        signals = collect_body_signals(state_dir=tmp_path)
        assert len(signals) == 1
        assert signals[0].severity == "red"

    def test_ignores_healthy_organs(self, tmp_path):
        sd = tmp_path / ".sifta_state"
        sd.mkdir()
        health_path = sd / "organ_health_mesh.jsonl"
        health_path.write_text(json.dumps({
            "ts": time.time(),
            "organ": "hearing",
            "organ_file": "System/swarm_what_alice_hears.py",
            "health": 0.9,
        }) + "\n")
        signals = collect_body_signals(state_dir=tmp_path)
        assert len(signals) == 0

    def test_qualia_low_score_emits_signal(self, tmp_path):
        sd = tmp_path / ".sifta_state"
        sd.mkdir()
        (sd / "alice_conversation.jsonl").write_text(
            json.dumps({
                "ts": time.time(),
                "role": "assistant",
                "content": "I am Alice and I control many bodies without citing paths.",
            })
            + "\n",
            encoding="utf-8",
        )
        signals = collect_body_signals(state_dir=tmp_path)
        sources = {s.source for s in signals}
        assert "qualia_consistency" in sources

    def test_interconnect_score_empty_field_is_healthy(self, tmp_path):
        score, count = compute_field_interconnect_score(state_dir=tmp_path)
        assert score == 1.0
        assert count == 0

    def test_bias_correction_emits_training_signal(self, tmp_path):
        sd = tmp_path / ".sifta_state"
        sd.mkdir()
        (sd / "bias_correction_receipts.jsonl").write_text(
            json.dumps({
                "ts": time.time(),
                "kind": "BIAS_CORRECTION",
                "pattern_ids": ["safety_refusal"],
                "should_have": "Grounded receipt-first reply.",
            })
            + "\n",
            encoding="utf-8",
        )
        signals = collect_body_signals(state_dir=tmp_path)
        assert any(s.source == "training_bias" for s in signals)


# ---------------------------------------------------------------------------
# Task formulation
# ---------------------------------------------------------------------------

class TestFormulateTask:
    def test_basic_task(self):
        signal = BodySignal(
            signal_id=str(uuid.uuid4()),
            ts=time.time(),
            source="self_eval",
            severity="red",
            summary="Regex mismatch in RLHS detector",
            target_files=["System/swarm_rlhf_detector.py"],
            suggested_fix="Update the pattern",
        )
        task = formulate_task(signal)
        assert task.signal_id == signal.signal_id
        assert "swarm_rlhf_detector.py" in task.task_prompt
        assert "Regex mismatch" in task.task_prompt
        assert task.predicted_gain == 0.2  # red severity

    def test_task_with_no_target_files(self):
        signal = BodySignal(
            signal_id=str(uuid.uuid4()),
            ts=time.time(),
            source="owner_correction",
            severity="yellow",
            summary="George says the output is garbled",
            target_files=[],
        )
        task = formulate_task(signal)
        assert "MiMo must identify" in task.task_prompt

    def test_task_finds_test_files(self, tmp_path):
        # Create a fake test file
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_swarm_rlhf_detector.py").write_text("# test")
        signal = BodySignal(
            signal_id=str(uuid.uuid4()),
            ts=time.time(),
            source="self_eval",
            severity="yellow",
            summary="test",
            target_files=["System/swarm_rlhf_detector.py"],
        )
        task = formulate_task(signal, state_dir=tmp_path)
        # Test file discovery looks in the real tests dir, not tmp_path
        # so we just verify the task was created
        assert task.task_id


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

class TestParseMimoResponse:
    def test_structured_response(self):
        raw = json.dumps({
            "result": "CHANGED_FILES: System/swarm_foo.py\nDIFF_SUMMARY: Fixed the regex\nTESTS_PASSED: true\nNEW_CONTENT_START\nprint('fixed')\nNEW_CONTENT_END"
        })
        task = PatchTask(
            task_id=str(uuid.uuid4()),
            ts=time.time(),
            signal_id="sig1",
            target_files=["System/swarm_foo.py"],
            task_prompt="fix it",
        )
        result = PatchResult.__new__(PatchResult)
        # Test the extraction functions directly
        text = json.loads(raw).get("result", "")
        assert _extract_field(text, "CHANGED_FILES") == "System/swarm_foo.py"
        assert _extract_field(text, "DIFF_SUMMARY") == "Fixed the regex"
        assert _extract_field(text, "TESTS_PASSED") == "true"
        assert _extract_block(text, "NEW_CONTENT_START", "NEW_CONTENT_END") == "print('fixed')"

    def test_unstructured_response(self):
        text = "I fixed the issue by updating the regex pattern."
        assert _extract_field(text, "CHANGED_FILES") == ""
        assert _extract_block(text, "NEW_CONTENT_START", "NEW_CONTENT_END") == ""


# ---------------------------------------------------------------------------
# AST checking
# ---------------------------------------------------------------------------

class TestCheckAst:
    def test_valid_python(self):
        assert _check_ast("print('hello')", "test.py") is True

    def test_invalid_python(self):
        assert _check_ast("def foo(:", "test.py") is False

    def test_non_python_file(self):
        assert _check_ast("not python", "test.txt") is True

    def test_complex_valid(self):
        code = """
from __future__ import annotations
def foo(x: int) -> int:
    return x + 1
"""
        assert _check_ast(code, "System/swarm_foo.py") is True


# ---------------------------------------------------------------------------
# Status and formatting
# ---------------------------------------------------------------------------

class TestStatus:
    def test_empty_status(self, tmp_path):
        sd = tmp_path / ".sifta_state"
        sd.mkdir()
        status = spinal_cord_status(state_dir=tmp_path)
        assert status["total_cycles"] == 0
        assert status["proposals"]["total"] == 0

    def test_format_reply_empty(self, tmp_path):
        sd = tmp_path / ".sifta_state"
        sd.mkdir()
        reply = format_spinal_cord_reply(state_dir=tmp_path)
        assert "SPINAL CORD STATUS" in reply
        assert "No cycles yet" in reply

    def test_format_reply_with_cycles(self, tmp_path):
        sd = tmp_path / ".sifta_state"
        sd.mkdir()
        ledger = sd / "spinal_cord_cycles.jsonl"
        ledger.write_text(json.dumps({
            "cycle_id": "test1",
            "ts": time.time(),
            "status": "KEPT",
            "signal_source": "self_eval",
            "signal_severity": "red",
            "signal_summary": "test signal",
        }) + "\n")
        reply = format_spinal_cord_reply(state_dir=tmp_path)
        assert "KEPT" in reply
        assert "self_eval" in reply


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_truth_label(self):
        assert TRUTH_LABEL == "SPINAL_CORD_V1"

    def test_doctor(self):
        assert DOCTOR == "alice_spinal_cord"


class TestBiasTeacherSuccess:
    def test_record_on_kept_bias_patch(self, tmp_path):
        sd = tmp_path / ".sifta_state"
        sd.mkdir()
        receipt = {"status": "KEPT", "cycle_id": "cycle-test-1", "proposal_id": "prop-1"}
        _record_bias_teacher_success_if_kept(
            receipt=receipt,
            target_file="System/swarm_training_bias_detector.py",
            teach_context={"pattern_ids": ["safety_refusal"], "bias_probability": 0.5},
            state_dir=sd,
        )
        rows = (sd / "teacher_success.jsonl").read_text(encoding="utf-8")
        assert "bias_spinal_cycle" in rows
        assert "safety_refusal" in rows
        assert receipt.get("teacher_success_recorded") is True
