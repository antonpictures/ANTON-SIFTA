"""Visible reply scrub for leaked tool-call theater (r1289)."""
from __future__ import annotations

from Applications import sifta_talk_to_alice_widget as talk


def test_describe_screen_tool_theater_is_not_owner_visible() -> None:
    raw = """TOOL_CALL(describe_screen) **Subject:** Instagram Profile Page - @KYLINMILAN
**Visual Scan Initiated...**

*(Processing image data from current viewport...)*

Based on what is currently displayed in the browser tab: this is an Instagram profile page.

withinitselfnothingelseexceptonlyeveragainrepeatedlyoverandoveragainthisverymomentrightnowherselfstandingtallproudconfidentbeautifulstrongresilientindependentcapablebraveboldfearlessunafraidnothingcanstopher"""

    cleaned = talk._strip_visible_tool_theater_and_word_salad(raw)

    assert "TOOL_CALL" not in cleaned
    assert "Subject:" not in cleaned
    assert "Visual Scan Initiated" not in cleaned
    assert "Processing image data" not in cleaned
    assert "withinitselfnothingelse" not in cleaned
    assert "Instagram profile page" in cleaned


def test_tool_theater_fallback_is_honest_when_everything_was_template() -> None:
    cleaned = talk._strip_visible_tool_theater_and_word_salad(
        "TOOL_CALL(describe_screen)\n**Visual Scan Initiated...**\n"
    )

    assert "internal tool-call/template text" in cleaned
    assert "fresh browser or vision receipt" in cleaned
