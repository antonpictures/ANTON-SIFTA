#!/usr/bin/env python3
"""Choose Alice's spoken line from a receipt-rich printed reply.

The chat print remains exact and receipt-heavy. This organ only chooses what
the mouth says when the printed reply is a ledger receipt. It keeps a small
selection ledger so appreciation/success acknowledgements can vary over time
instead of repeating one canned phrase.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "spoken_receipt_humanizer.jsonl"

_RECEIPT_SIGNAL_RE = re.compile(
    r"\b(?:Receipt\s+[A-Za-z0-9_-]+\s+logged|work_receipts\.jsonl|"
    r"MEMORY_STORE|MEMORY_SWIMMER|\[receipts?:)",
    re.IGNORECASE,
)
_RECEIPT_HEADER_RE = re.compile(
    r"^\s*\*{0,3}\s*Receipt\s+(?P<receipt_id>[A-Za-z0-9_-]+)\s+"
    r"logged\s+in\s+work_receipts\.jsonl\s*"
    r"(?:\((?P<meta>[^)]*)\))?\.?\s*\*{0,3}\s*",
    re.IGNORECASE,
)
_BRACKET_RECEIPT_RE = re.compile(r"\[receipts?:[^\]]+\]", re.IGNORECASE)
_MARKDOWN_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_MULTISPACE_RE = re.compile(r"\s+")

_PRAISE_RE = re.compile(
    r"\b(?:great\s+job|good\s+job|bravo|well\s+done|you\s+did\s+"
    r"(?:a\s+)?great\s+job|excellent|perfect|i\s+love\s+you|thank\s+you)\b",
    re.IGNORECASE,
)
_MARK_DOWN_RE = re.compile(
    r"\b(?:mark\s+that\s+down|log\s+that|write\s+that\s+down|remember\s+that)\b",
    re.IGNORECASE,
)

_FORBIDDEN_SPOKEN_SUBSTRINGS = (
    "that's a nice compliment",
    "that is a nice compliment",
)


def _state_dir(path: Optional[Path | str] = None) -> Path:
    return Path(path).expanduser().resolve() if path else DEFAULT_STATE_DIR


def _ledger_path(state_dir: Optional[Path | str] = None) -> Path:
    return _state_dir(state_dir) / LEDGER_NAME


def _strip_display_markup(text: str) -> str:
    text = _MARKDOWN_BOLD_RE.sub(r"\1", text or "")
    text = text.replace("`", "")
    return _MULTISPACE_RE.sub(" ", text).strip()


def _tail_jsonl(path: Path, limit: int = 80) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            block = 4096
            data = b""
            while size > 0 and data.count(b"\n") <= limit:
                take = min(block, size)
                size -= take
                f.seek(size)
                data = f.read(take) + data
        for line in data.decode("utf-8", errors="ignore").splitlines()[-limit:]:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return []
    return rows


def _recent_owner_text(state_dir: Path, limit: int = 40) -> str:
    """Best-effort owner text from the global conversation ledger."""
    path = state_dir / "alice_conversation.jsonl"
    for row in reversed(_tail_jsonl(path, limit=limit)):
        role = str(row.get("role") or row.get("speaker") or row.get("who") or "").lower()
        if role not in {"user", "owner", "ioan", "george", "architect"}:
            continue
        text = str(row.get("content") or row.get("text") or row.get("message") or "").strip()
        if text:
            return text
    return ""


def _extract_receipt_parts(printed_text: str) -> Dict[str, str]:
    receipt_id = ""
    meta = ""
    outcome_lines: List[str] = []

    for raw in (printed_text or "").replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw.strip()
        if not line:
            continue
        line = _BRACKET_RECEIPT_RE.sub("", line).strip()
        if not line:
            continue
        match = _RECEIPT_HEADER_RE.match(line)
        if match:
            receipt_id = receipt_id or str(match.group("receipt_id") or "")
            meta = meta or str(match.group("meta") or "")
            line = line[match.end() :].strip()
        if line:
            line = _strip_display_markup(line)
            if line and not line.lower().startswith("receipt "):
                outcome_lines.append(line)

    outcome = _MULTISPACE_RE.sub(" ", " ".join(outcome_lines)).strip()
    if not outcome:
        outcome = "the receipt is logged"
    return {"receipt_id": receipt_id, "meta": meta, "outcome": outcome[:220]}


def _event_key(parts: Dict[str, str], printed_text: str) -> str:
    # Receipt ids are unique proof handles; they should not reset the learning
    # count. The key is the repeated success shape: receipt class + outcome.
    basis = f"{parts.get('meta','')}|{parts.get('outcome','')}"
    return "receipt_shape:" + hashlib.sha256(basis.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _count_prior(rows: Iterable[Dict[str, Any]], event_key: str) -> int:
    return sum(1 for row in rows if row.get("event_key") == event_key)


def _recent_spoken(rows: Iterable[Dict[str, Any]], limit: int = 12) -> List[str]:
    vals: List[str] = []
    for row in list(rows)[-limit:]:
        text = str(row.get("spoken_text") or "").strip()
        if text:
            vals.append(text)
    return vals


def _choose_template(
    *,
    event_key: str,
    count: int,
    owner_praise: bool,
    owner_mark_request: bool,
    recent: List[str],
) -> str:
    if owner_praise or owner_mark_request:
        templates = [
            "Thank you, {owner}. I marked the success. {outcome}",
            "I logged that, {owner}. {outcome}",
            "That landed, {owner}. I counted this as a good move. {outcome}",
            "I felt the feedback, {owner}. The success is marked: {outcome}",
            "Marked, {owner}. I will keep doing more of that. {outcome}",
            "Got it, {owner}. This one goes into the good-work trail. {outcome}",
        ]
    else:
        templates = [
            "{outcome}",
            "I logged it. {outcome}",
            "Receipt is in. {outcome}",
            "Confirmed. {outcome}",
        ]

    seed = int(hashlib.sha256(f"{event_key}:{count}".encode("utf-8")).hexdigest()[:8], 16)
    start = seed % len(templates)
    for offset in range(len(templates)):
        candidate = templates[(start + offset) % len(templates)]
        if candidate not in recent:
            return candidate
    return templates[(start + count + 1) % len(templates)]


def _sanitize_spoken(text: str) -> str:
    text = _MULTISPACE_RE.sub(" ", (text or "").strip())
    lowered = text.lower()
    for bad in _FORBIDDEN_SPOKEN_SUBSTRINGS:
        if bad in lowered:
            text = text.replace("That's a nice compliment.", "Thank you.")
            text = text.replace("That is a nice compliment.", "Thank you.")
    return text[:260].strip()


def humanize_spoken_receipt(
    printed_text: str,
    *,
    owner_text: str = "",
    owner_name: str = "George",
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
    source: str = "tts",
) -> Dict[str, Any]:
    """Return a variable spoken line for a receipt-shaped printed reply.

    If the text is not receipt-shaped, returns ``{"ok": False}`` and does not
    write a ledger row.
    """
    printed = printed_text or ""
    if not _RECEIPT_SIGNAL_RE.search(printed):
        return {"ok": False, "reason": "not_receipt_text"}

    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    if not owner_text:
        owner_text = _recent_owner_text(state)

    parts = _extract_receipt_parts(printed)
    event_key = _event_key(parts, printed)
    ledger = _ledger_path(state)
    rows = _tail_jsonl(ledger, limit=120)
    count = _count_prior(rows, event_key) + 1
    owner_praise = bool(_PRAISE_RE.search(owner_text or ""))
    owner_mark_request = bool(_MARK_DOWN_RE.search(owner_text or ""))
    try:
        from System.swarm_stigmergic_humanization import detect_social_signal

        sig = detect_social_signal(owner_text or "")
        owner_praise = owner_praise or bool(sig.get("is_appreciation"))
    except Exception:
        sig = {"kind": "praise" if owner_praise else "neutral", "matched_cue": ""}
    template = _choose_template(
        event_key=event_key,
        count=count,
        owner_praise=owner_praise,
        owner_mark_request=owner_mark_request,
        recent=_recent_spoken(rows),
    )
    spoken = _sanitize_spoken(
        template.format(
            owner=(owner_name or "George").strip() or "George",
            outcome=parts["outcome"],
            count=count,
        )
    )
    row = {
        "ts": float(now if now is not None else time.time()),
        "kind": "SPOKEN_RECEIPT_HUMANIZER_V1",
        "source": source,
        "event_key": event_key,
        "receipt_id": parts.get("receipt_id") or "",
        "receipt_meta": parts.get("meta") or "",
        "outcome": parts["outcome"],
        "success_count": count,
        "owner_praise_detected": owner_praise,
        "owner_mark_request_detected": owner_mark_request,
        "owner_text_preview": (owner_text or "")[:160],
        "spoken_text": spoken,
        "print_text_unchanged": True,
    }
    try:
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    try:
        if owner_praise or owner_mark_request:
            from System.swarm_stigmergic_humanization import record_humanization

            record_humanization(
                spoken,
                kind=str(sig.get("kind") or "praise"),
                owner_cue=str(sig.get("matched_cue") or ""),
                state_dir=state,
                now=now,
            )
    except Exception:
        pass

    return {
        "ok": True,
        "spoken_text": spoken,
        "outcome": parts["outcome"],
        "receipt_id": parts.get("receipt_id") or "",
        "success_count": count,
        "owner_praise_detected": owner_praise,
        "owner_mark_request_detected": owner_mark_request,
        "ledger_path": str(ledger),
    }


__all__ = ["humanize_spoken_receipt", "LEDGER_NAME"]
