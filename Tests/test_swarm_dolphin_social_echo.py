import json
import time
from pathlib import Path
from typing import Any

from System.swarm_dolphin_social_echo import (
    IDENTITY_PATH,
    AUDIOGRAM_LEDGER,
    ECHO_LEDGER,
    SOCIAL_LEDGER,
    clamp01,
    load_identity,
    encode_signature,
    decode_similarity,
    compute_social_echo,
    write_social_echo,
)


def test_clamp01():
    assert clamp01(-0.5) == 0.0
    assert clamp01(1.5) == 1.0
    assert clamp01(0.5) == 0.5
    assert clamp01("invalid") == 0.0


def test_stable_identity(tmp_path: Path, monkeypatch: Any):
    # Override path to use tmp_path
    tmp_identity = tmp_path / "agent_identity.json"
    monkeypatch.setattr("System.swarm_dolphin_social_echo.IDENTITY_PATH", tmp_identity)
    
    # First load creates it
    val1 = load_identity()
    assert tmp_identity.exists()
    assert 0.0 <= val1 <= 1.0
    
    # Second load reads it
    val2 = load_identity()
    assert val1 == val2
    
    # Force a corrupt file
    tmp_identity.write_text("invalid json")
    assert load_identity() == 0.5


def test_encode_and_decode_signature():
    identity = 0.8
    intent = 0.5
    
    sig = encode_signature(identity, intent)
    assert abs(sig - (0.7 * 0.8 + 0.3 * 0.5)) < 1e-5
    
    match = decode_similarity(sig, sig)
    assert match == 1.0
    
    match_diff = decode_similarity(sig, 0.0)
    assert match_diff < 1.0


def test_compute_social_echo(tmp_path: Path, monkeypatch: Any):
    tmp_audio = tmp_path / "stigmergic_audiogram.jsonl"
    tmp_echo = tmp_path / "bat_echo_localizer.jsonl"
    tmp_identity = tmp_path / "agent_identity.json"
    
    monkeypatch.setattr("System.swarm_dolphin_social_echo.AUDIOGRAM_LEDGER", tmp_audio)
    monkeypatch.setattr("System.swarm_dolphin_social_echo.ECHO_LEDGER", tmp_echo)
    monkeypatch.setattr("System.swarm_dolphin_social_echo.IDENTITY_PATH", tmp_identity)
    
    # Test empty state
    row = compute_social_echo()
    assert "social_presence" in row
    assert "distress_signal" in row
    assert 0.0 <= row["social_presence"] <= 1.0
    
    # Test with fake data
    tmp_audio.write_text(json.dumps({"rms": 0.8, "stress": 0.9}) + "\n")
    tmp_echo.write_text(json.dumps({"freq_shift_norm": 0.7, "attenuation": 0.1}) + "\n")
    
    row2 = compute_social_echo()
    assert row2["social_presence"] >= 0.0
    assert row2["attention_gain"] >= 0.3


def test_write_social_echo(tmp_path: Path, monkeypatch: Any):
    tmp_social = tmp_path / "dolphin_social_echo.jsonl"
    tmp_identity = tmp_path / "agent_identity.json"
    
    monkeypatch.setattr("System.swarm_dolphin_social_echo.SOCIAL_LEDGER", tmp_social)
    monkeypatch.setattr("System.swarm_dolphin_social_echo.IDENTITY_PATH", tmp_identity)
    
    row = write_social_echo()
    assert tmp_social.exists()
    lines = tmp_social.read_text().strip().splitlines()
    assert len(lines) == 1
    written_row = json.loads(lines[0])
    assert written_row["ts"] == row["ts"]
    assert written_row["emitted_signature"] == row["emitted_signature"]
