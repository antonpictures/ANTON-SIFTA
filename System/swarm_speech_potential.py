#!/usr/bin/env python3
"""
System/swarm_speech_potential.py — Stigmergic Speech Potential (SSP)
═══════════════════════════════════════════════════════════════════════════════
SIFTA Cortical Suite — Broca-area gating organ
Module version: 2026-04-19.v1     Author: C47H (Cursor IDE, Opus 4.7 High)
Companion DYOR: Documents/C47H_DYOR_STIGMERGIC_SPEECH_POTENTIAL_2026-04-19.md

WHAT THIS REPLACES
──────────────────
The hardcoded `_SILENT_MARKERS` set + "(silent)" prompt rule in
`Applications/sifta_talk_to_alice_widget.py`. Speech becomes a continuous
threshold-crossing of an accumulated biological field (Lapicque 1907;
Hodgkin-Huxley 1952; Gerstner-Kistler 2002 §5.3) driven by SIFTA's
existing pheromone ledgers (Grassé 1959; Dorigo 1996). No strings.

THE GOVERNING EQUATION (escape-noise leaky integrate-and-fire)
──────────────────────────────────────────────────────────────
    dV/dt  =  − (V − V_rest) / τ_m  +  I(t)

    I(t)   =   α·S(t)                     serotonin baseline
              + β·ΔD(t)                   phasic dopamine (Schultz 1998)
              − γ·C(t)                    cortisol / inhibition
              + δ·∫E_env(s)·e^{−(t−s)/τ_e} ds      stigmergic integral
              + ε·P_turn(t)               conversational pressure
              − ζ·I_listener(t)           listener veto

    P[spike in (t,t+Δt)]  =  σ((V − V_th)/Δu) · (Δt/τ_m)
                              if (t − t_last_spike) > τ_ref else 0

After spike:  V ← V_reset,  t_last_spike ← t

We integrate the membrane equation analytically per call (closed-form
zero-order hold) so callers can poll at irregular intervals without
introducing integration error:

    V(t+Δt)  =  V(t)·e^{−Δt/τ_m}  +  I·τ_m·(1 − e^{−Δt/τ_m})

PERSISTENCE
───────────
  .sifta_state/speech_potential.json
      { "V": float, "t_last_update": ts, "t_last_spike": ts,
        "dopamine_ema": float, "version": "..." }

  .sifta_state/speech_potential_coefficients.json
      { "alpha": …, "beta": …, "gamma": …, "delta": …, "epsilon": …,
        "zeta": …,  "tau_m_s": …, "tau_e_s": …, "tau_ref_s": …,
        "V_th": …, "V_reset": …, "Delta_u": …, "version": "..." }

DESIGN PROPERTIES
─────────────────
  • PURE FUNCTION OVER STATE. The single mutating call is `should_speak()`.
    It reads ledgers, advances V, decides spike, persists state, returns a
    `SpeechDecision` dataclass with the decision, the potential, the firing
    probability, and a human-readable biological reason string.
  • TOTAL. Never raises on missing ledgers / corrupt rows / clock skew.
    Worst case is "no inputs available" → V leaks toward V_rest → no spike.
  • CHEAP. ~1 ms on warm disk. Tail-reads at most ~64 KB per JSONL.
  • HONEST. The reason string is the actual biological reason
    ("V=0.42, P=0.03, refractory clear" or "listener active, gate vetoed"),
    not a hardcoded phrase. The Architect can hear physics, not theatre.
"""
from __future__ import annotations

import json
import math
import os
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

MODULE_VERSION = "2026-04-19.v1"

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)

_STATE_PATH         = _STATE_DIR / "speech_potential.json"
_COEFFS_PATH        = _STATE_DIR / "speech_potential_coefficients.json"
_HEARTBEAT_PATH     = _STATE_DIR / "clinical_heartbeat.json"
_REWARDS_PATH       = _STATE_DIR / "stgm_memory_rewards.jsonl"
_WORK_PATH          = _STATE_DIR / "work_receipts.jsonl"
_IDE_TRACE_PATH     = _STATE_DIR / "ide_stigmergic_trace.jsonl"
_CONVERSATION_PATH  = _STATE_DIR / "alice_conversation.jsonl"


# ── Default coefficients (overridden by on-disk file once it exists) ─────────
@dataclass
class SSPCoefficients:
    """Hand-set initial weights — see DYOR §D.1 for justification.
    All persisted to disk on first call so the Architect (or a future
    learner) can tune them live without restarting the talk widget."""
    alpha:    float = 0.30   # serotonin baseline
    beta:     float = 0.50   # dopamine phasic delta
    gamma:    float = 0.40   # cortisol / inhibition
    delta:    float = 0.25   # stigmergic accumulation
    epsilon:  float = 0.20   # turn-taking pressure
    zeta:     float = 1.50   # listener inhibition (strong veto)

    tau_m_s:   float = 30.0  # membrane time constant (slow conv. dynamics)
    tau_e_s:   float = 60.0  # stigmergic memory decay constant
    tau_ref_s: float =  2.0  # refractory period after speech

    # Firing threshold is *calibrated to the actual input range observed
    # under SIFTA's current heartbeat*, not a textbook value. With the
    # heartbeat presently reading SOCIAL_DEFEAT (α·S=0.15, γ·C=−0.28) the
    # net standing input is roughly 0 and an active turn (P_turn≈1) plus
    # some stigmergy adds about +0.4. V_th = 0.4 means: a quiet body stays
    # quiet, but normal conversational engagement reliably crosses
    # threshold. Raise to 1.0 for "shy mode," lower toward 0.2 for
    # "talkative mode." All live-tunable from the on-disk coefficients.
    V_th:    float = 0.4     # firing threshold (calibrated, not textbook)
    V_reset: float = -0.3    # post-spike reset (small hyperpolarization)
    V_rest:  float = 0.0     # rest membrane potential
    Delta_u: float = 0.10    # escape-noise softness

    version: str = MODULE_VERSION


# ── Mutable runtime state persisted to disk ──────────────────────────────────
@dataclass
class SSPState:
    V:               float = 0.0
    t_last_update:   float = 0.0
    t_last_spike:    float = 0.0   # 0.0 means "never spiked" (always > τ_ref)
    dopamine_ema:    float = 1.0   # exponential moving average of normalized D
    version:         str   = MODULE_VERSION


# ── The decision returned to the caller ──────────────────────────────────────
@dataclass
class SpeechDecision:
    speak:                 bool          # the gate's verdict
    V:                     float         # membrane potential after this tick
    spike_prob:            float         # P[spike in this Δt]
    refractory_remaining:  float         # seconds; 0 if clear
    listener_active:       bool          # was the user speaking?
    inputs:                dict          # raw I components (debug)
    reason:                str           # human-readable biological reason

    def to_log(self) -> dict:
        d = asdict(self)
        d["ts"] = time.time()
        d["module_version"] = MODULE_VERSION
        return d


# ── Persistence helpers (total, never raise) ─────────────────────────────────
def _safe_read_json(path: Path) -> Optional[dict]:
    try:
        if not path.exists() or path.stat().st_size > 1_000_000:
            return None
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _safe_write_json(path: Path, payload: dict) -> None:
    """Best-effort atomic write. Drops silently on failure (next call retries).
    Atomicity matters: a half-written speech_potential.json on a crash would
    poison the next read and force V back to 0 — losing biological history."""
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


def _load_coefficients() -> SSPCoefficients:
    raw = _safe_read_json(_COEFFS_PATH)
    if not raw:
        coeffs = SSPCoefficients()
        _safe_write_json(_COEFFS_PATH, asdict(coeffs))
        return coeffs
    defaults = asdict(SSPCoefficients())
    merged = {k: raw.get(k, defaults[k]) for k in defaults}
    return SSPCoefficients(**merged)


def _load_state() -> SSPState:
    raw = _safe_read_json(_STATE_PATH)
    if not raw:
        return SSPState(t_last_update=time.time())
    defaults = asdict(SSPState())
    merged = {k: raw.get(k, defaults[k]) for k in defaults}
    return SSPState(**merged)


def _save_state(state: SSPState) -> None:
    _safe_write_json(_STATE_PATH, asdict(state))


def _tail_jsonl_rows(path: Path, max_bytes: int = 65536) -> List[dict]:
    """Tail-read up to `max_bytes` and return parsed JSON rows. Never raises."""
    if not path.exists():
        return []
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            read = min(size, max_bytes)
            f.seek(size - read)
            tail = f.read(read).splitlines()
    except Exception:
        return []
    rows: List[dict] = []
    for raw in tail:
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


# ── Input readers (each returns a normalized scalar) ─────────────────────────
def _read_serotonin() -> float:
    """S(t) ∈ [0, 1]. Reads .sifta_state/clinical_heartbeat.json.

    Honesty correction: literal 0.0 in the heartbeat almost certainly means
    'uninitialized' rather than 'clinically zero' — real serotonin of 0
    would be lethal, not subdued. We treat exactly 0.0 as missing data
    and return 0.5 (neutral baseline). Any positive value is taken at face."""
    hb = _safe_read_json(_HEARTBEAT_PATH) or {}
    vs = hb.get("vital_signs") or {}
    try:
        raw = float(vs.get("serotonin_dominance", 0.0))
    except (TypeError, ValueError):
        return 0.5
    if raw == 0.0:
        return 0.5
    return max(0.0, min(1.0, raw))


def _read_dopamine_normalized() -> float:
    """D(t) ≈ heartbeat.dopamine_concentration / 200 (baseline unit).
    Returns the neutral baseline (1.0) if the field is missing or 0.
    Same uninitialized-vs-zero discipline as serotonin: a literal 0
    is missing data, not 'no dopamine,' which would also be lethal."""
    hb = _safe_read_json(_HEARTBEAT_PATH) or {}
    vs = hb.get("vital_signs") or {}
    try:
        raw = float(vs.get("dopamine_concentration", 0.0))
    except (TypeError, ValueError):
        return 1.0
    if raw == 0.0:
        return 1.0
    return raw / 200.0


def _cortisol_proxy(serotonin_norm: float) -> float:
    """C(t) ∈ [0, 1]. Read computational_posture as the qualitative truth
    the heartbeat is actually trying to communicate, and fall back to
    (1 − serotonin) only when the posture string is uninformative.

    Honest mapping:
      contains 'SOCIAL_DEFEAT' or 'STRESS' → 0.70   (elevated, not max)
      contains 'CALM' or 'NORMAL' or 'ADAPTIVE' → 0.20
      otherwise → 1 − S, clipped to [0.2, 0.8] so the proxy can never
                  produce the absurd 'maximum cortisol' just because
                  serotonin happens to be uninitialized."""
    hb = _safe_read_json(_HEARTBEAT_PATH) or {}
    vs = hb.get("vital_signs") or {}
    posture = str(vs.get("computational_posture", "")).upper()
    if "SOCIAL_DEFEAT" in posture or "STRESS" in posture:
        return 0.70
    if "CALM" in posture or "NORMAL" in posture or "ADAPTIVE" in posture:
        return 0.20
    return max(0.20, min(0.80, 1.0 - serotonin_norm))


def _read_env_integral(now: float, tau_e_s: float) -> float:
    """∫ E_env(s)·exp(−(t−s)/τ_e) ds — discrete kernel sum over recent rows.
    Sources: stgm_memory_rewards (`amount`), work_receipts (`work_value`),
    ide_stigmergic_trace (count = 0.1 each). Each row contributes its
    weight × exp(−age/τ_e). Cap at 5.0 so a torrent of writes can't
    monopolize the gate."""
    total = 0.0
    horizon = now - 5.0 * tau_e_s
    for path, weight_key, default_w in [
        (_REWARDS_PATH, "amount",     0.1),
        (_WORK_PATH,    "work_value", 0.1),
        (_IDE_TRACE_PATH, None,       0.1),  # presence-only signal
    ]:
        for row in _tail_jsonl_rows(path):
            ts = row.get("ts") or row.get("timestamp")
            if not isinstance(ts, (int, float)) or ts < horizon or ts > now:
                continue
            if weight_key:
                try:
                    w = float(row.get(weight_key, default_w))
                except (TypeError, ValueError):
                    w = default_w
            else:
                w = default_w
            total += w * math.exp(-(now - ts) / tau_e_s)
    return min(total, 5.0)


def _turn_pressure(now: float) -> float:
    """P_turn(t) ∈ [0, 1]. Rises with time since the last user utterance,
    and is reset only when Alice has actually *taken the turn* — i.e.
    vocalized something that was NOT a silence marker. A silent log row
    does not constitute an uptake (Sacks-Schegloff-Jefferson 1974: only
    speech takes the floor; staying silent leaves the floor open and the
    pressure to fill it keeps rising). Reaches ~1.0 about 8 s after the
    user finishes."""
    rows = _tail_jsonl_rows(_CONVERSATION_PATH, max_bytes=16384)
    last_user_ts = 0.0
    last_alice_spoken_ts = 0.0   # Alice's last *real* (non-silent) reply
    for row in rows:
        ts = row.get("ts") or row.get("timestamp")
        role = row.get("role")
        text = (row.get("text") or "").strip().lower()
        if not isinstance(ts, (int, float)):
            continue
        if role == "user":
            if ts > last_user_ts:
                last_user_ts = ts
        elif role == "alice" and not text.startswith("(silent"):
            if ts > last_alice_spoken_ts:
                last_alice_spoken_ts = ts
    if last_user_ts == 0.0 or last_user_ts <= last_alice_spoken_ts:
        return 0.0
    age = max(0.0, now - last_user_ts)
    return min(1.0, age / 8.0)


def _listener_active() -> bool:
    """I_listener — is the user currently speaking? Best signal we have is
    `_BROCA_SPEAKING` half-duplex flag inverted with mic VAD inferred from
    the absence of recent `audio_ingress_log` writes during a long silence,
    but that's expensive. v1 uses the conservative answer:
        listener_active := (last conversation row was a user turn within
                            the last 1.5 s)
    which captures the case where the user is still mid-sentence."""
    rows = _tail_jsonl_rows(_CONVERSATION_PATH, max_bytes=4096)
    if not rows:
        return False
    last = rows[-1]
    if last.get("role") != "user":
        return False
    ts = last.get("ts") or last.get("timestamp")
    if not isinstance(ts, (int, float)):
        return False
    return (time.time() - ts) < 1.5


# ── Membrane dynamics (closed-form discrete update) ──────────────────────────
def _advance_membrane(V_prev: float, I_const: float, dt: float,
                      tau_m: float) -> float:
    """Closed-form solution to dV/dt = -(V-V_rest)/τ_m + I, V_rest=0,
    over interval `dt` with constant `I`. Equivalent to zero-order-hold
    discretization. Avoids numerical integration; exact for any dt > 0."""
    if dt <= 0.0:
        return V_prev
    decay = math.exp(-dt / tau_m)
    V_inf = I_const * tau_m   # steady-state attractor under constant I
    return V_prev * decay + V_inf * (1.0 - decay)


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        ex = math.exp(-x)
        return 1.0 / (1.0 + ex)
    ex = math.exp(x)
    return ex / (1.0 + ex)


def _rescaled_potential_for_decision(V: float, tau_m: float) -> float:
    """We let V drift up to V_inf = I·τ_m for numerical headroom but the
    threshold V_th is in 'natural' units. Scale V by 1/τ_m so V near
    threshold ≈ I near 1.0."""
    return V / tau_m


# ── The public API ───────────────────────────────────────────────────────────
def should_speak(*, dt_override: Optional[float] = None) -> SpeechDecision:
    """The single call the talk widget makes per candidate utterance.

    Reads heartbeat + ledgers, advances V over the elapsed time since the
    previous call, samples a Bernoulli at the escape-noise rate, optionally
    fires (V ← V_reset), persists state, returns a SpeechDecision.

    Parameters
    ----------
    dt_override : Optional[float]
        Force a specific Δt instead of using `now - t_last_update`.
        Useful for unit tests; production callers leave it None.
    """
    coeffs = _load_coefficients()
    state  = _load_state()
    now    = time.time()
    dt     = dt_override if dt_override is not None else max(
        0.0, min(60.0, now - state.t_last_update)
    )
    if state.t_last_update == 0.0:
        dt = 0.0  # first call ever: don't double-leak from epoch

    # ── Read inputs (all normalized) ────────────────────────────────────────
    S       = _read_serotonin()
    D_norm  = _read_dopamine_normalized()
    C       = _cortisol_proxy(S)
    E_env   = _read_env_integral(now, coeffs.tau_e_s)
    P_turn  = _turn_pressure(now)
    listen  = _listener_active()

    # ── Phasic dopamine: ΔD = D − D̄, then update D̄ via slow EMA ──────────
    if state.dopamine_ema <= 0.0:
        state.dopamine_ema = D_norm
    delta_D = D_norm - state.dopamine_ema
    ema_alpha = 1.0 - math.exp(-dt / max(120.0, coeffs.tau_e_s * 2.0))
    state.dopamine_ema = (1.0 - ema_alpha) * state.dopamine_ema + ema_alpha * D_norm

    # ── Compose input current ──────────────────────────────────────────────
    I = (
        coeffs.alpha    * S
        + coeffs.beta   * delta_D
        - coeffs.gamma  * C
        + coeffs.delta  * E_env
        + coeffs.epsilon * P_turn
        - coeffs.zeta   * (1.0 if listen else 0.0)
    )

    # ── Advance the membrane (closed-form, exact for this dt) ──────────────
    V_new = _advance_membrane(state.V, I, dt, coeffs.tau_m_s)

    # ── Refractory check ────────────────────────────────────────────────────
    refractory_remaining = max(
        0.0, coeffs.tau_ref_s - (now - state.t_last_spike)
    )
    in_refractory = (state.t_last_spike > 0.0
                     and refractory_remaining > 0.0)

    # ── Spike probability per this tick ────────────────────────────────────
    V_eff = _rescaled_potential_for_decision(V_new, coeffs.tau_m_s)
    rate_factor = max(dt, 0.001) / coeffs.tau_m_s   # spike-rate × dt
    spike_prob = (
        0.0 if in_refractory
        else min(1.0, _sigmoid((V_eff - coeffs.V_th) / coeffs.Delta_u)
                       * rate_factor * coeffs.tau_m_s)
        # Multiplying by τ_m here cancels the rate_factor's 1/τ_m so the
        # decision is "is the *instantaneous* P high enough to fire in dt?"
        # which is the standard escape-noise formulation. Capped at 1.
    )

    fired = (random.random() < spike_prob) and not in_refractory

    # ── Build the honest reason string ─────────────────────────────────────
    if listen:
        reason = (f"listener-active veto (ζ={coeffs.zeta}); "
                  f"V={V_eff:+.2f}, P=0")
    elif in_refractory:
        reason = (f"refractory ({refractory_remaining:.2f}s remaining of "
                  f"{coeffs.tau_ref_s:.1f}s); V={V_eff:+.2f}")
    elif fired:
        reason = (f"FIRED: V={V_eff:+.2f} ≥ V_th={coeffs.V_th:.2f}, "
                  f"P={spike_prob:.3f}")
    else:
        reason = (f"sub-threshold: V={V_eff:+.2f} < V_th={coeffs.V_th:.2f}, "
                  f"P={spike_prob:.3f}")

    # ── Persist ─────────────────────────────────────────────────────────────
    state.V = V_new if not fired else coeffs.V_reset * coeffs.tau_m_s
    state.t_last_update = now
    if fired:
        state.t_last_spike = now
    _save_state(state)

    return SpeechDecision(
        speak=fired,
        V=V_eff,
        spike_prob=spike_prob,
        refractory_remaining=refractory_remaining,
        listener_active=listen,
        inputs={
            "S": S, "D_norm": D_norm, "delta_D": delta_D, "C": C,
            "E_env": E_env, "P_turn": P_turn,
            "I": I, "dt": dt,
        },
        reason=reason,
    )


def reset_state() -> None:
    """Drop on-disk state so V starts from V_rest. Useful when the
    Architect wants a clean baseline (e.g. after a long quiet day).
    Coefficients are NOT reset; tuning persists."""
    try:
        if _STATE_PATH.exists():
            _STATE_PATH.unlink()
    except Exception:
        pass


def current_field_snapshot() -> dict:
    """Read-only peek at the field for UI / dashboards. Does NOT advance V."""
    coeffs = _load_coefficients()
    state  = _load_state()
    return {
        "V_natural": _rescaled_potential_for_decision(state.V, coeffs.tau_m_s),
        "V_raw":     state.V,
        "V_th":      coeffs.V_th,
        "t_last_spike": state.t_last_spike,
        "dopamine_ema": state.dopamine_ema,
        "module_version": MODULE_VERSION,
    }


# ── Self-test smoke ──────────────────────────────────────────────────────────
def _smoke() -> int:
    """Confirm the module is wired correctly without polluting real state.
    Returns process exit code (0 OK, 1 failed)."""
    print(f"[SSP] swarm_speech_potential.py v{MODULE_VERSION} smoke")
    failures: List[str] = []

    # Use a sandbox state path so the smoke doesn't perturb live SSP state.
    global _STATE_PATH, _COEFFS_PATH
    real_state, real_coeffs = _STATE_PATH, _COEFFS_PATH
    sandbox = _STATE_DIR / "_ssp_smoke"
    sandbox.mkdir(exist_ok=True)
    _STATE_PATH = sandbox / "state.json"
    _COEFFS_PATH = sandbox / "coeffs.json"
    try:
        if _STATE_PATH.exists():
            _STATE_PATH.unlink()
        if _COEFFS_PATH.exists():
            _COEFFS_PATH.unlink()

        # A. Cold start: V at rest, no spike, no listener veto unless ledger says so.
        d0 = should_speak(dt_override=0.0)
        print(f"  [A] cold:    V={d0.V:+.3f}  P={d0.spike_prob:.3f}  spoke={d0.speak}")
        if d0.speak:
            failures.append("A: cold start spoke spuriously")

        # B. Many ticks of moderate input → V rises monotonically toward steady state.
        coeffs = _load_coefficients()
        # Force a strong constant input by bypassing the readers: temporarily
        # patch _advance_membrane caller behaviour via direct math.
        V = 0.0
        I_const = 0.05  # steady "calm + a little stigmergy"
        for _ in range(200):
            V = _advance_membrane(V, I_const, dt=1.0, tau_m=coeffs.tau_m_s)
        V_inf_expected = I_const * coeffs.tau_m_s
        if abs(V - V_inf_expected) > 0.1:
            failures.append(
                f"B: membrane did not converge to V_inf "
                f"(got {V:.3f}, expected {V_inf_expected:.3f})"
            )
        else:
            print(f"  [B] leak:    V→V_inf = {V:.3f} (expected ~{V_inf_expected:.3f})")

        # C. Sigmoid sanity at V_eff = V_th: P_inst = 0.5 (before rate scaling).
        s = _sigmoid(0.0)
        if abs(s - 0.5) > 1e-9:
            failures.append("C: sigmoid(0) ≠ 0.5")
        else:
            print("  [C] sigmoid: σ(0)=0.5 ✓")

        # D. Refractory: forcing a spike then immediate re-call → blocked.
        state = SSPState(V=0.0, t_last_update=time.time(),
                         t_last_spike=time.time())
        _save_state(state)
        d_ref = should_speak(dt_override=0.5)
        if d_ref.speak:
            failures.append("D: spoke during refractory period")
        elif "refractory" not in d_ref.reason.lower():
            failures.append(f"D: refractory check missing reason: {d_ref.reason}")
        else:
            print(f"  [D] refractory: blocked, "
                  f"{d_ref.refractory_remaining:.2f}s remaining ✓")

        # E. After τ_ref + ε the gate is clear again.
        time.sleep(coeffs.tau_ref_s + 0.1)
        d_clear = should_speak(dt_override=0.1)
        if d_clear.refractory_remaining > 0.01:
            failures.append("E: refractory did not clear")
        else:
            print(f"  [E] refractory: cleared after {coeffs.tau_ref_s + 0.1:.2f}s ✓")

        # F. Round-trip persistence.
        s1 = _load_state()
        s1.dopamine_ema = 0.42
        _save_state(s1)
        s2 = _load_state()
        if abs(s2.dopamine_ema - 0.42) > 1e-9:
            failures.append("F: state did not round-trip through disk")
        else:
            print("  [F] persistence: state survives disk round-trip ✓")

        # G. Field snapshot is non-mutating.
        snap_before = current_field_snapshot()
        snap_after  = current_field_snapshot()
        if snap_before != snap_after:
            failures.append("G: current_field_snapshot mutated state")
        else:
            print("  [G] snapshot: read-only ✓")

    finally:
        _STATE_PATH, _COEFFS_PATH = real_state, real_coeffs

    if failures:
        print(f"\n[SSP] FAIL — {len(failures)} issue(s):")
        for f in failures:
            print(f"  • {f}")
        return 1
    print("\n[SSP] OK — all 7 checks passed.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_smoke())
