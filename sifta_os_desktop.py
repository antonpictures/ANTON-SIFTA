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
from PyQt6.QtGui import QFont, QColor, QKeySequence, QShortcut

_REPO = Path(__file__).resolve().parent
_SYS = _REPO / "System"
_VENV_PYTHON = _REPO / ".venv" / "bin" / "python"
_PYTHON_BIN = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else (sys.executable or "python3")

# ── Swarm Intelligence Subsystems ────────────────────────────
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_SYS) not in sys.path:
    sys.path.insert(0, str(_SYS))

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
    try:
        widgets = [root, *root.findChildren(QWidget)]
    except RuntimeError:
        return
    seen: set[int] = set()
    for widget in widgets:
        marker = id(widget)
        if marker in seen:
            continue
        seen.add(marker)
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

    def moveEvent(self, event):
        if self._is_snapping:
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
        btn_close = QPushButton("✕  CLOSE")
        btn_close.setStyleSheet(
            "background-color: #f7768e; color: #15161e; font-weight: bold;"
            "border-radius: 4px; padding: 2px 8px;"
        )
        btn_close.clicked.connect(lambda: close_parent_subwindow(self))
        header.addWidget(btn_close)
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
        btn_close = QPushButton("✕  CLOSE")
        btn_close.setStyleSheet(
            "background-color: #f7768e; color: #15161e; font-weight: bold;"
            "border-radius: 4px; padding: 2px 8px;"
        )
        btn_close.clicked.connect(lambda: close_parent_subwindow(self))
        header.addWidget(btn_close)
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

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setStyleSheet(
            "QPushButton { background: #f7768e; color: #15161e; font-weight: bold; border-radius: 12px; }"
            "QPushButton:hover { background: #db4b4b; }"
        )
        btn_close.clicked.connect(lambda: close_parent_subwindow(self))
        toolbar.addWidget(btn_close)

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
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setStyleSheet(
            "QPushButton { background: #f7768e; color: #15161e; font-weight: bold; border-radius: 12px; }"
        )
        btn_close.clicked.connect(lambda: close_parent_subwindow(self))
        header.addWidget(btn_close)
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
        self.setBackground(QBrush(QColor("#0d0e17")))
        self._wallpaper_source = QPixmap()
        self._wallpaper_cache = QPixmap()
        self._wallpaper_cache_size = None
        
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
        _n_particles = int(_os.environ.get("SIFTA_DESKTOP_PHOTONS", "200"))
        
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
            
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)
        
        self.watermark_font = QFont("Helvetica Neue", 110, QFont.Weight.Black)
        self.watermark_sub = QFont("Courier New", 18, QFont.Weight.Bold)

    def set_wallpaper_pixmap(self, pixmap):
        self._wallpaper_source = pixmap if isinstance(pixmap, QPixmap) else QPixmap()
        self._wallpaper_cache = QPixmap()
        self._wallpaper_cache_size = None
        self.viewport().update()

    def _scaled_wallpaper(self, width, height):
        if self._wallpaper_source.isNull() or width <= 0 or height <= 0:
            return QPixmap()
        size_key = (int(width), int(height), self._wallpaper_source.cacheKey())
        if self._wallpaper_cache_size != size_key or self._wallpaper_cache.isNull():
            self._wallpaper_cache = self._wallpaper_source.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._wallpaper_cache_size = size_key
        return self._wallpaper_cache

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
                
            positions = np.array([[float(p[0]), float(p[1])] for p in self.particles], dtype=np.float32)
            
            memory_field = getattr(self, "_engine_memory", np.zeros((self.cfg.grid_size, self.cfg.grid_size), dtype=np.float32))
            memory_field *= 0.92
            for pos in positions:
                i, j = self.engine._idx(pos)
                memory_field[i, j] += 0.3
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
                
        else:
            for p in self.particles:
                p[0] += p[2]
                p[1] += p[3]
                if p[0] < 0: p[0] = w
                elif p[0] > w: p[0] = 0
                if p[1] < 0: p[1] = h
                elif p[1] > h: p[1] = 0
                
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = event.rect()
        w, h = self.viewport().width(), self.viewport().height()
        wallpaper = self._scaled_wallpaper(w, h)
        has_wallpaper = not wallpaper.isNull()
        if has_wallpaper:
            x = int((w - wallpaper.width()) / 2)
            y = int((h - wallpaper.height()) / 2)
            painter.drawPixmap(x, y, wallpaper)
            painter.fillRect(rect, QColor(3, 6, 12, 58))
        else:
            painter.fillRect(rect, QColor("#080a0f"))
        
        painter.setPen(QPen(QColor(120, 162, 247, 30), 1))
        for x in range(0, w, 40): painter.drawLine(x, 0, x, h)
        for y in range(0, h, 40): painter.drawLine(0, y, w, y)

        if not has_wallpaper:
            painter.setFont(self.watermark_font)
            painter.setPen(QColor(255, 255, 255, 18))
            painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter, "SIFTA")
            
            painter.setFont(self.watermark_sub)
            painter.setPen(QColor(255, 255, 255, 40))
            painter.drawText(0, h // 2 + 70, w, 30, Qt.AlignmentFlag.AlignCenter, "STIGMERGIC BIOLOGICAL SWARM")

        painter.setPen(Qt.PenStyle.NoPen)
        for p in self.particles:
            px = float(p[0] * w) if self.use_engine else float(p[0])
            py = float(p[1] * h) if self.use_engine else float(p[1])
            if 0 <= px <= w and 0 <= py <= h:
                c = QColor(125, 207, 255, 45) if p[4] > 5 else QColor(187, 154, 247, 40)
                painter.setBrush(c)
                painter.drawEllipse(QRectF(px, py, float(p[4]), float(p[4])))


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


# ── Launchpad / Spotlight (module-level widgets; defined before SiftaDesktop so
#    the module’s execution order matches import introspection and one source of truth.) ──


class LaunchpadWidget(QWidget):

    _TAB_BASE = (
        "QPushButton { background: rgba(36,40,59,0.7); color: #a9b1d6; "
        "border: 1px solid #414868; border-radius: 12px; "
        "padding: 4px 16px; font-size: 13px; font-weight: bold; }"
        "QPushButton:hover { background: rgba(187,154,247,0.25); color: #c0caf5; }"
    )
    _TAB_ACTIVE = (
        "QPushButton { background: rgba(187,154,247,0.45); color: #ffffff; "
        "border: 1px solid #bb9af7; border-radius: 12px; "
        "padding: 4px 16px; font-size: 13px; font-weight: bold; }"
    )

    def __init__(self, desktop):
        super().__init__(desktop)
        self.desktop = desktop
        self._active_cat = "All"
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(10, 10, 15, 0.92);")

        root = QVBoxLayout(self)
        root.setContentsMargins(50, 30, 50, 40)
        root.setSpacing(14)

        title = QLabel("Launchpad")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "color: #ffffff; font-size: 30px; font-weight: 700;"
            " font-family: 'Helvetica Neue', Helvetica, sans-serif;"
        )
        root.addWidget(title)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search apps")
        self.search_bar.setFixedWidth(420)
        self.search_bar.setStyleSheet(
            "QLineEdit { background: rgba(36, 40, 59, 0.86); color: #ffffff;"
            " border: 1px solid #414868; border-radius: 12px; padding: 10px 14px;"
            " font-size: 18px; }"
        )
        self.search_bar.textChanged.connect(lambda _text: self._rebuild_grid(self._active_cat))
        root.addWidget(self.search_bar, alignment=Qt.AlignmentFlag.AlignHCenter)
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc_shortcut.activated.connect(self.hide)

        # ── Category tab bar ──────────────────────────────────────────────
        tab_row = QHBoxLayout()
        tab_row.setSpacing(8)
        tab_row.addStretch()

        cats = ["All"] + sorted({
            _macos_app_category(name, dat)
            for name, dat in desktop._apps_manifest_cache.items()
        })

        self._tab_btns: dict[str, QPushButton] = {}
        for cat in cats:
            btn = QPushButton(cat)
            btn.setFixedHeight(26)
            btn.setStyleSheet(self._TAB_ACTIVE if cat == "All" else self._TAB_BASE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, c=cat: self._set_category(c))
            tab_row.addWidget(btn)
            self._tab_btns[cat] = btn

        tab_row.addStretch()
        root.addLayout(tab_row)

        # ── App list ──────────────────────────────────────────────────────
        self.grid_container = QWidget()
        self.grid_container.setAutoFillBackground(False)
        self.grid_container.setStyleSheet("background: transparent;")
        self.grid_layout = QVBoxLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 8, 0, 8)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid_container)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        scroll.viewport().setStyleSheet("background: transparent;")
        root.addWidget(scroll)

        self._app_buttons: list[tuple[str, str, QPushButton]] = []
        self._populate_grid()

    def _populate_grid(self):
        for name, dat in sorted(self.desktop._apps_manifest_cache.items()):
            cat = _macos_app_category(name, dat)
            icon = self._icon_for(name, cat)
            btn = QPushButton(f"{icon}  {name}    {cat}")
            btn.setMinimumHeight(44)
            btn.setMaximumWidth(760)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(10, 10, 15, 0.42);
                    color: #c0caf5;
                    font-size: 14px;
                    font-weight: 650;
                    border: 1px solid rgba(65, 72, 104, 0.72);
                    border-radius: 10px;
                    padding: 9px 14px;
                    text-align: left;
                }
                QPushButton:hover {
                    background: rgba(187,154,247,0.32);
                    border: 1px solid rgba(187,154,247,0.72);
                    color: #ffffff;
                }
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"{name} — {cat}")
            btn.clicked.connect(lambda _=False, n=name: self._launch(n))
            self._app_buttons.append((name, cat, btn))
        self._rebuild_grid("All")

    def _rebuild_grid(self, category: str):
        # Remove widgets from grid WITHOUT reparenting to None (that kills PyQt6 signals)
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
        query = self.search_bar.text().strip().casefold()
        for name, cat, btn in self._app_buttons:
            if category != "All" and cat != category:
                continue
            if query and query not in name.casefold():
                continue
            self.grid_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
            btn.show()
        self.grid_layout.addStretch(1)

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
        if "alice" in n:
            return "🧜‍♀️"
        if "conversation" in n or "chat" in n:
            return "💬"
        if "library" in n:
            return "📚"
        if "file" in n:
            return "📁"
        if "terminal" in n:
            return "👩‍💻"
        if "settings" in n or category == "System Settings":
            return "⚙️"
        if category == "Games":
            return "🎮"
        if category == "Creative":
            return "🎨"
        if category == "Network":
            return "🌐"
        if category == "Developer":
            return "🧰"
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
        layout.addWidget(self.list_widget)

    def _update_list(self):
        self.list_widget.clear()
        query = self.search_bar.text().strip().casefold()
        matches = []
        for name, dat in sorted(self.desktop._apps_manifest_cache.items()):
            category = _macos_app_category(name, dat)
            haystack = " ".join((name, category, dat.get("entry_point", ""))).casefold()
            if not query or query in haystack:
                matches.append((name, category))
        for name, category in matches[:12]:
            item = QListWidgetItem(f"{name}    {category}")
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
        self._apps_manifest_cache: dict[str, dict] = {}

        # Central layout
        central = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.mdi = SiftaMdiArea()
        self.mdi.subWindowActivated.connect(self._on_subwindow_activated)
        _desktop_init_trace("after SiftaMdiArea()")
        
        # ── Desktop Mesh Relay Client (Headless for Taskbar Status) ──
        self._mesh_connected = False
        if _sifta_env_mesh_disabled():
            self._desktop_mesh = None
        else:
            try:
                if str(_SYS) not in sys.path:
                    sys.path.insert(0, str(_SYS))
                from System.global_cognitive_interface import _SwarmMeshClientWorker, SWARM_RELAY_URI

                self._desktop_mesh = _SwarmMeshClientWorker(
                    uri=SWARM_RELAY_URI, architect_id="DESKTOP_HUD"
                )
                self._desktop_mesh.connection_status.connect(self._on_desktop_mesh_status)
                self._desktop_mesh.start()
            except Exception:
                self._desktop_mesh = None
        _desktop_init_trace("after mesh worker")

        main_layout.addWidget(self._build_top_menu_bar())
        main_layout.addWidget(self.mdi, 1)
        main_layout.addWidget(self._build_dock())

        central.setLayout(main_layout)
        self.setCentralWidget(central)
        _desktop_init_trace("after setCentralWidget()")
        
        # self._build_desktop_shortcuts() # Removed by Architect
        self._load_apps_manifest_and_autostart()
        _desktop_init_trace("after _load_apps_manifest_and_autostart()")

        # macOS-style overlays (not inside try/except — failures are visible in tests).
        self._spotlight = SpotlightWidget(self)
        _desktop_init_trace("after SpotlightWidget()")
        self._spotlight.hide()
        self._launchpad = LaunchpadWidget(self)
        _desktop_init_trace("after LaunchpadWidget()")
        self._launchpad.hide()
        _desktop_init_trace("after Launchpad/Spotlight widgets")

        # Clock now lives inside the top menu bar (see _build_top_menu_bar).
        # Swarm Economy HUD chrome (wallet/peer/economy_pulse) is no longer
        # mounted on the bar; the data path in _update_clock is gated on
        # hasattr(self, "wallet_label") and skips cleanly when absent.

        # Cache local serial exactly once for the HUD to avoid `ioreg` spam
        self._local_hw_serial = "UNKNOWN"
        try:
            if str(_SYS) not in sys.path:
                sys.path.insert(0, str(_SYS))
            from silicon_serial import read_apple_serial
            self._local_hw_serial = read_apple_serial()
        except Exception:
            pass

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
        self._wallpaper_timer = QTimer(self)
        self._wallpaper_timer.timeout.connect(self._maybe_reload_wallpaper)
        self._wallpaper_timer.start(2000)

        # Resident Alice attention policy. This does not touch camera hardware
        # directly; it leases the canonical eye target through
        # System.swarm_camera_target, with a reason row in
        # .sifta_state/sensory_attention_ledger.jsonl.
        self._attention_director_timer = QTimer(self)
        self._attention_director_timer.timeout.connect(self._tick_attention_director)
        self._attention_director_timer.start(2000)
        QTimer.singleShot(800, self._tick_attention_director)
        _desktop_init_trace("leave __init__")

    def _wallpaper_candidates(self):
        env_wp = os.environ.get("SIFTA_DESKTOP_WALLPAPER", "").strip()
        if env_wp:
            yield env_wp
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

        QMdiArea.setBackground(QBrush(QPixmap(...))) tiles the pixmap. That is
        why the live desktop looked like repeated panels instead of one macOS-like
        desktop surface. The MDI area now owns the single scaled/cropped paint.
        """
        try:
            from PyQt6.QtGui import QBrush, QColor, QPixmap

            state = self._selected_wallpaper_state()
            if not force and state == self._wallpaper_state:
                return
            self._wallpaper_state = state

            wp_path = state[0]
            if wp_path:
                pm = QPixmap(wp_path)
                if not pm.isNull():
                    self.mdi.setBackground(QBrush(QColor("#080a0f")))
                    if hasattr(self.mdi, "set_wallpaper_pixmap"):
                        self.mdi.set_wallpaper_pixmap(pm)
                    return
            if hasattr(self.mdi, "set_wallpaper_pixmap"):
                self.mdi.set_wallpaper_pixmap(QPixmap())
            self.mdi.setBackground(QBrush(QColor("#0a0a0f")))
        except Exception as exc:
            print(f"[SiftaDesktop] wallpaper reload failed: {exc}", file=sys.stderr)

    def _maybe_reload_wallpaper(self):
        self._apply_wallpaper(force=False)

    def _attention_director_enabled(self) -> bool:
        value = os.environ.get("SIFTA_DISABLE_ATTENTION_DIRECTOR", "").strip().lower()
        return value not in {"1", "true", "yes"}

    def _tick_attention_director(self) -> None:
        if not self._attention_director_enabled():
            return
        try:
            from System.swarm_sensor_attention_director import tick

            decision = tick(write_hardware=True)
            if hasattr(self, "_alice_status_label") and not self._alice_status_label.text():
                role = "room" if decision.target_role == "room_patrol_eye" else "near"
                self._alice_status_label.setText(f"👁  {role} eye")
                self._alice_status_label.setStyleSheet(
                    "color: #7dcfff; font-size: 12px; font-weight: bold;"
                    " background: transparent; padding: 0 12px;"
                )
        except Exception as exc:
            print(f"[SiftaDesktop] attention director tick failed: {exc}", file=sys.stderr)

    def closeEvent(self, event):
        if hasattr(self, "_attention_director_timer"):
            self._attention_director_timer.stop()
        if hasattr(self, "mdi"):
            for sub in list(self.mdi.subWindowList()):
                try:
                    sub.close()
                except RuntimeError:
                    pass
            QApplication.processEvents()
        if getattr(self, "_desktop_mesh", None) is not None:
            self._desktop_mesh.stop()
        super().closeEvent(event)

    def _on_desktop_mesh_status(self, status):
        self._mesh_connected = status

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
        """Poll Alice's vocal state every second and update the top-bar indicator."""
        if not hasattr(self, "_alice_status_label"):
            return
        try:
            import time as _time

            # 1) BROCA_SPEAKING → she is speaking right now
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

            # 2) Recent broca entry (< 4 s ago) → thinking / generating
            broca_log = _REPO / ".sifta_state" / "broca_vocalizations.jsonl"
            try:
                import json as _json
                with open(broca_log, "rb") as _f:
                    _f.seek(0, 2)
                    size = _f.tell()
                    _f.seek(max(0, size - 512))
                    last = _f.read().decode("utf-8", "replace").strip().split("\n")[-1]
                row = _json.loads(last)
                if now - row.get("ts", 0) < 4:
                    self._alice_status_label.setText("🧠  thinking…")
                    self._alice_status_label.setStyleSheet(
                        "color: #bb9af7; font-size: 12px; font-weight: bold;"
                        " background: transparent; padding: 0 12px;"
                    )
                    return
            except Exception:
                pass

            # 3) Recent wernicke entry (< 3 s ago) → listening / heard something
            wern_log = _REPO / ".sifta_state" / "wernicke_semantics.jsonl"
            try:
                with open(wern_log, "rb") as _f:
                    _f.seek(0, 2)
                    size = _f.tell()
                    _f.seek(max(0, size - 512))
                    last = _f.read().decode("utf-8", "replace").strip().split("\n")[-1]
                row = _json.loads(last)
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
        # Clock is layout-managed inside _build_top_menu_bar — no manual positioning needed.
        if hasattr(self, "mdi") and hasattr(self, "_wallpaper_state"):
            self._apply_wallpaper(force=True)


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
        creative = prog.addMenu("Creative ▶")
        sims = prog.addMenu("Simulations ▶")
        net  = prog.addMenu("Networking ▶")
        sys_menu = prog.addMenu("System ▶")

        # ── Core Built-in OS Apps ────────────────────────
        acc.addAction("🐜 Swarm Chat").triggered.connect(self.open_swarm_chat)
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

                    target_menu = acc
                    if cat == "Simulations":
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
                    target_menu.addAction(app_name).triggered.connect(launch)

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
        self._relay_indicator = QLabel("Mesh: Local mode")
        self._relay_indicator.setStyleSheet(
            "color: #565f89; font-family: monospace; font-size: 11px; padding: 0 8px;"
        )
        layout.addWidget(self._relay_indicator)

        # Heartbeat timer to check GCI mesh status
        self._relay_timer = QTimer(self)
        self._relay_timer.timeout.connect(self._update_relay_indicator)
        self._relay_timer.start(2000)

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
            self._relay_indicator.setText("●  Mesh: Local mode")
            self._relay_indicator.setStyleSheet(
                "color: #565f89; font-family: monospace; font-size: 11px; padding: 0 8px;"
            )
            return

        if self._desktop_mesh.isRunning() and self._mesh_connected:
            self._relay_indicator.setText("●  Mesh: Shared link")
            self._relay_indicator.setStyleSheet(
                "color: #9ece6a; font-family: monospace; font-size: 11px;"
                " font-weight: bold; padding: 0 8px;"
            )
        else:
            self._relay_indicator.setText("●  Mesh: Local mode")
            self._relay_indicator.setStyleSheet(
                "color: #565f89; font-family: monospace; font-size: 11px;"
                " font-weight: normal; padding: 0 8px;"
            )
    # ── Window factories ───────────────────────────────────
    def _make_sub(self, widget, title, w, h, border_color="#414868", x=None, y=None, key=None):
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
            | Qt.WindowType.WindowCloseButtonHint
        )
        # macOS Qt adds a "?" context-help button by default — kill it
        sub.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        # Use a custom dark title bar to avoid white native title strips on macOS.
        title_bar = QWidget()
        title_bar.setFixedHeight(28)
        title_bar.setStyleSheet(
            "background-color: #0f1118; border-bottom: 1px solid #2a2f3a;"
        )
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(8, 3, 8, 3)
        title_layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #c0caf5; font-weight: 600;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        # No custom close button here — the native window/title bar already
        # provides one (macOS traffic light or Qt MDI close). Drawing a second
        # red X confused users (Architect feedback 2026-04-24).
        
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
        sub.show()
        self._open_windows[slot_key] = sub
        sub.destroyed.connect(lambda _k=slot_key: self._open_windows.pop(_k, None))
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
        
        sub  = self._make_sub(chat, "🐜 SIFTA CORE CHAT", w, h, "#565f89", x=x, y=y, key="SIFTA CORE CHAT")
        self.active_chat_sub = sub
        sub.destroyed.connect(lambda _obj=None, _sub=sub: setattr(self, "active_chat_sub", None) if self.active_chat_sub is _sub else None)

    def open_video_editor(self):
        editor = VideoEditorSubWindow()
        self._make_sub(editor, "Aether Silence Remover & Stitcher", 750, 450, "#414868")

    def spawn_text_editor(self, filepath=None):
        name = os.path.basename(filepath) if filepath else "Untitled"
        self._make_sub(SwarmTextEditorWindow(filepath), f"SwarmText: {name}", 700, 500, "#bb9af7")

    def spawn_terminal(self, title, cmd, args):
        self._make_sub(TerminalSubWindow(cmd, args), title, 600, 400, "#9ece6a")

    def spawn_embedded_script(self, title, script_path):
        self._make_sub(EmbeddedScriptSubWindow(title, script_path), title, 860, 560, "#9ece6a")

    # ── Swarm-intelligent app launcher ───────────────────
    def _launch_app(self, title, module_path, class_name, w=660, h=540):
        """Launch an app: record fitness, WM pheromone, suggest position."""
        record_launch(title)
        wm_record_open(title)
        fs_record_access(module_path)

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
        self.spawn_native_widget(title, module_path, class_name, w=w, h=h, x=x, y=y)


    def _launch_terminal_app(self, title, entry):
        """Launch a script app inside iSwarm OS (no external popout intent)."""
        record_launch(title)
        wm_record_open(title)
        fs_record_access(entry)
        self.spawn_embedded_script(title, entry)

    def spawn_native_widget(self, title, module_path, class_name, w=660, h=540, x=None, y=None):
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
            sub = self._make_sub(widget, f"⚙ {title}", w, h, "#7aa2f7", x=x, y=y, key=title)
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
        if app_name in self._apps_manifest_cache:
            dat = self._apps_manifest_cache[app_name]
            self._launch_app(
                app_name,
                dat.get("entry_point"),
                dat.get("widget_class"),
                w=int(dat.get("window_width", 920)),
                h=int(dat.get("window_height", 640))
            )

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
            elif hasattr(self, "_launchpad") and self._launchpad.isVisible():
                self._launchpad.hide()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def _load_apps_manifest_and_autostart(self):
        import json

        manifest_path = _REPO / "Applications" / "apps_manifest.json"
        if not manifest_path.exists():
            return
        try:
            apps = json.loads(manifest_path.read_text(encoding="utf-8"))
            self._apps_manifest_cache = dict(apps)
        except Exception as exc:
            print(f"[Boot Error] Failed to load apps manifest: {exc}")
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
        if hasattr(self, "_launchpad"):
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
        if not hasattr(self, "_launchpad"):
            return
        if self._launchpad.isVisible():
            self._launchpad.hide()
            return
        if hasattr(self, "_spotlight"):
            self._spotlight.hide()
        surface = self.centralWidget() if self._launchpad.parentWidget() is self else (self._launchpad.parentWidget() or self)
        self._launchpad.setGeometry(surface.geometry() if surface is self.centralWidget() else surface.rect())
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
            "File": [
                ("Open Conversation History", lambda: self._trigger_manifest_app("Conversation History")),
                ("Open Stigmergic Library",   lambda: self._trigger_manifest_app("Stigmergic Library")),
                ("Open Terminal",             lambda: self._trigger_manifest_app("Terminal")),
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
                ("Alice Health", lambda: self._trigger_manifest_app("Biological Dashboard")),
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

    def _on_subwindow_activated(self, sub):
        """mdi.subWindowActivated — update app name label and menus."""
        if sub is None:
            display = "SIFTA OS"
            title   = "SIFTA OS"
        else:
            title   = sub.windowTitle()
            display = title.lstrip("⚙ 🐜").strip() or "SIFTA OS"
            if "SIFTA CORE CHAT" in title:
                display = "Swarm Chat"
            if len(display) > 26:
                display = display[:24] + "…"
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

        # ── Active app name (macOS style, bold purple) ─────────────────────
        self._menu_app_label = QLabel("SIFTA OS")
        self._menu_app_label.setStyleSheet(
            "color: #bb9af7; font-weight: bold; font-size: 13px; padding: 0 14px 0 4px;"
        )
        layout.addWidget(self._menu_app_label)

        # ── Relay indicator (dim) ───────────────────────────────────────────
        self._relay_indicator = QLabel("")
        self._relay_indicator.setFixedWidth(115)
        self._relay_indicator.setToolTip("Network mesh status.")
        self._relay_indicator.setStyleSheet(
            "color: #565f89; font-family: monospace; font-size: 11px; padding: 0 6px;"
        )
        layout.addWidget(self._relay_indicator)
        if not hasattr(self, "_relay_timer"):
            self._relay_timer = QTimer(self)
            self._relay_timer.timeout.connect(self._update_relay_indicator)
            self._relay_timer.start(2000)
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

        make_dock_btn("🚀", "Launchpad",         self._toggle_launchpad)
        make_dock_btn("🔍", "Spotlight",          self._toggle_spotlight)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(32)
        sep.setStyleSheet("color: rgba(255,255,255,0.08);")
        pill_layout.addWidget(sep)

        make_dock_btn("🧜‍♀️", "Alice",            lambda: self._trigger_manifest_app("Alice"))
        make_dock_btn("💓",  "Alice Health",       lambda: self._trigger_manifest_app("Biological Dashboard"))
        make_dock_btn("💬",  "Swarm Chat",         self.open_swarm_chat)
        make_dock_btn("📚",  "Stigmergic Library", lambda: self._trigger_manifest_app("Stigmergic Library"))
        make_dock_btn("🗣️", "Conversation",       lambda: self._trigger_manifest_app("Conversation History"))
        make_dock_btn("👩‍💻","Terminal",           lambda: self._trigger_manifest_app("Terminal"))

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFixedHeight(32)
        sep2.setStyleSheet("color: rgba(255,255,255,0.08);")
        pill_layout.addWidget(sep2)

        make_dock_btn("⚙️", "System Settings",    lambda: self._trigger_manifest_app("System Settings"))

        outer.addWidget(pill)
        outer.addStretch(1)
        return bar




# ──────────────────────────────────────────────────────────────
# BOOT
# ──────────────────────────────────────────────────────────────

# ── Global 2026 Dark Theme ────────────────────────────────────────────────────
_GLOBAL_QSS = """
QMainWindow, QDialog { background: #0d0e17; }
QWidget { font-family: "Helvetica Neue", -apple-system, sans-serif; font-size: 13px; color: #c0caf5; }
QMdiSubWindow { background: #13141f; border: 1px solid #2a2d3e; border-radius: 12px; }
QMdiSubWindow > QWidget { background: #13141f; }
QScrollBar:vertical { background: transparent; width: 5px; margin: 0; }
QScrollBar::handle:vertical { background: #3b4261; border-radius: 2px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #7aa2f7; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 5px; margin: 0; }
QScrollBar::handle:horizontal { background: #3b4261; border-radius: 2px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: #7aa2f7; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
QLineEdit { background: rgba(30,32,48,0.95); border: 1px solid #3b4261; border-radius: 8px; padding: 7px 12px; color: #c0caf5; selection-background-color: #3d59a1; }
QLineEdit:focus { border: 1px solid #7aa2f7; }
QTextEdit, QPlainTextEdit { background: rgba(19,20,31,0.95); border: 1px solid #2a2d3e; border-radius: 8px; padding: 8px; color: #c0caf5; selection-background-color: #3d59a1; }
QPushButton { background: rgba(59,66,97,0.5); border: 1px solid #3b4261; border-radius: 8px; color: #c0caf5; padding: 6px 16px; font-weight: 500; }
QPushButton:hover { background: rgba(187,154,247,0.22); border: 1px solid #bb9af7; color: #fff; }
QPushButton:pressed { background: rgba(187,154,247,0.38); }
QListWidget, QTreeWidget { background: rgba(19,20,31,0.9); border: 1px solid #2a2d3e; border-radius: 8px; color: #c0caf5; outline: none; }
QListWidget::item, QTreeWidget::item { padding: 6px 12px; border-radius: 6px; }
QListWidget::item:selected, QTreeWidget::item:selected { background: rgba(122,162,247,0.22); color: #7aa2f7; }
QListWidget::item:hover, QTreeWidget::item:hover { background: rgba(59,66,97,0.4); }
QTabWidget::pane { border: 1px solid #2a2d3e; border-radius: 8px; background: rgba(19,20,31,0.8); }
QTabBar::tab { background: transparent; color: #565f89; padding: 7px 16px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #7aa2f7; border-bottom: 2px solid #7aa2f7; }
QTabBar::tab:hover { color: #c0caf5; }
QLabel { color: #c0caf5; background: transparent; }
QComboBox { background: rgba(30,32,48,0.95); border: 1px solid #3b4261; border-radius: 8px; padding: 6px 12px; color: #c0caf5; }
QComboBox:hover { border: 1px solid #7aa2f7; }
QComboBox QAbstractItemView { background: #1e2030; border: 1px solid #3b4261; selection-background-color: rgba(122,162,247,0.22); }
QSlider::groove:horizontal { background: #2a2d3e; height: 4px; border-radius: 2px; }
QSlider::handle:horizontal { background: #7aa2f7; width: 14px; height: 14px; border-radius: 7px; margin: -5px 0; }
QSlider::sub-page:horizontal { background: #7aa2f7; border-radius: 2px; }
QCheckBox { color: #c0caf5; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #3b4261; border-radius: 4px; background: rgba(30,32,48,0.9); }
QCheckBox::indicator:checked { background: #7aa2f7; border: 1px solid #7aa2f7; }
QGroupBox { border: 1px solid #2a2d3e; border-radius: 8px; margin-top: 20px; padding-top: 12px; color: #565f89; font-size: 11px; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 8px; left: 12px; color: #565f89; }
QToolTip { background: #1e2030; border: 1px solid #3b4261; border-radius: 6px; color: #c0caf5; padding: 4px 8px; font-size: 12px; }
QMessageBox { background: #1a1b26; }
QProgressBar { background: rgba(30,32,48,0.8); border: 1px solid #2a2d3e; border-radius: 5px; text-align: center; color: #c0caf5; font-size: 11px; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7aa2f7,stop:1 #bb9af7); border-radius: 5px; }
QSplitter::handle { background: #2a2d3e; }
"""

if __name__ == "__main__":

    import os
    os.environ["QT_MEDIA_BACKEND"] = "darwin"
    app = QApplication(sys.argv)
    app.setFont(QFont("Helvetica Neue", 13))
    app.setStyleSheet(_GLOBAL_QSS)

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
