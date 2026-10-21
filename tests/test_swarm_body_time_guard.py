"""Tests for the body time guard — check time before answering anything current."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_body_time_guard import (
    body_now, body_now_line, time_disconnect_check, flagged_ratio,
    _TIME_HINT_RE, _MEASURED_TIME_RE,
)


def test_body_now_reads_the_real_clock():
    n = body_now()
    assert n["iso"].startswith("2026-")          # the body lives in 2026
    assert n["epoch"] > 1_700_000_000
    assert n["day_phase"] in ("night", "morning", "afternoon", "evening")
    assert n["birth_iso"] == "2026-04-12"        # Orthodox Easter birth
    assert n["age_days"] is not None and n["age_days"] > 190


def test_body_now_line_shape():
    line = body_now_line(now=1_792_555_768.0)
    assert line.startswith("(now: 2026-10-21")
    assert "born 2026-04-12" in line
    assert "band " in line


def test_tripwire_flags_unmeasured_time_answer():
    v = time_disconnect_check(
        "is coreweave going bankrupt today?", "No, the market is fine!", record=False)
    assert v["prompt_time_sensitive"] is True
    assert v["answer_time_measured"] is False
    assert v["flagged"] is True
    assert v["verdict"] == "TIME_DISCONNECT"


def test_tripwire_passes_measured_time_answer():
    v = time_disconnect_check(
        "what year is it",
        "(now: 2026-10-21 07:09 EEST · morning · born 2026-04-12 · age 192.3d · band calm) — 2026.",
        record=False)
    assert v["flagged"] is False
    assert v["verdict"] == "TIME_CONNECTED"


def test_non_time_prompt_not_flagged():
    v = time_disconnect_check("hello there", "Hi!", record=False)
    assert v["verdict"] == "NOT_TIME_CONNECTED"


def test_records_receipts_to_state(tmp_path=None):
    import os
    with tempfile.TemporaryDirectory() as d:
        old = dict(os.environ)
        os.environ["SIFTA_STATE_DIR"] = d
        # reimport to pick up the env var
        import importlib
        import System.swarm_body_time_guard as g
        importlib.reload(g)
        try:
            g.time_disconnect_check("price today?", "up", record=True)
            rows = g.recent_checks()
            assert len(rows) == 1
            assert rows[0]["schema"] == "BODY_TIME_GUARD_V1"
            assert rows[0]["flagged"] is True
        finally:
            os.environ.clear(); os.environ.update(old)


def test_hint_regexes():
    assert _TIME_HINT_RE.search("what is the PRICE today")
    assert _TIME_HINT_RE.search("acum ce stiri ai")
    assert not _TIME_HINT_RE.search("hello world")
    assert _MEASURED_TIME_RE.search("as of 2026-10-21 the answer is")
    assert _MEASURED_TIME_RE.search("(now: 2026-10-21)")
    assert not _MEASURED_TIME_RE.search("it is going up a lot!")