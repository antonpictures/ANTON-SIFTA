from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
WIDGET = REPO / "Applications" / "sifta_talk_to_alice_widget.py"


def test_early_direct_bonsai_bypass_is_removed():
    text = WIDGET.read_text(encoding="utf-8", errors="replace")

    assert "EARLY DIRECT BONSAI GENERATION removed" in text
    assert 'model="bonsai_chat_direct_effector"' not in text
    assert "ABSOLUTE DIRECT BROWSER IMAGE-GRID BYPASS" not in text
    assert "visual_image_grid_direct_effector" not in text