#!/usr/bin/env python3
"""swarm_needle_tool_router.py — r1623-02: tiny tool-intent router (no 26M model yet).

Fahd dirt: Needle ~26M tool-caller. Until pulled, this pure classifier routes
owner intent to effector classes so the fat cortex is not required for every
open-browser / switch / self-code decision.

Truth label: NEEDLE_TOOL_ROUTER_V1
"""

from __future__ import annotations

import re
from typing import Any

TRUTH_LABEL = "NEEDLE_TOOL_ROUTER_V1"

_RULES: tuple[tuple[str, re.Pattern[str], float], ...] = (
    (
        "self_code",
        re.compile(
            r"\bSELF_CODE_|\bSELF_READ\b|\bcode\s+R\d{3,4}\b|\bgo\b.{0,40}\bcode\b|"
            r"\bself[\s_-]?code\b|\brewrite\s+your\s+body\b",
            re.I,
        ),
        0.95,
    ),
    (
        "cortex_switch",
        re.compile(
            r"\bswitch\b.{0,40}\b(?:cortex|core\s*text|brain|model)\b|"
            r"\b(?:cortex|model)\b.{0,20}\bto\b",
            re.I,
        ),
        0.9,
    ),
    (
        "browser_open",
        re.compile(
            r"\b(?:open|navigate|go\s+to|load)\b.{0,60}\b(?:https?://|instagram|ebay|"
            r"youtube|browser|tab)\b",
            re.I,
        ),
        0.88,
    ),
    (
        "browser_search",
        re.compile(
            r"\bsearch\b.{0,40}\b(?:for|on)\b|\bgoogle\b|\bduckduckgo\b",
            re.I,
        ),
        0.85,
    ),
    (
        "describe_page",
        re.compile(
            r"\bdescribe\b.{0,40}\b(?:page|item|screen|instagram|ebay)\b|"
            r"\bwhat\s+(?:page|tab)\b",
            re.I,
        ),
        0.85,
    ),
    (
        "describe_body",
        re.compile(
            r"\bdescribe\s+yourself\b|\btalk\s+about\s+your\s+body\b|\bwhat\s+are\s+you\b",
            re.I,
        ),
        0.8,
    ),
    (
        "chat",
        re.compile(r".", re.I),
        0.1,
    ),
)


def route_tool_intent(text: str) -> dict[str, Any]:
    """Classify owner turn into a tool lane. Deterministic, offline."""
    t = str(text or "").strip()
    if not t:
        return {
            "truth_label": TRUTH_LABEL,
            "intent": "empty",
            "confidence": 0.0,
            "use_fat_cortex": False,
            "reason": "empty",
        }
    for name, pattern, conf in _RULES:
        if name == "chat":
            continue
        if pattern.search(t):
            fat = name in {"chat", "describe_body"} or conf < 0.5
            # self_code and switch still need cortex for content, but lane is clear
            use_fat = name not in {"browser_open"}  # pure open can be effector-first later
            if name in {"self_code", "describe_page", "describe_body", "cortex_switch"}:
                use_fat = True
            return {
                "truth_label": TRUTH_LABEL,
                "intent": name,
                "confidence": conf,
                "use_fat_cortex": use_fat,
                "reason": f"matched_{name}",
                "needle_model_status": "not_pulled_use_rules",
            }
    return {
        "truth_label": TRUTH_LABEL,
        "intent": "chat",
        "confidence": 0.1,
        "use_fat_cortex": True,
        "reason": "default_chat",
        "needle_model_status": "not_pulled_use_rules",
    }


def needle_probe_status() -> dict[str, Any]:
    """Honest: has a Needle-class Ollama tag been installed?"""
    tags: tuple[str, ...] = ()
    try:
        from System.sifta_inference_defaults import probe_installed_ollama_tags

        tags = probe_installed_ollama_tags() or ()
    except Exception as exc:
        return {
            "ok": False,
            "installed": False,
            "error": f"{type(exc).__name__}: {exc}",
            "truth_label": TRUTH_LABEL,
        }
    hits = [t for t in tags if "needle" in str(t).lower()]
    return {
        "ok": True,
        "installed": bool(hits),
        "tags": hits,
        "truth_label": TRUTH_LABEL,
        "note": "rules router active until needle tag present",
    }


__all__ = ["TRUTH_LABEL", "route_tool_intent", "needle_probe_status"]
