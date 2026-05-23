import json
from pathlib import Path

from System.swarm_bell_research_spine import (
    BELL_ANALOGUE_TRUTH_GUARD,
    quarantined_sources,
    research_spine_payload,
    verified_source_ids,
    write_research_spine_receipt,
)


def test_research_spine_has_bell_chsh_and_contextual_controls():
    ids = set(verified_source_ids())

    assert "bell_1964" in ids
    assert "chsh_1969" in ids
    assert "hall_2010_measurement_dependence" in ids
    assert "papatryfonos_2024_pilot_wave_bell" in ids
    assert "sulis_khan_2023_collective_contextuality" in ids


def test_research_spine_quarantines_unverified_eqfi():
    quarantined = {row["source_id"]: row for row in quarantined_sources()}

    assert "eqfi_academia_2025" in quarantined
    assert quarantined["eqfi_academia_2025"]["status"] == "unverified_quarantine"
    assert "Do not use as proof-bearing" in quarantined["eqfi_academia_2025"]["rule"]


def test_research_spine_truth_guard_stays_sim_only():
    payload = research_spine_payload()

    assert "SIM_ONLY classical contextual analogue" in BELL_ANALOGUE_TRUTH_GUARD
    assert "does not prove the physical cause" in payload["truth_guard"]
    assert payload["truth_label"] == "SIFTA_BELL_RESEARCH_SPINE_V1"
    assert payload["source_count"] >= 8
    assert payload["quarantine_count"] >= 1


def test_write_research_spine_receipt(tmp_path: Path):
    receipt = write_research_spine_receipt(receipt_path=tmp_path / "spine.jsonl")

    saved = json.loads((tmp_path / "spine.jsonl").read_text(encoding="utf-8"))
    assert saved["trace_id"] == receipt["trace_id"]
    assert saved["sha256"] == receipt["sha256"]
    assert saved["kind"] == "BELL_RESEARCH_SPINE_RECEIPT"
    assert saved["verified_sources"][0]["source_id"] == "bell_1964"
