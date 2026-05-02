import json
from pathlib import Path

from System import swarm_youtube_watch_memory as mem


def test_infer_snatch_movie_clip_frame_names_director():
    frame = mem.infer_reality_frame(
        {
            "title": "Snatch - Best of Brick top ( + deleted scene)",
            "content_kind": "film_clip_page",
            "page_context": "signals=brick,fighter,gangster",
            "content_signals": ["brick", "fighter"],
        }
    )

    assert frame["reality_frame"] == "FICTIONAL_MEDIA_CLIP"
    assert frame["content_category"] == "Film & Animation"
    assert frame["source_work"] == "Snatch"
    assert frame["director"] == "Guy Ritchie"
    assert frame["profanity_frame"] == "FICTIONAL_DIALOGUE"
    assert "fictional media clip" in frame["dialogue_boundary"]


def test_remember_youtube_watch_writes_ledger_and_safe_notes(tmp_path: Path):
    row = {
        "title": "Snatch - Best of Brick top ( + deleted scene)",
        "url": "https://www.youtube.com/watch?v=IXugVZMsZ24",
        "video_id": "IXugVZMsZ24",
        "status": "pasted_page_context",
        "content_kind": "film_clip_page",
        "page_context": "title=Snatch - Best of Brick top; signals=brick,fighter",
        "ask_panel_answer_excerpt": "This tense exchange happens early in the video.",
        "suggested_questions": ["How does Brick Top define his role?"],
        "caption_chars": 0,
    }

    out = mem.remember_youtube_watch(row, state_dir=tmp_path)

    assert out["truth_label"] == mem.TRUTH_LABEL
    assert out["video_id"] == "IXugVZMsZ24"
    assert out["full_subtitles_stored"] is False
    assert out["raw_audio_logged"] is False
    assert out["reality_frame"]["director"] == "Guy Ritchie"

    ledger = tmp_path / "youtube_watch_memory.jsonl"
    assert ledger.exists()
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    saved = json.loads(lines[0])
    assert saved["memory_id"] == out["memory_id"]

    notes = Path(out["notes_file"])
    assert notes.exists()
    body = notes.read_text(encoding="utf-8")
    assert "FICTIONAL_MEDIA_CLIP" in body
    assert "Guy Ritchie" in body
    assert "not a full subtitle transcript" in body


def test_latest_watch_context_includes_dialogue_boundary(tmp_path: Path):
    mem.remember_youtube_watch(
        {
            "title": "Snatch - Best of Brick top",
            "content_kind": "film_clip_page",
            "page_context": "signals=brick,fighter",
        },
        state_dir=tmp_path,
    )

    ctx = mem.latest_watch_context(state_dir=tmp_path)

    assert "watched_with=George" in ctx
    assert "frame=FICTIONAL_MEDIA_CLIP" in ctx
    assert "director=Guy Ritchie" in ctx
    assert "fictional media clip" in ctx


def test_youtube_video_id_variants():
    assert mem.youtube_video_id("https://www.youtube.com/watch?v=IXugVZMsZ24") == "IXugVZMsZ24"
    assert mem.youtube_video_id("https://youtu.be/IXugVZMsZ24?t=1") == "IXugVZMsZ24"
    assert mem.youtube_video_id("https://youtube.com/shorts/IXugVZMsZ24") == "IXugVZMsZ24"
