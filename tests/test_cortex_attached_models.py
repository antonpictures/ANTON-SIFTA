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
    assert cap.format_attached_model("krishairnd/Gemma-4-Uncensored:latest") == (
        "krisha-g4u (local Ollama) (krishairnd/Gemma-4-Uncensored:latest)"
    )
    qwenpaw = cap._MIMO_LOCAL_QWENPAW_9B
    assert cap.format_attached_model(qwenpaw) == (
        f"QwenPaw 9B heretic 1M (local Ollama) ({qwenpaw})"
    )
    assert cap.format_attached_model(cap.FIREWORKS_KIMI_K2P6_MODEL) == (
        "Kimi K2.6 (fireworks-api kimi-k2p6) (accounts/fireworks/models/kimi-k2p6)"
    )
    assert "QwenPaw" in cap.format_attached_model(qwenpaw)


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
    assert codex.get("default_attached") == "GPT-5.3-Codex-Spark"
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
    # Owner 2026-06-25: local MiMo picker reflects current kept local bodies.
    assert rec.get("default_attached") == cap._MIMO_DEFAULT_ATTACHED
    assert rec.get("live") is True
    models = rec.get("attached_models") or []
    # 2026-07-11: locals from live ollama inventory + cloud keeps (no deleted 26B/diffusion).
    assert "mimo-auto" in models
    assert "accounts/fireworks/models/kimi-k2p6" in models
    assert "krishairnd/Gemma-4-Uncensored:latest" in models
    assert "ornith:latest" in models
    assert "satgeze/qwenpaw-9b-heretic-1m:latest" in models or any(
        "qwenpaw" in str(m) for m in models
    )
    assert cap._MIMO_LOCAL_GEMMA26_OLLAMA not in models
    assert "diffusion:diffusiongemma-26b" not in models
    for removed in (
        "mimo-v2.5-pro",
        "mimo-v2-flash",
        "mimo-v2-omni",
        "mimo-v2-pro",
        "mimo-v2.5",
    ):
        assert removed not in models
    assert rec.get("routes_any_provider") is True
    assert rec.get("picker_is_upstream") is True


def test_sync_catalog_mimo_fallback_defaults_to_dialogue_local(tmp_path, monkeypatch):
    from System import swarm_cline_settings_probe as probe

    monkeypatch.setattr(probe, "probe_external_brain", lambda lane, **kwargs: {
        "status": "no_config_found",
        "provider": "",
        "model": "",
    })

    cap.sync_cortex_attached_models_catalog(state_dir=tmp_path)
    rec = cap.attached_models_for_cortex("mimo:mimo-cli-default", state_dir=tmp_path)

    # r1560: No prior binding -> default is the smallest known runnable dialogue local model.
    assert rec.get("default_attached") == cap._MIMO_DEFAULT_ATTACHED
    assert "mimo-v2.5-pro" not in (rec.get("attached_models") or [])


def test_sync_catalog_resets_removed_mimo_v25_pro_default(tmp_path, monkeypatch):
    from System import swarm_cline_settings_probe as probe

    cap.record_attached_models(
        "mimo:mimo-cli-default",
        [
            "mimo-v2.5-pro",
            "mimo-auto",
            "krishairnd/Gemma-4-Uncensored:latest",
        ],
        default_attached="mimo-v2.5-pro",
        source="stale_mimo_v25_binding",
        state_dir=tmp_path,
    )
    monkeypatch.setattr(probe, "probe_external_brain", lambda lane, **kwargs: {
        "status": "no_config_found",
        "provider": "",
        "model": "",
    })

    cap.sync_cortex_attached_models_catalog(state_dir=tmp_path)
    rec = cap.attached_models_for_cortex("mimo:mimo-cli-default", state_dir=tmp_path)

    # r1244/r1560: paid MiMo cloud ids pruned; stale defaults reset to dialogue local.
    assert rec.get("default_attached") == cap._MIMO_DEFAULT_ATTACHED
    assert "mimo-v2.5-pro" not in (rec.get("attached_models") or [])


def test_sanitize_migrates_deleted_qwen35_tag_to_qwenpaw(tmp_path):
    legacy = "trinhnv1205/Qwen3.5-9B-Uncensored-ctx64k:latest"
    cap.record_attached_models(
        "mimo:mimo-cli-default",
        ["mimo-auto", legacy, "krishairnd/Gemma-4-Uncensored:latest"],
        default_attached=legacy,
        source="owner_deleted_qwen35",
        state_dir=tmp_path,
    )
    rec = cap.attached_models_for_cortex("mimo:mimo-cli-default", state_dir=tmp_path)
    assert legacy not in (rec.get("attached_models") or [])
    assert cap._MIMO_LOCAL_QWENPAW_9B in (rec.get("attached_models") or [])
    assert rec.get("default_attached") == cap._MIMO_LOCAL_QWENPAW_9B


def test_attached_models_for_cortex_sanitizes_non_dialogue_mimo_default_on_read(tmp_path):
    cap.record_attached_models(
        "mimo:mimo-cli-default",
        ["mimo-auto", "krishairnd/Gemma-4-Uncensored:latest", cap._MIMO_LOCAL_QWEN35_MT],
        default_attached=cap._MIMO_LOCAL_QWEN35_MT,
        source="stale_translation_default",
        state_dir=tmp_path,
    )
    rec = cap.attached_models_for_cortex("mimo:mimo-cli-default", state_dir=tmp_path)
    assert rec.get("default_attached") == cap._MIMO_DEFAULT_ATTACHED
    assert rec.get("source") == "owner_pruned_removed_mimo_v25_pro_default_2026-06-17"


def test_attached_models_for_cortex_sanitizes_diffusion_mimo_default_on_read(tmp_path):
    # 2026-07-11: diffusiongemma deleted from desk — not on MiMo attach list.
    # Stale default is pruned via REMOVED path (same as paid MiMo cloud ids).
    diffusion = "diffusion:diffusiongemma-26b"
    cap.record_attached_models(
        "mimo:mimo-cli-default",
        ["mimo-auto", "krishairnd/Gemma-4-Uncensored:latest", diffusion],
        default_attached=diffusion,
        source="stale_diffusion_default",
        state_dir=tmp_path,
    )

    rec = cap.attached_models_for_cortex("mimo:mimo-cli-default", state_dir=tmp_path)

    assert diffusion not in (rec.get("attached_models") or [])
    assert rec.get("default_attached") == cap._MIMO_DEFAULT_ATTACHED
    assert rec.get("source") == "owner_pruned_removed_mimo_v25_pro_default_2026-06-17"
    # Still marked non-dialogue if someone tries to bind it elsewhere.
    assert cap.is_mimo_non_dialogue_attached_default(diffusion)


def test_settings_refuses_diffusion_mimo_attached_default(tmp_path):
    # Diffusion is not on the attach list — refuse as not_in_attached_list.
    diffusion = "diffusion:diffusiongemma-26b"
    cap.record_attached_models(
        "mimo:mimo-cli-default",
        ["mimo-auto", "krishairnd/Gemma-4-Uncensored:latest"],
        default_attached="mimo-auto",
        source="settings_test_seed",
        state_dir=tmp_path,
    )

    receipt = cap.persist_attached_llm_default(
        "mimo:mimo-cli-default",
        diffusion,
        state_dir=tmp_path,
        owner_text="settings test",
    )

    assert receipt["ok"] is False
    assert receipt["reason"] == "not_in_attached_list"
    rec = cap.attached_models_for_cortex("mimo:mimo-cli-default", state_dir=tmp_path)
    assert rec.get("default_attached") == "mimo-auto"


def test_attached_models_for_cortex_sanitizes_stale_mimo_default_on_read(tmp_path):
    cap.record_attached_models(
        "mimo:mimo-cli-default",
        ["mimo-auto", "krishairnd/Gemma-4-Uncensored:latest"],
        default_attached="mimo-v2.5-pro",
        source="stale_binding",
        state_dir=tmp_path,
    )
    rec = cap.attached_models_for_cortex("mimo:mimo-cli-default", state_dir=tmp_path)
    # r1244/r1560: stale removed default sanitized on read -> dialogue local model
    assert rec.get("default_attached") == cap._MIMO_DEFAULT_ATTACHED


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
