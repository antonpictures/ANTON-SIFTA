"""CUR-V1..V3 — owner-frame on-demand describe wiring."""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest


def test_is_owner_visual_describe_query_detects_clothes_and_colors():
    from Applications.sifta_talk_to_alice_widget import (
        _is_can_you_see_me_query,
        _is_owner_visual_describe_query,
    )

    assert _is_owner_visual_describe_query("describe my clothes")
    assert _is_owner_visual_describe_query("can you see colors on me")
    assert _is_owner_visual_describe_query("what can you see now")
    assert not _is_owner_visual_describe_query("can you see me")
    assert not _is_can_you_see_me_query("describe my clothes")
    assert not _is_can_you_see_me_query("CAN U SEE ATTACHED BUTTON ON CURRENT PAGE?")


def test_describe_owner_frame_on_demand_writes_receipt(tmp_path: Path):
    from System.swarm_saccadic_blink_vision import describe_owner_frame_on_demand

    frame = tmp_path / "visual_stigmergy_last_frame.jpg"
    frame.write_bytes(b"fakejpg")
    (tmp_path / "visual_stigmergy.jsonl").write_text(
        json.dumps({"ts": 1.0, "sha8": "abc", "w": 640, "h": 480, "motion_mean": 0.02})
        + "\n",
        encoding="utf-8",
    )

    with mock.patch(
        "System.swarm_saccadic_blink_vision._run_owner_frame_vlm",
        return_value={
            "status": "ok",
            "source": "test",
            "eye_role": "owner_eye",
            "description": "grey t-shirt, dark hair, desk behind",
        },
    ):
        row = describe_owner_frame_on_demand(state_dir=tmp_path, owner_text="describe my clothes")

    assert row.get("on_demand") is True
    desc = row.get("semantic_description") or {}
    assert desc.get("status") == "ok"
    assert "grey t-shirt" in str(desc.get("description"))
    ledger = (tmp_path / "saccadic_blink_vision.jsonl").read_text(encoding="utf-8")
    assert "owner_frame_on_demand" in ledger
    assert "should_not_persist" not in ledger


def test_describe_unavailable_without_frame(tmp_path: Path):
    from System.swarm_saccadic_blink_vision import describe_owner_frame_on_demand

    row = describe_owner_frame_on_demand(state_dir=tmp_path, owner_text="describe me")
    desc = row.get("semantic_description") or {}
    assert desc.get("status") == "unavailable"


def test_owner_visual_describe_context_block_uses_receipt():
    from Applications.sifta_talk_to_alice_widget import _owner_visual_describe_context_block

    with mock.patch(
        "System.swarm_saccadic_blink_vision.describe_owner_frame_on_demand",
        return_value={
            "frame_age_s": 12.0,
            "semantic_description": {
                "status": "ok",
                "description": "blue shirt, beige wall",
            },
        },
    ):
        block = _owner_visual_describe_context_block("describe my clothes")
    assert "OWNER VISUAL DESCRIBE TURN" in block
    assert "blue shirt" in block
    assert "Do not invent colors" in block


def test_pacino_guard_stays_on_world_eye_only():
    from System.swarm_saccadic_blink_vision import _default_description

    ctx = {
        "enable_local_vlm": True,
        "eye_role": "world_eye",
        "world_frame_path": None,
        "visual": {},
        "face": {},
        "semantic_labels": [],
    }
    out = _default_description(ctx)
    assert out.get("status") == "unavailable"
    assert "Pacino" in str(out.get("description"))
