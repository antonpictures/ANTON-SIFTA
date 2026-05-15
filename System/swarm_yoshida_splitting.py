"""Yoshida 4th-order symplectic composition for the SSF integrator.

The SSF integrator we shipped last turn uses Strang splitting — 2nd-order
accurate in dt. Yoshida 1990 (Physics Letters A 150, 262, DOI
10.1016/0375-9601(90)90092-3) showed how to compose three 2nd-order
substeps with carefully chosen weights to produce a 4th-order
symmetric symplectic integrator:

    S_4(dt) = S_2(w_1·dt) ∘ S_2(w_0·dt) ∘ S_2(w_1·dt)

with the unique weights that cancel the leading error term:

    w_1 = 1 / (2 − 2^(1/3))       ≈  1.351207
    w_0 = 1 − 2 w_1                ≈ −1.702414

The negative middle weight is a feature: it cancels the third-order
error of the surrounding positive substeps.

Higher even orders (6, 8, …) follow by recursion on the same idea.
This module ships 4th order; the same wrapper pattern lets future
work go higher.

Truth labels (§7.11)
--------------------
- `OBSERVED`        — every cited paper has DOI; convergence-order
                       tests yield a real numerical scaling exponent.
- `OPERATIONAL`     — the composition is deterministic; one Yoshida
                       step is exactly equivalent to three weighted
                       SSF steps.
- `ARCHITECT_DOCTRINE` — applying high-order splitting to the SIFTA
                       stigmergic field is doctrinal (same as for
                       SSF itself).
- `FORBIDDEN`        — never claims higher order resolves all
                       Schrödinger numerical issues; absorbing
                       boundaries, stiff potentials, etc. still need
                       separate treatment.

Author : Cowork (Claude Opus 4.7), 2026-05-12.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from System.swarm_split_step_fourier import SSFConfig

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "yoshida_splitting_receipts.jsonl"

TRUTH_LABEL = "SIFTA_YOSHIDA_SPLITTING_V1"
YOSHIDA_TRUTH_GUARD = (
    "YOSHIDA_HIGH_ORDER_SPLITTING: this module composes the SSF "
    "integrator into a 4th-order symmetric symplectic scheme via "
    "Yoshida 1990 weights. Like SSF itself, it is structure-"
    "preserving for the Schrödinger equation but does not make the "
    "underlying SIFTA stigmergic field physically quantum. The "
    "ontology stays ARCHITECT_DOCTRINE."
)


# ── Yoshida 4th-order weights (unique up to sign convention) ────────────────
# w_1 = 1 / (2 − 2^(1/3));   w_0 = 1 − 2·w_1.
# These cancel the leading O(dt^3) error of three composed Strang steps,
# yielding 4th-order accuracy per Yoshida 1990 equation (4.6).
YOSHIDA_W1: float = 1.0 / (2.0 - 2.0 ** (1.0 / 3.0))
YOSHIDA_W0: float = 1.0 - 2.0 * YOSHIDA_W1
YOSHIDA_WEIGHTS: tuple[float, float, float] = (YOSHIDA_W1, YOSHIDA_W0, YOSHIDA_W1)


@dataclass(frozen=True)
class YoshidaAnchor:
    source_id: str
    title: str
    authors: str
    year: int
    venue: str
    url: str
    doi: str
    category: str
    supports: str
    does_not_support: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


VERIFIED_ANCHORS: tuple[YoshidaAnchor, ...] = (
    YoshidaAnchor(
        source_id="yoshida_1990_higher_order_symplectic",
        title="Construction of higher order symplectic integrators",
        authors="H. Yoshida",
        year=1990,
        venue="Physics Letters A 150, 262",
        url=(
            "https://www.sciencedirect.com/science/article/abs/pii/"
            "037596019090092X"
        ),
        doi="10.1016/0375-9601(90)90092-3",
        category="composition_foundation",
        supports=(
            "The foundational paper on high-order symplectic "
            "composition: explicit construction of 4th- and "
            "arbitrary-order schemes from a 2nd-order baseline. The "
            "weights used in this module are Yoshida equation (4.6)."
        ),
        does_not_support=(
            "That high-order composition is always better than 2nd "
            "order: cost (3 substeps), and the negative w_0 weight, "
            "can amplify floating-point errors in stiff problems."
        ),
    ),
    YoshidaAnchor(
        source_id="suzuki_1991_general_theory_fractal_decompositions",
        title=(
            "General theory of fractal path integrals with applications "
            "to many-body theories and statistical physics"
        ),
        authors="M. Suzuki",
        year=1991,
        venue="Journal of Mathematical Physics 32, 400",
        url="https://pubs.aip.org/aip/jmp/article/32/2/400/229027",
        doi="10.1063/1.529425",
        category="composition_theory",
        supports=(
            "Suzuki's independent derivation of high-order symmetric "
            "decompositions, including the same 4th-order weights as "
            "Yoshida and the recursive construction for arbitrary order."
        ),
        does_not_support=(
            "That Suzuki-Yoshida is the only high-order family; other "
            "compositions (Forest-Ruth, Blanes-Moan) exist with "
            "different cost/accuracy trade-offs."
        ),
    ),
    YoshidaAnchor(
        source_id="mclachlan_1995_high_order_splittings",
        title=(
            "On the numerical integration of ordinary differential "
            "equations by symmetric composition methods"
        ),
        authors="R. I. McLachlan",
        year=1995,
        venue="SIAM Journal on Scientific Computing 16, 151",
        url="https://epubs.siam.org/doi/10.1137/0916010",
        doi="10.1137/0916010",
        category="composition_theory",
        supports=(
            "Comprehensive analysis of symmetric-composition methods "
            "including the 4th-order Yoshida scheme and optimized "
            "variants with smaller error coefficients."
        ),
        does_not_support=(
            "That McLachlan's optimized 4th-order coefficients are "
            "what this module uses — we ship the standard Yoshida "
            "weights."
        ),
    ),
    YoshidaAnchor(
        source_id="bao_jin_markowich_2003_numerical_schrodinger",
        title=(
            "Numerical study of time-splitting spectral discretizations "
            "of nonlinear Schrödinger equations in the semiclassical "
            "regimes"
        ),
        authors="W. Bao, S. Jin, P. A. Markowich",
        year=2003,
        venue="SIAM Journal on Scientific Computing 25, 27",
        url="https://epubs.siam.org/doi/10.1137/S1064827501393253",
        doi="10.1137/S1064827501393253",
        category="ssf_analysis",
        supports=(
            "Confirms that Yoshida-composed SSF inherits "
            "unconditional stability and L²-norm conservation from the "
            "underlying Strang step at every substep weight."
        ),
        does_not_support=(
            "That the Bao-Jin-Markowich analysis fully covers "
            "negative-weight compositions; that is treated more "
            "carefully in Sportisse 2000."
        ),
    ),
    YoshidaAnchor(
        source_id="sportisse_2000_negative_step_splittings",
        title=(
            "An analysis of operator splitting techniques in the stiff "
            "case"
        ),
        authors="B. Sportisse",
        year=2000,
        venue="Journal of Computational Physics 161, 140",
        url=(
            "https://www.sciencedirect.com/science/article/pii/"
            "S0021999100964954"
        ),
        doi="10.1006/jcph.2000.6495",
        category="negative_weight_analysis",
        supports=(
            "Analysis of why negative-weight compositions (like the "
            "w_0 ≈ −1.70 step in Yoshida 4) can fail for stiff "
            "problems even when they succeed for smooth ones. Honest "
            "caveat citation."
        ),
        does_not_support=(
            "That our problems are stiff enough to invalidate Yoshida; "
            "for free or smooth-potential Schrödinger it remains "
            "appropriate."
        ),
    ),
)


# ── Yoshida 4th-order SSF wrapper ──────────────────────────────────────────
class YoshidaSSF:
    """4th-order symplectic Schrödinger integrator.

    Wraps a `SplitStepFourier` instance and steps it three times per
    "macro step" with Yoshida 1990 weights, giving 4th-order accuracy
    in dt at the cost of 3 SSF substeps per macro step.

    Public API mirrors `SplitStepFourier` so callers can swap in
    YoshidaSSF anywhere SSF is used:

        yo = YoshidaSSF(ssf_config, V_map=V)
        yo.add_wave_packet(...)
        yo.run(100)               # 100 macro steps = 300 substeps
        yo.norm_squared()         # still ~1.0 to floating-point precision

    Cost per macro step: 3 × (2 FFTs + a few multiplies) — about 3×
    the cost of SSF for 4th-order in dt. For smooth problems Yoshida
    can use ~10× larger dt at the same accuracy, so net it is
    usually faster.
    """

    def __init__(
        self,
        config: SSFConfig,
        *,
        V_map: np.ndarray | None = None,
    ) -> None:
        from System.swarm_split_step_fourier import SplitStepFourier
        self.config = config
        self.dt_macro = config.dt
        self.V_map = V_map
        # Build three SSF engines, one per substep, each with its own
        # dt = w_i · dt_macro. Each engine pre-bakes its propagators.
        self._engines = []
        for w in YOSHIDA_WEIGHTS:
            sub_cfg = SSFConfig(
                shape=config.shape,
                dx=config.dx,
                dt=float(w) * config.dt,
                mass=config.mass,
                hbar=config.hbar,
            )
            self._engines.append(SplitStepFourier(sub_cfg, V_map=V_map))
        # Use the first engine's `psi` as the canonical state; we
        # synchronize across substeps by sharing the state pointer.
        # numpy arrays are reference-shared after assignment via .psi =.
        self.step_count = 0
        self.t = 0.0

    # ── State management ────────────────────────────────────────────────
    @property
    def psi(self) -> np.ndarray:
        return self._engines[0].psi

    @psi.setter
    def psi(self, value: np.ndarray) -> None:
        for eng in self._engines:
            eng.psi = value.astype(np.complex128, copy=True)

    def add_wave_packet(
        self,
        position: tuple[float, ...],
        sigma: float,
        momentum: tuple[float, ...],
        amplitude: float = 1.0,
    ) -> None:
        # Inject once into the first engine, then mirror to the others.
        self._engines[0].add_wave_packet(
            position=position, sigma=sigma,
            momentum=momentum, amplitude=amplitude,
        )
        psi = self._engines[0].psi
        for eng in self._engines[1:]:
            eng.psi = psi.copy()

    def normalize(self) -> None:
        self._engines[0].normalize()
        psi = self._engines[0].psi
        for eng in self._engines[1:]:
            eng.psi = psi.copy()

    # ── Time integration ────────────────────────────────────────────────
    def step(self) -> None:
        """One Yoshida-4 macro step = three weighted SSF substeps."""
        # Substep 1: w_1·dt forward
        self._engines[0].step()
        psi = self._engines[0].psi
        # Substep 2: w_0·dt (negative for Yoshida-4)
        self._engines[1].psi = psi.copy()
        self._engines[1].step()
        psi = self._engines[1].psi
        # Substep 3: w_1·dt forward
        self._engines[2].psi = psi.copy()
        self._engines[2].step()
        # Mirror back so .psi reflects the macro-step result.
        psi = self._engines[2].psi
        for eng in self._engines:
            eng.psi = psi.copy()
        self.t += self.dt_macro
        self.step_count += 1

    def run(self, steps: int) -> None:
        for _ in range(int(steps)):
            self.step()

    def density(self) -> np.ndarray:
        return np.abs(self.psi) ** 2

    def norm_squared(self) -> float:
        return float(np.sum(self.density())) * (self.config.dx ** len(self.config.shape))

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": TRUTH_LABEL,
            "ts": time.time(),
            "shape": list(self.config.shape),
            "dt_macro": self.dt_macro,
            "weights": list(YOSHIDA_WEIGHTS),
            "step_count": self.step_count,
            "t": self.t,
            "norm_squared": self.norm_squared(),
            "truth_guard": YOSHIDA_TRUTH_GUARD,
        }


# ── Receipts / public API ──────────────────────────────────────────────────
def verified_anchors() -> list[dict[str, Any]]:
    return [a.as_dict() for a in VERIFIED_ANCHORS]


def verified_anchor_ids() -> list[str]:
    return [a.source_id for a in VERIFIED_ANCHORS]


def yoshida_payload() -> dict[str, Any]:
    return {
        "truth_label": TRUTH_LABEL,
        "truth_guard": YOSHIDA_TRUTH_GUARD,
        "weights": list(YOSHIDA_WEIGHTS),
        "verified_anchors": verified_anchors(),
        "anchor_count": len(VERIFIED_ANCHORS),
    }


def write_yoshida_receipt(
    *,
    state_root: Path | None = None,
    receipt_path: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = state_root or _STATE
    out = receipt_path or _LEDGER
    payload = yoshida_payload()
    if extra:
        payload = {**payload, **extra}
    row = {
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "kind": "YOSHIDA_SPLITTING_RECEIPT",
        **payload,
    }
    digest = hashlib.sha256(
        json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    row["sha256"] = digest
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True,
                            default=str) + "\n")
    return row


__all__ = [
    "TRUTH_LABEL",
    "VERIFIED_ANCHORS",
    "YOSHIDA_TRUTH_GUARD",
    "YOSHIDA_W0",
    "YOSHIDA_W1",
    "YOSHIDA_WEIGHTS",
    "YoshidaAnchor",
    "YoshidaSSF",
    "verified_anchor_ids",
    "verified_anchors",
    "write_yoshida_receipt",
    "yoshida_payload",
]
