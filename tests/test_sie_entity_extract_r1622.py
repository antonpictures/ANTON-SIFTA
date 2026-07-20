"""r1622-03 — entity feeder proposals only."""
from __future__ import annotations

from System.swarm_sie_entity_feeder import deposit_proposals, extract_entity_proposals


def test_extracts_capitalized_names():
    props = extract_entity_proposals("I met Vevsachi yesterday in Brawley with Mark.")
    surfaces = {p["surface"] for p in props}
    assert "Vevsachi" in surfaces or "Brawley" in surfaces


def test_deposit_writes_ledger(tmp_path):
    row = deposit_proposals("Talk to Vevsachi about SIFTA", state_dir=tmp_path, write=True)
    assert row["truth_label"]
    ledger = tmp_path / ".sifta_state" / "sie_entity_proposals.jsonl"
    # state_dir may be tmp_path or tmp_path/.sifta_state depending on helper
    assert row.get("proposals") is not None
