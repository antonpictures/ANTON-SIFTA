from __future__ import annotations

import json
import os
import subprocess

from System import swarm_camera_target as target


def _redirect_paths(monkeypatch, tmp_path):
    json_path = tmp_path / "active_saccade_target.json"
    txt_path = tmp_path / "active_saccade_target.txt"
    monkeypatch.setattr(target, "TARGET_JSON", json_path)
    monkeypatch.setattr(target, "TARGET_TXT_LEGACY", txt_path)
    monkeypatch.setattr(target, "_live_devices", lambda: [])
    return json_path, txt_path


def test_legacy_key_value_one_means_macbook(monkeypatch):
    monkeypatch.setattr(target, "_live_devices", lambda: [])

    rec = target.parse_legacy_text("active_saccade_target=1")

    assert rec is not None
    assert rec["index"] == 1
    assert rec["name"] == "MacBook Pro Camera"


def test_legacy_key_value_one_resolves_to_live_macbook_not_usb(monkeypatch):
    monkeypatch.setattr(
        target,
        "_live_devices",
        lambda: [
            ("mac-live", "MacBook Pro Camera"),
            ("usb-live", "USB Camera VID:1133 PID:2081"),
        ],
    )

    rec = target.parse_legacy_text("active_saccade_target=1")

    assert rec is not None
    assert rec["index"] == 0
    assert rec["name"] == "MacBook Pro Camera"


def test_write_target_corrects_combobox_index_from_name(monkeypatch, tmp_path):
    json_path, txt_path = _redirect_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        target,
        "_live_devices",
        lambda: [("mac-live", "MacBook Pro Camera")],
    )

    rec = target.write_target(
        name="MacBook Pro Camera",
        index=99,
        writer="what_alice_sees_widget",
    )

    assert rec["index"] == 0
    assert txt_path.read_text(encoding="utf-8").strip() == "0"
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["name"] == "MacBook Pro Camera"
    assert saved["index"] == 0


def test_write_target_preserves_live_index_when_unique_id_present(monkeypatch, tmp_path):
    json_path, txt_path = _redirect_paths(monkeypatch, tmp_path)

    rec = target.write_target(
        name="USB Camera VID:1133 PID:2081",
        index=1,
        unique_id="0x3121000046d0821",
        writer="owner_camera_command",
    )

    assert rec["index"] == 1
    assert txt_path.read_text(encoding="utf-8").strip() == "1"
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["unique_id"] == "0x3121000046d0821"
    assert saved["index"] == 1


def test_write_target_uses_live_identity_over_frozen_name_index(monkeypatch, tmp_path):
    json_path, txt_path = _redirect_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        target,
        "_live_devices",
        lambda: [
            ("mac-live", "MacBook Pro Camera"),
            ("usb-live", "USB Camera VID:1133 PID:2081"),
        ],
    )

    rec = target.write_target(
        name="USB Camera VID:1133 PID:2081",
        index=0,
        writer="owner_camera_command",
    )

    assert rec["index"] == 1
    assert rec["unique_id"] == "usb-live"
    assert txt_path.read_text(encoding="utf-8").strip() == "1"
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["name"] == "USB Camera VID:1133 PID:2081"
    assert saved["index"] == 1
    assert saved["unique_id"] == "usb-live"


def test_byte_repr_unique_id_resolves_to_live_device(monkeypatch):
    monkeypatch.setattr(
        target,
        "_live_devices",
        lambda: [
            ("mac-live", "MacBook Pro Camera"),
            ("0x3121000046d0821", "USB Camera VID:1133 PID:2081"),
        ],
    )

    rec = {
        "name": "USB Camera VID:1133 PID:2081",
        "index": None,
        "unique_id": "b'0x3121000046d0821'",
        "writer": "what_alice_sees_widget",
    }

    assert target.resolve_index(rec) == 1


def test_active_high_priority_lease_blocks_widget_mirror_write(monkeypatch, tmp_path):
    json_path, _txt_path = _redirect_paths(monkeypatch, tmp_path)

    held = target.write_target(
        name="iPhone Camera",
        index=3,
        writer="crucible_unified_field",
        priority=50,
        lease_s=30.0,
    )
    blocked = target.write_target(
        name="MacBook Pro Camera",
        index=1,
        writer="what_alice_sees_widget",
        priority=0,
    )

    assert held["index"] == 3
    assert blocked["index"] == 3
    assert blocked["writer"] == "crucible_unified_field"
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["index"] == 3
    assert saved["priority"] == 50
    assert saved["lease_until"] is not None


def test_higher_priority_write_can_override_active_lease(monkeypatch, tmp_path):
    json_path, _txt_path = _redirect_paths(monkeypatch, tmp_path)

    target.write_target(
        name="iPhone Camera",
        index=3,
        writer="swarm_multisensory_colliculus",
        priority=20,
        lease_s=30.0,
    )
    rec = target.write_target(
        name="MacBook Pro Desk View Camera",
        index=5,
        writer="crucible_unified_field",
        priority=50,
        lease_s=30.0,
    )

    assert rec["index"] == 5
    assert rec["writer"] == "crucible_unified_field"
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["index"] == 5
    assert saved["priority"] == 50


def test_expired_lease_allows_widget_write(monkeypatch, tmp_path):
    json_path, _txt_path = _redirect_paths(monkeypatch, tmp_path)
    json_path.write_text(
        json.dumps(
            {
                "name": "iPhone Camera",
                "index": 3,
                "unique_id": None,
                "ts": 1.0,
                "writer": "crucible_unified_field",
                "priority": 50,
                "lease_until": 1.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rec = target.write_target(
        name="MacBook Pro Camera",
        index=1,
        writer="what_alice_sees_widget",
        priority=0,
    )

    assert rec["index"] == 1
    assert rec["writer"] == "what_alice_sees_widget"


def test_read_target_heals_newer_legacy_txt_over_stale_json(monkeypatch, tmp_path):
    json_path, txt_path = _redirect_paths(monkeypatch, tmp_path)
    json_path.write_text(
        json.dumps({"name": "iPhone Camera", "index": 3, "writer": "old"}) + "\n",
        encoding="utf-8",
    )
    txt_path.write_text("1\n", encoding="utf-8")
    os.utime(json_path, (100.0, 100.0))
    os.utime(txt_path, (200.0, 200.0))

    rec = target.read_target()

    assert rec is not None
    assert rec["index"] == 1
    assert rec["name"] == "MacBook Pro Camera"
    healed = json.loads(json_path.read_text(encoding="utf-8"))
    assert healed["index"] == 1


def test_name_only_built_in_camera_resolves_to_macbook(monkeypatch):
    monkeypatch.setattr(target, "_live_devices", lambda: [])
    rec = target.parse_legacy_text("Built-in Camera")

    assert rec is not None
    assert rec["index"] == 1
    assert target.resolve_index(rec) == 1


def test_legacy_bare_iphone_index_refused_without_owner_writer(monkeypatch):
    monkeypatch.setattr(target, "_live_devices", lambda: [])
    rec = target.parse_legacy_text("3")

    assert rec is not None
    assert rec["name"] == "iPhone Camera"
    assert rec["writer"] == "legacy_txt_int"
    assert target.resolve_index(rec) == -1


def test_legacy_bare_iphone_index_falls_back_to_live_macbook(monkeypatch):
    monkeypatch.setattr(
        target,
        "_live_devices",
        lambda: [
            ("continuity-uid", "Ioan's iPhone Camera"),
            ("built-in-uid", "MacBook Pro Camera"),
        ],
    )
    rec = target.parse_legacy_text("3")

    assert rec is not None
    assert target.resolve_index(rec) == 1


def test_owner_writer_can_explicitly_select_iphone(monkeypatch):
    monkeypatch.setattr(target, "_live_devices", lambda: [])
    rec = {
        "name": "iPhone Camera",
        "index": 3,
        "unique_id": None,
        "writer": "owner_camera_command",
    }

    assert target.resolve_index(rec) == 3


def test_preferred_live_index_never_auto_picks_iphone(monkeypatch):
    monkeypatch.setattr(
        target,
        "_live_devices",
        lambda: [("continuity-uid", "Ioan's iPhone Camera")],
    )

    assert target.preferred_live_index() == -1


def test_detached_logitech_target_falls_back_to_live_macbook(monkeypatch):
    monkeypatch.setattr(
        target,
        "_live_devices",
        lambda: [("built-in-uid", "MacBook Pro Camera")],
    )
    rec = {
        "name": "USB Camera VID:1133 PID:2081",
        "index": 0,
        "unique_id": "detached-logitech-uid",
    }

    assert target.resolve_index(rec) == 0


def test_owner_locked_detached_usb_target_does_not_open_macbook(monkeypatch):
    monkeypatch.setattr(
        target,
        "_live_devices",
        lambda: [("built-in-uid", "MacBook Pro Camera")],
    )
    rec = {
        "name": "USB Camera VID:1133 PID:2081",
        "index": 0,
        "unique_id": None,
        "writer": "owner_camera_command",
    }

    assert target.resolve_index(rec) == -1


def test_attention_director_detached_usb_target_does_not_open_macbook(monkeypatch):
    monkeypatch.setattr(
        target,
        "_live_devices",
        lambda: [("built-in-uid", "MacBook Pro Camera")],
    )
    rec = {
        "name": "USB Camera VID:1133 PID:2081",
        "index": 0,
        "unique_id": None,
        "writer": "swarm_sensor_attention_director",
    }

    assert target.resolve_index(rec) == -1


def test_prompt_line_reports_owner_usb_target_not_live(monkeypatch, tmp_path):
    _redirect_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        target,
        "_live_devices",
        lambda: [("built-in-uid", "MacBook Pro Camera")],
    )
    target.write_target(
        name="USB Camera VID:1133 PID:2081",
        index=0,
        writer="owner_camera_command",
    )

    line = target.prompt_line()

    assert "USB Camera VID:1133 PID:2081" in line
    assert "not live/unresolved" in line
    assert "writer=owner_camera_command" in line


def test_refresh_active_target_from_live_heals_stale_usb_index(monkeypatch, tmp_path):
    json_path, txt_path = _redirect_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        target,
        "_live_devices",
        lambda: [
            ("mac-uid", "MacBook Pro Camera"),
            ("0x3121000046d0821", "USB Camera VID:1133 PID:2081"),
        ],
    )
    json_path.write_text(
        json.dumps(
            {
                "name": "USB Camera VID:1133 PID:2081",
                "index": 0,
                "unique_id": None,
                "ts": 1.0,
                "writer": "owner_camera_command",
                "priority": 95,
                "lease_until": 9999.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = target.refresh_active_target_from_live(now=123.0)
    healed = json.loads(json_path.read_text(encoding="utf-8"))

    assert result["changed"] is True
    assert healed["index"] == 1
    assert healed["unique_id"] == "0x3121000046d0821"
    assert healed["writer"] == "owner_camera_command"
    assert healed["lease_until"] == 9999.0
    assert txt_path.read_text(encoding="utf-8").strip() == "1"


def test_topology_refresh_uses_state_dir_target_paths(monkeypatch, tmp_path):
    global_dir = tmp_path / "global"
    state_dir = tmp_path / "state"
    global_json = global_dir / "active_saccade_target.json"
    global_txt = global_dir / "active_saccade_target.txt"
    monkeypatch.setattr(target, "TARGET_JSON", global_json)
    monkeypatch.setattr(target, "TARGET_TXT_LEGACY", global_txt)
    global_dir.mkdir()
    state_dir.mkdir()
    global_json.write_text(
        json.dumps({"name": "MacBook Pro Camera", "index": 0, "writer": "global"}) + "\n",
        encoding="utf-8",
    )
    global_txt.write_text("0\n", encoding="utf-8")
    (state_dir / "active_saccade_target.json").write_text(
        json.dumps(
            {
                "name": "USB Camera VID:1133 PID:2081",
                "index": 0,
                "unique_id": None,
                "writer": "owner_camera_command",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        target,
        "_live_devices",
        lambda: [
            ("mac-uid", "MacBook Pro Camera"),
            ("usb-live", "USB Camera VID:1133 PID:2081"),
        ],
    )

    result = target.probe_camera_topology(state_dir=state_dir, now=2000.0, write_receipt=True)

    assert result["active_target_refresh"]["changed"] is True
    state_saved = json.loads((state_dir / "active_saccade_target.json").read_text(encoding="utf-8"))
    global_saved = json.loads(global_json.read_text(encoding="utf-8"))
    assert state_saved["unique_id"] == "usb-live"
    assert state_saved["index"] == 1
    assert global_saved["writer"] == "global"
    assert global_saved["name"] == "MacBook Pro Camera"


def test_probe_camera_topology_writes_attach_detach_receipts(monkeypatch, tmp_path):
    monkeypatch.setattr(target, "_live_devices", lambda: [("usb-1", "USB Camera VID:1133 PID:2081")])
    first = target.probe_camera_topology(state_dir=tmp_path, now=1000.0, write_receipt=True)
    assert first["changed"] is True
    assert first["appeared"][0]["name"] == "USB Camera VID:1133 PID:2081"

    monkeypatch.setattr(target, "_live_devices", lambda: [("built-in-1", "MacBook Pro Camera")])
    second = target.probe_camera_topology(state_dir=tmp_path, now=1010.0, write_receipt=True)
    assert second["changed"] is True
    assert second["vanished"][0]["name"] == "USB Camera VID:1133 PID:2081"
    assert second["appeared"][0]["name"] == "MacBook Pro Camera"

    rows = [
        json.loads(line)
        for line in (tmp_path / "device_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["kind"] for row in rows] == ["attached", "attached", "detached"]
    assert rows[-1]["is_logitech"] is True


def test_live_devices_exclude_iphone_by_default(monkeypatch):
    monkeypatch.delenv("SIFTA_ALLOW_IPHONE_CAMERA", raising=False)
    monkeypatch.delenv("SIFTA_ALLOW_VIRTUAL_CAMERA", raising=False)
    monkeypatch.setattr(target, "_qt_live_devices", lambda: [])
    monkeypatch.setattr(
        target,
        "_avfoundation_live_devices",
        lambda: [
            ("mb-uid", "MacBook Pro Camera"),
            ("iphone-uid", "iPhone Camera"),
            ("obs-uid", "OBS Virtual Camera"),
            ("usb-uid", "USB Camera VID:1133 PID:2081"),
        ],
    )

    snap = target._topology_snapshot()
    names = [d["name"] for d in snap["devices"]]

    assert "MacBook Pro Camera" in names
    assert "USB Camera VID:1133 PID:2081" in names
    assert "iPhone Camera" not in names
    assert "OBS Virtual Camera" not in names


def test_live_devices_fallback_to_system_profiler_without_opening_cameras(monkeypatch):
    monkeypatch.delenv("SIFTA_ALLOW_IPHONE_CAMERA", raising=False)
    monkeypatch.delenv("SIFTA_ALLOW_VIRTUAL_CAMERA", raising=False)
    monkeypatch.setattr(target, "_qt_live_devices", lambda: [])
    monkeypatch.setattr(target, "_avfoundation_live_devices", lambda: [])

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=["system_profiler"],
            returncode=0,
            stdout=json.dumps(
                {
                    "SPCameraDataType": [
                        {
                            "_name": "MacBook Pro Camera",
                            "spcamera_unique-id": "mac-uid",
                        },
                        {
                            "_name": "USB Camera VID:1133 PID:2081",
                            "spcamera_unique-id": "usb-uid",
                        },
                        {
                            "_name": "OBS Virtual Camera",
                            "spcamera_unique-id": "obs-uid",
                        },
                        {
                            "_name": "iPhone Camera",
                            "spcamera_unique-id": "iphone-uid",
                        },
                    ]
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(target.subprocess, "run", fake_run)

    assert target.live_devices() == [
        ("mac-uid", "MacBook Pro Camera"),
        ("usb-uid", "USB Camera VID:1133 PID:2081"),
    ]


def test_live_devices_strict_allowlist_ignores_virtual_override(monkeypatch):
    monkeypatch.setenv("SIFTA_ALLOW_VIRTUAL_CAMERA", "1")
    monkeypatch.setattr(target, "_qt_live_devices", lambda: [])
    monkeypatch.setattr(
        target,
        "_avfoundation_live_devices",
        lambda: [
            ("mb-uid", "MacBook Pro Camera"),
            ("usb-uid", "USB Camera VID:1133 PID:2081"),
            ("obs-uid", "OBS Virtual Camera"),
            ("iphone-uid", "iPhone Camera"),
            ("noise-uid", "Model ID: MacBook Pro Camera"),
            ("uvc-uid", "UVC Camera VendorID_1133 ProductID_2081"),
        ],
    )

    snap = target._topology_snapshot()
    names = [d["name"] for d in snap["devices"]]

    assert names == ["MacBook Pro Camera", "USB Camera VID:1133 PID:2081"]


def test_is_allowed_owner_body_camera_allowlist(monkeypatch):
    assert target.is_allowed_owner_body_camera("MacBook Pro Camera")
    assert target.is_allowed_owner_body_camera("USB Camera VID:1133 PID:2081")
    assert not target.is_allowed_owner_body_camera("OBS Virtual Camera")
    assert not target.is_allowed_owner_body_camera("iPhone Camera")
    assert not target.is_allowed_owner_body_camera("Ioan's iPhone Camera")
    assert not target.is_allowed_owner_body_camera("Model ID: MacBook Pro Camera")
    assert not target.is_allowed_owner_body_camera("UVC Camera VendorID_1133 ProductID_2081")
    assert not target.is_allowed_owner_body_camera("Camera")
    assert not target.is_allowed_owner_body_camera("Other Webcam")
