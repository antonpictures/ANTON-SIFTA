"""r1623-01 — local headroom diet shrinks fat prompts, keeps soul blocks."""
from __future__ import annotations

from System.swarm_headroom_context_diet import (
    diet_prompt_parts,
    is_local_ollama_mind,
)


def test_local_mind_detection():
    assert is_local_ollama_mind("ornith:latest")
    assert is_local_ollama_mind("satgeze/qwenpaw-9b-heretic-1m:latest")
    assert not is_local_ollama_mind("mimo:mimo-cli-default")
    assert not is_local_ollama_mind("claude:claude-code-cli-default")


def test_diet_protects_host_and_trims_fat():
    parts = [
        "HOST TEACHING (keep me): soul on disk",
        "BODY FROM RECEIPTS (keep me): limbs",
        "FAT EXCERPT " + ("word " * 4000),
        "ANOTHER FAT " + ("junk " * 3000),
    ]
    out, report = diet_prompt_parts(parts, model_id="ornith:latest")
    joined = "\n\n".join(out)
    assert "HOST TEACHING" in joined
    assert "BODY FROM RECEIPTS" in joined
    assert report.get("local_diet") is True
    assert report.get("final_chars_after_dedupe", report.get("final_chars", 0)) < sum(
        len(p) for p in parts
    )
