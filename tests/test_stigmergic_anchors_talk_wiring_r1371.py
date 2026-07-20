"""r1371 — Talk carries shared-experience anchors in the live cortex prompt."""
from __future__ import annotations

from pathlib import Path


def test_talk_prompt_wires_shared_experience_anchors() -> None:
    src = Path("Applications/sifta_talk_to_alice_widget.py").read_text(encoding="utf-8")
    assert "swarm_stigmergic_shared_experience_anchors" in src
    assert "scan_conversation_for_anchors" in src
    assert "shared_experience_anchors_prompt_block" in src
    assert "max_rows=300" in src

