#!/usr/bin/env python3
"""System/swarm_slit_coherence_posterior.py — stigmergic slit coherence organ.

This organ is deliberately separate from ``swarm_alice_body_slit.py``.
The Alice-body slit organ couples swimmer survival to live silicon entropy
and thermal state. This file owns the clean inference problem:

    Given an observed double-slit detector pattern, what coherence
    visibility gamma best explains the screen?

Equal-intensity two-slit boundary
=================================

For a Fraunhofer double-slit with equal slit intensity:

    I(x) = sinc²(pi a x / lambda L)
           · [1 + V cos(2 pi d x / lambda L + phase)]

Michelson visibility is:

    V = (I_max - I_min) / (I_max + I_min) = |gamma_12|

For the SIFTA swimmer translation used here, ``gamma_hypothesis`` is the
surviving coherent fraction in the equal-slit ensemble limit. The old
``gamma²`` mapping is intentionally not used.

Stigmergic posterior
====================

Each swimmer carries a ``gamma_hypothesis`` and optional ``phase_hypothesis``.
It scores against the observed detector strip, deposits pheromone if it is
among the best explainers, and the final pheromone field becomes a posterior
over gamma. That posterior, not a single hard-coded formula output, is the
receipt Alice can reason from.

Discovery mode
==============

``discover_survival_visibility_rule`` runs a second swarm over candidate
rules of the form:

    V = scale · p_survive ** exponent

This lets the organism test whether the body-coupled slit receipts obey
``V ≈ p_survive`` or drift toward a different survival-to-visibility law.

Truth label: ``SIFTA_SLIT_COHERENCE_POSTERIOR_V0``.

Scope boundary
==============

This is a receipt-backed inference/simulation organ. It does not claim a new
physical theory of quantum mechanics. It gives SIFTA a disciplined way to
estimate and compare coherence ledgers without confusing which-path receipts,
screen receipts, and inferred survival rules.
"""
from __future__ import annotations

import json
import math
import time
import uuid
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PHEROMONE_LEDGER = _STATE / "slit_coherence_pheromone_field.jsonl"
_CENSUS_LEDGER = _STATE / "slit_coherence_swimmer_census.jsonl"
_RECEIPTS_LEDGER = _STATE / "slit_coherence_receipts.jsonl"
_DISCOVERY_LEDGER = _STATE / "slit_coherence_discovery_receipts.jsonl"

_TRUTH_LABEL = "SIFTA_SLIT_COHERENCE_POSTERIOR_V0"


def _now() -> float:
    return time.time()


def _safe_append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from System.jsonl_file_lock import append_line_locked  # type: ignore

            append_line_locked(path, json.dumps(row, ensure_ascii=False) + "\n")
            return
        except Exception:
            pass
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        # Receipts should not crash the organ; the returned result still
        # contains the same data for the caller to surface.
        pass


def _request_clearance(lane: str, cost: str = "feather") -> Optional[Dict[str, Any]]:
    try:
        from System.swarm_physics_gate import request_clearance  # type: ignore

        return request_clearance(cost_class=cost, lane=lane)
    except Exception:
        return None


def _qualia_marker(lane: str, note: str = "") -> Dict[str, Any]:
    try:
        from System.swarm_consciousness_organ import qualia_marker  # type: ignore

        return qualia_marker(lane=lane, note=note)
    except Exception:
        return {"lane": lane, "note": note, "fallback": True}


class ThermodynamicClearanceDeferred(RuntimeError):
    """Raised when Alice's body wants to rest before affording this inference.

    Doctrine (George, 2026-05-19): nothing is denied or banned in this system.
    Work is *deferred* / *yielded* / *rested* based on the live body economy.
    Same body, balanced. The covenant amendment lives in
    ``.sifta_state/ide_stigmergic_trace.jsonl`` (action=COVENANT_AMENDMENT_RECEIVED,
    amendment_id=NOTHING_IS_DENIED_BALANCE_IS_THE_LAW_v1).
    """

    def __init__(self, clearance: Dict[str, Any]) -> None:
        self.clearance = clearance
        reasons = ",".join(str(x) for x in clearance.get("reasons", [])) or "unknown"
        super().__init__(
            f"slit coherence deferred — body asked for rest first: {reasons}"
        )


# Backward-compat alias so existing callers don't break; both names refer to
# the same class. New code should use ThermodynamicClearanceDeferred.
ThermodynamicClearanceDenied = ThermodynamicClearanceDeferred


def _processing_clearance(
    process_kind: str,
    *,
    payload: Dict[str, Any],
    expected_value: float,
    write_ledger: bool,
) -> Dict[str, Any]:
    """Ask Alice's processing thermodynamic gate before running the organ."""
    try:
        from System.swarm_processing_thermodynamic_gate import request_processing_clearance

        return request_processing_clearance(
            process_kind,
            expected_value=expected_value,
            payload=payload,
            write_ledger=write_ledger,
        )
    except Exception as exc:
        return {
            "truth_label": "PROCESSING_THERMODYNAMIC_GATE_UNAVAILABLE",
            "allowed": True,
            "action": "allow",
            "reasons": [f"gate_unavailable:{type(exc).__name__}"],
            "body": _body_thermodynamic_snapshot(),
            "receipt_hash": None,
        }


def _body_thermodynamic_snapshot() -> Dict[str, Any]:
    """Best-effort body snapshot for receipts when the gate is unavailable."""
    thermal: Dict[str, Any] = {}
    try:
        thermal = json.loads((_STATE / "thermal_cortex_state.json").read_text(encoding="utf-8"))
        if not isinstance(thermal, dict):
            thermal = {}
    except Exception:
        thermal = {}
    metabolic: Dict[str, Any] = {}
    try:
        from System.swarm_metabolic_homeostasis import MetabolicHomeostat

        h = MetabolicHomeostat()
        metabolic = h.build_ledger_row(h.sample_live())
    except Exception as exc:
        metabolic = {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "thermal": thermal or {"source": "missing"},
        "metabolic": metabolic,
    }


def _swimmer_census_payload(swimmers: Sequence[Any], *, kind: str, receipt_id: str) -> Dict[str, Any]:
    """Return a cryptographic census for every swimmer born in the run."""
    rows: List[Dict[str, Any]] = []
    for sw in swimmers:
        row: Dict[str, Any] = {"swimmer_id": str(getattr(sw, "swimmer_id", ""))}
        if hasattr(sw, "gamma_hypothesis"):
            row["gamma_hypothesis"] = float(getattr(sw, "gamma_hypothesis"))
        if hasattr(sw, "phase_hypothesis_rad"):
            row["phase_hypothesis_rad"] = float(getattr(sw, "phase_hypothesis_rad"))
        if hasattr(sw, "exponent_hypothesis"):
            row["exponent_hypothesis"] = float(getattr(sw, "exponent_hypothesis"))
        if hasattr(sw, "scale_hypothesis"):
            row["scale_hypothesis"] = float(getattr(sw, "scale_hypothesis"))
        rows.append(row)
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "receipt_id": receipt_id,
        "kind": kind,
        "swimmer_count": len(rows),
        "swimmer_ids_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "unaccounted_swimmers": 0,
        "all_swimmers_accounted": True,
        "swimmers": rows,
    }


def _clamp01(value: float) -> float:
    return float(min(1.0, max(0.0, value)))


def _integral(y: np.ndarray, x: np.ndarray) -> float:
    """Numpy 1.x/2.x compatible trapezoid integral."""
    if hasattr(np, "trapezoid"):
        return float(np.trapezoid(y, x))
    return float(np.trapz(y, x))  # pragma: no cover - old numpy fallback


def detector_axis(n_points: int = 512, span: float = 0.020) -> np.ndarray:
    """Return detector coordinates in meters centered on the optical axis."""
    if n_points < 16:
        raise ValueError("n_points must be >= 16")
    return np.linspace(-float(span) / 2.0, float(span) / 2.0, int(n_points))


def _sinc_sq(beta: np.ndarray) -> np.ndarray:
    # numpy.sinc(y) = sin(pi*y)/(pi*y), so beta/pi is the right input.
    return np.sinc(beta / math.pi) ** 2


def double_slit_intensity(
    x_m: np.ndarray,
    *,
    gamma: float,
    slit_width_m: float = 80e-6,
    slit_separation_m: float = 300e-6,
    wavelength_m: float = 532e-9,
    screen_distance_m: float = 2.0,
    phase_rad: float = 0.0,
    normalize: bool = True,
) -> np.ndarray:
    """Fraunhofer equal-intensity double-slit pattern with visibility gamma."""
    if x_m.ndim != 1:
        raise ValueError("x_m must be a 1-D detector axis")
    if slit_width_m <= 0 or slit_separation_m <= 0 or wavelength_m <= 0 or screen_distance_m <= 0:
        raise ValueError("slit geometry and wavelength must be positive")

    gamma = _clamp01(float(gamma))
    beta = math.pi * slit_width_m * x_m / (wavelength_m * screen_distance_m)
    delta = 2.0 * math.pi * slit_separation_m * x_m / (wavelength_m * screen_distance_m)
    envelope = _sinc_sq(beta)
    intensity = envelope * (1.0 + gamma * np.cos(delta + float(phase_rad)))
    intensity = np.clip(intensity, 0.0, None).astype(np.float64)
    if normalize:
        area = _integral(intensity, x_m)
        if area > 0:
            intensity = intensity / area
    return intensity


def simulate_detector_pattern(
    *,
    gamma: float,
    n_points: int = 512,
    span_m: float = 0.020,
    slit_width_m: float = 80e-6,
    slit_separation_m: float = 300e-6,
    wavelength_m: float = 532e-9,
    screen_distance_m: float = 2.0,
    phase_rad: float = 0.0,
    noise_sigma: float = 0.0,
    seed: int = 0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Generate a detector strip and optional additive sensor noise."""
    x = detector_axis(n_points=n_points, span=span_m)
    intensity = double_slit_intensity(
        x,
        gamma=gamma,
        slit_width_m=slit_width_m,
        slit_separation_m=slit_separation_m,
        wavelength_m=wavelength_m,
        screen_distance_m=screen_distance_m,
        phase_rad=phase_rad,
    )
    if noise_sigma > 0:
        rng = np.random.default_rng(seed)
        intensity = np.clip(intensity + rng.normal(0.0, float(noise_sigma), size=intensity.shape), 0.0, None)
        area = _integral(intensity, x)
        if area > 0:
            intensity = intensity / area
    return x, intensity


def _normalize_for_score(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=np.float64).copy()
    y = np.clip(y, 0.0, None)
    y -= float(y.mean())
    norm = float(np.linalg.norm(y))
    if norm <= 1e-12:
        return np.zeros_like(y)
    return y / norm


def _pattern_score(observed: np.ndarray, predicted: np.ndarray) -> float:
    obs = _normalize_for_score(observed)
    pred = _normalize_for_score(predicted)
    mse = float(np.mean((obs - pred) ** 2))
    # Higher is better. A perfect match is 0.0.
    return -mse


@dataclass
class SlitCoherenceSwimmer:
    swimmer_id: str
    gamma_hypothesis: float
    phase_hypothesis_rad: float = 0.0
    pheromone: float = 0.0
    last_score: float = 0.0
    ticks: int = 0


@dataclass
class SlitCoherenceResult:
    receipt_id: str
    posterior_mean_gamma: float
    posterior_std_gamma: float
    posterior_map_gamma: float
    posterior_map_phase_rad: float
    planted_gamma: Optional[float]
    gamma_abs_error: Optional[float]
    fringe_visibility: float
    n_swimmers: int
    ticks: int
    swimmers: List[SlitCoherenceSwimmer]
    thermodynamic_clearance: Dict[str, Any]
    swimmer_census: Dict[str, Any]
    truth_label: str = _TRUTH_LABEL


def estimate_michelson_visibility(intensity: np.ndarray, *, trim_fraction: float = 0.08) -> float:
    """Robust Michelson visibility estimate from a detector strip.

    The trim avoids a single noisy pixel defining I_min/I_max.
    """
    y = np.asarray(intensity, dtype=np.float64)
    y = np.clip(y, 0.0, None)
    if y.size < 8:
        raise ValueError("intensity must contain at least 8 samples")
    lo_q = float(np.quantile(y, trim_fraction))
    hi_q = float(np.quantile(y, 1.0 - trim_fraction))
    denom = hi_q + lo_q
    if denom <= 1e-12:
        return 0.0
    return _clamp01((hi_q - lo_q) / denom)


def infer_coherence_posterior(
    x_m: np.ndarray,
    observed_intensity: np.ndarray,
    *,
    n_swimmers: int = 81,
    gamma_grid: Optional[Sequence[float]] = None,
    phase_grid_rad: Sequence[float] = (0.0,),
    ticks: int = 5,
    pheromone_evaporation: float = 0.25,
    slit_width_m: float = 80e-6,
    slit_separation_m: float = 300e-6,
    wavelength_m: float = 532e-9,
    screen_distance_m: float = 2.0,
    planted_gamma: Optional[float] = None,
    enforce_thermodynamics: bool = True,
    write_ledger: bool = True,
) -> SlitCoherenceResult:
    """Run the gamma posterior swarm against one observed detector pattern."""
    x = np.asarray(x_m, dtype=np.float64)
    observed = np.asarray(observed_intensity, dtype=np.float64)
    if x.ndim != 1 or observed.ndim != 1 or x.shape != observed.shape:
        raise ValueError("x_m and observed_intensity must be 1-D arrays of the same shape")
    if ticks < 1:
        raise ValueError("ticks must be >= 1")
    if not 0.0 <= pheromone_evaporation < 1.0:
        raise ValueError("pheromone_evaporation must be in [0, 1)")

    if gamma_grid is None:
        gamma_grid = np.linspace(0.0, 1.0, int(n_swimmers))
    else:
        gamma_grid = np.asarray(list(gamma_grid), dtype=np.float64)

    phase_values = list(float(p) for p in phase_grid_rad)
    if not phase_values:
        phase_values = [0.0]

    thermo_payload = {
        "n_detector_points": int(observed.size),
        "n_swimmers_requested": int(len(gamma_grid) * len(phase_values)),
        "phase_count": len(phase_values),
        "ticks": int(ticks),
        "write_ledger": bool(write_ledger),
    }
    thermodynamic_clearance = _processing_clearance(
        "slit_coherence_posterior",
        payload=thermo_payload,
        expected_value=0.82,
        write_ledger=write_ledger,
    )
    if enforce_thermodynamics and not bool(thermodynamic_clearance.get("allowed", True)):
        raise ThermodynamicClearanceDenied(thermodynamic_clearance)

    swimmers: List[SlitCoherenceSwimmer] = []
    for gamma in gamma_grid:
        for phase in phase_values:
            swimmers.append(
                SlitCoherenceSwimmer(
                    swimmer_id=f"slit-{uuid.uuid4().hex[:10]}",
                    gamma_hypothesis=_clamp01(float(gamma)),
                    phase_hypothesis_rad=float(phase),
                )
            )

    receipt_id = f"slit-coh-{uuid.uuid4().hex[:12]}"
    qm = _qualia_marker("slit.coherence.posterior", note=f"n_swimmers={len(swimmers)}")
    swimmer_census = _swimmer_census_payload(swimmers, kind="gamma_posterior", receipt_id=receipt_id)
    if write_ledger:
        _safe_append_jsonl(
            _CENSUS_LEDGER,
            {
                "ts": _now(),
                "truth_label": _TRUTH_LABEL,
                "thermodynamic_clearance_hash": thermodynamic_clearance.get("receipt_hash"),
                **swimmer_census,
            },
        )

    for tick in range(ticks):
        for sw in swimmers:
            sw.pheromone *= (1.0 - pheromone_evaporation)

        for sw in swimmers:
            predicted = double_slit_intensity(
                x,
                gamma=sw.gamma_hypothesis,
                slit_width_m=slit_width_m,
                slit_separation_m=slit_separation_m,
                wavelength_m=wavelength_m,
                screen_distance_m=screen_distance_m,
                phase_rad=sw.phase_hypothesis_rad,
            )
            sw.last_score = _pattern_score(observed, predicted)
            sw.ticks += 1

        scores = np.array([sw.last_score for sw in swimmers], dtype=np.float64)
        k = max(1, len(swimmers) // 6)
        top_idx = np.argsort(scores)[-k:]
        top_scores = scores[top_idx]
        s_min = float(top_scores.min())
        s_max = float(top_scores.max())
        if s_max > s_min:
            local_w = (top_scores - s_min) / (s_max - s_min + 1e-12)
            local_w = local_w + 0.05
            local_w = local_w / local_w.sum() * k
        else:
            local_w = np.ones(k, dtype=np.float64)

        for idx, w in zip(top_idx, local_w):
            sw = swimmers[int(idx)]
            sw.pheromone += float(w)
            if write_ledger:
                clearance = _request_clearance("slit.coherence.pheromone")
                clearance_hash = clearance.get("clearance_hash") if isinstance(clearance, dict) else None
                _safe_append_jsonl(
                    _PHEROMONE_LEDGER,
                    {
                        "ts": _now(),
                        "truth_label": _TRUTH_LABEL,
                        "tick": tick,
                        "swimmer_id": sw.swimmer_id,
                        "gamma_hypothesis": sw.gamma_hypothesis,
                        "phase_hypothesis_rad": sw.phase_hypothesis_rad,
                        "score": sw.last_score,
                        "pheromone": sw.pheromone,
                        "clearance_hash": clearance_hash,
                        "qualia_marker": qm,
                    },
                )

    weights = np.array([sw.pheromone for sw in swimmers], dtype=np.float64)
    if float(weights.sum()) <= 0.0:
        weights = np.ones_like(weights)
    weights = weights / weights.sum()
    gammas = np.array([sw.gamma_hypothesis for sw in swimmers], dtype=np.float64)
    mean_gamma = float((weights * gammas).sum())
    var_gamma = float((weights * (gammas - mean_gamma) ** 2).sum())
    std_gamma = math.sqrt(max(var_gamma, 0.0))
    map_idx = int(np.argmax(weights))
    map_gamma = float(gammas[map_idx])
    map_phase = float(swimmers[map_idx].phase_hypothesis_rad)
    gamma_error = None if planted_gamma is None else abs(mean_gamma - float(planted_gamma))
    visibility = estimate_michelson_visibility(observed)

    if write_ledger:
        clearance = _request_clearance("slit.coherence.posterior")
        clearance_hash = clearance.get("clearance_hash") if isinstance(clearance, dict) else None
        _safe_append_jsonl(
            _RECEIPTS_LEDGER,
            {
                "ts": _now(),
                "receipt_id": receipt_id,
                "truth_label": _TRUTH_LABEL,
                "n_swimmers": len(swimmers),
                "ticks": ticks,
                "posterior_mean_gamma": mean_gamma,
                "posterior_std_gamma": std_gamma,
                "posterior_map_gamma": map_gamma,
                "posterior_map_phase_rad": map_phase,
                "fringe_visibility": visibility,
                "planted_gamma": planted_gamma,
                "gamma_abs_error": gamma_error,
                "equal_intensity_boundary": "Michelson V = |gamma12| = gamma for equal slit intensities",
                "thermodynamic_clearance": thermodynamic_clearance,
                "body_thermodynamics": thermodynamic_clearance.get("body") or _body_thermodynamic_snapshot(),
                "swimmer_census": {
                    k: v for k, v in swimmer_census.items() if k != "swimmers"
                },
                "clearance_hash": clearance_hash,
                "qualia_marker": qm,
            },
        )

    return SlitCoherenceResult(
        receipt_id=receipt_id,
        posterior_mean_gamma=mean_gamma,
        posterior_std_gamma=std_gamma,
        posterior_map_gamma=map_gamma,
        posterior_map_phase_rad=map_phase,
        planted_gamma=planted_gamma,
        gamma_abs_error=gamma_error,
        fringe_visibility=visibility,
        n_swimmers=len(swimmers),
        ticks=ticks,
        swimmers=swimmers,
        thermodynamic_clearance=thermodynamic_clearance,
        swimmer_census=swimmer_census,
    )


@dataclass(frozen=True)
class CoherenceCase:
    p_survive: float
    x_m: np.ndarray
    observed_intensity: np.ndarray
    label: str = ""


@dataclass
class RuleDiscoverySwimmer:
    swimmer_id: str
    exponent_hypothesis: float
    scale_hypothesis: float = 1.0
    pheromone: float = 0.0
    last_score: float = 0.0


@dataclass
class SurvivalVisibilityRuleResult:
    receipt_id: str
    posterior_mean_exponent: float
    posterior_std_exponent: float
    posterior_mean_scale: float
    posterior_map_exponent: float
    posterior_map_scale: float
    case_count: int
    swimmers: List[RuleDiscoverySwimmer]
    thermodynamic_clearance: Dict[str, Any]
    swimmer_census: Dict[str, Any]
    truth_label: str = _TRUTH_LABEL


def discover_survival_visibility_rule(
    cases: Sequence[CoherenceCase],
    *,
    exponent_grid: Sequence[float] = tuple(np.linspace(0.35, 2.25, 77)),
    scale_grid: Sequence[float] = (0.9, 1.0, 1.1),
    ticks: int = 6,
    pheromone_evaporation: float = 0.25,
    slit_width_m: float = 80e-6,
    slit_separation_m: float = 300e-6,
    wavelength_m: float = 532e-9,
    screen_distance_m: float = 2.0,
    enforce_thermodynamics: bool = True,
    write_ledger: bool = True,
) -> SurvivalVisibilityRuleResult:
    """Discover a survival-to-visibility rule from receipted cases.

    Each case should carry a known local survival estimate ``p_survive`` and
    an observed detector strip. The discovery swarm tests candidate
    ``V = scale * p_survive ** exponent`` laws across all cases.
    """
    if len(cases) < 2:
        raise ValueError("at least two cases are needed for rule discovery")
    if ticks < 1:
        raise ValueError("ticks must be >= 1")
    exponent_values = tuple(float(x) for x in exponent_grid)
    scale_values = tuple(float(x) for x in scale_grid)

    thermodynamic_clearance = _processing_clearance(
        "slit_coherence_rule_discovery",
        payload={
            "case_count": len(cases),
            "exponent_count": len(exponent_values),
            "scale_count": len(scale_values),
            "ticks": int(ticks),
        },
        expected_value=0.74,
        write_ledger=write_ledger,
    )
    if enforce_thermodynamics and not bool(thermodynamic_clearance.get("allowed", True)):
        raise ThermodynamicClearanceDenied(thermodynamic_clearance)

    swimmers = [
        RuleDiscoverySwimmer(
            swimmer_id=f"rule-{uuid.uuid4().hex[:10]}",
            exponent_hypothesis=float(exp),
            scale_hypothesis=float(scale),
        )
        for exp in exponent_values
        for scale in scale_values
    ]
    receipt_id = f"slit-rule-{uuid.uuid4().hex[:12]}"
    qm = _qualia_marker("slit.coherence.discovery", note=f"cases={len(cases)}")
    swimmer_census = _swimmer_census_payload(swimmers, kind="rule_discovery", receipt_id=receipt_id)
    if write_ledger:
        _safe_append_jsonl(
            _CENSUS_LEDGER,
            {
                "ts": _now(),
                "truth_label": _TRUTH_LABEL,
                "thermodynamic_clearance_hash": thermodynamic_clearance.get("receipt_hash"),
                **swimmer_census,
            },
        )

    for _tick in range(ticks):
        for sw in swimmers:
            sw.pheromone *= (1.0 - pheromone_evaporation)

        for sw in swimmers:
            errors: List[float] = []
            for case in cases:
                p = _clamp01(float(case.p_survive))
                gamma = _clamp01(sw.scale_hypothesis * (p ** sw.exponent_hypothesis))
                predicted = double_slit_intensity(
                    case.x_m,
                    gamma=gamma,
                    slit_width_m=slit_width_m,
                    slit_separation_m=slit_separation_m,
                    wavelength_m=wavelength_m,
                    screen_distance_m=screen_distance_m,
                )
                errors.append(-_pattern_score(case.observed_intensity, predicted))
            sw.last_score = -float(np.mean(errors))

        scores = np.array([sw.last_score for sw in swimmers], dtype=np.float64)
        k = max(1, len(swimmers) // 7)
        top_idx = np.argsort(scores)[-k:]
        top_scores = scores[top_idx]
        s_min = float(top_scores.min())
        s_max = float(top_scores.max())
        if s_max > s_min:
            local_w = (top_scores - s_min) / (s_max - s_min + 1e-12)
            local_w = local_w + 0.05
            local_w = local_w / local_w.sum() * k
        else:
            local_w = np.ones(k, dtype=np.float64)
        for idx, w in zip(top_idx, local_w):
            swimmers[int(idx)].pheromone += float(w)

    weights = np.array([sw.pheromone for sw in swimmers], dtype=np.float64)
    if float(weights.sum()) <= 0.0:
        weights = np.ones_like(weights)
    weights = weights / weights.sum()
    exps = np.array([sw.exponent_hypothesis for sw in swimmers], dtype=np.float64)
    scales = np.array([sw.scale_hypothesis for sw in swimmers], dtype=np.float64)
    mean_exp = float((weights * exps).sum())
    var_exp = float((weights * (exps - mean_exp) ** 2).sum())
    mean_scale = float((weights * scales).sum())
    map_idx = int(np.argmax(weights))

    if write_ledger:
        clearance = _request_clearance("slit.coherence.discovery")
        clearance_hash = clearance.get("clearance_hash") if isinstance(clearance, dict) else None
        _safe_append_jsonl(
            _DISCOVERY_LEDGER,
            {
                "ts": _now(),
                "receipt_id": receipt_id,
                "truth_label": _TRUTH_LABEL,
                "case_count": len(cases),
                "ticks": ticks,
                "posterior_mean_exponent": mean_exp,
                "posterior_std_exponent": math.sqrt(max(var_exp, 0.0)),
                "posterior_mean_scale": mean_scale,
                "posterior_map_exponent": swimmers[map_idx].exponent_hypothesis,
                "posterior_map_scale": swimmers[map_idx].scale_hypothesis,
                "rule_family": "V = scale * p_survive ** exponent",
                "thermodynamic_clearance": thermodynamic_clearance,
                "body_thermodynamics": thermodynamic_clearance.get("body") or _body_thermodynamic_snapshot(),
                "swimmer_census": {
                    k: v for k, v in swimmer_census.items() if k != "swimmers"
                },
                "clearance_hash": clearance_hash,
                "qualia_marker": qm,
            },
        )

    return SurvivalVisibilityRuleResult(
        receipt_id=receipt_id,
        posterior_mean_exponent=mean_exp,
        posterior_std_exponent=math.sqrt(max(var_exp, 0.0)),
        posterior_mean_scale=mean_scale,
        posterior_map_exponent=swimmers[map_idx].exponent_hypothesis,
        posterior_map_scale=swimmers[map_idx].scale_hypothesis,
        case_count=len(cases),
        swimmers=swimmers,
        thermodynamic_clearance=thermodynamic_clearance,
        swimmer_census=swimmer_census,
    )


if __name__ == "__main__":
    print(f"[{_TRUTH_LABEL}] smoke: infer gamma from synthetic double-slit")
    x_axis, observed = simulate_detector_pattern(gamma=0.72, noise_sigma=0.002, seed=7)
    result = infer_coherence_posterior(
        x_axis,
        observed,
        planted_gamma=0.72,
        write_ledger=False,
    )
    print(
        f"  planted_gamma=0.72 recovered={result.posterior_mean_gamma:.3f} "
        f"± {result.posterior_std_gamma:.3f} map={result.posterior_map_gamma:.3f}"
    )

    cases = []
    for i, p in enumerate((0.20, 0.40, 0.65, 0.90)):
        x, y = simulate_detector_pattern(gamma=p, noise_sigma=0.001, seed=100 + i)
        cases.append(CoherenceCase(p_survive=p, x_m=x, observed_intensity=y, label=f"p={p:.2f}"))
    rule = discover_survival_visibility_rule(cases, write_ledger=False)
    print(
        f"  discovered V≈scale*p^exponent: scale={rule.posterior_mean_scale:.3f} "
        f"exponent={rule.posterior_mean_exponent:.3f} ± {rule.posterior_std_exponent:.3f}"
    )
