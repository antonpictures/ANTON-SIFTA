from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
WIDGET = REPO / "Applications" / "sifta_talk_to_alice_widget.py"


def test_bonsai_generation_routes_before_browser_image_grid():
    text = WIDGET.read_text(encoding="utf-8", errors="replace")
    bonsai_idx = text.index("EARLY DIRECT BONSAI GENERATION")
    grid_idx = text.index("ABSOLUTE DIRECT BROWSER IMAGE-GRID BYPASS")

    assert bonsai_idx < grid_idx
    grid_block = text[grid_idx : grid_idx + 3000]
    assert "_is_bonsai_generation_request(text)" not in grid_block
    assert "visual_image_grid_direct_effector" in grid_block
