"""r1384 — Phillipe saleability one-sentence reflex."""
from __future__ import annotations

import json
from pathlib import Path

from System.swarm_philippe_saleability_reflex import (
    TRUTH_LABEL,
    answer_philippe_saleability_question,
    is_philippe_saleability_question,
)


def test_philippe_saleability_question_returns_one_grounded_sentence(tmp_path: Path) -> None:
    text = "By Phillipe's bar — are we saleable today? One sentence, honest."
    assert is_philippe_saleability_question(text)

    reply = answer_philippe_saleability_question(text, state_dir=tmp_path)

    assert reply.count(".") == 1
    assert "Not yet as a saleable whole product" in reply
    assert "trust-receipt wedge demo exists" in reply
    assert "George believes the code is real" in reply
    assert "CrewAI/LangGraph benchmark row" in reply
    assert "PPO" not in reply
    assert "fiscal" not in reply.lower()

    rows = [
        json.loads(line)
        for line in (tmp_path / ".sifta_state" / "philippe_saleability_reflex.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert rows[-1]["truth_label"] == TRUTH_LABEL
    assert rows[-1]["reply"] == reply


def test_non_saleability_philippe_mentions_do_not_fire() -> None:
    assert not is_philippe_saleability_question("Who is Phillipe?")
    assert not answer_philippe_saleability_question("Tell me the Phillipe contact anchor.", write=False)


def test_talk_widget_wires_philippe_saleability_reflex() -> None:
    src = Path("Applications/sifta_talk_to_alice_widget.py").read_text(encoding="utf-8")
    assert "answer_philippe_saleability_question" in src
    assert "philippe_saleability_reflex" in src
