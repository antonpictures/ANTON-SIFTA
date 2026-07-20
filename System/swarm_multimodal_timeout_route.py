#!/usr/bin/env python3
"""swarm_multimodal_timeout_route.py — r1621-04 multimodal timeout / fail-fast.

Glass fail: krishairnd/Gemma-4-Uncensored hung ~90s with no first token on
screenshot/describe turns. Text-heavy local tags must not sit on fat image
prompts until the global watchdog; route vision or fail fast with honest gap.

Truth label: MULTIMODAL_TIMEOUT_ROUTE_V1
"""

from __future__ import annotations

import re
from typing import Any, Optional, Sequence

TRUTH_LABEL = "MULTIMODAL_TIMEOUT_ROUTE_V1"

# Models that routinely stall on image+fat-prompt even if tag mentions gemma.
_KNOWN_TEXT_HEAVY_OR_STALL_RE = re.compile(
    r"(?:"
    r"krishairnd/gemma-4-uncensored|"
    r"heretic|"
    r"igorls/|"
    r"ornith|"
    r"qwenpaw|"
    r"nightshift|"
    r"north-mini-code|"
    r"hauhau|"
    r"ultragemma|"
    r"baytout3/|"
    r"text[\s_-]*only|"
    r"qat-q4_0-unquantized"
    r")",
    re.IGNORECASE,
)

_VISION_HINT_RE = re.compile(
    r"(?:"
    r"vision|llava|bakllava|moondream|minicpm|qwen-vl|qwen2\.?5?-?vl|"
    r"internvl|phi-3\.5-vision|llama3\.2-vision|mlx-vlm|qwopus|keye|"
    r"alice-m5-cortex|alice-gemma4"
    r")",
    re.IGNORECASE,
)


def is_risky_multimodal_text_mind(model: str) -> bool:
    """True when local mind is known to hang or lack a reliable vision path."""
    mid = str(model or "").strip()
    if not mid:
        return False
    if _VISION_HINT_RE.search(mid) and "uncensored" not in mid.lower():
        # alice-m5 / qwopus style — keep as vision-capable
        return False
    if _KNOWN_TEXT_HEAVY_OR_STALL_RE.search(mid):
        return True
    try:
        from System.swarm_body_multimodal_policy import is_text_only_cortex

        if is_text_only_cortex(mid):
            return True
    except Exception:
        pass
    try:
        from System.swarm_cortex_capabilities import is_vision_capable_model

        if not is_vision_capable_model(mid):
            return True
    except Exception:
        pass
    return False


def first_token_patience_for_multimodal(
    model: str,
    *,
    has_image: bool,
    base_s: float = 90.0,
) -> dict[str, Any]:
    """Shorten first-token wait when image is on a stall-prone mind."""
    base = max(8.0, float(base_s or 90.0))
    if not has_image:
        return {
            "truth_label": TRUTH_LABEL,
            "patience_s": base,
            "reason": "no_image",
            "fail_fast": False,
        }
    if is_risky_multimodal_text_mind(model):
        # 18s: long enough for a real VLM first token; short enough vs 90s hang.
        patience = min(base, 18.0)
        return {
            "truth_label": TRUTH_LABEL,
            "patience_s": patience,
            "reason": "image_on_text_heavy_or_stall_prone_mind",
            "fail_fast": True,
            "model": str(model or ""),
        }
    return {
        "truth_label": TRUTH_LABEL,
        "patience_s": min(base, 45.0),
        "reason": "image_on_vision_capable_or_unknown",
        "fail_fast": False,
        "model": str(model or ""),
    }


def route_multimodal_turn(
    model: str,
    *,
    has_image: bool,
    available_vlms: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    """Decide keep / redirect VLM / fail-fast honest gap. No side effects."""
    mid = str(model or "").strip()
    if not has_image:
        return {
            "action": "keep",
            "model": mid,
            "to": mid,
            "reason": "no_image",
            "truth_label": TRUTH_LABEL,
            "patience": first_token_patience_for_multimodal(mid, has_image=False),
        }
    # Prefer existing VLM redirect organ when text-only.
    try:
        from System.swarm_body_multimodal_policy import image_turn_vlm_redirect

        redir = image_turn_vlm_redirect(
            mid, True, available_vlms=list(available_vlms) if available_vlms is not None else None
        )
        if redir.get("redirect") and redir.get("to"):
            to = str(redir["to"])
            return {
                "action": "redirect_vlm",
                "model": mid,
                "to": to,
                "reason": str(redir.get("reason") or "vlm_redirect"),
                "truth_label": TRUTH_LABEL,
                "patience": first_token_patience_for_multimodal(to, has_image=True, base_s=45.0),
            }
    except Exception as exc:
        redir_err = f"vlm_redirect_failed:{type(exc).__name__}"
    else:
        redir_err = ""

    if is_risky_multimodal_text_mind(mid):
        return {
            "action": "fail_fast_text_only",
            "model": mid,
            "to": mid,
            "reason": (
                "image_on_stall_prone_local_mind_no_vlm; "
                "do not wait 90s — say no first token / no vision path"
            ),
            "truth_label": TRUTH_LABEL,
            "patience": first_token_patience_for_multimodal(mid, has_image=True),
            "owner_line": (
                "No first token on multimodal with this local mind within a short "
                "patience window. I am not pretending to see the pixels. "
                "Switch to a vision cortex/VLM or describe without image."
            ),
            "redir_err": redir_err,
        }
    return {
        "action": "keep",
        "model": mid,
        "to": mid,
        "reason": "vision_ok_or_unknown_keep",
        "truth_label": TRUTH_LABEL,
        "patience": first_token_patience_for_multimodal(mid, has_image=True, base_s=45.0),
    }


__all__ = [
    "TRUTH_LABEL",
    "is_risky_multimodal_text_mind",
    "first_token_patience_for_multimodal",
    "route_multimodal_turn",
]
