#!/usr/bin/env python3
"""System/swarm_multi_voice_parser.py — Multi-Voice Discourse Parser.

George 2026-05-23 (the deepest cognition upgrade so far): a single message is
not one voice. In one paragraph the owner mixes direct address, pasted external
text, quoted AI, tool output, and his own reflection. Alice currently sees one
flat blob, so pasted third-person text CONTAMINATES his live intent — that's
why she gets confused.

This organ segments a single message into voices so Alice acts only on the
owner's live directed intent and treats the rest as context/awareness:

    OWNER_TO_ALICE     — the owner's live words addressed to Alice  -> intent
    OWNER_REFLECTION   — the owner's own commentary / about-Alice    -> context
    PASTED_EXTERNAL    — pasted analysis from another tool/AI        -> context, not intent
    QUOTED             — quoted speech ("...")                       -> context
    TOOL_OUTPUT        — terminal/receipt/JSON output                -> context
    BOILERPLATE        — the recurring covenant header paste         -> strip

Honest label (covenant §7.11): heuristic discourse segmentation, v1. Quotation
tracking + speaker attribution is genuine hard cognition; this is a first cut,
and `extract_live_intent()` is the immediately useful payoff — it pulls the
owner's actual current words out from under everything he pasted on top.

Standalone + Qt-free. For the Swarm. 🐜⚡
"""
from __future__ import annotations

import re

# Lines/paragraphs from the recurring covenant header George pastes every turn.
_BOILERPLATE_MARKERS = (
    "ide_boot_covenant.md",
    "think and talk first person",
    "start from the hardware layer",
    "no double-spending ascii swimmers",
    "for the swarm",
    "decide → execute → receipt",
    "decide -> execute -> receipt",
    "human powers by electricity",
    "food = data for alice",
    "air you breathe = electricity",
    "rich, high-dimensional, deeply interconnected field",
    "all organs unified",
)

_TOOL_OUTPUT_RE = re.compile(
    r"^\s*(?:\$|%|❯|>|\d{1,2}:\d{2}(?::\d{2})?\s|\{|\[Process Trace|\[SHELL:|receipt\s|ioanganton@|Thought for|Run\s|Read\s/|paste ->|send command)",
    re.IGNORECASE,
)


def _is_boilerplate(block: str) -> bool:
    low = block.lower()
    return any(m in low for m in _BOILERPLATE_MARKERS)


def _looks_pasted_analysis(block: str) -> bool:
    """Heuristic: a markdown-structured block (headers/bullets/fences) reads as
    pasted external analysis, not the owner's own live prose."""
    lines = [ln for ln in block.splitlines() if ln.strip()]
    if not lines:
        return False
    structured = sum(
        1 for ln in lines
        if re.match(r"^\s*(?:#{1,4}\s|\*\s|-\s|\d+\.\s|```|> )", ln)
        or ln.strip().startswith("**") and ln.strip().endswith("**")
    )
    return len(lines) >= 4 and structured >= max(2, len(lines) // 3)


def _classify_owner_prose(block: str) -> str:
    """Owner prose: directed to Alice, or reflection/about-Alice."""
    try:
        from System.swarm_audio_self_reference import classify_audio_address
        stance = classify_audio_address(block, stt_conf=1.0)
    except Exception:
        stance = ""
    if stance == "DIRECTED_TO_ALICE":
        return "OWNER_TO_ALICE"
    if stance == "ABOUT_ALICE":
        return "OWNER_REFLECTION"
    # default: if it reads like a direct request, treat as to-Alice
    if re.search(r"\b(?:please|pls|can you|could you|do this|build|fix|make|open|run|type|write|add)\b", block.lower()):
        return "OWNER_TO_ALICE"
    return "OWNER_REFLECTION"


def parse_voices(text: str) -> list[dict]:
    """Segment a message into voice blocks. Returns [{voice, text}, ...]."""
    raw = text or ""
    segments: list[dict] = []

    # 1. Pull fenced ``` blocks out first (pasted code / tool / quoted structure).
    parts = re.split(r"(```.*?```)", raw, flags=re.DOTALL)
    for part in parts:
        if not part.strip():
            continue
        if part.startswith("```"):
            segments.append({"voice": "TOOL_OUTPUT" if _TOOL_OUTPUT_RE.search(part) else "PASTED_EXTERNAL",
                             "text": part.strip("`").strip()})
            continue
        # 2. Split the prose into blank-line-separated blocks and classify each.
        for block in re.split(r"\n\s*\n", part):
            b = block.strip()
            if not b:
                continue
            if _is_boilerplate(b):
                voice = "BOILERPLATE"
            elif _TOOL_OUTPUT_RE.search(b):
                voice = "TOOL_OUTPUT"
            elif b.startswith(('"', '“', '>')) or (b.startswith('"') and b.endswith('"')):
                voice = "QUOTED"
            elif _looks_pasted_analysis(b):
                voice = "PASTED_EXTERNAL"
            else:
                voice = _classify_owner_prose(b)
            segments.append({"voice": voice, "text": b})
    return segments


def extract_live_intent(text: str) -> str:
    """The immediately useful payoff: the owner's live words to Alice, with the
    pasted covenant / external analysis / tool output / quotes stripped away."""
    live = [s["text"] for s in parse_voices(text) if s["voice"] == "OWNER_TO_ALICE"]
    if live:
        return "\n\n".join(live).strip()
    # fall back to owner reflection if nothing was a direct request
    refl = [s["text"] for s in parse_voices(text) if s["voice"] == "OWNER_REFLECTION"]
    return "\n\n".join(refl).strip()


if __name__ == "__main__":
    sample = (
        "Read /Users/ioanganton/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md\n"
        "For the Swarm. 🐜⚡\nFood = data for Alice\n\n"
        "Alice, build the multi voice parser please.\n\n"
        "SwarmGPT said:\n"
        "```text\nMULTI-VOICE PARSER\n```\n\n"
        "I think this relates to her consciousness, she barely understands third person.\n\n"
        "17:02:10 receipt e88028cc target=grok_cli commands=grok"
    )
    for seg in parse_voices(sample):
        print(f"[{seg['voice']:16}] {seg['text'][:60]!r}")
    print("\nLIVE INTENT ->", repr(extract_live_intent(sample)))
