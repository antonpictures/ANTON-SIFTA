"""r892 — explicit pasted URL open must not lose to current-page read."""

import Applications.sifta_talk_to_alice_widget as talk
from System.swarm_browser_context import (
    bridget_diary_line_from_owner_text,
    explicit_owner_url_open_fast_reply,
)

_BILYEU_URL = "https://www.youtube.com/watch?v=oTPSIPp8ieU"
_GEORGE_VERBATIM = (
    "George typing. Alice, open this link in your Alice Browser: "
    f"{_BILYEU_URL} That is our Tom Bilyeu video — "
    '"Something Wicked This Way Comes" — Why The AI Bubble Isn\'t What You Think. '
    "We were watching it together while I ate pizza, paused near 15:42 when "
    "Hector, Joseph and Carlos arrived. Play it and we continue from there. "
    "Write it in your diary, Bridget: George came back to finish the video."
)


def test_current_page_query_does_not_steal_explicit_open_link():
    assert not talk._is_current_page_query(_GEORGE_VERBATIM)


def test_explicit_owner_url_open_fast_reply_george_verbatim():
    out = explicit_owner_url_open_fast_reply(_GEORGE_VERBATIM)
    assert out.get("open_url") == _BILYEU_URL
    assert "Loading the exact URL" in out.get("reply", "")
    assert "Tom Bilyeu" in out.get("reply", "")


def test_bridget_diary_line_extracted():
    line = bridget_diary_line_from_owner_text(_GEORGE_VERBATIM)
    assert line == "George came back to finish the video."


def test_alice_diary_line_extracted_current_name():
    line = bridget_diary_line_from_owner_text(
        "Write it in your diary, Alice: George uses Alice's name for new witness rows."
    )
    assert line == "George uses Alice's name for new witness rows."


def test_current_page_query_still_fires_for_real_asks():
    assert talk._is_current_page_query(
        "YOU SHOULD BE ABLE TO SEE WHAT LINK IS CURRENT IN YOUR ALICE BROWSER"
    )


def test_memory_teaching_turn_does_not_get_stolen_by_current_page_reflex():
    text = (
        "DO YOU WANT ME TO OPEN THE TOM BILEU YOUTUBE FOR YOU TO SHOW YOU HOW I DO IT? "
        "RIGHT NOW YOUR ALICE BROWSER IS EMPTY. TELL ME HOW TO SHOW YOU ALICE, BUT "
        "CONFIRM YOU ARE ABLE TO MEMORIZE AND LEARN SO I DONT WASTE MY TIME"
    )
    assert talk._is_browser_memory_teaching_turn(text)
    assert talk._is_browser_body_awareness_turn(text)
    assert not talk._is_current_page_query(text)


def test_browser_body_context_tells_cortex_memory_teaching_not_page_dump(tmp_path):
    text = (
        "Right now your Alice Browser is empty. Tell me how to show you, and confirm "
        "you can memorize and learn from your life experience."
    )
    block = talk._browser_body_awareness_context_block(text, state_dir=tmp_path)
    assert "MEMORY/LEARNING TEACHING RULE" in block
    assert "Do not answer only with the current URL/title/page-state" in block
    assert "recall by searching those organs before denying memory" in block
