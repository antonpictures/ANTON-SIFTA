#!/usr/bin/env python3
"""Tests for the cortex attached-models capability field (George 2026-05-30)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_cortex_capabilities as cap


CLINE = "cline:cline-cli-default"
SCREENSHOT = ["GPT-5.5", "GPT-5.4", "GPT-5.4-Mini", "GPT-5.3-Codex", "GPT-5.3-Codex-Spark", "GPT-5.2"]


def test_record_and_read_roundtrip(tmp_path):
    cap.record_attached_models(
        CLINE, SCREENSHOT,
        default_attached="GPT-5.5", source="owner_screenshot_test",
        routes_any_provider=True, picker_is_upstream=True, state_dir=tmp_path,
    )
    rec = cap.attached_models_for_cortex(CLINE, state_dir=tmp_path)
    assert rec["attached_models"] == SCREENSHOT
    assert rec["default_attached"] == "GPT-5.5"
    assert rec["routes_any_provider"] is True
    assert rec["picker_is_upstream"] is True
    assert rec["live"] is False  # snapshot, not a live config read


def test_unknown_cortex_returns_empty(tmp_path):
    assert cap.attached_models_for_cortex("grok:grok-4.3", state_dir=tmp_path) == {}


def test_record_is_non_destructive(tmp_path):
    cap.record_attached_models(CLINE, SCREENSHOT, state_dir=tmp_path)
    cap.record_attached_models("codex:gpt-5.5", ["GPT-5.5"], state_dir=tmp_path)
    # First cortex survives the second write.
    assert cap.attached_models_for_cortex(CLINE, state_dir=tmp_path)["attached_models"] == SCREENSHOT
    assert cap.attached_models_for_cortex("codex:gpt-5.5", state_dir=tmp_path)["attached_models"] == ["GPT-5.5"]


def test_default_falls_back_to_first_model(tmp_path):
    cap.record_attached_models(CLINE, SCREENSHOT, state_dir=tmp_path)  # no explicit default
    assert cap.attached_models_for_cortex(CLINE, state_dir=tmp_path)["default_attached"] == "GPT-5.5"


def test_prompt_block_lists_models(tmp_path):
    cap.record_attached_models(CLINE, SCREENSHOT, source="owner_screenshot_test", state_dir=tmp_path)
    block = cap.prompt_block_for_attached(CLINE, state_dir=tmp_path)
    assert "GPT-5.5" in block and "GPT-5.2" in block
    assert "last observed" in block  # snapshot provenance, not claimed live


def test_prompt_block_empty_for_unknown(tmp_path):
    assert cap.prompt_block_for_attached("grok:grok-4.3", state_dir=tmp_path) == ""


def test_live_flag_changes_provenance(tmp_path):
    cap.record_attached_models(CLINE, SCREENSHOT, live=True, state_dir=tmp_path)
    block = cap.prompt_block_for_attached(CLINE, state_dir=tmp_path)
    assert "live config read" in block


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
