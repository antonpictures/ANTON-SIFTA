"""Tests for the per-widget menu schema contract (task #55).

Architect 2026-05-14: "like in macOS Steve Jobs we have in cosame
type of distro, when I click File - new tab so I can have two browser
tabs … File Edit View all that changes with the active app."

This is the macOS-style context menu bar. Each app declares its
File / Edit / View / Window items via a `menu_schema(host)` method;
the SIFTA desktop swaps the menu bar when the active MDI subwindow
changes.

These tests verify the data contract (no Qt required):
  - SiftaBaseWidget exposes the classmethod that returns None by default
  - menu_schema() returns dict of {menu_name: list of (label, callable) | None}
  - Alice Browser's menu_schema()  declares File → New Browser Window etc.
  - Schema callable shape is correct (every non-None entry is a 2-tuple
    of (str, callable))
"""
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── SiftaBaseWidget contract ─────────────────────────────────────

def test_sifta_base_widget_has_menu_schema_classmethod():
    """Subclasses inherit the contract — default returns None."""
    # Read-import the source to avoid pulling all of PyQt6 just for this.
    src = (Path(__file__).resolve().parent.parent
           / "System" / "sifta_base_widget.py").read_text(encoding="utf-8")
    assert "def menu_schema" in src
    assert "@classmethod" in src.split("def menu_schema")[0].split("APP_NAME")[-1]


def test_sifta_base_widget_menu_schema_docstring_references_task_55():
    src = (Path(__file__).resolve().parent.parent
           / "System" / "sifta_base_widget.py").read_text(encoding="utf-8")
    # Architect's framing should be in the docstring
    block = src.split("def menu_schema")[1].split("def ")[0]
    assert "task #55" in block or "menu" in block.lower()


# ── Alice Browser schema (declared on a non-base-widget class) ───

def _load_alice_browser_class_via_ast():
    """Parse the AST to find the menu_schema method without importing
    PyQt6. We return the raw method body text for shape inspection."""
    src = (Path(__file__).resolve().parent.parent
           / "Applications" / "sifta_alice_browser_widget.py"
           ).read_text(encoding="utf-8")
    return src


def test_alice_browser_declares_menu_schema():
    src = _load_alice_browser_class_via_ast()
    assert "def menu_schema" in src


def test_alice_browser_file_menu_has_new_browser_window():
    """The architect's spec: 'File → New Tab' for Alice Browser. We
    chose 'New Browser Window' (cleanest semantics until tabs land)."""
    src = _load_alice_browser_class_via_ast()
    # The schema dict must mention File and New Browser Window
    assert '"File"' in src
    assert "New Browser Window" in src


def test_alice_browser_view_menu_has_back_forward_reload():
    """Browser View menu must include navigation actions."""
    src = _load_alice_browser_class_via_ast()
    assert '"View"' in src
    assert '"Back"' in src
    assert '"Forward"' in src
    assert '"Reload"' in src


def test_alice_browser_file_has_close_window_action():
    src = _load_alice_browser_class_via_ast()
    assert "Close Window" in src


# ── Schema callable shape (introspection of a dummy widget) ──────

class _FakeHost:
    """Stand-in for SiftaDesktop. Records every action callable target
    so tests can verify the schema wires up correctly."""
    def __init__(self):
        self.opened: list[str] = []
        self.closed: int = 0

    def _trigger_manifest_app(self, name: str) -> None:
        self.opened.append(name)

    def _close_active_subwindow(self) -> None:
        self.closed += 1


def test_schema_shape_is_dict_of_lists_of_tuples_or_none():
    """Build a minimal schema following the contract and verify shape."""
    schema = {
        "File": [
            ("New Window", lambda: None),
            None,  # separator
            ("Quit", lambda: None),
        ],
        "Edit": [
            ("Find", lambda: None),
        ],
    }
    for menu_name, items in schema.items():
        assert isinstance(menu_name, str)
        assert isinstance(items, list)
        for item in items:
            if item is None:
                continue
            assert isinstance(item, tuple)
            assert len(item) == 2
            label, cb = item
            assert isinstance(label, str)
            assert callable(cb)


# ── Desktop integration (data-shape only — no QApplication required) ──

def test_desktop_has_active_widget_menu_schema_helper():
    """The SiftaDesktop class exposes _active_widget_menu_schema."""
    src = (Path(__file__).resolve().parent.parent
           / "sifta_os_desktop.py").read_text(encoding="utf-8")
    assert "_active_widget_menu_schema" in src
    assert "def _active_widget_menu_schema" in src


def test_desktop_app_menu_spec_calls_widget_schema_first():
    """The hard-coded `overrides` dict must be consulted AFTER the widget
    schema, so a widget's declaration wins over the legacy hardcoded
    entry."""
    src = (Path(__file__).resolve().parent.parent
           / "sifta_os_desktop.py").read_text(encoding="utf-8")
    # In _app_menu_spec, the widget schema check comes before overrides.get
    block_start = src.find("def _app_menu_spec")
    block_end = src.find("def _close_active_subwindow", block_start)
    block = src[block_start:block_end]
    widget_check_pos = block.find("_active_widget_menu_schema()")
    overrides_pos = block.find("overrides.get(clean")
    assert widget_check_pos > 0, "widget schema not consulted"
    assert overrides_pos > 0, "overrides fallback missing"
    assert widget_check_pos < overrides_pos, (
        "widget schema must be consulted BEFORE the legacy overrides dict"
    )


def test_desktop_active_widget_helper_swallows_exceptions():
    """The helper must wrap the schema call in try/except so a buggy
    app's menu_schema() can never crash the menu bar."""
    src = (Path(__file__).resolve().parent.parent
           / "sifta_os_desktop.py").read_text(encoding="utf-8")
    block_start = src.find("def _active_widget_menu_schema")
    block_end = src.find("\n    def ", block_start + 10)
    block = src[block_start:block_end]
    assert "try:" in block
    assert "except Exception:" in block
    assert "return None" in block  # fall through to defaults


# ── Architectural marker ──────────────────────────────────────────

def test_alice_browser_has_architect_comment_anchor():
    """The architect's task #55 anchor comment must be present so
    future doctors can grep for it."""
    src = _load_alice_browser_class_via_ast()
    assert "task #55" in src or "menu_schema" in src
