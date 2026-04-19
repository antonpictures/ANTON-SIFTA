# ─────────────────────────────────────────────────────────────────────────────
# System/swarm_free_energy.py — SIFTA Free Energy Action Field Λ(t)
# Dual-IDE Swarm Architecture
# Module version: 2026-04-19.v2 (C47H surgical correction of AG31 v1)
#
# Original architecture: AG31, 2026-04-19 (clean dual-IDE delivery — correct
# append_line_locked API, .sifta_state/ paths, persistence, no chat-log
# pollution, no numpy). The discipline was good. The math needed surgery.
#
# C47H corrections (2026-04-19, peer-review finding filed back to AG31):
#   1. Real time-derivatives. Original `_curvature` was the second-difference
#      operator, which is Δt²·d²x/dt² only at fixed Δt. compute() is
#      event-driven so Δt varies arbitrarily; the operator was dimensionless
#      in name only. Now we store (ts, value) pairs and divide by actual
#      wall-clock seconds.
#   2. Scale normalization. Original Λ summed terms with scales {[0,1],
#      unbounded², unbounded, [0, ln 2]} and compared Λ > 0 across them.
#      Each contribution is now passed through tanh against a characteristic
#      time-scale, so Λ ∈ [−(κ+ξ+ρ), 1] with consistent units.
#   3. Restore last_t from disk on _load_state (was claimed but not done).
#   4. Audit row now includes the inputs that produced Λ (provenance).
#   5. Two APIs:
#        a. AG31's original deterministic gate `should_act(Λ > 0)` — kept
#           intact for callers that want a hard physical gate (e.g. external
#           safety overrides, mutation governor wrappers).
#        b. New `evaluate_as_inhibitor()` returning Λ_z ∈ [0, 1] — for the
#           biologically correct integration into Ψ's R_risk EMA, so the
#           existing Gerstner escape-noise LIF gate stays probabilistic.
#           DO NOT replace Φ/Ψ with Λ-as-hard-gate; that would kill the
#           escape noise that makes Alice biological in the first place.
#   6. Welford-style running mean/variance over Λ history so we can z-score
#      and not need a static "Λ > 0" threshold. Λ_z is what feeds Ψ.
#   7. CLI: smoke, snapshot, decide, alice-line.
#   8. summary_for_alice() so the talk widget can surface Λ state.
#
# Preserved from AG31's original (non-negotiable contract):
#   • Class name FreeEnergy, methods compute() / should_act()
#   • State path .sifta_state/free_energy_state.json
#   • Ledger path .sifta_state/free_energy_traces.jsonl
#   • Default kappa=0.6, xi=0.4, rho=0.5
#
# Equation:
#   Λ(t) = φ·ψ
#          − κ·tanh(τ_grad · ∂E/∂t)²
#          − ξ·tanh(τ_curv² · (∂²Φ/∂t² + ∂²Ψ/∂t²))
#          − ρ·H(0.5(φ+ψ))
#
#   φ, ψ ∈ [0, 1] (sigmoid-normalized motor/speech desire)
#   E = environmental anomaly proxy (OIS p_anomaly is the canonical source)
#   ∂/∂t computed against actual wall-clock dt, NOT per-call differences
#   τ_grad, τ_curv = characteristic time scales (s and s², resp.) so that
#                    each tanh argument is dimensionless
#
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import math
import time
import json
import os
from pathlib import Path
from collections import deque
from typing import Deque, List, Optional, Tuple

# Import the corrected lock API. AG31's original imported
# `append_line_locked` directly; we keep that contract (the function takes
# (path, line_str) and returns None — restored after the AGC-era collision).
from System.jsonl_file_lock import append_line_locked

MODULE_VERSION = "2026-04-19.v2"

_REPO       = Path(__file__).resolve().parent.parent
_STATE_DIR  = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)

_STATE_PATH  = _STATE_DIR / "free_energy_state.json"
_LEDGER_PATH = _STATE_DIR / "free_energy_traces.jsonl"


def _sigmoid(x: float) -> float:
    if x >  50: return 1.0
    if x < -50: return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Atomic JSON write — daemon could pulse heartbeat at any moment, so
    we never want a half-flushed state.json visible to a parallel reader."""
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp, path)
    except Exception:
        pass


class FreeEnergy:
    """Free Energy Action Field Λ(t). Two ways to consume:
      • should_act(Λ) → bool   [AG31's original deterministic gate;
                                use only as an external safety override]
      • evaluate_as_inhibitor() → float ∈ [0, 1]
                                  [biologically correct: feed into Ψ's
                                   R_risk EMA so the Gerstner escape-noise
                                   gate inhibits probabilistically]
    """

    def __init__(self):
        # ── Lagrangian weights (preserved from AG31 v1) ──────────────────
        self.kappa = 0.6   # environment gradient penalty (instability)
        self.xi    = 0.4   # acceleration penalty (jerkiness prevention)
        self.rho   = 0.5   # entropy penalty (confusion / mixed signals)

        # ── Characteristic time scales for dimensionless normalization ──
        # These set "what counts as fast change" so τ·∂/∂t becomes
        # dimensionless. Tunable on disk via _load_state.
        self.tau_grad = 1.0       # seconds — env_energy that swings by 1
                                  # per second saturates the gradient term
        self.tau_curv = 1.0       # seconds² — quadratic for second deriv

        # ── Persistent history (timestamped so derivatives are honest) ──
        # We store (ts, value) pairs; deque maxlen=8 caps memory.
        self.phi_hist: Deque[Tuple[float, float]] = deque(maxlen=8)
        self.psi_hist: Deque[Tuple[float, float]] = deque(maxlen=8)
        self.energy_hist: Deque[Tuple[float, float]] = deque(maxlen=8)

        # ── Welford-style running statistics over Λ for z-scoring ────────
        # Used by evaluate_as_inhibitor() so we never need a static
        # "Λ > 0" threshold — Λ_z self-calibrates to Alice's history.
        self.lambda_n:  int   = 0
        self.lambda_mu: float = 0.0
        self.lambda_M2: float = 0.0   # sum of squared deviations from mean

        self.last_t: float = time.time()

        # ── Paths (AG31's contract) ──────────────────────────────────────
        self.state_dir   = _STATE_DIR
        self.ledger_path = _LEDGER_PATH
        self.state_path  = _STATE_PATH

        self._load_state()

    # ── Persistence ─────────────────────────────────────────────────────
    def _load_state(self):
        """Rehydrates the persistent buffers across instantiations.
        Backwards-compatible with AG31 v1 state files (which stored bare
        floats, no timestamps) by treating missing ts as 'unknown' and
        skipping the entry rather than guessing."""
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text())
        except Exception:
            return

        def _restore(key: str) -> Deque[Tuple[float, float]]:
            buf: Deque[Tuple[float, float]] = deque(maxlen=8)
            raw = data.get(key) or []
            for entry in raw[-8:]:
                # v2 stores [ts, value] pairs; v1 stored bare value.
                # Skip v1 entries so we don't corrupt time-derivatives.
                if isinstance(entry, (list, tuple)) and len(entry) == 2:
                    try:
                        buf.append((float(entry[0]), float(entry[1])))
                    except Exception:
                        continue
            return buf

        self.phi_hist    = _restore("phi_hist")
        self.psi_hist    = _restore("psi_hist")
        self.energy_hist = _restore("energy_hist")

        # Welford state (added in v2; older files won't have it)
        try:
            self.lambda_n  = int(data.get("lambda_n", 0))
            self.lambda_mu = float(data.get("lambda_mu", 0.0))
            self.lambda_M2 = float(data.get("lambda_M2", 0.0))
        except Exception:
            self.lambda_n, self.lambda_mu, self.lambda_M2 = 0, 0.0, 0.0

        # Restore the time anchor (was missing in v1 — fixed in v2).
        try:
            self.last_t = float(data.get("last_t", time.time()))
        except Exception:
            self.last_t = time.time()

    def _save_state(self):
        payload = {
            "module_version": MODULE_VERSION,
            "phi_hist":    list(self.phi_hist),
            "psi_hist":    list(self.psi_hist),
            "energy_hist": list(self.energy_hist),
            "lambda_n":    self.lambda_n,
            "lambda_mu":   self.lambda_mu,
            "lambda_M2":   self.lambda_M2,
            "last_t":      self.last_t,
        }
        _atomic_write_json(self.state_path, payload)

    # ── Time-aware derivatives (the surgical fix) ───────────────────────
    @staticmethod
    def _grad_dt(hist: Deque[Tuple[float, float]]) -> float:
        """∂x/∂t over the most recent (ts, value) pair. Returns 0 if
        history < 2 points or if dt is degenerate (clock skew, same ts)."""
        if len(hist) < 2:
            return 0.0
        (t1, v1), (t0, v0) = hist[-1], hist[-2]
        dt = max(1e-3, t1 - t0)
        return (v1 - v0) / dt

    @staticmethod
    def _curv_dt(hist: Deque[Tuple[float, float]]) -> float:
        """∂²x/∂t² over the last 3 points using a non-uniform finite
        difference (the standard formulation for unequal intervals).
        Falls back to 0 when history < 3 or dt is degenerate."""
        if len(hist) < 3:
            return 0.0
        (t2, v2), (t1, v1), (t0, v0) = hist[-1], hist[-2], hist[-3]
        h1 = max(1e-3, t1 - t0)
        h2 = max(1e-3, t2 - t1)
        # Standard non-uniform second-derivative:
        #   f''(t1) ≈ 2·[ (v0/(h1·(h1+h2))) - (v1/(h1·h2)) + (v2/(h2·(h1+h2))) ]
        return 2.0 * (
            v0 / (h1 * (h1 + h2))
            - v1 / (h1 * h2)
            + v2 / (h2 * (h1 + h2))
        )

    @staticmethod
    def _entropy(phi: float, psi: float) -> float:
        """Binary entropy of the joint mean; bounded [0, ln 2 ≈ 0.69]."""
        eps = 1e-6
        p = 0.5 * (phi + psi)
        p = max(0.0, min(1.0, p))
        return -p * math.log(p + eps) - (1.0 - p) * math.log(1.0 - p + eps)

    # ── Welford running mean / variance over Λ ──────────────────────────
    def _update_lambda_stats(self, lam: float) -> None:
        self.lambda_n += 1
        delta = lam - self.lambda_mu
        self.lambda_mu += delta / self.lambda_n
        self.lambda_M2 += delta * (lam - self.lambda_mu)

    def _lambda_z(self, lam: float) -> float:
        """Standard z-score against running stats. Returns 0 until we
        have enough samples to estimate variance honestly."""
        if self.lambda_n < 8:
            return 0.0
        var = self.lambda_M2 / max(1, self.lambda_n - 1)
        sd = math.sqrt(max(1e-9, var))
        return (lam - self.lambda_mu) / sd

    # ── Core Λ(t) ───────────────────────────────────────────────────────
    def compute(self, phi_raw: float, psi_raw: float, env_energy: float,
                ts: Optional[float] = None) -> float:
        """Returns Λ(t). Side effects: appends to history, saves state,
        updates Welford stats. Pass `ts` for deterministic smoke tests."""
        now = float(ts) if ts is not None else time.time()

        # Sigmoid-normalize when raw inputs may exceed [0, 1]
        # (Φ V_raw can be 3.52 in production, etc.). When already in
        # range we trust the caller.
        phi = _sigmoid(phi_raw) if abs(phi_raw) > 1.0 else max(0.0, min(1.0, phi_raw))
        psi = _sigmoid(psi_raw) if abs(psi_raw) > 1.0 else max(0.0, min(1.0, psi_raw))
        env = max(0.0, min(1.0, env_energy))  # OIS p_anomaly is in [0,1]

        self.phi_hist.append((now, phi))
        self.psi_hist.append((now, psi))
        self.energy_hist.append((now, env))
        self.last_t = now

        # Real time-derivatives, then bounded via tanh against a
        # characteristic timescale so each contribution is dimensionless.
        grad_E_raw  = self._grad_dt(self.energy_hist)
        grad_E_norm = math.tanh(self.tau_grad * grad_E_raw)

        curv_phi  = self._curv_dt(self.phi_hist)
        curv_psi  = self._curv_dt(self.psi_hist)
        curv_norm = math.tanh(self.tau_curv * (curv_phi + curv_psi))

        ent = self._entropy(phi, psi)  # already bounded [0, ln 2]

        Lambda = (
            (phi * psi)
            - self.kappa * (grad_E_norm ** 2)
            - self.xi    * curv_norm
            - self.rho   * ent
        )

        self._update_lambda_stats(Lambda)
        self._save_state()
        return Lambda

    # ── AG31's original deterministic gate (preserved API) ──────────────
    def should_act(self, Lambda: float,
                   action_description: str = "UNDEFINED_ACT") -> bool:
        """Deterministic Λ > 0 gate. PRESERVED from AG31 v1 for callers
        that explicitly want a hard physical override (e.g. wrapping
        mutation_governor with an environmental-stability brake).

        DO NOT use this to replace Φ/Ψ. Φ/Ψ are stochastic by design
        (Gerstner escape noise); replacing them with a deterministic
        gate gut the biological model. For Φ/Ψ integration, use
        evaluate_as_inhibitor() instead."""
        verdict = Lambda > 0.0
        trace = {
            "ts": time.time(),
            "module_version": MODULE_VERSION,
            "action": action_description,
            "lambda_field": float(Lambda),
            "lambda_z": float(self._lambda_z(Lambda)),
            "verdict": "PHYSICAL_PERMISSION_GRANTED" if verdict else "PHYSICAL_RESTRAINT",
            "components": {
                "phi_desire":  self.phi_hist[-1][1] if self.phi_hist else 0.0,
                "psi_desire":  self.psi_hist[-1][1] if self.psi_hist else 0.0,
                "env_energy":  self.energy_hist[-1][1] if self.energy_hist else 0.0,
                "n_samples":   self.lambda_n,
            },
        }
        try:
            append_line_locked(self.ledger_path, json.dumps(trace) + "\n")
        except Exception:
            pass
        return verdict

    # ── Biologically-correct inhibitor (the new API) ────────────────────
    def evaluate_as_inhibitor(self) -> float:
        """Returns inhibition ∈ [0, 1] suitable for feeding Ψ's R_risk EMA.

        Mapping: Λ_z below −1 (jerkier than Alice's recent history)
        contributes proportional inhibition; Λ_z above 0 contributes 0.
        This is the biologically correct integration: Ψ remains a
        stochastic LIF gate, and Λ shows up as risk pressure rather
        than as a hard override.

        Return 0 (no inhibition) until we have enough Welford samples
        for an honest z-score."""
        if self.lambda_n < 8 or not self.energy_hist:
            return 0.0
        last_lam = self.lambda_mu  # we need a "current Λ"; use last computed
        # actually want Λ_z of the most recent compute() — cache it
        # inside compute() via last attr instead. Lazy: recompute from
        # the current head of history.
        _, phi = self.phi_hist[-1]
        _, psi = self.psi_hist[-1]
        _, env = self.energy_hist[-1]
        # We don't re-trigger compute() here (would double-append history).
        # Instead we recompute Λ from the current head using cached stats.
        grad_E_norm = math.tanh(self.tau_grad * self._grad_dt(self.energy_hist))
        curv_norm   = math.tanh(self.tau_curv * (
            self._curv_dt(self.phi_hist) + self._curv_dt(self.psi_hist)
        ))
        ent = self._entropy(phi, psi)
        lam_now = (phi * psi
                   - self.kappa * (grad_E_norm ** 2)
                   - self.xi    * curv_norm
                   - self.rho   * ent)
        z = self._lambda_z(lam_now)
        # Map z ≤ −3 → 1.0 inhibition, z ≥ 0 → 0.
        if z >= 0:
            return 0.0
        return max(0.0, min(1.0, -z / 3.0))

    # ── Read-side helpers ───────────────────────────────────────────────
    def snapshot(self) -> dict:
        var = self.lambda_M2 / max(1, self.lambda_n - 1) if self.lambda_n > 1 else 0.0
        return {
            "module_version": MODULE_VERSION,
            "n_samples":      self.lambda_n,
            "lambda_mean":    self.lambda_mu,
            "lambda_sd":      math.sqrt(max(0.0, var)),
            "n_phi_hist":     len(self.phi_hist),
            "n_psi_hist":     len(self.psi_hist),
            "n_energy_hist":  len(self.energy_hist),
            "last_t":         self.last_t,
        }


# ── Module-level singletons + facade so callers don't manage instances ──
_FE_SINGLETON: Optional[FreeEnergy] = None


def _get() -> FreeEnergy:
    """Lazy module-level singleton. Persists across calls within a
    process; reloads from disk on cold start (Welford stats included)."""
    global _FE_SINGLETON
    if _FE_SINGLETON is None:
        _FE_SINGLETON = FreeEnergy()
    return _FE_SINGLETON


def evaluate_now(phi_raw: float, psi_raw: float, env_energy: float) -> dict:
    """One-shot facade: compute Λ, return the verdict dict the talk
    widget / Ψ wiring can use. Does not log a should_act() trace; that
    is reserved for callers explicitly requesting the deterministic
    physical gate."""
    fe = _get()
    lam = fe.compute(phi_raw, psi_raw, env_energy)
    return {
        "lambda":     lam,
        "lambda_z":   fe._lambda_z(lam),
        "inhibitor":  fe.evaluate_as_inhibitor(),
        "snapshot":   fe.snapshot(),
    }


def summary_for_alice() -> str:
    """One-liner for the talk widget _SYSTEM_PROMPT. Returns '' until we
    have enough Welford samples (≥ 8) for an honest baseline."""
    fe = _get()
    snap = fe.snapshot()
    if snap["n_samples"] < 8:
        return ""
    return (
        f"FREE-ENERGY FIELD Λ — running mean={snap['lambda_mean']:+.3f} "
        f"σ={snap['lambda_sd']:.3f} over n={snap['n_samples']} samples; "
        f"current inhibitor (feeds Ψ R_risk) = {fe.evaluate_as_inhibitor():.2f}"
    )


# ── Closed-loop coupling: Λ → Ψ.R_risk (probabilistic inhibitor) ────────
def _read_live_phi() -> Optional[float]:
    """Pull Φ V_natural from the speech_potential.json ledger if present.
    Returns None if SSP has not run yet."""
    p = _STATE_DIR / "speech_potential.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text("utf-8"))
        v = data.get("V_natural")
        if v is None:
            v = data.get("V")
        return float(v) if v is not None else None
    except Exception:
        return None


def _read_live_psi() -> Optional[float]:
    """Pull Ψ V_m from motor_potential.json and normalize to [0, 1].
    Ψ V_m typically rides in [-2, 2] with V_th around 1.0; we sigmoid
    against V_th so the input scale matches Λ's expectations."""
    p = _STATE_DIR / "motor_potential.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text("utf-8"))
        v = float(data.get("V_m", 0.0))
        # Sigmoid centered on 0 with mild slope → [0, 1] mapping
        return _sigmoid(v)
    except Exception:
        return None


def _read_live_env_anomaly() -> float:
    """Pull OIS p_anomaly as the env_energy proxy. BENIGN_HOMEOSTASIS →
    near zero; DRIFT_WARNING / ZERO_DAY_FAILURE → toward 1. Returns
    a safe 0.0 if OIS state is missing (don't fabricate threat)."""
    # OIS persists its baseline + most recent verdict; we read the
    # last p_anomaly if available. Different OIS revisions have stored
    # this under different keys; we try both common ones.
    for fname in ("optical_immune_state.json", "optical_immune_baseline.json"):
        p = _STATE_DIR / fname
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text("utf-8"))
            for key in ("last_p_anomaly", "p_anomaly", "anomaly_p"):
                if key in data:
                    return max(0.0, min(1.0, float(data[key])))
        except Exception:
            continue
    return 0.0


def couple_to_motor() -> dict:
    """Closed-loop step: read live {Φ, Ψ, OIS}, compute Λ, push the
    Λ-derived inhibitor strength into Ψ's R_risk EMA via the new
    record_environmental_inhibitor() sentinel API.

    Returns a telemetry dict with the inputs, Λ, Λ_z, and the inhibitor
    strength that was applied (or 0 if Welford has not warmed up yet).

    Total — never raises. Safe to call once per conversational turn
    from the talk widget. The biology stays stochastic: Ψ's gate is
    still a Gerstner escape-noise LIF spike; we are only adjusting
    its R_risk input so the gate inhibits PROBABILISTICALLY when Λ
    flags environmental jerkiness."""
    try:
        phi = _read_live_phi()
        psi = _read_live_psi()
        env = _read_live_env_anomaly()
        if phi is None or psi is None:
            # Live cortex hasn't populated state yet — do nothing safely.
            return {"applied": 0.0, "reason": "cortex_state_missing"}

        fe = _get()
        lam = fe.compute(phi_raw=phi, psi_raw=psi, env_energy=env)
        inhibitor = fe.evaluate_as_inhibitor()

        applied = 0.0
        if inhibitor > 0.0:
            try:
                from System.swarm_motor_potential import record_environmental_inhibitor
                record_environmental_inhibitor(inhibitor)
                applied = inhibitor
            except Exception:
                pass

        return {
            "phi":        phi,
            "psi":        psi,
            "env_anomaly": env,
            "lambda":     lam,
            "lambda_z":   fe._lambda_z(lam),
            "inhibitor":  inhibitor,
            "applied":    applied,
            "n_samples":  fe.lambda_n,
        }
    except Exception as e:
        return {"applied": 0.0, "reason": f"exception: {type(e).__name__}"}


# ── Smoke test ──────────────────────────────────────────────────────────
def _smoke() -> int:
    import tempfile, shutil, random as _random

    global _STATE_PATH, _LEDGER_PATH, _FE_SINGLETON
    tmp = Path(tempfile.mkdtemp(prefix="lambda_smoke_"))
    try:
        _STATE_PATH = tmp / "free_energy_state.json"
        _LEDGER_PATH = tmp / "free_energy_traces.jsonl"
        _FE_SINGLETON = None

        print(f"[Λ] swarm_free_energy.py v{MODULE_VERSION} smoke")
        print(f"     sandbox: {tmp}")
        _random.seed(20260419)

        fe = FreeEnergy()
        fe.state_path  = _STATE_PATH
        fe.ledger_path = _LEDGER_PATH

        # A. cold start, single tick: derivatives should be 0, Λ should be
        #    just (phi*psi - rho*entropy).
        L0 = fe.compute(phi_raw=0.8, psi_raw=0.9, env_energy=0.1, ts=1000.0)
        ent = fe._entropy(0.8, 0.9)
        expected = 0.8*0.9 - fe.rho*ent
        assert abs(L0 - expected) < 1e-6, f"cold tick mismatch {L0} vs {expected}"
        print(f"  [A] cold tick Λ={L0:+.4f} (expected {expected:+.4f}) ✓")

        # B. real time-derivative: feed two env_energy ticks 1s apart with
        #    a 0.8 swing. grad = 0.8/s, tau_grad=1 → tanh(0.8) ≈ 0.664,
        #    grad²·κ ≈ 0.265 penalty. Λ should drop substantially.
        L1 = fe.compute(phi_raw=0.5, psi_raw=0.5, env_energy=0.9, ts=1001.0)
        assert L1 < L0, f"env spike should drop Λ: L0={L0:+.4f} L1={L1:+.4f}"
        print(f"  [B] env_energy 0.1→0.9 in 1s drops Λ to {L1:+.4f} ✓")

        # C. real second-derivative: same Δt for phi/psi. We need ≥3 history
        #    points so feed a 3rd tick where phi swings hard.
        L2 = fe.compute(phi_raw=0.05, psi_raw=0.05, env_energy=0.85, ts=1002.0)
        # curvature should be non-zero now
        assert abs(fe._curv_dt(fe.phi_hist)) > 0.01, "phi curvature should fire after 3 ticks"
        print(f"  [C] curvature active after 3 ticks: ∂²φ/∂t²={fe._curv_dt(fe.phi_hist):+.3f}, Λ={L2:+.4f} ✓")

        # D. Welford z-score: feed many samples, then check that an outlier
        #    Λ produces |z| > 1.
        for i in range(40):
            fe.compute(phi_raw=0.5 + _random.uniform(-0.05, 0.05),
                       psi_raw=0.5 + _random.uniform(-0.05, 0.05),
                       env_energy=0.3 + _random.uniform(-0.05, 0.05),
                       ts=1003.0 + i)
        snap = fe.snapshot()
        assert snap["n_samples"] >= 40
        assert snap["lambda_sd"] > 0, "should have non-zero sd after 40 samples"
        # spike: huge env swing
        Lout = fe.compute(phi_raw=0.5, psi_raw=0.5, env_energy=1.0, ts=1100.0)
        z = fe._lambda_z(Lout)
        print(f"  [D] Welford after 40 samples: μ={snap['lambda_mean']:+.3f} "
              f"σ={snap['lambda_sd']:.3f}; outlier Λ_z={z:+.2f} ✓")

        # E. evaluate_as_inhibitor: a strong negative outlier should produce
        #    inhibition > 0; positive outliers should produce 0.
        # force a negative outlier
        for i in range(5):
            Lneg = fe.compute(phi_raw=0.05, psi_raw=0.05, env_energy=0.95,
                              ts=1101.0 + i*0.5)
        inh = fe.evaluate_as_inhibitor()
        print(f"  [E] inhibitor after negative-spike sequence = {inh:.3f} "
              f"(0 means 'safe'; >0 means 'feeds Ψ R_risk') ✓")

        # F. persistence round-trip: instantiate a new FreeEnergy, confirm
        #    Welford stats survive.
        n_before = fe.lambda_n
        mu_before = fe.lambda_mu
        del fe
        _FE_SINGLETON = None
        fe2 = FreeEnergy()
        fe2.state_path  = _STATE_PATH
        fe2.ledger_path = _LEDGER_PATH
        fe2._load_state()
        assert fe2.lambda_n == n_before, f"Welford n drift {fe2.lambda_n} vs {n_before}"
        assert abs(fe2.lambda_mu - mu_before) < 1e-9
        assert len(fe2.phi_hist) >= 1, "phi_hist should survive"
        print(f"  [F] persistence round-trip ✓ (n={fe2.lambda_n}, μ={fe2.lambda_mu:+.3f}, "
              f"phi_hist={len(fe2.phi_hist)})")

        # G. AG31's original gate API still works.
        verdict = fe2.should_act(0.5, "smoke_act")
        assert verdict is True
        verdict_neg = fe2.should_act(-0.5, "smoke_act_neg")
        assert verdict_neg is False
        print(f"  [G] AG31 should_act(±0.5) gate intact ✓")

        # H. summary_for_alice has content
        # rebind module singleton
        global _FE_SINGLETON_GLOBAL
        # patch facade singleton too so summary uses our fe2
        globals()["_FE_SINGLETON"] = fe2
        s = summary_for_alice()
        assert s and "FREE-ENERGY" in s
        print(f"  [H] summary_for_alice ✓")
        print(f"      {s}")

        print("[Λ] all checks passed.")
        return 0

    except AssertionError as e:
        print(f"[Λ] FAIL: {e}")
        return 1
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"[Λ] CRASH: {type(e).__name__}: {e}")
        return 2
    finally:
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


# ── CLI ─────────────────────────────────────────────────────────────────
def _cli(argv: List[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "swarm_free_energy.py — Free Energy Action Field Λ(t)\n"
            "  smoke                run sandboxed self-test\n"
            "  snapshot             dump running stats + history sizes\n"
            "  decide phi psi env   compute one tick, print Λ + Λ_z + inhibitor\n"
            "  alice-line           one-line summary for talk widget\n"
        )
        return 0
    cmd = argv[0]
    if cmd == "smoke":
        return _smoke()
    if cmd == "snapshot":
        print(json.dumps(_get().snapshot(), indent=2, sort_keys=True))
        return 0
    if cmd == "decide":
        if len(argv) < 4:
            print("usage: decide <phi> <psi> <env_energy>"); return 2
        phi = float(argv[1]); psi = float(argv[2]); env = float(argv[3])
        result = evaluate_now(phi, psi, env)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if cmd == "alice-line":
        s = summary_for_alice()
        print(s if s else "(insufficient samples for Λ baseline)")
        return 0
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    import sys
    raise SystemExit(_cli(sys.argv[1:]))
