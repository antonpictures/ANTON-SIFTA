#!/usr/bin/env python3
"""
SIFTA ∥ OpenAI — Math-First AGI Benchmarks
============================================
Benchmark dashboard mapping OpenAI's stated math/research capability markers
(from Bubeck & Ryu / Andrew Mayne, "AI and Math") to what a local SIFTA node
can actually verify via ledgers, pytest, referees, and curated DOIs.

NOT a flame war — math problems are unambiguous; progress is verifiable.

Source: https://www.youtube.com/watch?v=9-TVwv6wtGQ

Truth labels (per Covenant §6/§7):
  long_context    = SIFTA uses persistent ledgers, not single 1M-token window
  autonomous_res  = GO-gated tournament loop + corpus exporters (partial)
  error_correct   = lysosome / referee / auditor lane (deterministic re-run)
  knowledge_inter = stigmergic bus + curated DOIs (no pretend PDF reads)
  verification    = pytest + py_compile + TM-score referees; NO Lean/Isabelle

No in-app Alice chat (§7.6). publish_focus only.
"""
from __future__ import annotations

import sys
import time
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPainter, QLinearGradient, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QFrame, QTextBrowser, QHeaderView,
    QProgressBar, QGridLayout, QScrollArea, QSizePolicy,
    QLineEdit,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_app_focus import publish_focus
from System.swarm_p_vs_np_millennium_gate import (
    OFFICIAL_SOURCES as P_VS_NP_OFFICIAL_SOURCES,
    assess_millennium_claim,
    run_verification_vs_search_demo,
)

_APP_NAME = "SIFTA ∥ OpenAI — Math Benchmarks"
_OFFSCREEN_RETAINED_WIDGETS: list[object] = []


def _offscreen_test_mode() -> bool:
    return (
        "pytest" in sys.modules
        or os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
    )

# ── Capability Markers ────────────────────────────────────────────────────
# From the Bubeck & Ryu episode, mapped to SIFTA truth.

CAPABILITY_MARKERS = [
    {
        "id": "long_context",
        "name": "Long-Context Reasoning",
        "episode_ref": "~12:36–13:16, ~23:05–23:45",
        "openai_claim": "Coherent thought over days–weeks, not seconds. "
                        "Sustained reasoning across a million-token window.",
        "sifta_anchor": "Persistent ledgers + hippocampus. 'Long' = cross-session "
                        "state + receipts, not one giant prompt.",
        "sifta_status": "PARTIAL",
        "prove_it": "Log each reasoning episode to ide_stigmergic_trace.jsonl; "
                    "measure continuity (same intent thread, hashes).",
        "gap": "No single 1M-token reasoning window. Cross-session state "
               "is ledger-based, not attention-based.",
    },
    {
        "id": "autonomous_research",
        "name": "Autonomous Research",
        "episode_ref": "~21:26–22:58, ~23:55–24:06",
        "openai_claim": "Systems that compress timelines on open problems; "
                        "toward publishable novelty.",
        "sifta_anchor": "Tournament loop, corpus exporters, protein/physics "
                        "engines — all GO-gated for promotion.",
        "sifta_status": "PARTIAL",
        "prove_it": "Define narrow problems (code-verified lemmas, regression "
                    "bounds) with pytest oracle + ledger row per attempt.",
        "gap": "Not autonomous publishing. No end-to-end paper generation.",
    },
    {
        "id": "error_correction",
        "name": "Error Correction",
        "episode_ref": "~12:52–13:12",
        "openai_claim": "Recover from a mistake in a long reasoning chain.",
        "sifta_anchor": "Lysosome / referee / Auditor lane; deterministic "
                        "re-run; immutable receipts show correction.",
        "sifta_status": "PRESENT",
        "prove_it": "Same proof attempt versioned in JSONL; diff tool outputs "
                    "stored under .sifta_state/ with truth_note.",
        "gap": "Correction is manual (Auditor lane), not yet fully autonomous.",
    },
    {
        "id": "knowledge_interconnection",
        "name": "Knowledge Interconnection",
        "episode_ref": "~16:53–17:23, ~32:58–33:04",
        "openai_claim": "Deep literature search across fields; hidden connections.",
        "sifta_anchor": "Stigmergic bus + curated docs (*.md spines) + "
                        "sanitized pulls only (§8 absorption).",
        "sifta_status": "PARTIAL",
        "prove_it": "Widget lists DOIs + repo paths; optional fetch only with "
                    "Architect-approved tool + receipt.",
        "gap": "No automated cross-field literature mining. Curated DOIs only.",
    },
    {
        "id": "verification",
        "name": "Proof Verification",
        "episode_ref": "~33:52–35:40",
        "openai_claim": "AI assists checking long formal proofs.",
        "sifta_anchor": "Formal verification of CODE (pytest, typecheck, "
                        "py_compile), TM-score / energy referees for structures.",
        "sifta_status": "PARTIAL",
        "prove_it": "Ship small certified lemmas (invariant proofs in Python) "
                    "+ link to human referee for math claims.",
        "gap": "No in-repo Lean/Isabelle pipeline. Code verification only, "
               "not formal mathematical proof checking.",
    },
]

# ── Scoped Problem Classes ────────────────────────────────────────────────

PROBLEM_CLASSES = [
    {
        "class": "In-Repo Certified",
        "description": "Numerical stability proofs, combinatorial bounds used by "
                       "swarm sims, explicit finite searches with reproducible seeds.",
        "status": "ACTIVE",
        "examples": [
            "Proof-of-property guards (swarm_stigmergic_dialogue, inference_economy)",
            "Halving algorithm convergence (STGM deflationary schedule)",
            "Finite search: swimmer population equilibrium bounds",
        ],
    },
    {
        "class": "Open-Problem Tracking",
        "description": "Ledger of claims — famous conjectures — status = open / "
                       "referenced / not attempted. Any progress row must attach "
                       "artifact path + test command.",
        "status": "PLANNED",
        "examples": [
            "Collatz conjecture — status: NOT ATTEMPTED (no artifact)",
            "P vs NP — status: REFERENCED (literature spine only)",
            "Protein folding energy landscape — status: ACTIVE (FoldSwarm referee)",
        ],
    },
    {
        "class": "Physics / Bio Bridge",
        "description": "Use existing organs (assembly spine, protein referee, "
                       "LJ/PoUW demos) as applied math stories.",
        "status": "ACTIVE",
        "examples": [
            "Assembly index metrology (Nature 2023) — illustrative bar chart",
            "Protein TM-score validation (ESMFold / MPNN / AF2)",
            "Lennard-Jones energy minimization (PoUW sim)",
        ],
    },
]

# ── Episode Chapters ──────────────────────────────────────────────────────

EPISODE_CHAPTERS = [
    ("03:01", "Open problem with ChatGPT"),
    ("06:57", "Research-level math"),
    ("11:32", "Why math for AGI"),
    ("21:26", "Automated researcher"),
    ("28:19", "Humans as models improve"),
    ("33:52", "Verifying proofs with AI"),
    ("36:00", "Shallow understanding risk"),
]

VIDEO_URL = "https://www.youtube.com/watch?v=9-TVwv6wtGQ"

# ── HuggingFace dataset IDs ───────────────────────────────────────────────
_GSM8K_ID = "openai/gsm8k"
_MATH_ID = "qwedsacf/competition_math"

# ═══════════════════════════════════════════════════════════════════════════
#  Live ledger readers
# ═══════════════════════════════════════════════════════════════════════════

def _count_proof_guards() -> int:
    """Count proof_of_property functions across the repo."""
    count = 0
    for py in _REPO.rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
            count += text.count("def proof_of_property")
        except Exception:
            pass
    return count


def _count_ledger_lines() -> int:
    """Count lines in the canonical repair_log.jsonl."""
    ledger = _REPO / "repair_log.jsonl"
    if not ledger.exists():
        return 0
    try:
        with ledger.open() as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _count_pytest_files() -> int:
    """Count test files in tests/."""
    tests_dir = _REPO / "tests"
    if not tests_dir.is_dir():
        return 0
    return len(list(tests_dir.glob("test_*.py")))


def _get_wallet_balance() -> float:
    """Get Alice's canonical wallet balance."""
    try:
        from System.warren_buffett import alice_wallet_balance, _local_serial
        return float(alice_wallet_balance(_local_serial()))
    except Exception:
        return 0.0


def _count_organs() -> int:
    """Count System/*.py organ modules."""
    sys_dir = _REPO / "System"
    if not sys_dir.is_dir():
        return 0
    return len([f for f in sys_dir.glob("*.py") if not f.name.startswith("__")])


# ═══════════════════════════════════════════════════════════════════════════
#  Arena: HuggingFace dataset loader + local Ollama solver
# ═══════════════════════════════════════════════════════════════════════════

import re
import random
import threading
import urllib.request
import urllib.error


def _extract_gsm8k_answer(answer_text: str) -> str:
    """Extract the final numeric answer from GSM8K '#### N' format."""
    m = re.search(r"####\s*(.+)", answer_text)
    return m.group(1).strip().replace(",", "") if m else ""


def _extract_number_from_response(text: str) -> str:
    """Extract the last number from an LLM response."""
    # Look for #### pattern first (if model mimics GSM8K format)
    m = re.search(r"####\s*(.+)", text)
    if m:
        return m.group(1).strip().replace(",", "")
    # Fall back to last number in text
    numbers = re.findall(r"-?\d+(?:\.\d+)?", text)
    return numbers[-1] if numbers else ""


def _hf_fetch_rows(dataset: str, split: str, offset: int, length: int,
                   config: str = "default", timeout: float = 8.0) -> list:
    """Fetch rows from HuggingFace Datasets Viewer API. No library needed.
    Returns list of row dicts, or [] on failure.
    """
    import urllib.request
    import urllib.parse
    params = urllib.parse.urlencode({
        "dataset": dataset,
        "config": config,
        "split": split,
        "offset": offset,
        "length": length,
    })
    url = f"https://datasets-server.huggingface.co/rows?{params}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        return [r["row"] for r in data.get("rows", [])]
    except Exception as exc:
        return [{"__hf_error": str(exc)}]


def _load_gsm8k_sample(n: int = 5) -> list:
    """Load n random GSM8K problems via HF API (fast, no library download)."""
    # GSM8K test split has 1319 rows
    offset = random.randint(0, max(0, 1319 - n))
    rows = _hf_fetch_rows("openai/gsm8k", "test", offset, n, config="main")
    if rows and "__hf_error" in rows[0]:
        # Fallback: try datasets library
        try:
            from datasets import load_dataset  # type: ignore
            ds = load_dataset("openai/gsm8k", "main", split="test")
            indices = random.sample(range(len(ds)), min(n, len(ds)))
            return [
                {
                    "source": "GSM8K",
                    "idx": i,
                    "question": ds[i]["question"],
                    "gold_answer": _extract_gsm8k_answer(ds[i]["answer"]),
                    "full_solution": ds[i]["answer"],
                }
                for i in indices
            ]
        except Exception as e:
            return [{"source": "GSM8K", "error": f"HF API: {rows[0]['__hf_error']} | lib: {e}"}]
    result = []
    for row in rows:
        if "question" not in row:
            continue
        result.append({
            "source": "GSM8K",
            "question": row["question"],
            "gold_answer": _extract_gsm8k_answer(row.get("answer", "")),
            "full_solution": row.get("answer", ""),
        })
    return result or [{"source": "GSM8K", "error": "No rows returned from HF API"}]


def _load_math_sample(n: int = 3) -> list:
    """Load n random MATH competition problems via HF API."""
    # lighteval/MATH has 12500 train rows
    offset = random.randint(0, max(0, 12500 - n))
    rows = _hf_fetch_rows("lighteval/MATH", "train", offset, n)
    if rows and "__hf_error" in rows[0]:
        try:
            from datasets import load_dataset  # type: ignore
            ds = load_dataset("lighteval/MATH", split="train")
            indices = random.sample(range(len(ds)), min(n, len(ds)))
            return [
                {
                    "source": "MATH",
                    "idx": i,
                    "question": ds[i]["problem"],
                    "level": ds[i].get("level", "?"),
                    "type": ds[i].get("type", "?"),
                    "gold_answer": ds[i].get("solution", ""),
                }
                for i in indices
            ]
        except Exception as e:
            return [{"source": "MATH", "error": f"HF API: {rows[0]['__hf_error']} | lib: {e}"}]
    result = []
    for row in rows:
        question_key = next((k for k in ("problem", "question", "Problem") if k in row), None)
        if not question_key:
            continue
        result.append({
            "source": "MATH",
            "question": row[question_key],
            "level": row.get("level", "?"),
            "type": row.get("type", "?"),
            "gold_answer": row.get("solution", row.get("answer", "")),
        })
    return result or [{"source": "MATH", "error": "No rows returned from HF API"}]



def _ollama_solve(question: str, timeout_s: float = 15.0) -> str:
    """Ask local Ollama to solve a math problem. Returns raw response."""
    try:
        from System.sifta_inference_defaults import resolve_ollama_model
        model = resolve_ollama_model(app_context="math_benchmark")
    except Exception:
        import os
        model = os.environ.get("SIFTA_DEFAULT_OLLAMA_MODEL", "alice-m5-cortex-8b-6.3gb:latest")

    prompt = (
        f"Solve this math problem step by step. "
        f"At the very end, write your final numeric answer after '#### '.\n\n"
        f"Problem: {question}\n\nSolution:"
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 512},
    }).encode()

    url = "http://127.0.0.1:11434/api/chat"
    req = urllib.request.Request(url, data=body,
                                headers={"Content-Type": "application/json"},
                                method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read())
        return (data.get("message") or {}).get("content", "").strip()
    except Exception as e:
        return f"[OLLAMA ERROR] {e}"


def _log_arena_result(problem: dict, response: str, correct: bool) -> None:
    """Write a receipt to the arena ledger."""
    ledger = _REPO / ".sifta_state" / "math_arena_results.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "source": problem.get("source", "?"),
        "idx": problem.get("idx", -1),
        "question_preview": problem.get("question", "")[:100],
        "gold_answer": problem.get("gold_answer", ""),
        "model_answer": _extract_number_from_response(response),
        "correct": correct,
        "model_response_len": len(response),
    }
    try:
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  Widget
# ═══════════════════════════════════════════════════════════════════════════

# Colors
_CYAN = "#00ffc8"
_AMBER = "#e0af68"
_RED = "#f7768e"
_GREEN = "#9ece6a"
_PURPLE = "#bb9af7"
_BLUE = "#7aa2f7"
_DIM = "#565f89"
_BG = "#080a12"
_BG2 = "#0c0a14"
_BG3 = "#191626"
_BORDER = "#2d2a41"


def _status_color(status: str) -> str:
    if status == "PRESENT":
        return _GREEN
    if status == "PARTIAL":
        return _AMBER
    if status == "PLANNED":
        return _BLUE
    return _RED


def _make_section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
    lbl.setStyleSheet(f"color: {_CYAN}; padding: 8px 2px 4px 2px;")
    return lbl


def _make_card(title: str, body_widget: QWidget) -> QFrame:
    card = QFrame()
    card.setStyleSheet(
        f"QFrame {{ background: {_BG2}; border: 1px solid {_BORDER}; "
        f"border-radius: 8px; }}"
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(12, 10, 12, 10)
    lay.setSpacing(6)
    t = QLabel(title)
    t.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
    t.setStyleSheet(f"color: {_PURPLE}; border: none;")
    lay.addWidget(t)
    body_widget.setStyleSheet("border: none;")
    lay.addWidget(body_widget)
    return card


class MathBenchmarkWidget(QWidget):
    """SIFTA ∥ OpenAI — Math-First AGI Benchmark Dashboard."""

    APP_NAME = _APP_NAME
    _live_snapshot_ready = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            QWidget {{ background: {_BG}; color: #c8d2f0; font-family: 'Menlo', monospace; }}
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgb(50,42,65), stop:1 rgb(30,25,42));
                border: 1px solid {_BORDER}; border-radius: 6px;
                padding: 6px 14px; color: #c8d2f0; font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ border-color: {_CYAN}; }}
            QTabWidget::pane {{ border: 1px solid {_BORDER}; background: {_BG2}; }}
            QTabBar::tab {{
                background: {_BG3}; color: {_DIM};
                border: 1px solid {_BORDER}; padding: 7px 18px; font-size: 10px;
            }}
            QTabBar::tab:selected {{ background: {_BG2}; color: {_CYAN}; border-bottom-color: {_CYAN}; }}
        """)

        self._arena_problems: list = []
        self._arena_results: list = []
        self._arena_running = False
        self._arena_loaded = False
        self._live_tab_seen = False
        self._live_refreshing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Title
        title_row = QHBoxLayout()
        title = QLabel("SIFTA ∥ OpenAI — Math-First AGI Benchmarks")
        title.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {_CYAN};")
        title_row.addWidget(title)
        title_row.addStretch()

        self._status_lbl = QLabel("Scanning…")
        self._status_lbl.setStyleSheet(f"color: {_DIM}; font-size: 10px;")
        title_row.addWidget(self._status_lbl)
        root.addLayout(title_row)

        subtitle = QLabel(
            "OpenAI researchers defined capability markers for math-driven AGI. "
            "We map each to what a local SIFTA node can verify — honestly."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {_DIM}; font-size: 10px; padding: 0 2px 6px 2px;")
        root.addWidget(subtitle)

        # Tabs
        tabs = QTabWidget()
        self._tabs = tabs
        tabs.addTab(self._build_capability_tab(), "Capability Matrix")
        tabs.addTab(self._build_arena_tab(), "⚔ Arena")
        tabs.addTab(self._build_problems_tab(), "Problem Classes")
        tabs.addTab(self._build_millennium_tab(), "🏛 P vs NP Gate")
        tabs.addTab(self._build_live_tab(), "Live Proofs")
        tabs.addTab(self._build_source_tab(), "Sources & Plan")
        tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(tabs, 1)

        publish_focus(_APP_NAME, "Math benchmark organ opened", tab="Capability Matrix")

        self._live_snapshot_ready.connect(self._apply_live_snapshot)

        # Refresh live data every 30s, but only after the Live Proofs tab was
        # opened once. Startup must paint immediately; proof scans are real
        # filesystem/ledger reads and do not belong on the first frame.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(
            lambda: self._refresh_live() if self._live_tab_seen else None
        )
        self._refresh_timer.start(30_000)

        # Arena pull deferred until first visit — NOT at init.
        # (HF pull at init freezes the widget even before Arena is opened.)
        self._arena_tab_seen: bool = False

        self._status_lbl.setText("Ready")

    def _on_tab_changed(self, idx: int) -> None:
        tab = self._tabs.tabText(idx) if 0 <= idx < self._tabs.count() else "?"
        publish_focus(_APP_NAME, f"Math benchmark tab selected: {tab}", tab=tab)
        if tab == "Live Proofs":
            self._live_tab_seen = True
            self._refresh_live()
        # Arena: auto-pull only on FIRST visit, not at widget init.
        if "⚔" in tab and not self._arena_tab_seen:
            self._arena_tab_seen = True
            QTimer.singleShot(200, self._arena_auto_pull)


    # ── Tab: Capability Matrix ────────────────────────────────────────

    def _build_capability_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setSpacing(10)
        lay.setContentsMargins(8, 8, 8, 8)

        for m in CAPABILITY_MARKERS:
            card = self._marker_card(m)
            lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(container)
        return scroll

    # ── Tab: P vs NP / Clay Millennium Gate ───────────────────────────

    def _build_millennium_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setSpacing(10)
        lay.setContentsMargins(8, 8, 8, 8)

        lay.addWidget(_make_section_label("🏛 P vs NP — Millennium Proof Hygiene Gate"))

        desc = QLabel(
            "This panel is deliberately conservative. It can run SAT verification/search "
            "demos and gate prize language. It cannot certify a Clay Mathematics "
            "Institute solution."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {_AMBER}; font-size: 10px;")
        lay.addWidget(desc)

        source_lines = "\n".join(
            f"{name}: {url}" for name, url in P_VS_NP_OFFICIAL_SOURCES.items()
        )
        src = QLabel(source_lines)
        src.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        src.setWordWrap(True)
        src.setStyleSheet(f"color: {_DIM}; font-size: 9px;")
        lay.addWidget(_make_card("Official Clay Sources", src))

        claim_row = QHBoxLayout()
        self._pvsnp_claim = QLineEdit()
        self._pvsnp_claim.setPlaceholderText("Type a claim to gate, e.g. 'we solved P vs NP'")
        self._pvsnp_claim.setText("We solved P vs NP and won the million dollar prize.")
        self._pvsnp_claim.setStyleSheet(
            f"background: {_BG2}; color: #c8d2f0; border: 1px solid {_BORDER}; "
            "border-radius: 6px; padding: 7px;"
        )
        claim_row.addWidget(self._pvsnp_claim, 1)

        gate_btn = QPushButton("Gate Claim")
        gate_btn.clicked.connect(self._pvsnp_gate_claim)
        claim_row.addWidget(gate_btn)

        demo_btn = QPushButton("Run SAT Demo")
        demo_btn.clicked.connect(self._pvsnp_run_demo)
        claim_row.addWidget(demo_btn)
        lay.addLayout(claim_row)

        self._pvsnp_output = QTextBrowser()
        self._pvsnp_output.setStyleSheet(
            f"QTextBrowser {{ background: {_BG2}; color: #c8d2f0; "
            f"border: 1px solid {_BORDER}; border-radius: 6px; "
            f"font-family: 'Menlo'; font-size: 10px; padding: 10px; }}"
        )
        self._pvsnp_output.setPlainText(
            "Ready. Gate a claim or run the SAT demo.\n\n"
            "Truth boundary: SAT demos are useful engineering evidence, not a Clay proof."
        )
        lay.addWidget(self._pvsnp_output, 1)

        scroll.setWidget(container)
        return scroll

    def _pvsnp_gate_claim(self) -> None:
        claim = self._pvsnp_claim.text().strip()
        result = assess_millennium_claim(claim, write=True)
        self._pvsnp_output.setPlainText(json.dumps(result, indent=2, ensure_ascii=False))
        publish_focus(_APP_NAME, f"P vs NP claim gate: {result['verdict']}", tab="P vs NP Gate")

    def _pvsnp_run_demo(self) -> None:
        result = run_verification_vs_search_demo(write=True)
        self._pvsnp_output.setPlainText(json.dumps(result, indent=2, ensure_ascii=False))
        publish_focus(_APP_NAME, "P vs NP SAT verification/search demo receipt written", tab="P vs NP Gate")

    def _marker_card(self, m: dict) -> QFrame:
        card = QFrame()
        sc = _status_color(m["sifta_status"])
        card.setStyleSheet(
            f"QFrame {{ background: {_BG2}; border: 1px solid {_BORDER}; "
            f"border-left: 3px solid {sc}; border-radius: 8px; }}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)

        # Header row
        hdr = QHBoxLayout()
        name = QLabel(m["name"])
        name.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        name.setStyleSheet(f"color: {_CYAN}; border: none;")
        hdr.addWidget(name)
        hdr.addStretch()

        badge = QLabel(f"  {m['sifta_status']}  ")
        badge.setStyleSheet(
            f"background: {sc}22; color: {sc}; border: 1px solid {sc}44; "
            f"border-radius: 4px; font-size: 9px; font-weight: bold; padding: 2px 8px;"
        )
        hdr.addWidget(badge)

        ep = QLabel(f"Episode: {m['episode_ref']}")
        ep.setStyleSheet(f"color: {_DIM}; font-size: 9px; border: none;")
        hdr.addWidget(ep)
        lay.addLayout(hdr)

        # OpenAI claim
        row_oa = QLabel(f"OpenAI thesis: {m['openai_claim']}")
        row_oa.setWordWrap(True)
        row_oa.setStyleSheet(f"color: {_AMBER}; font-size: 10px; border: none; padding: 2px 0;")
        lay.addWidget(row_oa)

        # SIFTA anchor
        row_s = QLabel(f"SIFTA anchor: {m['sifta_anchor']}")
        row_s.setWordWrap(True)
        row_s.setStyleSheet(f"color: {_GREEN}; font-size: 10px; border: none; padding: 2px 0;")
        lay.addWidget(row_s)

        # Prove-it path
        row_p = QLabel(f"Prove it: {m['prove_it']}")
        row_p.setWordWrap(True)
        row_p.setStyleSheet(f"color: #c8d2f0; font-size: 9px; border: none;")
        lay.addWidget(row_p)

        # Gap (honest annotation — not an error, so not red)
        row_g = QLabel(f"◦ Gap: {m['gap']}")
        row_g.setWordWrap(True)
        row_g.setStyleSheet(f"color: {_DIM}; font-size: 9px; border: none; padding: 2px 0; font-style: italic;")
        lay.addWidget(row_g)

        return card

    # ── Tab: Arena (live HuggingFace → Ollama → Verify) ───────────────

    def _build_arena_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setSpacing(8)
        lay.setContentsMargins(8, 8, 8, 8)

        lay.addWidget(_make_section_label(
            "⚔ Arena — Pull → Solve → Verify → Receipt"
        ))

        desc = QLabel(
            "Pulls real math problems from HuggingFace (GSM8K + MATH) only "
            "when requested. Sends to local Ollama. Verifies answers. "
            "Logs receipts to .sifta_state/math_arena_results.jsonl."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {_DIM}; font-size: 10px; padding: 0 0 8px 0;")
        lay.addWidget(desc)

        # Controls — single Reload + Solve All
        ctrl = QHBoxLayout()

        self._btn_reload = QPushButton("🔄 Reload")
        self._btn_reload.setToolTip("Clear table and pull a fresh batch of problems.")
        self._btn_reload.clicked.connect(self._arena_reload)
        ctrl.addWidget(self._btn_reload)

        self._btn_solve = QPushButton("🧠 Solve All")
        self._btn_solve.clicked.connect(self._arena_solve_all)
        self._btn_solve.setEnabled(False)
        ctrl.addWidget(self._btn_solve)

        ctrl.addStretch()

        self._arena_score = QLabel("Score: —")
        self._arena_score.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        self._arena_score.setStyleSheet(f"color: {_CYAN};")
        ctrl.addWidget(self._arena_score)
        lay.addLayout(ctrl)

        # Results table
        self._arena_table = QTableWidget(0, 5)
        self._arena_table.setHorizontalHeaderLabels([
            "Source", "Question", "Gold", "Model", "✓"
        ])
        self._arena_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._arena_table.setStyleSheet(
            f"QTableWidget {{ background: {_BG2}; border: 1px solid {_BORDER}; "
            f"font-size: 9px; color: #c8d2f0; gridline-color: {_BORDER}; }}"
            f"QHeaderView::section {{ background: {_BG3}; color: {_CYAN}; "
            f"border: 1px solid {_BORDER}; font-size: 9px; font-weight: bold; padding: 4px; }}"
        )
        lay.addWidget(self._arena_table, 1)

        # Status
        self._arena_status = QLabel("Ready. Hit Reload to pull GSM8K + MATH problems.")
        self._arena_status.setStyleSheet(f"color: {_DIM}; font-size: 10px;")
        lay.addWidget(self._arena_status)

        scroll.setWidget(container)
        return scroll

    def _arena_auto_pull(self) -> None:
        """Pull a mixed batch: 5 GSM8K + 3 MATH. User-triggered only."""
        self._arena_problems = []
        self._arena_results = []
        self._arena_table.setRowCount(0)
        self._arena_score.setText("Score: —")
        self._arena_status.setText("Pulling 5 GSM8K + 3 MATH from HuggingFace…")
        self._btn_reload.setEnabled(False)
        self._btn_solve.setEnabled(False)

        def _worker():
            gsm = _load_gsm8k_sample(5)
            math = _load_math_sample(3)
            QTimer.singleShot(0, lambda: self._arena_on_pulled(gsm + math))

        threading.Thread(target=_worker, daemon=True).start()

    def _arena_reload(self) -> None:
        """Clear table and pull a fresh batch."""
        self._arena_auto_pull()


    def _arena_pull(self, source: str, n: int) -> None:
        """Pull problems from HuggingFace in background thread (legacy path)."""
        self._arena_status.setText(f"Pulling {n} problems from {source.upper()}…")
        publish_focus(_APP_NAME, f"Pulling {n} {source.upper()} problems from HuggingFace",
                      tab="Arena")

        def _worker():
            if source == "gsm8k":
                problems = _load_gsm8k_sample(n)
            else:
                problems = _load_math_sample(n)
            QTimer.singleShot(0, lambda: self._arena_on_pulled(problems))

        threading.Thread(target=_worker, daemon=True).start()

    def _arena_on_pulled(self, problems: list) -> None:
        if hasattr(self, "_btn_reload"):
            self._btn_reload.setEnabled(True)

        # Separate good problems from error sentinels
        good = [p for p in problems if "error" not in p]
        errors = [p for p in problems if "error" in p]

        # Show errors as red rows in the table so they can't be missed
        for ep in errors:
            row = self._arena_table.rowCount()
            self._arena_table.insertRow(row)
            src_item = QTableWidgetItem(ep.get("source", "?"))
            src_item.setForeground(QColor("#f7768e"))
            err_item = QTableWidgetItem(f"⚠ {ep['error']}")
            err_item.setForeground(QColor("#f7768e"))
            self._arena_table.setItem(row, 0, src_item)
            self._arena_table.setItem(row, 1, err_item)
            self._arena_table.setItem(row, 2, QTableWidgetItem(""))
            self._arena_table.setItem(row, 3, QTableWidgetItem(""))
            self._arena_table.setItem(row, 4, QTableWidgetItem("✗"))

        if not good:
            self._arena_status.setText(
                f"⚠ Pull failed for all sources. Check HuggingFace network / datasets package. Hit Reload to retry."
            )
            return

        self._arena_problems.extend(good)
        self._btn_solve.setEnabled(True)

        # Update table with good problems
        for p in good:
            row = self._arena_table.rowCount()
            self._arena_table.insertRow(row)
            self._arena_table.setItem(row, 0, QTableWidgetItem(p.get("source", "?")))
            q = p.get("question", "")[:80] + ("…" if len(p.get("question", "")) > 80 else "")
            self._arena_table.setItem(row, 1, QTableWidgetItem(q))
            self._arena_table.setItem(row, 2, QTableWidgetItem(
                str(p.get("gold_answer", ""))[:30]
            ))
            self._arena_table.setItem(row, 3, QTableWidgetItem("—"))
            self._arena_table.setItem(row, 4, QTableWidgetItem("⏳"))

        self._arena_status.setText(
            f"Pulled {len(good)} problems. Total queue: {len(self._arena_problems)}. "
            f"Hit 'Solve All' to send to local Gemma4."
        )


    def _arena_solve_all(self) -> None:
        """Solve all queued problems one by one in background."""
        if self._arena_running or not self._arena_problems:
            return
        self._arena_running = True
        self._btn_solve.setEnabled(False)
        self._arena_results = []
        self._arena_status.setText("Solving… (local Gemma4 via Ollama)")
        publish_focus(_APP_NAME, f"Solving {len(self._arena_problems)} math problems",
                      tab="Arena")

        problems = list(self._arena_problems)

        def _worker():
            for i, p in enumerate(problems):
                if "error" in p:
                    continue
                question = p.get("question", "")
                response = _ollama_solve(question, timeout_s=30.0)
                model_answer = _extract_number_from_response(response)
                gold = str(p.get("gold_answer", "")).strip()

                # For GSM8K: exact numeric match
                correct = False
                if p.get("source") == "GSM8K":
                    correct = model_answer == gold
                else:
                    # MATH: just check if the model_answer appears in gold solution
                    correct = model_answer != "" and model_answer in gold

                _log_arena_result(p, response, correct)

                result = {
                    "idx": i,
                    "model_answer": model_answer,
                    "correct": correct,
                    "response_preview": response[:100],
                }
                QTimer.singleShot(0, lambda r=result: self._arena_on_solved(r))

            QTimer.singleShot(0, self._arena_on_done)

        threading.Thread(target=_worker, daemon=True).start()

    def _arena_on_solved(self, result: dict) -> None:
        idx = result["idx"]
        if idx < self._arena_table.rowCount():
            self._arena_table.setItem(idx, 3, QTableWidgetItem(
                result["model_answer"] or "∅"
            ))
            if result["correct"]:
                item = QTableWidgetItem("✅")
                item.setForeground(QColor(_GREEN))
            else:
                item = QTableWidgetItem("❌")
                item.setForeground(QColor(_RED))
            self._arena_table.setItem(idx, 4, item)

        self._arena_results.append(result)
        total = len(self._arena_problems)
        done = len(self._arena_results)
        correct = sum(1 for r in self._arena_results if r["correct"])
        self._arena_score.setText(f"Score: {correct}/{done}")
        self._arena_status.setText(f"Solving… {done}/{total}")

    def _arena_on_done(self) -> None:
        self._arena_running = False
        self._btn_solve.setEnabled(True)
        total = len(self._arena_results)
        correct = sum(1 for r in self._arena_results if r["correct"])
        pct = (correct / total * 100) if total else 0
        sc = _GREEN if pct >= 70 else _AMBER if pct >= 40 else _RED
        self._arena_score.setText(f"Score: {correct}/{total} ({pct:.0f}%)")
        self._arena_score.setStyleSheet(f"color: {sc}; font-weight: bold;")
        self._arena_status.setText(
            f"Done. {correct}/{total} correct ({pct:.0f}%). "
            f"Receipts logged to .sifta_state/math_arena_results.jsonl"
        )
        self._arena_problems.clear()
        publish_focus(_APP_NAME, f"Arena complete: {correct}/{total} ({pct:.0f}%)", tab="Arena")

    # ── Tab: Problem Classes ──────────────────────────────────────────

    def _build_problems_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setSpacing(10)
        lay.setContentsMargins(8, 8, 8, 8)

        lay.addWidget(_make_section_label("Scoped Problem Classes — \"Do Not Cosplay Fields Medals\""))

        for pc in PROBLEM_CLASSES:
            sc = _status_color(pc["status"])
            body = QWidget()
            bl = QVBoxLayout(body)
            bl.setSpacing(4)
            bl.setContentsMargins(0, 0, 0, 0)

            badge = QLabel(f"  {pc['status']}  ")
            badge.setStyleSheet(
                f"background: {sc}22; color: {sc}; border: 1px solid {sc}44; "
                f"border-radius: 4px; font-size: 9px; font-weight: bold; "
                f"padding: 2px 8px; max-width: 80px;"
            )
            bl.addWidget(badge)

            desc = QLabel(pc["description"])
            desc.setWordWrap(True)
            desc.setStyleSheet(f"color: #c8d2f0; font-size: 10px;")
            bl.addWidget(desc)

            for ex in pc["examples"]:
                exl = QLabel(f"  • {ex}")
                exl.setWordWrap(True)
                exl.setStyleSheet(f"color: {_DIM}; font-size: 9px;")
                bl.addWidget(exl)

            card = _make_card(pc["class"], body)
            card.setStyleSheet(
                card.styleSheet().replace(
                    f"border: 1px solid {_BORDER}",
                    f"border: 1px solid {_BORDER}; border-left: 3px solid {sc}"
                )
            )
            lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(container)
        return scroll

    # ── Tab: Live Proofs ──────────────────────────────────────────────

    def _build_live_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setSpacing(10)
        lay.setContentsMargins(8, 8, 8, 8)

        lay.addWidget(_make_section_label("Live SIFTA Proof Inventory"))

        desc = QLabel(
            "These are real, live numbers read from this node's canonical ledgers and "
            "file system. They are refreshed lazily so the app can open first; "
            "they are never hardcoded."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {_DIM}; font-size: 10px; padding: 0 0 8px 0;")
        lay.addWidget(desc)

        grid = QGridLayout()
        grid.setSpacing(8)

        self._live_labels: Dict[str, QLabel] = {}
        metrics = [
            ("proof_guards", "Proof-of-Property Guards", "Deterministic invariant checks across System/"),
            ("ledger_lines", "Canonical Ledger Lines", "Rows in repair_log.jsonl (STGM quorum)"),
            ("test_files", "Pytest Test Files", "Test modules in tests/"),
            ("organs", "System Organs", "Python modules in System/"),
            ("wallet", "Alice Wallet (STGM)", "Canonical balance from ledger_balance()"),
        ]
        for i, (key, title, desc_text) in enumerate(metrics):
            # Value
            val = QLabel("…")
            val.setFont(QFont("Menlo", 18, QFont.Weight.Bold))
            val.setStyleSheet(f"color: {_CYAN};")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._live_labels[key] = val

            # Title + desc
            t = QLabel(title)
            t.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
            t.setStyleSheet(f"color: {_PURPLE};")
            d = QLabel(desc_text)
            d.setStyleSheet(f"color: {_DIM}; font-size: 9px;")
            d.setWordWrap(True)

            cell = QFrame()
            cell.setStyleSheet(
                f"QFrame {{ background: {_BG2}; border: 1px solid {_BORDER}; border-radius: 8px; }}"
            )
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(12, 10, 12, 10)
            cl.addWidget(val)
            cl.addWidget(t)
            cl.addWidget(d)

            row_idx = i // 3
            col_idx = i % 3
            grid.addWidget(cell, row_idx, col_idx)

        lay.addLayout(grid)

        # Doctrine reminder
        doctrine = QLabel(
            "§ Covenant §7.3: Body Economy Honesty — these numbers are live recomputed, "
            "not stale tail-of-ledger snapshots."
        )
        doctrine.setWordWrap(True)
        doctrine.setStyleSheet(f"color: {_AMBER}; font-size: 9px; padding: 12px 0 0 0;")
        lay.addWidget(doctrine)

        lay.addStretch()
        scroll.setWidget(container)
        return scroll

    # ── Tab: Sources & Plan ───────────────────────────────────────────

    def _build_source_tab(self) -> QWidget:
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet(
            f"QTextBrowser {{ background: {_BG2}; color: #c8d2f0; "
            f"border: 1px solid {_BORDER}; border-radius: 6px; "
            f"font-family: 'Menlo'; font-size: 10px; padding: 12px; }}"
        )

        chapters_html = "".join(
            f"<tr><td style='color:{_CYAN};padding:3px 12px 3px 0;'>{ts}</td>"
            f"<td style='color:#c8d2f0;'>{title}</td></tr>"
            for ts, title in EPISODE_CHAPTERS
        )

        html = f"""
        <h3 style="color:{_CYAN};">Primary Source</h3>
        <p><a href="{VIDEO_URL}" style="color:{_BLUE};">
        Andrew Mayne — AI and Math (Bubeck &amp; Ryu)</a></p>
        <p style="color:{_DIM};">YouTube — chapters roughly:</p>
        <table>{chapters_html}</table>

        <h3 style="color:{_CYAN}; margin-top:16px;">SIFTA Doctrine</h3>
        <ul>
        <li style="color:{_AMBER};">§7.5 Python-first embedded QWidget — no browser escape</li>
        <li style="color:{_AMBER};">§7.6 No second Alice chat in-app — publish_focus only</li>
        <li style="color:{_AMBER};">§4 Predator Gate — any automated researcher loop must register</li>
        <li style="color:{_AMBER};">§1 Never fake proof — say exactly what is missing</li>
        </ul>

        <h3 style="color:{_CYAN}; margin-top:16px;">Cross-Links</h3>
        <ul>
        <li><span style="color:{_GREEN};">PREDATOR_V7_RESEARCH_SPINE.md</span> — plan item 8</li>
        <li><span style="color:{_GREEN};">IDE_BOOT_COVENANT.md</span> — §14 updated</li>
        <li><span style="color:{_GREEN};">SARA_IMARI_WALKER_ASSEMBLY_THEORY_RESEARCH.md</span> — chemistry bridge</li>
        <li><span style="color:{_GREEN};">ALICE_CORTEX_TOURNAMENT_v1.md</span> — ML paper spine</li>
        </ul>

        <h3 style="color:{_CYAN}; margin-top:16px;">Naming</h3>
        <p style="color:{_DIM};">
        Prefer <b>"Benchmarks: SIFTA ∥ OpenAI criteria"</b> if "vs" reads as hostile.
        Body copy states: OpenAI researchers defined useful markers — we implement
        the subset that a local OS can verify.
        </p>

        <h3 style="color:{_CYAN}; margin-top:16px;">Gap Acknowledgment</h3>
        <p style="color:{_RED};">
        <b>No in-repo Lean 4 / Isabelle pipeline.</b> Formal mathematical proof
        verification requires a proof assistant we do not currently ship. Code
        verification (pytest, py_compile, typecheck) is present. Mathematical
        proof checking is NOT.
        </p>
        """
        browser.setHtml(html)
        return browser

    # ── Live refresh ──────────────────────────────────────────────────

    def _refresh_live(self) -> None:
        if self._live_refreshing:
            return
        self._live_refreshing = True
        self._status_lbl.setText("Scanning proofs…")

        def _worker() -> None:
            snapshot: Dict[str, Any] = {}
            try:
                snapshot = {
                    "proof_guards": _count_proof_guards(),
                    "ledger_lines": _count_ledger_lines(),
                    "test_files": _count_pytest_files(),
                    "organs": _count_organs(),
                    "wallet": _get_wallet_balance(),
                    "ok": True,
                    "error": "",
                }
            except Exception as exc:
                snapshot = {"ok": False, "error": str(exc)}
            self._live_snapshot_ready.emit(snapshot)

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_live_snapshot(self, snapshot: Dict[str, Any]) -> None:
        self._live_refreshing = False
        try:
            if not snapshot.get("ok", False):
                self._status_lbl.setText(f"Error: {snapshot.get('error', 'unknown')}")
                return
            self._live_labels["proof_guards"].setText(str(snapshot.get("proof_guards", 0)))
            self._live_labels["ledger_lines"].setText(f"{int(snapshot.get('ledger_lines', 0)):,}")
            self._live_labels["test_files"].setText(str(snapshot.get("test_files", 0)))
            self._live_labels["organs"].setText(str(snapshot.get("organs", 0)))
            bal = float(snapshot.get("wallet", 0.0))
            self._live_labels["wallet"].setText(f"{bal:.2f}")
            self._status_lbl.setText(f"Live · {time.strftime('%H:%M:%S')}")
        except Exception as e:
            self._status_lbl.setText(f"Error: {e}")

    def closeEvent(self, event) -> None:
        self._refresh_timer.stop()
        if _offscreen_test_mode():
            self.hide()
            if self not in _OFFSCREEN_RETAINED_WIDGETS:
                _OFFSCREEN_RETAINED_WIDGETS.append(self)
            event.accept()
            return
        super().closeEvent(event)


# ── Standalone launch ─────────────────────────────────────────────────────

def create_widget(parent: QWidget | None = None) -> MathBenchmarkWidget:
    return MathBenchmarkWidget(parent)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MathBenchmarkWidget()
    w.setWindowTitle(_APP_NAME)
    w.resize(1100, 750)
    w.show()
    sys.exit(app.exec())
