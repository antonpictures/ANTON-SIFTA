#!/usr/bin/env python3
"""alice_reply_sanity.py — is this line an ANSWER, or processing narration?

Architect, 2026-09-30 (verbatim): "seems like she is getting gagged".

What he was looking at, read back from ``.sifta_state/alice_thinking_state.json``:

    model:  AliceG4U:latest          (a 6.3 GB local cortex)
    topic:  a dense technical paste, truncated to the 240-char status limit
    reply:  "(silent) $\\rightarrow$ ABSORBING HIGH DENSITY KNOWLEDGE PACKET...
             $\\leftarrow$ Processing via Cortex LLM Chain: $(\\text{Claude }...)

That is not a refusal and not a policy gag. It is a small model narrating *about
processing* instead of answering, and the status organ storing it as her reply.
She was not silenced; she stalled, and the surface had no way to tell the
difference. This module is that way.

WHAT IT IS
    A narration detector with an explicit, auditable vocabulary. It answers one
    question: does this text describe the act of thinking rather than say
    something to George? A flagged line is not evidence of anything except that
    the cortex produced no answer.

WHAT IT IS NOT
    Not a truth check, not a quality score, not a content filter, and it never
    rewrites or censors a reply. A false negative (narration that slips through)
    is acceptable; a false positive that swallows a real answer is not, so the
    threshold requires a marker plus noise, or two markers.

Callers decide what to do with the verdict. ``swarm_alice_thinking_state`` records
the verdict beside the reply instead of passing narration off as an answer.
"""
from __future__ import annotations

import re
from typing import Any

# Vocabulary observed in real stalled turns, plus the neighbouring family of
# "machine is doing something" verbs. Kept short deliberately: every entry is a
# phrase a normal answer rarely needs.
NARRATION_MARKERS: tuple[str, ...] = (
    "absorbing",
    "assimilating",
    "high density",
    "knowledge packet",
    "processing via",
    "cortex llm chain",
    "context metadata",
    "decrypting",
    "initializing cortex",
    "compiling response",
    "quantum",
    "stigmergic upload",
)

# Markers that are strong enough on their own to mean narration.
HARD_MARKERS: tuple[str, ...] = (
    "high density knowledge",
    "cortex llm chain",
    "knowledge packet",
    "system note",
    "processing via",
)

# Decorative noise that small models emit when they are stalling: LaTeX arrows,
# arrow glyphs, and bracketed "system" labels.
_NOISE = re.compile(r"\\rightarrow|\\leftarrow|\\text\{|→|←|\[SYSTEM[^\]]*\]", re.IGNORECASE)
_BARE_SILENT = re.compile(r"^\s*[\(\[]?\s*silent\s*[\)\]]?\s*$", re.IGNORECASE)
_HEX_TAG = re.compile(r"#[0-9a-f]{6,}\b", re.IGNORECASE)


def narration_markers(text: str) -> list[str]:
    """Every narration marker present, lowercased and de-duplicated."""
    lowered = str(text or "").lower()
    return sorted({marker for marker in NARRATION_MARKERS if marker in lowered})


def is_processing_narration(text: str) -> bool:
    """True when the text narrates processing instead of answering.

    Flagged when one hard marker is present, when two or more markers appear, or
    when a marker appears together with decorative/status noise.
    """
    body = str(text or "").strip()
    if not body:
        return False
    if _BARE_SILENT.match(body):
        return True
    lowered = body.lower()
    if any(marker in lowered for marker in HARD_MARKERS):
        return True
    hits = narration_markers(body)
    if len(hits) >= 2:
        return True
    noise = bool(_NOISE.search(body)) or bool(_HEX_TAG.search(body))
    return bool(hits) and noise


def flag_reply(text: str) -> dict[str, Any]:
    """One verdict object: the boolean plus the reasons that produced it.

    The reasons are recorded so a flagged turn can be audited later instead of
    being taken on faith, and so the vocabulary can be corrected when it is
    wrong.
    """
    body = str(text or "")
    hits = narration_markers(body)
    noise: list[str] = []
    if _NOISE.search(body):
        noise.append("decorative_or_status_noise")
    if _HEX_TAG.search(body):
        noise.append("hex_tag")
    if _BARE_SILENT.match(body.strip()):
        hits = hits + ["bare_silent"]
    return {
        "narration": is_processing_narration(body),
        "markers": hits,
        "noise": noise,
        "chars": len(body),
    }


def excerpt_for_status(text: str, limit: int = 160) -> str:
    """What the status strip should show for this reply.

    Narration is labelled as such rather than displayed as her words; the raw
    text is kept by the caller, never discarded.
    """
    verdict = flag_reply(text)
    if not verdict["narration"]:
        return str(text or "")[:limit]
    head = " ".join(str(text or "").split())[: max(0, limit - 60)]
    return f"(no answer — cortex emitted processing narration: {head})"[:limit]
