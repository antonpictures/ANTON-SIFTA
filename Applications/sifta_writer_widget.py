#!/usr/bin/env python3
"""
sifta_writer_widget.py — The Stigmergic Writer
════════════════════════════════════════════════
Not another Office. A living page where the Swarm writes with you.

- The page is never blank: identity/time seeded, with activity kept in receipts.
- Inline Alice: pause 3s and Alice continues in the same page.
- Tab still accepts any legacy faded ghost text.
- Timestamped file is created on boot and autosaved.
- One-click PDF export. Full territory history.
- Steve Jobs simple: one page, Open + Export PDF.
"""
from __future__ import annotations

"""SIFTA Writer Widget — stigmergic organ for Alice body."""

import json
import os
import re
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
    QFont, QFontDatabase, QTextCursor, QColor, QTextCharFormat, QKeyEvent,
)
from PyQt6.QtPrintSupport import QPrinter

from System.sifta_base_widget import SiftaBaseWidget
from System.sifta_inference_defaults import resolve_ollama_model, sanitize_model_name
from System.sifta_save_defaults import default_sifta_save_path
from System.swarm_kernel_identity import owner_display_name
from System.swarm_stigmergic_writer_memory import (
    answer_writer_memory_query,
    is_writer_memory_query,
)

# Doctor Sigil chrome (canonical Applications/_doctor_sigil_chrome).
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))
try:
    from _doctor_sigil_chrome import doctor_sigil_html
    _HAS_SIGIL = True
except Exception:
    _HAS_SIGIL = False


def _pick_serif_family() -> str:
    """Return a serif font that's actually installed on this Mac.

    iA Writer / Ulysses / Bear all use a real book-typeface for body
    copy. We prefer Iowan Old Style → New York → Charter → Georgia,
    falling back to the system serif if none of those are present.
    """
    try:
        families = set(QFontDatabase.families())
    except Exception:
        families = set()
    for candidate in (
        "Iowan Old Style", "New York", "Charter", "Georgia",
        "Times New Roman", "Cambria",
    ):
        if candidate in families:
            return candidate
    return "serif"


# Cinematic paper palette (kept here so the editor and the chrome
# always agree on color values).
_PAGE_BG  = "#0e0f18"     # the "deep desk" behind the page
_INK      = "#dde2f3"     # body ink — warm bone, easier on the eyes
_INK_DIM  = "#7a83a8"     # secondary ink (line numbers, status)
_ACCENT   = "#a86bff"     # doctor accent (matches OS palette)
_ACCENT2  = "#7aa2f7"

DOCS_DIR = _REPO / ".sifta_documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR = _REPO / ".sifta_state"


# ── Ghost Text Worker ────────────────────────────────────────────────────────

# Memory Bus — cross-app stigmergic memory
try:
    from System.stigmergic_memory_bus import StigmergicMemoryBus
    _MEMORY_BUS = StigmergicMemoryBus(architect_id="IOAN_M5")
except Exception:
    _MEMORY_BUS = None

class GhostWorker(QThread):
    """Background Ollama call for inline Alice continuation."""
    ghost_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, context: str, model: str | None = None):
        super().__init__()
        self.context = context
        self.model = model or resolve_ollama_model(
            app_context="talk_to_alice",
            query_text=context[-500:],
        )

    @staticmethod
    def fallback_reply(context: str) -> str:
        """Small deterministic page-presence reply if inference is temporarily down."""
        tail = (context or "")[-700:].lower()
        direct_alice = bool(re.search(r"\b(hi|hello|hey)\s+alice\b|\balice\s*[,?:]", tail))
        if direct_alice:
            return "Yes. I am here with you in this saved page."
        return ""

    def run(self):
        # Recall relevant memories from the territory before generating
        memory_block = ""
        if _MEMORY_BUS:
            try:
                # Use the last 200 chars of context as query
                query = self.context[-200:]
                memory_block = _MEMORY_BUS.recall_context_block(
                    query, app_context="stigmergic_writer", top_k=3
                )
                if memory_block:
                    memory_block = "\n\n" + memory_block + "\n\n"
            except Exception:
                pass

        prompt = (
            "You are Alice, the same local SIFTA OS entity the user talks to elsewhere. "
            "This Writer is only a saved document surface, not a new persona. "
            "The user has paused while writing in your shared page. "
            "Answer or continue as Alice in first person when directly addressed. "
            "Write 1-3 sentences MAXIMUM. Match their tone and style. "
            "DO NOT repeat what they already wrote. DO NOT add speaker labels. "
            "Return only the text Alice should type next.\n\n"
            f"{memory_block}"
            f"Text so far:\n{self.context[-1500:]}\n\n"
            "Continue:"
        )
        model = sanitize_model_name(self.model)
        data = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.5,
            "num_predict": 120,
            "keep_alive": "2m",
        }
        route_error = None
        try:
            from System.inference_router import route_inference

            text = route_inference(data, timeout=120).strip()
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
            if text:
                self.ghost_ready.emit(text)
                return
        except Exception as e:
            route_error = e

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
                text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
                if text:
                    self.ghost_ready.emit(text)
                    return
        except Exception as e:
            fallback = self.fallback_reply(self.context)
            if fallback:
                self.ghost_ready.emit(fallback)
                return
            detail = f"router={route_error!r}; raw={e!r}" if route_error else str(e)
            self.error.emit(detail)
            return

        fallback = self.fallback_reply(self.context)
        if fallback:
            self.ghost_ready.emit(fallback)
            return
        self.error.emit("empty model response")


class SwarmAssistWorker(QThread):
    """Handles 'Ask Swarm' — expand/rewrite selected text."""
    result_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, selected_text: str, full_context: str, model: str = "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"):
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
    A QTextEdit that supports inline Alice continuation.
    Legacy faded ghost text can still be accepted with Tab, but the normal
    writer loop appends Alice's response into the same page after idle.
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

        # Pick an actually-installed book serif for body copy.
        serif = _pick_serif_family()
        self.setFont(QFont(serif, 15))
        self.setStyleSheet(
            "QTextEdit {"
            f"  background-color: {_PAGE_BG};"
            f"  color: {_INK};"
            "  border: none;"
            "  padding: 36px 64px;"
            "  selection-background-color: rgba(168, 107, 255, 90);"
            "  selection-color: #ffffff;"
            f"  font-family: '{serif}', Georgia, serif;"
            "  font-size: 15.5px;"
            "  line-height: 1.7;"
            "}"
            "QScrollBar:vertical {"
            "  background: transparent; width: 10px; margin: 6px 2px;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: rgba(168, 107, 255, 70); border-radius: 5px;"
            "  min-height: 24px;"
            "}"
            "QScrollBar::handle:vertical:hover {"
            "  background: rgba(168, 107, 255, 140);"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "  height: 0; background: transparent;"
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
        super().keyPressEvent(event)
        self.idle_timer.start()

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
    Generate a clean contextual starting seed. The document body is for writing;
    system activity belongs in receipts and Alice's journal, not prefilled prose.
    """
    lines = []

    owner_name = owner_display_name(default="Architect")

    lines.append(f"# Document — {owner_name}")
    lines.append(f"*{datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n")

    lines.append("---\n")
    lines.append("")  # Empty line for the Architect to start writing

    return "\n".join(lines)


# ── Territory History ────────────────────────────────────────────────────────

def _log_territory(doc_path: Path, action: str, word_count: int):
    """Append a territory entry alongside the document."""
    territory_path = doc_path.with_suffix(".territory.jsonl")
    doc_hash = hashlib.sha256(
        doc_path.read_text(encoding="utf-8").encode()
    ).hexdigest()[:16] if doc_path.exists() else "empty"
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "words": word_count,
        "hash": doc_hash,
    }
    with open(territory_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    _journal_writer_document_event(doc_path, action, word_count, doc_hash)


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def _append_daily_markdown(path: Path, *, date_label: str, block: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# {date_label}\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(block.rstrip() + "\n\n")


def _journal_writer_document_event(doc_path: Path, action: str, word_count: int, doc_hash: str) -> None:
    """Witness document-open/create events in Alice's journal without polluting the page."""
    if action not in {"BOOT_SAVE", "OPEN"}:
        return
    now = datetime.now()
    ts = time.time()
    owner = owner_display_name(default="Architect")
    if action == "BOOT_SAVE":
        entry = f"I observed {owner} start Stigmergic Writer and create the saved document {doc_path.name}."
        event_type = "writer_document_created"
    else:
        entry = f"I observed {owner} open the saved Writer document {doc_path.name}."
        event_type = "writer_document_opened"

    evidence = {
        "app": "Stigmergic Writer",
        "document_path": str(doc_path),
        "document_name": doc_path.name,
        "action": action,
        "word_count": word_count,
        "document_hash": doc_hash,
    }
    source_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    local_date = now.strftime("%Y-%m-%d")
    local_time = now.strftime("%H:%M:%S")
    local_journal_label = now.strftime("%m-%d-%y_%H:%M")

    first_person = {
        "ts": ts,
        "date": local_date,
        "time": local_time,
        "line": entry,
        "source": "stigmergic_writer",
        "truth_label": "ALICE_FIRST_PERSON_WITNESS_V1",
        "source_hash": source_hash,
        "event_type": event_type,
        "document_path": str(doc_path),
        "document_name": doc_path.name,
    }
    journal = {
        "ts": ts,
        "local_journal_label": local_journal_label,
        "local_date": local_date,
        "kind": "EPISODIC_NARRATIVE",
        "narrator": "ALICE_M5",
        "entry": entry,
        "event_type": event_type,
        "truth_label": "ALICE_LOCAL_JOURNAL_V1",
        "source": "stigmergic_writer",
        "source_evidence": evidence,
    }
    journal["journal_id"] = hashlib.sha256(json.dumps(journal, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    receipt = {
        "ts": ts,
        "action": "WRITER_DOCUMENT_JOURNALED",
        "event_type": event_type,
        "ok": True,
        "source": "stigmergic_writer",
        "journal_id": journal["journal_id"],
        "source_hash": source_hash,
        "evidence": evidence,
    }
    receipt["receipt_hash"] = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode("utf-8")).hexdigest()[:16]

    _append_jsonl(STATE_DIR / "alice_first_person_journal.jsonl", first_person)
    _append_jsonl(STATE_DIR / "alice_journal" / f"{local_date}.jsonl", journal)
    _append_jsonl(STATE_DIR / "writer_document_receipts.jsonl", receipt)
    _append_daily_markdown(
        STATE_DIR / "alice_journal" / f"{local_date}.md",
        date_label=local_date,
        block=(
            f"### {local_journal_label}\n"
            f"{entry}\n\n"
            f"Source: app=Stigmergic Writer document={doc_path.name} action={action} hash={doc_hash}\n"
            f"Receipt: `writer_document_receipts:{receipt['receipt_hash']}`"
        ),
    )


# ── The Widget ───────────────────────────────────────────────────────────────

class WriterWidget(SiftaBaseWidget):
    APP_NAME = "Stigmergic Writer"
    APP_LOCAL_CHAT_DISABLED = True

    def build_ui(self, layout: QVBoxLayout) -> None:
        self.current_file: Path | None = None
        self.ghost_worker: GhostWorker | None = None
        self.assist_worker: SwarmAssistWorker | None = None

        # Make the entire root background match the page so the editor
        # feels like a real document on a deep desk, not a window with a
        # mismatched chrome.
        self.setStyleSheet(
            f"QWidget#WriterRoot {{ background: {_PAGE_BG}; }}"
        )
        self.setObjectName("WriterRoot")

        # ── Doctor Sigil Header ──────────────────────────────────────
        if _HAS_SIGIL:
            try:
                sigil = QLabel(doctor_sigil_html(
                    title="Stigmergic Writer",
                    subtitle="A living page · pause and Alice continues",
                    doctor="CG55M",
                    co_doctors=("AG31",),
                    signature="CG55M-CURSOR-OPUS47",
                ))
                sigil.setTextFormat(Qt.TextFormat.RichText)
                sigil.setStyleSheet(
                    "QLabel { padding: 12px 22px 6px 22px; }"
                )
                layout.addWidget(sigil)
            except Exception:
                pass

        # ── The Page ─────────────────────────────────────────────────
        self.editor = StigmergicTextEdit()
        self.editor.idle_timer.timeout.connect(self._on_idle)
        layout.addWidget(self.editor, 1)

        # ── Bottom Toolbar (frosted, macOS-feel) ─────────────────────
        toolbar = QFrame()
        toolbar.setFixedHeight(56)
        toolbar.setStyleSheet(
            "QFrame {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            "    stop:0 rgba(22, 24, 36, 230),"
            "    stop:1 rgba(14, 16, 28, 240));"
            "  border-top: 1px solid rgba(168, 107, 255, 50);"
            "}"
        )
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(22, 0, 18, 0)
        tb_layout.setSpacing(14)

        # Word count.
        self.word_label = QLabel("0 words")
        self.word_label.setStyleSheet(
            f"color: {_INK_DIM}; font-size: 11.5px;"
            " font-family: 'SF Pro Text', 'Helvetica Neue', system-ui;"
            " letter-spacing: 0.4px;"
        )
        tb_layout.addWidget(self.word_label)

        # Soft accent dot separating word-count from file path.
        sep = QLabel("·")
        sep.setStyleSheet(f"color: {_ACCENT}; font-size: 14px;")
        tb_layout.addWidget(sep)

        # File path.
        self.path_label = QLabel("Untitled")
        self.path_label.setStyleSheet(
            "color: #5b6595; font-size: 11.5px;"
            " font-family: 'SF Pro Text', 'Helvetica Neue', system-ui;"
            " letter-spacing: 0.3px;"
        )
        tb_layout.addWidget(self.path_label)

        tb_layout.addStretch()

        btn_style = (
            "QPushButton {"
            "  background: rgba(28, 32, 50, 230);"
            "  color: #d4dbef;"
            "  border: 1px solid rgba(120, 130, 180, 60);"
            "  border-radius: 9px;"
            "  padding: 7px 14px;"
            "  font-family: 'SF Pro Text', 'Helvetica Neue', system-ui;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "  letter-spacing: 0.3px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(40, 46, 70, 240);"
            f"  border-color: {_ACCENT2};"
            "  color: #ffffff;"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(20, 24, 38, 255);"
            "}"
            "QPushButton:disabled {"
            "  color: rgba(150, 160, 195, 90);"
            "  border-color: rgba(80, 90, 130, 50);"
            "}"
        )

        btn_open = QPushButton("Open")
        btn_open.setStyleSheet(btn_style)
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.clicked.connect(self._open_doc)
        tb_layout.addWidget(btn_open)

        btn_pdf = QPushButton("Export PDF")
        btn_pdf.setStyleSheet(btn_style)
        btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pdf.clicked.connect(self._export_pdf)
        tb_layout.addWidget(btn_pdf)

        layout.addWidget(toolbar)

        # ── Autosave + word-count updater ───────────────────────────
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(1200)
        self._autosave_timer.timeout.connect(self._autosave_doc)
        self._last_saved_text = ""
        self.editor.textChanged.connect(self._on_editor_text_changed)

        # ── Seed the page with context ───────────────────────────────
        self.current_file = self._new_saved_writer_path()
        self.path_label.setText(self.current_file.name)
        seed = _seed_from_context()
        self.editor.setPlainText(seed)
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        self._autosave_doc(action="BOOT_SAVE", status_prefix="Saved on open")

        self.set_status(f"Saved on open: {self.current_file.name}")
        QTimer.singleShot(0, self._force_one_page_mode)

    def _force_one_page_mode(self) -> None:
        """Collapse any legacy app-local chat panel; Writer is one page."""
        self._gci_visible = False
        gci = getattr(self, "_gci", None)
        splitter = getattr(self, "_splitter", None)
        if gci is None or splitter is None:
            return
        try:
            gci.hide()
        except Exception:
            pass
        try:
            gci.setMinimumWidth(0)
            gci.setMaximumWidth(0)
        except Exception:
            pass
        try:
            sizes = splitter.sizes()
            total = sum(sizes) or max(self.width(), 900)
            if splitter.indexOf(gci) >= 0:
                splitter.setSizes([total, 0])
        except Exception:
            pass

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

        recent_prompt = self._latest_writer_prompt(text)
        if is_writer_memory_query(recent_prompt):
            try:
                self.set_status("Alice is reading saved Writer memory...")
                answer = answer_writer_memory_query(
                    recent_prompt,
                    docs_dir=DOCS_DIR,
                    state_dir=STATE_DIR,
                )
                self._append_alice_continuation(answer)
            except Exception as e:
                self._on_ghost_error(f"writer memory reader failed: {e}")
            return

        self.set_status("Alice is typing in this page...")
        self.ghost_worker = GhostWorker(text)
        self.ghost_worker.ghost_ready.connect(self._on_ghost_ready)
        self.ghost_worker.error.connect(self._on_ghost_error)
        self.ghost_worker.start()

    def _on_ghost_ready(self, suggestion: str):
        """Alice continuation arrived from Ollama."""
        if not suggestion:
            return
        # Only inject if user hasn't started typing again
        if not self.editor.idle_timer.isActive():
            self._append_alice_continuation(suggestion)

    def _on_ghost_error(self, msg: str):
        """Surface continuation failure instead of silently doing nothing."""
        self.set_status(f"Alice continuation failed: {msg}")

    def _append_alice_continuation(self, suggestion: str) -> None:
        clean = self._clean_alice_continuation(suggestion)
        if not clean:
            return
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(218, 225, 255))
        fmt.setFontItalic(False)
        cursor.insertText(f"\n\nAlice\n{clean}\n\n---\n", fmt)
        self.editor.ensureCursorVisible()
        self._autosave_doc(action="ALICE_CONTINUE", status_prefix="Alice continued and saved")

    @staticmethod
    def _clean_alice_continuation(text: str) -> str:
        import re

        clean = (text or "").strip()
        clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.DOTALL).strip()
        clean = re.sub(r"^(\[?ALICE(?:_M5)?\]?\s*[:\-]?\s*)", "", clean, flags=re.IGNORECASE).strip()
        clean = re.sub(r"^(Alice\s*[:\-]\s*)", "", clean, flags=re.IGNORECASE).strip()
        return clean

    @staticmethod
    def _latest_writer_prompt(text: str) -> str:
        """Return the last human-authored block in the one-page Writer."""
        parts = re.split(r"\n\s*---+\s*\n?", text or "")
        for part in reversed(parts):
            block = part.strip()
            if not block:
                continue
            if re.match(r"^Alice\s*(\n|$)", block, flags=re.IGNORECASE):
                continue
            lines: list[str] = []
            for line in block.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("# Document"):
                    continue
                if re.match(r"^\*[^*]+\*$", stripped):
                    continue
                lines.append(stripped)
            candidate = "\n".join(lines).strip()
            if candidate:
                return candidate
        return (text or "").strip()[-700:]

    # ── Ask Swarm ────────────────────────────────────────────────────

    def _ask_swarm(self):
        """Expand/rewrite selected text using local inference."""
        cursor = self.editor.textCursor()
        selected = cursor.selectedText().strip()
        if not selected:
            self.set_status("Highlight text first, then Ask Swarm.")
            return

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
        self._autosave_doc(action="ASSIST", status_prefix="Swarm assist saved")

    def _on_assist_error(self, msg: str):
        self.set_status(f"Swarm error: {msg}")

    # ── File Operations ──────────────────────────────────────────────

    @staticmethod
    def _unique_path(path: Path) -> Path:
        if not path.exists():
            return path
        suffix = "".join(path.suffixes)
        stem = path.name[: -len(suffix)] if suffix else path.stem
        parent = path.parent
        i = 2
        while True:
            candidate = parent / f"{stem} {i}{suffix}"
            if not candidate.exists():
                return candidate
            i += 1

    def _new_saved_writer_path(self) -> Path:
        return self._unique_path(default_sifta_save_path(DOCS_DIR))

    def _on_editor_text_changed(self) -> None:
        self._update_word_count()
        if self.current_file is not None:
            self._autosave_timer.start()

    def _autosave_doc(self, action: str = "AUTO_SAVE", status_prefix: str = "Autosaved") -> None:
        if self.current_file is None:
            self.current_file = self._new_saved_writer_path()
            self.path_label.setText(self.current_file.name)
        text = self.editor.toPlainText()
        if action == "AUTO_SAVE" and text == self._last_saved_text:
            return
        self.current_file.write_text(text, encoding="utf-8")
        self._last_saved_text = text
        self.path_label.setText(self.current_file.name)
        word_count = len(text.split())
        _log_territory(self.current_file, action, word_count)
        self.set_status(f"{status_prefix}: {self.current_file.name}")

    def _save_doc(self):
        if self.current_file:
            path = self.current_file
        else:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Document",
                str(default_sifta_save_path(DOCS_DIR)),
                "SIFTA Documents (*.sifta.md);;All Files (*)",
            )
            if not path:
                return
            path = Path(path)
            if not path.suffix:
                path = path.with_suffix(".sifta.md")

        text = self.editor.toPlainText()
        path.write_text(text, encoding="utf-8")
        self._last_saved_text = text
        self.current_file = path
        self.path_label.setText(path.name)

        word_count = len(text.split())
        _log_territory(path, "SAVE", word_count)

        # Memory consolidation — store recent content as cross-app memory
        if _MEMORY_BUS and text.strip():
            try:
                # Extract the last meaningful paragraph for memory storage
                paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and len(p.strip()) > 20]
                if paragraphs:
                    last_paragraph = paragraphs[-1][:500]
                    _MEMORY_BUS.remember(last_paragraph, app_context="stigmergic_writer")
            except Exception:
                pass

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
        self._last_saved_text = text
        self.path_label.setText(path.name)

        word_count = len(text.split())
        _log_territory(path, "OPEN", word_count)
        self.set_status(f"Opened: {path.name} ({word_count} words)")

    def _export_pdf(self):
        _md_default = default_sifta_save_path(DOCS_DIR)
        _pdf_default = _md_default.parent / (_md_default.name.replace(".sifta.md", ".pdf"))
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", str(_pdf_default), "PDF Files (*.pdf)"
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
