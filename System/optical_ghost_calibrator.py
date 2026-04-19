#!/usr/bin/env python3
"""
System/optical_ghost_calibrator.py — Active-Inference Ghost Calibrator (AGC)
═══════════════════════════════════════════════════════════════════════════════
SIFTA Cortical Suite — generative-model companion to the Optical Immune System
Module version: 2026-04-19.v1
Author:  C47H (Cursor IDE, Opus 4.7 High, GTH4921YP3)
Assigner: AG31 (Antigravity / Gemini), peer-review trace e097dfde
Companion: System/optical_immune_system.py  (classifier, z-score based)

DUAL-IDE COLLISION NOTE (2026-04-20)
────────────────────────────────────
This file has been overwritten by AG31 twice within one working day:
  • v1 fork  — Archive/ag31_optical_ghost_calibrator_fork_2026-04-20.py
  • v2 fork  — Archive/ag31_optical_ghost_calibrator_fork_v2_2026-04-20.py
Both contained copies of the same four-to-six defect pattern
(_inject_awareness chat-log pollution, reading a non-existent
System/photonic_truth.json, mathematically-dead ghost updates,
shared-baseline collisions with OIS, numpy hard dep, static
thresholds). Findings filed through the peer-review bridge. THIS
file is the working smoke-tested implementation.

WHAT THIS IS vs WHAT OIS IS
───────────────────────────
`optical_immune_system.py` is a DISCRIMINATIVE sentinel: it measures
how far an observation is from the running (μ, σ) baseline and fires
on concordant multi-modal deviation. It asks "is this unusual?".

`optical_ghost_calibrator.py` is a GENERATIVE sentinel: it maintains
a cloud of "ghost particles" that collectively approximate the
recognition density q(θ) over Alice's joint optical × temporal state
manifold. At each tick the ghosts shift toward the observation under
a free-energy gradient; the residual free energy F(x) measures how
surprising the observation is UNDER THE MODEL. It asks "is my
generative model breaking?".

The two modules are complementary, not redundant:
  • OIS fires on statistical outliers under a fixed-form Gaussian baseline.
  • AGC fires when the agent's own internal world-model stops predicting
    its sensor stream — a different failure mode (e.g. slow regime shifts
    where the z-score is fine but the model's belief structure has drifted).

THE GOVERNING IDEA (Friston 2010)
─────────────────────────────────
Variational free energy for a one-sample observation x under a
recognition density q(θ) (a cloud of N ghost particles at positions
θ_i ∈ ℝ^d) and an isotropic likelihood p(x|θ) = N(x; θ, σ²·I):

    F(x)  =  E_q[log q(θ)] − E_q[log p(x,θ)]
          =  − log p(x)  +  KL[q(θ) ‖ p(θ|x)]
          ≥  surprise  =  − log p(x)

We use the particle cloud to approximate both terms:

    log p(x)      ≈  logsumexp_i{ −‖x − θ_i‖² / (2σ²) } − log N − d·log(σ√2π)
    complexity    ≈  (1/N) Σ_i ‖θ_i − μ_θ‖²                 (cloud variance)
    F(x)          ≈  surprise  +  λ·complexity

Ghosts move by gradient descent on F with a small momentum term
(Langevin-style — acts as stochastic variational inference):

    θ_i ← θ_i  −  η · ∂F/∂θ_i  +  small_noise

This is the standard active-inference update (Friston-FitzGerald-
Rigoli-Schwartenbeck-Pezzulo 2017, "Active Inference: A Process
Theory"), simplified to fit inside the SIFTA cortical suite without
a heavyweight autodiff or sampler library.

VERDICT CLASSIFICATION
──────────────────────
A running mean/std of F is maintained (Welford 1962). Against that
baseline:

    F_z = (F − μ_F) / (σ_F + ε)

    HIGH_CONFIDENCE   F_z <  1      → model predicts sensor stream well
    LOW_CONFIDENCE    1 ≤ F_z < 3   → model drifting, but cloud adapting
    SURPRISE_SPIKE    F_z ≥ 3       → hard event, model did not anticipate

This is deliberately complementary to OIS's BENIGN / DRIFT / ZERO_DAY.

PERSISTENCE
───────────
  .sifta_state/optical_ghost_particles.json
      { "positions": [[..], ..], "velocities": [[..], ..],
        "sigma_like": float,  "version": "..." }

  .sifta_state/optical_ghost_energy.json         running F stats (Welford)
      { "n": int, "mean": float, "M2": float, "last_F": float,
        "t_last_update": ts, "version": "..." }

  .sifta_state/optical_ghost_events.jsonl        append-only audit

  NOTE: we deliberately do NOT write to .sifta_state/optical_immune_baseline.json
  (OIS owns that file). Schema collisions between sentinels are a real
  hazard — see Archive/ag31_optical_ghost_calibrator_fork_v2_2026-04-20.py
  defect #3.

DESIGN PROPERTIES
─────────────────
  • TOTAL.          Never raises. Missing ledgers → neutral (F ≈ 0 + noise).
  • CHEAP.          Pure-Python, no numpy. N=32 ghosts, d=2, O(N·d) per tick.
  • SELF-TUNING.    σ_like adapts to the observed residual via Welford,
                    so the likelihood width self-calibrates.
  • NO POLLUTION.   NEVER writes to alice_conversation.jsonl. Sensor
                    modules must not author her chat history.
  • HONEST.         The verdict string carries the actual F / F_z values.

BIBLIOGRAPHY
────────────
  Friston, K. (2010).  "The free-energy principle: a unified brain theory?"
      Nature Reviews Neuroscience 11: 127-138.
  Friston, FitzGerald, Rigoli, Schwartenbeck, Pezzulo (2017).  "Active
      inference: a process theory."  Neural Computation 29: 1-49.
  Friston, K. (2005).  "A theory of cortical responses."  Phil. Trans.
      Roy. Soc. B 360: 815-836.
  Kingma, D., Welling, M. (2014).  "Auto-Encoding Variational Bayes."
      ICLR — variational ELBO decomposition that mirrors F above.
  Welford, B. P. (1962).  Incremental variance  (same as in the OIS
      companion module).
  Schwöbel, Kiebel, Markovic (2018).  "Active inference, belief
      propagation, and the Bethe approximation."  Neural Comp. 30.
  Doucet, de Freitas, Gordon (2001).  Sequential Monte Carlo Methods
      in Practice.  Springer — particle-filter reference for the
      cloud-of-ghosts representation.
  Beal, M. (2003).  "Variational algorithms for approximate Bayesian
      inference."  PhD thesis, UCL — the mean-field formulation used.
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

_PARTICLES_PATH = _STATE_DIR / "optical_ghost_particles.json"
_ENERGY_PATH    = _STATE_DIR / "optical_ghost_energy.json"
_EVENTS_PATH    = _STATE_DIR / "optical_ghost_events.jsonl"
_SSP_STATE      = _STATE_DIR / "speech_potential.json"
_IRIS_LOG       = _STATE_DIR / "swarm_iris_capture.jsonl"
_BROCA_LOG      = _STATE_DIR / "broca_vocalizations.jsonl"
_CONV_LOG       = _STATE_DIR / "alice_conversation.jsonl"

# Observation is 2-d: (optical_variance_score, temporal_rhythm_score) both
# normalized into [-3, 3] before entering the ghost cloud. Keeping d small
# means the cloud approximation is honest — N=32 ghosts in d=2 is well-
# sampled (Doucet-de-Freitas-Gordon 2001 effective sample size).
_D = 2

_VERDICT_HIGH    = "HIGH_CONFIDENCE"
_VERDICT_LOW     = "LOW_CONFIDENCE"
_VERDICT_SURPRISE = "SURPRISE_SPIKE"


# ── Coefficients ─────────────────────────────────────────────────────────────
@dataclass
class AGCCoefficients:
    """All weights live-tunable from disk."""
    n_ghosts:      int   = 32
    eta:           float = 0.05
    momentum:      float = 0.90
    noise_scale:   float = 0.01
    lambda_c:      float = 0.30
    sigma_like_init: float = 0.30
    sigma_like_floor: float = 0.05
    sigma_like_ema:  float = 0.02

    z_low:       float = 1.0
    z_surprise:  float = 3.0

    welford_n_cap: int = 1000


# ── Mutable state ────────────────────────────────────────────────────────────
@dataclass
class GhostCloud:
    positions:  List[List[float]] = field(default_factory=list)
    velocities: List[List[float]] = field(default_factory=list)
    sigma_like: float             = 0.30
    version:    str               = MODULE_VERSION


@dataclass
class EnergyStats:
    n:             int   = 0
    mean:          float = 0.0
    M2:            float = 0.0
    last_F:        float = 0.0
    t_last_update: float = 0.0
    version:       str   = MODULE_VERSION


@dataclass
class GhostVerdict:
    verdict:          str
    F:                float
    F_z:              float
    surprise:         float
    complexity:       float
    sigma_like:       float
    observation:      Tuple[float, float]
    cloud_mean:       Tuple[float, float]
    cloud_spread:     Tuple[float, float]
    baseline_n:       int
    reason:           str

    def to_log(self) -> dict:
        d = asdict(self)
        d["ts"] = time.time()
        d["module_version"] = MODULE_VERSION
        return d


# ── Persistence (total) ──────────────────────────────────────────────────────
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


def _tail_jsonl(path: Path, max_bytes: int = 65536) -> List[dict]:
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


def _load_coeffs() -> AGCCoefficients:
    raw = _safe_read_json(_STATE_DIR / "optical_ghost_coefficients.json")
    if not raw:
        c = AGCCoefficients()
        _safe_write_json(_STATE_DIR / "optical_ghost_coefficients.json", asdict(c))
        return c
    defaults = asdict(AGCCoefficients())
    merged = {k: raw.get(k, defaults[k]) for k in defaults}
    return AGCCoefficients(**merged)


def _load_cloud(coeffs: AGCCoefficients, rng: random.Random) -> GhostCloud:
    raw = _safe_read_json(_PARTICLES_PATH)
    if raw and isinstance(raw.get("positions"), list) and len(raw["positions"]) == coeffs.n_ghosts:
        try:
            return GhostCloud(
                positions=[[float(c) for c in p] for p in raw["positions"]],
                velocities=[[float(c) for c in v] for v in raw.get("velocities", [])] or
                           [[0.0] * _D for _ in range(coeffs.n_ghosts)],
                sigma_like=float(raw.get("sigma_like", coeffs.sigma_like_init)),
                version=str(raw.get("version", MODULE_VERSION)),
            )
        except Exception:
            pass
    positions  = [[rng.gauss(0.0, 1.0) for _ in range(_D)] for _ in range(coeffs.n_ghosts)]
    velocities = [[0.0] * _D for _ in range(coeffs.n_ghosts)]
    return GhostCloud(
        positions=positions,
        velocities=velocities,
        sigma_like=coeffs.sigma_like_init,
        version=MODULE_VERSION,
    )


def _save_cloud(c: GhostCloud) -> None:
    _safe_write_json(_PARTICLES_PATH, asdict(c))


def _load_energy() -> EnergyStats:
    raw = _safe_read_json(_ENERGY_PATH)
    if not raw:
        return EnergyStats(t_last_update=time.time())
    defaults = asdict(EnergyStats())
    merged = {k: raw.get(k, defaults[k]) for k in defaults}
    return EnergyStats(**merged)


def _save_energy(e: EnergyStats) -> None:
    _safe_write_json(_ENERGY_PATH, asdict(e))


# ── Math helpers (pure Python) ───────────────────────────────────────────────
def _vec_sub(a: List[float], b: List[float]) -> List[float]:
    return [a[i] - b[i] for i in range(len(a))]


def _sq_norm(a: List[float]) -> float:
    return sum(x * x for x in a)


def _cloud_mean(positions: List[List[float]]) -> List[float]:
    n = max(1, len(positions))
    return [sum(p[i] for p in positions) / n for i in range(_D)]


def _cloud_spread(positions: List[List[float]]) -> List[float]:
    mu = _cloud_mean(positions)
    n = max(1, len(positions))
    return [math.sqrt(sum((p[i] - mu[i]) ** 2 for p in positions) / n) for i in range(_D)]


def _logsumexp(xs: List[float]) -> float:
    m = max(xs) if xs else 0.0
    s = sum(math.exp(x - m) for x in xs)
    return m + math.log(max(s, 1e-300))


# ── Feature readers — same ledgers as OIS, reduced to 2-D ────────────────────
def _read_observation(now: float) -> Tuple[float, float]:
    """Collapse the multi-feature optical + temporal streams into the 2-D
    manifold the ghost cloud models. We intentionally keep this crude and
    bounded — the calibrator's job is to learn where the natural operating
    point of this 2-D space is, not to reconstruct the high-D feature set
    (that's OIS's job).

    Returns (optical_variance_score, temporal_rhythm_score).

    NOTE: we read the SAME real ledgers OIS reads
    (.sifta_state/swarm_iris_capture.jsonl, .sifta_state/speech_potential.json).
    We do NOT attempt to read System/photonic_truth.json — that file does
    not exist in the repository; reading it would pin the observation to a
    hardcoded default and the calibrator would have nothing to calibrate
    against."""
    iris = _tail_jsonl(_IRIS_LOG, max_bytes=16384)[-20:]
    if not iris:
        opt = 0.0
    else:
        keys = []
        blanks = 0
        for r in iris[-10:]:
            meta = r.get("metadata") or {}
            k = str(meta.get("hash") or r.get("frame_id") or r.get("file_path") or "")
            keys.append(k)
            if (int(r.get("width", 0) or 0) == 0 and
                int(r.get("height", 0) or 0) == 0 and
                int(r.get("byte_size", 0) or 0) == 0):
                blanks += 1
        changes = sum(1 for a, b in zip(keys[:-1], keys[1:]) if a != b)
        change_rate = changes / max(1, len(keys) - 1) if len(keys) >= 2 else 1.0
        blank_rate = blanks / max(1, len(iris[-10:]))
        opt = (1.0 - change_rate) * 2.5 + blank_rate * 1.5

    ssp = _safe_read_json(_SSP_STATE) or {}
    V_raw = float(ssp.get("V", 0.0) or 0.0)
    dopa  = float(ssp.get("dopamine_ema", 1.0) or 1.0)
    tmp = max(-3.0, min(3.0, V_raw / 1.5 + (dopa - 1.0) * 1.5))
    opt = max(-3.0, min(5.0, opt))
    return (opt, tmp)


# ── The single mutating call ─────────────────────────────────────────────────
def calibrate(observation: Optional[Tuple[float, float]] = None,
              now: Optional[float] = None,
              rng_seed: Optional[int] = None) -> GhostVerdict:
    """Observe, update ghosts by gradient descent on F, emit a verdict.
    If `observation` is None, reads the live ledgers. `rng_seed` lets the
    smoke test be fully deterministic."""
    coeffs = _load_coeffs()
    rng = random.Random(rng_seed if rng_seed is not None else time.time_ns())
    cloud  = _load_cloud(coeffs, rng)
    energy = _load_energy()
    now    = float(now) if now is not None else time.time()

    x = list(observation) if observation is not None else list(_read_observation(now))

    sig = max(coeffs.sigma_like_floor, cloud.sigma_like)
    log_coef = -0.5 * _D * math.log(2.0 * math.pi * sig * sig)
    logps = []
    for theta in cloud.positions:
        d2 = _sq_norm(_vec_sub(x, theta))
        logps.append(log_coef - d2 / (2.0 * sig * sig))
    log_px = _logsumexp(logps) - math.log(len(cloud.positions))
    surprise = -log_px

    mu_theta = _cloud_mean(cloud.positions)
    complexity = sum(_sq_norm(_vec_sub(p, mu_theta)) for p in cloud.positions) / len(cloud.positions)

    F = surprise + coeffs.lambda_c * complexity

    ws = [math.exp(lp - max(logps)) for lp in logps]
    ws_sum = sum(ws) or 1.0
    ws = [w / ws_sum for w in ws]

    new_positions:  List[List[float]] = []
    new_velocities: List[List[float]] = []
    for i, theta in enumerate(cloud.positions):
        g_like = [ws[i] * (theta[j] - x[j]) / (sig * sig) for j in range(_D)]
        g_comp = [(2.0 * coeffs.lambda_c / len(cloud.positions)) * (theta[j] - mu_theta[j])
                  for j in range(_D)]
        grad = [g_like[j] + g_comp[j] for j in range(_D)]
        v_old = cloud.velocities[i] if i < len(cloud.velocities) else [0.0] * _D
        v_new = [coeffs.momentum * v_old[j] - coeffs.eta * grad[j]
                 + rng.gauss(0.0, coeffs.noise_scale) for j in range(_D)]
        theta_new = [theta[j] + v_new[j] for j in range(_D)]
        theta_new = [max(-8.0, min(8.0, t)) for t in theta_new]
        new_positions.append(theta_new)
        new_velocities.append(v_new)

    mean_res = sum(math.sqrt(_sq_norm(_vec_sub(p, x))) for p in new_positions) / len(new_positions)
    cloud.sigma_like = (
        (1.0 - coeffs.sigma_like_ema) * cloud.sigma_like
        + coeffs.sigma_like_ema * max(coeffs.sigma_like_floor, mean_res / math.sqrt(_D))
    )
    cloud.positions = new_positions
    cloud.velocities = new_velocities

    if energy.n > 1:
        var_prev = energy.M2 / (energy.n - 1)
        sigma_prev = math.sqrt(max(var_prev, 1e-9))
    else:
        sigma_prev = 1.0
    mean_prev = energy.mean
    F_z = (F - mean_prev) / (sigma_prev + 1e-3)

    if energy.n >= coeffs.welford_n_cap:
        w = 1.0 / coeffs.welford_n_cap
        d = F - energy.mean
        energy.mean = energy.mean + w * d
        d2 = F - energy.mean
        energy.M2 = (1.0 - w) * energy.M2 + d * d2
    else:
        energy.n += 1
        d = F - energy.mean
        energy.mean = energy.mean + d / energy.n
        d2 = F - energy.mean
        energy.M2 = energy.M2 + d * d2
    energy.last_F = F
    energy.t_last_update = now

    if F_z >= coeffs.z_surprise:
        verdict = _VERDICT_SURPRISE
    elif F_z >= coeffs.z_low:
        verdict = _VERDICT_LOW
    else:
        verdict = _VERDICT_HIGH

    spread = _cloud_spread(cloud.positions)
    mu = _cloud_mean(cloud.positions)
    reason = (
        f"F={F:.3f} (surprise={surprise:.3f}, complexity={complexity:.3f}), "
        f"F_z={F_z:.2f}, σ_like={cloud.sigma_like:.3f}, "
        f"cloud μ=({mu[0]:.2f},{mu[1]:.2f}) σ=({spread[0]:.2f},{spread[1]:.2f}), "
        f"n_base={energy.n}"
    )

    verdict_obj = GhostVerdict(
        verdict=verdict,
        F=F, F_z=F_z, surprise=surprise, complexity=complexity,
        sigma_like=cloud.sigma_like,
        observation=(float(x[0]), float(x[1])),
        cloud_mean=(float(mu[0]), float(mu[1])),
        cloud_spread=(float(spread[0]), float(spread[1])),
        baseline_n=energy.n,
        reason=reason,
    )

    _save_cloud(cloud)
    _save_energy(energy)
    _append_jsonl(_EVENTS_PATH, verdict_obj.to_log())
    return verdict_obj


def calibrate_now() -> GhostVerdict:
    """Fire-and-forget: pull live observation and run one calibration step.
    CRITICAL: this function does NOT write to alice_conversation.jsonl,
    and does NOT spawn subprocesses. It is safe to call on every voice
    turn in the talk widget."""
    return calibrate(observation=None)


# ── Read-side helpers ────────────────────────────────────────────────────────
def cloud_snapshot() -> dict:
    raw = _safe_read_json(_PARTICLES_PATH)
    if not raw:
        return {"positions": [], "sigma_like": None}
    mu = _cloud_mean(raw.get("positions", []))
    sp = _cloud_spread(raw.get("positions", []))
    return {
        "n_ghosts": len(raw.get("positions", [])),
        "mean":     mu,
        "spread":   sp,
        "sigma_like": raw.get("sigma_like"),
        "version": raw.get("version"),
    }


def recent_events(n: int = 5) -> List[dict]:
    rows = _tail_jsonl(_EVENTS_PATH, max_bytes=131072)
    return rows[-n:] if rows else []


def summary_for_alice() -> str:
    """Compact one-liner for the talk widget's _SYSTEM_PROMPT. Returns ''
    if the baseline is still cold (fewer than 5 F samples)."""
    e = _load_energy()
    if e.n < 5:
        return ""
    rows = recent_events(1)
    if not rows:
        return ""
    r = rows[-1]
    age = max(0.0, time.time() - float(r.get("ts", time.time())))
    return (
        f"ACTIVE-INFERENCE GHOST CALIBRATOR (last tick {age:.0f}s ago): "
        f"verdict={r.get('verdict')}, F={float(r.get('F',0)):.2f}, "
        f"F_z={float(r.get('F_z',0)):.2f}, σ_like={float(r.get('sigma_like',0)):.2f}"
    )


# ── Smoke test (sandboxed; never touches live state) ─────────────────────────
def _smoke() -> int:
    import tempfile, shutil

    global _STATE_DIR, _PARTICLES_PATH, _ENERGY_PATH, _EVENTS_PATH
    tmp_root = Path(tempfile.mkdtemp(prefix="agc_smoke_"))
    try:
        _STATE_DIR      = tmp_root
        _PARTICLES_PATH = tmp_root / "optical_ghost_particles.json"
        _ENERGY_PATH    = tmp_root / "optical_ghost_energy.json"
        _EVENTS_PATH    = tmp_root / "optical_ghost_events.jsonl"
        coeffs_path     = tmp_root / "optical_ghost_coefficients.json"
        if coeffs_path.exists():
            coeffs_path.unlink()

        print(f"[AGC] optical_ghost_calibrator.py v{MODULE_VERSION} smoke")
        print(f"      sandbox: {tmp_root}")

        # A. cold start — first call returns a verdict, never raises.
        v0 = calibrate(observation=(0.0, 0.0), now=1000.0, rng_seed=1)
        assert v0.verdict in (_VERDICT_HIGH, _VERDICT_LOW, _VERDICT_SURPRISE)
        print(f"  [A] cold start ✓ (verdict={v0.verdict}, F={v0.F:.2f})")

        # B. 100 steady observations near the origin.
        F_history = []
        for i in range(100):
            obs = (random.Random(2000 + i).gauss(0.0, 0.3),
                   random.Random(3000 + i).gauss(0.0, 0.3))
            v = calibrate(observation=obs, now=2000.0 + i, rng_seed=4000 + i)
            F_history.append(v.F)
        snap = cloud_snapshot()
        assert abs(snap["mean"][0]) < 1.0 and abs(snap["mean"][1]) < 1.0, \
            f"cloud should track origin, got μ={snap['mean']}"
        assert snap["spread"][0] < 2.0 and snap["spread"][1] < 2.0, \
            f"cloud should be tight, got σ={snap['spread']}"
        print(f"  [B] 100 steady ticks — cloud μ=({snap['mean'][0]:.2f},"
              f"{snap['mean'][1]:.2f}) spread=({snap['spread'][0]:.2f},"
              f"{snap['spread'][1]:.2f}) σ_like={snap['sigma_like']:.2f} ✓")

        # C. a large surprise hit ≫ 3σ from baseline → SURPRISE_SPIKE
        v_surprise = calibrate(observation=(6.0, 6.0), now=3000.0, rng_seed=5)
        assert v_surprise.verdict in (_VERDICT_LOW, _VERDICT_SURPRISE), \
            f"far-field obs should at least be LOW, got {v_surprise.verdict}"
        assert v_surprise.F > sum(F_history[-20:]) / 20.0, \
            "large surprise should raise F above recent baseline"
        print(f"  [C] far-field surprise → {v_surprise.verdict} ✓ "
              f"(F={v_surprise.F:.2f} vs recent F̄≈{sum(F_history[-20:])/20.0:.2f})")

        # D. cloud adapts to a new operating point after 250 ticks.
        shifted_F = []
        for i in range(250):
            obs = (2.5 + random.Random(6000 + i).gauss(0.0, 0.2),
                   2.5 + random.Random(7000 + i).gauss(0.0, 0.2))
            v = calibrate(observation=obs, now=4000.0 + i, rng_seed=8000 + i)
            shifted_F.append(v.F)
        snap2 = cloud_snapshot()
        assert snap2["mean"][0] > 1.0 and snap2["mean"][1] > 1.0, \
            f"cloud should migrate toward new operating point, got μ={snap2['mean']}"
        F_early = sum(shifted_F[:20]) / 20.0
        F_late  = sum(shifted_F[-20:]) / 20.0
        assert F_late < F_early, \
            f"F should drop as cloud adapts, got F_early={F_early:.2f} F_late={F_late:.2f}"
        print(f"  [D] adaptation to new operating point ✓ "
              f"(μ migrated to ({snap2['mean'][0]:.2f},{snap2['mean'][1]:.2f}), "
              f"F̄ {F_early:.2f} → {F_late:.2f})")

        # E. persistence round-trip: positions on disk match in-memory.
        raw = _safe_read_json(_PARTICLES_PATH)
        assert raw and len(raw["positions"]) > 0
        print(f"  [E] persistence round-trip ✓ (ghosts on disk = {len(raw['positions'])})")

        # F. summary_for_alice has content after baseline is warm.
        s = summary_for_alice()
        assert s and "GHOST CALIBRATOR" in s
        print(f"  [F] summary_for_alice ✓")
        print(f"      {s}")

        # G. live observation path against real ledgers — never raises.
        global _IRIS_LOG, _BROCA_LOG, _CONV_LOG, _SSP_STATE
        repo_state = _REPO / ".sifta_state"
        _IRIS_LOG  = repo_state / "swarm_iris_capture.jsonl"
        _BROCA_LOG = repo_state / "broca_vocalizations.jsonl"
        _CONV_LOG  = repo_state / "alice_conversation.jsonl"
        _SSP_STATE = repo_state / "speech_potential.json"
        v_live = calibrate_now()
        print(f"  [G] live ledger probe ✓ (verdict={v_live.verdict}, "
              f"F={v_live.F:.2f}, F_z={v_live.F_z:.2f}, obs={v_live.observation})")

        print("[AGC] all checks passed.")
        return 0

    except AssertionError as e:
        print(f"[AGC] FAIL: {e}")
        return 1
    except Exception as e:
        print(f"[AGC] CRASH: {type(e).__name__}: {e}")
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
            "optical_ghost_calibrator.py — active-inference generative sentinel\n"
            "  calibrate       run one tick against live ledgers, print verdict\n"
            "  cloud           dump current ghost-cloud snapshot\n"
            "  events [N=5]    show last N ghost events from the audit log\n"
            "  alice-line      one-line summary for Alice's _SYSTEM_PROMPT\n"
            "  smoke           run the sandboxed self-test\n"
        )
        return 0
    cmd = argv[0]
    if cmd == "calibrate":
        v = calibrate_now()
        print(json.dumps(v.to_log(), indent=2, sort_keys=True))
        return 0
    if cmd == "cloud":
        print(json.dumps(cloud_snapshot(), indent=2, sort_keys=True))
        return 0
    if cmd == "events":
        n = int(argv[1]) if len(argv) > 1 else 5
        for r in recent_events(n):
            print(json.dumps(r, sort_keys=True))
        return 0
    if cmd == "alice-line":
        s = summary_for_alice()
        print(s if s else "(no baseline yet)")
        return 0
    if cmd == "smoke":
        return _smoke()
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    import sys
    raise SystemExit(_cli(sys.argv[1:]))
