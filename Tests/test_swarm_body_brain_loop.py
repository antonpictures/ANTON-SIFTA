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
    physiology = SwarmPhysiology()
    
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

def test_body_brain_tick_critical_sleep_trigger(clean_state):
    physiology = SwarmPhysiology()
    
    # Force a critical metabolic state (starving/high pressure)
    critical_state = MetabolicState(usd_burn_24h=12.0, local_units_24h=200.0, stgm_balance=0.0)
    
    with patch("System.swarm_body_brain_loop.MetabolicHomeostat.sample_live", return_value=critical_state):
        with patch("time.sleep") as mock_sleep:
            result = physiology.body_brain_tick()
            
            assert result["metabolic_mode"] in ("RED_CONSERVE", "CRITICAL_STARVATION")
            assert result["action"]["type"] == "rest"
            
            # Sleep should be called TWICE: once for motor execution (0.1) and once for enforced sleep (>0)
            assert mock_sleep.call_count == 2
