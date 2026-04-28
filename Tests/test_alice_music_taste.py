import json

from System import alice_music_taste as taste


def test_record_youtube_link_builds_bayesian_profile(tmp_path):
    ledger = tmp_path / "taste.jsonl"

    rows = taste.record_youtube_links(
        "Alice remember this mellow latin song https://youtu.be/abc123",
        path=ledger,
    )
    taste.record_youtube_links(
        "I don't like this rock track https://youtube.com/watch?v=bad",
        path=ledger,
    )

    assert rows[0]["url"] == "https://youtu.be/abc123"
    assert rows[0]["liked"] is True
    profile = taste.bayesian_profile(path=ledger)
    by_tag = {row["tag"]: row for row in profile}
    assert by_tag["mellow"]["preference"] == 2 / 3
    assert by_tag["latin"]["preference"] == 2 / 3
    assert by_tag["rock"]["preference"] == 1 / 3


def test_reply_names_bayesian_curve(tmp_path):
    ledger = tmp_path / "taste.jsonl"
    rows = taste.record_youtube_links(
        "save this lo-fi beat https://youtu.be/lofi",
        path=ledger,
    )

    reply = taste.reply_for_recorded_links(rows, path=ledger)

    assert "Bayesian taste curve" in reply
    assert "lo-fi" in reply


def test_taste_rows_are_jsonl(tmp_path):
    ledger = tmp_path / "taste.jsonl"
    taste.record_youtube_links("https://youtu.be/abc123", path=ledger)

    row = json.loads(ledger.read_text(encoding="utf-8").strip())

    assert row["event_kind"] == "MUSIC_TASTE_OBSERVATION"
    assert row["tags"] == ["uncategorized"]
