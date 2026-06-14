#!/usr/bin/env python3
"""SIFTA Stigmergic MAMMAL app — the unified surface.

THE ONE APP for everything MAMMAL × SIFTA. Three tabs, one window:

  Tab 1 — Drug Discovery Lab (Codex):
    Painted three-modality hero (molecule → DNA → protein → unified field)
    + Verify Weights + Run Token Ecology + Run Drug-Discovery Lab buttons
    + ranked HYPOTHESIS candidates with toxicity penalties

  Tab 2 — Live Token Ecology (Cowork):
    Animated 2D canvas showing the 7 swimmer species patrolling typed
    tokens. Token mortality is visible (weak hypotheses evaporate, strong
    ones stabilize as memory wells). 8 Hz tick.

  Tab 3 — Modality Detail (Cowork):
    Three scientific subplots — atom-bond molecular graph parsed from
    SMILES, gene-activity bar chart, amino-acid sequence strip colored
    by class. Shared embedding-space row populated when MAMMAL is
    queried via the Run Drug Discovery button on Tab 1.

  Help — the OS wrapper ? button loads the full operator's manual from
  Documents/APP_HELP.md. This widget does not carry a second help button.

Architect 2026-05-14: "ONE APP that has everything with ALL the help
and explanations — people gonna take a look tomorrow — top top deep
TIP."

Coordinated build: Codex shipped the drug-discovery lab backend +
painted hero (receipt 334fc77de273aa77). Cowork pulled in the live
canvas, modality detail, plain-English summary, and help system.
The other two MAMMAL apps (Stigmergic Mammal Canvas, MAMMAL Unified
Field) are deregistered from the manifest — ONE app now.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from System.swarm_mammal_drug_discovery_lab import run_mammal_drug_discovery_lab
from System.swarm_mammal_drug_repurposing import (
    rank_diseases_for_drug,
    write_receipt as write_repurposing_receipt,
)
from System.swarm_mammal_token_ecology import run_mammal_token_ecology
from System.swarm_mammal_weight_manager import prove_mammal_weights
# Cowork 2026-05-14 — JSON → plain-English translator for the
# "Impress Me" panel + "Explain why this matters" button per the
# architect's 2026-05-13 spec ("stop showing raw guts").
from System.swarm_mammal_impress_summary import (
    explain_why_this_matters,
    summary_what_happened,
)
# Cowork 2026-05-14 (consolidation pass) — pull in the live canvas
# (token ecology field with 7 swimmer species) and the detailed
# modality graphics (SMILES atom-bond, gene bars, AA strip).
from System.swarm_mammal_token_field import (
    MammalTokenField,
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
from System.swarm_mammal_modality_viz import (
    AA_CLASS_COLORS,
    example_drug_target_pair,
    gene_activity_bars,
    layout_atom_graph,
    parse_smiles_to_graph,
    protein_sequence_strip,
)
# matplotlib used for tabs 2 and 3 — defer import to avoid hard
# dependency at module load when matplotlib isn't present.
try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.patches
    _HAS_MPL = True
except Exception:
    _HAS_MPL = False


class _DrugDiscoveryGraphic(QWidget):
    """Painted three-modality MAMMAL -> SIFTA field explanation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(250)
        self._result: dict | None = None
        self.setStyleSheet("background: #03070b; border: 1px solid #1e2a44;")

    def set_result(self, result: dict | None) -> None:
        self._result = dict(result or {})
        self.update()

    def paintEvent(self, event):  # type: ignore[override]
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = max(1, self.width())
        h = max(1, self.height())
        p.fillRect(self.rect(), QColor("#03070b"))
        p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        p.setPen(QColor("#d8e3ff"))

        top_h = int(h * 0.42)
        pad = 18
        gap = 14
        col_w = (w - pad * 2 - gap * 2) / 3.0
        panels = [
            (QRectF(pad, 18, col_w, top_h - 26), "SMALL MOLECULE", "#4ee0a8"),
            (QRectF(pad + col_w + gap, 18, col_w, top_h - 26), "GENE EXPRESSION", "#a8e0a8"),
            (QRectF(pad + (col_w + gap) * 2, 18, col_w, top_h - 26), "PROTEIN / ANTIBODY", "#5aa8ff"),
        ]
        for rect, title, color in panels:
            self._draw_panel(p, rect, title, QColor(color))

        self._draw_molecule(p, panels[0][0])
        self._draw_dna(p, panels[1][0])
        self._draw_protein(p, panels[2][0])

        # Arrows into the unified field.
        field_rect = QRectF(pad, top_h + 18, w - pad * 2, h - top_h - 34)
        p.setPen(QPen(QColor("#f6c453"), 2))
        for rect, _title, _color in panels:
            x = rect.center().x()
            p.drawLine(int(x), int(rect.bottom() + 4), int(x), int(field_rect.top() + 10))
            p.drawLine(int(x), int(field_rect.top() + 10), int(x - 5), int(field_rect.top() + 3))
            p.drawLine(int(x), int(field_rect.top() + 10), int(x + 5), int(field_rect.top() + 3))

        self._draw_unified_field(p, field_rect)
        p.end()

    def _draw_panel(self, p: QPainter, rect: QRectF, title: str, color: QColor) -> None:
        p.setPen(QPen(color, 1))
        p.setBrush(QColor(8, 16, 24, 230))
        p.drawRoundedRect(rect, 6, 6)
        p.setPen(color)
        p.drawText(rect.adjusted(10, 8, -10, -8), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, title)

    def _draw_molecule(self, p: QPainter, rect: QRectF) -> None:
        cx, cy = rect.center().x(), rect.center().y() + 8
        pts = [(cx - 42, cy), (cx - 18, cy - 25), (cx + 16, cy - 22), (cx + 40, cy + 2), (cx + 14, cy + 28), (cx - 18, cy + 25)]
        p.setPen(QPen(QColor("#d8e3ff"), 2))
        for a, b in zip(pts, pts[1:] + pts[:1]):
            p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
        colors = ["#cfd6e8", "#4ee0a8", "#ff6e6e", "#cfd6e8", "#ffcc44", "#cfd6e8"]
        for (x, y), c in zip(pts, colors):
            p.setBrush(QColor(c))
            p.setPen(QColor("#101820"))
            p.drawEllipse(int(x - 7), int(y - 7), 14, 14)
        p.setPen(QColor("#b8c8e8"))
        p.setFont(QFont("Menlo", 9))
        p.drawText(rect.adjusted(8, rect.height() - 34, -8, -6), Qt.AlignmentFlag.AlignCenter, "SMILES / ligand tokens")

    def _draw_dna(self, p: QPainter, rect: QRectF) -> None:
        left, right = rect.left() + 28, rect.right() - 28
        mid = rect.center().y() + 2
        p.setPen(QPen(QColor("#d8e3ff"), 2))
        last1 = last2 = None
        for i in range(48):
            t = i / 47.0
            x = left + (right - left) * t
            y1 = mid + 24 * math.sin(t * math.tau * 2)
            y2 = mid - 24 * math.sin(t * math.tau * 2)
            if last1:
                p.drawLine(int(last1[0]), int(last1[1]), int(x), int(y1))
                p.drawLine(int(last2[0]), int(last2[1]), int(x), int(y2))
            if i % 6 == 0:
                p.drawLine(int(x), int(y1), int(x), int(y2))
            last1, last2 = (x, y1), (x, y2)
        p.setPen(QColor("#b8c8e8"))
        p.setFont(QFont("Menlo", 9))
        p.drawText(rect.adjusted(8, rect.height() - 34, -8, -6), Qt.AlignmentFlag.AlignCenter, "ranked genes / cell state")

    def _draw_protein(self, p: QPainter, rect: QRectF) -> None:
        p.setPen(QPen(QColor("#5aa8ff"), 4))
        left = rect.left() + 28
        mid = rect.center().y() + 4
        pts = []
        for i in range(24):
            x = left + i * ((rect.width() - 56) / 23)
            y = mid + 24 * math.sin(i * 0.75)
            pts.append((x, y))
        for a, b in zip(pts, pts[1:]):
            p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
        p.setPen(QPen(QColor("#ffcc44"), 3))
        p.drawArc(int(rect.center().x() - 28), int(mid - 46), 56, 56, 30 * 16, 240 * 16)
        p.setPen(QColor("#b8c8e8"))
        p.setFont(QFont("Menlo", 9))
        p.drawText(rect.adjusted(8, rect.height() - 34, -8, -6), Qt.AlignmentFlag.AlignCenter, "sequence / binding context")

    def _draw_unified_field(self, p: QPainter, rect: QRectF) -> None:
        p.setPen(QPen(QColor("#21f6c8"), 1))
        p.setBrush(QColor(6, 20, 18, 235))
        p.drawRoundedRect(rect, 8, 8)
        p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        p.setPen(QColor("#21f6c8"))
        p.drawText(rect.adjusted(12, 8, -12, -8), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, "SIFTA unified biomedical field")
        p.setFont(QFont("Menlo", 9))
        p.setPen(QColor("#d8e3ff"))
        result = self._result or {}
        candidates = result.get("candidates") or []
        if not candidates:
            lines = ["Press Run drug-discovery lab.", "The field will connect molecule + gene + protein tokens."]
        else:
            lines = [
                f"tokens: {result.get('field_snapshot', {}).get('n_tokens')}   swimmers: {result.get('field_snapshot', {}).get('n_swimmers')}   receipts: {result.get('field_snapshot', {}).get('n_receipts_total')}",
                "ranked HYPOTHESIS candidates:",
            ]
            lines.extend(
                f"{c.get('rank')}. {c.get('name')}  score={c.get('sifta_field_score'):.3f}  tox_penalty={c.get('components', {}).get('toxicity_penalty'):.3f}"
                for c in candidates[:4]
            )
        y = rect.top() + 36
        for line in lines:
            p.drawText(int(rect.left() + 14), int(y), line)
            y += 19
        # swimmer dots / trails
        colors = ["#4ee0a8", "#ff6e6e", "#ffcc44", "#b76eff", "#ff8c42", "#5aa8ff", "#e0a8ff"]
        for i, c in enumerate(colors):
            x = rect.right() - 170 + (i % 4) * 38
            yy = rect.center().y() + (i // 4) * 34
            p.setBrush(QColor(c))
            p.setPen(QColor("#ffffff"))
            p.drawEllipse(int(x), int(yy), 16, 16)


class StigmergicMammalWidget(QWidget):
    """Local MAMMAL + token ecology panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SIFTA MAMMAL Lab — Unified Field")
        self.resize(1180, 760)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # ── Header row ─────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("SIFTA MAMMAL Lab — Unified Field")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #21f6c8;")
        header.addWidget(title, 1)
        help_hint = QLabel("Use the window ? button for the unified operator manual.")
        help_hint.setStyleSheet(
            "color: #7f8aa8; font-family: Menlo; font-size: 10px; "
            "font-style: italic;"
        )
        header.addWidget(help_hint)
        root.addLayout(header)

        boundary = QLabel(
            "Research field only: local artifact proof + deterministic token swimmers. "
            "No clinical advice, no diagnosis, no cloud upload. §20.F: every prediction "
            "carries truth_class=HYPOTHESIS until wet-lab validation."
        )
        boundary.setWordWrap(True)
        boundary.setStyleSheet("color: #f6c453; font-weight: 700;")
        root.addWidget(boundary)

        # ── Three tabs: Lab / Live Canvas / Modality Detail ────
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { background: #03070b; border: 1px solid #1e2a44; } "
            "QTabBar::tab { background: #0d1422; color: #a8b8d8; padding: 6px 14px; "
            "font-family: Menlo; font-size: 11px; border-top-left-radius: 4px; "
            "border-top-right-radius: 4px; } "
            "QTabBar::tab:selected { background: #1a2438; color: #21f6c8; "
            "font-weight: 700; border-bottom: 2px solid #21f6c8; } "
            "QTabBar::tab:hover { background: #15213a; }"
        )
        root.addWidget(self._tabs, 1)

        # ── Tab 1: Drug Discovery Lab (Codex's flat layout) ───
        lab_tab = QWidget()
        lab_layout = QVBoxLayout(lab_tab)
        self._tabs.addTab(lab_tab, "💊 Drug Discovery Lab")

        row = QHBoxLayout()
        self._refresh_btn = QPushButton("Verify local weights")
        self._run_btn = QPushButton("Run token ecology")
        self._drug_btn = QPushButton("Run drug-discovery lab")
        # Cowork 2026-05-14 — "Explain why this matters" button per the
        # architect's spec. Translates the most recent run's JSON into
        # plain English ending with "cross-organ attention with memory".
        self._explain_btn = QPushButton("Explain why this matters")
        self._explain_btn.setStyleSheet(
            "QPushButton { background: #2a2410; color: #f6c453; "
            "font-weight: 700; border: 1px solid #f6c453; "
            "padding: 4px 10px; border-radius: 3px; } "
            "QPushButton:hover { background: #3a3420; }"
        )
        self._refresh_btn.clicked.connect(self.refresh)
        self._run_btn.clicked.connect(self.run_ecology)
        self._drug_btn.clicked.connect(self.run_drug_lab)
        self._explain_btn.clicked.connect(self.explain_last_run)
        row.addWidget(self._refresh_btn)
        row.addWidget(self._run_btn)
        row.addWidget(self._drug_btn)
        row.addWidget(self._explain_btn)
        row.addStretch(1)
        lab_layout.addLayout(row)

        self._drug_graphic = _DrugDiscoveryGraphic()
        self._drug_lab_result = run_mammal_drug_discovery_lab(steps=24, write=False)
        self._drug_graphic.set_result(self._drug_lab_result)
        lab_layout.addWidget(self._drug_graphic)

        # ── Drug-repurposing input panel ──────────────────────────
        # Architect 2026-05-14: "Where do I paste existing drugs to
        # find out what diseases they can cure that we did not know?"
        # This is the answer. Paste a name (carfilzomib, metformin,
        # aspirin, …) or a SMILES string → ranked HYPOTHESIS list
        # of diseases the drug might newly treat.
        repurp_label = QLabel(
            "💊  Drug repurposing — paste an existing drug. Get a ranked HYPOTHESIS "
            "list of diseases it might newly treat. Every line is HYPOTHESIS — wet-lab "
            "validation required before any clinical decision."
        )
        repurp_label.setWordWrap(True)
        repurp_label.setStyleSheet(
            "color: #f6c453; font-weight: 700; font-family: Menlo, monospace; "
            "padding: 8px 0 4px 0;"
        )
        lab_layout.addWidget(repurp_label)
        repurp_row = QHBoxLayout()
        from PyQt6.QtWidgets import QLineEdit
        self._repurp_input = QLineEdit()
        self._repurp_input.setPlaceholderText(
            "drug name (carfilzomib, metformin, aspirin, …) or SMILES (e.g. CC(=O)NC1=CC=C(O)C=C1)"
        )
        self._repurp_input.setStyleSheet(
            "QLineEdit { background: #061015; color: #f9fff7; "
            "font-family: Menlo, monospace; font-size: 13px; "
            "padding: 6px 10px; border: 1px solid #20d6b0; border-radius: 4px; }"
        )
        self._repurp_input.returnPressed.connect(self.run_drug_repurposing)
        repurp_row.addWidget(self._repurp_input, 1)
        self._repurp_btn = QPushButton("🔍  Find new diseases this drug might treat")
        self._repurp_btn.setStyleSheet(
            "QPushButton { background: #2a2410; color: #f6c453; "
            "font-weight: 700; border: 1px solid #f6c453; "
            "padding: 6px 14px; border-radius: 4px; } "
            "QPushButton:hover { background: #3a3420; }"
        )
        self._repurp_btn.clicked.connect(self.run_drug_repurposing)
        repurp_row.addWidget(self._repurp_btn)
        lab_layout.addLayout(repurp_row)

        # Results pane for the repurposing flow — separate from the
        # 3-column field/receipts panes below so the user sees their
        # query's answer clearly without scrolling.
        self._repurp_results = QPlainTextEdit()
        self._repurp_results.setReadOnly(True)
        self._repurp_results.setMaximumHeight(220)
        self._repurp_results.setStyleSheet(
            "QPlainTextEdit { background: #061015; color: #d8e3ff; "
            "font-family: Menlo, monospace; font-size: 12px; "
            "border: 1px solid #f6c453; padding: 8px; }"
        )
        self._repurp_results.setPlainText(
            "Paste a drug above and press Enter (or click the button) to see "
            "ranked HYPOTHESIS candidates.\n\nTry: carfilzomib, metformin, "
            "aspirin, imatinib, nintedanib, donepezil, atorvastatin, "
            "amoxicillin, remdesivir, levodopa.\n\nOr paste any SMILES "
            "string — the ranker estimates features from the molecular structure."
        )
        lab_layout.addWidget(self._repurp_results)

        cols = QHBoxLayout()
        self._weights = QPlainTextEdit()
        self._field = QPlainTextEdit()
        self._receipts = QPlainTextEdit()
        for edit in (self._weights, self._field, self._receipts):
            edit.setReadOnly(True)
            edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            edit.setStyleSheet(
                "QPlainTextEdit { background: #061015; color: #f9fff7; "
                "font-family: Menlo, monospace; font-size: 12px; border: 1px solid #20d6b0; }"
            )
        cols.addWidget(self._weights, 1)
        cols.addWidget(self._field, 2)
        cols.addWidget(self._receipts, 1)
        lab_layout.addLayout(cols, 1)

        # Cowork 2026-05-14 — "What Happened" plain-English summary pane.
        # The architect's complaint: "right now the app proves it; the UI
        # is still showing raw guts." This pane translates the run result
        # into the architect's exact prose template.
        self._impress = QPlainTextEdit()
        self._impress.setReadOnly(True)
        self._impress.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._impress.setStyleSheet(
            "QPlainTextEdit { background: #0a1410; color: #f6c453; "
            "font-family: Menlo, monospace; font-size: 13px; "
            "font-weight: 600; border: 1px solid #f6c453; padding: 6px; }"
        )
        self._impress.setPlainText(
            "WHAT HAPPENED\n\n"
            "(no run yet — press Run token ecology to populate, "
            "then 'Explain why this matters' for the plain-English version)"
        )
        # Modest fixed height — this is a summary, not a transcript.
        self._impress.setFixedHeight(220)
        lab_layout.addWidget(self._impress)

        # Cache of last result dict, so the Explain button uses real data
        self._last_result: dict | None = None

        # ── Tab 2: Live Token Ecology (Cowork's animated canvas) ───
        self._build_canvas_tab()

        # ── Tab 3: Modality Detail (Cowork's scientific subplots) ──
        self._build_modality_tab()

    # ── Tab 2: live token ecology canvas ───────────────────────

    def _build_canvas_tab(self) -> None:
        tab = QWidget()
        v = QVBoxLayout(tab)

        controls = QHBoxLayout()
        self._canvas_run_btn = QPushButton("▶ Run / Pause")
        self._canvas_run_btn.setCheckable(True)
        self._canvas_run_btn.setStyleSheet(
            "QPushButton { background: #1a2438; color: #21f6c8; font-weight: 700; "
            "border: 1px solid #21f6c8; padding: 5px 14px; border-radius: 3px; "
            "font-family: Menlo; } "
            "QPushButton:hover { background: #2a3448; } "
            "QPushButton:checked { background: #15401a; }"
        )
        self._canvas_run_btn.toggled.connect(self._on_canvas_run_toggled)
        controls.addWidget(self._canvas_run_btn)
        self._canvas_status = QLabel("Press Run — 7 swimmer species will patrol typed tokens at 8 Hz.")
        self._canvas_status.setStyleSheet("color:#a8b8d8; font-family: Menlo; font-size: 11px;")
        controls.addWidget(self._canvas_status, 1)
        v.addLayout(controls)

        if not _HAS_MPL:
            v.addWidget(QLabel("matplotlib not available — live canvas disabled."))
            self._tabs.addTab(tab, "🧬 Live Token Ecology")
            return

        self._canvas_fig = Figure(figsize=(9, 5), facecolor="#03070b")
        self._canvas_ax = self._canvas_fig.add_subplot(111)
        self._canvas_ax.set_facecolor("#03070b")
        for s in self._canvas_ax.spines.values():
            s.set_color("#1e2a44")
        self._canvas_ax.set_xticks([])
        self._canvas_ax.set_yticks([])
        self._canvas_canvas = FigureCanvas(self._canvas_fig)
        v.addWidget(self._canvas_canvas, 1)

        # Token field state
        self._canvas_field: Optional[MammalTokenField] = None
        self._canvas_timer = QTimer(self)
        self._canvas_timer.timeout.connect(self._canvas_tick)
        self._reseed_canvas()
        self._tabs.addTab(tab, "🧬 Live Token Ecology")

    def _reseed_canvas(self) -> None:
        if not _HAS_MPL:
            return
        self._canvas_field = MammalTokenField(width=16, height=12, seed=113)
        self._canvas_field.install_default_pool(seed=113)
        for sw in self._canvas_field.swimmers:
            sw.sensing_radius = 4.5
            sw.speed = 0.55
        seed_demo_field(self._canvas_field, n_each=5)
        self._render_canvas("DEMO seeded — press Run")

    def _on_canvas_run_toggled(self, checked: bool) -> None:
        if not _HAS_MPL or self._canvas_field is None:
            return
        if checked:
            self._canvas_run_btn.setText("⏸ Pause")
            self._canvas_timer.start(120)
            self._canvas_status.setText("Running. 7 swimmers patrolling…")
        else:
            self._canvas_run_btn.setText("▶ Run / Pause")
            self._canvas_timer.stop()

    def _canvas_tick(self) -> None:
        if self._canvas_field is None:
            return
        out = self._canvas_field.step()
        banner = (
            f"step {out['step']}  alive={out['n_tokens_alive']}  "
            f"died={self._canvas_field.tokens_died}  "
            f"receipts={len(self._canvas_field.receipts)}"
        )
        self._render_canvas(banner)

    def _render_canvas(self, banner: str) -> None:
        if not _HAS_MPL or self._canvas_field is None:
            return
        ax = self._canvas_ax
        ax.clear()
        ax.set_facecolor("#03070b")
        for s in ax.spines.values():
            s.set_color("#1e2a44")
        ax.set_xlim(0, self._canvas_field.width)
        ax.set_ylim(0, self._canvas_field.height)
        ax.set_xticks([])
        ax.set_yticks([])
        token_colors = {
            TT_PROTEIN: "#5aa8ff", TT_SMALL_MOLECULE: "#4ee0a8",
            TT_GENE_EXPRESSION: "#a8e0a8", TT_ANTIBODY: "#ffcc44",
            TT_SCALAR_ATTR: "#ffa07a", TT_TOKEN_ATTR: "#c0c0ff",
            TT_TIME_TAG: "#888888",
        }
        swimmer_colors = {
            "BINDING": "#4ee0a8", "CONTRADICTION": "#ff6e6e",
            "INFLAMMATION": "#ffcc44", "MUTATION": "#b76eff",
            "TOXICITY": "#ff8c42", "MEMORY": "#5aa8ff",
            "DREAM_REPLAY": "#e0a8ff",
        }
        for tok in self._canvas_field.tokens:
            c = token_colors.get(tok.type, "#ffffff")
            size = 50 + 250 * tok.energy
            alpha = 0.4 + 0.6 * tok.energy
            ax.scatter([tok.x], [tok.y], c=c, s=size, alpha=alpha,
                       edgecolors=c, linewidths=1.0)
        for sw in self._canvas_field.swimmers:
            c = swimmer_colors.get(sw.swimmer_type, "#ffffff")
            ax.scatter([sw.x], [sw.y], c=c, s=90, marker="^",
                       edgecolors="#ffffff", linewidths=0.5, zorder=5)
        ax.text(0.02, 0.98, banner, transform=ax.transAxes,
                va="top", ha="left", color="#f6c453", fontsize=9,
                fontweight="bold", family="Menlo")
        self._canvas_canvas.draw_idle()

    # ── Tab 3: detailed modality view ──────────────────────────

    def _build_modality_tab(self) -> None:
        tab = QWidget()
        v = QVBoxLayout(tab)
        if not _HAS_MPL:
            v.addWidget(QLabel("matplotlib not available — modality detail disabled."))
            self._tabs.addTab(tab, "🧪 Modality Detail")
            return
        intro = QLabel(
            "Scientific subplots: SMILES atom-bond graph + gene activity bars + "
            "amino-acid sequence colored by class. The MAMMAL paper figure, "
            "rendered live."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#a8b8d8; font-family: Menlo; font-size: 11px; padding: 4px;")
        v.addWidget(intro)

        self._modality_fig = Figure(figsize=(11, 4), facecolor="#03070b")
        self._modality_axes = [
            self._modality_fig.add_subplot(131),
            self._modality_fig.add_subplot(132),
            self._modality_fig.add_subplot(133),
        ]
        for ax in self._modality_axes:
            ax.set_facecolor("#03070b")
            for s in ax.spines.values():
                s.set_color("#1e2a44")
            ax.tick_params(colors="#4a5570", labelsize=7)
        self._modality_canvas = FigureCanvas(self._modality_fig)
        v.addWidget(self._modality_canvas, 1)

        caption = QLabel(
            "Demo pair: acetaminophen (CC(=O)NC1=CC=C(O)C=C1) × EGFR fragment. "
            "Click Run drug-discovery lab on Tab 1 to populate the shared "
            "embedding space with real MAMMAL queries."
        )
        caption.setWordWrap(True)
        caption.setStyleSheet("color:#888; font-family: Menlo; font-size: 10px;")
        v.addWidget(caption)

        self._render_modalities()
        self._tabs.addTab(tab, "🧪 Modality Detail")

    def _render_modalities(self) -> None:
        if not _HAS_MPL:
            return
        pair = example_drug_target_pair()
        ax_drug, ax_gene, ax_protein = self._modality_axes

        # Drug
        ax_drug.clear()
        ax_drug.set_facecolor("#03070b")
        for s in ax_drug.spines.values():
            s.set_color("#1e2a44")
        ax_drug.set_title("SMALL MOLECULE", color="#f6c453",
                          fontsize=9, fontweight="bold")
        graph = parse_smiles_to_graph(pair.drug_smiles)
        pos = layout_atom_graph(graph, iterations=80, seed=113)
        for b in graph.bonds:
            if b.a in pos and b.b in pos:
                xa, ya = pos[b.a]
                xb, yb = pos[b.b]
                lw = 2.4 if b.order == 2 else (3.2 if b.order == 3 else 1.4)
                ax_drug.plot([xa, xb], [ya, yb], color="#a0a0a0", linewidth=lw)
        for atom in graph.atoms:
            if atom.idx in pos:
                x, y = pos[atom.idx]
                ax_drug.scatter([x], [y], c=atom.color(), s=220,
                                edgecolors="#ffffff", linewidths=0.7, zorder=5)
                if atom.element != "C":
                    ax_drug.text(x, y, atom.element, ha="center", va="center",
                                 color="#ffffff", fontsize=8, fontweight="bold", zorder=6)
        ax_drug.set_xlim(-1.3, 1.3)
        ax_drug.set_ylim(-1.3, 1.3)
        ax_drug.set_xticks([])
        ax_drug.set_yticks([])
        ax_drug.set_aspect("equal")
        ax_drug.text(0.5, -0.1, pair.drug_name, transform=ax_drug.transAxes,
                     ha="center", color="#d8e3ff", fontsize=8, family="Menlo")

        # Gene bars
        ax_gene.clear()
        ax_gene.set_facecolor("#03070b")
        for s in ax_gene.spines.values():
            s.set_color("#1e2a44")
        ax_gene.set_title("GENE EXPRESSION", color="#f6c453",
                          fontsize=9, fontweight="bold")
        bars = gene_activity_bars(pair.target_gene_activity)
        if bars:
            labels = [b.label for b in bars]
            values = [b.value for b in bars]
            colors = [b.color for b in bars]
            ax_gene.barh(range(len(bars)), values, color=colors)
            ax_gene.set_yticks(range(len(bars)))
            ax_gene.set_yticklabels(labels, color="#d8e3ff", fontsize=8, family="Menlo")
            ax_gene.invert_yaxis()
            ax_gene.set_xlim(0, 1.1)

        # Protein
        ax_protein.clear()
        ax_protein.set_facecolor("#03070b")
        for s in ax_protein.spines.values():
            s.set_color("#1e2a44")
        ax_protein.set_title("PROTEIN", color="#f6c453",
                              fontsize=9, fontweight="bold")
        strip = protein_sequence_strip(pair.target_sequence, max_residues=60)
        for r in strip:
            row = r.index // 20
            col = r.index % 20
            ax_protein.add_patch(
                matplotlib.patches.Rectangle(
                    (col * 1.0, -row * 1.2), 0.9, 1.0,
                    facecolor=r.color, edgecolor="#ffffff", linewidth=0.3, alpha=0.9,
                )
            )
            ax_protein.text(
                col * 1.0 + 0.45, -row * 1.2 + 0.5, r.letter,
                ha="center", va="center", color="#000000", fontsize=6, fontweight="bold",
            )
        n_rows = max(1, (len(strip) - 1) // 20 + 1)
        ax_protein.set_xlim(-0.5, 20.5)
        ax_protein.set_ylim(-n_rows * 1.2, 1.4)
        ax_protein.set_xticks([])
        ax_protein.set_yticks([])

        self._modality_fig.tight_layout(pad=0.4)
        self._modality_canvas.draw_idle()

    def refresh(self) -> None:
        status = prove_mammal_weights(write=True)
        files = status.get("files", [])
        self._weights.setPlainText(
            "LOCAL MAMMAL WEIGHTS\n"
            f"installed: {status.get('installed')}\n"
            f"repo: {status.get('repo_id')}\n"
            f"revision: {status.get('revision')}\n"
            f"local_dir: {status.get('local_dir')}\n"
            f"total_bytes: {status.get('total_bytes')}\n\n"
            + "\n".join(
                f"{'OK' if f.get('present') else 'MISS'} {f.get('bytes'):>12} {f.get('sha256')[:12]} {f.get('path')}"
                for f in files
            )
        )

    def run_ecology(self) -> None:
        result = run_mammal_token_ecology(last_n_per_ledger=12, write=True)
        # Cowork 2026-05-14 — cache the result so the Explain button can
        # render the plain-English summary from the exact same numbers.
        self._last_result = dict(result)
        self._field.setPlainText(json.dumps({
            "truth_label": result.get("truth_label"),
            "n_tokens": result.get("n_tokens"),
            "n_scalar_projections": result.get("n_scalar_projections"),
            "n_pheromones": result.get("n_pheromones"),
            "pheromones_by_type": result.get("pheromones_by_type"),
            "metabolism": result.get("metabolism"),
            "pheromone_preview": result.get("pheromone_preview", [])[:12],
        }, indent=2, sort_keys=True))
        self._receipts.setPlainText(
            f"receipt_trace_id: {result.get('receipt_trace_id')}\n"
            f"receipt_sha256: {result.get('receipt_sha256')}\n\n"
            "LEDGERS\n"
            f"{Path('.sifta_state/mammal_weight_receipts.jsonl').resolve()}\n"
            f"{Path('.sifta_state/mammal_token_ecology_receipts.jsonl').resolve()}\n\n"
            "TYPES\n"
            "HYPOTHESIS\nCONTRADICTION_STORM\nINFLAMMATION_SIGNAL\n"
            "MUTATION_ZONE\nTOXICITY_CLUSTER\nMEMORY_WELL\nREPLAY_REINFORCED\nBINDING_TRAIL\n"
        )
        # Auto-render the "What Happened" panel so the user sees plain
        # English immediately, not just JSON. The Explain button below
        # gives the longer prose punchline on demand.
        self._impress.setPlainText(summary_what_happened(self._last_result))

    def run_drug_repurposing(self) -> None:
        """Architect 2026-05-14: paste a drug → rank diseases it might
        newly treat. Pure HYPOTHESIS — wet-lab validation required."""
        drug = self._repurp_input.text().strip()
        if not drug:
            self._repurp_results.setPlainText(
                "Paste a drug name or SMILES above first, then press Enter."
            )
            return
        try:
            result = rank_diseases_for_drug(drug, top_n=10)
        except Exception as e:  # noqa: BLE001
            self._repurp_results.setPlainText(
                f"Ranker failed: {type(e).__name__}: {e}"
            )
            return
        if not result.get("ok"):
            self._repurp_results.setPlainText(
                f"Could not rank: {result.get('reason', 'unknown error')}"
            )
            return
        # Write a signed receipt (truth_class=OPERATIONAL+HYPOTHESIS).
        try:
            write_repurposing_receipt(result)
        except Exception:
            pass
        # Render — clean, ranked, every line tagged HYPOTHESIS.
        lines = [
            f"DRUG REPURPOSING HYPOTHESIS · {drug}",
            f"drug_source: {result.get('drug_source')}  ·  probes: {result.get('n_probes')}",
            "─" * 64,
            f"{'rank':>4}  {'score':>6}  {'band':<9} {'disease':<32}",
            "─" * 64,
        ]
        for h in result.get("ranked", []):
            disease = h["disease_name"]
            if len(disease) > 30:
                disease = disease[:28] + "…"
            lines.append(
                f"{h['rank']:>4}  {h['score']:>6.3f}  {h['confidence_band']:<9} {disease}"
            )
        lines.append("─" * 64)
        lines.append("")
        lines.append("All lines are HYPOTHESIS. Predicted-worth-investigating only.")
        lines.append("Wet-lab validation required before any clinical use.")
        lines.append("")
        # Add the top result's rationale for context
        if result.get("ranked"):
            top = result["ranked"][0]
            lines.append(f"TOP CANDIDATE: {top['disease_name']}")
            lines.append(f"  score: {top['score']:.3f} ({top['confidence_band']})")
            lines.append(f"  canonical targets: {', '.join(top['target_proteins'][:5])}")
            lines.append(f"  rationale: {top['rationale']}")
        self._repurp_results.setPlainText("\n".join(lines))

    def run_drug_lab(self) -> None:
        result = run_mammal_drug_discovery_lab(steps=96, write=True)
        self._drug_lab_result = dict(result)
        self._drug_graphic.set_result(self._drug_lab_result)
        summary = {
            "truth_label": result.get("truth_label"),
            "truth_boundary": result.get("truth_boundary"),
            "paper": result.get("paper"),
            "pipeline_stages": result.get("pipeline_stages"),
            "modalities": result.get("modalities"),
            "field_snapshot": result.get("field_snapshot"),
            "candidates": result.get("candidates"),
            "novelty_claim": result.get("novelty_claim"),
        }
        self._field.setPlainText(json.dumps(summary, indent=2, sort_keys=True))
        self._receipts.setPlainText(
            f"receipt_trace_id: {result.get('receipt_trace_id')}\n"
            f"sha256: {result.get('sha256')}\n\n"
            "LEDGER\n"
            f"{Path('.sifta_state/mammal_drug_discovery_lab.jsonl').resolve()}\n\n"
            "RESEARCH SPINE\n"
            + "\n".join(
                f"{r.get('label')}: DOI {r.get('doi')} — {r.get('url')}"
                for r in result.get("research_spine", [])
            )
        )
        self._impress.setPlainText(
            "DRUG-DISCOVERY LAB\n\n"
            "SIFTA connected three biomedical evidence habitats in one field: "
            "small molecules, gene-expression context, and protein/antibody targets.\n\n"
            f"Top HYPOTHESIS in this deterministic field run: {result.get('top_candidate')}.\n"
            "This is the novel SIFTA surface: swimmers leave receipt trails across "
            "modalities before any model output is trusted. It is a research sandbox, "
            "not a clinical claim."
        )

    def explain_last_run(self) -> None:
        """Architect 2026-05-13 spec: 'Explain why this matters' button.
        Outputs the plain-English explanation ending with
        'cross-organ attention with memory'."""
        if self._last_result is None:
            self._impress.setPlainText(
                "WHAT HAPPENED\n\n"
                "No run yet. Press 'Run token ecology' first, then come "
                "back here — the explanation needs real numbers from a "
                "live ecology pass."
            )
            return
        # Both blocks: the WHAT HAPPENED summary AND the closing prose.
        body = (
            summary_what_happened(self._last_result)
            + "\n\n" + ("─" * 56) + "\n\n"
            + explain_why_this_matters(self._last_result)
        )
        self._impress.setPlainText(body)


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = StigmergicMammalWidget()
    w.show()
    sys.exit(app.exec())
