#!/usr/bin/env python3
"""
fold_swarm_sim.py — Stigmergic Cα folding (Go-model + LJ + obstacles)
=======================================================================

Biological metaphor for AlphaFold-scale *search* without a datacenter:
harmonic backbone, Lennard-Jones non-bonded terms, native-contact (Go)
funnel toward a hidden target fold, repulsive obstacles, and Metropolis
Monte Carlo moves **biased** by a 2D pheromone field deposited when moves
lower free energy.

Calculus (continuous objective, discrete MCMC kernel):
  E = E_bond + E_LJ + E_Go + E_obstacle
  E_bond = (k_b/2) Σ_i (||r_{i+1}-r_i|| - r_0)²
  E_LJ   = Σ_{|i-j|>1} 4ε ((σ/r)^12 - (σ/r)^6)   [r < r_cut]
  E_Go   = -ε_g Σ_{(i,j)∈N} exp(-(d_ij - d^nat_ij)² / 2σ_g²)   [Go-model]
  E_obs  = κ Σ_k Σ_i max(0, R_k - ||r_i - c_k||)²

Acceptance (Metropolis):  min(1, exp(-ΔE / k_B T))

Pheromone: 2D grid; on accepted downhill move, deposit along segment;
proposal drift includes small bias toward local pheromone gradient.

Swimmer bodies: SHA-256 commitment of (serial, sid, tick, r_digest);
optional Ed25519 checkpoint on state digest (see _maybe_sign_checkpoint).
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

_REPO = Path(__file__).resolve().parent.parent


@dataclass
class Obstacle:
    cx: float
    cy: float
    r: float
    kappa: float = 80.0


@dataclass
class FoldSwarmConfig:
    n_residues: int = 36
    n_swimmers: int = 128
    r0: float = 1.0
    k_bond: float = 220.0
    lj_epsilon: float = 0.55
    lj_sigma: float = 0.82
    lj_rcut: float = 2.2
    go_epsilon: float = 3.4
    go_sigma: float = 0.42
    k_obstacle: float = 1.0
    temperature: float = 0.55
    proposal_sigma: float = 0.055
    pheromone_grid: int = 56
    pheromone_deposit: float = 0.45
    pheromone_evap: float = 0.992
    bias_strength: float = 0.028
    seed: int = 4242
    checkpoint_every: int = 400


@dataclass
class Swimmer:
    sid: int
    hinge: int
    accepts: int = 0
    proposals: int = 0
    body_hash: str = ""

    def refresh_body(self, serial: str, tick: int, positions: np.ndarray) -> None:
        h = hashlib.sha256()
        h.update(serial.encode())
        h.update(f":{self.sid}:{tick}:".encode())
        h.update(positions.tobytes())
        self.body_hash = h.hexdigest()[:20]


class FoldSwarmSim:
    def __init__(self, cfg: FoldSwarmConfig | None = None) -> None:
        self.cfg = cfg or FoldSwarmConfig()
        self.rng = np.random.default_rng(self.cfg.seed)
        self.tick = 0
        self.serial = "GTH4921YP3"
        self._load_serial()

        self.native_r = self._build_native_fold()
        self.native_pairs, self.native_d = self._native_contacts()
        self.r = self._initial_extended()
        self.pher = np.zeros(
            (self.cfg.pheromone_grid, self.cfg.pheromone_grid), dtype=np.float64
        )
        self.world_lo = np.array([-1.0, -3.5], dtype=np.float64)
        self.world_hi = np.array([12.0, 3.5], dtype=np.float64)

        self.obstacles = [
            Obstacle(4.2, 1.1, 0.85),
            Obstacle(6.8, -1.4, 0.75),
            Obstacle(3.0, -2.0, 0.55),
        ]

        self.swimmers = [
            Swimmer(sid=s, hinge=int(self.rng.integers(1, self.cfg.n_residues - 2)))
            for s in range(self.cfg.n_swimmers)
        ]

        self.E_history: list[float] = []
        self.Q_history: list[float] = []
        self.Rg_history: list[float] = []
        self.checkpoints: list[dict[str, Any]] = []

        self.E = self._total_energy(self.r)
        self.accepts_tick = 0

    def _load_serial(self) -> None:
        try:
            import sys

            sys.path.insert(0, str(_REPO / "System"))
            from silicon_serial import read_apple_serial

            s = read_apple_serial()
            if s:
                self.serial = s
        except Exception:
            pass

    def _build_native_fold(self) -> np.ndarray:
        """Compact U-fold + slight helix tilt (2D Cα proxy)."""
        N = self.cfg.n_residues
        t = np.linspace(0, 1.8 * math.pi, N)
        # Figure-eight friendly compact fold
        x = 2.8 * np.cos(t) + 0.35 * np.sin(2.2 * t)
        y = 1.15 * np.sin(t) + 0.55 * np.cos(1.3 * t)
        r = np.stack([x, y], axis=1).astype(np.float64)
        r -= r.mean(axis=0, keepdims=True)
        scale = self.cfg.r0 * 0.92 * (N - 1) / max(
            1e-6, np.sum(np.linalg.norm(np.diff(r, axis=0), axis=1))
        )
        r *= scale
        return r

    def _native_contacts(self) -> tuple[list[tuple[int, int]], np.ndarray]:
        N = self.cfg.n_residues
        pairs: list[tuple[int, int]] = []
        dists: list[float] = []
        thr = 2.05 * self.cfg.r0
        for i in range(N):
            for j in range(i + 4, N):
                d = float(np.linalg.norm(self.native_r[i] - self.native_r[j]))
                if d < thr:
                    pairs.append((i, j))
                    dists.append(d)
        return pairs, np.array(dists, dtype=np.float64)

    def _initial_extended(self) -> np.ndarray:
        N = self.cfg.n_residues
        x = np.linspace(0.0, (N - 1) * self.cfg.r0 * 1.02, N)
        y = np.zeros(N, dtype=np.float64)
        r = np.stack([x, y], axis=1).astype(np.float64)
        r -= r.mean(axis=0, keepdims=True)
        return r

    def _bond_energy(self, r: np.ndarray) -> float:
        d = np.linalg.norm(np.diff(r, axis=0), axis=1)
        dev = d - self.cfg.r0
        return float(0.5 * self.cfg.k_bond * np.dot(dev, dev))

    def _lj_energy(self, r: np.ndarray) -> float:
        """WCA repulsion: Lennard-Jones truncated & shifted to zero at r_min = 2^(1/6) σ."""
        N = r.shape[0]
        eps = self.cfg.lj_epsilon
        sig = self.cfg.lj_sigma
        rmin = (2.0 ** (1.0 / 6.0)) * sig
        i, j = np.triu_indices(N, 2)
        dij = np.linalg.norm(r[i] - r[j], axis=1)
        m = (dij < rmin) & (dij > 1e-6)
        if not np.any(m):
            return 0.0
        dij = dij[m]
        sr = sig / dij
        s6 = sr**6
        s12 = s6 * s6
        u = 4.0 * eps * (s12 - s6)
        srmin = sig / rmin
        s6m = srmin**6
        s12m = s6m * s6m
        u0 = 4.0 * eps * (s12m - s6m)
        return float(np.sum(u - u0))

    def _go_energy(self, r: np.ndarray) -> float:
        if not self.native_pairs:
            return 0.0
        acc = 0.0
        sg2 = 2.0 * self.cfg.go_sigma**2
        for (i, j), dnat in zip(self.native_pairs, self.native_d):
            dij = float(np.linalg.norm(r[i] - r[j]))
            acc -= self.cfg.go_epsilon * math.exp(-((dij - dnat) ** 2) / sg2)
        return acc

    def _obstacle_energy(self, r: np.ndarray) -> float:
        acc = 0.0
        k0 = self.cfg.k_obstacle
        for obs in self.obstacles:
            for i in range(r.shape[0]):
                d = float(np.linalg.norm(r[i] - np.array([obs.cx, obs.cy])))
                if d < obs.r:
                    acc += obs.kappa * k0 * (obs.r - d) ** 2
        return acc

    def _total_energy(self, r: np.ndarray) -> float:
        return (
            self._bond_energy(r)
            + self._lj_energy(r)
            + self._go_energy(r)
            + self._obstacle_energy(r)
        )

    def _radius_gyration(self, r: np.ndarray) -> float:
        c = r.mean(axis=0)
        d2 = np.sum((r - c) ** 2, axis=1)
        return float(math.sqrt(d2.mean()))

    def _fraction_native_contacts(self, r: np.ndarray) -> float:
        if not self.native_pairs:
            return 0.0
        ok = 0
        for (i, j), dnat in zip(self.native_pairs, self.native_d):
            dij = float(np.linalg.norm(r[i] - r[j]))
            if dij < 1.4 * dnat:
                ok += 1
        return ok / len(self.native_pairs)

    def _world_to_grid(self, xy: np.ndarray) -> tuple[int, int]:
        g = self.cfg.pheromone_grid
        t = (xy - self.world_lo) / (self.world_hi - self.world_lo)
        gx = int(np.clip(t[0] * (g - 1), 0, g - 1))
        gy = int(np.clip(t[1] * (g - 1), 0, g - 1))
        return gx, gy

    def _pheromone_gradient(self, xy: np.ndarray) -> np.ndarray:
        g = self.cfg.pheromone_grid
        gx, gy = self._world_to_grid(xy)
        gx0 = max(0, gx - 1)
        gx1 = min(g - 1, gx + 1)
        gy0 = max(0, gy - 1)
        gy1 = min(g - 1, gy + 1)
        dpx = self.pher[gx1, gy] - self.pher[gx0, gy]
        dpy = self.pher[gx, gy1] - self.pher[gx, gy0]
        return np.array([dpx, dpy], dtype=np.float64)

    def _deposit_pheromone(self, r: np.ndarray, idx: int) -> None:
        g = self.cfg.pheromone_grid
        dep = self.cfg.pheromone_deposit
        for j in (idx - 1, idx, idx + 1):
            if 0 <= j < r.shape[0]:
                gx, gy = self._world_to_grid(r[j])
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        self.pher[
                            np.clip(gx + dx, 0, g - 1), np.clip(gy + dy, 0, g - 1)
                        ] += dep * 0.33

    def _maybe_sign_checkpoint(self) -> None:
        if self.tick % self.cfg.checkpoint_every != 0 or self.tick == 0:
            return
        payload = json.dumps(
            {
                "tick": self.tick,
                "E": round(self.E, 6),
                "Q": round(self._fraction_native_contacts(self.r), 6),
                "Rg": round(self._radius_gyration(self.r), 6),
                "Rg_native": round(self._radius_gyration(self.native_r), 6),
            },
            sort_keys=True,
        )
        row: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "payload": payload,
            "digest": hashlib.sha256(payload.encode()).hexdigest()[:32],
        }
        try:
            import sys

            if str(_REPO / "System") not in sys.path:
                sys.path.insert(0, str(_REPO / "System"))
            from crypto_keychain import sign_block

            row["ed25519"] = sign_block(payload)
        except Exception:
            row["ed25519"] = "UNAVAILABLE"
        self.checkpoints.append(row)
        if len(self.checkpoints) > 12:
            self.checkpoints.pop(0)

    def step(self) -> dict[str, Any]:
        self.tick += 1
        self.accepts_tick = 0
        self.pher *= self.cfg.pheromone_evap

        N = self.cfg.n_residues
        T = self.cfg.temperature
        sig_ang = self.cfg.proposal_sigma
        bias = self.cfg.bias_strength

        for sw in self.swimmers:
            h = sw.hinge
            if h <= 0 or h >= N - 1:
                sw.hinge = int(self.rng.integers(1, N - 2))
                h = sw.hinge

            pivot = self.r[h - 1].copy()
            mid = 0.5 * (self.r[h] + self.r[min(h + 1, N - 1)])
            gph = self._pheromone_gradient(mid)
            delta = self.rng.normal(0, sig_ang) + bias * float(
                np.dot(gph, self.r[h] - pivot) / (np.linalg.norm(gph) + 1e-9)
            ) * 0.01
            c, s = math.cos(delta), math.sin(delta)
            rot = np.array([[c, -s], [s, c]], dtype=np.float64)
            trial = self.r.copy()
            for k in range(h, N):
                trial[k] = pivot + rot @ (self.r[k] - pivot)

            e0 = self.E
            e1 = self._total_energy(trial)
            dE = e1 - e0
            sw.proposals += 1

            accept = False
            if dE <= 0.0:
                accept = True
            else:
                if self.rng.random() < math.exp(-dE / max(T, 1e-6)):
                    accept = True

            if accept:
                self.r = trial
                self.E = e1
                sw.accepts += 1
                self.accepts_tick += 1
                if dE < -1e-9:
                    self._deposit_pheromone(self.r, h)

            sw.refresh_body(self.serial, self.tick, self.r)

        self._maybe_sign_checkpoint()

        q = self._fraction_native_contacts(self.r)
        rg = self._radius_gyration(self.r)
        self.E_history.append(self.E)
        self.Q_history.append(q)
        self.Rg_history.append(rg)
        for name in ("E_history", "Q_history", "Rg_history"):
            arr = getattr(self, name)
            if len(arr) > 2500:
                setattr(self, name, arr[-2500:])

        return {
            "tick": self.tick,
            "E": self.E,
            "Q": q,
            "Rg": rg,
            "Rg_native": self._radius_gyration(self.native_r),
            "accept_rate": self.accepts_tick / max(1, self.cfg.n_swimmers),
            "n_native_pairs": len(self.native_pairs),
        }


if __name__ == "__main__":
    sim = FoldSwarmSim()
    print(
        f"Fold swarm: N={sim.cfg.n_residues}, swimmers={sim.cfg.n_swimmers}, "
        f"native contacts={len(sim.native_pairs)} (Go-model + WCA pivots)"
    )
    for _ in range(1200):
        m = sim.step()
        if sim.tick % 300 == 0:
            print(
                f"  t={m['tick']:5d}  E={m['E']:10.3f}  Q={m['Q']:.3f}  "
                f"Rg={m['Rg']:.3f}  acc={m['accept_rate']:.2f}"
            )
    print(f"Checkpoints: {len(sim.checkpoints)}")
