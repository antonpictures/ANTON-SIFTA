#!/usr/bin/env python3
"""sifta_mammal_unified_field_widget.py — MAMMAL killer figure, live.

Architect 2026-05-14 (after watching the MAMMAL video): "no graphics
and no drug discovery? look how nice graphics attached for the 3 items
in the stigmergic unified field?"

This widget answers that complaint. Three modality panels at the top
mirror the paper figure 1-to-1:

    ┌──────────────┬──────────────┬───────────────┐
    │ SMALL_MOL    │ GENE_EXPR    │ PROTEIN       │
    │ (atom+bond)  │ (bar chart)  │ (AA strip)    │
    └──────────────┴──────────────┴───────────────┘
              │           │            │
              ▼           ▼            ▼
    ┌──────────────────────────────────────────────┐
    │     SHARED EMBEDDING SPACE (when run)        │
    │  first-8-dim values from MammalOrgan query   │
    └──────────────────────────────────────────────┘
                        │
                        ▼
    ┌──────────────────────────────────────────────┐
    │  HYPOTHESIS  drug × target binding score     │
    │  (truth_class=HYPOTHESIS, §20.F)             │
    └──────────────────────────────────────────────┘

Default demo pair: **acetaminophen + EGFR fragment**.
The user can edit the SMILES + protein sequence and re-run.

The widget will:
  - When MAMMAL weights are missing → render the modalities + heuristic
    score (clearly labeled "PLACEHOLDER — pull weights first")
  - When MAMMAL is loaded → call query() on each modality, render real
    embedding first-8-dims in the shared space, score from cosine of
    embedding pair (still HYPOTHESIS class — biomedical claims need
    wet-lab validation per §20.F)

Companion to:
  - Codex's text-pane Stigmergic MAMMAL widget (verify+run+receipts)
  - My animated Stigmergic Mammal Canvas (token ecology field)
  - This widget: the **drug discovery surface** that matches the paper figure
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
from matplotlib.patches import FancyArrowPatch

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget
from System.swarm_mammal_modality_viz import (
    AA_CLASS_COLORS,
    BarSpec,
    DrugTargetPair,
    ResidueSpec,
    example_drug_target_pair,
    gene_activity_bars,
    heuristic_binding_score,
    layout_atom_graph,
    parse_smiles_to_graph,
    protein_sequence_strip,
)
from System.swarm_mammal_organ import MammalOrgan


# ── Palette ───────────────────────────────────────────────────────
BG = "#060810"
PANEL = "#0d1422"
PANEL_BORDER = "#1e2a44"
GOLD = "#ffcc44"
TEAL = "#00ffc8"
VIOLET = "#b76eff"
RED = "#ff6e6e"
DIM = "#4a5570"
TEXT = "#d8e3ff"


# ── Worker thread for MAMMAL queries ──────────────────────────────

class _ModalityQueryWorker(QThread):
    """Runs three MAMMAL queries (small_mol, gene_expr, protein) off
    the UI thread. Emits a dict with each modality's embedding."""
    finished_with_result = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, organ: MammalOrgan, pair: DrugTargetPair, parent=None):
        super().__init__(parent)
        self._organ = organ
        self._pair = pair

    def run(self):
        try:
            r_drug = self._organ.query(self._pair.drug_smiles)
            r_protein = self._organ.query(self._pair.target_sequence)
            gene_str = " ".join(
                f"{k}={v:.2f}" for k, v in self._pair.target_gene_activity.items()
            )
            r_gene = self._organ.query(gene_str)
            self.finished_with_result.emit({
                "ok": all((r_drug.ok, r_protein.ok, r_gene.ok)),
                "drug": r_drug.to_dict(),
                "protein": r_protein.to_dict(),
                "gene": r_gene.to_dict(),
            })
        except Exception as e:  # noqa: BLE001
            self.failed.emit(f"{type(e).__name__}: {e}")


# ── Canvas drawers ─────────────────────────────────────────────────

class _ModalityCanvas(FigureCanvas):
    """One row, three subplots — drug, gene, protein."""

    def __init__(self, parent=None):
        fig = Figure(figsize=(11, 3.0), facecolor=BG)
        super().__init__(fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.figure = fig
        self.ax_drug = fig.add_subplot(131)
        self.ax_gene = fig.add_subplot(132)
        self.ax_protein = fig.add_subplot(133)
        for ax in (self.ax_drug, self.ax_gene, self.ax_protein):
            self._style(ax)
        fig.tight_layout(pad=0.4)

    @staticmethod
    def _style(ax):
        ax.set_facecolor(BG)
        for spine in ax.spines.values():
            spine.set_color(DIM)
        ax.tick_params(colors=DIM, labelsize=7)
        ax.title.set_color(GOLD)

    def render(self, pair: DrugTargetPair) -> None:
        # ── DRUG (atom-bond) ─────────────────────────────────
        self.ax_drug.clear()
        self._style(self.ax_drug)
        self.ax_drug.set_title("SMALL MOLECULE", fontsize=9, fontweight="bold")
        graph = parse_smiles_to_graph(pair.drug_smiles)
        pos = layout_atom_graph(graph, iterations=80, seed=113)
        # Bonds
        for b in graph.bonds:
            if b.a in pos and b.b in pos:
                xa, ya = pos[b.a]
                xb, yb = pos[b.b]
                if b.order == 2:
                    self.ax_drug.plot([xa, xb], [ya, yb], color="#a0a0a0", linewidth=2.4, alpha=0.9)
                    self.ax_drug.plot([xa, xb], [ya, yb], color=BG, linewidth=0.6)
                elif b.order == 3:
                    self.ax_drug.plot([xa, xb], [ya, yb], color="#a0a0a0", linewidth=3.2)
                else:
                    self.ax_drug.plot([xa, xb], [ya, yb], color="#a0a0a0", linewidth=1.4)
        # Atoms
        for atom in graph.atoms:
            if atom.idx not in pos:
                continue
            x, y = pos[atom.idx]
            color = atom.color()
            self.ax_drug.scatter([x], [y], c=color, s=220, edgecolors="#ffffff", linewidths=0.7, zorder=5)
            if atom.element != "C":
                self.ax_drug.text(x, y, atom.element, ha="center", va="center",
                                  color="#ffffff", fontsize=8, fontweight="bold", zorder=6)
        self.ax_drug.set_xlim(-1.3, 1.3)
        self.ax_drug.set_ylim(-1.3, 1.3)
        self.ax_drug.set_xticks([])
        self.ax_drug.set_yticks([])
        self.ax_drug.set_aspect("equal")
        self.ax_drug.text(0.5, -0.18, pair.drug_name, transform=self.ax_drug.transAxes,
                          ha="center", color=TEXT, fontsize=8, family="Menlo")
        self.ax_drug.text(0.02, 1.02, pair.drug_smiles, transform=self.ax_drug.transAxes,
                          ha="left", color=DIM, fontsize=7, family="Menlo")

        # ── GENE (bar chart) ─────────────────────────────────
        self.ax_gene.clear()
        self._style(self.ax_gene)
        self.ax_gene.set_title("GENE EXPRESSION", fontsize=9, fontweight="bold")
        bars = gene_activity_bars(pair.target_gene_activity)
        if bars:
            labels = [b.label for b in bars]
            values = [b.value for b in bars]
            colors = [b.color for b in bars]
            y_positions = list(range(len(bars)))
            self.ax_gene.barh(y_positions, values, color=colors, edgecolor=PANEL_BORDER, linewidth=0.5)
            for i, b in enumerate(bars):
                self.ax_gene.text(b.value + 0.02, i, f"{b.value:.2f}",
                                  va="center", color=TEXT, fontsize=8, family="Menlo")
            self.ax_gene.set_yticks(y_positions)
            self.ax_gene.set_yticklabels(labels, color=TEXT, fontsize=8, family="Menlo")
            self.ax_gene.set_xlim(0, 1.15)
            self.ax_gene.invert_yaxis()
        self.ax_gene.set_xlabel("activity", color=DIM, fontsize=8)

        # ── PROTEIN (sequence strip) ─────────────────────────
        self.ax_protein.clear()
        self._style(self.ax_protein)
        self.ax_protein.set_title("PROTEIN", fontsize=9, fontweight="bold")
        strip = protein_sequence_strip(pair.target_sequence, max_residues=60)
        for r in strip:
            row = r.index // 20    # 20 residues per row
            col = r.index % 20
            self.ax_protein.add_patch(
                matplotlib.patches.Rectangle(
                    (col * 1.0, -row * 1.2), 0.9, 1.0,
                    facecolor=r.color, edgecolor="#ffffff", linewidth=0.3, alpha=0.9,
                )
            )
            self.ax_protein.text(
                col * 1.0 + 0.45, -row * 1.2 + 0.5, r.letter,
                ha="center", va="center", color="#000000", fontsize=6, fontweight="bold",
            )
        n_rows = max(1, (len(strip) - 1) // 20 + 1)
        self.ax_protein.set_xlim(-0.5, 20.5)
        self.ax_protein.set_ylim(-n_rows * 1.2, 1.4)
        self.ax_protein.set_xticks([])
        self.ax_protein.set_yticks([])
        self.ax_protein.set_aspect("auto")
        # Legend
        legend_items = list(AA_CLASS_COLORS.items())
        for i, (cls, color) in enumerate(legend_items):
            self.ax_protein.text(
                i * 3.2 + 0.5, -n_rows * 1.2 - 0.6,
                f"■ {cls}", color=color, fontsize=6.5, family="Menlo",
            )
        # Subtitle below the legend
        self.ax_protein.text(
            0.5, -0.35,
            pair.target_name[:42],
            transform=self.ax_protein.transAxes,
            ha="center", color=TEXT, fontsize=8, family="Menlo",
        )

        self.figure.tight_layout(pad=0.4)
        self.draw_idle()


class _EmbeddingCanvas(FigureCanvas):
    """Renders the three first-8-dim embedding rows (one per modality)
    as a horizontal stack of colored cells."""

    def __init__(self, parent=None):
        fig = Figure(figsize=(11, 1.8), facecolor=BG)
        super().__init__(fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.figure = fig
        self.ax = fig.add_subplot(111)
        self._style()
        fig.tight_layout(pad=0.4)

    def _style(self):
        self.ax.set_facecolor(BG)
        for spine in self.ax.spines.values():
            spine.set_color(DIM)
        self.ax.tick_params(colors=DIM, labelsize=7)

    def render(self, embeddings: dict[str, list[float]] | None) -> None:
        self.ax.clear()
        self._style()
        self.ax.set_title("SHARED EMBEDDING SPACE (MAMMAL first 8 dims)",
                          fontsize=9, fontweight="bold", color=GOLD)
        if not embeddings:
            self.ax.text(0.5, 0.5, "press Run Drug Discovery to populate",
                         transform=self.ax.transAxes, ha="center", va="center",
                         color=DIM, fontsize=10, family="Menlo")
            self.ax.set_xticks([])
            self.ax.set_yticks([])
            self.draw_idle()
            return
        rows = ["small_molecule", "gene_expression", "protein"]
        for ri, name in enumerate(rows):
            vec = embeddings.get(name) or [0.0] * 8
            for ci, v in enumerate(vec[:8]):
                # Map value to a color: red (negative) — gray (0) — teal (positive)
                norm = max(-1.0, min(1.0, float(v) / max(0.5, max(abs(x) for x in vec) or 1.0)))
                if norm > 0:
                    r, g, b = 78 + int(norm * 100), 224, 168
                    color = f"#{r:02x}{g:02x}{b:02x}"
                else:
                    r = 255
                    gb = 170 - int(abs(norm) * 100)
                    color = f"#{r:02x}{max(0,gb):02x}{max(0,gb):02x}"
                self.ax.add_patch(
                    matplotlib.patches.Rectangle(
                        (ci, -ri * 1.1), 0.96, 0.92,
                        facecolor=color, edgecolor=PANEL_BORDER, linewidth=0.5,
                    )
                )
                self.ax.text(ci + 0.48, -ri * 1.1 + 0.46, f"{v:+.2f}",
                             ha="center", va="center", color="#000000",
                             fontsize=6, family="Menlo")
            self.ax.text(-0.3, -ri * 1.1 + 0.46, name,
                         ha="right", va="center", color=TEXT, fontsize=8, family="Menlo")
        self.ax.set_xlim(-4.5, 8.5)
        self.ax.set_ylim(-3.6, 1.2)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.figure.tight_layout(pad=0.4)
        self.draw_idle()


# ── Main app ───────────────────────────────────────────────────────

class MammalUnifiedFieldApp(SiftaBaseWidget):
    APP_NAME = "MAMMAL Unified Field (drug discovery)"

    def build_ui(self, layout: QVBoxLayout) -> None:
        # Banner
        banner = QLabel(
            "ARCHITECT_DOCTRINE — Three modalities flow into one shared "
            "embedding space (small molecule + gene expression + protein), "
            "exactly as the MAMMAL paper figure shows. Every prediction "
            "below carries truth_class=HYPOTHESIS. §20.F: no wet-lab claims, "
            "no AlphaFold-beating language, no \"we solved binding\" outreach."
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
        self._txt_smiles = QLineEdit()
        self._txt_smiles.setPlaceholderText("SMILES (e.g. CC(=O)NC1=CC=C(O)C=C1 for acetaminophen)")
        self._txt_smiles.setStyleSheet(self._input_style())
        controls.addWidget(QLabel("Drug:"))
        controls.addWidget(self._txt_smiles, 2)

        self._txt_protein = QLineEdit()
        self._txt_protein.setPlaceholderText("Target protein sequence (single-letter AAs)")
        self._txt_protein.setStyleSheet(self._input_style())
        controls.addWidget(QLabel("Target:"))
        controls.addWidget(self._txt_protein, 3)
        for lbl in controls.parentWidget().findChildren(QLabel) if controls.parentWidget() else []:
            lbl.setStyleSheet(f"color: {TEAL}; font-family: Menlo; font-size: 10px;")
        layout.addLayout(controls)

        run_row = QHBoxLayout()
        self._btn_reset = QPushButton("↻ Load demo pair")
        self._btn_reset.setStyleSheet(self._teal_style())
        self._btn_reset.clicked.connect(self._load_demo)
        run_row.addWidget(self._btn_reset)

        self._btn_render = QPushButton("🎨 Re-render modalities")
        self._btn_render.setStyleSheet(self._teal_style())
        self._btn_render.clicked.connect(self._render_modalities)
        run_row.addWidget(self._btn_render)

        self._btn_run = QPushButton("💊 Run Drug Discovery")
        self._btn_run.setStyleSheet(self._gold_style())
        self._btn_run.clicked.connect(self._on_run)
        run_row.addWidget(self._btn_run)

        run_row.addStretch(1)
        self._lbl_status = QLabel("Loading demo pair…")
        self._lbl_status.setStyleSheet(
            f"color: {DIM}; font-family: Menlo; font-size: 10px;"
        )
        run_row.addWidget(self._lbl_status, 1)
        layout.addLayout(run_row)

        # Modality row
        self._modality_canvas = _ModalityCanvas()
        layout.addWidget(self._modality_canvas, 2)

        # Embedding row
        self._embedding_canvas = _EmbeddingCanvas()
        layout.addWidget(self._embedding_canvas, 1)

        # Hypothesis panel
        self._hypothesis_box = QPlainTextEdit()
        self._hypothesis_box.setReadOnly(True)
        self._hypothesis_box.setStyleSheet(
            f"QPlainTextEdit {{ background: {PANEL}; color: {TEXT}; "
            f"font-family: Menlo; font-size: 11px; "
            f"border: 1px solid {GOLD}; padding: 8px; }}"
        )
        self._hypothesis_box.setFixedHeight(140)
        self._hypothesis_box.setPlainText(
            "HYPOTHESIS panel — populated after Run Drug Discovery. "
            "Every score here is HYPOTHESIS class until wet-lab validation."
        )
        layout.addWidget(self._hypothesis_box)

        # State
        self._pair: Optional[DrugTargetPair] = None
        self._organ: Optional[MammalOrgan] = None
        self._worker: Optional[_ModalityQueryWorker] = None
        self._load_demo()

    # ── helpers ────────────────────────────────────────────

    def _input_style(self) -> str:
        return (
            f"background: {PANEL}; color: {TEXT}; font-family: Menlo; "
            f"font-size: 10px; padding: 4px 8px; border: 1px solid {PANEL_BORDER}; "
            f"border-radius: 3px;"
        )

    def _teal_style(self) -> str:
        return (
            f"QPushButton {{ background: {PANEL}; color: {TEAL}; "
            f"font-family: Menlo; font-size: 10px; font-weight: 700; "
            f"padding: 5px 12px; border: 1px solid {TEAL}; "
            f"border-radius: 3px; }} "
            f"QPushButton:hover {{ background: #102a28; }}"
        )

    def _gold_style(self) -> str:
        return (
            f"QPushButton {{ background: {PANEL}; color: {GOLD}; "
            f"font-family: Menlo; font-size: 11px; font-weight: 700; "
            f"padding: 6px 16px; border: 2px solid {GOLD}; "
            f"border-radius: 4px; }} "
            f"QPushButton:hover {{ background: #2a2410; }}"
        )

    # ── lifecycle ──────────────────────────────────────────

    def _load_demo(self) -> None:
        self._pair = example_drug_target_pair()
        self._txt_smiles.setText(self._pair.drug_smiles)
        self._txt_protein.setText(self._pair.target_sequence)
        self._lbl_status.setText(
            f"Demo pair: {self._pair.drug_name} × {self._pair.target_name[:32]}…"
        )
        self._render_modalities()
        self._embedding_canvas.render(None)
        self._render_hypothesis(None)

    def _current_pair(self) -> DrugTargetPair:
        """Build a pair from the input fields + the canonical gene activity."""
        smiles = self._txt_smiles.text().strip() or "CCO"
        seq = self._txt_protein.text().strip() or "MKTAY"
        # Re-use the demo gene activity (this widget doesn't ask the user
        # for it — could be a follow-up if needed).
        base = self._pair or example_drug_target_pair()
        return DrugTargetPair(
            drug_name="user_drug",
            drug_smiles=smiles,
            target_name="user_target",
            target_sequence=seq,
            target_gene_activity=dict(base.target_gene_activity),
            note=base.note,
        )

    def _render_modalities(self) -> None:
        pair = self._current_pair()
        self._modality_canvas.render(pair)

    def _on_run(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        pair = self._current_pair()
        if self._organ is None:
            self._organ = MammalOrgan()
        if not self._organ.weights_present():
            self._lbl_status.setText(
                "MAMMAL weights not on disk. Falling back to heuristic. "
                "See Documents/MAMMAL_ORGAN_PULL_GUIDE.md."
            )
            self._embedding_canvas.render({
                "small_molecule": [0.0] * 8,
                "gene_expression": [0.0] * 8,
                "protein": [0.0] * 8,
            })
            self._render_hypothesis(None, fallback_pair=pair)
            return
        self._btn_run.setEnabled(False)
        self._lbl_status.setText("Querying MAMMAL on three modalities…")
        self._worker = _ModalityQueryWorker(self._organ, pair, parent=self)
        self._worker.finished_with_result.connect(self._on_query_result)
        self._worker.failed.connect(self._on_query_failed)
        self._worker.start()

    def _on_query_result(self, payload: dict) -> None:
        self._btn_run.setEnabled(True)
        if not payload.get("ok"):
            self._lbl_status.setText("MAMMAL query partially failed — check receipts ledger.")
            self._render_hypothesis(None, fallback_pair=self._current_pair())
            return
        embeddings = {
            "small_molecule": (payload["drug"].get("output") or {}).get("first_8_dims", []),
            "gene_expression": (payload["gene"].get("output") or {}).get("first_8_dims", []),
            "protein": (payload["protein"].get("output") or {}).get("first_8_dims", []),
        }
        self._embedding_canvas.render(embeddings)
        # Score: cosine similarity between drug + protein embeddings
        d = embeddings["small_molecule"]
        p = embeddings["protein"]
        score = self._cosine(d, p)
        self._render_hypothesis(score, fallback_pair=self._current_pair())
        self._lbl_status.setText(
            f"MAMMAL ran. Cosine(drug, protein) = {score:.3f} (HYPOTHESIS)."
        )

    def _on_query_failed(self, err: str) -> None:
        self._btn_run.setEnabled(True)
        self._lbl_status.setText(f"Worker error: {err}")

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        import math
        n = min(len(a), len(b))
        if n == 0:
            return 0.0
        dot = sum(a[i] * b[i] for i in range(n))
        na = math.sqrt(sum(a[i] * a[i] for i in range(n))) or 1.0
        nb = math.sqrt(sum(b[i] * b[i] for i in range(n))) or 1.0
        return max(-1.0, min(1.0, dot / (na * nb)))

    def _render_hypothesis(
        self, score: Optional[float],
        *,
        fallback_pair: Optional[DrugTargetPair] = None,
    ) -> None:
        pair = fallback_pair or self._current_pair()
        graph = parse_smiles_to_graph(pair.drug_smiles)
        strip = protein_sequence_strip(pair.target_sequence)
        heuristic = heuristic_binding_score(graph, strip)
        heuristic.drug_name = pair.drug_name
        heuristic.target_name = pair.target_name
        if score is None:
            # No MAMMAL — heuristic only
            text = (
                f"HYPOTHESIS  ·  truth_class=HYPOTHESIS  ·  §20.F\n\n"
                f"drug:    {pair.drug_name}  ({pair.drug_smiles[:48]})\n"
                f"target:  {pair.target_name[:60]}\n\n"
                f"PLACEHOLDER score (no MAMMAL):  {heuristic.score:.3f}\n"
                f"rationale: {heuristic.rationale}\n\n"
                f"This is NOT a real binding prediction. Pull MAMMAL weights "
                f"to get the actual model's verdict — see "
                f"Documents/MAMMAL_ORGAN_PULL_GUIDE.md."
            )
        else:
            interpretation = (
                "high similarity" if score > 0.3 else
                "moderate similarity" if score > 0.0 else
                "weak / negative similarity"
            )
            text = (
                f"HYPOTHESIS  ·  truth_class=HYPOTHESIS  ·  §20.F\n\n"
                f"drug:    {pair.drug_name}  ({pair.drug_smiles[:48]})\n"
                f"target:  {pair.target_name[:60]}\n\n"
                f"MAMMAL cosine(drug-embed, protein-embed) = {score:+.3f}  "
                f"({interpretation})\n"
                f"heuristic placeholder score: {heuristic.score:.3f}\n\n"
                f"Interpretation: a non-zero MAMMAL cosine indicates the "
                f"model places the drug + target in nearby regions of its "
                f"learned representation. This is NOT a binding affinity "
                f"in kcal/mol. NOT a clinical claim. NOT a substitute for "
                f"docking or wet-lab. §20.F: no AlphaFold-beating language."
            )
        self._hypothesis_box.setPlainText(text)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = MammalUnifiedFieldApp()
    w.resize(1300, 880)
    w.setWindowTitle("MAMMAL Unified Field — drug × gene × protein")
    w.show()
    sys.exit(app.exec())
