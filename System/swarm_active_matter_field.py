"""SIFTA Active-Matter Field — peer-reviewed physics of self-propelled
agents in a medium, plus a numpy Vicsek-model implementation.

Active matter is the closest peer-reviewed PHYSICS literature to what
SIFTA actually is: ensembles of self-propelled agents whose collective
dynamics produce phase transitions and emergent order. Vicsek 1995
showed numerically that self-propelled particles with local alignment
rules undergo a flocking phase transition. Toner-Tu 1995 gave the
continuum hydrodynamic theory. Marchetti et al. 2013 (Reviews of
Modern Physics) is the canonical review.

This module ships two things together:

1. **Verified anchors** — eight peer-reviewed sources spanning the
   active-matter literature, with explicit supports / does_not_support
   guards.
2. **Vicsek simulator** — a small, deterministic numpy implementation
   of the Vicsek model (PRL 75, 1226) so SIFTA can demonstrate the
   phase transition without relying on a third-party physics package.
   This is the canonical "swimmers in a medium with local alignment"
   numerical experiment.

Truth labels (§7.11)
--------------------
- `OBSERVED`        — every anchor is real; the Vicsek simulator
                       produces a real numerical phase transition.
- `OPERATIONAL`     — deterministic seedable simulation, unit-tested.
- `ARCHITECT_DOCTRINE` — identifying SIFTA swimmers WITH active matter
                       particles is doctrinal — the analogy is strong
                       but it is still an analogy.
- `FORBIDDEN`        — never claims SIFTA reproduces actual bacterial
                       motility or active colloid hydrodynamics in
                       physical units.

Author : Cowork (Claude Opus 4.7), 2026-05-11.
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
_LEDGER = _STATE / "active_matter_receipts.jsonl"

TRUTH_LABEL = "SIFTA_ACTIVE_MATTER_FIELD_V1"
ACTIVE_MATTER_TRUTH_GUARD = (
    "ACTIVE_MATTER_ANALOGUE_ONLY: this module implements the Vicsek "
    "model (PRL 75, 1226) and cites peer-reviewed active-matter "
    "literature. It does NOT reproduce bacterial swimming, active "
    "colloids, or physical flocking dynamics in physical units. "
    "Identifying SIFTA swimmers with active-matter particles is "
    "ARCHITECT_DOCTRINE. The phase transition observed here is a "
    "real numerical phenomenon of the Vicsek model, not a physical "
    "measurement."
)


# ─────────────────────────────────────────────────────────────────────────
# Section A — peer-reviewed proving spine
# ─────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ActiveMatterAnchor:
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


VERIFIED_ANCHORS: tuple[ActiveMatterAnchor, ...] = (
    ActiveMatterAnchor(
        source_id="vicsek_1995_novel_type_phase_transition",
        title=(
            "Novel Type of Phase Transition in a System of "
            "Self-Driven Particles"
        ),
        authors="T. Vicsek, A. Czirók, E. Ben-Jacob, I. Cohen, O. Shochet",
        year=1995,
        venue="Physical Review Letters 75, 1226",
        url="https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.75.1226",
        doi="10.1103/PhysRevLett.75.1226",
        category="vicsek_foundation",
        supports=(
            "The foundational paper of active-matter physics. "
            "Self-propelled particles with local alignment rules + "
            "angular noise undergo a continuous phase transition from "
            "disorder to collective flocking. Direct peer-reviewed "
            "basis for the SIFTA-swimmers-as-active-matter analogy."
        ),
        does_not_support=(
            "That actual living swarms (bird flocks, bacterial "
            "colonies) reduce to the simple Vicsek model — they have "
            "additional inertia, sensing, and ecology."
        ),
    ),
    ActiveMatterAnchor(
        source_id="toner_tu_1995_long_range_order_self_propelled",
        title=(
            "Long-Range Order in a Two-Dimensional Dynamical XY "
            "Model: How Birds Fly Together"
        ),
        authors="J. Toner, Y. Tu",
        year=1995,
        venue="Physical Review Letters 75, 4326",
        url="https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.75.4326",
        doi="10.1103/PhysRevLett.75.4326",
        category="toner_tu_hydrodynamic",
        supports=(
            "Continuum hydrodynamic theory of flocking: derives the "
            "Toner-Tu equations and shows that 2D flocks can exhibit "
            "long-range order that equilibrium 2D systems cannot "
            "(escaping the Mermin-Wagner theorem). Companion to Vicsek "
            "1995."
        ),
        does_not_support=(
            "That 2D long-range order implies any specific 3D phase "
            "structure; the result is dimension-sensitive."
        ),
    ),
    ActiveMatterAnchor(
        source_id="toner_tu_1998_flocks_herds_schools",
        title=(
            "Flocks, herds, and schools: A quantitative theory of "
            "flocking"
        ),
        authors="J. Toner, Y. Tu",
        year=1998,
        venue="Physical Review E 58, 4828",
        url="https://journals.aps.org/pre/abstract/10.1103/PhysRevE.58.4828",
        doi="10.1103/PhysRevE.58.4828",
        category="toner_tu_hydrodynamic",
        supports=(
            "Detailed quantitative continuum theory of flocking — "
            "full derivation of the Toner-Tu equations and the "
            "anomalous scaling of velocity-velocity correlations in "
            "active 2D and 3D phases."
        ),
        does_not_support=(
            "Numerical exact-match to actual bird flock data — the "
            "Toner-Tu universality class is a coarse description."
        ),
    ),
    ActiveMatterAnchor(
        source_id="marchetti_2013_active_matter_RMP",
        title="Hydrodynamics of soft active matter",
        authors=(
            "M. C. Marchetti, J. F. Joanny, S. Ramaswamy, T. B. "
            "Liverpool, J. Prost, M. Rao, R. A. Simha"
        ),
        year=2013,
        venue="Reviews of Modern Physics 85, 1143",
        url="https://journals.aps.org/rmp/abstract/10.1103/RevModPhys.85.1143",
        doi="10.1103/RevModPhys.85.1143",
        category="active_matter_review",
        supports=(
            "The canonical review of soft active matter: defines the "
            "field, derives hydrodynamic theories for polar and "
            "nematic active fluids, and covers experimental systems "
            "from bacterial suspensions to cytoskeletal extracts. The "
            "single most-cited peer-reviewed entry point."
        ),
        does_not_support=(
            "That every active-matter system is fluid; granular and "
            "dry active matter have distinct treatments."
        ),
    ),
    ActiveMatterAnchor(
        source_id="ramaswamy_2010_mechanics_statistics_active",
        title="The Mechanics and Statistics of Active Matter",
        authors="S. Ramaswamy",
        year=2010,
        venue="Annual Review of Condensed Matter Physics 1, 323",
        url=(
            "https://www.annualreviews.org/doi/10.1146/"
            "annurev-conmatphys-070909-104101"
        ),
        doi="10.1146/annurev-conmatphys-070909-104101",
        category="active_matter_review",
        supports=(
            "Annual Review of Condensed Matter Physics overview of "
            "active matter mechanics and statistics — covers polar "
            "active fluids, giant number fluctuations, motility-"
            "induced phase separation, and the role of broken "
            "time-reversal symmetry."
        ),
        does_not_support=(
            "That all of biology reduces to active-matter physics — "
            "Ramaswamy is explicit that biology adds layers "
            "(signaling, memory, growth) beyond active matter."
        ),
    ),
    ActiveMatterAnchor(
        source_id="cates_tailleur_2015_motility_induced_phase_separation",
        title="Motility-Induced Phase Separation",
        authors="M. E. Cates, J. Tailleur",
        year=2015,
        venue="Annual Review of Condensed Matter Physics 6, 219",
        url=(
            "https://www.annualreviews.org/doi/10.1146/"
            "annurev-conmatphys-031214-014710"
        ),
        doi="10.1146/annurev-conmatphys-031214-014710",
        category="phase_separation",
        supports=(
            "Definitive review of motility-induced phase separation "
            "(MIPS): purely repulsive active particles can phase-"
            "separate into dense + dilute regions because slowing "
            "down where it is crowded is enough to drive instability. "
            "Direct peer-reviewed support for 'swimmers form organs' "
            "framing in SIFTA."
        ),
        does_not_support=(
            "That MIPS is the mechanism behind biological organ "
            "formation; the parallel is structural, not mechanistic."
        ),
    ),
    ActiveMatterAnchor(
        source_id="bechinger_2016_active_particles_complex_environments",
        title="Active Particles in Complex and Crowded Environments",
        authors=(
            "C. Bechinger, R. Di Leonardo, H. Löwen, C. Reichhardt, "
            "G. Volpe, G. Volpe"
        ),
        year=2016,
        venue="Reviews of Modern Physics 88, 045006",
        url="https://journals.aps.org/rmp/abstract/10.1103/RevModPhys.88.045006",
        doi="10.1103/RevModPhys.88.045006",
        category="active_matter_review",
        supports=(
            "Reviews of Modern Physics survey of active particles "
            "(self-propelled colloids and microswimmers) in complex "
            "environments — directly relevant to SIFTA swimmers "
            "navigating a structured stigmergic field with barriers."
        ),
        does_not_support=(
            "That SIFTA's classical agents reproduce hydrodynamic "
            "coupling between active colloids in real fluid."
        ),
    ),
    ActiveMatterAnchor(
        source_id="cavagna_2010_scale_free_correlations_starling_flocks",
        title=(
            "Scale-free correlations in starling flocks"
        ),
        authors=(
            "A. Cavagna, A. Cimarelli, I. Giardina, G. Parisi, R. "
            "Santagati, F. Stefanini, M. Viale"
        ),
        year=2010,
        venue="Proceedings of the National Academy of Sciences 107, 11865",
        url="https://www.pnas.org/doi/10.1073/pnas.1005766107",
        doi="10.1073/pnas.1005766107",
        category="empirical_flocking",
        supports=(
            "Empirical demonstration that starling flocks exhibit "
            "scale-free correlations — the correlation length grows "
            "with the system size. Direct evidence that active matter "
            "in nature exhibits the long-range coupling SIFTA's "
            "stigmergic field aims to model."
        ),
        does_not_support=(
            "That SIFTA's classical solver has measured a starling "
            "flock; the bridge is again structural."
        ),
    ),
)


def verified_anchors() -> list[dict[str, Any]]:
    return [a.as_dict() for a in VERIFIED_ANCHORS]


def verified_anchor_ids() -> list[str]:
    return [a.source_id for a in VERIFIED_ANCHORS]


# ─────────────────────────────────────────────────────────────────────────
# Section B — Vicsek numerical model (PRL 75, 1226)
# ─────────────────────────────────────────────────────────────────────────
@dataclass
class VicsekConfig:
    """Parameters of the Vicsek 1995 self-propelled particle model.

    n_particles  N
    box_size     L (square box, periodic boundary)
    speed        v0 (constant speed of every particle)
    radius       R (alignment-interaction radius)
    noise        η ∈ [0, 2π] (uniform additive angular noise per step)
    """
    n_particles: int
    box_size: float
    speed: float = 0.03
    radius: float = 1.0
    noise: float = 0.5

    def __post_init__(self) -> None:
        if self.n_particles < 1:
            raise ValueError("n_particles must be ≥ 1")
        if self.box_size <= 0:
            raise ValueError("box_size must be positive")
        if not (0.0 <= self.noise <= 2.0 * math.pi):
            raise ValueError("noise must lie in [0, 2π]")
        if self.speed < 0:
            raise ValueError("speed must be non-negative")
        if self.radius <= 0:
            raise ValueError("radius must be positive")


class VicsekModel:
    """A minimal deterministic numpy implementation of the Vicsek model.

    State per particle: position (x, y) in [0, L)² and heading θ. At
    each step:

        θᵢ ← angle(mean over j∈neighbors(i) of (cos θⱼ, sin θⱼ)) + ξ
        xᵢ ← xᵢ + v0 (cos θᵢ, sin θᵢ),  modulo L

    `ξ` is uniform in [-η/2, η/2]. Neighborhood: all particles within
    `radius` under periodic boundaries.
    """

    def __init__(self, config: VicsekConfig, *, seed: int | None = None) -> None:
        self.config = config
        self.rng = np.random.default_rng(seed)
        self.positions: np.ndarray = self.rng.uniform(
            0.0, config.box_size, size=(config.n_particles, 2)
        )
        self.thetas: np.ndarray = self.rng.uniform(
            -math.pi, math.pi, size=config.n_particles
        )
        self.step_count: int = 0

    def step(self) -> None:
        cfg = self.config
        N = cfg.n_particles
        L = cfg.box_size
        R = cfg.radius

        # Pairwise distances with periodic boundary correction.
        dx = self.positions[:, None, 0] - self.positions[None, :, 0]
        dy = self.positions[:, None, 1] - self.positions[None, :, 1]
        dx -= L * np.round(dx / L)
        dy -= L * np.round(dy / L)
        dist2 = dx * dx + dy * dy
        neighbors = dist2 <= (R * R)

        # Mean heading vector among each particle's neighbors.
        cos_t = np.cos(self.thetas)
        sin_t = np.sin(self.thetas)
        sum_cos = neighbors @ cos_t
        sum_sin = neighbors @ sin_t
        mean_theta = np.arctan2(sum_sin, sum_cos)

        # Add uniform noise.
        noise = self.rng.uniform(
            -cfg.noise / 2.0, cfg.noise / 2.0, size=N
        )
        self.thetas = mean_theta + noise

        # Move with constant speed.
        self.positions[:, 0] = (
            self.positions[:, 0] + cfg.speed * np.cos(self.thetas)
        ) % L
        self.positions[:, 1] = (
            self.positions[:, 1] + cfg.speed * np.sin(self.thetas)
        ) % L
        self.step_count += 1

    def run(self, steps: int) -> None:
        for _ in range(int(steps)):
            self.step()

    # ── Order parameter (the canonical Vicsek observable) ───────────────
    def polar_order(self) -> float:
        """φ = |⟨e^{iθ}⟩| ∈ [0, 1]. 0 = disordered, 1 = perfectly aligned."""
        N = self.config.n_particles
        if N == 0:
            return 0.0
        cos_t = np.cos(self.thetas)
        sin_t = np.sin(self.thetas)
        return float(math.hypot(cos_t.mean(), sin_t.mean()))

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": TRUTH_LABEL,
            "ts": time.time(),
            "n_particles": self.config.n_particles,
            "box_size": self.config.box_size,
            "speed": self.config.speed,
            "radius": self.config.radius,
            "noise": self.config.noise,
            "step_count": self.step_count,
            "polar_order": self.polar_order(),
            "truth_guard": ACTIVE_MATTER_TRUTH_GUARD,
        }


# ─────────────────────────────────────────────────────────────────────────
# Section C — Vicsek noise-parameter scan (the phase transition itself)
# ─────────────────────────────────────────────────────────────────────────
#
# Vicsek 1995 (PRL 75, 1226, DOI 10.1103/PhysRevLett.75.1226) Figure 2
# shows the polar order parameter φ as a function of noise amplitude η at
# fixed density. Below a critical η_c the system flocks (φ > 0); above
# it the system is disordered (φ → 0).
#
# This scan reproduces Figure 2 numerically and exposes the transition
# region directly for the SIFTA tournament document.
@dataclass(frozen=True)
class VicsekScanResult:
    """One Vicsek noise scan — η values vs steady-state polar order."""

    noises: tuple[float, ...]
    polar_orders: tuple[float, ...]
    polar_order_std: tuple[float, ...]
    n_particles: int
    box_size: float
    speed: float
    radius: float
    burn_in_steps: int
    average_over_steps: int
    seed: int | None
    truth_label: str = TRUTH_LABEL

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("noises", "polar_orders", "polar_order_std"):
            d[k] = list(d[k])
        return d

    def critical_noise_estimate(self, threshold: float = 0.5) -> float | None:
        """Estimate η_c as the noise where the order parameter crosses
        `threshold`. Returns None if no crossing is present.

        Vicsek 1995 ascertains a continuous transition; this rough
        estimate is for the tournament-document plot only.
        """
        prev_eta = None
        prev_phi = None
        for eta, phi in zip(self.noises, self.polar_orders):
            if prev_phi is not None:
                if (prev_phi - threshold) * (phi - threshold) <= 0:
                    # Linear interpolation between consecutive points.
                    if phi == prev_phi:
                        return float(eta)
                    return float(
                        prev_eta + (threshold - prev_phi) * (eta - prev_eta)
                        / (phi - prev_phi)
                    )
            prev_eta, prev_phi = eta, phi
        return None


def vicsek_noise_scan(
    *,
    noises: Sequence[float],
    n_particles: int = 200,
    box_size: float = 5.0,
    speed: float = 0.03,
    radius: float = 1.0,
    burn_in_steps: int = 200,
    average_over_steps: int = 100,
    seed: int | None = 0,
) -> VicsekScanResult:
    """Scan polar order vs noise to reproduce Vicsek 1995 Figure 2.

    For each noise η in `noises`:
    1. Build a fresh VicsekModel.
    2. Run `burn_in_steps` to reach steady state.
    3. Average the polar order over the next `average_over_steps`.
    4. Record mean and std.

    The averaging step is essential — the order parameter fluctuates,
    and a single instantaneous reading near the critical point is
    noisy.
    """
    noises_t = tuple(float(n) for n in noises)
    means: list[float] = []
    stds: list[float] = []
    rng = np.random.default_rng(seed)
    for eta in noises_t:
        cfg = VicsekConfig(
            n_particles=n_particles, box_size=box_size,
            speed=speed, radius=radius, noise=float(eta),
        )
        # Each scan point gets its own seed so the run is deterministic
        # and reproducible.
        seed_i = int(rng.integers(0, 2**31 - 1))
        m = VicsekModel(cfg, seed=seed_i)
        m.run(int(burn_in_steps))
        samples: list[float] = []
        for _ in range(int(average_over_steps)):
            m.step()
            samples.append(m.polar_order())
        means.append(float(np.mean(samples)))
        stds.append(float(np.std(samples)))
    return VicsekScanResult(
        noises=noises_t,
        polar_orders=tuple(means),
        polar_order_std=tuple(stds),
        n_particles=n_particles,
        box_size=box_size,
        speed=speed,
        radius=radius,
        burn_in_steps=burn_in_steps,
        average_over_steps=average_over_steps,
        seed=seed,
    )


_PHI_RAMP: str = " ░▒▓█"


def render_scan_ascii(result: VicsekScanResult, *, width: int = 50) -> str:
    """Render the η → φ transition curve as an ASCII plot.

    Each row corresponds to one (η, φ) point; the column position is
    proportional to φ. Reads top-down: increasing η.
    """
    if not result.noises:
        return "[Vicsek scan empty]\n"
    out: list[str] = []
    out.append(
        f"Vicsek 1995 (PRL 75, 1226) phase transition — "
        f"N={result.n_particles}, L={result.box_size}, "
        f"v0={result.speed}, R={result.radius}"
    )
    out.append("  η (noise) ┃ φ (polar order, 0 → 1)")
    out.append("  ──────────┃" + "─" * width)
    for eta, phi in zip(result.noises, result.polar_orders):
        col = int(max(0.0, min(1.0, phi)) * (width - 1))
        bar = " " * col + "█" + " " * (width - col - 1)
        out.append(f"  {eta:8.3f}  ┃{bar}  {phi:.3f}")
    crit = result.critical_noise_estimate()
    if crit is not None:
        out.append("")
        out.append(
            f"  η_c (φ=0.5 crossing, linear interp) ≈ {crit:.3f}"
        )
    return "\n".join(out)


# ─────────────────────────────────────────────────────────────────────────
# Section D — receipts / public API
# ─────────────────────────────────────────────────────────────────────────
def active_matter_payload() -> dict[str, Any]:
    return {
        "truth_label": TRUTH_LABEL,
        "truth_guard": ACTIVE_MATTER_TRUTH_GUARD,
        "verified_anchors": verified_anchors(),
        "anchor_count": len(VERIFIED_ANCHORS),
        "categories": sorted({a.category for a in VERIFIED_ANCHORS}),
    }


def write_active_matter_receipt(
    *,
    state_root: Path | None = None,
    receipt_path: Path | None = None,
    extra_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = state_root or _STATE
    out = receipt_path or _LEDGER
    payload = active_matter_payload()
    if extra_snapshot:
        payload = {**payload, "snapshot": extra_snapshot}
    row = {
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "kind": "ACTIVE_MATTER_RECEIPT",
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
    "ACTIVE_MATTER_TRUTH_GUARD",
    "ActiveMatterAnchor",
    "TRUTH_LABEL",
    "VERIFIED_ANCHORS",
    "VicsekConfig",
    "VicsekModel",
    "VicsekScanResult",
    "active_matter_payload",
    "render_scan_ascii",
    "verified_anchor_ids",
    "verified_anchors",
    "vicsek_noise_scan",
    "write_active_matter_receipt",
]
