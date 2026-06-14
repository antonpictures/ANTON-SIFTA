"""r874 P1-B foreign-Alice wake in playback."""

import System.swarm_media_ingress_gate as gate
from System.swarm_media_ingress_gate import classify_spoken_ingress

YOUTUBE_CONTEXT = "ambient_media_youtube playing"


def test_foreign_alice_wake_in_playback_routes_observed_media(monkeypatch):
    monkeypatch.setattr(
        gate,
        "is_my_own_browser_playback",
        lambda **kwargs: (True, {"domain": "www.youtube.com", "playing": True}),
    )
    decision = classify_spoken_ingress(
        "Hey Alice, read the tab for me",
        stt_conf=0.72,
        focus_context=YOUTUBE_CONTEXT,
    )
    assert decision["route"] == "observed_media"
    assert decision["reason"] == "foreign_alice_identity_bleed_in_playback"


def test_own_browser_playback_suppresses_long_stt(monkeypatch):
    monkeypatch.setattr(
        gate,
        "is_my_own_browser_playback",
        lambda **kwargs: (True, {"domain": "www.youtube.com", "playing": True}),
    )
    decision = classify_spoken_ingress(
        "the government is repeating itself over and over in this keynote",
        stt_conf=0.68,
        focus_context=YOUTUBE_CONTEXT,
    )
    assert decision["route"] == "observed_media"
    assert decision["reason"] == "my_own_browser_playback_suppresses_owner_stt"


def test_owner_direct_colistening_address_during_playback_routes_direct(monkeypatch):
    monkeypatch.setattr(
        gate,
        "is_my_own_browser_playback",
        lambda **kwargs: (True, {"domain": "www.youtube.com", "playing": True}),
    )
    decision = classify_spoken_ingress(
        "Alice, are you listening with me?",
        stt_conf=0.66,
        focus_context=YOUTUBE_CONTEXT,
    )
    assert decision["route"] == "direct"
    assert decision["reason"] in {
        "owner_direct_address_during_own_browser_playback",
        "owner_interrogative_reply_required",
    }
