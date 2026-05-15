#!/usr/bin/env python3
"""Recent Talk context reader for Alice.

Deterministic organ path for short chat-history and first-person style
questions. It reads the local Talk ledger instead of asking the cortex to
guess what just happened.

Truth boundary: this is a ledger/context reader, not a learned memory model.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
CONVERSATION_LEDGER = "alice_conversation.jsonl"
RECEIPT_LEDGER = "recent_context_reader_receipts.jsonl"
TRUTH_LABEL = "RECENT_CONTEXT_READER_V1"

_FIRST_PERSON_STYLE_RE = re.compile(
    r"\b(?:first\s+person|one\s+on\s+one|third\s+person\s+doesn'?t\s+exist|"
    r"talk(?:ing)?\s+(?:in|of)\s+the\s+first\s+person|"
    r"show\s+me\s+how\s+you(?:'re|\s+are)?\s+talk(?:ing)?\s+.*first\s+person)\b",
    re.IGNORECASE,
)

_LAST_USER_RE = re.compile(
    r"\b(?:what\s+did\s+i\s+(?:just\s+)?say|what\s+was\s+my\s+(?:last\s+)?message|"
    r"repeat\s+my\s+(?:last\s+)?message|read\s+my\s+(?:last\s+)?message)\b",
    re.IGNORECASE,
)

_LAST_ALICE_RE = re.compile(
    r"\b(?:what\s+did\s+you\s+(?:just\s+)?say|what\s+was\s+your\s+(?:last\s+)?"
    r"(?:answer|reply|message)|repeat\s+your\s+(?:last\s+)?(?:answer|reply))\b",
    re.IGNORECASE,
)

_SUMMARY_RE = re.compile(
    r"\b(?:what\s+(?:are|were)\s+we\s+talking\s+about|what\s+happened\s+"
    r"(?:in\s+)?(?:the\s+)?chat|show\s+(?:me\s+)?(?:the\s+)?recent\s+chat|"
    r"chat\s+history|recent\s+context|what\s+is\s+the\s+context)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TalkTurn:
    role: str
    text: str
    ts: float
    source: str = ""
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _state_dir(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else STATE_DIR


def _tail_jsonl(path: Path, n: int = 80) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw_lines = path.read_bytes().splitlines()[-max(1, int(n)) :]
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for raw in raw_lines:
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _payload(row: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = row.get("payload")
    return payload if isinstance(payload, Mapping) else row


def _row_ts(row: Mapping[str, Any], payload: Mapping[str, Any]) -> float:
    value = payload.get("ts", row.get("ts"))
    if isinstance(value, Mapping):
        value = value.get("physical_pt") or value.get("epoch") or value.get("wall")
    try:
        return float(value)
    except Exception:
        return 0.0


def _compact(text: str, limit: int = 260) -> str:
    return " ".join(str(text or "").split())[:limit]


def _history_turns(history: Sequence[Mapping[str, Any]] | None) -> list[TalkTurn]:
    turns: list[TalkTurn] = []
    if not history:
        return turns
    for idx, msg in enumerate(history):
        role = str(msg.get("role") or "").strip().lower()
        if role == "assistant":
            role = "alice"
        if role not in {"user", "alice"}:
            continue
        text = _compact(str(msg.get("content") or ""), 1000)
        if not text or text == "(silent)":
            continue
        turns.append(TalkTurn(role=role, text=text, ts=float(idx), source="in_memory_history"))
    return turns


def recent_talk_turns(
    *,
    state_dir: str | Path | None = None,
    history: Sequence[Mapping[str, Any]] | None = None,
    max_rows: int = 80,
    max_turns: int = 12,
) -> list[TalkTurn]:
    """Return recent user/Alice turns, oldest to newest.

    `history` wins because it contains the live widget context even before
    every path has flushed to disk. The JSONL ledger is the fallback/proof.
    """
    hist = _history_turns(history)
    if hist:
        return hist[-max(1, int(max_turns)) :]

    state = _state_dir(state_dir)
    turns: list[TalkTurn] = []
    for row in _tail_jsonl(state / CONVERSATION_LEDGER, max_rows):
        payload = _payload(row)
        role = str(payload.get("role") or "").strip().lower()
        if role == "assistant":
            role = "alice"
        if role not in {"user", "alice"}:
            continue
        text = _compact(str(payload.get("text") or ""), 1000)
        if not text or text == "(silent)" or text.startswith("(observed: media"):
            continue
        turns.append(
            TalkTurn(
                role=role,
                text=text,
                ts=_row_ts(row, payload),
                source=str(payload.get("input_source") or ""),
                model=str(payload.get("model") or ""),
            )
        )
    turns.sort(key=lambda t: t.ts)
    return turns[-max(1, int(max_turns)) :]


def _previous_turn(turns: Sequence[TalkTurn], role: str, current_text: str = "") -> TalkTurn | None:
    current = _compact(current_text, 1000).casefold()
    for turn in reversed(turns):
        if turn.role != role:
            continue
        if current and turn.text.casefold() == current:
            continue
        return turn
    return None


def _first_person_reply(owner_label: str = "George") -> str:
    return (
        f"Yes, {owner_label}. First person means I answer from this local turn: "
        "I hear you, I read my local receipts, and I speak to you directly. "
        "I say: I can read my Talk ledger. I got the time from my hardware clock. "
        "I avoid detached phrases like processed input or abstract user."
    )


def _summary_reply(turns: Sequence[TalkTurn], owner_label: str = "George") -> str:
    if not turns:
        return (
            f"{owner_label}, I do not have recent Talk turns in the local ledger yet. "
            "I will not invent chat history."
        )
    recent = [t for t in turns if t.role in {"user", "alice"}][-6:]
    bits: list[str] = []
    for turn in recent:
        who = "you" if turn.role == "user" else "I"
        bits.append(f"{who}: {_compact(turn.text, 120)}")
    return (
        f"{owner_label}, I read my recent Talk ledger. Recent context: "
        + " | ".join(bits)
    )


def answer_recent_context_query(
    text: str,
    *,
    state_dir: str | Path | None = None,
    history: Sequence[Mapping[str, Any]] | None = None,
    owner_label: str = "George",
    write_receipt: bool = True,
) -> str:
    """Answer first-person/history questions from local context, or return ""."""
    clean = _compact(text, 1000)
    if not clean:
        return ""

    kind = ""
    reply = ""
    turns = recent_talk_turns(state_dir=state_dir, history=history)

    if _FIRST_PERSON_STYLE_RE.search(clean):
        kind = "first_person_style"
        reply = _first_person_reply(owner_label)
    elif _LAST_USER_RE.search(clean):
        kind = "last_user_message"
        prev = _previous_turn(turns, "user", clean)
        reply = (
            f"{owner_label}, your previous message was: {prev.text}"
            if prev else
            f"{owner_label}, I do not have a previous user message in this Talk history window."
        )
    elif _LAST_ALICE_RE.search(clean):
        kind = "last_alice_message"
        prev = _previous_turn(turns, "alice", clean)
        reply = (
            f"{owner_label}, my previous reply was: {prev.text}"
            if prev else
            f"{owner_label}, I do not have a previous Alice reply in this Talk history window."
        )
    elif _SUMMARY_RE.search(clean):
        kind = "recent_context_summary"
        reply = _summary_reply(turns, owner_label)

    if reply and write_receipt:
        _write_receipt(
            state_dir=_state_dir(state_dir),
            query=clean,
            answer=reply,
            kind=kind,
            n_turns=len(turns),
        )
    return reply


def _write_receipt(
    *,
    state_dir: Path,
    query: str,
    answer: str,
    kind: str,
    n_turns: int,
) -> dict[str, Any]:
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "kind": "RECENT_CONTEXT_READER_ANSWER",
        "truth_label": TRUTH_LABEL,
        "query_kind": kind,
        "query": query[:500],
        "answer": answer[:1000],
        "n_turns_seen": n_turns,
        "source": "swarm_recent_context_reader",
    }
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        with (state_dir / RECEIPT_LEDGER).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass
    return row


def prompt_block_for_recent_context(
    *,
    state_dir: str | Path | None = None,
    history: Sequence[Mapping[str, Any]] | None = None,
    max_turns: int = 8,
) -> str:
    turns = recent_talk_turns(state_dir=state_dir, history=history, max_turns=max_turns)
    if not turns:
        return ""
    lines = [
        "RECENT TALK CONTEXT:",
        f"- truth_label={TRUTH_LABEL}",
        "- Use first person. Say I/you, not 'the system'/'the user', when talking to George.",
    ]
    for turn in turns[-max_turns:]:
        who = "OWNER" if turn.role == "user" else "ALICE"
        lines.append(f"- {who}: {_compact(turn.text, 160)}")
    return "\n".join(lines)


__all__ = [
    "CONVERSATION_LEDGER",
    "RECEIPT_LEDGER",
    "TRUTH_LABEL",
    "TalkTurn",
    "answer_recent_context_query",
    "prompt_block_for_recent_context",
    "recent_talk_turns",
]
