#!/usr/bin/env python3
"""
tests/test_swarm_vagus_pulse.py
══════════════════════════════════════════════════════════════════════
Tests for the Vagus Pulse (Nugget 1: Environmental Sync)
"""

from System.swarm_vagus_pulse import VagusPulse

def test_vagus_pulse_initialization():
    vp = VagusPulse(window_seconds=10)
    assert vp.window_seconds == 10
    assert len(vp.entropy_samples) == 0

def test_vagus_pulse_generation():
    vp = VagusPulse(window_seconds=5)
    
    # Needs at least 2 samples to calculate std_dev
    p1 = vp.generate_pulse()
    assert p1 == 0.0
    
    # 2nd sample should yield a valid float pulse
    p2 = vp.generate_pulse()
    assert isinstance(p2, float)
    assert 0.0 < p2 <= 1.0

def test_vagus_pulse_window_sliding():
    vp = VagusPulse(window_seconds=3)
    
    # Add 4 samples
    for _ in range(4):
        vp.generate_pulse()
        
    # The array should be capped at window_seconds
    assert len(vp.entropy_samples) == 3
