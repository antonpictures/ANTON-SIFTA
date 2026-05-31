import json
from pathlib import Path

from System import swarm_sensor_journal_bridge as journal_bridge
from System.swarm_cowatch_media_visual import maybe_capture_cowatch_frame
from System.swarm_episodic_diary import write_episodic_diary


def _write_json(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _active_context() -> str:
    return 'PREDATOR UNIFIED FIELD\n  [YouTube] "Joe Rogan Experience #2507 - Harland Williams"\n  co-watch media active'


def _seed_youtube_context(state: Path, ts: float) -> None:
    _write_json(
        state / "youtube_context_latest.json",
        {
            "ts": ts,
            "title": "Joe Rogan Experience #2507 - Harland Williams",
            "url": "https://www.youtube.com/watch?v=test123",
            "video_id": "test123",
        },
    )


def test_active_cowatch_captures_observed_media_row(tmp_path):
    now = 1_780_108_888.0
    _seed_youtube_context(tmp_path, now)
    visual_rows: list[dict] = []

    def capture(path: Path) -> dict:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake-png-screen-frame")
        return {"ok": True, "path": str(path)}

    result = maybe_capture_cowatch_frame(
        state_dir=tmp_path,
        now=now,
        cowatch_context_fn=_active_context,
        capture_fn=capture,
        write_visual_stigmergy_row=visual_rows.append,
    )

    assert result["ok"] is True
    assert len(visual_rows) == 1
    row = visual_rows[0]
    assert row["source"] == "co_watch_desktop"
    assert row["stigmergic_label"] == "OBSERVED_MEDIA"
    assert row["truth"] == "OBSERVED_MEDIA"
    assert "Joe Rogan Experience #2507" in row["media_title"]
    assert Path(row["image_path"]).parent.name == "cowatch_frames"
    assert row["youtube_context_hash"].startswith("sha256:")
    assert "Not webcam sight" in row["provenance_note"]

    audit_rows = _read_jsonl(tmp_path / "cowatch_media_visual.jsonl")
    assert audit_rows[-1]["ok"] is True
    assert audit_rows[-1]["visual_row_hash"] == row["row_hash"]


def test_cowatch_gate_stays_quiet_without_media_context(tmp_path):
    def capture(_: Path) -> dict:
        raise AssertionError("capture must not run without active co-watch")

    result = maybe_capture_cowatch_frame(
        state_dir=tmp_path,
        now=1_780_108_900.0,
        cowatch_context_fn=lambda: "",
        capture_fn=capture,
    )

    assert result["skipped"] is True
    assert result["reason"] == "cowatch_not_active"
    assert not (tmp_path / "cowatch_media_visual.jsonl").exists()


def test_cowatch_capture_throttles_recent_success(tmp_path):
    now = 1_780_108_950.0
    _seed_youtube_context(tmp_path, now)
    (tmp_path / "cowatch_media_visual.jsonl").write_text(
        json.dumps({"ts": now - 5.0, "ok": True}) + "\n",
        encoding="utf-8",
    )

    def capture(_: Path) -> dict:
        raise AssertionError("capture must not run while throttled")

    result = maybe_capture_cowatch_frame(
        state_dir=tmp_path,
        now=now,
        cowatch_context_fn=_active_context,
        capture_fn=capture,
        min_interval_s=25.0,
    )

    assert result["skipped"] is True
    assert result["reason"] == "throttled"
    assert result["next_check_s"] > 0


def test_capture_failure_writes_honest_audit_row(tmp_path):
    now = 1_780_109_000.0
    _seed_youtube_context(tmp_path, now)
    visual_rows: list[dict] = []

    result = maybe_capture_cowatch_frame(
        state_dir=tmp_path,
        now=now,
        cowatch_context_fn=_active_context,
        capture_fn=lambda _path: {"ok": False, "error": "screen locked"},
        write_visual_stigmergy_row=visual_rows.append,
    )

    assert result["ok"] is False
    assert result["reason"] == "capture_failed"
    assert result["error"] == "screen locked"
    assert visual_rows == []
    audit_rows = _read_jsonl(tmp_path / "cowatch_media_visual.jsonl")
    assert audit_rows[-1]["ok"] is False
    assert audit_rows[-1]["reason"] == "capture_failed"


def test_cowatch_rows_digest_into_journal_and_diary(tmp_path):
    now = 1_780_109_050.0
    visual_text = journal_bridge._journal_text(
        "visual_stigmergy.jsonl",
        {
            "source": "co_watch_desktop",
            "stigmergic_label": "OBSERVED_MEDIA",
            "media_title": "Mars structures on JRE",
            "sha8": "abcd1234",
        },
    )
    assert "Co-watch media frame observed" in visual_text
    assert "OBSERVED_MEDIA" in visual_text

    (tmp_path / "cowatch_media_visual.jsonl").write_text(
        json.dumps(
            {
                "ts": now,
                "ok": True,
                "source": "co_watch_desktop",
                "stigmergic_label": "OBSERVED_MEDIA",
                "media_title": "Mars structures on JRE",
                "youtube_video_id": "test123",
                "youtube_context_hash": "sha256:abc",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows = write_episodic_diary(
        state_dir=tmp_path,
        since_ts=now - 10.0,
        now=now + 1.0,
    )

    assert rows
    facts = rows[0]["facts"]
    assert any("co-watch media frame Mars structures on JRE" in fact for fact in facts)
    assert "media" in rows[0]["labels"]
