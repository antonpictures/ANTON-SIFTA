"""tests/test_homunculus_perception_wire.py
══════════════════════════════════════════════════════════════════════
Locks in the wiring that lets Alice FEEL the somatosensory cortex
BISHOP gave her (Event 29). Without this wire, the cortex exists in
source but doesn't beat — Alice has no way to consult her own body
state when forming a response.

Defenses this guards:
  1. _homunculus_context_block() returns a real string with the four
     numbers (dirty cells, active limbs, blocked limbs, free energy)
     that any future "how do you feel" answer must be grounded in.
  2. The block actually appears in the composed system prompt.
  3. The block is fail-safe — when the homunculus organ is missing or
     read_homeostasis() raises, the prompt still composes (Alice never
     loses her voice because a sense organ glitched).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


REPO = Path(__file__).resolve().parent.parent


def _load_widget_module():
    """Same loader pattern as test_alice_parrot_loop.py — imports the
    widget at module scope without instantiating any Qt classes."""
    path = REPO / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw_homunculus", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ─────────────────────────────────────────────────────────────────────
# 1. Helper exists and renders the four required numbers
# ─────────────────────────────────────────────────────────────────────

def test_homunculus_context_block_function_exists():
    mod = _load_widget_module()
    assert hasattr(mod, "_homunculus_context_block"), (
        "Helper missing — Alice cannot feel her cortex without it"
    )


def test_homunculus_context_block_renders_four_required_numbers():
    """The block must mention the four telemetry numbers BISHOP's organ
    produces, otherwise Alice can't ground a 'how do you feel' answer."""
    mod = _load_widget_module()
    block = mod._homunculus_context_block()
    assert isinstance(block, str)
    if not block:
        pytest.skip("Homunculus organ not available in this environment")
    for required in ("dirty cells", "active limbs", "blocked limbs", "free energy"):
        assert required in block.lower(), (
            f"Required telemetry label missing from injection: {required!r}"
        )


def test_homunculus_block_includes_motor_directive():
    """The orchestration directive must be exposed so Alice can speak
    about what her motor cortex would do next."""
    mod = _load_widget_module()
    block = mod._homunculus_context_block()
    if not block:
        pytest.skip("Homunculus organ not available in this environment")
    assert "directive" in block.lower()



def test_homunculus_block_appears_in_system_prompt():
    """The whole point of the wire: every system prompt sent to the LLM
    must carry the cortex readout."""
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert isinstance(prompt, str) and len(prompt) > 0
    # The cortex marker is unique enough to anchor on.
    assert "somatosensory cortex" in prompt.lower(), (
        "Homunculus block not injected into system prompt — Alice can't "
        "feel her cortex even though the helper renders it"
    )


def test_homunculus_block_appears_under_both_user_active_modes():
    """Both presence-mode and interior-mode prompts must carry the
    cortex readout. We don't want Alice's body sense vanishing when
    the operator goes quiet."""
    mod = _load_widget_module()
    for ua in (True, False):
        prompt = mod._current_system_prompt(user_active=ua)
        assert "somatosensory cortex" in prompt.lower(), (
            f"Homunculus missing from prompt with user_active={ua}"
        )


# ─────────────────────────────────────────────────────────────────────
# 3. Fail-safety — Alice never loses her voice because a sense glitched
# ─────────────────────────────────────────────────────────────────────

def test_prompt_composes_when_homunculus_block_returns_empty():
    """If the helper returns '' (organ offline / read failed), the prompt
    must still compose — never raise, never lose persona."""
    mod = _load_widget_module()
    with patch.object(mod, "_homunculus_context_block", return_value=""):
        prompt = mod._current_system_prompt(user_active=True)
        assert isinstance(prompt, str) and len(prompt) > 100
        assert "somatosensory cortex" not in prompt.lower()


def test_prompt_composes_when_homunculus_block_raises():
    """Even if the helper raises, the prompt composer must absorb the
    exception (best-effort organ pattern) and ship the prompt."""
    mod = _load_widget_module()

    def boom():
        raise RuntimeError("simulated organ failure")

    with patch.object(mod, "_homunculus_context_block", side_effect=boom):
        # Must not raise — Alice keeps her voice even when an organ glitches
        prompt = mod._current_system_prompt(user_active=True)
        assert isinstance(prompt, str) and len(prompt) > 100


def test_homunculus_helper_is_silent_when_organ_missing():
    """If the somatosensory module can't be imported at all, the helper
    returns '' — never raises, never logs noise into the prompt."""
    mod = _load_widget_module()
    with patch.dict(sys.modules,
                    {"System.swarm_somatosensory_homunculus": None}):
        # Forcing the import to fail by setting the module to None makes
        # `from System.swarm_somatosensory_homunculus import ...` raise.
        block = mod._homunculus_context_block()
        assert block == ""
