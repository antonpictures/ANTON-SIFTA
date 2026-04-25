from __future__ import annotations

import json
import os

from System import swarm_camera_target as target


def _redirect_paths(monkeypatch, tmp_path):
    json_path = tmp_path / "active_saccade_target.json"
    txt_path = tmp_path / "active_saccade_target.txt"
    monkeypatch.setattr(target, "TARGET_JSON", json_path)
    monkeypatch.setattr(target, "TARGET_TXT_LEGACY", txt_path)
    return json_path, txt_path


def test_legacy_key_value_one_means_macbook():
    rec = target.parse_legacy_text("active_saccade_target=1")

    assert rec is not None
    assert rec["index"] == 1
    assert rec["name"] == "MacBook Pro Camera"


def test_write_target_corrects_combobox_index_from_name(monkeypatch, tmp_path):
    json_path, txt_path = _redirect_paths(monkeypatch, tmp_path)

    rec = target.write_target(
        name="MacBook Pro Camera",
        index=0,
        writer="what_alice_sees_widget",
    )

    assert rec["index"] == 1
    assert txt_path.read_text(encoding="utf-8").strip() == "1"
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["name"] == "MacBook Pro Camera"
    assert saved["index"] == 1


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


def test_name_only_built_in_camera_resolves_to_macbook():
    rec = target.parse_legacy_text("Built-in Camera")

    assert rec is not None
    assert rec["index"] == 1
    assert target.resolve_index(rec) == 1
