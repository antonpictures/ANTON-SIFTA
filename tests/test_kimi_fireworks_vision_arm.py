#!/usr/bin/env python3
"""Tests: Kimi K2.6 sees with its OWN Fireworks API (SIFTA r214).

George 2026-05-31: "I'm on kimi k cortex, has tools image all — stay on kimi k api."
Kimi K2.6 is native multimodal on Fireworks, so when Kimi is the cortex the eye is its
own /chat/completions image_url call — not a swap to claude, and NOT the local gemma4
eye. These tests pin the honest failure modes, the capability transport flip, and the
router precedence (Kimi before the local fallback)."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_fireworks_vision_arm as fv
from System import swarm_cortex_capabilities as cc


def test_default_model_is_kimi():
    assert fv.DEFAULT_VISION_MODEL == "accounts/fireworks/models/kimi-k2p6"


def test_missing_image_is_honest_failure():
    r = fv.describe_image_fireworks("/does/not/exist.png", "describe")
    assert r.ok is False and r.status == "image_missing"


def test_no_key_is_honest_failure(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 40)
    # empty env + a state dir with no fireworks secret -> no key, honest stop
    r = fv.describe_image_fireworks(str(img), "describe", state_dir=tmp_path, env={})
    assert r.ok is False and r.status == "no_fireworks_api_key"


def test_result_shape_matches_arm_contract():
    r = fv.FireworksVisionResult(ok=True, output="a woman", model="kimi")
    assert hasattr(r, "ok") and hasattr(r, "output")
    assert r.ok is True and r.output == "a woman"


def test_capability_qwen_now_transports_and_stays_selected():
    assert cc._arm_can_receive_local_image("qwen_agent") is True
    pick = cc.pick_vision_arm(current_arm="qwen_agent", local_image_required=True)
    assert pick["selected_arm"] == "qwen_agent"
    assert pick["switched"] is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
