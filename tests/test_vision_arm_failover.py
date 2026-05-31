#!/usr/bin/env python3
"""Tests: Alice's image eyes are many arms with failover (George 2026-05-30).

She was routing every image to Kimi only; if she loses that API she must switch
to another vision-capable arm (claude/codex/grok/qwen/cline), not go blind. qwen
now has a direct Fireworks image transport, so it stays its own eye when Kimi is
the active cortex.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_cortex_capabilities as cap


def test_more_than_one_vision_arm_exists():
    arms = [a["arm_id"] for a in cap.vision_capable_arms()]
    # the whole point: not just kimi/cline
    assert "claude_agent" in arms and "codex_agent" in arms
    assert "cline_agent" in arms and "grok_agent" in arms
    assert "qwen_agent" in arms
    assert len(arms) >= 5


def test_local_browser_photo_ready_arms_track_transport_separately():
    ready = [a["arm_id"] for a in cap.vision_capable_arms(local_image_required=True)]
    all_rows = {a["arm_id"]: a for a in cap.vision_capable_arms()}
    assert "qwen_agent" in all_rows
    assert "qwen_agent" in ready
    assert all_rows["qwen_agent"]["local_image_transport"] is True
    assert "fireworks_image_url_base64" in all_rows["qwen_agent"]["transport_kind"]


def test_failover_when_cline_api_lost():
    pick = cap.pick_vision_arm(current_arm="cline_agent", unavailable=["cline_agent"])
    assert pick["selected_arm"] != "cline_agent"
    assert pick["switched"] is True
    assert "cline_agent" not in pick["fallbacks"]
    assert pick["reason"] == "current_cortex_api_unavailable_failover"
    assert "API may be expired" in pick["diary_note"]  # owner gets told


def test_default_eye_is_the_current_cortex():
    # George's rule: cline selected -> use cline; codex -> codex; claude -> claude
    for arm in ("cline_agent", "codex_agent", "claude_agent"):
        pick = cap.pick_vision_arm(current_arm=arm)
        assert pick["selected_arm"] == arm
        assert pick["reason"] == "current_cortex_sees_images"
        assert pick["switched"] is False


def test_failover_when_current_cortex_cannot_see_images():
    # active model is text-only (e.g. gpt-oss) even though the arm normally sees
    pick = cap.pick_vision_arm(current_arm="codex_agent", current_supports_image=False)
    assert pick["selected_arm"] != "codex_agent"
    assert pick["reason"] == "current_cortex_cannot_see_images_failover"
    assert "cannot read images" in pick["diary_note"]


def test_qwen_kimi_cortex_keeps_own_fireworks_eye_for_local_browser_photo():
    pick = cap.pick_vision_arm(
        current_arm="qwen_agent",
        current_model="qwen:accounts/fireworks/models/kimi-k2p6",
    )
    assert pick["selected_arm"] == "qwen_agent"
    assert pick["reason"] == "current_cortex_sees_images"
    assert pick["diary_note"] == ""


def test_failover_when_cline_lost_still_has_native_vision():
    # qwen is named here to prove extra blind/unavailable arms do not affect the choice.
    pick = cap.pick_vision_arm(unavailable=["qwen_agent", "cline_agent"])
    assert pick["selected_arm"] in ("claude_agent", "codex_agent", "grok_agent")


def test_keeps_current_arm_if_capable_and_up():
    pick = cap.pick_vision_arm(current_arm="codex_agent")
    assert pick["selected_arm"] == "codex_agent"
    assert pick["switched"] is False
    assert pick["diary_note"] == ""  # no note needed when the cortex just sees


def test_ordering_is_priority_stable():
    arms = cap.vision_capable_arms()
    prios = [a["priority"] for a in arms]
    assert prios == sorted(prios)
    assert arms[0]["arm_id"] == "claude_agent"  # highest priority eye


def test_all_unavailable_means_honest_blindness():
    every = [a["arm_id"] for a in cap.vision_capable_arms()]
    pick = cap.pick_vision_arm(unavailable=every)
    assert pick["selected_arm"] == ""
    assert pick["reason"] == "no_vision_arm_available"
    assert "cannot read a picture" in cap.vision_arms_block(unavailable=every)


def test_block_names_many_eyes_and_failover():
    block = cap.vision_arms_block(current_arm="cline_agent")
    assert "NOT pinned to Kimi" in block
    assert "claude_agent" in block and "codex_agent" in block and "qwen_agent" in block
    assert "local browser-photo ready now" in block
    assert "fall back" in block
    # blind arms are named so she never sends an image to them
    assert "hermes_agent" in block and "corvid_scout" in block


def test_records_cortex_arm_habit_with_transport_and_model(tmp_path):
    row = cap.record_cortex_arm_habit(
        "qwen_agent",
        cortex_model="qwen:accounts/fireworks/models/kimi-k2p6",
        task="browser_photo_local_image",
        ok=False,
        status="non_visual_reply",
        reason="arm_asked_for_image_contents",
        state_dir=tmp_path,
    )
    assert row["model_vision_capable"] is True
    assert row["arm_vision_family"] is True
    assert row["local_image_transport"] is True
    assert row["transport_kind"] == "fireworks_image_url_base64"
    assert (tmp_path / "cortex_arm_habits.jsonl").exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
