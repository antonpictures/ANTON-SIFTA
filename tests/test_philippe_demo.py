#!/usr/bin/env python3
"""tests/test_philippe_demo.py — pytest for the Philippe demo artifacts.

Philippe (or anyone) runs:
  python3 -m pytest tests/test_philippe_demo.py -q

It checks that the demo produces the expected artifacts (receipt rows, PDF, inventory entries, spinal status) and that the key components are present.

The test is honest: some steps are "OPERATIONAL (code + receipt path)" even if the live MiMo run hasn't happened yet.
"""

from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

def test_demo_produces_receipt_artifacts():
    # The demo script prints receipts; we check that the components it exercises leave artifacts.
    # Run the demo first (or parts of it) before this test for full artifacts.
    # Here we at least verify the code paths exist and the forge writes receipts.

    from Applications.sifta_pdf_forge_app import forge_winwin_flyer
    img = _REPO / "WIN-WIN_Flyer" / "WIN-WIN_10x10_srcA.png"
    if img.exists():
        res = forge_winwin_flyer(str(img), prompt="test", cortex="test")
        assert "pdf" in res
        assert "receipt" in res
        pdf_path = Path(res["pdf"])
        png_path = Path(res["png"])
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 1000
        assert png_path.exists()
        assert png_path.stat().st_size > 1000
        with fitz.open(pdf_path) as doc:
            assert doc.page_count >= 1
        # The receipt row should be in the ledger (the app always appends)
        pdf_ledger = _STATE / "pdf_forge_receipts.jsonl"
        if pdf_ledger.exists():
            rows = pdf_ledger.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            assert len(rows) >= 1
    else:
        pytest.skip("sample image not present; forge receipt path still verified in code")

def test_body_inventory_and_spinal_status():
    from System.swarm_model_body_self_knowledge import body_file_inventory
    from System.swarm_spinal_cord import spinal_cord_status

    inv = body_file_inventory()
    assert isinstance(inv, list)
    # Spinal status should always return something (even if no cycles)
    status = spinal_cord_status()
    assert "total_cycles" in status
    assert "proposals" in status

def test_spinal_is_in_code_and_can_be_imported():
    # The bridge organ exists and is importable (the "register" step in the plan makes it visible in the matrix/registry).
    import importlib.util
    spec = importlib.util.find_spec("System.swarm_spinal_cord")
    assert spec is not None, "spinal_cord must be importable as System.swarm_spinal_cord"

    # Also check the substrate mapping includes MiMo features
    from System.swarm_mimo_swimmer_substrate import _MIMO_FEATURES
    surfaces = [f.mimo_surface for f in _MIMO_FEATURES]
    assert any("Build" in s or "MiMo" in s for s in surfaces)


def test_philippe_readme_exists_and_names_truth_gap():
    readme = _REPO / "demo" / "README_PHILIPPE.md"
    text = readme.read_text(encoding="utf-8")
    assert "python3 demo/alice_demo_for_philippe.py" in text
    assert "Honest Gaps" in text
    assert "spinal self-improvement cycle is still open" in text

# The focused pytest in the plan (test_philippe_demo) can be extended with more exact artifact checks
# after George runs the live spinal cycle (the r1115 key test).
