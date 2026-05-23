import json

from System import swarm_camera_target
from System import swarm_execute_reflex as reflex


def _redirect(monkeypatch, tmp_path):
    monkeypatch.setattr(reflex, "_STATE", tmp_path)
    monkeypatch.setattr(swarm_camera_target, "TARGET_JSON", tmp_path / "active_saccade_target.json")
    monkeypatch.setattr(swarm_camera_target, "TARGET_TXT_LEGACY", tmp_path / "active_saccade_target.txt")


def test_execute_reflex_runs_camera_and_acuity_chorus(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    swarm_camera_target.write_target(
        name="USB Camera VID:1133 PID:2081",
        index=0,
        writer="test_seed",
    )
    (tmp_path / "visual_stigmergy.jsonl").write_text(
        json.dumps({"ts": 1, "grid_size": 44}) + "\n",
        encoding="utf-8",
    )

    row = reflex.detect_and_execute("EXECUTE switch to MacBook camera and increase resolution one step", stt_conf=0.8)

    assert row is not None
    assert row["ok"] is True
    assert row["actions"] == ["camera_target", "visual_acuity"]
    assert row["owner_eye_command"]["camera_target"]["index"] == 1
    assert row["owner_eye_command"]["acuity_target"]["grid_size"] == 46
    assert json.loads((tmp_path / "active_saccade_target.json").read_text(encoding="utf-8"))["index"] == 1
    assert json.loads((tmp_path / "active_visual_acuity.json").read_text(encoding="utf-8"))["grid_size"] == 46
    assert "one example" in row["response_seed"].casefold()


def test_execute_reflex_uses_usb_index_zero(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)

    row = reflex.detect_and_execute("execute use the Logitech camera", stt_conf=0.8)

    assert row is not None
    assert row["owner_eye_command"]["camera_target"]["index"] == 0
    assert json.loads((tmp_path / "active_saccade_target.json").read_text(encoding="utf-8"))["index"] == 0
