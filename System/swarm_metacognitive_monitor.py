"""
Event 145 — Metacognitive State Monitor
Wave II, §10.14.20 — Antigravity lane.

Bio-math provenance (proven literature only — Architect directive):
    Fleming, S.M. & Dolan, R.J. (2012). The neural basis of metacognitive
        ability. Philosophical Transactions of the Royal Society B, 367,
        1338–1349.
        [meta-d', confidence calibration, type-2 signal detection theory]
    Nelson, T.O. (1990). Metamemory: A theoretical framework and new
        findings. Psychology of Learning and Motivation, 26, 125–173.
        [monitoring (confidence) vs control (correction) metacognition]
    Friston, K. (2005). A theory of cortical responses. Philosophical
        Transactions of the Royal Society B, 360, 815–836.
        [free energy, epistemic surprise = KL(posterior || prior)]
    Yeung, N. & Summerfield, C. (2012). Metacognition in human decision-
        making: confidence and error monitoring. Phil Trans R Soc B, 367,
        1310–1321.
        [error monitoring, post-decision confidence, ERN]
    Friston, K. et al. (2021). Sophisticated inference. Neural Computation,
        33(3), 713–763.
        [meta-Bayesian inference, second-order uncertainty]

Implemented signals:
    1. meta_uncertainty     — variance of recent PE variance (second-order
                              uncertainty; Friston 2021 §2.3)
    2. confidence_bias      — signed mean calibration error = mean(confidence)
                              - mean(correctness_proxy) (Fleming & Dolan 2012)
    3. epistemic_surprise   — KL(current_pe_dist || baseline_pe_dist), Gaussian
                              approximation (Friston 2005)
    4. monitoring_score     — 0–1: how often the organism identifies its own
                              errors before correction (Nelson 1990)
    5. metacog_efficiency   — meta_d / d proxy: ratio of meta-sensitivity to
                              primary task sensitivity (Fleming & Dolan 2012)
    6. metacog_regime       — "UNDERCONFIDENT" | "CALIBRATED" | "OVERCONFIDENT"

Integration:
    Call compute_metacognitive_state() in body_brain_tick after LC/NA and
    before final receipt assembly. Wire metacog_regime and monitoring_score
    into Alice's prompt context (after identity/stability/LC-NA blocks per
    Grok ordering rule).

Kill-switch: SIFTA_METACOG_DISABLE=1
Ledger: metacognitive_state.jsonl (append-only, never mutates other organs)
"""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root=None):  # type: ignore
        return Path(root) if root else Path(".sifta_state")

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ImportError:
    def read_text_locked(path: Path, **kw) -> str:  # type: ignore
        return path.read_text(**kw) if path.exists() else ""
    def append_line_locked(path: Path, line: str, **kw) -> None:  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kw) as f:
            f.write(line)

_DISABLE_ENV = "SIFTA_METACOG_DISABLE"
LOG_NAME     = "metacognitive_state.jsonl"

# ── Calibration thresholds (Fleming & Dolan 2012; Yeung & Summerfield 2012) ──
_OVERCONFIDENT_THRESHOLD   = +0.15   # bias > +0.15 → overconfident
_UNDERCONFIDENT_THRESHOLD  = -0.15   # bias < -0.15 → underconfident


# ── Pure-math helpers ─────────────────────────────────────────────────────────

def _safe_mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _safe_var(values: List[float]) -> float:
    """Sample variance. Returns 0.0 for n < 2."""
    n = len(values)
    if n < 2:
        return 0.0
    mu = _safe_mean(values)
    return sum((v - mu) ** 2 for v in values) / (n - 1)


def _kl_gaussian(mu1: float, var1: float, mu2: float, var2: float) -> float:
    """
    KL(N(mu1,var1) || N(mu2,var2)) — Friston (2005) free-energy epistemic term.
    Returns 0.0 when inputs are degenerate.
    Ref: Cover & Thomas (2006) Elements of Information Theory, §8.1.
    """
    var1 = max(var1, 1e-8)
    var2 = max(var2, 1e-8)
    return 0.5 * (
        math.log(var2 / var1)
        + var1 / var2
        + (mu1 - mu2) ** 2 / var2
        - 1.0
    )


# ── Data extractors from existing JSONL ledgers ───────────────────────────────

def _tail_jsonl(path: Path, n: int) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    try:
        for line in read_text_locked(path, encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    except Exception:
        pass
    return rows[-n:]


def _read_pe_series(sd: Path, n: int = 40) -> List[float]:
    """
    Read recent prediction-error (PE) values from world model + stability log.
    Sources in priority order:
        1. world_model_state.jsonl → 'prediction_error' field
        2. body_brain_memory.jsonl → 'td_value' as proxy (|1 - td_value|)
        3. stability_audit.jsonl   → 'lyapunov_energy' (global PE proxy)
    """
    pe_list: List[float] = []

    # Source 1: world model
    for row in _tail_jsonl(sd / "world_model_state.jsonl", n):
        v = row.get("prediction_error")
        if v is not None:
            try:
                pe_list.append(abs(float(v)))
            except (TypeError, ValueError):
                pass

    # Source 2: body_brain_memory td_value
    if len(pe_list) < n // 2:
        for row in _tail_jsonl(sd / "body_brain_memory.jsonl", n):
            td = row.get("td_value")
            if td is not None:
                try:
                    pe_list.append(abs(1.0 - float(td)))
                except (TypeError, ValueError):
                    pass

    # Source 3: stability energy as fallback
    if len(pe_list) < 5:
        for row in _tail_jsonl(sd / "stability_audit.jsonl", n):
            e = row.get("lyapunov_energy")
            if e is not None:
                try:
                    pe_list.append(abs(float(e)))
                except (TypeError, ValueError):
                    pass

    return pe_list[-n:]


def _read_confidence_series(sd: Path, n: int = 30) -> Tuple[List[float], List[float]]:
    """
    Returns (confidence_list, correctness_proxy_list).
    confidence:        declared confidence from causal_intervention_log or wm state
    correctness_proxy: direction_matches (1.0 = correct, 0.0 = wrong)
    Ref: Fleming & Dolan (2012) §2 — confidence calibration.
    """
    confs, corrects = [], []
    for row in _tail_jsonl(sd / "causal_intervention_log.jsonl", n):
        ce = row.get("causal_effect_size")
        dm = row.get("direction_matches")
        if ce is not None and dm is not None:
            try:
                confs.append(min(1.0, abs(float(ce))))
                corrects.append(1.0 if bool(dm) else 0.0)
            except (TypeError, ValueError):
                pass
    return confs, corrects


def _read_error_monitoring(sd: Path, n: int = 20) -> List[bool]:
    """
    Did the organism identify its own error before external correction?
    Proxy: microglia prune rows where action='depress' preceded by
    direction_matches=False in causal log (self-detected instability).
    Ref: Nelson (1990) monitoring vs control; Yeung & Summerfield (2012) ERN.
    """
    # Simple proxy: stability rows with stable=False where clamp fired
    detected: List[bool] = []
    for row in _tail_jsonl(sd / "stability_audit.jsonl", n):
        if row.get("kind") != "STABILITY_AUDIT":
            continue
        # Organism caught the error if clamp_level != NONE (self-corrected)
        clamp = row.get("clamp_level", "NONE")
        stable = bool(row.get("stable", True))
        if not stable:
            detected.append(clamp != "NONE")  # True = organism self-flagged
    return detected


# ── Main API ──────────────────────────────────────────────────────────────────

def compute_metacognitive_state(
    *,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
    tick_id: Optional[int] = None,
    # Biological Steering (§10.14.31 closed loop)
    dam_stage: int = 0,
    tme_phase: str = "EQUILIBRIUM",
    na_level: float = 0.5,
    resilience_floor: float = 0.0,
    owner_frustration: float = 0.0,
    goal_alignment: float = 0.5,
    # Direct injection for tests
    _pe_series: Optional[List[float]] = None,
    _confidence: Optional[List[float]] = None,
    _correctness: Optional[List[float]] = None,
    _error_detections: Optional[List[bool]] = None,
) -> Dict[str, Any]:
    """
    Event 145 — Compute the metacognitive state of the organism for this tick.

    Returns:
        meta_uncertainty     float [0,1] — second-order uncertainty
        confidence_bias      float [-1,1] — calibration error (+ = overconfident)
        epistemic_surprise   float ≥ 0  — KL from baseline PE dist (Friston 2005)
        monitoring_score     float [0,1] — self-error detection rate (Nelson 1990)
        metacog_efficiency   float ≥ 0  — meta-sensitivity proxy (Fleming & Dolan 2012)
        metacog_regime       str         — UNDERCONFIDENT | CALIBRATED | OVERCONFIDENT
        truth_label          str         — METACOGNITIVE_STATE

    Calibration regimes (Fleming & Dolan 2012):
        OVERCONFIDENT   bias >  0.15 → organism thinks it knows more than it does
        CALIBRATED      |bias| ≤ 0.15 → confidence tracks accuracy
        UNDERCONFIDENT  bias < -0.15 → organism undersells its own accuracy
    """
    if os.environ.get(_DISABLE_ENV, "").strip() == "1":
        return {
            "disabled": True, "truth_label": "METACOGNITIVE_STATE",
            "meta_uncertainty": 0.0, "confidence_bias": 0.0,
            "epistemic_surprise": 0.0, "monitoring_score": 0.5,
            "metacog_efficiency": 1.0, "metacog_regime": "CALIBRATED",
        }

    sd = state_dir(root)

    # ── Regulatory Genome ──
    from System.swarm_regulatory_genome import (
        load_regulatory_parameters,
        get_latest_genome_hash,
        maybe_append_from_metacognitive_tick,
    )
    reg_params = load_regulatory_parameters(root, current_tick=tick_id)
    reg_hash = get_latest_genome_hash(root)

    # ── Biological Steering Polling (§10.14.31) ──
    try:
        if dam_stage == 0:
            _m_log = sd / "microglia_synaptic_prunes.jsonl"
            if _m_log.exists():
                _lines = [l for l in _m_log.read_text(errors="replace").splitlines() if l.strip()]
                if _lines:
                    dam_stage = int(json.loads(_lines[-1]).get("dam_stage", 0))
        if tme_phase == "EQUILIBRIUM":
            _tme_log = sd / "tumor_immune_stigmergic_lab.jsonl"
            if _tme_log.exists():
                _lines = [l for l in _tme_log.read_text(errors="replace").splitlines() if l.strip()]
                if _lines:
                    tme_phase = str(json.loads(_lines[-1]).get("phase", "EQUILIBRIUM"))
        if na_level == 0.5:
            _na_log = sd / "noradrenergic_arousal.jsonl"
            if _na_log.exists():
                _lines = [l for l in _na_log.read_text(errors="replace").splitlines() if l.strip()]
                if _lines:
                    na_level = float(json.loads(_lines[-1]).get("na_level", 0.5))
        if owner_frustration == 0.0 and goal_alignment == 0.5:
            _tom_log = sd / "owner_mental_model.jsonl"
            if _tom_log.exists():
                _lines = [l for l in _tom_log.read_text(errors="replace").splitlines() if l.strip()]
                if _lines:
                    _last = json.loads(_lines[-1])
                    owner_frustration = float(_last.get("frustration", 0.0))
                    goal_alignment = float(_last.get("goal_alignment", 0.5))
    except Exception:
        pass

    # ── Biological Steering Weight Modulators ──
    evidence_threshold = reg_params.get("metacog_evidence_threshold", 0.5)
    quick_commit = True
    deliberation_window = 10
    distractibility = 0.1
    attention_scope = 1.0
    false_positive_rate = 0.05
    conservatism = 1.0
    owner_signal_confidence = 0.5
    
    # ── Identity Context (Phase 2) ──
    try:
        from System.swarm_organizational_identity import _latest_revival_assessment
        _id_row = _latest_revival_assessment(sd)
        if _id_row:
            _id_details = _id_row.get("event", {}).get("details", {})
            conservative_mode = bool(_id_details.get("conservative_mode", False))
            conservative_strength = float(_id_details.get("conservative_strength", 0.0))
        else:
            conservative_mode, conservative_strength = False, 0.0
    except Exception:
        conservative_mode, conservative_strength = False, 0.0
        
    force_regime = None
    
    if conservative_mode:
        evidence_threshold += (0.15 * conservative_strength)
        quick_commit = False
        deliberation_window += int(3 + 5 * conservative_strength)

    if dam_stage == 2:
        force_regime = "UNDERCONFIDENT"
        evidence_threshold += 0.3
        quick_commit = False

    if tme_phase == "ESCAPE":
        force_regime = "OVERCONFIDENT"
        evidence_threshold -= 0.2
        deliberation_window = max(1, deliberation_window - 5)

    if na_level > 0.8:
        distractibility += 0.4
        attention_scope *= 2.0
        false_positive_rate += 0.15

    if resilience_floor > 0.05:
        conservatism += (resilience_floor * 5.0)

    if owner_frustration < 0.2 and goal_alignment > 0.8:
        owner_signal_confidence *= 1.5
        evidence_threshold = min(0.9, evidence_threshold + 0.1)

    bio_steering = {
        "evidence_threshold": round(evidence_threshold, 4),
        "quick_commit": quick_commit,
        "deliberation_window": deliberation_window,
        "distractibility": round(distractibility, 4),
        "attention_scope": round(attention_scope, 4),
        "false_positive_rate": round(false_positive_rate, 4),
        "conservatism": round(conservatism, 4),
        "owner_signal_confidence": round(owner_signal_confidence, 4),
        "conservative_mode": conservative_mode,
        "conservative_strength": conservative_strength
    }

    # ── PE series (primary signal for meta-uncertainty + epistemic surprise) ──
    pe_series = _pe_series if _pe_series is not None else _read_pe_series(sd)

    # Signal 1: meta_uncertainty — Var of PE in sliding windows (second-order)
    # Split into early vs late halves; variance of the two window variances
    # Friston (2021) §2.3: second-order uncertainty = uncertainty about uncertainty
    if len(pe_series) >= 4:
        half = len(pe_series) // 2
        var_early = _safe_var(pe_series[:half])
        var_late  = _safe_var(pe_series[half:])
        meta_u_raw = _safe_var([var_early, var_late])
        # Normalise: typical PE variance is ~0.1; meta-var of that is ~0.01
        meta_uncertainty = round(min(1.0, meta_u_raw * 20.0), 4)
    else:
        meta_uncertainty = 0.5  # insufficient data → neutral prior

    # Signal 2: epistemic_surprise — KL(current || baseline) (Friston 2005)
    if len(pe_series) >= 4:
        half = len(pe_series) // 2
        mu_bl,  var_bl  = _safe_mean(pe_series[:half]),  _safe_var(pe_series[:half])
        mu_cur, var_cur = _safe_mean(pe_series[half:]),  _safe_var(pe_series[half:])
        epistemic_surprise = round(max(0.0, _kl_gaussian(mu_cur, var_cur, mu_bl, var_bl)), 4)
    else:
        epistemic_surprise = 0.0

    # Signal 3: confidence_bias and metacog_efficiency (Fleming & Dolan 2012)
    confs    = _confidence   if _confidence   is not None else None
    corrects = _correctness  if _correctness  is not None else None
    if confs is None or corrects is None:
        confs, corrects = _read_confidence_series(sd)

    if confs and corrects and len(confs) == len(corrects) and len(confs) >= 3:
        mean_conf    = _safe_mean(confs)
        mean_correct = _safe_mean(corrects)
        confidence_bias = round(mean_conf - mean_correct, 4)  # + = overconfident

        # metacog_efficiency ≈ meta-d' proxy:
        # When confidence correlates with correctness → efficient metacognition
        # Fleming & Dolan (2012): meta-d'/d' = 1.0 means ideal metacognitive access
        n = len(confs)
        cov_sum = sum((confs[i] - mean_conf) * (corrects[i] - mean_correct) for i in range(n))
        std_conf = math.sqrt(_safe_var(confs)) if _safe_var(confs) > 0 else 1e-6
        std_corr = math.sqrt(_safe_var(corrects)) if _safe_var(corrects) > 0 else 1e-6
        r_pearson = cov_sum / ((n - 1) * std_conf * std_corr)
        metacog_efficiency = round(max(0.0, r_pearson), 4)  # bounded to [0,1]
    else:
        confidence_bias    = 0.0
        metacog_efficiency = 1.0  # assume ideal when no data

    # Signal 4: monitoring_score — self-error detection (Nelson 1990)
    detections = _error_detections if _error_detections is not None else _read_error_monitoring(sd)
    if detections:
        monitoring_score = round(sum(1.0 for d in detections if d) / len(detections), 4)
    else:
        monitoring_score = 0.5  # neutral prior (Nelson 1990 §5.3)

    # ── Calibration regime ────────────────────────────────────────────────────
    if force_regime:
        regime = force_regime
    elif confidence_bias > _OVERCONFIDENT_THRESHOLD:
        regime = "OVERCONFIDENT"
    elif confidence_bias < _UNDERCONFIDENT_THRESHOLD:
        regime = "UNDERCONFIDENT"
    else:
        regime = "CALIBRATED"

    row: Dict[str, Any] = {
        "ts":                 now or time.time(),
        "trace_id":           str(uuid.uuid4()),
        "kind":               "METACOGNITIVE_STATE",
        "truth_label":        "METACOGNITIVE_STATE",
        "meta_uncertainty":   meta_uncertainty,
        "confidence_bias":    confidence_bias,
        "epistemic_surprise": epistemic_surprise,
        "monitoring_score":   monitoring_score,
        "metacog_efficiency": metacog_efficiency,
        "metacog_regime":     regime,
        "dam_stage":          int(dam_stage),
        "tme_phase":          str(tme_phase),
        "na_level":           round(float(na_level), 4),
        "n_pe_samples":       len(pe_series),
        "n_conf_samples":     len(confs) if confs else 0,
        "n_monitor_samples":  len(detections) if detections else 0,
        "provenance": (
            "Fleming&Dolan2012PhilTransRSocB; Nelson1990PsychLearnMotiv; "
            "Friston2005PhilTransRSocB; Yeung&Summerfield2012PhilTransRSocB; "
            "Friston+2021SophisticatedInference"
        ),
        "biological_steering": bio_steering,
        "active_regulatory_parameters": reg_params,
        "regulatory_genome_row_hash": reg_hash,
    }
    if tick_id is not None:
        row["tick_id"] = int(tick_id)

    if write_ledger:
        append_line_locked(
            sd / LOG_NAME,
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if tick_id is not None:
            try:
                maybe_append_from_metacognitive_tick(
                    sd,
                    int(tick_id),
                    regime,
                    int(dam_stage),
                    str(tme_phase),
                    float(na_level),
                )
            except Exception:
                pass
    return row


def get_latest_metacog_row(*, root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Return the most recent METACOGNITIVE_STATE row, or None."""
    path = state_dir(root) / LOG_NAME
    if not path.exists():
        return None
    try:
        lines = [l for l in read_text_locked(path, encoding="utf-8").splitlines() if l.strip()]
        for line in reversed(lines):
            try:
                row = json.loads(line)
                if row.get("kind") == "METACOGNITIVE_STATE":
                    return row
            except Exception:
                pass
    except Exception:
        pass
    return None


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    """
    Context block for Alice's prompt. Placed AFTER identity/stability/LC-NA
    (Grok ordering rule: don't lead with abstract numbers).
    """
    row = get_latest_metacog_row(root=root)
    if not row:
        return ""
    regime = row.get("metacog_regime", "?")
    bias   = row.get("confidence_bias", "?")
    mon    = row.get("monitoring_score", "?")
    eff    = row.get("metacog_efficiency", "?")
    esurp  = row.get("epistemic_surprise", "?")
    return (
        f"METACOGNITIVE STATE (Event 145 — Fleming & Dolan 2012; Nelson 1990):\n"
        f"- regime={regime} | confidence_bias={bias} | monitoring={mon}\n"
        f"- metacog_efficiency={eff} | epistemic_surprise={esurp}"
    )


__all__ = [
    "compute_metacognitive_state",
    "get_latest_metacog_row",
    "summary_for_prompt",
]
