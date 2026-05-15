#!/usr/bin/env python3
"""sifta_stigmergic_mammal_canvas.py — animated MAMMAL field surface.

Architect 2026-05-13 spec (verbatim):
    LEFT   — live typed-token stream (PROTEIN / SM / GE / AB / SCALAR /
             TOKEN_ATTR / TIME_TAG)
    CENTER — 2D field with swimmers moving, token clusters glowing,
             contradiction storms, binding trails, memory wells
    RIGHT  — receipts: HYPOTHESIS / CONTRADICTION / LOW_CONFIDENCE /
             REPLAY_REINFORCED / TOXICITY_CLUSTER

Companion to `sifta_stigmergic_mammal_widget.py` (Codex's text-pane
verify+run-once view). Same architectural goal, different surface:
this version uses a live matplotlib canvas + 8 Hz timer for animated
swimmer motion and visible token mortality.

Backend: System.swarm_mammal_token_field (27/27 tests green) —
MammalTokenField + 7 swimmer species + token metabolism + sha256
receipts.

MAMMAL backend: System.swarm_mammal_organ (weights present,
snapshot 6d319d8d…). The "Query MAMMAL" path spawns the user's
prompt as a typed token with the model's embedding head as a
SCALAR_ATTR.

Truth class: OPERATIONAL for the simulation; HYPOTHESIS for any
biomedical receipt the swimmers emit. §20.F ceiling enforced.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget
from System.swarm_mammal_organ import MammalOrgan
from System.swarm_mammal_token_field import (
    MammalTokenField,
    ReceiptRow,
    RK_CONTRADICTION,
    RK_HYPOTHESIS,
    RK_LOW_CONFIDENCE,
    RK_REPLAY_REINFORCED,
    RK_TOXICITY_CLUSTER,
    TT_ANTIBODY,
    TT_GENE_EXPRESSION,
    TT_PROTEIN,
    TT_SCALAR_ATTR,
    TT_SMALL_MOLECULE,
    TT_TIME_TAG,
    TT_TOKEN_ATTR,
    seed_demo_field,
)


# ── Palette ────────────────────────────────────────────────────────
BG = "#060810"
PANEL = "#0d1422"
PANEL_BORDER = "#1e2a44"
GOLD = "#ffcc44"
TEAL = "#00ffc8"
VIOLET = "#b76eff"
RED = "#ff6e6e"
BLUE = "#5aa8ff"
DIM = "#4a5570"
TEXT = "#d8e3ff"

TOKEN_COLORS = {
    TT_PROTEIN:         "#5aa8ff",
    TT_SMALL_MOLECULE:  "#4ee0a8",
    TT_GENE_EXPRESSION: "#a8e0a8",
    TT_ANTIBODY:        "#ffcc44",
    TT_SCALAR_ATTR:     "#ffa07a",
    TT_TOKEN_ATTR:      "#c0c0ff",
    TT_TIME_TAG:        "#888888",
}
SWIMMER_COLORS = {
    "BINDING":       "#4ee0a8",
    "CONTRADICTION": "#ff6e6e",
    "INFLAMMATION":  "#ffcc44",
    "MUTATION":      "#b76eff",
    "TOXICITY":      "#ff8c42",
    "MEMORY":        "#5aa8ff",
    "DREAM_REPLAY":  "#e0a8ff",
}
RECEIPT_COLORS = {
    RK_HYPOTHESIS:        "#4ee0a8",
    RK_CONTRADICTION:     "#ff6e6e",
    RK_LOW_CONFIDENCE:    "#888888",
    RK_REPLAY_REINFORCED: "#5aa8ff",
    RK_TOXICITY_CLUSTER:  "#ff8c42",
}


# ── MAMMAL query worker ────────────────────────────────────────────

class _MammalQueryWorker(QThread):
    finished_with_result = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, organ: MammalOrgan, prompt: str, parent=None):
        super().__init__(parent)
        self._organ = organ
        self._prompt = prompt

    def run(self):
        try:
            r = self._organ.query(self._prompt)
            self.finished_with_result.emit({
                "ok": r.ok, "output": r.output, "error": r.error,
                "receipt_id": r.receipt_id, "prompt": self._prompt,
            })
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"{type(e).__name__}: {e}")


# ── Field canvas ───────────────────────────────────────────────────

class _FieldCanvas(FigureCanvas):
    def __init__(self, parent=None):
        fig = Figure(figsize=(7, 5), facecolor=BG)
        super().__init__(fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.figure = fig
        self.ax = fig.add_subplot(111)
        self._style_axes()
        fig.tight_layout(pad=0.4)

    def _style_axes(self):
        self.ax.set_facecolor(BG)
        for spine in self.ax.spines.values():
            spine.set_color(DIM)
        self.ax.tick_params(colors=DIM, labelsize=7)
        self.ax.set_aspect("equal")

    def render(self, field: MammalTokenField, banner: str = "") -> None:
        ax = self.ax
        ax.clear()
        self._style_axes()
        ax.set_xlim(0, field.width)
        ax.set_ylim(0, field.height)
        for tok in field.tokens:
            color = TOKEN_COLORS.get(tok.type, "#ffffff")
            size = 50 + 250 * tok.energy
            alpha = 0.4 + 0.6 * tok.energy
            ax.scatter([tok.x], [tok.y], c=color, s=size, alpha=alpha,
                       edgecolors=color, linewidths=1.0)
            if tok.visit_count >= 3:
                ax.scatter([tok.x], [tok.y], c="none", s=size * 1.8,
                           alpha=0.4, edgecolors=BLUE, linewidths=1.5)
        for sw in field.swimmers:
            color = SWIMMER_COLORS.get(sw.swimmer_type, "#ffffff")
            ax.scatter([sw.x], [sw.y], c=color, s=90, marker="^",
                       edgecolors="#ffffff", linewidths=0.5,
                       alpha=0.95, zorder=5)
        if banner:
            ax.text(0.02, 0.98, banner, transform=ax.transAxes,
                    va="top", ha="left", color=GOLD, fontsize=9,
                    fontweight="bold", family="Menlo")
        ax.set_xticks([])
        ax.set_yticks([])
        self.figure.tight_layout(pad=0.4)
        self.draw_idle()


# ── Main app ───────────────────────────────────────────────────────

class StigmergicMammalCanvasApp(SiftaBaseWidget):
    APP_NAME = "Stigmergic Mammal Canvas (live)"

    def build_ui(self, layout: QVBoxLayout) -> None:
        banner = QLabel(
            "ARCHITECT_DOCTRINE + OPERATIONAL — Living token ecology over "
            "the MAMMAL biomedical vocabulary. 7 typed token types × 7 "
            "swimmer species. Token metabolism: weak hypotheses evaporate, "
            "strong ones stabilize. §20.F: biomedical receipts inherit "
            "HYPOTHESIS class. Companion to the text-pane Stigmergic MAMMAL "
            "(this view animates the field)."
        )
        banner.setWordWrap(True)
        banner.setStyleSheet(
            f"background: #2a2410; color: {GOLD}; font-family: Menlo; "
            f"font-size: 10px; font-weight: 700; padding: 6px 8px; "
            f"border: 1px solid #5a4820; border-radius: 4px;"
        )
        layout.addWidget(banner)

        # Controls
        controls = QHBoxLayout()
        self._btn_run = QPushButton("▶ Run / Pause")
        self._btn_run.setCheckable(True)
        self._btn_run.setStyleSheet(self._teal_style())
        self._btn_run.toggled.connect(self._on_run_toggled)
        controls.addWidget(self._btn_run)

        self._btn_reseed = QPushButton("↻ Reseed")
        self._btn_reseed.setStyleSheet(self._teal_style())
        self._btn_reseed.clicked.connect(self._reseed)
        controls.addWidget(self._btn_reseed)

        self._btn_dream = QPushButton("💤 Dream mode")
        self._btn_dream.setCheckable(True)
        self._btn_dream.setStyleSheet(self._violet_style())
        self._btn_dream.toggled.connect(self._on_dream_toggled)
        controls.addWidget(self._btn_dream)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        controls.addWidget(sep)

        self._txt_query = QLineEdit()
        self._txt_query.setPlaceholderText(
            "type protein (MKTAYIA…) or SMILES (CC(=O)O…) — then Query MAMMAL"
        )
        self._txt_query.setStyleSheet(
            f"background: {PANEL}; color: {TEXT}; font-family: Menlo; "
            f"font-size: 10px; padding: 4px 8px; border: 1px solid {PANEL_BORDER}; "
            f"border-radius: 3px;"
        )
        controls.addWidget(self._txt_query, 1)

        self._btn_query = QPushButton("Query MAMMAL")
        self._btn_query.setStyleSheet(self._gold_style())
        self._btn_query.clicked.connect(self._on_query)
        controls.addWidget(self._btn_query)
        layout.addLayout(controls)

        # Three panes
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = self._panel("Token stream")
        self._stream = QTextEdit()
        self._stream.setReadOnly(True)
        self._stream.setStyleSheet(
            f"background: {BG}; color: {TEXT}; font-family: Menlo; "
            f"font-size: 10px; border: none;"
        )
        left.layout().addWidget(self._stream, 1)
        splitter.addWidget(left)

        center = self._panel("Living field — 7 swimmers, 7 token types")
        self._canvas = _FieldCanvas(center)
        center.layout().addWidget(self._canvas, 1)
        self._status = QLabel("Press Run to start.")
        self._status.setStyleSheet(
            f"color: {DIM}; font-family: Menlo; font-size: 9px; padding-top: 4px;"
        )
        center.layout().addWidget(self._status)
        splitter.addWidget(center)

        right = self._panel("Receipts")
        self._receipts_list = QListWidget()
        self._receipts_list.setStyleSheet(
            f"background: {BG}; color: {TEXT}; font-family: Menlo; "
            f"font-size: 9px; border: none;"
        )
        right.layout().addWidget(self._receipts_list, 1)
        self._counts = QLabel("HYP 0 · CTR 0 · LOW 0 · RPY 0 · TOX 0")
        self._counts.setStyleSheet(
            f"color: {GOLD}; font-family: Menlo; font-size: 9px; padding-top: 4px;"
        )
        right.layout().addWidget(self._counts)
        splitter.addWidget(right)

        splitter.setSizes([240, 600, 320])
        layout.addWidget(splitter, 1)

        # State
        self._field: Optional[MammalTokenField] = None
        self._organ: Optional[MammalOrgan] = None
        self._worker: Optional[_MammalQueryWorker] = None
        self._counts_by_kind: dict[str, int] = {
            RK_HYPOTHESIS: 0, RK_CONTRADICTION: 0, RK_LOW_CONFIDENCE: 0,
            RK_REPLAY_REINFORCED: 0, RK_TOXICITY_CLUSTER: 0,
        }
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._reseed()

    # ── helpers ────────────────────────────────────────────

    def _panel(self, title: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"background: {PANEL}; border: 1px solid {PANEL_BORDER}; "
            f"border-radius: 6px;"
        )
        v = QVBoxLayout(f)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {GOLD}; font-family: Menlo; font-size: 11px; "
            f"font-weight: 700;"
        )
        v.addWidget(lbl)
        return f

    def _teal_style(self) -> str:
        return (
            f"QPushButton {{ background: {PANEL}; color: {TEAL}; "
            f"font-family: Menlo; font-size: 10px; font-weight: 700; "
            f"padding: 5px 10px; border: 1px solid {TEAL}; "
            f"border-radius: 3px; }} "
            f"QPushButton:hover {{ background: #102a28; }} "
            f"QPushButton:checked {{ background: #154a3a; }}"
        )

    def _gold_style(self) -> str:
        return (
            f"QPushButton {{ background: {PANEL}; color: {GOLD}; "
            f"font-family: Menlo; font-size: 10px; font-weight: 700; "
            f"padding: 5px 10px; border: 1px solid {GOLD}; "
            f"border-radius: 3px; }} "
            f"QPushButton:hover {{ background: #2a2410; }}"
        )

    def _violet_style(self) -> str:
        return (
            f"QPushButton {{ background: {PANEL}; color: {VIOLET}; "
            f"font-family: Menlo; font-size: 10px; font-weight: 700; "
            f"padding: 5px 10px; border: 1px solid {VIOLET}; "
            f"border-radius: 3px; }} "
            f"QPushButton:hover {{ background: #2a1a3a; }} "
            f"QPushButton:checked {{ background: #3a2a5e; }}"
        )

    # ── lifecycle ──────────────────────────────────────────

    def _reseed(self) -> None:
        self._field = MammalTokenField(width=16, height=12, seed=113)
        self._field.install_default_pool(seed=113)
        for sw in self._field.swimmers:
            sw.sensing_radius = 4.5
            sw.speed = 0.55
        seed_demo_field(self._field, n_each=5)
        self._stream.clear()
        self._receipts_list.clear()
        self._counts_by_kind = {k: 0 for k in self._counts_by_kind}
        self._stream_header()
        for t in self._field.tokens:
            self._stream_token(t)
        self._canvas.render(self._field, banner="DEMO seeded — press Run")
        self._refresh_counts()

    def _on_run_toggled(self, checked: bool) -> None:
        if checked:
            self._btn_run.setText("⏸ Pause")
            self._timer.start(120)
            self._status.setText("Running. 7 swimmers patrolling…")
        else:
            self._btn_run.setText("▶ Run / Pause")
            self._timer.stop()
            self._status.setText("Paused.")

    def _on_dream_toggled(self, checked: bool) -> None:
        if self._field is None:
            return
        self._field.dream_mode = checked
        self._status.setText(
            "Dream mode ON — DreamReplaySwimmer reinforcing strong clusters."
            if checked else "Dream mode OFF."
        )

    def _tick(self) -> None:
        if self._field is None:
            return
        prev = len(self._field.receipts)
        out = self._field.step()
        for r in self._field.receipts[prev:]:
            self._append_receipt(r)
            self._counts_by_kind[r.kind] = self._counts_by_kind.get(r.kind, 0) + 1
        banner = (
            f"step {out['step']}   alive={out['n_tokens_alive']}   "
            f"died={self._field.tokens_died}   "
            f"receipts={len(self._field.receipts)}"
        )
        if self._field.dream_mode:
            banner += "   💤 DREAM"
        self._canvas.render(self._field, banner=banner)
        self._refresh_counts()
        # trim stream
        doc = self._stream.document()
        if doc.blockCount() > 220:
            c = self._stream.textCursor()
            c.movePosition(QTextCursor.MoveOperation.Start)
            for _ in range(doc.blockCount() - 200):
                c.select(QTextCursor.SelectionType.LineUnderCursor)
                c.removeSelectedText()
                c.deleteChar()

    # ── stream helpers ─────────────────────────────────────

    def _stream_header(self) -> None:
        f1 = QTextCharFormat()
        f1.setForeground(QColor(GOLD))
        f1.setFontWeight(700)
        c = self._stream.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        c.insertText("typed token stream\n", f1)
        f2 = QTextCharFormat()
        f2.setForeground(QColor(DIM))
        c.insertText("-" * 24 + "\n", f2)

    def _stream_token(self, tok) -> None:
        c = self._stream.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        f = QTextCharFormat()
        f.setForeground(QColor(TOKEN_COLORS.get(tok.type, "#ffffff")))
        f.setFontWeight(600)
        c.insertText(f"[{tok.type[:9]:<9}] ", f)
        f2 = QTextCharFormat()
        f2.setForeground(QColor(TEXT))
        c.insertText(f"{tok.value[:34]}\n", f2)

    def _append_receipt(self, r: ReceiptRow) -> None:
        item = QListWidgetItem(f"[{r.kind[:3]}] {r.text[:80]}")
        item.setForeground(QColor(RECEIPT_COLORS.get(r.kind, "#ffffff")))
        self._receipts_list.addItem(item)
        while self._receipts_list.count() > 100:
            self._receipts_list.takeItem(0)
        self._receipts_list.scrollToBottom()

    def _refresh_counts(self) -> None:
        c = self._counts_by_kind
        self._counts.setText(
            f"HYP {c[RK_HYPOTHESIS]} · CTR {c[RK_CONTRADICTION]} · "
            f"LOW {c[RK_LOW_CONFIDENCE]} · RPY {c[RK_REPLAY_REINFORCED]} · "
            f"TOX {c[RK_TOXICITY_CLUSTER]}"
        )

    # ── MAMMAL query path ─────────────────────────────────

    def _on_query(self) -> None:
        prompt = self._txt_query.text().strip()
        if not prompt:
            self._status.setText("Type a protein or SMILES first.")
            return
        if self._worker is not None and self._worker.isRunning():
            return
        if self._organ is None:
            self._organ = MammalOrgan()
            if not self._organ.weights_present():
                self._status.setText(
                    "MAMMAL weights not on disk. See Documents/MAMMAL_ORGAN_PULL_GUIDE.md."
                )
                return
        self._btn_query.setEnabled(False)
        self._status.setText(f"Querying MAMMAL on {prompt[:40]!r}…")
        self._worker = _MammalQueryWorker(self._organ, prompt, parent=self)
        self._worker.finished_with_result.connect(self._on_query_result)
        self._worker.failed.connect(self._on_query_failed)
        self._worker.start()

    def _on_query_result(self, payload: dict) -> None:
        self._btn_query.setEnabled(True)
        if not payload.get("ok"):
            self._status.setText(f"MAMMAL query failed: {payload.get('error')}")
            return
        prompt = payload["prompt"]
        output = payload.get("output") or {}
        first_dims = output.get("first_8_dims", [])
        ttype = self._infer_token_type(prompt)
        if self._field is not None:
            tok = self._field.spawn_token(
                ttype, prompt[:24], energy=1.0, embedding=first_dims,
            )
            self._stream_token(tok)
            if first_dims:
                self._field.spawn_token(
                    TT_SCALAR_ATTR, f"emb0:{first_dims[0]:.3f}",
                    x=tok.x + 0.5, y=tok.y, energy=0.8,
                )
                self._stream_token(self._field.tokens[-1])
        self._status.setText(
            f"MAMMAL → {ttype} token spawned · receipt {payload['receipt_id']} · "
            f"shape {output.get('shape', [])}"
        )

    def _on_query_failed(self, err: str) -> None:
        self._btn_query.setEnabled(True)
        self._status.setText(f"Worker error: {err}")

    def _infer_token_type(self, prompt: str) -> str:
        s = prompt.strip()
        if not s:
            return TT_TOKEN_ATTR
        if any(c in s for c in "()[]=#@") or any(c.isdigit() for c in s):
            return TT_SMALL_MOLECULE
        if s.isupper() and len(s) >= 20 and all(c in "ACDEFGHIKLMNPQRSTVWY" for c in s):
            return TT_PROTEIN
        if "CDR" in s or "Ig" in s:
            return TT_ANTIBODY
        return TT_PROTEIN


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = StigmergicMammalCanvasApp()
    w.resize(1280, 760)
    w.setWindowTitle("Stigmergic Mammal Canvas — MAMMAL × 7 swimmers × 7 token types")
    w.show()
    sys.exit(app.exec())
