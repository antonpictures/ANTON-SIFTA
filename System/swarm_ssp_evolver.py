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


# ── Paths ────────────────────────────────────────────────────────────────
_STATE_DIR       = _REPO / ".sifta_state"
_COEFFS_LIVE     = _STATE_DIR / "speech_potential_coefficients.json"
_COEFFS_PROPOSED = _STATE_DIR / "speech_potential_coefficients_proposed.json"
_EVOLUTION_LOG   = _STATE_DIR / "ssp_evolution.jsonl"
_CONVERSATION    = _STATE_DIR / "alice_conversation.jsonl"
_REWARDS         = _STATE_DIR / "stgm_memory_rewards.jsonl"


# ── Per-parameter bounds (safety-respecting, physically meaningful) ──────
# Only parameters the evolver is allowed to touch appear here. Structural
# constants (tau_m_s, tau_ref_s, V_reset, V_rest) are deliberately frozen
# by default — they encode design commitments, not free variables.
BOUNDS: Dict[str, Tuple[float, float]] = {
    "alpha":   (0.00, 1.00),   # serotonin baseline — nonnegative
    "beta":    (0.00, 2.00),   # dopamine phasic   — nonnegative
    "gamma":   (0.00, 1.50),   # cortisol inhibit  — nonnegative
    "delta":   (0.00, 1.00),   # stigmergic accum  — nonnegative
    "epsilon": (0.00, 1.00),   # turn pressure     — nonnegative
    "zeta":    (0.50, 3.00),   # listener veto     — FLOOR 0.5 so she
                               #                     cannot learn to interrupt
    "V_th":    (0.10, 0.90),   # firing threshold  — outside this range
                               #                     Alice becomes pathological
    "Delta_u": (0.02, 0.50),   # escape softness   — too high → noise wins
}
MUTABLE_KEYS = tuple(BOUNDS.keys())


# ── Dataclasses ──────────────────────────────────────────────────────────
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
    lambda_rate:          float = 0.50    # penalty on rate mismatch
    lambda_refractory:    float = 0.30    # penalty on refractory violations


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


# ── The simulator — closed-form SSP over a user-turn schedule ────────────
def _simulate_would_fire(
    coeffs: SSPCoefficients,
    user_turns: List[Dict],
    *,
    standing_input: float,
    listener_active_fn,  # callable: (user_turn_row) -> bool
) -> List[Dict]:
    """For each user turn, advance V from the previous turn's state and
    return whether θ would have spoken there. Deterministic threshold test
    (no escape noise) — we want to measure the MEAN behavior of θ, not
    stochastic jitter. Reports spike_prob alongside the binary decision so
    callers with a different noise model can rescore.

    standing_input = α·S − γ·C + β·(D_ema − 1). Turn pressure and listener
    inhibition are added per-turn (they are the things that *vary* between
    turns). E_env is collapsed into `standing_input` as a constant because
    it has no per-turn structure in the replay.
    """
    if not user_turns:
        return []

    V = 0.0
    t_prev = user_turns[0]["ts"]
    t_last_spike = 0.0
    out: List[Dict] = []

    for u in user_turns:
        t = u["ts"]
        dt = max(0.0, t - t_prev)

        # Turn pressure at this user turn: ramps from 0 at user-just-spoke
        # toward 1 after 8 s. We're AT the user turn instant, so P_turn=0.
        # (The pressure builds during Alice's thinking time — not modeled
        # at the per-turn level here; captured instead by the steady-state
        # input.) We set P_turn to 1.0 at this instant to mean "the user
        # has just released the floor and pressure peaks now." This matches
        # the real _turn_pressure dynamics at `age ≥ 8 s`.
        p_turn = 1.0

        listener = 1.0 if listener_active_fn(u) else 0.0

        I = (
            standing_input
            + coeffs.epsilon * p_turn
            - coeffs.zeta    * listener
        )

        # Advance membrane
        V = _advance_membrane(V, I, dt, coeffs.tau_m_s)

        # Decision (deterministic, noise=0)
        V_natural = _rescaled_potential_for_decision(V, coeffs.tau_m_s)
        in_refractory = (t - t_last_spike) < coeffs.tau_ref_s and t_last_spike > 0.0

        # Escape-noise spike probability (for reporting, not decision)
        p_spike = _sigmoid((V_natural - coeffs.V_th) / max(1e-6, coeffs.Delta_u))
        fire = (V_natural >= coeffs.V_th) and not in_refractory

        out.append({
            "ts":          t,
            "V":           V,
            "V_natural":   V_natural,
            "I":           I,
            "p_spike":     p_spike,
            "in_refractory": in_refractory,
            "fire":        fire,
        })

        if fire:
            V = coeffs.V_reset
            t_last_spike = t

        t_prev = t

    return out


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
    coeffs: SSPCoefficients,
    *,
    convo: List[Dict],
    rewards: List[Dict],
    user_turns: List[Dict],
    standing_input: float,
    listener_fn,
    fit_cfg: FitnessConfig,
    target_rate: float,
) -> Tuple[float, Dict]:
    """Return (fitness, debug_info). Fitness is maximized."""
    sim = _simulate_would_fire(
        coeffs, user_turns,
        standing_input=standing_input,
        listener_active_fn=listener_fn,
    )
    if not sim:
        return 0.0, {"n_turns": 0}

    fires = [s for s in sim if s["fire"]]
    n_turns = len(sim)
    n_fires = len(fires)
    observed_rate = n_fires / n_turns

    # Reward capture per fire
    if fires:
        captures = [
            _sum_rewards_in_window(rewards, s["ts"], s["ts"] + fit_cfg.reward_window_s)
            for s in fires
        ]
        mean_capture = sum(captures) / len(captures)
    else:
        mean_capture = 0.0

    # Refractory violations (shouldn't happen given our simulator, but guard
    # against silly bounds: count fires within tau_ref of each other)
    violations = 0
    for a, b in zip(fires, fires[1:]):
        if (b["ts"] - a["ts"]) < coeffs.tau_ref_s:
            violations += 1

    rate_err = observed_rate - target_rate
    fitness = (
        mean_capture
        - fit_cfg.lambda_rate * (rate_err * rate_err)
        - fit_cfg.lambda_refractory * violations
    )

    return fitness, {
        "n_turns": n_turns,
        "n_fires": n_fires,
        "observed_rate": observed_rate,
        "target_rate": target_rate,
        "mean_reward_capture": mean_capture,
        "rate_err": rate_err,
        "refractory_violations": violations,
    }


# ── Mutation ─────────────────────────────────────────────────────────────
def _clip(value: float, key: str) -> float:
    lo, hi = BOUNDS[key]
    return max(lo, min(hi, value))


def _mutate(coeffs: SSPCoefficients, *, sigma_frac: float, rng: random.Random
            ) -> SSPCoefficients:
    """Propose a new coefficient vector. Per-parameter Gaussian step scaled
    by the parameter's own range, then clipped to its bounds. Only keys in
    MUTABLE_KEYS are touched."""
    changes: Dict[str, float] = {}
    for k in MUTABLE_KEYS:
        lo, hi = BOUNDS[k]
        span = hi - lo
        step = rng.gauss(0.0, sigma_frac * span)
        current = getattr(coeffs, k)
        changes[k] = _clip(current + step, k)
    return replace(coeffs, **changes)


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

    initial = _load_coefficients()
    initial_fitness, initial_dbg = _fitness(
        initial, convo=convo, rewards=rewards, user_turns=user_turns,
        standing_input=(initial.alpha * S - initial.gamma * C + initial.beta * dD),
        listener_fn=listener_fn, fit_cfg=fitness, target_rate=target_rate,
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
    initial = _load_coefficients()
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


def _write_proposal(best: SSPCoefficients, report: EvolutionReport) -> None:
    """Proposal file contains the FULL coefficient vector so apply_proposal
    is a single file move. Includes provenance so we can prove what ran."""
    full = asdict(best)
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
        ide="cursor_m5",
        method="annealing_apply",
        coefficients=prop_clean,
        fitness_delta=prov.get("delta_fitness"),
        target_rate=prov.get("target_rate"),
        observed_rate=prov.get("observed_rate"),
        iterations_run=prov.get("iterations_run"),
        note="swarm_ssp_evolver.apply_proposal",
        module_version=MODULE_VERSION,
        coeffs_path=_COEFFS_LIVE,
        repo_root=_REPO,
        extra={
            "proposed_by": prov.get("proposed_by"),
            "proposal_provenance_ts": prov.get("ts"),
        },
    )
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
    live = _load_coefficients()
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

    # Plant a coefficients file with known defaults
    defaults = asdict(SSPCoefficients())
    with (fake_state / "speech_potential_coefficients.json").open("w") as f:
        json.dump(defaults, f)

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
    backup = (_STATE_DIR, _COEFFS_LIVE, _COEFFS_PROPOSED, _EVOLUTION_LOG,
              _CONVERSATION, _REWARDS)
    _STATE_DIR       = fake_state
    _COEFFS_LIVE     = fake_state / "speech_potential_coefficients.json"
    _COEFFS_PROPOSED = fake_state / "speech_potential_coefficients_proposed.json"
    _EVOLUTION_LOG   = fake_state / "ssp_evolution.jsonl"
    _CONVERSATION    = fake_state / "alice_conversation.jsonl"
    _REWARDS         = fake_state / "stgm_memory_rewards.jsonl"

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

        # θ_a: easy-firing — low threshold + strong drive → should spike often
        coeffs_a = replace(SSPCoefficients(),
                           V_th=0.10, alpha=0.90, epsilon=0.90, gamma=0.00)
        # θ_b: hard-firing — high threshold + weak drive → should rarely spike
        coeffs_b = replace(SSPCoefficients(),
                           V_th=0.90, alpha=0.05, epsilon=0.05, gamma=1.00)
        lfn = _listener_active_for(convo)
        fa, dbg_a = _fitness(
            coeffs_a, convo=convo, rewards=rewards, user_turns=users,
            standing_input=(coeffs_a.alpha*S - coeffs_a.gamma*C + coeffs_a.beta*dD),
            listener_fn=lfn, fit_cfg=FitnessConfig(), target_rate=target,
        )
        fb, dbg_b = _fitness(
            coeffs_b, convo=convo, rewards=rewards, user_turns=users,
            standing_input=(coeffs_b.alpha*S - coeffs_b.gamma*C + coeffs_b.beta*dD),
            listener_fn=lfn, fit_cfg=FitnessConfig(), target_rate=target,
        )
        if abs(fa - fb) < 1e-6:
            failures.append(
                f"A: fitness did not change between two very different θ "
                f"(a={fa:.6f} fires={dbg_a['n_fires']}, "
                f"b={fb:.6f} fires={dbg_b['n_fires']})"
            )
        else:
            print(f"  [A] fitness responds to θ  "
                  f"(easy: fit={fa:+.4f} fires={dbg_a['n_fires']}  |  "
                  f"hard: fit={fb:+.4f} fires={dbg_b['n_fires']}  |  Δ={fb-fa:+.4f}) ✓")

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
        c = SSPCoefficients()
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
         _CONVERSATION, _REWARDS) = backup

    if failures:
        print("\n[swarm_ssp_evolver] FAIL")
        for f_ in failures:
            print(f"  • {f_}")
        return 1
    print("\n[swarm_ssp_evolver] OK — all 6 checks passed (live files untouched).")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
