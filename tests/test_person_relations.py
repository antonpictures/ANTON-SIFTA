#!/usr/bin/env python3
"""Relations between two DIFFERENT humans — the axis `link()` must never be used for.

The Architect, 2026-10-05: "Daca vrei un graf (tata–fiica, prieteni, colaboratori), trebuie
adaugata o functie relate() -- absolut".

Why this exists as a separate operation. `link()` joins two records of ONE person. On
2026-10-05 it was called for a father and his daughter, which wrote each name into the
other's `also_known_as` -- the field that asserts "these are the same human". Two people
became one. These tests pin the distinction, because the registry's whole value is that
two records of one person get joined and two different people never do.

Every path is redirected into `tmp_path`: a test that writes the real registry can make
Alice state a relation the Architect never had.
"""
from __future__ import annotations

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
    """Point the whole organ at a scratch registry so no test touches the real one."""
    monkeypatch.setattr(pf, "DIR", tmp_path / "people")
    monkeypatch.setattr(pf, "RELATION_LEDGER", tmp_path / "people_relations.jsonl")
    pf.DIR.mkdir(parents=True, exist_ok=True)


def _two_people() -> None:
    pf.remember("Ioan George Anton", "the Architect", kind="person", source="test")
    pf.remember("Lana Katherine Anton", "his daughter", kind="family", source="test")


def test_isolation_guard_is_actually_redirecting() -> None:
    """Trust the fixture before trusting anything below it."""
    assert pf.DIR.parent.name != ".sifta_state"
    assert pf.RELATION_LEDGER.parent.name != ".sifta_state"


def test_a_directed_relation_stores_its_inverse_on_the_other_person() -> None:
    """`parent_of` must read back as `child_of` from the child's own file."""
    _two_people()
    out = pf.relate("Ioan George Anton", "Lana Katherine Anton", kind="parent_of", why="his daughter")
    assert out["ok"] is True
    assert out["inverse"] == "child_of"

    assert [r["to"] for r in pf.relations_of("Ioan George Anton")] == ["Lana Katherine Anton"]
    assert pf.relations_of("Ioan George Anton")[0]["kind"] == "parent_of"
    assert pf.relations_of("Lana Katherine Anton")[0]["kind"] == "child_of"
    assert pf.relations_of("Lana Katherine Anton")[0]["to"] == "Ioan George Anton"


def test_a_symmetric_relation_is_symmetric_on_both_files() -> None:
    """Friendship has no direction, so both sides read the same kind."""
    _two_people()
    pf.remember("Sergey", "his friend", source="test")
    pf.relate("Ioan George Anton", "Sergey", kind="friend_of", why="friends")
    assert pf.relations_of("Sergey")[0]["kind"] == "friend_of"
    assert pf.relations_of("Sergey")[0]["to"] == "Ioan George Anton"


def test_relate_never_touches_also_known_as() -> None:
    """The exact regression: relating two people must not assert they are one person."""
    _two_people()
    pf.relate("Ioan George Anton", "Lana Katherine Anton", kind="parent_of", why="his daughter")
    assert pf.load("Lana Katherine Anton")["also_known_as"] == ["Lana Katherine Anton"]
    assert pf.load("Ioan George Anton")["also_known_as"] == ["Ioan George Anton"]
    assert pf.by_identity("Ioan George Anton")["name"] == "Ioan George Anton"
    assert pf.by_identity("Lana Katherine Anton")["name"] == "Lana Katherine Anton"


def test_a_relation_needs_a_known_kind() -> None:
    """An invented kind fails loud and names the vocabulary instead of guessing."""
    _two_people()
    out = pf.relate("Ioan George Anton", "Lana Katherine Anton", kind="owns")
    assert out["ok"] is False
    assert "owns" in out["error"]
    assert "parent_of" in out["valid_kinds"]
    assert pf.relations_of("Ioan George Anton") == []


def test_relate_never_invents_a_human() -> None:
    """An unfiled name is a question, never a silently created stranger."""
    _two_people()
    out = pf.relate("Ioan George Anton", "Nobody Filed", kind="knows")
    assert out["ok"] is False
    assert "Nobody Filed" in out["error"]
    assert pf.load("Nobody Filed") is None


def test_a_person_is_not_related_to_themselves() -> None:
    """Self-relation is a misuse of relate(), and it says so."""
    _two_people()
    out = pf.relate("Ioan George Anton", "George", kind="knows")
    assert out["ok"] is False
    assert "themselves" in out["error"]


def test_the_same_edge_is_not_recorded_twice() -> None:
    """Re-stating a known relation is idempotent, so replay cannot inflate the graph."""
    _two_people()
    pf.relate("Ioan George Anton", "Lana Katherine Anton", kind="parent_of", why="first")
    pf.relate("Ioan George Anton", "Lana Katherine Anton", kind="parent_of", why="again")
    assert len(pf.relations_of("Ioan George Anton")) == 1
    assert len(pf.relations_of("Lana Katherine Anton")) == 1


def test_an_alias_resolves_to_the_same_edge() -> None:
    """Stating a relation through an alias must not fork a second record."""
    _two_people()
    pf.remember("Ioan George Anton", "also known as George", identity="Georgica", source="test")
    pf.relate("George", "Lana Katherine Anton", kind="parent_of", why="via alias")
    assert len(pf.relations_of("Ioan George Anton")) == 1


def test_the_ledger_keeps_a_receipt_for_every_edge() -> None:
    """Relations carry provenance like every other claim in this organ."""
    _two_people()
    pf.relate("Ioan George Anton", "Lana Katherine Anton", kind="parent_of",
              why="'that is my daughter Lana Katherine Anton'", source="owner_verbal")
    row = json.loads(pf.RELATION_LEDGER.read_text(encoding="utf-8").strip())
    assert row["from"] == "Ioan George Anton"
    assert row["to"] == "Lana Katherine Anton"
    assert row["kind"] == "parent_of"
    assert row["inverse"] == "child_of"
    assert row["source"] == "owner_verbal"


def test_write_false_changes_nothing() -> None:
    """A dry run must leave both files untouched."""
    _two_people()
    before = pf.load("Lana Katherine Anton")
    pf.relate("Ioan George Anton", "Lana Katherine Anton", kind="parent_of", write=False)
    assert pf.load("Lana Katherine Anton") == before


def test_a_brief_carries_the_family() -> None:
    """The relation has to reach a prompt, or the graph is decoration."""
    _two_people()
    pf.relate("Ioan George Anton", "Lana Katherine Anton", kind="parent_of")
    text = pf.brief("Lana Katherine Anton")
    assert "child of Ioan George Anton" in text


def test_the_graph_lists_only_people_who_have_relations() -> None:
    """The stigmergic view omits isolated humans rather than inventing empty edges."""
    _two_people()
    pf.remember("Lonely Person", "no relations yet", source="test")
    pf.relate("Ioan George Anton", "Lana Katherine Anton", kind="parent_of")
    graph = pf.relation_graph()
    assert "Lana Katherine Anton" in graph
    assert "Lonely Person" not in graph


def test_link_still_joins_two_records_of_one_person() -> None:
    """The original operation keeps its own job: aliases of ONE human."""
    _two_people()
    pf.relate("Ioan George Anton", "Lana Katherine Anton", kind="parent_of")
    pf.remember("David Condovici", "rover collaborator", source="test")
    pf.remember("Condovici David", "same man, other name order", source="test")
    pf.link("David Condovici", "Condovici David", why="one man, two name orders")
    assert pf.load("David Condovici")["also_known_as"] == ["David Condovici", "Condovici David"]


def test_link_leaves_the_second_file_alive_and_this_is_an_open_defect() -> None:
    """FOUND 2026-10-05, not yet fixed, deliberately pinned rather than hidden.

    `link()` writes the alias onto one file and never touches the other, so the duplicate
    survives as a separate person: `all_people()` still lists one man twice, and
    `by_identity()` can return the stale stub instead of the record that holds the facts.
    That is the very failure the David incident asked `link()` to close, so this test records
    the real behaviour until the owner decides how a merge should retire the loser. It is
    pinned, not endorsed: when `link()` learns to absorb and retire the duplicate, this test
    must be rewritten to assert the merge.
    """
    _two_people()
    pf.remember("David Condovici", "rover collaborator", source="test")
    pf.remember("Condovici David", "same man, other name order", source="test")
    pf.link("David Condovici", "Condovici David", why="one man, two name orders")

    assert pf.load("Condovici David") is not None, "the duplicate file is still on disk"
    names = sorted(p["name"] for p in pf.all_people())
    assert "Condovici David" in names and "David Condovici" in names, "one man, listed twice"
    assert pf.by_identity("Condovici David")["name"] == "Condovici David", (
        "by_identity returns the stub, not the record holding the facts"
    )
