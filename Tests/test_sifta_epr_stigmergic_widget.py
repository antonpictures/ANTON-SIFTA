from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _load_epr_module():
    repo = Path(__file__).resolve().parent.parent
    path = repo / "Applications" / "sifta_epr_stigmergic_widget.py"
    spec = importlib.util.spec_from_file_location("sifta_epr_stigmergic_widget", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_epr_experiment_writes_sim_only_receipt(tmp_path: Path):
    mod = _load_epr_module()
    ledger = tmp_path / "epr_receipts.jsonl"
    exp = mod.EPRStigmergicExperiment(seed=7, receipt_path=ledger, receipt_stride=0)

    for _ in range(8):
        exp.run_batch(n_per_setting=2)
    row = exp.write_receipt()

    assert row["truth_label"] == "SIFTA_EPR_STIGMERGIC_ANALOGUE_V1"
    assert "not a physical proof" in row["limit_note"]
    assert "not quantum identity" in row["claim"]
    assert row["research_spine_available"] is True
    assert row["research_spine_source_count"] >= 8
    assert "SIM_ONLY" in row["research_spine_truth_guard"]
    assert set(row["s"]) == {"lhv", "qm", "stig"}
    assert row["signature"]

    saved = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert saved["chain_hash"] == exp.chain_hash
    assert saved["truth_label"] == row["truth_label"]
    spine_receipt = tmp_path / "epr_research_spine_receipts.jsonl"
    assert spine_receipt.exists()
    assert json.loads(spine_receipt.read_text(encoding="utf-8").splitlines()[-1])["truth_label"] == "SIFTA_EPR_RESEARCH_SPINE_V1"


def test_epr_referee_separates_lhv_qm_and_stig_contextual_regions(tmp_path: Path):
    mod = _load_epr_module()
    row = mod.run_epr_referee(
        seed=11,
        batches=140,
        n_per_setting=3,
        receipt_path=tmp_path / "referee.jsonl",
    )

    assert row["referee"]["lhv_bound_obeyed"] is True
    assert row["referee"]["qm_reaches_epr_bell_region"] is True
    assert row["referee"]["stig_contextual_region"] is True
    assert row["referee"]["physical_claim"] is False
    assert abs(row["s"]["lhv"]) <= 2.15
    assert abs(row["s"]["qm"]) > 2.35
    assert abs(row["s"]["stig"]) > 2.20


def test_epr_same_axis_anticorrelation_emerges_from_contextual_field(tmp_path: Path):
    mod = _load_epr_module()
    exp = mod.EPRStigmergicExperiment(
        seed=5,
        receipt_path=tmp_path / "same_axis.jsonl",
        receipt_stride=0,
    )

    for _ in range(120):
        exp.run_pair(0.0, 0.0, "same_axis")

    metrics = exp.metrics()
    assert metrics["epr_same_axis_stig"] < -0.75
    assert metrics["research_spine_available"] is True
    assert metrics["assumption_audit"]["physical_cause_claim"] is False
    assert metrics["assumption_audit"]["measurement_independence_relaxed"] is True


def test_epr_manifest_entry_is_embedded_simulation():
    repo = Path(__file__).resolve().parent.parent
    manifest = json.loads((repo / "Applications" / "apps_manifest.json").read_text())
    entry = manifest["EPR Paradox — Stigmergic Dissolution"]

    assert entry["category"] == "Simulations"
    assert entry["entry_point"] == "Applications/sifta_epr_stigmergic_widget.py"
    assert entry["widget_class"] == "EPRStigmergicWidget"
    assert entry["autostart"] is False
    assert "SIM_ONLY" in entry["description"]
    assert "does not claim the physical cause" in entry["description"]


def test_epr_widget_language_is_not_physical_cause_claim():
    mod = _load_epr_module()

    assert "SIM_ONLY" in mod._SIM_LIMIT_NOTE
    assert "not a physical proof" in mod._SIM_LIMIT_NOTE
    assert "cause claim" in mod._SIM_LIMIT_NOTE
    assert "Proof of Quantum Non-Locality" not in (mod.EPRStigmergicWidget.__doc__ or "")


def test_epr_widget_instantiates_offscreen():
    mod = _load_epr_module()
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    widget = mod.EPRStigmergicWidget()
    try:
        widget.timer.stop()
        widget._tick()
        app.processEvents()
        assert widget.experiment.total_pairs > 0
        assert widget.canvas is not None
    finally:
        widget.deleteLater()
        app.processEvents()
