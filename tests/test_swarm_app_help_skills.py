"""Tests for System/swarm_app_help_skills.py — the orthogonal layer
that merges the static APP_SKILL_DOMAINS seed with Grok's stigmergic
swarm_app_health rows, auto-scans receipts for skill attribution, and
materialises Documents/app_help/<slug>.md per app.

These tests stub out the I/O sides (manifest path, app health trace
location) so they run hermetically — no dependency on live ledger state.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from System import swarm_app_health
from System import swarm_app_help_skills as helpskills


# ── helpers ──────────────────────────────────────────────────────────────


def _seed_health_trace(monkeypatch, tmp_path: Path):
    """Redirect Grok's app_health module to a tmp directory."""
    health_root = tmp_path / "app_health"
    monkeypatch.setattr(swarm_app_health, "_STATE", tmp_path, raising=True)
    monkeypatch.setattr(swarm_app_health, "_HEALTH_ROOT", health_root, raising=True)
    return health_root


def _write_health_rows(health_root: Path, app_slug: str, *rows: dict) -> Path:
    p = health_root / app_slug
    p.mkdir(parents=True, exist_ok=True)
    path = p / "health_trace.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def _write_receipt(tmp_path: Path, filename: str, *rows: dict) -> Path:
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


# ── effective_skills_for_app ─────────────────────────────────────────────


def test_effective_skills_returns_empty_for_unknown_app(monkeypatch, tmp_path: Path):
    _seed_health_trace(monkeypatch, tmp_path)
    es = helpskills.effective_skills_for_app("Mystery App")
    assert es.app_canonical == "Mystery App"
    assert es.stigmergic == []
    # The static APP_SKILL_DOMAINS has no entry matching "mystery app",
    # so the seed is also empty.
    assert es.static_seed == []
    assert es.merged == []


def test_effective_skills_merges_stigmergic_with_static_seed(monkeypatch, tmp_path: Path):
    health_root = _seed_health_trace(monkeypatch, tmp_path)
    now = time.time()
    _write_health_rows(
        health_root, "ace",
        {"ts": now - 100, "app": "Ace", "action": "initial_seed",
         "skills": ["child_mic_turn_visibility", "tight_cue_language"]},
        {"ts": now - 10, "app": "Ace", "action": "enter_update",
         "skills": ["empty_text_receipt", "tight_cue_language"]},
    )

    es = helpskills.effective_skills_for_app("Ace")

    # Stigmergic is union, newest-first ordering preserved.
    assert "empty_text_receipt" in es.stigmergic
    assert "child_mic_turn_visibility" in es.stigmergic
    assert "tight_cue_language" in es.stigmergic
    # APP_SKILL_DOMAINS has phonics/reading_teaching/etc for ace/wordace.
    assert "phonics" in es.static_seed or "reading_teaching" in es.static_seed
    # Merged contains all stigmergic + all unique static, no duplicates.
    assert len(es.merged) == len(set(es.merged))
    for s in es.stigmergic:
        assert s in es.merged
    for s in es.static_seed:
        assert s in es.merged
    # Stigmergic skills come first in the merged list.
    if es.stigmergic and es.static_seed:
        first_static_idx = next(
            (i for i, s in enumerate(es.merged) if s in es.static_seed
             and s not in es.stigmergic),
            None,
        )
        if first_static_idx is not None:
            assert first_static_idx >= len(es.stigmergic)


def test_effective_skills_last_seen_ts_is_max_across_rows(monkeypatch, tmp_path: Path):
    health_root = _seed_health_trace(monkeypatch, tmp_path)
    _write_health_rows(
        health_root, "ace",
        {"ts": 100.0, "app": "Ace", "action": "seed", "skills": ["phonics"]},
        {"ts": 200.0, "app": "Ace", "action": "update", "skills": ["phonics"]},
        {"ts": 50.0,  "app": "Ace", "action": "older", "skills": ["phonics"]},
    )

    es = helpskills.effective_skills_for_app("Ace")
    assert es.last_seen_ts["phonics"] == 200.0


# ── auto_scan_recent_receipts ────────────────────────────────────────────


def test_auto_scan_finds_skill_mentions_in_work_receipts(monkeypatch, tmp_path: Path):
    _seed_health_trace(monkeypatch, tmp_path)
    _write_receipt(
        tmp_path, "work_receipts.jsonl",
        {"ts": 100.0, "app": "Ace", "skill_name": "phonics", "note": "scored CORRECT"},
        {"ts": 150.0, "app": "Ace", "skill": "positive_reinforcement"},
        {"ts": 200.0, "app": "Pheromone Symphony", "skill_name": "music_theory"},
    )

    skills = helpskills.auto_scan_recent_receipts(
        "Ace",
        since_ts=0.0,
        until_ts=300.0,
        state_dir=tmp_path,
        ledgers=[Path("work_receipts.jsonl")],
    )
    assert "phonics" in skills
    assert "positive_reinforcement" in skills
    # Symphony skill is filtered out because the app field doesn't match.
    assert "music_theory" not in skills


def test_auto_scan_is_idempotent_on_repeated_call(monkeypatch, tmp_path: Path):
    _seed_health_trace(monkeypatch, tmp_path)
    _write_receipt(
        tmp_path, "work_receipts.jsonl",
        {"ts": 100.0, "app": "Ace", "skill_name": "phonics"},
    )

    first = helpskills.auto_scan_recent_receipts(
        "Ace", since_ts=0.0, until_ts=300.0,
        state_dir=tmp_path, ledgers=[Path("work_receipts.jsonl")],
    )
    second = helpskills.auto_scan_recent_receipts(
        "Ace", since_ts=0.0, until_ts=300.0,
        state_dir=tmp_path, ledgers=[Path("work_receipts.jsonl")],
    )

    assert first == ["phonics"]
    assert second == []  # sha-marker recognised, no double-record


def test_auto_scan_records_via_grok_module(monkeypatch, tmp_path: Path):
    health_root = _seed_health_trace(monkeypatch, tmp_path)
    _write_receipt(
        tmp_path, "work_receipts.jsonl",
        {"ts": 100.0, "app": "Ace", "skill_name": "phonics"},
    )

    helpskills.auto_scan_recent_receipts(
        "Ace", since_ts=0.0, until_ts=300.0,
        state_dir=tmp_path, ledgers=[Path("work_receipts.jsonl")],
    )

    health_rows = swarm_app_health.get_app_health("Ace")
    assert len(health_rows) >= 1
    autoscan_rows = [r for r in health_rows if r.get("action") == "auto_scan_skill_attribution"]
    assert len(autoscan_rows) == 1
    assert "phonics" in autoscan_rows[0].get("skills", [])
    assert autoscan_rows[0].get("extra", {}).get("autoscan_sha")


def test_auto_scan_no_matches_returns_empty(monkeypatch, tmp_path: Path):
    _seed_health_trace(monkeypatch, tmp_path)
    _write_receipt(
        tmp_path, "work_receipts.jsonl",
        {"ts": 100.0, "app": "Other App", "skill_name": "irrelevant"},
    )

    skills = helpskills.auto_scan_recent_receipts(
        "Ace", since_ts=0.0, until_ts=300.0,
        state_dir=tmp_path, ledgers=[Path("work_receipts.jsonl")],
    )
    assert skills == []


def test_auto_scan_reads_canonical_keys_from_metadata(monkeypatch, tmp_path: Path):
    _seed_health_trace(monkeypatch, tmp_path)
    _write_receipt(
        tmp_path, "work_receipts.jsonl",
        {"ts": 100.0, "metadata": {"app_canonical": "Ace", "skill_name": "phonics"}},
    )

    skills = helpskills.auto_scan_recent_receipts(
        "Ace", since_ts=0.0, until_ts=300.0,
        state_dir=tmp_path, ledgers=[Path("work_receipts.jsonl")],
    )
    assert "phonics" in skills


# ── materialize_help_file ────────────────────────────────────────────────


def test_materialize_help_file_emits_valid_markdown(monkeypatch, tmp_path: Path):
    health_root = _seed_health_trace(monkeypatch, tmp_path)
    _write_health_rows(
        health_root, "ace",
        {"ts": time.time(), "ts_iso": "2026-05-16T12:00:00Z", "app": "Ace",
         "action": "initial_seed", "skills": ["phonics", "patience"],
         "note": "Seed row", "stgm_delta": 1.0, "source": "test"},
    )

    out_dir = tmp_path / "Documents" / "app_help"
    path = helpskills.materialize_help_file(
        "Ace",
        manifest_entry={
            "category": "Alice",
            "description": "Alice teaches a child to read.",
            "icon": "🐝",
            "signature": "COWORK_OPUS47_ACE_V0",
            "truth_label": "SIFTA_TEACH_ACE_TO_READ_V0",
        },
        output_dir=out_dir,
    )

    assert path.exists()
    body = path.read_text(encoding="utf-8")
    assert "# 🐝 Ace" in body
    assert "Alice teaches a child to read." in body
    assert "Category" in body
    assert "phonics" in body
    assert "initial_seed" in body
    assert "Seed row" in body


def test_materialize_help_file_handles_app_with_no_health_rows(monkeypatch, tmp_path: Path):
    _seed_health_trace(monkeypatch, tmp_path)
    out_dir = tmp_path / "Documents" / "app_help"
    path = helpskills.materialize_help_file(
        "Pheromone Symphony (Generative Music)",
        manifest_entry={
            "category": "Creative",
            "description": "Stigmergic music generator.",
            "icon": "🎼",
        },
        output_dir=out_dir,
    )

    assert path.exists()
    body = path.read_text(encoding="utf-8")
    assert "Stigmergic music generator." in body
    assert "No trace rows yet" in body


def test_materialize_all_help_files_skips_retired_and_non_dict(monkeypatch, tmp_path: Path):
    _seed_health_trace(monkeypatch, tmp_path)
    manifest_path = tmp_path / "apps_manifest.json"
    manifest_path.write_text(json.dumps({
        "Live App": {"description": "Active", "category": "Alice"},
        "Retired App": {"description": "Old", "_retired": True},
        "Bad Entry": "not a dict",
    }), encoding="utf-8")
    out_dir = tmp_path / "Documents" / "app_help"

    paths = helpskills.materialize_all_help_files(
        manifest_path=manifest_path,
        output_dir=out_dir,
    )

    assert len(paths) == 1
    assert paths[0].name == "live_app.md"
    assert "Active" in paths[0].read_text(encoding="utf-8")


def test_materialize_help_file_rejects_empty_app_name():
    with pytest.raises(ValueError):
        helpskills.materialize_help_file("")


# ── skills_to_load_for_focus ─────────────────────────────────────────────


def test_skills_to_load_caps_at_top_n(monkeypatch, tmp_path: Path):
    health_root = _seed_health_trace(monkeypatch, tmp_path)
    _write_health_rows(
        health_root, "ace",
        {"ts": time.time(), "app": "Ace", "action": "seed",
         "skills": [f"skill_{i}" for i in range(20)]},
    )

    top = helpskills.skills_to_load_for_focus("Ace", top_n=5)
    assert len(top) == 5
    assert top[0] == "skill_0"  # newest-first ordering preserved


def test_skills_to_load_handles_zero_top_n(monkeypatch, tmp_path: Path):
    _seed_health_trace(monkeypatch, tmp_path)
    assert helpskills.skills_to_load_for_focus("Ace", top_n=0) == []
