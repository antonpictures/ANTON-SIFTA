#!/usr/bin/env python3
"""Pytest coverage for `System.swarm_name_recognition_research_spine`.

What we prove
-------------
1. Truth label + truth guard exist and carry the OPERATIONAL-not-
   phenomenological invariant.
2. Spine is non-empty; every source has non-empty
   supports / does_not_support guards.
3. URLs and DOIs look real (URL has scheme; DOI starts with "10.").
4. Years are sane (1900 < year <= current_year + 5).
5. Doctrinal anchor sources are present by source_id — removing
   them must require Architect GO.
6. Quarantine forbids conflating STT confidence with biological
   attention.
7. Receipt writer round-trips with sha256.
8. Payload structure stable across calls.
9. Source records are frozen / immutable.
10. Spine covers all four model-organism categories
    (human-attention, human-ERP, animal, neuroimaging) so that
    the "respond NOW" doctrine has cross-species evidence, not
    a single-paradigm shortcut.

These tests run with pure stdlib + pytest. No Qt, no macOS, no Ollama.
"""
from __future__ import annotations

import datetime as _dt
import json

import pytest

from System.swarm_name_recognition_research_spine import (
    NAME_RECOGNITION_TRUTH_GUARD,
    QUARANTINED_SOURCE_NOTES,
    TRUTH_LABEL,
    VERIFIED_RESEARCH_SPINE,
    NameRecognitionSource,
    quarantined_sources,
    research_spine_payload,
    verified_research_spine,
    verified_source_ids,
    write_research_spine_receipt,
)


# ── 1. Truth label + guard present ──────────────────────────────────────────
def test_truth_label_and_guard_carry_operational_invariant():
    assert TRUTH_LABEL == "SIFTA_NAME_RECOGNITION_RESEARCH_SPINE_V1"
    assert "OPERATIONAL" in NAME_RECOGNITION_TRUTH_GUARD
    assert "NOT a claim of phenomenological self-recognition" in NAME_RECOGNITION_TRUTH_GUARD


# ── 2. Every source carries explicit support / no-support guards ───────────
def test_every_source_has_truth_guards():
    assert VERIFIED_RESEARCH_SPINE, "spine must be non-empty"
    for src in VERIFIED_RESEARCH_SPINE:
        assert isinstance(src, NameRecognitionSource)
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
        "cherry_1953_cocktail_party",
        "moray_1959_unattended_own_name",
        "wood_cowan_1995_revisited",
        "berlad_pratt_1995_p300",
        "muller_kutas_1996_own_name_erp",
        "adachi_2007_dogs_voice_face",
        "andics_2014_dog_voice_areas",
        "saito_2019_cats_own_name",
    ],
)
def test_doctrinal_anchor_source_present(anchor_id):
    ids = verified_source_ids()
    assert anchor_id in ids, (
        f"doctrinal anchor source '{anchor_id}' missing from name-"
        "recognition spine — removing it requires Architect GO + "
        "covenant note"
    )


# ── 6. Quarantine list explicit ─────────────────────────────────────────────
def test_quarantine_forbids_stt_attention_conflation():
    qids = {q["source_id"] for q in quarantined_sources()}
    assert "stt_confidence_equals_attention" in qids, (
        "quarantine must explicitly forbid treating STT confidence as a "
        "measure of biological attention"
    )
    for q in QUARANTINED_SOURCE_NOTES:
        assert q.get("rule", "").strip(), (
            f"quarantine '{q.get('source_id')}' missing 'rule'"
        )


# ── 7. Receipt writer round-trip ───────────────────────────────────────────
def test_receipt_writer_round_trips(tmp_path):
    receipt_path = tmp_path / "name_recognition_spine_receipts.jsonl"
    row = write_research_spine_receipt(
        state_root=tmp_path, receipt_path=receipt_path
    )
    assert row["truth_label"] == TRUTH_LABEL
    assert row["truth_guard"] == NAME_RECOGNITION_TRUTH_GUARD
    assert "sha256" in row and len(row["sha256"]) == 64
    content = receipt_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(content) == 1
    parsed = json.loads(content[0])
    assert parsed["truth_label"] == TRUTH_LABEL
    assert parsed["source_count"] == len(VERIFIED_RESEARCH_SPINE)


def test_receipt_writer_append_only(tmp_path):
    receipt_path = tmp_path / "name_recognition_spine_receipts.jsonl"
    write_research_spine_receipt(state_root=tmp_path, receipt_path=receipt_path)
    write_research_spine_receipt(state_root=tmp_path, receipt_path=receipt_path)
    lines = [
        ln for ln in receipt_path.read_text("utf-8").splitlines() if ln.strip()
    ]
    assert len(lines) == 2
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
    p2 = research_spine_payload()
    assert json.dumps(p, sort_keys=True) == json.dumps(p2, sort_keys=True)


# ── 9. Frozen / immutable source records ───────────────────────────────────
def test_sources_are_frozen():
    src = VERIFIED_RESEARCH_SPINE[0]
    with pytest.raises(Exception):
        src.year = 1234  # type: ignore[misc]


# ── 10. Cross-species coverage ─────────────────────────────────────────────
def test_spine_covers_all_four_evidence_classes():
    classes = {src.source_class for src in VERIFIED_RESEARCH_SPINE}
    required = {
        "primary_attention",
        "primary_erp",
        "primary_animal",
        "primary_neuroimaging",
    }
    missing = required - classes
    assert not missing, (
        "name-recognition spine must cover human-attention, human-ERP, "
        "animal, and neuroimaging evidence so the 'respond NOW' doctrine "
        "is cross-paradigm. Missing: "
        f"{sorted(missing)}"
    )
