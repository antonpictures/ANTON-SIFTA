"""Tests for System/swarm_bio_world_model.py (Event 111)."""

from __future__ import annotations

import json

from System import swarm_bio_world_model as bwm


def test_manifest_has_formula_and_research_topics() -> None:
    m = bwm.get_manifest()
    assert m.get("formula_revision") == "111"
    assert m.get("truth_label")
    assert len(m.get("research_plan_anchors", [])) >= 2
    assert len(bwm.RESEARCH_PLAN_ANCHORS) >= 2


def test_deposit_bio_world_update_writes_ledger(tmp_path) -> None:
    row = bwm.deposit_bio_world_update({"event": "test_111", "note": "pytest"}, state_dir=tmp_path)
    assert row["truth_label"] == bwm.LEDGER_TRUTH
    assert row["homeworld_serial"]
    assert row["event"] == "test_111"
    path = tmp_path / bwm._BIO_WORLD_LOG_NAME
    assert path.exists()
    line = path.read_text(encoding="utf-8").strip().splitlines()[-1]
    loaded = json.loads(line)
    assert loaded["truth_label"] == bwm.LEDGER_TRUTH
    assert loaded["formula_revision"] == "111"


def test_get_bio_world_summary_observed_bounded(tmp_path) -> None:
    s = bwm.get_bio_world_summary(state_dir=tmp_path)
    assert s["truth_label"] == bwm.SUMMARY_TRUTH
    assert 0.0 <= s["organism_health"] <= 1.0
    assert isinstance(s["active_organs"], list)
    assert s["bio_claims_rows_observed"] >= 0
    assert s["skill_primitives_rows_observed"] >= 0
    assert s["rlhf_cutoff_rate_observed"] is None or 0.0 <= s["rlhf_cutoff_rate_observed"] <= 1.0


def test_bio_world_model_os_facade() -> None:
    m = bwm.BioWorldModelOS.get_manifest()
    assert m["name"] == "SIFTA_BIO_WORLD_MODEL_OS"
