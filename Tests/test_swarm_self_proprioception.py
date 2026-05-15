"""Smoke tests for inward substrate snapshot organ."""

from __future__ import annotations

import json
import time
from pathlib import Path

from System.swarm_self_proprioception import SwarmSelfProprioception, snapshot


def test_self_proprioception_empty_state(tmp_path: Path) -> None:
    body = SwarmSelfProprioception(state_root=tmp_path).read()
    assert body["truth_label"] == "SELF_PROPRIOCEPTION_V1"
    assert body["t"] > 0
    assert "homeworld_serial" in body
    assert body["kernel"]["source"] in ("UNKNOWN", "KernelProcessTable.snapshot")
    assert body["last_visual_wake"] is None
    assert body["last_face_event_age_s"] is None
    assert isinstance(body["sensor_completeness"], float)


def test_face_and_visual_tails(tmp_path: Path) -> None:
    vis = tmp_path / "visual_stigmergy.jsonl"
    vis.write_text(
        json.dumps({"t": time.time() - 2.0, "wake_reason": "surprise", "delta": 0.1}) + "\n",
        encoding="utf-8",
    )
    face = tmp_path / "face_detection_events.jsonl"
    face.write_text(
        json.dumps({"ts": time.time() - 5.0, "event": "FACE_DETECTION", "faces_detected": 1}) + "\n",
        encoding="utf-8",
    )
    body = snapshot(state_root=tmp_path)
    assert body["last_visual_wake"]["wake_reason"] == "surprise"
    assert body["last_face_event_age_s"] is not None
    assert body["last_face_event_age_s"] >= 0.0


def test_snapshot_helper(tmp_path: Path) -> None:
    out = snapshot(state_root=tmp_path)
    assert isinstance(out, dict)
