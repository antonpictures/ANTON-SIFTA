#!/usr/bin/env python3
"""System/swarm_bonsai_image_organ.py — Bonsai Image stigmergic organ.

George's ask (r146/r207): generate AI images locally on the M-series Mac with
prism-ml/bonsai-image-ternary-4B-mlx-2bit (1.58-bit ternary FLUX.2 Klein 4B,
Apple-Silicon-native MLX), then TEACH Alice what each image is in stigmergic
language — so she "sees" it the same way she sees a camera frame, but the
provenance is honest: it is AI-generated, not a real-world scene.

Two honest boundaries this organ enforces:

  • §7.16 reality/fiction boundary — an AI image is NEVER deposited as a real
    OBSERVED camera scene. Every row this organ writes carries
    `source="ai_generated"` and `stigmergic_label="OBSERVED_AI_GENERATED"`.
    Alice may LEARN from it; she may not claim she saw it with her camera.

  • Generation runs on Apple Silicon via MLX. This module does NOT bundle the
    model or the MLX diffusion kernels. It shells out to a generation backend
    the owner sets up on the Mac (the Bonsai-Image-Demo repo, pointed at by the
    SIFTA_BONSAI_DEMO_DIR env var). If the backend is not present, generation
    returns an honest error instead of faking an image.

The LEARNING half (fingerprint + deposit into the visual_stigmergy lane that the
camera organs already read) is implemented here against the real on-disk schema.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_VISUAL_LANE = _STATE / "visual_stigmergy.jsonl"          # same lane the camera writes
_BONSAI_TRACE = _STATE / "bonsai_image_trace.jsonl"        # this organ's own append-only ledger
_ANT_CORTEX_TRACE = _STATE / "bonsai_ant_cortex.jsonl"     # ant+cortex prompt composition trace
_IMAGES_DIR = _STATE / "bonsai_images"

MODEL_ID = "prism-ml/bonsai-image-ternary-4B-mlx-2bit"
DEFAULT_MODEL_SUBDIR = "models/bonsai-image-4B-ternary-mlx"
# Owner sets this on the Mac to the cloned https://github.com/PrismML-Eng/Bonsai-Image-Demo
_DEMO_DIR_ENV = "SIFTA_BONSAI_DEMO_DIR"


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _row_hash(row: Dict[str, Any]) -> str:
    body = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _tail_jsonl(path: Path, limit: int = 24) -> list[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()[-max(1, limit):]
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "for", "from", "in", "is", "it", "of",
    "on", "or", "the", "this", "to", "with",
}


def _clean_fragment(value: Any) -> str:
    text = re.sub(r"[^a-zA-Z0-9 _-]+", " ", str(value or "").lower())
    text = re.sub(r"[_-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 3 or text in _STOP_WORDS:
        return ""
    return text[:48]


def _field_fragments(row: Dict[str, Any]) -> list[str]:
    fragments: list[str] = []
    for key in ("owner_label", "meaning", "prompt", "stigmergic_label"):
        raw = row.get(key)
        if not raw:
            continue
        for part in re.split(r"[,;/|]+", str(raw)):
            clean = _clean_fragment(part)
            if clean:
                fragments.append(clean)
        for word in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", str(raw).lower()):
            clean = _clean_fragment(word)
            if clean:
                fragments.append(clean)

    hue = row.get("hue_deg")
    if isinstance(hue, (int, float)):
        if 70 <= float(hue) <= 170:
            fragments.append("green living hue")
        elif 15 <= float(hue) <= 65:
            fragments.append("warm golden light")
        elif 180 <= float(hue) <= 270:
            fragments.append("cool blue atmosphere")
        else:
            fragments.append("unusual color field")

    entropy = row.get("entropy_bits")
    if isinstance(entropy, (int, float)):
        fragments.append("rich textured detail" if float(entropy) >= 6.0 else "quiet simple form")

    saliency = row.get("saliency_peak")
    if isinstance(saliency, (int, float)) and float(saliency) >= 0.25:
        fragments.append("strong focal contrast")
    if row.get("source") == "ai_generated":
        fragments.append("honest ai generated provenance")
    return fragments


def extract_bonsai_pheromone_fragments(
    visual_rows: Iterable[Dict[str, Any]],
    trace_rows: Iterable[Dict[str, Any]],
) -> list[str]:
    """Extract prompt fragments from the visual pheromone field."""
    seen: set[str] = set()
    out: list[str] = []
    for row in list(visual_rows) + list(trace_rows):
        for fragment in _field_fragments(row):
            if fragment not in seen:
                out.append(fragment)
                seen.add(fragment)
    if out:
        return out[:64]
    return [
        "bonsai tree",
        "quiet ceramic studio",
        "soft morning light",
        "calm craft patience",
        "honest ai generated provenance",
    ]


def update_pheromone_weight(
    current: float,
    candidate_score: float,
    *,
    evaporation: float = 0.18,
    deposit: float = 0.72,
) -> float:
    """Biology-inspired stigmergic update: next=(1-e)*now + d*score."""
    return round(((1.0 - evaporation) * float(current)) + (deposit * float(candidate_score)), 6)


def _weighted_sample(rng: random.Random, weights: Dict[str, float], k: int) -> list[str]:
    pool = dict(weights)
    chosen: list[str] = []
    for _ in range(min(k, len(pool))):
        total = sum(max(v, 0.0001) for v in pool.values())
        dart = rng.random() * total
        acc = 0.0
        picked = next(iter(pool))
        for fragment, weight in pool.items():
            acc += max(weight, 0.0001)
            if acc >= dart:
                picked = fragment
                break
        chosen.append(picked)
        pool.pop(picked, None)
    return chosen


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "ant-cortex-bonsai"


def generate_ant_prompt_candidates(
    fragments: Optional[list[str]] = None,
    *,
    visual_rows: Optional[list[Dict[str, Any]]] = None,
    trace_rows: Optional[list[Dict[str, Any]]] = None,
    ant_count: int = 24,
    rounds: int = 5,
    seed: int = 42,
) -> list[Dict[str, Any]]:
    """Let prompt fragments compete through pheromone-weighted ant walks."""
    if fragments is None:
        fragments = extract_bonsai_pheromone_fragments(visual_rows or [], trace_rows or [])
    fragments = [f for f in fragments if _clean_fragment(f)]
    if not fragments:
        fragments = extract_bonsai_pheromone_fragments([], [])

    rng = random.Random(seed)
    weights = {fragment: 1.0 for fragment in fragments}
    candidates: list[Dict[str, Any]] = []
    for round_idx in range(max(1, rounds)):
        for ant_idx in range(max(1, ant_count)):
            chosen = _weighted_sample(rng, weights, k=3)
            if not chosen:
                continue
            weight_mean = sum(weights.get(fragment, 1.0) for fragment in chosen) / len(chosen)
            novelty = len(set(chosen)) / max(1, len(chosen))
            score = round((0.65 * novelty) + (0.35 * min(2.0, weight_mean) / 2.0), 6)
            for fragment in chosen:
                weights[fragment] = update_pheromone_weight(weights[fragment], score)
            prompt = "A " + ", ".join(chosen) + ", composed as a teachable Bonsai image for Alice"
            candidates.append({
                "prompt": prompt,
                "owner_label": _slug(chosen[0]),
                "meaning": ", ".join(chosen),
                "score": score,
                "fragments": chosen,
                "round": round_idx,
                "ant": ant_idx,
            })

    deduped: dict[str, Dict[str, Any]] = {}
    for row in sorted(candidates, key=lambda r: (-float(r["score"]), r["prompt"])):
        deduped.setdefault(row["prompt"], row)
    return list(deduped.values())[:5]


def parse_bonsai_cortex_json(text: str) -> Dict[str, str]:
    """Parse the cortex JSON contract, including markdown-fenced JSON."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty cortex response")
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1)
    elif not raw.startswith("{"):
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise ValueError("cortex response did not contain JSON object")
        raw = match.group(0)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid cortex JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("cortex JSON must be an object")
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("cortex JSON missing non-empty prompt")
    owner_label = str(data.get("owner_label") or _slug(prompt)).strip()
    meaning = str(data.get("meaning") or "").strip()
    rationale = str(data.get("rationale") or "").strip()
    return {
        "prompt": prompt,
        "owner_label": owner_label or _slug(prompt),
        "meaning": meaning,
        "rationale": rationale,
    }


def _ant_cortex_messages(candidates: list[Dict[str, Any]]) -> list[Dict[str, str]]:
    compact = [
        {
            "prompt": c.get("prompt", ""),
            "owner_label": c.get("owner_label", ""),
            "meaning": c.get("meaning", ""),
            "score": c.get("score", 0),
        }
        for c in candidates
    ]
    return [
        {
            "role": "system",
            "content": (
                "You are Alice's Bonsai Image Studio cortex helper. Ant swimmers already "
                "sampled visual pheromone fragments. Select or refine one teachable AI-image "
                "prompt. Return ONLY JSON with keys: prompt, owner_label, meaning, rationale."
            ),
        },
        {
            "role": "user",
            "content": json.dumps({"ant_candidates": compact}, ensure_ascii=False),
        },
    ]


def call_live_bonsai_cortex(candidates: list[Dict[str, Any]], *, timeout_s: int = 45) -> Dict[str, Any]:
    """Ask the current Alice cortex to choose/refine ant-generated candidates."""
    query_text = "\n".join(str(c.get("prompt", "")) for c in candidates)
    from System.sifta_inference_defaults import resolve_ollama_model

    model = resolve_ollama_model(app_context="bonsai_image_studio", query_text=query_text)
    messages = _ant_cortex_messages(candidates)
    text = ""
    try:
        from System.swarm_gemini_brain import is_cloud_model, stream_chat
        if is_cloud_model(model):
            errors: list[str] = []
            for kind, payload in stream_chat(
                model,
                messages,
                temperature=0.4,
                request_tag=f"bonsai-ant-{uuid.uuid4().hex[:8]}",
                timeout_s=timeout_s,
            ):
                if kind == "done":
                    text = str(payload or "")
                elif kind == "token" and not text:
                    text += str(payload or "")
                elif kind == "error":
                    errors.append(str(payload))
            if errors and not text.strip():
                return {"ok": False, "model": model, "error": "; ".join(errors)}
        else:
            from System.inference_router import route_inference

            payload = {
                "model": model,
                "system": messages[0]["content"],
                "prompt": messages[1]["content"],
                "stream": False,
                "temperature": 0.4,
                "num_predict": 220,
                "keep_alive": "2m",
            }
            text = route_inference(payload, timeout=timeout_s).strip()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "model": model, "error": f"{type(exc).__name__}: {exc}"}

    try:
        selected = parse_bonsai_cortex_json(text)
    except ValueError as exc:
        return {"ok": False, "model": model, "error": str(exc), "raw_text": text[:1000]}
    return {"ok": True, "model": model, "selected": selected, "raw_text": text[:1000]}


def compose_bonsai_ant_cortex(*, seed: int = 42, timeout_s: int = 45, tail_limit: int = 24) -> Dict[str, Any]:
    """Ants sample the visual field, live cortex refines, and the attempt is receipted."""
    ts = time.time()
    visual_rows = _tail_jsonl(_VISUAL_LANE, tail_limit)
    trace_rows = _tail_jsonl(_BONSAI_TRACE, tail_limit)
    fragments = extract_bonsai_pheromone_fragments(visual_rows, trace_rows)
    candidates = generate_ant_prompt_candidates(fragments, seed=seed)
    cortex = call_live_bonsai_cortex(candidates, timeout_s=timeout_s)
    ok = bool(cortex.get("ok"))
    row: Dict[str, Any] = {
        "ts": ts,
        "schema": "BONSAI_ANT_CORTEX_COMPOSE_V1",
        "receipt_id": f"r-bonsai-ant-cortex-{int(ts * 1000)}",
        "ok": ok,
        "formula": "pheromone_next=(1-evaporation)*pheromone_now+deposit*candidate_score",
        "source_app": "Bonsai Image Studio (AI Vision)",
        "field_inputs": {
            "visual_rows": len(visual_rows),
            "bonsai_trace_rows": len(trace_rows),
            "fragment_count": len(fragments),
        },
        "candidates": candidates,
        "cortex_model": cortex.get("model", ""),
        "selected": cortex.get("selected") if ok else None,
        "error": "" if ok else cortex.get("error", "cortex failed"),
    }
    row["row_hash"] = _row_hash(row)
    _append_jsonl(_ANT_CORTEX_TRACE, row)
    result = dict(row)
    result["trace_path"] = str(_ANT_CORTEX_TRACE)
    return result


# ── Generation backend (Apple Silicon / MLX — runs on the Mac) ────────────────

def _demo_model_dir(demo_dir: Path) -> Path:
    return demo_dir / DEFAULT_MODEL_SUBDIR


def bonsai_backend_status() -> Dict[str, Any]:
    """Return an honest readiness report for the owner-configured MLX backend."""
    demo_dir = os.environ.get(_DEMO_DIR_ENV, "").strip()
    if not demo_dir:
        return {
            "ok": False,
            "configured": False,
            "env_var": _DEMO_DIR_ENV,
            "demo_dir": "",
            "model_dir": "",
            "script_path": "",
            "error": (
                f"Bonsai generation backend not configured. Set {_DEMO_DIR_ENV} to the "
                f"cloned Bonsai-Image-Demo dir on the Mac, run ./setup.sh and "
                f"./scripts/download_model.sh first. (Apple-Silicon/MLX only.)"
            ),
        }

    demo_path = Path(demo_dir).expanduser()
    model_dir = _demo_model_dir(demo_path)
    script_path = demo_path / "scripts" / "generate.sh"
    base = {
        "configured": True,
        "env_var": _DEMO_DIR_ENV,
        "demo_dir": str(demo_path),
        "model_dir": str(model_dir),
        "script_path": str(script_path),
    }
    if not demo_path.exists():
        return {
            **base,
            "ok": False,
            "error": f"Bonsai generation backend directory does not exist: {demo_path}",
        }
    try:
        has_model = model_dir.exists() and any(model_dir.iterdir())
    except OSError:
        has_model = False
    if not has_model:
        return {
            **base,
            "ok": False,
            "error": (
                f"Bonsai ternary MLX model is not downloaded yet: {model_dir}. "
                f"Run: cd {demo_path} && ./scripts/download_model.sh ternary"
            ),
        }
    if not script_path.exists():
        return {
            **base,
            "ok": False,
            "error": f"Bonsai generation script is missing: {script_path}. Re-run backend setup.",
        }
    return {**base, "ok": True, "error": ""}


def model_present() -> bool:
    demo_dir = os.environ.get(_DEMO_DIR_ENV, "").strip()
    if not demo_dir:
        return False
    model_dir = _demo_model_dir(Path(demo_dir).expanduser())
    try:
        return model_dir.exists() and any(model_dir.iterdir())
    except OSError:
        return False


def generate_bonsai_image(prompt: str, *, seed: int = 42, resolution: str = "512x512") -> Dict[str, Any]:
    """Render one image via the local MLX Bonsai backend on Apple Silicon.

    Honest contract: this shells out to the owner-configured Bonsai-Image-Demo
    generate script. It does NOT fabricate an image if the backend is missing —
    it returns {"ok": False, "error": ...} so no fake OBSERVED row is written.
    """
    status = bonsai_backend_status()
    if not status.get("ok"):
        return {
            "ok": False,
            "error": status.get("error", "Bonsai backend is not ready."),
            "backend_status": status,
        }
    demo_path = Path(str(status.get("demo_dir") or ""))
    _IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _IMAGES_DIR / f"{int(time.time() * 1000)}_{seed}.png"
    gen = Path(str(status.get("script_path") or (demo_path / "scripts" / "generate.sh")))
    # Real generate.py flags (verified against the cloned demo): -p/--prompt,
    # --seed, --steps, --size WxH (default 512x512), --output PNG path.
    cmd = [str(gen), "--prompt", prompt, "--seed", str(seed),
           "--size", resolution, "--output", str(out_path)]
    try:
        proc = subprocess.run(cmd, cwd=demo_path, capture_output=True, text=True, timeout=300)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"generation backend launch failed: {type(exc).__name__}: {exc}"}
    if proc.returncode != 0 or not out_path.exists():
        return {"ok": False, "error": f"generation failed rc={proc.returncode}: {(proc.stderr or '')[:1200]}"}
    return {"ok": True, "image_path": str(out_path), "prompt": prompt, "seed": seed, "model": MODEL_ID}


# ── Perceptual fingerprint (so the AI image enters the camera's visual lane) ──

def _visual_fingerprint(image_path: str) -> Dict[str, Any]:
    """Compute the same shape of perceptual fingerprint the camera lane stores.

    Best-effort and clearly approximate: it reproduces the visual_stigmergy
    schema keys (sha8, w, h, entropy_bits, hue_deg, motion_mean, saliency_peak)
    from a still image. motion_mean is 0.0 — a generated still has no motion.
    Requires Pillow; degrades to a hash-only fingerprint if Pillow is absent.
    """
    raw = Path(image_path).read_bytes()
    fp: Dict[str, Any] = {"sha8": hashlib.sha256(raw).hexdigest()[:8], "motion_mean": 0.0}
    try:
        from PIL import Image  # type: ignore
        import colorsys
        im = Image.open(image_path).convert("RGB")
        fp["w"], fp["h"] = im.width, im.height
        small = im.resize((64, 64))
        px = list(small.getdata())
        # Shannon entropy over greyscale histogram
        hist = [0] * 256
        for r, g, b in px:
            hist[(r * 299 + g * 587 + b * 114) // 1000] += 1
        n = float(sum(hist)) or 1.0
        fp["entropy_bits"] = round(-sum((c / n) * math.log2(c / n) for c in hist if c), 3)
        # mean hue in degrees
        hs = [colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[0] for r, g, b in px]
        fp["hue_deg"] = round((sum(hs) / len(hs)) * 360.0, 1)
        # crude saliency peak = max normalized luminance variance proxy
        lum = [(r * 299 + g * 587 + b * 114) / 255000.0 for r, g, b in px]
        mean = sum(lum) / len(lum)
        fp["saliency_peak"] = round(max(abs(x - mean) for x in lum), 3)
    except Exception:  # noqa: BLE001
        fp["fingerprint_note"] = "Pillow unavailable; hash-only fingerprint"
    return fp


# ── Teach: deposit into the visual lane, AI-labeled, with the owner's meaning ─

def teach_bonsai_image(image_path: str, owner_label: str, meaning: str = "",
                       *, prompt: str = "", seed: Optional[int] = None) -> Dict[str, Any]:
    """Teach Alice what a generated image IS, in stigmergic language.

    Writes ONE row to the same visual_stigmergy lane the camera organs read, so
    Alice perceives it as a visual event — but tagged source=ai_generated /
    OBSERVED_AI_GENERATED (§7.16: labeled provenance, never a faked real scene),
    carrying the owner's stigmergic label + meaning so she learns the semantic.
    """
    fp = _visual_fingerprint(image_path)
    ts = time.time()
    row = {
        "ts": ts,
        "source": "ai_generated",
        "stigmergic_label": "OBSERVED_AI_GENERATED",
        "owner_label": (owner_label or "").strip(),
        "meaning": (meaning or "").strip(),
        "prompt": prompt,
        "seed": seed,
        "model": MODEL_ID,
        "image_path": str(image_path),
        "taught_by": "owner",
        "receipt_id": f"r207-bonsai-teach-{int(ts * 1000)}",
        **fp,
    }
    _append_jsonl(_VISUAL_LANE, row)     # enters the lane the camera writes
    _append_jsonl(_BONSAI_TRACE, row)    # organ-local audit
    return {"ok": True, "trace": row, "visual_lane": str(_VISUAL_LANE)}


def generate_and_teach(prompt: str, owner_label: str, meaning: str = "", *,
                       seed: int = 42, resolution: str = "512x512") -> Dict[str, Any]:
    """Generate, then teach in one call."""
    gen = generate_bonsai_image(prompt, seed=seed, resolution=resolution)
    if not gen.get("ok"):
        return gen
    taught = teach_bonsai_image(gen["image_path"], owner_label, meaning, prompt=prompt, seed=seed)
    return {"ok": True, "image_path": gen["image_path"], "trace": taught["trace"]}


if __name__ == "__main__":  # tiny self-probe (no generation; no model needed)
    print("model_present:", model_present())
    print("demo backend:", os.environ.get(_DEMO_DIR_ENV) or "(not set)")
    print("visual lane:", _VISUAL_LANE)
