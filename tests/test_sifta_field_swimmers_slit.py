from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _load_module():
    repo = Path(__file__).resolve().parent.parent
    path = repo / "Applications" / "sifta_field_swimmers_slit.py"
    spec = importlib.util.spec_from_file_location("sifta_field_swimmers_slit", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_pair(mod, *, steps: int = 500, width: int = 200, height: int = 120):
    double = mod.FieldSwimmerExperiment(seed=11, two_slits=True, width=width, height=height)
    single = mod.FieldSwimmerExperiment(seed=11, two_slits=False, width=width, height=height)
    for _ in range(steps):
        double.tick()
        single.tick()
    return double, single


def test_field_primary_slit_separates_double_from_single_detector_pattern():
    mod = _load_module()
    double, single = _run_pair(mod)

    d_metrics = double.metrics()
    s_metrics = single.metrics()
    max_delta = float(np.max(np.abs(double.detector_pattern() - single.detector_pattern())))

    assert d_metrics["truth_label"] == "SIFTA_FIELD_SWIMMERS_SLIT_V2"
    assert d_metrics["peak_count"] >= s_metrics["peak_count"] + 2
    assert d_metrics["detector_total"] > s_metrics["detector_total"]
    assert max_delta > 0.5


def test_field_primary_slit_receipt_is_truth_labeled_and_limited(tmp_path: Path):
    mod = _load_module()
    mod._RECEIPT_LEDGER = tmp_path / "field_swimmers_slit_receipts.jsonl"
    double, _single = _run_pair(mod)

    row = double.write_receipt()

    assert row["truth_label"] == "SIFTA_FIELD_SWIMMERS_SLIT_V2"
    assert row["schema"] == row["truth_label"]
    assert row["ontology"] == "FIELD_PRIMARY"
    assert row["spatial_dimensions"] == 2
    assert row["peak_count"] >= 3
    assert "does not prove the physical cause" in row["limit_note"]
    assert row["seal"]

    saved = json.loads(mod._RECEIPT_LEDGER.read_text(encoding="utf-8").splitlines()[-1])
    assert saved["truth_label"] == row["truth_label"]
    assert saved["chain"] == row["chain"]


def test_field_primary_slit_manifest_entry_is_embedded_simulation():
    repo = Path(__file__).resolve().parent.parent
    manifest = json.loads((repo / "Applications" / "apps_manifest.json").read_text())
    entry = manifest["Unified Field Slit — Swimmers Inside the Soup"]

    assert entry["category"] == "Simulations"
    assert entry["entry_point"] == "Applications/sifta_field_swimmers_slit.py"
    assert entry["widget_class"] == "FieldSwimmersSlitWidget"
    assert entry["autostart"] is False
    assert "field-primary analogue" in entry["description"]
    assert "does not prove the physical cause" in entry["description"]


def test_field_primary_slit_widget_instantiates_offscreen():
    mod = _load_module()
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    widget = mod.FieldSwimmersSlitWidget()
    try:
        widget._timer.stop()
        widget._on_tick()
        app.processEvents()
        assert widget.exp_double.field.tick_count >= 3
        assert widget.exp_single.field.tick_count >= 3
        assert widget._canvas is not None
    finally:
        widget.deleteLater()
        app.processEvents()
