"""Tests for direct time/date skill (task #51).

Architect 2026-05-14: "if I ask Alice what's the date what's the time
she knows how to get that right and to answer separate — like answer
what's the date, tell me what the time."
"""
import datetime as _dt
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_alice_time_date_skill import (
    LEDGER_NAME,
    TRUTH_LABEL,
    answer_and_journal,
    answer_time_or_date,
    classify_time_or_date_intent,
)


# ── Intent classification ────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("What time is it?", "time"),
    ("what time is it", "time"),
    ("tell me the time", "time"),
    ("current time please", "time"),
    ("how late is it?", "time"),
    ("got the time?", "time"),
    ("What's the time?", "time"),
])
def test_time_intents_classified(text, expected):
    assert classify_time_or_date_intent(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("What's the date?", "date"),
    ("what is the date today", "date"),
    ("today's date please", "date"),
    ("current date", "date"),
    ("what day is it", "date"),
    ("what date is today", "date"),
])
def test_date_intents_classified(text, expected):
    assert classify_time_or_date_intent(text) == expected


@pytest.mark.parametrize("text", [
    "tell me the date and time",
    "what's the date and time?",
    "time and date please",
    "Tell me both the date and time.",
])
def test_both_intent_classified(text):
    assert classify_time_or_date_intent(text) == "both"


@pytest.mark.parametrize("text", [
    "Explain the MAMMAL paper",
    "Show me the receipts",
    "How does the cortex work?",
    "",
    "   ",
])
def test_non_time_date_returns_none(text):
    assert classify_time_or_date_intent(text) is None


def test_none_input_returns_none():
    assert classify_time_or_date_intent(None) is None  # type: ignore[arg-type]


# ── Answer composition ──────────────────────────────────────────

def test_answer_time_at_fixed_moment():
    moment = _dt.datetime(2026, 5, 14, 11, 47, 0)  # 11:47 AM
    out = answer_time_or_date("time", now=moment)
    assert out == "It's 11:47 AM."


def test_answer_date_at_fixed_moment():
    moment = _dt.datetime(2026, 5, 14, 11, 47, 0)
    out = answer_time_or_date("date", now=moment)
    assert out == "It's Thursday, May 14, 2026."


def test_answer_both_at_fixed_moment():
    moment = _dt.datetime(2026, 5, 14, 11, 47, 0)
    out = answer_time_or_date("both", now=moment)
    assert out == "It's 11:47 AM on Thursday, May 14, 2026."


def test_answer_strips_leading_zero_in_hour():
    moment = _dt.datetime(2026, 5, 14, 7, 5, 0)  # 7:05 AM, not 07:05
    out = answer_time_or_date("time", now=moment)
    assert out == "It's 7:05 AM."
    assert not out.startswith("It's 0")


def test_answer_strips_leading_zero_in_day_of_month():
    moment = _dt.datetime(2026, 5, 4, 11, 47, 0)  # May 4, not May 04
    out = answer_time_or_date("date", now=moment)
    assert out == "It's Monday, May 4, 2026."


def test_answer_evening_pm():
    moment = _dt.datetime(2026, 5, 14, 22, 30, 0)  # 10:30 PM
    out = answer_time_or_date("time", now=moment)
    assert out == "It's 10:30 PM."


def test_answer_no_intent_returns_empty():
    assert answer_time_or_date("", now=_dt.datetime.now()) == ""


# ── Full pipeline: detect → answer → journal ────────────────────

def test_pipeline_writes_journal_row_with_importance(tmp_path):
    moment = _dt.datetime(2026, 5, 14, 11, 47, 0)
    out = answer_and_journal(
        "What time is it?",
        source="voice",
        now=moment,
        state_root=tmp_path,
    )
    assert out.fired is True
    assert out.intent == "time"
    assert out.answer == "It's 11:47 AM."
    assert out.importance == 0.05  # UTILITY
    assert out.importance_label == "UTILITY"
    # Journal row written
    ledger = tmp_path / LEDGER_NAME
    assert ledger.exists()
    row = json.loads(ledger.read_text().strip().splitlines()[-1])
    assert row["importance"] == 0.05
    assert row["importance_label"] == "UTILITY"
    assert row["intent"] == "time"
    assert row["answer_text"] == "It's 11:47 AM."
    assert row["skill"] == TRUTH_LABEL
    assert row["iso_timestamp"] == "2026-05-14T11:47:00"


def test_pipeline_does_not_journal_when_no_intent(tmp_path):
    out = answer_and_journal(
        "Explain MAMMAL", source="typed", state_root=tmp_path,
    )
    assert out.fired is False
    assert out.answer == ""
    ledger = tmp_path / LEDGER_NAME
    assert not ledger.exists()


def test_pipeline_carries_iso_timestamp(tmp_path):
    moment = _dt.datetime(2026, 5, 14, 7, 32, 54, 502836)
    out = answer_and_journal(
        "What time is it?", now=moment, source="voice", state_root=tmp_path,
    )
    assert out.iso_timestamp == "2026-05-14T07:32:54.502836"


def test_pipeline_journal_row_has_trace_id(tmp_path):
    out = answer_and_journal(
        "What's the date?", source="voice", state_root=tmp_path,
    )
    assert out.journal_row is not None
    assert "trace_id" in out.journal_row
    assert len(out.journal_row["trace_id"]) >= 16  # uuid string


def test_pipeline_no_write_flag_doesnt_create_ledger(tmp_path):
    out = answer_and_journal(
        "What time is it?", source="voice", state_root=tmp_path, write=False,
    )
    assert out.fired is True
    assert out.answer
    # No ledger created
    assert not (tmp_path / LEDGER_NAME).exists()


def test_pipeline_preserves_existing_journal_schema(tmp_path):
    """The new journal rows must include the standard fields so existing
    consumers (memory gravity, dream organ) still work."""
    moment = _dt.datetime(2026, 5, 14, 11, 47, 0)
    out = answer_and_journal(
        "What time is it?", now=moment, source="voice", state_root=tmp_path,
    )
    row = out.journal_row
    assert row is not None
    # Existing schema fields
    assert "ts" in row
    assert "date" in row
    assert "time" in row
    assert "line" in row
    assert "source" in row
    assert "source_hash" in row
    assert "truth_label" in row
    # And the new importance fields
    assert "importance" in row
    assert "importance_label" in row


# ── Determinism ─────────────────────────────────────────────────

def test_same_moment_same_answer():
    """Same datetime → exactly same string."""
    moment = _dt.datetime(2026, 5, 14, 11, 47, 0)
    a = answer_time_or_date("both", now=moment)
    b = answer_time_or_date("both", now=moment)
    assert a == b


# ── Truth boundary ──────────────────────────────────────────────

def test_truth_label_is_v1():
    assert TRUTH_LABEL == "TIME_DATE_SKILL_V1"


def test_truth_boundary_in_module():
    from System.swarm_alice_time_date_skill import TRUTH_BOUNDARY
    assert "clock" in TRUTH_BOUNDARY.lower()
    assert "operational" in TRUTH_BOUNDARY.lower()
