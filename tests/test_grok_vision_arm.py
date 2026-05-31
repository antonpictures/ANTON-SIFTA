#!/usr/bin/env python3
"""Tests: grok cortex sees with grok's OWN eye (SIFTA r211).

George 2026-05-31: "I have grok cortex selected, use grok cortex — why still
claude?" grok-4 is multimodal but its arm (grok_chat.py) only ever sent text, so
pick_vision_arm marked it transport-incapable (r205) and failed over to claude.
These tests pin grok's new --image path: the screenshot is inlined as an xAI
image_url base64 data URI, the launcher hands grok the path, and capabilities now
keep grok selected as its own eye."""
import importlib.util
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_spec = importlib.util.spec_from_file_location("grok_chat", os.path.join(_REPO, "grok_chat.py"))
gc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gc)

from System import swarm_cortex_capabilities as cc
from System.swarm_agent_arm_launcher import get_agent_arm, _build_command


def _png(tmp_path):
    p = tmp_path / "shot.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 64)
    return str(p)


def test_text_only_one_shot_unchanged():
    assert gc.build_one_shot_messages("hello", None) == [{"role": "user", "content": "hello"}]
    assert gc.build_one_shot_messages("hello", []) == [{"role": "user", "content": "hello"}]


def test_image_one_shot_builds_image_url_content(tmp_path):
    img = _png(tmp_path)
    msg = gc.build_one_shot_messages("describe", [img])
    content = msg[0]["content"]
    assert content[0] == {"type": "text", "text": "describe"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_two_images_both_inlined(tmp_path):
    a, b = _png(tmp_path), str(tmp_path / "b.png")
    (tmp_path / "b.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"y" * 32)
    content = gc.build_one_shot_messages("two", [a, b])[0]["content"]
    assert sum(1 for c in content if c["type"] == "image_url") == 2


def test_vision_model_kept_or_raised_when_image_present():
    assert gc.vision_model_for("grok-3", True) == "grok-4"          # text-only raised to valid id
    assert gc.vision_model_for("grok-4", True) == "grok-4"
    assert gc.vision_model_for("grok:grok-4.3", True) == "grok-4"   # product-version -> valid API id
    assert gc.vision_model_for("grok-2-vision-1212", True) == "grok-2-vision-1212"
    assert gc.vision_model_for("grok-3", False) == "grok-3"         # no image: untouched


def test_launcher_passes_image_only_to_grok():
    grok = _build_command(get_agent_arm("grok_agent"), "look", image_path="/tmp/x.png")
    assert "--image" in grok and "/tmp/x.png" in grok
    assert "--model" in grok and "grok-4" in grok
    assert "--image" not in _build_command(get_agent_arm("grok_agent"), "look")
    # claude/codex read the path agentically from the prompt — no --image flag.
    assert "--image" not in _build_command(get_agent_arm("claude_agent"), "look", image_path="/tmp/x.png")


def test_launcher_normalizes_grok_cortex_model_hint():
    grok = _build_command(
        get_agent_arm("grok_agent"),
        "look",
        image_path="/tmp/x.png",
        model_hint="grok:grok-4.3",
    )
    idx = grok.index("--model")
    assert grok[idx + 1] == "grok-4"


def test_capability_grok_now_transports_local_image():
    assert cc._arm_can_receive_local_image("grok_agent") is True
    pick = cc.pick_vision_arm(current_arm="grok_agent", local_image_required=True)
    assert pick["selected_arm"] == "grok_agent"
    assert pick["switched"] is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
