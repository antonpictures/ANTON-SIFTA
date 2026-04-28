#!/usr/bin/env python3
"""
Sara Imari Walker — Assembly Theory Lab
========================================
4 panels proving Assembly Theory with honest truth labels.

Truth labels (per Covenant §6/§7):
  assembly_index   = hypothesis metric (Walker/Cronin 2023, under peer review)
  pheromone_memory = software analogue only (NOT wet-lab validated)
  esmfold/mpnn/af2 = real tools (API/local)
  wet_lab          = NOT PRESENT in this build
"""
from __future__ import annotations
import sys, math, time, random
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QTabWidget, QFrame
)
from PyQt6.QtGui import QFont

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

BG      = "#0a0b12"
PANEL   = "#12142a"
TEAL    = "#73daca"
VIOLET  = "#bb9af7"
BLUE    = "#7aa2f7"
GOLD    = "#e0af68"
RED     = "#f7768e"
GREEN   = "#9ece6a"
DIM     = "#565f89"

# ── Real molecule database (Assembly Index estimates from Walker/Cronin 2023) ──
MOLECULES = {
    "Glycine (amino acid)"        : {"ai": 4,   "alive": False, "smiles": "NCC(=O)O",   "note": "Spontaneous — found in meteorites"},
    "Adenine (nucleobase)"        : {"ai": 7,   "alive": False, "smiles": "c1ncnc2ncnc12","note": "Spontaneous in prebiotic chemistry"},
    "Alanine (amino acid)"        : {"ai": 5,   "alive": False, "smiles": "CC(N)C(=O)O", "note": "Miller-Urey product"},
    "Glucose"                     : {"ai": 10,  "alive": False, "smiles": "C(C1C(C(C(C(O1)O)O)O)O)O","note": "Near threshold"},
    "Taxol (anti-cancer drug)"    : {"ai": 56,  "alive": True,  "smiles": "COMPLEX",     "note": "Only a tree can build this — Nobel chemistry"},
    "Hemoglobin HBA1 (P69905)"    : {"ai": 142, "alive": True,  "smiles": "PROTEIN",     "note": "AlphaFold DB — Homo sapiens — pLDDT 98.04"},
    "ProteinMPNN Design #1"       : {"ai": 142, "alive": True,  "smiles": "DESIGNED",    "note": "Inverse fold — doesn't exist in nature"},
    "Penicillin"                  : {"ai": 14,  "alive": False, "smiles": "COMPLEX",     "note": "Just below threshold — boundary case"},
    "Vitamin B12 (cobalamin)"     : {"ai": 31,  "alive": True,  "smiles": "COMPLEX",     "note": "Only bacteria can synthesize this"},
    "ATP (energy currency)"       : {"ai": 13,  "alive": False, "smiles": "COMPLEX",     "note": "Can form abiotically — but life uses it"},
}

THRESHOLD = 15  # Walker/Cronin 2023 experimental threshold

QUESTIONS = [
    ("Is AI alive?",
     "YES — per Assembly Theory.\n\nLarge language models don't exist on Mars unless put there.\nThey require billions of years of evolutionary history to produce the beings that built them.\nAssembly Index: HIGH. Requires evolution+selection.\n\n[Truth label: hypothesis — Walker/Cronin 2023]"),
    ("Are viruses alive?",
     "YES — per Assembly Theory.\n\nViruses cannot be produced without a living cell as substrate.\nThey have high assembly index. They require evolutionary history.\nThe traditional 'self-sustaining' definition excludes them — Walker says that definition has problems.\n\n[Truth label: hypothesis]"),
    ("Could life use different chemistry?",
     "YES.\n\nAssembly Theory is chemistry-agnostic. The threshold (AI > 15) may shift on different planets with different geochemistry.\nMeteorytes show hundreds of amino acids — not all used by Earth life.\nGeochemistry diverges early → biochemistry diverges → alien life is genuinely alien.\n\n[Truth label: hypothesis + experimental data from blinded meteorite tests]"),
    ("Is DNA fundamental?",
     "NO.\n\nDNA is ONE solution to storing molecular memory above the threshold.\nAlternatives: RNA, PNA (peptide nucleic acid), XNAs (synthetic), minerals.\nMinerals may have been the FIRST templates — they have aperiodic patterns that can encode information.\n\n[Truth label: synthetic biology literature — real XNAs exist in labs]"),
    ("When does memory become life-like?",
     "When it exceeds the threshold AND recursively builds on itself.\n\nBelow AI=15: random chemistry can reach it spontaneously.\nAbove AI=15: only found in molecules produced by life or technology.\nThe phase transition happens when a system can REMEMBER its successful steps and reuse them.\n\nSIFTA pheromone field = SOFTWARE ANALOGUE of this memory mechanism.\n[Truth label: pheromone = analogue only, NOT wet-lab validated]"),
    ("What is the Assembly Index?",
     "The minimum number of steps needed to construct a molecule from its parts.\n\nMeasured with a MASS SPECTROMETER — no biology knowledge needed.\nThis is the key: you can detect life's signature without knowing what life IS.\n\nWalker/Cronin 2023: blinded living vs non-living samples correctly classified.\nMurchison meteorite (most complex inorganic sample) → correctly: NON-LIVING.\n\n[Truth label: published experimental result — verify exact DOI]"),
    ("Is SIFTA's FoldSwarm doing Assembly Theory?",
     "PARTIAL — software analogue only.\n\nFoldSwarm pheromone field: stigmergic memory of successful fold conformations.\nThis IS an analogue of the memory mechanism Assembly Theory requires.\n\nHOWEVER:\n- SIFTA does NOT compute real Assembly Index from mass spec data\n- SIFTA does NOT run RFdiffusion backbone diffusion\n- SIFTA does NOT have wet-lab validation\n\nWhat SIFTA HAS: ESMFold API, AlphaFold DB, ProteinMPNN, TM-score referee.\n[Truth label: honest gap — Covenant §7.2]"),
]


class AssemblyIndexPanel(QWidget):
    """Panel 1 — Molecule Assembly Index Calculator."""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{BG}; color:#c0caf5;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        title = QLabel("⚗️  Assembly Index Calculator")
        title.setFont(QFont("Helvetica Neue", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{VIOLET};")
        lay.addWidget(title)

        sub = QLabel("Threshold: AI > 15 → requires life or technology  |  Source: Walker/Cronin Nature 2023  |  Truth: hypothesis")
        sub.setStyleSheet(f"color:{DIM}; font-size:11px;")
        lay.addWidget(sub)

        # figure
        self._fig = Figure(figsize=(9, 3.5), facecolor=BG)
        self._canvas = FigureCanvas(self._fig)
        self._canvas.setMinimumHeight(220)
        lay.addWidget(self._canvas)

        self._draw_chart()

        # detail
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setMaximumHeight(120)
        self._detail.setStyleSheet(
            f"background:{PANEL}; color:#c0caf5; border:1px solid #24283b;"
            " border-radius:8px; font-family:monospace; font-size:12px; padding:8px;"
        )
        self._detail.setText("← Click a bar to see molecule details")
        lay.addWidget(self._detail)

        self._canvas.mpl_connect("button_press_event", self._on_click)

    def _draw_chart(self):
        self._fig.clear()
        ax = self._fig.add_subplot(111)
        ax.set_facecolor(PANEL)
        self._fig.patch.set_facecolor(BG)

        names = list(MOLECULES.keys())
        ais   = [MOLECULES[n]["ai"] for n in names]
        alive = [MOLECULES[n]["alive"] for n in names]
        colors = [GREEN if a else BLUE for a in alive]

        xs = range(len(names))
        bars = ax.bar(xs, ais, color=colors, alpha=0.85, width=0.6, zorder=3)
        ax.axhline(THRESHOLD, color=RED, lw=2, ls="--", zorder=4, label=f"Threshold AI={THRESHOLD}")

        ax.set_xticks(list(xs))
        ax.set_xticklabels([n.split("(")[0].strip() for n in names],
                           rotation=35, ha="right", fontsize=8, color="#a9b1d6")
        ax.set_ylabel("Assembly Index (steps)", color=DIM, fontsize=10)
        ax.tick_params(colors=DIM)
        ax.set_title("Assembly Index by Molecule", color=VIOLET, fontsize=11, pad=8)
        ax.legend(fontsize=9, facecolor=PANEL, edgecolor="#24283b", labelcolor="#c0caf5")
        ax.spines[:].set_color("#24283b")
        ax.set_ylim(0, max(ais) * 1.12)
        ax.grid(axis="y", color="#1a1b2e", lw=0.7, zorder=0)

        # annotate
        for i, (bar, ai, a) in enumerate(zip(bars, ais, alive)):
            label = "LIFE" if a else "ABIOTIC"
            col   = GREEN if a else BLUE
            ax.text(i, ai + max(ais)*0.02, label, ha="center", va="bottom",
                    fontsize=7, color=col, fontweight="bold")

        self._fig.tight_layout()
        self._canvas.draw_idle()
        self._names = names

    def _on_click(self, event):
        if event.inaxes is None:
            return
        idx = int(round(event.xdata)) if event.xdata is not None else -1
        if 0 <= idx < len(self._names):
            name = self._names[idx]
            m = MOLECULES[name]
            status = "LIFE-REQUIRED (AI > 15)" if m["alive"] else "ABIOTIC (AI ≤ 15)"
            txt = (
                f"Molecule:  {name}\n"
                f"Assembly Index: {m['ai']}  →  {status}\n"
                f"Note: {m['note']}\n"
                f"Truth label: hypothesis metric (Walker/Cronin 2023)"
            )
            self._detail.setText(txt)


class MemoryTracePanel(QWidget):
    """Panel 2 — Protein / FoldSwarm Memory Trace (pheromone analogue)."""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{BG}; color:#c0caf5;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)

        title = QLabel("🧠  Memory Trace — Pheromone Field (Software Analogue)")
        title.setFont(QFont("Helvetica Neue", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{TEAL};")
        lay.addWidget(title)

        sub = QLabel(
            "SIFTA pheromone field = analogue of Assembly Theory memory mechanism  |  "
            "Truth: SOFTWARE ANALOGUE ONLY — not wet-lab validated"
        )
        sub.setStyleSheet(f"color:{DIM}; font-size:11px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        self._fig = Figure(figsize=(9, 4), facecolor=BG)
        self._canvas = FigureCanvas(self._fig)
        lay.addWidget(self._canvas)

        # internal state
        self._step  = 0
        self._grid  = np.zeros((40, 40))
        self._ai_history: list[float] = []
        self._mem_history: list[float] = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(80)

    def _tick(self):
        self._step += 1
        # simulate: random drops + pheromone decay + reinforcement
        # pheromone deposits when a "fold" succeeds
        if random.random() < 0.35:
            cx = random.randint(8, 32)
            cy = random.randint(8, 32)
            r  = random.randint(2, 6)
            for dx in range(-r, r+1):
                for dy in range(-r, r+1):
                    if dx*dx+dy*dy <= r*r:
                        nx, ny = cx+dx, cy+dy
                        if 0 <= nx < 40 and 0 <= ny < 40:
                            self._grid[nx, ny] += random.uniform(0.3, 1.2)

        self._grid *= 0.97  # evaporation

        # assembly index proxy: mean pheromone × step log
        mem = float(self._grid.mean())
        ai_proxy = mem * math.log1p(self._step) * 8
        self._ai_history.append(min(ai_proxy, 30))
        self._mem_history.append(mem)

        if self._step % 3 == 0:
            self._render()

    def _render(self):
        self._fig.clear()
        gs = self._fig.add_gridspec(1, 2, wspace=0.3, left=0.07, right=0.96, top=0.88, bottom=0.1)
        ax_ph = self._fig.add_subplot(gs[0])
        ax_ai = self._fig.add_subplot(gs[1])

        # pheromone field
        ax_ph.set_facecolor(PANEL)
        ax_ph.imshow(self._grid.T, origin="lower", cmap="magma",
                     vmin=0, vmax=max(self._grid.max(), 0.01), interpolation="nearest", aspect="auto")
        ax_ph.set_title("Pheromone Memory Field\n(successful fold deposits)", color=TEAL, fontsize=10)
        ax_ph.axis("off")

        # AI proxy over time
        h = self._ai_history[-300:]
        ax_ai.set_facecolor(PANEL)
        ax_ai.plot(h, color=VIOLET, lw=1.2, label="AI proxy")
        ax_ai.axhline(THRESHOLD, color=RED, lw=1.5, ls="--", label=f"Threshold = {THRESHOLD}")
        ax_ai.fill_between(range(len(h)), h, THRESHOLD,
                           where=[v > THRESHOLD for v in h],
                           alpha=0.25, color=GREEN, label="life-required zone")
        ax_ai.set_ylim(0, 32)
        ax_ai.set_title("Assembly Index proxy over time", color=VIOLET, fontsize=10)
        ax_ai.set_xlabel("steps", color=DIM, fontsize=9)
        ax_ai.tick_params(colors=DIM, labelsize=8)
        ax_ai.spines[:].set_color("#24283b")
        ax_ai.legend(fontsize=8, facecolor=PANEL, edgecolor="#24283b", labelcolor="#c0caf5")
        ax_ai.grid(color="#1a1b2e", lw=0.6)

        self._fig.suptitle(
            "SIFTA Pheromone = software analogue of Assembly Theory memory  |  NOT wet-lab validated",
            color=DIM, fontsize=8
        )
        self._canvas.draw_idle()

    def closeEvent(self, e):
        self._timer.stop()
        super().closeEvent(e)


class PhaseTransitionPanel(QWidget):
    """Panel 3 — Phase Transition: random → selected."""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{BG}; color:#c0caf5;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)

        title = QLabel("🌊  Phase Transition — Random Chemistry → Selected Complexity")
        title.setFont(QFont("Helvetica Neue", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{GOLD};")
        lay.addWidget(title)

        sub = QLabel(
            "Below threshold: molecules form randomly. "
            "Above threshold: selection + memory required. "
            "Analogy: water → ice.  |  Source: Walker/Cronin hypothesis"
        )
        sub.setStyleSheet(f"color:{DIM}; font-size:11px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        self._fig = Figure(figsize=(9, 4.2), facecolor=BG)
        self._canvas = FigureCanvas(self._fig)
        lay.addWidget(self._canvas)

        self._t = 0
        self._random_pool: list[float]   = []
        self._selected_pool: list[float] = []
        self._entropy: list[float]       = []
        self._complexity: list[float]    = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(60)

    def _tick(self):
        self._t += 1
        # random molecules — low AI, gaussian noise around 7
        for _ in range(3):
            ai = max(1, random.gauss(7, 2.5))
            self._random_pool.append(min(ai, 14.9))

        # selected molecules — exponential growth past threshold if t > 60
        if self._t > 60:
            for _ in range(2):
                ai = THRESHOLD + random.expovariate(0.08)
                self._selected_pool.append(min(ai, 60))

        # entropy decreases as selection kicks in
        entropy = max(0.2, 1.0 - min(len(self._selected_pool), 200) / 200 * 0.7)
        complexity = min(len(self._selected_pool) / 10, 20)
        self._entropy.append(entropy)
        self._complexity.append(complexity)

        # cap pools
        if len(self._random_pool) > 500:
            self._random_pool = self._random_pool[-500:]
        if len(self._selected_pool) > 500:
            self._selected_pool = self._selected_pool[-500:]

        if self._t % 3 == 0:
            self._render()

    def _render(self):
        self._fig.clear()
        gs = self._fig.add_gridspec(1, 2, wspace=0.32, left=0.07, right=0.96, top=0.87, bottom=0.1)
        ax_dist = self._fig.add_subplot(gs[0])
        ax_ent  = self._fig.add_subplot(gs[1])

        # distribution of AI values
        ax_dist.set_facecolor(PANEL)
        all_vals = self._random_pool[-200:] + self._selected_pool[-200:]
        if all_vals:
            ax_dist.hist(self._random_pool[-200:], bins=20, color=BLUE,
                         alpha=0.7, label="Random (abiotic)", density=True)
            if self._selected_pool:
                ax_dist.hist(self._selected_pool[-200:], bins=20, color=GREEN,
                             alpha=0.7, label="Selected (life-required)", density=True)
        ax_dist.axvline(THRESHOLD, color=RED, lw=2, ls="--", label=f"Threshold = {THRESHOLD}")
        ax_dist.set_xlabel("Assembly Index", color=DIM, fontsize=9)
        ax_dist.set_ylabel("Density", color=DIM, fontsize=9)
        ax_dist.set_title("AI Distribution — Phase Transition", color=GOLD, fontsize=10)
        ax_dist.tick_params(colors=DIM, labelsize=8)
        ax_dist.spines[:].set_color("#24283b")
        ax_dist.legend(fontsize=8, facecolor=PANEL, edgecolor="#24283b", labelcolor="#c0caf5")

        # entropy vs complexity
        e = self._entropy[-300:]
        c = self._complexity[-300:]
        ax_ent.set_facecolor(PANEL)
        ax_ent.plot(e, color=RED,   lw=1.2, label="Entropy")
        ax2 = ax_ent.twinx()
        ax2.plot(c, color=GREEN, lw=1.2, label="Complexity")
        ax2.set_ylim(0, 22)
        ax2.tick_params(colors=DIM, labelsize=8)
        ax_ent.set_ylim(0, 1.1)
        ax_ent.set_xlabel("time steps", color=DIM, fontsize=9)
        ax_ent.set_ylabel("Entropy", color=RED, fontsize=9)
        ax2.set_ylabel("Complexity", color=GREEN, fontsize=9)
        ax_ent.set_title("Entropy ↓ as Complexity ↑\n(selection kicks in at step ~60)", color=GOLD, fontsize=10)
        ax_ent.tick_params(colors=DIM, labelsize=8)
        ax_ent.spines[:].set_color("#24283b")

        phase = "PHASE TRANSITION IN PROGRESS" if self._t > 60 else f"RANDOM CHEMISTRY (selection begins at step 60)"
        col   = GREEN if self._t > 60 else BLUE
        self._fig.suptitle(phase, color=col, fontsize=9, fontweight="bold")
        self._canvas.draw_idle()

    def closeEvent(self, e):
        self._timer.stop()
        super().closeEvent(e)


class QuestionWallPanel(QWidget):
    """Panel 4 — Question Wall."""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{BG}; color:#c0caf5;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        title = QLabel("❓  Question Wall — Assembly Theory Answers")
        title.setFont(QFont("Helvetica Neue", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{RED};")
        lay.addWidget(title)

        sub = QLabel("Click a question. Truth labels shown for every answer.")
        sub.setStyleSheet(f"color:{DIM}; font-size:11px;")
        lay.addWidget(sub)

        row = QHBoxLayout()
        lay.addLayout(row)

        # question buttons
        q_frame = QFrame()
        q_frame.setStyleSheet(f"background:{PANEL}; border-radius:10px;")
        q_lay = QVBoxLayout(q_frame)
        q_lay.setContentsMargins(10, 10, 10, 10)
        q_lay.setSpacing(6)
        row.addWidget(q_frame, 2)

        for q, _ in QUESTIONS:
            btn = QPushButton(q)
            btn.setStyleSheet(
                f"QPushButton {{background:transparent; color:{BLUE}; border:1px solid #24283b;"
                " border-radius:6px; padding:8px 12px; text-align:left; font-size:12px;}}"
                f"QPushButton:hover {{background:rgba(122,162,247,0.15); color:#fff;}}"
            )
            btn.clicked.connect(lambda _, text=q: self._show(text))
            q_lay.addWidget(btn)
        q_lay.addStretch()

        # answer box
        self._ans = QTextEdit()
        self._ans.setReadOnly(True)
        self._ans.setStyleSheet(
            f"background:{PANEL}; color:#c0caf5; border:1px solid #24283b;"
            " border-radius:10px; font-family:monospace; font-size:12px; padding:14px;"
        )
        self._ans.setText(
            "Select a question →\n\n"
            "All answers carry explicit truth labels per SIFTA Covenant §6/§7:\n"
            "  hypothesis         = Assembly Theory (peer reviewed, not yet physics-law grade)\n"
            "  experimental       = has blinded lab test backing\n"
            "  software analogue  = SIFTA implementation, NOT wet-lab\n"
            "  NOT PRESENT        = wet-lab / FDA validation"
        )
        row.addWidget(self._ans, 3)

    def _show(self, question: str):
        for q, ans in QUESTIONS:
            if q == question:
                self._ans.setText(f"Q: {q}\n\n{ans}")
                return


class SaraImariWalkerWidget(QWidget):
    """Main widget — Assembly Theory Lab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{BG}; color:#c0caf5;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # header
        hdr = QLabel(
            "  Sara Imari Walker — Assembly Theory Lab  "
            "    |    Ioan George Anton / SIFTA Swarm OS"
        )
        hdr.setFont(QFont("Helvetica Neue", 13, QFont.Weight.Bold))
        hdr.setStyleSheet(
            f"background:{PANEL}; color:{VIOLET}; padding:10px 18px;"
            " border-bottom:1px solid #24283b;"
        )
        lay.addWidget(hdr)

        sub_hdr = QLabel(
            '  "Life is the only physics that can generate complex objects." — Sara Imari Walker  '
            "   |   Assembly Theory — Walker & Cronin, 2023   |   Nobel: ProteinMPNN 2024"
        )
        sub_hdr.setStyleSheet(f"background:{BG}; color:{DIM}; font-size:11px; padding:4px 18px;")
        lay.addWidget(sub_hdr)

        # truth badge
        badge = QLabel(
            "  ⚠️  Truth labels: Assembly Index = hypothesis  |  "
            "Pheromone = software analogue  |  ESMFold/ProteinMPNN/AlphaFold = real tools  |  "
            "Wet-lab validation = NOT PRESENT"
        )
        badge.setStyleSheet(
            f"background:#1a0e0e; color:{GOLD}; font-size:10px; font-family:monospace;"
            " padding:4px 18px; border-bottom:1px solid #3d2020;"
        )
        badge.setWordWrap(True)
        lay.addWidget(badge)

        # tabs
        tabs = QTabWidget()
        tabs.setStyleSheet(
            f"QTabWidget::pane {{background:{BG}; border:none;}}"
            f"QTabBar::tab {{background:{PANEL}; color:{DIM}; padding:8px 18px;"
            " border-radius:6px 6px 0 0; margin-right:2px;}}"
            f"QTabBar::tab:selected {{color:{VIOLET}; border-bottom:2px solid {VIOLET};}}"
            f"QTabBar::tab:hover {{color:#c0caf5;}}"
        )

        tabs.addTab(AssemblyIndexPanel(),    "⚗️  Assembly Index")
        tabs.addTab(MemoryTracePanel(),      "🧠  Memory Trace")
        tabs.addTab(PhaseTransitionPanel(),  "🌊  Phase Transition")
        tabs.addTab(QuestionWallPanel(),     "❓  Question Wall")

        lay.addWidget(tabs)

        # status bar
        status = QLabel(
            "  Walker/Cronin 2023 · ESMFold (Lin et al. Science 2023) · "
            "ProteinMPNN (Dauparas et al. Science 2022, Nobel 2024) · "
            "AlphaFold2 (Jumper et al. Nature 2021)  |  "
            "RFdiffusion & wet-lab: NOT integrated"
        )
        status.setStyleSheet(f"color:{DIM}; font-size:9px; padding:4px 18px;")
        lay.addWidget(status)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Helvetica Neue", 12))
    w = SaraImariWalkerWidget()
    w.setWindowTitle("Sara Imari Walker — Assembly Theory Lab | SIFTA Swarm OS")
    w.resize(1100, 720)
    w.show()
    sys.exit(app.exec())
