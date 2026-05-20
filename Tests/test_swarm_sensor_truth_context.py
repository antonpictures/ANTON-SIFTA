import json
import time
from pathlib import Path

from System.swarm_sensor_truth_context import build_sensor_truth_context, summary_for_alice


def _write_json(path: Path, row: dict) -> None:
    path.write_text(json.dumps(row), encoding="utf-8")


def _append_jsonl(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _write_kernel(state: Path, now: float, *, health: float = 1.0, heartbeat_age_s: float = 3.0) -> None:
    _write_json(
        state / "kernel_process_table.json",
        {
            "processes": {
                "e35_vision_001": {
                    "health": health,
                    "last_heartbeat_ts": now - heartbeat_age_s,
                }
            }
        },
    )


def test_fresh_visual_row_with_active_eye_verifies_live_frames_not_identity(tmp_path):
    now = time.time()
    _write_json(
        tmp_path / "active_saccade_target.json",
        {"name": "USB Camera VID:1133 PID:2081", "index": 0, "writer": "test", "ts": now},
    )
    _append_jsonl(
        tmp_path / "visual_stigmergy.jsonl",
        {"ts": now, "w": 1920, "h": 1080, "entropy_bits": 7.2},
    )
    _write_kernel(tmp_path, now)
    _append_jsonl(
        tmp_path / "acoustic_fingerprints.jsonl",
        {
            "ts": now,
            "playback_fingerprint": {
                "channel_cue": "nearfield_voice_likely",
                "nearfield_voice_likelihood": 0.8,
                "farfield_replay_likelihood": 0.2,
            },
        },
    )

    ctx = build_sensor_truth_context(state_dir=tmp_path, now=now)
    text = summary_for_alice(state_dir=tmp_path, now=now)

    assert ctx["visual_stigmergy"]["fresh"] is True
    assert ctx["visual_stigmergy"]["explicit_camera_receipt"] is False
    assert ctx["visual_stigmergy"]["camera_source_attribution"] == "inferred_from_active_eye_target"
    assert ctx["camera_unified_field_proof"]["connection_state"] == "LIVE_CAPTURE_VERIFIED"
    assert ctx["camera_live_capture_verified"] is True
    assert ctx["speaker_identity_verified"] is False
    assert "speaker_identity_verified=false" in text
    assert "proves live visual frames" in text
    assert "does not prove owner identity" in text


def test_explicit_camera_receipt_can_verify_live_capture(tmp_path):
    now = time.time()
    _append_jsonl(
        tmp_path / "visual_stigmergy.jsonl",
        {
            "ts": now,
            "w": 640,
            "h": 480,
            "camera_name": "MacBook Pro Camera",
            "entropy_bits": 6.5,
        },
    )
    _write_kernel(tmp_path, now)

    ctx = build_sensor_truth_context(state_dir=tmp_path, now=now)

    assert ctx["visual_stigmergy"]["explicit_camera_receipt"] is True
    assert ctx["camera_unified_field_proof"]["connection_state"] == "LIVE_CAPTURE_VERIFIED"
    assert ctx["camera_live_capture_verified"] is True


def test_stale_visual_proof_is_prompt_visible_as_disconnected(tmp_path):
    now = time.time()
    _write_json(
        tmp_path / "active_saccade_target.json",
        {"name": "MacBook Pro Camera", "index": 1, "writer": "test", "ts": now},
    )
    _append_jsonl(
        tmp_path / "active_eye_identity_frames.jsonl",
        {"ts": now - 594, "w": 1920, "h": 1080, "sha8": "stale"},
    )
    _append_jsonl(
        tmp_path / "visual_stigmergy.jsonl",
        {"ts": now - 589, "w": 1920, "h": 1080, "sha8": "stale"},
    )
    _write_kernel(tmp_path, now, heartbeat_age_s=594)

    ctx = build_sensor_truth_context(state_dir=tmp_path, now=now)
    text = summary_for_alice(state_dir=tmp_path, now=now)

    assert ctx["camera_live_capture_verified"] is False
    assert ctx["camera_unified_field_proof"]["connection_state"] == "DISCONNECTED_OR_STALE_INPUT"
    assert "stale_visual_stigmergy" in ctx["camera_unified_field_proof"]["disconnect_reasons"]
    assert "camera_connection_state=DISCONNECTED_OR_STALE_INPUT" in text
    assert "must say the camera input is stale/disconnected" in text


def test_owner_sensor_correction_is_prompt_visible(tmp_path):
    now = time.time()
    _append_jsonl(
        tmp_path / "sensor_claim_corrections.jsonl",
        {
            "ts": now,
            "claim": "voice_separation_proven",
            "observed": "George says the test did not prove George-vs-YouTube separation",
        },
    )

    text = summary_for_alice(state_dir=tmp_path, now=now)

    assert "latest_owner_sensor_correction=voice_separation_proven" in text
    assert "did not prove George-vs-YouTube separation" in text
