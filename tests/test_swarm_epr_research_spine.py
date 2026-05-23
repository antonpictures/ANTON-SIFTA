#!/usr/bin/env python3
"""Pytest coverage for `System.swarm_epr_research_spine`.

What we prove
-------------
1. The truth label and truth guard exist and carry the SIM_ONLY invariant.
2. The verified spine is non-empty and every source has a non-empty
   supports / does_not_support guard.
3. Every source carries a real-looking URL or DOI (URL must contain a
   schema; DOI, when present, must start with "10.").
4. Years are sane (1900 < year <= current_year + 5 for in-press preprints).
5. The doctrinal anchor sources are present by source_id — removing them
   would break SIFTA's EPR claim hygiene and must require Architect GO.
6. The quarantine list explicitly forbids loophole-free replica claims.
7. The receipt writer round-trips: writes a JSONL row with sha256 digest,
   re-readable as JSON, with `truth_label` and `truth_guard` preserved.
8. The payload structure is stable: keys present, source counts match
   tuple length, no hidden mutation between calls.

These tests run with pure stdlib + pytest. No Qt, no macOS, no Ollama.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest

from System.swarm_epr_research_spine import (
    EPR_ANALOGUE_TRUTH_GUARD,
    QUARANTINED_SOURCE_NOTES,
    TRUTH_LABEL,
    VERIFIED_RESEARCH_SPINE,
    EPRResearchSource,
    quarantined_sources,
    research_spine_payload,
    verified_research_spine,
    verified_source_ids,
    write_research_spine_receipt,
)


# ── 1. Truth label + guard present ──────────────────────────────────────────
def test_truth_label_and_guard_carry_sim_only_invariant():
    assert TRUTH_LABEL == "SIFTA_EPR_RESEARCH_SPINE_V1"
    assert "SIM_ONLY" in EPR_ANALOGUE_TRUTH_GUARD
    assert "does not prove the physical cause" in EPR_ANALOGUE_TRUTH_GUARD


# ── 2. Every source carries explicit support / no-support guards ───────────
def test_every_source_has_truth_guards():
    assert VERIFIED_RESEARCH_SPINE, "spine must be non-empty"
    for src in VERIFIED_RESEARCH_SPINE:
        assert isinstance(src, EPRResearchSource)
        assert src.source_id, f"{src.title}: empty source_id"
        assert src.supports.strip(), f"{src.source_id}: empty supports guard"
        assert src.does_not_support.strip(), (
            f"{src.source_id}: empty does_not_support guard — every source "
            "must declare what it must NOT be used to claim"
        )


# ── 3. URLs and DOIs look real ─────────────────────────────────────────────
def test_urls_and_dois_are_well_formed():
    for src in VERIFIED_RESEARCH_SPINE:
        assert src.url.startswith(("http://", "https://")), (
            f"{src.source_id}: url missing scheme — '{src.url}'"
        )
        if src.doi:
            assert src.doi.startswith("10."), (
                f"{src.source_id}: doi must start with '10.' if present "
                f"— got '{src.doi}'"
            )


# ── 4. Years are sane ──────────────────────────────────────────────────────
def test_years_in_realistic_range():
    cur = _dt.datetime.now().year
    for src in VERIFIED_RESEARCH_SPINE:
        assert 1900 < src.year <= cur + 5, (
            f"{src.source_id}: year {src.year} outside [1901..{cur + 5}]"
        )


# ── 5. Doctrinal anchor sources present ────────────────────────────────────
@pytest.mark.parametrize(
    "anchor_id",
    [
        "epr_1935",
        "bohm_1951",
        "aspect_1982",
        "hensen_2015_loophole_free",
        "giustina_2015_significant_loophole_free",
        "shalm_2015_strong_loophole_free",
        "wiseman_2007_steering",
        "cavalcanti_2009_steering_criteria",
    ],
)
def test_doctrinal_anchor_source_present(anchor_id):
    ids = verified_source_ids()
    assert anchor_id in ids, (
        f"doctrinal anchor source '{anchor_id}' missing from EPR spine — "
        "removing it requires Architect GO + covenant note"
    )


# ── 6. Quarantine list explicit ─────────────────────────────────────────────
def test_quarantine_forbids_replica_claims():
    qids = {q["source_id"] for q in quarantined_sources()}
    assert "any_loophole_free_replica_claim" in qids, (
        "quarantine must explicitly forbid claims that the SIFTA EPR "
        "simulator replicates / supersedes Hensen / Giustina / Shalm 2015"
    )
    # Each quarantine entry must carry a rule.
    for q in QUARANTINED_SOURCE_NOTES:
        assert q.get("rule", "").strip(), (
            f"quarantine '{q.get('source_id')}' missing 'rule'"
        )


# ── 7. Receipt writer round-trip ───────────────────────────────────────────
def test_receipt_writer_round_trips(tmp_path):
    receipt_path = tmp_path / "epr_spine_receipts.jsonl"
    row = write_research_spine_receipt(
        state_root=tmp_path, receipt_path=receipt_path
    )
    assert row["truth_label"] == TRUTH_LABEL
    assert row["truth_guard"] == EPR_ANALOGUE_TRUTH_GUARD
    assert "sha256" in row and len(row["sha256"]) == 64
    # File must contain exactly one line that re-parses to a dict.
    content = receipt_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(content) == 1
    parsed = json.loads(content[0])
    assert parsed["truth_label"] == TRUTH_LABEL
    assert parsed["source_count"] == len(VERIFIED_RESEARCH_SPINE)


def test_receipt_writer_append_only(tmp_path):
    receipt_path = tmp_path / "epr_spine_receipts.jsonl"
    write_research_spine_receipt(state_root=tmp_path, receipt_path=receipt_path)
    write_research_spine_receipt(state_root=tmp_path, receipt_path=receipt_path)
    lines = [
        ln for ln in receipt_path.read_text("utf-8").splitlines() if ln.strip()
    ]
    assert len(lines) == 2
    # SHA256 of two receipts written at different timestamps must differ.
    a = json.loads(lines[0])
    b = json.loads(lines[1])
    assert a["sha256"] != b["sha256"]


# ── 8. Payload structure stable ────────────────────────────────────────────
def test_payload_structure_stable():
    p = research_spine_payload()
    for key in (
        "truth_label", "truth_guard", "verified_sources",
        "quarantined_sources", "source_count", "quarantine_count",
    ):
        assert key in p, f"payload missing key '{key}'"
    assert p["source_count"] == len(VERIFIED_RESEARCH_SPINE)
    assert p["quarantine_count"] == len(QUARANTINED_SOURCE_NOTES)
    # Calling again must produce a structurally identical (deep) payload.
    p2 = research_spine_payload()
    assert json.dumps(p, sort_keys=True) == json.dumps(p2, sort_keys=True)


# ── 9. Frozen / immutable source records ───────────────────────────────────
def test_sources_are_frozen():
    src = VERIFIED_RESEARCH_SPINE[0]
    with pytest.raises(Exception):
        # frozen=True dataclass: attempt to mutate must raise
        src.year = 1234  # type: ignore[misc]
