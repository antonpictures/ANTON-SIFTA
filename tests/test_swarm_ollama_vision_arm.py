#!/usr/bin/env python3
"""Tests: local vision arm — Alice's local eye for images (SIFTA r210).

George 2026-05-31: a LOCAL ollama cortex must look with its OWN local eye, not
silently fall to claude every time. These tests pin the local-model picker, the
honest failure modes, and the capability wiring that keeps the local eye selected
when it is the active cortex (with cloud arms only as failover)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_ollama_vision_arm as ov
from System import swarm_cortex_capabilities as cc


def test_picks_first_installed_vision_model():
    assert ov.pick_local_vision_model(installed=["llama3.2-vision:11b", "gemma:2b"]) == "llama3.2-vision:11b"
    assert ov.pick_local_vision_model(installed=["mistral:7b", "llava:13b"]) == "llava:13b"
    assert ov.pick_local_vision_model(installed=["qwen2-vl:7b"]) == "qwen2-vl:7b"


def test_no_vision_model_returns_empty_honestly():
    assert ov.pick_local_vision_model(installed=["gemma:2b", "mistral:7b"]) == ""
    assert ov.local_vision_available(installed=[]) is False
    assert ov.local_vision_available(installed=["llama3.1:8b"]) is False
    assert ov.local_vision_available(installed=["minicpm-v:8b"]) is True


def test_describe_missing_image_is_honest_failure():
    r = ov.describe_image_local("/does/not/exist.png", "describe")
    assert r.ok is False
    assert r.status == "image_missing"
    assert r.output == ""


def test_describe_no_local_model_is_honest_failure(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    r = ov.describe_image_local(str(img), "describe", model="")  # forced empty + no probe match
    # With no model passed it probes ollama; on a host with no vision model (or no
    # ollama) it must fail honestly, never pretend it saw the picture.
    assert r.ok is False
    assert r.status in {"no_local_vision_model_installed", "ollama_request_failed",
                        "empty_local_vision_reply"}


def test_result_shape_matches_agent_arm_contract():
    r = ov.LocalVisionResult(ok=True, output="a woman", model="llava:13b")
    assert hasattr(r, "ok") and hasattr(r, "output")  # describe_current_photo reads these
    assert r.ok is True and r.output == "a woman"


def test_capability_wiring_keeps_local_eye_selected():
    # The local eye is a real vision arm and can transport the local PNG.
    assert cc._arm_is_vision("ollama_vision_agent") is True
    assert cc._arm_can_receive_local_image("ollama_vision_agent") is True
    # When the active cortex IS the local eye, pick_vision_arm keeps it (no failover).
    pick = cc.pick_vision_arm(current_arm="ollama_vision_agent", local_image_required=True)
    assert pick["selected_arm"] == "ollama_vision_agent"
    assert pick["switched"] is False
    # Cloud arms remain available as honest failover, not as the default eye.
    assert "claude_agent" in pick["fallbacks"]


def test_no_cortex_still_defaults_to_cloud_priority_one():
    # The pre-r210 'always claude' is now ONLY this path: no current cortex at all.
    pick = cc.pick_vision_arm(current_arm="", local_image_required=True)
    assert pick["selected_arm"] == "claude_agent"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
