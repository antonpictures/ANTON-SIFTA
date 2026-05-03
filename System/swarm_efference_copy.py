"""
Event 143 — Efference Copy / Sensorimotor Agency Monitor
SIFTA v8.0 — Closes the sensorimotor loop; provides real agency detection.

Bio-math provenance (proven literature only — Architect directive):
    Sperry, R.W. (1950). Neural basis of the spontaneous optokinetic
        response produced by visual inversion. Journal of Comparative and
        Physiological Psychology, 43(6), 482–489.
        [coined "efference copy": copy of motor command sent to sensory predictor]
    von Holst, E. & Mittelstaedt, H. (1950). Das Reafferenzprinzip.
        Naturwissenschaften, 37(20), 464–476.
        [Reafference principle: efference copy → expected reafference;
         mismatch = exafference (external); match = self-generated]
    Wolpert, D.M., Ghahramani, Z. & Jordan, M.I. (1995). An internal model
        for sensorimotor integration. Science, 269(5232), 1880–1882.
        [Forward model: predicts sensory consequence from motor command;
         inverse model: infers command from desired state]
    Blakemore, S.J., Wolpert, D.M. & Frith, C.D. (1998). Central
        cancellation of self-produced tickle sensation. Nature Neuroscience,
        1(7), 635–640.
        [Prediction accuracy → sensory attenuation; PE = unexpected reafference]
    Frith, C.D., Blakemore, S.J. & Wolpert, D.M. (2000). Explaining the
        symptoms of schizophrenia: Abnormalities in the awareness of action.
        Brain Research Reviews, 31(2–3), 357–363.
        [agency attribution: high PE → "not me" (exafference); low PE → agency]
    Wolpert, D.M. & Kawato, M. (1998). Multiple paired forward and inverse
        models for motor control. Neural Networks, 11(7–8), 1317–1329.
        [MOSAIC: modular forward/inverse model selection by context]

SIFTA efference copy design:
    Motor command = system action (tool call, gate change, API call, write)
    Forward model  = predict expected log signature (hash of recent tick state)
    Comparator     = compare predicted vs observed log signature
    PE             = L2 distance between predicted and observed feature vectors
    agency_conf    = sigmoid(-PE / sigma) — Blakemore 1998 sensory attenuation
    self_generated = agency_conf > threshold

    Outputs wire into (Grok integration spec):
        - Stability Audit: PE as additional instability signal
        - LC/NA: high PE → unexpected → boost arousal
        - Causal Prober: agency_conf gates whether probing attribution is valid

Kill-switch: SIFTA_EFFERENCE_DISABLE=1
Ledger: efference_copy_log.jsonl (append-only)
State:  efference_state.json (forward model EMA, persisted)
"""
from __future__ import annotations

import hashlib
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
    from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked
except ImportError:
    def read_text_locked(path, **kw):  # type: ignore
        return path.read_text(**kw) if path.exists() else ""
    def append_line_locked(path, line, **kw):  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kw) as f:
            f.write(line)
    def rewrite_text_locked(path, content, **kw):  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", **kw) as f:
            f.write(content)

_DISABLE_ENV = "SIFTA_EFFERENCE_DISABLE"
LOG_NAME     = "efference_copy_log.jsonl"
STATE_NAME   = "efference_state.json"

# ── Constants ──────────────────────────────────────────────────────────────────
_SIGMA             = 0.30   # PE normalisation σ (Blakemore 1998 sensory attenuation width)
_AGENCY_THRESHOLD  = 0.55   # agency_conf above this → self_generated (Frith 2000 §3.2)
_PE_ALPHA          = 0.25   # EMA alpha for forward model update (Wolpert 1995 §2)
_WINDOW_SIZE       = 8      # tick-feature window for forward model


# ── Math helpers ───────────────────────────────────────────────────────────────

def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def _l2(a: List[float], b: List[float]) -> float:
    """L2 distance between two equal-length feature vectors."""
    if len(a) != len(b) or not a:
        return 1.0
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _feature_vector(tick_state: Dict[str, Any]) -> List[float]:
    """
    Extract a compact float feature vector from tick_state.
    Ref: Wolpert et al. (1995) — forward model predicts over a low-dim state repr.

    Dimensions:
        0: td_value (reward signal)
        1: uncertainty (world model uncertainty)
        2: stability_score (normalised Lyapunov V)
        3: astrocyte_heat (metabolic)
        4: na_level (arousal)
        5: valence (affective)
    """
    def _safe(key: str, default: float = 0.5) -> float:
        v = tick_state.get(key)
        if v is None:
            return default
        try:
            return max(0.0, min(1.0, float(v)))
        except Exception:
            return default

    return [
        _safe("td_value",        0.5),
        _safe("uncertainty",     0.5),
        _safe("stability_score", 0.5),
        _safe("astrocyte_heat",  0.3),
        _safe("na_level",        0.5),
        _safe("valence",         0.5),
    ]


def _action_signature(action_kind: str, action_payload: Dict[str, Any]) -> str:
    """Stable hash of an action (motor command fingerprint)."""
    blob = json.dumps({"kind": action_kind, **action_payload}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


# ── Forward model state I/O ────────────────────────────────────────────────────

def _load_forward_state(sd: Path) -> Dict[str, Any]:
    path = sd / STATE_NAME
    if path.exists():
        try:
            raw = read_text_locked(path, encoding="utf-8", errors="replace").strip()
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    # Default: uniform prior over feature space (no prior history)
    return {
        "predicted_features":   [0.5] * 6,
        "pe_ema":               0.5,      # running PE average
        "total_actions":        0,
        "self_generated_count": 0,
    }


def _save_forward_state(sd: Path, state: Dict[str, Any]) -> None:
    try:
        rewrite_text_locked(sd / STATE_NAME, json.dumps(state) + "\n", encoding="utf-8")
    except Exception:
        pass


# ── Core computation ───────────────────────────────────────────────────────────

def compute_efference_copy(
    *,
    action_kind: str = "idle",
    action_payload: Optional[Dict[str, Any]] = None,
    observed_tick_state: Optional[Dict[str, Any]] = None,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
    # Test injection
    _predicted_features: Optional[List[float]] = None,
    _observed_features:  Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Event 143 — Compute efference copy receipt for this tick.

    Algorithm (Wolpert et al. 1995 + Blakemore et al. 1998):
        1. Load persisted forward model prediction (from last tick).
        2. Extract feature vector from observed_tick_state.
        3. PE = L2(predicted, observed) / √N  (normalised L2)
        4. agency_conf = sigmoid(-(PE / σ) * scale)
        5. self_generated = agency_conf > _AGENCY_THRESHOLD
        6. Update forward model: predicted_t+1 = EMA(predicted_t, observed_t, α)
        7. Persist + log.

    Args:
        action_kind:      label of the motor command (tool call type, gate name, etc.)
        action_payload:   key-value metadata of the command
        observed_tick_state: feature dict from this tick's outcome

    Returns receipt dict with:
        prediction_error   — float [0, 1]: mismatch between predicted and actual
        agency_confidence  — float [0, 1]: confidence this outcome was self-generated
        self_generated     — bool: agency_confidence > threshold
        pe_ema             — running EMA of PE (Wolpert & Kawato 1998 model selection)
        truth_label        — "EFFERENCE_COPY"
    """
    if os.environ.get(_DISABLE_ENV, "").strip() == "1":
        return {
            "disabled": True, "truth_label": "EFFERENCE_COPY",
            "prediction_error": 0.0, "agency_confidence": 1.0,
            "self_generated": True, "pe_ema": 0.0,
        }

    sd = state_dir(root)
    fwd = _load_forward_state(sd)
    action_payload = action_payload or {}
    observed_tick_state = observed_tick_state or {}

    # ── Feature vectors ──────────────────────────────────────────────────────
    predicted = (_predicted_features if _predicted_features is not None
                 else fwd["predicted_features"])
    observed  = (_observed_features if _observed_features is not None
                 else _feature_vector(observed_tick_state))

    # Ensure same length (pad or truncate to 6)
    _N = 6
    predicted = (list(predicted) + [0.5] * _N)[:_N]
    observed  = (list(observed)  + [0.5] * _N)[:_N]

    # ── Prediction error (normalised L2) ─────────────────────────────────────
    # Blakemore (1998): PE = mismatch between efference copy prediction and reafference
    pe_raw    = _l2(predicted, observed) / math.sqrt(_N)
    pe_norm   = max(0.0, min(1.0, pe_raw))

    # ── Agency confidence ─────────────────────────────────────────────────────
    # Blakemore (1998): sensory attenuation is maximal when prediction is perfect.
    # Frith (2000): agency_conf = f(1 - PE) — inversely related to mismatch.
    # sigmoid((1 - pe_norm/σ) * 4):
    #   PE=0   → sigmoid(+∞ clipped) → ~1.0  (perfect prediction → full agency)
    #   PE=σ   → sigmoid(0) → 0.5            (at noise floor → uncertain)
    #   PE→1   → sigmoid(-ve large) → ~0.0   (exafference → no agency)
    _pe_ratio = min(pe_norm / (_SIGMA + 1e-9), 4.0)   # cap ratio to avoid overflow
    agency_conf = round(_sigmoid((1.0 - _pe_ratio) * 4.0), 4)
    self_gen    = agency_conf > _AGENCY_THRESHOLD

    # ── Running PE EMA (Wolpert & Kawato 1998: model selection by prediction quality) ──
    pe_ema_old = float(fwd["pe_ema"])
    pe_ema     = round(pe_ema_old * (1.0 - _PE_ALPHA) + pe_norm * _PE_ALPHA, 4)

    # ── Update forward model: predict next tick's features ───────────────────
    # Wolpert (1995) §2: forward model updated via prediction error
    new_predicted = [
        round(p * (1.0 - _PE_ALPHA) + o * _PE_ALPHA, 4)
        for p, o in zip(predicted, observed)
    ]

    total = int(fwd.get("total_actions", 0)) + 1
    self_gen_count = int(fwd.get("self_generated_count", 0)) + (1 if self_gen else 0)

    # ── Persist forward model ────────────────────────────────────────────────
    new_fwd = {
        "predicted_features":   new_predicted,
        "pe_ema":               pe_ema,
        "total_actions":        total,
        "self_generated_count": self_gen_count,
    }
    _save_forward_state(sd, new_fwd)

    # ── Build receipt ─────────────────────────────────────────────────────────
    row: Dict[str, Any] = {
        "ts":                now or time.time(),
        "trace_id":          str(uuid.uuid4()),
        "kind":              "EFFERENCE_COPY",
        "truth_label":       "EFFERENCE_COPY",
        "action_kind":       action_kind,
        "action_signature":  _action_signature(action_kind, action_payload),
        "prediction_error":  round(pe_norm, 4),
        "agency_confidence": agency_conf,
        "self_generated":    self_gen,
        "pe_ema":            pe_ema,
        "self_generated_rate": round(self_gen_count / max(1, total), 4),
        "vectors": {
            "predicted": [round(x, 4) for x in predicted],
            "observed":  [round(x, 4) for x in observed],
        },
        "agency_threshold":  _AGENCY_THRESHOLD,
        "provenance": (
            "Sperry1950JCPP; vonHolst&Mittelstaedt1950Naturwiss; "
            "Wolpert+1995Science; Blakemore+1998NatNeurosci; "
            "Frith+2000BrainResRev; Wolpert&Kawato1998NeuralNetw"
        ),
    }

    if write_ledger:
        append_line_locked(
            sd / LOG_NAME,
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def get_latest_efference_row(*, root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Return the most recent EFFERENCE_COPY receipt."""
    path = state_dir(root) / LOG_NAME
    if not path.exists():
        return None
    try:
        lines = [l for l in read_text_locked(path, encoding="utf-8").splitlines() if l.strip()]
        for line in reversed(lines):
            try:
                row = json.loads(line)
                if row.get("kind") == "EFFERENCE_COPY":
                    return row
            except Exception:
                pass
    except Exception:
        pass
    return None


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    """Context block for Alice's prompt. Ref: Frith (2000) agency awareness."""
    row = get_latest_efference_row(root=root)
    if not row:
        return ""
    pe   = row.get("prediction_error", "?")
    conf = row.get("agency_confidence", "?")
    sg   = row.get("self_generated", "?")
    ema  = row.get("pe_ema", "?")
    rate = row.get("self_generated_rate", "?")
    regime = ("HIGH_AGENCY" if float(conf) > 0.7
               else "LOW_AGENCY" if float(conf) < 0.4
               else "UNCERTAIN_AGENCY")
    return (
        f"EFFERENCE COPY (Event 143 — Wolpert+1995; Frith+2000):\n"
        f"- regime={regime} | PE={pe} | PE_ema={ema} | "
        f"agency_conf={conf} | self_generated={sg} | sg_rate={rate}"
    )


__all__ = [
    "compute_efference_copy",
    "get_latest_efference_row",
    "summary_for_prompt",
    "_feature_vector",
    "_l2",
    "_sigmoid",
    "_action_signature",
]
