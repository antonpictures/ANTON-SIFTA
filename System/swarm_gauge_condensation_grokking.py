#!/usr/bin/env python3
"""Event 94: gauge ladders, condensation, and grokking diagnostics.

This module turns the Event 94 research backlog into executable, bounded
research scaffolding. It is deliberately small and SIM_ONLY:

- U(1)-style lattice links expose gauge-invariant plaquettes and Wilson loops.
- A Ginzburg-Landau order-parameter ladder models condensation as delayed
  macro-order from local reinforcement.
- A grokking detector distinguishes early memorization from delayed
  generalization.

Truth guard
-----------
This module does not implement quantum field theory, does not solve the Higgs
mechanism, and does not prove that LLM grokking is a gauge phenomenon. It gives
SIFTA a tested toy loop for the analogies named in Event 94.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np


TRUTH_LABEL = "SIFTA_EVENT94_GAUGE_CONDENSATION_GROKKING_V1"
EVENT94_TRUTH_GUARD = (
    "SIM_ONLY research loop. U(1) lattice links, GL condensation, and "
    "grokking-delay diagnostics are analogues for SIFTA routing/audit fields; "
    "they do not replace Yang-Mills theory, superconductivity, Higgs physics, "
    "or mechanistic interpretability."
)


def _wrap_angle(theta: np.ndarray | float) -> np.ndarray | float:
    """Wrap phase angles to (-pi, pi]."""
    return (np.asarray(theta) + math.pi) % (2.0 * math.pi) - math.pi


@dataclass(frozen=True)
class GaugeLatticeConfig:
    """Shape and coupling for a 2D periodic U(1)-style lattice."""

    height: int = 8
    width: int = 8
    coupling: float = 1.0

    def __post_init__(self) -> None:
        if self.height < 2 or self.width < 2:
            raise ValueError("gauge lattice needs at least 2x2 sites")
        if self.coupling <= 0:
            raise ValueError("coupling must be positive")


class U1GaugeLattice:
    """Small U(1)-style lattice for audit-loop invariance tests.

    `theta_x[y, x]` is the link from site `(y, x)` to `(y, x+1)`.
    `theta_y[y, x]` is the link from site `(y, x)` to `(y+1, x)`.
    """

    def __init__(
        self,
        config: GaugeLatticeConfig | None = None,
        *,
        theta_x: np.ndarray | None = None,
        theta_y: np.ndarray | None = None,
    ) -> None:
        self.config = config or GaugeLatticeConfig()
        shape = (self.config.height, self.config.width)
        self.theta_x = (
            np.zeros(shape, dtype=np.float64)
            if theta_x is None
            else np.array(theta_x, dtype=np.float64)
        )
        self.theta_y = (
            np.zeros(shape, dtype=np.float64)
            if theta_y is None
            else np.array(theta_y, dtype=np.float64)
        )
        if self.theta_x.shape != shape or self.theta_y.shape != shape:
            raise ValueError("theta_x and theta_y must match config shape")
        self.theta_x = _wrap_angle(self.theta_x)
        self.theta_y = _wrap_angle(self.theta_y)

    @classmethod
    def with_uniform_flux(
        cls,
        flux: float,
        config: GaugeLatticeConfig | None = None,
    ) -> "U1GaugeLattice":
        """Create a Landau-gauge-like field with nearly uniform plaquette flux."""
        cfg = config or GaugeLatticeConfig()
        theta_x = np.zeros((cfg.height, cfg.width), dtype=np.float64)
        theta_y = np.zeros((cfg.height, cfg.width), dtype=np.float64)
        for y in range(cfg.height):
            theta_x[y, :] = -float(flux) * y
        return cls(cfg, theta_x=theta_x, theta_y=theta_y)

    def copy(self) -> "U1GaugeLattice":
        return U1GaugeLattice(
            self.config,
            theta_x=self.theta_x.copy(),
            theta_y=self.theta_y.copy(),
        )

    def plaquette_angles(self) -> np.ndarray:
        """Return the oriented elementary loop phase at every lattice cell."""
        right_then_down = self.theta_x + np.roll(self.theta_y, -1, axis=1)
        down_then_right = self.theta_y + np.roll(self.theta_x, -1, axis=0)
        return _wrap_angle(right_then_down - down_then_right)

    def wilson_loop_phase(self, top: int, left: int, height: int, width: int) -> float:
        """Return a rectangular loop phase, invariant under local gauge shifts."""
        if height <= 0 or width <= 0:
            raise ValueError("loop height and width must be positive")
        h, w = self.config.height, self.config.width
        phase = 0.0
        y0, x0 = top % h, left % w
        y1 = (top + height) % h
        x1 = (left + width) % w
        for dx in range(width):
            phase += self.theta_x[y0, (left + dx) % w]
            phase -= self.theta_x[y1, (left + dx) % w]
        for dy in range(height):
            phase += self.theta_y[(top + dy) % h, x1]
            phase -= self.theta_y[(top + dy) % h, x0]
        return float(_wrap_angle(phase))

    def gauge_transform(self, alpha: np.ndarray) -> "U1GaugeLattice":
        """Apply a local phase change at each site and return a new lattice."""
        alpha = np.asarray(alpha, dtype=np.float64)
        if alpha.shape != (self.config.height, self.config.width):
            raise ValueError("alpha must match lattice shape")
        tx = self.theta_x + alpha - np.roll(alpha, -1, axis=1)
        ty = self.theta_y + alpha - np.roll(alpha, -1, axis=0)
        return U1GaugeLattice(self.config, theta_x=tx, theta_y=ty)

    def field_strength_energy(self) -> float:
        """Wilson-action-like compact field energy."""
        plaq = self.plaquette_angles()
        return float(self.config.coupling * np.sum(1.0 - np.cos(plaq)))

    def audit_loop_summary(self) -> dict[str, Any]:
        plaq = self.plaquette_angles()
        return {
            "truth_label": TRUTH_LABEL,
            "truth_guard": EVENT94_TRUTH_GUARD,
            "mean_abs_plaquette": float(np.mean(np.abs(plaq))),
            "max_abs_plaquette": float(np.max(np.abs(plaq))),
            "field_strength_energy": self.field_strength_energy(),
            "wilson_loop_phase_2x2": self.wilson_loop_phase(0, 0, 2, 2),
        }


@dataclass(frozen=True)
class CondensationParams:
    """Ginzburg-Landau scalar-potential parameters."""

    beta: float = 1.0
    relaxation: float = 0.35

    def __post_init__(self) -> None:
        if self.beta <= 0:
            raise ValueError("beta must be positive")
        if not 0 < self.relaxation <= 1:
            raise ValueError("relaxation must be in (0, 1]")


def gl_equilibrium_amplitude(alpha: float, beta: float = 1.0) -> float:
    """Return the stable |psi| minimum for V = alpha|psi|^2 + beta|psi|^4/2."""
    if beta <= 0:
        raise ValueError("beta must be positive")
    return 0.0 if alpha >= 0 else math.sqrt(-float(alpha) / float(beta))


def condensation_ladder(
    alpha_schedule: Iterable[float],
    *,
    params: CondensationParams | None = None,
) -> list[dict[str, float]]:
    """Relax an order parameter through a control-parameter schedule."""
    p = params or CondensationParams()
    amplitude = 0.0
    rows: list[dict[str, float]] = []
    for step, alpha in enumerate(alpha_schedule):
        target = gl_equilibrium_amplitude(float(alpha), p.beta)
        amplitude += p.relaxation * (target - amplitude)
        potential = float(alpha) * amplitude * amplitude + 0.5 * p.beta * amplitude ** 4
        rows.append(
            {
                "step": float(step),
                "alpha": float(alpha),
                "target_amplitude": float(target),
                "amplitude": float(amplitude),
                "condensate_density": float(amplitude * amplitude),
                "gl_potential": float(potential),
                "mass_gap_proxy": float(math.sqrt(max(0.0, -2.0 * float(alpha)))),
            }
        )
    return rows


def condensation_transition_step(
    rows: list[dict[str, float]],
    *,
    threshold: float = 0.25,
) -> int | None:
    """First row where condensate density crosses threshold."""
    for row in rows:
        if row["condensate_density"] >= threshold:
            return int(row["step"])
    return None


@dataclass(frozen=True)
class GrokkingDetection:
    """Delayed generalization detector output."""

    truth_label: str
    train_fit_epoch: int | None
    generalization_epoch: int | None
    delay_epochs: int | None
    grokking_detected: bool
    algorithmic_score_gain: float
    note: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_grokking_epoch(
    train_loss: Iterable[float],
    validation_loss: Iterable[float],
    algorithmic_score: Iterable[float] | None = None,
    *,
    train_fit_fraction: float = 0.25,
    validation_fraction: float = 0.45,
    min_delay: int = 5,
    min_score_gain: float = 0.2,
) -> GrokkingDetection:
    """Detect delayed validation improvement after early training fit."""
    tr = np.asarray(list(train_loss), dtype=np.float64)
    va = np.asarray(list(validation_loss), dtype=np.float64)
    if tr.ndim != 1 or va.ndim != 1 or len(tr) != len(va) or len(tr) < 3:
        raise ValueError("train_loss and validation_loss must be equal-length 1D arrays")
    if algorithmic_score is None:
        score = np.linspace(0.0, 1.0, len(tr), dtype=np.float64)
    else:
        score = np.asarray(list(algorithmic_score), dtype=np.float64)
        if score.shape != tr.shape:
            raise ValueError("algorithmic_score must match loss arrays")

    train_threshold = float(tr[0]) * float(train_fit_fraction)
    val_threshold = float(va[0]) * float(validation_fraction)
    train_candidates = np.where(tr <= train_threshold)[0]
    train_epoch = int(train_candidates[0]) if len(train_candidates) else None
    if train_epoch is None:
        return GrokkingDetection(
            TRUTH_LABEL, None, None, None, False, 0.0,
            "train fit threshold not reached",
        )

    val_candidates = np.where(va[train_epoch:] <= val_threshold)[0]
    gen_epoch = int(train_epoch + val_candidates[0]) if len(val_candidates) else None
    if gen_epoch is None:
        return GrokkingDetection(
            TRUTH_LABEL, train_epoch, None, None, False, 0.0,
            "validation threshold not reached",
        )

    delay = gen_epoch - train_epoch
    gain = float(score[gen_epoch] - score[train_epoch])
    detected = delay >= min_delay and gain >= min_score_gain
    note = (
        "delayed generalization with algorithmic score gain"
        if detected
        else "threshold crossed without enough delay/score gain"
    )
    return GrokkingDetection(TRUTH_LABEL, train_epoch, gen_epoch, delay, detected, gain, note)


def dominant_fourier_mode(signal: Iterable[float]) -> dict[str, float | int]:
    """Return the strongest nonzero Fourier mode as a spectral wiring proxy."""
    arr = np.asarray(list(signal), dtype=np.float64)
    if arr.ndim != 1 or len(arr) < 4:
        raise ValueError("signal must contain at least four samples")
    centered = arr - float(np.mean(arr))
    power = np.abs(np.fft.rfft(centered)) ** 2
    if len(power) <= 1:
        return {"mode": 0, "mode_power": 0.0, "total_power": 0.0, "mode_fraction": 0.0}
    nonzero = power[1:]
    idx = int(np.argmax(nonzero) + 1)
    total = float(np.sum(nonzero))
    mode_power = float(power[idx])
    return {
        "mode": idx,
        "mode_power": mode_power,
        "total_power": total,
        "mode_fraction": 0.0 if total <= 0 else mode_power / total,
    }


def event94_payload() -> dict[str, Any]:
    return {
        "truth_label": TRUTH_LABEL,
        "truth_guard": EVENT94_TRUTH_GUARD,
        "surfaces": [
            "u1_lattice_audit_loops",
            "ginzburg_landau_condensation_ladder",
            "grokking_delay_detector",
            "spectral_mode_probe",
        ],
        "primary_anchors": [
            "yang_mills_1954_gauge_invariance",
            "wilson_1974_lattice_gauge",
            "bcs_1957_superconductivity",
            "higgs_1964_broken_symmetries",
            "power_2022_grokking",
            "nanda_2023_grokking_mech_interp",
        ],
    }


def write_event94_receipt(
    *,
    state_root: Path | None = None,
    receipt_path: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = state_root or Path(__file__).resolve().parent.parent / ".sifta_state"
    out = receipt_path or root / "event94_gauge_condensation_grokking_receipts.jsonl"
    row = {
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "kind": "EVENT94_GAUGE_CONDENSATION_GROKKING_RECEIPT",
        **event94_payload(),
    }
    if extra:
        row["extra"] = dict(extra)
    row["sha256"] = hashlib.sha256(
        json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


__all__ = [
    "CondensationParams",
    "EVENT94_TRUTH_GUARD",
    "GaugeLatticeConfig",
    "GrokkingDetection",
    "TRUTH_LABEL",
    "U1GaugeLattice",
    "condensation_ladder",
    "condensation_transition_step",
    "detect_grokking_epoch",
    "dominant_fourier_mode",
    "event94_payload",
    "gl_equilibrium_amplitude",
    "write_event94_receipt",
]
