#!/usr/bin/env python3
"""r287: receipts as living memory cells — strength decays, reuse reinforces.

Pins the derived ecology over the strict receipt lane: recent/reused receipts are strong,
unused ones decay by half-life, an explicit reference resets the clock (reinforcement), and
only load-bearing receipts are handed to the existing consolidation organs. The four canonical
ledgers are never mutated — this is a read-derived view + a separate reference index.
"""
import json

from System import swarm_receipt_memory_ecology as eco

NOW = 1_000_000_000.0
DAY = 86400.0


def _seed(tmp_path):
    sdir = tmp_path / ".sifta_state"
    sdir.mkdir(parents=True, exist_ok=True)
    rows = [
        {"ts": NOW, "receipt_id": "r-recent", "summary": "x"},
        {"ts": NOW - 14 * DAY, "receipt_id": "r-old", "summary": "x"},   # 2 half-lives old
        {"ts": NOW - 3600, "receipt_id": "r-reused", "summary": "x"},
        {"ts": NOW - 1800, "receipt_id": "r-reused", "summary": "x"},
        {"ts": NOW - 60, "receipt_id": "r-reused", "summary": "x"},
    ]
    (sdir / "work_receipts.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return tmp_path


def test_recent_beats_old_and_counts_reuse(tmp_path):
    _seed(tmp_path)
    rows = eco.receipt_ecology(state_dir=tmp_path, now=NOW)
    by = {r["receipt_id"]: r for r in rows}
    assert by["r-recent"]["strength"] > by["r-old"]["strength"]
    assert 0.2 < by["r-old"]["strength"] < 0.3            # ~0.25 at two 7-day half-lives
    assert by["r-reused"]["reinforcement_count"] == 3
    assert rows[0]["strength"] >= rows[-1]["strength"]    # sorted strongest first


def test_reinforce_resets_the_decay_clock(tmp_path):
    _seed(tmp_path)
    before = eco.receipt_strength("r-old", state_dir=tmp_path, now=NOW)
    eco.reinforce("r-old", note="referenced again", state_dir=tmp_path, now=NOW)
    after = {r["receipt_id"]: r for r in eco.receipt_ecology(state_dir=tmp_path, now=NOW)}
    assert after["r-old"]["strength"] > 0.9               # clock reset -> strong again
    assert after["r-old"]["strength"] > before
    assert after["r-old"]["reinforcement_count"] == 2     # original row + 1 reference


def test_consolidation_candidates_are_load_bearing_only(tmp_path):
    _seed(tmp_path)
    cand = {r["receipt_id"]
            for r in eco.consolidation_candidates(state_dir=tmp_path, now=NOW, min_strength=0.5)}
    assert "r-recent" in cand and "r-reused" in cand
    assert "r-old" not in cand                            # decayed below the promote threshold


def test_block_speaks_the_field(tmp_path):
    _seed(tmp_path)
    blk = eco.receipt_ecology_block(state_dir=tmp_path, now=NOW)
    assert "RECEIPT MEMORY ECOLOGY" in blk
    assert "r-recent" in blk


def test_reads_all_four_canonical_ledgers(tmp_path):
    sdir = tmp_path / ".sifta_state"
    sdir.mkdir(parents=True, exist_ok=True)
    for ledger_name in eco.CANONICAL_LEDGER_NAMES:
        (sdir / ledger_name).write_text(
            json.dumps({"ts": NOW, "receipt_id": "r-fanout", "ledger_name": ledger_name}) + "\n",
            encoding="utf-8",
        )

    row = {r["receipt_id"]: r for r in eco.receipt_ecology(state_dir=tmp_path, now=NOW)}["r-fanout"]

    assert row["reinforcement_count"] == len(eco.CANONICAL_LEDGER_NAMES)
    assert row["ledger_count"] == len(eco.CANONICAL_LEDGER_NAMES)
    assert set(row["source_ledgers"]) == set(eco.CANONICAL_LEDGER_NAMES)


def test_reads_iso_timestamp_rows_from_real_ledgers(tmp_path):
    sdir = tmp_path / ".sifta_state"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "work_receipts.jsonl").write_text(
        json.dumps({
            "ts": "2026-05-10T14:19:55-0700",
            "receipt_id": "r-iso-time",
            "summary": "older ledger dialect",
        }) + "\n",
        encoding="utf-8",
    )

    rows = {r["receipt_id"]: r for r in eco.receipt_ecology(state_dir=tmp_path, now=NOW)}

    assert "r-iso-time" in rows
    assert rows["r-iso-time"]["last_ts"] > 0
