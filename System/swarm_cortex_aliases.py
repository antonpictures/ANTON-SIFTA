#!/usr/bin/env python3
"""Round 99 — Cortex aliases so Alice can switch her brain by name.

George's ask (2026-05-28): "if i tell alice to switch the qwen cortex to
deepseek she cn do it -- hard huh? so many settings , we have to find
names for everything"

This module is the alias layer over the canonical cortex tags from
``sifta_inference_defaults.py``. Instead of asking Alice (or the owner)
to type ``qwen:accounts/fireworks/models/gpt-oss-20b``, she can say
``cheap`` or ``drafter`` and the resolver finds the right tag.

The aliases are intentionally short, mood-tagged, owner-friendly. They
mirror the same pattern the arm aliases use in ``swarm_tool_router``
(``qwen`` / ``cline`` / ``kimi`` etc.). One alias table per layer.

Public surface
══════════════
    resolve_cortex_alias(name)  → canonical cortex tag (or "" if unknown)
    set_cortex_by_alias(name)   → writes swimmer_ollama_assignments.json
                                  and returns the receipt-shape dict
    list_aliases()              → dict[alias, canonical_tag] for the UI
    list_canonical_groups()     → dict[group_label, [alias, ...]] for prompts

Pure stdlib. Never raises out of the public API. Reuses the existing
``sifta_inference_defaults`` resolver + assignment writer so no two
sources of truth.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Mapping

try:
    from System.sifta_inference_defaults import (
        CANONICAL_CLOUD_CLAUDE,
        CANONICAL_CLOUD_CLINE,
        CANONICAL_CLOUD_CODEX,
        CANONICAL_CLOUD_GROK,
        CANONICAL_CLOUD_QWEN,
        CANONICAL_CLOUD_QWEN_LONG_DEEPSEEK_FLASH,
        CANONICAL_CLOUD_QWEN_PREMIUM_KIMI,
        CANONICAL_OLLAMA_DAILY,
        CANONICAL_OLLAMA_FALLBACK,
        CANONICAL_OLLAMA_GEMMA4_SMALL,
        CANONICAL_OLLAMA_LOW_RAM,
        CANONICAL_OLLAMA_REFLEX,
        set_default_ollama_model,
    )
except Exception:  # pragma: no cover - direct fallback so import never fails
    CANONICAL_CLOUD_CLAUDE = "claude:claude-code-cli-default"
    CANONICAL_CLOUD_CLINE = "cline:cline-cli-default"
    CANONICAL_CLOUD_CODEX = "codex:gpt-5.5"
    CANONICAL_CLOUD_GROK = "grok:grok-4.3"
    CANONICAL_CLOUD_QWEN = "qwen:accounts/fireworks/models/gpt-oss-20b"
    CANONICAL_CLOUD_QWEN_LONG_DEEPSEEK_FLASH = "qwen:accounts/fireworks/models/deepseek-v4-flash"
    CANONICAL_CLOUD_QWEN_PREMIUM_KIMI = "qwen:accounts/fireworks/models/kimi-k2p6"
    CANONICAL_OLLAMA_DAILY = "alice-m5-cortex-8b-6.3gb:latest"
    CANONICAL_OLLAMA_FALLBACK = "alice-Q-m1-scout-2.3b-2.7gb:latest"
    CANONICAL_OLLAMA_GEMMA4_SMALL = "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"
    CANONICAL_OLLAMA_LOW_RAM = "alice-m1-cortex-4.5b-3.4gb:latest"
    CANONICAL_OLLAMA_REFLEX = "sifta-classifier-c1-3.1b-6.2gb:latest"

    def set_default_ollama_model(model: str) -> dict:  # type: ignore
        return {"ok": False, "error": "import_failed", "model": model}


# ─── Alias table (case-insensitive lookup) ─────────────────────────────────

# Mood-tagged short names → canonical cortex tag. Multiple aliases may
# point at the same tag; that's intentional — different vocabulary lanes
# for different turn shapes (technical / colloquial / role-based).
CORTEX_ALIASES: dict[str, str] = {
    # ── cheap / fast cloud (gpt-oss-20b $0.07/M) ──
    "cheap":    CANONICAL_CLOUD_QWEN,
    "fast":     CANONICAL_CLOUD_QWEN,
    "drafter":  CANONICAL_CLOUD_QWEN,
    "router":   CANONICAL_CLOUD_QWEN,
    "draft":    CANONICAL_CLOUD_QWEN,
    "qwen":     CANONICAL_CLOUD_QWEN,
    "gpt-oss":  CANONICAL_CLOUD_QWEN,
    "20b":      CANONICAL_CLOUD_QWEN,

    # ── premium cloud (Kimi K2.6 $0.95/M + 262k + vision) ──
    "kimi":     CANONICAL_CLOUD_QWEN_PREMIUM_KIMI,
    "k2p6":     CANONICAL_CLOUD_QWEN_PREMIUM_KIMI,
    "vision":   CANONICAL_CLOUD_QWEN_PREMIUM_KIMI,
    "premium":  CANONICAL_CLOUD_QWEN_PREMIUM_KIMI,

    # ── long context (DeepSeek-V4-Flash 1M $0.14/M) ──
    "long":     CANONICAL_CLOUD_QWEN_LONG_DEEPSEEK_FLASH,
    "book":     CANONICAL_CLOUD_QWEN_LONG_DEEPSEEK_FLASH,
    "huge":     CANONICAL_CLOUD_QWEN_LONG_DEEPSEEK_FLASH,
    "deepseek": CANONICAL_CLOUD_QWEN_LONG_DEEPSEEK_FLASH,
    "v4-flash": CANONICAL_CLOUD_QWEN_LONG_DEEPSEEK_FLASH,

    # ── cloud teachers (CLI-OAuth based) ──
    "grok":   CANONICAL_CLOUD_GROK,
    "xai":    CANONICAL_CLOUD_GROK,
    "claude": CANONICAL_CLOUD_CLAUDE,
    "codex":  CANONICAL_CLOUD_CODEX,
    "cline":  CANONICAL_CLOUD_CLINE,

    # ── local cortices (private, no network, no $) ──
    "local":   CANONICAL_OLLAMA_DAILY,
    "default": CANONICAL_OLLAMA_DAILY,
    "smart":   CANONICAL_OLLAMA_DAILY,
    "m5":      CANONICAL_OLLAMA_DAILY,
    "8b":      CANONICAL_OLLAMA_DAILY,
    "private": CANONICAL_OLLAMA_DAILY,

    "tiny":   CANONICAL_OLLAMA_GEMMA4_SMALL,
    "small":  CANONICAL_OLLAMA_GEMMA4_SMALL,
    "gemma":  CANONICAL_OLLAMA_GEMMA4_SMALL,
    "5b":     CANONICAL_OLLAMA_GEMMA4_SMALL,

    "low-ram": CANONICAL_OLLAMA_LOW_RAM,
    "m1":      CANONICAL_OLLAMA_LOW_RAM,
    "4b":      CANONICAL_OLLAMA_LOW_RAM,

    "reflex":     CANONICAL_OLLAMA_REFLEX,
    "classifier": CANONICAL_OLLAMA_REFLEX,
    "scout":      CANONICAL_OLLAMA_FALLBACK,
}


# Friendly grouping for a "list available cortices" prompt block.
CORTEX_GROUPS: dict[str, tuple[str, ...]] = {
    "cheap_cloud_drafter":       ("cheap", "fast", "drafter", "router", "qwen", "gpt-oss", "20b"),
    "premium_cloud_vision":      ("kimi", "k2p6", "vision", "premium"),
    "long_context_cloud":        ("long", "book", "huge", "deepseek", "v4-flash"),
    "cloud_teacher_oauth":       ("grok", "xai", "claude", "codex", "cline"),
    "local_smart_8b":            ("local", "default", "smart", "m5", "8b", "private"),
    "local_small_5b":            ("tiny", "small", "gemma", "5b"),
    "local_low_ram_4b":          ("low-ram", "m1", "4b"),
    "local_reflex_classifier":   ("reflex", "classifier", "scout"),
}


def _norm(name: object) -> str:
    return str(name or "").strip().casefold()


def resolve_cortex_alias(name: str) -> str:
    """Return the canonical cortex tag for ``name``, or ``""`` if unknown.

    Pass-through: if ``name`` is already a canonical tag (contains ``:`` or
    starts with ``alice-``), return it unchanged. That lets callers chain
    ``set_default_ollama_model(resolve_cortex_alias(x))`` without branching.
    """
    raw = _norm(name)
    if not raw:
        return ""
    if ":" in raw or raw.startswith("alice-") or raw.startswith("sifta-"):
        return name  # already canonical
    return CORTEX_ALIASES.get(raw, "")


def list_aliases() -> dict[str, str]:
    """Return a copy of the alias table for UI / prompt rendering."""
    return dict(CORTEX_ALIASES)


def list_canonical_groups() -> dict[str, list[str]]:
    """Return ``CORTEX_GROUPS`` with list-of-aliases values (JSON friendly)."""
    return {k: list(v) for k, v in CORTEX_GROUPS.items()}


def set_cortex_by_alias(
    name: str,
    *,
    state_dir: str | Path | None = None,
) -> dict:
    """Set the default cortex by alias. Receipt-shape return.

    Returns a dict ``{ok, alias, resolved_tag, ts, reason}``. ``ok`` is True
    iff the alias resolved AND the assignment write succeeded.
    """
    raw = _norm(name)
    resolved = resolve_cortex_alias(name)
    out: dict = {
        "ok": False,
        "ts": time.time(),
        "alias": raw,
        "resolved_tag": resolved,
        "reason": "",
    }
    if not resolved:
        out["reason"] = (
            f"unknown alias {raw!r}; list_aliases() shows what's available"
        )
        return out
    try:
        result = set_default_ollama_model(resolved)
        if isinstance(result, dict) and result.get("ok") is False:
            out["reason"] = (
                f"set_default_ollama_model declined: "
                f"{result.get('error', 'unknown')}"
            )
            return out
        out["ok"] = True
        out["reason"] = f"cortex set to {resolved} via alias {raw!r}"
    except Exception as exc:
        out["reason"] = f"{type(exc).__name__}: {exc}"
    return out


def cortex_alias_prompt_block() -> str:
    """Short prompt block telling Alice what aliases she can use."""
    lines = ["CORTEX ALIASES (say or dispatch any of these):"]
    for group_name, aliases in CORTEX_GROUPS.items():
        canonical = CORTEX_ALIASES.get(aliases[0], "")
        lines.append(
            f"- {group_name}: {' / '.join(aliases)}  →  {canonical}"
        )
    lines.append(
        "Rule: switching cortex writes a receipted assignment; "
        "Alice can call set_cortex_by_alias herself for owner-asked switches."
    )
    return "\n".join(lines)


__all__ = [
    "CORTEX_ALIASES",
    "CORTEX_GROUPS",
    "cortex_alias_prompt_block",
    "list_aliases",
    "list_canonical_groups",
    "resolve_cortex_alias",
    "set_cortex_by_alias",
]
