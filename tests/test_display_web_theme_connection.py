from __future__ import annotations

from pathlib import Path

from System import sifta_desktop_themes as themes


ROOT = Path(__file__).resolve().parents[1]


def test_web_inspired_dark_theme_is_available_and_uses_editorial_palette():
    palette = themes.THEMES["stigmergicode_dark"]
    assert palette.bg_deep == "#12100e"
    assert palette.accent_primary == "#d97745"
    assert palette.text_primary == "#f4eee5"
    assert palette.display_name == "◉ Stigmergicode Dark"


def test_fresh_theme_fallback_is_web_inspired(monkeypatch, tmp_path):
    monkeypatch.setattr(themes, "_THEME_FILE", tmp_path / "desktop_theme.json")
    assert themes.load_active_theme_id() == "stigmergicode_dark"
    assert themes.active_palette().theme_id == "stigmergicode_dark"


def test_global_qss_connects_display_palette_to_web_family_font():
    qss = themes.generate_global_qss(themes.THEMES["stigmergicode_dark"])
    assert 'font-family: "Avenir Next"' in qss
    assert "#12100e" in qss
