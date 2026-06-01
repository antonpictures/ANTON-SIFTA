#!/usr/bin/env python3
"""swarm_desktop_wallpaper.py — "Generate your desktop with Bonsai" (r272).

Architect George 2026-06-01: add a button "Generate your desktop with Bonsai" (we have Bonsai
installed) + a text box where the user types the desired prompt. By default the LLM generates a
new prompt from the selected theme — and the default text is ALWAYS different.

This organ holds the testable logic; the System Settings Display tab is the thin Qt shell:
  - default_prompt_for_theme(theme_id): an always-different prompt seeded from the theme + the
    clock, so an empty box still produces a fresh desktop every time.
  - generate_desktop_wallpaper(prompt, theme_id): wraps swarm_bonsai_image_organ.generate_bonsai_image
    (on-device ternary MLX, §7.16 OBSERVED_AI_GENERATED) and returns {ok, path, prompt, error}.
The image is the deterministic substrate; the prompt is the owner's (or the varied default). No
restriction (First Law §0.0) — any prompt the owner types is honored.
"""
from __future__ import annotations

import random
import time
from typing import Any, Callable, Dict, Optional

# Per-theme mood vocabulary — the seed palette the varied default draws from. These are
# descriptors, not fixed captions; the rotation + clock seed make each default unique.
_THEME_MOODS = {
    "beeson_v8": ["amber honeycomb light", "stigmergic swarm trails", "warm hive geometry",
                  "golden ant paths", "bee-gold lattice"],
    "predator_v7": ["bioluminescent jungle dusk", "thermal-vision greens", "wet obsidian leaves",
                    "predator heat shimmer", "deep canopy glow"],
    "mermaid_v6": ["teal underwater caustics", "pearl and coral light", "slow kelp drift",
                   "siren bioluminescence", "deep-sea calm"],
}
_DEFAULT_MOODS = ["soft volumetric light", "calm abstract gradients", "organic flowing forms",
                  "quiet minimal landscape", "luminous stigmergic field"]
_SCENES = ["a vast quiet horizon", "a close macro texture", "a flowing abstract field",
           "a still nocturne", "a sunrise over geometry", "a dreaming microcosm"]
_FINISH = ["4k wallpaper, painterly", "soft bokeh, cinematic", "clean minimal, high detail",
           "matte, atmospheric depth", "wide desktop composition"]


def default_prompt_for_theme(theme_id: str = "beeson_v8", *, rng: Optional[random.Random] = None) -> str:
    """An always-different wallpaper prompt seeded from the theme + the clock.

    Two calls (different clock / rng) yield different prompts — so an empty box still gives a
    fresh desktop each time, themed to the current skin.
    """
    rng = rng or random.Random(time.time_ns())
    moods = _THEME_MOODS.get(str(theme_id or "").strip().lower(), _DEFAULT_MOODS)
    mood = rng.choice(moods)
    scene = rng.choice(_SCENES)
    finish = rng.choice(_FINISH)
    return f"{scene}, {mood}, {finish}"


def generate_desktop_wallpaper(
    prompt: str = "",
    *,
    theme_id: str = "beeson_v8",
    seed: Optional[int] = None,
    resolution: str = "1024x1024",
    generator: Optional[Callable[..., Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Generate a desktop wallpaper via Bonsai. Empty prompt -> a varied theme default.

    ``generator`` defaults to swarm_bonsai_image_organ.generate_bonsai_image; inject a fake in
    tests. Returns {ok, path, prompt, error}. Never raises.
    """
    used = str(prompt or "").strip() or default_prompt_for_theme(theme_id)
    if seed is None:
        seed = int(time.time()) % 100000

    def _default_gen(p: str, *, seed: int, resolution: str) -> Dict[str, Any]:
        from System.swarm_bonsai_image_organ import generate_bonsai_image
        return generate_bonsai_image(p, seed=seed, resolution=resolution)

    gen = generator or _default_gen
    try:
        res = gen(used, seed=seed, resolution=resolution)
    except Exception as exc:  # never crash the settings panel
        return {"ok": False, "path": "", "prompt": used, "error": f"{type(exc).__name__}: {exc}"}
    res = res if isinstance(res, dict) else {}
    path = str(res.get("out_path") or res.get("path") or res.get("image_path") or "")
    ok = bool(res.get("ok", bool(path))) and bool(path)
    return {"ok": ok, "path": path, "prompt": used, "error": str(res.get("error") or "")}


__all__ = ["default_prompt_for_theme", "generate_desktop_wallpaper"]
