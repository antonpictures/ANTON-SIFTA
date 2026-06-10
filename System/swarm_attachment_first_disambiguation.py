#!/usr/bin/env python3
"""Attachment-first product disambiguation before web search (r874 P1-C)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "ATTACHMENT_FIRST_DISAMBIGUATION_V1"

_NAMED_ENTITY_RE = re.compile(
    r"\b(?:fable\s*5?|anthropic|claude\s+fable|mythos)\b",
    re.IGNORECASE,
)
_XBOX_TRAP_RE = re.compile(r"\b(?:xbox|fable\s+(?:game|video\s+game|iii|iv))\b", re.IGNORECASE)


def _tail_jsonl(path: Path, n: int = 8) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return []
    return rows


def has_staged_attachment(*, state_dir: str | Path | None = None, max_age_s: float = 900.0) -> bool:
    base = Path(state_dir) if state_dir is not None else STATE_DIR
    now = __import__("time").time()
    for row in reversed(_tail_jsonl(base / "talk_image_attachment_context.jsonl", 12)):
        try:
            ts = float(row.get("ts") or 0.0)
        except Exception:
            ts = 0.0
        if ts and (now - ts) > max_age_s:
            continue
        if row.get("image_path") or row.get("path"):
            return True
    return False


def build_attachment_first_context(
    owner_text: str,
    *,
    image_path: str | None = None,
    state_dir: str | Path | None = None,
) -> Optional[str]:
    """OCR/layout evidence block for cortex when screenshot + named entity collide."""
    clean = " ".join((owner_text or "").strip().split())
    if not clean or not _NAMED_ENTITY_RE.search(clean):
        return None
    staged = bool(image_path) or has_staged_attachment(state_dir=state_dir)
    if not staged:
        return None

    path = image_path
    if not path:
        for row in reversed(_tail_jsonl((Path(state_dir) if state_dir else STATE_DIR) / "talk_image_attachment_context.jsonl", 12)):
            path = str(row.get("image_path") or row.get("path") or "").strip()
            if path:
                break
    if not path:
        return None

    try:
        from System.swarm_attachment_vision_lane import describe_attachment_for_talk

        ocr_block = describe_attachment_for_talk(
            clean,
            path,
            state_dir=state_dir,
        )
    except Exception:
        ocr_block = ""

    if not ocr_block:
        return None

    lines = [
        "[ATTACHMENT-FIRST DISAMBIGUATION — read staged screenshot OCR before web guess]",
        ocr_block,
        "Owner named a product in text. If OCR shows Claude/Anthropic/Fable IDE UI, "
        "do NOT answer with Xbox game Fable. Search Anthropic Claude Fable 5 only after OCR.",
    ]
    if _XBOX_TRAP_RE.search(clean):
        lines.append("BLOCK: owner text intersects Xbox-game trap; OCR wins.")
    return "\n".join(lines)


def should_block_xbox_fable_guess(
    owner_text: str,
    cortex_reply: str,
    *,
    image_path: str | None = None,
    state_dir: str | Path | None = None,
) -> bool:
    """Dry guard for tests — True when staged Claude UI should block Xbox answer."""
    if not build_attachment_first_context(owner_text, image_path=image_path, state_dir=state_dir):
        return False
    reply = (cortex_reply or "").lower()
    return bool(_XBOX_TRAP_RE.search(reply) and _NAMED_ENTITY_RE.search(owner_text or ""))


__all__ = [
    "TRUTH_LABEL",
    "build_attachment_first_context",
    "has_staged_attachment",
    "should_block_xbox_fable_guess",
]