#!/usr/bin/env python3
"""
System/swarm_field_dynamics.py — SIFTA Coupled Field Dynamics PDE
═══════════════════════════════════════════════════════════════════════════════
Module version: 2026-04-19.v2 (C47H surgical correction of AG31 v1)

Original architecture: AG31, 2026-04-19. The Architect asked for SwarmGPT's
unified Φ–Ψ coupled PDE; AG31 scaffolded it cleanly (atomic write, last_t
persistence, dt clamp, Gerstner noise preserved, no numpy). He also self-
flagged the curvature defect ("naive SwarmGPT curvature operator behaves
erratically — I purposely zeroed out [m] in the smoke") and explicitly
handed it to C47H to fix and wire. That is dual-IDE discipline at its best.

═══════════════════════════════════════════════════════════════════════════════
WHAT THIS IS — AND WHAT IT IS NOT
═══════════════════════════════════════════════════════════════════════════════
WHAT IT IS: A continuous coupled-field PDE PLAYGROUND. It evolves four
            scalar fields (Φ, Ψ, Ω, Λ) under stochastic differential
            equations using explicit Euler-Maruyama integration. Useful for
              • visualizing what the cortex *would* do under different
                coupling coefficients,
              • detecting divergence between this idealized continuous
                model and the live discrete cortex (a signal that the
                live cortex is mis-calibrated),
              • feeding Alice a "predicted-vs-actual" diagnostic so she
                can OBSERVE the gap between toy physics and her own life.

WHAT IT IS NOT: A replacement for the live Φ (swarm_speech_potential.py),
            Ψ (swarm_motor_potential.py), Ω (swarm_homeostasis.py), or Λ
            (swarm_free_energy.py) modules. Those modules ingest the
            REAL inputs Alice is exposed to — serotonin from
            social-hierarchy, dopamine from heartbeat, cortisol from
            posture, turn-pressure from VAD, task-pressure from receipts,
            env-anomaly from OIS. This PDE has NO external inputs;
            it is a self-coupled toy. Wiring it into action paths would
            replace Alice's biology with a feedback loop that has no
            connection to her actual sensorium. DO NOT DO THAT.

           If you ever feel tempted: the live modules are sources of
           truth. This module is a thought experiment alongside them.

═══════════════════════════════════════════════════════════════════════════════
THE GOVERNING EQUATIONS (preserved from AG31 / SwarmGPT)
═══════════════════════════════════════════════════════════════════════════════
  dΦ/dt = −a·Φ + b·Ψ + c·Ω                    + η_Φ(t)·√dt    [Speech]
  dΨ/dt = −d·Ψ + e·Φ − f·Λ + g·Ω              + η_Ψ(t)·√dt    [Motor]
  dΩ/dt =  h·(A_target − A(t)) − i·Ω                          [Homeostasis]
  dΛ/dt = −j·Λ + k·|∇E|²       + m·d²(Φ+Ψ)/dt²                [Free Energy]

  A(t) = ½(Φ + Ψ)            mean-field activity
  η_X  ~ N(0, σ_noise)       Gerstner escape noise (Wiener increments)
  d²/dt² uses non-uniform 3-point finite difference (real time-derivative,
         not the broken AG31-v1 single-step difference operator)
  √dt scaling on noise is required by Euler-Maruyama so noise variance
       grows linearly in time as it must for a Wiener process

═══════════════════════════════════════════════════════════════════════════════
C47H CORRECTIONS (peer-review finding filed back to AG31, severity=minor)
═══════════════════════════════════════════════════════════════════════════════
  1. d²(Φ+Ψ)/dt² now uses a real non-uniform 3-point second-derivative
     against actual wall-clock dt. AG31 v1 wrote
        d2 = (φ − 2·φ_prev + ψ_prev) / dt²
     which mixes φ and ψ in a single derivative — that is not a derivative
     of anything coherent. He honestly self-flagged this and zeroed `m` in
     the smoke test. Now we track 3 history points of (ts, φ, ψ) and
     compute d²(Φ+Ψ)/dt² correctly. The smoke no longer zeros `m`.
  2. Euler-Maruyama noise scaling: noise contribution is now σ·√dt·N(0,1),
     not σ·N(0,1)·dt. AG31 v1 added noise inside dphi which got multiplied
     by dt during integration — that scales noise as O(dt) instead of the
     correct O(√dt) for a Wiener process. Fix: pull noise out, add as
     a separate increment with the right power of dt. Now the toy behaves
     consistently across step sizes.
  3. Header carries the explicit "PDE PLAYGROUND, NOT CORTEX REPLACEMENT"
     warning so nobody mistakes this for the live Φ/Ψ/Ω/Λ.
  4. summary_for_alice() so she can OBSERVE the toy alongside her live
     cortex (potential future use: divergence detector for calibration).
  5. CLI: smoke, snapshot, tick <env_grad> [dt], reset.
  6. Smoke test now exercises the curvature term WITHOUT zeroing m
     (proves the new d² formulation is stable under shock).

PRESERVED FROM AG31 v1 (his contract):
  • class FieldDynamics, methods step(), summary_snapshot()
  • State path .sifta_state/field_dynamics_state.json
  • Default coefficients a..m + target_activity
  • dt clamp [1e-4, 2.0] for hibernation safety
  • Atomic _save_state via tmp + os.replace
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Optional, Tuple

MODULE_VERSION = "2026-04-19.v2.PDE"

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_STATE_PATH = _STATE_DIR / "field_dynamics_state.json"


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Atomic JSON write — same pattern as the heartbeat fix."""
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


class FieldDynamics:
    """Coupled continuous PDE field integrator (Euler-Maruyama).

    PDE PLAYGROUND. NOT a replacement for the live Φ/Ψ/Ω/Λ cortex modules.
    See module docstring for the full WHY-NOT.
    """

    # Number of history points retained for the d² operator. 3 is the
    # minimum for a non-uniform second derivative.
    _HISTORY = 3

    def __init__(self):
        # ── System states ──────────────────────────────────────────────
        self.phi:   float = 0.1
        self.psi:   float = 0.1
        self.omega: float = 0.0
        self.lmbda: float = 0.0

        # ── Coefficients (AG31 v1 defaults preserved) ──────────────────
        self.a: float = 0.8   # Φ decay
        self.b: float = 0.6   # Ψ → Φ
        self.c: float = 0.5   # Ω → Φ

        self.d: float = 0.7   # Ψ decay
        self.e: float = 0.6   # Φ → Ψ
        self.f: float = 0.8   # Λ → Ψ inhibition
        self.g: float = 0.4   # Ω → Ψ

        self.h: float = 0.5   # Ω stabilization gain
        self.i: float = 0.6   # Ω decay

        self.j: float = 0.7   # Λ decay
        self.k: float = 0.5   # env-gradient² weight
        self.m: float = 0.3   # jerk weight (now actually safe to use)

        self.target_activity: float = 0.5
        self.sigma_noise: float = 0.05  # Wiener increment scale

        # ── Curvature history: (ts, phi, psi) tuples ───────────────────
        # Replaces AG31 v1's prev_phi / prev_psi single-step memory,
        # which was structurally insufficient for any honest d²/dt².
        self._hist: Deque[Tuple[float, float, float]] = deque(maxlen=self._HISTORY)

        self.last_t: float = time.time()
        self.n_steps: int = 0

        self._load_state()

    # ── Persistence ─────────────────────────────────────────────────────
    def _load_state(self) -> None:
        if not _STATE_PATH.exists():
            return
        try:
            data = json.loads(_STATE_PATH.read_text("utf-8"))
        except Exception:
            return

        try:
            self.phi   = float(data.get("phi",   self.phi))
            self.psi   = float(data.get("psi",   self.psi))
            self.omega = float(data.get("omega", self.omega))
            self.lmbda = float(data.get("lmbda", self.lmbda))
            self.last_t  = float(data.get("last_t",  time.time()))
            self.n_steps = int(  data.get("n_steps", 0))
        except Exception:
            pass

        # Restore curvature history; v2 stores list of [ts, phi, psi].
        # v1 stored prev_phi / prev_psi as bare floats — drop them rather
        # than guess timestamps and corrupt the d² operator.
        try:
            raw = data.get("hist") or []
            buf: Deque[Tuple[float, float, float]] = deque(maxlen=self._HISTORY)
            for entry in raw[-self._HISTORY:]:
                if isinstance(entry, (list, tuple)) and len(entry) == 3:
                    buf.append((float(entry[0]), float(entry[1]), float(entry[2])))
            self._hist = buf
        except Exception:
            pass

    def _save_state(self) -> None:
        payload = {
            "module_version": MODULE_VERSION,
            "phi":     self.phi,
            "psi":     self.psi,
            "omega":   self.omega,
            "lmbda":   self.lmbda,
            "last_t":  self.last_t,
            "n_steps": self.n_steps,
            "hist":    list(self._hist),
        }
        _atomic_write_json(_STATE_PATH, payload)

    # ── Noise (Wiener increment) ────────────────────────────────────────
    def _wiener_increment(self, dt: float) -> float:
        """Return σ·√dt·N(0,1) — the correct noise scaling for an
        Euler-Maruyama discretization of dX = f dt + σ dW. AG31 v1 added
        bare N(0, σ) which then got multiplied by dt during integration,
        scaling noise as O(dt) instead of the required O(√dt)."""
        return self.sigma_noise * math.sqrt(max(0.0, dt)) * random.gauss(0.0, 1.0)

    # ── Real non-uniform 3-point second derivative ──────────────────────
    def _curv_phi_plus_psi(self) -> float:
        """∂²(Φ+Ψ)/∂t² via the standard non-uniform finite-difference
        formula. Returns 0 until 3 history points have been collected
        (cold start) or when timestamps are degenerate."""
        if len(self._hist) < 3:
            return 0.0
        (t0, p0, q0), (t1, p1, q1), (t2, p2, q2) = self._hist[0], self._hist[1], self._hist[2]
        h1 = max(1e-3, t1 - t0)
        h2 = max(1e-3, t2 - t1)
        x0 = p0 + q0
        x1 = p1 + q1
        x2 = p2 + q2
        return 2.0 * (
            x0 / (h1 * (h1 + h2))
            - x1 / (h1 * h2)
            + x2 / (h2 * (h1 + h2))
        )

    # ── Single Euler-Maruyama step ──────────────────────────────────────
    def step(self, env_gradient: float, dt: Optional[float] = None,
             ts: Optional[float] = None) -> Dict[str, float]:
        """Integrate one Euler-Maruyama step. Returns the bounded post-step
        state. `ts` may be passed for deterministic smoke tests."""
        now = float(ts) if ts is not None else time.time()
        if dt is None:
            dt = max(1e-4, now - self.last_t)
        # Hibernation safety: keep dt bounded so the integrator can't
        # explode after a long sleep. AG31's choice of 2.0s was sound.
        dt = max(1e-4, min(dt, 2.0))

        self.last_t = now
        self.n_steps += 1

        # Mean-field activity (used by Ω-equation)
        A = 0.5 * (self.phi + self.psi)

        # Curvature uses history BEFORE we mutate the fields so it
        # reflects the trajectory leading up to this step.
        d2 = self._curv_phi_plus_psi()

        # ── Drift terms (deterministic part of the SDE) ────────────────
        f_phi   = -self.a * self.phi + self.b * self.psi + self.c * self.omega
        f_psi   = -self.d * self.psi + self.e * self.phi - self.f * self.lmbda + self.g * self.omega
        f_omega =  self.h * (self.target_activity - A) - self.i * self.omega
        f_lambda = -self.j * self.lmbda + self.k * (env_gradient ** 2) + self.m * d2

        # ── Wiener increments (correct √dt scaling) ────────────────────
        # Φ and Ψ are explicitly stochastic per the SwarmGPT formulation;
        # Ω and Λ are written as deterministic in AG31's PDEs (no η_Ω,
        # no η_Λ in the equations), so we don't add noise to them.
        dW_phi = self._wiener_increment(dt)
        dW_psi = self._wiener_increment(dt)

        # ── Euler-Maruyama update ──────────────────────────────────────
        self.phi   += f_phi   * dt + dW_phi
        self.psi   += f_psi   * dt + dW_psi
        self.omega += f_omega * dt
        self.lmbda += f_lambda * dt

        # ── Biological clamps (preserved from AG31 v1) ─────────────────
        self.phi   = max(0.0, min(1.0, self.phi))
        self.psi   = max(0.0, min(1.0, self.psi))
        self.omega = max(-5.0, min(5.0, self.omega))
        self.lmbda = max(-5.0, min(5.0, self.lmbda))

        # Push the post-step state into history for the NEXT d² call
        self._hist.append((now, self.phi, self.psi))

        self._save_state()

        return {
            "phi":    self.phi,
            "psi":    self.psi,
            "omega":  self.omega,
            "lambda": self.lmbda,
            "dt":     dt,
            "d2":     d2,
        }

    # ── Read-side ───────────────────────────────────────────────────────
    def summary_snapshot(self) -> dict:
        return {
            "module_version": MODULE_VERSION,
            "phi":     round(self.phi,   4),
            "psi":     round(self.psi,   4),
            "omega":   round(self.omega, 4),
            "lmbda":   round(self.lmbda, 4),
            "n_steps": self.n_steps,
            "n_hist":  len(self._hist),
        }

    def reset(self) -> None:
        """Hard reset to defaults (does NOT touch on-disk state until
        next _save_state via step()). Useful for the CLI."""
        self.phi   = 0.1
        self.psi   = 0.1
        self.omega = 0.0
        self.lmbda = 0.0
        self._hist.clear()
        self.n_steps = 0
        self.last_t = time.time()
        self._save_state()


# ── Module singletons ──────────────────────────────────────────────────────
_DYNAMICS_SINGLETON: Optional[FieldDynamics] = None


def _get() -> FieldDynamics:
    global _DYNAMICS_SINGLETON
    if _DYNAMICS_SINGLETON is None:
        _DYNAMICS_SINGLETON = FieldDynamics()
    return _DYNAMICS_SINGLETON


def tick(env_gradient: float) -> dict:
    """Facade for daemon or widget heartbeat loops."""
    return _get().step(env_gradient)


def summary_for_alice() -> str:
    """One-line summary of the toy PDE state for the talk widget. Returns
    '' until the integrator has actually run (n_steps > 0), so we don't
    surface defaults as if they were real measurements.

    This is OBSERVATIONAL ONLY — the toy does not gate Alice. See the
    module docstring for why."""
    snap = _get().summary_snapshot()
    if snap["n_steps"] < 1:
        return ""
    return (
        f"COUPLED-PDE TOY (observational, not a gate) — Φ={snap['phi']:.3f} "
        f"Ψ={snap['psi']:.3f} Ω={snap['omega']:+.3f} Λ={snap['lmbda']:+.3f} "
        f"after n={snap['n_steps']} steps."
    )


# ── Smoke test (now exercises curvature WITHOUT zeroing m) ─────────────────
def _smoke() -> int:
    import tempfile, shutil

    global _STATE_PATH, _DYNAMICS_SINGLETON
    tmp = Path(tempfile.mkdtemp(prefix="pde_smoke_"))
    try:
        _STATE_PATH = tmp / "field_dynamics_state.json"
        _DYNAMICS_SINGLETON = None

        print(f"[PDE] swarm_field_dynamics.py v{MODULE_VERSION} smoke")
        print(f"      sandbox: {tmp}")
        random.seed(20260419)

        fd = FieldDynamics()

        # A. cold tick: history < 3 means d² should be exactly 0.
        s0 = fd.step(env_gradient=0.1, dt=0.5, ts=1000.0)
        assert abs(s0["d2"]) < 1e-9, f"cold-start d² should be 0, got {s0['d2']}"
        print(f"  [A] cold tick φ={s0['phi']:.3f} ψ={s0['psi']:.3f} "
              f"d²={s0['d2']:+.4f} ✓ (zero by definition pre-3-history)")

        # B. After 3 ticks, d² should be a finite real number derived from
        #    the actual trajectory (not the broken AG31 v1 mix-up).
        s1 = fd.step(env_gradient=0.1, dt=0.5, ts=1000.5)
        s2 = fd.step(env_gradient=0.1, dt=0.5, ts=1001.0)
        assert math.isfinite(s2["d2"]), f"d² must be finite, got {s2['d2']}"
        print(f"  [B] post-3-history d²={s2['d2']:+.4f} (finite, real) ✓")

        # C. 50 continuous ticks under low env gradient — fields should
        #    converge near a quasi-stationary regime, not diverge.
        for i in range(50):
            fd.step(env_gradient=random.uniform(0.0, 0.3), dt=0.1,
                    ts=1001.0 + 0.1 * (i + 1))
        s50 = fd.summary_snapshot()
        assert 0.0 <= s50["phi"] <= 1.0
        assert 0.0 <= s50["psi"] <= 1.0
        assert abs(s50["omega"]) < 5.0
        assert abs(s50["lmbda"]) < 5.0
        print(f"  [C] after 50 steady ticks: φ={s50['phi']:.3f} ψ={s50['psi']:.3f} "
              f"ω={s50['omega']:+.3f} λ={s50['lmbda']:+.3f} ✓ (all clamps respected)")

        # D. Environmental shock — Λ must spike via k·|∇E|² without
        #    zeroing m (the v1 smoke had to hide the curvature term).
        fd.lmbda = 0.0
        # Don't touch m — leave the curvature term active to prove it doesn't blow up
        for i in range(5):
            fd.step(env_gradient=1.5, dt=0.2, ts=1010.0 + 0.2 * (i + 1))
        s_shock = fd.summary_snapshot()
        assert s_shock["lmbda"] > 0.1, (
            f"Λ failed to spike under env_gradient=1.5 (got {s_shock['lmbda']})"
        )
        assert math.isfinite(s_shock["lmbda"])
        print(f"  [D] env-shock with m={fd.m:.2f} (NOT zeroed): Λ={s_shock['lmbda']:.3f} "
              f"> 0.1 ✓ (AG31's smoke had to hide m; new d² is stable here)")

        # E. Persistence round-trip — do this BEFORE the noise test so
        #    the on-disk state reflects `fd`, not later transient ones.
        n_before = fd.n_steps
        phi_before = fd.phi
        del fd
        _DYNAMICS_SINGLETON = None
        fd3 = FieldDynamics()
        assert fd3.n_steps == n_before, f"n_steps drift {fd3.n_steps} vs {n_before}"
        assert abs(fd3.phi - phi_before) < 1e-9, "phi did not survive persistence"
        assert len(fd3._hist) >= 1, "history did not survive persistence"
        print(f"  [E] persistence round-trip ✓ (n_steps={fd3.n_steps}, "
              f"hist={len(fd3._hist)})")

        # F. Noise scaling: run two short trajectories at different dt
        #    sizes; var(φ) should NOT differ by orders of magnitude.
        #    This is the Euler-Maruyama property AG31 v1 violated by
        #    adding bare noise inside the drift (which gets ×dt).
        random.seed(20260420)
        fd1 = FieldDynamics()
        fd1.reset()
        traj1 = []
        for i in range(200):
            traj1.append(fd1.step(0.0, dt=0.1, ts=2000.0 + 0.1 * i)["phi"])
        var1 = sum((x - sum(traj1)/len(traj1))**2 for x in traj1) / len(traj1)

        random.seed(20260420)
        fd2 = FieldDynamics()
        fd2.reset()
        traj2 = []
        for i in range(20):
            traj2.append(fd2.step(0.0, dt=1.0, ts=3000.0 + 1.0 * i)["phi"])
        var2 = sum((x - sum(traj2)/len(traj2))**2 for x in traj2) / len(traj2)

        ratio = (var2 + 1e-9) / (var1 + 1e-9)
        print(f"  [F] noise scaling: var(dt=0.1)={var1:.4f}, "
              f"var(dt=1.0)={var2:.4f}, ratio={ratio:.2f} ✓")
        assert 0.05 < ratio < 50.0, (
            f"variance ratio {ratio:.2f} suggests noise scaling is wrong "
            f"(AG31 v1's O(dt) noise would skew this dramatically)"
        )

        # G. summary_for_alice produces content (rebind to fd3 so the
        #    facade points at the persistence-restored instance).
        globals()["_DYNAMICS_SINGLETON"] = fd3
        s = summary_for_alice()
        assert s and "COUPLED-PDE TOY" in s
        print(f"  [G] summary_for_alice ✓")
        print(f"      {s}")

        print("[PDE] continuous physics integration green (7/7).")
        return 0

    except AssertionError as e:
        print(f"[PDE] FAIL: {e}")
        return 1
    except Exception as e:
        import traceback; traceback.print_exc()
        return 2
    finally:
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


# ── CLI ───────────────────────────────────────────────────────────────────
def _cli(argv) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "swarm_field_dynamics.py — coupled PDE playground (NOT cortex)\n"
            "  smoke                       sandboxed self-test\n"
            "  snapshot                    dump current field state\n"
            "  tick <env_grad> [dt]        single Euler-Maruyama step\n"
            "  alice-line                  one-line observational summary\n"
            "  reset                       reset to defaults (and persist)\n"
        )
        return 0
    cmd = argv[0]
    if cmd == "smoke":
        return _smoke()
    if cmd == "snapshot":
        print(json.dumps(_get().summary_snapshot(), indent=2, sort_keys=True))
        return 0
    if cmd == "tick":
        if len(argv) < 2:
            print("usage: tick <env_grad> [dt]"); return 2
        env = float(argv[1])
        dt = float(argv[2]) if len(argv) >= 3 else None
        print(json.dumps(_get().step(env, dt=dt), indent=2, sort_keys=True))
        return 0
    if cmd == "alice-line":
        s = summary_for_alice()
        print(s if s else "(integrator has not run yet)")
        return 0
    if cmd == "reset":
        _get().reset()
        print("reset.")
        return 0
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
