#!/usr/bin/env python3
"""Kimi/Fireworks vision arm — Alice's eye when her cortex IS Kimi K2.6 (r214).

George 2026-05-31: "I'm on kimi k cortex, has tools image all — stay on kimi k api."
Kimi K2.6 (accounts/fireworks/models/kimi-k2p6) is native multimodal (Vision tag on
Fireworks). So when Kimi is the active cortex, she should see with KIMI's own API — not
fail over to claude or to the local eye. The qwen Code CLI is text-only, so this arm
talks to the Fireworks OpenAI-compatible /chat/completions endpoint directly, inlining
the screenshot as an image_url base64 data URI.

Key is the local node secret (read_fireworks_api_key), never embedded in receipts.
Pure stdlib. Honest failure (no key / error / empty) — never pretends Kimi saw.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from System.swarm_fireworks_qwen_config import (
    FIREWORKS_CHAT_COMPLETIONS_URL,
    FIREWORKS_KIMI_K2P6_MODEL,
    read_fireworks_api_key,
)

ARM_ID = "qwen_agent"  # the Fireworks arm id Alice already knows
DEFAULT_VISION_MODEL = FIREWORKS_KIMI_K2P6_MODEL


@dataclass(frozen=True)
class FireworksVisionResult:
    """Shaped like AgentArmResult so describe_current_photo reads .ok/.output uniformly."""
    ok: bool
    output: str = ""
    status: str = ""
    arm_id: str = ARM_ID
    model: str = ""
    stderr: str = ""


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def describe_image_fireworks(
    image_path: str,
    prompt: str,
    *,
    model: str = "",
    timeout_s: float = 300.0,
    state_dir=None,
    env=None,
) -> FireworksVisionResult:
    """Let Kimi K2.6 (or another Fireworks vision model) look at the screenshot.

    ``ok`` is True only when Kimi answered with non-empty text. On any miss (no key,
    HTTP error, empty answer) ``ok`` is False with an honest ``status`` — George wants
    to STAY on Kimi, so a failure is reported, not silently swapped for claude."""
    p = Path(image_path)
    if not image_path or not p.exists():
        return FireworksVisionResult(ok=False, status="image_missing")
    key = read_fireworks_api_key(state_dir=state_dir, env=env)
    if not key:
        return FireworksVisionResult(ok=False, status="no_fireworks_api_key")
    chosen = (model or "").strip() or DEFAULT_VISION_MODEL
    try:
        uri = _data_uri(p)
    except Exception as exc:
        return FireworksVisionResult(ok=False, status="image_read_failed", stderr=str(exc), model=chosen)
    body = json.dumps({
        "model": chosen,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": uri}},
            ],
        }],
        "temperature": 0.2,
        "stream": False,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            FIREWORKS_CHAT_COMPLETIONS_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as handle:
            payload = json.loads(handle.read().decode("utf-8", "replace"))
    except Exception as exc:
        return FireworksVisionResult(ok=False, status="fireworks_request_failed",
                                     stderr=str(exc), model=chosen)
    text = ""
    try:
        text = str(payload["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        return FireworksVisionResult(ok=False, status="unexpected_response_format", model=chosen)
    if not text:
        return FireworksVisionResult(ok=False, status="empty_kimi_reply", model=chosen)
    return FireworksVisionResult(ok=True, output=text, status="ok", model=chosen)


__all__ = ["ARM_ID", "DEFAULT_VISION_MODEL", "FireworksVisionResult", "describe_image_fireworks"]
