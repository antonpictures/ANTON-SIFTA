import os
import time
from pathlib import Path

import cv2
import numpy as np

import System.swarm_architect_face_recognition as recog


def _patch_state(monkeypatch, tmp_path: Path) -> Path:
    state = tmp_path / ".sifta_state"
    frames = state / "owner_body_vision_frames"
    frames.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(recog, "_STATE", state)
    monkeypatch.setattr(recog, "_FRAMES_DIR", frames)
    monkeypatch.setattr(recog, "_EMBEDDING", state / "architect_face_embedding.npy")
    monkeypatch.setattr(recog, "_META", state / "architect_face_meta.json")
    monkeypatch.setattr(recog, "_LEDGER", state / "face_recognition_events.jsonl")
    monkeypatch.setattr(recog, "_BINARY", state / "sifta_face_detect")
    recog._RECOGNITION_CACHE = {}
    recog._RECOGNITION_CACHE_AT = 0.0
    return state


def _write_embedding(path: Path) -> None:
    vec = np.ones(64 * 64, dtype=np.float32)
    vec = vec / np.linalg.norm(vec)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(path), vec)


def test_stale_latest_frame_never_confirms_architect(monkeypatch, tmp_path):
    state = _patch_state(monkeypatch, tmp_path)
    _write_embedding(state / "architect_face_embedding.npy")
    frame_path = state / "owner_body_vision_frames" / "old.png"
    cv2.imwrite(str(frame_path), np.zeros((96, 96, 3), dtype=np.uint8))
    old_ts = time.time() - 3600
    os.utime(frame_path, (old_ts, old_ts))

    result = recog.recognise(max_frame_age_s=60.0)

    assert result["is_architect"] is False
    assert result["method"] == "stale_frame"
    assert result["error"] == "latest_frame_stale"
    assert "confirmed" not in result["alice_line"].lower()
    assert result["frame_age_s"] >= 3500


def test_no_frame_available_writes_non_identity_receipt(monkeypatch, tmp_path):
    state = _patch_state(monkeypatch, tmp_path)
    _write_embedding(state / "architect_face_embedding.npy")

    result = recog.recognise(max_frame_age_s=60.0)

    assert result["is_architect"] is False
    assert result["method"] == "no_frame"
    assert result["alice_line"] == ""
    assert (state / "face_recognition_events.jsonl").exists()


def test_failed_training_attempt_writes_receipt(monkeypatch, tmp_path):
    state = _patch_state(monkeypatch, tmp_path)

    result = recog.train()

    assert result["ok"] is False
    assert result["error"] == "no_fresh_frame_available"
    ledger = state / "face_recognition_events.jsonl"
    assert ledger.exists()
    assert "FACE_TRAINING" in ledger.read_text(encoding="utf-8")


def test_alice_line_only_confirms_when_identity_gate_passes():
    assert "confirmed" in recog._build_alice_line(True, 0.94).lower()
    uncertain = recog._build_alice_line(False, 0.69).lower()
    assert "confirmed" not in uncertain
    assert "uncertain" in uncertain
