import os
import json
import time
import numpy as np
from pathlib import Path
from typing import Any

from System.swarm_stigmergic_cochlea import StigmergicCochlea, COCHLEA_LOG


def test_cochlea_default_state():
    cochlea = StigmergicCochlea()
    state = cochlea.get_latest_features()
    assert state["vad_active"] == 0.0
    assert state["danger_state"] == 0.0
    assert "mfcc_mean" in state


def test_cochlea_synthetic_buffer_loud_noise(monkeypatch: Any, tmp_path: Path):
    tmp_log = tmp_path / "stigmergic_cochlea.jsonl"
    monkeypatch.setattr("System.swarm_stigmergic_cochlea.COCHLEA_LOG", tmp_log)
    monkeypatch.setattr("System.swarm_stigmergic_cochlea.STATE_DIR", tmp_path)

    # Disable hardware mic completely for tests
    monkeypatch.setenv("SIFTA_MIC_OPT_IN", "0")
    
    cochlea = StigmergicCochlea(samplerate=16000, block_duration=0.05)
    cochlea.start()
    
    try:
        # Generate loud synthetic noise (high RMS)
        y = np.random.normal(0, 0.8, size=800)
        cochlea.inject_synthetic_buffer(y)
        
        # Wait up to 2.0s for thread to process
        for _ in range(20):
            features = cochlea.get_latest_features()
            if features["vad_active"] == 1.0:
                break
            time.sleep(0.1)
            
        assert features["vad_active"] == 1.0  # High RMS should trigger VAD
        assert features["volume"] > 0.1
        
        # Verify ledger write
        assert tmp_log.exists()
        lines = tmp_log.read_text().strip().splitlines()
        assert len(lines) > 0
        written_state = json.loads(lines[-1])
        assert "stress" in written_state
    finally:
        cochlea.stop()


def test_cochlea_synthetic_buffer_silence(monkeypatch: Any, tmp_path: Path):
    tmp_log = tmp_path / "stigmergic_cochlea.jsonl"
    monkeypatch.setattr("System.swarm_stigmergic_cochlea.COCHLEA_LOG", tmp_log)
    monkeypatch.setattr("System.swarm_stigmergic_cochlea.STATE_DIR", tmp_path)
    monkeypatch.setenv("SIFTA_MIC_OPT_IN", "0")
    
    cochlea = StigmergicCochlea(samplerate=16000, block_duration=0.05)
    cochlea.start()
    
    try:
        # Generate silence
        y = np.zeros(800)
        cochlea.inject_synthetic_buffer(y)
        
        time.sleep(0.3)
        
        features = cochlea.get_latest_features()
        assert features["vad_active"] == 0.0
        assert features["volume"] < 0.01
        
    finally:
        cochlea.stop()
