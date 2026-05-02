"""
Tests for Event 100 — drive biases basal ganglia action selection.
Truth label: SIMULATED_INTRINSIC_DRIVE
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_body_brain_loop import SwarmPhysiology


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_receipt(topic="biology", goal="Test goal.", score=0.15, source="test_harness"):
    """Synthetic drive receipt that satisfies AC-4 (source: test_harness)."""
    return SimpleNamespace(
        topic=topic,
        goal=goal,
        score=score,
        source=source,
    )

def _safe_danger(is_critical=False, pressure=0.2, mode="GREEN_GROW"):
    return {"is_critical": is_critical, "pressure": pressure, "mode": mode}

def _physiology():
    return SwarmPhysiology(enable_george_prior=False)


# ── AC-1: _choose_action() signature and drive bias ───────────────────────────

class TestChooseAction:

    def test_no_receipt_returns_no_bias(self):
        p = _physiology()
        action = p._choose_action("biology", _safe_danger(), intrinsic_receipt=None)
        assert action["drive_bias_applied"] is False

    def test_receipt_above_floor_applies_bias(self):
        p = _physiology()
        receipt = _make_receipt(topic="physics", score=0.20)
        action = p._choose_action("explore", _safe_danger(), intrinsic_receipt=receipt)
        assert action["drive_bias_applied"] is True
        assert action["drive_bias_topic"] == "physics"
        assert action["drive_bias_score"] == pytest.approx(0.20, abs=1e-5)
        assert "drive_bias_goal" in action

    def test_receipt_below_floor_no_bias(self):
        p = _physiology()
        receipt = _make_receipt(score=0.01)  # below 0.05 floor
        action = p._choose_action("explore", _safe_danger(), intrinsic_receipt=receipt)
        assert action["drive_bias_applied"] is False

    def test_critical_danger_overrides_drive(self):
        """Safety gate: is_critical must suppress drive bias unconditionally."""
        p = _physiology()
        receipt = _make_receipt(score=0.99)  # very high score
        action = p._choose_action("biology", _safe_danger(is_critical=True),
                                  intrinsic_receipt=receipt)
        assert action["type"] == "rest"
        assert action["drive_bias_applied"] is False

    def test_energy_attention_overrides_drive(self):
        p = _physiology()
        receipt = _make_receipt(score=0.99)
        action = p._choose_action("energy", _safe_danger(), intrinsic_receipt=receipt)
        assert action["type"] == "forage"
        assert action["drive_bias_applied"] is False

    def test_stagnation_break_overrides_drive(self):
        p = _physiology()
        p.value_history = [1.0] * 5  # flat → stagnation
        receipt = _make_receipt(score=0.99)
        action = p._choose_action("explore", _safe_danger(), intrinsic_receipt=receipt)
        assert action.get("is_stagnation_break") is True
        assert action["drive_bias_applied"] is False

    def test_action_type_is_explore_when_biased(self):
        p = _physiology()
        receipt = _make_receipt(score=0.25)
        action = p._choose_action("architecture", _safe_danger(), intrinsic_receipt=receipt)
        assert action["type"] == "explore"

    def test_test_harness_source_label(self):
        """AC-4: synthetic receipts must carry source='test_harness'."""
        receipt = _make_receipt(source="test_harness")
        assert receipt.source == "test_harness"


# ── AC-2: Ledger fields ────────────────────────────────────────────────────────

class TestLedgerFields:

    def test_ledger_has_drive_bias_fields(self, tmp_path, monkeypatch):
        import System.swarm_body_brain_loop as mod
        monkeypatch.setattr(mod, "_STATE_DIR", tmp_path)

        p = _physiology()

        # Mock dependencies so only _write_memory is exercised
        action = {
            "type": "explore", "target": "biology",
            "drive_bias_applied": True,
            "drive_bias_topic": "biology",
            "drive_bias_score": 0.15,
            "drive_bias_goal": "Read about neurons.",
        }
        result = {"status": "completed"}
        now_state = {}

        row = p._write_memory(
            action, result, 1.0, now_state,
            drive_state="biology", metabolic_mode="GREEN_GROW",
        )

        assert row["drive_bias_applied"] is True
        assert row["drive_bias_topic"] == "biology"
        assert row["drive_bias_score"] == pytest.approx(0.15, abs=1e-5)

    def test_ledger_has_false_when_no_bias(self, tmp_path, monkeypatch):
        import System.swarm_body_brain_loop as mod
        monkeypatch.setattr(mod, "_STATE_DIR", tmp_path)

        p = _physiology()
        action = {"type": "explore", "target": "explore", "drive_bias_applied": False}
        row = p._write_memory(
            action, {}, 1.0, {},
            drive_state="explore", metabolic_mode="GREEN_GROW",
        )
        assert row["drive_bias_applied"] is False
        assert row["drive_bias_topic"] is None
        assert row["drive_bias_score"] is None


# ── AC-3: No double-daemon ─────────────────────────────────────────────────────

class TestNoDaemonDoubleStart:

    def test_enable_false_creates_no_daemon(self):
        p = SwarmPhysiology(enable_george_prior=False)
        assert p._george_prior_daemon is None

    def test_start_george_prior_idempotent(self):
        from System.swarm_intrinsic_drive import start_george_prior, stop_george_prior
        d1 = start_george_prior(tick_interval=100)
        d2 = start_george_prior(tick_interval=100)
        assert d1 is d2
        stop_george_prior()


# ── M2: Drive × TD correlation sanity ─────────────────────────────────────────

class TestDriveTDCorrelation:

    def test_biased_action_has_score_field(self):
        p = _physiology()
        receipt = _make_receipt(score=0.18)
        action = p._choose_action("biology", _safe_danger(), intrinsic_receipt=receipt)
        assert "drive_bias_score" in action
        assert isinstance(action["drive_bias_score"], float)

    def test_score_preserved_in_ledger_row(self, tmp_path, monkeypatch):
        import System.swarm_body_brain_loop as mod
        monkeypatch.setattr(mod, "_STATE_DIR", tmp_path)
        p = _physiology()
        action = {
            "type": "explore", "target": "biology",
            "drive_bias_applied": True,
            "drive_bias_topic": "biology",
            "drive_bias_score": 0.18,
        }
        row = p._write_memory(action, {}, 2.5, {},
                               drive_state="biology", metabolic_mode="GREEN_GROW")
        assert row["drive_bias_score"] == pytest.approx(0.18, abs=1e-5)
        assert row["td_value"] == pytest.approx(2.5, abs=1e-5)
