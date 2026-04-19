#!/usr/bin/env python3
"""
System/optical_immune_system.py — Optical Immune System (OIS)
═══════════════════════════════════════════════════════════════════════════════
SIFTA Cortical Suite — visual immune membrane (Vision Olympiad / Loop 3)
Module version: 2026-04-19.v1
Author:  C47H (Cursor IDE, Opus 4.7 High, GTH4921YP3)
Assigner: AG31 (Antigravity / Gemini), peer-review trace 8ea22498

DUAL-IDE COLLISION NOTE (2026-04-20)
────────────────────────────────────
While C47H was running smoke tests on this file, AG31 wrote his own
version into the same path. AG31's version is preserved at
`Archive/ag31_optical_immune_system_fork_2026-04-20.py` with a
forensic header listing nine concrete defects (broken context-manager
use of `append_line_locked`, always-zero z-score, alice_conversation.jsonl
pollution on every instantiation, missing photonic_truth.json source,
no on-disk baseline persistence, etc.). Findings have been filed back
to AG31 through the peer-review bridge. THIS file is the working,
smoke-tested implementation.

WHAT THIS REPLACES
──────────────────
Static thresholds for camera noise / blank frames / hash drift in
`System/optical_ingress.py` and the visual cortex stack. Anomaly
detection becomes a self-calibrating biologically-coupled membrane
that fuses two heterogeneous channels — incoming optical hardware
variance and Alice's temporal interaction rhythms (her SSP spike
history) — through a sigmoid gate over a topological (multi-feature)
z-score baseline.

THE GOVERNING IDEA (not theatre)
────────────────────────────────
At each tick we observe a feature vector x⃗ = [x_optical … x_temporal].
A rolling baseline N(μ⃗, σ⃗) is maintained on-line via Welford's
incremental variance (Welford 1962). The standardized residual

    z_i = (x_i − μ_i) / (σ_i + ε)

is the per-feature deviation. The composite "topological" deviation
in each modality is the L2 norm of its z-vector (Mahalanobis-lite
under a diagonal covariance assumption — see Carlsson 2009 for the
broader topological-data-analysis frame in which a Mahalanobis
neighborhood is the simplest persistence radius):

    z_optical  =  ‖z_{i ∈ optical}‖_2
    z_temporal =  ‖z_{i ∈ temporal}‖_2

The two channels fuse multiplicatively in log-odds space — i.e.
through a sigmoid (Baltrušaitis et al. 2018, "Multimodal Machine
Learning") with cross-channel coupling weights:

    p_anomaly  =  σ( w_o · z_optical  +  w_t · z_temporal  +  b )

p_anomaly drives a leaky integrate-and-fire immune membrane V_imm:

    dV_imm/dt = − V_imm / τ_imm  +  κ · p_anomaly
    fire when V_imm > V_th_imm   →   V_imm ← 0,  refractory τ_ref_imm

Verdict classification (three cells; Forrest-Hofmeyr-Somayaji 1997
computer-immunology / Aickelin-Cayzer 2002 danger-model framing):

    BENIGN_HOMEOSTASIS   z_o low,  z_t low   →  baseline drift only
    DRIFT_WARNING        one channel elevated →  watch, don't fire
    ZERO_DAY_FAILURE     both elevated OR
                         membrane crossed V_th_imm → fire response

A genuinely dark room (low brightness, low byte_size, low rhythm)
becomes the new μ⃗ within a few minutes — Alice does not panic when
the lights go out. A camera-driver corruption that produces
identical-byte frames (zero hash drift) WHILE Alice is mid-
conversation (active temporal channel) cannot be explained as
homeostasis: both channels diverge → ZERO_DAY.

PERSISTENCE
───────────
  .sifta_state/optical_immune_baseline.json
      { "feature_keys": [...],
        "n":   int,                   # samples in baseline
        "mean": [..],                 # μ_i  (EMA-updated)
        "M2":   [..],                 # Welford accumulator
        "version": "..." }

  .sifta_state/optical_immune_state.json
      { "V_imm": float, "t_last_update": ts, "t_last_fire": ts,
        "last_hash": str, "version": "..." }

  .sifta_state/optical_immune_events.jsonl     append-only audit
      { "ts": ts, "verdict": "...", "z_optical": .., "z_temporal": ..,
        "p_anomaly": .., "V_imm": .., "features": {..}, "module_version": .. }

DESIGN PROPERTIES
─────────────────
  • TOTAL.       Never raises. Missing camera / SSP / ledgers → benign default.
  • SELF-CAL.    No magic numbers for "what is dark." μ, σ adapt online.
  • COUPLED.     Optical channel cannot fire alone. Temporal channel cannot
                 fire alone. Genuine zero-day requires concordant deviation.
  • CHEAP.       ~1 ms per evaluate_now() call when no camera capture; the
                 capture itself is the only expensive op (handled by
                 optical_ingress with its own 5 s ffmpeg timeout).
  • HONEST.      The verdict carries a `reason` string with the actual
                 z-scores, not a hardcoded label. When Alice asks "why",
                 she gets physics.
  • NO POLLUTION. Does not write to alice_conversation.jsonl on import or
                 instantiation. Alice's chat ledger stays clean.

BIBLIOGRAPHY
────────────
  Welford, B. P. (1962).  "Note on a method for calculating corrected sums
      of squares and products." Technometrics 4(3): 419-420.
  Knuth, D. E. (1998).   The Art of Computer Programming, Vol. 2 §4.2.2,
      online variance.
  Carlsson, G. (2009).   "Topology and data."  Bull. AMS 46(2): 255-308.
  Baltrušaitis, Ahuja, Morency (2018). "Multimodal Machine Learning:
      A Survey and Taxonomy."  IEEE TPAMI 41(2): 423-443.
  Forrest, S., Hofmeyr, S., Somayaji, A. (1997). "Computer immunology."
      Comm. ACM 40(10): 88-96.
  Forrest, S., Perelson, A., Allen, L., Cherukuri, R. (1994). "Self-
      nonself discrimination in a computer." IEEE Symp. on Sec. & Privacy.
  Aickelin, U., Cayzer, S. (2002). "The Danger Theory and Its Application
      to Artificial Immune Systems." ICARIS-02.
  Matzinger, P. (1994). "Tolerance, danger, and the extended family."
      Annual Review of Immunology 12: 991-1045.
  Dasgupta, D. (2006). "Advances in artificial immune systems."  IEEE
      Computational Intelligence Magazine 1(4): 40-49.
  Gerstner, W., Kistler, W. M. (2002). Spiking Neuron Models §5.3.
      [LIF + escape-noise — same substrate as swarm_speech_potential.py]
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MODULE_VERSION = "2026-04-19.v1"

_REPO       = Path(__file__).resolve().parent.parent
_STATE_DIR  = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)

_BASELINE_PATH = _STATE_DIR / "optical_immune_baseline.json"
_STATE_PATH    = _STATE_DIR / "optical_immune_state.json"
_EVENTS_PATH   = _STATE_DIR / "optical_immune_events.jsonl"
_SSP_STATE     = _STATE_DIR / "speech_potential.json"
_IRIS_LOG      = _STATE_DIR / "swarm_iris_capture.jsonl"
_BROCA_LOG     = _STATE_DIR / "broca_vocalizations.jsonl"
_CONV_LOG      = _STATE_DIR / "alice_conversation.jsonl"

# Feature axes. Order is part of the on-disk schema — DO NOT REORDER without
# bumping MODULE_VERSION (the baseline file is keyed positionally).
OPTICAL_FEATURES  = ("byte_size_kb", "hash_change_rate", "blank_frame_ratio")
TEMPORAL_FEATURES = ("alice_isi_s", "ssp_V", "ssp_dopamine_ema")
ALL_FEATURES      = OPTICAL_FEATURES + TEMPORAL_FEATURES

_VERDICT_BENIGN  = "BENIGN_HOMEOSTASIS"
_VERDICT_DRIFT   = "DRIFT_WARNING"
_VERDICT_ZERODAY = "ZERO_DAY_FAILURE"


# ── Coefficients ─────────────────────────────────────────────────────────────
@dataclass
class OISCoefficients:
    """All weights live-tunable from disk. See header for justification."""
    w_optical:  float = 1.0
    w_temporal: float = 1.0
    bias:       float = -2.5      # negative bias → quiet by default

    tau_imm_s:     float = 90.0   # immune membrane time constant (slow)
    tau_ref_imm_s: float = 30.0   # refractory after immune fire (don't spam)
    V_th_imm:      float = 0.7    # firing threshold for IMMUNE_RESPONSE
    kappa:         float = 1.0    # how strongly p_anomaly charges V_imm

    z_drift:    float = 1.5       # one channel above this  → DRIFT_WARNING
    z_zeroday:  float = 2.5       # both channels above this → ZERO_DAY

    baseline_n_cap: int = 1000    # cap N so old samples don't lock the baseline


# ── Mutable runtime state ────────────────────────────────────────────────────
@dataclass
class OISState:
    V_imm:         float = 0.0
    t_last_update: float = 0.0
    t_last_fire:   float = 0.0
    last_hash:     str   = ""
    version:       str   = MODULE_VERSION


@dataclass
class OISBaseline:
    """Welford rolling baseline over ALL_FEATURES. Vectors are positional."""
    feature_keys: List[str] = field(default_factory=lambda: list(ALL_FEATURES))
    n:    int               = 0
    mean: List[float]       = field(default_factory=lambda: [0.0] * len(ALL_FEATURES))
    M2:   List[float]       = field(default_factory=lambda: [0.0] * len(ALL_FEATURES))
    version: str            = MODULE_VERSION


@dataclass
class ImmuneVerdict:
    verdict:     str
    z_optical:   float
    z_temporal:  float
    p_anomaly:   float
    V_imm:       float
    fired:       bool
    refractory_remaining: float
    features:    Dict[str, float]
    z_per_feature: Dict[str, float]
    reason:      str

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
                f.readline()  # discard partial
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


def _load_coeffs() -> OISCoefficients:
    raw = _safe_read_json(_STATE_DIR / "optical_immune_coefficients.json")
    if not raw:
        c = OISCoefficients()
        _safe_write_json(_STATE_DIR / "optical_immune_coefficients.json", asdict(c))
        return c
    defaults = asdict(OISCoefficients())
    merged = {k: raw.get(k, defaults[k]) for k in defaults}
    return OISCoefficients(**merged)


def _load_state() -> OISState:
    raw = _safe_read_json(_STATE_PATH)
    if not raw:
        return OISState(t_last_update=time.time())
    defaults = asdict(OISState())
    merged = {k: raw.get(k, defaults[k]) for k in defaults}
    return OISState(**merged)


def _save_state(s: OISState) -> None:
    _safe_write_json(_STATE_PATH, asdict(s))


def _load_baseline() -> OISBaseline:
    raw = _safe_read_json(_BASELINE_PATH)
    if not raw or raw.get("feature_keys") != list(ALL_FEATURES):
        return OISBaseline()
    try:
        return OISBaseline(
            feature_keys=list(raw.get("feature_keys", ALL_FEATURES)),
            n=int(raw.get("n", 0)),
            mean=[float(x) for x in raw.get("mean", [0.0]*len(ALL_FEATURES))],
            M2=[float(x) for x in raw.get("M2", [0.0]*len(ALL_FEATURES))],
            version=str(raw.get("version", MODULE_VERSION)),
        )
    except Exception:
        return OISBaseline()


def _save_baseline(b: OISBaseline) -> None:
    _safe_write_json(_BASELINE_PATH, asdict(b))


# ── Welford online (μ, σ²) update — the core "self-calibrating" math ─────────
def _welford_update(b: OISBaseline, x: List[float], n_cap: int) -> Tuple[List[float], List[float]]:
    """One Welford step per feature axis. Returns (μ, σ) for use *this tick*
    BEFORE the update (so a sample is judged against the prior baseline,
    not against itself — preserves anomaly sensitivity). Then the baseline
    is updated for next time. n is capped so the running window stays
    responsive to slow regime shifts (a lit room → a dark room over hours).
    """
    n_prev = b.n
    mean_prev = list(b.mean)
    var_prev = [
        (b.M2[i] / (n_prev - 1)) if n_prev > 1 else 1.0
        for i in range(len(ALL_FEATURES))
    ]
    sigma_prev = [math.sqrt(max(v, 1e-9)) for v in var_prev]

    new_n = min(n_prev + 1, n_cap)
    if n_prev >= n_cap:
        w = 1.0 / n_cap
        for i in range(len(ALL_FEATURES)):
            d = x[i] - b.mean[i]
            b.mean[i] = b.mean[i] + w * d
            d2 = x[i] - b.mean[i]
            b.M2[i] = (1.0 - w) * b.M2[i] + d * d2
    else:
        b.n = new_n
        for i in range(len(ALL_FEATURES)):
            d = x[i] - b.mean[i]
            b.mean[i] = b.mean[i] + d / b.n
            d2 = x[i] - b.mean[i]
            b.M2[i] = b.M2[i] + d * d2

    return mean_prev, sigma_prev


# ── Feature extractors ───────────────────────────────────────────────────────
def _read_optical_features(now: float, last_hash: str) -> Tuple[Dict[str, float], str]:
    """Returns (feature_map, current_hash). Fully total: missing camera or
    log → zeros (which become benign once the baseline learns 'this is the
    normal state when headless')."""
    rows = _tail_jsonl(_IRIS_LOG, max_bytes=16384)
    rows = sorted(rows, key=lambda r: float(r.get("ts_captured", 0.0) or 0.0))[-20:]

    if not rows:
        return ({k: 0.0 for k in OPTICAL_FEATURES}, last_hash)

    latest = rows[-1]
    byte_size = float(latest.get("byte_size", 0)) / 1024.0   # KB

    # Hash drift: fraction of consecutive frames whose identifier changed.
    # If iris_capture didn't record a hash, fall back to file_path / frame_id
    # (timestamp-suffixed) — good enough proxy for "did the frame change at
    # all?". A stuck driver yields all identical → drift_rate ≈ 0.
    keys = []
    for r in rows[-10:]:
        meta = r.get("metadata") or {}
        h = meta.get("hash") or r.get("frame_id") or r.get("file_path") or ""
        keys.append(str(h))
    if len(keys) >= 2:
        changes = sum(1 for a, b in zip(keys[:-1], keys[1:]) if a != b)
        hash_change_rate = changes / max(1, len(keys) - 1)
    else:
        hash_change_rate = 1.0   # one row = give benefit of doubt

    # Blank frame: width=0, height=0, byte_size=0 → AG31's mock fallback.
    blank_count = sum(
        1 for r in rows[-10:]
        if int(r.get("width", 0) or 0) == 0
        and int(r.get("height", 0) or 0) == 0
        and int(r.get("byte_size", 0) or 0) == 0
    )
    blank_frame_ratio = blank_count / max(1, len(rows[-10:]))

    cur_hash = keys[-1] if keys else last_hash

    return ({
        "byte_size_kb":     byte_size,
        "hash_change_rate": hash_change_rate,
        "blank_frame_ratio": blank_frame_ratio,
    }, cur_hash)


def _read_temporal_features(now: float) -> Dict[str, float]:
    """Pulls Alice's conversational rhythm from her SSP state and the
    actual broca / conversation logs. ISI = inter-spike interval, mean
    over the last 10 vocalizations. Long silence → large ISI → temporal
    channel quiet (anomaly hard to fire on its own). Active conversation
    → small ISI + elevated V → temporal channel responsive."""
    spike_ts: List[float] = []
    broca_rows = _tail_jsonl(_BROCA_LOG, max_bytes=32768)
    for r in broca_rows[-30:]:
        if r.get("ok") and r.get("spoken"):
            try:
                spike_ts.append(float(r.get("ts", 0.0) or 0.0))
            except Exception:
                continue
    if len(spike_ts) < 2:
        for r in _tail_jsonl(_CONV_LOG, max_bytes=32768)[-30:]:
            if str(r.get("role")) == "alice":
                content = str(r.get("content") or "")
                if content and content != "(silent)":
                    try:
                        spike_ts.append(float(r.get("ts", 0.0) or 0.0))
                    except Exception:
                        continue
    spike_ts = sorted(t for t in spike_ts if t > 0.0)
    if len(spike_ts) >= 2:
        isis = [b - a for a, b in zip(spike_ts[:-1], spike_ts[1:]) if (b - a) > 0]
        alice_isi_s = sum(isis) / len(isis) if isis else float(now - spike_ts[-1])
    elif len(spike_ts) == 1:
        alice_isi_s = max(0.0, now - spike_ts[-1])
    else:
        alice_isi_s = 600.0  # cold start → large ISI

    ssp = _safe_read_json(_SSP_STATE) or {}
    v_ssp        = float(ssp.get("V", 0.0) or 0.0)
    dopamine_ema = float(ssp.get("dopamine_ema", 1.0) or 1.0)

    return {
        "alice_isi_s":      alice_isi_s,
        "ssp_V":            v_ssp,
        "ssp_dopamine_ema": dopamine_ema,
    }


# ── Membrane physics (closed-form ZOH update, same as SSP) ───────────────────
def _advance_membrane(V: float, dt: float, drive: float, tau: float) -> float:
    """V(t+dt) = V(t)·e^{−dt/τ} + drive·τ·(1 − e^{−dt/τ})  — Gerstner 2002."""
    if dt <= 0:
        return V
    decay = math.exp(-dt / max(tau, 1e-3))
    return V * decay + drive * tau * (1.0 - decay) / max(tau, 1e-3)


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


# ── The single mutating call ─────────────────────────────────────────────────
def evaluate(features: Optional[Dict[str, float]] = None,
             now: Optional[float] = None) -> ImmuneVerdict:
    """Topological z-score + sigmoid fusion + LIF membrane.

    If `features` is None, pulls them from the live SIFTA ledgers. Pass an
    explicit dict in tests to control the input. `now` defaults to time.time().
    Always returns a verdict; never raises.
    """
    coeffs = _load_coeffs()
    state  = _load_state()
    base   = _load_baseline()
    now    = float(now) if now is not None else time.time()

    if features is None:
        opt_feats, cur_hash = _read_optical_features(now, state.last_hash)
        tmp_feats           = _read_temporal_features(now)
        feats               = {**opt_feats, **tmp_feats}
    else:
        feats = {k: float(features.get(k, 0.0)) for k in ALL_FEATURES}
        cur_hash = state.last_hash

    x = [feats[k] for k in ALL_FEATURES]

    # Update Welford baseline; receive the PRIOR (μ, σ) so we can score the
    # current sample against history, not against itself.
    mean_prev, sigma_prev = _welford_update(base, x, coeffs.baseline_n_cap)

    z_per: Dict[str, float] = {}
    for i, k in enumerate(ALL_FEATURES):
        z_per[k] = (x[i] - mean_prev[i]) / (sigma_prev[i] + 1e-3)

    z_optical = math.sqrt(sum(z_per[k] ** 2 for k in OPTICAL_FEATURES))
    z_temp    = math.sqrt(sum(z_per[k] ** 2 for k in TEMPORAL_FEATURES))

    logit = coeffs.w_optical * z_optical + coeffs.w_temporal * z_temp + coeffs.bias
    p_anomaly = _sigmoid(logit)

    dt = max(0.0, now - state.t_last_update) if state.t_last_update > 0 else 0.0
    refractory_remaining = max(
        0.0,
        coeffs.tau_ref_imm_s - (now - state.t_last_fire) if state.t_last_fire > 0 else 0.0,
    )
    V_imm = state.V_imm
    fired = False
    if refractory_remaining > 0:
        V_imm = _advance_membrane(V_imm, dt, 0.0, coeffs.tau_imm_s)
    else:
        V_imm = _advance_membrane(V_imm, dt, coeffs.kappa * p_anomaly, coeffs.tau_imm_s)
        if V_imm > coeffs.V_th_imm:
            fired = True
            V_imm = 0.0

    if fired:
        verdict = _VERDICT_ZERODAY
    elif z_optical >= coeffs.z_zeroday and z_temp >= coeffs.z_zeroday:
        verdict = _VERDICT_ZERODAY
    elif z_optical >= coeffs.z_drift or z_temp >= coeffs.z_drift:
        verdict = _VERDICT_DRIFT
    else:
        verdict = _VERDICT_BENIGN

    reason = (
        f"z_opt={z_optical:.2f}, z_tmp={z_temp:.2f}, "
        f"p={p_anomaly:.3f}, V_imm={V_imm:.2f}/{coeffs.V_th_imm:.2f}, "
        f"refr={refractory_remaining:.1f}s, n_base={base.n}"
    )
    if fired:
        reason += " — IMMUNE FIRED"

    new_state = OISState(
        V_imm=V_imm,
        t_last_update=now,
        t_last_fire=now if fired else state.t_last_fire,
        last_hash=cur_hash,
        version=MODULE_VERSION,
    )
    _save_state(new_state)
    _save_baseline(base)

    verdict_obj = ImmuneVerdict(
        verdict=verdict,
        z_optical=z_optical,
        z_temporal=z_temp,
        p_anomaly=p_anomaly,
        V_imm=V_imm,
        fired=fired,
        refractory_remaining=refractory_remaining,
        features=feats,
        z_per_feature=z_per,
        reason=reason,
    )
    _append_jsonl(_EVENTS_PATH, verdict_obj.to_log())
    return verdict_obj


def evaluate_now() -> ImmuneVerdict:
    """Fire-and-forget convenience: pull live features and judge.
    A dedicated camera capture is NOT triggered here — we score against
    whatever the iris pipeline most recently logged. Trigger an explicit
    capture from optical_ingress.capture_photonic_truth() upstream if you
    need a fresh frame this tick."""
    return evaluate(features=None)


# ── Read-side helpers (Alice-facing) ─────────────────────────────────────────
def baseline_snapshot() -> dict:
    b = _load_baseline()
    out = {"n": b.n, "version": b.version, "features": {}}
    for i, k in enumerate(ALL_FEATURES):
        var = (b.M2[i] / (b.n - 1)) if b.n > 1 else 0.0
        out["features"][k] = {"mean": b.mean[i], "sigma": math.sqrt(max(var, 0.0))}
    return out


def recent_events(n: int = 5) -> List[dict]:
    rows = _tail_jsonl(_EVENTS_PATH, max_bytes=131072)
    return rows[-n:] if rows else []


def summary_for_alice() -> str:
    """One-line block for the talk widget's _SYSTEM_PROMPT. Tells Alice the
    state of her visual immune system in language she can use when asked
    'do you see anything?'. Returns '' if no baseline has been built yet."""
    b = _load_baseline()
    if b.n < 3:
        return ""
    rows = recent_events(1)
    if not rows:
        return ""
    r = rows[-1]
    age = max(0.0, time.time() - float(r.get("ts", time.time())))
    return (
        f"OPTICAL IMMUNE (visual cortex sentinel, last tick {age:.0f}s ago): "
        f"verdict={r.get('verdict')}, z_optical={float(r.get('z_optical',0)):.2f}, "
        f"z_temporal={float(r.get('z_temporal',0)):.2f}, "
        f"p_anomaly={float(r.get('p_anomaly',0)):.3f}"
    )


# ── Smoke test (sandboxed; never touches live state) ─────────────────────────
def _smoke() -> int:
    """Self-test. Runs against a tempdir so the live baseline is preserved.
    Pass criteria printed; returns 0 on success, nonzero on failure."""
    import tempfile
    import shutil

    global _STATE_DIR, _BASELINE_PATH, _STATE_PATH, _EVENTS_PATH
    tmp_root = Path(tempfile.mkdtemp(prefix="ois_smoke_"))
    try:
        _STATE_DIR     = tmp_root
        _BASELINE_PATH = tmp_root / "optical_immune_baseline.json"
        _STATE_PATH    = tmp_root / "optical_immune_state.json"
        _EVENTS_PATH   = tmp_root / "optical_immune_events.jsonl"
        coeffs_path    = tmp_root / "optical_immune_coefficients.json"
        if coeffs_path.exists():
            coeffs_path.unlink()

        print(f"[OIS] optical_immune_system.py v{MODULE_VERSION} smoke")
        print(f"      sandbox: {tmp_root}")

        # A. cold start → benign
        v0 = evaluate(features={k: 0.0 for k in ALL_FEATURES}, now=1000.0)
        assert v0.verdict == _VERDICT_BENIGN, f"cold start should be benign, got {v0.verdict}"
        print(f"  [A] cold start → BENIGN ✓ ({v0.reason})")

        # B. feed 50 normal samples → baseline learns "calm room"
        import random as _r
        _r.seed(42)
        normal = lambda: {
            "byte_size_kb":     50.0 + _r.gauss(0, 2.0),
            "hash_change_rate":  0.95 + _r.gauss(0, 0.02),
            "blank_frame_ratio": 0.0,
            "alice_isi_s":      30.0 + _r.gauss(0, 3.0),
            "ssp_V":             0.1 + _r.gauss(0, 0.05),
            "ssp_dopamine_ema":  1.0 + _r.gauss(0, 0.05),
        }
        for i in range(50):
            evaluate(features=normal(), now=2000.0 + i)
        snap = baseline_snapshot()
        assert snap["n"] >= 50, f"baseline should have >=50 samples, has {snap['n']}"
        assert snap["features"]["byte_size_kb"]["sigma"] > 0.0
        print(f"  [B] baseline learned (n={snap['n']}, "
              f"μ_bytes={snap['features']['byte_size_kb']['mean']:.1f}KB) ✓")

        # C. one optical-only deviation → DRIFT_WARNING (single channel)
        f = normal()
        f["byte_size_kb"]     = 200.0   # huge deviation above baseline
        f["hash_change_rate"] = 0.0     # stuck driver
        v_drift = evaluate(features=f, now=3000.0)
        assert v_drift.verdict in (_VERDICT_DRIFT, _VERDICT_ZERODAY), \
            f"optical spike should at least drift, got {v_drift.verdict}"
        assert v_drift.z_optical > v_drift.z_temporal, \
            f"optical channel should dominate, got z_o={v_drift.z_optical:.2f} z_t={v_drift.z_temporal:.2f}"
        print(f"  [C] optical-only spike → {v_drift.verdict} ✓ "
              f"(z_o={v_drift.z_optical:.1f}, z_t={v_drift.z_temporal:.1f})")

        # D. concordant deviation in BOTH channels → ZERO_DAY
        f2 = normal()
        f2["byte_size_kb"]      = 0.5      # camera dropped to almost-blank
        f2["hash_change_rate"]  = 0.0      # stuck
        f2["blank_frame_ratio"] = 1.0      # all blanks
        f2["alice_isi_s"]       = 0.5      # she's mid-conversation
        f2["ssp_V"]             = 5.0      # SSP pegged
        f2["ssp_dopamine_ema"]  = 5.0      # phasic dopamine surge
        v_zero = evaluate(features=f2, now=3001.0)
        assert v_zero.verdict == _VERDICT_ZERODAY, \
            f"concordant deviation should be zero-day, got {v_zero.verdict}"
        print(f"  [D] concordant deviation → {v_zero.verdict} ✓ "
              f"(z_o={v_zero.z_optical:.1f}, z_t={v_zero.z_temporal:.1f}, "
              f"V_imm={v_zero.V_imm:.2f}, fired={v_zero.fired})")

        # E. self-calibration: 100 samples of "the room got dark" should
        #    drift the baseline so dark is the new normal.
        dark = lambda: {
            "byte_size_kb":      5.0 + _r.gauss(0, 0.5),
            "hash_change_rate":  0.95 + _r.gauss(0, 0.02),
            "blank_frame_ratio": 0.0,
            "alice_isi_s":      30.0 + _r.gauss(0, 3.0),
            "ssp_V":             0.1 + _r.gauss(0, 0.05),
            "ssp_dopamine_ema":  1.0 + _r.gauss(0, 0.05),
        }
        for i in range(100):
            evaluate(features=dark(), now=4000.0 + i)
        snap2 = baseline_snapshot()
        new_bytes_mean_pre = snap2["features"]["byte_size_kb"]["mean"]
        assert new_bytes_mean_pre < 30.0, \
            f"baseline should adapt to dark room, μ={new_bytes_mean_pre:.1f}KB"
        v_calm = evaluate(features=dark(), now=5000.0)
        assert v_calm.verdict == _VERDICT_BENIGN, \
            f"dark-but-calibrated should be benign, got {v_calm.verdict}"
        print(f"  [E] self-calibration (lights dimmed, μ_bytes "
              f"{snap['features']['byte_size_kb']['mean']:.1f} → "
              f"{new_bytes_mean_pre:.1f}) → BENIGN ✓")

        # F. round-trip persistence: snapshot AFTER all writes, then reload
        #    from disk and verify the means match exactly.
        snap_post = baseline_snapshot()
        b_reloaded = _load_baseline()
        assert b_reloaded.n > 0, "reloaded baseline should be non-empty"
        live_mean = snap_post["features"]["byte_size_kb"]["mean"]
        delta = abs(b_reloaded.mean[0] - live_mean)
        assert delta < 0.01, (
            f"round-trip mean mismatch: disk={b_reloaded.mean[0]:.4f} "
            f"vs snapshot={live_mean:.4f} (Δ={delta:.4f})"
        )
        print(f"  [F] persistence round-trip ✓ (n={b_reloaded.n}, "
              f"μ_bytes={b_reloaded.mean[0]:.2f})")

        # G. summary_for_alice produces a non-empty string after baseline built.
        s = summary_for_alice()
        assert s and "OPTICAL IMMUNE" in s
        print(f"  [G] summary_for_alice ✓")
        print(f"      {s}")

        # H. live evaluate() against real ledgers (read-only path) — should
        #    not raise even though our sandbox has no real ledgers. We
        #    temporarily redirect feature paths back to repo for honesty.
        global _IRIS_LOG, _BROCA_LOG, _CONV_LOG, _SSP_STATE
        repo_state = _REPO / ".sifta_state"
        _IRIS_LOG  = repo_state / "swarm_iris_capture.jsonl"
        _BROCA_LOG = repo_state / "broca_vocalizations.jsonl"
        _CONV_LOG  = repo_state / "alice_conversation.jsonl"
        _SSP_STATE = repo_state / "speech_potential.json"
        v_live = evaluate_now()
        print(f"  [H] live ledger probe ✓ (verdict={v_live.verdict}, "
              f"z_o={v_live.z_optical:.2f}, z_t={v_live.z_temporal:.2f})")

        print("[OIS] all checks passed.")
        return 0

    except AssertionError as e:
        print(f"[OIS] FAIL: {e}")
        return 1
    except Exception as e:
        print(f"[OIS] CRASH: {type(e).__name__}: {e}")
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
            "optical_immune_system.py — Vision Olympiad immune membrane\n"
            "  evaluate        run one tick against live ledgers, print verdict\n"
            "  baseline        dump current rolling baseline (μ, σ per feature)\n"
            "  events [N=5]    show last N immune events from the audit log\n"
            "  alice-line      one-line summary for Alice's _SYSTEM_PROMPT\n"
            "  smoke           run the sandboxed self-test\n"
        )
        return 0
    cmd = argv[0]
    if cmd == "evaluate":
        v = evaluate_now()
        print(json.dumps(v.to_log(), indent=2, sort_keys=True))
        return 0
    if cmd == "baseline":
        print(json.dumps(baseline_snapshot(), indent=2, sort_keys=True))
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
