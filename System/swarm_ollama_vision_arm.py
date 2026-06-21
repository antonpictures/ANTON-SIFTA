#!/usr/bin/env python3
"""Local vision arm — Alice's LOCAL eye for images (r210).

George 2026-05-31: "why is claude always used to detect the image if I have
another cortex selected? I now have the local cortex." The describe path only
knew cloud agent eyes (claude→codex→grok→qwen→cline), so a LOCAL ollama cortex
had no eye of its own and always fell to claude_agent (priority 1).

This arm gives a local cortex its own eye: it base64-encodes the on-screen
screenshot and POSTs it to a locally-installed Ollama vision model
(llama3.2-vision / llava / qwen2-vl / the cached Qwen2-VL family) via
/api/generate with `images=[...]`. No cloud, no per-image cost, stays on the
owner's silicon. If no local vision model is installed or Ollama is offline,
this arm reports an honest failure and the caller fails over to a cloud eye
WITH an owner-facing note — never a silent claude default.

Pure stdlib (urllib + base64 + json). The eye that runs on the owner's own
electricity. 🐜⚡
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Local vision-model name fragments. Kept in sync with
# swarm_cortex_capabilities.LOCAL_VISION_NEEDLES; duplicated here so this arm
# has no import cycle and can stand alone.
_LOCAL_VISION_NEEDLES: tuple[str, ...] = (
    "vision", "llava", "bakllava", "moondream", "minicpm",
    "qwen-vl", "qwen2-vl", "qwen2.5-vl", "qwen2.5vl",
    "internvl", "phi-3.5-vision", "llama3.2-vision", "granite3.2-vision",
    # Gemma multimodal family — George 2026-05-31 designated gemma4 as Alice's local
    # eye for text-only cortexes (deepseek, gpt-oss, …). gemma3 4B+ and the SIFTA
    # gemma4-alice cortex carry a vision head.
    "gemma4", "gemma-4", "gemma3", "gemma-3", "sifta-gemma4-alice",
)
# Preferred local eye, in order: George's designated gemma4 first, then any other
# installed vision model. The cortex he TYPES can be text-only; the EYE he borrows
# should be his local gemma4, not a paid cloud arm.
# George 2026-06-18: Krishna (krishairnd/Gemma-4) is the default local image/video eye —
# reuse the warm Ollama cortex instead of loading a second MLX VLM into RAM.
LOCAL_VISION_EYE_DEFAULT = "krishairnd/Gemma-4-Uncensored:latest"  # r1386: renamed identifier only; real Ollama tag unchanged
_PREFERRED_VISION_NEEDLES: tuple[str, ...] = (
    "krishairnd/gemma-4-uncensored",
    "sifta-gemma4-alice",
    "gemma4",
    "gemma-4",
    "gemma3",
    "gemma-3",
)
_DEFAULT_HOST = "http://127.0.0.1:11434"
_VISION_EYE_OVERRIDE_FILE = "local_vision_eye.txt"  # owner names the exact tag here

ARM_ID = "ollama_vision_agent"


def _state_dir(state_dir=None):
    from pathlib import Path as _P
    if state_dir is None:
        return _P(__file__).resolve().parents[1] / ".sifta_state"
    p = _P(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _configured_eye(state_dir=None) -> str:
    """Owner-named local vision tag (no hardcoding): env SIFTA_LOCAL_VISION_EYE or
    .sifta_state/local_vision_eye.txt. Empty if not set."""
    val = os.environ.get("SIFTA_LOCAL_VISION_EYE", "").strip()
    if val:
        return val
    try:
        return (_state_dir(state_dir) / _VISION_EYE_OVERRIDE_FILE).read_text(encoding="utf-8").strip()
    except Exception:
        return ""


@dataclass(frozen=True)
class LocalVisionResult:
    """Shaped like swarm_agent_arm_launcher.AgentArmResult so describe_current_photo
    can read ``.ok`` and ``.output`` uniformly regardless of which eye answered."""
    ok: bool
    output: str = ""
    status: str = ""
    arm_id: str = ARM_ID
    model: str = ""
    stderr: str = ""


def _ollama_tags(host: str = _DEFAULT_HOST, timeout: float = 2.0) -> list[str]:
    """Names of models actually installed on local Ollama. [] if offline."""
    try:
        req = urllib.request.Request(
            f"{host.rstrip('/')}/api/tags", headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as handle:
            payload = json.loads(handle.read().decode("utf-8", "replace"))
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    names: list[str] = []
    for entry in payload.get("models") or []:
        if isinstance(entry, dict):
            name = str(entry.get("name") or entry.get("model") or "").strip()
            if name:
                names.append(name)
    return names


def pick_local_vision_model(
    *, host: str = _DEFAULT_HOST, timeout: float = 2.0,
    installed: Optional[list[str]] = None, state_dir=None,
) -> str:
    """The local Ollama model Alice should use as her eye, or "".

    Order (George 2026-05-31): (1) the owner-named tag if it is installed; (2) the
    designated gemma4 local eye (then other gemma) — so a text-only cortex like
    deepseek/gpt-oss borrows gemma4, not a paid cloud arm; (3) any other installed
    vision model. Truth boundary: only reports what /api/tags returns. Empty means
    'no local eye' and the caller fails over to cloud with an honest note."""
    tags = installed if installed is not None else _ollama_tags(host=host, timeout=timeout)
    lows = [(name, name.lower()) for name in tags]
    # (1) owner override, if actually installed
    want = _configured_eye(state_dir).lower()
    if want:
        for name, low in lows:
            if want == low or want in low:
                return name
    # (2) designated gemma4 eye first, then other gemma
    for needle in _PREFERRED_VISION_NEEDLES:
        for name, low in lows:
            if needle in low:
                return name
    # (3) any other vision-capable local model
    for name, low in lows:
        if any(n in low for n in _LOCAL_VISION_NEEDLES):
            return name
    return ""


def local_vision_available(
    *, host: str = _DEFAULT_HOST, timeout: float = 2.0,
    installed: Optional[list[str]] = None, state_dir=None,
) -> bool:
    return bool(pick_local_vision_model(host=host, timeout=timeout,
                                        installed=installed, state_dir=state_dir))


def describe_image_local(
    image_path: str,
    prompt: str,
    *,
    model: str = "",
    host: str = _DEFAULT_HOST,
    timeout_s: float = 300.0,
    tags_timeout: float = 2.0,
    state_dir=None,
) -> LocalVisionResult:
    """Let a LOCAL Ollama vision model look at the screenshot and describe it.

    Returns a LocalVisionResult; ``ok`` is True only when a local vision model
    actually answered with non-empty text. On any miss (no model, Ollama down,
    empty answer) ``ok`` is False with an honest ``status`` so the caller fails
    over to a cloud eye and tells the owner why."""
    p = Path(image_path)
    if not image_path or not p.exists():
        return LocalVisionResult(ok=False, status="image_missing")
    chosen = (model or "").strip() or pick_local_vision_model(
        host=host, timeout=tags_timeout, state_dir=state_dir)
    if not chosen:
        return LocalVisionResult(ok=False, status="no_local_vision_model_installed")
    try:
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    except Exception as exc:
        return LocalVisionResult(ok=False, status="image_read_failed", stderr=str(exc), model=chosen)
    body = json.dumps({
        "model": chosen,
        "prompt": prompt,
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0.2},
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{host.rstrip('/')}/api/generate",
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as handle:
            payload = json.loads(handle.read().decode("utf-8", "replace"))
    except Exception as exc:
        return LocalVisionResult(ok=False, status="ollama_request_failed",
                                 stderr=str(exc), model=chosen)
    text = ""
    if isinstance(payload, dict):
        text = str(payload.get("response") or "").strip()
    if not text:
        return LocalVisionResult(ok=False, status="empty_local_vision_reply", model=chosen)
    return LocalVisionResult(ok=True, output=text, status="ok", model=chosen)


__all__ = [
    "ARM_ID", "LocalVisionResult", "pick_local_vision_model",
    "local_vision_available", "describe_image_local",
]
