import json

from System import swarm_camera_target
from System.swarm_owner_camera_commands import handle_owner_camera_command, summary_for_prompt


def _redirect_camera_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(swarm_camera_target, "TARGET_JSON", tmp_path / "active_saccade_target.json")
    monkeypatch.setattr(swarm_camera_target, "TARGET_TXT_LEGACY", tmp_path / "active_saccade_target.txt")


def test_side_camera_command_writes_usb_eye(monkeypatch, tmp_path):
    _redirect_camera_paths(monkeypatch, tmp_path)

    row = handle_owner_camera_command("Now switch to the side camera.", state_dir=tmp_path)

    assert row is not None
    assert row["target"]["name"] == "USB Camera VID:1133 PID:2081"
    assert row["camera_target"]["index"] == 0
    saved = json.loads((tmp_path / "active_saccade_target.json").read_text(encoding="utf-8"))
    assert saved["writer"] == "owner_camera_command"
    assert saved["priority"] >= 95
    assert saved["lease_until"] - saved["ts"] >= 1700
    assert "requested_eye=side_camera" in summary_for_prompt(row)


def test_front_camera_command_writes_macbook_eye(monkeypatch, tmp_path):
    _redirect_camera_paths(monkeypatch, tmp_path)

    row = handle_owner_camera_command(
        "switch to the front camera to the MacBook camera.",
        state_dir=tmp_path,
    )

    assert row is not None
    assert row["target"]["name"] == "MacBook Pro Camera"
    assert row["camera_target"]["index"] == 1


def test_generic_switch_toggles_usb_to_macbook_eye(monkeypatch, tmp_path):
    _redirect_camera_paths(monkeypatch, tmp_path)
    swarm_camera_target.write_target(
        name="USB Camera VID:1133 PID:2081",
        index=0,
        writer="test_seed",
    )

    row = handle_owner_camera_command("alice, pls switch the camera", state_dir=tmp_path)

    assert row is not None
    assert row["target"]["name"] == "MacBook Pro Camera"
    assert row["target"]["toggle_from"] == "USB Camera VID:1133 PID:2081"
    assert row["camera_target"]["index"] == 1


def test_generic_switch_toggles_macbook_to_usb_eye(monkeypatch, tmp_path):
    _redirect_camera_paths(monkeypatch, tmp_path)
    swarm_camera_target.write_target(
        name="MacBook Pro Camera",
        index=1,
        writer="test_seed",
    )

    row = handle_owner_camera_command("switch the camera", state_dir=tmp_path)

    assert row is not None
    assert row["target"]["name"] == "USB Camera VID:1133 PID:2081"
    assert row["target"]["toggle_from"] == "MacBook Pro Camera"
    assert row["camera_target"]["index"] == 0


def test_camera_count_statement_does_not_write_target(monkeypatch, tmp_path):
    _redirect_camera_paths(monkeypatch, tmp_path)

    row = handle_owner_camera_command("You have two cameras.", state_dir=tmp_path)

    assert row is None
    assert not (tmp_path / "active_saccade_target.json").exists()


def test_self_narrated_switch_claim_does_not_toggle_eye(monkeypatch, tmp_path):
    _redirect_camera_paths(monkeypatch, tmp_path)
    swarm_camera_target.write_target(
        name="MacBook Pro Camera",
        index=1,
        writer="test_seed",
    )

    row = handle_owner_camera_command("I'll switch the camera.", state_dir=tmp_path)

    saved = json.loads((tmp_path / "active_saccade_target.json").read_text(encoding="utf-8"))
    assert row is None
    assert saved["name"] == "MacBook Pro Camera"


def test_resolution_command_writes_visual_acuity_target(monkeypatch, tmp_path):
    _redirect_camera_paths(monkeypatch, tmp_path)
    (tmp_path / "visual_stigmergy.jsonl").write_text(
        json.dumps({"ts": 1, "grid_size": 44}) + "\n",
        encoding="utf-8",
    )

    row = handle_owner_camera_command("Increase camera resolution one step.", state_dir=tmp_path)

    assert row is not None
    assert row["target"] is None
    assert row["acuity_target"]["grid_size"] == 46
    assert "visual_acuity=46x46" in summary_for_prompt(row)
    saved = json.loads((tmp_path / "active_visual_acuity.json").read_text(encoding="utf-8"))
    assert saved["writer"] == "owner_camera_command"


def test_combined_switch_and_resolution_command_writes_both_receipts(monkeypatch, tmp_path):
    _redirect_camera_paths(monkeypatch, tmp_path)
    swarm_camera_target.write_target(
        name="USB Camera VID:1133 PID:2081",
        index=0,
        writer="test_seed",
    )
    (tmp_path / "visual_stigmergy.jsonl").write_text(
        json.dumps({"ts": 1, "grid_size": 44}) + "\n",
        encoding="utf-8",
    )

    row = handle_owner_camera_command("switch camera and increase resolution.", state_dir=tmp_path)

    assert row is not None
    assert row["camera_target"]["name"] == "MacBook Pro Camera"
    assert row["acuity_target"]["grid_size"] == 46
    assert row["actions"] == ["camera_target", "visual_acuity"]
