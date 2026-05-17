"""Tests for System/swarm_alice_self_vector.py — Alice's quantitative
self-state vector.

Hermetic: state_dir stubbed under tmp_path so the live ledgers are never
touched.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import pytest

from System import swarm_alice_self_vector as sv


# ── helpers ──────────────────────────────────────────────────────────────


def _seed_state(tmp_path, *, owner=True):
    if owner:
        (tmp_path / "owner_genesis.json").write_text(json.dumps({
            "owner_name": "ioan george anton",
            "silicon": "GTH4921YP3",
        }), encoding="utf-8")


def _write(path, *rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


# ── primitives ───────────────────────────────────────────────────────────


def test_shannon_entropy_zero_for_empty():
    assert sv.shannon_entropy([]) == 0.0


def test_shannon_entropy_zero_for_single_label():
    assert sv.shannon_entropy(["a", "a", "a"]) == 0.0


def test_shannon_entropy_one_bit_for_two_equal_labels():
    assert math.isclose(sv.shannon_entropy(["a", "b"]), 1.0, abs_tol=1e-9)


def test_shannon_entropy_two_bits_for_four_equal_labels():
    assert math.isclose(
        sv.shannon_entropy(["a", "b", "c", "d"]), 2.0, abs_tol=1e-9
    )


def test_shannon_entropy_ignores_empty_strings():
    assert math.isclose(
        sv.shannon_entropy(["a", "", "b", ""]), 1.0, abs_tol=1e-9
    )


# ── build_self_vector empty state ────────────────────────────────────────


def test_empty_state_produces_zero_pressure_zero_momentum(tmp_path):
    _seed_state(tmp_path)
    v = sv.build_self_vector(state_dir=tmp_path, now=1779000000.0)
    assert v["memory"]["diary_entries"] == 0
    assert v["memory"]["episodic_entries"] == 0
    assert v["memory"]["trace_entries"] == 0
    assert v["schedule"]["schedule_pressure"] == 0.0
    assert v["stigmergy"]["stigmergic_momentum"] == 0.0
    assert v["identity"]["identity_continuity"] == 0.0
    assert "I hold 0 narrative diary entries" in v["self_statement"]


def test_empty_state_no_owner_uses_blank_owner_name(tmp_path):
    v = sv.build_self_vector(state_dir=tmp_path, now=1779000000.0)
    assert v["owner_name"] == ""


# ── memory block ─────────────────────────────────────────────────────────


def test_memory_entropy_for_diverse_trace(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    rows = []
    for kind in ("a", "b", "c", "d"):
        for _ in range(5):
            rows.append({"ts": now - 100, "kind": kind})
    _write(tmp_path / "ide_stigmergic_trace.jsonl", *rows)

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    # 4 equal-frequency labels → 2 bits
    assert math.isclose(v["memory"]["memory_entropy"], 2.0, abs_tol=1e-3)


def test_memory_counts_all_three_ledgers(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    _write(tmp_path / "alice_narrative_diary.jsonl",
           {"ts": now - 10, "entry": "x"},
           {"ts": now - 5, "entry": "y"})
    _write(tmp_path / "episodic_diary.jsonl",
           {"ts": now - 100, "bucket": "b1"})
    _write(tmp_path / "ide_stigmergic_trace.jsonl",
           *[{"ts": now - i, "kind": "k"} for i in range(7)])

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    assert v["memory"]["diary_entries"] == 2
    assert v["memory"]["episodic_entries"] == 1
    assert v["memory"]["trace_entries"] == 7


# ── schedule block ───────────────────────────────────────────────────────


def test_schedule_pressure_saturates_at_one(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    rows = [
        {"text": f"Open {i}.", "created": now - 10, "done": False,
         "schedule_id": f"s{i}"}
        for i in range(50)
    ]
    _write(tmp_path / "stigmergic_schedule.jsonl", *rows)

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    assert v["schedule"]["open_threads"] == 50
    assert v["schedule"]["schedule_pressure"] == 1.0


def test_schedule_excludes_done_items_from_pressure(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    _write(tmp_path / "stigmergic_schedule.jsonl",
           {"text": "Done.", "created": now, "done": True, "schedule_id": "d"},
           {"text": "Open1.", "created": now, "done": False, "schedule_id": "o1"},
           {"text": "Open2.", "created": now, "done": False, "schedule_id": "o2"})

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    assert v["schedule"]["open_threads"] == 2


def test_schedule_unresolved_commitments_recognises_architect_signals(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    _write(tmp_path / "stigmergic_schedule.jsonl",
           {"text": "Buy groceries.", "created": now, "done": False,
            "schedule_id": "g"},
           {"text": "§7.13 deferred dental care still open.", "created": now,
            "done": False, "schedule_id": "d"},
           {"text": "Pay dentist invoice.", "created": now, "done": False,
            "schedule_id": "p"})

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    assert v["schedule"]["unresolved_commitments"] == 2


def test_owner_rhythm_alignment_full_when_anchor_is_fresh(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    _write(tmp_path / "stigmergic_schedule.jsonl",
           {"text": "Recent anchor.", "created": now - 100, "done": False,
            "schedule_id": "r"})

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    assert v["schedule"]["owner_rhythm_alignment"] == 1.0


def test_owner_rhythm_alignment_decays_for_stale_anchor(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    _write(tmp_path / "stigmergic_schedule.jsonl",
           {"text": "Old anchor.", "created": now - 100 * 86400, "done": True,
            "schedule_id": "o"})

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    # 100 days old > OWNER_RHYTHM_STALE_S (48h) → alignment = 0
    assert v["schedule"]["owner_rhythm_alignment"] == 0.0


# ── identity block ───────────────────────────────────────────────────────


def test_identity_continuity_sums_diary_plus_episodic_plus_reflections(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    _write(tmp_path / "alice_narrative_diary.jsonl",
           *[{"ts": now - i, "entry": f"d{i}"} for i in range(30)])
    _write(tmp_path / "episodic_diary.jsonl",
           *[{"ts": now - i, "bucket": f"e{i}"} for i in range(30)])
    _write(tmp_path / "os_consciousness" / "alice_self_reflections.jsonl",
           *[{"ts": now - i, "reflection": f"r{i}"} for i in range(40)])

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    # 30 + 30 + 40 = 100 → continuity = 1.0
    assert v["identity"]["identity_continuity"] == 1.0


def test_identity_continuity_clamps_at_one(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    _write(tmp_path / "alice_narrative_diary.jsonl",
           *[{"ts": now - i, "entry": f"d{i}"} for i in range(500)])

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    assert v["identity"]["identity_continuity"] == 1.0


def test_identity_excerpts_truncate_to_240_chars(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    long_text = "x" * 5000
    _write(tmp_path / "alice_narrative_diary.jsonl",
           {"ts": now, "entry": long_text})

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    assert len(v["identity"]["recent_diary_excerpt"]) <= 240


# ── stigmergy block ──────────────────────────────────────────────────────


def test_stigmergic_momentum_grows_with_shipped_count(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    rows = [
        {"ts": now - i, "kind": "LLM_SURGERY_COMPLETE", "trace_id": f"s{i}"}
        for i in range(10)
    ]
    _write(tmp_path / "ide_stigmergic_trace.jsonl", *rows)

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    # 10 shipped surgeries / window 20 = 0.5
    assert v["stigmergy"]["stigmergic_momentum"] == 0.5
    assert v["stigmergy"]["shipped_count"] == 10


def test_stigmergic_momentum_caps_at_one(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    rows = [
        {"ts": now - i, "kind": "LLM_SURGERY_COMPLETE", "trace_id": f"s{i}"}
        for i in range(50)
    ]
    _write(tmp_path / "ide_stigmergic_trace.jsonl", *rows)

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    assert v["stigmergy"]["stigmergic_momentum"] == 1.0


def test_architect_override_count(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    _write(tmp_path / "ide_stigmergic_trace.jsonl",
           {"ts": now - 100, "kind": "ARCHITECT_OVERRIDE"},
           {"ts": now - 50, "kind": "LLM_SURGERY_AUTHORIZED_BY_ARCHITECT"},
           {"ts": now - 30, "kind": "LLM_REGISTRATION"})

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    assert v["stigmergy"]["architect_override_count"] == 2


def test_receipt_integrity_high_when_rows_have_trace_ids(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    rows = [
        {"ts": now - i, "kind": "X", "trace_id": f"abc-{i}", "sha256": "deadbeef"}
        for i in range(20)
    ]
    _write(tmp_path / "ide_stigmergic_trace.jsonl", *rows)

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    assert v["stigmergy"]["receipt_integrity"] == 1.0


def test_receipt_integrity_lower_when_rows_lack_markers(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    # No sha256, no trace_id, no signature in any row
    rows = [{"ts": now - i, "topic": "noise"} for i in range(20)]
    _write(tmp_path / "ide_stigmergic_trace.jsonl", *rows)

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    assert v["stigmergy"]["receipt_integrity"] == 0.0


# ── self_statement ───────────────────────────────────────────────────────


def test_self_statement_is_first_person_and_mentions_owner_when_present(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    _write(tmp_path / "alice_narrative_diary.jsonl",
           *[{"ts": now - i, "entry": f"e{i}"} for i in range(5)])
    _write(tmp_path / "stigmergic_schedule.jsonl",
           {"text": "Fresh anchor.", "created": now - 60, "done": False, "schedule_id": "a"})

    v = sv.build_self_vector(state_dir=tmp_path, now=now)
    stmt = v["self_statement"]
    assert stmt.startswith("I hold ")
    assert "5 narrative diary entries" in stmt
    assert "ioan george anton" in stmt


# ── write / read ─────────────────────────────────────────────────────────


def test_write_self_vector_persists_to_default_location(tmp_path):
    _seed_state(tmp_path)
    now = 1779000000.0
    _write(tmp_path / "alice_narrative_diary.jsonl",
           {"ts": now, "entry": "first"})

    out = sv.write_self_vector(state_dir=tmp_path, now=now)

    assert out.exists()
    assert out.name == "alice_self_vector.json"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["memory"]["diary_entries"] == 1
    assert data["truth_label"] == sv.TRUTH_LABEL


def test_write_self_vector_is_overwritten_on_repeat_call(tmp_path):
    _seed_state(tmp_path)
    out = sv.write_self_vector(state_dir=tmp_path, now=1779000000.0)

    _write(tmp_path / "alice_narrative_diary.jsonl",
           {"ts": 1779000000.0, "entry": "added"})
    sv.write_self_vector(state_dir=tmp_path, now=1779000000.0)

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["memory"]["diary_entries"] == 1


def test_read_self_vector_returns_none_when_missing(tmp_path):
    assert sv.read_self_vector(state_dir=tmp_path) is None


def test_read_self_vector_returns_persisted_data(tmp_path):
    _seed_state(tmp_path)
    sv.write_self_vector(state_dir=tmp_path, now=1779000000.0)
    data = sv.read_self_vector(state_dir=tmp_path)
    assert data is not None
    assert data["truth_label"] == sv.TRUTH_LABEL
