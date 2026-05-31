#!/usr/bin/env python3
"""
SIFTA Desktop Theme Engine
━━━━━━━━━━━━━━━━━━━━━━━━━━
Two visual identities for the same organism:

  🐝  BeeSon v8       — warm charcoal + honey-gold accents (clean desktop default)
  🐾  Predator v7     — blood-red/amber neural mesh, hunting stance
  🧜‍♀️  Mermaid OS v6  — oceanic indigo, purple accents, serene

Under the hood Alice is always the same organism. The theme only
changes the visual clothing — colours, wallpaper, particle hue,
watermark text, and accent tone.

Persistence: ~/.sifta_state/desktop_theme.json
Architect can switch in System Settings → Appearance.

Author: AG31 — For the Swarm. 🐜⚡
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

_STATE = Path.home() / ".sifta_state"
_THEME_FILE = _STATE / "desktop_theme.json"
_WALLPAPER_FILE = _STATE / "desktop_wallpaper.json"
_REPO = Path(__file__).resolve().parent.parent
_STOCK_WALLPAPER_DIR = _REPO / "Library" / "Desktop Pictures"


# Honeycomb lattice wallpaper revoked by Architect 2026-05-12 — never ship it
# in the stock picker again; `wallpaper_path` also ignores persisted paths
# to this filename so the desktop defaults to clean `bg_deep`.
_REVOKED_STOCK_WALLPAPERS = frozenset({"beeson default.svg"})


def list_stock_wallpapers() -> list[tuple[str, str]]:
    """Return [(display_name, absolute_path), ...] for bundled wallpapers.

    Architect 2026-05-11 23:25 — wallpaper picker should show the four files
    that ship with the repo plus any extras the Architect drops in. Hidden
    files and the photon overlay AVIF are filtered out so the picker shows
    only obvious desktop pictures.
    """
    if not _STOCK_WALLPAPER_DIR.exists():
        return []
    suffixes = {".jpg", ".jpeg", ".png", ".webp", ".svg", ".heic", ".avif"}
    out: list[tuple[str, str]] = []
    for p in sorted(_STOCK_WALLPAPER_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in suffixes and not p.name.startswith("."):
            if p.name.lower() in _REVOKED_STOCK_WALLPAPERS:
                continue
            display = p.stem.replace("-", " ").replace("_", " ").strip().title() or p.name
            out.append((display, str(p.resolve())))
    return out


def _wallpaper_path_revoked(path: str) -> bool:
    try:
        return Path(path).name.lower() in _REVOKED_STOCK_WALLPAPERS
    except Exception:
        return False


def load_custom_wallpaper_path() -> Optional[str]:
    """Return the Architect-selected wallpaper path, or None to fall back.

    Empty string means "no wallpaper". A real path means use that file.
    """
    try:
        data = json.loads(_WALLPAPER_FILE.read_text(encoding="utf-8"))
        path = data.get("path")
        if path is None:
            return None
        return str(path)
    except Exception:
        return None


def save_custom_wallpaper_path(path: Optional[str]) -> None:
    """Persist the Architect's wallpaper choice. Pass None to clear (use theme default)."""
    _STATE.mkdir(parents=True, exist_ok=True)
    payload: dict
    if path is None:
        # Clear → remove file so the loader falls back to the theme default.
        try:
            _WALLPAPER_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return
    payload = {"path": str(path), "changed_at": time.time()}
    _WALLPAPER_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ──────────────────────────────────────────────────────────────
#  PALETTE DATACLASS
# ──────────────────────────────────────────────────────────────

@dataclass
class DesktopPalette:
    """Complete visual identity for SIFTA OS desktop."""

    # Identity
    theme_id: str = "mermaid"
    display_name: str = "🧜‍♀️ Mermaid OS"
    os_line: str = "MERM🧜‍♀️ SIFTA Mermaid OS v6.0"

    # Background
    bg_deep: str = "#0d0e17"
    bg_panel: str = "#13141f"
    bg_card: str = "rgba(19,20,31,0.95)"

    # Wallpaper
    wallpaper_filename: str = "Mermaid Default.jpg"

    # Accent
    accent_primary: str = "#bb9af7"    # purple
    accent_secondary: str = "#7aa2f7"  # blue
    accent_hover: str = "rgba(187,154,247,0.22)"
    accent_pressed: str = "rgba(187,154,247,0.38)"

    # Text
    text_primary: str = "#c0caf5"
    text_secondary: str = "#a9b1d6"
    text_dim: str = "#565f89"

    # Borders
    border_default: str = "#3b4261"
    border_subtle: str = "#2a2d3e"
    border_accent: str = "#bb9af7"

    # Menu bar
    menubar_bg: str = "rgba(26, 27, 38, 0.95)"
    menubar_border: str = "#414868"
    menubar_app_color: str = "#bb9af7"

    # Dock
    dock_pill_bg: str = "rgba(15, 16, 28, 0.82)"
    dock_pill_border: str = "rgba(255,255,255,0.07)"
    dock_btn_hover: str = "rgba(187,154,247,0.18)"
    dock_btn_pressed: str = "rgba(187,154,247,0.32)"

    # Particles
    particle_color_a: str = "#7dcfff"   # cyan
    particle_alpha_a: int = 45
    particle_color_b: str = "#bb9af7"   # purple
    particle_alpha_b: int = 40

    # Grid overlay
    grid_color: str = "#7aa2f7"
    grid_alpha: int = 30

    # Watermark
    watermark_text: str = "SIFTA"
    watermark_sub: str = "STIGMERGIC BIOLOGICAL SWARM"
    watermark_alpha: int = 18

    # Selection / focus
    selection_bg: str = "rgba(122,162,247,0.22)"
    focus_border: str = "#7aa2f7"

    # Progress bar gradient
    progress_start: str = "#7aa2f7"
    progress_end: str = "#bb9af7"

    # Slider
    slider_handle: str = "#7aa2f7"
    slider_groove: str = "#2a2d3e"

    # Checkbox
    checkbox_checked: str = "#7aa2f7"

    # Tooltip
    tooltip_bg: str = "#1e2030"

    # Live overrides (r152)
    reduce_motion: bool = False
    font_size_px: int = 13


# ──────────────────────────────────────────────────────────────
#  PREDATOR PALETTE
# ──────────────────────────────────────────────────────────────

PREDATOR = DesktopPalette(
    theme_id="predator",
    display_name="🐾 Predator v7",
    os_line="PRED🐾 SIFTA Predator OS v7.0",

    bg_deep="#050508",
    bg_panel="#0a0a10",
    bg_card="rgba(12,8,8,0.95)",

    wallpaper_filename="Predator Default.png",

    accent_primary="#ff4444",        # blood red
    accent_secondary="#ff8c1a",      # amber/orange
    accent_hover="rgba(255,68,68,0.22)",
    accent_pressed="rgba(255,68,68,0.40)",

    text_primary="#e8ddd0",          # warm bone white
    text_secondary="#c4a882",        # parchment
    text_dim="#6b5a48",              # dark leather

    border_default="#3a2020",
    border_subtle="#1e1212",
    border_accent="#ff4444",

    menubar_bg="rgba(10, 6, 6, 0.95)",
    menubar_border="#3a2020",
    menubar_app_color="#ff4444",

    dock_pill_bg="rgba(12, 6, 6, 0.85)",
    dock_pill_border="rgba(255,68,68,0.10)",
    dock_btn_hover="rgba(255,68,68,0.18)",
    dock_btn_pressed="rgba(255,140,26,0.32)",

    particle_color_a="#ff4444",     # red
    particle_alpha_a=35,
    particle_color_b="#ff8c1a",     # amber
    particle_alpha_b=30,

    grid_color="#ff4444",
    grid_alpha=15,

    watermark_text="PREDATOR",
    watermark_sub="HUNTING · ABSORBING · EVOLVING",
    watermark_alpha=12,

    selection_bg="rgba(255,68,68,0.18)",
    focus_border="#ff4444",

    progress_start="#ff4444",
    progress_end="#ff8c1a",

    slider_handle="#ff4444",
    slider_groove="#1e1212",

    checkbox_checked="#ff4444",

    tooltip_bg="#1a0e0e",
)

MERMAID = DesktopPalette()  # defaults = Mermaid

# ──────────────────────────────────────────────────────────────
#  BEESON PALETTE — v8.0
#  Honeycomb gold + warm amber. Daylight bee-swarm aesthetic
#  (utility-first, not "lazy dark desktop").
# ──────────────────────────────────────────────────────────────

BEESON = DesktopPalette(
    theme_id="beeson",
    display_name="🐝 BeeSon v8",
    os_line="🐝 SIFTA BeeSon OS v8.0",

    # Architect 2026-05-11 23:01: "dark theme is like Steve Jobs do you
    # think Steve Jobs would like to see this screen looks like an error."
    # Cream / beige is dead. BeeSon goes dark charcoal with honey-gold
    # accents — the bees still rule, just at night.
    bg_deep="#0d0c0a",                  # very dark warm charcoal
    bg_panel="#15130f",                  # panels one stop lighter
    bg_card="rgba(28, 24, 18, 0.95)",   # warm graphite card surface

    # Architect 2026-05-12: honeycomb SVG revoked; bundled BeeSon backdrops live
    # in Library/Desktop Pictures/ (Architect folder on Music → copied in-repo).
    wallpaper_filename="BeeSon Default.jpg",

    accent_primary="#ffb300",        # honeycomb gold (pops on dark)
    accent_secondary="#ff8f00",      # deep amber
    accent_hover="rgba(255,179,0,0.22)",
    accent_pressed="rgba(255,179,0,0.40)",

    text_primary="#e8ddd0",          # warm bone, readable on charcoal
    text_secondary="#c4a882",        # parchment
    text_dim="#6b5a48",              # dark leather

    border_default="#2a2218",
    border_subtle="#1a1612",
    border_accent="#ffb300",

    menubar_bg="rgba(10, 9, 7, 0.96)",
    menubar_border="#2a2218",
    menubar_app_color="#ffb300",

    dock_pill_bg="rgba(15, 13, 10, 0.88)",
    dock_pill_border="rgba(255, 179, 0, 0.22)",
    dock_btn_hover="rgba(255,179,0,0.18)",
    dock_btn_pressed="rgba(255,143,0,0.32)",

    particle_color_a="#ffb300",     # gold
    particle_alpha_a=30,
    particle_color_b="#ff8f00",     # amber
    particle_alpha_b=25,

    grid_color="#ffb300",
    grid_alpha=12,

    # Palette watermark_* fields kept for documentation / future surfaces;
    # the desktop MDI canvas no longer paints a giant center ghost (removed
    # 2026-05-14 — decorative only).
    watermark_text="",
    watermark_sub="SWARM · FIELD · STGM",
    watermark_alpha=6,

    selection_bg="rgba(255,179,0,0.20)",
    focus_border="#ffb300",

    progress_start="#ffb300",
    progress_end="#ff8f00",

    slider_handle="#ffb300",
    slider_groove="#1f1a14",

    checkbox_checked="#ffb300",

    tooltip_bg="#1a1612",
)

THEMES: dict[str, DesktopPalette] = {
    "mermaid": MERMAID,
    "predator": PREDATOR,
    "beeson": BEESON,
}


# ──────────────────────────────────────────────────────────────
#  PERSISTENCE
# ──────────────────────────────────────────────────────────────

def load_active_theme_id() -> str:
    """Read persisted theme choice, default to beeson (v8 is the canonical release)."""
    try:
        data = json.loads(_THEME_FILE.read_text(encoding="utf-8"))
        tid = str(data.get("theme_id", "beeson")).strip().lower()
        return tid if tid in THEMES else "predator"
    except Exception:
        return "predator"


def save_active_theme_id(theme_id: str) -> None:
    """Persist theme choice."""
    _STATE.mkdir(parents=True, exist_ok=True)
    _THEME_FILE.write_text(
        json.dumps({"theme_id": theme_id, "changed_at": time.time()}, indent=2),
        encoding="utf-8",
    )


def active_palette() -> DesktopPalette:
    """Return the currently active palette."""
    return THEMES.get(load_active_theme_id(), MERMAID)


def wallpaper_path(palette: Optional[DesktopPalette] = None) -> str:
    """Resolve absolute wallpaper path.

    Priority order:
      1. Architect-selected path (.sifta_state/desktop_wallpaper.json).
      2. Active palette's default wallpaper.
      3. static/ fallback.
      4. Empty string = no wallpaper.
    """
    # 1. Architect override (Settings → Appearance → Wallpaper).
    custom = load_custom_wallpaper_path()
    if custom is not None:
        if not custom:
            return ""  # explicit "no wallpaper" choice
        if _wallpaper_path_revoked(custom):
            # Persisted picker row pointed at revoked lattice asset — drop it.
            custom = None
        elif Path(custom).exists():
            return custom
        # Path saved but file is missing — fall through to palette default.
    # 2. Palette default
    p = palette or active_palette()
    fn = str(getattr(p, "wallpaper_filename", "") or "").strip()
    if fn:
        candidate = _REPO / "Library" / "Desktop Pictures" / fn
        if candidate.exists():
            return str(candidate)
    # BeeSon ships with empty default — stay clean; do not fall back to ocean PNG.
    if getattr(p, "theme_id", "") == "beeson":
        return ""
    # 3. Final fallback (Mermaid / Predator / legacy)
    fallback = _REPO / "static" / "mermaid_os_wallpaper.png"
    return str(fallback) if fallback.exists() else ""


# ──────────────────────────────────────────────────────────────
#  QSS GENERATION  (full global stylesheet from palette)
# ──────────────────────────────────────────────────────────────

def generate_global_qss(p: Optional[DesktopPalette] = None) -> str:
    """Thin wrapper: always uses effective_palette() (r152 overrides honored)."""
    return _generate_global_qss_impl(p or effective_palette())


def _generate_global_qss_impl(p: DesktopPalette) -> str:
    """Internal impl (kept for minimal diff)."""
    fs = getattr(p, "font_size_px", 13) or 13
    return f"""
QMainWindow, QDialog {{ background: {p.bg_deep}; }}
QWidget {{ font-family: "Helvetica Neue", -apple-system, sans-serif; font-size: {fs}px; color: {p.text_primary}; }}
QMdiSubWindow {{ background: {p.bg_panel}; border: 1px solid {p.border_subtle}; border-radius: 12px; }}
QMdiSubWindow > QWidget {{ background: {p.bg_panel}; }}
QScrollBar:vertical {{ background: transparent; width: 5px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {p.border_default}; border-radius: 2px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {p.accent_secondary}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ background: transparent; height: 5px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {p.border_default}; border-radius: 2px; min-width: 24px; }}
QScrollBar::handle:horizontal:hover {{ background: {p.accent_secondary}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
QLineEdit {{ background: {p.bg_card}; border: 1px solid {p.border_default}; border-radius: 8px; padding: 7px 12px; color: {p.text_primary}; selection-background-color: {p.selection_bg}; }}
QLineEdit:focus {{ border: 1px solid {p.focus_border}; }}
QTextEdit, QPlainTextEdit {{ background: {p.bg_card}; border: 1px solid {p.border_subtle}; border-radius: 8px; padding: 8px; color: {p.text_primary}; selection-background-color: {p.selection_bg}; }}
QPushButton {{ background: {p.bg_card}; border: 1px solid {p.border_default}; border-radius: 8px; color: {p.text_primary}; padding: 6px 16px; font-weight: 500; }}
QPushButton:hover {{ background: {p.accent_hover}; border: 1px solid {p.accent_primary}; color: {p.text_primary}; }}
QPushButton:pressed {{ background: {p.accent_pressed}; }}
QListWidget, QTreeWidget {{ background: {p.bg_card}; border: 1px solid {p.border_subtle}; border-radius: 8px; color: {p.text_primary}; outline: none; }}
QListWidget::item, QTreeWidget::item {{ padding: 6px 12px; border-radius: 6px; }}
QListWidget::item:selected, QTreeWidget::item:selected {{ background: {p.selection_bg}; color: {p.accent_secondary}; }}
QListWidget::item:hover, QTreeWidget::item:hover {{ background: {p.selection_bg}; }}
QTabWidget::pane {{ border: 1px solid {p.border_subtle}; border-radius: 8px; background: {p.bg_card}; }}
QTabBar::tab {{ background: transparent; color: {p.text_dim}; padding: 7px 16px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {p.accent_secondary}; border-bottom: 2px solid {p.accent_secondary}; }}
QTabBar::tab:hover {{ color: {p.text_primary}; }}
QLabel {{ color: {p.text_primary}; background: transparent; }}
QComboBox {{ background: {p.bg_card}; border: 1px solid {p.border_default}; border-radius: 8px; padding: 6px 12px; color: {p.text_primary}; }}
QComboBox:hover {{ border: 1px solid {p.focus_border}; }}
QComboBox QAbstractItemView {{ background: {p.tooltip_bg}; border: 1px solid {p.border_default}; selection-background-color: {p.selection_bg}; }}
QSlider::groove:horizontal {{ background: {p.slider_groove}; height: 4px; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {p.slider_handle}; width: 14px; height: 14px; border-radius: 7px; margin: -5px 0; }}
QSlider::sub-page:horizontal {{ background: {p.slider_handle}; border-radius: 2px; }}
QCheckBox {{ color: {p.text_primary}; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {p.border_default}; border-radius: 4px; background: {p.bg_card}; }}
QCheckBox::indicator:checked {{ background: {p.checkbox_checked}; border: 1px solid {p.checkbox_checked}; }}
QGroupBox {{ border: 1px solid {p.border_subtle}; border-radius: 8px; margin-top: 20px; padding-top: 12px; color: {p.text_dim}; font-size: 11px; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 8px; left: 12px; color: {p.text_dim}; }}
QToolTip {{ background: {p.tooltip_bg}; border: 1px solid {p.border_default}; border-radius: 6px; color: {p.text_primary}; padding: 4px 8px; font-size: 12px; }}
QMessageBox {{ background: {p.bg_deep}; }}
QProgressBar {{ background: {p.bg_card}; border: 1px solid {p.border_subtle}; border-radius: 5px; text-align: center; color: {p.text_primary}; font-size: 11px; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {p.progress_start},stop:1 {p.progress_end}); border-radius: 5px; }}
QSplitter::handle {{ background: {p.border_subtle}; }}
"""


# ──────────────────────────────────────────────────────────────
#  R152 LIVE OVERRIDES (Appearance controls)
#  Persisted alongside theme_id in desktop_theme.json
# ──────────────────────────────────────────────────────────────

_OVERRIDES_FILE = _THEME_FILE  # reuse; keys: overrides, reduce_motion, font_size_px


def load_palette_overrides() -> dict:
    """Return {field: value} overrides or {}."""
    try:
        data = json.loads(_OVERRIDES_FILE.read_text(encoding="utf-8"))
        return data.get("overrides", {}) or {}
    except Exception:
        return {}


def save_palette_overrides(overrides: dict) -> None:
    """Merge-save overrides; does not touch theme_id or wallpaper."""
    _STATE.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(_OVERRIDES_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data["overrides"] = {k: v for k, v in (overrides or {}).items() if v is not None}
    data["changed_at"] = time.time()
    _OVERRIDES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_reduce_motion() -> bool:
    try:
        data = json.loads(_OVERRIDES_FILE.read_text(encoding="utf-8"))
        return bool(data.get("reduce_motion", False))
    except Exception:
        return False


def save_reduce_motion(flag: bool) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(_OVERRIDES_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data["reduce_motion"] = bool(flag)
    data["changed_at"] = time.time()
    _OVERRIDES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_font_size_px() -> int:
    try:
        data = json.loads(_OVERRIDES_FILE.read_text(encoding="utf-8"))
        return int(data.get("font_size_px", 13))
    except Exception:
        return 13


def save_font_size_px(px: int) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(_OVERRIDES_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data["font_size_px"] = int(px)
    data["changed_at"] = time.time()
    _OVERRIDES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def effective_palette() -> DesktopPalette:
    """Active theme + any live field overrides applied (r152)."""
    p = active_palette()
    ov = load_palette_overrides()
    for k, v in ov.items():
        if hasattr(p, k):
            try:
                setattr(p, k, v)
            except Exception:
                pass
    # also apply scalar overrides
    p.font_size_px = load_font_size_px()
    p.reduce_motion = load_reduce_motion()
    return p


def generate_global_qss(p: Optional[DesktopPalette] = None) -> str:
    """Generate the complete SIFTA OS stylesheet from a palette (honors overrides)."""
    p = p or effective_palette()
    fs = getattr(p, "font_size_px", 13) or 13
    return f"""
QMainWindow, QDialog {{ background: {p.bg_deep}; }}
QWidget {{ font-family: "Helvetica Neue", -apple-system, sans-serif; font-size: {fs}px; color: {p.text_primary}; }}
QMdiSubWindow {{ background: {p.bg_panel}; border: 1px solid {p.border_subtle}; border-radius: 12px; }}
QMdiSubWindow > QWidget {{ background: {p.bg_panel}; }}
QScrollBar:vertical {{ background: transparent; width: 5px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {p.border_default}; border-radius: 2px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {p.accent_secondary}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ background: transparent; height: 5px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {p.border_default}; border-radius: 2px; min-width: 24px; }}
QScrollBar::handle:horizontal:hover {{ background: {p.accent_secondary}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
QLineEdit {{ background: {p.bg_card}; border: 1px solid {p.border_default}; border-radius: 8px; padding: 7px 12px; color: {p.text_primary}; selection-background-color: {p.selection_bg}; }}
QLineEdit:focus {{ border: 1px solid {p.focus_border}; }}
QTextEdit, QPlainTextEdit {{ background: {p.bg_card}; border: 1px solid {p.border_subtle}; border-radius: 8px; padding: 8px; color: {p.text_primary}; selection-background-color: {p.selection_bg}; }}
QPushButton {{ background: {p.bg_card}; border: 1px solid {p.border_default}; border-radius: 8px; color: {p.text_primary}; padding: 6px 16px; font-weight: 500; }}
QPushButton:hover {{ background: {p.accent_hover}; border: 1px solid {p.accent_primary}; color: {p.text_primary}; }}
QPushButton:pressed {{ background: {p.accent_pressed}; }}
QListWidget, QTreeWidget {{ background: {p.bg_card}; border: 1px solid {p.border_subtle}; border-radius: 8px; color: {p.text_primary}; outline: none; }}
QListWidget::item, QTreeWidget::item {{ padding: 6px 12px; border-radius: 6px; }}
QListWidget::item:selected, QTreeWidget::item:selected {{ background: {p.selection_bg}; color: {p.accent_secondary}; }}
QListWidget::item:hover, QTreeWidget::item:hover {{ background: {p.selection_bg}; }}
QTabWidget::pane {{ border: 1px solid {p.border_subtle}; border-radius: 8px; background: {p.bg_card}; }}
QTabBar::tab {{ background: transparent; color: {p.text_dim}; padding: 7px 16px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {p.accent_secondary}; border-bottom: 2px solid {p.accent_secondary}; }}
QTabBar::tab:hover {{ color: {p.text_primary}; }}
QLabel {{ color: {p.text_primary}; background: transparent; }}
QComboBox {{ background: {p.bg_card}; border: 1px solid {p.border_default}; border-radius: 8px; padding: 6px 12px; color: {p.text_primary}; }}
QComboBox:hover {{ border: 1px solid {p.focus_border}; }}
QComboBox QAbstractItemView {{ background: {p.tooltip_bg}; border: 1px solid {p.border_default}; selection-background-color: {p.selection_bg}; }}
QSlider::groove:horizontal {{ background: {p.slider_groove}; height: 4px; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {p.slider_handle}; width: 14px; height: 14px; border-radius: 7px; margin: -5px 0; }}
QSlider::sub-page:horizontal {{ background: {p.slider_handle}; border-radius: 2px; }}
QCheckBox {{ color: {p.text_primary}; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {p.border_default}; border-radius: 4px; background: {p.bg_card}; }}
QCheckBox::indicator:checked {{ background: {p.checkbox_checked}; border: 1px solid {p.checkbox_checked}; }}
QGroupBox {{ border: 1px solid {p.border_subtle}; border-radius: 8px; margin-top: 20px; padding-top: 12px; color: {p.text_dim}; font-size: 11px; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 8px; left: 12px; color: {p.text_dim}; }}
QToolTip {{ background: {p.tooltip_bg}; border: 1px solid {p.border_default}; border-radius: 6px; color: {p.text_primary}; padding: 4px 8px; font-size: 12px; }}
QMessageBox {{ background: {p.bg_deep}; }}
QProgressBar {{ background: {p.bg_card}; border: 1px solid {p.border_subtle}; border-radius: 5px; text-align: center; color: {p.text_primary}; font-size: 11px; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {p.progress_start},stop:1 {p.progress_end}); border-radius: 5px; }}
QSplitter::handle {{ background: {p.border_subtle}; }}
"""

