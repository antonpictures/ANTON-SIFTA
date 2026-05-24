#!/usr/bin/env python3
"""System/swarm_hard_recall.py — Hard Memory Recall (exact retrieval, no summary).

George 2026-05-23: he asked Alice "read back my previous prompt" and she generated
commentary ABOUT summarizing instead of the actual words. Memory recall collapsed
into language-cloud mode. The fix is a HARD recall path:

    If the owner says "read back" / "what did I say" / "quote" / "repeat my
    previous prompt" / "show previous message" — NO abstraction, NO summary,
    NO meta-analysis. ONLY the exact ledger row, verbatim.

This organ reads the one global chat ledger (.sifta_state/alice_conversation.jsonl),
finds the owner's exact previous turn(s), and returns the raw text. It does not
call the cortex. That is the whole point: deterministic retrieval, so a small
flaky cortex can never philosophise over a memory question.

Ledger schema (probed 2026-05-23):
    row = {event_id, ts, payload, prev_hash, this_hash}
    payload = {ts, role, text, ...}      # role in {'user','alice','corvid',...}
    payload may be a dict OR a JSON string — handled both ways.

Honest label (covenant §7.11): OBSERVED_HARD_RECALL_V1. Deterministic ledger
retrieval, receipted. Work in progress.

Standalone + Qt-free. For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_CONVO = _REPO / ".sifta_state" / "alice_conversation.jsonl"
_LEDGER = _REPO / ".sifta_state" / "hard_recall.jsonl"

# Owner turn roles (the ledger uses 'user'; accept synonyms defensively).
_OWNER_ROLES = {"user", "owner", "george", "primary_operator"}

# A recall request: the owner wants exact words back, not a summary.
_RECALL_RE = re.compile(
    r"\b(?:read\s+back|what\s+did\s+i\s+(?:say|ask|write)|"
    r"quote(?:\s+me)?|repeat\s+(?:my|the|that)|say\s+(?:that\s+)?again|"
    r"show\s+(?:me\s+)?(?:my|the)\s+(?:previous|last|prior)\s+(?:message|prompt|turn)|"
    r"(?:my|the)\s+(?:previous|last|prior)\s+(?:prompt|message|turn))\b",
    re.IGNORECASE,
)


def is_recall_request(text: str) -> bool:
    """True if this turn asks to read back exact prior words (heuristic v1)."""
    return bool(_RECALL_RE.search(text or ""))


def _coerce_payload(row: dict) -> dict:
    pay = row.get("payload")
    if isinstance(pay, str):
        try:
            pay = json.loads(pay)
        except Exception:
            return {}
    return pay if isinstance(pay, dict) else {}


def _read_turns(max_rows: int = 400) -> list[dict]:
    """Return recent {role,text,ts} turns oldest->newest. Reads only the tail."""
    if not _CONVO.exists():
        return []
    try:
        lines = _CONVO.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    turns: list[dict] = []
    for line in lines[-max_rows:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        pay = _coerce_payload(row)
        if not pay:
            continue
        role = str(pay.get("role") or "").strip().lower()
        text = pay.get("text")
        if not isinstance(text, str):
            continue
        turns.append({"role": role, "text": text, "ts": pay.get("ts") or row.get("ts")})
    return turns


def recall_previous_owner_turn(n_back: int = 1, *, exclude_recall: bool = True) -> dict:
    """Return the owner's exact n-th previous turn (verbatim), skipping recall
    requests themselves so 'read back my previous prompt' returns the real prior
    prompt, not the recall command."""
    turns = _read_turns()
    owner_turns = [t for t in turns if t["role"] in _OWNER_ROLES]
    if exclude_recall:
        owner_turns = [t for t in owner_turns if not is_recall_request(t["text"])]
    if not owner_turns:
        return {"found": False, "text": "", "ts": None}
    idx = len(owner_turns) - n_back
    if idx < 0:
        idx = 0
    t = owner_turns[idx]
    return {"found": True, "text": t["text"], "ts": t["ts"], "n_back": n_back}


def _receipt(row: dict) -> None:
    try:
        _LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def hard_recall(text: str) -> dict:
    """THE guard the reply path calls. If the turn is a recall request, return the
    exact prior owner text to output VERBATIM (no cortex, no summary).

    Returns:
      {"mode": "HARD_RECALL", "exact_text": <verbatim>, "found": bool, ...}  on recall
      {"mode": "NONE"}                                                       otherwise
    """
    if not is_recall_request(text):
        return {"mode": "NONE"}
    rec = recall_previous_owner_turn(1)
    if rec["found"]:
        exact = f'Your previous prompt was:\n\n"{rec["text"]}"'
    else:
        exact = "I have no earlier prompt from you in the global chat ledger to read back."
    out = {
        "mode": "HARD_RECALL",
        "found": rec["found"],
        "exact_text": exact,
        "retrieved_text": rec.get("text", ""),
        "retrieved_ts": rec.get("ts"),
        "truth_label": "OBSERVED_HARD_RECALL_V1",
    }
    _receipt({"ts": time.time(), "kind": "HARD_RECALL", "request_preview": text[:120],
              "found": rec["found"], "retrieved_ts": rec.get("ts"),
              "truth_label": "OBSERVED_HARD_RECALL_V1"})
    return out


if __name__ == "__main__":
    print("=== hard recall smoke ===")
    for q in ["read back for me my previous prompt pls", "what did I say before?",
              "quote my last message", "summarize the budget"]:
        r = hard_recall(q)
        print(f"[{r['mode']:11}] <- {q!r}")
        if r["mode"] == "HARD_RECALL":
            print("   ->", r["exact_text"].replace("\n", " ")[:120])
