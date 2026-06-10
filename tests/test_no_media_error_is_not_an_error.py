"""r905 — NO_MEDIA_ERROR is the healthy placeholder, never a detected error.

George (2026-06-10, innocent Instagram photo): "WHAT IS THIS WHO BLOCKED?"
Nobody blocked. diagnose_media_error_code(None) returns label NO_MEDIA_ERROR
meaning "no_browser_media_error_observed" — and media_playback_error_from_state
promoted it into a detected error whenever stale recent_errors existed,
so Alice announced the healthy label as a disease over a photo post.
"""

from System.swarm_browser_page_state import media_playback_error_from_state
from System.swarm_media_codec_bridge import diagnose_media_error_code


def _state_with(diagnosis, recent_errors):
    return {
        "url": "https://www.instagram.com/p/EXAMPLE/?img_index=4",
        "title": "Instagram",
        "media_playback": {
            "codec_status": {
                "ok": False,
                "diagnosis": diagnosis,
                "recent_errors": recent_errors,
            }
        },
    }


def test_healthy_label_with_stale_recent_list_is_not_an_error():
    """The exact live shape from George's Lulu Cho / photo session."""
    diagnosis = diagnose_media_error_code(None)
    assert diagnosis["label"] == "NO_MEDIA_ERROR"
    state = _state_with(diagnosis, [{"ts": 1.0}])  # stale entry, no error text
    assert media_playback_error_from_state(state) == {}


def test_healthy_label_alone_is_not_an_error():
    state = _state_with(diagnose_media_error_code(None), [])
    assert media_playback_error_from_state(state) == {}


def test_real_code_is_still_an_error():
    diagnosis = diagnose_media_error_code(4)
    state = _state_with(diagnosis, [{"error": "DEMUXER_ERROR", "code": 4}])
    err = media_playback_error_from_state(state)
    assert err.get("detected") is True
    assert err.get("message") != "NO_MEDIA_ERROR"


def test_real_error_text_under_healthy_label_still_promotes():
    """A real raw error string in recent_errors must survive even when the
    top-level diagnosis came back as the placeholder."""
    state = _state_with(
        diagnose_media_error_code(None),
        [{"error": "PIPELINE_ERROR_DECODE: VDA Error 4", "code": 3}],
    )
    err = media_playback_error_from_state(state)
    assert err.get("detected") is True
    assert "PIPELINE_ERROR_DECODE" in str(err.get("message"))
