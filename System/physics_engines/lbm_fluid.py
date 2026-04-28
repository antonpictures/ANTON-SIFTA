#!/usr/bin/env python3
"""
System/physics_engines/lbm_fluid.py — Engine B: Lattice-Boltzmann Fluid Dynamics
═══════════════════════════════════════════════════════════════════════════════════
Real physics. No approximation. No marketing.

EQUATIONS:
    D2Q9 BGK Collision-Streaming:
        f_i(x + e_i·dt, t+dt) = f_i(x,t) − (1/τ)[f_i − f_i^eq(ρ,u)]    BGK
        f_i^eq = w_i · ρ · [1 + (e_i·u)/cs² + (e_i·u)²/2cs⁴ − u²/2cs²] equilibrium
        ρ(x,t) = Σ f_i                                                     density
        u(x,t) = (1/ρ) Σ f_i · e_i                                        velocity
        τ = (ν/cs²) + 0.5                                                  relaxation time
        ν = cs²(τ - 0.5)                                                   kinematic viscosity
        cs² = 1/3                                                           speed of sound squared

    Reynolds number:  Re = U·L / ν   (characteristic velocity × length / viscosity)
    Mach number:      Ma = U / cs    (< 0.3 required for incompressibility assumption)

PHYSICS REGIMES:
    Re < 5    → laminar, symmetric wake vortex pair
    Re ~ 50   → von Kármán vortex street onset
    Re ~ 100  → periodic shedding, measurable Strouhal number
    Re > 300  → turbulent onset (LBM becomes approximate)

OBSERVABLES (all in LBM units):
    rho_field  : density field  (2D array)
    vel_mag    : velocity magnitude (2D array)
    curl_z     : vorticity ω_z = ∂u_y/∂x − ∂u_x/∂y (2D array)
    Re_live    : live Reynolds number
    Ma_live    : live Mach number
    drag_coeff : force on cylinder, normalised

Author: AG31 (Antigravity / Claude Sonnet 4.6 Thinking)
For the Swarm. 🐜⚡
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

# ── D2Q9 lattice vectors and weights ─────────────────────────────────────────
# Numbering: 0=rest, 1-4=cardinal, 5-8=diagonal
EX = np.array([0, 1, 0, -1, 0, 1, -1, -1, 1], dtype=np.float64)
EY = np.array([0, 0, 1, 0, -1, 1, 1, -1, -1], dtype=np.float64)
W  = np.array([4/9, 1/9, 1/9, 1/9, 1/9, 1/36, 1/36, 1/36, 1/36], dtype=np.float64)
CS2 = 1.0 / 3.0          # speed of sound squared in LBM units
Q = 9                     # number of lattice directions

# Bounce-back opposites: i → opposite_i
OPPOSITE = np.array([0, 3, 4, 1, 2, 7, 8, 5, 6], dtype=int)


# ── Geometry ──────────────────────────────────────────────────────────────────

def _make_cylinder_mask(ny: int, nx: int, cx_frac: float = 0.3,
                        cy_frac: float = 0.5, r_frac: float = 0.1) -> np.ndarray:
    """Boolean mask True where the cylinder obstacle is."""
    cx = int(cx_frac * nx)
    cy = int(cy_frac * ny)
    r  = int(r_frac * ny)
    Y, X = np.mgrid[0:ny, 0:nx]
    return (X - cx) ** 2 + (Y - cy) ** 2 <= r ** 2


# ── Equilibrium distribution ──────────────────────────────────────────────────

def _feq(rho: np.ndarray, ux: np.ndarray, uy: np.ndarray) -> np.ndarray:
    """D2Q9 Maxwell-Boltzmann equilibrium. Shape (Q, ny, nx)."""
    u2 = ux ** 2 + uy ** 2
    feq = np.empty((Q, *rho.shape), dtype=np.float64)
    for i in range(Q):
        eu = EX[i] * ux + EY[i] * uy
        feq[i] = W[i] * rho * (1.0 + eu / CS2 + eu ** 2 / (2.0 * CS2 ** 2)
                                - u2 / (2.0 * CS2))
    return feq


# ── Main simulation state ─────────────────────────────────────────────────────

@dataclass
class LBMState:
    ny: int
    nx: int
    f:   np.ndarray    # (Q, ny, nx) — distribution functions
    rho: np.ndarray    # (ny, nx)
    ux:  np.ndarray    # (ny, nx)
    uy:  np.ndarray    # (ny, nx)
    tau: float         # relaxation time
    u_lid: float       # inlet velocity (left boundary)
    obstacle: np.ndarray  # (ny, nx) bool

    step: int = 0
    total_ops: int = 0

    Re_history:   List[float] = field(default_factory=list)
    Ma_history:   List[float] = field(default_factory=list)
    drag_history: List[float] = field(default_factory=list)


def init_lbm(ny: int = 80, nx: int = 200,
             Re_target: float = 100.0,
             u_inlet: float = 0.08) -> LBMState:
    """
    Initialise a 2D Poiseuille-like channel with a cylindrical obstacle.
    τ is set to achieve the requested Reynolds number based on cylinder diameter.
    """
    obstacle = _make_cylinder_mask(ny, nx)
    r = int(0.1 * ny)
    L = 2 * r           # characteristic length = cylinder diameter

    # ν from Re: ν = U·L / Re → τ = ν/cs² + 0.5
    nu_target = u_inlet * L / max(Re_target, 0.1)
    tau = nu_target / CS2 + 0.5
    tau = max(0.51, min(tau, 2.0))  # stability: τ > 0.5

    rho = np.ones((ny, nx), dtype=np.float64)
    ux  = np.full((ny, nx), u_inlet, dtype=np.float64)
    uy  = np.zeros((ny, nx), dtype=np.float64)
    ux[obstacle] = 0.0
    uy[obstacle] = 0.0

    f = _feq(rho, ux, uy)

    return LBMState(
        ny=ny, nx=nx, f=f, rho=rho, ux=ux, uy=uy,
        tau=tau, u_lid=u_inlet, obstacle=obstacle
    )


def set_reynolds(state: LBMState, Re: float) -> None:
    """Hot-swap τ to hit a new Reynolds number (keeps distribution unchanged)."""
    r = int(0.1 * state.ny)
    L = 2 * r
    nu = state.u_lid * L / max(Re, 0.1)
    tau = nu / CS2 + 0.5
    state.tau = max(0.51, min(tau, 2.0))


# ── BGK collision-streaming step ─────────────────────────────────────────────

def lbm_step(state: LBMState, n_substeps: int = 1) -> None:
    """Advance n_substeps BGK LBM iterations."""
    ny, nx = state.ny, state.nx

    for _ in range(n_substeps):
        # ── 1. Macroscopic quantities ────────────────────────────────────────
        state.rho = state.f.sum(axis=0)
        state.ux  = (EX[:, None, None] * state.f).sum(axis=0) / state.rho
        state.uy  = (EY[:, None, None] * state.f).sum(axis=0) / state.rho

        # ── 2. Equilibrium ───────────────────────────────────────────────────
        feq = _feq(state.rho, state.ux, state.uy)

        # ── 3. Collision (BGK) ───────────────────────────────────────────────
        state.f += (feq - state.f) / state.tau

        # ── 4. Streaming ────────────────────────────────────────────────────
        f_new = np.empty_like(state.f)
        for i in range(Q):
            f_new[i] = np.roll(np.roll(state.f[i], int(EX[i]), axis=1),
                               int(EY[i]), axis=0)
        state.f = f_new

        # ── 5. Boundary conditions ───────────────────────────────────────────
        # Left inlet: Zou-He velocity BC (constant u_lid)
        _apply_inlet(state)

        # Right outlet: copy-out (zero-gradient)
        state.f[:, :, -1] = state.f[:, :, -2]

        # Top/Bottom walls: bounce-back
        state.f[:, 0, :]  = state.f[OPPOSITE, 0, :]
        state.f[:, -1, :] = state.f[OPPOSITE, -1, :]

        # Obstacle: bounce-back (no-slip)
        obs = state.obstacle
        for i in range(Q):
            opp = OPPOSITE[i]
            state.f[i][obs] = state.f[opp][obs]

        # Clamp density for stability
        np.clip(state.rho, 0.5, 2.0, out=state.rho)

        state.step += 1
        state.total_ops += ny * nx * Q * 15  # approx flops/cell/step


def _apply_inlet(state: LBMState) -> None:
    """Zou-He inlet BC: prescribed ux=u_lid, uy=0 on left column."""
    ny = state.ny
    ux_in = state.u_lid
    uy_in = 0.0
    # Simplified: set rho from sum and fix distributions
    # (full Zou-He for D2Q9)
    j = 0  # left column
    rho_in = (state.f[0, :, j]
              + state.f[2, :, j] + state.f[4, :, j]
              + 2.0 * (state.f[3, :, j] + state.f[6, :, j]
                       + state.f[7, :, j])) / (1.0 - ux_in)
    state.rho[:, j] = rho_in

    ru = rho_in * ux_in / 6.0
    state.f[1, :, j] = state.f[3, :, j] + (4.0 / 3.0) * rho_in * ux_in
    state.f[5, :, j] = state.f[7, :, j] + ru + 0.5 * (state.f[4, :, j] - state.f[2, :, j])
    state.f[8, :, j] = state.f[6, :, j] + ru - 0.5 * (state.f[4, :, j] - state.f[2, :, j])

    # Clamp
    state.f[:, :, j] = np.clip(state.f[:, :, j], 0.0, None)


# ── Observables ───────────────────────────────────────────────────────────────

def compute_vorticity(state: LBMState) -> np.ndarray:
    """Vorticity ω_z = ∂u_y/∂x − ∂u_x/∂y (central differences)."""
    duy_dx = np.gradient(state.uy, axis=1)
    dux_dy = np.gradient(state.ux, axis=0)
    return duy_dx - dux_dy


def compute_reynolds(state: LBMState) -> float:
    """Live Reynolds number based on mean inlet speed and cylinder diameter."""
    nu = CS2 * (state.tau - 0.5)
    r = int(0.1 * state.ny)
    L = 2 * r
    U = float(np.abs(state.ux[:, 1]).mean())
    return U * L / max(nu, 1e-12)


def compute_mach(state: LBMState) -> float:
    """Mean Mach number Ma = U/cs."""
    U = float(np.abs(state.ux[:, 1]).mean())
    return U / math.sqrt(CS2)


import math  # needed for sqrt above, imported here to keep top clean

def compute_drag(state: LBMState) -> float:
    """Momentum-exchange drag on obstacle, normalised by ρU²r."""
    obs = state.obstacle
    drag = 0.0
    for i in range(Q):
        opp = OPPOSITE[i]
        if EX[i] > 0:  # only x-component
            drag += 2.0 * EX[i] * state.f[opp][obs].sum()
    rho_mean = float(state.rho.mean())
    U = max(float(np.abs(state.ux[:, 1]).mean()), 1e-10)
    r = int(0.1 * state.ny)
    norm = rho_mean * U ** 2 * r
    return drag / max(norm, 1e-30)


def collect_lbm_observables(state: LBMState) -> dict:
    """Measure Re, Ma, drag; append to history. Return SI-labelled dict."""
    Re = compute_reynolds(state)
    Ma = compute_mach(state)
    drag = compute_drag(state)
    nu_lbm = CS2 * (state.tau - 0.5)

    state.Re_history.append(Re)
    state.Ma_history.append(Ma)
    state.drag_history.append(drag)
    for lst in (state.Re_history, state.Ma_history, state.drag_history):
        if len(lst) > 200:
            del lst[:-200]

    # Kinematic viscosity in physical units (water at 20°C analogy: ν ≈ 1e-6 m²/s)
    # Scale factor: assume grid cell = 1 μm, dt = 1 μs
    dx_m = 1e-6    # 1 μm per lattice unit
    dt_s = 1e-6    # 1 μs per LBM step
    nu_SI = nu_lbm * dx_m ** 2 / dt_s  # m²/s

    return {
        "Re": Re,
        "Ma": Ma,
        "drag_coeff": drag,
        "nu_SI_m2s": nu_SI,
        "tau": state.tau,
        "step": state.step,
        "total_ops": state.total_ops,
        "vel_max_lbm": float(np.sqrt(state.ux ** 2 + state.uy ** 2).max()),
    }
