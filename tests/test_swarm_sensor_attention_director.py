import json
import time

from System import swarm_camera_target
from System.swarm_desire_field import DesireContext, compute_sensor_desire
from System.swarm_sensor_attention_director import (
    apply_attention_decision,
    compute_attention_drive,
    collect_world_state,
    decide_attention,
    summary_for_alice,
    tick_with_drive,
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


def test_owner_camera_lock_holds_against_face_policy(tmp_path, monkeypatch):
    _patch_camera_target(monkeypatch, tmp_path)
    now = time.time()
    swarm_camera_target.write_target(
        name="USB Camera VID:1133 PID:2081",
        index=0,
        writer="owner_camera_command",
        priority=95,
        lease_s=1800,
    )
    _append(
        tmp_path / "face_detection_events.jsonl",
        {"ts": now, "faces_detected": 1, "audience": "architect"},
    )

    world = collect_world_state(state_dir=tmp_path, now=now)
    decision = decide_attention(world)
    row = apply_attention_decision(decision, state_dir=tmp_path, write_hardware=True)

    assert decision.target_role == "room_patrol_eye"
    assert decision.reason == "owner_eye_lock_active"
    assert row["camera_target"]["writer"] == "owner_camera_command"
    assert row["camera_target"]["name"] == "USB Camera VID:1133 PID:2081"


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
    assert "camera_feed_topology=single_active_physical_eye" in summary
    assert "reason=room_patrol_" in summary
    assert "desire=" in summary
    assert "visual_motion_mean=0.3" in summary


def test_attention_desire_rises_when_owner_is_lost(tmp_path, monkeypatch):
    _patch_camera_target(monkeypatch, tmp_path)
    now = time.time()
    _append(
        tmp_path / "face_detection_events.jsonl",
        {"ts": now, "faces_detected": 0, "audience": "nobody"},
    )

    world = collect_world_state(state_dir=tmp_path, now=now)
    drive = compute_attention_drive(world, last_attention_ts=None)

    assert drive.desire > 0.55
    assert drive.next_interval_s < 3.2
    assert "owner_lost" in drive.reasons


def test_attention_desire_slows_down_when_owner_is_locked(tmp_path, monkeypatch):
    _patch_camera_target(monkeypatch, tmp_path)
    now = time.time()
    _append(
        tmp_path / "face_detection_events.jsonl",
        {"ts": now, "faces_detected": 1, "audience": "architect"},
    )

    world = collect_world_state(state_dir=tmp_path, now=now)
    drive = compute_attention_drive(world, last_attention_ts=now)

    assert drive.desire < 0.2
    assert drive.next_interval_s > 5.0
    assert "owner_locked" in drive.reasons


def test_tick_with_drive_writes_desire_status(tmp_path, monkeypatch):
    _patch_camera_target(monkeypatch, tmp_path)
    now = time.time()
    _append(
        tmp_path / "audio_ingress_log.jsonl",
        {"ts_captured": now, "rms_amplitude": 0.22},
    )

    decision, drive = tick_with_drive(state_dir=tmp_path, write_hardware=True, now=now)

    status = json.loads((tmp_path / "sensory_attention_status.json").read_text())
    assert decision.target_role == "room_patrol_eye"
    assert drive.desire == status["desire"]
    assert status["active_sense"] == "room_patrol_eye"
    assert "audio_spike" in status["desire_reasons"]


def test_desire_field_binds_owner_reward_energy_without_forcing_owner():
    hungry = DesireContext(
        stgm_balance=5.0,
        metabolic_pressure=0.8,
        reward_net=4.0,
        reward_events=12,
        source="test",
    )

    owner = compute_sensor_desire(
        owner_detected=1.0,
        unknown_signal=0.0,
        environment_signal=0.0,
        attention_stale=0.0,
        context=hungry,
    )
    novel = compute_sensor_desire(
        owner_detected=0.0,
        unknown_signal=0.8,
        environment_signal=0.8,
        attention_stale=1.0,
        context=hungry,
    )

    assert owner.preferred_role == "close_owner_eye"
    assert "owner_reward_cue" in owner.reasons
    assert novel.preferred_role == "room_patrol_eye"
    assert "exploration_pressure" in novel.reasons
    assert novel.room_patrol_drive > novel.close_owner_drive


def test_desire_field_can_switch_camera_when_no_hard_rule(tmp_path, monkeypatch):
    _patch_camera_target(monkeypatch, tmp_path)
    now = time.time()
    world = collect_world_state(state_dir=tmp_path, now=now)
    drive = compute_attention_drive(
        world,
        last_attention_ts=None,
        desire_context=DesireContext(
            stgm_balance=10.0,
            metabolic_pressure=0.75,
            reward_net=0.0,
            reward_events=3,
            source="test",
        ),
    )
    decision = decide_attention(world, desire_field=drive.field)

    assert drive.field is not None
    assert drive.field["preferred_role"] == "room_patrol_eye"
    assert decision.target_role == "room_patrol_eye"
    assert decision.reason == "desire_field_room_patrol_eye"
