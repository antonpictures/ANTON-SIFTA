from __future__ import annotations

import json
from pathlib import Path

from System.swarm_camera_unified_field_proof import build_camera_unified_field_proof


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _write_kernel(state: Path, now: float, *, health: float = 1.0) -> None:
    (state / "kernel_process_table.json").write_text(
        json.dumps(
            {
                "processes": {
                    "e35_vision_001": {
                        "health": health,
                        "last_heartbeat_ts": now - 3,
                    }
                }
            }
        ),
        encoding="utf-8",
    )


def test_owner_recognized_when_all_field_receipts_are_fresh(tmp_path: Path) -> None:
    now = 1000.0
    state = tmp_path
    _write_jsonl(
        state / "face_detection_events.jsonl",
        [{"ts": now - 4, "event": "FACE_DETECTION", "faces_detected": 1, "audience": "architect", "confidence": 0.81}],
    )
    _write_jsonl(
        state / "active_eye_identity_frames.jsonl",
        [{"ts": now - 2, "event": "ACTIVE_EYE_IDENTITY_FRAME", "device": "MacBook Pro Camera", "w": 1920, "h": 1080, "sha8": "abc12345"}],
    )
    _write_jsonl(
        state / "visual_stigmergy.jsonl",
        [{"ts": now - 1, "sha8": "abc12345", "motion_mean": 0.02, "saliency_peak": 0.3}],
    )
    _write_kernel(state, now)

    proof = build_camera_unified_field_proof(state, now=now)

    assert proof.status == "OWNER_RECOGNIZED"
    assert proof.ok is True
    assert proof.camera_healthy is True
    assert proof.frame_sha8 == "abc12345"
    assert "eye saw" in proof.summary


def test_unknown_user_is_useful_but_not_owner_claim(tmp_path: Path) -> None:
    now = 1000.0
    state = tmp_path
    _write_jsonl(
        state / "face_detection_events.jsonl",
        [{"ts": now - 4, "event": "FACE_DETECTION", "faces_detected": 1, "audience": "unknown_face", "confidence": 0.71}],
    )
    _write_jsonl(
        state / "active_eye_identity_frames.jsonl",
        [{"ts": now - 2, "event": "ACTIVE_EYE_IDENTITY_FRAME", "device": "USB Camera", "w": 1920, "h": 1080, "sha8": "def67890"}],
    )
    _write_jsonl(state / "visual_stigmergy.jsonl", [{"ts": now - 1, "sha8": "def67890"}])
    _write_kernel(state, now)

    proof = build_camera_unified_field_proof(state, now=now)

    assert proof.status == "UNKNOWN_USER_PRESENT"
    assert proof.ok is True
    assert proof.recognition == "unknown_user"
    assert "unknown user" in proof.summary


def test_stale_or_missing_field_receipts_refuse_health_claim(tmp_path: Path) -> None:
    now = 1000.0
    state = tmp_path
    _write_jsonl(
        state / "active_eye_identity_frames.jsonl",
        [{"ts": now - 999, "event": "ACTIVE_EYE_IDENTITY_FRAME", "device": "USB Camera", "sha8": "old"}],
    )
    _write_kernel(state, now)

    proof = build_camera_unified_field_proof(state, now=now, stale_s=300)

    assert proof.status == "NOT_PROVEN"
    assert proof.ok is False
    assert proof.camera_healthy is False
    assert "not proven" in proof.summary


def test_fresh_visual_and_face_prove_owner_even_if_saved_frame_is_stale(tmp_path: Path) -> None:
    now = 1000.0
    state = tmp_path
    _write_jsonl(
        state / "face_detection_events.jsonl",
        [{"ts": now - 2, "event": "FACE_DETECTION", "faces_detected": 1, "audience": "architect", "confidence": 0.8}],
    )
    _write_jsonl(
        state / "active_eye_identity_frames.jsonl",
        [{"ts": now - 999, "event": "ACTIVE_EYE_IDENTITY_FRAME", "device": "USB Camera", "w": 1920, "h": 1080, "sha8": "old"}],
    )
    _write_jsonl(
        state / "visual_stigmergy.jsonl",
        [{"ts": now - 1, "sha8": "fresh", "w": 1920, "h": 1080}],
    )
    _write_kernel(state, now)

    proof = build_camera_unified_field_proof(state, now=now)

    assert proof.status == "OWNER_RECOGNIZED"
    assert proof.camera_healthy is True


def test_write_receipt_records_proof_row(tmp_path: Path) -> None:
    now = 1000.0
    state = tmp_path
    _write_jsonl(state / "visual_stigmergy.jsonl", [{"ts": now - 1, "sha8": "abc"}])
    _write_jsonl(state / "active_eye_identity_frames.jsonl", [{"ts": now - 1, "sha8": "abc", "device": "USB"}])
    _write_kernel(state, now)

    proof = build_camera_unified_field_proof(state, now=now, write_receipt=True)
    rows = (state / "camera_unified_field_proof.jsonl").read_text(encoding="utf-8").splitlines()

    assert rows
    row = json.loads(rows[-1])
    assert row["receipt_id"] == proof.receipt_id
    assert row["truth_label"] == "CAMERA_UNIFIED_FIELD_PROOF_V1"
