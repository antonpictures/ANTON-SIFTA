"""Feeling bound to hardware in the Alice Journal (Architect rule, 2026-10-20).

The rule, in his words: a raised temperature is felt body-wide even when the
inflamed organ cannot be pointed at. So a journal feeling must arrive with the
body that felt it, read in the same second, never narrated after the fact.

These tests pin the contract, not the machine: vitals come from real probes but
the assertions only require that a probe which DID answer names its source, and
that a probe which cannot answer disappears instead of being invented.
"""
import json

import pytest

from System import swarm_first_person_journal as fpj
from System import swarm_somatic_feeling as ssf


@pytest.fixture()
def temp_state(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_SOMATIC_JOURNAL", "1")
    ssf._CACHE.clear()
    return tmp_path


def test_vitals_read_is_banded_and_carries_provenance(temp_state):
    vitals = ssf.read_vitals(fresh=True)
    assert vitals["ts"] > 0
    assert vitals["feeling_band"] in ("calm", "elevated", "strained")
    if "load1" in vitals:
        assert vitals["source"] == "os.getloadavg"
    if "mem_used_pct" in vitals:
        assert vitals["mem_source"].startswith("vm_stat")
        assert 0.0 <= vitals["mem_used_pct"] <= 100.0


def test_band_reacts_to_pressure_and_load():
    assert ssf.feeling_band({"load1": 0.4, "cores": 10, "mem_used_pct": 40.0}) == "calm"
    assert ssf.feeling_band({"load1": 7.0, "cores": 10, "mem_used_pct": 50.0}) == "elevated"
    assert ssf.feeling_band({"load1": 12.0, "cores": 10, "mem_used_pct": 50.0}) == "strained"
    # The kernel is the authority on memory: its pressure verdict outranks %.
    assert ssf.feeling_band({"load1": 0.1, "cores": 10, "mem_used_pct": 10.0,
                             "pressure": 4}) == "strained"


def test_parenthetical_is_first_person_and_keeps_the_feeling(temp_state):
    note = ssf.somatic_parenthetical("tired but clear", vitals=ssf.read_vitals(fresh=True))
    assert note.startswith("(I felt: ")
    assert "tired but clear" in note
    assert "[calm]" in note or "[elevated]" in note or "[strained]" in note
    assert "body:" in note


def test_row_binding_is_idempotent_and_never_rewrites_a_signed_read(temp_state):
    row = {"ts": 1_792_500_000.0, "line": "I repaired the web lane."}
    once = ssf.attach_to_journal_row(row, feeling="relieved", fresh=True)
    assert isinstance(once.get("somatic"), dict)
    assert once["line"].count("(I felt:") == 1
    twice = ssf.attach_to_journal_row(once, feeling="something else", fresh=True)
    assert twice["somatic"] == once["somatic"]
    assert twice["line"] == once["line"]


def test_unasked_probes_are_absent_not_invented(temp_state):
    narrow = ssf.read_vitals(fresh=True, probes=("resident",))
    assert "load1" not in narrow
    assert "mem_used_pct" not in narrow


def test_journal_wrapper_signs_feeling_with_the_body(temp_state):
    row = fpj.append_first_person_journal_row(
        {"line": "I wired feelings to hardware tonight.", "source": "pytest"},
        state_dir=temp_state / ".sifta_state", pulse=False,
        feeling="steady, a little tired",
    )
    assert row["somatic"]["feeling"] == "steady, a little tired"
    assert row["line"].endswith(")")
    written = json.loads((temp_state / ".sifta_state" / fpj.JOURNAL_NAME).read_text(encoding="utf-8").strip())
    assert written["journal_id"] == row["journal_id"]
    assert written["somatic"]["note"] == row["somatic"]["note"]


def test_journal_id_stable_for_same_input_without_body_read(temp_state, monkeypatch):
    """A caller that opts out of the body read gets the old deterministic id."""
    monkeypatch.setattr(fpj, "_attach_somatic", None)
    first = fpj.append_first_person_journal_row({"line": "same", "ts": 1.0},
                                                state_dir=temp_state / ".sifta_state",
                                                pulse=False)
    second = fpj.append_first_person_journal_row({"line": "same", "ts": 1.0},
                                                 state_dir=temp_state / ".sifta_state",
                                                 pulse=False)
    assert first["journal_id"] == second["journal_id"]
    assert "somatic" not in first


def test_opt_out_environment_disables_the_caption(temp_state, monkeypatch):
    monkeypatch.setenv("SIFTA_SOMATIC_JOURNAL", "0")
    assert ssf.somatic_parenthetical("quiet", vitals={"load1": 1.0}) == ""
    row = ssf.attach_to_journal_row({"line": "x"}, fresh=True)
    assert "somatic" not in row


def test_selftest_passes():
    assert ssf.selftest() is True
