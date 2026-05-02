#!/usr/bin/env python3
"""
tests/test_swarm_body_brain_loop.py
══════════════════════════════════════════════════════════════════════
Tests for the executable body-brain physiology loop.
"A living loop without tests is mythology."
"""

import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ["SIFTA_ALICE_ENABLE_CONSCIOUSNESS_LOOP"] = "1"

from System.swarm_body_brain_loop import SwarmPhysiology
from System.swarm_metabolic_homeostasis import MetabolicState

@pytest.fixture
def clean_state(tmp_path):
    with patch("System.swarm_body_brain_loop._STATE_DIR", tmp_path):
        yield tmp_path

def test_body_brain_tick_normal_cycle(clean_state):
    physiology = SwarmPhysiology(enable_george_prior=False)
    
    # Force a healthy metabolic state
    healthy_state = MetabolicState(usd_burn_24h=0.0, local_units_24h=0.0, stgm_balance=150.0)
    
    with patch("System.swarm_body_brain_loop.MetabolicHomeostat.sample_live", return_value=healthy_state):
        with patch("time.sleep") as mock_sleep:
            result = physiology.body_brain_tick()
            
            # Verify outputs
            assert "action" in result
            assert "value" in result
            assert "metabolic_mode" in result
            assert result["metabolic_mode"] == "GREEN_GROW"
            
            # Verify action execution (motor cortex sleep was called)
            mock_sleep.assert_called_once_with(0.1)
            
            # Verify memory was written
            memory_file = clean_state / "body_brain_memory.jsonl"
            assert memory_file.exists()
            lines = memory_file.read_text().strip().split("\n")
            assert len(lines) == 1
            row = json.loads(lines[0])
            assert row["event"] == "body_brain_tick"
            assert "action" in row
            assert "result" in row
            assert "td_value" in row
            assert row.get("drive_state")
            assert row.get("metabolic_mode")
            phen = clean_state / "visual_phenotype_uniforms.jsonl"
            assert phen.exists()
            prow = json.loads(phen.read_text().strip().splitlines()[-1])
            assert prow.get("u_stigmergic_drive") is not None
            assert prow.get("receipt_backed") is True
            assert row.get("tick_id")
            assert "u_chemotaxis_gradient" in prow
            assert row["drive_bias_applied"] is False
            assert row["truth_label"] == "NO_INTRINSIC_DRIVE_BIAS"

def test_body_brain_tick_critical_sleep_trigger(clean_state):
    physiology = SwarmPhysiology(enable_george_prior=False)
    
    # Force a critical metabolic state (starving/high pressure)
    critical_state = MetabolicState(usd_burn_24h=12.0, local_units_24h=200.0, stgm_balance=0.0)
    
    with patch("System.swarm_body_brain_loop.MetabolicHomeostat.sample_live", return_value=critical_state):
        with patch("time.sleep") as mock_sleep:
            result = physiology.body_brain_tick()
            
            assert result["metabolic_mode"] in ("RED_CONSERVE", "CRITICAL_STARVATION")
            assert result["action"]["type"] == "rest"
            
            # Sleep should be called TWICE: once for motor execution (0.1) and once for enforced sleep (>0)
            assert mock_sleep.call_count == 2


def test_choose_action_applies_high_score_intrinsic_drive_bias(clean_state):
    physiology = SwarmPhysiology(enable_george_prior=False)
    receipt = {
        "topic": "biology",
        "goal": "Inspect dream skill crystallization.",
        "score": 0.168,
        "source": "test_harness",
    }

    action = physiology._choose_action(
        "curiosity",
        {"is_critical": False, "mode": "GREEN_GROW", "pressure": 0.0},
        intrinsic_receipt=receipt,
    )

    assert action["type"] == "explore"
    assert action["target"] == "curiosity"
    assert action["drive_bias_applied"] is True
    assert action["drive_bias_topic"] == "biology"
    assert action["drive_bias_goal"] == "Inspect dream skill crystallization."
    assert action["drive_bias_score"] == 0.168
    assert action["drive_bias_source"] == "test_harness"
    assert action["truth_label"] == "SIMULATED_INTRINSIC_DRIVE"


def test_choose_action_ignores_low_score_intrinsic_drive_bias(clean_state):
    physiology = SwarmPhysiology(enable_george_prior=False)
    receipt = {"topic": "biology", "goal": "Too weak.", "score": 0.01, "source": "test_harness"}

    action = physiology._choose_action(
        "curiosity",
        {"is_critical": False, "mode": "GREEN_GROW", "pressure": 0.0},
        intrinsic_receipt=receipt,
    )

    assert action["type"] == "explore"
    assert action["drive_bias_applied"] is False
    assert action["drive_bias_topic"] == ""
    assert action["truth_label"] == "NO_INTRINSIC_DRIVE_BIAS"


def test_body_brain_tick_writes_drive_bias_ledger_fields(clean_state):
    physiology = SwarmPhysiology(enable_george_prior=False)
    healthy_state = MetabolicState(usd_burn_24h=0.0, local_units_24h=0.0, stgm_balance=150.0)
    receipt = {
        "topic": "identity",
        "goal": "Review the founding covenant.",
        "score": 0.2,
        "source": "test_harness",
    }

    with patch("System.swarm_body_brain_loop._GEORGE_PRIOR_AVAILABLE", True):
        with patch("System.swarm_body_brain_loop.get_current_drive", return_value=receipt):
            with patch("System.swarm_body_brain_loop.MetabolicHomeostat.sample_live", return_value=healthy_state):
                with patch("time.sleep"):
                    result = physiology.body_brain_tick()

    assert result["action"]["drive_bias_applied"] is True
    row = json.loads((clean_state / "body_brain_memory.jsonl").read_text().splitlines()[-1])
    assert row["drive_bias_applied"] is True
    assert row["drive_bias_topic"] == "identity"
    assert row["drive_bias_goal"] == "Review the founding covenant."
    assert row["drive_bias_score"] == 0.2
    assert row["drive_bias_source"] == "test_harness"
    assert row["truth_label"] == "SIMULATED_INTRINSIC_DRIVE"


def test_critical_danger_suppresses_drive_bias_even_with_receipt(clean_state):
    physiology = SwarmPhysiology(enable_george_prior=False)
    receipt = {
        "topic": "biology",
        "goal": "Should not override rest.",
        "score": 0.5,
        "source": "test_harness",
    }

    action = physiology._choose_action(
        "curiosity",
        {"is_critical": True, "mode": "CRITICAL_STARVATION", "pressure": 1.0},
        intrinsic_receipt=receipt,
    )

    assert action["type"] == "rest"
    assert action["drive_bias_applied"] is False
    assert action["drive_bias_topic"] == ""
    assert action["truth_label"] == "NO_INTRINSIC_DRIVE_BIAS"
