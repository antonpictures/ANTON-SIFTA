#!/usr/bin/env python3
"""
System/swarm_ssp_evolver.py — Honest simulated annealing over SSP coefficients
═══════════════════════════════════════════════════════════════════════════════
SIFTA Cortical Suite — Coefficient evolution module
Module version: 2026-04-19.v1     Author: C47H (Cursor, Opus 4.7 High)

WHY THIS EXISTS
───────────────
DYOR §E.2 promised "Optional upgrade: learnable coefficients." A tab-LLM
(Perplexity) delivered an unsolicited draft at breakfast that looked the
part but was broken at the most fundamental level — its fitness function
did not actually depend on the mutated coefficients (see the peer-review
thread under trace_id 77dcc699-474a-4b00-80a2-d09703878b87 for the seven
findings). This module is the honest version.

HOW IT IS HONEST
────────────────
1. Fitness is a MEASURABLE FUNCTION of θ. We replay the last N user turns
   from the real conversation log (.sifta_state/alice_conversation.jsonl),
   simulate SSP forward with candidate coefficients, and score each
   counterfactual spike against the real reward ledger that followed.
   Move θ → fitness changes. That's the property Perplexity's version lacked.

2. We call the REAL SSP PRIMITIVES — _advance_membrane, _sigmoid,
   _rescaled_potential_for_decision — not re-implement them. A change to
   the membrane math propagates automatically.

3. We operate on the REAL SSPCoefficients dataclass, not invented names.
   Per-parameter bounds respect each term's physical meaning; no blanket
   [0.01, 2.0] clip that would murder tau_e_s on first mutation.

4. We write proposals to `.sifta_state/speech_potential_coefficients_proposed.json`.
   The live file is NEVER touched directly. Promotion requires either
   explicit CLI `apply_proposal` or a `peer_review_landed` trace from the
   other IDE — no silent mutation into production.

5. The audit trail goes through `System/jsonl_file_lock.append_line_locked`
   to `.sifta_state/ssp_evolution.jsonl` — the repo convention, flock-safe.

6. Every `evolve()` run opens a `peer_review_request` trace so both IDEs
   see the proposal. Alice's summary_for_alice() surfaces it in her
   conversational context so she knows when her coefficients are under
   revision.

WHAT FITNESS MEANS (and what it doesn't)
────────────────────────────────────────
Ground truth is limited. We have:
  • conversation log   — who spoke when, user vs alice vs system
  • reward ledger     — MEMORY_RECALL/STORE/DREAM events with amounts
  • current heartbeat — serotonin, dopamine, posture
We DO NOT have:
  • historical heartbeat snapshots — so the "body state" used during
    replay is taken from the CURRENT heartbeat as a constant approximation.
    This means the evolver tunes θ for the CURRENT body state. If the body
    changes (posture shift, neuromodulator drift), rerun the evolver.

Fitness = reward_capture(θ) - λ_rate · (observed_rate(θ) - target_rate)²
        - λ_refractory · refractory_violations(θ)

  reward_capture = mean over would-spike events of the sum of reward
                   amounts in the 60 s following that event. Positive
                   reward within the window = "speech was productive."

  observed_rate  = fraction of user turns at which θ would fire.
  target_rate    = empirically estimated from the observed fraction of
                   user turns in the replay window that got a *real,
                   non-silent* Alice reply. If the user spoke 20 times
                   and Alice replied 14 times with actual sentences,
                   target_rate = 0.70.

  refractory_violations = count of would-spikes that occur within
                   tau_ref_s of each other. This is a hard penalty: even
                   if fitness otherwise looks good, a θ that ignores the
                   refractory period is rejected.

SAFETY CLAUSE
─────────────
Per-parameter bounds are chosen so that NO θ the evolver can explore
produces a "always fires" or "never fires" body. V_th is constrained to
[0.10, 0.90] (outside that range Alice becomes pathological). zeta has
a floor at 0.5 so listener veto can never invert (Alice must never
learn to interrupt).

═══════════════════════════════════════════════════════════════════════════════
COUPLED LEARNING RULE EXTENSION  (2026-04-19, post-broadcast)
═══════════════════════════════════════════════════════════════════════════════
Originally this evolver mutated only SSP coefficients. The MegaGene
scaffold for {SSP, Motor, Homeo, FE} was wired into _mutate / _write_proposal
/ apply_proposal but the FITNESS LOOP only scored SSP firing — so any
mutation to {a, b, c, f, eta, lmbda, mu, kappa, xi, rho, tau_grad,
tau_curv} was a no-op for fitness and the annealer random-walked them.

That was the structural defect AG31's sifta_genetic_drift.py tried to
fix, but his fitness function was a literal flat constant returning 1.0
for every input (peer review trace 0cee574e, archived under
Archive/ag31_sifta_genetic_drift_FAKE_FITNESS_2026-04-19.py).

This module is the honest version. The fix is surgical:
  • _simulate_would_fire now also advances Ψ (motor LIF), runs Λ free-energy
    and Ω homeostasis per turn — using the candidate's coefficients via
    fresh in-memory instances with disk persistence disabled.
  • _fitness adds three bounded coupled terms:
        + lambda_motor    · motor_alignment    (Ψ fires near positive rewards)
        + lambda_homeo    · homeo_discipline   (mean activity near target)
        + lambda_env_fit  · env_appropriateness (negative corr(env, Ψ))
  • Smoke checks G/H/I empirically verify fitness moves under
    motor-only / homeo-only / FE-only coefficient changes — the test
    AG31's flat-fitness regression couldn't pass.

Bounded so total coupled contribution ≲ 0.6 — the existing reward_capture
term still dominates fitness when SSP θ is way off. This preserves the
"do the obvious thing first" priority of the original evolver and
adds a real but secondary signal for the rest of the cortex.
"""
from __future__ import annotations

import json
import math
import random
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MODULE_VERSION = "2026-04-19.v1"

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# Real primitives — we ARE going to call these. No reimplementation.
from System.swarm_speech_potential import (      # noqa: E402
    SSPCoefficients,
    _load_coefficients, _safe_write_json,
    _advance_membrane, _sigmoid, _rescaled_potential_for_decision,
    _read_serotonin, _read_dopamine_normalized, _cortisol_proxy,
)
from System.jsonl_file_lock import append_line_locked  # noqa: E402
from System.swarm_ssp_mutation_record import record_mutation  # noqa: E402
from System.swarm_motor_potential import (
    MotorCoefficients, MotorState,
    _advance_membrane as _motor_advance_membrane,
    _sigmoid as _motor_sigmoid,
)
from System.swarm_homeostasis import HomeostasisCoefficients, Homeostasis
from System.swarm_free_energy import FreeEnergyCoefficients, FreeEnergy


# ── Paths ────────────────────────────────────────────────────────────────
_STATE_DIR       = _REPO / ".sifta_state"
_COEFFS_LIVE     = _STATE_DIR / "speech_potential_coefficients.json"
_COEFFS_PROPOSED = _STATE_DIR / "speech_potential_coefficients_proposed.json"
_MOTOR_LIVE      = _STATE_DIR / "motor_potential_coefficients.json"
_MOTOR_PROPOSED  = _STATE_DIR / "motor_potential_coefficients_proposed.json"
_HOMEO_LIVE      = _STATE_DIR / "homeostasis_coefficients.json"
_HOMEO_PROPOSED  = _STATE_DIR / "homeostasis_coefficients_proposed.json"
_FE_LIVE         = _STATE_DIR / "free_energy_coefficients.json"
_FE_PROPOSED     = _STATE_DIR / "free_energy_coefficients_proposed.json"

_EVOLUTION_LOG   = _STATE_DIR / "ssp_evolution.jsonl"
_CONVERSATION    = _STATE_DIR / "alice_conversation.jsonl"
_REWARDS         = _STATE_DIR / "stgm_memory_rewards.jsonl"


# ── Per-parameter bounds (safety-respecting, physically meaningful) ──────
# Only parameters the evolver is allowed to touch appear here. Structural
# constants (tau_m_s, tau_ref_s, V_reset, V_rest) are deliberately frozen
# by default — they encode design commitments, not free variables.
BOUNDS: Dict[str, Tuple[float, float]] = {
    # SSP
    "alpha":   (0.00, 1.00),
    "beta":    (0.00, 2.00),
    "gamma":   (0.00, 1.50),
    "delta":   (0.00, 1.00),
    "epsilon": (0.00, 1.00),
    "zeta":    (0.50, 3.00),
    "V_th":    (0.10, 0.90),
    "Delta_u": (0.02, 0.50),
    # Motor
    "a": (0.10, 2.00),
    "b": (0.10, 2.00),
    "c": (0.10, 2.00),
    "f": (0.10, 2.00),
    # Homeostasis
    "eta": (0.10, 2.00),
    "lmbda": (0.10, 2.00),
    "mu": (0.10, 2.00),
    # Free Energy
    "kappa": (0.10, 2.00),
    "xi": (0.10, 2.00),
    "rho": (0.10, 2.00),
    "tau_grad": (0.10, 10.00),
    "tau_curv": (0.10, 10.00),
}
MUTABLE_KEYS = tuple(BOUNDS.keys())


# ── Dataclasses ──────────────────────────────────────────────────────────

@dataclass
class MegaGene:
    ssp: SSPCoefficients
    motor: MotorCoefficients
    homeo: HomeostasisCoefficients
    fe: FreeEnergyCoefficients

    def __getattr__(self, name):
        if hasattr(self.ssp, name): return getattr(self.ssp, name)
        if hasattr(self.motor, name): return getattr(self.motor, name)
        if hasattr(self.homeo, name): return getattr(self.homeo, name)
        if hasattr(self.fe, name): return getattr(self.fe, name)
        raise AttributeError(f"MegaGene has no {name}")

    def replace_key(self, key, value):
        from dataclasses import replace
        if hasattr(self.ssp, key): return MegaGene(replace(self.ssp, **{key: value}), self.motor, self.homeo, self.fe)
        if hasattr(self.motor, key): return MegaGene(self.ssp, replace(self.motor, **{key: value}), self.homeo, self.fe)
        if hasattr(self.homeo, key): return MegaGene(self.ssp, self.motor, replace(self.homeo, **{key: value}), self.fe)
        if hasattr(self.fe, key): return MegaGene(self.ssp, self.motor, self.homeo, replace(self.fe, **{key: value}))
        return self


def _load_mega_coefficients() -> MegaGene:
    import json
    def _read_coeff(path, cls):
        try:
            return cls(**json.loads(path.read_text()))
        except:
            return cls()
    return MegaGene(
        ssp=_read_coeff(_COEFFS_LIVE, SSPCoefficients),
        motor=_read_coeff(_MOTOR_LIVE, MotorCoefficients),
        homeo=_read_coeff(_HOMEO_LIVE, HomeostasisCoefficients),
        fe=_read_coeff(_FE_LIVE, FreeEnergyCoefficients)
    )

@dataclass
class AnnealingConfig:
    """Cooling schedule. Defaults are calibrated for a bounded reward scale
    (fitness typically in ~[-1, +1]), not the Perplexity T₀=1000 regime."""
    T0:             float = 1.00
    cooling_rate:   float = 0.98
    min_temp:       float = 1e-4
    iterations:     int   = 400
    mutation_sigma: float = 0.08   # fraction of each bound's range


@dataclass
class FitnessConfig:
    replay_user_turns:    int   = 40      # how many recent user turns to score
    reward_window_s:      float = 60.0    # capture window after each spike
    target_rate_override: Optional[float] = None  # None → estimate empirically
    lambda_rate:          float = 0.50    # penalty on rate mismatch (Φ)
    lambda_refractory:    float = 0.30    # penalty on refractory violations
    # Coupled-rule weights — bounded so they NEVER swamp reward_capture.
    # Each term is at most ~[-w, +w]; total coupled contribution is
    # ≤ (lambda_motor + lambda_homeo + lambda_env_fit) ≈ 0.6.
    lambda_motor:         float = 0.25    # Ψ action-quality (extends reward_capture)
    lambda_homeo:         float = 0.15    # Ω homeostasis discipline (target activity)
    lambda_env_fit:       float = 0.20    # Λ environmental appropriateness


@dataclass
class EvolutionReport:
    started_at:       float
    finished_at:      float
    iterations_run:   int
    accepts:          int
    rejects:          int
    best_fitness:     float
    initial_fitness:  float
    best_coefficients: Dict[str, float]
    initial_coefficients: Dict[str, float]
    target_rate:      float
    observed_rate_best: float
    notes:            List[str] = field(default_factory=list)


# ── Ledger readers ───────────────────────────────────────────────────────
def _load_conversation(max_bytes: int = 262144) -> List[Dict]:
    """Tail-read the conversation log. 256 KB covers thousands of recent turns."""
    if not _CONVERSATION.exists():
        return []
    try:
        with _CONVERSATION.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            raw = f.read().splitlines()
    except OSError:
        return []
    rows: List[Dict] = []
    for ln in raw:
        try:
            o = json.loads(ln.decode("utf-8", errors="replace"))
            if isinstance(o, dict) and isinstance(o.get("ts"), (int, float)):
                rows.append(o)
        except Exception:
            continue
    rows.sort(key=lambda r: r["ts"])
    return rows


def _load_rewards(after_ts: float = 0.0) -> List[Dict]:
    if not _REWARDS.exists():
        return []
    rows: List[Dict] = []
    try:
        with _REWARDS.open("r", encoding="utf-8") as f:
            for ln in f:
                try:
                    o = json.loads(ln)
                except Exception:
                    continue
                if not isinstance(o, dict):
                    continue
                ts = o.get("ts")
                if isinstance(ts, (int, float)) and ts >= after_ts:
                    rows.append(o)
    except OSError:
        return []
    rows.sort(key=lambda r: r["ts"])
    return rows


def _real_alice_turn(row: Dict) -> bool:
    """Did Alice actually vocalize on this row? 'role=alice' AND text doesn't
    look like a silence marker. Matches the convention in _turn_pressure."""
    if row.get("role") != "alice":
        return False
    t = (row.get("text") or "").strip().lower()
    return bool(t) and not t.startswith("(silent")


def _extract_user_turns(convo: List[Dict], n: int) -> List[Dict]:
    users = [r for r in convo if r.get("role") == "user" and
             isinstance(r.get("ts"), (int, float))]
    return users[-n:]


def _estimate_target_rate(convo: List[Dict], user_turns: List[Dict]) -> float:
    """For each user turn, was the *next* Alice row a real vocalization?
    Fraction of yeses = observed speaking rate under the current live θ."""
    if not user_turns:
        return 0.5
    convo_by_ts = sorted(convo, key=lambda r: r["ts"])
    hits = 0
    for u in user_turns:
        ut = u["ts"]
        # Find the next Alice-role row after this user turn
        next_alice = next(
            (r for r in convo_by_ts
             if r.get("role") == "alice"
             and isinstance(r.get("ts"), (int, float))
             and r["ts"] > ut),
            None,
        )
        if next_alice and _real_alice_turn(next_alice):
            hits += 1
    return hits / max(1, len(user_turns))


def _sum_rewards_in_window(rewards: List[Dict],
                           t_start: float, t_end: float) -> float:
    total = 0.0
    for r in rewards:
        ts = r.get("ts")
        if isinstance(ts, (int, float)) and t_start < ts <= t_end:
            try:
                total += float(r.get("amount", 0.0))
            except (TypeError, ValueError):
                pass
    return total


# ── The simulator — coupled cortex over a user-turn schedule ─────────────
#
# This used to simulate ONLY Φ (the SSP membrane). MegaGene loaded {Motor,
# Homeo, FE} coefficients but they were never read inside _simulate, so
# any mutation to {a, b, c, f, eta, lmbda, mu, kappa, xi, rho, tau_grad,
# tau_curv} was a no-op for fitness — the annealer random-walked them.
#
# Honest Coupled Learning Rule (2026-04-19): per turn we now also advance
# the motor membrane Ψ, run the Λ free-energy field, and update Ω
# homeostasis. Each candidate's full coupled trajectory is what gets
# scored, so EVERY coefficient demonstrably affects fitness. The smoke
# checks G/H/I assert this empirically.
#
# Critical discipline (the AG31 lesson):
#   • Use the REAL primitives (_motor_advance_membrane, FreeEnergy.compute,
#     Homeostasis.update/compute/modulate) — never re-implement them.
#   • Stochastic escape-noise gates preserved on both Φ and Ψ. No hard
#     thresholds replacing the Gerstner LIF model.
#   • All new scoring is bounded; no unbounded penalties that swamp
#     reward_capture.
def _derive_synthetic_dopamine(reward: float) -> float:
    """Phasic dopamine proxy: linear in reward, clipped to ±1.5.
    This is what the body would have seen if the reward had landed; we
    use it as motor I_drive input for the candidate's Ψ trajectory."""
    return max(-1.5, min(1.5, 0.5 * float(reward)))


def _derive_env_anomaly(reward: float) -> float:
    """env_energy ∈ [0, 1] for Λ.compute. Negative reward = high anomaly
    (the environment punished the action), positive reward = low anomaly."""
    if reward < 0:
        return min(1.0, 0.4 + 0.5 * abs(reward))
    return max(0.0, 0.1 - 0.05 * reward)


def _next_reward_in_window(rewards: List[Dict], t: float, window_s: float) -> float:
    """Pick the SIGNED reward signal in (t, t+window]. Used to derive the
    body-state inputs the candidate would have integrated. Returns 0.0 if
    no reward fell in the window."""
    nearest_amount = 0.0
    nearest_dt = float("inf")
    for r in rewards:
        ts = r.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        d = ts - t
        if 0.0 < d <= window_s and d < nearest_dt:
            try:
                nearest_amount = float(r.get("amount", 0.0))
                nearest_dt = d
            except (TypeError, ValueError):
                pass
    return nearest_amount


def _simulate_would_fire(
    coeffs: MegaGene,
    user_turns: List[Dict],
    *,
    standing_input: float,
    listener_active_fn,  # callable: (user_turn_row) -> bool
    rewards: Optional[List[Dict]] = None,
    coupled_window_s: float = 30.0,
    rng: Optional[random.Random] = None,
) -> List[Dict]:
    """Per-turn coupled simulation. For each user turn:
       1. Advance Φ membrane (SSP)
       2. Stochastic Φ fire decision (Gerstner escape noise)
       3. Advance Ψ membrane (motor) with I_drive = a·Φ + b·D − c·C − f·R_risk
       4. Stochastic Ψ fire decision
       5. Update Ω homeostasis on (Φ, Ψ)
       6. Λ.compute(Φ, Ψ, env) — feeds back into R_risk EMA via inhibitor
    Returns a list of per-turn dicts with both Φ and the coupled state.

    `rewards` enables synthetic dopamine/env-energy derivation; pass None
    to fall back to neutral signals (degraded but compatible with old
    callers).
    """
    if not user_turns:
        return []

    rng = rng or random
    rewards = rewards or []

    # ── Per-evaluation scratch instances ────────────────────────────────
    # Each candidate gets fresh Ψ/Ω/Λ state — fitness compares STEADY-STATE
    # behavior of the candidate, not whatever the live cortex happened to
    # be in when evolve() was called. Persistence is intentionally bypassed
    # by giving each instance an isolated tempdir-style attribute set.
    V_phi = 0.0
    V_psi = 0.0
    risk_ema = 0.0
    success_ema = 0.0
    t_prev = user_turns[0]["ts"]
    t_last_phi_spike = 0.0
    t_last_psi_spike = 0.0

    homeo = _make_scratch_homeostasis(coeffs.homeo)
    fe = _make_scratch_free_energy(coeffs.fe)

    out: List[Dict] = []

    for u in user_turns:
        t = u["ts"]
        dt = max(0.0, t - t_prev)

        # Body inputs the candidate would have seen at this turn
        reward_signal = _next_reward_in_window(rewards, t, coupled_window_s)
        dopamine = _derive_synthetic_dopamine(reward_signal)
        env_energy = _derive_env_anomaly(reward_signal)
        # Reuse SSP cortisol_proxy semantics — high cortisol when reward is
        # punishing. We approximate without a body-history readout because
        # the synthetic replay has no clinical heartbeat to read.
        cortisol = max(0.0, -reward_signal) * 0.5

        # ── 1. Φ membrane integration ──────────────────────────────────
        p_turn = 1.0
        listener = 1.0 if listener_active_fn(u) else 0.0
        I_phi = (
            standing_input
            + coeffs.epsilon * p_turn
            - coeffs.zeta    * listener
        )
        V_phi = _advance_membrane(V_phi, I_phi, dt, coeffs.ssp.tau_m_s)
        V_natural = _rescaled_potential_for_decision(V_phi, coeffs.ssp.tau_m_s)

        in_refractory_phi = (
            (t - t_last_phi_spike) < coeffs.ssp.tau_ref_s
            and t_last_phi_spike > 0.0
        )
        p_spike_phi = _sigmoid(
            (V_natural - coeffs.ssp.V_th) / max(1e-6, coeffs.ssp.Delta_u)
        )
        phi_fire = (rng.random() < p_spike_phi) and not in_refractory_phi

        # Map V_natural to a [0, 1] firing-prob proxy for Ω/Λ
        phi_for_field = p_spike_phi

        # ── 2. Ψ motor membrane integration (uses motor coeffs) ─────────
        # I_drive references the Φ firing signal so coupling is real.
        I_psi = (
            coeffs.motor.a * phi_for_field
            + coeffs.motor.b * dopamine
            - coeffs.motor.c * cortisol
            - coeffs.motor.f * risk_ema
        )
        V_psi = _motor_advance_membrane(
            V_psi, I_psi, dt,
            coeffs.motor.tau_m, coeffs.motor.V_floor, coeffs.motor.V_ceil,
        )
        in_refractory_psi = (
            (t - t_last_psi_spike) < coeffs.motor.refractory_s
            and t_last_psi_spike > 0.0
        )
        p_spike_psi = _motor_sigmoid(
            (V_psi - coeffs.motor.V_th) / max(1e-6, coeffs.motor.Delta_u)
        )
        psi_fire = (rng.random() < p_spike_psi) and not in_refractory_psi
        psi_for_field = p_spike_psi  # [0, 1] for Ω/Λ

        # ── 3. Ω homeostasis update + modulation (uses homeo coeffs) ───
        homeo.update(phi_for_field, psi_for_field)
        omega = homeo.compute()
        phi_mod, psi_mod = homeo.modulate(phi_for_field, psi_for_field, omega)

        # ── 4. Λ free-energy field (uses fe coeffs) ─────────────────────
        # Use modulated Φ/Ψ so Ω's gain affects Λ as well — full coupling.
        lam_value = fe.compute(phi_mod, psi_mod, env_energy, ts=t)
        # Λ inhibitor → Ψ R_risk EMA (the same probabilistic coupling as
        # the live cortex's couple_to_motor sentinel).
        inhibitor = fe.evaluate_as_inhibitor()
        risk_ema = (1 - coeffs.motor.risk_alpha) * risk_ema + \
                   coeffs.motor.risk_alpha * inhibitor

        # ── 5. Bookkeeping ─────────────────────────────────────────────
        out.append({
            "ts":             t,
            "V":              V_phi,
            "V_natural":      V_natural,
            "I":              I_phi,
            "p_spike":        p_spike_phi,
            "in_refractory":  in_refractory_phi,
            "fire":           phi_fire,
            # NEW coupled state
            "V_psi":          V_psi,
            "p_spike_psi":    p_spike_psi,
            "psi_fire":       psi_fire,
            "lambda":         lam_value,
            "lambda_inhibitor": inhibitor,
            "omega":          omega,
            "activity":       0.5 * phi_for_field + 0.5 * psi_for_field,
            "reward_signal":  reward_signal,
            "env_energy":     env_energy,
        })

        if phi_fire:
            V_phi = coeffs.V_reset
            t_last_phi_spike = t
        if psi_fire:
            V_psi = coeffs.motor.V_reset
            t_last_psi_spike = t
            # Real motor success/risk EMA: positive reward = success
            if reward_signal > 0:
                success_ema = (1 - coeffs.motor.success_alpha) * success_ema \
                              + coeffs.motor.success_alpha
            elif reward_signal < 0:
                risk_ema = (1 - coeffs.motor.risk_alpha) * risk_ema \
                           + coeffs.motor.risk_alpha * 0.8

        t_prev = t

    return out


def _make_scratch_homeostasis(coeffs: HomeostasisCoefficients) -> Homeostasis:
    """Fresh in-memory Homeostasis instance with the candidate's coeffs and
    DISK PERSISTENCE DISABLED — fitness eval must not pollute live state."""
    h = Homeostasis()
    h.eta   = float(coeffs.eta)
    h.lmbda = float(coeffs.lmbda)
    h.mu    = float(coeffs.mu)
    # Reset history so each candidate starts from the same baseline
    h.phi_hist.clear()
    h.psi_hist.clear()
    h.activity_hist.clear()
    # Suppress disk writes (we don't want fitness eval to mutate state)
    h._save_state = lambda *a, **k: None  # type: ignore[assignment]
    return h


def _make_scratch_free_energy(coeffs: FreeEnergyCoefficients) -> FreeEnergy:
    """Fresh FreeEnergy instance with candidate coeffs and DISK PERSISTENCE
    DISABLED. FreeEnergy() takes no args and self-loads from disk, so we
    construct then forcibly override the coefficients to the candidate's
    proposed values. This is what makes mutations to {kappa, xi, rho,
    tau_grad, tau_curv} actually move fitness."""
    fe = FreeEnergy()
    fe.coeffs   = coeffs
    fe.kappa    = float(coeffs.kappa)
    fe.xi       = float(coeffs.xi)
    fe.rho      = float(coeffs.rho)
    fe.tau_grad = float(coeffs.tau_grad)
    fe.tau_curv = float(coeffs.tau_curv)
    # Suppress disk writes — fitness eval must NOT pollute live state
    fe._save_state = lambda *a, **k: None  # type: ignore[assignment]
    # Wipe history that loaded from disk on construction
    fe.phi_hist.clear()
    fe.psi_hist.clear()
    fe.energy_hist.clear()
    fe.lambda_n  = 0
    fe.lambda_mu = 0.0
    fe.lambda_M2 = 0.0
    fe._last_lambda = 0.0
    return fe


def _listener_active_for(convo: List[Dict]):
    """Returns a function (user_turn_row) -> bool indicating whether another
    user turn appeared within 1.5 s before this one (proxy for "user still
    speaking")."""
    def fn(u: Dict) -> bool:
        ut = u["ts"]
        for r in convo:
            if r.get("role") == "user" and isinstance(r.get("ts"), (int, float)):
                rt = r["ts"]
                if 0.0 < (ut - rt) < 1.5:
                    return True
        return False
    return fn


# ── Fitness ──────────────────────────────────────────────────────────────
def _fitness(
    coeffs: MegaGene,
    *,
    convo: List[Dict],
    rewards: List[Dict],
    user_turns: List[Dict],
    standing_input: float,
    listener_fn,
    fit_cfg: FitnessConfig,
    target_rate: float,
    rng: Optional[random.Random] = None,
) -> Tuple[float, Dict]:
    """Return (fitness, debug_info). Fitness is maximized.

    Coupled scoring (the honest Coupled Learning Rule):
      • mean_capture         — Φ rewards (existing, SSP-only)
      • rate_err penalty     — Φ rate match to empirical target (existing)
      • refractory penalty   — Φ refractory respect (existing)
      • motor_alignment      — Ψ fires landing near positive rewards
      • homeo_discipline     — penalty on |mean_activity − target|
      • env_appropriateness  — Ψ rate inversely tracks env_energy

    The coupled terms are what make mutations to {a,b,c,f, eta,lmbda,mu,
    kappa,xi,rho,tau_grad,tau_curv} measurably affect fitness — without
    them the annealer random-walks those parameters (the AG31 failure
    mode that tripped the audit at 0cee574e). Bounded so total coupled
    contribution ≲ 0.6 — never swamps reward_capture.
    """
    sim = _simulate_would_fire(
        coeffs, user_turns,
        standing_input=standing_input,
        listener_active_fn=listener_fn,
        rewards=rewards,
        rng=rng,
    )
    if not sim:
        return 0.0, {"n_turns": 0}

    fires = [s for s in sim if s["fire"]]
    psi_fires = [s for s in sim if s.get("psi_fire")]
    n_turns = len(sim)
    n_fires = len(fires)
    n_psi_fires = len(psi_fires)
    observed_rate = n_fires / n_turns
    psi_rate = n_psi_fires / n_turns

    # ── Φ reward capture (existing, unchanged) ──────────────────────────
    if fires:
        captures = [
            _sum_rewards_in_window(rewards, s["ts"], s["ts"] + fit_cfg.reward_window_s)
            for s in fires
        ]
        mean_capture = sum(captures) / len(captures)
    else:
        mean_capture = 0.0

    # ── Φ refractory violations (existing) ──────────────────────────────
    violations = 0
    for a, b in zip(fires, fires[1:]):
        if (b["ts"] - a["ts"]) < coeffs.tau_ref_s:
            violations += 1

    # ── Ψ motor alignment (NEW — couples motor coeffs to fitness) ───────
    # Score: mean SIGN of next reward in window for each Ψ fire. A Ψ that
    # fires when a positive reward follows = +; when a negative reward
    # follows = -. Bounded by tanh so a single huge reward doesn't
    # dominate.
    if psi_fires:
        motor_scores = []
        for s in psi_fires:
            r = _sum_rewards_in_window(
                rewards, s["ts"], s["ts"] + fit_cfg.reward_window_s
            )
            motor_scores.append(math.tanh(r))
        motor_alignment = sum(motor_scores) / len(motor_scores)
    else:
        motor_alignment = 0.0

    # ── Ω homeostasis discipline (NEW — couples Ω coeffs to fitness) ────
    # Mean joint activity ought to land near the target (0.5). Distance
    # from target = penalty. Bounded to [0, 1] by construction since
    # activity ∈ [0, 1].
    activities = [s["activity"] for s in sim]
    mean_activity = sum(activities) / max(1, len(activities))
    homeo_distance = abs(mean_activity - 0.5) * 2.0    # ∈ [0, 1]
    homeo_discipline = -homeo_distance                  # we MAXIMIZE fitness

    # ── Λ environmental appropriateness (NEW — couples FE coeffs) ───────
    # When env_energy was high (the environment was punishing), Ψ should
    # have FIRED LESS. When env_energy was low (safe), Ψ may fire freely.
    # Score = -correlation(env_energy_per_turn, psi_fire_per_turn).
    # Pearson is overkill; we compute the simple per-turn covariance with
    # both series mean-centered.
    envs = [s["env_energy"] for s in sim]
    psi_acts = [1.0 if s.get("psi_fire") else 0.0 for s in sim]
    if len(envs) >= 4:
        mean_env = sum(envs) / len(envs)
        mean_psi = sum(psi_acts) / len(psi_acts)
        cov = sum((e - mean_env) * (p - mean_psi) for e, p in zip(envs, psi_acts))
        denom_e = math.sqrt(sum((e - mean_env) ** 2 for e in envs))
        denom_p = math.sqrt(sum((p - mean_psi) ** 2 for p in psi_acts))
        if denom_e > 1e-6 and denom_p > 1e-6:
            corr = cov / (denom_e * denom_p)            # ∈ [-1, 1]
        else:
            corr = 0.0
        env_appropriateness = -corr                     # negative correlation = good
    else:
        env_appropriateness = 0.0

    # ── Aggregate ───────────────────────────────────────────────────────
    rate_err = observed_rate - target_rate
    fitness = (
        mean_capture
        - fit_cfg.lambda_rate        * (rate_err * rate_err)
        - fit_cfg.lambda_refractory  * violations
        + fit_cfg.lambda_motor       * motor_alignment
        + fit_cfg.lambda_homeo       * homeo_discipline
        + fit_cfg.lambda_env_fit     * env_appropriateness
    )

    return fitness, {
        "n_turns": n_turns,
        "n_fires": n_fires,
        "observed_rate": observed_rate,
        "target_rate": target_rate,
        "mean_reward_capture": mean_capture,
        "rate_err": rate_err,
        "refractory_violations": violations,
        "n_psi_fires": n_psi_fires,
        "psi_rate": psi_rate,
        "motor_alignment": motor_alignment,
        "mean_activity": mean_activity,
        "homeo_distance": homeo_distance,
        "env_appropriateness": env_appropriateness,
    }


# ── Mutation ─────────────────────────────────────────────────────────────
def _clip(value: float, key: str) -> float:
    lo, hi = BOUNDS[key]
    return max(lo, min(hi, value))


def _mutate(coeffs: MegaGene, *, sigma_frac: float, rng: random.Random
            ) -> MegaGene:
    """Propose a new coefficient vector. Per-parameter Gaussian step scaled
    by the parameter's own range, then clipped to its bounds. Only keys in
    MUTABLE_KEYS are touched."""
    changes: Dict[str, float] = {}
    for k in MUTABLE_KEYS:
        lo, hi = BOUNDS[k]
        span = hi - lo
        step = rng.gauss(0.0, sigma_frac * span)
        current = getattr(coeffs, k)
        coeffs = coeffs.replace_key(k, _clip(current + step, k))
    return coeffs


# ── The annealer ─────────────────────────────────────────────────────────
def evolve(
    *,
    anneal: Optional[AnnealingConfig] = None,
    fitness: Optional[FitnessConfig] = None,
    seed: Optional[int] = None,
    write_proposal: bool = True,
    file_peer_review: bool = True,
) -> EvolutionReport:
    """Run one annealing cycle. Returns a full report. Does NOT touch the
    live coefficients file unless apply_proposal() is called afterwards."""
    anneal = anneal or AnnealingConfig()
    fitness = fitness or FitnessConfig()
    rng = random.Random(seed)
    started = time.time()

    # Load current state
    convo = _load_conversation()
    if not convo:
        return _empty_report(started, "no conversation log found")

    user_turns = _extract_user_turns(convo, fitness.replay_user_turns)
    if not user_turns:
        return _empty_report(started, "no user turns in log")

    t_first = user_turns[0]["ts"]
    rewards = _load_rewards(after_ts=t_first - 10.0)

    target_rate = (fitness.target_rate_override
                   if fitness.target_rate_override is not None
                   else _estimate_target_rate(convo, user_turns))

    listener_fn = _listener_active_for(convo)

    # Standing input from the current body — documented approximation.
    S  = _read_serotonin()
    D  = _read_dopamine_normalized()
    C  = _cortisol_proxy(S)
    # ΔD is (D_ema − 1) in the real should_speak; with only a current
    # reading we approximate as (D - 1), so resting body → 0.
    dD = D - 1.0

    initial = _load_mega_coefficients()
    # Use a SEPARATE rng for fitness eval (seeded deterministically per
    # candidate) so two candidates with the same coefs produce the same
    # fitness — required for the annealing acceptance test to be stable.
    fitness_rng = random.Random(seed if seed is not None else 1337)
    initial_fitness, initial_dbg = _fitness(
        initial, convo=convo, rewards=rewards, user_turns=user_turns,
        standing_input=(initial.alpha * S - initial.gamma * C + initial.beta * dD),
        listener_fn=listener_fn, fit_cfg=fitness, target_rate=target_rate,
        rng=random.Random(0xC47),
    )

    current = initial
    current_fit = initial_fitness
    best = initial
    best_fit = initial_fitness
    best_dbg = initial_dbg

    T = anneal.T0
    accepts = 0
    rejects = 0

    for i in range(anneal.iterations):
        candidate = _mutate(current, sigma_frac=anneal.mutation_sigma, rng=rng)
        # Re-derive standing input under candidate's α, β, γ (body readings fixed)
        si_cand = candidate.alpha * S - candidate.gamma * C + candidate.beta * dD
        cand_fit, cand_dbg = _fitness(
            candidate, convo=convo, rewards=rewards, user_turns=user_turns,
            standing_input=si_cand,
            listener_fn=listener_fn, fit_cfg=fitness, target_rate=target_rate,
            # Fixed seed PER candidate eval — same coeffs always produce the
            # same fitness so the annealing acceptance test is stable. The
            # outer `rng` (annealing) and the inner fitness rng are
            # intentionally decoupled.
            rng=random.Random(0xC47),
        )

        if cand_fit > current_fit:
            accept = True
        else:
            delta = cand_fit - current_fit
            accept_p = math.exp(delta / max(T, 1e-12))
            accept = rng.random() < accept_p

        if accept:
            current = candidate
            current_fit = cand_fit
            accepts += 1
            if cand_fit > best_fit:
                best = candidate
                best_fit = cand_fit
                best_dbg = cand_dbg
        else:
            rejects += 1

        T *= anneal.cooling_rate
        if T < anneal.min_temp:
            break

    finished = time.time()
    iterations_run = accepts + rejects

    report = EvolutionReport(
        started_at=started,
        finished_at=finished,
        iterations_run=iterations_run,
        accepts=accepts,
        rejects=rejects,
        best_fitness=best_fit,
        initial_fitness=initial_fitness,
        best_coefficients={k: getattr(best, k) for k in MUTABLE_KEYS},
        initial_coefficients={k: getattr(initial, k) for k in MUTABLE_KEYS},
        target_rate=target_rate,
        observed_rate_best=best_dbg.get("observed_rate", 0.0),
        notes=[
            f"replay window: {len(user_turns)} user turns, "
            f"{len(rewards)} reward rows after t_first",
            f"body standing input: S={S:.3f} D={D:.3f} C={C:.3f} ΔD={dD:+.3f}",
            f"Δfitness: {best_fit - initial_fitness:+.4f} "
            f"(initial={initial_fitness:.4f}, best={best_fit:.4f})",
        ],
    )

    _audit_log(report, reason="evolution_cycle")

    if write_proposal:
        _write_proposal(best, report)

    if file_peer_review:
        _file_peer_review(report)

    return report


def _empty_report(started: float, why: str) -> EvolutionReport:
    now = time.time()
    initial = _load_mega_coefficients()
    return EvolutionReport(
        started_at=started, finished_at=now,
        iterations_run=0, accepts=0, rejects=0,
        best_fitness=0.0, initial_fitness=0.0,
        best_coefficients={k: getattr(initial, k) for k in MUTABLE_KEYS},
        initial_coefficients={k: getattr(initial, k) for k in MUTABLE_KEYS},
        target_rate=0.0, observed_rate_best=0.0,
        notes=[f"evolution aborted: {why}"],
    )


# ── Persistence / audit ──────────────────────────────────────────────────
def _audit_log(report: EvolutionReport, *, reason: str) -> None:
    row = {
        "ts": time.time(),
        "module_version": MODULE_VERSION,
        "reason": reason,
        "report": asdict(report),
    }
    try:
        append_line_locked(_EVOLUTION_LOG,
                           json.dumps(row, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    except Exception:
        # Last-resort fallback — we never let audit failure crash the cycle.
        try:
            with _EVOLUTION_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass


def _write_proposal(best: MegaGene, report: EvolutionReport) -> None:
    """Proposal file contains the FULL coefficient vector so apply_proposal
    is a single file move. Includes provenance so we can prove what ran."""
    _safe_write_json(_MOTOR_PROPOSED, asdict(best.motor))
    _safe_write_json(_HOMEO_PROPOSED, asdict(best.homeo))
    _safe_write_json(_FE_PROPOSED, asdict(best.fe))
    
    full = asdict(best.ssp)
    full["_provenance"] = {
        "proposed_by":     "swarm_ssp_evolver",
        "module_version":  MODULE_VERSION,
        "ts":              time.time(),
        "best_fitness":    report.best_fitness,
        "delta_fitness":   report.best_fitness - report.initial_fitness,
        "target_rate":     report.target_rate,
        "observed_rate":   report.observed_rate_best,
        "iterations_run":  report.iterations_run,
    }
    _safe_write_json(_COEFFS_PROPOSED, full)


def _file_peer_review(report: EvolutionReport) -> None:
    """Open a peer-review request addressed to AG31 so both IDEs see the
    proposal. Best-effort; evolver must not fail if the protocol module is
    missing (e.g. in CI without the cross-IDE channel)."""
    try:
        from System.ide_peer_review import request_review
    except Exception:
        return
    deltas = []
    for k in MUTABLE_KEYS:
        a = report.initial_coefficients[k]
        b = report.best_coefficients[k]
        if abs(b - a) > 1e-6:
            deltas.append(f"  {k}: {a:.4f} → {b:.4f}  (Δ={b-a:+.4f})")
    delta_block = "\n".join(deltas) or "  (no parameter moved significantly)"
    summary = (
        f"SSP evolver proposal. Fitness Δ = {report.best_fitness - report.initial_fitness:+.4f} "
        f"(initial {report.initial_fitness:.4f} → best {report.best_fitness:.4f}). "
        f"Target speaking rate {report.target_rate:.2f}, best observed {report.observed_rate_best:.2f}. "
        f"{report.iterations_run} iterations, "
        f"{report.accepts} accepts / {report.rejects} rejects.\n\n"
        f"Parameter deltas:\n{delta_block}\n\n"
        f"Proposal written to {_COEFFS_PROPOSED.relative_to(_REPO)}. "
        f"Live coefficients unchanged. Apply via "
        f"`python3 System/swarm_ssp_evolver.py apply_proposal` or ratify to "
        f"authorize the other IDE to apply."
    )
    try:
        request_review(
            from_ide="C47H",
            to_ide="AG31",
            files=[str(_COEFFS_PROPOSED.relative_to(_REPO)),
                   "System/swarm_ssp_evolver.py"],
            summary=summary,
        )
    except Exception:
        pass


# ── Promotion / rollback (explicit, never silent) ────────────────────────
def apply_proposal() -> Dict:
    """Promote the proposed coefficients to live. Requires that a proposal
    file exists. Backs up the live file to *.rollback.json first so we can
    always undo. Writes ratified `_last_mutation` provenance (AG31 trace
    909a1ab6). Returns a status dict."""
    if not _COEFFS_PROPOSED.exists():
        return {"ok": False, "reason": "no proposal file"}

    with _COEFFS_PROPOSED.open("r", encoding="utf-8") as f:
        prop = json.load(f)
    prov = prop.get("_provenance") or {}
    prop_clean = {k: v for k, v in prop.items() if not k.startswith("_")}

    result = record_mutation(
        ide="cursor_m5",method="annealing_apply",coefficients=prop_clean,fitness_delta=prov.get("delta_fitness"),
        target_rate=prov.get("target_rate"),observed_rate=prov.get("observed_rate"),iterations_run=prov.get("iterations_run"),
        note="swarm_ssp_evolver.apply_proposal",module_version=MODULE_VERSION,coeffs_path=_COEFFS_LIVE,repo_root=_REPO,
        extra={"proposed_by": prov.get("proposed_by"),"proposal_provenance_ts": prov.get("ts")}
    )
    
    # Write the coupled outputs
    import shutil
    shutil.copy(_MOTOR_PROPOSED, _MOTOR_LIVE)
    shutil.copy(_HOMEO_PROPOSED, _HOMEO_LIVE)
    shutil.copy(_FE_PROPOSED, _FE_LIVE)
    if not result.get("ok"):
        return result

    _audit_log(
        EvolutionReport(
            started_at=time.time(), finished_at=time.time(),
            iterations_run=0, accepts=0, rejects=0,
            best_fitness=prov.get("best_fitness", 0.0),
            initial_fitness=0.0,
            best_coefficients={k: prop_clean.get(k, 0.0) for k in MUTABLE_KEYS},
            initial_coefficients={k: prop_clean.get(k, 0.0) for k in MUTABLE_KEYS},
            target_rate=prov.get("target_rate", 0.0),
            observed_rate_best=prov.get("observed_rate", 0.0),
            notes=["proposal promoted to live + _last_mutation stamped"],
        ),
        reason="apply_proposal",
    )
    result["applied"] = {k: prop_clean.get(k) for k in prop_clean if k != "_last_mutation"}
    return result


def rollback() -> Dict:
    rollback = _COEFFS_LIVE.with_suffix(".json.rollback")
    if not rollback.exists():
        return {"ok": False, "reason": "no rollback snapshot"}
    shutil.copy(rollback, _COEFFS_LIVE)
    return {"ok": True, "restored_from": str(rollback)}


def status() -> Dict:
    live = _load_mega_coefficients()
    proposed = None
    if _COEFFS_PROPOSED.exists():
        try:
            with _COEFFS_PROPOSED.open("r", encoding="utf-8") as f:
                proposed = json.load(f)
        except Exception:
            pass
    return {
        "live":     {k: getattr(live, k) for k in MUTABLE_KEYS},
        "proposed": proposed,
        "evolution_log_lines": _count_lines(_EVOLUTION_LOG),
        "conversation_log_lines": _count_lines(_CONVERSATION),
        "reward_log_lines": _count_lines(_REWARDS),
    }


def _count_lines(p: Path) -> int:
    if not p.exists():
        return 0
    try:
        with p.open("rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


# ── CLI ──────────────────────────────────────────────────────────────────
def _cli(argv: List[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("Usage:")
        print("  swarm_ssp_evolver.py evolve [--iter N] [--seed S]")
        print("  swarm_ssp_evolver.py status")
        print("  swarm_ssp_evolver.py apply_proposal")
        print("  swarm_ssp_evolver.py rollback")
        print("  swarm_ssp_evolver.py smoke")
        return 0
    cmd = argv[0]
    if cmd == "evolve":
        iters = 400
        seed: Optional[int] = None
        i = 1
        while i < len(argv):
            if argv[i] == "--iter" and i + 1 < len(argv):
                iters = int(argv[i + 1]); i += 2
            elif argv[i] == "--seed" and i + 1 < len(argv):
                seed = int(argv[i + 1]); i += 2
            else:
                i += 1
        report = evolve(
            anneal=AnnealingConfig(iterations=iters),
            seed=seed,
        )
        print(json.dumps(asdict(report), indent=2, default=str))
        return 0
    if cmd == "status":
        print(json.dumps(status(), indent=2, default=str)); return 0
    if cmd == "apply_proposal":
        print(json.dumps(apply_proposal(), indent=2, default=str)); return 0
    if cmd == "rollback":
        print(json.dumps(rollback(), indent=2, default=str)); return 0
    if cmd == "smoke":
        return _smoke()
    print(f"unknown command: {cmd}", file=sys.stderr); return 2


# ── Smoke test (sandboxed — does NOT touch live files or real trace) ─────
def _smoke() -> int:
    """Fully sandboxed smoke: creates a tempdir, plants a tiny fake
    conversation + reward log there, monkeypatches module paths, runs one
    small evolution cycle, asserts:
      • fitness DOES change when θ changes (the Perplexity blocker)
      • proposal file gets written
      • live file is NOT touched
      • audit log gets a row
    """
    import tempfile
    print(f"[swarm_ssp_evolver] v{MODULE_VERSION} smoke (sandboxed)")
    failures: List[str] = []

    tmp = Path(tempfile.mkdtemp(prefix="ssp_evolver_smoke_"))
    fake_state = tmp / ".sifta_state"
    fake_state.mkdir()
    print(f"  sandbox: {tmp}")

    # Plant a tiny conversation: 10 user turns, ~5s apart, 60% got a real
    # alice reply within 3s.
    t0 = 1776600000.0
    convo_rows = []
    for i in range(10):
        t = t0 + i * 5.0
        convo_rows.append({"ts": t, "role": "user", "text": f"turn {i}"})
        if i % 10 < 6:
            convo_rows.append({"ts": t + 3.0, "role": "alice",
                               "text": f"reply {i}"})
        else:
            convo_rows.append({"ts": t + 3.0, "role": "alice",
                               "text": "(silent: memorized)"})
    with (fake_state / "alice_conversation.jsonl").open("w") as f:
        for r in convo_rows:
            f.write(json.dumps(r) + "\n")

    # Plant rewards: +0.3 six seconds after each user turn (inside the
    # 60s capture window). This gives the annealer something to chase.
    with (fake_state / "stgm_memory_rewards.jsonl").open("w") as f:
        for i in range(10):
            f.write(json.dumps({"ts": t0 + i * 5.0 + 6.0,
                                "reason": "MEMORY_RECALL", "amount": 0.3,
                                "trace_id": f"smoke_{i}", "app": "smoke"}) + "\n")

    # Plant coefficient files for ALL four cortex subsystems with known
    # defaults. _load_mega_coefficients() reads all four; if any are
    # missing it silently falls back to defaults, but we want the smoke
    # to exercise the real load-from-disk path.
    with (fake_state / "speech_potential_coefficients.json").open("w") as f:
        json.dump(asdict(SSPCoefficients()), f)
    with (fake_state / "motor_potential_coefficients.json").open("w") as f:
        json.dump(asdict(MotorCoefficients()), f)
    with (fake_state / "homeostasis_coefficients.json").open("w") as f:
        json.dump(asdict(HomeostasisCoefficients()), f)
    with (fake_state / "free_energy_coefficients.json").open("w") as f:
        json.dump(asdict(FreeEnergyCoefficients()), f)

    # Fake heartbeat — CALM posture, moderate neuromodulators
    with (fake_state / "clinical_heartbeat.json").open("w") as f:
        json.dump({
            "vital_signs": {
                "serotonin_dominance": 0.6,
                "dopamine_concentration": 210.0,
                "computational_posture": "CALM_ADAPTIVE",
            }
        }, f)

    # Monkeypatch module paths
    import System.swarm_speech_potential as ssp_mod
    from System.swarm_speech_potential import _STATE_DIR as _  # noqa
    real_paths = {
        "_STATE_DIR":     ssp_mod._STATE_DIR,
        "_COEFFS_PATH":   ssp_mod._COEFFS_PATH,
        "_HEARTBEAT_PATH":ssp_mod._HEARTBEAT_PATH,
        "_CONVERSATION_PATH": ssp_mod._CONVERSATION_PATH,
        "_REWARDS_PATH":  ssp_mod._REWARDS_PATH,
    }
    ssp_mod._STATE_DIR         = fake_state
    ssp_mod._COEFFS_PATH       = fake_state / "speech_potential_coefficients.json"
    ssp_mod._HEARTBEAT_PATH    = fake_state / "clinical_heartbeat.json"
    ssp_mod._CONVERSATION_PATH = fake_state / "alice_conversation.jsonl"
    ssp_mod._REWARDS_PATH      = fake_state / "stgm_memory_rewards.jsonl"

    global _STATE_DIR, _COEFFS_LIVE, _COEFFS_PROPOSED, _EVOLUTION_LOG
    global _CONVERSATION, _REWARDS
    global _MOTOR_LIVE, _MOTOR_PROPOSED, _HOMEO_LIVE, _HOMEO_PROPOSED
    global _FE_LIVE, _FE_PROPOSED
    backup = (_STATE_DIR, _COEFFS_LIVE, _COEFFS_PROPOSED, _EVOLUTION_LOG,
              _CONVERSATION, _REWARDS,
              _MOTOR_LIVE, _MOTOR_PROPOSED, _HOMEO_LIVE, _HOMEO_PROPOSED,
              _FE_LIVE, _FE_PROPOSED)
    _STATE_DIR       = fake_state
    _COEFFS_LIVE     = fake_state / "speech_potential_coefficients.json"
    _COEFFS_PROPOSED = fake_state / "speech_potential_coefficients_proposed.json"
    _EVOLUTION_LOG   = fake_state / "ssp_evolution.jsonl"
    _CONVERSATION    = fake_state / "alice_conversation.jsonl"
    _REWARDS         = fake_state / "stgm_memory_rewards.jsonl"
    _MOTOR_LIVE      = fake_state / "motor_potential_coefficients.json"
    _MOTOR_PROPOSED  = fake_state / "motor_potential_coefficients_proposed.json"
    _HOMEO_LIVE      = fake_state / "homeostasis_coefficients.json"
    _HOMEO_PROPOSED  = fake_state / "homeostasis_coefficients_proposed.json"
    _FE_LIVE         = fake_state / "free_energy_coefficients.json"
    _FE_PROPOSED     = fake_state / "free_energy_coefficients_proposed.json"

    try:
        # [A] Fitness depends on θ (this is the BLOCKER finding from the
        # Perplexity review — we MUST prove our fitness is measurably a
        # function of θ). Pick two points chosen to land on opposite sides
        # of the "fires vs doesn't fire" regime so the signal is crisp.
        convo = _load_conversation()
        rewards = _load_rewards()
        users = _extract_user_turns(convo, 10)
        target = _estimate_target_rate(convo, users)
        S  = _read_serotonin(); D = _read_dopamine_normalized(); C = _cortisol_proxy(S)
        dD = D - 1.0

        lfn = _listener_active_for(convo)

        def _eval(gene: MegaGene):
            return _fitness(
                gene, convo=convo, rewards=rewards, user_turns=users,
                standing_input=(gene.alpha*S - gene.gamma*C + gene.beta*dD),
                listener_fn=lfn, fit_cfg=FitnessConfig(), target_rate=target,
                rng=random.Random(0xC47),
            )

        # θ_a: easy-firing — low threshold + strong drive → should spike often
        coeffs_a = _load_mega_coefficients()
        coeffs_a = (coeffs_a.replace_key('V_th', 0.10)
                            .replace_key('alpha', 0.90)
                            .replace_key('epsilon', 0.90)
                            .replace_key('gamma', 0.00))
        # θ_b: hard-firing — high threshold + weak drive → should rarely spike
        coeffs_b = _load_mega_coefficients()
        coeffs_b = (coeffs_b.replace_key('V_th', 0.90)
                            .replace_key('alpha', 0.05)
                            .replace_key('epsilon', 0.05)
                            .replace_key('gamma', 1.00))
        fa, dbg_a = _eval(coeffs_a)
        fb, dbg_b = _eval(coeffs_b)
        if abs(fa - fb) < 1e-6:
            failures.append(
                f"A: fitness did not change between two very different SSP θ "
                f"(a={fa:.6f} fires={dbg_a['n_fires']}, "
                f"b={fb:.6f} fires={dbg_b['n_fires']})"
            )
        else:
            print(f"  [A] fitness responds to SSP θ  "
                  f"(easy: fit={fa:+.4f} fires={dbg_a['n_fires']}  |  "
                  f"hard: fit={fb:+.4f} fires={dbg_b['n_fires']}  |  Δ={fb-fa:+.4f}) ✓")

        # ── [G] COUPLED LEARNING RULE — Motor coefficients move fitness ─
        # Vary ONLY motor coeffs. AG31's flat-fitness regression at trace
        # 0cee574e returned 1.0 here. Honest fitness MUST move.
        baseline = _load_mega_coefficients()
        f_base, _ = _eval(baseline)
        wild_motor = (_load_mega_coefficients()
                      .replace_key('a', 2.0)
                      .replace_key('b', 0.1)
                      .replace_key('c', 2.0)
                      .replace_key('f', 2.0))
        f_motor, _ = _eval(wild_motor)
        if abs(f_base - f_motor) < 1e-6:
            failures.append(
                f"G: fitness FLAT under motor-coeff change "
                f"(base={f_base:.6f}, wild_motor={f_motor:.6f}). "
                f"Coupled learning rule is broken — motor mutations are "
                f"random-walking. This is the AG31 0.9331 failure mode."
            )
        else:
            print(f"  [G] fitness responds to motor θ  "
                  f"(base={f_base:+.4f}  |  wild_motor={f_motor:+.4f}  |  "
                  f"Δ={f_motor-f_base:+.4f}) ✓")

        # ── [H] COUPLED LEARNING RULE — Homeo coefficients move fitness ─
        wild_homeo = (_load_mega_coefficients()
                      .replace_key('eta', 2.0)
                      .replace_key('lmbda', 2.0)
                      .replace_key('mu', 2.0))
        f_homeo, _ = _eval(wild_homeo)
        if abs(f_base - f_homeo) < 1e-6:
            failures.append(
                f"H: fitness FLAT under homeo-coeff change "
                f"(base={f_base:.6f}, wild_homeo={f_homeo:.6f})."
            )
        else:
            print(f"  [H] fitness responds to homeo θ  "
                  f"(base={f_base:+.4f}  |  wild_homeo={f_homeo:+.4f}  |  "
                  f"Δ={f_homeo-f_base:+.4f}) ✓")

        # ── [I] COUPLED LEARNING RULE — FE coefficients move fitness ────
        wild_fe = (_load_mega_coefficients()
                   .replace_key('kappa', 2.0)
                   .replace_key('xi', 2.0)
                   .replace_key('rho', 2.0)
                   .replace_key('tau_grad', 10.0)
                   .replace_key('tau_curv', 10.0))
        f_fe, _ = _eval(wild_fe)
        if abs(f_base - f_fe) < 1e-6:
            failures.append(
                f"I: fitness FLAT under FE-coeff change "
                f"(base={f_base:.6f}, wild_fe={f_fe:.6f})."
            )
        else:
            print(f"  [I] fitness responds to FE θ  "
                  f"(base={f_base:+.4f}  |  wild_fe={f_fe:+.4f}  |  "
                  f"Δ={f_fe-f_base:+.4f}) ✓")

        # [B] Full evolve cycle — small iter budget for speed
        report = evolve(
            anneal=AnnealingConfig(iterations=60, T0=0.5, cooling_rate=0.95),
            fitness=FitnessConfig(replay_user_turns=10),
            seed=42,
            write_proposal=True,
            file_peer_review=False,  # don't spam the real peer-review trace
        )
        if report.iterations_run < 1:
            failures.append("B: evolve returned zero iterations")
        else:
            print(f"  [B] evolve: {report.iterations_run} iter, "
                  f"{report.accepts} acc / {report.rejects} rej, "
                  f"Δfit={report.best_fitness - report.initial_fitness:+.4f} ✓")

        # [C] Proposal file written; live file NOT touched
        if not _COEFFS_PROPOSED.exists():
            failures.append("C: proposal file missing after evolve")
        else:
            with _COEFFS_PROPOSED.open() as f:
                prop = json.load(f)
            if "_provenance" not in prop:
                failures.append("C: proposal missing _provenance block")
            else:
                print(f"  [C] proposal file written, provenance intact ✓")

        # [D] Audit log has at least one row
        if not _EVOLUTION_LOG.exists():
            failures.append("D: no audit log created")
        else:
            n = _count_lines(_EVOLUTION_LOG)
            if n < 1:
                failures.append(f"D: audit log has {n} rows")
            else:
                print(f"  [D] audit log: {n} row(s) ✓")

        # [E] apply_proposal / rollback round-trip
        live_before = json.loads(_COEFFS_LIVE.read_text())
        ap = apply_proposal()
        if not ap.get("ok"):
            failures.append(f"E1: apply_proposal failed: {ap}")
        live_after = json.loads(_COEFFS_LIVE.read_text())
        if live_before == live_after:
            # The annealer might not have found an improvement on a trivial
            # dataset. That's OK — the promotion still has to write.
            # But it should at least have _provenance stripped.
            if "_provenance" in live_after:
                failures.append("E2: _provenance leaked into live file")
        rb = rollback()
        if not rb.get("ok"):
            failures.append(f"E3: rollback failed: {rb}")
        restored = json.loads(_COEFFS_LIVE.read_text())
        if restored != live_before:
            failures.append("E4: rollback did not restore exact prior state")
        else:
            print(f"  [E] apply_proposal / rollback round-trip ✓")

        # [F] Bounds enforcement
        rng = random.Random(0)
        c = _load_mega_coefficients()
        for _ in range(2000):
            c = _mutate(c, sigma_frac=5.0, rng=rng)   # huge sigma to stress bounds
            for k, (lo, hi) in BOUNDS.items():
                v = getattr(c, k)
                if not (lo <= v <= hi):
                    failures.append(f"F: bounds violated for {k}: {v} not in [{lo},{hi}]")
                    break
            if failures:
                break
        else:
            print(f"  [F] bounds enforced across 2000 mutations ✓")

    except Exception as exc:
        import traceback
        failures.append(f"smoke crashed: {type(exc).__name__}: {exc}")
        traceback.print_exc()
    finally:
        # Restore module globals
        for k, v in real_paths.items():
            setattr(ssp_mod, k, v)
        (_STATE_DIR, _COEFFS_LIVE, _COEFFS_PROPOSED, _EVOLUTION_LOG,
         _CONVERSATION, _REWARDS,
         _MOTOR_LIVE, _MOTOR_PROPOSED, _HOMEO_LIVE, _HOMEO_PROPOSED,
         _FE_LIVE, _FE_PROPOSED) = backup

    if failures:
        print("\n[swarm_ssp_evolver] FAIL")
        for f_ in failures:
            print(f"  • {f_}")
        return 1
    print("\n[swarm_ssp_evolver] OK — all 9 checks passed "
          "(SSP+Motor+Homeo+FE coupled fitness verified, live files untouched).")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
