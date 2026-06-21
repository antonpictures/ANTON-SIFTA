#!/usr/bin/env python3
"""System-prompt budget governor (r216).

George 2026-05-31: a Kimi turn hung ~90s with sysprompt_chars=140996 (~35k tokens).
The base system prompt is built from ~40 context builders; a few of them (memory /
recall excerpts, page text, diary tails) can run unbounded and bloat every turn —
slow prefill on a cloud cortex, and real $ at $0.95/Mtoken input.

This governor bounds the prompt WITHOUT me having to guess which builder ran hot:
  1. Per-block cap — no single block may exceed ``per_block_max``.
  2. Total budget — if the assembled parts still exceed ``total_max``, water-fill a
     single cap C (binary search) and trim every block longer than C down to C.
It NEVER drops a block entirely (every block keeps at least a grounding head down to
``min_block``), so identity / effector-truth / runtime-contract blocks — which are all
small — pass through untouched; only runaway excerpt blocks get trimmed, with a marker
pointing at the receipts that hold the full data.

Pure stdlib, deterministic, side-effect free. Tested.
"""
from __future__ import annotations

import os
from typing import Any

_MARKER = " […trimmed for context budget; full data lives in my receipts]"
_LIVE_MARKER = "\n\n[…trimmed for live cortex dispatch budget; full context remains in receipts]\n\n"
_SEP_LEN = 2  # "\n\n" join separator between blocks
_TEACHER_CORTEX_PREFIXES = (
    "antigravity:",
    "claude:",
    "cline:",
    "codex:",
    "grok:",
    "mimo:",
    "qwen:",
    "xai:",
)


def _env_int(name: str, default: int) -> int:
    try:
        v = int(str(os.environ.get(name, "")).strip())
        return v if v > 0 else default
    except Exception:
        return default


def _bounded_env_int(name: str, default: int, *, floor: int, ceiling: int) -> int:
    return max(floor, min(ceiling, _env_int(name, default)))


def clamp_prompt_parts(
    parts: list[str],
    *,
    total_max: int = 48000,
    per_block_max: int = 6000,
    min_block: int = 300,
    marker: str = _MARKER,
    protected_prefixes: tuple[str, ...] = (),
) -> tuple[list[str], dict[str, Any]]:
    """Bound a list of system-prompt blocks to a character budget.

    Returns ``(clamped_parts, report)``. ``report`` carries orig/final char counts and
    how many blocks were trimmed — for honest logging. Order is preserved; no block is
    removed. Small blocks (the core grounding) are never touched when the fat ones are
    the cause of the overflow."""
    blocks = [p for p in parts if p]
    orig = sum(len(b) for b in blocks)
    report: dict[str, Any] = {
        "orig_chars": orig, "blocks": len(blocks),
        "total_max": total_max, "per_block_max": per_block_max,
        "trimmed_blocks": 0, "applied": False,
    }

    def _is_protected(block: str) -> bool:
        head = (block or "").lstrip()
        return any(head.startswith(prefix) for prefix in protected_prefixes if prefix)

    protected = [_is_protected(b) for b in blocks]

    def _cap(block: str, cap: int) -> str:
        if len(block) <= cap:
            return block
        return block[: max(0, cap - len(marker))].rstrip() + marker

    # Stage 1 — per-block hard cap.
    capped = [b if keep else _cap(b, per_block_max) for b, keep in zip(blocks, protected)]
    report["trimmed_blocks"] = sum(1 for a, b in zip(blocks, capped) if a != b)

    def _total(bs: list[str]) -> int:
        return sum(len(b) for b in bs) + _SEP_LEN * max(0, len(bs) - 1)

    # Stage 2 — water-fill total budget if still over.
    if _total(capped) > total_max and capped:
        lens = [len(b) for b in capped]
        lo, hi, best = min_block, max(lens), min_block
        while lo <= hi:
            mid = (lo + hi) // 2
            proposed = sum(
                l if keep else min(l, mid)
                for l, keep in zip(lens, protected)
            ) + _SEP_LEN * max(0, len(lens) - 1)
            if proposed <= total_max:
                best, lo = mid, mid + 1
            else:
                hi = mid - 1
        capped = [b if keep else _cap(b, best) for b, keep in zip(capped, protected)]
        report["water_fill_cap"] = best
        report["trimmed_blocks"] = sum(1 for a, b in zip(blocks, capped) if a != b)

    report["final_chars"] = sum(len(b) for b in capped)
    report["applied"] = report["final_chars"] < orig
    return capped, report


def clamp_for_env(parts: list[str]) -> tuple[list[str], dict[str, Any]]:
    """Convenience wrapper honouring owner overrides:
    SIFTA_SYSPROMPT_BASE_BUDGET (total) and SIFTA_SYSPROMPT_BLOCK_MAX (per-block)."""
    return clamp_prompt_parts(
        parts,
        total_max=_env_int("SIFTA_SYSPROMPT_BASE_BUDGET", 48000),
        per_block_max=_env_int("SIFTA_SYSPROMPT_BLOCK_MAX", 6000),
        protected_prefixes=(
            "CORTEX BOOT IDENTITY CONTRACT",
            "MY PHYSICAL IDENTITY",
            "UNTRUTHFUL PHRASES",
            "MY LANGUAGE SELF-GOVERNANCE",
            "ALICE_SELF_ADDRESSING",
            "OWNER CAMERA / WATCHING-ME QUESTION",
            "LOCAL SCREENSHOT / IMAGE PATH",
            "RUNTIME CONSTRAINTS",
            "WALL CLOCK GROUND TRUTH",
            "TIME ACCESS PROTOCOL",
            "FALSE REFUSAL QUARANTINE",
            "RESIDUE METABOLISM SELF-KNOWLEDGE",
            "LOCAL IDENTITY BOUNDARY",
            "IDE DOCTORS vs ONE LARYNX",
            "ALICE SELF ORGAN",
            "COMPOSITE IDENTITY",
            "STIGMERGIC SPEECH POTENTIAL",
            "SIFTA APP SLOT",
            "ACE APP BRIEF",
            "CURRENT FOCUSED APP",
            "CO-WATCH RECEIPTS",
            "WHAT I CAN DO",
            "LIVE HUMAN CONVERSATION STYLE",
            "STIGMERGIC APP ATTENTION BIAS",
            "GENERIC APP AWARENESS",
        ),
    )


def dedupe_prompt_text(text: str, *, min_len: int = 80) -> tuple[str, dict[str, Any]]:
    """Collapse EXACT-duplicate paragraphs in an assembled system prompt (r794).

    George 2026-06-08: the ~80k prompt is Alice's body / OS self-knowledge — she
    MUST keep knowing it, so we may NOT trim it away. But ~40 context builders
    restate the same body / organ / app / identity paragraphs across protected
    blocks, and clamp_prompt_parts is forbidden from touching protected blocks.
    Dedupe is the safe cut: it drops only a paragraph that is a character-for-
    character repeat of one already kept (length >= ``min_len`` so short headers
    and separators stay), preserving every UNIQUE fact. The whole prompt is one
    system message, so a paragraph kept once is still seen by the cortex —
    dropping its later exact copies loses nothing she knows.

    Deterministic, side-effect free. Returns ``(deduped_text, report)``.
    """
    if not text:
        return text, {
            "orig_chars": 0, "final_chars": 0,
            "removed_paragraphs": 0, "removed_chars": 0, "applied": False,
        }
    paragraphs = text.split("\n\n")
    seen: set[str] = set()
    kept: list[str] = []
    removed = 0
    for p in paragraphs:
        key = p.strip()
        if len(key) >= min_len and key in seen:
            removed += 1
            continue
        if len(key) >= min_len:
            seen.add(key)
        kept.append(p)
    out = "\n\n".join(kept)
    return out, {
        "orig_chars": len(text),
        "final_chars": len(out),
        "removed_paragraphs": removed,
        "removed_chars": len(text) - len(out),
        "applied": len(out) < len(text),
    }


def live_turn_budget_for_model(model: str | None = None) -> int:
    """Return the hard foreground-dispatch system-prompt budget for a cortex model.

    The base governor protects identity/body blocks. This live-turn budget is stricter:
    foreground teacher/cortex calls must answer before the owner times out, so an
    oversized assembled prompt gets a final head+tail clamp even when earlier protected
    blocks were preserved.
    """
    m = (model or "").strip().lower()
    if m.startswith(_TEACHER_CORTEX_PREFIXES):
        return _bounded_env_int(
            "SIFTA_LIVE_TEACHER_SYSPROMPT_BUDGET",
            36000,
            floor=12000,
            ceiling=64000,
        )
    return _bounded_env_int(
        "SIFTA_LIVE_CORTEX_SYSPROMPT_BUDGET",
        48000,
        floor=12000,
        ceiling=96000,
    )


def _trim_middle_keep_head_tail(text: str, max_chars: int, *, marker: str = _LIVE_MARKER) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= len(marker) + 20:
        return text[:max_chars]
    remaining = max_chars - len(marker)
    head_chars = int(remaining * 0.70)
    tail_chars = remaining - head_chars
    return text[:head_chars].rstrip() + marker + text[-tail_chars:].lstrip()


def clamp_live_turn_prompt(
    text: str,
    *,
    model: str | None = None,
    max_chars: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Hard-clamp an assembled foreground system prompt before cortex dispatch.

    This intentionally ignores protected-prefix exemptions because it runs after the
    covenant/body prompt has already been assembled. It keeps the beginning and the
    live tail, which preserves stable identity plus the most recent screen/body
    receipts while removing middle bloat that causes prefill timeouts.
    """
    original = text or ""
    deduped, dedupe_report = dedupe_prompt_text(original)
    budget = max_chars if max_chars is not None else live_turn_budget_for_model(model)
    budget = max(1200, int(budget))
    clamped = _trim_middle_keep_head_tail(deduped, budget)
    return clamped, {
        "orig_chars": len(original),
        "deduped_chars": len(deduped),
        "final_chars": len(clamped),
        "max_chars": budget,
        "model": model or "",
        "dedupe_removed_chars": dedupe_report.get("removed_chars", 0),
        "middle_trimmed_chars": max(0, len(deduped) - len(clamped)),
        "applied": len(clamped) < len(original),
    }


__all__ = [
    "clamp_prompt_parts",
    "clamp_for_env",
    "dedupe_prompt_text",
    "live_turn_budget_for_model",
    "clamp_live_turn_prompt",
]
