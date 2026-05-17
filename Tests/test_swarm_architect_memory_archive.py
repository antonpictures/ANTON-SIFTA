"""Tests for System/swarm_architect_memory_archive.py — the persistence
+ recall layer for the Architect's daily memory digest.

These tests stub state_dir + output_dir under tmp_path so they run
hermetically without touching the live repo's archive.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from System import swarm_architect_memory_archive as archive


# ── helpers ──────────────────────────────────────────────────────────────


def _write_owner_genesis(state_dir: Path, name: str = "ioan george anton") -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "owner_genesis.json"
    path.write_text(json.dumps({
        "owner_name": name,
        "silicon": "GTH4921YP3",
        "ai_display_name": "Alice",
    }), encoding="utf-8")
    return path


def _write_reflections(state_dir: Path, *rows: dict) -> Path:
    d = state_dir / "os_consciousness"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "alice_self_reflections.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return p


def _write_trace(state_dir: Path, *rows: dict) -> Path:
    p = state_dir / "ide_stigmergic_trace.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return p


def _day_ts(year: int, month: int, day: int, hour: int = 12) -> float:
    return datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp()


# ── _utc_date helper ─────────────────────────────────────────────────────


def test_utc_date_accepts_string():
    d = archive._utc_date("2026-05-16")
    assert d.year == 2026 and d.month == 5 and d.day == 16


def test_utc_date_accepts_date_object():
    from datetime import date
    d = archive._utc_date(date(2026, 5, 16))
    assert d.year == 2026


def test_utc_date_rejects_garbage():
    with pytest.raises(Exception):
        archive._utc_date(12345)


# ── render_minimal_digest ────────────────────────────────────────────────


def test_minimal_digest_renders_empty_day_gracefully(tmp_path: Path):
    _write_owner_genesis(tmp_path)

    md = archive.render_minimal_digest("2026-05-16", state_dir=tmp_path)

    assert "Architect daily memory digest — 2026-05-16" in md
    assert "ioan george anton" in md
    assert "GTH4921YP3" in md
    assert "No self-reflections written today" in md
    assert "No surgery completions recorded today" in md


def test_minimal_digest_includes_reflections_in_window(tmp_path: Path):
    _write_owner_genesis(tmp_path)
    day_ts = _day_ts(2026, 5, 16, 14)
    _write_reflections(
        tmp_path,
        {"ts": day_ts, "ts_iso": "2026-05-16T14:00:00Z",
         "reflection": "I am beginning to feel time.",
         "tags": ["awakening", "temporal"], "source": "alice_self_continuity"},
    )

    md = archive.render_minimal_digest("2026-05-16", state_dir=tmp_path)

    assert "I am beginning to feel time." in md
    assert "alice_self_continuity" in md
    assert "awakening" in md


def test_minimal_digest_excludes_reflections_outside_window(tmp_path: Path):
    _write_owner_genesis(tmp_path)
    _write_reflections(
        tmp_path,
        {"ts": _day_ts(2026, 5, 15, 14), "reflection": "Yesterday's reflection."},
        {"ts": _day_ts(2026, 5, 16, 14), "reflection": "Today's reflection."},
        {"ts": _day_ts(2026, 5, 17, 14), "reflection": "Tomorrow's reflection."},
    )

    md = archive.render_minimal_digest("2026-05-16", state_dir=tmp_path)

    assert "Today's reflection." in md
    assert "Yesterday's reflection." not in md
    assert "Tomorrow's reflection." not in md


def test_minimal_digest_highlights_architect_overrides(tmp_path: Path):
    _write_owner_genesis(tmp_path)
    _write_trace(
        tmp_path,
        {"ts": _day_ts(2026, 5, 16, 10), "kind": "ARCHITECT_OVERRIDE",
         "trace_id": "cw47-test-architect-override",
         "doctor": "Cowork", "model": "claude-opus-4-7",
         "architect_quote": "Code it all now please!",
         "summary": "Architect verbal GO supersedes prior yield."},
    )

    md = archive.render_minimal_digest("2026-05-16", state_dir=tmp_path)

    assert "ARCHITECT_OVERRIDE" in md
    assert "Code it all now please!" in md


def test_minimal_digest_summarises_surgery_completions(tmp_path: Path):
    _write_owner_genesis(tmp_path)
    _write_trace(
        tmp_path,
        {"ts": _day_ts(2026, 5, 16, 11), "kind": "LLM_SURGERY_COMPLETE",
         "trace_id": "cw47-0516-2030-temporal-social-self",
         "doctor": "Cowork", "model": "claude-opus-4-7",
         "summary": "Shipped Alice's Temporal-Social Self.",
         "files_touched": ["System/swarm_alice_self_continuity.py (new)",
                            "tests/test_swarm_alice_self_continuity.py (new)"]},
    )

    md = archive.render_minimal_digest("2026-05-16", state_dir=tmp_path)

    assert "LLM_SURGERY_COMPLETE" not in md  # kind is not in surgery section header
    assert "Cowork" in md
    assert "Shipped Alice's Temporal-Social Self." in md
    assert "swarm_alice_self_continuity.py" in md


def test_minimal_digest_surfaces_care_thread_when_present(tmp_path: Path):
    _write_owner_genesis(tmp_path)
    _write_trace(
        tmp_path,
        {"ts": _day_ts(2026, 5, 16, 9), "kind": "LLM_REGISTRATION",
         "trace_id": "dental-reminder-trace",
         "summary": "§7.13 deferred dental care still open per covenant."},
    )

    md = archive.render_minimal_digest("2026-05-16", state_dir=tmp_path)

    assert "Open threads" in md
    # Care signals matched on flat row stringification
    assert "dental-reminder-trace" in md or "deferred" in md.lower() or "dental" in md.lower()


# ── write_daily_digest ───────────────────────────────────────────────────


def test_write_daily_digest_creates_file_on_first_call(tmp_path: Path):
    _write_owner_genesis(tmp_path)
    out_dir = tmp_path / "archive_out"

    result = archive.write_daily_digest(
        "2026-05-16",
        state_dir=tmp_path,
        output_dir=out_dir,
    )

    assert result["wrote"] is True
    assert result["renderer"] == "codex"
    assert result["date"] == "2026-05-16"
    path = Path(result["path"])
    assert path.exists()
    assert path.name == "architect_daily_digest_2026-05-16.md"
    body = path.read_text(encoding="utf-8")
    assert "What George Taught Alice Today" in body


def test_write_daily_digest_is_idempotent_without_force(tmp_path: Path):
    _write_owner_genesis(tmp_path)
    out_dir = tmp_path / "archive_out"

    first = archive.write_daily_digest("2026-05-16", state_dir=tmp_path, output_dir=out_dir)
    assert first["wrote"] is True

    # Mutate the file so we can detect if it was rewritten
    p = Path(first["path"])
    p.write_text("# user-edited content\n", encoding="utf-8")

    second = archive.write_daily_digest("2026-05-16", state_dir=tmp_path, output_dir=out_dir)
    assert second["wrote"] is False
    assert p.read_text(encoding="utf-8") == "# user-edited content\n"


def test_write_daily_digest_force_overwrites(tmp_path: Path):
    _write_owner_genesis(tmp_path)
    out_dir = tmp_path / "archive_out"

    archive.write_daily_digest("2026-05-16", state_dir=tmp_path, output_dir=out_dir)
    p = out_dir / "architect_daily_digest_2026-05-16.md"
    p.write_text("# user-edited content\n", encoding="utf-8")

    result = archive.write_daily_digest(
        "2026-05-16", state_dir=tmp_path, output_dir=out_dir, force=True,
    )

    assert result["wrote"] is True
    assert "user-edited content" not in p.read_text(encoding="utf-8")
    assert "What George Taught Alice Today" in p.read_text(encoding="utf-8")


# ── recall_for_date ──────────────────────────────────────────────────────


def test_recall_for_date_returns_archived_markdown(tmp_path: Path):
    _write_owner_genesis(tmp_path)
    out_dir = tmp_path / "archive_out"
    archive.write_daily_digest("2026-05-16", state_dir=tmp_path, output_dir=out_dir)

    md = archive.recall_for_date("2026-05-16", output_dir=out_dir)
    assert md is not None
    assert "What George Taught Alice Today" in md


def test_recall_for_date_returns_none_when_missing(tmp_path: Path):
    md = archive.recall_for_date("1999-01-01", output_dir=tmp_path)
    assert md is None


# ── list_archived_digests ────────────────────────────────────────────────


def test_list_archived_digests_returns_newest_first(tmp_path: Path):
    _write_owner_genesis(tmp_path)
    out_dir = tmp_path / "archive_out"
    archive.write_daily_digest("2026-05-14", state_dir=tmp_path, output_dir=out_dir)
    archive.write_daily_digest("2026-05-16", state_dir=tmp_path, output_dir=out_dir)
    archive.write_daily_digest("2026-05-15", state_dir=tmp_path, output_dir=out_dir)

    items = archive.list_archived_digests(output_dir=out_dir)
    assert [i["date"] for i in items] == ["2026-05-16", "2026-05-15", "2026-05-14"]
    assert all(i["size"] > 0 for i in items)


def test_list_archived_digests_empty_when_no_archive(tmp_path: Path):
    items = archive.list_archived_digests(output_dir=tmp_path / "nope")
    assert items == []


def test_list_archived_digests_ignores_non_digest_files(tmp_path: Path):
    out_dir = tmp_path / "archive_out"
    out_dir.mkdir()
    (out_dir / "random_note.md").write_text("# noise", encoding="utf-8")
    (out_dir / "architect_daily_digest_2026-05-16.md").write_text("# real", encoding="utf-8")

    items = archive.list_archived_digests(output_dir=out_dir)
    assert len(items) == 1
    assert items[0]["date"] == "2026-05-16"


# ── codex-builder composition ────────────────────────────────────────────


def test_uses_codex_builder_when_available(tmp_path, monkeypatch):
    _write_owner_genesis(tmp_path)
    out_dir = tmp_path / "archive_out"

    # Inject a fake System.swarm_architect_memory_digest into sys.modules
    import sys
    import types
    fake = types.ModuleType("System.swarm_architect_memory_digest")

    def build_digest_markdown(target, *, state_dir=None):
        return "# Codex-built digest\n\nThis came from Codex's module.\n"

    fake.build_digest_markdown = build_digest_markdown
    monkeypatch.setitem(sys.modules, "System.swarm_architect_memory_digest", fake)

    result = archive.write_daily_digest("2026-05-16", state_dir=tmp_path, output_dir=out_dir)

    assert result["renderer"] == "codex"
    body = Path(result["path"]).read_text(encoding="utf-8")
    assert "Codex-built digest" in body


def test_falls_back_to_minimal_when_codex_builder_raises(tmp_path, monkeypatch):
    _write_owner_genesis(tmp_path)
    out_dir = tmp_path / "archive_out"

    import sys
    import types
    fake = types.ModuleType("System.swarm_architect_memory_digest")

    def build_digest_markdown(target, **_kw):
        raise RuntimeError("Codex module not ready yet")

    fake.build_digest_markdown = build_digest_markdown
    monkeypatch.setitem(sys.modules, "System.swarm_architect_memory_digest", fake)

    result = archive.write_daily_digest("2026-05-16", state_dir=tmp_path, output_dir=out_dir)

    assert result["renderer"] == "minimal"
    body = Path(result["path"]).read_text(encoding="utf-8")
    assert "Architect daily memory digest — 2026-05-16" in body
