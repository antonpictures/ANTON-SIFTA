#!/usr/bin/env python3
"""Phillipe saleability reflex — one honest sentence, no buyer-bar theater."""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "PHILIPPE_SALEABILITY_REFLEX_V1"
LEDGER_NAME = "philippe_saleability_reflex.jsonl"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

_PHILIPPE_RE = re.compile(r"\bphil(?:l?i|i)ppe\b|\bphillipe\b", re.IGNORECASE)
_SALEABILITY_RE = re.compile(
    r"\b(?:saleable|sellable|saleability|commercial|market|buyer|product)\b",
    re.IGNORECASE,
)
_BAR_RE = re.compile(r"\b(?:bar|honest|one\s+sentence|today|ready)\b", re.IGNORECASE)

_HONEST_SENTENCE = (
    "Not yet as a saleable whole product by Phillipe's bar: the trust-receipt wedge "
    "demo exists and George believes the code is real, but we still need a recorded "
    "buyer demo, a CrewAI/LangGraph benchmark row, and external users or revenue."
)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _append_receipt(
    *,
    owner_text: str,
    reply: str,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    row = {
        "schema": "PHILIPPE_SALEABILITY_REFLEX_ROW_V1",
        "truth_label": TRUTH_LABEL,
        "receipt_id": str(uuid.uuid4()),
        "ts": time.time(),
        "owner_text": " ".join(str(owner_text or "").split())[:400],
        "reply": reply,
        "basis": [
            "r1368/r1369/r1379 Phillipe bar: demo, use case, benchmark, users, revenue/pilots",
            "r1380 trust-receipt wedge exists on disk",
            "r1382 George YES founder vote recorded",
            "MiMo benchmark and outside users/revenue still missing",
        ],
    }
    path = _state_dir(state_dir) / LEDGER_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def is_philippe_saleability_question(text: str) -> bool:
    clean = " ".join(str(text or "").split())
    if not clean:
        return False
    if not _PHILIPPE_RE.search(clean):
        return False
    if not _SALEABILITY_RE.search(clean):
        return False
    return bool(_BAR_RE.search(clean) or "?" in clean)


def answer_philippe_saleability_question(
    text: str,
    *,
    state_dir: Optional[Path | str] = None,
    write: bool = True,
) -> str:
    if not is_philippe_saleability_question(text):
        return ""
    if write:
        _append_receipt(owner_text=text, reply=_HONEST_SENTENCE, state_dir=state_dir)
    return _HONEST_SENTENCE


__all__ = [
    "TRUTH_LABEL",
    "answer_philippe_saleability_question",
    "is_philippe_saleability_question",
]
