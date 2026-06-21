#!/usr/bin/env python3
"""Structured photo understanding — Alice's queryable scene record (r239).

George 2026-05-31: "I'm looking at the BioHuman body example's body and clothes, I wish you could too — what do I
need to code so you detect photo humans / clothing / objects / location / environment?" A brother
(Alice, in her own ledger analysis) spec'd the exact organ. This is it.

It turns a photo into ONE structured scene record:
    {humans:[{id,pose,clothing:[{piece,colors,materials,zones}]}],
     objects:[{class,relation}], location:{setting,indoor_outdoor},
     environment:{lighting,background:[...]}}

Two ingest paths, same output:
  1. STRICT JSON from a capable vision arm (STRUCTURED_SCENE_PROMPT asks for it) — parsed +
     normalized.
  2. PROSE FALLBACK — when the arm returns a normal description (today's default), the scene is
     built from the existing organs (swarm_wardrobe_pieces for clothing, swarm_visual_form_memory
     for the dominant form, a small object/location/lighting lexicon). So this works NOW, before
     any JSON-mode VLM, and degrades gracefully on a 403.

Grounded in: open-vocab detection (OWL-ViT/GLIP/Detic), fashion parsing (DeepFashion/Fashionpedia),
scene recognition (Places365). Honest scope: it names humans/garments/objects/setting for
recall + shopping; it does not infer private attributes of the person. Pure stdlib + two SIFTA organs.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

from System.swarm_wardrobe_pieces import (
    extract_wardrobe_pieces,
    resolve_wardrobe_piece_query,
)
try:
    from System.swarm_visual_form_memory import infer_form_category
except Exception:  # pragma: no cover
    def infer_form_category(_t: str) -> str:  # type: ignore
        return "other"

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = "photo_structured_understanding.jsonl"
TRUTH_LABEL = "PHOTO_STRUCTURED_UNDERSTANDING_V1"

STRUCTURED_SCENE_PROMPT = (
    "Look at the image at this exact path: {path}\n"
    "Return STRICT JSON ONLY (no prose, no markdown fence) matching this schema; use empty values "
    "when unsure, never guess:\n"
    '{"humans":[{"id":0,"pose":"","clothing":[{"piece":"","colors":[],"materials":[],"zones":[]}]}],'
    '"objects":[{"class":"","relation":""}],'
    '"location":{"setting":"","indoor_outdoor":""},'
    '"environment":{"lighting":"","background":[]}}\n'
    "Describe the MAIN subject and its setting. State only what is clearly visible."
)

_HUMAN_RE = re.compile(
    r"\b(?:person|people|woman|women|man|men|girl|boy|guy|model|lady|she|he|her|his|human)\b", re.I)
_OBJECT_VOCAB = (
    "rock", "rocks", "boulder", "boulders", "umbrella", "umbrellas", "pool", "lounger",
    "sun lounger", "chair", "table", "stool", "mirror", "wall", "column", "stairs", "staircase",
    "tree", "trees", "plant", "brush", "sand", "car", "building", "guitar", "couch", "sofa",
    "bed", "window", "door", "stage", "bench", "fence", "curb", "sidewalk", "railing",
)
_INDOOR = ("indoor", "room", "bedroom", "kitchen", "studio", "interior", "office", "vanity")
_OUTDOOR = ("outdoor", "outside", "beach", "ocean", "desert", "street", "sidewalk", "pool",
            "mountain", "forest", "sky", "field", "rooftop", "garden")
_SETTING = ("beach", "desert", "pool", "poolside", "studio", "bedroom", "kitchen", "street",
            "rooftop", "mountain", "forest", "rocks", "resort", "garden", "stage", "city")
_LIGHTING = ("sunlight", "sunlit", "harsh sun", "bright", "soft", "golden", "warm", "dim",
             "neon", "studio light", "natural light", "shadow", "backlit", "overcast")


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _find_json(raw: str) -> Optional[dict[str, Any]]:
    """Extract the first JSON object from an arm reply (strip code fences, locate {...})."""
    s = (raw or "").strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.IGNORECASE | re.MULTILINE).strip()
    start = s.find("{")
    end = s.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(s[start:end + 1])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _norm_list(v: Any) -> list:
    return v if isinstance(v, list) else ([] if v in (None, "") else [v])


def _normalize_scene(obj: dict[str, Any]) -> dict[str, Any]:
    humans = []
    for h in _norm_list(obj.get("humans")):
        if not isinstance(h, dict):
            continue
        clothing = []
        for c in _norm_list(h.get("clothing")):
            if isinstance(c, dict) and c.get("piece"):
                clothing.append({
                    "piece": str(c.get("piece") or ""),
                    "colors": _norm_list(c.get("colors")),
                    "materials": _norm_list(c.get("materials")),
                    "zones": _norm_list(c.get("zones")),
                })
        humans.append({"id": h.get("id", len(humans)), "pose": str(h.get("pose") or ""),
                       "clothing": clothing})
    objects = []
    for o in _norm_list(obj.get("objects")):
        if isinstance(o, dict) and o.get("class"):
            objects.append({"class": str(o.get("class") or ""), "relation": str(o.get("relation") or "")})
        elif isinstance(o, str) and o:
            objects.append({"class": o, "relation": ""})
    loc = obj.get("location") if isinstance(obj.get("location"), dict) else {}
    env = obj.get("environment") if isinstance(obj.get("environment"), dict) else {}
    return {
        "humans": humans,
        "objects": objects,
        "location": {"setting": str(loc.get("setting") or ""),
                     "indoor_outdoor": str(loc.get("indoor_outdoor") or "")},
        "environment": {"lighting": str(env.get("lighting") or ""),
                        "background": _norm_list(env.get("background"))},
        "source": "vision_arm_json",
    }


def build_scene_from_prose(description: str) -> dict[str, Any]:
    """Fallback: assemble a structured scene from a normal prose description (works today)."""
    text = " ".join((description or "").lower().split())
    clothing = [{"piece": p["piece"], "colors": p.get("colors", []),
                 "materials": p.get("materials", []), "zones": p.get("zones", [])}
                for p in extract_wardrobe_pieces(description)]
    has_human = bool(_HUMAN_RE.search(text)) or bool(clothing)
    humans = [{"id": 0, "pose": "", "clothing": clothing}] if has_human else []
    seen: set[str] = set()
    objects = []
    for w in _OBJECT_VOCAB:
        if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", text):
            base = w.rstrip("s")
            if base not in seen:
                seen.add(base)
                objects.append({"class": w, "relation": ""})
    setting = next((s for s in _SETTING if re.search(rf"(?<![a-z]){re.escape(s)}(?![a-z])", text)), "")
    indoor_outdoor = ("indoor" if any(k in text for k in _INDOOR)
                      else "outdoor" if any(k in text for k in _OUTDOOR) else "")
    lighting = next((l for l in _LIGHTING if l in text), "")
    return {
        "humans": humans,
        "objects": objects,
        "location": {"setting": setting, "indoor_outdoor": indoor_outdoor},
        "environment": {"lighting": lighting, "background": [o["class"] for o in objects]},
        "form": infer_form_category(description),
        "source": "prose_fallback",
    }


def parse_scene(raw: str, *, description_fallback: str = "") -> dict[str, Any]:
    """Normalize an arm reply into a scene. Strict JSON if present; else prose fallback."""
    obj = _find_json(raw)
    if obj is not None and any(k in obj for k in ("humans", "objects", "location", "environment")):
        scene = _normalize_scene(obj)
        # if the JSON came back empty but we have prose, enrich from prose
        if not scene["humans"] and not scene["objects"] and (description_fallback or raw):
            return build_scene_from_prose(description_fallback or raw)
        return scene
    return build_scene_from_prose(description_fallback or raw)


def record_scene(
    url: str, scene: dict[str, Any], *, arm: str = "", image_hash: str = "",
    frame_epoch: float = 0.0, now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    row = {
        "ts": float(now if now is not None else time.time()),
        "truth_label": TRUTH_LABEL,
        "url": str(url or ""),
        "image_hash": str(image_hash or ""),
        "frame_epoch": float(frame_epoch or 0.0),
        "arm": str(arm or ""),
        "scene": scene,
    }
    path = _state(state_dir) / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def latest_scene(*, url: Optional[str] = None, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    try:
        rows = [json.loads(l) for l in (_state(state_dir) / LEDGER).read_text(
            encoding="utf-8", errors="replace").splitlines() if l.strip().startswith("{")]
    except Exception:
        return {}
    if url:
        rows = [r for r in rows if r.get("url") == url] or rows
    return rows[-1] if rows else {}


def scene_understanding_block(scene: dict[str, Any]) -> str:
    """First-person: what Alice sees in the photo, by axis — humans, clothing, objects, setting."""
    if not scene:
        return ""
    humans = scene.get("humans") or []
    lines = ["WHAT I SEE IN THE PHOTO (structured, from my own eye):"]
    if humans:
        for h in humans:
            garments = ", ".join(
                " ".join((c.get("colors") or []) + (c.get("materials") or []) + [c.get("piece", "")]).strip()
                for c in (h.get("clothing") or [])
            ) or "no distinct garments named"
            pose = f" ({h['pose']})" if h.get("pose") else ""
            lines.append(f"  - human{pose}: wearing {garments}")
    else:
        lines.append("  - no human subject detected")
    objs = [o.get("class", "") for o in (scene.get("objects") or []) if o.get("class")]
    if objs:
        lines.append("  - objects: " + ", ".join(objs))
    loc = scene.get("location") or {}
    if loc.get("setting") or loc.get("indoor_outdoor"):
        lines.append(f"  - location: {loc.get('setting') or '?'} ({loc.get('indoor_outdoor') or '?'})")
    env = scene.get("environment") or {}
    if env.get("lighting"):
        lines.append(f"  - environment: {env.get('lighting')}")
    return "\n".join(lines)


def resolve_scene_query(owner_text: str, scene: dict[str, Any], description: str = "") -> dict[str, Any]:
    """Resolve a vague owner reference to a scene element + a search query.

    Clothing references ('the green puffy leg things') reuse the wardrobe resolver. Object /
    background references ('the rocks behind her') resolve against the scene objects."""
    owner = " ".join((owner_text or "").lower().split())
    # clothing first (delegate to the wardrobe resolver over the description)
    if description:
        clothing_hit = resolve_wardrobe_piece_query(owner_text, description)
        if clothing_hit.get("query") and re.search(
                r"\b(?:wear|wearing|outfit|leg|legs|top|bottom|bottoms|shoe|shoes|heel|dress|swimsuit|"
                r"warmer|warmers|jacket|hat|glasses|garment|clothing|piece)\b", owner):
            return {**clothing_hit, "kind": "clothing"}
    # objects / background
    for o in (scene.get("objects") or []):
        cls = str(o.get("class") or "").lower()
        if cls and re.search(rf"(?<![a-z]){re.escape(cls.rstrip('s'))}", owner):
            return {"kind": "object", "target": cls, "query": cls, "source": "scene_object_resolver"}
    if re.search(r"\b(?:background|behind|setting|location|place|where)\b", owner):
        loc = (scene.get("location") or {}).get("setting") or ""
        bg = ", ".join((scene.get("environment") or {}).get("background") or [])
        q = (loc or bg).strip()
        if q:
            return {"kind": "location", "target": "background/setting", "query": q,
                    "source": "scene_location_resolver"}
    return {"kind": "", "target": "", "query": "", "source": "no_scene_match"}


__all__ = [
    "STRUCTURED_SCENE_PROMPT", "TRUTH_LABEL",
    "parse_scene", "build_scene_from_prose", "record_scene", "latest_scene",
    "scene_understanding_block", "resolve_scene_query",
]
