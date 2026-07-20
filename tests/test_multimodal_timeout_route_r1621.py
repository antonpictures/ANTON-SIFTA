"""r1621-04 — multimodal fail-fast / VLM route."""
from __future__ import annotations

from System.swarm_multimodal_timeout_route import (
    first_token_patience_for_multimodal,
    is_risky_multimodal_text_mind,
    route_multimodal_turn,
)


def test_krisha_and_qwenpaw_are_risky_for_multimodal():
    assert is_risky_multimodal_text_mind("krishairnd/Gemma-4-Uncensored:latest")
    assert is_risky_multimodal_text_mind("satgeze/qwenpaw-9b-heretic-1m:latest")
    assert is_risky_multimodal_text_mind("ornith:latest")


def test_patience_short_on_image_risky_mind():
    p = first_token_patience_for_multimodal(
        "krishairnd/Gemma-4-Uncensored:latest",
        has_image=True,
        base_s=90.0,
    )
    assert p["fail_fast"] is True
    assert p["patience_s"] <= 18.0


def test_route_fail_fast_without_vlm():
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
