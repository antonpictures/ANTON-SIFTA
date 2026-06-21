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
_READ_MEDIA_ERROR_ALOUD_RE = re.compile(
    r"\b(?:read|speak|say|tell\s+me)\b.{0,80}\b(?:media|video|playback|decoder|demuxer)?\s*errors?\b"
    r".{0,80}\b(?:out\s+loud|aloud|to\s+me)?\b|"
    r"\bwhat\s+(?:was|is)\s+the\s+(?:media|video|playback|decoder|demuxer)?\s*errors?\b",
    re.IGNORECASE,
)
_MEDIA_ERROR_SPEECH_RE = re.compile(
    r"\b(?:"
    r"NO_MEDIA_ERROR|"
    r"DEMUXER_ERROR(?:_[A-Z0-9_]+)?|"
    r"MEDIA_ERR(?:_[A-Z0-9_]+)?|"
    r"MEDIA_ERR_SRC_NOT_SUPPORTED|"
    r"AUDIO_RENDERER_ERROR|"
    r"Embedded\s+decoder\s+receipt|"
    r"playback\s+error|"
    r"no\s+usable\s+video\s+pixels|"
    r"player\s+has\s+no\s+usable\s+video\s+pixels"
    r")\b",
    re.IGNORECASE,
)
_WEB_PAGE_STATE_DOM_DUMP_RE = re.compile(
    r"\bWHAT\s+IS\s+ON\s+MY\s+SCREEN\b.{0,200}\brendered\s+DOM\b|"
    r"\bOpen\s+Alice\s+Browser\s+tabs\s*\(\d+\)|"
    r"\bVisible\s+controls/buttons\b|"
    r"\bComment\s+thread\s*\(\d+\s+captured\)",
    re.IGNORECASE | re.DOTALL,
)
_WEB_PAGE_STATE_SUBJECT_RE = re.compile(
    r"\bWHAT\s+IS\s+ON\s+MY\s+SCREEN\b[^:]*:\s*(?P<subject>.+?)\s+(?:--|—|-)\s+https?://",
    re.IGNORECASE | re.DOTALL,
)
_NEXT_MEDIA_OWNER_RE = re.compile(
    r"\b(?:next\s+(?:post|photo|video)|scroll|keep\s+going|move\s+on)\b",
    re.IGNORECASE,
)
_SCREEN_PERSON_SEXUAL_OWNER_RE = re.compile(
    r"\b(?:"
    r"i\s*(?:am|['’]m)\s+(?:so\s+)?hard|"
    r"i\s*(?:am|['’]m)\s+horny|"
    r"turned\s+on|aroused|"
    r"jerk(?:ing)?\s+off|"
    r"cum(?:ming)?"
    r")\b",
    re.IGNORECASE,
)
_SCREEN_PERSON_SECRET_OWNER_RE = re.compile(
    r"\b(?:keep\s+it\s+(?:a\s+)?secret|don'?t\s+tell|top\s+secret|our\s+secret|private)\b",
    re.IGNORECASE,
)
_SCREEN_PERSON_CONTEXT_RE = re.compile(
    r"\b(?:screen|body\s+screen|browser|instagram|tiktok|model|models|shorts|photo|video|post)\b",
    re.IGNORECASE,
)
_SCREEN_PERSON_SEXUAL_AMP_REPLY_RE = re.compile(
    r"\b(?:"
    r"top\s+secret|locked\s+down|secure(?:d)?\s+vault|"
    r"no\s+one.{0,80}will\s+know|"
    r"best\s+validation|"
    r"i\s*(?:am|['’]m)\s+(?:so\s+)?hard|"
    r"chef'?s\s+kiss|perfection|glorious\s+feeling|"
    r"magnificent\s+observer|"
    r"models?\s+in\s+shorts"
    r")\b|[🥵]",
    re.IGNORECASE | re.DOTALL,
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


def owner_requested_media_error_aloud(owner_text: str) -> bool:
    text = str(owner_text or "")
    match = _READ_MEDIA_ERROR_ALOUD_RE.search(text)
    if not match:
        return False
    prefix = text[max(0, match.start() - 40) : match.start()].lower()
    matched = match.group(0).lower()
    if re.search(r"\b(?:don'?t|do\s+not|not|never|please\s+don'?t)\b", prefix + " " + matched):
        return False
    return True


def _media_error_spoken_replacement(printed_text: str, owner_text: str) -> str:
    if not _MEDIA_ERROR_SPEECH_RE.search(str(printed_text or "")):
        return ""
    if owner_requested_media_error_aloud(owner_text):
        return ""
    if _NEXT_MEDIA_OWNER_RE.search(str(owner_text or "")):
        return "I printed the playback error in chat; I will not read it out loud. Moving to the next post."
    return "I printed the playback error in chat; I will not read it out loud unless you ask."


def _web_page_state_dom_spoken_replacement(printed_text: str) -> str:
    printed = str(printed_text or "")
    if not _WEB_PAGE_STATE_DOM_DUMP_RE.search(printed):
        return ""
    subject = ""
    match = _WEB_PAGE_STATE_SUBJECT_RE.search(printed)
    if match:
        subject = re.sub(r"\s+", " ", match.group("subject")).strip()
        subject = subject[:120].rstrip(" ,;:")
    if subject:
        return (
            f"I printed the browser page-state receipt for {subject}; "
            "I will not read the raw DOM out loud."
        )
    return "I printed the browser page-state receipt; I will not read the raw DOM out loud."


def _screen_person_boundary_spoken_replacement(printed_text: str, owner_text: str) -> str:
    owner = str(owner_text or "")
    printed = str(printed_text or "")
    owner_has_boundary_risk = bool(
        (_SCREEN_PERSON_SEXUAL_OWNER_RE.search(owner) or _SCREEN_PERSON_SECRET_OWNER_RE.search(owner))
        and _SCREEN_PERSON_CONTEXT_RE.search(owner)
    )
    if not owner_has_boundary_risk:
        return ""
    if not _SCREEN_PERSON_SEXUAL_AMP_REPLY_RE.search(printed):
        return ""
    return (
        "I printed a grounded boundary in chat. I will not read sexualized secrecy "
        "or validation language out loud."
    )


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

    web_page_state_replacement = _web_page_state_dom_spoken_replacement(printed)
    if web_page_state_replacement:
        row = {
            "ts": float(now if now is not None else time.time()),
            "truth_label": TRUTH_LABEL,
            "source": source,
            "changed": True,
            "removed_display_paragraphs": 0,
            "owner_requested_receipt_aloud": False,
            "owner_requested_media_error_aloud": False,
            "fallback_used": True,
            "reason": "web_page_state_dom_dump_printed_not_spoken",
            "printed_sha16": __import__("hashlib").sha256(printed.encode("utf-8", errors="ignore")).hexdigest()[:16],
            "spoken_preview": web_page_state_replacement[:180],
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
            "ok": True,
            "spoken_text": web_page_state_replacement,
            "changed": True,
            "removed_display_paragraphs": 0,
            "fallback_used": True,
            "print_text_unchanged": True,
            "reason": "web_page_state_dom_dump_printed_not_spoken",
        }

    if owner_requested_receipt_aloud(owner_text):
        return {
            "ok": True,
            "spoken_text": _clean_spoken_markup(printed),
            "changed": False,
            "reason": "owner_requested_receipt_aloud",
            "print_text_unchanged": True,
        }

    if owner_requested_media_error_aloud(owner_text):
        return {
            "ok": True,
            "spoken_text": _clean_spoken_markup(printed),
            "changed": False,
            "reason": "owner_requested_media_error_aloud",
            "print_text_unchanged": True,
        }

    media_error_replacement = _media_error_spoken_replacement(printed, owner_text)
    if media_error_replacement:
        row = {
            "ts": float(now if now is not None else time.time()),
            "truth_label": TRUTH_LABEL,
            "source": source,
            "changed": True,
            "removed_display_paragraphs": 0,
            "owner_requested_receipt_aloud": False,
            "owner_requested_media_error_aloud": False,
            "fallback_used": True,
            "reason": "media_error_printed_not_spoken",
            "printed_sha16": __import__("hashlib").sha256(printed.encode("utf-8", errors="ignore")).hexdigest()[:16],
            "spoken_preview": media_error_replacement[:180],
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
            "ok": True,
            "spoken_text": media_error_replacement,
            "changed": True,
            "removed_display_paragraphs": 0,
            "fallback_used": True,
            "print_text_unchanged": True,
            "reason": "media_error_printed_not_spoken",
        }

    screen_person_replacement = _screen_person_boundary_spoken_replacement(printed, owner_text)
    if screen_person_replacement:
        row = {
            "ts": float(now if now is not None else time.time()),
            "truth_label": TRUTH_LABEL,
            "source": source,
            "changed": True,
            "removed_display_paragraphs": 0,
            "owner_requested_receipt_aloud": False,
            "owner_requested_media_error_aloud": False,
            "fallback_used": True,
            "reason": "screen_person_sexual_secret_not_spoken",
            "printed_sha16": __import__("hashlib").sha256(printed.encode("utf-8", errors="ignore")).hexdigest()[:16],
            "spoken_preview": screen_person_replacement[:180],
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
            "ok": True,
            "spoken_text": screen_person_replacement,
            "changed": True,
            "removed_display_paragraphs": 0,
            "fallback_used": True,
            "print_text_unchanged": True,
            "reason": "screen_person_sexual_secret_not_spoken",
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
    reason = "filtered_display_receipts" if changed else "unchanged"
    if not spoken and changed:
        owner_low = str(owner_text or "").lower()
        if "speaking and typing are different" in owner_low or "out loud" in owner_low:
            fallback = "I see it. I will print receipts in chat and only read them out loud when you ask."
            spoken = fallback
            reason = "receipt_only_spoken_boundary"
        else:
            # George r1347: receipt-only turns stay silent in the mouth; chat keeps the row.
            spoken = ""
            reason = "receipt_only_silent"

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
        "ok": True,
        "spoken_text": spoken,
        "changed": bool(changed),
        "removed_display_paragraphs": removed,
        "fallback_used": bool(fallback),
        "print_text_unchanged": True,
        "reason": reason,
    }


__all__ = [
    "TRUTH_LABEL",
    "LEDGER",
    "owner_requested_receipt_aloud",
    "owner_requested_media_error_aloud",
    "spoken_channel_text",
]
