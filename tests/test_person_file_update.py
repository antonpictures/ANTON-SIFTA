#!/usr/bin/env python3
"""The person's file is updated, not only read, when Alice answers them on WhatsApp.

The Architect, 2026-10-05: "fi sigura cand raspunzi pe whatsapp to the person, have his
stigmergic file data ready and updated."

The answer lane already looked the person up before it spoke — that is the "ready" half, and it
was in place. The "updated" half was missing entirely: the lane wrote to its own receipts and to
the first-person journal, and never back to the human's file, so a file held the day it was
created and nothing of what passed between them since.

Matching is exact by design. Everywhere else in this organ a fuzzy near-match is a question,
never an action; writing a fact to a near-match would be acting on one, and it would put a
stranger's words into someone else's file.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import System.swarm_person_file as pf  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A scratch registry: a test must never append to a real human's file."""
    monkeypatch.setattr(pf, "DIR", tmp_path / "people")
    monkeypatch.setattr(pf, "RELATION_LEDGER", tmp_path / "people_relations.jsonl")
    pf.DIR.mkdir(parents=True, exist_ok=True)


def test_isolation_guard_is_actually_redirecting() -> None:
    """Trust the fixture before trusting anything below it."""
    assert pf.DIR.parent.name != ".sifta_state"


def test_an_exchange_is_written_onto_the_persons_file() -> None:
    """What they said and what was answered both land, with the time and the channel.

    The alias is established first because that is the real dependency: the label that arrives
    on WhatsApp is the push name "David", while the file is keyed "David Condovici". The live
    registry carries that alias, so the test builds the same state instead of inventing a
    looser match inside note_exchange().
    """
    pf.remember("David Condovici", "rover collaborator", source="test")
    pf.link("David Condovici", "David", why="the push name his messages arrive under")
    out = pf.note_exchange(
        "David", "mai vine George pe la rover?", "Da, azi lucreaza la el.",
        channel="whatsapp group", identity="253158408360157@lid", when=1_700_000_000.0,
    )
    assert out["ok"] is True
    assert out["person"] == "David Condovici"

    person = pf.load("David Condovici")
    exchange = [f for f in person["facts"] if f["kind"] == "whatsapp_exchange"]
    assert len(exchange) == 1
    fact = exchange[0]["fact"]
    assert "mai vine George pe la rover?" in fact
    assert "Da, azi lucreaza la el." in fact
    assert "whatsapp group" in fact
    assert "253158408360157@lid" in fact


def test_the_jid_is_recorded_so_the_next_lookup_resolves_by_identity() -> None:
    """The "ready" half depends on this: a jid seen once must resolve thereafter."""
    pf.remember("David Condovici", "rover collaborator", source="test")
    pf.link("David Condovici", "David", why="the push name his messages arrive under")
    assert pf.by_identity("253158408360157@lid") is None
    pf.note_exchange("David", "salut", "salut", identity="253158408360157@lid")
    assert pf.by_identity("253158408360157@lid")["name"] == "David Condovici"


def test_an_unknown_name_is_refused_rather_than_filed_against_a_near_match() -> None:
    """A stranger's words must never land in someone else's file."""
    pf.remember("David Condovici", "rover collaborator", source="test")
    out = pf.note_exchange("Davi", "cine esti?", "nu stiu")
    assert out["ok"] is False
    assert "exactly" in out["error"]
    assert [f for f in pf.load("David Condovici")["facts"] if f["kind"] == "whatsapp_exchange"] == []


def test_an_empty_name_is_refused() -> None:
    """No name, no file, and it says so instead of guessing."""
    assert pf.note_exchange("", "salut", "salut")["ok"] is False
    assert pf.note_exchange("   ", "salut", "salut")["ok"] is False


def test_write_false_changes_nothing() -> None:
    """A dry run leaves the file exactly as it was."""
    pf.remember("David Condovici", "rover collaborator", source="test")
    before = pf.load("David Condovici")
    pf.note_exchange("David", "salut", "salut", write=False)
    assert pf.load("David Condovici") == before


def test_the_answer_lane_updates_the_file_only_after_delivery() -> None:
    """Read the lane's source and pin that the update sits inside the delivered branch.

    A reply that never reached the phone must not be remembered as having happened, so the call
    belongs after the bridge confirmed ok — not beside the prompt assembly.
    """
    path = REPO / "System" / "swarm_whatsapp_answer_lane.py"
    source = path.read_text(encoding="utf-8")
    assert "from System.swarm_person_file import note_exchange" in source
    delivered = source.index('if receipt["ok"]:')
    update = source.index("note_exchange(")
    assert update > delivered, "the write must sit inside the delivered branch"
    assert "person_file" in source, "the receipt must record whether the file was updated"


def test_the_organ_compiles_and_exposes_the_writer() -> None:
    """The lane imports it by name; a rename here would break replies silently."""
    assert callable(pf.note_exchange)
    assert "note_exchange" in (REPO / "System" / "swarm_person_file.py").read_text(encoding="utf-8")
