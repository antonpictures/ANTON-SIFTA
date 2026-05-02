import json
from pathlib import Path

from System import swarm_youtube_context as yc


def _watch_html(base_url: str = "https://caption.local/api?lang=en") -> str:
    player = {
        "captions": {
            "playerCaptionsTracklistRenderer": {
                "captionTracks": [
                    {
                        "baseUrl": base_url,
                        "languageCode": "en",
                        "name": {"simpleText": "English"},
                    }
                ]
            }
        }
    }
    return f"<html><script>ytInitialPlayerResponse = {json.dumps(player)};</script></html>"


def test_extract_player_response_and_choose_caption_track():
    player = yc.extract_player_response(_watch_html())

    assert player is not None
    track = yc.choose_caption_track(player)
    assert track is not None
    assert track["languageCode"] == "en"
    assert track["baseUrl"].startswith("https://caption.local")


def test_parse_json3_caption_payload_normalizes_segments():
    payload = {
        "events": [
            {"segs": [{"utf8": "Hello "}, {"utf8": "George\n"}]},
            {"segs": [{"utf8": "Alice is watching."}]},
        ]
    }

    assert yc.parse_caption_payload(json.dumps(payload)) == "Hello George Alice is watching."


def test_extract_youtube_video_id_accepts_watch_url_and_bare_id():
    assert yc.extract_youtube_video_id("https://www.youtube.com/watch?v=IXugVZMsZ24") == "IXugVZMsZ24"
    assert yc.extract_youtube_video_id("https://youtu.be/abcdEFGHijk") == "abcdEFGHijk"
    assert yc.extract_youtube_video_id("IXugVZMsZ24") == "IXugVZMsZ24"


def test_fetch_caption_context_uses_watch_page_then_caption_url():
    seen = []

    def fake_fetch(url: str, _timeout: float) -> str:
        seen.append(url)
        if "watch?v=abc123" in url:
            return _watch_html("https://caption.local/api?lang=en")
        assert "fmt=json3" in url
        return json.dumps({"events": [{"segs": [{"utf8": "caption text"}]}]})

    ctx = yc.fetch_caption_context("abc123", fetcher=fake_fetch)

    assert ctx["status"] == "captions_available"
    assert ctx["caption_excerpt"] == "caption text"
    assert ctx["caption_chars"] == len("caption text")
    assert len(seen) == 2


def test_observe_snapshot_writes_ledger_and_publishes_focus(monkeypatch, tmp_path):
    ledger = Path(tmp_path) / "youtube_context.jsonl"
    state = Path(tmp_path) / "youtube_context_latest.json"
    calls = []

    monkeypatch.setattr(yc, "LEDGER", ledger)
    monkeypatch.setattr(yc, "STATE_FILE", state)

    import System.swarm_app_focus as app_focus

    monkeypatch.setattr(app_focus, "publish_focus", lambda *a, **kw: calls.append((a, kw)))

    def fake_fetch(url: str, _timeout: float) -> str:
        if "watch?v=abc123" in url:
            return _watch_html()
        return json.dumps({"events": [{"segs": [{"utf8": "the caption"}]}]})

    row = yc.observe_snapshot(
        {
            "app": "Safari",
            "window": "Video - YouTube",
            "browser": {
                "url": "https://www.youtube.com/watch?v=abc123",
                "title": "Video - YouTube",
                "youtube_video_id": "abc123",
                "is_youtube": True,
            },
        },
        fetcher=fake_fetch,
        force=True,
    )

    assert row is not None
    assert row["status"] == "captions_available"
    assert ledger.exists()
    assert state.exists()
    assert (Path(tmp_path) / "youtube_watch_memory.jsonl").exists()
    assert len(calls) == 1
    assert calls[0][0][0] == "YouTube"
    assert calls[0][1]["metadata"]["caption_excerpt"] == "the caption"


def test_observe_pasted_page_builds_shared_media_context(monkeypatch, tmp_path):
    ledger = Path(tmp_path) / "youtube_context.jsonl"
    state = Path(tmp_path) / "youtube_context_latest.json"
    calls = []

    monkeypatch.setattr(yc, "_STATE", Path(tmp_path))
    monkeypatch.setattr(yc, "LEDGER", ledger)
    monkeypatch.setattr(yc, "STATE_FILE", state)

    import System.swarm_app_focus as app_focus

    monkeypatch.setattr(app_focus, "publish_focus", lambda *a, **kw: calls.append((a, kw)))

    row = yc.observe_pasted_page(
        """
        Skip navigation
        Snatch - Best of Brick top ( + deleted scene)
        MelodicsRareMusicVid
        3.27K subscribers
        3,893,013 views  May 3, 2022
        Ask about this video
        How does Brick Top define his role?
        What are the consequences for failure?
        WE'RE CHANGING THE FIGHTER
        This tense exchange happens early in the video when Turkish and his associates
        try to inform Brick Top that they are changing their fighter.
        AI can make mistakes, so double-check it.
        @greg
        Brick Top is one of those examples of old dangerous professionals.
        """,
        source="pytest_paste",
        url="https://www.youtube.com/watch?v=IXugVZMsZ24",
    )

    assert row["status"] == "pasted_page_context"
    assert row["context_route"] == "shared_media_context"
    assert row["content_kind"] == "film_clip_page"
    assert row["video_id"] == "IXugVZMsZ24"
    assert row["title"] == "Snatch - Best of Brick top ( + deleted scene)"
    assert row["channel"] == "MelodicsRareMusicVid"
    assert row["view_count_text"] == "3,893,013"
    assert row["published_text"] == "May 3, 2022"
    assert row["reality_frame"] == "FICTIONAL_MEDIA_CLIP"
    assert row["director"] == "Guy Ritchie"
    assert row["profanity_frame"] == "FICTIONAL_DIALOGUE"
    assert "fictional media clip" in row["dialogue_boundary"]
    assert row["watch_memory_id"]
    assert Path(row["watch_notes_file"]).exists()
    assert "brick" in row["content_signals"]
    assert row["raw_audio_logged"] is False
    assert ledger.exists()
    assert state.exists()
    assert len(calls) == 1
    assert calls[0][0][0] == "YouTube"
    assert calls[0][1]["metadata"]["context_route"] == "shared_media_context"

    prompt_context = yc.get_latest_context(max_age_s=10.0)
    assert prompt_context is not None
    assert "pasted_page_context" in prompt_context
    assert "page_context=" in prompt_context
    assert "reality_frame=FICTIONAL_MEDIA_CLIP" in prompt_context
    assert "director=Guy Ritchie" in prompt_context


def test_pasted_page_with_leading_url_keeps_video_title(monkeypatch, tmp_path):
    monkeypatch.setattr(yc, "_STATE", Path(tmp_path))
    monkeypatch.setattr(yc, "LEDGER", Path(tmp_path) / "youtube_context.jsonl")
    monkeypatch.setattr(yc, "STATE_FILE", Path(tmp_path) / "youtube_context_latest.json")

    row = yc.observe_pasted_page(
        """
        https://www.youtube.com/watch?v=IXugVZMsZ24
        Snatch - Best of Brick top ( + deleted scene)
        Unofficial YouTube clip; no official subtitles available.
        Fiction movie clip.
        """,
        publish=False,
    )

    assert row["url"] == "https://www.youtube.com/watch?v=IXugVZMsZ24"
    assert row["video_id"] == "IXugVZMsZ24"
    assert row["title"] == "Snatch - Best of Brick top ( + deleted scene)"
    assert row["director"] == "Guy Ritchie"


def test_record_architect_youtube_cowatch_writes_transcript_and_ledger(monkeypatch, tmp_path):
    cow = tmp_path / "youtube_architect_cowatch.jsonl"

    def fake_fetch(url: str, _timeout: float) -> str:
        if "watch?v=abcZ" in url:
            return _watch_html("https://caption.local/api?lang=en")
        return json.dumps({"events": [{"segs": [{"utf8": "line one "}, {"utf8": "line two"}]}]})

    out = yc.record_architect_youtube_cowatch(
        "https://www.youtube.com/watch?v=abcZdefGhIj",
        category_lane="fiction",
        architect_note="pytest co-watch",
        fetcher=fake_fetch,
        state_dir=tmp_path,
        publish_focus_event=False,
    )
    assert out["ok"] is True
    r = out["receipt"]
    assert r["truth_label"] == "ARCHITECT_YOUTUBE_COWATCH_SESSION"
    assert r["youtube_video_id"] == "abcZdefGhIj"
    assert r["category_lane"] == "fiction"
    assert cow.exists()
    tpath = tmp_path / "youtube_transcripts" / "abcZdefGhIj.md"
    assert tpath.exists()
    text = tpath.read_text(encoding="utf-8")
    assert "line one line two" in text
    assert "fiction" in text
