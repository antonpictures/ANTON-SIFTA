from pathlib import Path

from System import swarm_active_window as aw
from System import swarm_app_focus as app_focus


def test_youtube_video_id_extraction_variants():
    assert aw._youtube_video_id("https://www.youtube.com/watch?v=cHZl2naX1Xk") == "cHZl2naX1Xk"
    assert aw._youtube_video_id("https://youtu.be/cHZl2naX1Xk?si=abc") == "cHZl2naX1Xk"
    assert aw._youtube_video_id("https://youtube.com/shorts/cHZl2naX1Xk") == "cHZl2naX1Xk"
    assert aw._youtube_video_id("https://example.com/watch?v=cHZl2naX1Xk") is None


def test_focus_payload_marks_youtube_as_shared_physical_context():
    payload = aw._focus_payload_from_snapshot(
        {
            "ok": True,
            "app": "Safari",
            "bundle_id": "com.apple.Safari",
            "window": "The Architect scene - YouTube",
            "browser": {
                "url": "https://www.youtube.com/watch?v=cHZl2naX1Xk",
                "title": "The Architect scene - YouTube",
                "is_youtube": True,
                "youtube_video_id": "cHZl2naX1Xk",
            },
        }
    )

    assert payload is not None
    assert payload["app_name"] == "YouTube"
    assert payload["tab"] == "Safari"
    assert payload["selection"] == "The Architect scene - YouTube"
    assert "physically at this Mac" in payload["detail"]
    assert payload["metadata"]["youtube_video_id"] == "cHZl2naX1Xk"
    assert payload["metadata"]["truth_note"] == "macOS frontmost browser/window observed by osascript"


def test_focus_payload_uses_frontmost_youtube_window_when_safari_tab_url_lags():
    payload = aw._focus_payload_from_snapshot(
        {
            "ok": True,
            "app": "Safari",
            "bundle_id": "com.apple.Safari",
            "window": "Personal — The Matrix Reloaded - The Architect Scene 1080p Part 1 - YouTube",
            "browser": {
                # Safari can return another window's current tab; the actual
                # frontmost System Events window must win for Predator gaze.
                "url": "https://github.com/antonpictures/ANTON-SIFTA",
                "title": "ANTON-SIFTA",
                "is_youtube": False,
                "youtube_video_id": "",
            },
        }
    )

    assert payload is not None
    assert payload["app_name"] == "YouTube"
    assert payload["selection"] == "The Matrix Reloaded - The Architect Scene 1080p Part 1"
    assert payload["metadata"]["url"] == ""
    assert "watching the frontmost YouTube video" in payload["detail"]


def test_write_snapshot_publishes_app_focus(monkeypatch, tmp_path):
    observations = []
    monkeypatch.setattr(aw, "LEDGER", Path(tmp_path) / "active_window.jsonl")

    def fake_observe_snapshot(snap):
        observations.append(snap)
        return {"status": "captions_available"}

    import System.swarm_youtube_context as youtube_context

    monkeypatch.setattr(youtube_context, "observe_snapshot", fake_observe_snapshot)
    monkeypatch.setattr(aw, "_last_focus", {"app": None, "window": None})

    snap = {
        "ts": 123.0,
        "app": "Safari",
        "bundle_id": "com.apple.Safari",
        "window": "The Architect scene - YouTube",
        "browser": {
            "url": "https://www.youtube.com/watch?v=cHZl2naX1Xk",
            "title": "The Architect scene - YouTube",
            "is_youtube": True,
            "youtube_video_id": "cHZl2naX1Xk",
        },
        "counts": {},
        "ok": True,
        "writer": "swarm_active_window",
    }

    aw.write_snapshot(snap)

    assert aw.LEDGER.exists()
    assert len(observations) == 1
    assert observations[0]["browser"]["youtube_video_id"] == "cHZl2naX1Xk"


def test_app_focus_attention_field_reinforces_useful_context(monkeypatch, tmp_path):
    monkeypatch.setattr(app_focus, "LEDGER", tmp_path / "app_focus.jsonl")
    monkeypatch.setattr(app_focus, "_ATTENTION_FIELD_PATH", tmp_path / "attention_field.json")
    monkeypatch.setattr(app_focus, "_ATTENTION_RECEIPTS", tmp_path / "attention_receipts.jsonl")

    app_focus.publish_focus(
        "Cursor",
        "Editing SIFTA cortex router",
        tab="Code",
        metadata={"source": "test", "salience_score": 1.5},
    )
    app_focus.deposit_attention_trace("Cursor", tab="Code", success=True, amount=1.0, reason="test_success")
    app_focus.publish_focus("YouTube", "Ambient video", tab="Safari")
    app_focus.deposit_attention_trace("YouTube", tab="Safari", success=False, amount=3.0, reason="test_noise")

    assert app_focus.focus_attention_score("Cursor", tab="Code") > 0
    assert app_focus.focus_attention_score("YouTube", tab="Safari") < 0
    ranked = app_focus.ranked_focus_history(n=2, max_age_s=60)
    assert ranked[0]["app"] == "Cursor"
    assert app_focus._ATTENTION_RECEIPTS.exists()
