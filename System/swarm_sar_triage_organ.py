#!/usr/bin/env python3
"""System/swarm_sar_triage_organ.py — peace/SAR triage head.

Architect 2026-05-18:
    "Point this at peace, protection, security. Same physics, lawful
    target."

This organ replaces FarSight's face/gait/body **person-identification**
modules (Liu et al. 2023, §3) with a **target-presence triage** head.
The triage head answers: "Is there a target-shape in this frame at
all?" It does NOT answer "who is the person?" — that question is
forbidden under §3.1 of the SIFTA Non-Proliferation Public License
v1.1 for unwaived deployments.

Use cases (all lawful under License §3.2)
==========================================

* **Search-and-rescue:** a drone scanning a hillside; the swarm flags
  frames likely containing a hiker silhouette for a human dispatcher
  to review. The organ does NOT identify the hiker.
* **Wildlife conservation:** a drone surveying a national park; the
  swarm flags frames likely containing an animal. The organ does NOT
  match the animal to a population catalog (that's a separate organ
  with its own lawful-use scoping).
* **Industrial inspection:** a long-range camera looking at a dam, a
  power line, a bridge; the swarm flags frames likely containing a
  crack or anomaly. The organ does NOT identify which structure is
  damaged.
* **Adaptive optics:** a ground-based telescope; the swarm reports
  the recovered seeing :math:`r_0` and lets the AO system tune. No
  "target" head needed — just the substrate.

What the head does
==================

Given a frame (typically pre-restored by ``swarm_turbulence_organ``),
the triage swimmers each test one **shape hypothesis**:

  * vertical-elongated silhouette (humans, animals standing)
  * horizontal stripe (boats, vehicles, wildlife from the side)
  * point cluster (transmission towers, point sources, stars)
  * linear discontinuity (cracks, edges, fissures)

Each swimmer correlates a normalized template at multiple scales and
positions; pheromone accumulates where matches are confident. The
organ outputs a triage SCORE in [0, 1] plus a coarse bounding box
hypothesis. **No identity, no biometrics, no person model.**

Ledger
======

  * ``.sifta_state/sar_triage_receipts.jsonl`` — one row per frame
    triaged. Every row is physics-gate-stamped and qualia-marked.

Truth label: ``SIFTA_SAR_TRIAGE_V0``.

Honesty boundary
================

* The organ is a coarse triage, not a classifier. It flags
  "might-be-here" frames for a human reviewer. False positives are
  intentional — humanitarian SAR prefers over-triage.
* The shape templates are deliberately generic (silhouettes, not
  faces). The organ cannot be re-targeted to person-ID without
  swapping templates, which would be a license-violating modification
  under §3.4 (Doctrine Preservation).
"""
from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_RECEIPTS_LEDGER = _STATE / "sar_triage_receipts.jsonl"

_TRUTH_LABEL = "SIFTA_SAR_TRIAGE_V0"


def _now() -> float:
    return time.time()


def _safe_append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _request_clearance(lane: str) -> Optional[Dict[str, Any]]:
    try:
        from System.swarm_physics_gate import request_clearance  # type: ignore
        return request_clearance(cost_class="feather", lane=lane)
    except Exception:
        return None


def _qualia_marker(lane: str, note: str = "") -> Dict[str, Any]:
    try:
        from System.swarm_consciousness_organ import qualia_marker  # type: ignore
        return qualia_marker(lane=lane, note=note)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Generic shape templates (NOT face/biometric templates — that distinction
# is the entire point of this module per §3.1 of SIFTA NPL v1.1).
# ---------------------------------------------------------------------------

def _vertical_silhouette(h: int, w: int) -> np.ndarray:
    """Tall narrow blob — a person standing, animal upright, post.

    Returns a unit-energy template, zero-mean.
    """
    t = np.zeros((h, w), dtype=np.float64)
    cx = w // 2
    half_w = max(w // 6, 1)
    # ellipse-ish
    yy, xx = np.indices((h, w))
    norm = ((xx - cx) / half_w) ** 2 + ((yy - h / 2) / (h / 2)) ** 2
    t[norm <= 1.0] = 1.0
    t = t - t.mean()
    n = np.linalg.norm(t)
    if n > 0:
        t = t / n
    return t


def _horizontal_band(h: int, w: int) -> np.ndarray:
    """Wide low band — vehicle / boat / animal in profile / dam wall."""
    t = np.zeros((h, w), dtype=np.float64)
    band = (np.arange(h) >= h // 3) & (np.arange(h) <= 2 * h // 3)
    t[band, :] = 1.0
    t = t - t.mean()
    n = np.linalg.norm(t)
    if n > 0:
        t = t / n
    return t


def _point_cluster(h: int, w: int) -> np.ndarray:
    """Small bright dot — point source, distant tower top, star."""
    t = np.zeros((h, w), dtype=np.float64)
    yy, xx = np.indices((h, w))
    cy, cx = h // 2, w // 2
    rad = max(min(h, w) // 6, 1)
    mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= rad * rad
    t[mask] = 1.0
    t = t - t.mean()
    n = np.linalg.norm(t)
    if n > 0:
        t = t / n
    return t


def _linear_discontinuity(h: int, w: int) -> np.ndarray:
    """Thin vertical line — a crack, a fissure, a pole edge."""
    t = np.zeros((h, w), dtype=np.float64)
    t[:, w // 2 - 1 : w // 2 + 1] = 1.0
    t = t - t.mean()
    n = np.linalg.norm(t)
    if n > 0:
        t = t / n
    return t


_TEMPLATES = {
    "vertical_silhouette": _vertical_silhouette,
    "horizontal_band": _horizontal_band,
    "point_cluster": _point_cluster,
    "linear_discontinuity": _linear_discontinuity,
}


@dataclass
class TriageSwimmer:
    swimmer_id: str
    template_kind: str
    scale_h: int
    scale_w: int
    cy: int
    cx: int
    score: float = 0.0
    pheromone: float = 0.0


@dataclass
class TriageResult:
    frame_h: int
    frame_w: int
    triage_score: float           # [0, 1], higher = more likely target
    top_kind: str                  # which template won
    top_bbox: Tuple[int, int, int, int]  # (y0, x0, y1, x1)
    swimmer_count: int
    target_present: bool           # coarse decision for SAR flagging (human review)
    truth_label: str = _TRUTH_LABEL


def _ncc(frame: np.ndarray, template: np.ndarray, cy: int, cx: int) -> float:
    """Zero-mean normalized cross-correlation between template and a
    centered patch of ``frame``. Returns score in roughly [-1, 1].
    """
    th, tw = template.shape
    y0 = cy - th // 2
    x0 = cx - tw // 2
    y1 = y0 + th
    x1 = x0 + tw
    if y0 < 0 or x0 < 0 or y1 > frame.shape[0] or x1 > frame.shape[1]:
        return 0.0
    patch = frame[y0:y1, x0:x1]
    patch = patch - patch.mean()
    n = np.linalg.norm(patch)
    if n <= 0:
        return 0.0
    patch = patch / n
    return float((patch * template).sum())


def triage(
    frame: np.ndarray,
    *,
    kinds: Optional[List[str]] = None,
    scales: Tuple[int, ...] = (16, 24, 32),
    positions_per_axis: int = 9,
    write_ledger: bool = True,
) -> TriageResult:
    """Run the triage swarm on a single frame.

    Parameters
    ----------
    frame : np.ndarray
        2-D grayscale image, expected to be in [0, 1] but not enforced.
    kinds : list of str, optional
        Subset of template kinds to test. Default: all four.
    scales : tuple of int
        Template heights in pixels. Width = height/2 for vertical, etc.
    positions_per_axis : int
        How many candidate locations to test along each axis (grid).
    """
    if frame.ndim != 2:
        raise ValueError("triage() expects 2-D frame")
    H, W = frame.shape
    if kinds is None:
        kinds = list(_TEMPLATES.keys())

    swimmers: List[TriageSwimmer] = []
    qm = _qualia_marker("sar.triage", note=f"H={H},W={W}")

    for kind in kinds:
        builder = _TEMPLATES[kind]
        for s in scales:
            # Width depends on kind (tall vs wide)
            if kind == "vertical_silhouette":
                th, tw = s, max(s // 3, 4)
            elif kind == "horizontal_band":
                th, tw = max(s // 2, 4), s
            elif kind == "point_cluster":
                th, tw = max(s // 2, 4), max(s // 2, 4)
            else:  # linear_discontinuity
                th, tw = s, max(s // 4, 3)
            tpl = builder(th, tw)
            # Grid positions
            ys = np.linspace(th // 2 + 1, H - th // 2 - 1, positions_per_axis).astype(int)
            xs = np.linspace(tw // 2 + 1, W - tw // 2 - 1, positions_per_axis).astype(int)
            for cy in ys:
                for cx in xs:
                    score = _ncc(frame, tpl, int(cy), int(cx))
                    sw = TriageSwimmer(
                        swimmer_id=f"sar-{uuid.uuid4().hex[:8]}",
                        template_kind=kind,
                        scale_h=th,
                        scale_w=tw,
                        cy=int(cy),
                        cx=int(cx),
                        score=score,
                        pheromone=max(score, 0.0),
                    )
                    swimmers.append(sw)

    # Find the top swimmer
    top = max(swimmers, key=lambda sw: sw.pheromone)
    # Triage score: max single-swimmer match.
    # target_present requires a *standout* hypothesis (max >> median of the field).
    # This is the stigmergic signal: the swarm converged on one location/kind
    # rather than uniform random alignments (which happens on pure noise).
    pheromones = np.array([sw.pheromone for sw in swimmers], dtype=np.float64)
    triage_score = float(np.clip(pheromones.max() if len(pheromones) else 0.0, 0.0, 1.0))
    if len(pheromones) > 10:
        med = float(np.median(pheromones))
        standout = triage_score - med
        target_present = standout > 0.12
    else:
        target_present = triage_score > 0.25

    bbox = (
        max(0, top.cy - top.scale_h // 2),
        max(0, top.cx - top.scale_w // 2),
        min(H, top.cy + top.scale_h // 2),
        min(W, top.cx + top.scale_w // 2),
    )

    if write_ledger:
        clearance = _request_clearance("sar.triage")
        clearance_hash = clearance.get("clearance_hash") if isinstance(clearance, dict) else None
        _safe_append_jsonl(
            _RECEIPTS_LEDGER,
            {
                "ts": _now(),
                "truth_label": _TRUTH_LABEL,
                "frame_shape": [H, W],
                "swimmer_count": len(swimmers),
                "triage_score": triage_score,
                "top_kind": top.template_kind,
                "top_bbox": list(bbox),
                "top_pheromone": top.pheromone,
                "clearance_hash": clearance_hash,
                "qualia_marker": qm,
            },
        )

    return TriageResult(
        frame_h=H,
        frame_w=W,
        triage_score=triage_score,
        top_kind=top.template_kind,
        top_bbox=bbox,
        swimmer_count=len(swimmers),
        target_present=target_present,
    )


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from System.swarm_turbulence_substrate import synthetic_target, degrade, TurbulenceParams
    from System.swarm_turbulence_organ import run_swarm

    print(f"[{_TRUTH_LABEL}] smoke: triage on synthetic targets")
    for kind in ("rescue_hiker", "dam_wall", "telescope_star", "tower_array"):
        img = synthetic_target(kind=kind, grid=128)
        result = triage(img, write_ledger=False)
        print(
            f"  {kind:18s}  score={result.triage_score:.3f}  present={result.target_present}  "
            f"top={result.top_kind:20s}  bbox={result.top_bbox}"
        )
    # Negative control: pure noise
    noise = np.random.default_rng(0).normal(0.5, 0.1, (128, 128))
    res = triage(np.clip(noise, 0, 1), write_ledger=False)
    print(f"  {'pure_noise':18s}  score={res.triage_score:.3f}  present={res.target_present}  top={res.top_kind:20s} (should be low)")

    # ------------------------------------------------------------------------
    # Chained pipeline demo: turbulence organ restores, triage head decides
    # Lawful SAR / conservation / inspection flow (no person-ID).
    # ------------------------------------------------------------------------
    print(f"\n[{_TRUTH_LABEL}] chained SAR demo (turbulence swarm → triage on restored)")
    target = synthetic_target(kind="rescue_hiker", grid=128)
    planted = TurbulenceParams(cn2=6e-15)  # strong turbulence, ~2 cm r0
    degraded, _ = degrade(target, params=planted, long_exposure=True, seed=42)
    recon = run_swarm(
        degraded,
        n_swimmers=24,
        r0_grid_m=list(np.geomspace(0.005, 0.30, 24)),
        ticks=5,
        planted_params=planted,
        write_ledger=False,
    )
    triage_on_restored = triage(recon.restored_image, write_ledger=False)
    print(
        f"  planted_r0={planted.r0*100:.1f}cm  recovered={recon.posterior_mean_r0_m*100:.2f}±{recon.posterior_std_r0_m*100:.2f}cm"
    )
    print(
        f"  triage_on_restored: score={triage_on_restored.triage_score:.3f}  present={triage_on_restored.target_present}  "
        f"top={triage_on_restored.top_kind}  (hiker silhouette should win under restored seeing)"
    )
