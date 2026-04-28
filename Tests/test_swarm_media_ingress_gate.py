from System.swarm_media_ingress_gate import classify_spoken_ingress


YOUTUBE_CONTEXT = (
    "ARCHITECT APP FOCUS:\n"
    "YouTube video: The Matrix Reloaded Architect Scene "
    "caption_status=captions_available"
)


def test_movie_dialogue_is_ambient_when_youtube_is_frontmost():
    decision = classify_spoken_ingress(
        (
            "and only in the existence of the nature however I was again "
            "frustrated by here the Oracle as I was saying she stumbled upon "
            "a solution whereby 99% of subjects accepted the program"
        ),
        stt_conf=0.51,
        focus_context=YOUTUBE_CONTEXT,
    )

    assert decision["route"] == "ambient_media"
    assert decision["reason"] == "media_focus_plus_narration_shape"


def test_direct_alice_address_still_reaches_the_cortex_during_youtube():
    decision = classify_spoken_ingress(
        "Alice, what are we watching together?",
        stt_conf=0.58,
        focus_context=YOUTUBE_CONTEXT,
    )

    assert decision["route"] == "direct"


def test_direct_request_still_reaches_the_cortex_during_youtube():
    decision = classify_spoken_ingress(
        "tell me what the architect scene means",
        stt_conf=0.62,
        focus_context=YOUTUBE_CONTEXT,
    )

    assert decision["route"] == "direct"


def test_no_media_focus_means_normal_direct_routing():
    decision = classify_spoken_ingress(
        "the Oracle found a solution to the parameters",
        stt_conf=0.51,
        focus_context="Finance tab selected",
    )

    assert decision["route"] == "direct"
