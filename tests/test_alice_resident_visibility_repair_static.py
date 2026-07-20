"""Static guard for Alice resident-panel boot visibility repair."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_records_and_repairs_alice_resident_visibility() -> None:
    src = (ROOT / "sifta_os_desktop.py").read_text(encoding="utf-8")

    assert "def _ensure_alice_resident_visible" in src
    assert "def _alice_resident_visibility_state" in src
    assert "ensure_talk_visible" in src
    assert "ALICE_RESIDENT_VISIBILITY_REPAIR_V1" in src
    assert "post_boot_900ms" in src
    assert "post_boot_2200ms" in src

    for field in (
        "alice_panel_visible",
        "alice_resident_visible",
        "alice_talk_visible",
        "alice_panel_width",
        "body_splitter_sizes",
    ):
        assert field in src


def test_alice_widget_has_talk_visibility_reassertion_hook() -> None:
    src = (ROOT / "Applications" / "sifta_alice_widget.py").read_text(encoding="utf-8")

    assert "def ensure_talk_visible" in src
    assert "self._overlay_layout.setCurrentWidget(self._talk)" in src
    assert "self._talk.raise_()" in src
    assert "talk_visibility_reasserted" in src
