import json

from System import alice_music_effector as music


def test_music_play_deposits_truthful_receipt(monkeypatch, tmp_path):
    ledger = tmp_path / "music.jsonl"
    monkeypatch.setattr(music, "_LEDGER", ledger)

    class Result:
        returncode = 0
        stdout = "state=playing"
        stderr = ""

    calls = {}

    def fake_run(args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr(music.subprocess, "run", fake_run)

    result = music.play(mood="mellow")

    assert result["ok"] is True
    assert result["status"] == "PLAY_REQUESTED"
    assert result["mood"] == "mellow"
    assert calls["args"][0] == "osascript"
    row = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert row["event_kind"] == "MUSIC_PLAY_ATTEMPT"
    assert "does not guarantee a specific track" in row["truth_note"]


def test_music_govern_rejects_unknown_verb():
    result = music.govern("make_symphony")

    assert result["ok"] is False
    assert "unknown music verb" in result["error"]


def test_open_youtube_rejects_non_youtube_urls(monkeypatch, tmp_path):
    ledger = tmp_path / "music.jsonl"
    monkeypatch.setattr(music, "_LEDGER", ledger)

    result = music.open_youtube("https://example.com/song")

    assert result["ok"] is False
    assert result["status"] == "REJECTED_URL"


def test_open_youtube_uses_default_browser(monkeypatch, tmp_path):
    ledger = tmp_path / "music.jsonl"
    monkeypatch.setattr(music, "_LEDGER", ledger)

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    calls = {}

    def fake_run(args, **kwargs):
        calls["args"] = args
        return Result()

    monkeypatch.setattr(music.subprocess, "run", fake_run)

    result = music.open_youtube("https://youtu.be/abc123", mood="mellow")

    assert result["ok"] is True
    assert result["status"] == "YOUTUBE_OPENED"
    assert calls["args"] == ["open", "https://youtu.be/abc123"]
