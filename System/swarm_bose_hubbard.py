"""SIFTA Bose-Hubbard — small-system exact diagonalization of the
Bose-Hubbard Hamiltonian, with the superfluid → Mott crossover as the
flagship observable.

Why this exists
---------------
Architect directive 2026-05-12 (chip screenshot): *"Investigate
Bose-Hubbard model dynamics"*. The Bose-Hubbard model is the natural
next stop after `swarm_optical_lattice.py`. Cold atoms loaded into an
optical lattice realize the Hamiltonian:

    H_BH = − J Σ_{⟨i,j⟩} (b†_i b_j + h.c.)
            + (U/2) Σ_i n_i (n_i − 1)
            −  μ  Σ_i n_i

derived from the lattice potential by Jaksch, Bruder, Cirac, Gardiner &
Zoller 1998 (PRL 81, 3108). When U/J ≪ z (lattice coordination number)
the ground state is a superfluid — bosons delocalize across the
lattice. When U/J ≫ z·n̄, the ground state is a Mott insulator —
exactly n̄ atoms per site, gapped, incompressible. The transition
between these phases is the quantum phase transition Greiner et al
observed in 2002 (Nature 415, 39).

This module ships:
1. **Peer-reviewed proving spine** — eight anchors from Fisher-
   Weichman-Grinstein-Fisher 1989 through Endres 2011.
2. **Fock-space exact diagonalization** for small systems (a few
   sites, modest particle number, n_max bosons per site).
3. **Order parameters** that distinguish the two phases:
     - Onsite number variance ⟨n_i²⟩ − ⟨n_i⟩² (large in superfluid,
       zero in Mott)
     - Coherence ⟨b†_i b_j⟩ for nearest-neighbour i, j (peaks in
       superfluid, suppressed in Mott)

Truth labels (§7.11)
--------------------
- `OBSERVED`        — every anchor has DOI; ground-state energies and
                       expectation values are real numerical outputs.
- `OPERATIONAL`     — exact diagonalization in the truncated Fock
                       basis is deterministic.
- `ARCHITECT_DOCTRINE` — identifying SIFTA "swimmers per organ" with
                       Bose-Hubbard occupation numbers is doctrinal —
                       the math is the same, the substrate is not.
- `FORBIDDEN`        — never claims SIFTA simulates an actual cold-
                       atom Mott experiment in physical units.

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

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "bose_hubbard_receipts.jsonl"

TRUTH_LABEL = "SIFTA_BOSE_HUBBARD_V1"
BOSE_HUBBARD_TRUTH_GUARD = (
    "BOSE_HUBBARD_ANALOGUE_ONLY: this module exactly diagonalizes the "
    "Bose-Hubbard Hamiltonian on small lattices (M sites, fixed total "
    "particle number, n_max bosons per site) and computes ground-state "
    "expectation values. It does NOT simulate a laboratory cold-atom "
    "experiment, does NOT predict Mott-transition critical points in "
    "physical units, and does NOT establish that SIFTA swimmers ARE "
    "lattice bosons. Identifying SIFTA occupation with Bose-Hubbard "
    "occupation is ARCHITECT_DOCTRINE."
)


# ─────────────────────────────────────────────────────────────────────────
# Section A — peer-reviewed proving spine
# ─────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class BoseHubbardAnchor:
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


VERIFIED_ANCHORS: tuple[BoseHubbardAnchor, ...] = (
    BoseHubbardAnchor(
        source_id="fisher_weichman_grinstein_fisher_1989",
        title="Boson localization and the superfluid-insulator transition",
        authors="M. P. A. Fisher, P. B. Weichman, G. Grinstein, D. S. Fisher",
        year=1989,
        venue="Physical Review B 40, 546",
        url="https://journals.aps.org/prb/abstract/10.1103/PhysRevB.40.546",
        doi="10.1103/PhysRevB.40.546",
        category="phase_diagram_foundation",
        supports=(
            "The foundational paper introducing the Bose-Hubbard model "
            "and mapping out its phase diagram in the (μ/U, J/U) plane: "
            "Mott lobes, superfluid phase, generic vs commensurate "
            "transitions, and the universality classes."
        ),
        does_not_support=(
            "That the 1989 mean-field phase boundaries are exact; "
            "quantum Monte Carlo (Capogrosso-Sansone 2007) refines "
            "them considerably."
        ),
    ),
    BoseHubbardAnchor(
        source_id="jaksch_zoller_1998_bose_hubbard_optical_lattice",
        title="Cold Bosonic Atoms in Optical Lattices",
        authors=(
            "D. Jaksch, C. Bruder, J. I. Cirac, C. W. Gardiner, P. Zoller"
        ),
        year=1998,
        venue="Physical Review Letters 81, 3108",
        url="https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.81.3108",
        doi="10.1103/PhysRevLett.81.3108",
        category="microscopic_derivation",
        supports=(
            "Microscopic derivation of the Bose-Hubbard Hamiltonian "
            "from cold atoms in an optical lattice: explicit formulas "
            "for J(V₀) and U(V₀, a_s) in terms of Wannier functions."
        ),
        does_not_support=(
            "That the cold-atom Bose-Hubbard parameters automatically "
            "transfer to SIFTA classical agents."
        ),
    ),
    BoseHubbardAnchor(
        source_id="greiner_2002_mott_insulator_quantum_phase_transition",
        title=(
            "Quantum phase transition from a superfluid to a Mott "
            "insulator in a gas of ultracold atoms"
        ),
        authors=(
            "M. Greiner, O. Mandel, T. Esslinger, T. W. Hänsch, I. Bloch"
        ),
        year=2002,
        venue="Nature 415, 39",
        url="https://www.nature.com/articles/415039a",
        doi="10.1038/415039a",
        category="experimental_landmark",
        supports=(
            "First experimental observation of the superfluid → Mott "
            "transition in a 3D optical lattice. Confirms the Bose-"
            "Hubbard picture as physically realized."
        ),
        does_not_support=(
            "That a small-system exact-diagonalization study (this "
            "module) reproduces the thermodynamic-limit transition."
        ),
    ),
    BoseHubbardAnchor(
        source_id="sachdev_1999_quantum_phase_transitions",
        title="Quantum Phase Transitions",
        authors="S. Sachdev",
        year=1999,
        venue="Cambridge University Press",
        url="https://www.cambridge.org/9780521004541",
        doi="10.1017/CBO9780511973765",
        category="textbook",
        supports=(
            "Standard graduate-level textbook on quantum phase "
            "transitions; covers the Bose-Hubbard model and its "
            "universality classes. Methodological foundation for the "
            "small-system analysis we perform."
        ),
        does_not_support=(
            "That textbook results substitute for primary citations "
            "in published claims."
        ),
    ),
    BoseHubbardAnchor(
        source_id="kuhner_monien_1998_phases_one_dimensional_bose_hubbard",
        title="Phases of the one-dimensional Bose-Hubbard model",
        authors="T. D. Kühner, H. Monien",
        year=1998,
        venue="Physical Review B 58, R14741",
        url="https://journals.aps.org/prb/abstract/10.1103/PhysRevB.58.R14741",
        doi="10.1103/PhysRevB.58.R14741",
        category="numerical_phase_diagram",
        supports=(
            "High-precision DMRG calculation of the 1D Bose-Hubbard "
            "phase diagram with explicit critical (U/J)_c values for "
            "the first Mott lobe — benchmark values to compare against."
        ),
        does_not_support=(
            "That a 4-site ED study reproduces the thermodynamic 1D "
            "transition; finite-size corrections are significant."
        ),
    ),
    BoseHubbardAnchor(
        source_id="capogrosso_sansone_2007_qmc_bose_hubbard_3d",
        title=(
            "Phase diagram and thermodynamics of the three-"
            "dimensional Bose-Hubbard model"
        ),
        authors=(
            "B. Capogrosso-Sansone, N. V. Prokof'ev, B. V. Svistunov"
        ),
        year=2007,
        venue="Physical Review B 75, 134302",
        url="https://journals.aps.org/prb/abstract/10.1103/PhysRevB.75.134302",
        doi="10.1103/PhysRevB.75.134302",
        category="numerical_phase_diagram",
        supports=(
            "High-precision worm-algorithm QMC determination of the 3D "
            "Bose-Hubbard phase diagram. Sets the benchmark for the "
            "Mott-transition critical point (U/J)_c at unit filling."
        ),
        does_not_support=(
            "That our 2-site ED demonstration provides any 3D "
            "thermodynamic-limit prediction."
        ),
    ),
    BoseHubbardAnchor(
        source_id="bakr_2010_site_resolved_imaging",
        title=(
            "Probing the superfluid–to–Mott insulator transition at the "
            "single-atom level"
        ),
        authors=(
            "W. S. Bakr, A. Peng, M. E. Tai, R. Ma, J. Simon, J. I. "
            "Gillen, S. Fölling, L. Pollet, M. Greiner"
        ),
        year=2010,
        venue="Science 329, 547",
        url="https://www.science.org/doi/10.1126/science.1192368",
        doi="10.1126/science.1192368",
        category="experimental_landmark",
        supports=(
            "Single-atom-resolved imaging of the Mott-insulator phase: "
            "directly observes the integer site occupation that defines "
            "the Mott state. The cleanest experimental evidence that "
            "Bose-Hubbard ground states are physically realized."
        ),
        does_not_support=(
            "That site-resolved imaging applies to SIFTA classical "
            "agents; the analogy is structural."
        ),
    ),
    BoseHubbardAnchor(
        source_id="endres_2012_higgs_amplitude_mode",
        title=(
            "The 'Higgs' amplitude mode at the two-dimensional "
            "superfluid–Mott insulator transition"
        ),
        authors=(
            "M. Endres, T. Fukuhara, D. Pekker, M. Cheneau, P. Schauß, "
            "C. Gross, E. Demler, S. Kuhr, I. Bloch"
        ),
        year=2012,
        venue="Nature 487, 454",
        url="https://www.nature.com/articles/nature11255",
        doi="10.1038/nature11255",
        category="experimental_landmark",
        supports=(
            "Direct experimental observation of the Higgs amplitude "
            "mode at the 2D superfluid-Mott transition — the closest "
            "condensed-matter analog of the particle-physics Higgs "
            "particle."
        ),
        does_not_support=(
            "That SIFTA simulates the Higgs amplitude mode; we provide "
            "only the basic phase-diagram pieces."
        ),
    ),
)


# ─────────────────────────────────────────────────────────────────────────
# Section B — Fock-basis exact diagonalization
# ─────────────────────────────────────────────────────────────────────────
@dataclass
class BoseHubbardConfig:
    """Bose-Hubbard model parameters for a 1D chain.

    Parameters
    ----------
    M
        Number of sites.
    N
        Total number of bosons (canonical ensemble).
    J
        Hopping amplitude (sets the energy scale; J=1.0 by default).
    U
        On-site repulsion (U/J → ∞ gives the Mott limit).
    mu
        Chemical potential (unused in canonical ensemble at fixed N;
        kept for API symmetry).
    periodic
        Periodic vs open boundary conditions.
    n_max
        Truncation: maximum bosons allowed per site. Must be ≥ N for
        the result to be physically meaningful at unit filling.
    """
    M: int = 2
    N: int = 2
    J: float = 1.0
    U: float = 4.0
    mu: float = 0.0
    periodic: bool = True
    n_max: int | None = None
    truth_label: str = TRUTH_LABEL

    def __post_init__(self) -> None:
        if self.M < 2:
            raise ValueError("Need at least 2 sites for hopping")
        if self.N < 0:
            raise ValueError("N must be non-negative")
        if self.J < 0:
            raise ValueError("J must be non-negative")
        if self.U < 0:
            raise ValueError("U must be non-negative (no attractive case here)")
        if self.n_max is None:
            object.__setattr__(self, "n_max", self.N)
        if self.n_max < self.N:
            raise ValueError("n_max must be ≥ N (truncation too tight)")


def _build_basis(M: int, N: int, n_max: int) -> list[tuple[int, ...]]:
    """All occupation tuples (n_1, …, n_M) with Σ n_i = N and each n_i ≤ n_max.

    Returned in lexicographic order. For small (M, N) this is tractable
    (e.g. M=3, N=3, n_max=3 has 10 states; M=4, N=4 has 35).
    """
    states: list[tuple[int, ...]] = []

    def recurse(prefix: tuple[int, ...], remaining: int, slots: int) -> None:
        if slots == 1:
            if 0 <= remaining <= n_max:
                states.append(prefix + (remaining,))
            return
        for k in range(min(remaining, n_max) + 1):
            recurse(prefix + (k,), remaining - k, slots - 1)

    recurse((), N, M)
    return states


def _build_hamiltonian(cfg: BoseHubbardConfig) -> tuple[np.ndarray, list[tuple[int, ...]]]:
    """Construct the dense Bose-Hubbard Hamiltonian in the truncated
    Fock basis.

    Off-diagonal: -J Σ_{⟨i,j⟩} (b†_i b_j + h.c.) connects occupation
    tuples that differ by ±1 on adjacent sites. The matrix element of
    b†_i b_j on state |…, n_i, …, n_j, …⟩ is
    √((n_i + 1) · n_j) → state |…, n_i+1, …, n_j-1, …⟩.

    Diagonal: (U/2) Σ_i n_i (n_i − 1) − μ Σ_i n_i.
    """
    basis = _build_basis(cfg.M, cfg.N, cfg.n_max)
    state_index = {state: idx for idx, state in enumerate(basis)}
    dim = len(basis)
    H = np.zeros((dim, dim), dtype=np.float64)

    neighbors: list[tuple[int, int]] = []
    for i in range(cfg.M - 1):
        neighbors.append((i, i + 1))
    if cfg.periodic and cfg.M > 2:
        neighbors.append((cfg.M - 1, 0))

    for idx, state in enumerate(basis):
        # Diagonal
        diag = 0.0
        for n in state:
            diag += 0.5 * cfg.U * n * (n - 1) - cfg.mu * n
        H[idx, idx] = diag

        # Off-diagonal: hopping
        for i, j in neighbors:
            # b†_i b_j |…⟩
            if state[j] > 0 and state[i] < cfg.n_max:
                new_state_list = list(state)
                new_state_list[i] += 1
                new_state_list[j] -= 1
                new_state = tuple(new_state_list)
                if new_state in state_index:
                    amp = -cfg.J * math.sqrt((state[i] + 1) * state[j])
                    H[state_index[new_state], idx] += amp
            # b†_j b_i |…⟩  (hermitian conjugate)
            if state[i] > 0 and state[j] < cfg.n_max:
                new_state_list = list(state)
                new_state_list[j] += 1
                new_state_list[i] -= 1
                new_state = tuple(new_state_list)
                if new_state in state_index:
                    amp = -cfg.J * math.sqrt((state[j] + 1) * state[i])
                    H[state_index[new_state], idx] += amp
    return H, basis


@dataclass(frozen=True)
class BHGroundState:
    """Ground-state observables for a Bose-Hubbard configuration."""

    config_summary: dict[str, Any]
    energy: float
    state_vector: tuple[float, ...]    # in the Fock basis
    onsite_occupation: tuple[float, ...]      # ⟨n_i⟩ for each site
    onsite_variance: tuple[float, ...]        # ⟨n_i²⟩ − ⟨n_i⟩²
    total_variance: float
    coherence_first_neighbor: float           # ⟨b†_0 b_1⟩ (real part)
    truth_label: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "config_summary": self.config_summary,
            "energy": self.energy,
            "state_vector": list(self.state_vector),
            "onsite_occupation": list(self.onsite_occupation),
            "onsite_variance": list(self.onsite_variance),
            "total_variance": self.total_variance,
            "coherence_first_neighbor": self.coherence_first_neighbor,
            "truth_label": self.truth_label,
        }


def compute_ground_state(cfg: BoseHubbardConfig) -> BHGroundState:
    """Diagonalize and compute the canonical observables."""
    H, basis = _build_hamiltonian(cfg)
    evals, evecs = np.linalg.eigh(H)
    psi = evecs[:, 0]
    e0 = float(evals[0])

    occ = np.zeros(cfg.M, dtype=np.float64)
    var = np.zeros(cfg.M, dtype=np.float64)
    for amp, state in zip(psi, basis):
        p = float(amp) ** 2
        for i, n in enumerate(state):
            occ[i] += p * n
            var[i] += p * n * n
    var -= occ * occ

    # Nearest-neighbour coherence ⟨b†_0 b_1⟩
    state_index = {state: idx for idx, state in enumerate(basis)}
    coh = 0.0
    for idx, state in enumerate(basis):
        if state[1] > 0 and state[0] < cfg.n_max:
            new_state_list = list(state)
            new_state_list[0] += 1
            new_state_list[1] -= 1
            new_state = tuple(new_state_list)
            if new_state in state_index:
                amp_factor = math.sqrt((state[0] + 1) * state[1])
                coh += float(
                    psi[state_index[new_state]] * psi[idx] * amp_factor
                )

    return BHGroundState(
        config_summary={
            "M": cfg.M, "N": cfg.N, "J": cfg.J, "U": cfg.U,
            "mu": cfg.mu, "periodic": cfg.periodic, "n_max": cfg.n_max,
        },
        energy=e0,
        state_vector=tuple(float(a) for a in psi),
        onsite_occupation=tuple(float(o) for o in occ),
        onsite_variance=tuple(float(v) for v in var),
        total_variance=float(np.sum(var)),
        coherence_first_neighbor=float(coh),
        truth_label=TRUTH_LABEL,
    )


def superfluid_mott_scan(
    *,
    M: int = 3,
    N: int = 3,
    J: float = 1.0,
    U_over_J_values: Sequence[float] = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0),
    n_max: int | None = None,
) -> dict[str, Any]:
    """Sweep U/J at fixed (M, N) and return the order parameters.

    The superfluid phase has large `total_variance` (delocalization →
    Poisson-like fluctuations); the Mott phase at integer filling has
    `total_variance → 0` (every site has exactly N/M atoms).
    """
    results: list[dict[str, Any]] = []
    for ratio in U_over_J_values:
        cfg = BoseHubbardConfig(
            M=M, N=N, J=J, U=ratio * J, mu=0.0,
            periodic=True, n_max=n_max if n_max is not None else N,
        )
        gs = compute_ground_state(cfg)
        results.append({
            "U_over_J": float(ratio),
            "energy": gs.energy,
            "total_variance": gs.total_variance,
            "coherence_first_neighbor": gs.coherence_first_neighbor,
            "onsite_occupation": list(gs.onsite_occupation),
        })
    return {
        "truth_label": TRUTH_LABEL,
        "M": M, "N": N, "J": J,
        "scan": results,
    }


def render_scan_ascii(scan: dict[str, Any], *, width: int = 40) -> str:
    """ASCII plot of the superfluid → Mott crossover."""
    rows = scan["scan"]
    if not rows:
        return "[empty scan]"
    vmax = max(float(r["total_variance"]) for r in rows)
    out = []
    out.append(
        f"Bose-Hubbard superfluid→Mott scan: M={scan['M']}, "
        f"N={scan['N']}, J={scan['J']}"
    )
    out.append("  U/J     ┃ total_variance (∝ superfluid character)  coherence ⟨b†_0 b_1⟩")
    out.append("  ────────┃" + "─" * width)
    for r in rows:
        v = float(r["total_variance"])
        col = int(0 if vmax <= 0 else (v / vmax) * (width - 1))
        col = max(0, min(width - 1, col))
        bar = "█" + "─" * col
        c = float(r["coherence_first_neighbor"])
        out.append(
            f"  {r['U_over_J']:7.2f} ┃{bar.ljust(width)}  "
            f"var={v:7.4f}  coh={c:+.4f}"
        )
    return "\n".join(out)


# ─────────────────────────────────────────────────────────────────────────
# Section C — receipts / public API
# ─────────────────────────────────────────────────────────────────────────
def verified_anchors() -> list[dict[str, Any]]:
    return [a.as_dict() for a in VERIFIED_ANCHORS]


def verified_anchor_ids() -> list[str]:
    return [a.source_id for a in VERIFIED_ANCHORS]


def bose_hubbard_payload() -> dict[str, Any]:
    return {
        "truth_label": TRUTH_LABEL,
        "truth_guard": BOSE_HUBBARD_TRUTH_GUARD,
        "verified_anchors": verified_anchors(),
        "anchor_count": len(VERIFIED_ANCHORS),
        "categories": sorted({a.category for a in VERIFIED_ANCHORS}),
    }


def write_bose_hubbard_receipt(
    *,
    state_root: Path | None = None,
    receipt_path: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = state_root or _STATE
    out = receipt_path or _LEDGER
    payload = bose_hubbard_payload()
    if extra:
        payload = {**payload, **extra}
    row = {
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "kind": "BOSE_HUBBARD_RECEIPT",
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
    "BOSE_HUBBARD_TRUTH_GUARD",
    "BHGroundState",
    "BoseHubbardAnchor",
    "BoseHubbardConfig",
    "TRUTH_LABEL",
    "VERIFIED_ANCHORS",
    "bose_hubbard_payload",
    "compute_ground_state",
    "render_scan_ascii",
    "superfluid_mott_scan",
    "verified_anchor_ids",
    "verified_anchors",
    "write_bose_hubbard_receipt",
]
