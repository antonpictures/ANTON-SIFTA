"""r1621-04 — multimodal fail-fast / VLM route."""
from __future__ import annotations

from System.swarm_multimodal_timeout_route import (
    first_token_patience_for_multimodal,
    is_risky_multimodal_text_mind,
    route_multimodal_turn,
)


def test_name_heuristics_are_risky_when_capabilities_are_unknown(monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_capabilities._ollama_capabilities",
        lambda _model: None,
    )
    assert is_risky_multimodal_text_mind("krishairnd/Gemma-4-Uncensored:latest")
    assert is_risky_multimodal_text_mind("satgeze/qwenpaw-9b-heretic-1m:latest")
    assert is_risky_multimodal_text_mind("ornith:latest")


def test_metadata_overrides_risky_name(monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_capabilities._ollama_capabilities",
        lambda _model: frozenset({"completion", "vision"}),
    )
    assert not is_risky_multimodal_text_mind("krishairnd/Gemma-4-Uncensored:latest")


def test_metadata_can_mark_vision_named_model_text_only(monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_capabilities._ollama_capabilities",
        lambda _model: frozenset({"completion"}),
    )
    assert is_risky_multimodal_text_mind("minicpm-v-4_5-abliterated:latest")


def test_patience_short_on_image_risky_mind(monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_capabilities._ollama_capabilities",
        lambda _model: None,
    )
    p = first_token_patience_for_multimodal(
        "krishairnd/Gemma-4-Uncensored:latest",
        has_image=True,
        base_s=90.0,
    )
    assert p["fail_fast"] is True
    assert p["patience_s"] <= 18.0


def test_route_fail_fast_without_vlm(monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_capabilities._ollama_capabilities",
        lambda _model: None,
    )
    r = route_multimodal_turn(
        "krishairnd/Gemma-4-Uncensored:latest",
        has_image=True,
        available_vlms=[],
    )
    assert r["action"] in {"fail_fast_text_only", "redirect_vlm"}
    if r["action"] == "fail_fast_text_only":
        assert "owner_line" in r
        assert r["patience"]["patience_s"] <= 18.0


def test_no_image_keeps_model():
    r = route_multimodal_turn("ornith:latest", has_image=False)
    assert r["action"] == "keep"
