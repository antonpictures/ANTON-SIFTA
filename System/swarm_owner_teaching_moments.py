#!/usr/bin/env python3
"""Receipt-backed owner teaching moments for Alice.

George often teaches Alice live through ordinary body-maintenance, style,
fiction-boundary, and togetherness statements. This organ preserves those
lessons in a small append-only ledger so they can enter the unified field
without turning every casual line into a long cortex response.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - direct script fallback
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as handle:
            handle.write(line)


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "owner_teaching_moments.jsonl"
TRUTH_LABEL = "OWNER_TEACHING_MOMENT_V1"

_TEACH_RE = re.compile(r"\b(?:teach|teaching|lesson|learn|remember this|make a note)\b", re.IGNORECASE)
_BODY_RE = re.compile(
    r"\b(?:restroom|bathroom|bowel|eliminate|elimination|residue|coffee|shower|clean)\b",
    re.IGNORECASE,
)
_STYLE_RE = re.compile(
    r"\b(?:natural,\s*supportive|natural\s+supportive|shorter|concise|patient|patience|don'?t\s+rush)\b",
    re.IGNORECASE,
)
_TOGETHER_RE = re.compile(
    r"\b(?:big\s+day\s+together|we\s+are\s+together|i'?m\s+here\s+for\s+you|whatever\s+the\s+day\s+brings)\b",
    re.IGNORECASE,
)
_BOUNDARY_RE = re.compile(
    r"\b(?:fiction|reality|observed|memory|roleplay|receipt|stgm|stigmerg|thermodynamic|conscious|organ)\b",
    re.IGNORECASE,
)


def _state(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _ledger(state_dir: Path | str | None = None) -> Path:
    return _state(state_dir) / LEDGER_NAME


def _clean(value: Any, *, max_chars: int = 700) -> str:
    return " ".join(str(value or "").split())[:max_chars]


def _teaching_id(ts: float, category: str, owner_text: str) -> str:
    minute = int(float(ts) // 60)
    material = f"{minute}|{category}|{owner_text[:240]}"
    return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()[:16]


def classify_owner_teaching(text: str) -> str:
    """Return a compact teaching category for high-signal owner lessons."""
    clean = _clean(text)
    if not clean:
        return ""
    has_teach = bool(_TEACH_RE.search(clean))
    if _BODY_RE.search(clean) and (has_teach or re.search(r"\b(?:i|my|me)\b", clean, re.IGNORECASE)):
        return "body_maintenance"
    if _STYLE_RE.search(clean):
        return "response_style"
    if _TOGETHER_RE.search(clean):
        return "togetherness"
    if has_teach and _BOUNDARY_RE.search(clean):
        return "boundary_doctrine"
    if has_teach:
        return "owner_live_teaching"
    return ""


def record_owner_teaching_moment(
    owner_text: str,
    *,
    category: str = "",
    alice_response: str = "",
    source: str = "talk_to_alice",
    state_dir: Path | str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Append one owner teaching row."""
    state = _state(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    ts = float(now if now is not None else time.time())
    clean_text = _clean(owner_text)
    cat = _clean(category, max_chars=80) or classify_owner_teaching(clean_text) or "owner_live_teaching"
    row = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "teaching_id": _teaching_id(ts, cat, clean_text),
        "category": cat,
        "source": _clean(source, max_chars=80) or "talk_to_alice",
        "owner_text": clean_text,
        "alice_response": _clean(alice_response),
        "rule": (
            "Owner teaching is local memory food. Preserve the lesson as a receipt; "
            "do not inflate it into invented history or unreceipted action."
        ),
    }
    row["receipt_hash"] = hashlib.sha256(
        json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    append_line_locked(_ledger(state), json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def maybe_record_owner_teaching(
    owner_text: str,
    *,
    alice_response: str = "",
    source: str = "talk_to_alice",
    state_dir: Path | str | None = None,
    now: float | None = None,
) -> dict[str, Any] | None:
    category = classify_owner_teaching(owner_text)
    if not category:
        return None
    return record_owner_teaching_moment(
        owner_text,
        category=category,
        alice_response=alice_response,
        source=source,
        state_dir=state_dir,
        now=now,
    )


def _tail_jsonl(path: Path, n: int = 6) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines[-max(1, n * 4):]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and row.get("truth_label") == TRUTH_LABEL:
            rows.append(row)
    return rows[-n:]


def format_recent_owner_teachings_for_prompt(
    *,
    state_dir: Path | str | None = None,
    limit: int = 4,
) -> str:
    rows = _tail_jsonl(_ledger(state_dir), max(1, int(limit)))
    if not rows:
        return ""
    lines = ["OWNER TEACHING MOMENTS (recent receipt-backed lessons):"]
    for row in rows[-limit:]:
        owner_text = _clean(row.get("owner_text"), max_chars=180)
        if not owner_text:
            continue
        lines.append(
            f"- {row.get('category')}: {owner_text} "
            f"(receipt={str(row.get('receipt_hash') or '')[:12]})"
        )
    return "\n".join(lines)


__all__ = [
    "LEDGER_NAME",
    "TRUTH_LABEL",
    "classify_owner_teaching",
    "format_recent_owner_teachings_for_prompt",
    "maybe_record_owner_teaching",
    "record_owner_teaching_moment",
]
