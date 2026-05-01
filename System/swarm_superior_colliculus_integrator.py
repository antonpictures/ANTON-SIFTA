#!/usr/bin/env python3
"""Event 98 — Superior colliculus multisensory → body-brain bridge.

Reads tails of ``visual_phenotype_uniforms.jsonl``, ``stigmergic_cochlea.jsonl``,
and optionally ``owl_spatial_hearing.jsonl``, then fuses scalars using
Meredith/Stein-style **spatial coincidence**, **temporal coincidence**, and
**inverse effectiveness** (weak+weak → larger multiplicative gain than
strong+strong).

Truth label on appended rows: ``MULTISENSORY_COLLICULUS_MERGE`` — engineering
receipt for ledger coupling, not a claim of midbrain recording.

Does **not** auto-hook ``SwarmPhysiology.body_brain_tick``; callers merge when
they want an explicit multisensory overlay on an existing tick receipt.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from System.jsonl_file_lock import append_line_locked
from System.swarm_stigmergic_cochlea_integrator import (
    body_brain_memory_path,
    read_latest_cochlea_features,
    validate_body_brain_tick,
)

_REPO = Path(__file__).resolve().parent.parent

TRUTH_MULTISENSORY = "MULTISENSORY_COLLICULUS_MERGE"
# Meredith/Stein temporal: broader window in seconds (video frame / cochlea window scale)
TEMPORAL_TAU_SEC = 0.25
# Spatial: radians mismatch decay (Wallace/Stein SC metaphors)
SPATIAL_DECAY_PER_RAD = 2.0
TD_SALIENCE_WEIGHT = 0.45


def _state_root() -> Path:
    try:
        import System.swarm_body_brain_loop as _bbl

        root = getattr(_bbl, "_STATE_DIR", None)
        if root is not None:
            return Path(root).resolve()
    except Exception:
        pass
    return (_REPO / ".sifta_state").resolve()


def phenotype_ledger_path(state_root: Optional[Path] = None) -> Path:
    return (state_root or _state_root()) / "visual_phenotype_uniforms.jsonl"


def owl_ledger_path(state_root: Optional[Path] = None) -> Path:
    return (state_root or _state_root()) / "owl_spatial_hearing.jsonl"


def _read_latest_jsonl_object(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in reversed([ln.strip() for ln in raw.splitlines() if ln.strip()]):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def read_latest_visual_uniforms(
    *,
    phenotype_path: Optional[Path] = None,
    state_root: Optional[Path] = None,
) -> Dict[str, Any]:
    path = phenotype_path or phenotype_ledger_path(state_root)
    row = _read_latest_jsonl_object(path)
    if not row:
        return {
            "u_stigmergic_drive": 0.2,
            "u_metabolic_scope": 0.5,
            "u_heading": 0.0,
            "ts": None,
            "visual_receipt_backed": False,
        }
    try:
        drive = float(row.get("u_stigmergic_drive", 0.2))
    except (TypeError, ValueError):
        drive = 0.2
    try:
        scope = float(row.get("u_metabolic_scope", 0.5))
    except (TypeError, ValueError):
        scope = 0.5
    try:
        heading = float(row.get("u_heading", 0.0))
    except (TypeError, ValueError):
        heading = 0.0
    ts = row.get("ts")
    try:
        ts_f = float(ts) if ts is not None else None
    except (TypeError, ValueError):
        ts_f = None
    return {
        "u_stigmergic_drive": max(0.0, min(1.0, drive)),
        "u_metabolic_scope": max(0.0, min(1.0, scope)),
        "u_heading": heading,
        "ts": ts_f,
        "visual_receipt_backed": True,
    }


def read_latest_owl_azimuth(
    *,
    owl_path: Optional[Path] = None,
    state_root: Optional[Path] = None,
) -> Tuple[float, Optional[float]]:
    """Return (azimuth_rad, timestamp) from last owl ledger row."""
    path = owl_path or owl_ledger_path(state_root)
    row = _read_latest_jsonl_object(path)
    if not row:
        return 0.0, None
    try:
        az = float(row.get("azimuth_rad", 0.0))
    except (TypeError, ValueError):
        az = 0.0
    if not math.isfinite(az):
        az = 0.0
    ts = row.get("timestamp", row.get("ts"))
    try:
        ts_f = float(ts) if ts is not None else None
    except (TypeError, ValueError):
        ts_f = None
    return az, ts_f


def _wrap_pi(delta: float) -> float:
    d = (delta + math.pi) % (2.0 * math.pi) - math.pi
    return abs(d)


def spatial_alignment(owl_azimuth_rad: float, visual_heading_rad: float) -> float:
    """Meredith/Stein spatial coincidence proxy in radians."""
    diff = _wrap_pi(owl_azimuth_rad - visual_heading_rad)
    return math.exp(-diff * SPATIAL_DECAY_PER_RAD)


def temporal_alignment(
    visual_ts: Optional[float],
    audio_ts: Optional[float],
    *,
    tau_sec: float = TEMPORAL_TAU_SEC,
) -> float:
    """Temporal coincidence: exponential decay vs |Δt| (Meredith/Stein temporal rule)."""
    if visual_ts is None or audio_ts is None:
        return 0.88
    dt = abs(float(visual_ts) - float(audio_ts))
    if not math.isfinite(dt):
        return 0.88
    return math.exp(-dt / max(tau_sec, 1e-6))


def inverse_effectiveness_boost(combined_raw: float) -> float:
    """Steep boost when bimodal evidence is weak (Meredith/Stein inverse effectiveness)."""
    if combined_raw >= 0.62 or not math.isfinite(combined_raw):
        return 1.0
    return min(8.0, 1.0 / (combined_raw + 0.05))


def compute_integrated_salience(
    visual: Dict[str, Any],
    audio_feats: Dict[str, Any],
    owl_azimuth_rad: float,
    *,
    owl_ts: Optional[float] = None,
) -> Dict[str, Any]:
    """Fuse phenotype + cochlea (+ owl azimuth). Returns metrics + ``integrated_salience`` in [0, 1]."""
    v_drive = max(0.0, min(1.0, float(visual.get("u_stigmergic_drive", 0.2))))
    v_scope = max(0.0, min(1.0, float(visual.get("u_metabolic_scope", 0.5))))
    v_heading = float(visual.get("u_heading", 0.0))
    v_ts = visual.get("ts")

    a_stress = max(0.0, min(1.0, float(audio_feats.get("acoustic_stress", 0.1))))
    a_danger = max(0.0, min(1.0, float(audio_feats.get("acoustic_danger_proxy", 0.0))))

    spatial = spatial_alignment(owl_azimuth_rad, v_heading)
    audio_ts = audio_feats.get("cochlea_ts")
    try:
        audio_ts_f = float(audio_ts) if audio_ts is not None else None
    except (TypeError, ValueError):
        audio_ts_f = None
    try:
        visual_ts_f = float(v_ts) if v_ts is not None else None
    except (TypeError, ValueError):
        visual_ts_f = None
    temporal_vis_audio = temporal_alignment(visual_ts_f, audio_ts_f)
    temporal = temporal_vis_audio
    if owl_ts is not None and audio_ts_f is not None:
        temporal = min(temporal, temporal_alignment(owl_ts, audio_ts_f))

    combined_raw = (v_drive + a_stress) / 2.0
    inv = inverse_effectiveness_boost(combined_raw)
    # Core bimodal drive: sum term + product term (superadditive scaffold)
    core = (v_drive + a_stress) * 0.5 + v_drive * a_stress
    core = (core + 0.25 * a_danger) * (0.55 + 0.45 * v_scope)
    # When both modalities are weak, inflate gain slightly (inverse effectiveness regime)
    saturation = 1.65 if combined_raw < 0.25 else 1.0
    raw = core * spatial * temporal * inv * saturation
    salience = max(0.0, min(1.0, raw))

    return {
        "integrated_salience": round(float(salience), 6),
        "spatial_alignment": round(float(spatial), 6),
        "temporal_alignment": round(float(temporal), 6),
        "inverse_effectiveness": round(float(inv), 6),
        "bimodal_core": round(float(core), 6),
        "combined_raw": round(float(combined_raw), 6),
    }


def integrate_to_body_brain(
    mem_row: Dict[str, Any],
    *,
    phenotype_path: Optional[Path] = None,
    cochlea_ledger: Optional[Path] = None,
    owl_path: Optional[Path] = None,
    state_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Apply collicular salience as ``td_value`` boost on a validated body-brain tick."""
    validate_body_brain_tick(mem_row)
    visual = read_latest_visual_uniforms(phenotype_path=phenotype_path, state_root=state_root)
    audio = read_latest_cochlea_features(cochlea_ledger=cochlea_ledger, state_root=state_root)
    owl_az, owl_ts = read_latest_owl_azimuth(owl_path=owl_path, state_root=state_root)
    metrics = compute_integrated_salience(visual, audio, owl_az, owl_ts=owl_ts)

    updated = dict(mem_row)
    current_td = float(updated.get("td_value", 0.0))
    if not math.isfinite(current_td):
        current_td = 0.0
    boost = metrics["integrated_salience"] * TD_SALIENCE_WEIGHT
    updated["td_value"] = round(current_td + boost, 6)
    updated["collicular_salience"] = metrics["integrated_salience"]
    updated["colliculus_spatial_alignment"] = metrics["spatial_alignment"]
    updated["colliculus_temporal_alignment"] = metrics["temporal_alignment"]
    updated["colliculus_inverse_effectiveness"] = metrics["inverse_effectiveness"]
    updated["multisensory_integrated"] = True
    updated["tick_source"] = "superior_colliculus_integrator"
    updated["truth_label"] = TRUTH_MULTISENSORY
    updated["colliculus_overlay_ts"] = time.time()
    return updated


def append_integrated_tick(
    updated_row: Dict[str, Any],
    *,
    memory_path: Optional[Path] = None,
    state_root: Optional[Path] = None,
) -> None:
    path = memory_path or body_brain_memory_path(state_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(path, json.dumps(updated_row, ensure_ascii=False) + "\n")


class SuperiorColliculusIntegrator:
    read_latest_visual_uniforms = staticmethod(read_latest_visual_uniforms)
    read_latest_owl_azimuth = staticmethod(read_latest_owl_azimuth)
    compute_integrated_salience = staticmethod(compute_integrated_salience)
    integrate_to_body_brain = staticmethod(integrate_to_body_brain)
    append_integrated_tick = staticmethod(append_integrated_tick)
    spatial_alignment = staticmethod(spatial_alignment)
    temporal_alignment = staticmethod(temporal_alignment)
    inverse_effectiveness_boost = staticmethod(inverse_effectiveness_boost)


__all__ = [
    "SPATIAL_DECAY_PER_RAD",
    "TEMPORAL_TAU_SEC",
    "TD_SALIENCE_WEIGHT",
    "TRUTH_MULTISENSORY",
    "SuperiorColliculusIntegrator",
    "append_integrated_tick",
    "compute_integrated_salience",
    "integrate_to_body_brain",
    "inverse_effectiveness_boost",
    "owl_ledger_path",
    "phenotype_ledger_path",
    "read_latest_owl_azimuth",
    "read_latest_visual_uniforms",
    "spatial_alignment",
    "temporal_alignment",
]
