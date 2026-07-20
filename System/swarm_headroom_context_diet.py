#!/usr/bin/env python3
"""swarm_headroom_context_diet.py — r1623-01: Headroom-style token diet for local cortex.

Fahd dirt: Headroom + Ollama cut agent tokens ~90%. We already have
`swarm_sysprompt_budget.clamp_for_env`. This organ adds a *local-first*
aggressive diet: protect soul/host/self-code blocks, slash fat excerpts harder
when the active mind is a local Ollama tag (stalls at 90s prefill).

Does not call external Headroom service — local pure clamp with receipts.

Truth label: HEADROOM_CONTEXT_DIET_V1
"""

from __future__ import annotations

import os
import re
from typing import Any

TRUTH_LABEL = "HEADROOM_CONTEXT_DIET_V1"

# Keep these heads even under aggressive local diet.
_PROTECTED_PREFIXES: tuple[str, ...] = (
    "HOST TEACHING",
    "BODY FROM RECEIPTS",
    "LIVE ALICE BROWSER RECEIPT",
    "BROWSER TIME SENSE",
    "NUMBERED OWNER QUESTIONS",
    "SELF-CODE READY",
    "SELF-CODING HAND",
    "THIS TURN IS ALICE SELF-CODING",
    "BODY CODE FROM DISK",
    "CORTEX BOOT IDENTITY",
    "MY PHYSICAL IDENTITY",
    "WALL CLOCK GROUND TRUTH",
    "RUNTIME CONSTRAINTS",
    "FALSE REFUSAL QUARANTINE",
    "COMPOSITE IDENTITY",
    "SELF-PLAN",
    "ACTIVE PLAN",
    "CAMPAIGN R1621",
)


def _env_int(name: str, default: int) -> int:
    try:
        v = int(str(os.environ.get(name, "")).strip())
        return v if v > 0 else default
    except Exception:
        return default


def is_local_ollama_mind(model_id: str) -> bool:
    mid = str(model_id or "").strip().lower()
    if not mid:
        return False
    if mid.startswith(
        (
            "claude:",
            "codex:",
            "grok:",
            "mimo:",
            "qwen:",
            "cline:",
            "antigravity:",
            "accounts/",
        )
    ):
        return False
    if "fireworks" in mid or "openai" in mid:
        return False
    # bare ollama tags: name:tag or name
    return ":" in mid or bool(re.match(r"^[a-z0-9][\w./-]{2,120}$", mid))


def diet_prompt_parts(
    parts: list[str],
    *,
    model_id: str = "",
    force_local: bool = False,
) -> tuple[list[str], dict[str, Any]]:
    """Clamp parts for local minds more aggressively than cloud defaults."""
    from System.swarm_sysprompt_budget import clamp_prompt_parts, dedupe_prompt_text

    local = force_local or is_local_ollama_mind(model_id)
    # Local default ~18k chars (~4.5k tokens) hard ceiling; cloud keeps 48k env default.
    total_max = _env_int(
        "SIFTA_HEADROOM_LOCAL_BUDGET" if local else "SIFTA_SYSPROMPT_BASE_BUDGET",
        18000 if local else 48000,
    )
    per_block = _env_int(
        "SIFTA_HEADROOM_LOCAL_BLOCK_MAX" if local else "SIFTA_SYSPROMPT_BLOCK_MAX",
        2400 if local else 6000,
    )
    clamped, report = clamp_prompt_parts(
        list(parts or []),
        total_max=total_max,
        per_block_max=per_block,
        min_block=220 if local else 300,
        protected_prefixes=_PROTECTED_PREFIXES,
    )
    # Paragraph-level exact dedupe on joined text, then re-split for report honesty.
    joined = "\n\n".join(clamped)
    deduped, drep = dedupe_prompt_text(joined, min_len=60)
    final_parts = [p for p in deduped.split("\n\n") if p]
    report = dict(report)
    report.update(
        {
            "truth_label": TRUTH_LABEL,
            "local_diet": local,
            "model_id": str(model_id or ""),
            "dedupe_removed_paragraphs": drep.get("removed_paragraphs", 0),
            "final_chars_after_dedupe": len(deduped),
            "orig_parts": len(parts or []),
            "final_parts": len(final_parts),
        }
    )
    return final_parts, report


def diet_report_line(report: dict[str, Any]) -> str:
    if not report:
        return ""
    return (
        f"[headroom diet local={report.get('local_diet')} "
        f"chars {report.get('orig_chars')}→{report.get('final_chars_after_dedupe', report.get('final_chars'))} "
        f"trimmed_blocks={report.get('trimmed_blocks')}]"
    )


__all__ = [
    "TRUTH_LABEL",
    "is_local_ollama_mind",
    "diet_prompt_parts",
    "diet_report_line",
]
