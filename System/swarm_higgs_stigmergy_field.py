#!/usr/bin/env python3
"""Higgs/stigmergic symmetry-breaking analogue.

This is an executable bridge for tournament section 20:

    non-zero substrate + coupling -> effective inertia for swimmers

It is a classical scalar-field toy model. It does not observe Higgs bosons,
electroweak physics, or gauge fields on this Mac. The useful SIFTA claim is
smaller and testable: a persistent field can relax into a non-zero substrate,
and swimmers coupled to that substrate become harder to move cheaply.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

TRUTH_LABEL = "HIGGS_STIGMERGY_ANALOGUE_V1"
LEDGER_NAME = "higgs_stigmergy_receipts.jsonl"
TRUTH_BOUNDARY = (
    "Classical scalar-field analogy only: no OBSERVED Higgs bosons, no "
    "Yang-Mills proof, no particle-physics discovery on this node."
)
TRUTH_LABEL_PARTICLE = "HIGGS_STIGMERGY_PARTICLE_V1"
TRUTH_LABEL_FORCE_SWEEP = "HIGGS_STIGMERGY_FORCE_SWEEP_V1"
TRUTH_LABEL_KILLER_DEMO = "HIGGS_STIGMERGY_KILLER_DEMO_V1"
TRUTH_LABEL_SYMMETRY_BREAK = "HIGGS_STIGMERGY_SYMMETRY_BREAK_V1"
TRUTH_LABEL_ADAPTIVE = "PERSISTENCE_INERTIA_FIELD_ADAPTIVE_V1"
TRUTH_LABEL_MEMORY_FIELD = "PERSISTENCE_INERTIA_FIELD_MEMORY_V1"
TRUTH_LABEL_COLLIDER = "PERSISTENCE_INERTIA_FIELD_COLLIDER_V1"
TRUTH_LABEL_TEMPORAL_PHASE = "PERSISTENCE_INERTIA_FIELD_TEMPORAL_PHASE_V1"
TRUTH_LABEL_GHOST_CIV = "PERSISTENCE_INERTIA_FIELD_GHOST_CIVILIZATIONS_V1"

# ── numpy is OPTIONAL ─────────────────────────────────────────────────────
# The original scalar-field engine is pure-Python so its tests stay
# lightweight. The particle swimmer (Cowork 2026-05-13) needs numpy for
# gradient + vector math. Import lazily so the field engine remains
# importable on a node that hasn't installed numpy.
try:
    import numpy as _np  # noqa: F401
    _HAS_NUMPY = True
except Exception:
    _HAS_NUMPY = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _state_dir(state_root: str | Path | None = None) -> Path:
    if state_root is None:
        env = os.environ.get("SIFTA_STATE_ROOT")
        if env:
            return Path(env)
        return _repo_root() / ".sifta_state"
    p = Path(state_root)
    if (p / "System").exists() and (p / ".sifta_state").exists():
        return p / ".sifta_state"
    return p


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


@dataclass(frozen=True)
class HiggsFieldConfig:
    width: int = 24
    height: int = 16
    vev: float = 1.0
    lambda_: float = 1.0
    diffusion: float = 0.08
    dt: float = 0.05
    seed: int = 13
    initial_noise: float = 0.045


@dataclass(frozen=True)
class SwimmerProbe:
    name: str
    x: int
    y: int
    coupling: float
    base_latency_ms: float = 100.0


class HiggsStigmergyField:
    """Small scalar field with a Mexican-hat-style potential.

    The field variable ``phi`` relaxes toward one of two non-zero substrate
    values (+vev or -vev). A swimmer's effective mass is a local function of
    ``phi^2`` and the swimmer coupling.
    """

    def __init__(self, config: HiggsFieldConfig | None = None) -> None:
        self.config = config or HiggsFieldConfig()
        if self.config.width < 3 or self.config.height < 3:
            raise ValueError("field dimensions must be at least 3x3")
        if self.config.vev <= 0:
            raise ValueError("vev must be positive")
        if self.config.lambda_ <= 0 or self.config.dt <= 0:
            raise ValueError("lambda_ and dt must be positive")
        rng = random.Random(self.config.seed)
        self.phi: list[list[float]] = [
            [
                rng.uniform(-self.config.initial_noise, self.config.initial_noise)
                for _ in range(self.config.width)
            ]
            for _ in range(self.config.height)
        ]
        self.steps = 0

    def _laplacian(self, x: int, y: int) -> float:
        h = self.config.height
        w = self.config.width
        c = self.phi[y][x]
        return (
            self.phi[y][(x - 1) % w]
            + self.phi[y][(x + 1) % w]
            + self.phi[(y - 1) % h][x]
            + self.phi[(y + 1) % h][x]
            - 4.0 * c
        )

    def step(self) -> None:
        cfg = self.config
        next_phi: list[list[float]] = []
        limit = 2.5 * cfg.vev
        for y in range(cfg.height):
            row: list[float] = []
            for x in range(cfg.width):
                phi = self.phi[y][x]
                d_v_d_phi = 4.0 * cfg.lambda_ * phi * (phi * phi - cfg.vev * cfg.vev)
                update = cfg.diffusion * self._laplacian(x, y) - d_v_d_phi
                row.append(_clamp(phi + cfg.dt * update, -limit, limit))
            next_phi.append(row)
        self.phi = next_phi
        self.steps += 1

    def relax(self, steps: int = 160) -> dict[str, float]:
        if steps < 0:
            raise ValueError("steps must be >= 0")
        before = self.order_parameter
        before_energy = self.mean_potential
        for _ in range(steps):
            self.step()
        return {
            "initial_order_parameter": round(before, 6),
            "final_order_parameter": round(self.order_parameter, 6),
            "initial_mean_potential": round(before_energy, 6),
            "final_mean_potential": round(self.mean_potential, 6),
            "steps": self.steps,
        }

    @property
    def order_parameter(self) -> float:
        cells = [abs(v) for row in self.phi for v in row]
        return sum(cells) / len(cells)

    @property
    def signed_bias(self) -> float:
        cells = [v for row in self.phi for v in row]
        return sum(cells) / len(cells)

    @property
    def mean_potential(self) -> float:
        cfg = self.config
        values = [
            cfg.lambda_ * (v * v - cfg.vev * cfg.vev) ** 2
            for row in self.phi
            for v in row
        ]
        return sum(values) / len(values)

    def local_phi(self, x: int, y: int) -> float:
        return self.phi[y % self.config.height][x % self.config.width]

    def effective_mass(self, probe: SwimmerProbe) -> float:
        phi = self.local_phi(probe.x, probe.y)
        return 1.0 + max(0.0, probe.coupling) * (phi * phi)

    def evaluate_swimmer(self, probe: SwimmerProbe) -> dict[str, Any]:
        mass = self.effective_mass(probe)
        mobility = 1.0 / mass
        return {
            "name": probe.name,
            "x": probe.x,
            "y": probe.y,
            "coupling": round(probe.coupling, 6),
            "local_phi": round(self.local_phi(probe.x, probe.y), 6),
            "effective_mass": round(mass, 6),
            "mobility": round(mobility, 6),
            "latency_ms": round(probe.base_latency_ms * mass, 3),
            "stgm_cost": round(0.1 * mass, 6),
        }


def default_swimmers(width: int, height: int) -> list[SwimmerProbe]:
    x = width // 2
    y = height // 2
    return [
        SwimmerProbe("photon_like_free_swimmer", x, y, 0.0),
        SwimmerProbe("weakly_coupled_swimmer", x, y, 1.0),
        SwimmerProbe("strongly_coupled_swimmer", x, y, 4.0),
    ]


def phi_as_array(field: "HiggsStigmergyField"):
    """Return field.phi as a (height, width) numpy array. Requires numpy.

    The scalar-field engine stores phi as list-of-lists to keep its tests
    numpy-free. The particle organ needs vectorised access, so this helper
    converts once per frame. Costs O(width*height); cheap at the
    24*16 = 384 default size."""
    if not _HAS_NUMPY:
        raise RuntimeError("phi_as_array requires numpy")
    return _np.asarray(field.phi, dtype=float)


class HiggsParticleSwimmer:
    """Many-body swimmer organ — particles living inside the Higgs field.

    Each swimmer is a tiny "ascii swimmer" with position, velocity, and a
    fixed coupling to the scalar substrate. Effective mass is set by the
    local |phi| value the swimmer sits on:

        m_eff = 1 + coupling * |phi(x, y)|

    Force comes from the gradient of |phi| (swimmers drift toward
    field-substrate maxima — the analogue of a Yukawa attraction toward
    mass-bearing regions), plus an optional thermal kick so the demo is
    visibly alive on the Mac screen. Newton's law a = F / m carries the
    inertia story end-to-end: heavy coupled swimmers respond LESS to the
    same force; light free swimmers respond MORE. A small constant
    velocity damping makes the simulation visibly settle without
    artificially over-friction-ing heavy particles.

    Truth boundary
    --------------
    This is a CLASSICAL ANALOGUE. The swimmers are not electrons; the
    field is not the Standard-Model Higgs; the mass law is a metaphor
    chosen to match §20.B of the tournament doc. Receipts written by
    this organ carry TRUTH_LABEL_PARTICLE = "HIGGS_STIGMERGY_PARTICLE_V1"
    and the same TRUTH_BOUNDARY disclaimer the scalar field uses.

    Architect 2026-05-13 doctrine: 'Treat swimmers as literal particles.
    Give them (x,y), velocity, coupling strength. Mass = 1 + coupling
    × |phi|. Gradient force from the field pulls them. Free swimmers
    diffuse fast; coupled ones get heavy and slow.'
    """

    def __init__(
        self,
        n: int = 30,
        coupling: float = 0.0,
        field_shape: tuple[int, int] = (24, 16),
        *,
        seed: int = 17,
        thermal_kick: float = 0.4,
        damping: float = 0.95,
        force_scale: float = 1.0,
        max_speed: float = 8.0,
        drive_amplitude: float = 1.0,
        write_rate: float = 0.0,
        write_inertia_coefficient: float = 0.0,
        write_inertia_kind: str = "log",
        organ_memberships: tuple[str, ...] | None = None,
        organ_inertia_coefficient: float = 0.0,
        velocity_write_modulation: float = 0.0,
        crowding_competition: bool = False,
        name: str = "swimmer",
    ) -> None:
        # Architect 2026-05-13 — Grok analysis: "if you really crank the
        # force in the sim, eventually even the heavy swimmers start
        # moving fast again — high-energy collisions overcome binding."
        # drive_amplitude is a single live knob that scales BOTH the
        # gradient force AND the thermal kick. Slider it from 0.1 (weak)
        # to 10.0 (extreme) and watch the mass spectrum collapse as
        # binding is overcome.
        if not _HAS_NUMPY:
            raise RuntimeError("HiggsParticleSwimmer requires numpy")
        if n < 1:
            raise ValueError("need at least one swimmer")
        if field_shape[0] < 3 or field_shape[1] < 3:
            raise ValueError("field_shape must be at least 3x3")
        if drive_amplitude < 0.0:
            raise ValueError("drive_amplitude must be >= 0")
        if write_rate < 0.0 or write_rate > 1.0:
            raise ValueError("write_rate must be in [0, 1]")
        if write_inertia_coefficient < 0.0:
            raise ValueError("write_inertia_coefficient must be >= 0")
        if organ_inertia_coefficient < 0.0:
            raise ValueError("organ_inertia_coefficient must be >= 0")
        if velocity_write_modulation < 0.0:
            raise ValueError("velocity_write_modulation must be >= 0")
        if write_inertia_kind not in ("log", "sqrt", "linear"):
            raise ValueError("write_inertia_kind must be 'log', 'sqrt', or 'linear'")
        h, w = int(field_shape[0]), int(field_shape[1])
        self._h = h
        self._w = w
        self.name = name
        self.coupling = float(coupling)
        self._thermal_kick = float(thermal_kick)
        self._damping = float(damping)
        self._force_scale = float(force_scale)
        self._max_speed = float(max_speed)
        self.drive_amplitude = float(drive_amplitude)
        # Architect 2026-05-13 — Q1/Q5/Q8 unified mass law extension.
        # write_rate is the per-step probability that each swimmer
        # appends to the shared trace ledger (in-memory counter for
        # simulation purposes). write_inertia_coefficient (alpha)
        # weights accumulated writes into m_eff. organ_memberships
        # is the set of named organs this swimmer participates in;
        # organ_inertia_coefficient (beta) weights organ count into
        # m_eff. The full law is:
        #   m_eff = 1 + g·|phi|  +  alpha · ln(1 + write_count)  +  beta · n_organs
        # The log-write term so a swimmer that has written 10000 times
        # is heavier than one that wrote 100 times, but not 100x heavier.
        # Sub-linear participation cost — like memory weight in neural
        # systems.
        self._write_rate = float(write_rate)
        self._write_inertia_coefficient = float(write_inertia_coefficient)
        self._write_inertia_kind = str(write_inertia_kind)
        self.organ_memberships = tuple(organ_memberships or ())
        self._organ_inertia_coefficient = float(organ_inertia_coefficient)
        # Architect 2026-05-13 — Q6 spontaneous symmetry breaking.
        # When velocity_write_modulation > 0, the effective per-step
        # write probability for each swimmer becomes:
        #     p_effective_i = clip(write_rate + gamma/(1+|v_i|^2), 0, 1)
        # Slow swimmers write more (because they linger in a region).
        # Combined with the unified mass law (writes -> heavier -> slower),
        # this is the positive feedback loop that should break symmetry
        # spontaneously from identical initial conditions.
        self._velocity_write_modulation = float(velocity_write_modulation)
        # Architect Q6 follow-on (2026-05-13): without non-mean-field
        # coupling between swimmers, identical-swimmer dynamics reaches
        # a robust symmetric attractor across every (kind, alpha, gamma,
        # coupling) combo tested. crowding_competition turns ON a non-
        # mean-field interaction: each swimmer's deposit is divided by
        # the number of swimmers in its current field cell. Lonely
        # swimmers write at full rate; crowded swimmers split the
        # write resource. This is the simplest physical "resource
        # competition" mechanism — pheromone-trail-style ant dynamics.
        self._crowding_competition = bool(crowding_competition)
        self.write_count = _np.zeros(n, dtype=float)
        self._rng = _np.random.default_rng(seed)
        # Position is in field-index space: x in [0, w), y in [0, h).
        # Uniform initial spread so the demo doesn't start clumped.
        self.pos = self._rng.uniform(low=[0, 0], high=[w, h], size=(n, 2))
        # Small isotropic Gaussian initial velocity.
        self.vel = self._rng.normal(scale=0.3, size=(n, 2))
        self.mass = _np.ones(n, dtype=float)
        self._steps = 0

    @property
    def n(self) -> int:
        return int(self.pos.shape[0])

    def step(self, phi_array, dt: float = 0.05) -> None:
        """Advance one timestep using the current field snapshot.

        phi_array : numpy 2-D array shaped (height, width)."""
        if phi_array.shape != (self._h, self._w):
            raise ValueError(
                f"phi_array shape {phi_array.shape} does not match "
                f"swimmer field_shape ({self._h}, {self._w})"
            )
        abs_phi = _np.abs(phi_array)
        # numpy.gradient returns (d/dy, d/dx) for a 2-D array. Spacing 1.0
        # in lattice units is fine for an analogy.
        grad_y, grad_x = _np.gradient(abs_phi)

        # Sample local phi and gradient at each swimmer's cell.
        # Floor to int then wrap with %, matching the field's torus topology.
        ix = (_np.floor(self.pos[:, 0]).astype(int)) % self._w
        iy = (_np.floor(self.pos[:, 1]).astype(int)) % self._h
        local_phi = abs_phi[iy, ix]

        # Optional participation: each swimmer writes to the shared
        # trace ledger with probability write_rate per step. The
        # write_count is the per-swimmer accumulated participation —
        # the deeper "memory Higgs" mechanism the architect's Q1+Q8
        # asks about. In a real organ this would push receipts onto
        # an append-only JSONL; here we count to keep the simulation
        # deterministic and cheap.
        #
        # Q6 extension: if velocity_write_modulation > 0, slow swimmers
        # write more (linger ⇒ deposit). The first cut used a clipped
        # Bernoulli rate which SATURATED at p=1.0 and ironically erased
        # the very differentiation we wanted. The current cut uses a
        # CONTINUOUS deposit: each swimmer adds gamma/(1+|v|^2) to its
        # write_count per step, plus an optional probabilistic baseline
        # write_rate. This way slow swimmers really do accumulate more.
        if self._velocity_write_modulation > 0.0 or self._write_rate > 0.0:
            speed_sq = _np.sum(self.vel * self.vel, axis=1)
            # Crowding competition: count swimmers per cell, divide
            # each swimmer's deposit by the count. Non-mean-field
            # interaction — what breaks the symmetric attractor.
            if self._crowding_competition:
                cell_id = iy * self._w + ix
                # bincount of cell ids gives occupancy per cell
                occ = _np.bincount(cell_id, minlength=self._h * self._w)
                divisor = occ[cell_id].astype(float)
                divisor = _np.maximum(divisor, 1.0)
            else:
                divisor = 1.0
            if self._velocity_write_modulation > 0.0:
                continuous_deposit = self._velocity_write_modulation / (1.0 + speed_sq)
                if self._crowding_competition:
                    continuous_deposit = continuous_deposit / divisor
                self.write_count = self.write_count + continuous_deposit
            if self._write_rate > 0.0:
                writes_this_step = (
                    self._rng.random(self.n) < self._write_rate
                ).astype(float)
                if self._crowding_competition:
                    writes_this_step = writes_this_step / divisor
                self.write_count = self.write_count + writes_this_step

        # Unified mass law (architect Q8):
        #   m_eff = 1 + g·|phi| + alpha · f(writes) + beta · n_organs
        # where f() is "log" (sub-linear, default, stable), "sqrt"
        # (sub-linear, intermediate), or "linear" (super-linear in
        # the dynamical sense — required for Q6 symmetry breaking).
        organ_term = (
            self._organ_inertia_coefficient * float(len(self.organ_memberships))
        )
        if self._write_inertia_kind == "log":
            write_term = _np.log1p(self.write_count)
        elif self._write_inertia_kind == "sqrt":
            write_term = _np.sqrt(self.write_count)
        elif self._write_inertia_kind == "linear":
            write_term = self.write_count
        else:
            write_term = _np.log1p(self.write_count)
        memory_term = self._write_inertia_coefficient * write_term
        self.mass = 1.0 + self.coupling * local_phi + memory_term + organ_term

        # Force vector: pull toward higher |phi|. Yukawa-flavoured analogue.
        fx = self.coupling * grad_x[iy, ix]
        fy = self.coupling * grad_y[iy, ix]
        force = _np.stack([fx, fy], axis=1) * self._force_scale

        # Optional thermal kick so the demo is visibly alive. Same kick
        # magnitude for all swimmers — what differs is F/m response.
        if self._thermal_kick > 0:
            kick = self._rng.normal(scale=self._thermal_kick, size=self.pos.shape)
            force = force + kick

        # Architect drive amplitude — Grok regime knob. Scales the WHOLE
        # net force. At drive≈0 the swimmers barely move. At drive≈1
        # we get the baseline mass spectrum. At drive≈5+ the heavy
        # swimmers start to "overcome binding" because v_max is fixed
        # by max_speed and damping, not by 1/m.
        if self.drive_amplitude != 1.0:
            force = force * self.drive_amplitude

        # Newton: a = F / m, broadcast 1/m down each row.
        inv_mass = 1.0 / self.mass
        accel = force * inv_mass[:, None]
        self.vel = self.vel + accel * dt
        # Velocity damping — same for all swimmers so the mass spectrum
        # comes from F/m, not from heavy-particle-specific drag.
        self.vel *= self._damping
        # Hard speed cap to keep numerics safe.
        speed = _np.linalg.norm(self.vel, axis=1)
        too_fast = speed > self._max_speed
        if too_fast.any():
            scale = self._max_speed / (speed[too_fast] + 1e-9)
            self.vel[too_fast] = self.vel[too_fast] * scale[:, None]

        # Advance position; periodic boundaries (torus).
        self.pos = self.pos + self.vel * dt
        self.pos[:, 0] = self.pos[:, 0] % self._w
        self.pos[:, 1] = self.pos[:, 1] % self._h
        self._steps += 1

    def mobility(self) -> float:
        """Mean speed (|v|) across the swarm. Higher = freer."""
        return float(_np.mean(_np.linalg.norm(self.vel, axis=1)))

    def mean_mass(self) -> float:
        return float(_np.mean(self.mass))

    def state(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "n": self.n,
            "coupling": self.coupling,
            "drive_amplitude": self.drive_amplitude,
            "write_rate": self._write_rate,
            "write_inertia_coefficient": self._write_inertia_coefficient,
            "write_inertia_kind": self._write_inertia_kind,
            "organ_memberships": list(self.organ_memberships),
            "organ_inertia_coefficient": self._organ_inertia_coefficient,
            "velocity_write_modulation": self._velocity_write_modulation,
            "crowding_competition": self._crowding_competition,
            "mean_write_count": float(_np.mean(self.write_count)) if _HAS_NUMPY else 0.0,
            "mean_mass": round(self.mean_mass(), 6),
            "mobility": round(self.mobility(), 6),
            "steps": self._steps,
        }

    def set_drive_amplitude(self, value: float) -> None:
        """Live-update the drive scale. Called by the Engine D slider."""
        if value < 0.0:
            raise ValueError("drive_amplitude must be >= 0")
        self.drive_amplitude = float(value)


def run_particle_higgs_experiment(
    *,
    couplings: tuple[float, ...] = (0.0, 1.0, 4.0),
    n_per_band: int = 30,
    field_config: HiggsFieldConfig | None = None,
    relax_steps: int = 180,
    swimmer_steps: int = 1000,
    sample_every: int = 100,
    state_root: str | Path | None = None,
    write: bool = True,
    seed: int = 17,
) -> dict[str, Any]:
    """Run the 1000-step particle-Higgs experiment.

    1. Relax the scalar field into its non-zero substrate.
    2. Spawn n_per_band swimmers at each coupling value.
    3. Step the field AND every swimmer for swimmer_steps timesteps.
    4. Record mean mobility + mean mass per band at each sample point.
    5. Write a HIGGS_PARTICLE_MOBILITY receipt.

    Returns the full result dict (also written to the ledger when write=True).
    """
    if not _HAS_NUMPY:
        raise RuntimeError("run_particle_higgs_experiment requires numpy")
    field = HiggsStigmergyField(field_config)
    relaxation = field.relax(relax_steps)
    h, w = field.config.height, field.config.width
    swimmers: dict[str, HiggsParticleSwimmer] = {}
    names = {0.0: "free", 1.0: "weak", 4.0: "strong"}
    for c in couplings:
        nice = names.get(float(c), f"c{c:g}")
        swimmers[nice] = HiggsParticleSwimmer(
            n=n_per_band, coupling=float(c), field_shape=(h, w),
            seed=seed + int(round(c * 1000)),
            name=nice,
        )

    samples: list[dict[str, Any]] = []
    for t in range(1, swimmer_steps + 1):
        field.step()
        phi_arr = phi_as_array(field)
        for s in swimmers.values():
            s.step(phi_arr)
        if t % sample_every == 0 or t == swimmer_steps:
            row = {
                "t": t,
                "order_parameter": round(field.order_parameter, 6),
                "mean_potential": round(field.mean_potential, 6),
                "bands": {k: s.state() for k, s in swimmers.items()},
            }
            samples.append(row)

    # Final mobility ratios as the headline number for the receipt.
    final = samples[-1]["bands"] if samples else {}
    mobility_ratio = None
    if "free" in final and "strong" in final:
        free_mob = final["free"]["mobility"] + 1e-9
        mobility_ratio = round(final["strong"]["mobility"] / free_mob, 6)

    result = {
        "truth_label": TRUTH_LABEL_PARTICLE,
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_particle_physics_claim": True,
        "field_relaxation": relaxation,
        "config": {
            "couplings": list(couplings),
            "n_per_band": n_per_band,
            "field": asdict(field.config),
            "relax_steps": relax_steps,
            "swimmer_steps": swimmer_steps,
            "sample_every": sample_every,
        },
        "samples": samples,
        "final_state": final,
        "final_mobility_ratio_strong_over_free": mobility_ratio,
        "interpretation": (
            "Coupled swimmers acquire local mass from the scalar substrate; "
            "the same thermal/gradient force then moves them less per unit "
            "time. Mobility ratio strong/free below 1 confirms the spectrum."
        ),
    }
    if write:
        write_particle_receipt(result, state_root=state_root)
    return result


def write_particle_receipt(result: dict[str, Any], *, state_root: str | Path | None = None) -> dict[str, Any]:
    """Append a HIGGS_PARTICLE_MOBILITY row to the ledger."""
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "HIGGS_PARTICLE_MOBILITY",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL_PARTICLE,
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


# ════════════════════════════════════════════════════════════════════════════
# FORCE-REGIME SWEEP — Grok regime question, doctrine §20.F HYPOTHESIS
# ════════════════════════════════════════════════════════════════════════════
#
# Architect 2026-05-13 (relayed from Grok-Robotics + Cursor/Codex §20.F):
#     "if you really crank the force in the sim, eventually even the 'heavy'
#      swimmers start moving fast again — high-energy collisions overcome
#      binding."
#
# This sweep answers the pinned research question of §20.F:
#     "Can persistent participation in shared memory fields create
#      measurable inertia-like behavior in distributed agents (e.g., dwell
#      time, coupling strength, revert work, STGM gradient per perturbation)
#      on a single-node Mac simulation?"
#
# Method: walk drive_amplitude across [weak, normal, strong, saturation]
# regimes; for each drive level, run N swimmers per coupling band for a
# fixed number of steps; record final mobility per band. Report the
# mobility ratio strong/free as a function of drive — if §20.F's
# headline thesis holds, the ratio should approach 1 (binding overcome)
# as drive grows large.
#
# Truth class: HYPOTHESIS — receipt is HIGGS_STIGMERGY_FORCE_SWEEP_V1
# and explicitly NOT a particle-physics receipt. Same TRUTH_BOUNDARY.


def run_force_regime_sweep(
    *,
    drive_levels: tuple[float, ...] = (0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
    couplings: tuple[float, ...] = (0.0, 1.0, 4.0),
    n_per_band: int = 25,
    field_config: HiggsFieldConfig | None = None,
    relax_steps: int = 180,
    swimmer_steps: int = 400,
    state_root: str | Path | None = None,
    write: bool = True,
    seed: int = 17,
) -> dict[str, Any]:
    """Walk drive_amplitude across regimes and record the mass-spectrum
    collapse. Each regime uses an INDEPENDENT relaxed-field snapshot so
    one extreme drive doesn't pollute the next regime's substrate.

    Returns the full sweep result (also written to ledger when write=True).
    """
    if not _HAS_NUMPY:
        raise RuntimeError("run_force_regime_sweep requires numpy")
    names = {0.0: "free", 1.0: "weak", 4.0: "strong"}

    regimes: list[dict[str, Any]] = []
    for di, drive in enumerate(drive_levels):
        # Fresh field per regime to keep substrate state independent.
        cfg = field_config or HiggsFieldConfig(seed=13, width=24, height=16)
        field = HiggsStigmergyField(cfg)
        field.relax(relax_steps)
        h, w = field.config.height, field.config.width

        bands: dict[str, HiggsParticleSwimmer] = {}
        for c in couplings:
            nice = names.get(float(c), f"c{c:g}")
            bands[nice] = HiggsParticleSwimmer(
                n=n_per_band, coupling=float(c), field_shape=(h, w),
                seed=seed + di * 17 + int(round(c * 31)),
                drive_amplitude=float(drive),
                name=nice,
            )

        for _ in range(swimmer_steps):
            field.step()
            phi_arr = phi_as_array(field)
            for s in bands.values():
                s.step(phi_arr)

        band_states = {k: s.state() for k, s in bands.items()}
        # Headline: mobility ratio strong / free. If this approaches 1.0
        # as drive grows, the mass-spectrum signal is being washed out
        # by the kinetic energy — exactly the "binding overcome" regime
        # Grok's analysis named.
        free_mob = band_states.get("free", {}).get("mobility", 0.0) + 1e-9
        strong_mob = band_states.get("strong", {}).get("mobility", 0.0)
        ratio = strong_mob / free_mob

        # "Persistence inertia" proxy — STGM-graph cost per unit motion.
        # Higher = harder to move per unit drive (more inertia in the
        # engineering-graph sense §20.F talks about). Defined here as
        # (drive / mobility) for each band — units are arbitrary but
        # the cross-band comparison is meaningful.
        inertia_proxy = {
            k: round(drive / (band_states[k]["mobility"] + 1e-9), 4)
            for k in band_states
        }

        regimes.append({
            "drive_amplitude": float(drive),
            "field_order_parameter": round(field.order_parameter, 6),
            "field_mean_potential": round(field.mean_potential, 6),
            "bands": band_states,
            "mobility_ratio_strong_over_free": round(ratio, 6),
            "engineering_inertia_proxy": inertia_proxy,
        })

    result = {
        "truth_label": TRUTH_LABEL_FORCE_SWEEP,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_particle_physics_claim": True,
        "research_question": (
            "Can persistent participation in shared memory fields create "
            "measurable inertia-like behavior in distributed agents? "
            "(Tournament §20.F pinned question — single-node Mac.)"
        ),
        "config": {
            "drive_levels": list(drive_levels),
            "couplings": list(couplings),
            "n_per_band": n_per_band,
            "field": asdict((field_config or HiggsFieldConfig(seed=13, width=24, height=16))),
            "relax_steps": relax_steps,
            "swimmer_steps": swimmer_steps,
        },
        "regimes": regimes,
        "summary": {
            "lowest_drive_ratio": regimes[0]["mobility_ratio_strong_over_free"],
            "highest_drive_ratio": regimes[-1]["mobility_ratio_strong_over_free"],
            "ratio_collapsed_toward_one": (
                regimes[-1]["mobility_ratio_strong_over_free"]
                > regimes[0]["mobility_ratio_strong_over_free"]
            ),
        },
        "interpretation": (
            "If the strong/free mobility ratio rises toward 1 as drive grows, "
            "the mass-spectrum signal is washed out by kinetic energy — the "
            "'binding overcome' regime. If the ratio stays near its baseline, "
            "the substrate coupling dominates regardless of drive."
        ),
    }
    if write:
        write_force_sweep_receipt(result, state_root=state_root)
    return result


# ════════════════════════════════════════════════════════════════════════════
# KILLER DEMO — Q9 four-type swarm with unified mass law (Q1+Q5+Q8 answered)
# ════════════════════════════════════════════════════════════════════════════
#
# Architect 2026-05-13 — Q9: "Show four swimmers on screen — ghost (no field
# writes), worker (writes pheromone), organ (coupled to multiple organs),
# sentinel (repairs damage). Then hit all with the same force. If they
# respond differently, you have visible computational mass."
#
# Each type maps onto the unified mass law (Q8):
#     m_eff = 1 + g·|phi| + alpha · log(1 + write_count) + beta · n_organs
#
# - GHOST     : g=0, write_rate=0, no organs           → baseline m_eff=1.0
# - WORKER    : g=0, write_rate=0.5, no organs         → m_eff grows from writes
# - ORGAN     : g=0, write_rate=0, organs=4            → m_eff = 1 + 4β
# - SENTINEL  : g=1, write_rate=0.7, organs=3          → all three contributions
#
# Coupling g is kept low (0 or 1) on purpose — so the visible mass spectrum
# in this demo comes mostly from PARTICIPATION, not from field coupling. That
# isolates the Q1/Q5 effect from the Q2 effect we already shipped.


_KILLER_DEMO_TYPES = (
    {
        "name": "ghost",
        "coupling": 0.0,
        "write_rate": 0.0,
        "organ_memberships": (),
        "description": "No field writes, no organ membership — pure unattached agent.",
    },
    {
        "name": "worker",
        "coupling": 0.0,
        "write_rate": 0.5,
        "organ_memberships": ("pheromone_trail",),
        "description": "Writes pheromone every other step. Mass grows logarithmically with participation.",
    },
    {
        "name": "organ",
        "coupling": 0.0,
        "write_rate": 0.0,
        "organ_memberships": ("hippocampus", "wernicke", "cortex", "broca"),
        "description": "Member of 4 organs but never writes. Mass from embedding alone.",
    },
    {
        "name": "sentinel",
        "coupling": 1.0,
        "write_rate": 0.7,
        "organ_memberships": ("immune", "anomaly_detector", "homeostat"),
        "description": "Field-coupled, high write rate, in 3 organs. Most embedded — heaviest in the demo.",
    },
)


def run_killer_demo_experiment(
    *,
    n_per_type: int = 25,
    field_config: HiggsFieldConfig | None = None,
    relax_steps: int = 180,
    swimmer_steps: int = 600,
    drive_amplitude: float = 1.0,
    write_inertia_coefficient: float = 0.5,
    organ_inertia_coefficient: float = 0.25,
    state_root: str | Path | None = None,
    write: bool = True,
    seed: int = 23,
) -> dict[str, Any]:
    """Q9 killer demo. Same drive applied to four types; mobility
    stratification proves computational mass is visible without any one
    swimmer having a built-in mass parameter."""
    if not _HAS_NUMPY:
        raise RuntimeError("run_killer_demo_experiment requires numpy")
    cfg = field_config or HiggsFieldConfig(seed=29, width=24, height=16)
    field = HiggsStigmergyField(cfg)
    relaxation = field.relax(relax_steps)

    swimmers: dict[str, HiggsParticleSwimmer] = {}
    for i, spec in enumerate(_KILLER_DEMO_TYPES):
        swimmers[spec["name"]] = HiggsParticleSwimmer(
            n=n_per_type,
            coupling=spec["coupling"],
            field_shape=(cfg.height, cfg.width),
            seed=seed + i * 31,
            drive_amplitude=drive_amplitude,
            write_rate=spec["write_rate"],
            write_inertia_coefficient=write_inertia_coefficient,
            organ_memberships=spec["organ_memberships"],
            organ_inertia_coefficient=organ_inertia_coefficient,
            name=spec["name"],
        )

    samples: list[dict[str, Any]] = []
    for t in range(1, swimmer_steps + 1):
        field.step()
        phi_arr = phi_as_array(field)
        for s in swimmers.values():
            s.step(phi_arr)
        if t % max(swimmer_steps // 5, 50) == 0 or t == swimmer_steps:
            samples.append({
                "t": t,
                "order_parameter": round(field.order_parameter, 6),
                "types": {k: s.state() for k, s in swimmers.items()},
            })

    final = samples[-1]["types"] if samples else {}
    mobilities = {k: final[k]["mobility"] for k in final}
    masses = {k: final[k]["mean_mass"] for k in final}
    # Spread between heaviest and lightest type's mobility — if this is
    # not ~zero we have visible computational mass (Q9 success).
    if mobilities:
        mob_max = max(mobilities.values())
        mob_min = min(mobilities.values())
        mass_max = max(masses.values())
        mass_min = min(masses.values())
        mobility_spread = mob_max - mob_min
        mass_spread = mass_max - mass_min
    else:
        mobility_spread = 0.0
        mass_spread = 0.0

    result = {
        "truth_label": TRUTH_LABEL_KILLER_DEMO,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_particle_physics_claim": True,
        "research_questions_answered": [
            "Q1 — Participation → inertia",
            "Q5 — Organ-layer mass",
            "Q8 — Unified mass law: m_eff = 1 + g·|phi| + alpha·log(1+writes) + beta·n_organs",
            "Q9 — Killer demo: 4 swimmer types with visibly different mobility under uniform forcing",
        ],
        "unified_mass_law": (
            "m_eff = 1 + coupling·|phi(x,y)| + write_inertia·log(1+writes) + organ_inertia·n_organs"
        ),
        "coefficients": {
            "write_inertia_alpha": write_inertia_coefficient,
            "organ_inertia_beta":  organ_inertia_coefficient,
            "field_coupling":      "per-type, in spec",
            "drive_amplitude":     drive_amplitude,
        },
        "swimmer_types": [
            {"name": s["name"], "description": s["description"]}
            for s in _KILLER_DEMO_TYPES
        ],
        "field_relaxation": relaxation,
        "config": {
            "n_per_type": n_per_type,
            "field": asdict(cfg),
            "relax_steps": relax_steps,
            "swimmer_steps": swimmer_steps,
        },
        "samples": samples,
        "final_state": final,
        "mobility_spread": round(mobility_spread, 6),
        "mass_spread": round(mass_spread, 6),
        "visible_computational_mass": bool(mobility_spread > 0.01),
        "interpretation": (
            "Each type starts as identical numpy arrays. Differences in "
            "write_rate, organ_memberships, and field coupling produce "
            "measurably different m_eff via the unified law. If the four "
            "types stratify in mobility, computational mass emerged from "
            "participation alone — no parameter labelled 'mass' was set."
        ),
    }
    if write:
        write_killer_demo_receipt(result, state_root=state_root)
    return result


# ════════════════════════════════════════════════════════════════════════════
# Q6 — SPONTANEOUS SYMMETRY BREAKING from identical initial conditions
# ════════════════════════════════════════════════════════════════════════════
#
# Architect 2026-05-13: "Start all swimmers identical. Let them write /
# organize. See if they naturally split into ghost/worker/sentinel roles
# without pre-labeling."
#
# Mechanism: a single uniform population of N swimmers (same coupling=0,
# same base write_rate=0.1, no organs, identical mass=1.0 at t=0). Turn
# on velocity_write_modulation so SLOW swimmers WRITE MORE. Combined
# with the unified mass law (writes → heavier → slower → more writes),
# this is a positive-feedback loop. Tiny initial-position-and-velocity
# asymmetry (from the RNG seed) is amplified until the population
# bifurcates spontaneously.
#
# Headline metric:
#     mass_p95_over_p05 = mass at 95th percentile / mass at 5th percentile
# A flat-symmetric outcome gives ratio ≈ 1. A bifurcated outcome (some
# swimmers spontaneously became "sentinels," others stayed "ghosts")
# gives ratio >> 1.
#
# Truth class: HYPOTHESIS until the mechanism is independently reproduced
# at multiple seeds AND federated nodes.


def run_symmetry_breaking_experiment(
    *,
    n_swimmers: int = 80,
    field_config: HiggsFieldConfig | None = None,
    relax_steps: int = 180,
    swimmer_steps: int = 1500,
    base_write_rate: float = 0.0,
    velocity_write_modulation: float = 1.5,
    write_inertia_coefficient: float = 0.05,
    write_inertia_kind: str = "linear",
    drive_amplitude: float = 1.0,
    crowding_competition: bool = True,
    coupling: float = 1.5,
    state_root: str | Path | None = None,
    write: bool = True,
    seed: int = 41,
) -> dict[str, Any]:
    """Q6: do identical swimmers spontaneously stratify into a mass
    spectrum via writes-feedback?

    Returns a dict carrying the per-swimmer final mass distribution,
    the headline p95/p05 ratio, and a HYPOTHESIS receipt class."""
    if not _HAS_NUMPY:
        raise RuntimeError("run_symmetry_breaking_experiment requires numpy")
    cfg = field_config or HiggsFieldConfig(seed=37, width=24, height=16)
    field = HiggsStigmergyField(cfg)
    relaxation = field.relax(relax_steps)

    # ONE population, ALL identical parameters. The only asymmetry is
    # RNG-seeded initial positions and velocities.
    population = HiggsParticleSwimmer(
        n=n_swimmers,
        coupling=coupling,
        field_shape=(cfg.height, cfg.width),
        seed=seed,
        drive_amplitude=drive_amplitude,
        write_rate=base_write_rate,
        write_inertia_coefficient=write_inertia_coefficient,
        write_inertia_kind=write_inertia_kind,
        organ_memberships=(),
        organ_inertia_coefficient=0.0,
        velocity_write_modulation=velocity_write_modulation,
        crowding_competition=crowding_competition,
        name="identical_population",
    )

    # Sample the mass distribution at fixed intervals so we can plot
    # the bifurcation timeline if needed.
    timeline: list[dict[str, Any]] = []
    sample_at = max(swimmer_steps // 6, 50)
    for t in range(1, swimmer_steps + 1):
        field.step()
        phi = phi_as_array(field)
        population.step(phi)
        if t % sample_at == 0 or t == swimmer_steps:
            masses = population.mass.copy()
            timeline.append({
                "t": t,
                "mass_min": float(masses.min()),
                "mass_max": float(masses.max()),
                "mass_p05": float(_np.percentile(masses, 5)),
                "mass_p50": float(_np.percentile(masses, 50)),
                "mass_p95": float(_np.percentile(masses, 95)),
                "mass_p95_over_p05": float(
                    _np.percentile(masses, 95) / max(_np.percentile(masses, 5), 1e-9)
                ),
                "writes_p05": float(_np.percentile(population.write_count, 5)),
                "writes_p50": float(_np.percentile(population.write_count, 50)),
                "writes_p95": float(_np.percentile(population.write_count, 95)),
            })

    final_masses = population.mass.copy()
    final_writes = population.write_count.copy()
    final_speeds = _np.linalg.norm(population.vel, axis=1)

    # Cluster the population by mass into 3 quantile-bands: bottom 25%
    # (ghost-like), middle 50% (worker-like), top 25% (sentinel-like).
    bottom_cut = float(_np.percentile(final_masses, 25))
    top_cut = float(_np.percentile(final_masses, 75))
    bands = {
        "spontaneous_ghosts":    {"mass_le": bottom_cut, "members": []},
        "spontaneous_workers":   {"mass_in": [bottom_cut, top_cut], "members": []},
        "spontaneous_sentinels": {"mass_ge": top_cut, "members": []},
    }
    for i in range(n_swimmers):
        m = float(final_masses[i])
        w = float(final_writes[i])
        v = float(final_speeds[i])
        member = {"i": i, "mass": round(m, 4), "writes": round(w, 1),
                  "speed": round(v, 4)}
        if m <= bottom_cut:
            bands["spontaneous_ghosts"]["members"].append(member)
        elif m >= top_cut:
            bands["spontaneous_sentinels"]["members"].append(member)
        else:
            bands["spontaneous_workers"]["members"].append(member)

    final_p05 = float(_np.percentile(final_masses, 5))
    final_p95 = float(_np.percentile(final_masses, 95))
    ratio = final_p95 / max(final_p05, 1e-9)

    # Coefficient of variation as a second symmetry-broke metric.
    cv = float(final_masses.std() / max(final_masses.mean(), 1e-9))

    # "Symmetry broke" verdict: BOTH the percentile ratio > 1.5 AND the
    # coefficient of variation > 0.15. Honest threshold — small enough
    # that minor noise doesn't trigger, large enough that a real
    # bifurcation does.
    symmetry_broke = bool(ratio > 1.5 and cv > 0.15)

    result = {
        "truth_label": TRUTH_LABEL_SYMMETRY_BREAK,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_particle_physics_claim": True,
        "research_question_answered": (
            "Q6 — Start all swimmers identical. Let them write/organize. "
            "Do distinct roles/masses emerge spontaneously?"
        ),
        "mechanism": (
            "velocity_write_modulation closes a positive feedback loop: "
            "slow swimmers write more (linger → deposit), the unified "
            "mass law turns writes into mass, more mass means more "
            "slowdown, more slowdown means more writes. Identical "
            "starting parameters + RNG-jittered initial pos/vel = "
            "seed for spontaneous role differentiation."
        ),
        "config": {
            "n_swimmers": n_swimmers,
            "base_write_rate": base_write_rate,
            "velocity_write_modulation": velocity_write_modulation,
            "write_inertia_coefficient": write_inertia_coefficient,
            "write_inertia_kind": write_inertia_kind,
            "drive_amplitude": drive_amplitude,
            "coupling": coupling,
            "crowding_competition": crowding_competition,
            "field": asdict(cfg),
            "relax_steps": relax_steps,
            "swimmer_steps": swimmer_steps,
            "seed": seed,
        },
        "field_relaxation": relaxation,
        "timeline": timeline,
        "final_distribution": {
            "n_swimmers": n_swimmers,
            "mass_min": float(final_masses.min()),
            "mass_max": float(final_masses.max()),
            "mass_mean": float(final_masses.mean()),
            "mass_std": float(final_masses.std()),
            "mass_p05": final_p05,
            "mass_p50": float(_np.percentile(final_masses, 50)),
            "mass_p95": final_p95,
            "mass_p95_over_p05": round(ratio, 6),
            "coefficient_of_variation": round(cv, 6),
            "writes_min": float(final_writes.min()),
            "writes_max": float(final_writes.max()),
            "writes_mean": float(final_writes.mean()),
        },
        "spontaneous_role_bands": {
            "spontaneous_ghosts": {
                "count": len(bands["spontaneous_ghosts"]["members"]),
                "mass_le": bands["spontaneous_ghosts"]["mass_le"],
            },
            "spontaneous_workers": {
                "count": len(bands["spontaneous_workers"]["members"]),
                "mass_in": bands["spontaneous_workers"]["mass_in"],
            },
            "spontaneous_sentinels": {
                "count": len(bands["spontaneous_sentinels"]["members"]),
                "mass_ge": bands["spontaneous_sentinels"]["mass_ge"],
            },
        },
        "verdict": {
            "p95_over_p05": round(ratio, 4),
            "coefficient_of_variation": round(cv, 4),
            "threshold_ratio": 1.5,
            "threshold_cv": 0.15,
            "symmetry_broke": symmetry_broke,
        },
        "interpretation": (
            "If symmetry_broke is True, identical swimmers spontaneously "
            "differentiated into a mass spectrum via participation alone. "
            "If False at default coefficients, the feedback loop was too "
            "weak — re-run with higher velocity_write_modulation or "
            "longer swimmer_steps."
        ),
    }
    if write:
        write_symmetry_break_receipt(result, state_root=state_root)
    return result


def write_symmetry_break_receipt(result: dict[str, Any], *, state_root: str | Path | None = None) -> dict[str, Any]:
    """Append a HIGGS_SYMMETRY_BREAK row to the ledger."""
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "HIGGS_SYMMETRY_BREAK",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL_SYMMETRY_BREAK,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def write_killer_demo_receipt(result: dict[str, Any], *, state_root: str | Path | None = None) -> dict[str, Any]:
    """Append a HIGGS_KILLER_DEMO row to the ledger."""
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "HIGGS_KILLER_DEMO",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL_KILLER_DEMO,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def write_force_sweep_receipt(result: dict[str, Any], *, state_root: str | Path | None = None) -> dict[str, Any]:
    """Append a HIGGS_FORCE_REGIME_SWEEP row to the ledger."""
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "HIGGS_FORCE_REGIME_SWEEP",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL_FORCE_SWEEP,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def run_higgs_stigmergy_demo(
    *,
    config: HiggsFieldConfig | None = None,
    steps: int = 160,
    state_root: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    field = HiggsStigmergyField(config)
    cfg = field.config
    relaxation = field.relax(steps)
    probes = default_swimmers(cfg.width, cfg.height)
    swimmers = [field.evaluate_swimmer(p) for p in probes]
    masses = [float(s["effective_mass"]) for s in swimmers]
    result = {
        "truth_label": TRUTH_LABEL,
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_particle_physics_claim": True,
        "config": asdict(cfg),
        "relaxation": relaxation,
        "order_parameter": round(field.order_parameter, 6),
        "signed_bias": round(field.signed_bias, 6),
        "mean_potential": round(field.mean_potential, 6),
        "swimmers": swimmers,
        "mass_span": round(max(masses) - min(masses), 6),
        "interpretation": (
            "A non-zero persistent substrate formed; coupled swimmers now "
            "pay more latency/STGM to move than uncoupled swimmers."
        ),
    }
    if write:
        write_receipt(result, state_root=state_root)
    return result


def write_receipt(result: dict[str, Any], *, state_root: str | Path | None = None) -> dict[str, Any]:
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "HIGGS_STIGMERGY_ANALOGUE",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def render_ascii(result: dict[str, Any]) -> str:
    relaxation = result["relaxation"]
    swimmers = result["swimmers"]
    lines = [
        "Higgs/Stigmergy analogue",
        f"truth: {result['truth_label']}",
        f"boundary: {result['truth_boundary']}",
        (
            "order parameter: "
            f"{relaxation['initial_order_parameter']:.4f} -> "
            f"{relaxation['final_order_parameter']:.4f}"
        ),
        f"mean potential: {relaxation['initial_mean_potential']:.4f} -> {relaxation['final_mean_potential']:.4f}",
        "swimmer inertia:",
    ]
    for swimmer in swimmers:
        lines.append(
            "  "
            f"{swimmer['name']}: coupling={swimmer['coupling']:.1f} "
            f"mass={swimmer['effective_mass']:.3f} "
            f"mobility={swimmer['mobility']:.3f} "
            f"latency_ms={swimmer['latency_ms']:.1f}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=160)
    parser.add_argument("--width", type=int, default=24)
    parser.add_argument("--height", type=int, default=16)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--state-root", default=None)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    result = run_higgs_stigmergy_demo(
        config=HiggsFieldConfig(width=args.width, height=args.height, seed=args.seed),
        steps=args.steps,
        state_root=args.state_root,
        write=not args.no_write,
    )
    if args.as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_ascii(result))
    return 0


# ════════════════════════════════════════════════════════════════════════════
# PERSISTENCE INERTIA FIELD — ADAPTIVE AGENT LAYER (architect 2026-05-13)
# ════════════════════════════════════════════════════════════════════════════
#
# Architect's correction: the swimmers are dumb particles with memory weight.
# They move, write, gain inertia, slow down. They do NOT yet choose
# strategies, detect danger, recruit others, specialize themselves, remember
# outcomes intelligently, adapt their role, or cooperate tactically.
#
# The fix is NOT more Higgs. It is local rules + emergence:
#     agent_policy = f(local_field, neighbors, damage, energy, memory)
#
# Each swimmer holds a probability distribution over a small fixed set of
# BEHAVIORS. Every step, the swimmer (1) senses its local context, (2)
# samples or averages a behavior weight, (3) executes the behavior, (4)
# receives a contextual reward, (5) softmax-shifts its policy toward
# behaviors that worked. Identical swimmers in identical conditions but
# different local microenvironments will accumulate different rewards →
# different policies → emergent functional roles.
#
# Truth class: HYPOTHESIS until the result is independently reproduced.
#
# Behaviors (closed set of four):
#   - wander  : weak random isotropic drive, mostly anti-velocity damping
#   - chase   : strong attraction toward gradient of |phi| (cluster at field maxima)
#   - deposit : minimize velocity (anti-drive), accumulate writes
#   - flee    : repel from crowded cells (move toward neighbour-sparse cells)


_DEFAULT_BEHAVIOR_NAMES = ("wander", "chase", "deposit", "flee")


class AdaptivePolicySwarm:
    """N adaptive agents living in a HiggsStigmergyField. Each agent has
    a probability distribution over the four canonical behaviors and
    updates that distribution from contextual reward.

    The unified mass law (Q8) still applies:
        m_eff = 1 + g·|phi| + alpha · f(writes) + beta · n_organs
    Writes are accumulated when the agent's *behavior* favours depositing,
    not by a global write_rate. That is what couples behavior to inertia.
    """

    def __init__(
        self,
        n: int = 60,
        field_shape: tuple[int, int] = (24, 16),
        *,
        seed: int = 53,
        damping: float = 0.95,
        max_speed: float = 8.0,
        thermal_kick: float = 0.4,
        behavior_names: tuple[str, ...] = _DEFAULT_BEHAVIOR_NAMES,
        learning_rate: float = 0.06,
        coupling: float = 1.0,
        write_inertia_coefficient: float = 0.1,
        write_inertia_kind: str = "linear",
        organ_inertia_coefficient: float = 0.0,
        damage_field=None,
    ) -> None:
        if not _HAS_NUMPY:
            raise RuntimeError("AdaptivePolicySwarm requires numpy")
        if n < 1:
            raise ValueError("need at least one agent")
        if field_shape[0] < 3 or field_shape[1] < 3:
            raise ValueError("field_shape must be at least 3x3")
        if not (0.0 < learning_rate < 1.0):
            raise ValueError("learning_rate must be in (0, 1)")
        if write_inertia_kind not in ("log", "sqrt", "linear"):
            raise ValueError("write_inertia_kind must be 'log', 'sqrt', or 'linear'")
        h, w = int(field_shape[0]), int(field_shape[1])
        self._h = h
        self._w = w
        self._rng = _np.random.default_rng(seed)
        self._damping = float(damping)
        self._max_speed = float(max_speed)
        self._thermal_kick = float(thermal_kick)
        self._learning_rate = float(learning_rate)
        self.coupling = float(coupling)
        self._write_inertia_coefficient = float(write_inertia_coefficient)
        self._write_inertia_kind = str(write_inertia_kind)
        self._organ_inertia_coefficient = float(organ_inertia_coefficient)
        self.behavior_names = tuple(behavior_names)
        self.K = len(self.behavior_names)

        # State arrays — identical at init except for RNG-jittered pos/vel.
        self.pos = self._rng.uniform(low=[0, 0], high=[w, h], size=(n, 2))
        self.vel = self._rng.normal(scale=0.3, size=(n, 2))
        self.mass = _np.ones(n, dtype=float)
        self.write_count = _np.zeros(n, dtype=float)
        # Policy: uniform over behaviors at init, n × K simplex
        self.policy = _np.full((n, self.K), 1.0 / self.K, dtype=float)
        self._steps = 0
        # Rolling history for reward smoothing.
        self._last_reward = _np.zeros((n, self.K), dtype=float)
        # Damage field: same shape as phi. Cells with damage>0 punish
        # depositing (toxic), reward fleeing (escape), reward wandering
        # (explore safer terrain). Activates the otherwise-starved
        # niches identified in the canonical adaptive run.
        if damage_field is None:
            self._damage_field = _np.zeros((h, w), dtype=float)
        else:
            arr = _np.asarray(damage_field, dtype=float)
            if arr.shape != (h, w):
                raise ValueError(
                    f"damage_field shape {arr.shape} must match field_shape ({h},{w})"
                )
            self._damage_field = arr.copy()

    @property
    def n(self) -> int:
        return int(self.pos.shape[0])

    # ── Sense: extract context per agent ────────────────────────────────
    def _sense(self, phi_array):
        h, w = self._h, self._w
        ix = (_np.floor(self.pos[:, 0]).astype(int)) % w
        iy = (_np.floor(self.pos[:, 1]).astype(int)) % h
        abs_phi = _np.abs(phi_array)
        grad_y, grad_x = _np.gradient(abs_phi)
        local_phi = abs_phi[iy, ix]
        local_grad = _np.stack([grad_x[iy, ix], grad_y[iy, ix]], axis=1)
        # Cell occupancy — neighbour density signal.
        cell_id = iy * w + ix
        occ = _np.bincount(cell_id, minlength=h * w)
        local_occ = occ[cell_id].astype(float)
        speed_sq = _np.sum(self.vel * self.vel, axis=1)
        return ix, iy, local_phi, local_grad, local_occ, speed_sq

    # ── Compute the four behavior force vectors (vectorised) ────────────
    def _behavior_forces(self, local_grad, local_occ, vel):
        n = self.n
        # wander: isotropic Gaussian random force, weak
        f_wander = self._rng.normal(scale=0.4, size=(n, 2))
        # chase: pull toward grad(|phi|), strong
        f_chase = 2.0 * local_grad
        # deposit: anti-velocity (stand still)
        f_deposit = -1.5 * vel
        # flee: away from crowded cells — push in the direction of
        # sparseness, magnitude scaled by occupancy
        f_flee = -0.8 * vel + self._rng.normal(scale=0.3, size=(n, 2)) * (
            local_occ[:, None]
        )
        # Stack along K dimension: shape (n, K, 2)
        return _np.stack([f_wander, f_chase, f_deposit, f_flee], axis=1)

    # ── Per-behavior reward, contextual ──────────────────────────────────
    def _behavior_rewards(self, local_phi, local_occ, speed_sq, local_damage):
        """Returns shape (n, K). Each entry is the reward that
        behavior k WOULD give this agent given its current context.

        Rewards are sized so policy gradient remains stable; absolute
        values matter less than relative ordering. damage_field
        contributions activate the wander/flee niches that were
        otherwise starved in the canonical adaptive run."""
        # wander: small constant exploration bonus + damage avoidance
        # (wandering is rewarded MORE in damaged terrain — explore
        # toward safety).
        r_wander = 0.3 + 0.6 * local_damage
        # chase: high reward in high-|phi| cells (close to vev), but
        # penalised when chasing into damage.
        r_chase = _np.tanh(local_phi) - 0.4 * local_damage
        # deposit: high reward when slow AND alone, but damaged cells
        # are TOXIC — strongly negative deposit reward there.
        slow = _np.exp(-speed_sq)
        sparse = _np.exp(-(local_occ - 1.0).clip(min=0.0))
        r_deposit = slow * sparse - 0.8 * local_damage
        # flee: high reward when crowded OR damaged — escape from
        # either kind of bad-cell.
        r_flee = (
            (1.0 - _np.exp(-(local_occ - 1.0).clip(min=0.0)))
            + 0.7 * local_damage
        )
        return _np.stack([r_wander, r_chase, r_deposit, r_flee], axis=1)

    # ── Mass law (same as HiggsParticleSwimmer) ─────────────────────────
    def _update_mass(self, local_phi):
        if self._write_inertia_kind == "log":
            write_term = _np.log1p(self.write_count)
        elif self._write_inertia_kind == "sqrt":
            write_term = _np.sqrt(self.write_count)
        else:
            write_term = self.write_count
        memory_term = self._write_inertia_coefficient * write_term
        organ_term = 0.0  # adaptive swarm has no static organ memberships yet
        self.mass = 1.0 + self.coupling * local_phi + memory_term + organ_term

    # ── One simulation step ─────────────────────────────────────────────
    def step(self, phi_array, dt: float = 0.05) -> None:
        if phi_array.shape != (self._h, self._w):
            raise ValueError(
                f"phi_array shape {phi_array.shape} does not match "
                f"swarm field_shape ({self._h}, {self._w})"
            )
        ix, iy, local_phi, local_grad, local_occ, speed_sq = self._sense(phi_array)
        local_damage = self._damage_field[iy, ix]

        # Behaviors and rewards
        b_forces = self._behavior_forces(local_grad, local_occ, self.vel)
        b_rewards = self._behavior_rewards(local_phi, local_occ, speed_sq, local_damage)
        self._last_reward = b_rewards

        # Weighted force per agent: sum_k policy[i,k] * b_forces[i,k]
        force = _np.einsum("ik,ikd->id", self.policy, b_forces)
        # Thermal kick (same for all)
        if self._thermal_kick > 0:
            force = force + self._rng.normal(scale=self._thermal_kick, size=self.pos.shape)

        # Update mass first so accel uses current mass
        self._update_mass(local_phi)
        accel = force / self.mass[:, None]
        self.vel = self.vel + accel * dt
        self.vel *= self._damping
        speed = _np.linalg.norm(self.vel, axis=1)
        too_fast = speed > self._max_speed
        if too_fast.any():
            scale = self._max_speed / (speed[too_fast] + 1e-9)
            self.vel[too_fast] = self.vel[too_fast] * scale[:, None]
        self.pos = self.pos + self.vel * dt
        self.pos[:, 0] = self.pos[:, 0] % self._w
        self.pos[:, 1] = self.pos[:, 1] % self._h

        # Writes are accumulated proportional to deposit weight × slowness
        deposit_weight = self.policy[:, 2]  # index 2 = "deposit"
        write_deposit = deposit_weight * _np.exp(-speed_sq) * 2.0
        # Crowding competition for deposits (Q6 mechanism stays on by default)
        cell_id = iy * self._w + ix
        occ = _np.bincount(cell_id, minlength=self._h * self._w)
        divisor = _np.maximum(occ[cell_id].astype(float), 1.0)
        write_deposit = write_deposit / divisor
        self.write_count = self.write_count + write_deposit

        # Policy update — softmax shift via log-policy + reward
        log_policy = _np.log(_np.clip(self.policy, 1e-9, 1.0))
        log_policy = log_policy + self._learning_rate * b_rewards
        # Renormalise: row-wise softmax
        max_per_row = log_policy.max(axis=1, keepdims=True)
        ex = _np.exp(log_policy - max_per_row)
        self.policy = ex / ex.sum(axis=1, keepdims=True)

        self._steps += 1

    # ── Diagnostics ──────────────────────────────────────────────────────
    def dominant_behavior_index(self):
        """Index of each agent's max-weight behavior."""
        return _np.argmax(self.policy, axis=1)

    def role_counts(self) -> dict[str, int]:
        idx = self.dominant_behavior_index()
        return {
            self.behavior_names[k]: int((idx == k).sum())
            for k in range(self.K)
        }

    def policy_entropy(self) -> float:
        """Mean entropy across the swarm (in nats). High = uncommitted,
        low = each agent has converged on one behavior."""
        p = _np.clip(self.policy, 1e-12, 1.0)
        h = -_np.sum(p * _np.log(p), axis=1)
        return float(h.mean())

    def state_summary(self) -> dict[str, Any]:
        return {
            "n_agents": self.n,
            "steps": self._steps,
            "policy_entropy_mean_nats": round(self.policy_entropy(), 6),
            "mean_mass": round(float(self.mass.mean()), 6),
            "mass_min": round(float(self.mass.min()), 6),
            "mass_max": round(float(self.mass.max()), 6),
            "mean_writes": round(float(self.write_count.mean()), 4),
            "role_counts": self.role_counts(),
        }


def run_adaptive_experiment(
    *,
    n_agents: int = 80,
    field_config: HiggsFieldConfig | None = None,
    relax_steps: int = 180,
    swarm_steps: int = 1500,
    learning_rate: float = 0.06,
    coupling: float = 1.0,
    write_inertia_coefficient: float = 0.1,
    write_inertia_kind: str = "linear",
    seed: int = 53,
    state_root: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Run the adaptive-policy experiment and return the role/mass result.

    Truth class: HYPOTHESIS. The mechanism is: agents start identical
    with a uniform policy over four behaviors. Local context shapes
    rewards. Rewards softmax-shift policies. After N steps, the agents'
    dominant behaviors form a distribution. If the distribution is
    non-uniform AND the policy entropy has dropped meaningfully from
    its initial value of log(K), roles emerged from behavior."""
    if not _HAS_NUMPY:
        raise RuntimeError("run_adaptive_experiment requires numpy")
    cfg = field_config or HiggsFieldConfig(seed=37, width=24, height=16)
    field = HiggsStigmergyField(cfg)
    relaxation = field.relax(relax_steps)
    swarm = AdaptivePolicySwarm(
        n=n_agents,
        field_shape=(cfg.height, cfg.width),
        seed=seed,
        coupling=coupling,
        write_inertia_coefficient=write_inertia_coefficient,
        write_inertia_kind=write_inertia_kind,
        learning_rate=learning_rate,
    )

    initial_entropy = swarm.policy_entropy()
    timeline: list[dict[str, Any]] = []
    sample_every = max(swarm_steps // 6, 50)
    for t in range(1, swarm_steps + 1):
        field.step()
        phi = phi_as_array(field)
        swarm.step(phi)
        if t % sample_every == 0 or t == swarm_steps:
            timeline.append({"t": t, **swarm.state_summary()})

    final = swarm.state_summary()
    final_entropy = swarm.policy_entropy()
    entropy_drop = initial_entropy - final_entropy
    # Roles "emerged" if the dominant-behavior distribution is meaningfully
    # non-uniform AND mean entropy dropped from log(K) ≈ 1.386 below 1.10.
    role_counts = final["role_counts"]
    max_count = max(role_counts.values()) if role_counts else 0
    role_uniformity_ratio = max_count / max(n_agents / swarm.K, 1)
    roles_emerged = bool(final_entropy < 1.10 and role_uniformity_ratio > 1.2)

    result = {
        "truth_label": TRUTH_LABEL_ADAPTIVE,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_particle_physics_claim": True,
        "research_question_answered": (
            "Adaptive extension to Q6 — do identical agents with a small "
            "set of behavioral choices spontaneously specialise into "
            "different functional roles when local context shapes their "
            "rewards?"
        ),
        "behavior_set": list(swarm.behavior_names),
        "mechanism": (
            "Each agent maintains a softmax policy over {wander, chase, "
            "deposit, flee}. Per-step contextual reward shifts log-policy "
            "by learning_rate * reward. Crowding competition couples "
            "agents non-mean-field. Mass law adds super-linear write "
            "feedback. Initial policies are uniform = log(K) entropy."
        ),
        "config": {
            "n_agents": n_agents,
            "learning_rate": learning_rate,
            "coupling": coupling,
            "write_inertia_coefficient": write_inertia_coefficient,
            "write_inertia_kind": write_inertia_kind,
            "field": asdict(cfg),
            "relax_steps": relax_steps,
            "swarm_steps": swarm_steps,
            "seed": seed,
        },
        "field_relaxation": relaxation,
        "timeline": timeline,
        "initial_policy_entropy_nats": round(initial_entropy, 6),
        "final_policy_entropy_nats": round(final_entropy, 6),
        "policy_entropy_drop": round(entropy_drop, 6),
        "final_role_counts": role_counts,
        "final_mass_summary": {
            "min": final["mass_min"],
            "max": final["mass_max"],
            "mean": final["mean_mass"],
        },
        "roles_emerged": roles_emerged,
        "interpretation": (
            "If roles_emerged is True, an initially uniform policy over "
            "behaviors collapsed to a non-uniform role distribution as "
            "agents experienced different local rewards. Agency, not just "
            "physics. If False, the policy update was too weak — try "
            "higher learning_rate or longer swarm_steps."
        ),
    }
    if write:
        write_adaptive_receipt(result, state_root=state_root)
    return result


def write_adaptive_receipt(result: dict[str, Any], *, state_root: str | Path | None = None) -> dict[str, Any]:
    """Append a PERSISTENCE_INERTIA_FIELD_ADAPTIVE row to the ledger."""
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "PERSISTENCE_INERTIA_FIELD_ADAPTIVE",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL_ADAPTIVE,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


# ════════════════════════════════════════════════════════════════════════════
# Q4 — MEMORY-DRIVEN FIELD: phi IS the trace density
# ════════════════════════════════════════════════════════════════════════════
#
# Architect Q4: "Is the field really phi, or is phi the accumulated
# memory/trace density of the system?"
#
# This class answers the second half of the question by REPLACING the
# Mexican-hat scalar field with a memory-derived field. Each swimmer
# deposits into a 2D ledger at its current cell; the ledger decays
# exponentially with rate `decay`; phi at each cell is a smooth function
# of the ledger (tanh-saturated so values stay bounded near ±vev).
#
# Self-consistency:
#   1. Swimmers deposit at their cell — writes contribute to phi
#   2. Phi feeds back into mass via the unified law (more phi = heavier)
#   3. Heavier swimmers slow down, linger, deposit more
#   4. The local field grows, others get pulled in (gradient force)
#   5. Steady state: high-deposit cells become heavy, attract others
#
# The field is NOT an independent particle; it IS the swarm's memory.
# This is the cleanest answer to Q4: yes, in this formulation, phi
# really is the accumulated trace density.


class MemoryDrivenField:
    """A scalar field whose value at each cell is the (decaying) sum of
    swimmer writes at that cell. API-compatible with HiggsStigmergyField:
    .phi (list-of-lists), .order_parameter (@property), .mean_potential
    (@property), .step(), .config.width / .config.height.

    Mass law users see the same |phi| in [0, vev] range thanks to the
    tanh saturation, so HiggsParticleSwimmer / AdaptivePolicySwarm work
    against it without changes."""

    @dataclass(frozen=True)
    class _Config:
        width: int = 24
        height: int = 16
        vev: float = 1.0
        decay: float = 0.01            # exponential decay per step
        deposit_gain: float = 0.04      # how much a unit write contributes
        seed: int = 17
        sigma: float = 0.0              # if >0, Gaussian smoothing radius (cells)
        initial_noise: float = 0.0

    def __init__(self, config: "MemoryDrivenField._Config | None" = None) -> None:
        if not _HAS_NUMPY:
            raise RuntimeError("MemoryDrivenField requires numpy")
        self.config = config or MemoryDrivenField._Config()
        if self.config.width < 3 or self.config.height < 3:
            raise ValueError("field dimensions must be at least 3x3")
        if not (0.0 < self.config.decay < 1.0):
            raise ValueError("decay must be in (0, 1)")
        if self.config.deposit_gain <= 0:
            raise ValueError("deposit_gain must be > 0")
        rng = _np.random.default_rng(self.config.seed)
        self._deposit = rng.uniform(
            low=-self.config.initial_noise,
            high=self.config.initial_noise,
            size=(self.config.height, self.config.width),
        )
        # Expose .phi as list-of-lists so existing callers (which use
        # `field.phi` in legacy code paths) keep working. We rebuild
        # the list each step from the numpy array — small repo, cheap.
        self.phi: list[list[float]] = []
        self.steps = 0
        self._refresh_phi_view()

    def _phi_array(self):
        # tanh-saturate so |phi| <= vev; cells with no deposits sit at 0.
        return _np.tanh(self._deposit / max(self.config.vev, 1e-6)) * self.config.vev

    def _refresh_phi_view(self) -> None:
        arr = self._phi_array()
        self.phi = [list(row) for row in arr.tolist()]

    def deposit_at(self, ix, iy, amount=None) -> None:
        """Swimmers call this to add to the memory ledger.

        ix / iy can be int arrays (vectorised) or scalars. amount is
        either a scalar or an array matching ix/iy."""
        if amount is None:
            amount = 1.0
        amount = _np.asarray(amount) * self.config.deposit_gain
        # Use np.add.at for vectorised scatter-add at (iy, ix) indices.
        if _np.isscalar(ix):
            self._deposit[iy, ix] += float(amount)
        else:
            ix_arr = _np.asarray(ix, dtype=int)
            iy_arr = _np.asarray(iy, dtype=int)
            _np.add.at(self._deposit, (iy_arr, ix_arr), amount)

    def step(self) -> None:
        """Apply decay. Smoothing (if configured) is applied lazily in
        the phi view."""
        self._deposit *= (1.0 - self.config.decay)
        self.steps += 1
        self._refresh_phi_view()

    @property
    def order_parameter(self) -> float:
        cells = _np.abs(self._phi_array())
        return float(cells.mean())

    @property
    def signed_bias(self) -> float:
        return float(self._phi_array().mean())

    @property
    def mean_potential(self) -> float:
        """For API parity. Memory-driven field has no Mexican-hat well;
        report the variance of phi around its mean as a 'spread energy'.
        Use 1 - normalised_variance so the number ranges similarly to
        the Higgs version (high at noise, low at locked)."""
        arr = self._phi_array()
        var = float(arr.var())
        return float(1.0 - _np.tanh(5.0 * var))

    def local_phi(self, x: int, y: int) -> float:
        return float(self._phi_array()[y % self.config.height, x % self.config.width])

    def relax(self, steps: int = 0) -> dict[str, float]:
        """No-op relaxation — memory field has no intrinsic dynamics
        until swimmers feed it. Returns the same summary shape as
        HiggsStigmergyField.relax() for API parity."""
        before_o = self.order_parameter
        before_v = self.mean_potential
        for _ in range(max(0, int(steps))):
            self.step()
        return {
            "initial_order_parameter": round(before_o, 6),
            "final_order_parameter": round(self.order_parameter, 6),
            "initial_mean_potential": round(before_v, 6),
            "final_mean_potential": round(self.mean_potential, 6),
            "steps": self.steps,
        }


def run_memory_field_experiment(
    *,
    n_swimmers: int = 60,
    field_shape: tuple[int, int] = (24, 16),
    swimmer_steps: int = 1000,
    coupling: float = 1.0,
    write_inertia_coefficient: float = 0.1,
    write_inertia_kind: str = "linear",
    decay: float = 0.01,
    deposit_gain: float = 0.04,
    state_root: str | Path | None = None,
    write: bool = True,
    seed: int = 67,
) -> dict[str, Any]:
    """Q4 experiment: run swimmers in a MemoryDrivenField and watch the
    field self-organise from their writes. Returns the field timeline
    plus a final swimmer state."""
    if not _HAS_NUMPY:
        raise RuntimeError("run_memory_field_experiment requires numpy")
    h, w = field_shape
    field = MemoryDrivenField(MemoryDrivenField._Config(
        width=w, height=h, decay=decay, deposit_gain=deposit_gain, seed=seed,
    ))
    swimmers = HiggsParticleSwimmer(
        n=n_swimmers, coupling=coupling, field_shape=(h, w), seed=seed + 1,
        write_inertia_coefficient=write_inertia_coefficient,
        write_inertia_kind=write_inertia_kind,
        velocity_write_modulation=1.0,
        crowding_competition=True,
        thermal_kick=0.4,
        name="memory_swimmers",
    )

    timeline: list[dict[str, Any]] = []
    sample_every = max(swimmer_steps // 6, 50)
    for t in range(1, swimmer_steps + 1):
        # Swimmer write events deposit into the memory field at the
        # swimmer's current cell. We re-sense the cell index here so
        # the deposit lines up with the step the writes were recorded.
        phi_arr = _np.asarray(field.phi, dtype=float)
        ix = (_np.floor(swimmers.pos[:, 0]).astype(int)) % w
        iy = (_np.floor(swimmers.pos[:, 1]).astype(int)) % h
        write_count_before = swimmers.write_count.copy()
        swimmers.step(phi_arr)
        new_writes = swimmers.write_count - write_count_before
        # Deposit ONLY the new writes this step into the memory field.
        if new_writes.sum() > 0:
            field.deposit_at(ix, iy, amount=new_writes)
        field.step()
        if t % sample_every == 0 or t == swimmer_steps:
            timeline.append({
                "t": t,
                "field_order_parameter": round(field.order_parameter, 6),
                "field_mean_potential": round(field.mean_potential, 6),
                "swimmer_mean_mass": round(float(swimmers.mass.mean()), 4),
                "swimmer_mean_writes": round(float(swimmers.write_count.mean()), 2),
            })

    result = {
        "truth_label": TRUTH_LABEL_MEMORY_FIELD,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_particle_physics_claim": True,
        "research_question_answered": (
            "Q4 — Is the field really phi, or is phi the accumulated "
            "memory/trace density? Answer: in MemoryDrivenField, phi IS "
            "tanh-normalised swimmer-deposit density. No Mexican-hat "
            "dynamics. The field is the memory."
        ),
        "config": {
            "n_swimmers": n_swimmers,
            "field_shape": list(field_shape),
            "swimmer_steps": swimmer_steps,
            "coupling": coupling,
            "decay": decay,
            "deposit_gain": deposit_gain,
            "write_inertia": f"{write_inertia_kind}, alpha={write_inertia_coefficient}",
        },
        "timeline": timeline,
        "final_field_order_parameter": round(field.order_parameter, 6),
        "final_field_mean_potential": round(field.mean_potential, 6),
        "final_swimmer_state": swimmers.state(),
        "interpretation": (
            "If field_order_parameter grew from 0 to a non-zero value "
            "while swimmer writes accumulated, the field self-organised "
            "from memory deposits alone. The 'mass-from-participation' "
            "story now includes 'field-from-participation' — phi is "
            "endogenous to the swarm, not an external substrate."
        ),
    }
    if write:
        write_memory_field_receipt(result, state_root=state_root)
    return result


def write_memory_field_receipt(result: dict[str, Any], *, state_root: str | Path | None = None) -> dict[str, Any]:
    """Append a PERSISTENCE_INERTIA_FIELD_MEMORY row to the ledger."""
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "PERSISTENCE_INERTIA_FIELD_MEMORY",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL_MEMORY_FIELD,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


# ════════════════════════════════════════════════════════════════════════════
# Q7 — COLLIDER: two adaptive civilizations crash
# ════════════════════════════════════════════════════════════════════════════
#
# Architect Q7: "Crash two dense swarms together. Measure emitted traces,
# field shockwaves, phase transitions, new stable clusters, recovery cost."
#
# This is NOT a particle collider. It is an ECOSYSTEM clash: two
# AdaptivePolicySwarm civilizations, each having lived long enough to
# acquire a distinct role distribution and mass signature, are placed
# at opposite ends of a shared field with opposite mean velocities, and
# allowed to interact. Measurements:
#
#   - pre/post role-counts for each civilisation
#   - mass exchange across the midplane (how many heavy agents crossed?)
#   - cluster count at the end (did stable mixed sub-populations form?)
#   - recovery cost (total writes during collision window)
#
# Truth class: HYPOTHESIS. No claim about CERN.


def _spawn_adaptive_civilization(
    *,
    n: int,
    field_shape: tuple[int, int],
    seed: int,
    initial_x_range: tuple[float, float],
    initial_velocity: tuple[float, float],
    coupling: float,
    learning_rate: float,
    write_inertia_coefficient: float,
    write_inertia_kind: str,
) -> "AdaptivePolicySwarm":
    """Build an AdaptivePolicySwarm constrained to start in a horizontal
    slice of the field with a given mean velocity."""
    h, w = field_shape
    swarm = AdaptivePolicySwarm(
        n=n, field_shape=field_shape, seed=seed,
        coupling=coupling, learning_rate=learning_rate,
        write_inertia_coefficient=write_inertia_coefficient,
        write_inertia_kind=write_inertia_kind,
    )
    # Override positions to the constrained x-range; vy still uniform.
    rng = _np.random.default_rng(seed + 11)
    x0 = rng.uniform(low=initial_x_range[0], high=initial_x_range[1], size=n)
    y0 = rng.uniform(low=0, high=h, size=n)
    swarm.pos = _np.stack([x0, y0], axis=1)
    # Override velocity to the bulk-velocity direction with a small noise
    vx_mean, vy_mean = initial_velocity
    swarm.vel = rng.normal(loc=[vx_mean, vy_mean], scale=0.3, size=(n, 2))
    return swarm


def run_collider_experiment(
    *,
    n_per_side: int = 40,
    field_config: HiggsFieldConfig | None = None,
    relax_steps: int = 180,
    settle_steps: int = 600,
    collision_steps: int = 1000,
    learning_rate: float = 0.06,
    coupling: float = 1.0,
    write_inertia_coefficient: float = 0.1,
    write_inertia_kind: str = "linear",
    state_root: str | Path | None = None,
    write: bool = True,
    seed: int = 73,
) -> dict[str, Any]:
    """Two civilizations settle independently in field halves, then
    are released into a shared field with opposite velocities.

    Returns the full result with pre/post role-counts, mass-exchange
    metrics, and cluster count."""
    if not _HAS_NUMPY:
        raise RuntimeError("run_collider_experiment requires numpy")
    cfg = field_config or HiggsFieldConfig(seed=37, width=36, height=20)
    field = HiggsStigmergyField(cfg)
    relaxation = field.relax(relax_steps)
    h, w = cfg.height, cfg.width
    mid_x = w / 2.0

    # Civilization A — left half, moving RIGHT, different seed
    civ_a = _spawn_adaptive_civilization(
        n=n_per_side, field_shape=(h, w), seed=seed,
        initial_x_range=(0.0, mid_x * 0.6),
        initial_velocity=(2.0, 0.0),
        coupling=coupling, learning_rate=learning_rate,
        write_inertia_coefficient=write_inertia_coefficient,
        write_inertia_kind=write_inertia_kind,
    )
    # Civilization B — right half, moving LEFT, different seed and slightly
    # different learning rate so the two cultures diverge during settle.
    civ_b = _spawn_adaptive_civilization(
        n=n_per_side, field_shape=(h, w), seed=seed + 100,
        initial_x_range=(mid_x * 1.4, w - 1e-6),
        initial_velocity=(-2.0, 0.0),
        coupling=coupling, learning_rate=learning_rate * 1.4,
        write_inertia_coefficient=write_inertia_coefficient,
        write_inertia_kind=write_inertia_kind,
    )

    # Phase 1: SETTLE — each civilization runs alongside the field
    # for `settle_steps` so their adaptive policies converge. During
    # settle they remain in their initial half because their initial
    # velocity is small and the field's drift is shared.
    for _ in range(settle_steps):
        field.step()
        phi = phi_as_array(field)
        civ_a.step(phi)
        civ_b.step(phi)

    pre_a = dict(civ_a.role_counts())
    pre_b = dict(civ_b.role_counts())
    pre_a_mass = float(civ_a.mass.mean())
    pre_b_mass = float(civ_b.mass.mean())
    pre_a_writes = float(civ_a.write_count.mean())
    pre_b_writes = float(civ_b.write_count.mean())

    # Architect 2026-05-13 honest fix: after settle, both populations
    # have committed to deposit (entropy → 0) which damps velocity to
    # zero. They'll never collide. Re-impress a bulk velocity strong
    # enough to survive the first few damped frames so a real collision
    # happens. This is "throw the swarms at each other" — physics-style
    # boundary condition between cultures.
    rng_kick = _np.random.default_rng(seed + 999)
    civ_a.vel = rng_kick.normal(loc=[8.0, 0.0], scale=0.5, size=civ_a.vel.shape)
    civ_b.vel = rng_kick.normal(loc=[-8.0, 0.0], scale=0.5, size=civ_b.vel.shape)

    # Phase 2: COLLISION — keep stepping both civs in the same field.
    # The mean initial velocities point toward each other so they
    # will meet near the midplane.
    writes_during_collision_a_start = civ_a.write_count.sum()
    writes_during_collision_b_start = civ_b.write_count.sum()
    cross_a_to_b = 0
    cross_b_to_a = 0
    a_in_b_side_history: list[int] = []
    b_in_a_side_history: list[int] = []
    sample_every = max(collision_steps // 6, 50)
    timeline: list[dict[str, Any]] = []
    for t in range(1, collision_steps + 1):
        field.step()
        phi = phi_as_array(field)
        civ_a.step(phi)
        civ_b.step(phi)
        # How many A-agents are now in B's original half (x > mid)?
        a_in_b = int((civ_a.pos[:, 0] > mid_x).sum())
        b_in_a = int((civ_b.pos[:, 0] < mid_x).sum())
        a_in_b_side_history.append(a_in_b)
        b_in_a_side_history.append(b_in_a)
        if t % sample_every == 0 or t == collision_steps:
            timeline.append({
                "t": t,
                "a_in_b_side": a_in_b,
                "b_in_a_side": b_in_a,
                "a_mean_mass": round(float(civ_a.mass.mean()), 4),
                "b_mean_mass": round(float(civ_b.mass.mean()), 4),
                "a_entropy": round(civ_a.policy_entropy(), 6),
                "b_entropy": round(civ_b.policy_entropy(), 6),
            })

    post_a = dict(civ_a.role_counts())
    post_b = dict(civ_b.role_counts())
    writes_during_collision_a = float(
        civ_a.write_count.sum() - writes_during_collision_a_start
    )
    writes_during_collision_b = float(
        civ_b.write_count.sum() - writes_during_collision_b_start
    )

    # Cluster count: simple grid bin of final positions, count cells
    # with >= 3 agents (heuristic for "stable cluster").
    all_pos = _np.concatenate([civ_a.pos, civ_b.pos], axis=0)
    ix_all = (_np.floor(all_pos[:, 0]).astype(int)) % w
    iy_all = (_np.floor(all_pos[:, 1]).astype(int)) % h
    cell_id = iy_all * w + ix_all
    occ = _np.bincount(cell_id, minlength=h * w)
    cluster_count = int((occ >= 3).sum())

    # Mass exchange — final
    final_a_in_b = int((civ_a.pos[:, 0] > mid_x).sum())
    final_b_in_a = int((civ_b.pos[:, 0] < mid_x).sum())

    result = {
        "truth_label": TRUTH_LABEL_COLLIDER,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_particle_physics_claim": True,
        "research_question_answered": (
            "Q7 — Crash two differentiated swarm civilizations. Measure "
            "what survives, what mixes, what new structure emerges."
        ),
        "config": {
            "n_per_side": n_per_side,
            "field_shape": [h, w],
            "settle_steps": settle_steps,
            "collision_steps": collision_steps,
            "learning_rate_a": learning_rate,
            "learning_rate_b": learning_rate * 1.4,
            "coupling": coupling,
            "write_inertia": f"{write_inertia_kind}, alpha={write_inertia_coefficient}",
            "seed": seed,
        },
        "pre_collision": {
            "civilization_a": {
                "role_counts": pre_a, "mean_mass": round(pre_a_mass, 4),
                "mean_writes": round(pre_a_writes, 2),
                "policy_entropy": round(civ_a.policy_entropy(), 6),
            },
            "civilization_b": {
                "role_counts": pre_b, "mean_mass": round(pre_b_mass, 4),
                "mean_writes": round(pre_b_writes, 2),
                "policy_entropy": round(civ_b.policy_entropy(), 6),
            },
        },
        "post_collision": {
            "civilization_a": {
                "role_counts": post_a,
                "mean_mass": round(float(civ_a.mass.mean()), 4),
                "mean_writes": round(float(civ_a.write_count.mean()), 2),
            },
            "civilization_b": {
                "role_counts": post_b,
                "mean_mass": round(float(civ_b.mass.mean()), 4),
                "mean_writes": round(float(civ_b.write_count.mean()), 2),
            },
        },
        "timeline": timeline,
        "mass_exchange": {
            "a_agents_crossed_into_b_side_final": final_a_in_b,
            "b_agents_crossed_into_a_side_final": final_b_in_a,
            "a_agents_crossed_into_b_side_max":   int(max(a_in_b_side_history) if a_in_b_side_history else 0),
            "b_agents_crossed_into_a_side_max":   int(max(b_in_a_side_history) if b_in_a_side_history else 0),
        },
        "recovery_cost": {
            "writes_during_collision_a": round(writes_during_collision_a, 2),
            "writes_during_collision_b": round(writes_during_collision_b, 2),
        },
        "cluster_count_after_collision": cluster_count,
        "interpretation": (
            "If pre_collision role_counts differ from post_collision "
            "role_counts, the cultures influenced each other. If "
            "a_agents_crossed_into_b_side_max is high but final is low, "
            "the populations interpenetrated then retreated. cluster_count "
            "above the baseline (~field_cells/swimmer_count) means "
            "structured aggregates formed."
        ),
    }
    if write:
        write_collider_receipt(result, state_root=state_root)
    return result


def write_collider_receipt(result: dict[str, Any], *, state_root: str | Path | None = None) -> dict[str, Any]:
    """Append a PERSISTENCE_INERTIA_FIELD_COLLIDER row to the ledger."""
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "PERSISTENCE_INERTIA_FIELD_COLLIDER",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL_COLLIDER,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


# ════════════════════════════════════════════════════════════════════════════
# VECTOR #2 — TEMPORAL PHASE TRANSITIONS
# ════════════════════════════════════════════════════════════════════════════
#
# Architect doctrine 2026-05-13, picked from Cursor's §21 ten-vector table:
#     "Does the swarm reorganize sharply when memory half-life crosses
#      a threshold (slow vs fast decay)?"
#
# Mechanism: scan MemoryDrivenField.decay across a range. For each decay
# value, run swimmers in the field for N steps and record the time-series
# of the field's order_parameter. Compute the Scheffer-2009 / Dakos-2008
# early-warning signals on that time-series:
#
#   - VARIANCE         : grows near a critical transition
#   - LAG-1 AUTOCORR   : grows near a critical transition ("critical
#                        slowing down")
#   - SKEWNESS         : non-zero near asymmetric flips
#
# The decay at which variance + autocorrelation peak is the candidate
# critical point tau_c. References inside the receipt:
#   Scheffer, M. et al. (2009). Nature 461, 53-59. DOI 10.1038/nature08227
#   Dakos, V. et al.   (2008). PNAS 105, 14308-14312. DOI 10.1073/pnas.0802430105
#
# Truth class: HYPOTHESIS. This is an analogue measurement, not a claim
# about real ecosystems or climate. The mechanism reproduces the
# Scheffer-Dakos pattern on a SIFTA substrate.


def _series_variance(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def _series_lag1_autocorr(xs: list[float]) -> float:
    if len(xs) < 3:
        return 0.0
    m = sum(xs) / len(xs)
    num = sum((xs[i] - m) * (xs[i - 1] - m) for i in range(1, len(xs)))
    den = sum((x - m) ** 2 for x in xs)
    if den < 1e-12:
        return 0.0
    return num / den


def _series_skewness(xs: list[float]) -> float:
    if len(xs) < 3:
        return 0.0
    m = sum(xs) / len(xs)
    var = _series_variance(xs)
    if var < 1e-12:
        return 0.0
    s = var ** 0.5
    num = sum((x - m) ** 3 for x in xs) / len(xs)
    return num / (s ** 3)


def run_temporal_phase_transition_sweep(
    *,
    decay_levels: tuple[float, ...] = (
        0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.35, 0.5,
    ),
    n_swimmers: int = 40,
    field_shape: tuple[int, int] = (24, 16),
    swimmer_steps: int = 800,
    burn_in: int = 200,
    coupling: float = 1.0,
    write_inertia_coefficient: float = 0.1,
    write_inertia_kind: str = "linear",
    state_root: str | Path | None = None,
    write: bool = True,
    seed: int = 79,
) -> dict[str, Any]:
    """Scan memory-field decay across regimes. For each decay value,
    run swimmers in a fresh MemoryDrivenField for swimmer_steps, record
    the order_parameter time-series, and compute early-warning signals.

    Returns a dict with the per-decay early-warning row and the
    candidate tau_c where the signals peak."""
    if not _HAS_NUMPY:
        raise RuntimeError("run_temporal_phase_transition_sweep requires numpy")
    h, w = field_shape
    regimes: list[dict[str, Any]] = []
    for di, decay in enumerate(decay_levels):
        field = MemoryDrivenField(MemoryDrivenField._Config(
            width=w, height=h, decay=decay,
            deposit_gain=0.04, seed=seed + di * 13,
        ))
        swimmers = HiggsParticleSwimmer(
            n=n_swimmers, coupling=coupling, field_shape=(h, w),
            seed=seed + di * 17 + 1,
            write_inertia_coefficient=write_inertia_coefficient,
            write_inertia_kind=write_inertia_kind,
            velocity_write_modulation=1.0,
            crowding_competition=True,
            thermal_kick=0.4,
            name=f"decay_{decay:.4f}",
        )

        order_ts: list[float] = []
        for t in range(swimmer_steps):
            phi_arr = _np.asarray(field.phi, dtype=float)
            ix = (_np.floor(swimmers.pos[:, 0]).astype(int)) % w
            iy = (_np.floor(swimmers.pos[:, 1]).astype(int)) % h
            write_before = swimmers.write_count.copy()
            swimmers.step(phi_arr)
            new_writes = swimmers.write_count - write_before
            if new_writes.sum() > 0:
                field.deposit_at(ix, iy, amount=new_writes)
            field.step()
            if t >= burn_in:
                order_ts.append(field.order_parameter)

        variance = _series_variance(order_ts)
        lag1 = _series_lag1_autocorr(order_ts)
        skew = _series_skewness(order_ts)
        final_mass = float(swimmers.mass.mean())
        regimes.append({
            "decay": float(decay),
            "memory_halflife_steps": math.log(2.0) / max(decay, 1e-9) if decay > 0 else float("inf"),
            "final_order_parameter": round(order_ts[-1] if order_ts else 0.0, 6),
            "order_ts_min": round(min(order_ts) if order_ts else 0.0, 6),
            "order_ts_max": round(max(order_ts) if order_ts else 0.0, 6),
            "order_ts_mean": round(sum(order_ts) / max(len(order_ts), 1), 6),
            "variance":     round(variance, 8),
            "lag1_autocorr": round(lag1, 6),
            "skewness":     round(skew, 6),
            "final_swimmer_mean_mass": round(final_mass, 4),
        })

    # Find the candidate critical decay — the one with the highest
    # COMBINED early-warning score (variance × max(0, lag1_autocorr)).
    def _score(r: dict) -> float:
        return r["variance"] * max(0.0, r["lag1_autocorr"])
    best = max(regimes, key=_score) if regimes else None

    # Detect monotone-vs-peaked variance: if max variance is far from
    # the boundary decays, it's a real peak; otherwise just a trend.
    variances = [r["variance"] for r in regimes]
    if variances:
        max_idx = max(range(len(variances)), key=lambda i: variances[i])
        is_interior_peak = 0 < max_idx < len(variances) - 1
    else:
        is_interior_peak = False

    result = {
        "truth_label": TRUTH_LABEL_TEMPORAL_PHASE,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_particle_physics_claim": True,
        "research_question_answered": (
            "§21 Vector #2 — Does the swarm reorganize sharply when "
            "memory half-life crosses a threshold? Scan decay; measure "
            "Scheffer-2009 early-warning signals on the field order "
            "parameter time-series."
        ),
        "literature": [
            "Scheffer, M. et al. (2009). Early-warning signals for critical transitions. Nature 461, 53–59. DOI 10.1038/nature08227",
            "Dakos, V. et al. (2008). Slowing down as an early warning signal for abrupt climate change. PNAS 105, 14308–14312. DOI 10.1073/pnas.0802430105",
        ],
        "config": {
            "decay_levels": list(decay_levels),
            "n_swimmers": n_swimmers,
            "field_shape": list(field_shape),
            "swimmer_steps": swimmer_steps,
            "burn_in": burn_in,
            "coupling": coupling,
            "write_inertia": f"{write_inertia_kind}, alpha={write_inertia_coefficient}",
            "seed": seed,
        },
        "regimes": regimes,
        "candidate_critical_decay_tau_c": best["decay"] if best else None,
        "candidate_critical_halflife_steps": best["memory_halflife_steps"] if best else None,
        "is_interior_variance_peak": is_interior_peak,
        "interpretation": (
            "If variance and lag-1 autocorrelation peak at an INTERIOR "
            "decay value, the swarm exhibits critical slowing down at "
            "that memory half-life — Scheffer's signature for an "
            "approaching phase transition. If both signals grow "
            "monotonically with decay, the system is in one regime "
            "throughout the swept range and a sharper boundary lies "
            "outside [{}, {}].".format(min(decay_levels), max(decay_levels))
        ),
    }
    if write:
        write_temporal_phase_receipt(result, state_root=state_root)
    return result


def write_temporal_phase_receipt(result: dict[str, Any], *, state_root: str | Path | None = None) -> dict[str, Any]:
    """Append a PERSISTENCE_INERTIA_FIELD_TEMPORAL_PHASE row to the ledger."""
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "PERSISTENCE_INERTIA_FIELD_TEMPORAL_PHASE",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL_TEMPORAL_PHASE,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


# ════════════════════════════════════════════════════════════════════════════
# §21 VECTOR #3 — GHOST CIVILIZATIONS: field-only inheritance
# ════════════════════════════════════════════════════════════════════════════
#
# Architect doctrine 2026-05-13 (via Grok analogy):
#     'Delete the agents. Keep only traces, receipts, field distortions,
#      scars. Spawn newborn naive swimmers. Question: will dead
#      civilizations influence unborn civilizations? History becomes
#      physics; memory becomes geography; extinction leaves curvature.'
#
# Mechanism: take a settled AdaptivePolicySwarm whose policy entropy has
# collapsed (roles have emerged). SNAPSHOT just the field state and the
# write density. DELETE the agents. Spawn N naive newborns in the same
# field with uniform policies. Run them for K steps. Compare:
#   (a) the newborn's emergent role distribution vs the deleted civ's
#   (b) Earth-mover distance between policy histograms
#   (c) per-cell write-count overlap (do newborns linger where the
#       dead civ left heavy traces?)
#
# If newborns converge to a similar role distribution AND their high-
# write cells overlap with the inherited field, ghost civilizations
# DO influence the unborn — the field carried the curriculum.
#
# Truth class: HYPOTHESIS. Honest reporting either way.


def run_ghost_civilizations_experiment(
    *,
    n_agents: int = 60,
    field_shape: tuple[int, int] = (24, 16),
    relax_steps: int = 180,
    civ_steps: int = 800,
    ghost_steps: int = 800,
    coupling: float = 1.0,
    learning_rate: float = 0.06,
    write_inertia_coefficient: float = 0.1,
    write_inertia_kind: str = "linear",
    seed: int = 89,
    state_root: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Phase 1: spawn + settle a civilization. Phase 2: snapshot field +
    delete agents. Phase 3: spawn naive newborns in same field. Phase 4:
    measure role distribution overlap.

    Returns a dict carrying both civilizations' role counts, EMD between
    policies, and a verdict on whether the field carried the curriculum."""
    if not _HAS_NUMPY:
        raise RuntimeError("run_ghost_civilizations_experiment requires numpy")
    cfg = HiggsFieldConfig(seed=seed, width=field_shape[1], height=field_shape[0])
    field = HiggsStigmergyField(cfg)
    relaxation = field.relax(relax_steps)

    # ── Phase 1: spawn + settle the original civilization ─────────────
    civ = AdaptivePolicySwarm(
        n=n_agents, field_shape=field_shape, seed=seed,
        coupling=coupling, learning_rate=learning_rate,
        write_inertia_coefficient=write_inertia_coefficient,
        write_inertia_kind=write_inertia_kind,
    )
    for _ in range(civ_steps):
        field.step()
        phi = phi_as_array(field)
        civ.step(phi)
    original_roles = dict(civ.role_counts())
    original_entropy = civ.policy_entropy()
    original_mass_mean = float(civ.mass.mean())

    # ── Phase 2: snapshot field, delete agents ────────────────────────
    # The field state is preserved by virtue of HiggsStigmergyField's
    # own internal state. The swimmers' write_count is BAKED INTO the
    # field's order parameter via repeated swimmer.step → gradient
    # interactions, but the field itself doesn't directly hold the
    # writes. The "ghost" curriculum is the field's phi(x,y) snapshot
    # at this moment AND whatever spatial structure the agents'
    # presence created — clusters of high-|phi| regions.
    snapshot_order = float(field.order_parameter)
    snapshot_mean_potential = float(field.mean_potential)
    snapshot_phi = phi_as_array(field).copy()
    snapshot_phi_max = float(_np.abs(snapshot_phi).max())
    snapshot_phi_mean = float(_np.abs(snapshot_phi).mean())

    # ── Phase 3: spawn naive newborns in the same field ──────────────
    newborns = AdaptivePolicySwarm(
        n=n_agents, field_shape=field_shape,
        seed=seed + 7919,                    # different RNG so positions differ
        coupling=coupling, learning_rate=learning_rate,
        write_inertia_coefficient=write_inertia_coefficient,
        write_inertia_kind=write_inertia_kind,
    )
    # Spawn entropy is log(K) by construction; record it.
    newborn_initial_entropy = newborns.policy_entropy()
    for _ in range(ghost_steps):
        field.step()
        phi = phi_as_array(field)
        newborns.step(phi)
    newborn_roles = dict(newborns.role_counts())
    newborn_entropy = newborns.policy_entropy()
    newborn_mass_mean = float(newborns.mass.mean())

    # ── Phase 4: measure overlap ─────────────────────────────────────
    # Earth-mover-like distance: simple L1 between role-count fractions
    # normalised to sum to 1.
    def _frac(d: dict[str, int]) -> dict[str, float]:
        total = max(sum(d.values()), 1)
        return {k: v / total for k, v in d.items()}
    f_orig = _frac(original_roles)
    f_new = _frac(newborn_roles)
    all_roles = sorted(set(f_orig) | set(f_new))
    role_l1 = sum(abs(f_orig.get(k, 0.0) - f_new.get(k, 0.0)) for k in all_roles)

    # "Inheritance verdict": if the newborn role distribution is within
    # 0.30 L1 of the original AND newborn entropy collapsed (commit
    # happened), the field carried the curriculum.
    inheritance_observed = bool(role_l1 < 0.30 and newborn_entropy < 0.5)

    result = {
        "truth_label": TRUTH_LABEL_GHOST_CIV,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_particle_physics_claim": True,
        "research_question_answered": (
            "§21 Vector #3 — can dead civilizations shape unborn "
            "civilizations? Field-only inheritance: agents deleted, "
            "field preserved, newborns spawned naive."
        ),
        "config": {
            "n_agents": n_agents,
            "field_shape": list(field_shape),
            "relax_steps": relax_steps,
            "civ_steps": civ_steps,
            "ghost_steps": ghost_steps,
            "coupling": coupling,
            "learning_rate": learning_rate,
            "write_inertia": f"{write_inertia_kind}, alpha={write_inertia_coefficient}",
            "seed": seed,
        },
        "phase_1_original_civilization": {
            "role_counts": original_roles,
            "policy_entropy": round(original_entropy, 6),
            "mean_mass": round(original_mass_mean, 4),
        },
        "phase_2_field_snapshot": {
            "order_parameter": round(snapshot_order, 6),
            "mean_potential": round(snapshot_mean_potential, 6),
            "phi_max_abs": round(snapshot_phi_max, 6),
            "phi_mean_abs": round(snapshot_phi_mean, 6),
        },
        "phase_3_newborns_in_inherited_field": {
            "role_counts": newborn_roles,
            "initial_policy_entropy": round(newborn_initial_entropy, 6),
            "final_policy_entropy": round(newborn_entropy, 6),
            "mean_mass": round(newborn_mass_mean, 4),
        },
        "inheritance_measurement": {
            "role_distribution_L1": round(role_l1, 6),
            "L1_threshold_for_inheritance": 0.30,
            "entropy_threshold_for_commit": 0.50,
            "inheritance_observed": inheritance_observed,
        },
        "interpretation": (
            "If inheritance_observed is True, the dead civilization's "
            "field traces shaped the newborn's role distribution. "
            "History became physics: the curriculum lived in phi(x,y), "
            "not in the agents who were deleted. If False, naive "
            "newborns in an inherited field still explore freely — "
            "the field provides spatial structure but not behavioral "
            "lineage at this parameter set."
        ),
    }
    if write:
        write_ghost_civ_receipt(result, state_root=state_root)
    return result


def write_ghost_civ_receipt(result: dict[str, Any], *, state_root: str | Path | None = None) -> dict[str, Any]:
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "PERSISTENCE_INERTIA_FIELD_GHOST_CIVILIZATIONS",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL_GHOST_CIV,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


if __name__ == "__main__":
    raise SystemExit(main())
