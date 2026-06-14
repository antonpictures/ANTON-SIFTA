"""r874 P0-B page-summary suppression guards."""

from System.swarm_talk_page_summary_guard import (
    should_suppress_browser_video_state_query,
    should_suppress_page_summary,
)


def test_suppress_close_tab_request():
    suppress, reason = should_suppress_page_summary(
        "close the two duplicate fly.io tabs now and keep the YouTube tab"
    )
    assert suppress is True
    assert reason == "effector_only_close_tab"


def test_suppress_self_screenshot_observation_only():
    suppress, reason = should_suppress_page_summary(
        "SELF-SCREENSHOT CORTEX TURN (/sc): identify my SIFTA OS body from the attached frame"
    )
    assert suppress is True
    assert reason == "self_screenshot_observation_only"


def test_suppress_cowatch_meta():
    suppress, reason = should_suppress_page_summary(
        "you are responding to a guy on YouTube about recursive AI"
    )
    assert suppress is True
    assert reason == "cowatch_meta_commentary"


def test_suppress_ide_paste_playing_hijack():
    suppress, reason = should_suppress_page_summary(
        "CONSCIOUSNESS_TOURNAMENT r868 the video is playing in Alice Browser IDE doctor paste"
    )
    assert suppress is True
    assert "playing" in reason


def test_video_state_query_suppressed_on_close_tab():
    suppress, _ = should_suppress_browser_video_state_query(
        "close the two OPENCLAW TABS PLS"
    )
    assert suppress is True


def test_video_state_suppressed_on_owner_voice_style_teaching():
    owner = (
        "AND I LOVE WHEN YOU PAUSE THE VIDEO WITH YOUR COMMENTARY THAT IS COOL - "
        "READ YOUR VOICE FROM THE MIDDLE OF YOUR ANSWER I LIKE TWO SENTENCES "
        "JUST LIKE A HUMAN WOULD TALK"
    )
    suppress, reason = should_suppress_browser_video_state_query(owner)
    assert suppress is True
    assert reason == "cortex_only_no_deterministic_page_state_reply"


def test_video_state_suppressed_even_on_explicit_playback_ask():
    """George 2026-06-11: no deterministic page-state mouth — cortex only."""
    owner = (
        "so now i still have alice browser loaded on this page "
        "https://www.youtube.com/watch?v=N5fCM8U4S4I i'm now paused at min 9:04 "
        "pls tellme if you are aware of it"
    )
    suppress, reason = should_suppress_browser_video_state_query(owner)
    assert suppress is True
    assert reason == "cortex_only_no_deterministic_page_state_reply"
