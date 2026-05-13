"""
SIFTA Python OS Simulator
Desktop Environment Manager — Stabilized Build
Claude/Anthropic audit pass: syntax errors patched, SwarmChatWindow wired to Ollama.
"""

import sys
import os
import time
import json
import datetime
import hashlib
import urllib.request
import urllib.error
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMdiArea, QMdiSubWindow,
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel,
    QTextEdit, QFrame, QMenu, QMessageBox, QLineEdit, QComboBox,
    QListWidget, QListWidgetItem, QScrollArea, QSplitter
)
from PyQt6.QtCore import Qt, QPoint, QRect, QProcess, QProcessEnvironment, QTimer, QDateTime, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QKeySequence, QShortcut, QIcon, QPixmap, QPainter

_REPO = Path(__file__).resolve().parent
_SYS = _REPO / "System"
_VENV_PYTHON = _REPO / ".venv" / "bin" / "python"
_PYTHON_BIN = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else (sys.executable or "python3")

# ── Swarm Intelligence Subsystems ────────────────────────────
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_SYS) not in sys.path:
    sys.path.insert(0, str(_SYS))

try:
    from System.qt_webengine_bootstrap import bootstrap_qt_webengine

    _WEBENGINE_BOOTSTRAP = bootstrap_qt_webengine()
except Exception as _webengine_boot_exc:
    _WEBENGINE_BOOTSTRAP = None

from app_fitness import ranked_apps, record_crash, record_launch  # noqa: E402
from stigmergic_wm import neighbors as wm_neighbors  # noqa: E402
from stigmergic_wm import record_open as wm_record_open  # noqa: E402
from stigmergic_wm import reset_session as wm_reset_session  # noqa: E402
from stigmergic_wm import suggest_position  # noqa: E402
from stigmergic_wm import _load as wm_load  # noqa: E402
from pheromone_fs import clusters as fs_clusters  # noqa: E402
from pheromone_fs import neighbors as fs_neighbors  # noqa: E402
from pheromone_fs import record_access as fs_record_access  # noqa: E402


def _desktop_autostart_enabled() -> bool:
    if os.environ.get("SIFTA_DESKTOP_SKIP_WM_AUTOSTART") == "1":
        return False
    return os.environ.get("SIFTA_DESKTOP_ENABLE_AUTOSTART") == "1"


def _session_restore_from_wm_enabled() -> bool:
    """Re-open stigmergic_wm last_session (explicit; not implied by manifest autostart)."""
    v = os.environ.get("SIFTA_DESKTOP_ENABLE_SESSION_RESTORE", "").strip().lower()
    return v in ("1", "true", "yes")


_OFFSCREEN_CLOSED_DESKTOPS: list[object] = []


def _economy_hud_full_scan_enabled() -> bool:
    """
    Full wallet/HUD path in _update_clock runs scan_repair_log + treasuries (heavy).
    Skip on offscreen and typical CI so smoke/tests stay fast; normal interactive
    sessions are unchanged. Override with SIFTA_FORCE_ECONOMY_SCAN=1 for headless checks.
    """
    if os.environ.get("SIFTA_FORCE_ECONOMY_SCAN", "").strip().lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("SIFTA_SKIP_ECONOMY_SCAN", "").strip().lower() in ("1", "true", "yes"):
        return False
    if os.environ.get("CI", "").strip().lower() in ("1", "true", "yes"):
        return False
    q = os.environ.get("QT_QPA_PLATFORM", "").strip().lower()
    if q == "offscreen":
        return False
    return True


def _load_widget_class(entry_point: str, class_name: str):
    """Resolve a widget class from a repo-relative path (used by tests and tooling)."""
    if "." in entry_point and not entry_point.endswith(".py"):
        raise RuntimeError(f"Module side-channel violation. Use Applications/apps_manifest.json standard paths. Got: {entry_point}")
        
    import importlib.util

    abs_path = str(_REPO / entry_point)
    module_name = os.path.splitext(os.path.basename(abs_path))[0]
    spec = importlib.util.spec_from_file_location(module_name, abs_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to build import spec for {entry_point}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return getattr(mod, class_name)


def _append_repair_log_line(row: dict) -> None:
    if str(_SYS) not in sys.path:
        sys.path.insert(0, str(_SYS))
    from System.ledger_append import append_ledger_line

    append_ledger_line(_REPO / "repair_log.jsonl", row)


def _append_dead_drop_line(row: dict) -> None:
    if str(_SYS) not in sys.path:
        sys.path.insert(0, str(_SYS))
    from System.ledger_append import append_jsonl_line

    append_jsonl_line(_REPO / "m5queen_dead_drop.jsonl", row)


# ──────────────────────────────────────────────────────────────
# UTILITY: find parent QMdiSubWindow and close it
# ──────────────────────────────────────────────────────────────

def close_parent_subwindow(widget):
    p = widget.parent()
    while p is not None and not isinstance(p, QMdiSubWindow):
        p = p.parent()
    if p:
        p.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        p.close()


def _shutdown_qprocess(
    process,
    *,
    polite_input: bytes | None = None,
    polite_ms: int = 500,
    terminate_ms: int = 1500,
    kill_ms: int = 2500,
) -> None:
    """Stop a QProcess before Qt object destruction can warn or leak."""
    if process is None:
        return
    try:
        if process.state() == QProcess.ProcessState.NotRunning:
            return
        if polite_input:
            try:
                process.write(polite_input)
                process.closeWriteChannel()
            except Exception:
                pass
            if process.waitForFinished(polite_ms):
                return
        process.terminate()
        if process.waitForFinished(terminate_ms):
            return
        process.kill()
        process.waitForFinished(kill_ms)
    except RuntimeError:
        # The C++ object may already be gone during app teardown.
        return


def _shutdown_embedded_widget_tree(root: QWidget | None) -> None:
    """Drain embedded app resources before a QMdiSubWindow is destroyed."""
    if root is None:
        return
    widgets: list[QWidget] = []
    seen: set[int] = set()

    def collect(widget: QWidget | None) -> None:
        if widget is None:
            return
        marker = id(widget)
        if marker in seen:
            return
        seen.add(marker)
        widgets.append(widget)
        try:
            layout = widget.layout()
        except RuntimeError:
            return
        if layout is None:
            return
        for i in range(layout.count()):
            try:
                child = layout.itemAt(i).widget()
            except RuntimeError:
                continue
            if isinstance(child, QWidget):
                collect(child)

    collect(root)
    for widget in widgets:
        shutdown = getattr(widget, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown()
                continue
            except RuntimeError:
                continue
            except Exception:
                pass
        _shutdown_qprocess(getattr(widget, "process", None))


def _widget_provides_contextual_help(widget: QWidget | None) -> bool:
    """Return True when a child app already exposes the standard app help."""
    if widget is None:
        return False
    try:
        for button in widget.findChildren(QPushButton):
            if (
                button.text().strip() == "?"
                and button.toolTip().startswith("Help ")
            ):
                return True
    except RuntimeError:
        return False
    return False


def _ranges_overlap(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 < b1 and b0 < a1


def clamp_mdi_subwindow_top_left(
    x: int,
    y: int,
    width: int,
    height: int,
    viewport: QRect,
) -> tuple[int, int]:
    min_x = viewport.x()
    min_y = viewport.y()
    max_x = viewport.x() + viewport.width() - width
    max_y = viewport.y() + viewport.height() - height
    if width > viewport.width():
        max_x = min_x
    if height > viewport.height():
        max_y = min_y
    return int(max(min_x, min(max_x, x))), int(max(min_y, min(max_y, y)))


def mdi_subwindow_rect_overlaps_siblings(
    mdi: QMdiArea,
    candidate: QRect,
    ignore: QMdiSubWindow | None,
) -> bool:
    for sibling in mdi.subWindowList():
        if sibling is ignore or sibling.isHidden():
            continue
        if candidate.intersects(sibling.geometry()):
            return True
    return False


def resolve_mdi_subwindow_position(
    mdi: QMdiArea,
    sub: QMdiSubWindow,
    width: int,
    height: int,
    x_pref: int,
    y_pref: int,
    *,
    max_attempts: int = 64,
    step_x: int = 28,
    step_y: int = 24,
) -> tuple[int, int]:
    vp = mdi.viewport().rect()
    col_span = max(int(step_x), 1)
    row_span = max(int(step_y), 1)
    col_count = max(1, (vp.width() - width + col_span) // col_span) if width <= vp.width() else 1
    row_count = max(1, (vp.height() - height + row_span) // row_span) if height <= vp.height() else 1

    for attempt in range(max_attempts):
        if attempt == 0:
            px, py = clamp_mdi_subwindow_top_left(x_pref, y_pref, width, height, vp)
        else:
            idx = attempt - 1
            col = idx % col_count
            row = (idx // col_count) % row_count
            px = vp.x() + col * col_span
            py = vp.y() + row * row_span
            px, py = clamp_mdi_subwindow_top_left(px, py, width, height, vp)
        cand = QRect(px, py, width, height)
        if not mdi_subwindow_rect_overlaps_siblings(mdi, cand, sub):
            return px, py

    return clamp_mdi_subwindow_top_left(x_pref, y_pref, width, height, vp)


class MagneticSubWindow(QMdiSubWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_snapping = False
        self._snap_threshold = 20
        self._sifta_pinned_top_left: QPoint | None = None
        self._sifta_repinning = False

    def set_sifta_pinned(self, pinned: bool = True) -> None:
        """Keep selected organs embedded: resizable, but not draggable."""
        self._sifta_pinned_top_left = self.pos() if pinned else None

    def _restore_pinned_position(self) -> None:
        if self._sifta_pinned_top_left is None or self._sifta_repinning:
            return
        if self.pos() == self._sifta_pinned_top_left:
            return
        try:
            self._sifta_repinning = True
            self.move(self._sifta_pinned_top_left)
        finally:
            self._sifta_repinning = False

    def moveEvent(self, event):
        if self._is_snapping or self._sifta_repinning:
            super().moveEvent(event)
            return

        if self._sifta_pinned_top_left is not None:
            if self.pos() != self._sifta_pinned_top_left:
                self._restore_pinned_position()
            super().moveEvent(event)
            return

        mdi_area = self.mdiArea()
        if mdi_area:
            my_rect = self.geometry()
            snap_x = my_rect.x()
            snap_y = my_rect.y()
            snapped = False

            my_l = my_rect.x()
            my_r = my_rect.x() + my_rect.width()
            my_t = my_rect.y()
            my_b = my_rect.y() + my_rect.height()

            for sibling in mdi_area.subWindowList():
                if sibling is self or sibling.isHidden():
                    continue
                sib_rect = sibling.geometry()
                sib_l = sib_rect.x()
                sib_r = sib_rect.x() + sib_rect.width()
                sib_t = sib_rect.y()
                sib_b = sib_rect.y() + sib_rect.height()

                if abs(my_l - sib_r) < self._snap_threshold and _ranges_overlap(my_t, my_b, sib_t, sib_b):
                    snap_x = sib_r
                    snapped = True
                elif abs(my_r - sib_l) < self._snap_threshold and _ranges_overlap(my_t, my_b, sib_t, sib_b):
                    snap_x = sib_l - my_rect.width()
                    snapped = True

                if abs(my_t - sib_b) < self._snap_threshold and _ranges_overlap(my_l, my_r, sib_l, sib_r):
                    snap_y = sib_b
                    snapped = True
                elif abs(my_b - sib_t) < self._snap_threshold and _ranges_overlap(my_l, my_r, sib_l, sib_r):
                    snap_y = sib_t - my_rect.height()
                    snapped = True

            if snapped:
                snap_x, snap_y = clamp_mdi_subwindow_top_left(
                    snap_x, snap_y, my_rect.width(), my_rect.height(), mdi_area.viewport().rect()
                )
                try:
                    self._is_snapping = True
                    self.move(snap_x, snap_y)
                finally:
                    self._is_snapping = False
                event.accept()
                return

        super().moveEvent(event)

    def closeEvent(self, event):
        _shutdown_embedded_widget_tree(self.widget())
        if (
            "pytest" in sys.modules
            or os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
        ):
            self.hide()
            event.accept()
            return
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────
# Chat window moved to Applications/sifta_swarm_chat.py
# ──────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────
# TERMINAL SUB-WINDOW
# ──────────────────────────────────────────────────────────────

class TerminalSubWindow(QWidget):
    def __init__(self, cmd, args):
        super().__init__()
        layout = QVBoxLayout()
        self.setStyleSheet("background-color: #0c0c11; color: #9ece6a; font-family: monospace;")

        header = QHBoxLayout()
        header.addStretch()
        layout.addLayout(header)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("border: 1px solid #3b4261; padding: 5px;")
        layout.addWidget(self.chat_display)
        self.setLayout(layout)

        self.process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", os.getcwd())
        self.process.setProcessEnvironment(env)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.start(cmd, args)
        self.chat_display.append(f"> {cmd} {' '.join(args)}")

    def handle_stdout(self):
        data = self.process.readAllStandardOutput()
        self.chat_display.append(bytes(data).decode("utf-8", errors="replace").strip())

    def handle_stderr(self):
        data = self.process.readAllStandardError()
        self.chat_display.append("[ERR] " + bytes(data).decode("utf-8", errors="replace").strip())

    def shutdown(self):
        _shutdown_qprocess(getattr(self, "process", None), polite_input=b"exit\n")

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────
# EMBEDDED SCRIPT APP WINDOW (forced in-OS launch)
# ──────────────────────────────────────────────────────────────

class EmbeddedScriptSubWindow(QWidget):
    """Runs a python app script inside an MDI window.
    Unlike terminal launching, this forces a non-popout plotting backend
    so menu apps stay inside iSwarm OS."""

    def __init__(self, app_title: str, script_path: str):
        super().__init__()
        self.app_title = app_title
        self.script_path = script_path
        layout = QVBoxLayout()
        self.setStyleSheet("background-color: #0c0c11; color: #9ece6a; font-family: monospace;")

        header = QHBoxLayout()
        title = QLabel(f"{app_title} — embedded runtime")
        title.setStyleSheet("color: #7aa2f7; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        btn_restart = QPushButton("↻ Restart")
        btn_restart.setStyleSheet(
            "QPushButton { background-color: #9ece6a; color: #15161e; font-weight: bold; border-radius: 4px; padding: 3px 8px; }"
            "QPushButton:hover { background-color: #b9f27c; }"
        )
        btn_restart.clicked.connect(self._start)
        header.addWidget(btn_restart)
        layout.addLayout(header)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("border: 1px solid #3b4261; padding: 5px;")
        layout.addWidget(self.log)
        self.setLayout(layout)

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_merged)
        self._start()

    def _start(self):
        if self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
            self.process.waitForFinished(1000)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", os.getcwd())
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("SIFTA_EMBEDDED", "1")
        env.insert("MPLBACKEND", "Agg")
        self.process.setProcessEnvironment(env)
        self.process.start(_PYTHON_BIN, [self.script_path])
        self.log.append(f"> {_PYTHON_BIN} {self.script_path}")
        self.log.append("[iSwarm] Embedded mode forced (MPLBACKEND=Agg)")

    def _read_merged(self):
        data = self.process.readAllStandardOutput()
        txt = bytes(data).decode("utf-8", errors="replace").strip()
        if txt:
            self.log.append(txt)

    def shutdown(self):
        _shutdown_qprocess(getattr(self, "process", None))

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────
# SWARM TEXT EDITOR
# ──────────────────────────────────────────────────────────────

class SwarmTextEditorWindow(QWidget):
    def __init__(self, filepath=None):
        super().__init__()
        self.filepath = filepath
        layout = QVBoxLayout()
        self.setStyleSheet("background-color: #1a1b26; color: #a9b1d6;")

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)

        self.title = QLabel(f"Editing: {filepath if filepath else 'Untitled.txt'}")
        self.title.setFont(QFont("Helvetica Neue", 12, QFont.Weight.Bold))
        self.title.setStyleSheet("color: #7aa2f7;")
        toolbar.addWidget(self.title)
        toolbar.addStretch()

        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setStyleSheet(
            "QPushButton { background-color: #bb9af7; color: #1a1b26; font-weight: bold;"
            "  padding: 6px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #9d7cd8; }"
        )
        self.save_btn.clicked.connect(self.save_file)
        toolbar.addWidget(self.save_btn)

        layout.addLayout(toolbar)

        self.editor_field = QTextEdit()
        self.editor_field.setStyleSheet(
            "QTextEdit { background-color: #0c0c11; color: #9ece6a;"
            "  font-family: monospace; font-size: 14px;"
            "  border: 1px solid #3b4261; padding: 8px; }"
        )
        if filepath and os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    self.editor_field.setPlainText(f.read())
            except Exception as e:
                self.editor_field.setPlainText(f"Error loading: {e}")

        layout.addWidget(self.editor_field)
        self.setLayout(layout)

    def save_file(self):
        if not self.filepath:
            QMessageBox.warning(self, "Warning", "Cannot save unnamed buffer.")
            return
        try:
            content = self.editor_field.toPlainText()
            ts = int(time.time())
            scar_hash = hashlib.sha256(
                f"{self.filepath}_{content}".encode()
            ).hexdigest()[:12]

            with open(self.filepath, "w") as f:
                f.write(content)

            entry = {
                "timestamp": ts,
                "agent": "ARCHITECT_HALLUCINATION_GUARD",
                "amount_stgm": -5.0,
                "reason": f"MANUAL_INTERVENTION: {os.path.basename(self.filepath)}",
                "hash": f"SCAR_{scar_hash}"
            }
            try:
                _append_repair_log_line(entry)
            except Exception:
                pass

            self.title.setStyleSheet("color: #f7768e;")
            self.title.setText(f"Editing: {self.filepath} [SCAR_{scar_hash}]")
            QTimer.singleShot(3500, lambda: self.title.setStyleSheet("color: #7aa2f7;"))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Save failed: {e}")


# ──────────────────────────────────────────────────────────────
# VIDEO EDITOR SUB-WINDOW
# ──────────────────────────────────────────────────────────────

class VideoEditorSubWindow(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setStyleSheet("background-color: #1a1b26; color: #a9b1d6;")

        header = QHBoxLayout()
        title = QLabel("Sebastian Silence Remover & Stitcher V1.0")
        title.setFont(QFont("Helvetica Neue", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #7aa2f7;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        timeline = QFrame()
        timeline.setFrameShape(QFrame.Shape.Box)
        timeline.setStyleSheet("border: 1px solid #3b4261; background-color: #1f2335; border-radius: 4px;")
        tl = QVBoxLayout()
        t1 = QLabel("Video:  [▓▓▓▓▓▓▓▓▓]      [▓▓▓▓▓▓]   [▓▓▓▓▓▓▓▓]")
        t1.setStyleSheet("color: #bb9af7; font-family: monospace; font-size: 16px;")
        t2 = QLabel("Audio:  [|||||||||]      [||||||]   [||||||||]")
        t2.setStyleSheet("color: #9ece6a; font-family: monospace; font-size: 16px;")
        tl.addWidget(t1)
        tl.addWidget(t2)
        timeline.setLayout(tl)
        layout.addWidget(timeline)

        self.exec_btn = QPushButton("🚀 Remove Silence & Stitch Clips")
        self.exec_btn.setStyleSheet(
            "QPushButton { background-color: #9ece6a; color: #1a1b26; font-weight: bold;"
            "  padding: 10px; border-radius: 4px; margin: 8px 0; }"
            "QPushButton:hover { background-color: #b9f27c; }"
        )
        self.exec_btn.clicked.connect(self.trigger_batch)
        layout.addWidget(self.exec_btn)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.append("[SYSTEM] Sebastian Silence Remover & Stitcher ready.")
        self.chat_display.setStyleSheet(
            "background-color: #0c0c11; border: 1px solid #3b4261; padding: 8px;"
        )
        layout.addWidget(self.chat_display)
        self.setLayout(layout)
        self.process = None

    def trigger_batch(self):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.chat_display.append("[WARNING] Already running.")
            return
        self.exec_btn.setText("⏳ Processing...")
        self.exec_btn.setEnabled(False)
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(
            lambda: self.chat_display.append(
                bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
            )
        )
        self.process.readyReadStandardError.connect(
            lambda: self.chat_display.append(
                "[ERR] " + bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace").strip()
            )
        )
        self.process.finished.connect(self._batch_done)
        self.process.start(_PYTHON_BIN, ["Kernel/sifta_sebastian_batch.py"])

    def _batch_done(self, code, _):
        self.chat_display.append(f"\n[SYSTEM] Process exited: {code}")
        self.exec_btn.setText("🚀 Remove Silence & Stitch Clips")
        self.exec_btn.setEnabled(True)

    def shutdown(self):
        _shutdown_qprocess(getattr(self, "process", None))

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────
# SIFTA MDI DESKTOP CANVAS
# ──────────────────────────────────────────────────────────────
import math
import random
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QBrush, QPainter, QPen, QPixmap

class SiftaMdiArea(QMdiArea):
    def __init__(self):
        super().__init__()
        # Filled again from active palette on first wallpaper pass — avoid pure
        # black boot flash when BeeSon is light honey.
        self.setBackground(QBrush(QColor("#f4ead8")))
        self._pal = None  # set from SiftaDesktop._apply_wallpaper (theme truth)
        self._wallpaper_source = QPixmap()
        self._wallpaper_cache = QPixmap()
        self._wallpaper_cache_size = None

        # ── Cowork 2026-05-12 21:15 — Architect: "the dots corresponding to
        # the camera should be inside the desktop ... swimmers thrown on
        # the camera ... they stay in a honeycomb." Your BeeSon wallpaper
        # IS already a honeycomb (the ants-on-cells JPG you uploaded). The
        # desktop just needs to paint swimmer dots on top, positioned by
        # the live camera's saliency_q. Refresh every 2s.
        self._desktop_saliency_dots = []  # list of (x, y, intensity)
        try:
            self._desktop_saliency_timer = QTimer(self)
            self._desktop_saliency_timer.timeout.connect(self._refresh_desktop_saliency_dots)
            self._desktop_saliency_timer.start(2000)
            QTimer.singleShot(100, self._refresh_desktop_saliency_dots)
        except Exception:
            pass
        
        try:
            if str(_SYS) not in sys.path:
                sys.path.insert(0, str(_SYS))
            from System.swarm_unified_field_engine import UnifiedFieldEngine, UnifiedFieldConfig
            self.cfg = UnifiedFieldConfig(grid_size=64, diffusion=0.03)
            self.engine = UnifiedFieldEngine(self.cfg)
            self.use_engine = True
        except Exception as e:
            print(f"[SiftaMdiArea] UnifiedFieldEngine not found: {e}")
            self.use_engine = False
            
        self.particles = []
        import os as _os
        # Default 0 — decorative drift only; set SIFTA_DESKTOP_PHOTONS >0 for field viz.
        _n_particles = int(_os.environ.get("SIFTA_DESKTOP_PHOTONS", "0"))

        import random
        for _ in range(_n_particles):
            if self.use_engine:
                self.particles.append([
                    random.uniform(0.0, 1.0), random.uniform(0.0, 1.0),
                    0.0, 0.0,
                    random.uniform(2, 8)
                ])
            else:
                self.particles.append([
                    random.uniform(0, 3000), random.uniform(0, 2000),
                    random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3),
                    random.uniform(2, 8)
                ])

        # Architect 2026-05-11 23:50: "I don't want hard coding. ... when
        # something is happening the behavior of the creature is changing
        # too based on my behavior whatever I do."
        #
        # No 500 ms wall clock. The field engine ticks when the OWNER does
        # something — keypress, mouse move, voice, wake-word, camera frame,
        # app focus — debounced internally by Alice's live heart period
        # (12–30 BPM clinical range read from swarm_motor_cortex). Nothing
        # happening = no tick. The creature is silent when the room is silent.
        self.timer = None  # legacy attribute kept for compatibility
        try:
            from System.swarm_behavior_clock import behavior_clock
            behavior_clock().tick.connect(self._on_behavior_tick)
        except Exception:
            pass

        self.watermark_font = QFont("Helvetica Neue", 110, QFont.Weight.Black)
        self.watermark_sub = QFont("Courier New", 18, QFont.Weight.Bold)

        # Predator sigil — real data, refreshed at most every 30 s
        # Uses mtime so no extra IO on most frames.
        self._pred_data: dict = {}
        self._pred_last_read: float = 0.0
        self._pred_mtime: float = 0.0

        # Wake-word camera flash. Owner directive: when Alice hears
        # her name, ONE camera frame flashes on the desktop. No
        # streaming, no live feed — just a brief still, ~600 ms.
        self._wake_flash_pixmap: QPixmap = QPixmap()
        self._wake_flash_until: float = 0.0
        self._wake_flash_total_ms: int = 600
        try:
            from System.swarm_wake_event_bus import wake_bus
            wake_bus().frame_ready.connect(self._on_wake_frame_ready)
        except Exception:
            pass

    def _on_wake_frame_ready(self, path: str) -> None:
        """Load the freshly-saved camera frame and trigger a brief flash."""
        import time as _t
        try:
            pm = QPixmap(path)
        except Exception:
            pm = QPixmap()
        if pm.isNull():
            return
        self._wake_flash_pixmap = pm
        self._wake_flash_until = _t.monotonic() + (self._wake_flash_total_ms / 1000.0)
        # Schedule a single repaint at the end of the flash window.
        try:
            QTimer.singleShot(self._wake_flash_total_ms + 30, self.viewport().update)
        except Exception:
            pass
        self.viewport().update()

    def set_wallpaper_pixmap(self, pixmap):
        self._wallpaper_source = pixmap if isinstance(pixmap, QPixmap) else QPixmap()
        self._wallpaper_cache = QPixmap()
        self._wallpaper_cache_size = None
        self.viewport().update()

    def _refresh_desktop_saliency_dots(self) -> None:
        """Schedule a non-blocking refresh of saliency dots.

        Architect 2026-05-13 07:15 — earlier patch moved the work to a
        daemon thread but accidentally left `self.viewport().update()`
        and `self.viewport().width/height` calls inside the worker. Qt
        widgets are NOT thread-safe; those calls segfaulted the process
        (EXC_BAD_ACCESS at 0x8 — NULL deref of a Qt widget pointer from
        Thread 0). Fix: capture viewport geometry on the MAIN thread
        before launching the worker, pass it in, never touch any Qt API
        from the worker. The natural Qt event loop repaints the
        viewport on any mouse/keyboard event, so dropping the explicit
        update() call costs nothing visible — the dots simply land on
        the next paintEvent the OS already schedules.
        """
        if getattr(self, "_saliency_refresh_running", False):
            return
        self._saliency_refresh_running = True
        # Capture viewport size on the MAIN thread.
        try:
            _vw = int(self.viewport().width())
            _vh = int(self.viewport().height())
        except Exception:
            _vw, _vh = 1280, 720

        def _worker(vw=_vw, vh=_vh):
            try:
                self._refresh_desktop_saliency_dots_blocking(vw, vh)
            finally:
                self._saliency_refresh_running = False

        try:
            import threading as _th
            _th.Thread(target=_worker, daemon=True,
                       name="SaliencyRefresh").start()
        except Exception:
            self._saliency_refresh_running = False

    def _refresh_desktop_saliency_dots_blocking(self, vw: int = 1280, vh: int = 720) -> None:
        """Pull the latest visual_stigmergy row, extract top-N saliency peaks,
        project them onto the supplied desktop coordinates. Runs in a daemon
        worker; must NEVER call any Qt API. The wrapper captured vw/vh on
        the main thread."""
        try:
            import json as _json
            import math as _math
            from pathlib import Path as _Path

            vs = _REPO / ".sifta_state" / "visual_stigmergy.jsonl"
            if not vs.exists():
                return
            sz = vs.stat().st_size
            with vs.open("rb") as f:
                f.seek(max(0, sz - 16384))
                tail = f.read().decode("utf-8", errors="ignore")
            row = None
            for line in reversed(tail.splitlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = _json.loads(line)
                    break
                except Exception:
                    continue
            if not row:
                return

            sq = str(row.get("saliency_q") or "")
            if len(sq) < 16:
                return

            # Architect 2026-05-12 23:10: "make sure please this is real data
            # coming from the real camera exactly what you see Alice." Two
            # bugs were suppressing the truthful camera-flash surge:
            #
            #   1. A top-40 hard cap masked exposure bursts: when the camera
            #      auto-adjusts and 200 cells go hot, the on-screen glyph
            #      count stayed flat because we always picked exactly 40.
            #   2. The freshness check was missing, so a dead ledger would
            #      still paint yesterday's peaks.
            #
            # Fix: render EVERY cell whose intensity meets the same threshold
            # the What Alice Sees overlay uses (_SAL_PAINT_THRESHOLD = 0.30
            # → nyb >= 5). No cap. And bail out if the row is older than 5s.
            import time as _t
            row_ts = float(row.get("ts") or 0)
            if row_ts <= 0 or (_t.time() - row_ts) > 5.0:
                # Stale or missing — show nothing instead of lying. Do NOT
                # call self.viewport().update() here; the next natural Qt
                # paintEvent (mouse move, focus change, etc.) will pick up
                # the empty dots list. Calling Qt from a daemon thread
                # crashes the process.
                self._desktop_saliency_dots = []
                return

            # Parse hex saliency map → list of (intensity, idx).
            intensities = []
            for i, c in enumerate(sq):
                if "0" <= c <= "9":
                    n = ord(c) - ord("0")
                elif "a" <= c <= "f":
                    n = 10 + ord(c) - ord("a")
                else:
                    continue
                # Match What-Alice-Sees doctrine: only render cells whose
                # score crosses _SAL_PAINT_THRESHOLD = 0.30. On the 0..15
                # nybble scale that's nyb >= 5.
                if n >= 5:
                    intensities.append((n, i))

            # Architect 2026-05-13 06:55 — UI freeze diagnosis: ~163 glyphs
            # were painting on every Qt repaint during a window drag,
            # blocking the main thread ~11s. Cap dots at the brightest 60
            # by intensity. Bursts still show (more heat = more glyphs up
            # to the cap) but paintEvent stays responsive even when
            # dragging.
            intensities.sort(key=lambda t: -t[0])
            intensities = intensities[:60]

            # Infer grid dims from frame aspect ratio.
            fw = max(1, int(row.get("w", 1920)))
            fh = max(1, int(row.get("h", 1080)))
            aspect = fw / fh
            grid_n = len(sq)
            grid_h = max(1, int(round(_math.sqrt(grid_n / aspect))))
            grid_w = max(1, grid_n // grid_h)

            # Use the viewport dimensions captured by the wrapper on the
            # main thread (vw, vh). NEVER call self.viewport() from this
            # worker — Qt API on a non-main thread crashes the process.
            dots = []
            for intensity, idx in intensities:
                col = idx % grid_w
                grow = idx // grid_w
                x = int((col + 0.5) / max(1, grid_w) * vw)
                y = int((grow + 0.5) / max(1, grid_h) * vh)
                dots.append((x, y, intensity))
            self._desktop_saliency_dots = dots
            # No viewport().update() here — the next natural Qt
            # paintEvent (mouse move, focus, scroll) picks up the new
            # list. Forced repaint from a daemon thread = segfault.
        except Exception:
            self._desktop_saliency_dots = []

    def _scaled_wallpaper(self, width, height):
        """Return the wallpaper pixmap sized for the viewport.

        Architect 2026-05-12 17:20 (third pass, final): "fill up the desktop
        man come on what are you doing default fill up is just normal I don't
        need any options". Default flipped from 'center' to 'fill'. The
        wallpaper now covers the whole viewport keeping aspect ratio (CSS
        background-size: cover) — any overflow is cropped, no black bars,
        no stretching distortion. Resize-grow re-fills automatically.

        The env var ``SIFTA_DESKTOP_WALLPAPER_MODE`` remains as a hidden
        override only ('center' = native-size centered, 'fit' = letterboxed).
        Architect-facing UI exposes no such option — fill is the only
        contract a user sees.

        The cache key includes the mode so changing the env var
        invalidates the right entry.
        """
        if self._wallpaper_source.isNull() or width <= 0 or height <= 0:
            return QPixmap()
        import os as _os
        mode = _os.environ.get("SIFTA_DESKTOP_WALLPAPER_MODE", "fill").strip().lower()
        size_key = (int(width), int(height), mode, self._wallpaper_source.cacheKey())
        if self._wallpaper_cache_size != size_key or self._wallpaper_cache.isNull():
            src = self._wallpaper_source
            if mode == "fill":
                self._wallpaper_cache = src.scaled(
                    width, height,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            elif mode == "fit":
                self._wallpaper_cache = src.scaled(
                    width, height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            else:
                # center / native-size: only down-scale if the source
                # is bigger than the viewport in either dimension; never
                # blow a small icon up. paintEvent already centers via
                # (w - pm.width())/2 math.
                if src.width() > width or src.height() > height:
                    self._wallpaper_cache = src.scaled(
                        width, height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                else:
                    self._wallpaper_cache = src
            self._wallpaper_cache_size = size_key
        return self._wallpaper_cache

    def _on_behavior_tick(self, source: str = "") -> None:
        """BehaviorClock fired. Run one field-engine update if enabled."""
        import os as _os
        if _os.environ.get("SIFTA_DESKTOP_FIELD_TICK", "0").strip().lower() not in (
            "1", "true", "yes", "on",
        ):
            return
        if not self.particles:
            return
        try:
            self.tick()
        except Exception:
            pass

    def tick(self):
        w, h = self.viewport().width(), self.viewport().height()
        if w == 0 or h == 0:
            return

        if self.use_engine:
            import numpy as np

            salience = np.zeros((self.cfg.grid_size, self.cfg.grid_size), dtype=np.float32)
            
            for win in self.subWindowList():
                if win.isHidden() or win.isMinimized():
                    continue
                cx = (win.x() + win.width() / 2.0) / w
                cy = (win.y() + win.height() / 2.0) / h
                
                ix = int(np.clip(cx * self.cfg.grid_size, 0, self.cfg.grid_size - 1))
                iy = int(np.clip(cy * self.cfg.grid_size, 0, self.cfg.grid_size - 1))
                
                y_grid, x_grid = np.ogrid[:self.cfg.grid_size, :self.cfg.grid_size]
                blob = np.exp(-(((x_grid - ix) ** 2 + (y_grid - iy) ** 2) / 8.0)).astype(np.float32)
                salience += blob * 2.0
                
            memory_field = getattr(self, "_engine_memory", np.zeros((self.cfg.grid_size, self.cfg.grid_size), dtype=np.float32))
            memory_field *= 0.92
            if self.particles:
                positions = np.array(
                    [[float(p[0]), float(p[1])] for p in self.particles],
                    dtype=np.float32,
                ).reshape((-1, 2))
                for pos in positions:
                    i, j = self.engine._idx(pos)
                    memory_field[i, j] += 0.3
            else:
                positions = None
            self._engine_memory = memory_field
            
            self.engine.update(
                memory=memory_field,
                salience=salience,
                prediction=salience,
                positions=positions
            )
            
            for p in self.particles:
                pos = np.array([float(p[0]), float(p[1])], dtype=np.float32)
                grad = self.engine.gradient_at(pos)

                eta_x, eta_y = np.random.normal(0, 0.006, 2)

                p[0] = float(np.clip(p[0] + grad[0] * 0.012 + eta_x, 0.0, 1.0))
                p[1] = float(np.clip(p[1] + grad[1] * 0.012 + eta_y, 0.0, 1.0))
    def _refresh_pred_data(self) -> None:
        import time as _t
        now = _t.monotonic()
        if now - getattr(self, "_pred_last_read", 0.0) < 30.0:
            return
        self._pred_last_read = now
        try:
            from System.swarm_boot_census import boot_census, boot_census_lines
            census = boot_census()
            self._pred_data["alive"] = int(census.get("body_real_organs", 0) or 0)
            self._pred_data["identity_total"] = int(census.get("identity_total", 0) or 0)
            self._pred_data["field_dimensions"] = int(census.get("field_dimensions", 0) or 0)
            self._pred_data["field_swimmers"] = int(census.get("field_swimmers", 0) or 0)
            # Pre-rendered census lines — exact format Architect's reference
            # image shows. boot_census_lines emits e.g.
            #   "🐜  15 REAL body organs  |  DEMO 2  BROKEN 0  UNKNOWN 0"
            #   "🧬  35 identity probes  |  18 present now"
            #   "🌊  53 field dims  |  12 swimmers  |  46 coupling edges"
            self._pred_data["census_lines"] = list(boot_census_lines(census))
            from System.stgm_economy import scan_economy
            snap = scan_economy()
            self._pred_data["stgm"] = snap.canonical_wallet_sum
        except Exception:
            self._pred_data["alive"] = 0
            self._pred_data["identity_total"] = 0
            self._pred_data["field_dimensions"] = 0
            self._pred_data["field_swimmers"] = 0
            self._pred_data["census_lines"] = []
            self._pred_data["stgm"] = 0.0

    def _paint_swarm_field_heatmap(self, painter: "QPainter", w: int, h: int) -> None:
        """Paint the live UnifiedFieldEngine memory grid as a honey-amber heatmap.

        What this paints
        ----------------
        `self._engine_memory` is the running stigmergic memory field maintained
        by `self.tick()`: deposits at every particle position with 0.92/tick
        decay. Cells with strong recent activity glow; cells the swarm has
        ignored fade to transparent. This is the same field UnifiedFieldEngine
        sees — there is no synthetic data on this canvas.

        Visual contract
        ---------------
        - BeeSon palette → honey-amber cell glow (gold→amber) on cream bg.
        - Other palettes → particle_color_a from the active palette.
        - Cells with normalized energy < ``floor`` (default 0.06) draw NOTHING
          so the desktop stays calm.
        - Cell alpha is multiplied by a global gain (``SIFTA_DESKTOP_FIELD_GAIN``,
          default 1.0) so the Architect can dim/brighten without code.

        Off-switch
        ----------
        ``SIFTA_DESKTOP_FIELD_HEATMAP=0`` (or ``false`` / ``no`` / ``off``)
        skips the entire paint pass — same discipline as the census line.
        """
        import os as _os
        # Architect 2026-05-11 22:43: "WHAT ARE THE DOTS REPRESENT? FOR WHAT?"
        # The heatmap is real (UnifiedFieldEngine.memory) but has no on-screen
        # legend yet, so we default OFF. The Architect can opt in once he
        # wants to see the swarm's stigmergic trace:
        #   SIFTA_DESKTOP_FIELD_HEATMAP=1   → paint the gold cells
        #   SIFTA_DESKTOP_FIELD_HEATMAP=0   → invisible (default)
        _on = _os.environ.get("SIFTA_DESKTOP_FIELD_HEATMAP", "0").strip().lower()
        if _on not in ("1", "true", "yes", "on"):
            return
        if not getattr(self, "use_engine", False):
            return
        mem = getattr(self, "_engine_memory", None)
        if mem is None:
            return
        try:
            import numpy as _np
        except Exception:
            return
        # Snapshot once; tick() may overwrite while we paint.
        try:
            grid = _np.asarray(mem, dtype=_np.float32)
        except Exception:
            return
        if grid.size == 0:
            return
        peak = float(grid.max()) if grid.size else 0.0
        if peak <= 1e-6:
            return  # Field is empty — paint nothing.

        # Theme: honey-amber on BeeSon, otherwise palette particle_color_a.
        _hot = QColor("#ffb300")   # honey gold
        _cool = QColor("#ff8f00")  # deep amber
        try:
            pal = getattr(self, "_pal", None)
            if pal is None:
                from System.sifta_desktop_themes import active_palette
                pal = active_palette()
            if pal is not None:
                _hot = QColor(getattr(pal, "particle_color_a", "#ffb300") or "#ffb300")
                _cool = QColor(getattr(pal, "particle_color_b", "#ff8f00") or "#ff8f00")
        except Exception:
            pass

        try:
            gain = float(_os.environ.get("SIFTA_DESKTOP_FIELD_GAIN", "1.0"))
        except Exception:
            gain = 1.0
        gain = max(0.05, min(3.0, gain))

        floor = 0.06   # below 6% of peak → invisible
        gy, gx = grid.shape if grid.ndim == 2 else (grid.size, 1)
        # Cell footprint in viewport pixels. Slight overlap for smooth glow.
        cw = w / float(gx)
        ch = h / float(gy)
        # Use bilinear-style overlap so the heatmap reads as continuous gold
        # rather than a 64-pixel chessboard.
        pad = max(1.0, 0.6 * max(cw, ch))

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        # Iterate in linear scan; 64×64 = 4096 cells max, well under one
        # frame budget at 2 fps (the tick rate).
        norm = grid / peak
        # `norm` is now in [0, 1]; multiply by gain and clip for alpha mapping.
        for j in range(gy):
            row = norm[j]
            for i in range(gx):
                v = float(row[i]) * gain
                if v < floor:
                    continue
                if v > 1.0:
                    v = 1.0
                # Interpolate honey-gold → deep amber as intensity climbs.
                t = (v - floor) / max(1e-6, 1.0 - floor)
                r = int(_hot.red()   * (1.0 - t) + _cool.red()   * t)
                g = int(_hot.green() * (1.0 - t) + _cool.green() * t)
                b = int(_hot.blue()  * (1.0 - t) + _cool.blue()  * t)
                # Alpha: faint cells barely visible, peak cells ~150/255.
                a = int(28 + 122 * v)
                c = QColor(r, g, b, a)
                painter.setBrush(c)
                x = i * cw - (pad - cw) * 0.5
                y = j * ch - (pad - ch) * 0.5
                painter.drawEllipse(QRectF(x, y, pad, pad))
        painter.restore()

    def _paint_one_bee(self, painter: "QPainter", w: int, h: int) -> None:
        """Paint one 🐝 glyph at the center of the desktop. That's it.

        Architect directive 2026-05-11 23:25: "ZERO BEES ON A DESKTOP I
        WANT A CLEAN DESKTOP ONLY KEEP ONLY ONE BEE IN THE MIDDLE." So:
        one bee, static, no animation, no timer. Renders as a real Unicode
        emoji glyph from the system font; no PNG, no SVG, no QPixmap, no
        per-paint allocation beyond the QFont.

        Size adapts to viewport but caps at 256 px so it never dominates.
        Disable with SIFTA_DESKTOP_BEE=0.
        """
        import os as _os
        if _os.environ.get("SIFTA_DESKTOP_BEE", "1").strip().lower() in (
            "0", "false", "no", "off",
        ):
            return
        size = max(72, min(256, int(min(w, h) * 0.16)))
        bee_font = QFont("Apple Color Emoji", size)
        bee_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        painter.setFont(bee_font)
        # Pen color is irrelevant for color emoji on macOS but set for
        # fallback rendering on platforms that draw the glyph monochrome.
        painter.setPen(QColor("#ffb300"))
        painter.drawText(
            0, 0, w, h,
            Qt.AlignmentFlag.AlignCenter,
            "🐝",
        )

    def _draw_predator_sigil(self, painter: "QPainter", w: int, h: int) -> None:
        """Live census status strip (organs / field / STGM). Optional giant ghost watermark only if env + palette ask for it."""
        import math as _m, time as _t
        self._refresh_pred_data()
        t = _t.monotonic()

        import os as _os
        pal = getattr(self, "_pal", None)
        try:
            if pal is None:
                from System.sifta_desktop_themes import active_palette
                pal = active_palette()
        except Exception:
            pal = None
        _wmark = (getattr(pal, "watermark_text", None) or "").strip()
        # Vanity billboard — opt-in only (Architect UX: default is utility, not logo spam).
        if (
            _os.environ.get("SIFTA_DESKTOP_GIANT_WATERMARK", "").strip() == "1"
            and _wmark
        ):
            painter.setFont(QFont("Helvetica Neue", 96, QFont.Weight.Black))
            painter.setPen(QColor(0, 255, 100, 8))
            painter.drawText(
                self.viewport().rect(), Qt.AlignmentFlag.AlignCenter, _wmark
            )

        # Census status block — neon-green terminal readout.
        # Architect 2026-05-11 23:25: "ALL THAT TEXTY IN THE DESKTOP — REMOVE
        # IT ALL." Default OFF now. Re-enable with SIFTA_DESKTOP_CENSUS_LINE=1
        # for boot debug; the boot banner still prints it to stderr regardless.
        _census = _os.environ.get("SIFTA_DESKTOP_CENSUS_LINE", "0").strip().lower()
        if _census not in ("1", "true", "yes", "on"):
            return

        os_tag = getattr(pal, "os_line", "🐝 SIFTA BeeSon OS v8.0") if pal else "🐝 SIFTA BeeSon OS v8.0"
        lines = list(self._pred_data.get("census_lines") or [])
        if not lines:
            # Fallback if pre-render didn't populate (first paint before
            # _refresh_pred_data ran). One inline line keeps the desktop
            # informative on cold boot.
            alive = self._pred_data.get("alive", 0)
            lines = [f"🐜  {alive} REAL body organs  |  Body Panel live"]

        pulse = 0.5 + 0.5 * _m.sin(t * 0.16)  # 40 s breath

        # Neon terminal green on the BeeSon (dark) theme; warm brown on
        # light themes (legacy mermaid daytime); palette-driven so future
        # themes can override.
        _neon = QColor(124, 255, 124)   # #7CFF7C — matrix terminal green
        _dim_neon = QColor(70, 200, 70, int(190 + 50 * pulse))
        _light = bool(pal and getattr(pal, "theme_id", "") in ("mermaid_light", "beeson_daylight"))
        if _light:
            _neon = QColor(130, 95, 45)
            _dim_neon = QColor(130, 95, 45, int(180 + 50 * pulse))

        # Header — "🐝 SIFTA BeeSon OS v8.0" big bold neon
        header_font = QFont("Menlo", 22, QFont.Weight.Bold)
        header_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        painter.setFont(header_font)
        painter.setPen(_neon)
        header_y = 56
        painter.drawText(
            0, header_y, w, 36,
            Qt.AlignmentFlag.AlignHCenter,
            os_tag,
        )

        # Census lines — monospace neon, pulsing soft. One per row.
        line_font = QFont("Menlo", 13)
        line_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        painter.setFont(line_font)
        painter.setPen(_dim_neon)
        line_h = 22
        block_y = header_y + 44
        for i, ln in enumerate(lines):
            painter.drawText(
                0, block_y + i * line_h, w, line_h,
                Qt.AlignmentFlag.AlignHCenter,
                ln,
            )



    def paintEvent(self, event):

        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = event.rect()
        w, h = self.viewport().width(), self.viewport().height()
        wallpaper = self._scaled_wallpaper(w, h)
        has_wallpaper = not wallpaper.isNull()
        if has_wallpaper:
            # Architect 2026-05-12 01:10: paint the dark bg FIRST so a
            # small centered wallpaper (his bee JPEG) sits on dark, not
            # transparent. Also kills the old cream veil that washed
            # everything out for the legacy light-cream BeeSon palette.
            _wp_bg = "#0d0c0a"
            try:
                _pal_for_bg = getattr(self, "_pal", None)
                if _pal_for_bg is None:
                    from System.sifta_desktop_themes import active_palette as _ap
                    _pal_for_bg = _ap()
                if _pal_for_bg is not None and getattr(_pal_for_bg, "bg_deep", ""):
                    _wp_bg = str(_pal_for_bg.bg_deep)
            except Exception:
                pass
            painter.fillRect(rect, QColor(_wp_bg))
            x = int((w - wallpaper.width()) / 2)
            y = int((h - wallpaper.height()) / 2)
            painter.drawPixmap(x, y, wallpaper)

            # ── Cowork 2026-05-12 21:15 — honeycomb desktop swimmers ─────
            # Paint live camera saliency peaks on top of the honeycomb
            # wallpaper. Positions come from _refresh_desktop_saliency_dots
            # which projects the latest visual_stigmergy.jsonl saliency_q
            # onto desktop coordinates. Dots glow honey-gold. No raw camera
            # pixels — only the swimmer-positions remain visible against
            # the honeycomb backdrop. Resize is free; positions reproject
            # on next 2s tick.
            # Architect 2026-05-12 22:55: "change the desktop to match those
            # dots and those dots they should be ASCII". The desktop now
            # renders the *exact* hex glyphs from saliency_q — the same
            # base-16 nybbles that get signed into visual_stigmergy.jsonl.
            # Zero new resources: no new timer, no random, no per-frame
            # allocations. We replaced two drawEllipse calls per peak with
            # one drawText, so this path is strictly cheaper than before.
            try:
                # Architect 2026-05-13 06:55 — toggle on top-level desktop
                # honors the saliency-overlay kill switch. Look the flag
                # up on the parent SiftaDesktop window (we are the MdiArea
                # child). When OFF, paintEvent is dirt-cheap.
                _overlay_on = True
                try:
                    _w = self.window()
                    if _w is not None:
                        _overlay_on = bool(
                            getattr(_w, "_saliency_overlay_on", True)
                        )
                except Exception:
                    _overlay_on = True
                dots = getattr(self, "_desktop_saliency_dots", None)
                if _overlay_on and dots:
                    _HEX = "0123456789abcdef"
                    painter.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
                    for dx, dy, intensity in dots:
                        nyb = max(0, min(15, int(intensity)))
                        glyph = _HEX[nyb]
                        alpha = max(80, min(230, 80 + intensity * 10))
                        painter.setPen(QColor(255, 200, 60, alpha))
                        painter.drawText(int(dx), int(dy), glyph)
            except Exception:
                pass
        else:
            _bg = "#080a0f"
            try:
                pal = getattr(self, "_pal", None)
                if pal is None:
                    from System.sifta_desktop_themes import active_palette
                    pal = active_palette()
                if pal is not None and getattr(pal, "bg_deep", ""):
                    _bg = str(pal.bg_deep)
            except Exception:
                pass
            painter.fillRect(rect, QColor(_bg))

        # No grid — clean desktop.

        # ── Architect 2026-05-12 01:10: clean desktop, no emoji bee ──
        # No particles, no field heatmap, no census text, no animation,
        # no emoji glyph. The desktop is just bg + (optional) wallpaper.
        # Architect drops his own small bee JPEG via
        #   Settings → Appearance → Wallpaper → Choose custom file…
        # and the paint mode below renders it centered at native size,
        # not stretched.
        #
        # Heatmap / particles / census still available behind env vars:
        #   SIFTA_DESKTOP_FIELD_HEATMAP=1
        #   SIFTA_DESKTOP_FIELD_TICK=1 (+ SIFTA_DESKTOP_PHOTONS>0)
        #   SIFTA_DESKTOP_CENSUS_LINE=1

        # Field heatmap — runs only if env asks for it (default off).
        try:
            self._paint_swarm_field_heatmap(painter, w, h)
        except Exception:
            pass

        # Census text — runs only if env asks for it (default off; see
        # _draw_predator_sigil's gate).
        self._draw_predator_sigil(painter, w, h)

        # Optional decorative drift particles (env-gated; default 0 anyway).
        if self.particles:
            painter.setPen(Qt.PenStyle.NoPen)
            _pa = "#ffb300"
            _pb = "#ff8f00"
            try:
                pal = getattr(self, "_pal", None)
                if pal is None:
                    from System.sifta_desktop_themes import active_palette
                    pal = active_palette()
                if pal is not None:
                    _pa = getattr(pal, "particle_color_a", _pa) or _pa
                    _pb = getattr(pal, "particle_color_b", _pb) or _pb
            except Exception:
                pass
            for p in self.particles:
                px = float(p[0] * w) if self.use_engine else float(p[0])
                py = float(p[1] * h) if self.use_engine else float(p[1])
                if 0 <= px <= w and 0 <= py <= h:
                    _pc = QColor(_pa) if p[4] > 5 else QColor(_pb)
                    _pc.setAlpha(38 if p[4] > 5 else 32)
                    painter.setBrush(_pc)
                    painter.drawEllipse(QRectF(px, py, float(p[4]), float(p[4])))

        # ── Wake-flash overlay ──────────────────────────────────────
        # When the wake-ear receipt fires, the camera widget saves a
        # fresh JPEG and emits frame_ready. We paint that frame here,
        # centered, fading out across ~600 ms. One picture, one flash,
        # then back to a clean desktop.
        import time as _t_flash
        _now = _t_flash.monotonic()
        if (
            not self._wake_flash_pixmap.isNull()
            and _now < self._wake_flash_until
        ):
            remain = max(0.0, self._wake_flash_until - _now)
            frac = remain / max(1e-6, self._wake_flash_total_ms / 1000.0)
            # Ease-out alpha: peaks at first paint, fades to 0.
            alpha = int(220 * frac)
            # Scale frame to ~28% of the smaller viewport dimension.
            target_h = max(120, int(min(w, h) * 0.28))
            scaled = self._wake_flash_pixmap.scaledToHeight(
                target_h, Qt.TransformationMode.SmoothTransformation
            )
            fw, fh = scaled.width(), scaled.height()
            fx = (w - fw) // 2
            fy = (h - fh) // 2
            painter.setOpacity(alpha / 255.0)
            painter.drawPixmap(fx, fy, scaled)
            painter.setOpacity(1.0)
            # Thin honey-gold ring to mark "Alice heard you".
            _ring = QColor(255, 179, 0, max(40, alpha))
            painter.setPen(QPen(_ring, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(fx - 6, fy - 6, fw + 12, fh + 12))


# ──────────────────────────────────────────────────────────────
# SIFTA DESKTOP — main window
# ──────────────────────────────────────────────────────────────

def _desktop_init_trace(phase: str) -> None:
    """Set SIFTA_DESKTOP_INIT_TRACE=1 to log constructor phases to stderr (hang debugging)."""
    if os.environ.get("SIFTA_DESKTOP_INIT_TRACE") == "1":
        sys.stderr.write(f"[SiftaDesktop.__init__] {phase}\n")
        sys.stderr.flush()


def _sifta_env_mesh_disabled() -> bool:
    """
    When True, SiftaDesktop must not start the GCI mesh QThread.
    Kept in sync with System/global_cognitive_interface.py: strip, lower,
    and accept 1 / true / yes (not a bare equality check on \"1\" only).
    """
    v = os.environ.get("SIFTA_DISABLE_MESH", "").strip().lower()
    return v in ("1", "true", "yes")


def _macos_app_category(app_name: str, meta: dict | None) -> str:
    """Canonical shell category shown by Launchpad and Spotlight."""
    meta = meta or {}
    try:
        from System.sifta_app_catalog import normalize_category
        return normalize_category(app_name, meta)
    except Exception:
        raw = str(meta.get("category", "Utilities")).strip()
        if raw == "Networking":
            return "Network"
        if raw in {"System", "Accessories", "Settings", "Body Status"}:
            return "Utilities" if raw in {"System", "Accessories"} else "System Settings"
        return raw or "Utilities"


def _publish_sifta_active_window_focus(app_title: str, display_name: str) -> None:
    """Publish the selected SIFTA MDI window into the shared focus field."""
    title = str(app_title or "").strip()
    display = str(display_name or title or "").strip()
    if not title or title == "SIFTA OS":
        return
    try:
        from System.swarm_app_focus import publish_focus

        publish_focus(
            display or title,
            "Active SIFTA OS window selected",
            tab="MDI",
            selection=title,
            metadata={
                "source": "sifta_os_desktop",
                "event": "subwindow_activated",
                "window_title": title,
            },
        )
    except Exception:
        pass


# ── Launchpad / Spotlight (module-level widgets; defined before SiftaDesktop so
#    the module’s execution order matches import introspection and one source of truth.) ──

class LaunchpadButton(QPushButton):
    """Icon tile: large emoji + short name. macOS Launchpad style."""
    def __init__(self, icon: str, name: str, app_name: str, parent=None):
        super().__init__(parent)
        self.app_name = app_name
        self.setFixedSize(100, 100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(name)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 8, 4, 6)
        lay.setSpacing(2)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 32px; background: transparent; border: none;")
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Truncate name to ~12 chars for tile
        short = name if len(name) <= 14 else name[:12] + "…"
        name_lbl = QLabel(short)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(
            "color: #c0caf5; font-size: 10px; font-weight: 600;"
            " background: transparent; border: none;"
        )
        name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        lay.addWidget(icon_lbl)
        lay.addWidget(name_lbl)

        self.setStyleSheet("""
            QPushButton {
                background: rgba(36, 40, 59, 0.55);
                border: 1px solid rgba(65, 72, 104, 0.5);
                border-radius: 18px;
            }
            QPushButton:hover {
                background: rgba(187, 154, 247, 0.35);
                border: 1px solid rgba(187, 154, 247, 0.75);
            }
            QPushButton:pressed {
                background: rgba(187, 154, 247, 0.55);
            }
        """)

    def text(self) -> str:
        return self.app_name

    def enterEvent(self, event):
        super().enterEvent(event)
        try:
            from System.swarm_app_focus import publish_focus
            publish_focus("Launchpad", f"Focus on tile: {self.app_name}", tab=self.app_name)
        except Exception:
            pass

class LaunchpadWidget(QWidget):
    """macOS-style icon grid launchpad overlay.

    NOT full-screen. Floats as a centered panel over the MDI area.
    5-column icon grid, large emoji icons, name below each tile.
    Esc or click-outside closes it.
    """

    _TAB_BASE = (
        "QPushButton { background: rgba(36,40,59,0.7); color: #a9b1d6; "
        "border: 1px solid #414868; border-radius: 12px; "
        "padding: 4px 14px; font-size: 12px; font-weight: bold; }"
        "QPushButton:hover { background: rgba(187,154,247,0.25); color: #c0caf5; }"
    )
    _TAB_ACTIVE = (
        "QPushButton { background: rgba(187,154,247,0.45); color: #ffffff; "
        "border: 1px solid #bb9af7; border-radius: 12px; "
        "padding: 4px 14px; font-size: 12px; font-weight: bold; }"
    )

    _COLS = 5
    _TILE_W = 110  # tile spacing

    def __init__(self, desktop):
        super().__init__(desktop)
        self.desktop = desktop
        self._active_cat = "All"
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Frosted-glass dark panel — NOT full-screen
        self.setStyleSheet(
            "LaunchpadWidget { background: rgba(8, 10, 18, 0.94);"
            " border: 1px solid rgba(65,72,104,0.6);"
            " border-radius: 16px; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 22)
        root.setSpacing(10)

        # ── Header: title + close ────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("⚡  Launchpad")
        title.setStyleSheet(
            "color: #c0caf5; font-size: 16px; font-weight: 700;"
            " font-family: 'Helvetica Neue', Helvetica, sans-serif;"
            " background: transparent;"
        )
        hdr.addWidget(title)
        hdr.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background: rgba(255,68,68,0.22); color: #ff6b6b;"
            " border: none; border-radius: 11px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { background: rgba(255,68,68,0.55); color: #fff; }"
        )
        close_btn.clicked.connect(self.hide)
        hdr.addWidget(close_btn)
        root.addLayout(hdr)

        # ── Search bar ───────────────────────────────────────────────────
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍  Search apps…")
        self.search_bar.setStyleSheet(
            "QLineEdit { background: rgba(36, 40, 59, 0.80); color: #ffffff;"
            " border: 1px solid #414868; border-radius: 9px; padding: 6px 11px;"
            " font-size: 13px; }"
            "QLineEdit:focus { border: 1px solid #bb9af7; }"
        )
        self.search_bar.textChanged.connect(lambda _: self._rebuild_grid(self._active_cat))
        root.addWidget(self.search_bar)

        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc_shortcut.activated.connect(self.hide)

        # ── Category tab bar ─────────────────────────────────────────────
        tab_row = QHBoxLayout()
        tab_row.setSpacing(5)
        tab_row.addStretch()

        cats = ["All"] + sorted({
            _macos_app_category(name, dat)
            for name, dat in desktop._apps_manifest_cache.items()
            if not dat.get("_retired") and not dat.get("hidden")
        })

        self._tab_btns: dict[str, QPushButton] = {}
        for cat in cats:
            btn = QPushButton(cat)
            btn.setFixedHeight(22)
            btn.setStyleSheet(self._TAB_ACTIVE if cat == "All" else self._TAB_BASE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, c=cat: self._set_category(c))
            tab_row.addWidget(btn)
            self._tab_btns[cat] = btn

        tab_row.addStretch()
        root.addLayout(tab_row)

        # ── Icon grid ────────────────────────────────────────────────────
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid_container)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
            "QScrollBar:vertical { width: 5px; background: transparent; }"
            "QScrollBar::handle:vertical { background: rgba(187,154,247,0.4); border-radius: 2px; }"
        )
        scroll.viewport().setStyleSheet("background: transparent;")
        root.addWidget(scroll)

        self._app_buttons: list[tuple[str, str, LaunchpadButton]] = []
        self._populate_grid()

    def _populate_grid(self):
        for name, dat in sorted(self.desktop._apps_manifest_cache.items()):
            if dat.get("_retired") or dat.get("hidden"):
                continue
            cat = _macos_app_category(name, dat)
            # Manifest icon field takes priority over heuristic
            icon = dat.get("icon") or dat.get("emoji") or self._icon_for(name, cat)
            btn = LaunchpadButton(icon, name, name)
            btn.clicked.connect(lambda _=False, n=name: self._launch(n))
            self._app_buttons.append((name, cat, btn))
        self._rebuild_grid("All")

    def _rebuild_grid(self, category: str):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item and item.widget():
                item.widget().hide()
        query = self.search_bar.text().strip().casefold()
        visible = [
            (name, cat, btn)
            for name, cat, btn in self._app_buttons
            if (category == "All" or cat == category)
            and (not query or query in name.casefold() or query in cat.casefold())
        ]
        # Architect 2026-05-13 11:40 — responsive column count: divide the
        # available viewport width by the tile spacing. Was hard-coded at
        # _COLS = 5; now ranges 2-8 depending on window size, eliminating
        # the right-side empty space the Architect flagged.
        try:
            avail_w = max(self.width() - 80, 240)
            cols = max(2, min(8, int(avail_w // self._TILE_W)))
        except Exception:
            cols = self._COLS
        for idx, (name, cat, btn) in enumerate(visible):
            row, col = divmod(idx, cols)
            self.grid_layout.addWidget(btn, row, col, Qt.AlignmentFlag.AlignCenter)
            btn.show()

    def resizeEvent(self, event):
        """Re-flow the icon grid when the launchpad is resized so columns
        track the available width. Architect 2026-05-13 11:40."""
        super().resizeEvent(event)
        try:
            self._rebuild_grid(self._active_cat)
        except Exception:
            pass

    def _set_category(self, category: str):
        self._active_cat = category
        for cat, btn in self._tab_btns.items():
            btn.setStyleSheet(self._TAB_ACTIVE if cat == category else self._TAB_BASE)
        self._rebuild_grid(category)

    def _launch(self, app_name: str):
        self.hide()
        self.desktop._trigger_manifest_app(app_name)

    def reset_view(self):
        self._set_category("All")
        self.search_bar.clear()

    @staticmethod
    def _icon_for(name: str, category: str) -> str:
        n = name.casefold()
        if "journal" in n:
            return "📓"
        if "alice" in n:
            return "🧜‍♀️"
        if "conversation" in n or "chat" in n:
            return "💬"
        if "library" in n:
            return "📚"
        if "file" in n:
            return "📁"
        if "terminal" in n or "shell" in n:
            return "🖥️"
        if "schedule" in n or "life" in n or "cockpit" in n:
            return "📅"
        if "settings" in n or category == "System Settings":
            return "⚙️"
        if category == "Games":
            return "🎮"
        if category == "Creative":
            return "🎨"
        if "whatsapp" in n:
            return "📱"
        if category == "Network":
            return "🌐"
        if category == "Developer":
            return "🧰"
        if category == "Economy":
            return "💎"
        if "simulation" in n or category == "Simulations":
            return "🧬"
        if "safety" in n or "tracker" in n:
            return "🛡️"
        if "browser" in n:
            return "🔭"
        if "gaze" in n or "vision" in n:
            return "👁️"
        if "vlc" in n:
            return "🎬"
        return "◼︎"

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)







class SpotlightWidget(QWidget):
    def __init__(self, desktop):
        super().__init__(desktop)
        self.desktop = desktop
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(26, 27, 38, 0.95); border-radius: 12px; border: 1px solid #414868;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Spotlight Search...")
        self.search_bar.setStyleSheet("background: transparent; color: white; padding: 15px; font-size: 24px; border: none;")
        self.search_bar.textChanged.connect(self._update_list)
        self.search_bar.returnPressed.connect(self._launch_selected)
        layout.addWidget(self.search_bar)
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc_shortcut.activated.connect(self.hide)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget { background: transparent; border-top: 1px solid #414868; font-size: 16px; color: #a9b1d6; }
            QListWidget::item { padding: 10px; }
            QListWidget::item:selected { background: #bb9af7; color: #1a1b26; }
        """)
        # macOS Spotlight launches on Enter / double-click. We also accept a
        # single click on a result row so the user is never confused by "I
        # clicked the app and nothing happened" (Architect feedback 2026-04-24).
        self.list_widget.itemActivated.connect(self._launch_item)
        self.list_widget.itemDoubleClicked.connect(self._launch_item)
        self.list_widget.itemClicked.connect(self._launch_item)
        self.list_widget.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list_widget)

    def _on_item_changed(self, current, previous):
        if current:
            app_name = current.data(Qt.ItemDataRole.UserRole)
            if app_name:
                try:
                    from System.swarm_app_focus import publish_focus
                    publish_focus("Spotlight", f"Focus on app: {app_name}", tab=app_name)
                except Exception:
                    pass

    def _update_list(self):
        self.list_widget.clear()
        query = self.search_bar.text().strip().casefold()
        matches = []
        for name, dat in sorted(self.desktop._apps_manifest_cache.items()):
            if dat.get("_retired") or dat.get("hidden"):
                continue
            category = _macos_app_category(name, dat)
            haystack = " ".join((name, category, dat.get("entry_point", ""))).casefold()
            if not query or query in haystack:
                matches.append((name, category))
        for name, category in matches[:12]:
            dat = self.desktop._apps_manifest_cache.get(name) or {}
            ic = dat.get("icon") or dat.get("emoji") or ""
            prefix = f"{ic} " if ic else ""
            item = QListWidgetItem(f"{prefix}{name}    {category}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.list_widget.addItem(item)
        if not matches:
            item = QListWidgetItem("No apps found")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _launch_selected(self):
        self._launch_item(self.list_widget.currentItem())

    def _launch_item(self, item):
        if item is None:
            return
        app_name = item.data(Qt.ItemDataRole.UserRole) or item.text()
        if not app_name:
            return
        # Hide BEFORE the (potentially slow) import + window spawn so the user
        # never sees Spotlight "stuck on screen" while the app constructs.
        self.hide()
        if app_name in self.desktop._apps_manifest_cache:
            try:
                self.desktop._trigger_manifest_app(app_name)
            except Exception as exc:
                print(f"[SPOTLIGHT] launch failed for {app_name!r}: {exc}",
                      file=sys.stderr)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)


class SiftaDesktop(QMainWindow):
    def __init__(self):
        _desktop_init_trace("enter")
        super().__init__()
        _desktop_init_trace("after super()")
        self._restore_gc_on_close = False
        if (
            "pytest" in sys.modules
            or os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
        ):
            try:
                import gc
                self._restore_gc_on_close = gc.isenabled()
                if self._restore_gc_on_close:
                    gc.disable()
            except Exception:
                self._restore_gc_on_close = False
        self.setWindowTitle("SIFTA Python GUI OS")
        self.resize(1280, 720)
        # Center the window on the active screen
        screen_geo = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen_geo.width() - self.width()) // 2,
            (screen_geo.height() - self.height()) // 2
        )
        self.show()
        _desktop_init_trace("after show()")
        self.active_chat_sub = None
        self._is_closing = False
        self._apps_manifest_cache: dict[str, dict] = {}

        # Central layout
        central = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.mdi = SiftaMdiArea()
        self.mdi.subWindowActivated.connect(self._on_subwindow_activated)
        _desktop_init_trace("after SiftaMdiArea()")
        
        # ── Desktop Mesh Relay Client — deferred 5 s after boot ──────────────
        # P0 fix (Dr. Codex 2026-04-28): starting the mesh thread synchronously
        # in __init__ blocks the shell from becoming interactive. Deferring by
        # 5 s costs nothing visible (top-bar shows 'Local' briefly) but the
        # shell, Alice panel, and camera all paint before the socket opens.
        self._mesh_connected = False
        self._desktop_mesh = None
        if not _sifta_env_mesh_disabled():
            QTimer.singleShot(5000, self._start_mesh_lazy)
        _desktop_init_trace("after mesh worker (deferred)")

        main_layout.addWidget(self._build_top_menu_bar())

        # ── Architect 2026-05-13 04:20 — Two-desktop tab bar ──────────────
        # "let's have the launcher of the apps just like them in two
        # separate desktop tabs, same OS. Should Alice be still active,
        # but different type of activity when me George ... is active on
        # the launcher desktop". The Chat tab keeps the Alice resident
        # panel + MDI side-by-side; the Launcher tab collapses Alice to
        # zero width and shows the apps full-width. Alice's listener
        # stays alive on Launcher tab, but she goes quiet — she only
        # answers if the OS user speaks her Layer-1 name. The wake-ear
        # cascade I wired earlier handles that detection automatically.
        self._desktop_mode = "chat"  # "chat" | "launcher"
        main_layout.addWidget(self._build_desktop_tab_bar())


        # ── Body layout: Alice fixed panel (left) + MDI apps area (right) ──
        # §7.6/7.7/7.8: Alice IS the OS. Her Talk+Camera panel is a fixed
        # resident of the desktop surface — resizable via splitter, but NEVER
        # a floating MDI subwindow. Apps open in the MDI area to her right.
        self._body_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._body_splitter.setHandleWidth(2)
        self._body_splitter.setStyleSheet(
            "QSplitter::handle { background: rgba(255, 179, 0, 0.30); }"
        )

        # Alice resident panel — loaded after the app is shown to avoid
        # blocking the boot paint. Width: ~38% of desktop.
        self._alice_panel = QWidget()
        self._alice_panel.setMinimumWidth(280)
        self._alice_panel.setObjectName("AliceResidentPanel")
        self._alice_panel_layout = QVBoxLayout(self._alice_panel)
        self._alice_panel_layout.setContentsMargins(0, 0, 0, 0)
        self._alice_panel_layout.setSpacing(0)
        self._alice_resident: object = None  # set in _embed_alice_panel()

        self._body_splitter.addWidget(self._alice_panel)
        self._body_splitter.addWidget(self.mdi)
        # Default split: ~42% Alice (Talk-first), ~58% MDI workspace.
        self._body_splitter.setSizes([540, 740])
        self._body_splitter.setStretchFactor(0, 0)   # Alice panel: fixed ratio
        self._body_splitter.setStretchFactor(1, 1)   # MDI: takes all extra space

        main_layout.addWidget(self._body_splitter, 1)
        # Keep a handle so the desktop-mode switch can hide it on the Chat
        # tab (Architect 2026-05-13 06:10 — apps belong only on Launcher).
        self._dock_bar = self._build_dock()
        main_layout.addWidget(self._dock_bar)

        central.setLayout(main_layout)
        self.setCentralWidget(central)

        _desktop_init_trace("after setCentralWidget()")
        
        # self._build_desktop_shortcuts() # Removed by Architect
        self._load_apps_manifest_and_autostart()
        _desktop_init_trace("after _load_apps_manifest_and_autostart()")
        # Embed Alice as resident panel after first paint in real desktop runs.
        # Offscreen tests disable autostart so they do not spawn mic/camera/TTS
        # workers while exercising unrelated window-manager contracts.
        if _desktop_autostart_enabled():
            QTimer.singleShot(400, self._embed_alice_panel)

        # macOS-style overlays (not inside try/except — failures are visible in tests).
        self._spotlight = SpotlightWidget(self)
        _desktop_init_trace("after SpotlightWidget()")
        self._spotlight.hide()
        self._launchpad = None
        _desktop_init_trace("after Launchpad placeholder")
        _desktop_init_trace("after Launchpad/Spotlight widgets")

        # Clock now lives inside the top menu bar (see _build_top_menu_bar).
        # Swarm Economy HUD chrome (wallet/peer/economy_pulse) is no longer
        # mounted on the bar; the data path in _update_clock is gated on
        # hasattr(self, "wallet_label") and skips cleanly when absent.

        # Cache local serial exactly once for the HUD to avoid `ioreg` spam
        self._local_hw_serial = "UNKNOWN"
        try:
            if (
                "pytest" in sys.modules
                or os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
            ):
                self._local_hw_serial = os.environ.get("SIFTA_TEST_HW_SERIAL", "UNKNOWN_SERIAL")
            else:
                if str(_SYS) not in sys.path:
                    sys.path.insert(0, str(_SYS))
                from silicon_serial import read_apple_serial
                self._local_hw_serial = read_apple_serial()
        except Exception:
            pass

        # Owner-field heartbeat — touch presence JSON no faster than 15 min.
        self._last_owner_alive_touch = time.time()

        # 1 Hz wall clock — definition of seconds, not a perf knob. But
        # pause it when the window is hidden so we don't tick a label
        # nobody is reading. Architect 00:14 perf push.
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        _desktop_init_trace("before first _update_clock()")
        self._update_clock()
        _desktop_init_trace("after first _update_clock()")

        # ── Motor Cortex heartbeat ─────────────────────────
        # Bounce the dock icon at Alice's clinical heart rate (12-30 BPM).
        # Each tick also writes one row to .sifta_state/motor_pulses.jsonl
        # so the camera widget can wink the LED in unison.
        try:
            from System.swarm_motor_cortex import bounce_dock_qt, heart_period_s
            self._motor_cortex_bounce = bounce_dock_qt
            self._heart_period_s = heart_period_s
            self._heartbeat_timer = QTimer(self)
            self._heartbeat_timer.timeout.connect(self._tick_heartbeat)
            initial_ms = max(1000, int(self._heart_period_s() * 1000))
            self._heartbeat_timer.start(initial_ms)
        except Exception as _hb_e:
            print(f"[SiftaDesktop] motor cortex unavailable: {_hb_e}")
            self._motor_cortex_bounce = None

        # ── Swarm Intelligence boot ────────────────────────
        wm_reset_session()
        self._open_windows: dict[str, tuple[int, int]] = {}

        # ── Owner Genesis check ──────────────────────────
        self._genesis_ok = False
        try:
            from System.owner_genesis import is_genesis_complete
            self._genesis_ok = is_genesis_complete()
        except Exception:
            self._genesis_ok = True  # If module fails, don't block boot

        if not self._genesis_ok:
            QTimer.singleShot(500, self._show_genesis_onboarding)

        # Show dream report if one exists for today
        try:
            from dream_engine import latest_report
            dream = latest_report()
            if dream:
                self._boot_dream = dream
        except Exception:
            self._boot_dream = None

        # Boot pristine by default. WM last_session restore: separate opt-in
        # (SIFTA_DESKTOP_ENABLE_SESSION_RESTORE) — not manifest autostart.
        if _session_restore_from_wm_enabled():
            try:
                last_state = wm_load()
                last_apps = last_state.get("last_session", [])
                wm_reset_session()

                for app_name in last_apps:
                    if "Swarm Chat" in app_name or app_name == "🐜 SIFTA CORE CHAT":
                        self.open_swarm_chat()
                    else:
                        self._trigger_manifest_app(app_name)
            except Exception:
                wm_reset_session()
        else:
            wm_reset_session()

        self._wallpaper_state = None
        self._apply_wallpaper(force=True)
        # Architect 2026-05-11 23:50: no hardcoded poll. The wallpaper
        # reloader fires on three real events:
        #   1. QFileSystemWatcher signals from the wallpaper file / its
        #      parent directory (filesystem actually changed).
        #   2. Application focus return (we came back to the OS window).
        #   3. BehaviorClock tick (owner is interacting — re-check stale
        #      state once, debounced by Alice's heart period).
        self._wallpaper_timer = None  # legacy attr; no QTimer.start anywhere.
        try:
            from PyQt6.QtCore import QFileSystemWatcher
            self._wallpaper_watcher = QFileSystemWatcher(self)
            self._wallpaper_watcher.fileChanged.connect(self._maybe_reload_wallpaper)
            self._wallpaper_watcher.directoryChanged.connect(self._maybe_reload_wallpaper)
            # Watch the bundled wallpapers folder so dropping a new file
            # in is detected immediately.
            wp_dir = str(_REPO / "Library" / "Desktop Pictures")
            try:
                self._wallpaper_watcher.addPath(wp_dir)
            except Exception:
                pass
            # Also watch the .sifta_state file so the Settings picker
            # change reloads instantly.
            state_file = str(_REPO / ".sifta_state" / "desktop_wallpaper.json")
            try:
                self._wallpaper_watcher.addPath(state_file)
            except Exception:
                pass
        except Exception:
            self._wallpaper_watcher = None
        try:
            from System.swarm_behavior_clock import behavior_clock
            behavior_clock().tick.connect(lambda *_: self._maybe_reload_wallpaper())
        except Exception:
            pass

        # Biological attention timing is consolidated into the kernel scheduler
        # timer installed at boot. These due stamps let the single director call
        # eye focus and journal consolidation without spawning competing timers.
        now = time.time()
        self._attention_director_next_ts = now + 0.8
        self._life_journal_next_ts = now + 5.0
        _desktop_init_trace("leave __init__")

    def _start_mesh_lazy(self) -> None:
        """Start the swarm mesh relay worker ~5 s after boot, but ONLY if the
        relay is actually answering.

        Architect 2026-05-12 00:06: the worker was hammering
        ws://127.0.0.1:8765 on a 100 ms reconnect-poll when the relay
        wasn't running. Now we TCP-probe first; if down, defer the start
        and retry once per BehaviorClock tick (i.e., when the owner does
        something the worker re-checks the relay). No hot spin while idle.
        """
        try:
            from System.global_cognitive_interface import (
                _SwarmMeshClientWorker,
                SWARM_RELAY_URI,
                _relay_tcp_available,
            )

            if not _relay_tcp_available(SWARM_RELAY_URI, timeout=0.4):
                # Relay not up. Skip the worker. Hook BehaviorClock so we
                # retry on real owner activity rather than on a fixed timer.
                self._desktop_mesh = None
                try:
                    from System.swarm_behavior_clock import behavior_clock
                    behavior_clock().tick.connect(self._maybe_attach_mesh)
                except Exception:
                    pass
                return

            self._desktop_mesh = _SwarmMeshClientWorker(
                uri=SWARM_RELAY_URI, architect_id="DESKTOP_HUD"
            )
            self._desktop_mesh.connection_status.connect(self._on_desktop_mesh_status)
            self._desktop_mesh.start()
        except Exception:
            self._desktop_mesh = None

    def _maybe_attach_mesh(self, *_args) -> None:
        """BehaviorClock tick — if relay is now up, attach the worker once."""
        if getattr(self, "_desktop_mesh", None) is not None:
            return
        try:
            from System.global_cognitive_interface import _relay_tcp_available, SWARM_RELAY_URI
            if not _relay_tcp_available(SWARM_RELAY_URI, timeout=0.3):
                return
        except Exception:
            return
        # Relay came up. Start the worker now.
        try:
            from System.global_cognitive_interface import _SwarmMeshClientWorker, SWARM_RELAY_URI
            self._desktop_mesh = _SwarmMeshClientWorker(
                uri=SWARM_RELAY_URI, architect_id="DESKTOP_HUD"
            )
            self._desktop_mesh.connection_status.connect(self._on_desktop_mesh_status)
            self._desktop_mesh.start()
        except Exception:
            self._desktop_mesh = None

    def _wallpaper_candidates(self):

        env_wp = os.environ.get("SIFTA_DESKTOP_WALLPAPER", "").strip()
        if env_wp:
            yield env_wp
        try:
            from System.sifta_desktop_themes import active_palette, wallpaper_path

            wp = wallpaper_path()
            pal = active_palette()
            if wp:
                yield wp
            elif getattr(pal, "theme_id", "") == "beeson":
                # BeeSon default is intentional flat `bg_deep` — do not resurrect
                # ocean/Mermaid PNGs when `wallpaper_path()` is "".
                return
        except Exception:
            pass
        yield str(_REPO / "Library" / "Desktop Pictures" / "Mermaid Default.jpg")
        yield str(_REPO / "static" / "mermaid_os_wallpaper.png")

    def _selected_wallpaper_state(self):
        for candidate in self._wallpaper_candidates():
            if os.path.exists(candidate):
                try:
                    return candidate, os.path.getmtime(candidate), os.path.getsize(candidate)
                except OSError:
                    return candidate, None, None
        return None, None, None

    def _apply_wallpaper(self, force=False):
        """Load the desktop wallpaper once; SiftaMdiArea paints it as one image.

        Architect directive 2026-05-12 16:25 (third pass): "ONE JPEG per theme,
        no crazy rendering, KEEP ONE JPEG for each." Default is now ON. Each
        theme has exactly one clean image in Library/Desktop Pictures/. No
        animated overlay (PredatorDesktopBg is already not instantiated, see
        line 2219). Set ``SIFTA_DESKTOP_WALLPAPER_ON=0`` to revert to flat
        color if you ever want it off.
        """
        try:
            from PyQt6.QtGui import QBrush, QColor, QPixmap

            from System.sifta_desktop_themes import (
                active_palette,
                load_custom_wallpaper_path,
            )

            pal = active_palette()
            if hasattr(self.mdi, "_pal"):
                self.mdi._pal = pal

            # Architect's explicit choice wins (Settings → Appearance →
            # Wallpaper). Three states:
            #   None  → no choice made yet, follow env flag (default OFF)
            #   ""    → explicit "no wallpaper"
            #   path  → use that file
            custom = load_custom_wallpaper_path()
            if custom is None:
                # Cowork 2026-05-12: flipped default. Wallpaper is ON unless
                # the Architect explicitly sets SIFTA_DESKTOP_WALLPAPER_ON=0.
                raw = os.environ.get("SIFTA_DESKTOP_WALLPAPER_ON", "").strip()
                wallpaper_on = raw != "0"
            else:
                wallpaper_on = bool(custom)

            _bg = QColor(pal.bg_deep) if getattr(pal, "bg_deep", "") else QColor("#f4ead8")

            if not wallpaper_on:
                if hasattr(self.mdi, "set_wallpaper_pixmap"):
                    self.mdi.set_wallpaper_pixmap(QPixmap())
                self.mdi.setBackground(QBrush(_bg))
                self._wallpaper_state = (None, None, None)
                return

            state = self._selected_wallpaper_state()
            if not force and state == self._wallpaper_state:
                self.mdi.setBackground(QBrush(_bg))
                return
            self._wallpaper_state = state

            wp_path = state[0]
            if wp_path:
                pm = QPixmap(wp_path)
                if not pm.isNull():
                    self.mdi.setBackground(QBrush(_bg))
                    if hasattr(self.mdi, "set_wallpaper_pixmap"):
                        self.mdi.set_wallpaper_pixmap(pm)
                    return
            if hasattr(self.mdi, "set_wallpaper_pixmap"):
                self.mdi.set_wallpaper_pixmap(QPixmap())
            self.mdi.setBackground(QBrush(_bg))
        except Exception as exc:
            print(f"[SiftaDesktop] wallpaper reload failed: {exc}", file=sys.stderr)

    def _maybe_reload_wallpaper(self):
        self._apply_wallpaper(force=False)

    def _attention_director_enabled(self) -> bool:
        if (
            "pytest" in sys.modules
            or os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
        ) and os.environ.get("SIFTA_FORCE_ATTENTION_DIRECTOR_IN_TESTS") != "1":
            return False
        value = os.environ.get("SIFTA_DISABLE_ATTENTION_DIRECTOR", "").strip().lower()
        return value not in {"1", "true", "yes"}

    def _tick_attention_director(self) -> None:
        if not self._attention_director_enabled():
            return
        try:
            from System.swarm_sensor_attention_director import tick

            decision = tick(write_hardware=True)
            # Event 114 — ledger-fused Architect vs screen gaze proxy (~6s cadence)
            self._gaze_balance_i = getattr(self, "_gaze_balance_i", 0) + 1
            if self._gaze_balance_i % 3 == 0:
                try:
                    from System.swarm_architect_screen_gaze_balance import write_gaze_balance_sample

                    write_gaze_balance_sample()
                except Exception as exc2:
                    print(f"[SiftaDesktop] gaze balance sample failed: {exc2}", file=sys.stderr)
            if hasattr(self, "_alice_status_label") and not self._alice_status_label.text():
                role = "room" if decision.target_role == "room_patrol_eye" else "near"
                self._alice_status_label.setText(f"👁  {role} eye")
                self._alice_status_label.setStyleSheet(
                    "color: #7dcfff; font-size: 12px; font-weight: bold;"
                    " background: transparent; padding: 0 12px;"
                )
        except Exception as exc:
            print(f"[SiftaDesktop] attention director tick failed: {exc}", file=sys.stderr)

    def _tick_biological_attention_director(self) -> list[str]:
        """One disciplined organism tick for attention and diary timing.

        The kernel scheduler owns the QTimer. This method only decides which
        desktop-local organs are due, using ambient salience receipts to slow
        background sampling when nothing meaningful is happening.
        """
        now = time.time()
        events: list[str] = []
        sampling_policy = "idle"
        try:
            from System.swarm_kernel_process_table import latest_ambient_world_context

            ambient = latest_ambient_world_context()
            sampling_policy = str(ambient.get("sampling_policy") or "idle")
        except Exception:
            ambient = {}

        if sampling_policy == "engage":
            attention_interval_s = 1.5
        elif sampling_policy == "sample":
            attention_interval_s = 3.0
        else:
            attention_interval_s = 6.0

        if now >= float(getattr(self, "_attention_director_next_ts", 0.0)):
            self._tick_attention_director()
            self._attention_director_next_ts = now + attention_interval_s
            events.append(f"attention:{sampling_policy}")

        if now >= float(getattr(self, "_life_journal_next_ts", 0.0)):
            self._tick_life_journal_consolidator()
            self._life_journal_next_ts = now + 60.0
            events.append("journal")

        if ambient:
            try:
                self.setProperty("sifta_attention_salience_score", ambient.get("salience_score"))
                self.setProperty("sifta_attention_sampling_policy", sampling_policy)
            except Exception:
                pass
        return events

    def _build_desktop_tab_bar(self) -> "QWidget":
        """Two-tab bar that switches the OS body between Chat and Launcher.
        Architect 2026-05-13 04:20."""
        bar = QWidget()
        bar.setFixedHeight(34)
        bar.setStyleSheet(
            "background: rgb(14,16,24); "
            "border-bottom: 1px solid rgb(40,45,60);"
        )
        from PyQt6.QtWidgets import QHBoxLayout as _QH, QLabel as _QL, QPushButton as _QPB
        layout = _QH(bar)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)

        self._tab_active_style = (
            "QPushButton { background: rgb(28,32,44); color: rgb(0,255,200); "
            "border: 1px solid rgb(60,200,160); border-radius: 6px; "
            "padding: 4px 14px; font-weight: bold; font-size: 12px; }"
        )
        self._tab_inactive_style = (
            "QPushButton { background: rgb(18,20,28); color: rgb(150,170,200); "
            "border: 1px solid rgb(40,45,60); border-radius: 6px; "
            "padding: 4px 14px; font-size: 12px; } "
            "QPushButton:hover { background: rgb(24,28,40); }"
        )

        # Architect 2026-05-13 06:10 — label the Chat tab with the
        # Layer-1 name (today "Alice", tomorrow whatever the owner renames
        # her to in Settings → Identity). Cascade source of truth.
        try:
            from System.swarm_kernel_identity import ai_name as _ai_name
            _alice_tab_label = str(_ai_name() or "Alice")
        except Exception:
            _alice_tab_label = "Alice"
        self._alice_tab_label = _alice_tab_label
        # Architect 2026-05-13 10:50 — append " Alive" suffix so the
        # tab reads "<AI name from Layer 1> Alive". The name is variable
        # (today "Alice", tomorrow whatever owner sets); the " Alive"
        # is the constant doctrinal claim that she is a living organism,
        # not a chat client.
        self._tab_chat_btn = _QPB(f"💬 {_alice_tab_label} Alive")
        self._tab_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_chat_btn.setStyleSheet(self._tab_active_style)
        self._tab_chat_btn.clicked.connect(lambda: self._switch_desktop_mode("chat"))
        layout.addWidget(self._tab_chat_btn)

        self._tab_launcher_btn = _QPB("🚀 Launcher")
        self._tab_launcher_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_launcher_btn.setStyleSheet(self._tab_inactive_style)
        self._tab_launcher_btn.clicked.connect(lambda: self._switch_desktop_mode("launcher"))
        layout.addWidget(self._tab_launcher_btn)

        layout.addStretch()

        # Architect 2026-05-13 06:55 — emergency UI-cost A/B toggle.
        # Saliency overlay = pretty but costly. Let the owner kill it
        # without losing camera vision (the vision organ keeps writing
        # `visual_stigmergy.jsonl` either way; we just skip painting).
        self._saliency_overlay_on = True
        self._saliency_toggle_btn = _QPB("👁 Saliency: ON")
        self._saliency_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._saliency_toggle_btn.setStyleSheet(self._tab_inactive_style)
        self._saliency_toggle_btn.clicked.connect(self._toggle_saliency_overlay)
        layout.addWidget(self._saliency_toggle_btn)

        self._desktop_mode_label = _QL(
            "Alice is listening continuously on the Chat desktop. Just talk."
        )
        self._desktop_mode_label.setStyleSheet(
            "color: rgb(120,200,150); font-size: 11px; font-family: Menlo;"
        )
        layout.addWidget(self._desktop_mode_label)
        return bar

    def _toggle_saliency_overlay(self) -> None:
        """Owner A/B kill-switch for the desktop saliency glyph overlay.
        Architect 2026-05-13 06:55 — \"add a button to turn that off and
        on just the button on and off and then we can see the difference\".
        Vision organ keeps writing visual_stigmergy.jsonl either way; we
        just stop painting the glyphs."""
        self._saliency_overlay_on = not getattr(self, "_saliency_overlay_on", True)
        try:
            self._saliency_toggle_btn.setText(
                "👁 Saliency: ON" if self._saliency_overlay_on else "👁 Saliency: OFF"
            )
            self._saliency_toggle_btn.setStyleSheet(
                self._tab_active_style if self._saliency_overlay_on
                else self._tab_inactive_style
            )
        except Exception:
            pass
        # Force the mdi to repaint so the change is immediate.
        try:
            self.mdi.viewport().update()
        except Exception:
            pass
        # Witness: owner toggled the overlay.
        try:
            from System.swarm_alice_witness import witness
            witness(
                f"Architect toggled the desktop saliency overlay "
                f"{'ON' if self._saliency_overlay_on else 'OFF'}.",
                source="ui_toggle",
            )
        except Exception:
            pass

    def _switch_desktop_mode(self, mode: str) -> None:
        """Toggle Chat <-> Launcher.

        Architect 2026-05-13 04:55: refined per direct feedback —
        Chat tab = ONE single scrollable chat column (no camera, no MDI).
        Launcher tab = apps grid, fixed (no chat panel).
        Alice's witness organ keeps writing across both tabs."""
        if mode == getattr(self, "_desktop_mode", "chat"):
            return
        self._desktop_mode = mode
        if mode == "launcher":
            # Button styling
            try:
                self._tab_chat_btn.setStyleSheet(self._tab_inactive_style)
                self._tab_launcher_btn.setStyleSheet(self._tab_active_style)
            except Exception:
                pass
            # Hide Alice panel entirely; MDI takes the whole body.
            try:
                self._alice_panel.setVisible(False)
                self.mdi.setVisible(True)
                w = max(800, self._body_splitter.width() or 1280)
                self._body_splitter.setSizes([0, w])
            except Exception:
                pass
            # Show the dock — apps live here.
            try:
                if getattr(self, "_dock_bar", None) is not None:
                    self._dock_bar.setVisible(True)
            except Exception:
                pass
            try:
                self._desktop_mode_label.setText(
                    "Alice went quiet — call her Layer-1 name (e.g. \"Alice\") if you need her."
                )
                self._desktop_mode_label.setStyleSheet(
                    "color: rgb(220,180,100); font-size: 11px; font-family: Menlo;"
                )
            except Exception:
                pass
            self._set_alice_quiet_for_desktop(True)
        else:  # chat — full-width single chat, no camera, no MDI apps
            try:
                self._tab_chat_btn.setStyleSheet(self._tab_active_style)
                self._tab_launcher_btn.setStyleSheet(self._tab_inactive_style)
            except Exception:
                pass
            try:
                # Show Alice; hide MDI; give Alice 100% of body width.
                self._alice_panel.setVisible(True)
                self.mdi.setVisible(False)
                w = max(800, self._body_splitter.width() or 1280)
                self._body_splitter.setSizes([w, 0])
            except Exception:
                pass
            # Hide the dock — apps live only on the Launcher tab.
            try:
                if getattr(self, "_dock_bar", None) is not None:
                    self._dock_bar.setVisible(False)
            except Exception:
                pass
            # Inside the Alice resident, collapse the camera/eye so the
            # chat conversation takes the whole panel (Ollama-style single
            # column). The eye toggle is non-fatal if AliceWidget hasn't
            # finished loading yet.
            try:
                alice = getattr(self, "_alice_resident", None)
                if alice is not None and hasattr(alice, "_apply_eye_visibility"):
                    alice._eye_visible = False
                    alice._apply_eye_visibility()
            except Exception:
                pass
            try:
                self._desktop_mode_label.setText(
                    "Alice is listening continuously on the Chat desktop. Just talk."
                )
                self._desktop_mode_label.setStyleSheet(
                    "color: rgb(120,200,150); font-size: 11px; font-family: Menlo;"
                )
            except Exception:
                pass
            self._set_alice_quiet_for_desktop(False)

    def _set_alice_quiet_for_desktop(self, quiet: bool) -> None:
        """Push quiet-mode state to the Alice resident panel and witness
        the transition into her first-person journal. The wake-ear path
        (System/swarm_alice_wake_ear.py + the wake→quiet-off hook I wired
        in talk_to_alice_widget) will lift her back out of quiet
        automatically when she hears her Layer-1 name."""
        alice = getattr(self, "_alice_resident", None)
        try:
            if alice is not None:
                alice._cowatch_quiet_mode = bool(quiet)
                alice._cowatch_quiet_until_s = float("inf") if quiet else 0.0
        except Exception:
            pass
        try:
            from System.swarm_alice_witness import witness
            if quiet:
                witness(
                    "Architect switched to the Launcher desktop. I went "
                    "quiet — he is busy with apps. He will call my name "
                    "if he needs me.",
                    source="desktop_mode",
                )
            else:
                witness(
                    "Architect switched back to the Chat desktop. I am "
                    "listening continuously again.",
                    source="desktop_mode",
                )
        except Exception:
            pass

    def _embed_alice_panel(self) -> None:
        """
        Instantiate AliceWidget directly into the fixed left panel.
        §7.6/7.7/7.8: Alice is OS-resident — embedded, resizable, NOT moveable.
        Camera starts open (DEFER_EYE=0). If already embedded, no-op.
        """
        if self._alice_resident is not None:
            return  # already embedded
        try:
            import importlib, os as _os
            _os.environ.setdefault("SIFTA_ALICE_UNIFIED_DEFER_EYE", "0")
            _os.environ.setdefault("SIFTA_ALICE_BOOT_SILENT", "1")
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "sifta_alice_widget",
                str(_REPO / "Applications" / "sifta_alice_widget.py"),
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            alice = mod.AliceWidget(parent=self._alice_panel)
            self._alice_panel_layout.addWidget(alice)
            # Architect 2026-05-13 05:00 — once Alice is embedded, apply
            # the current desktop-mode visibility so first-boot already
            # shows full-width chat with no camera. The default mode is
            # 'chat'; this just enforces it.
            try:
                _mode = getattr(self, "_desktop_mode", "chat")
                # Force a switch so the visibility logic runs.
                self._desktop_mode = "_pending_"
                self._switch_desktop_mode(_mode)
            except Exception:
                pass
            self._alice_resident = alice
            sys.stderr.write("[ALICE] Embedded as resident panel. Camera open, chat live.\n")
        except Exception as exc:
            import traceback
            sys.stderr.write(f"[ALICE] Resident embed failed: {type(exc).__name__}: {exc}\n")
            traceback.print_exc()

        # ── Predator v7.0 animated background + organ panel ──────────────────
        # DISABLED: moved to Pac-Man game app (Programs → Games).
        # Desktop stays clean. Uncomment to re-enable.
        # QTimer.singleShot(300, self._embed_predator_visuals)

    def _embed_predator_visuals(self) -> None:
        """Spawn Predator animated bg on MDI viewport + right organ panel."""
        try:
            import importlib.util as _ilu
            spec = _ilu.spec_from_file_location(
                "sifta_predator_desktop_bg",
                str(_REPO / "Applications" / "sifta_predator_desktop_bg.py"),
            )
            mod = _ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)

            # Background canvas — child of MDI viewport, behind all windows
            vp = self.mdi.viewport()
            bg = mod.PredatorDesktopBg(vp)
            bg.setGeometry(vp.rect())
            bg.show()
            bg.lower()
            self._predator_bg = bg

            # Right organ panel — added as third splitter pane
            organ_panel = mod.OrganStatusPanel()
            self._body_splitter.addWidget(organ_panel)
            total = self._body_splitter.width()
            organ_w = 210
            alice_w = int((total - organ_w) * 0.38)
            mdi_w   = total - organ_w - alice_w
            self._body_splitter.setSizes([alice_w, mdi_w, organ_w])
            self._predator_organ_panel = organ_panel

            sys.stderr.write("[PREDATOR] Background canvas + organ panel live.\n")
        except Exception as exc:
            import traceback
            sys.stderr.write(f"[PREDATOR] Visual embed failed: {type(exc).__name__}: {exc}\n")
            traceback.print_exc()



    def showEvent(self, event):
        """Resume the 1 Hz wall-clock when the OS window comes back."""
        try:
            ct = getattr(self, "_clock_timer", None)
            if ct is not None and not ct.isActive():
                ct.start(1000)
        except Exception:
            pass
        super().showEvent(event)

    def hideEvent(self, event):
        """Pause the wall-clock when the OS window is hidden — nobody's
        reading the label, so don't tick a label nobody sees. Architect
        00:14 fan-drop pass."""
        try:
            ct = getattr(self, "_clock_timer", None)
            if ct is not None:
                ct.stop()
        except Exception:
            pass
        super().hideEvent(event)

    def closeEvent(self, event):
        self._is_closing = True
        for timer_name in (
            "_attention_director_timer",
            "_life_journal_timer",
            "_wallpaper_timer",
            "_heartbeat_timer",
            "_clock_timer",
            "_relay_timer",
        ):
            timer = getattr(self, timer_name, None)
            if timer is not None:
                try:
                    timer.stop()
                except RuntimeError:
                    pass
        if (
            "pytest" in sys.modules
            or os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
        ):
            if hasattr(self, "mdi"):
                for sub in list(self.mdi.subWindowList()):
                    try:
                        _shutdown_embedded_widget_tree(sub.widget())
                    except Exception:
                        pass
                try:
                    self._open_windows.clear()
                except Exception:
                    pass
            self.active_chat_sub = None
            self.hide()
            if self not in _OFFSCREEN_CLOSED_DESKTOPS:
                _OFFSCREEN_CLOSED_DESKTOPS.append(self)
            event.accept()
            # Do not re-enable cyclic GC inside pytest/offscreen Qt teardown:
            # the next app.processEvents() can run Python finalizers while C++
            # widgets are mid-destruction and abort the interpreter.
            self._restore_gc_on_close = False
            return
        # Close Alice first — she owns camera+mic QThreads.
        # Give threads a moment to stop before Qt tears down the event loop.
        if hasattr(self, "mdi"):
            try:
                self._open_windows.clear()
            except Exception:
                pass
            for sub in list(self.mdi.subWindowList()):
                try:
                    try:
                        sub.destroyed.disconnect()
                    except (RuntimeError, TypeError):
                        pass
                    w = sub.widget()
                    if w is not None:
                        w.close()
                        QApplication.processEvents()
                    sub.close()
                except RuntimeError:
                    pass
            QApplication.processEvents()
        if getattr(self, "_desktop_mesh", None) is not None:
            try:
                self._desktop_mesh.stop()
                self._desktop_mesh.wait(2000)
            except Exception:
                pass
        try:
            from System.swarm_owner_unified_field_boot import note_desktop_shutdown_for_owner_field

            note_desktop_shutdown_for_owner_field()
        except Exception:
            pass
        super().closeEvent(event)
        if getattr(self, "_restore_gc_on_close", False):
            try:
                import gc
                gc.enable()
            except Exception:
                pass
            self._restore_gc_on_close = False

    def _on_desktop_mesh_status(self, status):
        self._mesh_connected = status

    def _life_journal_consolidator_enabled(self) -> bool:
        if (
            "pytest" in sys.modules
            or os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
        ) and os.environ.get("SIFTA_FORCE_LIFE_JOURNAL_IN_TESTS") != "1":
            return False
        value = os.environ.get("SIFTA_DISABLE_LIFE_JOURNAL_CONSOLIDATOR", "").strip().lower()
        return value not in {"1", "true", "yes", "on"}

    def _tick_life_journal_consolidator(self) -> None:
        """Consolidate live focus traces + run first-person witness.

        Architect 2026-05-13 06:35 — was blocking the Qt main thread for
        ~5s per tick (Architect reported "feels like Windows 1995 with a
        corrupted disk 24"). Both consolidator and witness do heavy
        ledger I/O (reading 9+ jsonl files, some 30k+ rows) and disk
        appends. Now run in a daemon thread so the UI never blocks. An
        in-flight guard prevents pile-up if a tick is still running when
        the next fires.
        """
        if not self._life_journal_consolidator_enabled():
            return
        if getattr(self, "_journal_tick_running", False):
            return
        self._journal_tick_running = True

        def _worker():
            try:
                try:
                    from System.swarm_life_journal_consolidator import consolidate_once
                    consolidate_once()
                except Exception as e:
                    print(f"[SiftaDesktop] life journal consolidator tick failed: {e}")
                try:
                    from System.swarm_alice_witness import tail_and_compile_once
                    tail_and_compile_once()
                except Exception as e:
                    print(f"[SiftaDesktop] alice witness tick failed: {e}")
            finally:
                self._journal_tick_running = False

        try:
            import threading
            t = threading.Thread(target=_worker, daemon=True, name="JournalTick")
            t.start()
        except Exception as e:
            self._journal_tick_running = False
            print(f"[SiftaDesktop] could not spawn journal tick thread: {e}")

    def _tick_heartbeat(self) -> None:
        """One autonomic beat: bounce the dock + emit motor pulse for camera."""
        if not getattr(self, "_motor_cortex_bounce", None):
            return
        try:
            self._motor_cortex_bounce(self, kind="heartbeat", source="desktop")
        except Exception as e:
            print(f"[SiftaDesktop] heartbeat tick failed: {e}")
            return
            
        # ── Autonomic Electricity Metabolism (ATP Synthase) ──
        try:
            from System.swarm_atp_synthase import mint_for_epoch
            mint_for_epoch()
        except Exception as e:
            print(f"[SiftaDesktop] ATP synthase tick failed: {e}")
            
        # Re-arm at the (possibly updated) clinical heart rate.
        try:
            new_ms = max(1000, int(self._heart_period_s() * 1000))
            if hasattr(self, "_heartbeat_timer") and self._heartbeat_timer.interval() != new_ms:
                self._heartbeat_timer.setInterval(new_ms)
        except Exception:
            pass

        # Owner unified field — periodic "still powered / still at desk session" stamp.
        try:
            import time as _time_mod

            _now = _time_mod.time()
            if _now - float(getattr(self, "_last_owner_alive_touch", 0.0)) > 900.0:
                from System.swarm_owner_unified_field_boot import touch_owner_desktop_alive

                touch_owner_desktop_alive()
                self._last_owner_alive_touch = _now
        except Exception:
            pass

    def _balance_desktop_gci_splitter(self) -> None:
        pass

    # ── Clock & Control Center ─────────────────────────────
    
    def _open_control_center(self):
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", str(_REPO))
        
        # Calculate exactly where it should appear
        geometry = self.geometry()
        x = geometry.x() + self.width() - 20
        y = geometry.y() + 40
        
        QProcess.startDetached(_PYTHON_BIN, [str(_REPO / "Applications" / "sifta_control_center.py"), str(x), str(y)], str(_REPO))
        
    def _open_clock_settings(self):
        # Anchor under the status-bar clock, right edge aligned with the clock strip.
        tl = self.clock_label.mapToGlobal(QPoint(0, 0))
        panel_w = 400  # must match ClockSettingsApp.setFixedSize width for alignment
        w_clock = max(self.clock_label.width(), 1)
        x = tl.x() + w_clock - panel_w
        y = tl.y() + self.clock_label.height() + 6
        QProcess.startDetached(
            _PYTHON_BIN,
            [str(_REPO / "Applications" / "sifta_clock_settings.py"), str(x), str(y)],
            str(_REPO),
        )
    
    def _update_clock(self):
        settings = {}
        if not (
            "pytest" in sys.modules
            or os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
        ):
            settings_path = _REPO / ".sifta_state" / "clock_settings.json"
            if settings_path.exists():
                try:
                    with open(settings_path, "r") as f:
                        settings = json.load(f)
                except Exception:
                    pass
                
        now = QDateTime.currentDateTime()
        
        # Build the format string
        fmt_parts = []
        if settings.get("show_day_of_week", True):
            fmt_parts.append("ddd")
        if settings.get("show_date", True):
            fmt_parts.append("MMM d")
            
        # Time string
        t_fmt = "h:mm" if settings.get("show_am_pm", True) else "H:mm"
        if settings.get("show_seconds", False):
            t_fmt += ":ss"
        if settings.get("show_am_pm", True):
            t_fmt += " AP"
            
        time_str = now.toString(t_fmt)
        
        if settings.get("flash_separators", False):
            if now.time().second() % 2 == 1:
                time_str = time_str.replace(":", " ")
                
        if fmt_parts:
            date_str = now.toString(" ".join(fmt_parts))
            time_str = f"{date_str}   {time_str}"

        if hasattr(self, "clock_label"):
            self.clock_label.setText(time_str)
        if not (
            "pytest" in sys.modules
            or os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
        ):
            self._update_alice_status()
            
            
        # Optional: Announce the time
        if settings.get("announce_time", False) and now.time().second() == 0:
            m = now.time().minute()
            interval = settings.get("announce_interval", "On the hour")
            should_announce = False
            if interval == "On the hour" and m == 0:
                should_announce = True
            elif interval == "On the half hour" and m in (0, 30):
                should_announce = True
            elif interval == "On the quarter hour" and m in (0, 15, 30, 45):
                should_announce = True
                
            if should_announce:
                h = now.time().hour()
                h_12 = h % 12 or 12
                ampm = "AM" if h < 12 else "PM"
                m_str = "o'clock" if m == 0 else str(m)
                say_text = f"It's {h_12} {m_str} {ampm}"
                
                say_args = [say_text]
                voice = settings.get("announce_voice", "System Voice")
                if voice != "System Voice":
                    say_args = ["-v", voice, say_text]
                
                QProcess.startDetached("say", say_args)

        # ── Swarm economy HUD (heavy: scan_repair_log, treasuries). Gated; see
        #    _economy_hud_full_scan_enabled() — offscreen/CI skip; live default on.


    def _update_alice_status(self):
        """Poll Alice's vocal state and update the top-bar indicator.
        P0 fix (Dr. Codex 2026-04-28): mtime-gated — disk reads only when
        either JSONL file has changed since last check. On idle seconds
        (no speech, no transcription) this is a pure stat() call — ~0.01 ms.
        """
        if not hasattr(self, "_alice_status_label"):
            return
        try:
            import time as _time

            # 1) BROCA_SPEAKING — in-memory flag, zero disk cost
            try:
                from System.swarm_broca_wernicke import _BROCA_SPEAKING
                if _BROCA_SPEAKING.is_set():
                    self._alice_status_label.setText("🗣  speaking")
                    self._alice_status_label.setStyleSheet(
                        "color: #e0af68; font-size: 12px; font-weight: bold;"
                        " background: transparent; padding: 0 12px;"
                    )
                    return
            except Exception:
                pass

            now = _time.time()
            import json as _json

            # 2) Broca log — stat() first; only open if mtime changed
            broca_log = _REPO / ".sifta_state" / "broca_vocalizations.jsonl"
            try:
                mtime = broca_log.stat().st_mtime
                if mtime != getattr(self, "_broca_mtime", None):
                    self._broca_mtime = mtime
                    with open(broca_log, "rb") as _f:
                        size = _f.seek(0, 2)
                        _f.seek(max(0, size - 512))
                        last = _f.read().decode("utf-8", "replace").strip().split("\n")[-1]
                    self._broca_last_row = _json.loads(last)
                row = getattr(self, "_broca_last_row", {})
                if now - row.get("ts", 0) < 4:
                    self._alice_status_label.setText("🧠  thinking…")
                    self._alice_status_label.setStyleSheet(
                        "color: #bb9af7; font-size: 12px; font-weight: bold;"
                        " background: transparent; padding: 0 12px;"
                    )
                    return
            except Exception:
                pass

            # 3) Wernicke log — same mtime gate
            wern_log = _REPO / ".sifta_state" / "wernicke_semantics.jsonl"
            try:
                mtime = wern_log.stat().st_mtime
                if mtime != getattr(self, "_wern_mtime", None):
                    self._wern_mtime = mtime
                    with open(wern_log, "rb") as _f:
                        size = _f.seek(0, 2)
                        _f.seek(max(0, size - 512))
                        last = _f.read().decode("utf-8", "replace").strip().split("\n")[-1]
                    self._wern_last_row = _json.loads(last)
                row = getattr(self, "_wern_last_row", {})
                if now - row.get("ts", 0) < 3:
                    self._alice_status_label.setText("🎙  listening")
                    self._alice_status_label.setStyleSheet(
                        "color: #9ece6a; font-size: 12px; font-weight: bold;"
                        " background: transparent; padding: 0 12px;"
                    )
                    return
            except Exception:
                pass

            # 4) Idle — clear
            self._alice_status_label.setText("")
        except Exception:
            pass


    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Clock is layout-managed inside _build_top_menu_bar — no manual
        # positioning needed.
        #
        # Architect 2026-05-12 00:35: window resize was taking 30 s because
        # the previous version called `self._apply_wallpaper(force=True)`
        # on every single resize event. Dragging the window handle fires
        # ~60 of those per second; each one re-reads the wallpaper file
        # from disk (141 KB SVG / 700 KB JPG), decodes it, and forces a
        # SmoothTransformation rescale on the QPixmap.
        #
        # `SiftaMdiArea._scaled_wallpaper` already caches the scaled
        # pixmap keyed by (width, height) and re-scales when the cache
        # key changes — no disk read needed on resize. So we just let
        # Qt's normal paintEvent flow handle it, and DEBOUNCE the
        # filesystem re-check to ~150 ms after the user stops resizing.
        if hasattr(self, "mdi") and hasattr(self, "_wallpaper_state"):
            wpd = getattr(self, "_wallpaper_resize_debounce", None)
            if wpd is None:
                wpd = QTimer(self)
                wpd.setSingleShot(True)
                wpd.timeout.connect(lambda: self._apply_wallpaper(force=True))
                self._wallpaper_resize_debounce = wpd
            wpd.start(150)


    # ── Taskbar ────────────────────────────────────────────
    def _build_taskbar(self):
        """
        Classic bottom strip (SIFTA menu, relay, power). Not mounted in the main
        Mermaid column (top bar + MDI + dock only) — call sites only, if reintroduced.
        """
        bar = QWidget()
        bar.setFixedHeight(45)
        bar.setStyleSheet("background-color: #1a1b26; border-top: 1px solid #414868;")

        layout = QHBoxLayout()
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(10)

        btn_start = QPushButton("🐜 SIFTA")
        btn_start.setStyleSheet(
            "QPushButton { font-weight: bold; background-color: #bb9af7;"
            "  color: #15161e; padding: 6px 12px; border-radius: 4px; }"
            "QPushButton::menu-indicator { image: none; }"
            "QPushButton:hover { background-color: #9d7cd8; }"
        )
        menu = QMenu(btn_start)
        menu.setStyleSheet(
            "QMenu { background-color: #1a1b26; color: #a9b1d6; border: 1px solid #414868; padding: 5px; }"
            "QMenu::item { padding: 5px 20px; }"
            "QMenu::item:selected { background-color: #24283b; color: #bb9af7; }"
        )

        prog = menu.addMenu("Programs ▶")
        acc  = prog.addMenu("Accessories ▶")
        utilities_menu = prog.addMenu("Utilities ▶")
        creative = prog.addMenu("Creative ▶")
        sims = prog.addMenu("Simulations ▶")
        net  = prog.addMenu("Networking ▶")
        sys_menu = prog.addMenu("System ▶")

        # ── Core Built-in OS Apps ────────────────────────
        acc.addAction("💭 Swarm Chat").triggered.connect(self.open_swarm_chat)
        acc.addAction("Silence Remover & Stitcher").triggered.connect(self.open_video_editor)
        acc.addAction("SwarmText Editor").triggered.connect(lambda: self.spawn_text_editor(None))

        # ── Dynamic Native Apps (sorted by fitness) ────────
        manifest_path = "Applications/apps_manifest.json"
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r") as f:
                    apps = json.load(f)
                self._apps_manifest_cache = dict(apps)
                app_names_sorted = ranked_apps(list(apps.keys()))
                for app_name in app_names_sorted:
                    app_data = apps[app_name]
                    cat = app_data.get("category", "Accessories")
                    entry = app_data.get("entry_point", "")
                    widget_class = app_data.get("widget_class", "")
                    if not entry:
                        continue
                    if app_data.get("_retired"):  # AG31: skip retired apps in Programs menu
                        continue

                    target_menu = acc
                    if cat == "Utilities":
                        target_menu = utilities_menu
                    elif cat == "Simulations":
                        target_menu = sims
                    elif cat == "Creative":
                        target_menu = creative
                    elif cat == "Networking":
                        target_menu = net
                    elif cat == "System":
                        target_menu = sys_menu

                    launch = (
                        (lambda nm, ep, wc, dat: lambda: self._launch_app(
                            nm,
                            ep,
                            wc,
                            w=int(dat.get("window_width", 920)),
                            h=int(dat.get("window_height", 640)),
                        ))(app_name, entry, widget_class, dict(app_data))
                        if widget_class
                        else (lambda nm, e: lambda: self._launch_terminal_app(nm, e))(app_name, entry)
                    )
                    ic = str(app_data.get("icon") or app_data.get("emoji") or "").strip()
                    disp = f"{ic} {app_name}" if ic else app_name
                    target_menu.addAction(disp).triggered.connect(launch)

                # ── AUTOSTART ───────────────────────────────────────────────
                # Any manifest entry with `"autostart": true` is opened
                # automatically when the desktop comes up. This is how Alice
                # (Talk-to-Alice + What-Alice-Sees) becomes part of "the OS"
                # without the Architect ever clicking a menu. Each app gets
                # its own QTimer.singleShot using its `autostart_delay_ms` so
                # they appear in `autostart_order` and the desktop has time
                # to paint before camera/mic init kicks in.
                #
                # macOS reality (one-time, then forever):
                #   The very first boot after a fresh install will trigger
                #   the system TCC consent dialog for Camera and Microphone
                #   when the widgets initialize. Click Allow once for each.
                #   macOS persists the grant per app; subsequent boots are
                #   silent.
                if _desktop_autostart_enabled():
                    autostart_entries = [
                        (name, dat) for name, dat in apps.items()
                        if dat.get("autostart") is True and dat.get("entry_point")
                    ]
                    autostart_entries.sort(
                        key=lambda kv: (int(kv[1].get("autostart_order", 99)),
                                        kv[0].lower())
                    )
                    for ord_idx, (name, dat) in enumerate(autostart_entries):
                        delay = int(dat.get("autostart_delay_ms",
                                            700 + 600 * ord_idx))
                        QTimer.singleShot(
                            delay,
                            (lambda nm: lambda: self._autostart_one(nm))(name),
                        )
            except Exception as e:
                print(f"[Boot Error] Failed to load apps manifest: {e}")

        # ── Swarm Intelligence submenu ─────────────────────
        intel = menu.addMenu("Swarm Intelligence ▶")
        intel.setStyleSheet(
            "QMenu { background-color: #1a1b26; color: #a9b1d6; border: 1px solid #414868; padding: 5px; }"
            "QMenu::item { padding: 5px 20px; }"
            "QMenu::item:selected { background-color: #24283b; color: #bb9af7; }"
        )
        intel.addAction("🧠 Dream Report").triggered.connect(self._show_dream_report)
        intel.addAction("🛡 Immune Status").triggered.connect(self._show_immune_status)
        intel.addAction("🗳 Quorum Proposals").triggered.connect(self._show_quorum_status)
        intel.addAction("⚡ Nerve Channel").triggered.connect(self._show_nerve_status)
        intel.addAction("🗺 File Trails").triggered.connect(self._show_file_trails)
        intel.addAction("📊 App Fitness").triggered.connect(self._show_fitness_scores)

        docs = menu.addMenu("Documents ▶")
        docs.addAction("README.md").triggered.connect(lambda: self.spawn_text_editor("Documents/README.md"))
        docs.addAction("APP_HELP.md").triggered.connect(lambda: self.spawn_text_editor("Documents/APP_HELP.md"))
        docs.addAction("repair_log.jsonl").triggered.connect(lambda: self.spawn_text_editor("Utilities/repair_log.jsonl"))

        menu.addSeparator()
        finance_menu = menu.addMenu("Finance ▶")
        finance_menu.addAction("⚡ Swarm Finance").triggered.connect(
            lambda: self.spawn_native_widget(
                "Swarm Finance", "Applications/sifta_finance.py", "FinanceDashboard",
                w=480, h=640, x=420, y=30
            )
        )

        menu.addSeparator()
        menu.addAction("Help").triggered.connect(
            lambda: self.spawn_text_editor("Documents/APP_HELP.md")
        )
        btn_start.setMenu(menu)
        layout.addWidget(btn_start)

        # ── Mesh status indicator ──
        self._relay_indicator = QLabel("Mesh: Global mode")
        self._relay_indicator.setStyleSheet(
            "color: #565f89; font-family: monospace; font-size: 11px; padding: 0 8px;"
        )
        layout.addWidget(self._relay_indicator)

        # Mesh status indicator — was a 2 s poll, now signal-driven.
        # Architect 00:14: the mesh worker already emits connection_status;
        # the indicator updates on that event plus on BehaviorClock ticks
        # so it stays fresh when the owner is doing something.
        self._relay_timer = QTimer(self)  # kept for API compat, never started
        self._relay_timer.timeout.connect(self._update_relay_indicator)
        try:
            dm = getattr(self, "_desktop_mesh", None)
            if dm is not None:
                dm.connection_status.connect(lambda *_a: self._update_relay_indicator())
        except Exception:
            pass
        try:
            from System.swarm_behavior_clock import behavior_clock
            behavior_clock().tick.connect(lambda *_a: self._update_relay_indicator())
        except Exception:
            pass
        # One initial paint so the indicator isn't blank at first show.
        QTimer.singleShot(0, self._update_relay_indicator)

        btn_power = QPushButton("⏻")
        btn_power.setStyleSheet(
            "QPushButton { background: transparent; color: #f7768e; font-weight: bold; border: none; padding: 0 10px; }"
            "QPushButton:hover { background-color: #24283b; border-radius: 4px; }"
        )
        btn_power.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_power.clicked.connect(self.close)
        
        layout.addStretch(1)
        layout.addWidget(btn_power)
        bar.setLayout(layout)
        return bar

    def _update_relay_indicator(self):
        """Check if the desktop's WebSocket mesh client is connected."""
        if not hasattr(self, "_desktop_mesh") or self._desktop_mesh is None:
            self._relay_indicator.setText("●  Mesh: Global mode")
            self._relay_indicator.setStyleSheet(
                "color: #565f89; font-family: monospace; font-size: 11px; padding: 0 4px;"
            )
            return

        if self._desktop_mesh.isRunning() and self._mesh_connected:
            self._relay_indicator.setText("●  Mesh: Global link")
            self._relay_indicator.setStyleSheet(
                "color: #9ece6a; font-family: monospace; font-size: 11px;"
                " font-weight: bold; padding: 0 4px;"
            )
        else:
            self._relay_indicator.setText("●  Mesh: Global mode")
            self._relay_indicator.setStyleSheet(
                "color: #565f89; font-family: monospace; font-size: 11px;"
                " font-weight: normal; padding: 0 4px;"
            )
    # ── Window factories ───────────────────────────────────
    def _make_sub(self, widget, title, w, h, border_color="#414868", x=None, y=None, key=None, pinned=False):
        # Singleton-by-key for EVERY caller. One click = one window. Re-clicks
        # raise the existing window instead of spawning duplicates. `key`
        # lets callers (e.g. spawn_native_widget) match the slot they
        # pre-claimed under a different display title (icon prefix etc).
        slot_key = key if key is not None else title
        existing = self._open_windows.get(slot_key)
        if existing is not None and existing != "_LOADING_":
            try:
                if (
                    existing not in self.mdi.subWindowList()
                    or existing.isHidden()
                    or existing.widget() is None
                ):
                    try:
                        _shutdown_embedded_widget_tree(existing.widget())
                    except Exception:
                        pass
                    try:
                        self.mdi.removeSubWindow(existing)
                    except Exception:
                        pass
                    try:
                        existing.deleteLater()
                    except Exception:
                        pass
                    self._open_windows.pop(slot_key, None)
                else:
                    existing.showNormal()
                    existing.raise_()
                    self.mdi.setActiveSubWindow(existing)
                    try:
                        widget.deleteLater()
                    except Exception:
                        pass
                    return existing
            except RuntimeError:
                self._open_windows.pop(slot_key, None)

        existing = self._open_windows.get(slot_key)
        if existing is not None and existing != "_LOADING_":
            try:
                existing.show()
                existing.raise_()
                self.mdi.setActiveSubWindow(existing)
                try:
                    widget.deleteLater()
                except Exception:
                    pass
                return existing
            except RuntimeError:
                self._open_windows.pop(slot_key, None)

        sub = MagneticSubWindow()
        sub.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        sub.setWindowFlags(
            Qt.WindowType.SubWindow
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint
            # WindowCloseButtonHint removed AG31: macOS traffic-light (top-left) handles close.
            # Adding a second X in the right corner confused Architect and duplicate-closed windows.
        )
        sub.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        # Architect 2026-05-12 22:25: "he cannot be resized". On macOS the
        # QMdiSubWindow native resize edges are nearly invisible against the
        # dark frame. Force a visible bottom-right size grip so every app
        # window can be dragged smaller/larger by the corner.
        try:
            sub.setSizeGripEnabled(True)
        except Exception:
            pass

        # Use a custom dark title bar to avoid white native title strips on macOS.
        title_bar = QWidget()
        title_bar.setFixedHeight(30)
        title_bar.setStyleSheet(
            "background-color: #0f1118; border-bottom: 1px solid #2a2f3a;"
        )
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(8, 3, 6, 3)
        title_layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #c0caf5; font-weight: 600; font-size: 12px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # ── ? Help button (AG31) ───────────────────────────────────────────
        # Non-BaseWidget apps need wrapper help; SiftaBaseWidget apps already
        # expose their own contextual help button inside the app chrome.
        _help_app_name = title  # capture for closure
        _manifest_cache = self._apps_manifest_cache

        def _make_help_popup(app_name: str) -> None:
            """Show a styled help popup for `app_name`."""
            from PyQt6.QtWidgets import QTextBrowser, QDialog, QVBoxLayout as _VBox, QHBoxLayout as _HBox, QPushButton as _Btn
            from PyQt6.QtCore import QUrl

            meta = _manifest_cache.get(app_name, {})
            entry = meta.get("entry_point", "")
            description = meta.get("description", "")
            github_url = (
                f"https://github.com/antonpictures/ANTON-SIFTA/blob/main/{entry}"
                if entry else "https://github.com/antonpictures/ANTON-SIFTA"
            )

            # Pull from APP_HELP.md
            from System.sifta_base_widget import _load_help_text
            help_body = _load_help_text(app_name)

            html = f"""
<html><head><style>
  body   {{ background:#0b1020; color:#c0caf5; font-family:'Menlo',monospace;
            font-size:13px; padding:18px; margin:0; }}
  h2     {{ color:#00ffc8; margin:0 0 6px 0; font-size:16px; }}
  .tag   {{ color:#565f89; font-size:11px; margin-bottom:14px; }}
  .desc  {{ color:#7aa2f7; margin-bottom:14px; font-style:italic; }}
  .body  {{ color:#c0caf5; white-space:pre-wrap; line-height:1.6; }}
  a      {{ color:#00ffc8; text-decoration:none; }}
  a:hover{{ text-decoration:underline; }}
  hr     {{ border:none; border-top:1px solid #2a2f3a; margin:14px 0; }}
</style></head><body>
<h2>{app_name}</h2>
<div class="tag">SIFTA OS &nbsp;·&nbsp; <a href="{github_url}">View source on GitHub ↗</a></div>
{"<div class='desc'>" + description + "</div>" if description else ""}
<hr>
<div class="body">{help_body.replace("<","&lt;").replace(">","&gt;")}</div>
</body></html>"""

            dlg = QDialog()
            dlg.setWindowTitle(f"? Help — {app_name}")
            dlg.setMinimumSize(660, 480)
            dlg.setStyleSheet("QDialog { background: #0b1020; }")
            vl = _VBox(dlg)
            vl.setContentsMargins(0, 0, 0, 0)
            browser = QTextBrowser()
            browser.setOpenExternalLinks(True)
            browser.setStyleSheet(
                "QTextBrowser { background:#0b1020; border:none; padding:4px; }"
            )
            browser.setHtml(html)
            vl.addWidget(browser)
            hl = _HBox()
            hl.setContentsMargins(12, 6, 12, 10)
            hl.addStretch()
            close_btn = _Btn("Close")
            close_btn.setFixedWidth(80)
            close_btn.setStyleSheet(
                "QPushButton { background:#1a1b26; color:#c0caf5; border:1px solid #414868;"
                " border-radius:5px; padding:5px 10px; } QPushButton:hover { border-color:#00ffc8; }"
            )
            close_btn.clicked.connect(dlg.accept)
            hl.addWidget(close_btn)
            vl.addLayout(hl)
            dlg.exec()

        if not _widget_provides_contextual_help(widget):
            btn_help = QPushButton("?")
            btn_help.setObjectName("mdiTitleHelpButton")
            btn_help.setFixedSize(22, 22)
            btn_help.setToolTip(f"Help — {_help_app_name}")
            btn_help.setStyleSheet(
                "QPushButton { background: #1a1b26; color: #00ffc8; border: 1px solid #2a2f3a;"
                " border-radius: 5px; font-weight: bold; font-size: 13px; padding: 0; }"
                " QPushButton:hover { background: #24283b; border-color: #00ffc8; }"
            )
            btn_help.clicked.connect(lambda _=False, n=_help_app_name: _make_help_popup(n))
            title_layout.addWidget(btn_help)

        # QMdiSubWindow has no setTitleBarWidget in PyQt6. We inject it inside.

        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addWidget(title_bar)
        wrapper_layout.addWidget(widget)
        
        # Set the wrapper and apply dimensions AFTER construction so it doesn't collapse.
        # Leave an inset lane in the MDI viewport so large apps can still cascade
        # visibly instead of every oversized window clamping to (0, 0).
        vp = self.mdi.viewport().rect()
        max_w = max(360, vp.width() - 80) if vp.width() > 160 else int(w)
        max_h = max(300, vp.height() - 80) if vp.height() > 160 else int(h)
        w = min(int(w), int(max_w))
        h = min(int(h), int(max_h))
        sub.setWidget(wrapper)
        sub.setWindowTitle(title)
        sub.resize(w, h)

        sub.setStyleSheet(f"""
            QMdiSubWindow {{
                background-color: #1a1b26;
                border: 2px solid {border_color};
                border-radius: 6px;
            }}
        """)
        self.mdi.addSubWindow(sub)
        siblings = [
            sw for sw in self.mdi.subWindowList()
            if sw is not sub and not sw.isHidden()
        ]
        if x is None or y is None:
            if siblings:
                last = siblings[-1]
                x_pref = last.x() + 60
                y_pref = last.y() + 40
            else:
                x_pref, y_pref = 60, 40
        else:
            x_pref, y_pref = int(x), int(y)
        x_resolved, y_resolved = resolve_mdi_subwindow_position(
            self.mdi,
            sub,
            int(w),
            int(h),
            int(x_pref),
            int(y_pref),
            step_x=60,
            step_y=40,
        )
        occupied_top_left = {(sw.x(), sw.y()) for sw in siblings}
        nudge_attempt = 0
        visible_max_x = max(0, vp.width() - 160)
        visible_max_y = max(30, vp.height() - 120)
        while (x_resolved, max(30, y_resolved)) in occupied_top_left and nudge_attempt < 12:
            nudge_attempt += 1
            x_resolved += 60
            y_resolved = max(30, y_resolved + 40)
            if x_resolved > visible_max_x:
                x_resolved = 60 + (nudge_attempt % 4) * 28
            if y_resolved > visible_max_y:
                y_resolved = 40 + (nudge_attempt % 4) * 24
        sub.move(x_resolved, max(30, y_resolved))  # never overlap the top bar
        if pinned:
            sub.set_sifta_pinned(True)
            sub.setToolTip("Pinned SIFTA organ: resizable, not draggable.")
        sub.show()
        self._open_windows[slot_key] = sub
        open_windows = self._open_windows
        sub.destroyed.connect(lambda _obj=None, _k=slot_key, _windows=open_windows: _windows.pop(_k, None))
        # Architect 2026-05-13 08:10 — witness journal entry on every
        # app close, paired with the app_launch witness on open. The
        # journal now shows both opens and closes of every app in plain
        # first-person English with date+time.
        sub.destroyed.connect(
            lambda _obj=None, _t=str(title or "the app"): self._witness_app_close(_t)
        )
        return sub

    def _panel_help_text(self, title: str) -> str:
        """Plain-language help for built-in status panels."""
        t = title.lower()
        if "dream report" in t:
            return (
                "Dream Report summarizes overnight swarm activity.\n\n"
                "- Dead drop: message traffic + error mentions\n"
                "- Repairs: interventions made\n"
                "- Economy: STGM mint activity\n"
                "- Crashing apps: low-fitness app alerts\n"
                "- Top fitness: most stable / most used apps\n\n"
                "Assessment 'Anomalies detected' means review flagged lines."
            )
        if "immune memory" in t:
            return (
                "Immune Memory shows learned threat signatures (antibodies).\n\n"
                "- Total antibodies: known threat patterns\n"
                "- Matches: successful recognitions\n"
                "- Pattern types: threat categories (e.g., ip_flood)\n\n"
                "This panel confirms whether swarm immunity is learning."
            )
        if "quorum sense" in t:
            return (
                "Quorum Sense governs irreversible actions.\n\n"
                "- No active proposals = no pending high-risk actions\n"
                "- Active proposals show vote progress and age\n\n"
                "Use this before major destructive or one-way operations."
            )
        if "nerve channel" in t:
            return (
                "Nerve Channel is the fast UDP reflex bus between nodes.\n\n"
                "- Protocol and datagram size confirm wire format\n"
                "- Test decode verifies packet parsing\n"
                "- Signal list is the reflex vocabulary (HEARTBEAT, ALERT, etc.)\n\n"
                "Set peer IPs in System/nerve_channel.py for live cross-node pulses."
            )
        if "file trails" in t:
            return (
                "File Trails show stigmergic co-access patterns.\n\n"
                "- Trail pairs: files frequently touched together\n"
                "- Clusters: emergent working sets\n\n"
                "Useful for understanding architecture gravity and workflow coupling."
            )
        if "app fitness" in t:
            return (
                "App Fitness ranks stability + utility over time.\n\n"
                "- Launches increase fitness\n"
                "- Crashes reduce fitness\n"
                "- Daily decay prevents stale rankings\n\n"
                "Negative scores are warning signals, not fatal errors."
            )
        return (
            "SIFTA system panel.\n\n"
            "Read values as telemetry: state, trend, and anomaly flags.\n"
            "Use SIFTA → Help to open Documents/APP_HELP.md, or in-app ? on SiftaBaseWidget apps."
        )

    def open_swarm_chat(self):
        if self.active_chat_sub is not None:
            try:
                subs = self.mdi.subWindowList()
                if (
                    self.active_chat_sub in subs
                    and not self.active_chat_sub.isHidden()
                    and self.active_chat_sub.widget() is not None
                ):
                    self.active_chat_sub.showNormal()
                    self.active_chat_sub.raise_()
                    return
            except RuntimeError:
                pass
            self.active_chat_sub = None
            self._open_windows.pop("SIFTA CORE CHAT", None)
        
        import sys
        _apps_path = str(_REPO / "Applications")
        if _apps_path not in sys.path:
            sys.path.insert(0, _apps_path)
            
        from sifta_swarm_chat import SwarmChatWindow
        chat = SwarmChatWindow()
        
        # The user wants the core interface extremely prominent
        mdi_w = self.mdi.width() if self.mdi.width() > 100 else 1280
        mdi_h = self.mdi.height() if self.mdi.height() > 100 else 720
        w = max(800, int(mdi_w * 0.70))
        h = max(600, int(mdi_h * 0.82))
        x = max(0, (mdi_w - w) // 2)
        y = max(40, mdi_h - h - 10)  # Pin to bottom with small margin
        
        sub  = self._make_sub(chat, "🐜 SIFTA CORE CHAT", w, h, "#565f89", x=x, y=y, key="SIFTA CORE CHAT", pinned=True)
        self.active_chat_sub = sub
        sub.destroyed.connect(lambda _obj=None, _sub=sub: setattr(self, "active_chat_sub", None) if self.active_chat_sub is _sub else None)

    def open_video_editor(self):
        editor = VideoEditorSubWindow()
        self._make_sub(editor, "Aether Silence Remover & Stitcher", 750, 450, "#414868", x=20, y=40, pinned=True)

    def spawn_text_editor(self, filepath=None):
        name = os.path.basename(filepath) if filepath else "Untitled"
        self._make_sub(SwarmTextEditorWindow(filepath), f"SwarmText: {name}", 700, 500, "#bb9af7")

    def spawn_terminal(self, title, cmd, args):
        self._make_sub(TerminalSubWindow(cmd, args), title, 600, 400, "#9ece6a")

    def spawn_embedded_script(self, title, script_path):
        self._make_sub(EmbeddedScriptSubWindow(title, script_path), title, 860, 560, "#9ece6a")

    # ── Swarm-intelligent app launcher ───────────────────
    def _launch_app(self, title, module_path, class_name, w=660, h=540, pinned=False):
        """Launch an app: record fitness, WM pheromone, suggest position.
        Architect 2026-05-13 05:00 — Alice's witness organ logs every
        app-open with date+time so the journal preserves "what apps
        Architect used at what time". Quiet-mode doesn't suppress
        witness writes; she records even when she isn't speaking."""
        record_launch(title)
        wm_record_open(title)
        fs_record_access(module_path)
        try:
            from System.swarm_alice_witness import witness
            try:
                from System.swarm_kernel_identity import owner_display_name as _odn
                _owner = _odn() or "George"
            except Exception:
                _owner = "George"
            witness(
                f"{_owner} opened the {title} app.",
                source="app_launch",
            )
        except Exception:
            pass
        try:
            from System.swarm_app_focus import publish_focus
            publish_focus(title, "User launched application from Programs menu")
        except Exception:
            pass
        try:
            from System.swarm_unified_cowatch_field import write_organ_focus
            write_organ_focus(title)  # initial open — no guess data yet
        except Exception:
            pass

        # Build {title: (x,y)} from live subwindow positions for the cascade calc
        win_positions = {}
        for name, sw in self._open_windows.items():
            try:
                win_positions[name] = (sw.x(), sw.y())
            except Exception:
                pass

        pos = suggest_position(
            title, win_positions,
            mdi_w=self.mdi.width() or 1280,
            mdi_h=self.mdi.height() or 720,
            win_w=w, win_h=h,
        )
        x, y = pos if pos else (60, 40)
        self.spawn_native_widget(title, module_path, class_name, w=w, h=h, x=x, y=y, pinned=pinned)


    def _launch_terminal_app(self, title, entry):
        """Launch a script app inside iSwarm OS (no external popout intent)."""
        record_launch(title)
        wm_record_open(title)
        fs_record_access(entry)
        try:
            from System.swarm_app_focus import publish_focus
            publish_focus(title, "User launched terminal application from Programs menu")
        except Exception:
            pass
        self.spawn_embedded_script(title, entry)

    def _launch_headless_terminal_probe(self, title: str = "Terminal"):
        from types import SimpleNamespace

        widget = QWidget()
        state = {"running": True}

        def is_running() -> bool:
            return state["running"]

        def mark_stopped() -> None:
            state["running"] = False

        widget.process = None
        widget.terminal = SimpleNamespace(is_running=is_running)
        widget.mark_stopped = mark_stopped
        widget.shutdown = mark_stopped
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Headless terminal probe"))
        sub = self._make_sub(widget, title, 700, 450, "#9ece6a", key=title)
        sub.destroyed.connect(lambda _obj=None, w=widget: w.mark_stopped())
        return sub

    def spawn_native_widget(self, title, module_path, class_name, w=660, h=540, x=None, y=None, pinned=False):
        """Import a SIFTA app module and embed its widget class inside the MDI.
        No subprocess. No separate QApplication. Stays inside Swarm OS.

        Singleton: if this app is already open (or is being loaded), raise it —
        never open a duplicate. Sentinel is set BEFORE module loading to close
        the race between double-clicks.
        """
        # ── Singleton guard — check first ─────────────────────────────────
        existing = self._open_windows.get(title)
        if existing is not None:
            if existing == "_LOADING_":
                return  # already loading — ignore extra click
            try:
                existing.show()
                existing.raise_()
                self.mdi.setActiveSubWindow(existing)
                return
            except RuntimeError:
                # C++ object deleted without the signal firing — clean up
                self._open_windows.pop(title, None)

        # ── Claim the slot immediately so re-entry is blocked ─────────────
        self._open_windows[title] = "_LOADING_"

        try:
            import importlib.util
            import sys
            abs_path = str(_REPO / module_path)
            module_name = os.path.splitext(os.path.basename(abs_path))[0]
            spec = importlib.util.spec_from_file_location(module_name, abs_path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Unable to build import spec for {module_path}")
            mod = importlib.util.module_from_spec(spec)
            # Python 3.13 dataclasses + postponed annotations need module registered
            # in sys.modules before exec_module() or dataclass decoration can fail.
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)
            widget_cls = getattr(mod, class_name)
            widget = widget_cls()
            sub = self._make_sub(widget, f"⚙ {title}", w, h, "#7aa2f7", x=x, y=y, key=title, pinned=pinned)
        except Exception as e:
            self._open_windows.pop(title, None)       # clear sentinel on failure
            record_crash(title)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Launch Error", f"Failed to load {title}:\n{e}")




    # ── Swarm Intelligence Panels ──────────────────────────
    def _show_genesis_onboarding(self):
        """Show the Owner Genesis onboarding if no genesis scar exists."""
        try:
            from Applications.sifta_genesis_widget import GenesisWidget
            w = GenesisWidget()
            self._make_sub(w, "Owner Genesis", 620, 720, "#ff28c8")
        except Exception as e:
            print(f"[GENESIS] Onboarding failed to load: {e}")

    def _show_dream_report(self):
        from Applications.sifta_intelligence_panels import DreamReportPanel
        self._make_sub(DreamReportPanel(), "🧠 Dream Report", 800, 480, "#bb9af7")

    def _show_immune_status(self):
        from Applications.sifta_intelligence_panels import ImmuneSystemPanel
        self._make_sub(ImmuneSystemPanel(), "🛡 Immune Memory", 750, 460, "#f7768e")

    def _show_quorum_status(self):
        from Applications.sifta_intelligence_panels import QuorumSensePanel
        self._make_sub(QuorumSensePanel(), "🗳 Quorum Sense", 700, 480, "#e0af68")

    def _show_nerve_status(self):
        from Applications.sifta_intelligence_panels import NerveChannelPanel
        self._make_sub(NerveChannelPanel(), "⚡ Nerve Channel", 750, 480, "#73daca")

    def _show_file_trails(self):
        from Applications.sifta_intelligence_panels import FileTrailsPanel
        self._make_sub(FileTrailsPanel(), "🗺 File Trails", 800, 600, "#9ece6a")

    def _show_fitness_scores(self):
        from Applications.sifta_intelligence_panels import AppFitnessPanel
        self._make_sub(AppFitnessPanel(), "📊 App Fitness", 800, 600, "#7dcfff")


    def _autostart_one(self, app_name: str) -> None:
        """
        Open one autostart app and announce it on stderr so a silent
        failure (e.g. faster-whisper not installed, camera blocked) is
        visible in the boot log instead of looking like Alice just chose
        not to wake up.
        """
        try:
            print(f"[AUTOSTART] launching {app_name!r}…", file=sys.stderr)
            self._trigger_manifest_app(app_name)
        except Exception as exc:
            print(f"[AUTOSTART] {app_name!r} failed: "
                  f"{type(exc).__name__}: {exc}", file=sys.stderr)

    def _trigger_manifest_app(self, app_name: str):
        if app_name in {"Alice", "Talk to Alice", "What Alice Sees"}:
            # §7.6/7.7/7.8: Alice is the fixed resident panel — not a floating MDI window.
            # _embed_alice_panel handles idempotency (no-op if already embedded).
            self._embed_alice_panel()
            return
        if app_name in self._apps_manifest_cache:
            dat = self._apps_manifest_cache[app_name]
            entry = dat.get("entry_point")
            widget_class = dat.get("widget_class")
            if widget_class:
                if (
                    app_name == "Terminal"
                    and (
                        "pytest" in sys.modules
                        or os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
                    )
                ):
                    self._launch_headless_terminal_probe(app_name)
                    return
                self._launch_app(
                    app_name,
                    entry,
                    widget_class,
                    w=int(dat.get("window_width", 920)),
                    h=int(dat.get("window_height", 640))
                )
            elif entry:
                self._launch_terminal_app(app_name, entry)

    def _build_desktop_shortcuts(self):
        # Removed. The desktop is now a pristine stigmergic canvas. 
        pass

    def keyPressEvent(self, event):
        mods = event.modifiers()
        key = event.key()
        if mods == Qt.KeyboardModifier.MetaModifier and key == Qt.Key.Key_Space:
            self._toggle_spotlight()
        elif mods == Qt.KeyboardModifier.MetaModifier and key == Qt.Key.Key_W:
            self._close_active_subwindow()
        elif mods == Qt.KeyboardModifier.MetaModifier and key == Qt.Key.Key_Q:
            self.close()
        elif mods == Qt.KeyboardModifier.MetaModifier and key in (Qt.Key.Key_QuoteLeft, Qt.Key.Key_Tab):
            self._cycle_windows()
        elif key == Qt.Key.Key_Escape:
            if hasattr(self, "_spotlight") and self._spotlight.isVisible():
                self._spotlight.hide()
            elif getattr(self, "_launchpad", None) is not None and self._launchpad.isVisible():
                self._launchpad.hide()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def _ensure_manifest_cache_loaded(self) -> None:
        """Populate ``_apps_manifest_cache`` once (dock + Launchpad need it early)."""
        if self._apps_manifest_cache:
            return
        import json

        manifest_path = _REPO / "Applications" / "apps_manifest.json"
        if not manifest_path.exists():
            return
        try:
            apps = json.loads(manifest_path.read_text(encoding="utf-8"))
            self._apps_manifest_cache = dict(apps)
        except Exception as exc:
            print(f"[Boot Error] Failed to load apps manifest: {exc}")

    def _load_apps_manifest_and_autostart(self):
        self._ensure_manifest_cache_loaded()
        if not self._apps_manifest_cache:
            return

        if not _desktop_autostart_enabled():
            return

        autostart_entries = [
            (name, dat) for name, dat in self._apps_manifest_cache.items()
            if dat.get("autostart") is True and dat.get("entry_point")
        ]
        autostart_entries.sort(
            key=lambda kv: (int(kv[1].get("autostart_order", 99)), kv[0].lower())
        )
        for idx, (name, dat) in enumerate(autostart_entries):
            delay = int(dat.get("autostart_delay_ms", 700 + 600 * idx))
            QTimer.singleShot(delay, (lambda nm: lambda: self._autostart_one(nm))(name))

    def _toggle_spotlight(self):
        if not hasattr(self, "_spotlight"):
            return
        if self._spotlight.isVisible():
            self._spotlight.hide()
            return
        if getattr(self, "_launchpad", None) is not None:
            self._launchpad.hide()
        surface = self.centralWidget() if self._spotlight.parentWidget() is self else (self._spotlight.parentWidget() or self)
        surface_rect = surface.geometry() if surface is self.centralWidget() else surface.rect()
        self._spotlight.setGeometry(
            surface_rect.x() + max(20, surface_rect.width() // 2 - 300),
            surface_rect.y() + max(60, surface_rect.height() // 3 - 120),
            min(600, max(320, surface_rect.width() - 40)),
            300,
        )
        self._spotlight.show()
        self._spotlight.raise_()
        self._spotlight.activateWindow()
        self._spotlight.search_bar.setFocus()
        self._spotlight.search_bar.clear()
        self._spotlight._update_list()

    def _toggle_launchpad(self):
        if getattr(self, "_launchpad", None) is None:
            self._launchpad = LaunchpadWidget(self)
            self._launchpad.hide()
        if self._launchpad.isVisible():
            self._launchpad.hide()
            return
        if hasattr(self, "_spotlight"):
            self._spotlight.hide()
        surface = self.centralWidget() or self
        rect = surface.geometry() if surface is self.centralWidget() else surface.rect()
        self._launchpad.setGeometry(rect)

        self._launchpad.reset_view()
        self._launchpad.show()
        self._launchpad.raise_()
        self._launchpad.activateWindow()
        self._launchpad.search_bar.setFocus()


    def _cycle_windows(self):
        """macOS-style window cycling for the MDI desktop (Cmd+` / Cmd+Tab)."""
        subs = [sw for sw in self.mdi.subWindowList() if not sw.isHidden()]
        if not subs:
            return
        active = self.mdi.activeSubWindow()
        try:
            idx = subs.index(active)
        except ValueError:
            idx = -1
        target = subs[(idx + 1) % len(subs)]
        target.showNormal()
        target.raise_()
        self.mdi.setActiveSubWindow(target)

    # ── Per-app menu definitions ───────────────────────────────────────────
    def _app_menu_spec(self, app_title: str) -> dict:
        """Return {menu_name: [(label, callable) | None, ...]} for app_title.
        None in list = separator. This drives the macOS-style dynamic menu bar."""
        _sep = None
        default = {
            # Architect 2026-05-13 07:15 — File menu pared to the two
            # apps about HER life and HIS life, plus Quit. Everything
            # else lives in the Launcher tab. Less to click, less to
            # crash, faster open.
            "File": [
                ("Alice Journal",     lambda: self._trigger_manifest_app("Alice Journal")),
                ("Provider Schedule", lambda: self._trigger_manifest_app("Provider Schedule")),
                _sep,
                ("Quit SIFTA OS", self.close),
            ],
            "Edit": [
                ("System Settings",       lambda: self._trigger_manifest_app("System Settings")),
                ("Intelligence Settings", lambda: self._trigger_manifest_app("Intelligence Settings")),
                _sep,
                ("Clock Settings",        self._open_clock_settings),
            ],
            "View": [
                ("Launchpad",    self._toggle_launchpad),
                ("Spotlight",    self._toggle_spotlight),
                _sep,
                ("Body Status", lambda: self._trigger_manifest_app("Biological Dashboard")),
            ],
            "Window": [
                ("Cascade Windows", self.mdi.cascadeSubWindows),
                ("Tile Windows",    self.mdi.tileSubWindows),
                _sep,
                ("Close All",       self.mdi.closeAllSubWindows),
            ],
        }
        overrides = {
            "System Settings": {
                "File": [
                    ("Close Window", lambda: self._close_active_subwindow()),
                    _sep,
                    ("Quit SIFTA OS", self.close),
                ],
                "Edit": [
                    ("Preferences…", lambda: self._trigger_manifest_app("System Settings")),
                    _sep,
                    ("Clock Settings", self._open_clock_settings),
                ],
                "View":   default["View"],
                "Window": default["Window"],
            },
            "SIFTA CORE CHAT": {
                "File": [
                    ("New Chat",     self.open_swarm_chat),
                    _sep,
                    ("Close Window", lambda: self._close_active_subwindow()),
                    ("Quit SIFTA OS", self.close),
                ],
                "Edit":   default["Edit"],
                "View":   default["View"],
                "Window": default["Window"],
            },
            "Conversation History": {
                "File": [
                    ("Open Conversation", lambda: self._trigger_manifest_app("Conversation History")),
                    _sep,
                    ("Close Window",  lambda: self._close_active_subwindow()),
                    ("Quit SIFTA OS", self.close),
                ],
                "Edit":   default["Edit"],
                "View":   default["View"],
                "Window": default["Window"],
            },
        }
        # Strip the ⚙ prefix _make_sub adds, and handle chat window title
        clean = app_title.lstrip("⚙ 🐜").strip()
        if "SIFTA CORE CHAT" in app_title:
            clean = "SIFTA CORE CHAT"
        return overrides.get(clean, default)

    def _close_active_subwindow(self):
        sub = self.mdi.activeSubWindow()
        if sub:
            sub.close()

    def _witness_app_close(self, title: str) -> None:
        """Architect 2026-05-13 08:10 — pair with _launch_app's witness:
        when an MDI subwindow is destroyed, write a first-person line to
        Alice's journal so opens and closes both land in plain English."""
        try:
            from System.swarm_alice_witness import witness
            # Strip the leading icon glyph that _make_sub prepends so the
            # line reads cleanly. ("⚙ Alice Journal" → "Alice Journal".)
            clean = (title or "").lstrip("⚙🐜🚀💬👁🌐 \t").strip()
            if not clean:
                clean = "an app"
            try:
                from System.swarm_kernel_identity import owner_display_name as _odn
                owner = _odn() or "George"
            except Exception:
                owner = "George"
            witness(f"{owner} closed the {clean} app.", source="app_close")
        except Exception:
            pass

    def _on_subwindow_activated(self, sub):
        """mdi.subWindowActivated — update app name label and menus."""
        if getattr(self, "_is_closing", False):
            return
        if sub is None:
            display = "SIFTA OS"
            title   = "SIFTA OS"
        else:
            title   = sub.windowTitle()
            display = title.lstrip("⚙ 🐜").strip() or "SIFTA OS"
            if "SIFTA CORE CHAT" in title:
                display = "Swarm Chat"
            focus_display = display
            if len(display) > 26:
                display = display[:24] + "…"
            _publish_sifta_active_window_focus(title, focus_display)
        if hasattr(self, "_menu_app_label"):
            self._menu_app_label.setText(display)
        self._update_menu_bar_for_app(title)

    def _update_menu_bar_for_app(self, app_title: str):
        """Rebuild all four dynamic menu buttons for app_title."""
        if not hasattr(self, "_dyn_menu_btns"):
            return
        spec = self._app_menu_spec(app_title)
        _SS = (
            "QMenu { background: #1a1b26; color: #c0caf5;"
            " border: 1px solid #414868; border-radius: 6px; }"
            "QMenu::item { padding: 6px 24px 6px 14px; font-size: 13px; }"
            "QMenu::item:selected { background: rgba(187,154,247,0.3); border-radius: 4px; }"
            "QMenu::separator { height: 1px; background: #414868; margin: 4px 8px; }"
        )
        for menu_name, btn in self._dyn_menu_btns.items():
            menu = QMenu(btn)
            menu.setStyleSheet(_SS)
            for item in spec.get(menu_name, []):
                if item is None:
                    menu.addSeparator()
                else:
                    label, cb = item
                    menu.addAction(label).triggered.connect(cb)
            btn.setMenu(menu)

    def _build_top_menu_bar(self):
        bar = QWidget()
        bar.setFixedHeight(26)
        bar.setStyleSheet(
            "background-color: rgba(26, 27, 38, 0.95); border-bottom: 1px solid #414868;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(0)

        # ── Active app name (hidden — kept for API compat) ─────────────────
        self._menu_app_label = QLabel("")
        self._menu_app_label.hide()

        # ── Relay indicator (left-anchored, where SIFTA OS label used to be)
        self._relay_indicator = QLabel("")
        self._relay_indicator.setFixedWidth(145)
        self._relay_indicator.setToolTip("Network mesh status.")
        self._relay_indicator.setStyleSheet(
            "color: #565f89; font-family: monospace; font-size: 11px; padding: 0 4px;"
        )
        layout.addWidget(self._relay_indicator)
        # Signal-driven now (Architect 00:14 fan-drop). No 2 s poll.
        if not hasattr(self, "_relay_timer"):
            self._relay_timer = QTimer(self)
            self._relay_timer.timeout.connect(self._update_relay_indicator)
        try:
            dm = getattr(self, "_desktop_mesh", None)
            if dm is not None:
                dm.connection_status.connect(lambda *_a: self._update_relay_indicator())
        except Exception:
            pass
        try:
            from System.swarm_behavior_clock import behavior_clock
            behavior_clock().tick.connect(lambda *_a: self._update_relay_indicator())
        except Exception:
            pass
        self._update_relay_indicator()

        _BTN_SS = (
            "QPushButton { color: #a9b1d6; background: transparent; border: none;"
            " padding: 0 10px; font-size: 13px; }"
            "QPushButton:hover, QPushButton:pressed { color: #ffffff;"
            " background: rgba(187,154,247,0.22); border-radius: 4px; }"
            "QPushButton::menu-indicator { width: 0; }"
        )

        # ── Four dynamic menu buttons ───────────────────────────────────────
        self._dyn_menu_btns = {}
        for name in ("File", "Edit", "View", "Window"):
            btn = QPushButton(name)
            btn.setStyleSheet(_BTN_SS)
            btn.setFixedHeight(22)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(btn)
            self._dyn_menu_btns[name] = btn

        # Populate with SIFTA OS defaults
        self._update_menu_bar_for_app("SIFTA OS")

        layout.addStretch(1)

        # ── Alice live status indicator ────────────────────────────────────
        self._alice_status_label = QLabel("")
        self._alice_status_label.setStyleSheet(
            "color: #9ece6a; font-size: 12px; font-weight: bold;"
            " background: transparent; padding: 0 12px;"
        )
        self._alice_status_label.setFixedHeight(22)
        layout.addWidget(self._alice_status_label)

        # ── Clock button ────────────────────────────────────────────────────
        self.clock_label = QPushButton()
        self.clock_label.setFlat(True)
        self.clock_label.setStyleSheet(
            "QPushButton { color: #c0caf5; font-size: 13px; font-weight: bold;"
            " background: transparent; border: none; outline: none; padding: 0 12px; }"
            "QPushButton:hover { color: #ffffff;"
            " background: rgba(187,154,247,0.22); border-radius: 4px; }"
            "QPushButton:focus { outline: none; border: none; }"
            "QPushButton::menu-indicator { width: 0; }"
        )
        self.clock_label.setFixedHeight(22)
        self.clock_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clock_label.clicked.connect(self._open_clock_settings)
        layout.addWidget(self.clock_label)

        return bar

    def _build_dock(self):
        self._ensure_manifest_cache_loaded()
        bar = QWidget()
        bar.setFixedHeight(96)
        bar.setStyleSheet("background: transparent;")

        outer = QHBoxLayout(bar)
        outer.setContentsMargins(0, 0, 0, 12)
        outer.addStretch(1)

        # ── Frosted glass pill ────────────────────────────────────────────
        pill = QFrame()
        pill.setStyleSheet("""
            QFrame {
                background: rgba(15, 16, 28, 0.82);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 20px;
            }
        """)
        pill_layout = QHBoxLayout(pill)
        pill_layout.setContentsMargins(16, 8, 16, 8)
        pill_layout.setSpacing(4)

        _BTN_SS = """
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 14px;
                font-size: 30px;
                padding: 4px;
                color: #c0caf5;
            }
            QPushButton:hover {
                background: rgba(187,154,247,0.18);
            }
            QPushButton:pressed {
                background: rgba(187,154,247,0.32);
            }
        """

        def make_dock_btn(emoji, name, callback):
            btn = QPushButton(emoji)
            btn.setFixedSize(56, 56)
            btn.setToolTip(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(_BTN_SS)
            btn.clicked.connect(lambda _checked=False, cb=callback: cb())
            pill_layout.addWidget(btn)

        # Architect 2026-05-13 11:40 — Spotlight removed from dock;
        # it duplicates the Launchpad's own search bar. The freed slot
        # is given to Alice Journal — her witness diary, which the
        # Architect explicitly wants visible at all times for the
        # "lobotomy recovery" use case.
        make_dock_btn("🚀", "Launchpad",     self._toggle_launchpad)
        make_dock_btn("📔", "Alice Journal", lambda: self._trigger_manifest_app("Alice Journal"))

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(32)
        sep.setStyleSheet("color: rgba(255,255,255,0.08);")
        pill_layout.addWidget(sep)

        # Pinned shortcuts use each app's manifest ``icon`` (unique per manifest row).
        # Architect 2026-05-13 11:20 — dock-hub list refreshed:
        #   • Alice removed: she is the always-on resident panel; clicking
        #     the dock icon launches nothing. Replaced with the Bell's
        #     Theorem stigmergic simulator so the dock surface shows
        #     research apps the owner actually opens.
        #   • WhatsApp Organ restored after Codex 2026-05-13 repair:
        #     owner-explicit UI sends can use WhatsApp.app visible-name search
        #     for contacts/groups while still writing SIFTA effector receipts.
        _dock_hub = ["Bell's Theorem — Classical Analogue",
                     "Finance", "Stigmerobotics",
                     "SIFTA Physics Observatory", "Alice Browser",
                     "WhatsApp Organ"]
        _cache = getattr(self, "_apps_manifest_cache", {}) or {}
        for _title in _dock_hub:
            if _title not in _cache:
                continue
            row = _cache[_title]
            emoji = str(row.get("icon") or row.get("emoji") or "◇").strip() or "◇"
            make_dock_btn(
                emoji,
                _title,
                lambda t=_title: self._trigger_manifest_app(t),
            )

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFixedHeight(32)
        sep2.setStyleSheet("color: rgba(255,255,255,0.08);")
        pill_layout.addWidget(sep2)

        _sso = (_cache.get("System Settings") or {}).get("icon") or (_cache.get("System Settings") or {}).get("emoji")
        make_dock_btn(
            str(_sso or "⚙️").strip() or "⚙️",
            "System Settings",
            lambda: self._trigger_manifest_app("System Settings"),
        )

        outer.addWidget(pill)
        outer.addStretch(1)
        return bar




# ──────────────────────────────────────────────────────────────
# BOOT
# ──────────────────────────────────────────────────────────────

# ── Global 2026 Dark Theme ────────────────────────────────────────────────────
# _GLOBAL_QSS is now generated dynamically from the active theme palette.
# This ensures Predator / Mermaid colors actually apply at boot.
# The hardcoded Mermaid stylesheet has been removed (it was overriding the theme engine).
def _get_global_qss() -> str:
    try:
        from System.sifta_desktop_themes import generate_global_qss
        return generate_global_qss()
    except Exception:
        return ""  # fallback: no style (Qt defaults)


_SCHEDULER_THROTTLE_THRESHOLD = 0.0
_SCHEDULER_ALLOCATOR_PID = "desktop_body_001"
_SCHEDULER_MAX_ALLOCATIONS_PER_TICK = 4
_SCHEDULER_MAX_SPEND_PER_TICK = 0.08
_SCHEDULER_MAX_SLICE_SPEND = 0.03
_ATTENTION_DIRECTOR_INTERVAL_MS = 3000
_KERNEL_MAINTENANCE_INTERVAL_S = {
    "engage": 12.0,
    "sample": 25.0,
    "idle": 60.0,
}
_KERNEL_ALLOCATION_INTERVAL_S = {
    "engage": 10.0,
    "sample": 20.0,
    "idle": 45.0,
}
_KERNEL_SAFETY_HEARTBEAT_INTERVAL_S = 180.0


def _floatish(value, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _scheduler_policy_from_kernel(kernel_table) -> tuple[str, float]:
    """Read the latest ambient context without waking the cortex."""
    try:
        from System.swarm_kernel_process_table import latest_ambient_world_context

        state_root = getattr(kernel_table, "state_root", _REPO / ".sifta_state")
        context = latest_ambient_world_context(state_root)
    except Exception:
        context = {}
    policy = str(context.get("sampling_policy") or "idle").strip().lower()
    if policy not in _KERNEL_MAINTENANCE_INTERVAL_S:
        policy = "idle"
    return policy, _floatish(context.get("salience_score"), default=0.0)


def _kernel_need_signal(policy: str, salience: float, pending_work: list[dict]) -> bool:
    """True when Alice has a reason to spend attention now."""
    return bool(pending_work) or policy == "engage" or float(salience) >= 0.55


def _qt_float_property(app: QApplication, name: str, *, default: float = 0.0) -> float:
    return _floatish(app.property(name), default=default)


def _repair_evidence_gain_from_metadata(metadata: dict) -> float:
    reason = str((metadata or {}).get("repair_reason") or "")
    if reason == "negative_stgm_contributor":
        return 0.35
    if reason == "missing_physical_grounding":
        return 0.28
    if reason == "not_alive":
        return 0.24
    return 0.18


def _pending_work_from_kernel(kernel_table) -> list[dict]:
    """Return lightweight pending tasks already visible in kernel receipts."""
    pending: list[dict] = []
    try:
        unhealthy = list(kernel_table.list_unhealthy())
    except Exception:
        unhealthy = []
    for proc in unhealthy:
        if getattr(proc, "pid", "") == "kernel:self_maintenance":
            continue
        metadata = dict(getattr(proc, "metadata", {}) or {})
        pending.append(
            {
                "pid": proc.pid,
                "type": metadata.get("repair_reason") or "repair",
                "evidence_gain": _repair_evidence_gain_from_metadata(metadata),
                "stgm_delta": _floatish(metadata.get("repair_budget_stgm"), default=0.01),
                "thermal": _floatish(metadata.get("thermal_cost"), default=0.0),
                "interrupt_risk": _floatish(metadata.get("interrupt_risk"), default=0.0),
                "requested_budget": _floatish(metadata.get("repair_budget_stgm"), default=0.01),
            }
        )
    try:
        extension_tasks = getattr(kernel_table, "pending_work", [])
    except Exception:
        extension_tasks = []
    if isinstance(extension_tasks, list):
        pending.extend(task for task in extension_tasks if isinstance(task, dict) and task.get("pid"))
    return pending


def _allocate_from_pending(
    kernel_table,
    pending_work: list[dict],
    *,
    allocator_pid: str = _SCHEDULER_ALLOCATOR_PID,
    threshold: float = _SCHEDULER_THROTTLE_THRESHOLD,
) -> dict | None:
    """Rank pending work by scheduler utility and receipt one budget slice."""
    allocations = _allocate_many_from_pending(
        kernel_table,
        pending_work,
        allocator_pid=allocator_pid,
        threshold=threshold,
        max_allocations=1,
    )
    return allocations[0] if allocations else None


def _allocate_many_from_pending(
    kernel_table,
    pending_work: list[dict],
    *,
    allocator_pid: str = _SCHEDULER_ALLOCATOR_PID,
    threshold: float = _SCHEDULER_THROTTLE_THRESHOLD,
    max_allocations: int = _SCHEDULER_MAX_ALLOCATIONS_PER_TICK,
    max_spend_per_tick: float = _SCHEDULER_MAX_SPEND_PER_TICK,
    max_slice_spend: float = _SCHEDULER_MAX_SLICE_SPEND,
) -> list[dict]:
    """Rank pending work and receipt several bounded budget slices."""
    scored: list[tuple[float, dict]] = []
    for task in pending_work:
        pid = str(task.get("pid") or "").strip()
        if not pid:
            continue
        score = kernel_table.scheduler_utility(
            pid,
            evidence_gain=_floatish(task.get("evidence_gain"), default=0.0),
            stgm_delta=_floatish(task.get("stgm_delta"), default=0.0),
            thermal=_floatish(task.get("thermal"), default=0.0),
            interrupt_risk=_floatish(task.get("interrupt_risk"), default=0.0),
        )
        scored.append((score, task))

    allocations: list[dict] = []
    seen_targets: set[str] = set()
    max_slices = max(0, int(max_allocations))
    total_spend_this_tick = 0.0
    spend_cap = max(0.0, float(max_spend_per_tick))
    slice_cap = max(0.0, float(max_slice_spend))
    for score, task in sorted(scored, key=lambda item: item[0], reverse=True):
        if len(allocations) >= max_slices:
            break
        if spend_cap <= 0.0 or slice_cap <= 0.0:
            break
        if score < threshold:
            continue
        target_pid = str(task.get("pid") or "").strip()
        if target_pid in seen_targets:
            continue
        requested = min(max(_floatish(task.get("requested_budget"), default=0.01), 0.0), slice_cap)
        if not target_pid or requested <= 0.0:
            continue
        if total_spend_this_tick + requested > spend_cap:
            break
        spend_pid = allocator_pid if kernel_table.get(allocator_pid) is not None else target_pid
        try:
            budget = kernel_table.sys_budget_state(spend_pid, requested_spend=requested)
        except AttributeError:
            budget = {"state": "ALLOW"}
        except Exception:
            continue
        budget_state = str(budget.get("state") or "")
        if budget_state == "BLOCK":
            continue
        if budget_state == "THROTTLE":
            requested = min(requested * 0.5, 0.025, slice_cap)
            if requested <= 0.0:
                continue
            if total_spend_this_tick + requested > spend_cap:
                break
        purpose = f"scheduled:{task.get('type') or 'pending'}:{target_pid}"
        try:
            rid = kernel_table.sys_spend(spend_pid, requested, purpose=purpose)
        except Exception:
            continue
        total_spend_this_tick += requested
        if target_pid != spend_pid and kernel_table.get(target_pid) is not None:
            kernel_table.heartbeat(
                target_pid,
                current_job=f"scheduled:{task.get('type') or 'pending'}",
                receipt_id=rid,
                metadata={
                    "scheduled_allocation_receipt_id": rid,
                    "scheduled_allocator_pid": spend_pid,
                    "scheduled_budget_stgm": f"{requested:.6f}",
                    "scheduled_score": f"{score:.6f}",
                    "scheduled_task_type": str(task.get("type") or "pending"),
                },
            )
        seen_targets.add(target_pid)
        allocations.append({
            "pid": target_pid,
            "allocator_pid": spend_pid,
            "receipt_id": rid,
            "score": score,
            "budget": requested,
            "type": str(task.get("type") or "pending"),
        })
    return allocations


def _install_kernel_scheduler_timer(
    app: QApplication,
    kernel_table,
    *,
    interval_ms: int = _ATTENTION_DIRECTOR_INTERVAL_MS,
    desktop_body=None,
) -> QTimer | None:
    """Run the kernel + attention director inside one Qt event-loop timer."""
    if kernel_table is None:
        return None
    scheduler_timer = QTimer(app)
    scheduler_timer.setObjectName("SIFTAKernelSchedulerTimer")
    scheduler_timer.setInterval(max(50, int(interval_ms)))

    def _kernel_scheduler_tick() -> None:
        try:
            now = time.time()
            policy, salience = _scheduler_policy_from_kernel(kernel_table)
            maintenance_interval = _KERNEL_MAINTENANCE_INTERVAL_S.get(policy, _KERNEL_MAINTENANCE_INTERVAL_S["idle"])
            allocation_interval = _KERNEL_ALLOCATION_INTERVAL_S.get(policy, _KERNEL_ALLOCATION_INTERVAL_S["idle"])
            pending_work = _pending_work_from_kernel(kernel_table)
            need_signal = _kernel_need_signal(policy, salience, pending_work)
            app.setProperty("sifta_kernel_scheduler_sampling_policy", policy)
            app.setProperty("sifta_kernel_scheduler_salience", round(salience, 3))
            app.setProperty("sifta_kernel_scheduler_need_signal", need_signal)
            app.setProperty("sifta_kernel_scheduler_pending_count", len(pending_work))

            last_maintenance_ts = _qt_float_property(
                app,
                "sifta_kernel_scheduler_last_maintenance_ts",
                default=0.0,
            )
            age_since_maintenance = now - last_maintenance_ts if last_maintenance_ts > 0.0 else _KERNEL_SAFETY_HEARTBEAT_INTERVAL_S
            safety_heartbeat_due = age_since_maintenance >= _KERNEL_SAFETY_HEARTBEAT_INTERVAL_S
            event_maintenance_due = need_signal and age_since_maintenance >= maintenance_interval
            maintenance_due = bool(safety_heartbeat_due or event_maintenance_due)
            actions = 0
            if maintenance_due:
                actions = kernel_table.self_maintenance_tick(max_actions=3)
                app.setProperty("sifta_kernel_scheduler_last_maintenance_ts", now)
                app.setProperty(
                    "sifta_kernel_scheduler_next_maintenance_ts",
                    now + (maintenance_interval if need_signal else _KERNEL_SAFETY_HEARTBEAT_INTERVAL_S),
                )
            app.setProperty("sifta_kernel_scheduler_last_actions", actions)
            app.setProperty("sifta_kernel_scheduler_maintenance_due", maintenance_due)
            app.setProperty("sifta_kernel_scheduler_safety_heartbeat_due", safety_heartbeat_due)
            if kernel_table.get("desktop_body_001") is not None:
                app.setProperty(
                    "sifta_kernel_scheduler_desktop_score",
                    kernel_table.scheduler_utility("desktop_body_001"),
                )

            last_allocation_ts = _qt_float_property(
                app,
                "sifta_kernel_scheduler_last_allocation_ts",
                default=0.0,
            )
            age_since_allocation = now - last_allocation_ts if last_allocation_ts > 0.0 else allocation_interval
            allocation_due = bool(pending_work and age_since_allocation >= allocation_interval)
            allocations = []
            if allocation_due:
                allocations = _allocate_many_from_pending(
                    kernel_table,
                    pending_work,
                    max_allocations=_SCHEDULER_MAX_ALLOCATIONS_PER_TICK,
                    max_spend_per_tick=_SCHEDULER_MAX_SPEND_PER_TICK,
                    max_slice_spend=_SCHEDULER_MAX_SLICE_SPEND,
                )
                app.setProperty("sifta_kernel_scheduler_last_allocation_ts", now)
                app.setProperty(
                    "sifta_kernel_scheduler_next_allocation_ts",
                    now + allocation_interval,
                )
            app.setProperty("sifta_kernel_scheduler_allocation_due", allocation_due)
            app.setProperty("sifta_kernel_scheduler_last_allocations", allocations)
            app.setProperty("sifta_kernel_scheduler_last_allocation", allocations[0] if allocations else None)
            app.setProperty(
                "sifta_kernel_scheduler_last_spend",
                round(sum(float(row.get("budget") or 0.0) for row in allocations), 6),
            )
            director_events = []
            if desktop_body is not None and hasattr(desktop_body, "_tick_biological_attention_director"):
                director_events = list(desktop_body._tick_biological_attention_director())
            app.setProperty("sifta_attention_director_last_events", director_events)
        except Exception as exc:
            sys.stderr.write(f"[BOOT] kernel scheduler tick skipped: {exc}\n")

    # Adaptive interval — Architect 00:14 fan-drop. When the kernel
    # reports policy='engage' or 'sample', the scheduler runs at the base
    # 3 s cadence (it has real pending work). When policy='idle' nobody
    # is asking for cycles, so we slow to 30 s — still well within the
    # 60 s idle-maintenance interval and the 180 s safety heartbeat.
    _IDLE_INTERVAL_MS = 30_000
    _ENGAGE_INTERVAL_MS = max(50, int(interval_ms))

    def _adapt_interval() -> None:
        try:
            policy, _ = _scheduler_policy_from_kernel(kernel_table)
        except Exception:
            policy = "idle"
        target = _IDLE_INTERVAL_MS if policy == "idle" else _ENGAGE_INTERVAL_MS
        if scheduler_timer.interval() != target:
            scheduler_timer.setInterval(target)
            app.setProperty("sifta_kernel_scheduler_interval_ms", target)

    def _kernel_scheduler_tick_with_adapt() -> None:
        _kernel_scheduler_tick()
        _adapt_interval()

    scheduler_timer.timeout.connect(_kernel_scheduler_tick_with_adapt)
    _adapt_interval()  # set the right interval *before* first start.
    scheduler_timer.start()
    app._sifta_kernel_scheduler_timer = scheduler_timer
    app.setProperty("sifta_kernel_scheduler_interval_ms", scheduler_timer.interval())
    app.setProperty("sifta_kernel_scheduler_last_maintenance_ts", 0.0)
    app.setProperty("sifta_kernel_scheduler_last_allocation_ts", 0.0)
    return scheduler_timer


if __name__ == "__main__":

    import os
    os.environ["QT_MEDIA_BACKEND"] = "darwin"
    # The desktop eye uses Qt/AVFoundation. Keep legacy cv2 webcam probes out of
    # this process to avoid duplicate FFmpeg AVFoundation Objective-C classes.
    os.environ.setdefault("SIFTA_DISABLE_CV2_IN_QT_DESKTOP", "1")

    # ── Boot banner — dynamic from theme engine + organ registry ──────
    try:
        from System.sifta_desktop_themes import active_palette
        from System.swarm_body_monitor import ORGAN_DEFS
        _pal = active_palette()
        _n_organs = len(ORGAN_DEFS)
        _n_swimmers = int(os.environ.get("SIFTA_VISION_SWIMMERS", "1800"))
        _n_photons = int(os.environ.get("SIFTA_DESKTOP_PHOTONS", "0"))
    except Exception:
        class _pal:
            os_line = "🐝 SIFTA BeeSon OS v8.0"
        # Dynamic fallback: count System/*.py organ modules
        try:
            _sys_dir = Path(__file__).resolve().parent / "System"
            _n_organs = len([f for f in _sys_dir.glob("*.py") if not f.name.startswith("__")])
        except Exception:
            _n_organs = 0
        _n_swimmers = 1800
        _n_photons = 0

    # Shell script already printed the full banner with live theme+organ data.
    # Python only emits the app path so crash logs are traceable.
    sys.stderr.write(f"  [BOOT] app    : {os.path.abspath(__file__)}\n")
    sys.stderr.flush()

    # ── Kernel process table — first accountable process in the macOS/PyQt body.
    kernel_table = None
    try:
        from System.swarm_kernel_process_table import OrganProcess, get_kernel_process_table

        kernel_table = get_kernel_process_table()
        kernel_table.register(
            OrganProcess(
                pid="desktop_body_001",
                organ_id="sifta_os_desktop",
                ring=1,
                health=1.0,
                stgm_balance=0.0,
                current_job="boot",
                last_receipt_id="",
                failure_count=0,
                last_heartbeat_ts=time.time(),
                location="desk",
                bodies_present=["george"],
                metadata={
                    "os_bone": "macOS/PyQt",
                    "principle": "Alice is the desktop body",
                },
            ),
            receipt_id="desktop_boot_kernel_register",
        )
        sys.stderr.write("  [BOOT] kernel : desktop_body_001 registered\n")
    except Exception as exc:
        sys.stderr.write(f"[BOOT] kernel process table skipped: {exc}\n")
    sys.stderr.flush()

    app = QApplication(sys.argv)
    if kernel_table is not None:
        app.setProperty("sifta_kernel_process_table", kernel_table)
    app.setApplicationName("SIFTA OS")

    _bee_pix = QPixmap(256, 256)
    _bee_pix.fill(QColor(0, 0, 0, 0))
    _bee_painter = QPainter(_bee_pix)
    _bee_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _bee_font = QFont("Apple Color Emoji", 200)
    _bee_painter.setFont(_bee_font)
    _bee_painter.drawText(_bee_pix.rect(), Qt.AlignmentFlag.AlignCenter, "\U0001f41d")
    _bee_painter.end()
    app.setWindowIcon(QIcon(_bee_pix))

    app.setFont(QFont("Helvetica Neue", 13))
    app.setStyleSheet(_get_global_qss())   # Predator / Mermaid from theme engine

    # ── BehaviorClock — Alice ticks on owner behavior, not on a fixed
    # millisecond grid. Architect 2026-05-11 23:50. Install global event
    # filter so every keypress / mouse / focus event becomes a tick;
    # link the wake-bus and app-focus signal so non-UI stimulus also
    # counts. Debounce is the Architect's own clinical heart period —
    # not a magic number.
    try:
        from System.swarm_behavior_clock import behavior_clock
        _clock = behavior_clock()
        _clock.attach_to_qapp(app)
        _clock.link_wake_bus()
        _clock.link_app_focus()
    except Exception as exc:
        sys.stderr.write(f"[BOOT] behavior_clock not installed: {exc}\n")

    # ── Owner unified field — STIGTIME + schedule + presence (Event 119+) ─
    try:
        from System.swarm_owner_unified_field_boot import anchor_owner_unified_field_on_boot

        _boot_anchor = anchor_owner_unified_field_on_boot()
        sys.stderr.write(
            f"  [BOOT] owner_unified_field trace={_boot_anchor.get('receipt_trace_id')}\n"
        )
    except Exception as exc:
        sys.stderr.write(f"[BOOT] owner_unified_field_boot skipped: {exc}\n")

    # ── Hot-Reload Organ (Epoch 4, C47H) — install once at boot. ─────────
    # After this, code patches to whitelisted modules can land via:
    #   python3 -m System.swarm_hot_reload reload all
    # without killing this process. State (history, mood, heartbeat) lives.
    # Architect mandate 2026-04-19: "WHY SHUT HER DOWN EVEN BRO, IT'S HER
    # HARDWARE." This is the structural answer to that mandate.
    try:
        from System.swarm_hot_reload import install_signal_handler as _hot_reload_install
        _hot_reload_install()
    except Exception as _hr_exc:
        sys.stderr.write(f"[BOOT] hot-reload install skipped: {_hr_exc}\n")

    desktop = SiftaDesktop()
    if kernel_table is not None:
        if _install_kernel_scheduler_timer(app, kernel_table, desktop_body=desktop) is not None:
            sys.stderr.write(
                f"  [BOOT] kernel : scheduler/attention director active @ {_ATTENTION_DIRECTOR_INTERVAL_MS}ms\n"
            )

    # ── Alice body autopilot (CC2F / C47H 2026-04-23) ───────────────────
    # Before camera/mic autostart windows open, ensure the iPhone GPS
    # bridge is listening so the first Shortcut ping lands. Writes
    # .sifta_state/alice_body_autopilot.json for composite_identity.
    def _alice_body_autopilot_kick() -> None:
        try:
            from System.alice_body_autopilot import ensure_autonomic_services

            ensure_autonomic_services(boot_channel="sifta_os_desktop")
        except Exception as _ap_exc:
            sys.stderr.write(f"[BOOT] alice_body_autopilot: {_ap_exc}\n")

    QTimer.singleShot(120, _alice_body_autopilot_kick)

    sys.exit(app.exec())
