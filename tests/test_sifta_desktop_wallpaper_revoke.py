"""BeeSon wallpaper — honeycomb lattice revoked (Architect 2026-05-12)."""

from __future__ import annotations

from pathlib import Path

import pytest

import System.sifta_desktop_themes as themes


def test_beeson_palette_default_wallpaper_is_bundled_jpg() -> None:
    assert themes.BEESON.wallpaper_filename.strip() == "BeeSon Default.jpg"


def test_wallpaper_path_resolves_beeson_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(themes, "load_active_theme_id", lambda: "beeson")
    monkeypatch.setattr(themes, "load_custom_wallpaper_path", lambda: None)
    p = themes.wallpaper_path()
    assert p.endswith("BeeSon Default.jpg")
    assert Path(p).is_file()


def test_stock_wallpaper_includes_beeson_bundle() -> None:
    paths = {Path(p).name for _, p in themes.list_stock_wallpapers()}
    assert "BeeSon Default.jpg" in paths
    assert "BeeSon Yellow Meadow.jpg" in paths


def test_beeson_v8_1_theme_uses_current_yellow_meadow_wallpaper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(themes, "load_active_theme_id", lambda: "beeson_v8_1")
    monkeypatch.setattr(themes, "load_custom_wallpaper_path", lambda: None)

    assert themes.BEESON_V8_1.display_name == "🐝 BeeSon v8.1"
    assert themes.BEESON_V8_1.wallpaper_filename == "BeeSon Yellow Meadow.jpg"
    p = themes.wallpaper_path()
    assert p.endswith("BeeSon Yellow Meadow.jpg")
    assert Path(p).is_file()


def test_revoked_beeson_honeycomb_path_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    revoked = str(Path(themes._REPO) / "Library/Desktop Pictures/BeeSon Default.svg")
    monkeypatch.setattr(themes, "load_custom_wallpaper_path", lambda: revoked)
    monkeypatch.setattr(themes, "load_active_theme_id", lambda: "beeson")
    p = themes.wallpaper_path()
    assert "BeeSon Default.svg" not in p
    assert p.endswith("BeeSon Default.jpg")


def test_stock_wallpaper_list_never_includes_revoked_svg() -> None:
    for _label, path in themes.list_stock_wallpapers():
        assert Path(path).name.lower() not in themes._REVOKED_STOCK_WALLPAPERS
