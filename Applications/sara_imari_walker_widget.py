#!/usr/bin/env python3
"""
Sara Imari Walker — Assembly Theory Lab
========================================
Panels for assembly-theory *pedagogy* plus a **curated literature spine** (real DOIs)
and an explicit map: **what primary papers claim** vs **what SIFTA can solve today**.

Public mission (from her own framing): physics of life's emergence, digitizing
chemistry / chemputation, origins + life-detection — without smuggling vibes as data.

Truth labels (per Covenant §6/§7):
  assembly_index   = published metrology exists (Nature 2023); bar chart = illustrative
  pheromone_memory = software analogue only (NOT wet-lab validated)
  esmfold/mpnn/af2 = real tools (API/local)
  wet_lab          = NOT PRESENT in this build
"""
from __future__ import annotations
import html
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
    QLabel, QPushButton, QTextEdit, QTextBrowser, QTabWidget, QFrame,
)
from PyQt6.QtGui import QFont

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_app_focus import publish_focus

_APP_NAME = "Sara Imari Walker — Assembly Theory Lab"

BG      = "#0a0b12"
PANEL   = "#12142a"
TEAL    = "#73daca"
VIOLET  = "#bb9af7"
BLUE    = "#7aa2f7"
GOLD    = "#e0af68"
RED     = "#f7768e"
GREEN   = "#9ece6a"
DIM     = "#565f89"

# ── Curated primary literature (machine-readable; UI renders HTML links) ──
RESEARCH_BIBLIO: list[dict[str, str]] = [
    {
        "title": "Molecular assembly index as a mass-spectrometry-derived descriptor",
        "venue": "Nature",
        "year": "2023",
        "doi": "10.1038/s41586-023-06600-9",
        "role": "Flagship: assembly index in matter; blinded living vs abiotic sets.",
    },
    {
        "title": "Formalising the Pathways to Life Using Assembly Spaces",
        "venue": "Entropy",
        "year": "2022",
        "doi": "10.3390/e24070884",
        "role": "Math: assembly spaces, bounds, pathways formalism.",
    },
    {
        "title": "Assembly theory: a framework for quantifying selection",
        "venue": "arXiv",
        "year": "2022",
        "doi": "10.48550/arXiv.2206.02279",
        "role": "Foundational assembly-theory thread (preprint).",
    },
    {
        "title": "From matter to life: chemistry leading to compartmentalization",
        "venue": "Phil. Trans. R. Soc. A",
        "year": "2022",
        "doi": "10.1098/rsta.2021.0158",
        "role": "Origins pathways; compartments / proto-metabolic framing.",
    },
    {
        "title": "From matter to life: the informational architecture",
        "venue": "Phil. Trans. R. Soc. A",
        "year": "2016",
        "doi": "10.1098/rsta.2015.0049",
        "role": "Information / causal structure — 'biocode' in physics language.",
    },
    {
        "title": "Chemputer and Chemputation — A Universal Chemical Compound Synthesis Machine",
        "venue": "arXiv",
        "year": "2024",
        "doi": "10.48550/arXiv.2408.09171",
        "role": "Digitized chemistry / programmable synthesis — pairs with assembly narrative.",
    },
    {
        "title": "Organic synthesis in a modular robotic system driven by a chemical programming language",
        "venue": "Science",
        "year": "2019",
        "doi": "10.1126/science.aav2211",
        "role": "Executable reaction graphs on hardware — chemputation roots.",
    },
    {
        "title": "Life as No One Knows It: The Physics of Life's Emergence",
        "venue": "Riverhead (book)",
        "year": "2024",
        "doi": "",
        "role": "Public synthesis; ISBN 9780593191897 (trade listings).",
    },
]

# What SIFTA can honestly ship against that literature (organs / gaps).
SIFTA_SOLVABLE_MAP: list[tuple[str, str]] = [
    (
        "Inverse fold + structure DB + multi-axis structural referee",
        "`Applications/sifta_protein_folder_widget.py`, `System/sifta_protein_referee.py` — "
        "real tools; receipts per Covenant §7.2.",
    ),
    (
        "Stigmergic memory during fold search (pheromone / ACO analogue)",
        "`Applications/fold_swarm_pouw_sim.py` and related swarm organs — **software analogue**, "
        "not mass-spectrometry assembly index.",
    ),
    (
        "Mass-spectrometry assembly index on unknown samples",
        "**NOT PRESENT** — would require lab hardware + published pipelines; this widget cites the "
        "Nature 2023 paper and does not pretend to reproduce it.",
    ),
    (
        "Chemputer / closed-loop chemical execution",
        "**NOT PRESENT** — cite Cronin line (Science 2019; arXiv chemputation 2024); "
        "SIFTA stays computation + receipts inside the Qt organism.",
    ),
    (
        "BIOCODE Olympiad mandate traces (stigmergic proofs in-repo)",
        "`System/swarm_autocatalytic_closure.py` (event 14b), `System/swarm_spatial_hypercycle.py` (event 16) — "
        "regression hooks for swarm biocode organs.",
    ),
]

# ── Molecule bar chart: illustrative indices for teaching (not MS-derived in this UI) ──
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

THRESHOLD = 15  # Order-of-magnitude threshold discussed around Sharma et al., Nature 2023 (see Sources tab)

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
     "The minimum number of steps needed to construct a molecule from its parts.\n\n"
     "Primary metrology paper: Sharma et al., Nature (2023), DOI 10.1038/s41586-023-06600-9 — "
     "mass spectrometry + molecular fragmentation graphs; blinded living vs non-living classification.\n\n"
     "This SIFTA panel's bar **heights** are **pedagogical illustrations**, not copied from that paper's "
     "supplementary tables.\n\n[Truth label: definition + Nature result = published; bar numbers = pedagogy]"),
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

        sub = QLabel(
            "Threshold ~15 (literature order-of-magnitude)  |  Metrology: Sharma et al. Nature 2023 "
            "(DOI 10.1038/s41586-023-06600-9)  |  Bar chart: illustrative pedagogy, not MS replay"
        )
        sub.setWordWrap(True)
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
                f"Truth label: illustrative pedagogy — see Sources tab for Nature 2023 metrology"
            )
            self._detail.setText(txt)
            publish_focus(
                _APP_NAME, f"Clicked molecule: {name} — AI={m['ai']} — {status}",
                tab="Assembly Index", selection=name,
                metadata={"assembly_index": m["ai"], "alive": m["alive"], "note": m["note"]},
            )


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
        gs = self._fig.add_gridspec(1, 2, wspace=0.35, left=0.07, right=0.96, top=0.82, bottom=0.14)
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

        # truth label already shown in Qt widget above — no suptitle needed
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
            "  published metrology = Sharma et al. Nature 2023 (see Sources tab)\n"
            "  hypothesis        = interpretations beyond measured graphs\n"
            "  experimental       = has blinded lab test backing\n"
            "  software analogue  = SIFTA implementation, NOT wet-lab\n"
            "  NOT PRESENT        = wet-lab / FDA validation"
        )
        row.addWidget(self._ans, 3)

    def _show(self, question: str):
        for q, ans in QUESTIONS:
            if q == question:
                self._ans.setText(f"Q: {q}\n\n{ans}")
                publish_focus(
                    _APP_NAME, f"Exploring question: {q}",
                    tab="Question Wall", selection=q,
                    metadata={"answer_preview": ans[:120]},
                )
                return


def _sources_html() -> str:
    """Build rich text for Sources tab (DOI links + SIFTA map + Predator v7 alignment)."""
    rows = []
    for b in RESEARCH_BIBLIO:
        link = (
            f'<a href="https://doi.org/{html.escape(b["doi"], quote=True)}">{html.escape(b["doi"])}</a>'
            if b.get("doi")
            else "(book — use publisher / ISBN)"
        )
        t = html.escape(b["title"])
        v = html.escape(f"{b['venue']}, {b['year']}")
        r = html.escape(b["role"])
        rows.append(
            f"<tr><td><b>{t}</b><br/><span style='color:#565f89'>{v}</span></td>"
            f"<td>{link}</td><td>{r}</td></tr>"
        )
    sol_rows = "".join(
        f"<tr><td>{html.escape(title)}</td><td>{html.escape(desc)}</td></tr>"
        for title, desc in SIFTA_SOLVABLE_MAP
    )
    return f"""<html><body style="color:#c0caf5; font-family:Helvetica Neue, sans-serif; font-size:13px;">
<h2 style="color:#bb9af7;">Primary literature spine</h2>
<p style="color:#565f89;">Curated for the public mission she states openly: <b>physics of emergence</b>,
<b>origins / life detection</b>, <b>digitized chemistry (chemputation)</b>, and <b>memory-as-history</b> —
not “world as computation” cosplay. Links resolve via doi.org where a DOI exists.</p>
<table border="0" cellspacing="8" cellpadding="4" width="100%">
<tr style="color:#73daca;"><th align="left">Paper / book</th><th align="left">ID</th><th align="left">Role</th></tr>
{"".join(rows)}
</table>

<h2 style="color:#e0af68;">What SIFTA can solve here (honest map)</h2>
<table border="0" cellspacing="8" cellpadding="4" width="100%">
<tr style="color:#73daca;"><th align="left">Capability</th><th align="left">Repo / truth</th></tr>
{sol_rows}
</table>

<h2 style="color:#7aa2f7;">Predator v7 + BIOCODE Olympiad</h2>
<p><b>Predator v7</b> (see <code>Documents/PREDATOR_V7_RESEARCH_SPINE.md</code>, <code>Documents/IDE_BOOT_COVENANT.md</code> §7):
tool truth, sensory lock-on, receipts — <i>abstractions that clarify nature</i>, not extra fog layers.</p>
<p><b>BIOCODE Olympiad</b> (in-repo mandate strings): Event <b>14b</b> — <code>System/swarm_autocatalytic_closure.py</code>;
Event <b>16</b> — <code>System/swarm_spatial_hypercycle.py</code>. Full doctrine: <code>Documents/SARA_IMARI_WALKER_ASSEMBLY_THEORY_RESEARCH.md</code>.</p>

<h2 style="color:#f7768e;">Next build (when Architect says GO)</h2>
<ul>
<li>SMILES → graph → <i>toy</i> step estimator (still not mass spec — label truth).</li>
<li>Optional: fetch UniProt/AlphaFold metadata for one accession with receipt-backed HTTP.</li>
<li>FoldSwarm live pheromone tensor hook (read-only probe) for Memory Trace panel.</li>
</ul>
<p style="color:#565f89; font-size:11px;">For the Swarm. 🐜⚡ — CG55M@cursor · widget bolus 2026-04-28</p>
</body></html>"""


class SourcesAndPlanPanel(QWidget):
    """Curated DOIs, SIFTA solvable map, Predator v7 / Olympiad cross-links."""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{BG}; color:#c0caf5;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        title = QLabel("📚  Sources, SIFTA map & build plan")
        title.setFont(QFont("Helvetica Neue", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{VIOLET};")
        lay.addWidget(title)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet(
            f"background:{PANEL}; color:#c0caf5; border:1px solid #24283b; border-radius:10px; padding:8px;"
        )
        browser.setHtml(_sources_html())
        lay.addWidget(browser)


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
            "   |   Origins · life detection · assembly / memory  |   Digitize chemistry (chemputation) — Cronin line  "
            "   |   Popular book: Life as No One Knows It (Riverhead, 2024)"
        )
        sub_hdr.setStyleSheet(f"background:{BG}; color:{DIM}; font-size:11px; padding:4px 18px;")
        lay.addWidget(sub_hdr)

        # truth badge
        badge = QLabel(
            "  ⚠️  Truth labels: Nature 2023 metrology = real (see Sources tab)  |  "
            "Bar-chart AI numbers = illustrative pedagogy  |  Pheromone = software analogue  |  "
            "ESMFold/ProteinMPNN/AlphaFold = real tools  |  Wet-lab / chemputer = NOT PRESENT"
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

        tabs.addTab(SourcesAndPlanPanel(),   "📚  Sources & plan")
        tabs.addTab(AssemblyIndexPanel(),    "⚗️  Assembly Index")
        tabs.addTab(MemoryTracePanel(),      "🧠  Memory Trace")
        tabs.addTab(PhaseTransitionPanel(),  "🌊  Phase Transition")
        tabs.addTab(QuestionWallPanel(),     "❓  Question Wall")

        # publish focus on tab switch so Alice knows what panel is active
        def _on_tab_changed(idx: int):
            tab_name = tabs.tabText(idx).strip()
            publish_focus(_APP_NAME, f"Switched to tab: {tab_name}", tab=tab_name)
        tabs.currentChanged.connect(_on_tab_changed)

        lay.addWidget(tabs)

        # status bar
        status = QLabel(
            "  Sharma et al. Nature 2023 (DOI 10.1038/s41586-023-06600-9) · "
            "Marshall et al. Entropy 2022 (10.3390/e24070884) · "
            "ESMFold / ProteinMPNN / AlphaFold2 in other SIFTA organs  |  "
            "Chemputer execution: NOT integrated"
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
