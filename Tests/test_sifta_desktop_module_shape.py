"""
Guard against a split / merged sifta_os_desktop module shape: wrong __file__,
missing overlay types, or duplicate class bindings from patch order.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_sifta_os_desktop_resolves_to_repo_root_file():
    import sifta_os_desktop

    p = Path(sifta_os_desktop.__file__).resolve()
    assert p == REPO / "sifta_os_desktop.py", (
        f"Expected root desktop module, got {p!s}. Check PYTHONPATH / pytest import path."
    )


def test_sifta_os_desktop_public_overlay_and_magnetic_types():
    import sifta_os_desktop as m

    for name in (
        "SiftaDesktop",
        "LaunchpadWidget",
        "SpotlightWidget",
        "MagneticSubWindow",
        "clamp_mdi_subwindow_top_left",
        "resolve_mdi_subwindow_position",
    ):
        assert hasattr(m, name), f"missing {name!r}"

    assert m.LaunchpadWidget.__module__ == "sifta_os_desktop"
    assert m.SpotlightWidget.__module__ == "sifta_os_desktop"
    assert m.SiftaDesktop.__module__ == "sifta_os_desktop"


def test_economy_hud_scan_gated_for_offscreen_and_ci(monkeypatch):
    from sifta_os_desktop import _economy_hud_full_scan_enabled

    monkeypatch.delenv("SIFTA_FORCE_ECONOMY_SCAN", raising=False)
    monkeypatch.delenv("SIFTA_SKIP_ECONOMY_SCAN", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    assert _economy_hud_full_scan_enabled() is True
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assert _economy_hud_full_scan_enabled() is False
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.setenv("CI", "true")
    assert _economy_hud_full_scan_enabled() is False
    monkeypatch.setenv("SIFTA_FORCE_ECONOMY_SCAN", "1")
    assert _economy_hud_full_scan_enabled() is True
    monkeypatch.delenv("SIFTA_FORCE_ECONOMY_SCAN", raising=False)
    monkeypatch.setenv("SIFTA_SKIP_ECONOMY_SCAN", "yes")
    monkeypatch.setenv("CI", "")
    assert _economy_hud_full_scan_enabled() is False


def test_sifta_desktop_single_class_def_for_overlays_in_ast():
    import ast

    path = REPO / "sifta_os_desktop.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in ("LaunchpadWidget", "SpotlightWidget"):
            counts[node.name] = counts.get(node.name, 0) + 1
    for cls_name in ("LaunchpadWidget", "SpotlightWidget"):
        assert counts.get(cls_name) == 1, f"expected one class {cls_name!r} in {path!s}, got {counts!r}"


def test_desktop_has_no_loose_app_shortcut_tiles():
    """Normal apps belong in Launchpad/Spotlight/categories, not pinned to the canvas."""
    paths = [
        REPO / "sifta_os_desktop.py",
        REPO / ".simulation_publicpush_sandbox" / "sifta_os_desktop.py",
    ]
    forbidden = ("SWARM CHAT", "CASINO VAULT", "SYMPHONY")
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for label in forbidden:
            assert label not in source, f"{label!r} should not be a desktop shortcut in {path}"


def test_desktop_wallpaper_does_not_depend_on_antigravity_cache():
    paths = [
        REPO / "sifta_os_desktop.py",
        REPO / ".simulation_publicpush_sandbox" / "sifta_os_desktop.py",
    ]
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert ".gemini" not in source
        assert "antigravity/brain" not in source


def test_desktop_selects_tracked_mermaid_wallpaper(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")
    monkeypatch.setenv("SIFTA_SKIP_ECONOMY_SCAN", "1")
    monkeypatch.setenv("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", "1")
    monkeypatch.delenv("SIFTA_DESKTOP_WALLPAPER", raising=False)

    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from sifta_os_desktop import SiftaDesktop

    desktop = SiftaDesktop()
    try:
        selected, _mtime, size = desktop._selected_wallpaper_state()
        assert selected == str(REPO / "Library" / "Desktop Pictures" / "Mermaid Default.jpg")
        assert size and size > 0
        assert desktop._wallpaper_state[0] == selected
    finally:
        desktop.close()
        app.processEvents()


def test_alice_top_bar_status_retains_recent_activity(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")
    monkeypatch.setenv("SIFTA_SKIP_ECONOMY_SCAN", "1")
    monkeypatch.setenv("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", "1")

    import json
    import time
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    import sifta_os_desktop as desktop_module
    from sifta_os_desktop import SiftaDesktop

    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    monkeypatch.setattr(desktop_module, "_REPO", tmp_path)

    desktop = SiftaDesktop()
    try:
        broca = state_dir / "broca_vocalizations.jsonl"
        broca.write_text(json.dumps({"ts": time.time(), "spoken": "hello"}) + "\n", encoding="utf-8")
        desktop._update_alice_status()
        assert "thinking" in desktop._alice_status_label.text()

        broca.unlink()
        wernicke = state_dir / "wernicke_semantics.jsonl"
        wernicke.write_text(json.dumps({"ts": time.time(), "heard": "hello"}) + "\n", encoding="utf-8")
        desktop._update_alice_status()
        assert "listening" in desktop._alice_status_label.text()
    finally:
        desktop.close()
        app.processEvents()


def test_mesh_status_label_is_plain_language_not_hardware_alarm():
    paths = [
        REPO / "sifta_os_desktop.py",
        REPO / ".simulation_publicpush_sandbox" / "sifta_os_desktop.py",
    ]
    forbidden = ("M1 Relay", "Relay:", "OFFLINE")
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "Mesh: Local mode" in source
        assert "Mesh: Shared link" in source
        for token in forbidden:
            assert token not in source


def test_launchpad_and_spotlight_show_real_app_results(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")
    monkeypatch.setenv("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", "1")

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from sifta_os_desktop import SiftaDesktop

    desktop = SiftaDesktop()
    desktop.resize(1200, 800)
    desktop.show()
    app.processEvents()
    try:
        desktop._toggle_launchpad()
        app.processEvents()
        assert desktop._launchpad.isVisible()
        assert desktop._launchpad.parentWidget() is desktop
        assert desktop._launchpad.geometry() == desktop.centralWidget().geometry()
        assert len(desktop._launchpad._app_buttons) > 0
        desktop._launchpad.search_bar.setText("alice")
        app.processEvents()
        visible_launchpad_apps = [
            name for name, _cat, btn in desktop._launchpad._app_buttons if btn.isVisible()
        ]
        assert any("Alice" in name for name in visible_launchpad_apps)
        visible_launchpad_rows = [
            btn.text() for _name, _cat, btn in desktop._launchpad._app_buttons if btn.isVisible()
        ]
        assert visible_launchpad_rows
        assert all("\n" not in row for row in visible_launchpad_rows)
        assert any("System Settings" in row or "Alice" in row for row in visible_launchpad_rows)

        desktop._toggle_spotlight()
        app.processEvents()
        assert desktop._spotlight.isVisible()
        assert desktop._spotlight.parentWidget() is desktop
        desktop._spotlight.search_bar.setText("alice")
        app.processEvents()
        assert desktop._spotlight.list_widget.count() > 0
        first = desktop._spotlight.list_widget.item(0)
        assert first.data(Qt.ItemDataRole.UserRole) in desktop._apps_manifest_cache

        desktop._toggle_launchpad()
        app.processEvents()
        assert desktop._launchpad.isVisible()
        assert not desktop._spotlight.isVisible()

        desktop._toggle_spotlight()
        app.processEvents()
        assert desktop._spotlight.isVisible()
        assert not desktop._launchpad.isVisible()
    finally:
        desktop.close()
        app.processEvents()


def test_make_sub_cascades_default_positions(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")
    monkeypatch.setenv("SIFTA_SKIP_ECONOMY_SCAN", "1")
    monkeypatch.setenv("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", "1")

    from PyQt6.QtWidgets import QApplication, QLabel

    app = QApplication.instance() or QApplication([])

    from sifta_os_desktop import SiftaDesktop

    desktop = SiftaDesktop()
    desktop.resize(1200, 800)
    try:
        subs = [
            desktop._make_sub(QLabel(f"window {idx}"), f"Window {idx}", 260, 180)
            for idx in range(3)
        ]
        app.processEvents()
        positions = [(sub.x(), sub.y()) for sub in subs]
        assert len(set(positions)) == len(positions)

        for sub in subs:
            sub.close()
        app.processEvents()

        large_subs = [
            desktop._make_sub(QLabel(f"large {idx}"), f"Large {idx}", 1100, 760)
            for idx in range(3)
        ]
        app.processEvents()
        large_positions = [(sub.x(), sub.y()) for sub in large_subs]
        assert len(set(large_positions)) == len(large_positions)
    finally:
        desktop.close()
        app.processEvents()


def test_manifest_launches_are_singleton_and_terminal_shutdown(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")
    monkeypatch.setenv("SIFTA_SKIP_ECONOMY_SCAN", "1")
    monkeypatch.setenv("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", "1")

    from PyQt6.QtWidgets import QApplication, QWidget

    app = QApplication.instance() or QApplication([])

    from sifta_os_desktop import SiftaDesktop

    desktop = SiftaDesktop()
    desktop.resize(1200, 800)
    try:
        for _ in range(5):
            desktop._trigger_manifest_app("System Settings")
            app.processEvents()
        assert len(desktop.mdi.subWindowList()) == 1
        assert desktop._open_windows.get("System Settings") is not None

        for _ in range(5):
            desktop._trigger_manifest_app("Terminal")
            app.processEvents()
        assert len(desktop.mdi.subWindowList()) == 2
        terminal_sub = desktop._open_windows.get("Terminal")
        assert terminal_sub is not None

        terminal_widget = None
        wrapper = terminal_sub.widget()
        for child in wrapper.findChildren(QWidget):
            if hasattr(child, "process"):
                terminal_widget = child
                break
        assert terminal_widget is not None
        assert terminal_widget.terminal.is_running()

        terminal_sub.close()
        for _ in range(20):
            app.processEvents()
            if not terminal_widget.terminal.is_running():
                break
        assert not terminal_widget.terminal.is_running()
    finally:
        desktop.close()
        for _ in range(10):
            app.processEvents()


def test_core_chat_close_reopen_recreates_live_window(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")
    monkeypatch.setenv("SIFTA_SKIP_ECONOMY_SCAN", "1")
    monkeypatch.setenv("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", "1")

    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from sifta_os_desktop import SiftaDesktop

    desktop = SiftaDesktop()
    desktop.resize(1200, 800)
    try:
        desktop.open_swarm_chat()
        app.processEvents()
        first = desktop.active_chat_sub
        assert first is not None
        assert first in desktop.mdi.subWindowList()
        assert desktop._open_windows.get("SIFTA CORE CHAT") is first

        first.close()
        for _ in range(30):
            app.processEvents()
            if first.isHidden() or desktop.active_chat_sub is None:
                break

        desktop.open_swarm_chat()
        app.processEvents()
        second = desktop.active_chat_sub
        assert second is not None
        assert second is not first
        assert second in desktop.mdi.subWindowList()
        assert second.widget() is not None
        assert desktop._open_windows.get("SIFTA CORE CHAT") is second
    finally:
        desktop.close()
        for _ in range(10):
            app.processEvents()


def test_sandbox_desktop_launchpad_loads_manifest_before_render(monkeypatch):
    """Visible sandbox desktop must not boot with an empty Launchpad grid."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")
    monkeypatch.setenv("SIFTA_SKIP_ECONOMY_SCAN", "1")
    monkeypatch.setenv("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", "1")

    import importlib.util
    from PyQt6.QtWidgets import QApplication, QPushButton
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeyEvent

    app = QApplication.instance() or QApplication([])

    path = REPO / ".simulation_publicpush_sandbox" / "sifta_os_desktop.py"
    spec = importlib.util.spec_from_file_location("sifta_sandbox_desktop_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    desktop = module.SiftaDesktop()
    desktop.resize(1200, 800)
    desktop.show()
    app.processEvents()
    try:
        desktop._toggle_launchpad()
        app.processEvents()
        visible = [
            name for name, _category, btn in desktop._launchpad._app_buttons
            if btn.isVisible()
        ]
        assert len(desktop._apps_manifest_cache) >= 40
        assert "Alice" in desktop._apps_manifest_cache
        assert any("Alice" in name for name in visible)
        assert hasattr(desktop._launchpad, "search_bar")
        assert hasattr(desktop._launchpad, "_tab_btns")
        assert desktop.body_panel is not None
        assert desktop.body_panel.isVisible()
        assert getattr(desktop, "_resident_alice", None) is not None
        assert desktop._resident_alice.objectName() == "ResidentAliceSurface"
        assert hasattr(desktop, "_alice_status_label")
        assert hasattr(desktop, "_alice_level_bar")
        assert desktop._alice_status_label.text() != "not open"
        assert hasattr(desktop, "_attention_director_timer")
        assert desktop._attention_director_timer.isActive()
        assert desktop._attention_director_enabled()

        before = len(desktop.mdi.subWindowList())
        desktop._trigger_manifest_app("Alice")
        app.processEvents()
        assert len(desktop.mdi.subWindowList()) == before
        assert desktop._resident_alice.isVisible()
        desktop._launch_app(
            "Alice",
            "Applications/sifta_alice_widget.py",
            "AliceWidget",
            1000,
            850,
        )
        app.processEvents()
        assert len(desktop.mdi.subWindowList()) == before

        talk = desktop._resident_alice._talk
        talk._busy = True
        talk._status_pill.setText("thinking")
        talk._level.setValue(42)
        desktop._update_alice_desktop_state()
        assert desktop._alice_status_label.text() == "thinking"
        assert desktop._alice_level_bar.value() == 42

        tooltips = {
            btn.toolTip()
            for btn in desktop.findChildren(QPushButton)
            if btn.toolTip()
        }
        assert {"Launchpad", "Spotlight", "Alice", "Terminal", "System Settings"} <= tooltips
        assert getattr(desktop, "_clock_layout_managed", False) is True

        desktop._toggle_launchpad()
        desktop._toggle_spotlight()
        app.processEvents()
        assert desktop._spotlight.isVisible()
        desktop.keyPressEvent(
            QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        )
        app.processEvents()
        assert not desktop._spotlight.isVisible()
    finally:
        desktop.close()
        for _ in range(10):
            app.processEvents()


def test_sandbox_desktop_prefers_root_system_modules(monkeypatch):
    """Launcher cwd is the sandbox, but System imports must come from repo root."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")
    monkeypatch.chdir(REPO / ".simulation_publicpush_sandbox")

    import importlib.util
    import sys

    path = REPO / ".simulation_publicpush_sandbox" / "sifta_os_desktop.py"
    spec = importlib.util.spec_from_file_location("sifta_sandbox_path_order_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    import System.jsonl_file_lock as jsonl_file_lock

    assert Path(jsonl_file_lock.__file__).resolve() == REPO / "System" / "jsonl_file_lock.py"
    assert hasattr(jsonl_file_lock, "compact_locked")
    assert sys.path[0] == str(REPO)
