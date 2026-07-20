#!/usr/bin/env python3
"""Every owner turn is a small body execution.

r1337: Talk must leave one grounded receipt per owner turn even when there is
no external effector. In that case the body act is a local stigmergic memory
deposit: observed owner text + reply hash + source hook.

This organ is deliberately light: append-only JSONL, no network, no repo scan.
Truth label: BODY_TURN_EXECUTION_V1
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "BODY_TURN_EXECUTION_V1"
SCHEMA = "BODY_TURN_EXECUTION_ROW_V1"
LEDGER_NAME = "body_turn_execution.jsonl"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _sha(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", errors="replace")).hexdigest()


def _excerpt(text: str, limit: int = 240) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    return clean[:limit]


def _classify_body_act(owner_text: str, assistant_text: str = "") -> str:
    text = (owner_text or "").strip().lower()
    if not text:
        return "empty_turn_memory_deposit"
    if re.search(r"\b(search|open|click|close|scroll|type|load|find|look up|go to)\b", text):
        return "effector_or_search_turn_receipted"
    if re.search(r"\b(wrong|incorrect|broken|bug|fix this|try again|not right)\b", text):
        return "owner_correction_memory_deposit"
    if len(text) <= 16 and re.fullmatch(r"(ok+|okay+|oh+|mm+|thanks?|thank you+|haha+|lol)[.! ]*", text):
        return "phatic_turn_memory_deposit"
    if assistant_text:
        return "dialogue_turn_memory_deposit"
    return "owner_turn_memory_deposit"


def _recent_duplicate(path: Path, fingerprint: str, now: float, window_s: float = 10.0) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 32768))
            chunk = f.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    for line in reversed([ln.strip() for ln in chunk.splitlines() if ln.strip()]):
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("turn_fingerprint") != fingerprint:
            continue
        try:
            age = now - float(row.get("ts", 0.0) or 0.0)
        except Exception:
            age = window_s + 1.0
        if 0.0 <= age <= window_s:
            copy = dict(row)
            copy["dedupe_status"] = "reused_recent_body_turn_execution"
            return copy
        return None
    return None


def record_body_turn_execution(
    *,
    owner_text: str = "",
    assistant_text: str = "",
    state_dir: Optional[Path | str] = None,
    turn_source: str = "talk_post_turn",
    tts_ok: Optional[bool] = None,
    tts_error: str = "",
    body_act: str = "",
) -> dict[str, Any]:
    """Append the per-turn body execution receipt and return the row."""
    sd = _state_dir(state_dir)
    now = time.time()
    owner_sha = _sha(owner_text)
    assistant_sha = _sha(assistant_text)
    fingerprint = _sha(f"{owner_sha}:{assistant_sha}:{turn_source}")
    path = sd / LEDGER_NAME

    existing = _recent_duplicate(path, fingerprint, now)
    if existing is not None:
        return existing

    row: dict[str, Any] = {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "ts": now,
        "receipt_id": f"bodyturn-{fingerprint[:12]}-{int(now * 1000)}",
        "turn_fingerprint": fingerprint,
        "turn_source": turn_source,
        "execution_status": "EXECUTED",
        "body_act": body_act or _classify_body_act(owner_text, assistant_text),
        "grounding": "local_append_only_ledger",
        "owner_text_sha256": owner_sha,
        "assistant_text_sha256": assistant_sha,
        "owner_text_excerpt": _excerpt(owner_text),
        "assistant_text_excerpt": _excerpt(assistant_text),
        "tts_ok": tts_ok,
        "tts_error": _excerpt(tts_error, 200),
        "doctrine": "every owner turn leaves a body receipt; no external action is claimed unless an effector receipt exists",
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception as exc:
        row["execution_status"] = "WRITE_FAILED"
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def summary_for_prompt(*, state_dir: Optional[Path | str] = None, max_rows: int = 2) -> str:
    """Small prompt summary of latest body-turn receipts."""
    sd = _state_dir(state_dir)
    path = sd / LEDGER_NAME
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_rows:]
    except Exception:
        return ""
    rows: list[dict[str, Any]] = []
    for line in lines:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("truth_label") == TRUTH_LABEL:
            rows.append(row)
    if not rows:
        return ""
    out = ["BODY TURN EXECUTION RECEIPTS (latest; every owner turn is body work):"]
    for row in rows:
        out.append(
            f"- {row.get('body_act')} status={row.get('execution_status')} "
            f"receipt={row.get('receipt_id')} owner={row.get('owner_text_excerpt')!r}"
        )
    return "\n".join(out)


__all__ = [
    "TRUTH_LABEL",
    "SCHEMA",
    "LEDGER_NAME",
    "record_body_turn_execution",
    "summary_for_prompt",
]
