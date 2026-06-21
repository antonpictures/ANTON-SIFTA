"""CUR-F8/F9 — Talk binds diffusion selection to generator; snapshot sync."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_talk_candidates_keep_diffusion_first_with_receipted_local_fallback():
    from Applications.sifta_talk_to_alice_widget import _talk_ollama_model_candidates

    ladder = _talk_ollama_model_candidates("diffusion:llada-8b")
    assert ladder[:3] == [
        "diffusion:llada-8b",
        "krishairnd/Gemma-4-Uncensored:latest",
        "alice-m5-cortex-8b-6.3gb:latest",
    ]


def test_talk_candidates_still_falls_back_for_local_ar_primary():
    from Applications.sifta_talk_to_alice_widget import _talk_ollama_model_candidates

    ladder = _talk_ollama_model_candidates("igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest")
    assert ladder[0] == "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest"
    assert "alice-m5-cortex-8b-6.3gb:latest" in ladder


def test_persist_active_cortex_snapshot_writes_json(tmp_path, monkeypatch):
    from System import swarm_primary_cortex_switcher as switcher

    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    monkeypatch.setattr(switcher, "_STATE", state)
    monkeypatch.setattr(switcher, "_PRIMARY_CORTEX_JSON", state / "primary_cortex.json")

    row = switcher.persist_active_cortex_snapshot(
        "diffusion:llada-8b",
        source="test",
    )
    assert row["model"] == "diffusion:llada-8b"
    assert row["provider"] == "local_diffusion"
    payload = json.loads((state / "primary_cortex.json").read_text(encoding="utf-8"))
    assert payload["model"] == "diffusion:llada-8b"
    assert payload["truth_label"] == "PRIMARY_CORTEX_SNAPSHOT_V1"


def test_diffusion_model_detection_available_from_gemini_brain():
    from System.swarm_gemini_brain import _is_diffusion_model

    assert _is_diffusion_model("diffusion:llada-8b")
    assert not _is_diffusion_model("alice-m5-cortex-8b-6.3gb:latest")
