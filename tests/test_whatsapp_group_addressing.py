#!/usr/bin/env python3
"""Group addressing — when Alice answers in a group, and when she stays out.

The Architect, 2026-10-05, holding up a screenshot of group 199: "I took a screenshot from my
iPhone SE on whatsapp group 199 so I can show you the fact that your answer is missing. If you
are mentioned in a group, your WhatsApp name, you are suppose to answer. Or if anyone mentioned
Alice, the word :)"

The screenshot, read with the local eye, showed his message: "...sǎ o învǎțat pe **@Alice
GTH4921YP3** ca o las singura acasa ca sa dau o tura in jurul lacului..." — tagged, and answered
with silence.

The gate looked for " alice": a space followed by the letters. A WhatsApp mention is rendered
"@Alice", so the space sits BEFORE the "@" and every key missed. The gate was right to stay out
of other people's conversation and wrong to stay out of a direct mention, and the two are tested
together here so a fix for one cannot quietly break the other.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _lane():
    """Load the answer lane without importing the whole package tree."""
    path = REPO / "System" / "swarm_whatsapp_answer_lane.py"
    spec = importlib.util.spec_from_file_location("answer_lane_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GROUP = "120363045641065911@g.us"


def _addressed(text: str) -> bool:
    """Mirror of the lane's group branch, so the rule can be tested without a live row."""
    lane = _lane()
    low = " " + " ".join(text.casefold().split()) + " "
    if any(k in low for k in (" aluce", " alise", " alica", "@51235386302504")):
        return True
    return bool(lane._MENTION_ALICE.search(low))


@pytest.mark.parametrize(
    "text",
    [
        "Nu o sǎ vǎ vinǎ sǎ credeti ce greu e și sǎ o învǎțat pe @Alice GTH4921YP3 ca o las singura acasa",
        "intrebati-o pe Alice ce crede",
        "Alice, tu ce zici?",
        "o intrebam pe Alice?",
        "salut @Alice",
        "intreaba-l pe Alise",
        "scrie-i lui Aluce",
    ],
)
def test_being_addressed_is_recognised(text: str) -> None:
    """A mention of her name or account, in the forms he and his friends actually type."""
    assert _addressed(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Ce faci? Ne vedem maine la 10?",
        "Am dormit bușteanul.",
        "Georgică îmi e dor de blocu ala",
        "scrie la nume@alice.example",
        "alicexyz a zis ceva",
        "https://youtu.be/2n5xssjE_ls In curand in cinematografe.",
    ],
)
def test_other_peoples_conversation_is_left_alone(text: str) -> None:
    """The spam he forbade: classmates asking each other, links, and near-miss strings."""
    assert _addressed(text) is False


def test_the_literal_plain_key_no_longer_matches_a_word_that_merely_starts_with_it() -> None:
    """The old " alice" key had no word boundary; the pattern replaced it deliberately."""
    lane = _lane()
    assert " alice" not in (" aluce", " alise", " alica", "@51235386302504")
    assert lane._MENTION_ALICE.search(" alicexyz a zis ceva") is None
    assert lane._MENTION_ALICE.search(" alice a zis ceva") is not None


def test_an_email_address_is_not_a_mention() -> None:
    """A preceding letter, digit or "@" refuses the match, so a mail address is not addressing."""
    lane = _lane()
    assert lane._MENTION_ALICE.search(" nume@alice.example ") is None
    assert lane._MENTION_ALICE.search(" pe @alice ") is not None
