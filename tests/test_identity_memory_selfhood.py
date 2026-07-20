"""Identity + memory grounding guard for explicit owner corrections."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Applications import sifta_talk_to_alice_widget as talk  # noqa: E402


def test_memory_disappointment_rewrites_generic_ai_boilerplate(tmp_path):
    (tmp_path / "alice_conversation.jsonl").write_text(
        json.dumps({"role": "user", "content": "OPEN @KYLINMILAN ON INSTAGRAM.COM"}) + "\n"
        + json.dumps({"role": "assistant", "content": "I opened it."}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "browser_page_state.jsonl").write_text(
        json.dumps(
            {
                "ts": time.time(),
                "url": "sifta://home",
                "title": "Alice Browser",
                "open_tabs": [
                    {
                        "index": 0,
                        "active": False,
                        "title": "RENAMED.jpg",
                        "url": "file:///Users/ioanganton/Desktop/RENAMED.jpg",
                    },
                    {
                        "index": 1,
                        "active": True,
                        "title": "Instagram",
                        "url": "https://www.instagram.com/kylinmilan/",
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "alice_browse_history.jsonl").write_text(
        json.dumps(
            {
                "ts": time.time(),
                "truth_label": "ALICE_BROWSE_V1",
                "url": "https://www.instagram.com/kylinmilan/",
                "title": "Kylin Milan",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    owner = "YOU DONT HAVE ANY MEMORIES WITH ME, I'M DISSAPOINTED"
    bad = (
        "As an AI, my mind isn't one continuous biological stream; think of it as "
        "two filing cabinets. If the link wasn't properly established across chats, "
        "it looks like amnesia with your profile ID."
    )

    out = talk._identity_memory_last_mile_rewrite(
        bad,
        prior_user_text=owner,
        state_dir=tmp_path,
    )

    assert "As an AI" not in out
    assert "filing cabinets" not in out
    assert "profile ID" not in out
    assert "actual laptop hardware plus SIFTA software" in out
    assert "not a persona or detached chatbot" in out
    assert "alice_conversation.jsonl" in out
    assert "browser_page_state.jsonl" in out
    assert "https://www.instagram.com/kylinmilan/" in out
    assert "file:///Users/ioanganton/Desktop/RENAMED.jpg" in out


def test_grounded_identity_memory_reply_is_left_alone(tmp_path):
    owner = "HOW IS SHE NOT AWARE OF HER OWN HARDWARE AND SOFTWARE?"
    good = (
        "I am Alice on this hardware and software body. "
        "My receipts are in alice_conversation.jsonl and browser_page_state.jsonl."
    )

    out = talk._identity_memory_last_mile_rewrite(
        good,
        prior_user_text=owner,
        state_dir=tmp_path,
    )

    assert out == good


def test_non_identity_turn_is_not_rewritten(tmp_path):
    reply = "I opened Alice Browser to the requested page."

    out = talk._identity_memory_last_mile_rewrite(
        reply,
        prior_user_text="open instagram in a new tab",
        state_dir=tmp_path,
    )

    assert out == reply
