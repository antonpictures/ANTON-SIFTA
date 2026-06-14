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


def test_attached_model_labels_preserve_machine_ids():
    assert cap.format_attached_model("grok-composer-2.5-fast") == (
        "Composer 2.5 (grok-composer-2.5-fast)"
    )
    assert cap.format_attached_model("claude-haiku-4-5-20251001") == (
        "Haiku 4.5 (claude-haiku-4-5-20251001)"
    )
    assert cap.format_attached_model("openai-codex:gpt-5.4") == (
        "GPT-5.4 (openai-codex:gpt-5.4)"
    )
    assert cap.attached_model_matches_active("GPT-5.4", "openai-codex:gpt-5.4")


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


def test_sync_catalog_writes_cline_grok_codex_claude(tmp_path, monkeypatch):
    monkeypatch.setattr(cap, "_grok_cli_model_ids", lambda: ["grok-composer-2.5-fast", "grok-build"])
    out = cap.sync_cortex_attached_models_catalog(state_dir=tmp_path)
    assert "cline:cline-cli-default" in out.get("synced", [])
    cline = cap.attached_models_for_cortex(CLINE, state_dir=tmp_path)
    assert "GPT-5.4" in cline.get("attached_models", [])
    assert "grok-composer-2.5-fast" in cline.get("attached_models", [])
    assert "claude-fable-5" in cline.get("attached_models", [])
    assert "claude-opus-4-7" in cline.get("attached_models", [])
    grok = cap.attached_models_for_cortex("grok:grok-4.3", state_dir=tmp_path)
    assert "grok-build" in grok.get("attached_models", [])
    codex = cap.attached_models_for_cortex("codex:gpt-5.5", state_dir=tmp_path)
    assert codex.get("attached_models") == [
        "GPT-5.5",
        "GPT-5.4",
        "GPT-5.4-Mini",
        "GPT-5.3-Codex-Spark",
    ]
    claude = cap.attached_models_for_cortex("claude:claude-code-cli-default", state_dir=tmp_path)
    assert "claude-opus-3" in claude.get("attached_models", [])
    assert claude.get("default_attached") == "claude-opus-4-8"
    assert claude.get("default_label") == "Opus 4.8"
    assert claude.get("model_labels", {}).get("claude-haiku-4-5-20251001") == "Haiku 4.5"
    fireworks = cap.attached_models_for_cortex(
        "qwen:accounts/fireworks/models/kimi-k2p6",
        state_dir=tmp_path,
    )
    assert "accounts/fireworks/models/kimi-k2p7-code" in fireworks.get("attached_models", [])
    assert fireworks.get("model_labels", {}).get(
        "accounts/fireworks/models/kimi-k2p7-code"
    ) == "Kimi K2.7 Code"


def test_sync_catalog_includes_mimo(tmp_path, monkeypatch):
    # Mimic a configured MiMo lane so a live default is captured.
    home = tmp_path / "home"
    (home / ".mimo").mkdir(parents=True)
    (home / ".mimo" / "config.json").write_text(
        '{"provider": "fireworks", "model": "kimi-k2p6", "reasoningLevel": "high"}'
    )

    from System import swarm_cline_settings_probe as probe

    monkeypatch.setenv("HOME", str(home))

    # Make cline probing deterministic so this test only checks MIMO wiring.
    monkeypatch.setattr(probe, "probe_external_brain", lambda lane, **kwargs: (
        {"cline": {"status": "no_config_found", "model": "", "provider": ""}, "mimo": {
            "status": "ok", "provider": "fireworks", "model": "kimi-k2p6"
        }}[lane]
        if lane in {"cline", "mimo"}
        else {"status": "no_config_found", "provider": "", "model": ""}
    ))

    out = cap.sync_cortex_attached_models_catalog(state_dir=tmp_path)
    assert "mimo:mimo-cli-default" in out.get("synced", [])

    rec = cap.attached_models_for_cortex("mimo:mimo-cli-default", state_dir=tmp_path)
    assert rec.get("default_attached") == "fireworks:kimi-k2p6"
    models = rec.get("attached_models") or []
    assert models
    assert "mimo-v2.5-pro" in models
    assert "mimo-v2.5-pro-ultraspeed" in models
    assert "GPT-5.5" in models
    assert rec.get("routes_any_provider") is True
    assert rec.get("picker_is_upstream") is True


def test_sync_catalog_mimo_includes_cline_catalog_plus_native_models(tmp_path, monkeypatch):
    # If the shared OAuth catalog changes, MIMO must include it while keeping
    # its own native MiMo picker models visible.
    from System import swarm_cortex_capabilities as cap_module
    from System import swarm_cline_settings_probe as probe

    home = tmp_path / "home"
    (home / ".mimo").mkdir(parents=True)
    (home / ".mimo" / "config.json").write_text(
        '{"provider": "fireworks", "model": "kimi-k2p7-code", "reasoningLevel": "high"}'
    )
    (home / ".cline").mkdir(parents=True)
    (home / ".cline" / "settings.json").write_text(
        '{"provider": "openai-codex", "model": "gpt-5.4"}'
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(
        probe,
        "probe_external_brain",
        lambda lane, **kwargs: {
            "cline": {"status": "ok", "provider": "openai-codex", "model": "gpt-5.4"},
            "mimo": {"status": "ok", "provider": "fireworks", "model": "kimi-k2p7-code"},
        }[lane],
    )

    cap_module.sync_cortex_attached_models_catalog(state_dir=tmp_path)
    cline = cap_module.attached_models_for_cortex("cline:cline-cli-default", state_dir=tmp_path)
    mimo = cap_module.attached_models_for_cortex("mimo:mimo-cli-default", state_dir=tmp_path)
    cline_models = cline.get("attached_models") or []
    mimo_models = mimo.get("attached_models") or []
    assert set(cline_models).issubset(set(mimo_models))
    assert "mimo-v2.5-pro" in mimo_models
    assert "mimo-auto" in mimo_models
    assert "mimo-v2.5-pro" not in cline_models
    assert cline.get("routes_any_provider") is True
    assert mimo.get("routes_any_provider") is True
    assert mimo.get("default_attached") == "fireworks:kimi-k2p7-code"

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
