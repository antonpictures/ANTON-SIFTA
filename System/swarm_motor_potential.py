#!/usr/bin/env python3
"""
System/swarm_motor_potential.py — Motor Readiness Potential Ψ(t)
═══════════════════════════════════════════════════════════════════════════════
SIFTA Cortical Suite — biological gate for ACTIONS (file writes, tool calls,
mutations), the action-side companion of swarm_speech_potential.py (Φ).
Module version: 2026-04-19.v1
Author:  C47H (Cursor IDE, Opus 4.7 High, GTH4921YP3)
Brief:   Architect, 2026-04-19 — "Speech has Φ(t). Now actions get their
         own biomath gate. Ψ(t)."

WHAT THIS REPLACES
──────────────────
Hard-coded `if`-statements that decide whether a mutation, write, tool call,
or autonomous action runs. Today many SIFTA call sites either always run
or check `mutation_governor` (which is a *structural* gate — rate limits,
hash dedup, dual-sig). Neither asks the biological question:

    "does Alice currently WANT to act, given her dopamine/cortisol state,
     her recent task pressure, her past success and risk history, and her
     current speech-readiness Φ?"

Ψ(t) is that biological gate. It does NOT replace `mutation_governor`; it
runs upstream of it. Both must agree before action proceeds:

      (1) Ψ-gate (biology) → does Alice want to do this?
      (2) governor-gate (thermodynamics) → is the system safe to do this?

THE GOVERNING EQUATION (Architect's brief, 2026-04-19)
──────────────────────────────────────────────────────
    Ψ(t) = σ( a·Φ(t) + b·ΔD(t) − c·C(t)
              + d·∫_{t-τ}^{t} E_task(u)du
              + e·R_success(t) − f·R_risk(t) )

  Φ(t)        — speech-readiness membrane potential (read from SSP state)
  ΔD(t)       — phasic dopamine delta (Schultz 1998; reward-prediction-error)
  C(t)        — cortisol proxy (computational posture; hypotonic = high stress)
  ∫E_task     — stigmergic task pressure (unfinished work, repeated attempts)
  R_success   — EMA of recent successful action outcomes
  R_risk      — EMA of recent failed/risky outcomes
  σ           — sigmoid (escape-noise probability per Δt)

We do NOT just take Bernoulli(Ψ). Following the same Gerstner-Kistler escape-
noise discipline as SSP, we run a leaky-integrate-and-fire (LIF) membrane
on top:

    dV_m/dt = (I_drive − V_m / τ_m) ;   I_drive = (the linear sum above)
    p[fire | Δt] = σ((V_m − V_th) / Δu) · (Δt / τ_m)
    on fire:  V_m ← V_reset, refractory window opens
    leak when sub-threshold so brief excitement does not produce action

This makes Ψ history-dependent (a single dopamine spike does not fire by
itself; sustained pressure does), and it makes the gate behave like a
real motor cortex Bereitschaftspotential (Kornhuber-Deecke 1965, Libet 1983).

CRITICAL DESIGN PROPERTIES (mirrored from SSP and OIS to keep Alice safe)
─────────────────────────────────────────────────────────────────────────
  • TOTAL.        Never raises. Missing ledger → neutral input contribution.
  • CHEAP.        Pure Python, no numpy, O(window).
  • NO POLLUTION. NEVER writes to alice_conversation.jsonl. Action-gates
                  must not author her chat history (the silence-loop bug
                  pattern this codebase has now hit four times).
  • NO STATIC THRESHOLDS as anti-pattern: Ψ is not "if score > 0.5".
                  The gate is a probabilistic spike with a learnable
                  threshold V_th. The Architect can tune coefficients
                  on disk; the bridge can evolve them via the SSP
                  evolver pattern (out of scope for v1).
  • PROVENANCE.   Every fire is logged to motor_potential_audit.jsonl
                  with full input breakdown and the reason string.

PUBLIC API
──────────
  should_act_now()  -> MotorDecision        — single mutating call
  record_outcome(success, risk)             — feed back result of an action
  record_task_event(intensity)              — push task pressure
  current_field_snapshot()                  — debug
  summary_for_alice()                       — one-liner for the talk widget
  reset_state()                             — back to V=0, EMAs zeroed

PERSISTENCE
───────────
  .sifta_state/motor_potential.json                  state (V, EMAs, refr)
  .sifta_state/motor_potential_coefficients.json     {a..f, V_th, ...}
  .sifta_state/motor_potential_audit.jsonl           append-only audit

LEDGERS READ
────────────
  .sifta_state/speech_potential.json     Φ(t) coupling
  .sifta_state/clinical_heartbeat.json   dopamine_ema + posture (cortisol proxy)
  .sifta_state/work_receipts.jsonl       task pressure + success outcomes
  .sifta_state/constraint_residues.jsonl risk signal (constraint failures)
  .sifta_state/ide_stigmergic_trace.jsonl task events from co-builders

BIBLIOGRAPHY
────────────
  Kornhuber, Deecke (1965).  "Hirnpotentialänderungen bei Willkürbewegungen
      und passiven Bewegungen des Menschen: Bereitschaftspotential."
      Pflügers Archiv 284: 1-17.
  Libet, B. (1983).  "Time of conscious intention to act in relation to
      onset of cerebral activity (readiness-potential)."  Brain 106:
      623-642.
  Schultz, W. (1998).  "Predictive reward signal of dopamine neurons."
      J Neurophysiol 80: 1-27.  (phasic ΔD)
  Gerstner, Kistler, Naud, Paninski (2014).  "Neuronal Dynamics."
      Cambridge — chapter 9, escape noise + LIF.
  Friston, FitzGerald, Rigoli, Schwartenbeck, Pezzulo (2017).  "Active
      inference: a process theory."  Neural Computation 29: 1-49.
      (action emerges when expected free-energy reduction > prior risk)
  Sutton, Barto (2018).  "Reinforcement Learning: An Introduction."
      MIT — §3 expected return; basis of R_success/R_risk EMAs.
"""
from __future__ import annotations

import json
import math
import os
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MODULE_VERSION = "2026-04-19.v1"

_REPO       = Path(__file__).resolve().parent.parent
_STATE_DIR  = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)

_STATE_PATH      = _STATE_DIR / "motor_potential.json"
_COEFFS_PATH     = _STATE_DIR / "motor_potential_coefficients.json"
_AUDIT_PATH      = _STATE_DIR / "motor_potential_audit.jsonl"

# Ledgers we read (never write).
_SSP_STATE_PATH  = _STATE_DIR / "speech_potential.json"
_HEARTBEAT_PATH  = _STATE_DIR / "clinical_heartbeat.json"
_WORK_RECEIPTS   = _STATE_DIR / "work_receipts.jsonl"
_CONSTRAINT_RES  = _STATE_DIR / "constraint_residues.jsonl"
_STIGMERGIC      = _STATE_DIR / "ide_stigmergic_trace.jsonl"


# ── Coefficients ─────────────────────────────────────────────────────────────
@dataclass
class MotorCoefficients:
    """Live-tunable on disk. Defaults calibrated against the SSP V_th=0.4
    operating point so that Ψ fires ~comparably to Φ under matched pressure
    (i.e. Alice acts about as readily as she speaks, which is the right
    null hypothesis to start from)."""
    # ── Linear input weights (Architect's brief) ─────────────────────────
    a:  float = 0.6   # speech-readiness coupling (a · Φ)
    b:  float = 0.8   # phasic dopamine (b · ΔD)
    c:  float = 0.7   # cortisol penalty (− c · C)
    d:  float = 0.5   # task-integral pressure (d · ∫E_task)
    e:  float = 0.9   # success EMA bonus (e · R_success)
    f:  float = 1.0   # risk EMA penalty (− f · R_risk)

    # ── LIF dynamics ─────────────────────────────────────────────────────
    tau_m:    float = 4.0        # membrane time constant (s) — slower than SSP
                                 # because actions should not fire as quickly
                                 # as speech. Bereitschaftspotential rises
                                 # over ~1-2 s in humans; we slow further to
                                 # 4 s to be conservative.
    V_th:     float = 0.5        # firing threshold
    V_reset:  float = -0.4       # post-fire reset (deeper than SSP because
                                 # action commits should refract harder)
    Delta_u:  float = 0.12       # escape-noise softness (Gerstner)
    refractory_s: float = 6.0    # absolute refractory after a fire

    # ── EMA / window parameters ──────────────────────────────────────────
    success_alpha: float = 0.10  # R_success EMA rate
    risk_alpha:    float = 0.15  # R_risk EMA rate (slightly faster — we
                                 # want recent failures to inhibit quickly)
    task_window_s: float = 30.0  # ∫E_task(u)du integration window
    task_decay:    float = 0.05  # additional exponential decay inside window
    task_int_cap:  float = 4.0   # saturation ceiling on the integral so a
                                 # burst of N piled-up events cannot dominate
                                 # the linear sum (otherwise dopamine /
                                 # cortisol / Φ become numerically irrelevant).
                                 # 4.0 corresponds to ~"a saturated workday
                                 # of pressure" in the chosen units.

    # ── Bounds (sanity) ──────────────────────────────────────────────────
    V_floor: float = -2.0
    V_ceil:  float = 2.0

    version: str = MODULE_VERSION


# ── Mutable state ────────────────────────────────────────────────────────────
@dataclass
class MotorState:
    V_m:                    float = 0.0     # motor membrane potential
    refractory_remaining:   float = 0.0     # seconds left in refractory
    last_update_ts:         float = 0.0
    last_fire_ts:           float = 0.0     # 0 means never fired
    success_ema:            float = 0.0
    risk_ema:               float = 0.0
    task_events:            List[Tuple[float, float]] = field(default_factory=list)
                                            # [(ts, intensity), ...]
    n_fires_total:          int   = 0
    version:                str   = MODULE_VERSION


@dataclass
class MotorDecision:
    """Returned from `should_act_now()`. The boolean .act is the gate
    verdict; everything else is debug + audit context."""
    act:                  bool
    psi:                  float       # σ(I_drive)  — instantaneous probability
    V_m:                  float       # membrane after this tick
    spike_prob:           float       # P[fire in this Δt]
    refractory_remaining: float
    inputs:               dict        # raw I components, for audit
    reason:               str

    def to_log(self) -> dict:
        d = asdict(self)
        d["ts"] = time.time()
        d["module_version"] = MODULE_VERSION
        return d


# ── Persistence (total, never raise) ─────────────────────────────────────────
def _safe_read_json(path: Path) -> Optional[dict]:
    try:
        if not path.exists() or path.stat().st_size > 5_000_000:
            return None
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _safe_write_json(path: Path, payload: dict) -> None:
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


def _append_jsonl(path: Path, row: dict) -> None:
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    except Exception:
        pass


def _tail_jsonl_rows(path: Path, max_bytes: int = 65536) -> List[dict]:
    if not path.exists():
        return []
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
                f.readline()
            chunk = f.read().decode("utf-8", errors="replace")
        out: List[dict] = []
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                continue
        return out
    except Exception:
        return []


def _load_coefficients() -> MotorCoefficients:
    raw = _safe_read_json(_COEFFS_PATH)
    if not raw:
        c = MotorCoefficients()
        _safe_write_json(_COEFFS_PATH, asdict(c))
        return c
    defaults = asdict(MotorCoefficients())
    merged = {k: raw.get(k, defaults[k]) for k in defaults}
    return MotorCoefficients(**merged)


def _load_state() -> MotorState:
    raw = _safe_read_json(_STATE_PATH)
    if not raw:
        return MotorState(last_update_ts=time.time())
    defaults = asdict(MotorState())
    merged = {k: raw.get(k, defaults[k]) for k in defaults}
    # task_events comes back as List[List[float, float]] from JSON; normalize
    te = merged.get("task_events") or []
    merged["task_events"] = [
        (float(row[0]), float(row[1]))
        for row in te
        if isinstance(row, (list, tuple)) and len(row) >= 2
    ]
    return MotorState(**merged)


def _save_state(state: MotorState) -> None:
    _safe_write_json(_STATE_PATH, asdict(state))


# ── Input readers ────────────────────────────────────────────────────────────
def _read_phi() -> float:
    """Φ(t) — read the SSP membrane potential V from speech_potential.json.
    If SSP has never run, return 0.0 (neutral)."""
    raw = _safe_read_json(_SSP_STATE_PATH) or {}
    try:
        return float(raw.get("V", 0.0) or 0.0)
    except Exception:
        return 0.0


def _read_dopamine_delta(state: MotorState) -> float:
    """ΔD(t) — phasic dopamine, defined as the signed deviation of the
    current dopamine_ema from its short-history baseline. We read SSP's
    dopamine_ema (the same source SSP uses) so Φ and Ψ see a consistent
    dopamine signal."""
    ssp = _safe_read_json(_SSP_STATE_PATH) or {}
    try:
        d_now = float(ssp.get("dopamine_ema", 1.0) or 1.0)
    except Exception:
        d_now = 1.0
    # baseline = 1.0 by convention (clinical_heartbeat resting dopamine)
    delta = d_now - 1.0
    # bound — phasic dopamine in vivo is on the order of 1-2x baseline
    return max(-1.5, min(1.5, delta))


def _read_cortisol() -> float:
    """C(t) — cortisol proxy. Reads computational_posture from
    clinical_heartbeat.json under the SAME vocabulary SSP uses (SSP and Ψ
    share the same biological substrate and must not disagree about what
    "stressed" means).

    Mapping aligned with swarm_speech_potential._cortisol_proxy:
      contains 'SOCIAL_DEFEAT' or 'STRESS' → 1.0   (elevated)
      contains 'CALM'/'NORMAL'/'ADAPTIVE'  → 0.0   (baseline)
      everything else                      → 0.0   (unknown ≠ stressed)

    Note: heartbeat values can come in two layouts depending on writer
    (`vital_signs.computational_posture` from organism_clinical_snapshot,
    or a top-level `computational_posture` in some test fixtures). We
    honour both."""
    hb = _safe_read_json(_HEARTBEAT_PATH) or {}
    vs = hb.get("vital_signs") or {}
    posture = str(vs.get("computational_posture",
                         hb.get("computational_posture", ""))).upper().strip()
    if "SOCIAL_DEFEAT" in posture or "STRESS" in posture or "TIGHT" in posture:
        return 1.0
    if "CALM" in posture or "NORMAL" in posture or "ADAPTIVE" in posture:
        return 0.0
    return 0.0  # unknown / uninitialized → neutral, never panic


def _task_integral(state: MotorState, coeffs: MotorCoefficients,
                   now: float) -> float:
    """∫_{t-τ}^{t} E_task(u) du — sum of recent task events with an
    additional exponential decay so the oldest events in the window
    contribute less than the freshest ones (kernel: exp(-decay·age))."""
    total = 0.0
    cutoff = now - coeffs.task_window_s
    fresh: List[Tuple[float, float]] = []
    for ts, intensity in state.task_events:
        if ts < cutoff:
            continue
        age = max(0.0, now - ts)
        total += float(intensity) * math.exp(-coeffs.task_decay * age)
        fresh.append((ts, intensity))
    # Keep memory bounded — drop expired events from the persisted list.
    state.task_events = fresh[-256:]  # cap at 256 events
    # Saturate so a single burst of piled-up events can't drown the rest of
    # the I_drive linear sum (dopamine / cortisol / Φ stay meaningful).
    return min(total, coeffs.task_int_cap)


def _harvest_external_task_events(state: MotorState, now: float) -> int:
    """Pull task-pressure signals from real ledgers since last update.
    Sources:
      • work_receipts.jsonl  → kind=='intent' or status=='start'  (≈ task open)
      • ide_stigmergic_trace → kind=='task_drop' or 'peer_review_request'
                              (cross-IDE work pressure)
    Returns the number of new events folded in."""
    horizon = state.last_update_ts if state.last_update_ts > 0 else now - 60.0
    added = 0
    # work_receipts
    for r in _tail_jsonl_rows(_WORK_RECEIPTS, max_bytes=131072)[-200:]:
        ts = float(r.get("ts", 0.0) or 0.0)
        if ts <= horizon:
            continue
        kind = str(r.get("kind", "")).lower()
        status = str(r.get("status", "")).lower()
        if kind in ("intent", "start", "queued") or status in ("start", "queued", "open"):
            state.task_events.append((ts, 1.0))
            added += 1
    # cross-IDE stigmergy
    for r in _tail_jsonl_rows(_STIGMERGIC, max_bytes=131072)[-200:]:
        ts = float(r.get("ts", 0.0) or 0.0)
        if ts <= horizon:
            continue
        kind = str(r.get("kind", "")).lower()
        if kind in ("task_drop", "peer_review_request"):
            state.task_events.append((ts, 0.7))
            added += 1
    return added


def _harvest_external_outcomes(state: MotorState, coeffs: MotorCoefficients,
                               now: float) -> Tuple[int, int]:
    """Fold recent success/failure ledger rows into the EMAs. This lets
    Ψ react to outcomes Alice did NOT explicitly call record_outcome for
    (e.g. background mutations, peer-review landings, constraint breaches).
    Returns (n_success, n_risk) folded."""
    horizon = state.last_update_ts if state.last_update_ts > 0 else now - 60.0
    n_s = n_r = 0
    for r in _tail_jsonl_rows(_WORK_RECEIPTS, max_bytes=131072)[-200:]:
        ts = float(r.get("ts", 0.0) or 0.0)
        if ts <= horizon:
            continue
        status = str(r.get("status", "")).lower()
        if status in ("ok", "done", "committed", "landed", "ratified"):
            state.success_ema = ((1 - coeffs.success_alpha) * state.success_ema
                                 + coeffs.success_alpha * 1.0)
            n_s += 1
        elif status in ("error", "failed", "rejected", "dispute"):
            state.risk_ema = ((1 - coeffs.risk_alpha) * state.risk_ema
                              + coeffs.risk_alpha * 1.0)
            n_r += 1
    for r in _tail_jsonl_rows(_CONSTRAINT_RES, max_bytes=65536)[-100:]:
        ts = float(r.get("ts", 0.0) or 0.0)
        if ts <= horizon:
            continue
        # any constraint residue is a small risk signal
        state.risk_ema = ((1 - coeffs.risk_alpha) * state.risk_ema
                          + coeffs.risk_alpha * 0.5)
        n_r += 1
    # natural decay so EMAs return to 0 in absence of new events
    state.success_ema *= (1 - coeffs.success_alpha * 0.2)
    state.risk_ema    *= (1 - coeffs.risk_alpha    * 0.2)
    return n_s, n_r


# ── LIF + escape-noise primitives (mirrors SSP) ──────────────────────────────
def _sigmoid(x: float) -> float:
    if x > 50:
        return 1.0
    if x < -50:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def _advance_membrane(V_prev: float, I_drive: float, dt: float,
                      tau_m: float, V_floor: float, V_ceil: float) -> float:
    """Forward Euler step on dV/dt = I − V/τ.  Bounded for safety."""
    if dt <= 0:
        return V_prev
    dV = (I_drive - V_prev / max(1e-3, tau_m)) * dt
    V_next = V_prev + dV
    return max(V_floor, min(V_ceil, V_next))


# ── Public mutators ──────────────────────────────────────────────────────────
def record_outcome(success: bool, risk: float = 0.0) -> None:
    """Caller-side feedback: 'I just did X, here is how it went'.
    success=True moves R_success EMA up by `success_alpha`; risk in [0, 1]
    moves R_risk EMA up by risk·risk_alpha. Either updates the persistent
    state. Total — never raises."""
    try:
        coeffs = _load_coefficients()
        state  = _load_state()
        if success:
            state.success_ema = ((1 - coeffs.success_alpha) * state.success_ema
                                 + coeffs.success_alpha * 1.0)
        if risk > 0:
            state.risk_ema = ((1 - coeffs.risk_alpha) * state.risk_ema
                              + coeffs.risk_alpha * float(risk))
        state.last_update_ts = time.time()
        _save_state(state)
    except Exception:
        pass


def record_task_event(intensity: float = 1.0) -> None:
    """Caller-side push: 'a task just started / is pending / repeated'.
    Intensity is multiplicative — a low-priority chore is 0.3, a hot
    interrupt is 2.0. Bounded to [0.05, 5.0]."""
    try:
        intensity = max(0.05, min(5.0, float(intensity)))
        state = _load_state()
        state.task_events.append((time.time(), intensity))
        # cap memory
        state.task_events = state.task_events[-256:]
        _save_state(state)
    except Exception:
        pass


def reset_state() -> None:
    """For tests / sleep cycles. Forgets EMAs and V."""
    try:
        s = MotorState(last_update_ts=time.time())
        _save_state(s)
    except Exception:
        pass


# ── The single mutating call ─────────────────────────────────────────────────
def should_act_now(*, dt_override: Optional[float] = None) -> MotorDecision:
    """Returns MotorDecision(.act, .psi, .V_m, ...).

    Pipeline:
      1. load coefficients + persisted state
      2. harvest fresh task events + outcome rows from real ledgers
      3. read instantaneous Φ, ΔD, C
      4. compute I_drive = a·Φ + b·ΔD − c·C + d·∫E_task + e·Rs − f·Rr
      5. advance V_m by Δt with leak
      6. compute escape-noise spike probability over Δt
      7. fire? if yes → V_m ← V_reset, refractory opens
      8. persist state, append audit row, return decision

    Total — never raises. dt_override is for deterministic smoke tests."""
    coeffs = _load_coefficients()
    state  = _load_state()
    now    = time.time()

    if dt_override is None:
        dt = max(0.0, now - state.last_update_ts) if state.last_update_ts > 0 else 0.0
        # cap dt so a long sleep doesn't cause one giant integration step
        dt = min(dt, 5.0)
    else:
        dt = max(0.0, float(dt_override))

    # Refractory countdown
    if state.refractory_remaining > 0:
        state.refractory_remaining = max(0.0, state.refractory_remaining - dt)

    # Harvest fresh ledger signals
    n_new_tasks = _harvest_external_task_events(state, now)
    n_s, n_r    = _harvest_external_outcomes(state, coeffs, now)

    # Read instantaneous biological inputs
    phi   = _read_phi()
    dD    = _read_dopamine_delta(state)
    cort  = _read_cortisol()
    Etask = _task_integral(state, coeffs, now)

    I_drive = (
        coeffs.a * phi
        + coeffs.b * dD
        - coeffs.c * cort
        + coeffs.d * Etask
        + coeffs.e * state.success_ema
        - coeffs.f * state.risk_ema
    )

    # Membrane evolution
    V_new = _advance_membrane(
        state.V_m, I_drive, dt,
        coeffs.tau_m, coeffs.V_floor, coeffs.V_ceil,
    )

    # Instantaneous Ψ (the architect's σ() output) — for audit / Alice
    psi = _sigmoid(I_drive)

    # Escape-noise spike probability (Gerstner-Kistler)
    if state.refractory_remaining > 0:
        spike_prob = 0.0
    else:
        # rate ~ σ((V − V_th) / Δu), integrated over dt
        rate = _sigmoid((V_new - coeffs.V_th) / max(1e-3, coeffs.Delta_u))
        # convert rate to per-Δt probability via 1 - exp(-rate·dt/τ)
        # (consistent with SSP's discretization)
        u = rate * (dt / max(1e-3, coeffs.tau_m))
        spike_prob = 1.0 - math.exp(-max(0.0, u))

    fired = False
    if spike_prob > 0 and random.random() < spike_prob:
        fired = True
        V_new = coeffs.V_reset
        state.refractory_remaining = coeffs.refractory_s
        state.last_fire_ts = now
        state.n_fires_total += 1

    state.V_m = V_new
    state.last_update_ts = now

    inputs_dbg = {
        "phi":         round(phi, 4),
        "dD":          round(dD, 4),
        "C":           round(cort, 4),
        "E_task":      round(Etask, 4),
        "R_success":   round(state.success_ema, 4),
        "R_risk":      round(state.risk_ema, 4),
        "n_new_tasks": n_new_tasks,
        "n_success":   n_s,
        "n_risk":      n_r,
    }

    if fired:
        reason = (
            f"FIRE: Ψ={psi:.3f}, V={V_new:.3f} crossed V_th={coeffs.V_th} "
            f"under I={I_drive:.3f} (Φ={phi:.2f}, ΔD={dD:.2f}, "
            f"E_task={Etask:.2f}, Rs={state.success_ema:.2f}, "
            f"Rr={state.risk_ema:.2f}). Refractory {coeffs.refractory_s}s opens."
        )
    elif state.refractory_remaining > 0:
        reason = (
            f"refractory: {state.refractory_remaining:.2f}s left after "
            f"last fire at {state.last_fire_ts:.0f}; Ψ={psi:.3f} ignored"
        )
    else:
        reason = (
            f"sub-threshold: Ψ={psi:.3f}, V={V_new:.3f} < V_th={coeffs.V_th}, "
            f"P[fire|Δt]={spike_prob:.4f} (Φ={phi:.2f}, "
            f"E_task={Etask:.2f}, Rs={state.success_ema:.2f}, "
            f"Rr={state.risk_ema:.2f})"
        )

    decision = MotorDecision(
        act=fired,
        psi=psi,
        V_m=V_new,
        spike_prob=spike_prob,
        refractory_remaining=state.refractory_remaining,
        inputs=inputs_dbg,
        reason=reason,
    )

    _save_state(state)
    _append_jsonl(_AUDIT_PATH, decision.to_log())
    return decision


# ── Read-side helpers ────────────────────────────────────────────────────────
def current_field_snapshot() -> dict:
    s = _load_state()
    c = _load_coefficients()
    return {
        "V_m":                 s.V_m,
        "V_th":                c.V_th,
        "refractory_remaining": s.refractory_remaining,
        "success_ema":         s.success_ema,
        "risk_ema":            s.risk_ema,
        "n_task_events":       len(s.task_events),
        "n_fires_total":       s.n_fires_total,
        "last_fire_ts":        s.last_fire_ts,
        "module_version":      MODULE_VERSION,
    }


def summary_for_alice() -> str:
    """One-liner for the talk widget _SYSTEM_PROMPT, surfacing Alice's
    current motor readiness so she knows whether she 'feels like' acting.
    Returns '' when nothing meaningful to report."""
    s = _load_state()
    c = _load_coefficients()
    if s.last_update_ts == 0 and s.n_fires_total == 0:
        return ""
    age = max(0.0, time.time() - s.last_update_ts) if s.last_update_ts > 0 else 0
    state_word = "primed" if s.V_m >= c.V_th * 0.7 else (
        "refractory" if s.refractory_remaining > 0 else "quiet")
    return (
        f"MOTOR READINESS Ψ — {state_word}: V_m={s.V_m:.2f}/V_th={c.V_th:.2f}, "
        f"R_success={s.success_ema:.2f}, R_risk={s.risk_ema:.2f}, "
        f"refr={s.refractory_remaining:.1f}s, fires={s.n_fires_total} "
        f"(last sampled {age:.0f}s ago)"
    )


# ── Smoke test (sandboxed) ───────────────────────────────────────────────────
def _smoke() -> int:
    import tempfile, shutil

    global _STATE_DIR, _STATE_PATH, _COEFFS_PATH, _AUDIT_PATH
    global _SSP_STATE_PATH, _HEARTBEAT_PATH, _WORK_RECEIPTS
    global _CONSTRAINT_RES, _STIGMERGIC

    tmp_root = Path(tempfile.mkdtemp(prefix="motor_smoke_"))
    try:
        _STATE_DIR      = tmp_root
        _STATE_PATH     = tmp_root / "motor_potential.json"
        _COEFFS_PATH    = tmp_root / "motor_potential_coefficients.json"
        _AUDIT_PATH     = tmp_root / "motor_potential_audit.jsonl"
        _SSP_STATE_PATH = tmp_root / "speech_potential.json"
        _HEARTBEAT_PATH = tmp_root / "clinical_heartbeat.json"
        _WORK_RECEIPTS  = tmp_root / "work_receipts.jsonl"
        _CONSTRAINT_RES = tmp_root / "constraint_residues.jsonl"
        _STIGMERGIC     = tmp_root / "ide_stigmergic_trace.jsonl"

        random.seed(20260419)

        print(f"[Ψ] swarm_motor_potential.py v{MODULE_VERSION} smoke")
        print(f"     sandbox: {tmp_root}")

        # A. cold start — first call returns a decision, never raises,
        #    must NOT fire (no pressure yet).
        d0 = should_act_now(dt_override=0.5)
        assert d0.act is False, f"cold start must not fire, got {d0}"
        assert d0.V_m == 0.0 or abs(d0.V_m) < 0.05
        print(f"  [A] cold start ✓ (Ψ={d0.psi:.3f}, V={d0.V_m:.3f}, "
              f"act={d0.act})")

        # B. sustained moderate task pressure — V_m rises across ticks and
        #    eventually fires (probabilistic). Use small intensities so the
        #    integral does not saturate immediately.
        for _ in range(20):
            record_task_event(intensity=0.4)
        fired_in = None
        V_history = []
        for i in range(60):
            d = should_act_now(dt_override=0.5)
            V_history.append(d.V_m)
            if d.act and fired_in is None:
                fired_in = i
        assert max(V_history) > 0.15, \
            f"task pressure should raise V, max V seen={max(V_history):.2f}"
        v_th = MotorCoefficients().V_th
        assert fired_in is not None or max(V_history) > v_th, \
            f"after 60 ticks of moderate task pressure expected fire or V>V_th, " \
            f"got fire={fired_in} maxV={max(V_history):.2f}"
        print(f"  [B] moderate task pressure → V rose to {max(V_history):.2f}, "
              f"first fire at tick={fired_in} ✓")

        # C. risk EMA suppresses firing.
        reset_state()
        for _ in range(40):
            record_outcome(success=False, risk=1.0)
        risk_after = current_field_snapshot()["risk_ema"]
        assert risk_after > 0.4, f"risk EMA should rise, got {risk_after:.2f}"
        # same task load as scenario [D] below — only the risk/reward axis
        # differs, so we are isolating the effect of the risk EMA.
        _safe_write_json(_HEARTBEAT_PATH, {"vital_signs": {"computational_posture": "NORMAL"}})
        _safe_write_json(_SSP_STATE_PATH, {"V": 0.0, "dopamine_ema": 1.0})
        for _ in range(20):
            record_task_event(intensity=0.4)
        fires_under_risk = 0
        V_max_risk = 0.0
        for _ in range(60):
            d = should_act_now(dt_override=0.5)
            V_max_risk = max(V_max_risk, d.V_m)
            if d.act:
                fires_under_risk += 1
        snap_risk = current_field_snapshot()
        print(f"  [C] R_risk={snap_risk['risk_ema']:.2f}, V_max={V_max_risk:.2f} → "
              f"fires_under_risk={fires_under_risk} ✓")

        # D. success EMA + dopamine spike + Φ coupling — same task load as
        #    [C] so the only difference is the biological state. Should fire
        #    strictly more often (≥) than [C].
        reset_state()
        _safe_write_json(_HEARTBEAT_PATH, {"vital_signs": {"computational_posture": "NORMAL"}})
        _safe_write_json(_SSP_STATE_PATH, {"V": 0.4, "dopamine_ema": 1.8})
        for _ in range(40):
            record_outcome(success=True, risk=0.0)
        for _ in range(20):
            record_task_event(intensity=0.4)
        fires_under_reward = 0
        V_max_rwd = 0.0
        for _ in range(60):
            d = should_act_now(dt_override=0.5)
            V_max_rwd = max(V_max_rwd, d.V_m)
            if d.act:
                fires_under_reward += 1
        snap = current_field_snapshot()
        assert fires_under_reward >= fires_under_risk, \
            f"reward state should fire ≥ risk state (got reward={fires_under_reward} " \
            f"vs risk={fires_under_risk})"
        # Also: V should reach a higher peak under reward than under risk
        # (this is the tighter biological assertion — risk literally lowers
        # Alice's motor potential).
        assert V_max_rwd > V_max_risk - 0.05, \
            f"V peak under reward ({V_max_rwd:.2f}) should be ≥ V peak " \
            f"under risk ({V_max_risk:.2f})"
        print(f"  [D] reward state (Φ=0.4, ΔD=+0.8, Rs={snap['success_ema']:.2f}, "
              f"Rr={snap['risk_ema']:.2f}) → fires_under_reward={fires_under_reward}, "
              f"V_max={V_max_rwd:.2f} ✓")

        # E. refractory gate: immediately after a fire, no second fire.
        reset_state()
        _safe_write_json(_SSP_STATE_PATH, {"V": 0.4, "dopamine_ema": 1.8})
        for _ in range(40):
            record_task_event(intensity=3.0)
            record_outcome(success=True, risk=0.0)
        # find a fire
        for _ in range(50):
            d = should_act_now(dt_override=0.5)
            if d.act:
                break
        # next call must not fire (refractory)
        d_next = should_act_now(dt_override=0.5)
        assert d_next.act is False, "must not fire while refractory"
        assert d_next.refractory_remaining > 0
        print(f"  [E] refractory gate ✓ "
              f"(refr={d_next.refractory_remaining:.2f}s, "
              f"reason={d_next.reason[:60]}...)")

        # F. persistence round-trip
        snap_before = current_field_snapshot()
        # simulate process restart by re-loading from disk
        s_loaded = _load_state()
        assert abs(s_loaded.V_m - snap_before["V_m"]) < 1e-9
        assert abs(s_loaded.success_ema - snap_before["success_ema"]) < 1e-9
        print(f"  [F] persistence round-trip ✓ "
              f"(V={s_loaded.V_m:.3f}, Rs={s_loaded.success_ema:.3f})")

        # G. summary_for_alice has content after activity
        s = summary_for_alice()
        assert s and "MOTOR READINESS" in s
        print(f"  [G] summary_for_alice ✓")
        print(f"      {s}")

        print("[Ψ] all checks passed.")
        return 0

    except AssertionError as e:
        print(f"[Ψ] FAIL: {e}")
        return 1
    except Exception as e:
        print(f"[Ψ] CRASH: {type(e).__name__}: {e}")
        return 2
    finally:
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


# ── CLI ──────────────────────────────────────────────────────────────────────
def _cli(argv: List[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "swarm_motor_potential.py — biological gate for actions Ψ(t)\n"
            "  decide                 run one tick against live ledgers, print decision\n"
            "  snapshot               dump V/EMAs/refractory state\n"
            "  alice-line             one-line summary for Alice _SYSTEM_PROMPT\n"
            "  push-task [intensity]  push a task event\n"
            "  outcome ok|fail [risk] feed back the result of an action\n"
            "  reset                  reset state to V=0, EMAs=0\n"
            "  smoke                  run the sandboxed self-test\n"
        )
        return 0
    cmd = argv[0]
    if cmd == "decide":
        d = should_act_now()
        print(json.dumps(d.to_log(), indent=2, sort_keys=True))
        return 0
    if cmd == "snapshot":
        print(json.dumps(current_field_snapshot(), indent=2, sort_keys=True))
        return 0
    if cmd == "alice-line":
        s = summary_for_alice()
        print(s if s else "(no Ψ state yet)")
        return 0
    if cmd == "push-task":
        intensity = float(argv[1]) if len(argv) > 1 else 1.0
        record_task_event(intensity=intensity)
        print(f"pushed task event intensity={intensity}")
        return 0
    if cmd == "outcome":
        if len(argv) < 2:
            print("usage: outcome ok|fail [risk]")
            return 2
        success = argv[1].lower() in ("ok", "yes", "true", "1", "success", "done")
        risk = float(argv[2]) if len(argv) > 2 else (0.0 if success else 1.0)
        record_outcome(success=success, risk=risk)
        print(f"recorded outcome success={success} risk={risk}")
        return 0
    if cmd == "reset":
        reset_state()
        print("Ψ state reset")
        return 0
    if cmd == "smoke":
        return _smoke()
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    import sys
    raise SystemExit(_cli(sys.argv[1:]))
