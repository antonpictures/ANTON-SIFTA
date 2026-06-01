#!/usr/bin/env python3
"""Associative name memory + single-focus app habit field for Alice.

Names are treated as stigmergic handles, not as authority claims. A handle
such as "Grok", "Claude", "Sam Altman", or any other person/model/app name
can accumulate associations from the owner's current stream of consciousness.

The other half of the organ is focus: the active app pulls the relevant habits
into attention while the rest of the field stays as background context. This
matches the One Global Chat rule: one Alice, one stream, many app organs.

Pure stdlib. Local JSONL only. IDE trace, not an STGM receipt.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "name_association_memory.jsonl"
TRUTH_LABEL = "ASSOCIATIVE_NAME_MEMORY_V1"

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can",
    "do", "for", "from", "have", "her", "him", "his", "i", "if",
    "in", "is", "it", "just", "like", "me", "my", "not", "of",
    "on", "or", "our", "she", "so", "that", "the", "their", "them",
    "these", "they", "this", "to", "was", "we", "what", "when",
    "where", "while", "with", "you", "your",
}

_LIST_CUE_RE = re.compile(
    r"\b(?:names?\s+like|called|call(?:\s+her|\s+him|\s+them|\s+this)?|"
    r"her\s+name\s+is|his\s+name\s+is|their\s+name\s+is|name\s+is)\b"
    r"[:\s-]*(?P<tail>[^.?!\n]{1,220})",
    re.IGNORECASE,
)
_CAPITALIZED_NAME_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9_'-]{1,}(?:\s+[A-Z][A-Za-z0-9_'-]{1,}){0,3})\b"
)
_HANDLE_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_.]{2,40})")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_'-]{2,}")


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _clean_name(name: str) -> str:
    clean = " ".join(str(name or "").replace("_", " ").split())
    clean = clean.strip(" \t\r\n,;:()[]{}\"'")
    return clean


def _name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean_name(name).casefold()).strip()


def _is_probable_name(name: str, *, allow_lowercase_single: bool = False) -> bool:
    clean = _clean_name(name)
    if not clean:
        return False
    words = clean.split()
    if not (1 <= len(words) <= 4):
        return False
    if any(len(w) > 32 for w in words):
        return False
    lowered = [w.casefold().strip(".,;:!?") for w in words]
    if all(w in _STOPWORDS for w in lowered):
        return False
    if len(words) == 1 and lowered[0] in _STOPWORDS:
        return False
    if allow_lowercase_single:
        return True
    return any(w[:1].isupper() for w in words)


def _dedupe_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        clean = _clean_name(item)
        key = _name_key(clean)
        if not clean or not key or key in seen:
            continue
        seen.add(key)
        out.append(clean)
    return out


def extract_name_handles(text: str) -> list[str]:
    """Extract human/model/app name handles without hardcoding specific people.

    Lowercase single-token handles are only accepted when the owner explicitly
    frames a list as names ("names like grok, claude, ..."). Otherwise this
    sticks to capitalized names and @handles to avoid treating every noun as a
    person or model.
    """
    text_s = str(text or "")
    found: list[str] = []

    for match in _LIST_CUE_RE.finditer(text_s):
        tail = match.group("tail") or ""
        tail = re.sub(r"\s+\band\b\s+", ",", tail, flags=re.IGNORECASE)
        for part in re.split(r"[,;/|]+", tail):
            part = re.sub(r"\b(?:to\s+me|same\s+for|these\s+are)\b.*$", "", part, flags=re.IGNORECASE)
            part = re.sub(r"\b(?:are|is|was|were)\b.*$", "", part, flags=re.IGNORECASE)
            clean = _clean_name(part)
            if _is_probable_name(clean, allow_lowercase_single=True):
                found.append(clean)

    for handle in _HANDLE_RE.findall(text_s):
        clean = _clean_name(handle)
        if _is_probable_name(clean, allow_lowercase_single=True):
            found.append(clean)

    for match in _CAPITALIZED_NAME_RE.findall(text_s):
        clean = _clean_name(match)
        if _is_probable_name(clean):
            found.append(clean)

    return _dedupe_preserve(found)


def _context_terms(text: str, *, limit: int = 14) -> list[str]:
    terms: list[str] = []
    for raw in _WORD_RE.findall(str(text or "").casefold()):
        if raw in _STOPWORDS:
            continue
        if raw.isdigit():
            continue
        terms.append(raw)
    return _dedupe_preserve(terms)[: max(0, int(limit))]


def _context_hash(text: str, active_app: str) -> str:
    h = hashlib.sha256()
    h.update(str(active_app or "").casefold().encode("utf-8", errors="ignore"))
    h.update(b"\0")
    h.update(str(text or "").encode("utf-8", errors="ignore"))
    return h.hexdigest()[:16]


def _read_recent(path: Path, limit: int = 300) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return rows
    for line in lines[-max(0, int(limit)):]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def current_active_app(state_dir: Optional[Path | str] = None) -> str:
    state = _state(state_dir)
    desktop_state = state / "sifta_desktop_app_state.json"
    try:
        data = json.loads(desktop_state.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            active = str(data.get("active_app") or "").strip()
            if active:
                return active
            open_apps = data.get("open_apps") or []
            if isinstance(open_apps, list) and len(open_apps) == 1:
                return str(open_apps[0]).strip()
    except Exception:
        pass

    focus_path = state / "app_focus.jsonl"
    for row in reversed(_read_recent(focus_path, limit=50)):
        app = str(row.get("app") or row.get("current_app") or "").strip()
        if app:
            return app

    try:
        from System.swarm_capability_registry import current_app_name_from_field

        return str(current_app_name_from_field() or "").strip()
    except Exception:
        return ""


def remember_name_associations(
    user_text: str,
    *,
    active_app: str = "",
    stream_id: str = "",
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
    write: bool = True,
) -> dict[str, Any]:
    """Persist the name handles in this turn as associative memory rows."""
    ts = float(now if now is not None else time.time())
    state = _state(state_dir)
    app = str(active_app or current_active_app(state_dir) or "").strip()
    names = extract_name_handles(user_text)
    context_terms = _context_terms(user_text)
    ctx_hash = _context_hash(user_text, app)
    stream = stream_id or f"{app or 'global'}:{ctx_hash}"

    path = state / LEDGER_NAME
    recent = _read_recent(path)
    existing = {
        (str(r.get("name_key") or ""), str(r.get("context_hash") or ""))
        for r in recent
    }
    rows: list[dict[str, Any]] = []
    skipped = 0
    for name in names:
        key = _name_key(name)
        if not key:
            continue
        if (key, ctx_hash) in existing:
            skipped += 1
            continue
        row = {
            "ts": ts,
            "truth_label": TRUTH_LABEL,
            "memory_kind": "associative_name_handle",
            "name": name,
            "name_key": key,
            "active_app": app,
            "focus_stream_id": stream,
            "context_terms": context_terms,
            "context_hash": ctx_hash,
            "source": "owner_turn",
            "doctrine": "Names are associative handles in the stigmergic field, not authority claims.",
        }
        rows.append(row)
        if write:
            try:
                _append_jsonl(path, row)
            except Exception:
                pass

    return {
        "truth_label": TRUTH_LABEL,
        "active_app": app,
        "focus_stream_id": stream,
        "names": names,
        "context_terms": context_terms,
        "written": len(rows) if write else 0,
        "deduped": skipped,
        "rows": rows,
    }


def _habit_names_for_app(app: str, user_text: str, limit: int = 5) -> list[str]:
    if not app:
        return []
    try:
        from System.swarm_capability_registry import app_habit_field_summary

        summary = app_habit_field_summary(app, query=user_text, limit=limit)
        return [
            str(item.get("name") or "").strip()
            for item in (summary.get("habits") or [])
            if str(item.get("name") or "").strip()
        ][: max(0, int(limit))]
    except Exception:
        return []


def associative_focus_prompt(
    user_text: str,
    *,
    state_dir: Optional[Path | str] = None,
    write: bool = True,
    now: Optional[float] = None,
) -> str:
    """Prompt block for names-as-associations + one focused app stream."""
    packet = remember_name_associations(
        user_text,
        state_dir=state_dir,
        now=now,
        write=write,
    )
    app = str(packet.get("active_app") or "").strip()
    names = [str(n) for n in packet.get("names") or [] if str(n).strip()]
    habits = _habit_names_for_app(app, user_text)

    if not app and not names:
        return ""

    lines = [
        "ASSOCIATIVE FOCUS FIELD — one present stream, app-scoped habits.",
        "Names in the turn are stigmergic memory handles. Do not treat a name as proof, authority, or a separate organism; use it to retrieve nearby associations and receipts.",
    ]
    if names:
        lines.append("Name handles active now: " + ", ".join(names[:10]) + ".")
    if app:
        lines.append(f"Current app organ: {app}. Load this app's relevant habits before generic tool search.")
    if habits:
        lines.append("Habits pulled by current app: " + ", ".join(habits) + ".")
    lines.append(
        "Focus rule: keep one dominant stream of consciousness in the present. Past receipts and future goals support the current task; they do not become competing tasks unless the owner explicitly asks to branch."
    )
    lines.append(
        "If the owner multitasks or speaks fast, preserve the main thread, store side details as background associations, and answer from the focused app/body context first."
    )
    return "\n".join(lines)


__all__ = [
    "TRUTH_LABEL",
    "LEDGER_NAME",
    "extract_name_handles",
    "remember_name_associations",
    "associative_focus_prompt",
    "current_active_app",
]
