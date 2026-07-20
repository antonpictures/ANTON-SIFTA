#!/usr/bin/env python3
"""Local-LLM council and truthful economy view for Carpenter Pong.

Every swimmer contributes one compact observation to a batched prompt. One
local Ollama call advises both swarms without chain-of-thought; the simulation
still lets every swimmer combine that advice with its own sense and the field.
This keeps inference proportional to councils, not swimmers.

Canonical STGM is read-only here. The pressure estimate is game telemetry and
never mints, spends, or claims Alice's wallet balance.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


OLLAMA_URL = "http://127.0.0.1:11434/api/chat"


@dataclass(frozen=True)
class SideAdvice:
    target_y: float
    confidence: float


@dataclass(frozen=True)
class ChorusAdvice:
    left: SideAdvice
    right: SideAdvice
    model: str
    latency_s: float
    created_at: float
    council_digest: str


def _clamp(value: Any, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return (lo + hi) / 2.0


def parse_chorus_reply(text: str, *, model: str, council_digest: str, latency_s: float = 0.0) -> ChorusAdvice:
    """Parse strict JSON, tolerating a model wrapping it in a code fence."""
    raw = str(text or "").strip()
    fenced = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if fenced:
        raw = fenced.group(0)
    data = json.loads(raw)

    def side(name: str) -> SideAdvice:
        row = data.get(name) if isinstance(data, dict) else None
        if not isinstance(row, dict):
            raise ValueError(f"missing {name} advice")
        return SideAdvice(
            target_y=_clamp(row.get("target_y"), 0.02, 0.98),
            confidence=_clamp(row.get("confidence"), 0.0, 1.0),
        )

    return ChorusAdvice(
        left=side("left"),
        right=side("right"),
        model=str(model),
        latency_s=max(0.0, float(latency_s)),
        created_at=time.time(),
        council_digest=str(council_digest),
    )


def build_chorus_prompt(snapshot: dict[str, Any], observations: dict[str, list[dict[str, Any]]]) -> str:
    """Build one compact council packet containing every swimmer observation."""
    packet = {
        "ball": snapshot.get("ball", {}),
        "paddles": {
            "left": (snapshot.get("left") or {}).get("paddle_y"),
            "right": (snapshot.get("right") or {}).get("paddle_y"),
        },
        "fields": {
            "left": (snapshot.get("left") or {}).get("field_centroid"),
            "right": (snapshot.get("right") or {}).get("field_centroid"),
        },
        "swimmer_observations": observations,
    }
    return (
        "You are the no-thinking cortex adviser for two Carpenter Pong swarms. "
        "Every listed swimmer has spoken through one local observation. Read the "
        "whole council, predict where each paddle should center, and return JSON only: "
        '{"left":{"target_y":0.0,"confidence":0.0},'
        '"right":{"target_y":0.0,"confidence":0.0}}. '
        "target_y and confidence must be numbers from 0 to 1. Do not explain.\n"
        + json.dumps(packet, sort_keys=True, separators=(",", ":"))
    )


def ask_local_ollama(
    prompt: str,
    *,
    model: str,
    council_digest: str,
    timeout_s: float = 45.0,
) -> ChorusAdvice:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return only the requested compact JSON. No chain-of-thought."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "format": "json",
        "keep_alive": "5m",
        "options": {
            "temperature": 0.0,
            "num_ctx": 8192,
            "num_predict": 80,
        },
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=max(1.0, float(timeout_s))) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"local Ollama council failed: {type(exc).__name__}: {exc}") from exc
    message = data.get("message") if isinstance(data, dict) else None
    content = message.get("content") if isinstance(message, dict) else ""
    return parse_chorus_reply(
        str(content or ""),
        model=model,
        council_digest=council_digest,
        latency_s=time.monotonic() - started,
    )


def canonical_stgm_read_only() -> dict[str, Any]:
    """Read body economy truth without creating a wallet transaction."""
    try:
        from System.stgm_economy import stgm_body_truth_snapshot

        data = stgm_body_truth_snapshot(max_cache_age_s=300.0)
        return {
            "available": True,
            "balance_stgm": float(data.get("spendable_total_stgm") or data.get("canonical_wallet_sum") or 0.0),
            "label": str(data.get("visible_topbar_text_9dp") or "STGM 0.000000000"),
            "source": "repair_log.jsonl",
            "mode": "read_only_no_spend",
        }
    except Exception as exc:
        return {
            "available": False,
            "balance_stgm": 0.0,
            "label": "STGM unavailable",
            "source": "repair_log.jsonl",
            "mode": "read_only_no_spend",
            "error": f"{type(exc).__name__}: {exc}",
        }


__all__ = [
    "ChorusAdvice",
    "SideAdvice",
    "ask_local_ollama",
    "build_chorus_prompt",
    "canonical_stgm_read_only",
    "parse_chorus_reply",
]
