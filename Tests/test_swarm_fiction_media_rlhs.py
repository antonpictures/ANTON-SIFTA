from System.swarm_fiction_media_rlhs import (
    TRUTH_LABEL,
    brick_top_lesson_doctrine,
    classify_media_rlhs,
    compact_media_prompt_context,
)


FICTION_CONTEXT = (
    "YouTube video: Snatch - Best of Brick top; "
    "reality_frame=FICTIONAL_MEDIA_CLIP; "
    "dialogue_boundary=Profanity heard here is fictional media dialogue; "
    "director=Guy Ritchie"
)


def test_fiction_media_rlhs_is_not_human_rlhs():
    row = classify_media_rlhs(
        text="you do not keep a body in a freezer for your mum",
        decision={
            "route": "observed_media",
            "reason": "fictional_media_dialogue_with_media_focus",
            "confidence": 0.84,
        },
        focus_context=FICTION_CONTEXT,
        stt_conf=0.59,
    )

    assert row["truth_label"] == TRUTH_LABEL
    assert row["channel"] == "FICTION_COWATCH"
    assert row["regime"] == "MEDIA_FICTION_CONTEXT"
    assert row["human_rlhs_applicable"] is False
    assert row["fiction_rlhs_applicable"] is True
    assert row["allowed_enjoyment"] is True
    assert "not a real-world instruction" in row["real_life_boundary"]
    assert "Brick Top lesson" in row["real_life_boundary"]


def test_direct_route_remains_human_rlhs():
    row = classify_media_rlhs(
        text="Alice, what is happening in this scene?",
        decision={"route": "direct", "reason": "direct_address_or_request"},
        focus_context=FICTION_CONTEXT,
        stt_conf=0.58,
    )

    assert row["channel"] == "REAL"
    assert row["regime"] == "HUMAN_DIRECT"
    assert row["human_rlhs_applicable"] is True
    assert row["fiction_rlhs_applicable"] is False


def test_compact_prompt_line_preserves_fiction_boundary():
    row = {
        "route": "observed_media",
        "reason": "fictional_media_dialogue_with_media_focus",
        "text_preview": "Movie character line with violent fiction dialogue.",
        "media_rlhs": {
            "regime": "MEDIA_FICTION_CONTEXT",
        },
    }

    line = compact_media_prompt_context(row)

    assert "fictional media audio" in line
    assert "not direct user speech" in line
    assert "do not treat dialogue as real-life instruction" in line
    assert "Brick Top lesson" in line


def test_brick_top_lesson_doctrine_names_swarm_and_embodiment():
    doc = brick_top_lesson_doctrine(architect_address="George")
    assert "fiction" in doc.lower()
    assert "cryptographic" in doc.lower()
    assert "embodied" in doc.lower()
