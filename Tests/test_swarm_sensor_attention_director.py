import json
import time

from System import swarm_camera_target
from System.swarm_sensor_attention_director import (
    apply_attention_decision,
    collect_world_state,
    decide_attention,
    summary_for_alice,
)


def _append(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _patch_camera_target(monkeypatch, tmp_path):
    monkeypatch.setattr(swarm_camera_target, "TARGET_JSON", tmp_path / "active_saccade_target.json")
    monkeypatch.setattr(swarm_camera_target, "TARGET_TXT_LEGACY", tmp_path / "active_saccade_target.txt")


def test_owner_face_selects_close_eye(tmp_path, monkeypatch):
    _patch_camera_target(monkeypatch, tmp_path)
    now = time.time()
    _append(
        tmp_path / "face_detection_events.jsonl",
        {"ts": now, "faces_detected": 1, "audience": "architect"},
    )

    world = collect_world_state(state_dir=tmp_path, now=now)
    decision = decide_attention(world)

    assert decision.target_role == "close_owner_eye"
    assert decision.target_name == "MacBook Pro Camera"
    assert decision.reason == "owner_face_locked_close_eye"


def test_audio_motion_or_low_entropy_selects_room_eye_and_writes_ledger(tmp_path, monkeypatch):
    _patch_camera_target(monkeypatch, tmp_path)
    now = time.time()
    _append(
        tmp_path / "visual_stigmergy.jsonl",
        {"ts": now, "entropy_bits": 2.5, "motion_mean": 0.3},
    )
    _append(
        tmp_path / "audio_ingress_log.jsonl",
        {"ts_captured": now, "rms_amplitude": 0.22},
    )

    world = collect_world_state(state_dir=tmp_path, now=now)
    decision = decide_attention(world)
    row = apply_attention_decision(decision, state_dir=tmp_path, write_hardware=True)

    assert decision.target_role == "room_patrol_eye"
    assert decision.target_index == 0
    assert "audio_spike" in decision.reason
    assert row["camera_target"]["name"] == "USB Camera VID:1133 PID:2081"
    assert (tmp_path / "sensory_attention_ledger.jsonl").exists()


def test_external_ide_focus_selects_room_eye(tmp_path, monkeypatch):
    _patch_camera_target(monkeypatch, tmp_path)
    now = time.time()
    _append(
        tmp_path / "ide_screen_swimmers.jsonl",
        {
            "ts": now,
            "windows": [{"name": "Cursor", "x": 2000, "is_active": True}],
        },
    )

    world = collect_world_state(state_dir=tmp_path, now=now)
    decision = decide_attention(world)

    assert decision.target_role == "room_patrol_eye"
    assert decision.reason == "external_ide_focus_room_eye"


def test_high_priority_existing_eye_lease_is_respected(tmp_path, monkeypatch):
    _patch_camera_target(monkeypatch, tmp_path)
    now = time.time()
    swarm_camera_target.write_target(
        name="MacBook Pro Camera",
        writer="manual_owner_lock",
        priority=90,
        lease_s=60,
    )
    _append(
        tmp_path / "audio_ingress_log.jsonl",
        {"ts_captured": now, "rms_amplitude": 0.3},
    )

    world = collect_world_state(state_dir=tmp_path, now=now)
    decision = decide_attention(world)
    row = apply_attention_decision(decision, state_dir=tmp_path, write_hardware=True)
    current = swarm_camera_target.read_target()

    assert decision.target_role == "room_patrol_eye"
    assert row["camera_target"]["writer"] == "manual_owner_lock"
    assert current["name"] == "MacBook Pro Camera"


def test_attention_summary_surfaces_reason_and_evidence(tmp_path, monkeypatch):
    _patch_camera_target(monkeypatch, tmp_path)
    now = time.time()
    _append(
        tmp_path / "visual_stigmergy.jsonl",
        {"ts": now, "entropy_bits": 2.5, "motion_mean": 0.3},
    )

    world = collect_world_state(state_dir=tmp_path, now=now)
    decision = decide_attention(world)
    apply_attention_decision(decision, state_dir=tmp_path, write_hardware=True)

    summary = summary_for_alice(state_dir=tmp_path)
    assert "SENSORIMOTOR ATTENTION:" in summary
    assert "active_sense=room_patrol_eye" in summary
    assert "reason=room_patrol_" in summary
    assert "visual_motion_mean=0.3" in summary
