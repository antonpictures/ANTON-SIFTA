"""tests/test_browser_turn_intent_context.py — r986 nothing-pre-cortex doctrine.

The Dean Radin incident (George, 2026-06-11 ~14:00): "select Dean Radin,
let's listen and watch that" — the tile was ON Alice's screen, but a
pre-cortex recall reflex picked an old video (HlINKoGwoEk) from stale
search terms and answered for her. ARCHITECT_DOCTRINE: "NOTHING IS
DETERMINISTIC IN SIFTA — EVERYTHING goes to cortex; she is the observer
and the observed." These tests prove the reflex findings now ride INTO
the cortex turn instead of deciding it.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from System.swarm_browser_context import (  # noqa: E402
    browser_turn_intent_context,
    owner_youtube_recall_open_fast_reply,
)
from System.swarm_browser_page_state import record_page_state  # noqa: E402

_DEAN_URL = "https://www.youtube.com/watch?v=DeanRadin2513"
_ROGAN_URL = "https://www.youtube.com/watch?v=4Uk0_1yqdJo"
_STALE_RECALL_URL = "https://www.youtube.com/watch?v=HlINKoGwoEk"


def _seed_screen(state: Path) -> None:
    """Seed the page-state ledger with what was on her screen: YouTube home,
    Dean Radin tile among others (position irrelevant — text is the key)."""
    record_page_state(
        url="https://www.youtube.com/",
        title="YouTube",
        source="dom",
        links=[
            {"text": "The AI cash burn is about to pop", "href": "https://www.youtube.com/watch?v=cashburn"},
            {"text": "Joe Rogan Experience #2513 - Dean Radin", "href": _DEAN_URL},
            {"text": "Netanyahu says Israel 'not a party'", "href": "https://www.youtube.com/watch?v=nbcnews1"},
        ],
        state_dir=state,
    )


def test_select_dean_radin_reaches_cortex_with_screen_links(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    _seed_screen(state)
    block = browser_turn_intent_context(
        "select Dean Radin, let's listen and watch that", state_dir=state
    )
    assert block, "watch intent must produce a cortex context block"
    assert "I decide in cortex" in block
    assert "Joe Rogan Experience #2513 - Dean Radin" in block
    assert _DEAN_URL in block                      # the href she can act on
    assert "match by text" in block                # never by remembered layout


def test_owner_pasted_url_is_named_as_the_target(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    block = browser_turn_intent_context(
        f"you can not open the podcast joe rogan on screen? {_ROGAN_URL} you can not read?",
        state_dir=state,
    )
    assert "OWNER-GIVEN TARGET" in block
    assert _ROGAN_URL in block
    assert "must never override" in block
    # recall candidates are suppressed when he gave the target himself
    assert "RECALL CANDIDATES" not in block


def test_recall_reflex_no_longer_decides_when_owner_gave_url(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    # seed a stale browse receipt that used to win
    with (state / "alice_browse_history.jsonl").open("w") as f:
        f.write(json.dumps({
            "ts": time.time() - 86400,
            "url": _STALE_RECALL_URL,
            "title": "Got was depressed and he told him the same photos",
        }) + "\n")
    res = owner_youtube_recall_open_fast_reply(
        f"open the podcast joe rogan {_ROGAN_URL}", state_dir=state
    )
    assert res == {}, "recall lane must yield when the owner pasted an explicit URL"


def test_no_browser_intent_means_empty_block(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    assert browser_turn_intent_context("how are you feeling today?", state_dir=state) == ""


def test_page_state_block_carries_hrefs(tmp_path):
    from System.swarm_browser_page_state import page_state_block

    state = tmp_path / "state"
    state.mkdir()
    _seed_screen(state)
    block = page_state_block(state_dir=state)
    assert "Joe Rogan Experience #2513 - Dean Radin" in block
    assert _DEAN_URL in block
