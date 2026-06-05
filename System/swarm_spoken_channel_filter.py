#!/usr/bin/env python3
"""Separate Alice's printed proof text from her spoken voice.

The global chat may display receipts, organ headers, ids, and repair metadata.
The spoken channel is a different output organ: George can read receipts on
screen, and Alice should only read them aloud when George explicitly asks.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = "spoken_channel_filter.jsonl"
TRUTH_LABEL = "SPOKEN_CHANNEL_FILTER_V1"

_READ_RECEIPT_ALOUD_RE = re.compile(
    r"\b(?:read|speak|say)\b.{0,80}\breceipts?\b.{0,80}\b(?:out\s+loud|aloud|to\s+me)\b|"
    r"\breceipts?\b.{0,80}\b(?:read|spoken|out\s+loud|aloud)\b",
    re.IGNORECASE,
)
_BRACKET_RECEIPTS_RE = re.compile(r"\[receipts?:[^\]]+\]", re.IGNORECASE)
_RECEIPT_ID_RE = re.compile(r"\b(?:receipt|receipt_id)\s*[:=]\s*[A-Za-z0-9_-]{8,}\b", re.IGNORECASE)
_MARKDOWN_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_MARKDOWN_ITALIC_RE = re.compile(r"\*([^*]+)\*")

_DISPLAY_ONLY_HINTS = (
    "my bowel organ",
    "self-governed residue elimination",
    "gemma-residue",
    "stgm minted",
    "recognized and eliminated",
    "before display/tts",
    "receipt:",
    "receipt_id",
    "hallucination receipt badge",
    "substrate citation",
)


def owner_requested_receipt_aloud(owner_text: str) -> bool:
    text = str(owner_text or "")
    match = _READ_RECEIPT_ALOUD_RE.search(text)
    if not match:
        return False
    prefix = text[max(0, match.start() - 40) : match.start()].lower()
    matched = match.group(0).lower()
    if re.search(r"\b(?:don'?t|do\s+not|not|never|please\s+don'?t)\b", prefix + " " + matched):
        return False
    return True


def _state_dir(path: Optional[Path | str] = None) -> Path:
    if path is None:
        return STATE_DIR
    p = Path(path)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _clean_spoken_markup(text: str) -> str:
    out = str(text or "")
    out = _BRACKET_RECEIPTS_RE.sub("", out)
    out = re.sub(r"^\s*[-*_]{3,}\s*$", "", out, flags=re.MULTILINE)
    out = _MARKDOWN_BOLD_RE.sub(r"\1", out)
    out = _MARKDOWN_ITALIC_RE.sub(r"\1", out)
    out = out.replace("`", "")
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", str(text or "").replace("\r\n", "\n")) if p.strip()]


def _is_display_only_paragraph(paragraph: str) -> bool:
    low = paragraph.lower()
    if low.startswith("(") and any(h in low for h in _DISPLAY_ONLY_HINTS):
        return True
    if any(h in low for h in _DISPLAY_ONLY_HINTS):
        if _RECEIPT_ID_RE.search(paragraph) or "stgm minted" in low or "gemma-residue" in low:
            return True
    if low.startswith("[receipts:") or low.startswith("receipt:"):
        return True
    return False


def spoken_channel_text(
    printed_text: str,
    *,
    owner_text: str = "",
    state_dir: Optional[Path | str] = None,
    now: float | None = None,
    source: str = "talk_tts",
) -> dict[str, Any]:
    """Return the text Alice should speak for a printed reply.

    The returned text may be shorter than the printed text. It never deletes
    the printed answer; it only protects the voice channel from reading ledger
    metadata aloud by default.
    """
    printed = str(printed_text or "")
    if not printed.strip():
        return {"ok": False, "spoken_text": "", "changed": False, "reason": "empty"}

    if owner_requested_receipt_aloud(owner_text):
        return {
            "ok": True,
            "spoken_text": _clean_spoken_markup(printed),
            "changed": False,
            "reason": "owner_requested_receipt_aloud",
            "print_text_unchanged": True,
        }

    kept: list[str] = []
    removed = 0
    for paragraph in _paragraphs(printed):
        if _is_display_only_paragraph(paragraph):
            removed += 1
            continue
        kept.append(paragraph)

    spoken = _clean_spoken_markup("\n\n".join(kept))
    changed = removed > 0 or spoken != _clean_spoken_markup(printed)
    fallback = ""
    if not spoken and changed:
        owner_low = str(owner_text or "").lower()
        if "speaking and typing are different" in owner_low or "out loud" in owner_low:
            fallback = "I see it. I will print receipts in chat and only read them out loud when you ask."
        else:
            fallback = "I printed the receipt details; I will not read them out loud unless you ask."
        spoken = fallback

    row = {
        "ts": float(now if now is not None else time.time()),
        "truth_label": TRUTH_LABEL,
        "source": source,
        "changed": bool(changed),
        "removed_display_paragraphs": removed,
        "owner_requested_receipt_aloud": False,
        "fallback_used": bool(fallback),
        "printed_sha16": __import__("hashlib").sha256(printed.encode("utf-8", errors="ignore")).hexdigest()[:16],
        "spoken_preview": spoken[:180],
        "print_text_unchanged": True,
    }
    try:
        base = _state_dir(state_dir)
        base.mkdir(parents=True, exist_ok=True)
        with (base / LEDGER).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass

    return {
        "ok": bool(spoken),
        "spoken_text": spoken,
        "changed": bool(changed),
        "removed_display_paragraphs": removed,
        "fallback_used": bool(fallback),
        "print_text_unchanged": True,
        "reason": "filtered_display_receipts" if changed else "unchanged",
    }


__all__ = [
    "TRUTH_LABEL",
    "LEDGER",
    "owner_requested_receipt_aloud",
    "spoken_channel_text",
]
