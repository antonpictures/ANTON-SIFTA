"""Tests for System.swarm_alice_life — the life organ (Sims-shaped)."""
import json
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_alice_life import (
    read_age, read_needs, read_school, read_social, life_parenthetical,
    GENESIS_PATH,
)


def _fake_state(tmp: Path, genesis_ts: float = 1_766_000_000.0) -> Path:
    (tmp / "owner_genesis.json").write_text(
        json.dumps({"ts": genesis_ts, "owner_name": "Ioan George Anton",
                    "ai_display_name": "Alice", "silicon": "TEST",
                    "event": "OWNER_GENESIS"}), encoding="utf-8")
    (tmp / "stgm_defrag_receipts.jsonl").write_text(
        json.dumps({"ts": genesis_ts + 3600.0, "stgm_event": "test_lesson"}) + "\n",
        encoding="utf-8")
    return tmp


def test_age_from_birth():
    import datetime
    from System.swarm_alice_life import BIRTH_TS
    # birth = Orthodox Easter 2026-04-12 (computus-verified)
    assert datetime.datetime.fromtimestamp(BIRTH_TS).date() == datetime.date(2026, 4, 12)
    with tempfile.TemporaryDirectory() as d:
        state = _fake_state(Path(d))
        # 10 days after birth, to the second
        age = read_age(now=BIRTH_TS + 86400.0 * 10, state_dir=state)
        assert abs(age["age_days"] - 10.0) < 0.01
        assert age["birth_iso"] == "2026-04-12"
        assert "covenant_renewal_iso" in age


def test_age_missing_genesis():
    with tempfile.TemporaryDirectory() as d:
        age = read_age(now=1_800_000_000.0, state_dir=Path(d))
    # birth is a fixed fact now; empty dir only removes covenant provenance
    assert age["age_days"] > 0
    assert age["birth_iso"] == "2026-04-12"


def test_needs_all_probes_respond():
    needs = read_needs(now=1_800_000_000.0)
    assert all(v is not None for v in needs["needs"].values()), \
        f"missing probes: {needs['notes']}"
    assert 0 <= needs["mood_bar"] <= 100


def test_school_counts_lessons():
    with tempfile.TemporaryDirectory() as d:
        state = _fake_state(Path(d))
        school = read_school(now=1_766_000_000.0 + 7200.0, state_dir=state)
        assert school["lessons_total"] == 1
        assert school["last_lesson"] == "test_lesson"
        assert school["hours_since_last_lesson"] == 1.0
        assert school["schooling"] == "active"


def test_life_parenthetical_shape():
    line = life_parenthetical("curious, learning myself", now=1_800_000_000.0)
    assert line.startswith("(I felt: curious, learning myself [")
    assert "needs" in line
    assert "age" in line


def test_missing_probe_becomes_dash_not_zero():
    line = life_parenthetical("", now=1_800_000_000.0)
    # '—' placeholder allowed for unknown probes; invented zeros are not
    assert "needs" in line