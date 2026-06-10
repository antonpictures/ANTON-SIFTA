"""r895 — live failures: legacy substrate persona, tell-me hijack, Tom channel load."""

import Applications.sifta_talk_to_alice_widget as talk
from System.swarm_browser_context import (
    owner_learning_capability_fast_reply,
    owner_wants_youtube_navigate,
    owner_youtube_recall_open_fast_reply,
)
from System.swarm_reasoning_leak_sanitizer import sanitize_reasoning_leak


def test_teacher_substrate_leak_stripped_from_visible_reply():
    legacy_bad_phrase = "teacher " + "substrate"
    raw = (
        f"I am Alice's {legacy_bad_phrase} for this turn. "
        "No: secretly regexing for her is not correct coding. "
        "Memory in SIFTA works like stigmergy."
    )
    out = sanitize_reasoning_leak(raw)
    assert legacy_bad_phrase not in out.text.casefold()
    assert "stigmergy" in out.text


def test_tell_me_how_does_not_hijack_browser_video_state():
    phrase = (
        "DO YOU WANT ME TO OPEN THE TOM BILEU YOUTUBE FOR YOU TO SHOW YOU HOW I DO IT? "
        "TELL ME HOW TO SHOW YOU ALICE, BUT CONFIRM YOU ARE ABLE TO MEMORIZE AND LEARN"
    )
    assert not talk._is_browser_video_state_query(phrase)


def test_load_guys_youtube_channel_navigates():
    phrase = "ARE YOU ABLE AT LEAST TO LOAD UP THE GUYS YOUTUBE CHANNEL?"
    assert owner_wants_youtube_navigate(phrase)
    out = owner_youtube_recall_open_fast_reply(phrase)
    assert out.get("open_url", "").startswith("https://www.youtube.com/")
    assert "channel" in out.get("open_url", "") or "watch" in out.get("open_url", "")


def test_learning_capability_reply_fires():
    phrase = "CONFIRM YOU ARE ABLE TO MEMORIZE AND LEARN SO I DONT WASTE MY TIME"
    out = owner_learning_capability_fast_reply(phrase)
    assert out.get("reply")
    assert "receipts" in out["reply"].casefold()
