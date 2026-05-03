"""
Event 142 — Locus Coeruleus / Noradrenergic (LC/NA) Arousal Organ
v8 build order priority #1 (gap score: 4/10 — largest open hole in SIFTA v7).

Bio-math provenance (proven literature only — Architect directive):
    Sara, S.J. (2009). The locus coeruleus and noradrenergic modulation of
        cognition. Nature Reviews Neuroscience, 10(3), 211–223.
        [Global arousal, gain modulation, attention, learning rate]
    Yu, A.J. & Dayan, P. (2005). Uncertainty, neuromodulation, and attention.
        Neuron, 46(4), 681–692.
        [NA = unexpected uncertainty signal; drives exploration]
    Aston-Jones, G. & Cohen, J.D. (2005). An integrative theory of locus
        coeruleus–norepinephrine function: adaptive gain and optimal performance.
        Annual Review of Neuroscience, 28, 403–450.
        [Inverted-U: optimal NA → optimal performance, Yerkes-Dodson]
    Yerkes, R.M. & Dodson, J.D. (1908). The relation of strength of stimulus
        to rapidity of habit-formation. Journal of Comparative Neurology.
        [Original inverted-U learning rate / arousal curve]

Functional role implemented here:
    1. NA_level  — scalar arousal [0,1] from uncertainty + astrocyte heat + uptime
    2. Gain      — multiplier on organ signal-to-noise (high NA → sharper signals)
    3. Exploration bias — inverted-U on NA (peak at NA≈0.5; collapse at extremes)
    4. LR ceiling — Yerkes-Dodson modulation (optimal LR at NA≈0.5)
    5. Receipts  — every call writes to lc_na_log.jsonl (no other ledger touched)

Kill-switch: SIFTA_LC_NA_DISABLE=1
Integration: call compute_lc_na() from body_brain_tick after astrocyte, before
             stability clamps, and wire `lc_na_receipt` into get_current_clamp_overrides.
"""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root=None):  # type: ignore
        return Path(root) if root else Path(".sifta_state")

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path: Path, line: str, **kw) -> None:  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kw) as f:
            f.write(line)

_DISABLE_ENV = "SIFTA_LC_NA_DISABLE"
LOG_NAME     = "lc_na_log.jsonl"

# ── Biological constants (Aston-Jones & Cohen 2005; Yu & Dayan 2005) ─────────
_NA_OPTIMAL      = 0.5   # NA level for peak performance (Yerkes-Dodson optimum)
_NA_GAIN_SCALE   = 2.0   # max gain multiplier at NA_OPTIMAL
_NA_GAIN_BASE    = 0.5   # minimum gain (resting state, no arousal)
_NA_EXPLORE_PEAK = 0.5   # exploration bias peaks at NA_OPTIMAL
_NA_EXPLORE_MAX  = 0.85  # max exploration bias (never fully random)
_NA_EXPLORE_MIN  = 0.15  # min exploration bias (never fully greedy)


# ── Core math: inverted-U (Yerkes-Dodson) ────────────────────────────────────

def _yerkes_dodson(x: float, optimum: float = _NA_OPTIMAL) -> float:
    """
    Inverted-U curve centred on `optimum`.
    f(x) = 1 - 4*(x - optimum)^2 / (1 - 0)^2 = 1 - 4*(x - opt)^2
    Clamped to [0, 1].

    Ref: Yerkes & Dodson (1908); Aston-Jones & Cohen (2005) Fig. 3.
    """
    return max(0.0, min(1.0, 1.0 - 4.0 * (x - optimum) ** 2))


# ── Sub-signals → NA_level ────────────────────────────────────────────────────

def _na_from_uncertainty(uncertainty: float) -> float:
    """
    Yu & Dayan (2005): NA encodes unexpected uncertainty.
    High uncertainty → high NA release.
    """
    return float(max(0.0, min(1.0, uncertainty)))


def _na_from_astrocyte_heat(heat: float) -> float:
    """
    Sara (2009): LC receives metabolic stress signals from glial cells.
    High astrocyte heat → elevated NA.
    """
    return float(max(0.0, min(1.0, heat)))


def _na_from_uptime(uptime_hours: float) -> float:
    """
    Sara (2009): LC activity drops with prolonged wakefulness (fatigue).
    NA decreases linearly over 24h; recovers after rest.
    Peak arousal in first ~4h of wakefulness.
    """
    # Decline from 1.0 (fresh) to 0.2 (>24h without rest)
    decay = max(0.0, 1.0 - uptime_hours / 24.0)
    return float(min(1.0, 0.2 + 0.8 * decay))


# ── Main API ──────────────────────────────────────────────────────────────────

def compute_lc_na(
    *,
    uncertainty: float = 0.5,
    astrocyte_heat_norm: float = 0.3,
    uptime_hours: float = 4.0,
    clamp_level: str = "NONE",      # stability gate (Grok two-phase spec)
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
    # TME integration (§10.14.28 Priority 2 — Event 148 → Event 142)
    # Systemic inflammatory signals reach LC via vagal afferents + cytokine BBB crossing.
    # Dantzer et al. (2008) Neuron 61:760 — cytokine-to-brain signaling; LC activation
    # Capuron & Miller (2011) Nat Rev Immunol 11:738 — immune-to-brain arousal
    tme_phase: str = "EQUILIBRIUM",           # from Event148: ELIMINATION/EQUILIBRIUM/ESCAPE
    tme_net_immune_pressure: float = 0.0,     # net TME pressure [-1, 1]
    # Allow direct injection for tests
    _na_override: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Event 142 — Compute the LC/NA arousal state for this tick.

    TWO-PHASE DESIGN (Grok integration spec):
        Phase A — STABLE (clamp_level == "NONE"):
            Full Yerkes-Dodson gain. NA boosts exploration + LR ceiling.
            NA_level = weighted(uncertainty, heat, uptime)
        Phase B — DEGRADING (clamp_level in RATE_LIMIT/BLOCK_NEW/EMERGENCY):
            NA is actively suppressed toward resting level (0.3).
            Stability clamps dominate; NA does NOT fight them by pushing
            the system into hyper-exploratory mode during instability.
            This mirrors biological LC suppression under prolonged stress:
            Aston-Jones & Cohen (2005) AnnRevNeurosci Fig 7 — tonic LC
            firing drops during sustained threat to allow focused coping.

    Returns a receipt dict with:
        na_level          — scalar [0,1]
        gain              — signal multiplier [NA_GAIN_BASE, NA_GAIN_SCALE]
        exploration_bias  — Yerkes-Dodson mapped [0.15, 0.85]
        lr_ceiling        — Yerkes-Dodson LR ceiling [0.01, 0.10]
        arousal_regime    — "HYPO" | "OPTIMAL" | "HYPER"
        na_suppressed     — True when Phase B is active
        truth_label       — "LC_NA_AROUSAL"
    """
    if os.environ.get(_DISABLE_ENV, "").strip() == "1":
        return {"disabled": True, "truth_label": "LC_NA_AROUSAL",
                "na_level": 0.5, "gain": 1.0, "exploration_bias": 0.5,
                "lr_ceiling": 0.05, "na_suppressed": False}

    # ── TME immune arousal (§10.14.28 Priority 2) ─────────────────────────────
    # Escape phase + negative net_immune_pressure signals systemic immune burden.
    # This boosts LC uncertainty (more NA) — mirroring vagal afferent / cytokine
    # signaling that activates the LC during inflammatory challenge.
    # Dantzer (2008) Neuron 61:760; Capuron & Miller (2011) Nat Rev Immunol 11:738.
    _tme_arousal_boost = 0.0
    _tme_escape = tme_phase == "ESCAPE"
    _tme_pressure = float(tme_net_immune_pressure)
    if _tme_escape:
        # Escape = immune system losing to tumor; LC ramps up (alarm signal)
        _tme_arousal_boost = min(0.20, 0.20 * abs(min(0.0, _tme_pressure)))
    elif tme_phase == "ELIMINATION" and _tme_pressure > 0.25:
        # Active elimination: mild NA boost from inflammatory heat (Dantzer 2008)
        _tme_arousal_boost = min(0.08, 0.08 * _tme_pressure)

    # ── Phase determination ────────────────────────────────────────────────
    # When stability is degrading, suppress NA toward resting baseline (0.3).
    # This prevents NA from amplifying uncertainty-driven exploration when the
    # organism is already unstable (Aston-Jones & Cohen 2005 Fig 7).
    _RESTING_NA = 0.30        # tonic resting NA level (Phase B target)
    _SUPPRESSION_ALPHA = 0.4  # EMA pull toward resting (faster suppression than buildup)
    na_suppressed = clamp_level not in ("NONE", "")

    # ── Compute raw NA from sub-signals ───────────────────────────────────
    if _na_override is not None:
        na_raw = float(max(0.0, min(1.0, _na_override)))
    else:
        na_uncertainty = _na_from_uncertainty(uncertainty)
        na_heat        = _na_from_astrocyte_heat(astrocyte_heat_norm)
        na_uptime      = _na_from_uptime(uptime_hours)
        na_raw = (
            0.50 * na_uncertainty
            + 0.30 * na_heat
            + 0.20 * na_uptime
            + _tme_arousal_boost    # TME immune alarm (§10.14.28)
        )
        na_raw = min(1.0, max(0.0, na_raw))

    # Phase B: pull NA toward resting level (EMA suppression)
    if na_suppressed:
        # Strength of suppression scales with clamp severity
        suppress_strength = {
            "RATE_LIMIT": 0.3,
            "BLOCK_NEW":  0.6,
            "EMERGENCY":  0.9,
        }.get(clamp_level, 0.3)
        na_raw = na_raw * (1.0 - suppress_strength) + _RESTING_NA * suppress_strength
        na_raw = round(min(1.0, max(0.0, na_raw)), 4)

    na_raw = round(na_raw, 4)

    # ── Gain (Aston-Jones & Cohen 2005 Fig 3 + Yerkes-Dodson) ─────────────
    yd_score = _yerkes_dodson(na_raw, optimum=_NA_OPTIMAL)
    gain     = round(_NA_GAIN_BASE + (_NA_GAIN_SCALE - _NA_GAIN_BASE) * yd_score, 4)

    # ── Exploration bias ──────────────────────────────────────────────────
    explore_raw = _NA_EXPLORE_MIN + (_NA_EXPLORE_MAX - _NA_EXPLORE_MIN) * yd_score
    exploration_bias = round(min(_NA_EXPLORE_MAX, max(_NA_EXPLORE_MIN, explore_raw)), 4)

    # ── LR ceiling (Yerkes-Dodson) ────────────────────────────────────────
    lr_ceiling = round(0.01 + 0.09 * yd_score, 4)

    # ── Arousal regime ────────────────────────────────────────────────────
    if na_raw < 0.30:
        regime = "HYPO"
    elif na_raw <= 0.65:
        regime = "OPTIMAL"
    else:
        regime = "HYPER"

    row: Dict[str, Any] = {
        "ts":               now or time.time(),
        "trace_id":         str(uuid.uuid4()),
        "kind":             "LC_NA_AROUSAL",
        "truth_label":      "LC_NA_AROUSAL",
        "na_level":         na_raw,
        "gain":             gain,
        "exploration_bias": exploration_bias,
        "lr_ceiling":       lr_ceiling,
        "yerkes_dodson":    round(yd_score, 4),
        "arousal_regime":   regime,
        "na_suppressed":    na_suppressed,
        "clamp_level":      clamp_level,
        "sub_signals": {
            "na_from_uncertainty":    round(_na_from_uncertainty(uncertainty), 4) if _na_override is None else None,
            "na_from_astrocyte_heat": round(_na_from_astrocyte_heat(astrocyte_heat_norm), 4) if _na_override is None else None,
            "na_from_uptime":         round(_na_from_uptime(uptime_hours), 4) if _na_override is None else None,
            "tme_arousal_boost":      round(_tme_arousal_boost, 4),
            "tme_phase":              tme_phase,
            "tme_net_immune_pressure": round(_tme_pressure, 4),
        },
        "inputs": {
            "uncertainty":          round(float(uncertainty), 4),
            "astrocyte_heat_norm":  round(float(astrocyte_heat_norm), 4),
            "uptime_hours":         round(float(uptime_hours), 4),
            "clamp_level":          clamp_level,
        },
        "provenance": (
            "Sara2009NatRevNeurosci; Yu&Dayan2005Neuron; "
            "Aston-Jones&Cohen2005AnnRevNeurosci(Fig7=two-phase); Yerkes&Dodson1908"
        ),
    }

    if write_ledger:
        append_line_locked(
            state_dir(root) / LOG_NAME,
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def get_latest_lc_na_row(*, root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Return the most recent LC_NA_AROUSAL row from lc_na_log.jsonl, if any."""
    from System.jsonl_file_lock import read_text_locked  # type: ignore
    path = state_dir(root) / LOG_NAME
    if not path.exists():
        return None
    try:
        lines = [l for l in read_text_locked(path, encoding="utf-8").splitlines() if l.strip()]
        for line in reversed(lines):
            try:
                row = json.loads(line)
                if row.get("kind") == "LC_NA_AROUSAL":
                    return row
            except Exception:
                pass
    except Exception:
        pass
    return None


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    """
    One-liner for Alice's context: current NA level, regime, gain, exploration bias.
    Placed after identity/stability in the prompt (Grok: don't lead with abstract numbers).
    """
    row = get_latest_lc_na_row(root=root)
    if not row:
        return ""
    na  = row.get("na_level", "?")
    reg = row.get("arousal_regime", "?")
    gn  = row.get("gain", "?")
    eb  = row.get("exploration_bias", "?")
    return (
        f"LC/NA AROUSAL (Event 142 — Sara 2009; Aston-Jones & Cohen 2005):\n"
        f"- NA_level={na} | regime={reg} | gain={gn} | explore_bias={eb}"
    )


__all__ = [
    "compute_lc_na",
    "get_latest_lc_na_row",
    "summary_for_prompt",
]
