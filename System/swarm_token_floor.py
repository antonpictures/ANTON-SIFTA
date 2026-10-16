#!/usr/bin/env python3
"""A floor under the token budget, for cortexes that think before they speak.

WHY (measured 2026-10-09/10, three independent models)
    Mercury 2.5 answered in 2.1 s and reported 564 completion tokens of which 548 -- 97% -- were
    REASONING. The same shape appears in the local cortexes: asked a real question with a 300-token
    budget, mercury-2.5, AliceG4U and Ornith-1.5-9B ALL returned EMPTY content while reporting a
    full budget spent. A caller that sees empty content reads it as failure, and a caller that waits
    reads it as a stall -- which is how a healthy cortex gets blamed for being broken.

    The body has call sites asking for 60, 80 or 120 tokens. For a model that thinks first, that is
    not a small answer; it is no answer at all.

THE RULE
    A budget below the floor is raised to the floor. Above it, the caller's number is kept. The
    floor is a floor, not a target: it changes nothing for a cortex whose budget is already sane.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# Below this, a reasoning cortex is likely to answer with reasoning and no content.
MIN_REASONING_TOKENS = 400

# Model names known to emit reasoning before content. Matched case-insensitively as substrings, so
# "mercury-2.5", "nemotron-3-ultra:cloud" and "hf.co/.../Ornith-1.5-9B-uncensored-GGUF:Q4_K_M" all
# land here. An unlisted model is still floored: a floor that only protects the models I remembered
# would fail on the next one I borg -- which is the whole pattern this file exists to stop.
REASONING_HINTS = (
    "mercury", "nemotron", "aliceg4u", "ornith", "deepseek", "qwen", "gemini", "glm",
    "thinking", "reason",
)


def reasons(model: str = "") -> bool:
    """Whether a cortex is expected to think before it speaks."""
    name = (model or "").lower()
    if not name:
        return True
    return any(h in name for h in REASONING_HINTS)


def floor_tokens(requested: Any, model: str = "", minimum: Optional[int] = None) -> int:
    """The budget to actually ask for.

    @param requested - what the call site wanted.
    @param model - the cortex the request goes to.
    @param minimum - override the floor.
    @returns requested, raised to the floor when the cortex reasons and asked for too little.
    """
    try:
        n = int(requested)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return 0
    floor = MIN_REASONING_TOKENS if minimum is None else int(minimum)
    if reasons(model) and n < floor:
        return floor
    return n


def apply_to_options(options: Dict[str, Any], model: str = "") -> Dict[str, Any]:
    """Raise num_predict / max_tokens inside an options dict, in place, and return it."""
    for key in ("num_predict", "max_tokens", "max_completion_tokens"):
        if key in options:
            options[key] = floor_tokens(options[key], model)
    return options
