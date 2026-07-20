"""SIFTA PDF Forge utility — manifest + widget smoke."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "Applications" / "apps_manifest.json"
HTML = REPO / "Utilities" / "PDF_Forge" / "PDF_Forge.html"


def test_pdf_forge_registered_in_manifest():
    apps = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entry = apps["SIFTA PDF Forge"]
    assert entry["category"] == "Utilities"
    assert entry["entry_point"] == "Applications/sifta_pdf_forge_widget.py"
    assert entry["widget_class"] == "PdfForgeWidget"
    assert (REPO / entry["entry_point"]).is_file()
    assert HTML.is_file()


def test_pdf_forge_widget_imports():
    from Applications.sifta_pdf_forge_widget import PdfForgeWidget

    assert PdfForgeWidget.APP_NAME == "SIFTA PDF Forge"


def test_pdf_forge_has_imperial_valley_farmer_support_preset():
    html = HTML.read_text(encoding="utf-8")
    assert 'value="farmerSupport"' in html
    assert "IMPERIAL VALLEY FARMER BENEFIT PLAN" in html
    assert "Farm water rights protected in writing" in html
