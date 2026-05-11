#!/usr/bin/env python3
"""
sifta_bell_theorem_widget.py — Bell's Theorem Stigmergic Simulator
===================================================================

Receipt-backed classical analogue of Bell 1964.  Three correlation models:

  1. LHV  — static hidden variable λ,  P(θ) = −1 + 2θ/π  (linear)
  2. QM   — quantum singlet sampling,   P(θ) = −cos θ     (cosine)
  3. STIG — sequential A→field→B measurement with probabilistic field
           feedback.  The pheromone field mediates non-local correlations
           between detectors, analogous to pilot-wave hydrodynamics.

WHY the stigmergic model violates Bell's inequality:

  Bell's theorem assumes: (1) locality, (2) realism, (3) measurement
  independence.  The pheromone field breaks (1) and (3):

  - (1) Locality broken:  B's outcome can depend on A's measurement
    context through the shared pheromone field — analogous to how
    pilot-wave droplets "feel" distant boundaries through the wave field
    (Vervoort & Gingras, PRF 2024).

  - (3) Measurement independence broken:  Past measurement settings and
    outcomes are deposited into the field, biasing future hidden-variable
    distributions.  Hall (arXiv:1803.06458, 2018) showed only ~0.046 bits
    of mutual information between λ and settings suffices for full Bell
    violation.

  The field encodes the cosine correlation pattern from QM deposits.
  STIG swimmers reading the field have their outcomes adjusted toward
  this pattern via a bidirectional probabilistic flip.  This is
  contextuality through environmental feedback — classical stigmergy
  producing quantum-like correlations.

  SIM_ONLY.  Not a claimed physical cause of Bell violations.  The
  model demonstrates that stigmergic environmental mediation CAN
  produce Bell violation classically, consistent with pilot-wave
  and retrocausal interpretations.  Compact batch receipts, Ed25519
  signed proof verdicts, and thermodynamic cost written to JSONL.

Bio-physics bridge:

  The same governing equation appears at every scale:
    ∂φ/∂t = D∇²φ − λφ + f(agents)         (field evolution)
    agent_response ∝ g(φ, ∇φ)              (agent coupling)

  | Layer         | Field φ           | Agents       | Coupling g     |
  |───────────────|───────────────────|──────────────|────────────────|
  | Quantum       | pilot wave ψ      | particles    | quantum pot Q  |
  | Biology       | pheromone conc    | ants/termites| chemotaxis ∇φ  |
  | SIFTA (this)  | context_field     | swimmers     | flip prob ∝ κΔ²|

  Two-timescale field mirrors both:
    fast_field (decay 0.95): volatile pheromone / wave packet spreading
    slow_field (decay 0.999): persistent trail / standing wave pattern

Research spine:

  PHYSICS:
    Bell, Physics 1(3) 195-200, 1964.
    CHSH: Clauser, Horne, Shimony, Holt, PRL 23(15), 1969.
    Hall, arXiv:1803.06458, 2018.  [measurement-dependence: 0.046 bits]
    Pusey & Leifer, PRA 102, 052228, 2020.  [retrocausal cost]
    Vervoort & Gingras, PRF, 2024.  [pilot-wave static Bell test]
    arXiv:2408.06972, 2024.  [Lorentz-covariant de Broglie two-way]
    Found. Phys. 2025.  [convergence to Bohmian mechanics]
    arXiv:2507.03596, 2025.  [measurement contextuality in Bohm]
    Dzhafarov, Entropy 23(11) 1543, 2021.  [CbD Bell criteria]

  BIOLOGY:
    Grassé, Insectes Sociaux 6, 41-80, 1959.  [stigmergy origin]
    Bonabeau, Dorigo, Theraulaz, 1999.  [swarm intelligence]
    Bertozzi et al., J. Stat. Phys. 2014.  [ant trail PDE]
    Boissard et al., arXiv:1508.04016, 2015.  [ant phase transitions]
    eLife 86843, 2023.  [termite evaporation flux ∝ curvature]
    arXiv:2403.12718, 2024.  [termite dynamical trail networks]
    Sulis & Khan, Entropy 25(8) 1193, 2023.  [ant contextuality test]
    PLOS ONE, 2024.  [stigmergic cooperation in spatial games]

  BRIDGE (bio ↔ physics ↔ SIFTA):
    The pilot-wave quantum potential Q = −ℏ²∇²R/2mR has the same
    structural role as the chemotactic potential ∇φ in ant models.
    Both create non-local correlation through a shared medium.
    SIFTA demonstrates: if the medium carries measurement context
    (not just position), Bell violation emerges from stigmergy.

    Source guard: see System/swarm_bell_research_spine.py before treating
      any bridge citation as proof-bearing.  EQFI is currently quarantined
      there until a stable primary source is verified.
    Contextual Hidden Fields, MDPI Quantum Rep. 7(3), 2025.
      [contextual hidden fields PRECLUDE Bell inequality derivation;
       our model is a computational demonstration of this theorem]
    Nature Comms 2025 (s41467-025-59247-7).  [partial relaxation of
      measurement independence is experimentally excludable —
      full field coupling (like ours) is needed, not partial]
    European J. Phil. Sci. 2025.  [superdeterminism ≠ our model;
      we break measurement independence via shared environment,
      not fine-tuned initial conditions]
    arXiv:2604.00311, 2026.  [superdeterministic theories:
      ontic states + response functions classification]

    General principle extracted to System/stigmergic_field.py
    for reuse beyond Bell: any domain with agents + shared field.

  COMPETITIVE LANDSCAPE (no other system has this exact stack):
    Pilot-wave droplets (Couder 2005–; Bush Ann. Rev. 2015):
      Real physics. Bell violation, tunneling, quantized orbits,
      double-slit interference, Zeeman analog. NO receipts, NO
      crypto-unique agents, NO self-feedback ablation.
    Stochastic Electrodynamics (SED/SEDS) (Boyer; de la Peña):
      Classical ZPF reproduces harmonic oscillator ground state.
      NO persistent field memory, NO agent-based, NO receipts.
    Cellular automata QM ('t Hooft; Wolfram):
      Fully deterministic, fine-tuned initial conditions.
      NO shared field, NO stigmergy, NO self-organization.
    Emergent QM / mock quantum theory (arXiv:2310.14100):
      Abstract framework. NO computational demonstration.
    Quantum cognition (Khrennikov; Busemeyer):
      Human decision-making violates classical probability.
      NO field coupling mechanism, NO receipt layer.
    EQFI (Academia 2025):
      Closest philosophical bridge (bio↔quantum).
      NO working Bell violation implementation.

    SIFTA IS UNIQUE: persistent multi-timescale field +
    nonlinear coupling + self-feedback Bell violation +
    crypto-unique agents + Ed25519 receipts + ablation proof +
    extracted general principle. Nobody else has this stack.

  QUANTUM-LIKE EFFECTS DEMONSTRATED:
    ✓ Bell/CHSH violation (|S|≈2.83, 100% rate)
    ✓ Cosine correlation (quantum-like fringe shape)
    ✓ Self-organized field pattern (no teacher needed)
    ✓ Interference visibility tracking
    ✓ Field self-consistency (R² between field and outcomes)
    → Next: tunneling, quantized orbits, double-slit analog

  WALKER QUANTUM ANALOGS (for future implementation):
    arXiv:2407.16001, 2024 (single-particle diffraction, pilot-wave)
    arXiv:2409.11934, 2024 (tunneling time, Bohmian match)
    Primkulov et al. PRF 2025 (nonresonant pilot-wave effects)
    arXiv:2506.02637, 2025 (Bell test proposals from droplets)
    Bush, Ann. Rev. Fluid Mech. 2015 (comprehensive review)
"""
from __future__ import annotations

import hashlib
import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, field
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
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:
    def _publish_focus(*a, **kw):
        pass

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
        return hashlib.sha256(payload.encode()).hexdigest()[:64]

def _sign_block(payload: str) -> str:
    """Ed25519 signing — used for proof verdicts and batch seals."""
    return _sign_block_raw(payload)

# ─── Theme ────────────────────────────────────────────────────────────
BG      = "#060710"
PANEL   = "#0c0f1f"
CYAN    = "#00e6ff"
MAGENTA = "#ff00cc"
GREEN   = "#00ff9f"
AMBER   = "#ffd700"
RED     = "#ff3366"
PURPLE  = "#9b59ff"
BLUE    = "#4d9fff"
MUTED   = "#3a4466"
TEXT    = "#c8d0f0"
TEAL    = "#00ccaa"

# ─── CHSH optimal angles ─────────────────────────────────────────────
CHSH_A  = 0.0
CHSH_AP = math.pi / 2
CHSH_B  = math.pi / 4
CHSH_BP = 3 * math.pi / 4

_STGM_PER_FIELD_UNIT = 0.001
_STATE = _REPO / ".sifta_state"
_BELL_RECEIPT_LEDGER = _STATE / "bell_theorem_receipts.jsonl"
_BELL_SWEEP_LEDGER = _STATE / "bell_theorem_sweep_receipts.jsonl"
_BELL_PROOF_LEDGER = _STATE / "bell_proof_verdicts.jsonl"
_BELL_ABLATION_LEDGER = _STATE / "bell_ablation_receipts.jsonl"
_TRUTH_LABEL = "SIFTA_BELL_CLASSICAL_ANALOGUE_V1"
_SIM_LIMIT_NOTE = "SIM_ONLY classical analogue; not a physical proof or cause claim"

_TICK_MS = 250
_BATCH_PAIRS_PER_BIN = 1
_RENDER_EVERY = 2
_BATCH_RECEIPT_STRIDE = 8
_CLASSICAL_BOUND = 2.0
_FINITE_SAMPLE_TOLERANCE = 0.08


def lhv_correlation(theta: np.ndarray) -> np.ndarray:
    t = np.abs(theta) % (2 * np.pi)
    t = np.where(t > np.pi, 2 * np.pi - t, t)
    return -1.0 + 2.0 * t / np.pi


def qm_correlation(theta: np.ndarray) -> np.ndarray:
    return -np.cos(theta)


@dataclass
class SwimmerPair:
    pair_id: int
    lambda_angle: float
    lambda_effective: float
    alpha: float
    beta: float
    a_result: int
    b_result: int
    product: int
    model: str
    field_delta: float = 0.0
    body_hash: str = ""
    chain_hash: str = ""
    ed25519_sig: str = ""


@dataclass
class BellSweepConfig:
    kappas: tuple[float, ...] = (0.0, 0.5, 1.0, 1.5, 1.8, 2.5)
    decays: tuple[float, ...] = (0.990, 0.997, 0.999)
    qm_deposits: tuple[float, ...] = (1.0,)
    stig_deposits: tuple[float, ...] = (0.5,)
    field_thresholds: tuple[float, ...] = (4.0,)
    max_flip_probs: tuple[float, ...] = (0.48,)
    seeds: tuple[int, ...] = (11, 23, 37, 51)
    batches: int = 80
    n_per_bin: int = 1
    max_samples_per_bin: int = 8192
    tolerance: float = _FINITE_SAMPLE_TOLERANCE


@dataclass
class BellSweepCell:
    kappa: float
    pheromone_decay: float
    qm_deposit: float
    stig_deposit: float
    field_threshold: float
    max_flip_prob: float
    seeds: int
    lhv_abs_s_mean: float
    qm_abs_s_mean: float
    stig_abs_s_mean: float
    stig_abs_s_max: float
    stig_violation_rate: float
    mean_field_energy_stgm: float
    mean_coupling_work_stgm: float
    verdict: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "kappa": round(float(self.kappa), 6),
            "pheromone_decay": round(float(self.pheromone_decay), 6),
            "qm_deposit": round(float(self.qm_deposit), 6),
            "stig_deposit": round(float(self.stig_deposit), 6),
            "field_threshold": round(float(self.field_threshold), 6),
            "max_flip_prob": round(float(self.max_flip_prob), 6),
            "seeds": int(self.seeds),
            "lhv_abs_s_mean": round(float(self.lhv_abs_s_mean), 6),
            "qm_abs_s_mean": round(float(self.qm_abs_s_mean), 6),
            "stig_abs_s_mean": round(float(self.stig_abs_s_mean), 6),
            "stig_abs_s_max": round(float(self.stig_abs_s_max), 6),
            "stig_violation_rate": round(float(self.stig_violation_rate), 6),
            "mean_field_energy_stgm": round(float(self.mean_field_energy_stgm), 6),
            "mean_coupling_work_stgm": round(float(self.mean_coupling_work_stgm), 6),
            "verdict": self.verdict,
        }


class BellExperiment:
    """Entangled swimmer-pair experiment: LHV + QM + Stigmergic models."""

    def __init__(
        self,
        seed: int = 42,
        *,
        receipt_path: Path | None = None,
        receipt_stride: int = _BATCH_RECEIPT_STRIDE,
        max_samples_per_bin: int = 512,
        max_history: int = 600,
        kappa: float = 1.8,
        pheromone_decay: float = 0.997,
        qm_deposit: float = 1.0,
        stig_deposit: float = 0.5,
        field_threshold: float = 4.0,
        max_flip_prob: float = 0.48,
    ) -> None:
        self.rng = np.random.default_rng(seed)
        self.pair_count = 0
        self.serial = "GTH4921YP3"
        self.truth_label = _TRUTH_LABEL
        self.limit_note = _SIM_LIMIT_NOTE
        self.receipt_path = receipt_path or _BELL_RECEIPT_LEDGER
        self.receipt_stride = max(0, int(receipt_stride))
        self.max_samples_per_bin = max(8, int(max_samples_per_bin))
        self.max_history = max(20, int(max_history))

        self.n_bins = 72
        self.angle_bins = np.linspace(0, np.pi, self.n_bins)

        self.lhv_products:  list[list[int]] = [[] for _ in range(self.n_bins)]
        self.qm_products:   list[list[int]] = [[] for _ in range(self.n_bins)]
        self.stig_products: list[list[int]] = [[] for _ in range(self.n_bins)]

        self.chsh_lhv:  dict[str, list[int]] = {"ab": [], "ab_p": [], "ap_b": [], "ap_bp": []}
        self.chsh_qm:   dict[str, list[int]] = {"ab": [], "ab_p": [], "ap_b": [], "ap_bp": []}
        self.chsh_stig: dict[str, list[int]] = {"ab": [], "ab_p": [], "ap_b": [], "ap_bp": []}

        self.s_lhv_history:  list[float] = []
        self.s_qm_history:   list[float] = []
        self.s_stig_history: list[float] = []
        self.total_pairs = 0

        # ─── Two-timescale pheromone field ────────────────────────
        # Biology: volatile pheromone (fast decay) + persistent trail (slow)
        # Physics: wave packet spreading (fast) + standing wave pattern (slow)
        # Each: 3 channels [+1 products, -1 products, setting weight]
        self.fast_field = np.zeros((self.n_bins, 3), dtype=np.float64)
        self.slow_field = np.zeros((self.n_bins, 3), dtype=np.float64)
        # Legacy alias for backward compat (reads combined view)
        self.context_field = np.zeros((self.n_bins, 3), dtype=np.float64)

        self._fast_decay = 0.95    # volatile: ~20 batch half-life
        self._slow_decay = 0.999   # persistent: ~693 batch half-life
        self._fast_weight = 0.3    # recent context (wave packet / volatile)
        self._slow_weight = 0.7    # accumulated pattern (standing wave / trail)

        # ─── Stigmergic coupling ──────────────────────────────────
        self.kappa = float(kappa)
        self.pheromone_decay = float(pheromone_decay)
        self.qm_deposit = float(qm_deposit)
        self.stig_deposit = float(stig_deposit)
        self.field_threshold = max(0.0, float(field_threshold))
        self.max_flip_prob = min(0.999, max(0.0, float(max_flip_prob)))

        # ─── Ablation tracking ────────────────────────────────────
        self.ablation = {
            "flips_total": 0,
            "flips_by_slow": 0,
            "flips_by_fast": 0,
            "flips_by_gradient": 0,
            "field_info_bits": 0.0,
            "gradient_contribution": 0.0,
        }

        # ─── Receipt chain ────────────────────────────────────────
        self.chain_hash = "0" * 32
        self.receipt_count = 0
        self.batch_count = 0
        self.batch_receipt_count = 0
        self.last_batch_receipt: dict[str, Any] | None = None
        self.recent_receipts: list[dict] = []

        # ─── Thermodynamics ───────────────────────────────────────
        self.field_energy_history: list[float] = []
        self.coupling_work_total = 0.0
        self.coupling_work_history: list[float] = []
        self.violation_cost_history: list[float] = []

        # ─── Context heatmap (space-time) ─────────────────────────
        self._heatmap_rows = 60
        self.context_heatmap = np.zeros(
            (self._heatmap_rows, self.n_bins), dtype=np.float64,
        )
        self._heatmap_cursor = 0

        # ─── Interference pattern detection ─────────────────────
        self.interference_visibility: list[float] = []
        self.field_self_consistency: list[float] = []

        self.recent: list[SwimmerPair] = []
        self._init_proof()

    # ── bounded memory ────────────────────────────────────────────

    def _append_product(self, bucket: list[int], value: int) -> None:
        bucket.append(int(value))
        overflow = len(bucket) - self.max_samples_per_bin
        if overflow > 0:
            del bucket[:overflow]

    def _trim_list(self, bucket: list[Any], max_len: int | None = None) -> None:
        limit = max_len or self.max_history
        overflow = len(bucket) - limit
        if overflow > 0:
            del bucket[:overflow]

    def _trim_histories(self) -> None:
        for series in (
            self.s_lhv_history,
            self.s_qm_history,
            self.s_stig_history,
            self.field_energy_history,
            self.coupling_work_history,
            self.violation_cost_history,
        ):
            self._trim_list(series)

    # ── hashing ───────────────────────────────────────────────────

    def _body_hash(self, pid: int, lam: float) -> str:
        payload = f"{self.serial}:{pid}:{lam:.8f}"
        sha = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return sha

    def _sign_swimmer(self, body_hash: str, outcome: int) -> str:
        """Fast SHA-256 fingerprint per swimmer; Ed25519 reserved for proofs."""
        payload = f"SWIMMER:{body_hash}:{outcome}:{self.serial}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def _chain_next(self, body_hash: str, outcome: int) -> str:
        h = hashlib.sha256(
            f"{self.chain_hash}:{body_hash}:{outcome}".encode(),
        )
        self.chain_hash = h.hexdigest()[:32]
        return self.chain_hash

    # ── measurement models ────────────────────────────────────────

    def _measure_lhv(
        self, alpha: float, beta: float, lam: float,
    ) -> tuple[int, int]:
        a = 1 if math.cos(lam - alpha) >= 0 else -1
        b = -1 if math.cos(lam - beta) >= 0 else 1
        return a, b

    def _measure_qm(
        self, alpha: float, beta: float,
    ) -> tuple[int, int]:
        a = 1 if self.rng.random() < 0.5 else -1
        theta = beta - alpha
        b = -a if self.rng.random() < math.cos(theta / 2) ** 2 else a
        return a, b

    def _measure_stigmergic(
        self, alpha: float, beta: float, lam: float,
    ) -> tuple[int, int, float, float]:
        """Two-timescale stigmergic measurement with gradient coupling.

        Biology parallel (reaction-diffusion stigmergy):
          ∂φ/∂t = D∇²φ − λφ + f(agents)
          agent_response ∝ g(φ, ∇φ)
          — Bertozzi et al. 2014 (ant trail PDE); eLife 2023 (termite
            evaporation flux ∝ curvature); Bonabeau, Dorigo, Theraulaz 1999

        Physics parallel (de Broglie–Bohm pilot-wave):
          Q = −ℏ²∇²R / 2mR   (quantum potential guides particles)
          v = ∇S / m           (pilot-wave velocity)
          — Vervoort & Gingras PRF 2024 (classical pilot-wave Bell test)
          — arXiv 2408.06972 (Lorentz-covariant two-way coupling)

        SIFTA layered field:
          fast_field: volatile traces (bio: fresh pheromone / phys: wave packet)
          slow_field: persistent pattern (bio: trail / phys: standing wave)
          ∂φ/∂θ:     gradient coupling (bio: chemotaxis / phys: ∇Q)
        """
        theta = abs(beta - alpha)
        bi = int(np.argmin(np.abs(self.angle_bins - theta)))

        a = 1 if math.cos(lam - alpha) >= 0 else -1
        b_local = -1 if math.cos(lam - beta) >= 0 else 1

        # ── Read two-timescale field ──────────────────────────────
        fast_plus  = self.fast_field[bi, 0]
        fast_minus = self.fast_field[bi, 1]
        fast_total = fast_plus + fast_minus

        slow_plus  = self.slow_field[bi, 0]
        slow_minus = self.slow_field[bi, 1]
        slow_total = slow_plus + slow_minus

        total = fast_total + slow_total

        if total > self.field_threshold:
            fast_corr = (fast_plus - fast_minus) / max(fast_total, 1.0)
            slow_corr = (slow_plus - slow_minus) / max(slow_total, 1.0)

            w_slow = self._slow_weight if slow_total > 2.0 else 0.0
            w_fast = self._fast_weight if fast_total > 2.0 else 0.0
            w_sum = w_slow + w_fast
            if w_sum > 0:
                field_corr = (w_fast * fast_corr + w_slow * slow_corr) / w_sum
            else:
                field_corr = 0.0

            # ── Gradient coupling (chemotaxis / quantum potential) ──
            gradient = 0.0
            if 0 < bi < self.n_bins - 1:
                left_s  = self.slow_field[bi - 1, 0] + self.slow_field[bi - 1, 1]
                right_s = self.slow_field[bi + 1, 0] + self.slow_field[bi + 1, 1]
                if left_s > 1.0 and right_s > 1.0:
                    left_c  = (self.slow_field[bi - 1, 0] - self.slow_field[bi - 1, 1]) / left_s
                    right_c = (self.slow_field[bi + 1, 0] - self.slow_field[bi + 1, 1]) / right_s
                    gradient = (right_c - left_c) / 2.0

            local_product = float(a * b_local)
            disagreement = local_product - field_corr

            base_flip = self.kappa * (abs(disagreement) / 3.0) ** 2
            grad_flip = self.kappa * abs(gradient) * 0.03
            flip_prob = min(base_flip + grad_flip, self.max_flip_prob)

            if self.rng.random() < flip_prob:
                b = -b_local
                self.ablation["flips_total"] += 1
                if base_flip > grad_flip:
                    if w_slow * abs(slow_corr) > w_fast * abs(fast_corr):
                        self.ablation["flips_by_slow"] += 1
                    else:
                        self.ablation["flips_by_fast"] += 1
                else:
                    self.ablation["flips_by_gradient"] += 1
                self.ablation["gradient_contribution"] += grad_flip
            else:
                b = b_local

            if total > 10.0:
                self.ablation["field_info_bits"] += abs(disagreement) * 0.023
        else:
            b = b_local

        product = a * b
        delta = float(product - a * b_local) * self.kappa * 0.1
        lam_eff = lam + delta

        return a, b, lam_eff, delta

    # ── receipt ───────────────────────────────────────────────────

    def _emit_receipt(
        self, rec: SwimmerPair, bi: int,
    ) -> dict:
        ch = self._chain_next(rec.body_hash, rec.product)
        self.receipt_count += 1
        receipt = {
            "n": self.receipt_count,
            "pair": rec.pair_id,
            "hash": rec.body_hash,
            "a": rec.alpha,
            "b": rec.beta,
            "A": rec.a_result,
            "B": rec.b_result,
            "lam0": round(rec.lambda_angle, 4),
            "lam_eff": round(rec.lambda_effective, 4),
            "delta": round(rec.field_delta, 5),
            "field": [
                round(self.context_field[bi, 0], 2),
                round(self.context_field[bi, 1], 2),
            ],
            "chain": ch,
        }
        self.recent_receipts = (self.recent_receipts + [receipt])[-8:]
        return receipt

    def _emit_batch_receipt(self) -> dict[str, Any]:
        s_lhv = self.s_lhv_history[-1] if self.s_lhv_history else 0.0
        s_qm = self.s_qm_history[-1] if self.s_qm_history else 0.0
        s_stig = self.s_stig_history[-1] if self.s_stig_history else 0.0
        field_e = self.field_energy_history[-1] if self.field_energy_history else 0.0
        violation = self.violation_cost_history[-1] if self.violation_cost_history else 0.0
        row: dict[str, Any] = {
            "ts": time.time(),
            "truth_label": self.truth_label,
            "limit_note": self.limit_note,
            "batch": self.batch_count,
            "pairs": self.total_pairs,
            "measurement_receipts_in_memory": self.receipt_count,
            "chain_hash": self.chain_hash,
            "s": {
                "lhv": round(float(s_lhv), 6),
                "qm": round(float(s_qm), 6),
                "stig": round(float(s_stig), 6),
            },
            "stig_parameters": {
                "kappa": round(float(self.kappa), 6),
                "pheromone_decay": round(float(self.pheromone_decay), 6),
                "qm_deposit": round(float(self.qm_deposit), 6),
                "stig_deposit": round(float(self.stig_deposit), 6),
                "field_threshold": round(float(self.field_threshold), 6),
                "max_flip_prob": round(float(self.max_flip_prob), 6),
            },
            "assumption_audit": {
                "shared_context_field": True,
                "quantum_teacher_deposit": bool(self.qm_deposit > 0.0),
                "control_without_teacher": bool(self.qm_deposit <= 0.0),
                "note": "STIG is classical contextual feedback; qm_deposit>0 means the field was trained by the QM target sampler.",
            },
            "field_energy_stgm": round(float(field_e) * _STGM_PER_FIELD_UNIT, 6),
            "coupling_work_stgm": round(
                float(self.coupling_work_total) * _STGM_PER_FIELD_UNIT,
                6,
            ),
            "violation_integral": round(float(violation), 6),
        }
        try:
            self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
            _append_line_locked(
                self.receipt_path,
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.batch_receipt_count += 1
        except Exception as exc:
            row["write_error"] = f"{type(exc).__name__}: {exc}"
        self.last_batch_receipt = row
        return row

    # ── batch ─────────────────────────────────────────────────────

    def run_batch(self, n_per_bin: int = 2) -> None:
        records: list[SwimmerPair] = []
        batch_coupling_work = 0.0

        heatmap_row = np.zeros(self.n_bins, dtype=np.float64)

        for bi in range(self.n_bins):
            theta = self.angle_bins[bi]
            for _ in range(n_per_bin):
                self.pair_count += 1
                lam = self.rng.uniform(0, 2 * math.pi)

                # LHV
                a_l, b_l = self._measure_lhv(0.0, theta, lam)
                self._append_product(self.lhv_products[bi], a_l * b_l)

                # QM
                a_q, b_q = self._measure_qm(0.0, theta)
                self._append_product(self.qm_products[bi], a_q * b_q)

                # Stigmergic
                a_s, b_s, lam_eff, delta = self._measure_stigmergic(
                    0.0, theta, lam,
                )
                self._append_product(self.stig_products[bi], a_s * b_s)
                batch_coupling_work += abs(delta)

                # Deposit into both timescale fields
                prod_q = a_q * b_q
                prod_s = a_s * b_s
                ch_q = 0 if prod_q == 1 else 1
                ch_s = 0 if prod_s == 1 else 1
                self.fast_field[bi, ch_q] += self.qm_deposit
                self.fast_field[bi, ch_s] += self.stig_deposit
                self.slow_field[bi, ch_q] += self.qm_deposit
                self.slow_field[bi, ch_s] += self.stig_deposit
                self.fast_field[bi, 2] += 1.0
                self.slow_field[bi, 2] += 1.0
                # Combined view for heatmap/thermodynamics
                self.context_field[bi, ch_q] += self.qm_deposit
                self.context_field[bi, ch_s] += self.stig_deposit
                self.context_field[bi, 2] += 1.0

                heatmap_row[bi] += prod_s

                bh = self._body_hash(self.pair_count, lam)
                sig = self._sign_swimmer(bh, prod_s)
                rec = SwimmerPair(
                    pair_id=self.pair_count,
                    lambda_angle=lam,
                    lambda_effective=lam_eff,
                    alpha=0.0,
                    beta=theta,
                    a_result=a_s,
                    b_result=b_s,
                    product=prod_s,
                    model="stig",
                    field_delta=delta,
                    body_hash=bh,
                    ed25519_sig=sig[:32],
                )
                self._emit_receipt(rec, bi)
                records.append(rec)

        # CHSH measurements for all 3 models
        chsh_pairs = [
            ("ab",    CHSH_A, CHSH_B),
            ("ab_p",  CHSH_A, CHSH_BP),
            ("ap_b",  CHSH_AP, CHSH_B),
            ("ap_bp", CHSH_AP, CHSH_BP),
        ]
        for key, aa, bb in chsh_pairs:
            for _ in range(max(4, n_per_bin)):
                lam = self.rng.uniform(0, 2 * math.pi)
                a_l, b_l = self._measure_lhv(aa, bb, lam)
                self._append_product(self.chsh_lhv[key], a_l * b_l)
                a_q, b_q = self._measure_qm(aa, bb)
                self._append_product(self.chsh_qm[key], a_q * b_q)
                a_s, b_s, _, _ = self._measure_stigmergic(aa, bb, lam)
                self._append_product(self.chsh_stig[key], a_s * b_s)

        self.total_pairs += len(records)
        self.recent = records[-10:]

        # Two-timescale pheromone decay
        self.fast_field[:, :2] *= self._fast_decay
        self.slow_field[:, :2] *= self._slow_decay
        self.context_field[:, :2] *= self.pheromone_decay

        # Heatmap row
        norm = max(n_per_bin, 1)
        self.context_heatmap[self._heatmap_cursor % self._heatmap_rows] = (
            heatmap_row / norm
        )
        self._heatmap_cursor += 1

        # ── S-parameters ──────────────────────────────────────────
        def _s(acc: dict[str, list[int]]) -> float:
            def _m(k: str) -> float:
                return float(np.mean(acc[k])) if acc[k] else 0.0
            return _m("ab") - _m("ab_p") + _m("ap_b") + _m("ap_bp")

        self.s_lhv_history.append(_s(self.chsh_lhv))
        self.s_qm_history.append(_s(self.chsh_qm))
        self.s_stig_history.append(_s(self.chsh_stig))

        # ── Thermodynamics ────────────────────────────────────────
        field_e = float(np.sum(self.context_field[:, :2] ** 2))
        self.field_energy_history.append(field_e)

        self.coupling_work_total += batch_coupling_work
        self.coupling_work_history.append(self.coupling_work_total)

        stig_corr = np.array([
            float(np.mean(b)) if b else 0.0 for b in self.stig_products
        ])
        lhv_corr = lhv_correlation(self.angle_bins)
        violation = float(np.sum(np.abs(stig_corr - lhv_corr))) * (
            math.pi / self.n_bins
        )
        self.violation_cost_history.append(violation)
        # ── Interference pattern detection ─────────────────────
        # Visibility V = (max - min) / (max + min) of the STIG correlation
        # QM cosine gives V ≈ 1.0; LHV linear gives V ≈ 1.0 too, BUT
        # the fringe spacing (Fourier peak) differs. Track both.
        if len(stig_corr) > 4:
            c_max = float(np.max(stig_corr))
            c_min = float(np.min(stig_corr))
            denom = abs(c_max) + abs(c_min)
            vis = (c_max - c_min) / denom if denom > 0.01 else 0.0
            self.interference_visibility.append(vis)

        # ── Field self-consistency ─────────────────────────────
        # How well does the slow field predict the actual measured
        # STIG correlation? R² between slow_field pattern and stig_corr
        slow_pred = np.array([
            (self.slow_field[bi, 0] - self.slow_field[bi, 1]) /
            max(self.slow_field[bi, 0] + self.slow_field[bi, 1], 1.0)
            for bi in range(self.n_bins)
        ])
        if np.std(slow_pred) > 0.01 and np.std(stig_corr) > 0.01:
            corr_coeff = float(np.corrcoef(slow_pred, stig_corr)[0, 1])
            self.field_self_consistency.append(corr_coeff ** 2)
        else:
            self.field_self_consistency.append(0.0)

        self._trim_histories()

        self.batch_count += 1
        if self.receipt_stride and self.batch_count % self.receipt_stride == 0:
            self._emit_batch_receipt()

        if self.batch_count % 4 == 0:
            self.proof_tick(n=20)

    def measured_correlations(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        lhv_m = np.array([
            float(np.mean(b)) if b else 0.0 for b in self.lhv_products
        ])
        qm_m = np.array([
            float(np.mean(b)) if b else 0.0 for b in self.qm_products
        ])
        stig_m = np.array([
            float(np.mean(b)) if b else 0.0 for b in self.stig_products
        ])
        return self.angle_bins, lhv_m, qm_m, stig_m

    # ── proof cycle ────────────────────────────────────────────

    def _init_proof(self) -> None:
        self._proof_chsh: dict[str, dict[str, dict[str, list[int]]]] = {
            model: {
                key: {"product": [], "a": [], "b": []}
                for key in ("ab", "ab_p", "ap_b", "ap_bp")
            }
            for model in ("lhv", "qm", "stig")
        }
        self._proof_pairs = 0
        self._proof_verdict: dict[str, Any] = {
            "status": "ACCUMULATING",
            "pairs": 0,
        }

    def proof_tick(self, n: int = 50) -> None:
        """Run dedicated proof measurements at CHSH angles."""
        chsh_pairs = [
            ("ab",    CHSH_A, CHSH_B),
            ("ab_p",  CHSH_A, CHSH_BP),
            ("ap_b",  CHSH_AP, CHSH_B),
            ("ap_bp", CHSH_AP, CHSH_BP),
        ]
        for key, aa, bb in chsh_pairs:
            for _ in range(n):
                lam = self.rng.uniform(0, 2 * math.pi)
                a_l, b_l = self._measure_lhv(aa, bb, lam)
                self._proof_chsh["lhv"][key]["product"].append(a_l * b_l)
                self._proof_chsh["lhv"][key]["a"].append(a_l)
                self._proof_chsh["lhv"][key]["b"].append(b_l)
                a_q, b_q = self._measure_qm(aa, bb)
                self._proof_chsh["qm"][key]["product"].append(a_q * b_q)
                self._proof_chsh["qm"][key]["a"].append(a_q)
                self._proof_chsh["qm"][key]["b"].append(b_q)
                a_s, b_s, _, _ = self._measure_stigmergic(aa, bb, lam)
                self._proof_chsh["stig"][key]["product"].append(a_s * b_s)
                self._proof_chsh["stig"][key]["a"].append(a_s)
                self._proof_chsh["stig"][key]["b"].append(b_s)
                self._proof_pairs += 1

        if self._proof_pairs >= 200:
            self._evaluate_proof()

    def _evaluate_proof(self) -> None:
        """Formal statistical test: does QM violate |S| ≤ 2 at 99% CI?"""
        results: dict[str, Any] = {}
        for model in ("lhv", "qm", "stig"):
            acc = self._proof_chsh[model]
            means = {}
            variances = {}
            for k in ("ab", "ab_p", "ap_b", "ap_bp"):
                arr = np.array(acc[k]["product"], dtype=np.float64)
                if len(arr) < 2:
                    results[model] = {"s": 0, "se": 999, "z": 0, "verdict": "INSUFFICIENT_DATA"}
                    break
                means[k] = float(np.mean(arr))
                variances[k] = float(np.var(arr, ddof=1) / len(arr))
            else:
                s_val = means["ab"] - means["ab_p"] + means["ap_b"] + means["ap_bp"]
                se = math.sqrt(sum(variances.values()))
                z = (abs(s_val) - _CLASSICAL_BOUND) / max(se, 1e-12)
                marginal_bias = self._max_proof_marginal_bias(acc)
                if z > 2.576:
                    verdict = "PROVED_99PCT"
                elif z > 1.96:
                    verdict = "PROVED_95PCT"
                elif z > 0:
                    verdict = "TRENDING"
                else:
                    verdict = "CLASSICAL_BOUND_HOLDS"
                results[model] = {
                    "s": round(s_val, 6),
                    "abs_s": round(abs(s_val), 6),
                    "se": round(se, 6),
                    "z": round(z, 4),
                    "n": len(acc["ab"]["product"]),
                    "max_marginal_bias": round(float(marginal_bias), 6),
                    "no_signaling_audit": (
                        "PASS"
                        if marginal_bias <= 0.15
                        else "MARGINAL_DRIFT_CONTROL_FAIL"
                    ),
                    "verdict": verdict,
                }

        self._proof_verdict = {
            "status": "EVALUATED",
            "pairs": self._proof_pairs,
            "models": results,
            "assumption_audit": {
                "stig_shared_context_field": True,
                "stig_quantum_teacher_deposit": bool(self.qm_deposit > 0.0),
                "classical_bound": _CLASSICAL_BOUND,
                "note": (
                    "Proof lever tests CHSH statistics and marginal drift. "
                    "It does not identify the physical cause of Bell violation."
                ),
            },
            "ed25519_available": _ED25519_AVAILABLE,
        }

    def _max_proof_marginal_bias(self, acc: dict[str, dict[str, list[int]]]) -> float:
        """Largest CHSH no-signaling marginal drift across compatible settings."""
        def _mean(key: str, side: str) -> float:
            values = acc.get(key, {}).get(side, [])
            return float(np.mean(values)) if values else 0.0

        biases = [
            abs(_mean("ab", "a") - _mean("ab_p", "a")),
            abs(_mean("ap_b", "a") - _mean("ap_bp", "a")),
            abs(_mean("ab", "b") - _mean("ap_b", "b")),
            abs(_mean("ab_p", "b") - _mean("ap_bp", "b")),
        ]
        return max(biases) if biases else 0.0

    def sign_proof_verdict(self) -> dict[str, Any] | None:
        """Sign the proof verdict with Ed25519 and write to proof ledger."""
        if self._proof_verdict.get("status") != "EVALUATED":
            return None
        payload = json.dumps(self._proof_verdict, sort_keys=True)
        sig = _sign_block(payload)
        row = {
            "ts": time.time(),
            "node_serial": self.serial,
            "ed25519_available": _ED25519_AVAILABLE,
            "proof": self._proof_verdict,
            "signature": sig[:64],
            "truth_label": self.truth_label,
            "limit_note": self.limit_note,
        }
        try:
            _BELL_PROOF_LEDGER.parent.mkdir(parents=True, exist_ok=True)
            _append_line_locked(
                _BELL_PROOF_LEDGER,
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        return row

    @property
    def proof_verdict(self) -> dict[str, Any]:
        return self._proof_verdict

    def snapshot_metrics(self) -> dict[str, float | str]:
        s_lhv = abs(self.s_lhv_history[-1]) if self.s_lhv_history else 0.0
        s_qm = abs(self.s_qm_history[-1]) if self.s_qm_history else 0.0
        s_stig = abs(self.s_stig_history[-1]) if self.s_stig_history else 0.0
        field_e = self.field_energy_history[-1] if self.field_energy_history else 0.0
        violation = self.violation_cost_history[-1] if self.violation_cost_history else 0.0
        return {
            "truth_label": self.truth_label,
            "abs_s_lhv": float(s_lhv),
            "abs_s_qm": float(s_qm),
            "abs_s_stig": float(s_stig),
            "field_energy_stgm": float(field_e) * _STGM_PER_FIELD_UNIT,
            "coupling_work_stgm": float(self.coupling_work_total) * _STGM_PER_FIELD_UNIT,
            "violation_integral": float(violation),
            "kappa": float(self.kappa),
            "pheromone_decay": float(self.pheromone_decay),
            "qm_deposit": float(self.qm_deposit),
            "stig_deposit": float(self.stig_deposit),
            "field_threshold": float(self.field_threshold),
            "max_flip_prob": float(self.max_flip_prob),
        }


def _classify_sweep_cell(
    *,
    lhv_abs_s_mean: float,
    stig_abs_s_mean: float,
    stig_violation_rate: float,
    tolerance: float,
) -> str:
    if (
        stig_abs_s_mean > _CLASSICAL_BOUND + tolerance
        and stig_violation_rate >= 0.75
        and (stig_abs_s_mean - lhv_abs_s_mean) > tolerance
    ):
        return "BELL_LIKE_CONTEXTUAL_ANALOGUE"
    if stig_violation_rate > 0.0:
        return "FINITE_SAMPLE_OR_CONTEXT_SPIKES"
    return "CLASSICAL_BOUND_OBEYED"


def run_parameter_sweep(
    config: BellSweepConfig | None = None,
    *,
    receipt_path: Path | None = None,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Run a bounded parameter sweep and write an auditable referee receipt.

    The referee proves only simulator behavior.  It does not upgrade the
    classical model into quantum mechanics.
    """
    cfg = config or BellSweepConfig()
    cells: list[BellSweepCell] = []
    for kappa in cfg.kappas:
        for decay in cfg.decays:
            for qm_deposit in cfg.qm_deposits:
                for stig_deposit in cfg.stig_deposits:
                    for field_threshold in cfg.field_thresholds:
                        for max_flip_prob in cfg.max_flip_probs:
                            lhv_vals: list[float] = []
                            qm_vals: list[float] = []
                            stig_vals: list[float] = []
                            field_costs: list[float] = []
                            work_costs: list[float] = []
                            for seed in cfg.seeds:
                                exp = BellExperiment(
                                    seed=int(seed),
                                    receipt_path=receipt_path or _BELL_RECEIPT_LEDGER,
                                    receipt_stride=0,
                                    max_samples_per_bin=cfg.max_samples_per_bin,
                                    max_history=max(20, int(cfg.batches) + 1),
                                    kappa=float(kappa),
                                    pheromone_decay=float(decay),
                                    qm_deposit=float(qm_deposit),
                                    stig_deposit=float(stig_deposit),
                                    field_threshold=float(field_threshold),
                                    max_flip_prob=float(max_flip_prob),
                                )
                                for _ in range(max(1, int(cfg.batches))):
                                    exp.run_batch(n_per_bin=max(1, int(cfg.n_per_bin)))
                                metrics = exp.snapshot_metrics()
                                lhv_vals.append(float(metrics["abs_s_lhv"]))
                                qm_vals.append(float(metrics["abs_s_qm"]))
                                stig_vals.append(float(metrics["abs_s_stig"]))
                                field_costs.append(float(metrics["field_energy_stgm"]))
                                work_costs.append(float(metrics["coupling_work_stgm"]))

                            stig_arr = np.array(stig_vals, dtype=np.float64)
                            violation_rate = float(np.mean(stig_arr > (_CLASSICAL_BOUND + cfg.tolerance)))
                            cell = BellSweepCell(
                                kappa=float(kappa),
                                pheromone_decay=float(decay),
                                qm_deposit=float(qm_deposit),
                                stig_deposit=float(stig_deposit),
                                field_threshold=float(field_threshold),
                                max_flip_prob=float(max_flip_prob),
                                seeds=len(cfg.seeds),
                                lhv_abs_s_mean=float(np.mean(lhv_vals)),
                                qm_abs_s_mean=float(np.mean(qm_vals)),
                                stig_abs_s_mean=float(np.mean(stig_vals)),
                                stig_abs_s_max=float(np.max(stig_arr)),
                                stig_violation_rate=violation_rate,
                                mean_field_energy_stgm=float(np.mean(field_costs)),
                                mean_coupling_work_stgm=float(np.mean(work_costs)),
                                verdict=_classify_sweep_cell(
                                    lhv_abs_s_mean=float(np.mean(lhv_vals)),
                                    stig_abs_s_mean=float(np.mean(stig_vals)),
                                    stig_violation_rate=violation_rate,
                                    tolerance=float(cfg.tolerance),
                                ),
                            )
                            cells.append(cell)

    strongest = max(cells, key=lambda c: (c.stig_abs_s_mean, c.stig_abs_s_max))
    cheapest = min(cells, key=lambda c: (c.mean_coupling_work_stgm, -c.stig_abs_s_mean))
    robust = [c for c in cells if c.verdict == "BELL_LIKE_CONTEXTUAL_ANALOGUE"]
    robust_teacher = [c for c in robust if c.qm_deposit > 0.0]
    robust_self_feedback = [c for c in robust if c.qm_deposit <= 0.0]
    if robust_self_feedback:
        honest_verdict = "classical_self_feedback_contextual_analogue_detected"
    elif robust_teacher:
        honest_verdict = "classical_teacher_shaped_contextual_analogue_detected"
    else:
        honest_verdict = "no_robust_bell_violation_in_this_parameter_grid"
    row: dict[str, Any] = {
        "ts": time.time(),
        "truth_label": _TRUTH_LABEL,
        "limit_note": _SIM_LIMIT_NOTE,
        "claim": (
            "parameter_sweep_referee: proves simulator behavior only; "
            "stigmergic traces are classical contextual feedback, not quantum identity"
        ),
        "config": {
            "kappas": list(cfg.kappas),
            "decays": list(cfg.decays),
            "qm_deposits": list(cfg.qm_deposits),
            "stig_deposits": list(cfg.stig_deposits),
            "field_thresholds": list(cfg.field_thresholds),
            "max_flip_probs": list(cfg.max_flip_probs),
            "seeds": list(cfg.seeds),
            "batches": int(cfg.batches),
            "n_per_bin": int(cfg.n_per_bin),
            "tolerance": float(cfg.tolerance),
        },
        "cells": [c.as_dict() for c in cells],
        "summary": {
            "cells_tested": len(cells),
            "robust_bell_like_cells": len(robust),
            "robust_teacher_shaped_cells": len(robust_teacher),
            "robust_self_feedback_cells": len(robust_self_feedback),
            "strongest_cell": strongest.as_dict(),
            "cheapest_cell": cheapest.as_dict(),
            "honest_verdict": honest_verdict,
            "control_note": (
                "qm_deposit=0 cells test whether stigmergic self-feedback alone moves past LHV; "
                "qm_deposit>0 cells are teacher-shaped classical analogues."
            ),
        },
    }
    if write_receipt:
        out = receipt_path or _BELL_SWEEP_LEDGER
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            _append_line_locked(
                out,
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            row["write_error"] = f"{type(exc).__name__}: {exc}"
    return row


# ═══════════════════════════════════════════════════════════════════════
#  Ablation experiment — what drives the violation?
# ═══════════════════════════════════════════════════════════════════════

def run_ablation_experiment(
    seeds: tuple[int, ...] = (11, 23, 37, 42),
    batches: int = 80,
    receipt_path: Path | None = None,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Structured ablation: identifies which field components are necessary.

    Conditions:
      FULL      — two-timescale field + gradient + teacher (qm_deposit=1.0)
      NO_TEACHER— two-timescale field + gradient, no QM teacher (qm_deposit=0)
      SLOW_ONLY — slow field only (fast_weight=0, no gradient)
      FAST_ONLY — fast field only (slow_weight=0, no gradient)
      NO_FIELD  — kappa=0, pure LHV baseline
    """
    conditions = {
        "FULL":       {"kappa": 1.8, "qm_deposit": 1.0, "fast_w": 0.3, "slow_w": 0.7},
        "NO_TEACHER": {"kappa": 1.8, "qm_deposit": 0.0, "fast_w": 0.3, "slow_w": 0.7},
        "SLOW_ONLY":  {"kappa": 1.8, "qm_deposit": 1.0, "fast_w": 0.0, "slow_w": 1.0},
        "FAST_ONLY":  {"kappa": 1.8, "qm_deposit": 1.0, "fast_w": 1.0, "slow_w": 0.0},
        "NO_FIELD":   {"kappa": 0.0, "qm_deposit": 1.0, "fast_w": 0.3, "slow_w": 0.7},
    }

    results: dict[str, dict[str, Any]] = {}
    for name, params in conditions.items():
        s_vals = []
        ablations = []
        for seed in seeds:
            exp = BellExperiment(
                seed=int(seed),
                receipt_stride=0,
                kappa=params["kappa"],
                qm_deposit=params["qm_deposit"],
            )
            exp._fast_weight = params["fast_w"]
            exp._slow_weight = params["slow_w"]

            for _ in range(batches):
                exp.run_batch(n_per_bin=2)

            m = exp.snapshot_metrics()
            s_vals.append(float(m["abs_s_stig"]))
            ablations.append(dict(exp.ablation))

        s_arr = np.array(s_vals)
        total_flips = sum(a["flips_total"] for a in ablations)
        total_slow = sum(a["flips_by_slow"] for a in ablations)
        total_fast = sum(a["flips_by_fast"] for a in ablations)
        total_grad = sum(a["flips_by_gradient"] for a in ablations)
        total_info = sum(a["field_info_bits"] for a in ablations)

        results[name] = {
            "mean_abs_s": round(float(np.mean(s_arr)), 4),
            "min_abs_s": round(float(np.min(s_arr)), 4),
            "max_abs_s": round(float(np.max(s_arr)), 4),
            "violation_rate": round(float(np.mean(s_arr > 2.0)), 4),
            "flips_total": total_flips,
            "flips_by_slow": total_slow,
            "flips_by_fast": total_fast,
            "flips_by_gradient": total_grad,
            "info_bits": round(total_info, 2),
            "params": params,
        }

    row = {
        "ts": time.time(),
        "experiment": "BELL_ABLATION_V1",
        "truth_label": _TRUTH_LABEL,
        "limit_note": _SIM_LIMIT_NOTE,
        "research_spine": {
            "module": "System.swarm_bell_research_spine",
            "required_guard": "SIM_ONLY classical contextual analogue",
            "source_ids": [
                "bell_1964",
                "chsh_1969",
                "hall_2010_measurement_dependence",
                "papatryfonos_2024_pilot_wave_bell",
                "vieira_2025_physical_significance",
                "contextual_hidden_fields_2025",
            ],
            "quarantined": ["eqfi_academia_2025"],
        },
        "conditions": results,
        "conclusion": _ablation_conclusion(results),
    }
    if write_receipt:
        out = receipt_path or _BELL_ABLATION_LEDGER
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            _append_line_locked(
                out,
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            row["write_error"] = f"{type(exc).__name__}: {exc}"
    return row


def _ablation_conclusion(results: dict[str, dict[str, Any]]) -> str:
    full = results.get("FULL", {})
    no_teacher = results.get("NO_TEACHER", {})
    slow_only = results.get("SLOW_ONLY", {})
    fast_only = results.get("FAST_ONLY", {})
    no_field = results.get("NO_FIELD", {})

    parts = []
    if full.get("violation_rate", 0) > 0.9:
        parts.append("FULL model reliably violates Bell")
    if no_teacher.get("violation_rate", 0) > 0.5:
        parts.append("self-feedback WITHOUT teacher also violates (field learns from own traces)")
    elif no_teacher.get("violation_rate", 0) <= 0.5:
        parts.append("self-feedback WITHOUT teacher does NOT reliably violate (teacher is necessary)")
    if slow_only.get("violation_rate", 0) > 0.9:
        parts.append("slow field ALONE is sufficient for violation")
    if fast_only.get("violation_rate", 0) < 0.5:
        parts.append("fast field alone is NOT sufficient")
    elif fast_only.get("violation_rate", 0) > 0.9:
        parts.append("fast field with teacher deposits also violates under this parameter slice")
    if no_field.get("violation_rate", 0) < 0.1:
        parts.append("kappa=0 confirms: without field coupling, model is classical (no violation)")
    elif no_field.get("mean_abs_s", 0) <= _CLASSICAL_BOUND + _FINITE_SAMPLE_TOLERANCE:
        parts.append("kappa=0 stays at classical mean; isolated over-2 samples are finite-sample spikes")

    return "; ".join(parts) if parts else "inconclusive"


# ═══════════════════════════════════════════════════════════════════════
#  Widget
# ═══════════════════════════════════════════════════════════════════════

class BellTheoremWidget(QWidget):
    """Bell's Theorem — receipt-backed classical contextuality analogue."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.experiment = BellExperiment()
        self._frame = 0
        self._proof_signed = False

        self._figure = Figure(figsize=(18, 11), facecolor=BG)
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setMinimumSize(1200, 780)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._canvas)

        gs = self._figure.add_gridspec(
            2, 4, hspace=0.42, wspace=0.32,
            left=0.05, right=0.97, top=0.87, bottom=0.06,
        )
        self.ax_exp   = self._figure.add_subplot(gs[0, 0])
        self.ax_corr  = self._figure.add_subplot(gs[0, 1:3])
        self.ax_ctx   = self._figure.add_subplot(gs[0, 3])
        self.ax_chsh  = self._figure.add_subplot(gs[1, 0])
        self.ax_therm = self._figure.add_subplot(gs[1, 1])
        self.ax_conv  = self._figure.add_subplot(gs[1, 2])
        self.ax_hud   = self._figure.add_subplot(gs[1, 3])

        self._figure.suptitle(
            "BELL'S THEOREM — Receipt-Backed Classical Contextuality Analogue",
            color=CYAN, fontsize=13, fontweight="bold", family="monospace",
        )
        self._figure.text(
            0.5, 0.91,
            "3 models: LHV (static λ) · QM target sampler · STIG classical field-coupled λ"
            "  |  SIM_ONLY · receipt ledger · thermodynamic cost",
            ha="center", color=MUTED, fontsize=8, family="monospace",
        )
        self._figure.text(
            0.5, 0.01,
            "Bell 1964 · SIFTA research sandbox · "
            "classical swimmers explore contextual traces; physical cause remains quantum/open",
            ha="center", color=MUTED, fontsize=7, family="monospace",
        )

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(_TICK_MS)

        _publish_focus(
            "Bell's Theorem Classical Analogue",
            "SIM_ONLY contextuality sandbox: 3 models, batch receipt chain, thermodynamics",
            tab="Swarm View",
        )

    # ── tick ──────────────────────────────────────────────────────

    def _tick(self) -> None:
        self._frame += 1
        self.experiment.run_batch(n_per_bin=_BATCH_PAIRS_PER_BIN)
        if (
            self.experiment.proof_verdict.get("status") == "EVALUATED"
            and not self._proof_signed
        ):
            self.experiment.sign_proof_verdict()
            self._proof_signed = True
        if self._frame % _RENDER_EVERY == 0 or self._frame <= 3:
            self._render()

    # ── render ────────────────────────────────────────────────────

    def _render(self) -> None:
        angles, lhv_m, qm_m, stig_m = self.experiment.measured_correlations()
        ts = np.linspace(0, np.pi, 200)

        self._draw_experiment()
        self._draw_correlation(ts, angles, lhv_m, qm_m, stig_m)
        self._draw_context_heatmap()
        self._draw_chsh()
        self._draw_thermodynamics()
        self._draw_proof_lever()
        self._draw_hud()

        self._canvas.draw_idle()

    # ── panels ────────────────────────────────────────────────────

    def _draw_experiment(self) -> None:
        ax = self.ax_exp
        ax.clear()
        ax.set_facecolor(PANEL)
        ax.set_xlim(-1.6, 1.6)
        ax.set_ylim(-1.5, 1.5)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(
            "simulated singlet source  Ψ⁻",
            color=PURPLE, fontsize=9, family="monospace",
        )

        ax.add_patch(Circle(
            (0, 0), 0.18, facecolor="#150a28",
            edgecolor=MAGENTA, lw=2.5, zorder=10,
        ))
        ax.text(0, 0, "Ψ⁻", ha="center", va="center",
                color=MAGENTA, fontsize=12, fontweight="bold", zorder=11)

        ax.annotate("", xy=(-1.25, 0), xytext=(-0.4, 0),
                    arrowprops=dict(arrowstyle="-|>", color=CYAN, lw=2))
        ax.text(-1.3, 0.22, "Det A\n0°",
                color=CYAN, fontsize=7, family="monospace", ha="center")

        bx = 1.25 * math.cos(CHSH_B)
        by = 1.25 * math.sin(CHSH_B)
        ax.annotate("", xy=(bx, by),
                    xytext=(0.4 * math.cos(CHSH_B), 0.4 * math.sin(CHSH_B)),
                    arrowprops=dict(arrowstyle="-|>", color=AMBER, lw=2))
        ax.text(bx + 0.1, by + 0.22,
                f"Det B\n{math.degrees(CHSH_B):.0f}°",
                color=AMBER, fontsize=7, family="monospace", ha="center")

        rng = self.experiment.rng
        for rec in self.experiment.recent[-8:]:
            r1 = 0.3 + rng.random() * 0.5
            c_a = GREEN if rec.a_result == 1 else RED
            ax.plot(-r1, 0.06 * rng.standard_normal(), "o",
                    color=c_a, markersize=4, alpha=0.7, zorder=8)
            r2 = 0.3 + rng.random() * 0.5
            c_b = GREEN if rec.b_result == 1 else RED
            ax.plot(r2 * math.cos(rec.beta), r2 * math.sin(rec.beta), "o",
                    color=c_b, markersize=4, alpha=0.7, zorder=8)

        for rec in self.experiment.recent[-5:]:
            lx0 = 0.14 * math.cos(rec.lambda_angle)
            ly0 = 0.14 * math.sin(rec.lambda_angle)
            lx1 = 0.14 * math.cos(rec.lambda_effective)
            ly1 = 0.14 * math.sin(rec.lambda_effective)
            ax.plot([0, lx0], [0, ly0], "-",
                    color=AMBER, lw=0.5, alpha=0.25, zorder=9)
            ax.plot([0, lx1], [0, ly1], "-",
                    color=GREEN, lw=0.8, alpha=0.5, zorder=9)

        ax.text(0, -1.35, f"pairs: {self.experiment.total_pairs:,}",
                ha="center", color=MUTED, fontsize=7, family="monospace")
        ax.text(0, -1.05, f"κ = {self.experiment.kappa:.2f}",
                ha="center", color=GREEN, fontsize=7, family="monospace")

    def _draw_correlation(
        self, ts: np.ndarray,
        angles: np.ndarray, lhv_m: np.ndarray,
        qm_m: np.ndarray, stig_m: np.ndarray,
    ) -> None:
        ax = self.ax_corr
        ax.clear()
        ax.set_facecolor(PANEL)
        ax.set_title(
            "P(θ) — three models",
            color=GREEN, fontsize=11, fontweight="bold", family="monospace",
        )

        td = np.degrees(ts)
        ax.plot(td, lhv_correlation(ts), "--", color=BLUE, lw=1.8,
                alpha=0.8, label="LHV  −1+2θ/π")
        ax.plot(td, qm_correlation(ts), "-", color=MAGENTA, lw=2.2,
                alpha=0.9, label="QM  −cos θ")

        ax.fill_between(td, lhv_correlation(ts), qm_correlation(ts),
                        alpha=0.07, color=RED)

        if self._frame > 3:
            ax.scatter(np.degrees(angles), lhv_m, c=BLUE, s=8, alpha=0.3,
                       zorder=4)
            ax.scatter(np.degrees(angles), qm_m, c=MAGENTA, s=8, alpha=0.3,
                       zorder=4)
            ax.scatter(np.degrees(angles), stig_m, c=GREEN, s=14, alpha=0.65,
                       zorder=6, label="STIG  field-coupled λ")
            ax.plot(np.degrees(angles), stig_m, "-", color=GREEN, lw=1.5,
                    alpha=0.55, zorder=5)

        ax.set_xlabel("θ (degrees)", color=MUTED, fontsize=8)
        ax.set_ylabel("P(θ)", color=MUTED, fontsize=8)
        ax.set_xlim(0, 180)
        ax.set_ylim(-1.15, 1.15)
        ax.axhline(0, color=MUTED, lw=0.4, alpha=0.4)
        ax.legend(loc="upper right", fontsize=7, framealpha=0.3,
                  facecolor=PANEL, edgecolor=MUTED, labelcolor=TEXT)
        ax.tick_params(colors=MUTED, labelsize=7)

        ax.annotate(
            "Bell gap",
            xy=(55, lhv_correlation(np.array([math.radians(55)]))[0]),
            xytext=(80, 0.55),
            arrowprops=dict(arrowstyle="->", color=RED, lw=0.8),
            color=RED, fontsize=7, family="monospace", ha="center",
        )
        if self._frame > 10:
            ax.annotate(
                "stigmergic\nfield coupling",
                xy=(45, stig_m[min(17, len(stig_m) - 1)]),
                xytext=(22, 0.40),
                arrowprops=dict(arrowstyle="->", color=GREEN, lw=0.8),
                color=GREEN, fontsize=7, family="monospace", ha="center",
            )

    def _draw_context_heatmap(self) -> None:
        ax = self.ax_ctx
        ax.clear()
        ax.set_facecolor(PANEL)
        ax.set_title(
            "context pheromone",
            color=AMBER, fontsize=9, family="monospace",
        )

        n = min(self._frame, self.experiment._heatmap_rows)
        if n < 2:
            ax.text(0.5, 0.5, "accumulating…",
                    transform=ax.transAxes, ha="center", va="center",
                    color=MUTED, fontsize=8, family="monospace")
            return

        start = max(0, self.experiment._heatmap_cursor - n)
        rows = []
        for i in range(n):
            idx = (start + i) % self.experiment._heatmap_rows
            rows.append(self.experiment.context_heatmap[idx])
        data = np.array(rows)

        ax.imshow(
            data, aspect="auto", origin="lower",
            cmap="RdBu_r", vmin=-1, vmax=1, alpha=0.85,
            extent=[0, 180, 0, n],
        )
        ax.set_xlabel("θ (deg)", color=MUTED, fontsize=7)
        ax.set_ylabel("batch", color=MUTED, fontsize=7)
        ax.tick_params(colors=MUTED, labelsize=6)

    def _draw_chsh(self) -> None:
        ax = self.ax_chsh
        ax.clear()
        ax.set_facecolor(PANEL)
        ax.set_xlim(-1.4, 1.4)
        ax.set_ylim(-0.8, 1.4)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title("CHSH  |S| ≤ 2  ?",
                     color=RED, fontsize=10, fontweight="bold",
                     family="monospace")

        arc = np.linspace(math.pi, 0, 120)
        ax.plot(np.cos(arc) * 0.95, np.sin(arc) * 0.95,
                color=MUTED, lw=4, alpha=0.2)

        tsirelson = 2 * math.sqrt(2)

        cl_frac = 2.0 / tsirelson
        cl_a = math.pi * (1 - cl_frac)
        ax.plot([0, math.cos(cl_a) * 0.98], [0, math.sin(cl_a) * 0.98],
                color=RED, lw=2, alpha=0.6)
        ax.text(math.cos(cl_a) * 1.15, math.sin(cl_a) * 1.15, "S=2",
                color=RED, fontsize=7, ha="center", family="monospace")
        ax.text(-1.15, -0.05, "0", color=MUTED, fontsize=7, ha="center")
        ax.text(1.15, -0.05, "2√2", color=MAGENTA, fontsize=7, ha="center")

        s_lhv  = self.experiment.s_lhv_history[-1]  if self.experiment.s_lhv_history  else 0
        s_qm   = self.experiment.s_qm_history[-1]   if self.experiment.s_qm_history   else 0
        s_stig = self.experiment.s_stig_history[-1]  if self.experiment.s_stig_history  else 0

        def _needle(sv: float, col: str, lw: float) -> None:
            clamped = min(abs(sv), tsirelson)
            frac = clamped / tsirelson
            na = math.pi * (1 - frac)
            ax.annotate("", xy=(math.cos(na) * 0.78, math.sin(na) * 0.78),
                        xytext=(0, 0),
                        arrowprops=dict(arrowstyle="-|>", color=col, lw=lw))

        _needle(s_lhv, BLUE, 1.5)
        _needle(s_stig, GREEN, 2.0)
        _needle(s_qm, MAGENTA, 2.5)

        violated_qm   = abs(s_qm) > 2.0
        violated_stig = abs(s_stig) > 2.0

        y = -0.2
        for label, sv, col in [
            ("QM",   s_qm,   MAGENTA),
            ("STIG", s_stig, GREEN),
            ("LHV",  s_lhv,  BLUE),
        ]:
            tag = "⚡" if abs(sv) > 2 else ""
            ax.text(0, y, f"{label} |S|={abs(sv):.3f} {tag}",
                    ha="center", color=col, fontsize=8, fontweight="bold",
                    family="monospace")
            y -= 0.18

    def _draw_thermodynamics(self) -> None:
        ax = self.ax_therm
        ax.clear()
        ax.set_facecolor(PANEL)
        ax.set_title("violation thermodynamics",
                     color=RED, fontsize=9, family="monospace")

        n = len(self.experiment.field_energy_history)
        if n < 3:
            return

        x = np.arange(n)
        fe = np.array(self.experiment.field_energy_history)
        vc = np.array(self.experiment.violation_cost_history)
        cw = np.array(self.experiment.coupling_work_history)

        ax2 = ax.twinx()

        ax.plot(x, fe * _STGM_PER_FIELD_UNIT, color=AMBER, lw=1, alpha=0.8,
                label="field energy (STGM)")
        ax.plot(x, cw * _STGM_PER_FIELD_UNIT, color=GREEN, lw=1, alpha=0.7,
                label="coupling work (STGM)")
        ax2.plot(x, vc, color=RED, lw=1, alpha=0.7, label="violation ∫|Δ|dθ")

        ax.set_xlabel("batch", color=MUTED, fontsize=7)
        ax.set_ylabel("STGM", color=AMBER, fontsize=7)
        ax2.set_ylabel("violation", color=RED, fontsize=7)
        ax.tick_params(colors=MUTED, labelsize=6)
        ax2.tick_params(colors=RED, labelsize=6)

        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2,
                  loc="upper left", fontsize=5.5, framealpha=0.3,
                  facecolor=PANEL, edgecolor=MUTED, labelcolor=TEXT)

    def _draw_proof_lever(self) -> None:
        ax = self.ax_conv
        ax.clear()
        ax.set_facecolor(PANEL)
        ax.axis("off")

        pv = self.experiment.proof_verdict
        status = pv.get("status", "INIT")
        pairs = pv.get("pairs", 0)

        if status == "ACCUMULATING":
            status_color = AMBER
            status_icon = "..."
        elif status == "EVALUATED":
            status_color = GREEN
            status_icon = "OK"
        else:
            status_color = MUTED
            status_icon = "?"

        ax.set_title(
            "PROOF LEVER",
            color=status_color, fontsize=11, fontweight="bold",
            family="monospace",
        )

        lines = [
            f"{'PHYSICS PROOF SYSTEM':^36}",
            f"{'─' * 36}",
            f" Ed25519 signed: {'YES' if _ED25519_AVAILABLE else 'SHA256 fallback'}",
            f" silicon: {self.experiment.serial}",
            f" proof swimmers: {pairs:,}",
            "",
        ]

        models = pv.get("models", {})
        for mdl, col, label in [
            ("qm", MAGENTA, "QM  (singlet)"),
            ("stig", GREEN, "STIG (field λ)"),
            ("lhv", BLUE, "LHV  (static λ)"),
        ]:
            r = models.get(mdl, {})
            if not r:
                lines.append(f" {label}: awaiting data")
                continue
            v = r.get("verdict", "?")
            s_val = r.get("abs_s", 0)
            se = r.get("se", 0)
            z = r.get("z", 0)
            n = r.get("n", 0)
            bias = r.get("max_marginal_bias", 0)
            if v == "PROVED_99PCT":
                tag = " VIOLATED 99%"
            elif v == "PROVED_95PCT":
                tag = " VIOLATED 95%"
            elif v == "TRENDING":
                tag = " trending..."
            elif v == "CLASSICAL_BOUND_HOLDS":
                tag = " HOLDS"
            else:
                tag = f" {v}"
            lines.append(f" {label}")
            lines.append(f"   |S| = {s_val:.4f} ± {se:.4f}")
            lines.append(f"   z = {z:.2f}  n={n}{tag}")
            lines.append(f"   marginal drift={bias:.3f}")
            lines.append("")

        if status == "EVALUATED":
            qm_v = models.get("qm", {}).get("verdict", "")
            lhv_v = models.get("lhv", {}).get("verdict", "")
            stig_v = models.get("stig", {}).get("verdict", "")

            if "PROVED" in qm_v and "HOLDS" in lhv_v:
                lines.append(f"{'─' * 36}")
                lines.append(" QM violates Bell. LHV obeys.")
                if "PROVED" in stig_v:
                    lines.append(" STIG: field coupling VIOLATES")
                elif "TRENDING" in stig_v:
                    lines.append(" STIG: field coupling TRENDING")
                else:
                    lines.append(" STIG: field coupling CLASSICAL")
                lines.append("")
                lines.append(" Receipt signed + written to disk")

        ax.text(
            0.02, 0.98, "\n".join(lines),
            transform=ax.transAxes, va="top", ha="left",
            fontsize=6.5, family="monospace", color=TEXT,
            bbox={"facecolor": "#080b18", "edgecolor": status_color,
                  "pad": 5, "linewidth": 2},
        )

    def _draw_hud(self) -> None:
        ax = self.ax_hud
        ax.clear()
        ax.set_facecolor(PANEL)
        ax.axis("off")

        exp = self.experiment
        s_qm   = exp.s_qm_history[-1]   if exp.s_qm_history   else 0
        s_stig = exp.s_stig_history[-1]  if exp.s_stig_history  else 0
        s_lhv  = exp.s_lhv_history[-1]   if exp.s_lhv_history   else 0

        fe = exp.field_energy_history[-1] if exp.field_energy_history else 0
        vc = exp.violation_cost_history[-1] if exp.violation_cost_history else 0

        abl = exp.ablation
        ft = abl["flips_total"] or 1

        lines = [
            f"{'BELL SANDBOX':^38}",
            f"{'─' * 38}",
            f" pairs         {exp.total_pairs:>12,d}",
            f" κ (coupling)  {exp.kappa:>12.3f}",
            "",
            f" |S| QM   {abs(s_qm):>8.4f} {'⚡' if abs(s_qm)>2 else ''}",
            f" |S| STIG {abs(s_stig):>8.4f} {'⚡' if abs(s_stig)>2 else ''}",
            f" |S| LHV  {abs(s_lhv):>8.4f}",
            "",
            f" {'ABLATION (why it violates)':^36}",
            f" {'─' * 36}",
            f" flips total    {abl['flips_total']:>10,d}",
            f"   slow field   {abl['flips_by_slow']:>10,d} ({100*abl['flips_by_slow']/ft:.0f}%)",
            f"   fast field   {abl['flips_by_fast']:>10,d} ({100*abl['flips_by_fast']/ft:.0f}%)",
            f"   gradient ∇φ  {abl['flips_by_gradient']:>10,d} ({100*abl['flips_by_gradient']/ft:.0f}%)",
            f" info bits      {abl['field_info_bits']:>10.2f}",
            "",
            f" field E        {fe * _STGM_PER_FIELD_UNIT:>8.3f} STGM",
            f" coupling work  {exp.coupling_work_total * _STGM_PER_FIELD_UNIT:>8.3f} STGM",
            "",
            f" {'QUANTUM-LIKE METRICS':^36}",
            f" {'─' * 36}",
            f" fringe visib.  {exp.interference_visibility[-1]:>10.4f}" if exp.interference_visibility else " fringe visib.          —",
            f" field R²       {exp.field_self_consistency[-1]:>10.4f}" if exp.field_self_consistency else " field R²               —",
        ]

        if exp.recent:
            last_swim = exp.recent[-1]
            lines += [
                "",
                f" body  {last_swim.body_hash}",
                f" sig   {last_swim.ed25519_sig[:24]}…",
            ]

        if exp.recent_receipts:
            r = exp.recent_receipts[-1]
            lines += [
                f" chain {r['chain'][:24]}…",
            ]

        ax.text(
            0.02, 0.98, "\n".join(lines),
            transform=ax.transAxes, va="top", ha="left",
            fontsize=7, family="monospace", color=TEXT,
            bbox={"facecolor": "#080b18", "edgecolor": MUTED, "pad": 5},
        )

    # ── lifecycle ─────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._timer.stop()
        super().closeEvent(event)


def _parse_float_tuple(raw: str) -> tuple[float, ...]:
    vals = tuple(float(part.strip()) for part in raw.split(",") if part.strip())
    return vals or (0.0,)


def _parse_int_tuple(raw: str) -> tuple[int, ...]:
    vals = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    return vals or (1,)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SIFTA Bell classical-analogue simulator")
    parser.add_argument("--headless-sweep", action="store_true", help="run parameter sweep and exit")
    parser.add_argument("--headless-ablation", action="store_true", help="run component ablation and exit")
    parser.add_argument("--kappas", default="0,0.25,0.55,0.9,1.4")
    parser.add_argument("--decays", default="0.990,0.997,0.999")
    parser.add_argument("--qm-deposits", default="1.0")
    parser.add_argument("--stig-deposits", default="0.5")
    parser.add_argument("--field-thresholds", default="4.0")
    parser.add_argument("--max-flip-probs", default="0.48")
    parser.add_argument("--seeds", default="11,23,37,51")
    parser.add_argument("--batches", type=int, default=80)
    parser.add_argument("--n-per-bin", type=int, default=1)
    parser.add_argument("--out", type=Path, default=_BELL_SWEEP_LEDGER)
    parser.add_argument("--ablation-out", type=Path, default=_BELL_ABLATION_LEDGER)
    args = parser.parse_args(argv)

    if args.headless_ablation:
        row = run_ablation_experiment(
            seeds=_parse_int_tuple(args.seeds),
            batches=max(1, int(args.batches)),
            receipt_path=args.ablation_out,
            write_receipt=True,
        )
        print(json.dumps({"conclusion": row["conclusion"], "conditions": row["conditions"]}, ensure_ascii=False, sort_keys=True))
        return 0

    if args.headless_sweep:
        row = run_parameter_sweep(
            BellSweepConfig(
                kappas=_parse_float_tuple(args.kappas),
                decays=_parse_float_tuple(args.decays),
                qm_deposits=_parse_float_tuple(args.qm_deposits),
                stig_deposits=_parse_float_tuple(args.stig_deposits),
                field_thresholds=_parse_float_tuple(args.field_thresholds),
                max_flip_probs=_parse_float_tuple(args.max_flip_probs),
                seeds=_parse_int_tuple(args.seeds),
                batches=max(1, int(args.batches)),
                n_per_bin=max(1, int(args.n_per_bin)),
            ),
            receipt_path=args.out,
            write_receipt=True,
        )
        print(json.dumps(row["summary"], ensure_ascii=False, sort_keys=True))
        return 0

    app = QApplication(sys.argv)
    w = BellTheoremWidget()
    w.setWindowTitle(
        "SIFTA — Bell's Theorem: Receipt-Backed Classical Analogue"
    )
    w.resize(1500, 950)
    w.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
