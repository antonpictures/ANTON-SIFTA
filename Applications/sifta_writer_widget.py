#!/usr/bin/env python3
"""
sifta_writer_widget.py — The Stigmergic Writer
════════════════════════════════════════════════
Not another Office. A living page where the Swarm writes with you.

- The page is never blank: context-seeded from Architect activity.
- Ghost text: pause 3s and the Swarm suggests a continuation.
- Tab to accept, keep typing to dismiss.
- One-click PDF export. Full territory history.
- Steve Jobs simple: one page, four buttons.
"""
from __future__ import annotations

import json
import os
import sys
import time
import hashlib
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "System") not in sys.path:
    sys.path.insert(0, str(_REPO / "System"))

from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QWidget, QFileDialog, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import (
    QFont, QTextCursor, QColor, QTextCharFormat, QKeyEvent,
)
from PyQt6.QtPrintSupport import QPrinter

from System.sifta_base_widget import SiftaBaseWidget

DOCS_DIR = _REPO / ".sifta_documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


# ── Ghost Text Worker ────────────────────────────────────────────────────────

class GhostWorker(QThread):
    """Background Ollama call for ghost-text continuation."""
    ghost_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, context: str, model: str = "gemma4:latest"):
        super().__init__()
        self.context = context
        self.model = model

    def run(self):
        prompt = (
            "You are a writing assistant inside a desktop text editor. "
            "The user has paused while writing. Continue their text naturally. "
            "Write 1-3 sentences MAXIMUM. Match their tone and style. "
            "DO NOT repeat what they already wrote. DO NOT use quotes or explain yourself. "
            "Just continue the text directly.\n\n"
            f"Text so far:\n{self.context[-1500:]}\n\n"
            "Continue:"
        )
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.5,
            "num_predict": 120,
            "keep_alive": "2m",
        }
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                text = result.get("response", "").strip()
                # Strip think blocks
                import re
                text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
                if text:
                    self.ghost_ready.emit(text)
        except Exception as e:
            self.error.emit(str(e))


class SwarmAssistWorker(QThread):
    """Handles 'Ask Swarm' — expand/rewrite selected text."""
    result_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, selected_text: str, full_context: str, model: str = "gemma4:latest"):
        super().__init__()
        self.selected_text = selected_text
        self.full_context = full_context
        self.model = model

    def run(self):
        prompt = (
            "You are a writing assistant. The user has highlighted text they want improved. "
            "Rewrite and expand the highlighted text to be more detailed, clear, and professional. "
            "Keep the same intent. Return ONLY the improved text, nothing else.\n\n"
            f"Full document context:\n{self.full_context[-2000:]}\n\n"
            f"Highlighted text to improve:\n{self.selected_text}\n\n"
            "Improved version:"
        )
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.4,
            "num_predict": 512,
            "keep_alive": "2m",
        }
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                text = result.get("response", "").strip()
                import re
                text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
                if text:
                    self.result_ready.emit(text)
                    # Mint STGM
                    try:
                        from inference_economy import mint_reward
                        mint_reward(
                            agent_id="M5SIFTA_BODY",
                            action="WRITER_ASSIST",
                            file_repaired="Applications/sifta_writer_widget.py",
                            model=self.model,
                        )
                    except Exception:
                        pass
        except Exception as e:
            self.error.emit(str(e))


# ── The Living Page ──────────────────────────────────────────────────────────

class StigmergicTextEdit(QTextEdit):
    """
    A QTextEdit that supports ghost-text suggestions.
    Ghost text appears in faded gray when you stop typing for 3 seconds.
    Press Tab to accept. Any other key dismisses it.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ghost_text = ""
        self.ghost_start_pos = -1
        self.has_ghost = False

        # Idle timer — fires 3 seconds after last keystroke
        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.setInterval(3000)

        self.setFont(QFont("Inter", 15))
        self.setStyleSheet(
            "QTextEdit {"
            "  background-color: #0a0b14;"
            "  color: #c8d0f0;"
            "  border: none;"
            "  padding: 30px 50px;"
            "  selection-background-color: #1e3a5f;"
            "}"
        )
        self.setAcceptRichText(True)

    def keyPressEvent(self, event: QKeyEvent):
        # Tab accepts ghost text
        if event.key() == Qt.Key.Key_Tab and self.has_ghost:
            self._accept_ghost()
            return

        # Any other key dismisses ghost text
        if self.has_ghost:
            self._dismiss_ghost()

        # Reset idle timer on every keystroke
        self.idle_timer.stop()
        self.idle_timer.start()

        super().keyPressEvent(event)

    def inject_ghost(self, text: str):
        """Insert ghost text at current cursor in faded gray."""
        self._dismiss_ghost()  # Clear any previous ghost

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.ghost_start_pos = cursor.position()

        # Insert with faded formatting
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(100, 110, 140, 120))
        fmt.setFontItalic(True)
        cursor.insertText(text, fmt)
        self.ghost_text = text
        self.has_ghost = True

    def _accept_ghost(self):
        """Convert ghost text to real text."""
        if not self.has_ghost:
            return
        cursor = self.textCursor()
        cursor.setPosition(self.ghost_start_pos)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        # Re-insert with normal formatting
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(200, 210, 240))
        fmt.setFontItalic(False)
        cursor.insertText(self.ghost_text, fmt)
        self.has_ghost = False
        self.ghost_text = ""
        self.ghost_start_pos = -1

    def _dismiss_ghost(self):
        """Remove ghost text entirely."""
        if not self.has_ghost:
            return
        cursor = self.textCursor()
        cursor.setPosition(self.ghost_start_pos)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        self.has_ghost = False
        self.ghost_text = ""
        self.ghost_start_pos = -1


# ── Context Seeding ──────────────────────────────────────────────────────────

def _seed_from_context() -> str:
    """
    Read recent Architect activity and generate a contextual starting seed.
    The page is never blank.
    """
    lines = []

    # Owner name
    genesis_path = _REPO / ".sifta_state" / "owner_genesis.json"
    owner_name = "Architect"
    if genesis_path.exists():
        try:
            genesis = json.loads(genesis_path.read_text())
            owner_name = genesis.get("owner_name", "Architect")
        except Exception:
            pass

    lines.append(f"# Document — {owner_name}")
    lines.append(f"*{datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n")

    # Recent ledger activity (last 3 events)
    ledger_path = _REPO / "repair_log.jsonl"
    if ledger_path.exists():
        try:
            recent = []
            with open(ledger_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        recent.append(line)
            if recent:
                last_events = recent[-3:]
                lines.append("**Recent Swarm Activity:**")
                for entry_str in last_events:
                    try:
                        entry = json.loads(entry_str)
                        event = entry.get("event", entry.get("action", "activity"))
                        agent = entry.get("miner_id", entry.get("agent", "swarm"))
                        lines.append(f"- {agent}: {event}")
                    except Exception:
                        pass
                lines.append("")
        except Exception:
            pass

    lines.append("---\n")
    lines.append("")  # Empty line for the Architect to start writing

    return "\n".join(lines)


# ── Territory History ────────────────────────────────────────────────────────

def _log_territory(doc_path: Path, action: str, word_count: int):
    """Append a territory entry alongside the document."""
    territory_path = doc_path.with_suffix(".territory.jsonl")
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "words": word_count,
        "hash": hashlib.sha256(
            doc_path.read_text(encoding="utf-8").encode()
        ).hexdigest()[:16] if doc_path.exists() else "empty",
    }
    with open(territory_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── The Widget ───────────────────────────────────────────────────────────────

class WriterWidget(SiftaBaseWidget):
    APP_NAME = "Stigmergic Writer"

    def build_ui(self, layout: QVBoxLayout) -> None:
        self.current_file: Path | None = None
        self.ghost_worker: GhostWorker | None = None
        self.assist_worker: SwarmAssistWorker | None = None

        # ── The Page ─────────────────────────────────────────────────
        self.editor = StigmergicTextEdit()
        self.editor.idle_timer.timeout.connect(self._on_idle)
        layout.addWidget(self.editor, 1)

        # ── Bottom Toolbar ───────────────────────────────────────────
        toolbar = QFrame()
        toolbar.setFixedHeight(52)
        toolbar.setStyleSheet(
            "QFrame { background: #12131e; border-top: 1px solid #1f2335; }"
        )
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(15, 0, 15, 0)

        # Word count
        self.word_label = QLabel("0 words")
        self.word_label.setStyleSheet("color: #565f89; font-size: 11px;")
        tb_layout.addWidget(self.word_label)

        # File path
        self.path_label = QLabel("Untitled")
        self.path_label.setStyleSheet("color: #414868; font-size: 11px;")
        tb_layout.addWidget(self.path_label)

        tb_layout.addStretch()

        btn_style = (
            "QPushButton {"
            "  background: #1a1b26; color: #c0caf5; border: 1px solid #24283b;"
            "  border-radius: 6px; padding: 6px 16px; font-size: 12px; font-weight: bold;"
            "}"
            "QPushButton:hover { background: #24283b; border-color: #7aa2f7; }"
            "QPushButton:disabled { color: #414868; }"
        )

        btn_open = QPushButton("📂 Open")
        btn_open.setStyleSheet(btn_style)
        btn_open.clicked.connect(self._open_doc)
        tb_layout.addWidget(btn_open)

        btn_save = QPushButton("💾 Save")
        btn_save.setStyleSheet(btn_style)
        btn_save.clicked.connect(self._save_doc)
        tb_layout.addWidget(btn_save)

        self.btn_swarm = QPushButton("🧠 Ask Swarm")
        self.btn_swarm.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #7c3aed, stop:1 #5b21b6);"
            "  color: white; border: none; border-radius: 6px; padding: 6px 16px;"
            "  font-size: 12px; font-weight: bold;"
            "}"
            "QPushButton:hover { background: #8b5cf6; }"
            "QPushButton:disabled { background: #374151; color: #9ca3af; }"
        )
        self.btn_swarm.clicked.connect(self._ask_swarm)
        tb_layout.addWidget(self.btn_swarm)

        btn_pdf = QPushButton("📄 Export PDF")
        btn_pdf.setStyleSheet(btn_style)
        btn_pdf.clicked.connect(self._export_pdf)
        tb_layout.addWidget(btn_pdf)

        layout.addWidget(toolbar)

        # ── Word count updater ───────────────────────────────────────
        self.editor.textChanged.connect(self._update_word_count)

        # ── Seed the page with context ───────────────────────────────
        seed = _seed_from_context()
        self.editor.setPlainText(seed)
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)

        self.set_status("Territory is the Law. The page remembers everything.")

    # ── Ghost Text ───────────────────────────────────────────────────

    def _on_idle(self):
        """Fired 3 seconds after last keystroke."""
        if self.editor.has_ghost:
            return
        text = self.editor.toPlainText().strip()
        if len(text) < 20:
            return  # Not enough context yet

        if self.ghost_worker and self.ghost_worker.isRunning():
            return

        self.ghost_worker = GhostWorker(text)
        self.ghost_worker.ghost_ready.connect(self._on_ghost_ready)
        self.ghost_worker.start()

    def _on_ghost_ready(self, suggestion: str):
        """Ghost text arrived from Ollama."""
        if not suggestion:
            return
        # Only inject if user hasn't started typing again
        if not self.editor.idle_timer.isActive():
            self.editor.inject_ghost(" " + suggestion)

    # ── Ask Swarm ────────────────────────────────────────────────────

    def _ask_swarm(self):
        """Expand/rewrite selected text using local inference."""
        cursor = self.editor.textCursor()
        selected = cursor.selectedText().strip()
        if not selected:
            self.set_status("Highlight text first, then Ask Swarm.")
            return

        self.btn_swarm.setEnabled(False)
        self.set_status("🧠 Swarm is thinking...")

        full_text = self.editor.toPlainText()
        self.assist_worker = SwarmAssistWorker(selected, full_text)
        self.assist_worker.result_ready.connect(self._on_assist_ready)
        self.assist_worker.error.connect(self._on_assist_error)
        self.assist_worker.start()

    def _on_assist_ready(self, improved: str):
        """Replace selection with Swarm's improved version."""
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            cursor.insertText(improved)
        else:
            # Selection was lost — append at end
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText("\n\n" + improved)
        self.btn_swarm.setEnabled(True)
        self.set_status("✅ Swarm assist complete. STGM minted.")

    def _on_assist_error(self, msg: str):
        self.btn_swarm.setEnabled(True)
        self.set_status(f"Swarm error: {msg}")

    # ── File Operations ──────────────────────────────────────────────

    def _save_doc(self):
        if self.current_file:
            path = self.current_file
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Document", str(DOCS_DIR),
                "SIFTA Documents (*.sifta.md);;All Files (*)"
            )
            if not path:
                return
            path = Path(path)
            if not path.suffix:
                path = path.with_suffix(".sifta.md")

        text = self.editor.toPlainText()
        path.write_text(text, encoding="utf-8")
        self.current_file = path
        self.path_label.setText(path.name)

        word_count = len(text.split())
        _log_territory(path, "SAVE", word_count)
        self.set_status(f"Saved: {path.name} ({word_count} words)")

    def _open_doc(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Document", str(DOCS_DIR),
            "SIFTA Documents (*.sifta.md);;Markdown (*.md);;All Files (*)"
        )
        if not path:
            return
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        self.editor.setPlainText(text)
        self.current_file = path
        self.path_label.setText(path.name)

        word_count = len(text.split())
        _log_territory(path, "OPEN", word_count)
        self.set_status(f"Opened: {path.name} ({word_count} words)")

    def _export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", str(DOCS_DIR / "export.pdf"),
            "PDF Files (*.pdf)"
        )
        if not path:
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        self.editor.document().print(printer)
        self.set_status(f"📄 PDF exported: {Path(path).name}")

    # ── Utilities ────────────────────────────────────────────────────

    def _update_word_count(self):
        text = self.editor.toPlainText()
        count = len(text.split()) if text.strip() else 0
        self.word_label.setText(f"{count} words")


# ── Standalone ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = WriterWidget()
    w.resize(1100, 850)
    w.setWindowTitle("Stigmergic Writer — SIFTA OS")
    w.show()
    sys.exit(app.exec())
