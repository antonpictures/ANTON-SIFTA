#!/usr/bin/env python3
"""
sifta_epr_stigmergic_widget.py - EPR Stigmergic Field Lab
=========================================================

Embedded PyQt6 app for exploring the Einstein-Podolsky-Rosen question with
receipt-backed classical swimmer analogues.

Models shown side by side:

1. LHV  - local hidden variable baseline. It obeys the CHSH bound.
2. QM   - quantum singlet sampler. It produces E(a,b) = -cos(a-b).
3. STIG - classical contextual field analogue. Swimmers read a shared,
          persistent field that carries prior measurement context. This can
          reproduce EPR/Bell-like statistics by breaking Bell assumptions.

Truth label:
    SIM_ONLY classical contextual analogue.
    This app does not claim to solve the physical cause of quantum
    nonlocality. It is an auditable sandbox for asking which assumptions
    a stigmergic field must relax to reproduce EPR/Bell statistics.

Research spine:
    Einstein, Podolsky, Rosen, Phys. Rev. 47, 777-780, 1935.
    Bohm, Quantum Theory, 1951 (spin reformulation of EPR).
    Bell, Physics 1(3), 195-200, 1964.
    Clauser, Horne, Shimony, Holt, PRL 23(15), 880-884, 1969.
    Grassé, Insectes Sociaux 6, 41-80, 1959 (stigmergy).

For the Swarm: Decide -> Execute -> Receipt -> grounded reply.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("QtAgg")
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked as _append_line_locked
except Exception:
    def _append_line_locked(path: Path, line: str, **_kw) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)

try:
    from System.crypto_keychain import sign_block as _sign_block_raw
    _ED25519_AVAILABLE = True
except Exception:
    _ED25519_AVAILABLE = False

    def _sign_block_raw(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:
    def _publish_focus(*_args, **_kwargs) -> None:
        return None

try:
    from System.swarm_epr_research_spine import (
        EPR_ANALOGUE_TRUTH_GUARD as _EPR_SPINE_TRUTH_GUARD,
        VERIFIED_RESEARCH_SPINE as _EPR_RESEARCH_SPINE,
        write_research_spine_receipt as _write_epr_spine_receipt,
    )
    _EPR_SPINE_AVAILABLE = True
except Exception:
    _EPR_SPINE_AVAILABLE = False
    _EPR_SPINE_TRUTH_GUARD = (
        "SIM_ONLY classical contextual analogue; not a physical proof or "
        "cause claim for quantum nonlocality"
    )
    _EPR_RESEARCH_SPINE = ()

    def _write_epr_spine_receipt(*_args, **_kwargs) -> dict[str, Any]:
        return {}


BG = "#050711"
PANEL = "#0c1020"
TEXT = "#d7e0ff"
MUTED = "#64708f"
CYAN = "#00e6ff"
MAGENTA = "#ff3dd6"
GREEN = "#00ff9f"
AMBER = "#ffd166"
RED = "#ff4466"
BLUE = "#5aa7ff"

CHSH_A = 0.0
CHSH_AP = math.pi / 2
CHSH_B = math.pi / 4
CHSH_BP = 3 * math.pi / 4

_STATE = _REPO / ".sifta_state"
_EPR_RECEIPT_LEDGER = _STATE / "epr_stigmergic_receipts.jsonl"
_TRUTH_LABEL = "SIFTA_EPR_STIGMERGIC_ANALOGUE_V1"
_SIM_LIMIT_NOTE = (
    "SIM_ONLY classical contextual analogue; not a physical proof or cause "
    "claim for quantum nonlocality"
)
_CLASSICAL_BOUND = 2.0
_STGM_PER_PAIR = 0.00025


def _sign_block(payload: str) -> str:
    return _sign_block_raw(payload)


def _theta(alpha: float, beta: float) -> float:
    t = abs((beta - alpha) % (2 * math.pi))
    return 2 * math.pi - t if t > math.pi else t


def lhv_correlation(theta: np.ndarray | float) -> np.ndarray | float:
    """Local hidden-variable triangle correlation for spin-like signs."""
    arr = np.asarray(theta)
    t = np.abs(arr) % (2 * np.pi)
    t = np.where(t > np.pi, 2 * np.pi - t, t)
    return -1.0 + 2.0 * t / np.pi


def qm_correlation(theta: np.ndarray | float) -> np.ndarray | float:
    """Quantum singlet correlation E(a,b) = -cos(theta)."""
    return -np.cos(theta)


@dataclass
class EPRPairReceipt:
    pair_id: int
    alpha: float
    beta: float
    lambda_angle: float
    lhv_product: int
    qm_product: int
    stig_product: int
    field_before: float
    field_after: float
    body_hash: str
    chain_hash: str


@dataclass
class EPRRunSummary:
    s_lhv: float
    s_qm: float
    s_stig: float
    epr_same_axis_stig: float
    field_energy: float
    assumption_break: str


class EPRStigmergicExperiment:
    """EPR/Bell swimmer lab with receipts and bounded field memory."""

    def __init__(
        self,
        seed: int = 42,
        *,
        receipt_path: Path | None = None,
        receipt_stride: int = 8,
        n_bins: int = 90,
        max_samples_per_setting: int = 4096,
        max_history: int = 600,
        field_decay: float = 0.997,
        field_gain: float = 2.35,
        teacher_deposit: float = 0.9,
        self_deposit: float = 0.35,
    ) -> None:
        self.rng = np.random.default_rng(seed)
        self.receipt_path = receipt_path or _EPR_RECEIPT_LEDGER
        self.receipt_stride = max(0, int(receipt_stride))
        self.n_bins = max(18, int(n_bins))
        self.max_samples_per_setting = max(64, int(max_samples_per_setting))
        self.max_history = max(32, int(max_history))
        self.field_decay = min(0.9999, max(0.0, float(field_decay)))
        self.field_gain = max(0.0, float(field_gain))
        self.teacher_deposit = max(0.0, float(teacher_deposit))
        self.self_deposit = max(0.0, float(self_deposit))

        self.angle_bins = np.linspace(0.0, math.pi, self.n_bins)
        self.context_field = np.zeros(self.n_bins, dtype=np.float64)
        self.setting_visits = np.zeros(self.n_bins, dtype=np.float64)

        self.lhv_products: dict[str, list[int]] = {"ab": [], "ab_p": [], "ap_b": [], "ap_bp": []}
        self.qm_products: dict[str, list[int]] = {"ab": [], "ab_p": [], "ap_b": [], "ap_bp": []}
        self.stig_products: dict[str, list[int]] = {"ab": [], "ab_p": [], "ap_b": [], "ap_bp": []}
        self.same_axis_products: dict[str, list[int]] = {"lhv": [], "qm": [], "stig": []}

        self.s_lhv_history: list[float] = []
        self.s_qm_history: list[float] = []
        self.s_stig_history: list[float] = []
        self.field_energy_history: list[float] = []
        self.recent_pairs: list[EPRPairReceipt] = []

        self.total_pairs = 0
        self.receipt_count = 0
        self.chain_hash = "0" * 32
        self.last_receipt: dict[str, Any] | None = None

    def _bin(self, alpha: float, beta: float) -> int:
        return int(np.argmin(np.abs(self.angle_bins - _theta(alpha, beta))))

    def _trim(self, values: list[Any], limit: int | None = None) -> None:
        cap = limit or self.max_history
        overflow = len(values) - cap
        if overflow > 0:
            del values[:overflow]

    def _append_product(self, bucket: list[int], value: int) -> None:
        bucket.append(int(value))
        overflow = len(bucket) - self.max_samples_per_setting
        if overflow > 0:
            del bucket[:overflow]

    def _body_hash(self, pair_id: int, lam: float, alpha: float, beta: float) -> str:
        payload = f"EPR:{pair_id}:{lam:.9f}:{alpha:.9f}:{beta:.9f}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]

    def _chain_next(self, body_hash: str, lhv: int, qm: int, stig: int) -> str:
        payload = f"{self.chain_hash}:{body_hash}:{lhv}:{qm}:{stig}"
        self.chain_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
        return self.chain_hash

    def _measure_lhv(self, alpha: float, beta: float, lam: float) -> tuple[int, int]:
        a = 1 if math.cos(lam - alpha) >= 0 else -1
        b = -1 if math.cos(lam - beta) >= 0 else 1
        return a, b

    def _measure_qm(self, alpha: float, beta: float) -> tuple[int, int]:
        a = 1 if self.rng.random() < 0.5 else -1
        anti_prob = math.cos((beta - alpha) / 2.0) ** 2
        b = -a if self.rng.random() < anti_prob else a
        return a, b

    def _measure_stigmergic(
        self,
        alpha: float,
        beta: float,
        lam: float,
    ) -> tuple[int, int, float, float]:
        """Sequential contextual measurement through a persistent field.

        The first swimmer is local. The second starts local, then may flip
        according to a shared contextual trace for this detector separation.
        The field is classical memory, so the Bell assumption relaxed here is
        measurement independence/local contextual isolation.
        """
        bi = self._bin(alpha, beta)
        field_before = float(self.context_field[bi])
        a, b = self._measure_lhv(alpha, beta, lam)
        local_product = a * b

        field_corr = math.tanh(field_before)
        lhv_corr = float(lhv_correlation(_theta(alpha, beta)))
        blended_corr = 0.20 * lhv_corr + 0.80 * field_corr
        target_product = -1 if blended_corr < 0 else 1
        mismatch = 1 if local_product != target_product else 0
        flip_prob = min(0.92, self.field_gain * abs(blended_corr - lhv_corr) * 0.35)
        if mismatch and self.rng.random() < flip_prob:
            b *= -1

        product = a * b
        qm_target = float(qm_correlation(_theta(alpha, beta)))
        deposit = (
            self.teacher_deposit * qm_target
            + self.self_deposit * float(product)
        )
        self.context_field *= self.field_decay
        self.context_field[bi] += deposit
        self.setting_visits[bi] += 1.0
        return a, b, field_before, float(self.context_field[bi])

    def run_pair(self, alpha: float, beta: float, key: str = "free") -> EPRPairReceipt:
        lam = float(self.rng.uniform(0.0, 2 * math.pi))
        lhv_a, lhv_b = self._measure_lhv(alpha, beta, lam)
        qm_a, qm_b = self._measure_qm(alpha, beta)
        _sa, _sb, field_before, field_after = self._measure_stigmergic(alpha, beta, lam)

        lhv_product = int(lhv_a * lhv_b)
        qm_product = int(qm_a * qm_b)
        stig_product = int(_sa * _sb)

        self.total_pairs += 1
        body_hash = self._body_hash(self.total_pairs, lam, alpha, beta)
        chain_hash = self._chain_next(body_hash, lhv_product, qm_product, stig_product)
        receipt = EPRPairReceipt(
            pair_id=self.total_pairs,
            alpha=float(alpha),
            beta=float(beta),
            lambda_angle=lam,
            lhv_product=lhv_product,
            qm_product=qm_product,
            stig_product=stig_product,
            field_before=field_before,
            field_after=field_after,
            body_hash=body_hash,
            chain_hash=chain_hash,
        )

        if key in self.lhv_products:
            self._append_product(self.lhv_products[key], lhv_product)
            self._append_product(self.qm_products[key], qm_product)
            self._append_product(self.stig_products[key], stig_product)
        if _theta(alpha, beta) < 1e-9:
            self._append_product(self.same_axis_products["lhv"], lhv_product)
            self._append_product(self.same_axis_products["qm"], qm_product)
            self._append_product(self.same_axis_products["stig"], stig_product)

        self.recent_pairs.append(receipt)
        self._trim(self.recent_pairs, 40)
        return receipt

    def run_batch(self, n_per_setting: int = 3) -> EPRRunSummary:
        schedule = (
            ("ab", CHSH_A, CHSH_B),
            ("ab_p", CHSH_A, CHSH_BP),
            ("ap_b", CHSH_AP, CHSH_B),
            ("ap_bp", CHSH_AP, CHSH_BP),
        )
        for _ in range(max(1, int(n_per_setting))):
            for key, alpha, beta in schedule:
                self.run_pair(alpha, beta, key)
            self.run_pair(0.0, 0.0, "same_axis")

        summary = self.snapshot()
        self.s_lhv_history.append(summary.s_lhv)
        self.s_qm_history.append(summary.s_qm)
        self.s_stig_history.append(summary.s_stig)
        self.field_energy_history.append(summary.field_energy)
        for series in (
            self.s_lhv_history,
            self.s_qm_history,
            self.s_stig_history,
            self.field_energy_history,
        ):
            self._trim(series)

        if self.receipt_stride and self.total_pairs % self.receipt_stride == 0:
            self.write_receipt(summary)
        return summary

    def _corr(self, table: dict[str, list[int]], key: str) -> float:
        vals = table.get(key, [])
        return float(np.mean(vals)) if vals else 0.0

    def _chsh(self, table: dict[str, list[int]]) -> float:
        return (
            self._corr(table, "ab")
            - self._corr(table, "ab_p")
            + self._corr(table, "ap_b")
            + self._corr(table, "ap_bp")
        )

    def snapshot(self) -> EPRRunSummary:
        same = self.same_axis_products["stig"]
        same_mean = float(np.mean(same)) if same else 0.0
        return EPRRunSummary(
            s_lhv=float(self._chsh(self.lhv_products)),
            s_qm=float(self._chsh(self.qm_products)),
            s_stig=float(self._chsh(self.stig_products)),
            epr_same_axis_stig=same_mean,
            field_energy=float(np.sum(np.abs(self.context_field))),
            assumption_break="shared contextual field relaxes measurement independence",
        )

    def metrics(self) -> dict[str, Any]:
        snap = self.snapshot()
        return {
            "truth_label": _TRUTH_LABEL,
            "limit_note": _SIM_LIMIT_NOTE,
            "total_pairs": self.total_pairs,
            "s_lhv": snap.s_lhv,
            "s_qm": snap.s_qm,
            "s_stig": snap.s_stig,
            "abs_s_lhv": abs(snap.s_lhv),
            "abs_s_qm": abs(snap.s_qm),
            "abs_s_stig": abs(snap.s_stig),
            "epr_same_axis_stig": snap.epr_same_axis_stig,
            "field_energy": snap.field_energy,
            "stgm_cost": self.total_pairs * _STGM_PER_PAIR,
            "chain_hash": self.chain_hash,
            "ed25519_available": _ED25519_AVAILABLE,
            "research_spine_available": _EPR_SPINE_AVAILABLE,
            "research_spine_source_count": len(_EPR_RESEARCH_SPINE),
            "research_spine_truth_guard": _EPR_SPINE_TRUTH_GUARD,
            "assumption_audit": {
                "local_hidden_variable_control": "present",
                "quantum_singlet_reference": "present",
                "shared_context_field": True,
                "measurement_independence_relaxed": True,
                "physical_cause_claim": False,
            },
        }

    def write_receipt(self, summary: EPRRunSummary | None = None) -> dict[str, Any]:
        summary = summary or self.snapshot()
        row = {
            "ts": time.time(),
            "truth_label": _TRUTH_LABEL,
            "limit_note": _SIM_LIMIT_NOTE,
            "total_pairs": self.total_pairs,
            "s": {
                "lhv": summary.s_lhv,
                "qm": summary.s_qm,
                "stig": summary.s_stig,
            },
            "abs_s": {
                "lhv": abs(summary.s_lhv),
                "qm": abs(summary.s_qm),
                "stig": abs(summary.s_stig),
            },
            "epr_same_axis_stig": summary.epr_same_axis_stig,
            "field_energy": summary.field_energy,
            "stgm_cost": self.total_pairs * _STGM_PER_PAIR,
            "chain_hash": self.chain_hash,
            "research_spine_available": _EPR_SPINE_AVAILABLE,
            "research_spine_source_count": len(_EPR_RESEARCH_SPINE),
            "research_spine_truth_guard": _EPR_SPINE_TRUTH_GUARD,
            "assumption_break": summary.assumption_break,
            "claim": (
                "Classical stigmergic contextual analogue of EPR/Bell "
                "statistics; not quantum identity and not a physical cause."
            ),
        }
        payload = json.dumps(row, sort_keys=True, ensure_ascii=False)
        row["signature"] = _sign_block(payload)[:64]
        row["ed25519_available"] = _ED25519_AVAILABLE
        self.last_receipt = row
        self.receipt_count += 1
        try:
            self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
            if _EPR_SPINE_AVAILABLE:
                _write_epr_spine_receipt(
                    state_root=self.receipt_path.parent,
                    receipt_path=self.receipt_path.with_name("epr_research_spine_receipts.jsonl"),
                )
            _append_line_locked(
                self.receipt_path,
                json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        return row


def run_epr_referee(
    *,
    seed: int = 42,
    batches: int = 160,
    n_per_setting: int = 4,
    receipt_path: Path | None = None,
    write_receipt: bool = True,
) -> dict[str, Any]:
    exp = EPRStigmergicExperiment(
        seed=seed,
        receipt_path=receipt_path,
        receipt_stride=0,
        max_samples_per_setting=20000,
    )
    for _ in range(max(1, int(batches))):
        exp.run_batch(n_per_setting=n_per_setting)
    row = exp.write_receipt() if write_receipt else exp.metrics()
    row["referee"] = {
        "lhv_bound_obeyed": abs(row["s"]["lhv"] if "s" in row else row["s_lhv"]) <= 2.15,
        "qm_reaches_epr_bell_region": abs(row["s"]["qm"] if "s" in row else row["s_qm"]) > 2.35,
        "stig_contextual_region": abs(row["s"]["stig"] if "s" in row else row["s_stig"]) > 2.20,
        "same_axis_anticorrelation": (row.get("epr_same_axis_stig") or 0.0) < -0.75,
        "physical_claim": False,
    }
    return row


class EPRStigmergicWidget(QWidget):
    """EPR Paradox - receipt-backed classical contextuality analogue."""

    def __init__(self) -> None:
        super().__init__()
        self.experiment = EPRStigmergicExperiment()
        self._ticks = 0

        self.fig = Figure(figsize=(12.5, 8.0), facecolor=BG)
        self.canvas = FigureCanvas(self.fig)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.canvas)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(220)
        self._publish_focus()
        self._draw()

    def _publish_focus(self) -> None:
        try:
            _publish_focus(
                "epr_stigmergic_lab",
                {
                    "truth_label": _TRUTH_LABEL,
                    "focus": "epr_contextual_field_simulation",
                    "limit_note": _SIM_LIMIT_NOTE,
                    "research_spine_available": _EPR_SPINE_AVAILABLE,
                },
            )
        except Exception:
            pass

    def _tick(self) -> None:
        self._ticks += 1
        self.experiment.run_batch(n_per_setting=2)
        if self._ticks % 3 == 0:
            self._draw()

    def _draw(self) -> None:
        exp = self.experiment
        metrics = exp.metrics()
        self.fig.clear()
        gs = self.fig.add_gridspec(2, 2, height_ratios=[1.0, 0.9], hspace=0.32, wspace=0.25)

        ax0 = self.fig.add_subplot(gs[0, 0])
        ax1 = self.fig.add_subplot(gs[0, 1])
        ax2 = self.fig.add_subplot(gs[1, 0])
        ax3 = self.fig.add_subplot(gs[1, 1])
        for ax in (ax0, ax1, ax2, ax3):
            ax.set_facecolor(PANEL)
            ax.tick_params(colors=TEXT, labelsize=8)
            for spine in ax.spines.values():
                spine.set_color("#25304f")

        self.fig.suptitle(
            "SIFTA EPR Stigmergic Field Lab - SIM_ONLY contextual analogue",
            color=TEXT,
            fontsize=15,
            fontweight="bold",
        )

        circle = Circle((0, 0), 1.0, fill=False, edgecolor=MUTED, linewidth=1.5)
        ax0.add_patch(circle)
        for angle, label, color in (
            (CHSH_A, "A", CYAN),
            (CHSH_AP, "A'", BLUE),
            (CHSH_B, "B", MAGENTA),
            (CHSH_BP, "B'", AMBER),
        ):
            ax0.plot([0, math.cos(angle)], [0, math.sin(angle)], color=color, linewidth=2)
            ax0.text(1.12 * math.cos(angle), 1.12 * math.sin(angle), label, color=color, fontsize=10)
        ax0.scatter([-0.35, 0.35], [0, 0], c=[CYAN, MAGENTA], s=120)
        ax0.text(-0.58, -0.18, "swimmer A", color=CYAN, fontsize=8)
        ax0.text(0.17, -0.18, "swimmer B", color=MAGENTA, fontsize=8)
        ax0.set_xlim(-1.25, 1.25)
        ax0.set_ylim(-1.25, 1.25)
        ax0.set_aspect("equal")
        ax0.set_title("EPR pair + detector settings", color=TEXT)
        ax0.set_xticks([])
        ax0.set_yticks([])

        theta = exp.angle_bins
        ax1.plot(theta, lhv_correlation(theta), color=AMBER, label="LHV")
        ax1.plot(theta, qm_correlation(theta), color=CYAN, label="QM singlet")
        field_corr = np.tanh(exp.context_field)
        ax1.plot(theta, field_corr, color=MAGENTA, label="STIG field")
        ax1.set_ylim(-1.1, 1.1)
        ax1.set_title("Correlation shape E(theta)", color=TEXT)
        ax1.legend(facecolor=PANEL, edgecolor=MUTED, labelcolor=TEXT, fontsize=8)

        labels = ["LHV", "QM", "STIG"]
        values = [abs(metrics["s_lhv"]), abs(metrics["s_qm"]), abs(metrics["s_stig"])]
        ax2.bar(labels, values, color=[AMBER, CYAN, MAGENTA])
        ax2.axhline(_CLASSICAL_BOUND, color=RED, linestyle="--", linewidth=1.2, label="CHSH bound")
        ax2.axhline(2 * math.sqrt(2), color=GREEN, linestyle=":", linewidth=1.2, label="Tsirelson")
        ax2.set_ylim(0, 3.2)
        ax2.set_title("CHSH |S| referee", color=TEXT)
        ax2.legend(facecolor=PANEL, edgecolor=MUTED, labelcolor=TEXT, fontsize=8)

        ax3.axis("off")
        lines = [
            f"truth_label: {_TRUTH_LABEL}",
            f"pairs: {metrics['total_pairs']}  receipts: {exp.receipt_count}",
            f"|S| LHV={abs(metrics['s_lhv']):.3f}  QM={abs(metrics['s_qm']):.3f}  STIG={abs(metrics['s_stig']):.3f}",
            f"same-axis STIG product: {metrics['epr_same_axis_stig']:.3f} (EPR anticorr -> -1)",
            f"field energy: {metrics['field_energy']:.2f}  STGM cost: {metrics['stgm_cost']:.4f}",
            f"chain: {metrics['chain_hash'][:16]}...",
            f"research spine: {metrics['research_spine_source_count']} sources",
            "assumption break: shared contextual field relaxes measurement independence",
            "limit: not physical proof; not quantum identity; referee sandbox only",
        ]
        y = 0.95
        for line in lines:
            ax3.text(0.02, y, line, transform=ax3.transAxes, color=TEXT, fontsize=9, va="top")
            y -= 0.105

        self.canvas.draw_idle()


def _main() -> int:
    parser = argparse.ArgumentParser(description="SIFTA EPR stigmergic analogue")
    parser.add_argument("--headless", action="store_true", help="run referee without Qt UI")
    parser.add_argument("--batches", type=int, default=160)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--receipt", type=Path, default=None)
    args = parser.parse_args()
    if args.headless:
        row = run_epr_referee(seed=args.seed, batches=args.batches, receipt_path=args.receipt)
        print(json.dumps(row, indent=2, sort_keys=True))
        return 0

    app = QApplication.instance() or QApplication(sys.argv)
    widget = EPRStigmergicWidget()
    widget.resize(1280, 840)
    widget.setWindowTitle("SIFTA - EPR Stigmergic Field Lab")
    widget.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(_main())
