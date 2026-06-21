#!/usr/bin/env python3
"""Tests: gemma4 is Alice's designated LOCAL eye for text-only cortexes (SIFTA r213).

George 2026-05-31: "for deepseek and oss and similar have the gemma4 local be the
eye." A text-only cortex (deepseek, gpt-oss) can't see images, so it borrows an eye.
It must borrow the LOCAL gemma4 (free, on the owner's silicon), not a paid cloud arm.
These tests pin: gemma4 is recognized + preferred, an owner override wins, and with no
local vision model the picker is honestly empty (caller fails over to cloud with note)."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_ollama_vision_arm as ov
from System import swarm_cortex_capabilities as cc


def test_krishna_preferred_over_other_vision_models():
    inst = [
        "llava:13b",
        "krishairnd/Gemma-4-Uncensored:latest",
        "sifta-gemma4-alice:latest",
        "deepseek-v3:latest",
    ]
    assert ov.pick_local_vision_model(installed=inst) == "krishairnd/Gemma-4-Uncensored:latest"


def test_gemma4_preferred_when_krishna_absent():
    inst = ["llava:13b", "sifta-gemma4-alice:latest", "deepseek-v3:latest"]
    assert ov.pick_local_vision_model(installed=inst) == "sifta-gemma4-alice:latest"


def test_gemma4_tag_variants_recognized():
    assert ov.pick_local_vision_model(installed=["gemma4:12b"]) == "gemma4:12b"
    assert ov.pick_local_vision_model(installed=["gemma3:4b"]) == "gemma3:4b"
    assert ov.local_vision_available(installed=["sifta-gemma4-alice:q5"]) is True


def test_text_only_models_are_not_eyes():
    # deepseek / gpt-oss / mistral are text-only — no local eye, honest empty.
    assert ov.pick_local_vision_model(installed=["deepseek-v3", "gpt-oss:20b", "mistral:7b"]) == ""
    assert ov.local_vision_available(installed=["deepseek-r1:7b"]) is False


def test_owner_override_wins_when_installed():
    sd = Path(tempfile.mkdtemp())
    (sd / ".sifta_state").mkdir()
    (sd / ".sifta_state" / "local_vision_eye.txt").write_text("llava:13b")
    got = ov.pick_local_vision_model(installed=["sifta-gemma4-alice:latest", "llava:13b"], state_dir=sd)
    assert got == "llava:13b"


def test_override_ignored_if_not_installed_falls_to_gemma4():
    sd = Path(tempfile.mkdtemp())
    (sd / ".sifta_state").mkdir()
    (sd / ".sifta_state" / "local_vision_eye.txt").write_text("not-installed-model")
    got = ov.pick_local_vision_model(installed=["sifta-gemma4-alice:latest", "llava:13b"], state_dir=sd)
    assert got == "sifta-gemma4-alice:latest"


def test_gemma4_cortex_recognized_vision_capable():
    assert cc.is_vision_capable_model("sifta-gemma4-alice:latest") is True
    assert cc.is_vision_capable_model("gemma4:12b") is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
