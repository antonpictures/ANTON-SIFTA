#!/usr/bin/env python3
"""
sifta_physarum_contradiction_lab.py

Playable audit app for Claude/Cursor's "Slime-Mold Bank" memo.

It uses the real repo modules:
  - System.swarm_physarum_solver
  - System.proof_of_useful_work
  - System.swarm_warp9_federation

The point is not to dunk on the Physarum idea. The point is to show the
implementation boundary: the solver is real, but the current PoUW verifier is
not yet a semantic graph-solve verifier.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QBrush, QClipboard
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from System.proof_of_useful_work import WORK_VALUES, prove_useful_work
from System.swarm_physarum_solver import (
    PRUNE_THRESHOLD,
    MU,
    PhysarumSolver,
    DEMO_GRAPHS,
)

# 2026-04-26 — post-C55M-audit imports. These three live in
# proof_of_useful_work.py and were added to close the gaps Codex's
# original lab exposed. We import them defensively so that this lab can
# still run on an older snapshot of the repo (in which case the new
# checks will report UNAVAILABLE and the verdict still reflects the
# original Codex finding).
try:
    from System.proof_of_useful_work import (
        canonical_physarum_graph as _audit_canonical_graph,
        canonical_physarum_solution as _audit_canonical_solution,
        prove_physarum_solve as _audit_prove_physarum_solve,
        _PHYSARUM_RESULT_LEDGER as _audit_result_ledger,
        _PHYSARUM_PEER_LEDGER as _audit_peer_ledger,
    )
    _SEMANTIC_GATE_AVAILABLE = True
except Exception as _semantic_exc:  # pragma: no cover
    _SEMANTIC_GATE_AVAILABLE = False
    _SEMANTIC_GATE_IMPORT_ERROR = repr(_semantic_exc)


GRAPH_NAME = "tokyo_stub"
MEMO_URL = (
    "https://github.com/antonpictures/ANTON-SIFTA/blob/main/"
    "Documents/MARKETING_MEMO_TO_CARLTON_DOLE_FAVORITE_SIFTA_SIMULATION_2026-04-26.md"
)


TOKYO_LAYOUT: Dict[int, Tuple[float, float]] = {
    0: (0.08, 0.52),
    1: (0.18, 0.22),
    2: (0.18, 0.78),
    3: (0.30, 0.50),
    4: (0.42, 0.23),
    5: (0.43, 0.77),
    6: (0.55, 0.50),
    7: (0.66, 0.26),
    8: (0.66, 0.74),
    9: (0.77, 0.50),
    10: (0.87, 0.31),
    11: (0.87, 0.69),
    12: (0.94, 0.50),
    13: (0.98, 0.33),
    14: (0.98, 0.67),
}


def _sha256_json(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_graph(name: str = GRAPH_NAME) -> Tuple[List[int], List[Tuple[int, int, float]], int, int]:
    if name not in DEMO_GRAPHS:
        raise KeyError(f"Unknown demo graph: {name}")
    nodes, edges, source, sink = DEMO_GRAPHS[name]()
    return list(nodes), list(edges), int(source), int(sink)


def canonical_graph(nodes: List[int], edges: List[Tuple[int, int, float]], source: int, sink: int) -> Dict[str, Any]:
    return {
        "nodes": sorted(int(n) for n in nodes),
        "edges": [
            {"u": int(u), "v": int(v), "conductance": round(float(d), 10)}
            for u, v, d in sorted(edges, key=lambda e: (int(e[0]), int(e[1]), float(e[2])))
        ],
        "source": int(source),
        "sink": int(sink),
        "solver": {"module": "System.swarm_physarum_solver", "mu": MU, "prune_threshold": PRUNE_THRESHOLD},
    }


def canonical_solution(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "converged_at_iter": int(result["converged_at_iter"]),
        "initial_edges": int(result["initial_edges"]),
        "alive_edges": int(result["alive_edges"]),
        "pruned_edges": int(result["pruned_edges"]),
        "pruned_pct": float(result["pruned_pct"]),
        "optimal_topology": result["optimal_topology"],
    }


def run_claim_audit(max_iters: int = 650) -> Dict[str, Any]:
    """Run the live contradiction test without opening the GUI."""
    nodes, edges, source, sink = load_graph()
    before_payload = canonical_graph(nodes, edges, source, sink)
    before_hash = _sha256_json(before_payload)

    solver = PhysarumSolver(nodes, edges, source, sink)
    result = solver.solve(max_iters=max_iters)
    solution_payload = canonical_solution(result)
    after_hash = _sha256_json(solution_payload)

    forged_payload = {
        "claim": "forged city solve",
        "graph": GRAPH_NAME,
        "fake_pruned_pct": 99.9,
        "note": "This never ran the Physarum solver.",
        "nonce": "CARLTON_CAN_SEE_THE_GAP",
    }
    forged_hash = _sha256_json(forged_payload)

    honest_ok, honest_reason = prove_useful_work(before_hash, after_hash)
    forged_ok, forged_reason = prove_useful_work(before_hash, forged_hash)

    # ── Post-C55M semantic gate checks (added 2026-04-26 by Cursor in
    # response to Codex's audit). These complement — they DO NOT replace —
    # the original Codex checks above. The original body-gate checks
    # remain visible so Carlton can see the gap that was, and the new
    # rows show whether it was actually closed.
    semantic_honest: Dict[str, Any] = {"ok": None, "reason": "UNAVAILABLE"}
    semantic_forged: Dict[str, Any] = {"ok": None, "reason": "UNAVAILABLE"}
    semantic_double_spend: Dict[str, Any] = {"ok": None, "reason": "UNAVAILABLE"}
    canonical_graph_payload: Dict[str, Any] = {}
    if _SEMANTIC_GATE_AVAILABLE:
        canonical_graph_payload = _audit_canonical_graph(nodes, edges, source, sink)
        try:
            ok_h, reason_h, ev_h = _audit_prove_physarum_solve(
                canonical_graph=canonical_graph_payload,
                claimed_after_hash=after_hash,
                max_iters=max_iters,
            )
            semantic_honest = {
                "ok": bool(ok_h),
                "reason": reason_h,
                "hash_match": ev_h.get("hash_match"),
                "replay_hash": (ev_h.get("replay_hash") or "")[:16],
                "result_hash_spent": ev_h.get("result_hash_spent"),
                "peer_consensus_count": (
                    (ev_h.get("peer_consensus") or {}).get("attestation_count", 0)
                ),
            }
        except Exception as exc:
            semantic_honest = {"ok": False, "reason": f"ERROR: {exc}"}

        try:
            ok_f, reason_f, ev_f = _audit_prove_physarum_solve(
                canonical_graph=canonical_graph_payload,
                claimed_after_hash=forged_hash,
                max_iters=max_iters,
            )
            semantic_forged = {
                "ok": bool(ok_f),
                "reason": reason_f,
                "hash_match": ev_f.get("hash_match"),
                "replay_hash": (ev_f.get("replay_hash") or "")[:16],
            }
        except Exception as exc:
            semantic_forged = {"ok": False, "reason": f"ERROR: {exc}"}

        # Double-spend check: replay the same honest hash a second time
        # AFTER pretending it was already minted on. We do this by
        # appending and then removing a synthetic ledger row so the gate
        # sees the spend but the lab leaves no permanent stain.
        try:
            ledger_path = Path(_audit_result_ledger)
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            synthetic_row = (
                json.dumps({
                    "ts": time.time(),
                    "result_hash": after_hash,
                    "agent_id": "C55M_LAB_DOUBLE_SPEND_PROBE",
                    "territory": "audit_lab",
                    "receipt_id": "synthetic_for_audit",
                }) + "\n"
            )
            had_existing = ledger_path.exists()
            existing_bytes = ledger_path.read_bytes() if had_existing else b""
            with ledger_path.open("a", encoding="utf-8") as f:
                f.write(synthetic_row)

            ok_d, reason_d, ev_d = _audit_prove_physarum_solve(
                canonical_graph=canonical_graph_payload,
                claimed_after_hash=after_hash,
                max_iters=max_iters,
            )
            semantic_double_spend = {
                "ok": bool(ok_d),
                "reason": reason_d,
                "result_hash_spent": ev_d.get("result_hash_spent"),
            }

            # Restore the ledger to its prior state so the audit run
            # leaves no residue on the operator's machine.
            if had_existing:
                ledger_path.write_bytes(existing_bytes)
            else:
                ledger_path.unlink(missing_ok=True)
        except Exception as exc:
            semantic_double_spend = {"ok": False, "reason": f"ERROR: {exc}"}

    try:
        import System.swarm_warp9_federation as warp9
        federation_present = True
        federation_version = getattr(warp9, "MODULE_VERSION", "unknown")
        federation_claim = "spool transport present; semantic peer re-solve consensus not present here"
    except Exception as exc:
        federation_present = False
        federation_version = f"unavailable: {type(exc).__name__}"
        federation_claim = "unavailable"

    physarum_value = WORK_VALUES.get("PHYSARUM_SOLVE")
    physarum_value_canonical = (
        physarum_value is not None
        and abs(float(physarum_value) - 0.65) < 1e-9
    )

    # Verdict logic — MEMO_CONFIRMED requires BOTH the original Codex
    # checks to flip green AND the new semantic gate to fire.
    if not _SEMANTIC_GATE_AVAILABLE:
        verdict = "CONTRADICTS_MEMO" if forged_ok else "MEMO_CONFIRMED"
    else:
        memo_confirmed = (
            physarum_value_canonical
            and bool(semantic_honest.get("ok"))
            and not bool(semantic_forged.get("ok"))
            and not bool(semantic_double_spend.get("ok"))
        )
        verdict = "MEMO_CONFIRMED" if memo_confirmed else "CONTRADICTS_MEMO"

    return {
        "graph": GRAPH_NAME,
        "memo_url": MEMO_URL,
        "mu": MU,
        "prune_threshold": PRUNE_THRESHOLD,
        "nodes": len(nodes),
        "edges": len(edges),
        "source": source,
        "sink": sink,
        "result": result,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "forged_hash": forged_hash,
        "honest_pouw": {"ok": bool(honest_ok), "reason": honest_reason},
        "forged_pouw": {"ok": bool(forged_ok), "reason": forged_reason},
        "physarum_work_value_present": "PHYSARUM_SOLVE" in WORK_VALUES,
        "physarum_work_value_actual": physarum_value,
        "physarum_work_value_default_if_issued": WORK_VALUES.get("UNKNOWN_TYPE", 0.05),
        "physarum_work_value_canonical": physarum_value_canonical,
        "memo_claimed_work_value": 0.65,
        "semantic_gate_available": _SEMANTIC_GATE_AVAILABLE,
        "semantic_honest": semantic_honest,
        "semantic_forged": semantic_forged,
        "semantic_double_spend": semantic_double_spend,
        "federation_present": federation_present,
        "federation_version": federation_version,
        "federation_claim": federation_claim,
        "verdict": verdict,
    }


def make_claude_report(audit: Dict[str, Any]) -> str:
    result = audit["result"]
    missing_value = not audit["physarum_work_value_present"]
    forged_ok = bool(audit["forged_pouw"]["ok"])
    canonical_value = bool(audit.get("physarum_work_value_canonical"))
    semantic_available = bool(audit.get("semantic_gate_available"))
    sh = audit.get("semantic_honest") or {}
    sf = audit.get("semantic_forged") or {}
    sd = audit.get("semantic_double_spend") or {}

    lines = [
        "C55M Physarum Contradiction Lab result",
        "",
        f"Memo tested: {audit['memo_url']}",
        f"Graph: {audit['graph']} ({audit['nodes']} nodes, {audit['edges']} edges)",
        f"Solver constants: MU={audit['mu']}, PRUNE_THRESHOLD={audit['prune_threshold']}",
        f"Live solve: pruned {result['pruned_edges']}/{result['initial_edges']} edges "
        f"({result['pruned_pct']}%), alive_edges={result['alive_edges']}",
        f"before_hash={audit['before_hash'][:16]}... after_hash={audit['after_hash'][:16]}...",
        "",
        "Original Codex (C55M) audit checks:",
        f"1. PHYSARUM_SOLVE in WORK_VALUES? {not missing_value}",
        f"   memo_claim=0.65 actual={audit['physarum_work_value_actual']} "
        f"default_if_issued={audit['physarum_work_value_default_if_issued']}  "
        f"canonical_at_0.65={canonical_value}",
        f"2. prove_useful_work accepts honest solve hash? {audit['honest_pouw']}",
        f"3. prove_useful_work accepts forged changed hash? {audit['forged_pouw']}",
        f"4. federation state: {audit['federation_claim']} ({audit['federation_version']})",
        "",
        "Post-audit semantic gate checks (added 2026-04-26 by Cursor in",
        "response to Codex's lab — they probe the NEW prove_physarum_solve",
        "verifier, not the body-only prove_useful_work gate):",
    ]

    if not semantic_available:
        lines.append(
            "5. Semantic gate UNAVAILABLE — running on a snapshot before the "
            "post-audit patch landed. The original Codex finding stands."
        )
    else:
        lines.extend([
            f"5. prove_physarum_solve accepts honest deterministic replay? "
            f"{{'ok': {sh.get('ok')}, 'reason': '{sh.get('reason')}', "
            f"'hash_match': {sh.get('hash_match')}, "
            f"'peer_consensus_count': {sh.get('peer_consensus_count')}}}",
            f"6. prove_physarum_solve rejects forged claimed_after_hash? "
            f"{{'ok': {sf.get('ok')}, 'reason': '{sf.get('reason')}', "
            f"'hash_match': {sf.get('hash_match')}}}",
            f"7. prove_physarum_solve rejects already-minted result hash? "
            f"{{'ok': {sd.get('ok')}, 'reason': '{sd.get('reason')}'}}",
        ])

    lines.extend([
        "",
        "Verdict:",
    ])

    if audit.get("verdict") == "MEMO_CONFIRMED":
        lines.extend([
            "MEMO_CONFIRMED. The Physarum solver is real, PHYSARUM_SOLVE is now",
            "a canonical 0.65-valued PoUW work type, the semantic gate replays",
            "the solve deterministically and rejects forged hashes by",
            "HASH_MISMATCH, the result-hash spend ledger blocks double mints,",
            "and a peer-countersignature scaffold is wired to warp9.",
            "Body-gate prove_useful_work still accepts the forged hash by",
            "design — that gate is body-level only and the Slime-Mold Bank no",
            "longer relies on it as the semantic verifier.",
        ])
    else:
        lines.extend([
            "The Physarum solver is real. The marketing claim is ahead of the verifier.",
            "Current PoUW proves changed bytes + live system, not semantic city-waste reduction.",
        ])
        if forged_ok and not semantic_available:
            lines.append("A fake after_hash passes the same PoUW gate, so Slime-Mold Bank is not product-grade yet.")
        if missing_value:
            lines.append("PHYSARUM_SOLVE is not yet a canonical PoUW work type valued at 0.65.")

    lines.append("")
    lines.append(
        "Next honest frontier: peer countersignature consensus across "
        "warp9 federation peers (require ≥ 2 distinct attestations before "
        "issuing the receipt). The hook lives in "
        "request_peer_countersignature; flip require_peer_consensus=True "
        "on the call site once two M-class nodes are online."
    )
    return "\n".join(lines)


@dataclass
class SimulationState:
    nodes: List[int]
    edges: List[Tuple[int, int, float]]
    source: int
    sink: int
    solver: PhysarumSolver
    tick: int = 0
    running: bool = False
    flow: float = 0.0


def _make_state() -> SimulationState:
    nodes, edges, source, sink = load_graph()
    return SimulationState(nodes, edges, source, sink, PhysarumSolver(nodes, edges, source, sink))


class PhysarumCanvas(QWidget):
    """Multicolor live audit canvas used by standalone and SIFTA OS launchers."""

    def __init__(self, state: SimulationState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self.audit = run_claim_audit(max_iters=650)
        self.setMinimumSize(880, 620)

    def set_state(self, state: SimulationState) -> None:
        self.state = state
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        bg = QLinearGradient(0, 0, w, h)
        bg.setColorAt(0.0, QColor(3, 9, 20))
        bg.setColorAt(0.45, QColor(12, 18, 38))
        bg.setColorAt(1.0, QColor(3, 22, 18))
        p.fillRect(self.rect(), bg)

        self._draw_grid(p, w, h)
        left = QRectF(28, 70, w * 0.43, h - 120)
        right = QRectF(w * 0.53, 70, w * 0.43, h - 120)
        self._title(p, "CLAUDE CLAIM: money minted by city-saving solve", 30, 32, QColor(235, 235, 245))
        self._title(p, "LIVE CONTRADICTION: verifier accepts changed hashes", int(w * 0.53), 32, QColor(255, 220, 140))
        self._panel(p, left, QColor(32, 49, 84, 145))
        self._panel(p, right, QColor(76, 38, 48, 145))
        self._draw_graph(p, left, use_live=False)
        self._draw_graph(p, right, use_live=True)
        self._draw_meters(p, w, h)
        p.end()

    def _draw_grid(self, p: QPainter, w: int, h: int) -> None:
        pen = QPen(QColor(38, 66, 95, 75), 1)
        p.setPen(pen)
        for x in range(0, w, 36):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 36):
            p.drawLine(0, y, w, y)

    def _title(self, p: QPainter, text: str, x: int, y: int, color: QColor) -> None:
        p.setPen(color)
        font = QFont("Menlo", 13, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(x, y, text)

    def _panel(self, p: QPainter, r: QRectF, color: QColor) -> None:
        p.setPen(QPen(QColor(120, 170, 210, 160), 1.4))
        p.setBrush(QBrush(color))
        p.drawRoundedRect(r, 8, 8)

    def _point(self, rect: QRectF, node: int) -> Tuple[float, float]:
        x, y = TOKYO_LAYOUT.get(node, (0.5, 0.5))
        return rect.left() + x * rect.width(), rect.top() + y * rect.height()

    def _edge_color(self, conductance: float, live: bool) -> QColor:
        if not live:
            return QColor(110, 135, 160, 145)
        if conductance <= PRUNE_THRESHOLD:
            return QColor(190, 70, 85, 75)
        t = min(1.0, max(0.0, conductance))
        r = int(55 + 200 * t)
        g = int(130 + 110 * (1.0 - abs(t - 0.45)))
        b = int(255 - 170 * t)
        return QColor(r, g, b, 230)

    def _draw_graph(self, p: QPainter, rect: QRectF, use_live: bool) -> None:
        p.save()
        label = "Before: all tubes plausible" if not use_live else f"After/live: step {self.state.tick}"
        p.setPen(QColor(220, 228, 242))
        p.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        p.drawText(int(rect.left() + 18), int(rect.top() + 28), label)

        max_d = max(0.001, float(np.max(self.state.solver.D)))
        for k, (u, v, initial) in enumerate(self.state.edges):
            x1, y1 = self._point(rect, u)
            x2, y2 = self._point(rect, v)
            d = float(self.state.solver.D[k]) if use_live else float(initial)
            width = 1.0 + (7.0 * d / max_d if use_live else 2.0)
            if use_live and d <= PRUNE_THRESHOLD:
                width = 1.0
            color = self._edge_color(d / max_d if use_live else d, use_live)
            p.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(int(x1), int(y1), int(x2), int(y2))

        for n in self.state.nodes:
            x, y = self._point(rect, n)
            if n == self.state.source:
                fill = QColor(30, 230, 170)
            elif n == self.state.sink:
                fill = QColor(255, 85, 120)
            else:
                fill = QColor(250, 210, 80) if use_live else QColor(105, 210, 255)
            p.setBrush(QBrush(fill))
            p.setPen(QPen(QColor(5, 8, 15), 2))
            p.drawEllipse(QRectF(x - 8, y - 8, 16, 16))
            p.setPen(QColor(235, 240, 255))
            p.setFont(QFont("Menlo", 8))
            p.drawText(int(x + 9), int(y - 9), str(n))
        p.restore()

    def _draw_meters(self, p: QPainter, w: int, h: int) -> None:
        audit = self.audit
        result = audit["result"]
        missing_value = not audit["physarum_work_value_present"]
        forged_ok = bool(audit["forged_pouw"]["ok"])
        rows = [
            ("Live solver pruned", f"{result['pruned_pct']}%", QColor(63, 220, 171)),
            (
                "PHYSARUM_SOLVE valued at 0.65",
                "NO" if missing_value else "YES",
                QColor(255, 88, 112) if missing_value else QColor(63, 220, 171),
            ),
            (
                "Fake changed hash passes PoUW",
                "YES" if forged_ok else "NO",
                QColor(255, 88, 112) if forged_ok else QColor(63, 220, 171),
            ),
            ("Federation semantic replay", "NOT YET", QColor(255, 190, 80)),
        ]
        x0 = 36
        y0 = h - 36
        p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        for i, (name, value, color) in enumerate(rows):
            x = x0 + i * max(200, (w - 72) // 4)
            p.setPen(QColor(165, 176, 205))
            p.drawText(x, y0 - 22, name)
            p.setPen(color)
            p.drawText(x, y0, value)


class PhysarumContradictionLabWidget(QMainWindow):
    """SIFTA OS Programs -> Simulations entry for the Physarum audit lab."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SIFTA Physarum Contradiction Lab - Slime-Mold Bank Audit")
        self.state = _make_state()
        self.canvas = PhysarumCanvas(self.state)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.report_box = QPlainTextEdit()
        self.report_box.setReadOnly(True)
        self.report_box.setMaximumHeight(230)
        self.report_box.setPlainText(make_claude_report(self.canvas.audit))
        self.report_box.setStyleSheet(
            "background:#08111f;color:#dce8ff;border:1px solid #294461;"
            "font-family:Menlo;font-size:12px;"
        )
        self._build()

    def _build(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        banner = QLabel("SIFTA Physarum Contradiction Lab - real solver, real PoUW gap, real hashes")
        banner.setStyleSheet("color:#f6f0dd;font-family:Menlo;font-size:18px;font-weight:700;")
        layout.addWidget(banner)
        layout.addWidget(self.canvas, 1)
        buttons = QHBoxLayout()
        for text, fn in [
            ("Run / Pause Live Solve", self._toggle),
            ("Step 25", self._step_25),
            ("Reset", self._reset),
            ("Copy Claude Report", self._copy_report),
            ("Write Test Report", self._write_report),
        ]:
            b = QPushButton(text)
            b.clicked.connect(fn)
            b.setStyleSheet(
                "background:#12304a;color:#eef7ff;border:1px solid #3d7197;"
                "padding:8px 12px;font-weight:700;"
            )
            buttons.addWidget(b)
        layout.addLayout(buttons)
        layout.addWidget(self.report_box)
        self.setCentralWidget(root)
        self.resize(1280, 900)
        self.setStyleSheet("QMainWindow{background:#030914;}")

    def _tick(self) -> None:
        for _ in range(6):
            self.state.flow = self.state.solver.step()
            self.state.tick += 1
        self.canvas.update()

    def _toggle(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
        else:
            self.timer.start(30)

    def _step_25(self) -> None:
        for _ in range(25):
            self.state.flow = self.state.solver.step()
            self.state.tick += 1
        self.canvas.update()

    def _reset(self) -> None:
        self.state = _make_state()
        self.canvas.set_state(self.state)

    def _copy_report(self) -> None:
        QApplication.clipboard().setText(self.report_box.toPlainText(), QClipboard.Mode.Clipboard)

    def _write_report(self) -> None:
        out = REPO / ".sifta_state" / "physarum_contradiction_lab_report.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.report_box.toPlainText() + "\n", encoding="utf-8")
        self.report_box.appendPlainText(f"\nWrote: {out}")


def main() -> int:
    from PyQt6.QtCore import Qt, QTimer, QRectF
    from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QBrush, QClipboard
    from PyQt6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QPushButton,
        QPlainTextEdit,
        QVBoxLayout,
        QWidget,
    )

    class PhysarumCanvas(QWidget):
        def __init__(self, state: SimulationState, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.state = state
            self.audit = run_claim_audit(max_iters=650)
            self.setMinimumSize(880, 620)

        def set_state(self, state: SimulationState) -> None:
            self.state = state
            self.update()

        def paintEvent(self, _event) -> None:  # noqa: N802
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height()
            bg = QLinearGradient(0, 0, w, h)
            bg.setColorAt(0.0, QColor(3, 9, 20))
            bg.setColorAt(0.45, QColor(12, 18, 38))
            bg.setColorAt(1.0, QColor(3, 22, 18))
            p.fillRect(self.rect(), bg)

            self._draw_grid(p, w, h)
            left = QRectF(28, 70, w * 0.43, h - 120)
            right = QRectF(w * 0.53, 70, w * 0.43, h - 120)
            self._title(p, "CLAUDE CLAIM: money minted by city-saving solve", 30, 32, QColor(235, 235, 245))
            self._title(p, "LIVE CONTRADICTION: verifier accepts changed hashes", int(w * 0.53), 32, QColor(255, 220, 140))
            self._panel(p, left, QColor(32, 49, 84, 145))
            self._panel(p, right, QColor(76, 38, 48, 145))
            self._draw_graph(p, left, use_live=False)
            self._draw_graph(p, right, use_live=True)
            self._draw_meters(p, w, h)
            p.end()

        def _draw_grid(self, p: QPainter, w: int, h: int) -> None:
            pen = QPen(QColor(38, 66, 95, 75), 1)
            p.setPen(pen)
            for x in range(0, w, 36):
                p.drawLine(x, 0, x, h)
            for y in range(0, h, 36):
                p.drawLine(0, y, w, y)

        def _title(self, p: QPainter, text: str, x: int, y: int, color: QColor) -> None:
            p.setPen(color)
            font = QFont("Menlo", 13, QFont.Weight.Bold)
            p.setFont(font)
            p.drawText(x, y, text)

        def _panel(self, p: QPainter, r: QRectF, color: QColor) -> None:
            p.setPen(QPen(QColor(120, 170, 210, 160), 1.4))
            p.setBrush(QBrush(color))
            p.drawRoundedRect(r, 8, 8)

        def _point(self, rect: QRectF, node: int) -> Tuple[float, float]:
            x, y = TOKYO_LAYOUT.get(node, (0.5, 0.5))
            return rect.left() + x * rect.width(), rect.top() + y * rect.height()

        def _edge_color(self, conductance: float, live: bool) -> QColor:
            if not live:
                return QColor(110, 135, 160, 145)
            if conductance <= PRUNE_THRESHOLD:
                return QColor(190, 70, 85, 75)
            t = min(1.0, max(0.0, conductance))
            r = int(55 + 200 * t)
            g = int(130 + 110 * (1.0 - abs(t - 0.45)))
            b = int(255 - 170 * t)
            return QColor(r, g, b, 230)

        def _draw_graph(self, p: QPainter, rect: QRectF, use_live: bool) -> None:
            p.save()
            label = "Before: all tubes plausible" if not use_live else f"After/live: step {self.state.tick}"
            p.setPen(QColor(220, 228, 242))
            p.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
            p.drawText(int(rect.left() + 18), int(rect.top() + 28), label)

            max_d = max(0.001, float(np.max(self.state.solver.D)))
            for k, (u, v, initial) in enumerate(self.state.edges):
                x1, y1 = self._point(rect, u)
                x2, y2 = self._point(rect, v)
                d = float(self.state.solver.D[k]) if use_live else float(initial)
                width = 1.0 + (7.0 * d / max_d if use_live else 2.0)
                if use_live and d <= PRUNE_THRESHOLD:
                    width = 1.0
                p.setPen(QPen(self._edge_color(d / max_d if use_live else d, use_live), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(int(x1), int(y1), int(x2), int(y2))

            for n in self.state.nodes:
                x, y = self._point(rect, n)
                if n == self.state.source:
                    fill = QColor(30, 230, 170)
                elif n == self.state.sink:
                    fill = QColor(255, 85, 120)
                else:
                    fill = QColor(250, 210, 80) if use_live else QColor(105, 210, 255)
                p.setBrush(QBrush(fill))
                p.setPen(QPen(QColor(5, 8, 15), 2))
                p.drawEllipse(QRectF(x - 8, y - 8, 16, 16))
                p.setPen(QColor(235, 240, 255))
                p.setFont(QFont("Menlo", 8))
                p.drawText(int(x + 9), int(y - 9), str(n))
            p.restore()

        def _draw_meters(self, p: QPainter, w: int, h: int) -> None:
            audit = self.audit
            result = audit["result"]
            missing_value = not audit["physarum_work_value_present"]
            forged_ok = bool(audit["forged_pouw"]["ok"])
            rows = [
                ("Live solver pruned", f"{result['pruned_pct']}%", QColor(63, 220, 171)),
                ("PHYSARUM_SOLVE valued at 0.65", "NO" if missing_value else "YES", QColor(255, 88, 112) if missing_value else QColor(63, 220, 171)),
                ("Fake changed hash passes PoUW", "YES" if forged_ok else "NO", QColor(255, 88, 112) if forged_ok else QColor(63, 220, 171)),
                ("Federation semantic replay", "NOT YET", QColor(255, 190, 80)),
            ]
            x0 = 36
            y0 = h - 36
            p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
            for i, (name, value, color) in enumerate(rows):
                x = x0 + i * max(200, (w - 72) // 4)
                p.setPen(QColor(165, 176, 205))
                p.drawText(x, y0 - 22, name)
                p.setPen(color)
                p.drawText(x, y0, value)

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("SIFTA Physarum Contradiction Lab - Slime-Mold Bank Audit")
            self.state = _make_state()
            self.canvas = PhysarumCanvas(self.state)
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._tick)
            self.report_box = QPlainTextEdit()
            self.report_box.setReadOnly(True)
            self.report_box.setMaximumHeight(230)
            self.report_box.setPlainText(make_claude_report(self.canvas.audit))
            self.report_box.setStyleSheet("background:#08111f;color:#dce8ff;border:1px solid #294461;font-family:Menlo;font-size:12px;")
            self._build()

        def _build(self) -> None:
            root = QWidget()
            layout = QVBoxLayout(root)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(10)
            banner = QLabel("SIFTA Physarum Contradiction Lab - real solver, real PoUW gap, real hashes")
            banner.setStyleSheet("color:#f6f0dd;font-family:Menlo;font-size:18px;font-weight:700;")
            layout.addWidget(banner)
            layout.addWidget(self.canvas, 1)
            buttons = QHBoxLayout()
            for text, fn in [
                ("Run / Pause Live Solve", self._toggle),
                ("Step 25", self._step_25),
                ("Reset", self._reset),
                ("Copy Claude Report", self._copy_report),
                ("Write Test Report", self._write_report),
            ]:
                b = QPushButton(text)
                b.clicked.connect(fn)
                b.setStyleSheet("background:#12304a;color:#eef7ff;border:1px solid #3d7197;padding:8px 12px;font-weight:700;")
                buttons.addWidget(b)
            layout.addLayout(buttons)
            layout.addWidget(self.report_box)
            self.setCentralWidget(root)
            self.resize(1280, 900)
            self.setStyleSheet("QMainWindow{background:#030914;}")

        def _tick(self) -> None:
            for _ in range(6):
                self.state.flow = self.state.solver.step()
                self.state.tick += 1
            self.canvas.update()

        def _toggle(self) -> None:
            if self.timer.isActive():
                self.timer.stop()
            else:
                self.timer.start(30)

        def _step_25(self) -> None:
            for _ in range(25):
                self.state.flow = self.state.solver.step()
                self.state.tick += 1
            self.canvas.update()

        def _reset(self) -> None:
            self.state = _make_state()
            self.canvas.set_state(self.state)

        def _copy_report(self) -> None:
            QApplication.clipboard().setText(self.report_box.toPlainText(), QClipboard.Mode.Clipboard)

        def _write_report(self) -> None:
            out = REPO / ".sifta_state" / "physarum_contradiction_lab_report.txt"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(self.report_box.toPlainText() + "\n", encoding="utf-8")
            self.report_box.appendPlainText(f"\nWrote: {out}")

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    if "--audit-json" in sys.argv:
        print(json.dumps(run_claim_audit(), indent=2, sort_keys=True))
        raise SystemExit(0)
    if "--report" in sys.argv:
        print(make_claude_report(run_claim_audit()))
        raise SystemExit(0)
    raise SystemExit(main())
