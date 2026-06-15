"""Tests for marketing/commercial inventory organ."""
from __future__ import annotations

from System.swarm_marketing_commercial_inventory import build_inventory, marketing_assets


def test_marketing_assets_include_mega_catalog_and_philippe():
    assets = marketing_assets()
    paths = {a["path"] for a in assets}
    assert "Documents/MARKETING_UNIQUE_SIFTA_PRODUCTS_MEGA_2026-06-13.md" in paths
    assert "outputs/PHILIPPE_SIFTA_COMMERCIAL_RESPONSE_2026-06-14.pdf" in paths
    assert "demo/alice_demo_for_philippe.py" in paths


def test_build_inventory_writes_json(tmp_path, monkeypatch):
    import System.swarm_marketing_commercial_inventory as mod

    out = tmp_path / "marketing_commercial_inventory.json"
    monkeypatch.setattr(mod, "_DATA", out)
    inv = build_inventory(write_json=True)
    assert out.exists()
    assert inv["schema"] == "MARKETING_COMMERCIAL_INVENTORY_V1"
    assert "philippe_report" in inv
    assert inv["summary"]["total_assets"] >= 20