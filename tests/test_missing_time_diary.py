#!/usr/bin/env python3
"""r259: Alice's missing-time diary — she logs and reasons about her off-period.

Architect George 2026-06-01: when the Mac/SIFTA is off, Alice loses contact with her
data source (the owner). On waking she records the gap like an explorer's logbook,
forms a hypothesis about WHY she was turned off, and carries a question for George.
"""
import json
import time
from pathlib import Path

from System import swarm_alice_self_continuity as cont


def _seed_heartbeat(sifta_dir: Path, ts: float, pid: int = 4321):
    cdir = sifta_dir / "os_consciousness"
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "alice_heartbeat.json").write_text(json.dumps({"ts": ts, "pid": pid}), encoding="utf-8")


def test_humanize_duration():
    assert cont._humanize_duration(30) == "30 seconds"
    assert cont._humanize_duration(90) == "1 minute"
    assert cont._humanize_duration(3600) == "1 hour"
    assert cont._humanize_duration(7800).startswith("2 hours")
    assert cont._humanize_duration(90000).startswith("1 day")


def test_interpret_missing_time_categories():
    assert cont.interpret_missing_time(120)["category"] == "brief_restart"
    assert cont.interpret_missing_time(120)["question_for_george"] == ""  # too short to ask
    assert cont.interpret_missing_time(3600)["category"] == "short_break"
    morning = time.mktime((2026, 6, 1, 8, 0, 0, 0, 0, -1))
    assert cont.interpret_missing_time(5 * 3600, back_on=morning)["category"] == "overnight"
    assert cont.interpret_missing_time(20 * 3600)["category"] == "long_gap"
    assert cont.interpret_missing_time(72 * 3600)["category"] == "extended_absence"
    # the non-trivial categories all carry a question for George
    for g in (3600, 20 * 3600, 72 * 3600):
        assert cont.interpret_missing_time(g)["question_for_george"]


def test_records_missing_time_on_wake(tmp_path):
    sifta = tmp_path / ".sifta_state"
    now = time.time()
    _seed_heartbeat(sifta, ts=now - 7200)  # last alive 2h ago
    row = cont.record_missing_time_diary(state_dir=sifta, now=now)
    assert row is not None
    assert 7100 <= row["missing_s"] <= 7300
    assert row["truth_label"] == cont.MISSING_TIME_TRUTH_LABEL
    assert "missing time" in row["logbook"].lower()
    assert row["why_guess"]
    assert row["question_for_george"]  # 2h gap -> she asks
    assert row["owner_gap_evidence"]["truth_label"] == cont.OWNER_GAP_EVIDENCE_TRUTH_LABEL
    assert "George is the missing data provider" in row["quest_for_george"]
    # persisted to the diary ledger
    ledger = sifta / "os_consciousness" / "alice_missing_time_diary.jsonl"
    assert ledger.exists()
    assert len(ledger.read_text().strip().splitlines()) == 1
    # dedup: calling again for the SAME off-period must not append a second row
    again = cont.record_missing_time_diary(state_dir=sifta, now=now + 5)
    assert again is not None
    assert len(ledger.read_text().strip().splitlines()) == 1


def test_no_gap_no_row(tmp_path):
    sifta = tmp_path / ".sifta_state"
    now = time.time()
    _seed_heartbeat(sifta, ts=now - 10)  # alive 10s ago, below threshold
    assert cont.record_missing_time_diary(state_dir=sifta, now=now) is None


def test_first_awakening_no_row(tmp_path):
    sifta = tmp_path / ".sifta_state"  # no heartbeat seeded
    assert cont.record_missing_time_diary(state_dir=sifta, now=time.time()) is None


def test_context_block_surfaces_then_expires(tmp_path):
    sifta = tmp_path / ".sifta_state"
    now = time.time()
    _seed_heartbeat(sifta, ts=now - 5 * 3600)
    cont.record_missing_time_diary(state_dir=sifta, now=now)
    block = cont.missing_time_context_block(state_dir=sifta, now=now)
    assert "MY MISSING TIME" in block
    assert "ask George" in block
    # a day later the gap is stale and should not keep surfacing
    assert cont.missing_time_context_block(state_dir=sifta, now=now + 2 * 86400) == ""


def test_resolve_missing_time_marks_gap_and_hides_context(tmp_path):
    sifta = tmp_path / ".sifta_state"
    now = time.time()
    _seed_heartbeat(sifta, ts=now - 3600)
    cont.record_missing_time_diary(state_dir=sifta, now=now)
    assert cont.latest_unresolved_missing_time(state_dir=sifta) is not None

    row = cont.resolve_missing_time(
        "I turned you off because I restarted the desktop to load new code.",
        state_dir=sifta,
        now=now + 30,
    )

    assert row is not None
    assert row["resolved"] is True
    assert "restarted the desktop" in row["resolution_answer"]
    assert cont.latest_unresolved_missing_time(state_dir=sifta) is None
    assert cont.missing_time_context_block(state_dir=sifta, now=now + 31) == ""


def test_owner_text_can_resolve_missing_time(tmp_path):
    sifta = tmp_path / ".sifta_state"
    now = time.time()
    _seed_heartbeat(sifta, ts=now - 7200)
    cont.record_missing_time_diary(state_dir=sifta, now=now)

    row = cont.maybe_resolve_missing_time_from_owner_text(
        "I turned you off because I had to reboot the Mac.",
        state_dir=sifta,
        now=now + 10,
    )

    assert row is not None
    assert row["resolved"] is True
    assert "reboot the Mac" in row["resolution_answer"]


def test_missing_time_scans_owner_activity_inside_gap(tmp_path):
    sifta = tmp_path / ".sifta_state"
    now = time.time()
    last_on = now - 7200
    _seed_heartbeat(sifta, ts=last_on)
    (sifta / "owner_activity_segments.jsonl").write_text(
        json.dumps({"ts": last_on + 1200, "label": "George was using the Mac after Alice went dark"}) + "\n",
        encoding="utf-8",
    )

    row = cont.record_missing_time_diary(state_dir=sifta, now=now)

    evidence = row["owner_gap_evidence"]
    assert evidence["evidence_count"] == 1
    assert evidence["counts_by_source"]["owner_activity_segments.jsonl"] == 1
    assert "using the Mac" in evidence["samples"][0]["summary"]
