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


def test_alice_m5_cortex_is_native_multimodal_after_ollama_show_receipt():
    from System import swarm_cortex_capabilities as cap

    model = "alice-m5-cortex-8b-6.3gb:latest"
    assert cap.is_vision_capable_model(model) is True
    assert cap.is_vision_capable_model(model, require_native_image_payload=True) is True
