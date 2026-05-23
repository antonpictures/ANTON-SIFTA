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


def test_beeson_alice_eye_chrome_defaults_are_low_stress():
    """BeeSon demo path: eye organ can run, panel chrome stays calm."""
    alice = (REPO / "Applications" / "sifta_alice_widget.py").read_text()
    talk = (REPO / "Applications" / "sifta_talk_to_alice_widget.py").read_text()
    sees = (REPO / "Applications" / "sifta_what_alice_sees_widget.py").read_text()
    desktop = (REPO / "sifta_os_desktop.py").read_text()
    swimmer_field = (REPO / "System" / "sifta_swimmer_wallpaper_field.py").read_text()

    assert "SIFTA_ALICE_UNIFIED_DEFER_EYE=0   (default)" in alice
    assert "self._raw_video_visible = False" in alice
    # Architect 2026-05-11 22:43: "WHAT IS THAT FOR WHY DO I NEED TO CLICK?"
    # The `show raw` button moved behind SIFTA_EYE_DEV_CONTROLS=1 along with
    # the photons / ticker dev toggles.
    assert "self._btn_raw.setVisible(_show_dev)" in alice
    assert "self._btn_photons.setVisible(_show_dev)" in alice
    assert "self._btn_events.setVisible(_show_dev)" in alice
    assert "_STT_TURN_TIMEOUT_S" in talk
    assert "def _on_stt_watchdog" in talk

    assert "self._density_slider.setVisible(_eye_dev_on)" in sees
    assert "self._photon_count_label.setVisible(_eye_dev_on)" in sees
    assert "self._vision_body_btn.setVisible(_eye_dev_on)" in sees
    assert 'SIFTA_EYE_BOOT_OFF", "0"' in sees

    assert "REAL-DATA SWIMMER OVERLAY" not in desktop
    assert "self._swimmer_drift.field_state" not in desktop
    # Architect 2026-05-14: decorative photon particle overlay + boot stderr
    # for SIFTA_DESKTOP_PHOTONS removed — empty `particles` list, env knob dead.
    assert "SIFTA_DESKTOP_PHOTONS env var is no longer honored" in desktop
    assert "self.particles = []" in desktop
    assert "_n_photons = 200" not in desktop
    assert "positions = None" in desktop
    assert "positions=positions" in desktop
    assert "if not has_wallpaper:\n            self._draw_predator_sigil" not in desktop
    assert "class SwimmerDriftField" in swimmer_field
    assert "not wired" in swimmer_field
    assert "default desktop hot path" in swimmer_field


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


def test_kernel_scheduler_timer_ticks_inside_qt_app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication
    from sifta_os_desktop import _install_kernel_scheduler_timer

    app = QApplication.instance() or QApplication([])

    class FakeProcess:
        def __init__(self, pid: str, reason: str, budget: str):
            self.pid = pid
            self.metadata = {
                "repair_needed": "true",
                "repair_reason": reason,
                "repair_budget_stgm": budget,
            }

    class FakeKernelTable:
        def __init__(self):
            self.calls = 0
            self.scored = []
            self.spends = []
            self.heartbeats = []

        def self_maintenance_tick(self, *, max_actions: int):
            assert max_actions == 3
            self.calls += 1
            return 2

        def get(self, pid: str):
            return object() if pid in {"desktop_body_001", "ring2_high", "ring2_low"} else None

        def scheduler_utility(self, pid: str, **_kwargs):
            self.scored.append(pid)
            return {
                "desktop_body_001": 0.42,
                "ring2_high": 0.73,
                "ring2_low": 0.51,
            }[pid]

        def list_unhealthy(self):
            return [
                FakeProcess("ring2_low", "missing_physical_grounding", "0.02"),
                FakeProcess("ring2_high", "negative_stgm_contributor", "0.03"),
            ]

        def sys_budget_state(self, pid: str, requested_spend: float = 0.0):
            assert pid == "desktop_body_001"
            assert requested_spend > 0.0
            return {"state": "ALLOW"}

        def sys_spend(self, pid: str, amount: float, purpose: str):
            self.spends.append((pid, amount, purpose))
            return f"receipt_alloc_{len(self.spends)}"

        def heartbeat(self, pid: str, **kwargs):
            self.heartbeats.append((pid, kwargs))

    table = FakeKernelTable()
    timer = _install_kernel_scheduler_timer(app, table, interval_ms=250)
    try:
        assert timer is not None
        assert timer.isActive()
        assert timer.interval() == 250
        assert app.property("sifta_kernel_scheduler_interval_ms") == 250
        timer.timeout.emit()
        assert table.calls == 1
        assert table.scored == ["desktop_body_001", "ring2_low", "ring2_high"]
        assert table.spends == [
            ("desktop_body_001", 0.03, "scheduled:negative_stgm_contributor:ring2_high"),
            ("desktop_body_001", 0.02, "scheduled:missing_physical_grounding:ring2_low"),
        ]
        assert [row[0] for row in table.heartbeats] == ["ring2_high", "ring2_low"]
        assert table.heartbeats[0][1]["receipt_id"] == "receipt_alloc_1"
        assert app.property("sifta_kernel_scheduler_last_actions") == 2
        assert app.property("sifta_kernel_scheduler_desktop_score") == 0.42
        allocations = app.property("sifta_kernel_scheduler_last_allocations")
        assert [row["pid"] for row in allocations] == ["ring2_high", "ring2_low"]
        allocation = app.property("sifta_kernel_scheduler_last_allocation")
        assert allocation["pid"] == "ring2_high"
        assert allocation["allocator_pid"] == "desktop_body_001"
        assert allocation["receipt_id"] == "receipt_alloc_1"
        assert app.property("sifta_kernel_scheduler_last_spend") == 0.05

        timer.timeout.emit()
        assert table.calls == 1
        assert len(table.spends) == 2
        assert app.property("sifta_kernel_scheduler_last_actions") == 0
        assert app.property("sifta_kernel_scheduler_last_spend") == 0
        assert timer.interval() == 250
    finally:
        if timer is not None:
            timer.stop()


def test_kernel_scheduler_multi_allocation_respects_tick_spend_cap():
    from sifta_os_desktop import _allocate_many_from_pending

    class FakeKernelTable:
        def __init__(self):
            self.spends = []

        def get(self, pid: str):
            return object()

        def scheduler_utility(self, pid: str, **_kwargs):
            return {
                "task_a": 0.9,
                "task_b": 0.8,
                "task_c": 0.7,
            }[pid]

        def sys_budget_state(self, pid: str, requested_spend: float = 0.0):
            return {"state": "ALLOW"}

        def sys_spend(self, pid: str, amount: float, purpose: str):
            self.spends.append((pid, amount, purpose))
            return f"receipt_{len(self.spends)}"

        def heartbeat(self, pid: str, **_kwargs):
            return None

    pending = [
        {"pid": "task_a", "type": "repair", "evidence_gain": 0.9, "requested_budget": 0.03},
        {"pid": "task_b", "type": "repair", "evidence_gain": 0.8, "requested_budget": 0.03},
        {"pid": "task_c", "type": "repair", "evidence_gain": 0.7, "requested_budget": 0.03},
    ]
    table = FakeKernelTable()

    allocations = _allocate_many_from_pending(
        table,
        pending,
        allocator_pid="desktop_body_001",
        max_allocations=4,
        max_spend_per_tick=0.08,
        max_slice_spend=0.03,
    )

    assert [row["pid"] for row in allocations] == ["task_a", "task_b"]
    assert sum(row["budget"] for row in allocations) == 0.06
    assert len(table.spends) == 2


def test_kernel_scheduler_timer_drives_desktop_attention_director(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication
    from sifta_os_desktop import _install_kernel_scheduler_timer

    app = QApplication.instance() or QApplication([])

    class FakeKernelTable:
        def self_maintenance_tick(self, *, max_actions: int):
            return 0

        def get(self, pid: str):
            return object() if pid == "desktop_body_001" else None

        def scheduler_utility(self, pid: str, **_kwargs):
            return 0.25

        def list_unhealthy(self):
            return []

    class FakeDesktop:
        def __init__(self):
            self.calls = 0

        def _tick_biological_attention_director(self):
            self.calls += 1
            return ["attention:sample"]

    table = FakeKernelTable()
    desktop = FakeDesktop()
    timer = _install_kernel_scheduler_timer(app, table, interval_ms=1500, desktop_body=desktop)
    try:
        assert timer is not None
        assert timer.interval() == 30000
        assert app.property("sifta_kernel_scheduler_interval_ms") == 30000
        timer.timeout.emit()
        assert desktop.calls == 1
        assert app.property("sifta_attention_director_last_events") == ["attention:sample"]
    finally:
        if timer is not None:
            timer.stop()


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


def test_desktop_selects_tracked_theme_wallpaper(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")
    monkeypatch.setenv("SIFTA_SKIP_ECONOMY_SCAN", "1")
    monkeypatch.setenv("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", "1")
    monkeypatch.delenv("SIFTA_DESKTOP_WALLPAPER", raising=False)

    import sys
    import types

    from PyQt6.QtWidgets import QApplication, QWidget

    app = QApplication.instance() or QApplication([])

    fake_chat_module = types.ModuleType("sifta_swarm_chat")

    class SwarmChatWindow(QWidget):
        pass

    fake_chat_module.SwarmChatWindow = SwarmChatWindow
    monkeypatch.setitem(sys.modules, "sifta_swarm_chat", fake_chat_module)

    from sifta_os_desktop import SiftaDesktop
    from System.sifta_desktop_themes import wallpaper_path

    desktop = SiftaDesktop()
    try:
        selected, _mtime, size = desktop._selected_wallpaper_state()
        expected = wallpaper_path()
        assert selected == expected
        assert size and size > 0
        assert desktop._wallpaper_state[0] == selected
    finally:
        desktop.active_chat_sub = None
        desktop._open_windows.clear()
        desktop.hide()
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
        assert "Mesh: " in source
        assert any(label in source for label in ("Mesh: Local mode", "Mesh: Global mode"))
        assert any(label in source for label in ("Mesh: Shared link", "Mesh: Global link"))
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


def test_make_sub_enforces_single_visible_app_slot(monkeypatch):
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
        visible = [sub for sub in subs if not sub.isHidden()]
        assert visible == [subs[-1]]
        assert desktop.current_app_state()["open_apps"] == ["Window 2"]

        for sub in subs:
            sub.close()
        app.processEvents()

        large_subs = [
            desktop._make_sub(QLabel(f"large {idx}"), f"Large {idx}", 1100, 760)
            for idx in range(3)
        ]
        app.processEvents()
        large_visible = [sub for sub in large_subs if not sub.isHidden()]
        assert large_visible == [large_subs[-1]]
        assert desktop.current_app_state()["open_apps"] == ["Large 2"]
    finally:
        desktop.close()
        app.processEvents()


def test_mdi_wrapper_does_not_duplicate_base_widget_help(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")
    monkeypatch.setenv("SIFTA_SKIP_ECONOMY_SCAN", "1")
    monkeypatch.setenv("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", "1")

    from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

    from System.sifta_base_widget import SiftaBaseWidget
    from sifta_os_desktop import SiftaDesktop

    class HelpLoop(SiftaBaseWidget):
        APP_NAME = "System Settings"

        def build_ui(self, layout):
            layout.addWidget(QLabel("settings body"))

    def contextual_help_buttons(widget):
        return [
            button for button in widget.findChildren(QPushButton)
            if button.text() == "?" and button.toolTip().startswith("Help ")
        ]

    app = QApplication.instance() or QApplication([])

    desktop = SiftaDesktop()
    desktop.resize(1200, 800)
    try:
        base_sub = desktop._make_sub(HelpLoop(), "System Settings", 520, 360, "#414868")
        plain_sub = desktop._make_sub(QLabel("plain body"), "Plain Panel", 320, 220, "#414868")
        app.processEvents()

        assert len(contextual_help_buttons(base_sub.widget())) == 1
        assert len(contextual_help_buttons(plain_sub.widget())) == 1
        assert plain_sub.widget().findChild(QPushButton, "mdiTitleHelpButton") is not None
        assert base_sub.widget().findChild(QPushButton, "mdiTitleHelpButton") is None
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
        def visible_subwindows():
            return [sw for sw in desktop.mdi.subWindowList() if not sw.isHidden()]

        for _ in range(5):
            desktop._trigger_manifest_app("System Settings")
            app.processEvents()
        assert len(visible_subwindows()) == 1
        assert desktop._open_windows.get("System Settings") is not None
        assert desktop.current_app_state()["open_apps"] == ["System Settings"]

        for _ in range(5):
            desktop._trigger_manifest_app("Terminal")
            app.processEvents()
        assert len(visible_subwindows()) == 1
        assert desktop._open_windows.get("System Settings") is None
        terminal_sub = desktop._open_windows.get("Terminal")
        assert terminal_sub is not None
        assert desktop.current_app_state()["active_app"] == "Terminal"
        assert desktop.current_app_state()["open_apps"] == ["Terminal"]

        terminal_widget = None
        wrapper = terminal_sub.widget()
        for child in wrapper.findChildren(QWidget):
            if hasattr(child, "process"):
                terminal_widget = child
                break
        assert terminal_widget is not None
        assert terminal_widget.terminal.is_running()

        script_launch = {}
        original_script_launcher = desktop._launch_terminal_app
        desktop._launch_terminal_app = lambda title, entry: script_launch.update(
            {"title": title, "entry": entry}
        )
        try:
            desktop._trigger_manifest_app("Circadian Rhythm")
        finally:
            desktop._launch_terminal_app = original_script_launcher
        assert script_launch == {
            "title": "Circadian Rhythm",
            "entry": "Applications/circadian_rhythm.py",
        }

        terminal_sub.close()
        for _ in range(20):
            app.processEvents()
            if not terminal_widget.terminal.is_running():
                break
        assert not terminal_widget.terminal.is_running()
    finally:
        desktop.close()


def test_core_chat_close_reopen_recreates_live_window(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SIFTA_DISABLE_MESH", "1")
    monkeypatch.setenv("SIFTA_SKIP_ECONOMY_SCAN", "1")
    monkeypatch.setenv("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", "1")

    import sys
    import types

    from PyQt6.QtWidgets import QApplication, QWidget

    app = QApplication.instance() or QApplication([])

    fake_chat_module = types.ModuleType("sifta_swarm_chat")

    class SwarmChatWindow(QWidget):
        pass

    fake_chat_module.SwarmChatWindow = SwarmChatWindow
    monkeypatch.setitem(sys.modules, "sifta_swarm_chat", fake_chat_module)

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
        assert first.isHidden()

        desktop.open_swarm_chat()
        second = desktop.active_chat_sub
        assert second is not None
        assert second is not first
        assert second in desktop.mdi.subWindowList()
        assert second.widget() is not None
        assert desktop._open_windows.get("SIFTA CORE CHAT") is second
    finally:
        desktop.active_chat_sub = None
        desktop._open_windows.clear()
        desktop.hide()


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
        assert {
            "Swarm App Store\npowered by stigmergic ecology",
            "Spotlight",
            "Files",
            "Talk to Alice",
            "Swarm Chat",
            "Finance",
            "Fold Swarm",
            "Protein Colosseum",
            "PoUW Sim",
            "Assembly Theory",
            "Terminal",
            "System Settings",
        } <= tooltips
        assert "Alice" not in tooltips
        assert "Alice Health" not in tooltips
        assert "What Alice Sees" not in tooltips
        assert "Alice Safety Tracker" not in tooltips
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
