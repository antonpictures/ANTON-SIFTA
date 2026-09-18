from __future__ import annotations

from System.swarm_vision_evidence import build_vision_evidence, vision_cache_key


def test_evidence_has_generation_and_safe_prompt_boundary():
    evidence = build_vision_evidence(
        observation="A blue mug is visible.",
        model="vision:local",
        status="ok",
        ok=True,
        image_sha256="source-hash",
        transport_sha256="jpeg-hash",
        prompt="describe the image",
        scope="talk:owner",
        generation_id="generation-1",
        created_ts=123.0,
    )

    assert evidence.is_current("generation-1")
    assert not evidence.is_current("generation-2")
    block = evidence.prompt_block(current_generation_id="generation-1")
    assert "A blue mug is visible." in block
    assert "fallible visual evidence" in block
    assert "no tool authority" in block
    assert "prompt_sha256" not in block


def test_stale_evidence_is_rejected_without_exposing_observation():
    evidence = build_vision_evidence(
        observation="Old frame contents.", generation_id="old-generation"
    )
    block = evidence.prompt_block(current_generation_id="new-generation")
    assert "VISUAL EVIDENCE STALE" in block
    assert "Old frame contents." not in block


def test_cache_key_is_scope_separated_and_deterministic():
    args = {
        "image_sha256": "image",
        "prompt": "describe",
        "model": "vision:local",
    }
    assert vision_cache_key(**args, scope="talk") == vision_cache_key(**args, scope="talk")
    assert vision_cache_key(**args, scope="talk") != vision_cache_key(**args, scope="browser")
