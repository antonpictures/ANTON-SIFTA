#!/usr/bin/env python3
"""
swarm_cell_morphology_organ.py — Epigenetic Rejuvenation Observatory (observation side).

SIFTA doctrine: cells under a microscope -> camera -> computer vision ->
time-series morphology -> quantified cellular-state trajectory -> stigmergic
hash-chained ledger. Alice watches cells change over time and builds a
receipted record of their phenotypic state.

SAFETY SCOPE (hard boundary): this organ is the OBSERVATION / AUTOMATION arm
only. It ingests images, describes them, and tracks morphology over time.
It does NOT manufacture viral vectors, does NOT run recombinant nucleic-acid
work, and does NOT self-experiment. Those steps require institutional
biosafety oversight, training and containment — they are out of scope here.

Truth label: CELL_MORPHOLOGY_ORGAN_V1
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.swarm_world_awareness import append_trace, read_traces

try:
    from System.swarm_ollama_vision_arm import describe_image_local
    _VISION_AVAILABLE = True
except Exception:
    _VISION_AVAILABLE = False

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except Exception:
    _PIL_AVAILABLE = False

TRUTH_LABEL = "CELL_MORPHOLOGY_ORGAN_V1"
SOURCE = "cell_morphology"
_STATE = Path(__file__).resolve().parents[1] / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

DEFAULT_PROMPT = (
    "Describe this microscopy image as a single observation line: "
    "cell type, confluency, morphology (round/spindle/flat), any stress "
    "markers (blebbing, vacuoles, debris), and a one-phrase phenotypic state."
)

# Discrete state labels for the trajectory axis
PHENOTYPE_LABELS = (
    "healthy",
    "stressed",
    "confluent",
    "blebbing",
    "vacuolated",
    "debris_heavy",
    "detached",
    "mitotic",
)


def classify_phenotype(text: str, metrics: Dict[str, Any]) -> str:
    """
    Classify the cellular phenotype from vision text + metrics into a
    discrete label for the trajectory axis.
    """
    t = (text or "").lower()
    # Vision-driven keywords
    if any(k in t for k in ("bleb", "blebbing")):
        return "blebbing"
    if any(k in t for k in ("vacuol", "vacuole")):
        return "vacuolated"
    if any(k in t for k in ("debris", "dead", "lysis")):
        return "debris_heavy"
    if any(k in t for k in ("detach", "lifted", "floating")):
        return "detached"
    if any(k in t for k in ("mitos", "mitotic", "division", "rounding")):
        return "mitotic"
    if any(k in t for k in ("confluent", "dense", "packed")):
        return "confluent"
    if any(k in t for k in ("stress", "stressed", "unhealthy", "damaged")):
        return "stressed"
    if any(k in t for k in ("healthy", "normal", "viable")):
        return "healthy"
    # Metrics fallback (very rough heuristic)
    if metrics.get("texture_std", 0) > 80:
        return "stressed"
    return "healthy"


def _image_metrics(image_path: str) -> Dict[str, Any]:
    """Cheap numeric morphology vector: brightness + texture + geometry."""
    if not _PIL_AVAILABLE:
        return {}
    try:
        img = Image.open(image_path).convert("L")
        w, h = img.size
        px = list(img.getdata())
        if not px:
            return {"width": w, "height": h}
        mean = sum(px) / len(px)
        var = sum((p - mean) ** 2 for p in px) / len(px)
        return {
            "width": w,
            "height": h,
            "mean_brightness": round(mean, 2),
            "texture_std": round(var ** 0.5, 2),
        }
    except Exception:
        return {}


def ingest_frame(image_path: str, prompt: Optional[str] = None) -> Dict[str, Any]:
    """
    Observe one frame: describe it (local vision) + compute morphology metrics,
    then append a hash-chained trace. Return the row.
    """
    p = Path(image_path)
    if not p.exists():
        return {"ok": False, "error": "image_missing", "image_path": image_path}

    metrics = _image_metrics(image_path)
    description = ""
    status = "no_vision"
    if _VISION_AVAILABLE:
        res = describe_image_local(str(p), prompt or DEFAULT_PROMPT)
        if getattr(res, "ok", False):
            description = getattr(res, "output", "") or ""
            status = "described"
        else:
            status = getattr(res, "status", "vision_failed")

    row = append_trace(
        source=SOURCE,
        kind="cell_morphology",
        text=description or f"frame ingested (vision: {status})",
        image_id=p.name,
        confidence=1.0 if description else 0.5,
        extra={"metrics": metrics, "vision_status": status},
    )
    return {"ok": True, "status": status, "metrics": metrics, "row": row}


def trajectory(limit: int = 50) -> Dict[str, Any]:
    """
    Quantified cellular-state trajectory: read back the morphology traces Alice
    left, extract the numeric vector over time, and report the delta (latest
    vs earliest) as a signed state-drift signal.
    """
    rows = [r for r in read_traces(limit=limit * 4) if r.get("source") == SOURCE]
    rows = rows[:limit]
    points: List[Dict[str, Any]] = []
    for r in rows:
        m = (r.get("extra") or {}).get("metrics") or {}
        txt = (r.get("text") or "")[:120]
        phenotype = classify_phenotype(txt, m)
        points.append({
            "ts": r.get("ts"),
            "image_id": r.get("image_id"),
            "metrics": m,
            "text": txt,
            "phenotype": phenotype,
        })
    if len(points) < 2:
        return {
            "ok": True,
            "points": points,
            "drift": None,
            "note": "need >= 2 frames for a trajectory" if points else "no frames yet",
        }

    first = points[0]["metrics"]
    last = points[-1]["metrics"]
    drift: Dict[str, Any] = {}
    for key in ("mean_brightness", "texture_std"):
        if key in first and key in last:
            drift[key] = round(last[key] - first[key], 4)
    # Phenotype sequence for the trajectory axis
    phenotype_seq = [p["phenotype"] for p in points]
    return {"ok": True, "points": points, "drift": drift, "n": len(points), "phenotypes": phenotype_seq}


def trajectory_with_phenotypes(limit: int = 50) -> Dict[str, Any]:
    """
    Same as trajectory() but guarantees phenotype labels are included.
    """
    return trajectory(limit=limit)


def get_organ_info() -> Dict[str, Any]:
    """Metadata for discovery / registry."""
    return {
        "available": True,
        "label": TRUTH_LABEL,
        "effector": "System.swarm_cell_morphology_organ",
        "ledger": "cell_morphology_ledger.jsonl",
        "source": SOURCE,
        "purpose": (
            "observation/automation arm: microscope frame -> vision description "
            "-> time-series morphology -> stigmergic cellular-state trajectory"
        ),
        "safety_scope": (
            "observation only; no viral-vector manufacture, no recombinant "
            "nucleic-acid work, no human self-experimentation"
        ),
        "vision_available": _VISION_AVAILABLE,
        "pil_available": _PIL_AVAILABLE,
    }


def register_in_organ_registry() -> bool:
    """Append a discovery receipt to the canonical organ registry ledger."""
    try:
        from System.jsonl_file_lock import append_line_locked
        line = json.dumps(get_organ_info()) + "\n"
        if append_line_locked:
            append_line_locked(_STATE / "canonical_organ_registry.jsonl", line)
        else:
            with open(_STATE / "canonical_organ_registry.jsonl", "a") as f:
                f.write(line)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    import sys
    print(json.dumps(get_organ_info(), indent=2))
    if len(sys.argv) > 1:
        print("Ingesting frame:", sys.argv[1])
        print(json.dumps(ingest_frame(sys.argv[1]), indent=2))
    print("Trajectory:", json.dumps(trajectory(), indent=2))
