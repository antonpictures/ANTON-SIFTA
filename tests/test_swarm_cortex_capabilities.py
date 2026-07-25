from __future__ import annotations

import json


def test_selects_local_native_vision_cortex(monkeypatch, tmp_path):
    from System import swarm_cortex_capabilities as cap

    monkeypatch.setattr(cap, "_ollama_tags", lambda: ["deepseek-v3:latest", "llava:latest"])
    monkeypatch.setattr(cap, "list_available_cortexes_with_canonical_fallback", lambda: ["grok:grok-4.3"])

    row = cap.select_cortex_for_need(
        "image_pixels",
        current_model="deepseek-v3:latest",
        query_text="describe this screenshot",
        state_dir=tmp_path,
        write=True,
    )

    assert row["selected_model"] == "llava:latest"
    assert row["reason"] == "selected_native_image_payload_cortex"
    assert row["switched"] is True
    ledger = tmp_path / "cortex_need_switches.jsonl"
    assert ledger.exists()
    assert json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])["selected_model"] == "llava:latest"


def test_selects_kimi_path_prompt_when_no_native_vision(monkeypatch, tmp_path):
    from System import swarm_cortex_capabilities as cap

    monkeypatch.setattr(cap, "_ollama_tags", lambda: ["deepseek-v3:latest"])
    monkeypatch.setattr(
        cap,
        "list_available_cortexes_with_canonical_fallback",
        lambda: ["grok:grok-4.3", cap.CANONICAL_CLOUD_QWEN_PREMIUM_KIMI],
    )

    row = cap.select_cortex_for_need(
        "image_pixels",
        current_model="deepseek-v3:latest",
        state_dir=tmp_path,
        write=False,
    )

    assert row["selected_model"] == cap.CANONICAL_CLOUD_QWEN_PREMIUM_KIMI
    assert row["reason"] == "selected_vision_cortex_path_prompt"


def test_keeps_current_vision_cortex(monkeypatch, tmp_path):
    from System import swarm_cortex_capabilities as cap

    monkeypatch.setattr(cap, "_ollama_tags", lambda: ["llava:latest"])
    monkeypatch.setattr(cap, "list_available_cortexes_with_canonical_fallback", lambda: [])

    row = cap.select_cortex_for_need(
        "image_pixels",
        current_model="gemini:gemini-2.5-flash",
        state_dir=tmp_path,
        write=False,
    )

    assert row["selected_model"] == "gemini:gemini-2.5-flash"
    assert row["reason"] == "current_model_kept"
    assert row["switched"] is False
    assert cap.is_vision_capable_model("gemini:gemini-2.5-flash", require_native_image_payload=True)


def test_keeps_selected_grok_as_speaking_cortex_for_vision(monkeypatch, tmp_path):
    from System import swarm_cortex_capabilities as cap

    monkeypatch.setattr(
        cap,
        "_ollama_tags",
        lambda: ["igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest"],
    )
    monkeypatch.setattr(cap, "list_available_cortexes_with_canonical_fallback", lambda: [])

    row = cap.select_cortex_for_need(
        "image_pixels",
        current_model="grok:grok-4.3",
        query_text="look at the screen",
        state_dir=tmp_path,
        write=False,
    )

    assert row["selected_model"] == "grok:grok-4.3"
    assert row["reason"] == "current_owner_selected_cloud_speaker_kept"
    assert row["switched"] is False


def test_keeps_selected_mimo_as_speaking_cortex_for_vision(monkeypatch, tmp_path):
    from System import swarm_cortex_capabilities as cap

    monkeypatch.setattr(
        cap,
        "_ollama_tags",
        lambda: ["igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest"],
    )
    monkeypatch.setattr(cap, "list_available_cortexes_with_canonical_fallback", lambda: [])

    row = cap.select_cortex_for_need(
        "image_pixels",
        current_model="mimo:mimo-cli-default",
        query_text="use the camera receipt but answer with mimo",
        state_dir=tmp_path,
        write=False,
    )

    assert row["selected_model"] == "mimo:mimo-cli-default"
    assert row["reason"] == "current_owner_selected_cloud_speaker_kept"
    assert row["switched"] is False


def test_mimo_with_text_only_attached_model_routes_image_to_smallest_native_eye(
    monkeypatch, tmp_path
):
    from System import swarm_cortex_capabilities as cap

    large_eye = "vendor/gemma-4-26b-vision:latest"
    small_eye = "vendor/gemma-4-6b-vision:latest"
    text_only = "baytout3/Ornith-1.0-9B-uncensored-GGUF:Q8_0"
    monkeypatch.setattr(cap, "_ollama_tags", lambda: [large_eye, text_only, small_eye])
    monkeypatch.setattr(cap, "list_available_cortexes_with_canonical_fallback", lambda: [])
    monkeypatch.setattr(cap, "active_attached_model_for_cortex", lambda *args, **kwargs: text_only)

    from System import sifta_inference_defaults as defaults

    monkeypatch.setattr(
        defaults,
        "probe_installed_ollama_inventory",
        lambda: (
            {"name": large_eye, "size_bytes": 26_000_000_000},
            {"name": text_only, "size_bytes": 9_000_000_000},
            {"name": small_eye, "size_bytes": 6_000_000_000},
        ),
    )

    row = cap.select_cortex_for_need(
        "image_pixels",
        current_model="mimo:mimo-cli-default",
        query_text="/sx",
        state_dir=tmp_path,
        write=False,
    )

    assert row["selected_model"] == small_eye
    assert row["reason"] == "mimo_attached_text_only_selected_native_image_cortex"
    assert row["attached_model"] == text_only
    assert row["attached_native_image_payload"] is False
    assert row["switched"] is True


def test_alice_m5_cortex_is_native_multimodal_after_ollama_show_receipt():
    from System import swarm_cortex_capabilities as cap

    model = "alice-m5-cortex-8b-6.3gb:latest"
    assert cap.is_vision_capable_model(model) is True
    assert cap.is_vision_capable_model(model, require_native_image_payload=True) is True
