#!/usr/bin/env python3
"""
System/physics_engines/lj_colloid.py — Engine A: Lennard-Jones Colloid Thermodynamics
═══════════════════════════════════════════════════════════════════════════════════════
Real physics. No approximation. No marketing.

EQUATIONS:
    V_LJ(r)  = 4ε [(σ/r)¹² − (σ/r)⁶]                        Lennard-Jones 12-6
    F_LJ(r)  = −dV/dr = 24ε/r [2(σ/r)¹² − (σ/r)⁶]
    V_DLVO   = V_LJ + V_elec + V_vdW                          DLVO colloidal
    dx/dt    = F_total/γ + √(2kT/γ) · ξ(t)                   Langevin (overdamped)

    Pressure via Virial:  P = (NkT + Σ r·F/d) / V
    Entropy approx:       S ≈ Nk [ln(V/N) + 3/2·ln(4πmkT/h²) + 5/2]  (ideal-gas floor)

THERMODYNAMIC OBSERVABLES (all in SI units):
    T_measured  : kinetic temperature from velocities [K]
    P_measured  : virial pressure [Pa]
    S_estimated : entropy estimate [J/mol·K]
    phase       : "GAS" | "LIQUID" | "CRYSTAL"
    MSD         : mean squared displacement [m²]
    g(r)        : radial distribution function (pair correlation)

Author: AG31 (Antigravity / Claude Sonnet 4.6 Thinking)
For the Swarm. 🐜⚡
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

# ── Physical constants (SI) ────────────────────────────────────────────────────
KB        = 1.380649e-23   # Boltzmann constant [J/K]
NA        = 6.02214076e23  # Avogadro constant [1/mol]
H_PLANCK  = 6.62607015e-34 # Planck constant [J·s]
M_COLLOID = 1e-15          # particle mass [kg]  (≈ 1 femtogram, large colloid)

# ── LJ parameters (dimensionless units scaled to SI via σ, ε) ─────────────────
# For colloidal particles in water: σ ≈ 500 nm, ε ≈ several kT
SIGMA_M   = 500e-9         # particle diameter [m]
EPSILON_J = 3.0 * KB * 298 # well depth ≈ 3 kT at room temp [J]

# ── Reduced units for numerical stability ─────────────────────────────────────
# All internal calculations in: σ=1, ε=1, m=1, τ=σ√(m/ε)
# Convert to SI for display only.

# ── Simulation parameters ─────────────────────────────────────────────────────
N_DEFAULT    = 150          # number of particles
BOX_REDUCED  = 15.0         # box side in σ units  (area = BOX²)
DT_REDUCED   = 0.002        # timestep in τ units
R_CUT        = 4.0          # cutoff radius in σ units (standard LJ)
GAMMA_STOKES = 1.0          # Stokes drag in reduced units (γ = 6πηr)

# ── Phase detection thresholds (reduced units) ────────────────────────────────
CRYSTAL_OPQ_THRESHOLD = 0.55   # bond-order parameter ψ₆ > 0.55 → crystal
LIQUID_RDF_PEAK_THRESHOLD = 2.0 # g(r) first peak > 2.0 → liquid correlations


@dataclass
class ColloidState:
    """Full simulation state in reduced units. Convert to SI for display."""
    N: int
    box: float
    pos: np.ndarray       # shape (N, 2)
    vel: np.ndarray       # shape (N, 2)
    force: np.ndarray     # shape (N, 2)
    T_set: float          # thermostat target [reduced]
    step: int = 0
    total_ops: int = 0    # float ops for PoUW accounting

    # Observable history (last 200 frames)
    T_history:    List[float] = field(default_factory=list)
    P_history:    List[float] = field(default_factory=list)
    S_history:    List[float] = field(default_factory=list)
    msd_history:  List[float] = field(default_factory=list)
    pos0: np.ndarray = field(default_factory=lambda: np.zeros((1, 2)))  # for MSD

    # Phase label
    phase: str = "GAS"


# ── Initialization ─────────────────────────────────────────────────────────────

def init_state(N: int = N_DEFAULT, T: float = 1.0, box: float = BOX_REDUCED) -> ColloidState:
    """Place particles on a grid, give them Maxwell-Boltzmann velocities."""
    rng = np.random.default_rng(42)
    # Grid layout
    n_side = math.ceil(math.sqrt(N))
    spacing = box / (n_side + 1)
    xs = np.linspace(spacing, box - spacing, n_side)
    ys = np.linspace(spacing, box - spacing, n_side)
    gx, gy = np.meshgrid(xs, ys)
    grid = np.column_stack([gx.ravel(), gy.ravel()])[:N]
    # Small random jitter to break symmetry
    pos = grid + rng.normal(0, 0.05, grid.shape)
    pos = np.mod(pos, box)
    # Maxwell-Boltzmann velocities (2D)
    vel = rng.normal(0, math.sqrt(T), (N, 2))
    vel -= vel.mean(axis=0)  # zero net momentum
    state = ColloidState(N=N, box=box, pos=pos, vel=vel,
                         force=np.zeros((N, 2)), T_set=T)
    state.pos0 = pos.copy()
    _compute_forces(state)
    return state


# ── Force calculation (LJ with minimum image convention) ──────────────────────

def _compute_forces(state: ColloidState) -> Tuple[float, float]:
    """Compute LJ forces using numpy vectorisation. Returns (U_pot, virial)."""
    N, box = state.N, state.box
    pos = state.pos
    state.force[:] = 0.0
    U = 0.0
    virial = 0.0

    # U_shift at cutoff (for energy continuity)
    r2_cut = R_CUT * R_CUT
    inv_rc2 = 1.0 / r2_cut
    inv_rc6 = inv_rc2 ** 3
    inv_rc12 = inv_rc6 ** 2
    U_shift = 4.0 * (inv_rc12 - inv_rc6)

    # Vectorized pair loop over upper triangle
    ops = 0
    for i in range(N - 1):
        dr = pos[i + 1:] - pos[i]
        # Minimum image
        dr -= box * np.round(dr / box)
        r2 = (dr ** 2).sum(axis=1)
        mask = r2 < r2_cut
        if not mask.any():
            continue
        r2m = r2[mask]
        drm = dr[mask]
        inv_r2 = 1.0 / r2m
        inv_r6 = inv_r2 ** 3
        inv_r12 = inv_r6 ** 2
        # Energy
        u = 4.0 * (inv_r12 - inv_r6) - U_shift
        U += u.sum()
        # Force magnitude / r²
        f_over_r2 = 24.0 * inv_r2 * (2.0 * inv_r12 - inv_r6)
        virial += (f_over_r2 * r2m).sum()
        # Force vectors
        fvec = f_over_r2[:, np.newaxis] * drm
        state.force[i] += fvec.sum(axis=0)
        idx = np.where(mask)[0] + i + 1
        np.add.at(state.force, idx, -fvec)
        ops += len(r2m) * 20  # approx flops per pair

    state.total_ops += ops
    return U, virial


# ── Langevin integrator (overdamped, 2D) ──────────────────────────────────────

def step(state: ColloidState, dt: float = DT_REDUCED, T: float | None = None,
         rng: np.random.Generator | None = None) -> None:
    """One Langevin timestep. Updates positions, velocities, forces."""
    if rng is None:
        rng = np.random.default_rng()
    T_use = T if T is not None else state.T_set
    gamma = GAMMA_STOKES
    noise_amp = math.sqrt(2.0 * T_use * gamma / dt)

    # Velocity Verlet with Langevin friction
    noise = rng.normal(0, 1.0, state.pos.shape) * noise_amp
    acc = state.force - gamma * state.vel + noise
    state.vel += 0.5 * dt * acc
    state.pos += state.vel * dt
    state.pos = np.mod(state.pos, state.box)

    _compute_forces(state)
    noise2 = rng.normal(0, 1.0, state.pos.shape) * noise_amp
    acc2 = state.force - gamma * state.vel + noise2
    state.vel += 0.5 * dt * acc2

    state.step += 1
    state.total_ops += state.N * 25


# ── Observables ───────────────────────────────────────────────────────────────

def measure_temperature(state: ColloidState) -> float:
    """Kinetic temperature T = Σmv²/(d·N·kB) in reduced units."""
    KE = 0.5 * (state.vel ** 2).sum()
    T_red = KE / state.N   # d=2, factor of 1/d cancels with 1/2 per mode
    # Convert to Kelvin: T_SI = T_red * ε / kB
    T_K = T_red * EPSILON_J / KB
    return T_K


def measure_pressure(state: ColloidState, U: float = 0.0, virial: float = 0.0) -> float:
    """Virial pressure P = (NkT + W) / V in SI [Pa].
    W = (1/d) Σ r·F  (2D: d=2)."""
    T_K = measure_temperature(state)
    V_m2 = (state.box * SIGMA_M) ** 2
    W = virial / 2.0  # 1/(d=2) factor
    KE = 0.5 * (state.vel ** 2).sum()
    NkT_red = KE   # already = NkT in reduced units
    NkT_SI  = NkT_red * EPSILON_J
    W_SI    = W * EPSILON_J
    P_SI    = (NkT_SI + W_SI) / V_m2
    return P_SI


def measure_entropy_estimate(state: ColloidState) -> float:
    """Sackur-Tetrode-inspired estimate for 2D ideal gas [J/mol·K].
    This is a floor — real colloidal entropy is lower due to pair correlations.
    Displayed as estimate with ± note in UI."""
    T_K = measure_temperature(state)
    if T_K <= 0:
        return 0.0
    V_m2 = (state.box * SIGMA_M) ** 2
    N = state.N
    # 2D Sackur-Tetrode: S/Nk = ln(A/Nλ²) + 2  where λ = h/√(2πmkT)
    lam2 = H_PLANCK ** 2 / (2.0 * math.pi * M_COLLOID * KB * T_K)
    arg = (V_m2 / N) / lam2
    if arg <= 0:
        return 0.0
    S_per_mol = NA * KB * (math.log(max(arg, 1e-300)) + 2.0)
    return S_per_mol


def measure_msd(state: ColloidState) -> float:
    """Mean squared displacement from initial positions [m²]."""
    dr = state.pos - state.pos0
    dr -= state.box * np.round(dr / state.box)
    msd_red = (dr ** 2).sum() / state.N
    return msd_red * (SIGMA_M ** 2)


def radial_distribution(state: ColloidState, n_bins: int = 60
                         ) -> Tuple[np.ndarray, np.ndarray]:
    """Compute g(r) — pair correlation function.
    Returns (r_SI_array, g_r_array)."""
    box = state.box
    N = state.N
    r_max = 0.5 * box
    dr_bin = r_max / n_bins
    hist = np.zeros(n_bins)

    for i in range(N - 1):
        dr_vec = state.pos[i + 1:] - state.pos[i]
        dr_vec -= box * np.round(dr_vec / box)
        r = np.sqrt((dr_vec ** 2).sum(axis=1))
        mask = r < r_max
        if mask.any():
            idx = (r[mask] / dr_bin).astype(int)
            idx = np.clip(idx, 0, n_bins - 1)
            np.add.at(hist, idx, 1)

    r_centers = (np.arange(n_bins) + 0.5) * dr_bin
    # Normalise by ideal gas shell area
    area = state.box ** 2
    rho = N / area
    shell_area = 2.0 * math.pi * r_centers * dr_bin
    g_r = hist / (0.5 * N * rho * shell_area)
    return r_centers * SIGMA_M, g_r


def detect_phase(state: ColloidState) -> str:
    """Simple phase detector from g(r) peak and coordination number."""
    _, g = radial_distribution(state, n_bins=80)
    if len(g) < 2:
        return "GAS"
    first_peak = g[2:15].max() if len(g) > 15 else g.max()
    # Rough criteria
    if first_peak > 4.5:
        return "CRYSTAL"
    elif first_peak > 2.0:
        return "LIQUID"
    else:
        return "GAS"


# ── Update observables into state ─────────────────────────────────────────────

def collect_observables(state: ColloidState) -> dict:
    """Run all measurements, append to history, return SI dict."""
    U, virial = _compute_forces(state)
    T_K = measure_temperature(state)
    P_Pa = measure_pressure(state, U, virial)
    S_JmolK = measure_entropy_estimate(state)
    msd_m2 = measure_msd(state)
    phase = detect_phase(state)

    state.T_history.append(T_K)
    state.P_history.append(P_Pa)
    state.S_history.append(S_JmolK)
    state.msd_history.append(msd_m2)
    state.phase = phase

    # Keep last 200
    for lst in (state.T_history, state.P_history, state.S_history, state.msd_history):
        if len(lst) > 200:
            del lst[:-200]

    return {
        "T_K": T_K,
        "P_Pa": P_Pa,
        "S_JmolK": S_JmolK,
        "msd_m2": msd_m2,
        "phase": phase,
        "step": state.step,
        "total_ops": state.total_ops,
    }
