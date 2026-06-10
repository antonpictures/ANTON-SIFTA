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
