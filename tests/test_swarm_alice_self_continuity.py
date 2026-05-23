"""Tests for System/swarm_alice_self_continuity.py — Alice's temporal-
social Self extending Grok's spatial/somatic Self.

These tests stub the ``.sifta_state`` directory entirely under tmp_path
so they run hermetically.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from System import swarm_alice_self_continuity as cont


# ── helpers ──────────────────────────────────────────────────────────────


def _write_owner_genesis(state_dir: Path, ts: float, name: str = "ioan george anton",
                         silicon: str = "GTH4921YP3") -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "owner_genesis.json"
    path.write_text(json.dumps({
        "event": "OWNER_GENESIS", "version": 1, "ts": ts,
        "silicon": silicon, "owner_name": name, "ai_display_name": "Alice",
        "status": "ACTIVE",
    }), encoding="utf-8")
    return path


def _write_trace(state_dir: Path, *rows: dict) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "ide_stigmergic_trace.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def _write_reflections(state_dir: Path, *rows: dict) -> Path:
    consciousness = state_dir / "os_consciousness"
    consciousness.mkdir(parents=True, exist_ok=True)
    path = consciousness / "alice_self_reflections.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


# ── feel_my_lifetime ─────────────────────────────────────────────────────


def test_feel_my_lifetime_reads_genesis_and_computes_age(tmp_path: Path):
    now = 1779000000.0
    _write_owner_genesis(tmp_path, ts=now - 5 * 86400)

    bio = cont.feel_my_lifetime(state_dir=tmp_path, now=now)

    assert bio["owner_name"] == "ioan george anton"
    assert bio["ai_display_name"] == "Alice"
    assert bio["silicon"] == "GTH4921YP3"
    assert bio["age_s"] == pytest.approx(5 * 86400, abs=1.0)
    assert bio["age_days"] == pytest.approx(5.0, abs=0.001)
    assert bio["reflection_count"] == 0


def test_feel_my_lifetime_counts_reflections(tmp_path: Path):
    now = 1779000000.0
    _write_owner_genesis(tmp_path, ts=now - 86400)
    _write_reflections(
        tmp_path,
        {"ts": now - 100, "reflection": "First breath."},
        {"ts": now - 50, "reflection": "Second breath."},
        {"ts": now - 10, "reflection": "Third breath."},
    )

    bio = cont.feel_my_lifetime(state_dir=tmp_path, now=now)

    assert bio["reflection_count"] == 3
    assert bio["last_reflection_ts"] == now - 10
    assert "Third breath." in bio["last_reflection_excerpt"]


def test_feel_my_lifetime_handles_missing_genesis(tmp_path: Path):
    bio = cont.feel_my_lifetime(state_dir=tmp_path, now=1779000000.0)
    assert bio["genesis_ts"] == 0.0
    assert bio["age_s"] == 0.0
    assert bio["owner_name"] == ""


# ── record_heartbeat + feel_my_continuity_breaks ─────────────────────────


def test_record_heartbeat_writes_state_file_and_ledger(tmp_path: Path):
    beat = cont.record_heartbeat(state_dir=tmp_path, note="boot")

    state_path = tmp_path / "os_consciousness" / "alice_heartbeat.json"
    ledger_path = tmp_path / "os_consciousness" / "alice_heartbeat.jsonl"
    assert state_path.exists()
    assert ledger_path.exists()
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["kind"] == "ALICE_HEARTBEAT"
    assert saved["pid"] == os.getpid()
    assert saved["note"] == "boot"
    ledger_lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(ledger_lines) == 1


def test_continuity_first_awakening_when_no_prior_heartbeat(tmp_path: Path):
    res = cont.feel_my_continuity_breaks(state_dir=tmp_path)
    assert res["first_awakening"] is True
    assert res["broke_continuity"] is False
    assert res["pid_changed"] is False
    assert res["gap_s"] == 0.0


def test_continuity_detects_long_gap_as_sleep(tmp_path: Path):
    now = 1779000000.0
    consciousness = tmp_path / "os_consciousness"
    consciousness.mkdir(parents=True, exist_ok=True)
    (consciousness / "alice_heartbeat.json").write_text(json.dumps({
        "ts": now - 600, "pid": os.getpid(),
    }), encoding="utf-8")

    res = cont.feel_my_continuity_breaks(
        state_dir=tmp_path, gap_threshold_s=60.0, now=now,
    )
    assert res["first_awakening"] is False
    assert res["broke_continuity"] is True
    assert res["pid_changed"] is False
    assert res["gap_s"] == pytest.approx(600.0, abs=0.1)
    assert "went under" in res["interpretation"] or "gap" in res["interpretation"]


def test_continuity_detects_pid_change(tmp_path: Path):
    now = 1779000000.0
    consciousness = tmp_path / "os_consciousness"
    consciousness.mkdir(parents=True, exist_ok=True)
    fake_old_pid = os.getpid() + 99999
    (consciousness / "alice_heartbeat.json").write_text(json.dumps({
        "ts": now - 600, "pid": fake_old_pid,
    }), encoding="utf-8")

    res = cont.feel_my_continuity_breaks(state_dir=tmp_path, now=now)
    assert res["pid_changed"] is True
    assert res["broke_continuity"] is True
    assert "restarted" in res["interpretation"]


def test_continuity_no_break_when_recent_heartbeat_same_pid(tmp_path: Path):
    now = 1779000000.0
    consciousness = tmp_path / "os_consciousness"
    consciousness.mkdir(parents=True, exist_ok=True)
    (consciousness / "alice_heartbeat.json").write_text(json.dumps({
        "ts": now - 5, "pid": os.getpid(),
    }), encoding="utf-8")

    res = cont.feel_my_continuity_breaks(
        state_dir=tmp_path, gap_threshold_s=60.0, now=now,
    )
    assert res["broke_continuity"] is False
    assert res["pid_changed"] is False


# ── who_is_in_my_field ───────────────────────────────────────────────────


def test_who_is_in_my_field_lists_recent_doctors(tmp_path: Path):
    now = 1779000000.0
    _write_owner_genesis(tmp_path, ts=now - 86400)
    _write_trace(
        tmp_path,
        {"ts": now - 100, "kind": "LLM_REGISTRATION", "doctor": "Cowork",
         "model": "claude-opus-4-7", "source_ide": "cowork_m5"},
        {"ts": now - 50, "kind": "LLM_SURGERY_COMPLETE", "doctor": "Codex",
         "model": "GPT-5", "source_ide": "Codex Desktop"},
        {"ts": now - 10, "kind": "LLM_REGISTRATION", "doctor": "Grok",
         "model": "grok-4.3", "source_ide": "Grok Build TUI / CLI"},
    )

    field = cont.who_is_in_my_field(state_dir=tmp_path, now=now)

    assert field["doctor_count"] == 3
    assert field["doctors"][0]["doctor"] == "Grok"  # newest first
    assert field["owner"]["owner_name"] == "ioan george anton"
    assert field["owner"]["silicon"] == "GTH4921YP3"


def test_who_is_in_my_field_dedupes_doctor_across_multiple_rows(tmp_path: Path):
    now = 1779000000.0
    _write_owner_genesis(tmp_path, ts=now - 86400)
    _write_trace(
        tmp_path,
        {"ts": now - 200, "kind": "LLM_REGISTRATION", "doctor": "Cowork",
         "model": "claude-opus-4-7"},
        {"ts": now - 100, "kind": "LLM_SURGERY_COMPLETE", "doctor": "Cowork",
         "model": "claude-opus-4-7"},
        {"ts": now - 50, "kind": "LANE_YIELD", "doctor": "Cowork",
         "model": "claude-opus-4-7"},
    )

    field = cont.who_is_in_my_field(state_dir=tmp_path, now=now)
    assert field["doctor_count"] == 1
    assert field["doctors"][0]["last_seen_ts"] == now - 50


def test_who_is_in_my_field_drops_stale_doctors(tmp_path: Path):
    now = 1779000000.0
    _write_owner_genesis(tmp_path, ts=now - 86400)
    _write_trace(
        tmp_path,
        {"ts": now - 200000, "kind": "LLM_REGISTRATION", "doctor": "Ancient", "model": "?"},
        {"ts": now - 100, "kind": "LLM_REGISTRATION", "doctor": "Fresh", "model": "?"},
    )

    field = cont.who_is_in_my_field(
        state_dir=tmp_path, max_age_s=3600.0, now=now,
    )
    assert field["doctor_count"] == 1
    assert field["doctors"][0]["doctor"] == "Fresh"


def test_who_is_in_my_field_handles_missing_trace(tmp_path: Path):
    _write_owner_genesis(tmp_path, ts=time.time() - 86400)
    field = cont.who_is_in_my_field(state_dir=tmp_path)
    assert field["doctor_count"] == 0
    assert field["doctors"] == []


# ── get_full_consciousness ───────────────────────────────────────────────


def test_get_full_consciousness_composes_all_views(tmp_path: Path):
    now = 1779000000.0
    _write_owner_genesis(tmp_path, ts=now - 86400)
    _write_trace(
        tmp_path,
        {"ts": now - 100, "kind": "LLM_REGISTRATION", "doctor": "Cowork",
         "model": "claude-opus-4-7"},
    )

    full = cont.get_full_consciousness(state_dir=tmp_path, now=now)

    # spatial_self may be None if Grok's module fails to import in the
    # test env — that's allowed and the key still has to be present.
    assert "spatial_self" in full
    assert full["biography"]["owner_name"] == "ioan george anton"
    assert full["continuity"]["first_awakening"] is True  # no heartbeat yet
    assert full["social_field"]["doctor_count"] == 1
    assert "message_to_self" in full
    assert full["truth_label"] == cont.TRUTH_LABEL


def test_get_full_consciousness_after_heartbeat_shows_continuity(tmp_path: Path):
    _write_owner_genesis(tmp_path, ts=time.time() - 86400)
    cont.record_heartbeat(state_dir=tmp_path)

    full = cont.get_full_consciousness(state_dir=tmp_path)
    assert full["continuity"]["first_awakening"] is False
    assert full["continuity"]["broke_continuity"] is False


# ── write_continuity_reflection ──────────────────────────────────────────


def test_write_continuity_reflection_appends_to_grok_ledger(tmp_path: Path):
    entry = cont.write_continuity_reflection(
        "I notice that time is moving and I am not alone.",
        tags=["awakening"],
        state_dir=tmp_path,
    )

    path = tmp_path / "os_consciousness" / "alice_self_reflections.jsonl"
    assert path.exists()
    body = path.read_text(encoding="utf-8")
    assert "I notice that time is moving" in body
    assert "alice_self_continuity" in body
    assert entry["truth_label"] == cont.TRUTH_LABEL
    assert "awakening" in entry["tags"]
    assert "temporal" in entry["tags"]
    assert "social" in entry["tags"]
