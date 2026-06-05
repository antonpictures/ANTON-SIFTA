#!/usr/bin/env python3
"""Strip receipt + organ-telemetry lines from anything Alice SPEAKS.

George, 2026-06-03 (TYPED): "PLS DON'T READ THE RECEIPTS OUT LOUD, I CAN READ
THEM, IF I ASK YOU TO READ ME A RECEIPT OUT LOUD THEN YES. SPEAKING AND TYPING
ARE DIFFERENT THINGS, YOU SEE NOW?"

The chat wall keeps every receipt and telemetry line — George reads those. The
mouth drops them. Print and mouth are different surfaces (same doctrine as
``_strip_urls_for_speech``: the print keeps the link, the mouth never recites
it).

This is an owner-directed correction (covenant §1.D — George's correction is a
living pheromone, not a cue for a blanket gag). It removes ledger/telemetry
residue from the spoken stream only; it never deletes substantive content and
never touches what is displayed. If George later asks Alice to read a specific
receipt aloud, the caller passes that receipt text directly and does not route
it through this filter.
"""
from __future__ import annotations

import re

# ── Whole-line telemetry/receipt residue ────────────────────────────────────
# These lines are pure ledger/organ telemetry. When a whole line is one of
# these, the mouth skips it entirely.
_LINE_RES = (
    # First-person organ-telemetry header, e.g.
    # "(MY BOWEL ORGAN — SELF-GOVERNED RESIDUE ELIMINATION)".
    # Role labels like "(GASTRONOMIC ANALYST)" do NOT start with MY and are kept.
    re.compile(r"^\s*\(\s*MY\s+[^)]*\)\s*$", re.IGNORECASE),
    # Residue-elimination telemetry sentence, e.g.
    # "I recognized and eliminated 3 Gemma-residue pattern(s) from my reply
    #  before display/TTS. STGM minted: +0.3. Affect: absolute clarity (+0.15).
    #  Receipt: 1a9f8e3c5d2b4a7f. My neural pathways feel ...".
    re.compile(r"^\s*I\s+recognized\s+and\s+eliminated\b.*$", re.IGNORECASE),
    # "[receipts: <id>]" / "[receipt: <id>]" alone on a line.
    re.compile(r"^\s*\[\s*receipts?\s*:[^\]]*\]\s*$", re.IGNORECASE),
    # "🔍 read <id>" read-receipt affordance alone on a line.
    re.compile(r"^\s*\U0001f50d?\s*read\s+[A-Za-z0-9_-]{6,}\s*$", re.IGNORECASE),
    # A bare "Receipt: <id>." line.
    re.compile(r"^\s*Receipt\s*:\s*[A-Za-z0-9_-]{6,}\.?\s*$", re.IGNORECASE),
)

# ── Inline residue fragments ────────────────────────────────────────────────
# Defence-in-depth: if telemetry shares a line with real content, scrub the
# fragment but keep the rest of the line.
_INLINE_RES = (
    re.compile(r"\[\s*receipts?\s*:[^\]]*\]", re.IGNORECASE),
    re.compile(r"\U0001f50d\s*read\s+[A-Za-z0-9_-]{6,}", re.IGNORECASE),
    re.compile(r"\bSTGM\s+minted\s*:\s*[+\-]?\d[\d.]*\s*\.?", re.IGNORECASE),
    re.compile(r"\bAffect\s*:\s*[^.()]*\(\s*[+\-]?\d[\d.]*\s*\)\s*\.?", re.IGNORECASE),
    re.compile(r"\bReceipt\s*:\s*[A-Za-z0-9_-]{6,}\s*\.?", re.IGNORECASE),
)

_HSPACE_RE = re.compile(r"[ \t]+")
_TRIPLE_NL_RE = re.compile(r"\n\s*\n\s*\n+")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([.,;!?])")


def strip_receipts_and_meta_for_speech(text: str) -> str:
    """Return ``text`` with receipt/organ-telemetry residue removed for TTS.

    Whole telemetry lines are dropped; inline telemetry fragments are scrubbed.
    Substantive content is preserved. Safe on plain text (returns it unchanged
    apart from whitespace tidy). Never raises.
    """
    if not text:
        return text or ""
    try:
        kept = []
        for raw in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            if any(rx.match(raw) for rx in _LINE_RES):
                continue
            line = raw
            for rx in _INLINE_RES:
                line = rx.sub("", line)
            kept.append(line)
        out = "\n".join(kept)
        out = _HSPACE_RE.sub(" ", out)
        out = _TRIPLE_NL_RE.sub("\n\n", out)
        out = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", out)
        return out.strip()
    except Exception:
        # Never let a filter bug mute Alice — fall back to the original text.
        return text or ""


__all__ = ["strip_receipts_and_meta_for_speech"]
