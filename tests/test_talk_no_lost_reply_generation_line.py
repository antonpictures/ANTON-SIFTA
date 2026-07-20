from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TALK = REPO / "Applications" / "sifta_talk_to_alice_widget.py"


def test_banned_lost_reply_generation_line_not_in_talk_source() -> None:
    source = TALK.read_text(encoding="utf-8")
    old_lost_line = " ".join(
        [
            "I",
            "lost",
            "the",
            "reply",
            "generation.",
            "I",
            "will",
            "not",
            "claim",
            "screen-reading",
            "until",
            "a",
            "fresh",
            "receipt",
            "proves",
            "it.",
        ]
    )
    old_dead_line = " ".join(
        ["I", "hit", "a", "dead", "turn.", "Checking", "receipts", "before", "I", "answer."]
    )

    assert old_lost_line not in source
    assert old_dead_line not in source
