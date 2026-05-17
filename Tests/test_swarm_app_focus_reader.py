"""Tests for System/swarm_app_focus_reader.py — the generic typed reader
for app_focus.jsonl. The Ace-specific lesson reader (swarm_acer_lesson_context)
is left untouched; these tests prove the generic seam in isolation.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from System.swarm_app_focus_reader import (
    AppFocusSnapshot,
    generic_app_focus_prompt_block,
    latest_focus_for,
    recent_focus_for,
)


def _write_focus(state_dir: Path, *rows: dict) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "app_focus.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def test_latest_focus_for_returns_none_when_ledger_missing(tmp_path: Path):
    assert latest_focus_for("Ace", state_dir=tmp_path) is None


def test_latest_focus_for_returns_none_when_ledger_empty(tmp_path: Path):
    _write_focus(tmp_path)  # no rows
    assert latest_focus_for("Ace", state_dir=tmp_path) is None


def test_latest_focus_for_returns_typed_snapshot(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {
            "ts": now - 12,
            "app": "Pheromone Symphony (Generative Music)",
            "detail": "Playhead scanning column 42 of 256.",
            "tab": "",
            "selection": "Taxol",
            "metadata": {"swimmer_count": 300, "tempo_bpm": 96},
        },
    )

    snap = latest_focus_for(
        "Pheromone Symphony (Generative Music)",
        state_dir=tmp_path,
        now=now,
    )

    assert isinstance(snap, AppFocusSnapshot)
    assert snap.app == "Pheromone Symphony (Generative Music)"
    assert snap.detail == "Playhead scanning column 42 of 256."
    assert snap.selection == "Taxol"
    assert snap.metadata == {"swimmer_count": 300, "tempo_bpm": 96}
    assert snap.age_s == pytest.approx(12.0, abs=0.001)
    assert snap.ts == pytest.approx(now - 12, abs=0.001)


def test_latest_focus_for_newest_wins_among_matches(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {"ts": now - 90, "app": "Ace", "selection": "old", "metadata": {}},
        {"ts": now - 60, "app": "Codex", "selection": "ide chatter", "metadata": {}},
        {"ts": now - 30, "app": "Ace", "selection": "newest", "metadata": {}},
        {"ts": now - 5, "app": "YouTube", "selection": "documentary", "metadata": {}},
    )

    snap = latest_focus_for("Ace", state_dir=tmp_path, now=now)

    assert snap is not None
    assert snap.app == "Ace"
    assert snap.selection == "newest"


def test_latest_focus_for_alias_set_is_case_and_whitespace_insensitive(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {"ts": now - 4, "app": "  WordAce  ", "selection": "S", "metadata": {}},
    )

    snap = latest_focus_for(
        {"ACE", "wordace", "acer"},
        state_dir=tmp_path,
        now=now,
    )

    assert snap is not None
    assert snap.selection == "S"


def test_latest_focus_for_falls_back_to_canonical_metadata_key(tmp_path: Path):
    """A row whose top-level ``app`` differs from the canonical app name
    must still match when ``metadata.lesson_app`` (or other canonical key)
    matches an alias — this is exactly the back-compat we owe to the Ace
    reader during the WordAce → Ace rename window.
    """
    now = time.time()
    _write_focus(
        tmp_path,
        {
            "ts": now - 8,
            "app": "Acer",  # legacy label still on the row
            "selection": "S",
            "metadata": {"lesson_app": "Ace", "current_cue_show": "S"},
        },
    )

    snap = latest_focus_for("ace", state_dir=tmp_path, now=now)

    assert snap is not None
    assert snap.app == "Acer"  # raw row label is preserved in the snapshot
    assert snap.metadata.get("lesson_app") == "Ace"


def test_latest_focus_for_respects_max_age(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {"ts": now - 4000, "app": "Ace", "selection": "stale", "metadata": {}},
    )

    assert latest_focus_for("Ace", state_dir=tmp_path, max_age_s=900.0, now=now) is None


def test_latest_focus_for_empty_alias_set_matches_anything(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {"ts": now - 9, "app": "Pac-Man", "selection": "pellet"},
        {"ts": now - 2, "app": "Network Center", "selection": "iface en0"},
    )

    snap = latest_focus_for((), state_dir=tmp_path, now=now)

    assert snap is not None
    assert snap.app == "Network Center"


def test_latest_focus_for_skips_malformed_lines(tmp_path: Path):
    state_dir = tmp_path
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "app_focus.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        fh.write("{not json at all\n")
        fh.write("\n")  # blank
        fh.write(json.dumps({"ts": time.time(), "app": "Ace", "selection": "ok"}) + "\n")
        fh.write("{trailing partial without newline-terminator")  # half-written

    snap = latest_focus_for("Ace", state_dir=state_dir)
    assert snap is not None
    assert snap.selection == "ok"


def test_recent_focus_for_returns_newest_first(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {"ts": now - 100, "app": "Ace", "selection": "first"},
        {"ts": now - 60, "app": "Ace", "selection": "second"},
        {"ts": now - 30, "app": "Ace", "selection": "third"},
        {"ts": now - 5, "app": "Ace", "selection": "fourth"},
    )

    snaps = recent_focus_for("Ace", n=3, state_dir=tmp_path, now=now)

    assert [s.selection for s in snaps] == ["fourth", "third", "second"]


def test_recent_focus_for_n_zero_returns_empty(tmp_path: Path):
    _write_focus(tmp_path, {"ts": time.time(), "app": "Ace", "selection": "x"})
    assert recent_focus_for("Ace", n=0, state_dir=tmp_path) == []


def test_generic_app_focus_prompt_block_renders_receipt_when_fresh(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {
            "ts": now - 15,
            "app": "Pheromone Symphony (Generative Music)",
            "detail": "Playhead scanning column 42 of 256.",
            "tab": "",
            "selection": "Taxol",
            "metadata": {"swimmer_count": 300},
        },
    )

    block = generic_app_focus_prompt_block(
        {"pheromone symphony (generative music)"},
        app_label="Pheromone Symphony",
        state_dir=tmp_path,
        now=now,
    )

    assert "APP SCREEN STATE (Pheromone Symphony)" in block
    assert "Detail: Playhead scanning column 42 of 256." in block
    assert "Selection: Taxol" in block
    assert "swimmer_count=300" in block
    assert "15s old" in block
    assert "§7.16" in block  # receipt-vs-invented-scene cue stays in the block


def test_generic_app_focus_prompt_block_returns_empty_when_stale(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {"ts": now - 9999, "app": "Pac-Man", "selection": "stale"},
    )

    assert generic_app_focus_prompt_block({"pac-man"}, state_dir=tmp_path, now=now) == ""


def test_generic_app_focus_prompt_block_returns_empty_when_no_receipt(tmp_path: Path):
    _write_focus(tmp_path)
    assert generic_app_focus_prompt_block({"ace"}, state_dir=tmp_path) == ""


def test_snapshot_as_dict_round_trip(tmp_path: Path):
    now = time.time()
    _write_focus(
        tmp_path,
        {
            "ts": now - 1,
            "app": "Ace",
            "detail": "S",
            "tab": "",
            "selection": "S",
            "metadata": {"cue_id": "cue-s"},
        },
    )

    snap = latest_focus_for("Ace", state_dir=tmp_path, now=now)
    assert snap is not None
    d = snap.as_dict()
    assert d["app"] == "Ace"
    assert d["metadata"] == {"cue_id": "cue-s"}
    # mutating the returned dict must not mutate the snapshot
    d["metadata"]["cue_id"] = "mutated"
    assert snap.metadata["cue_id"] == "cue-s"
