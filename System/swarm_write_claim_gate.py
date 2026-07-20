#!/usr/bin/env python3
"""Receipt gate for write claims in Alice's visible replies.

"Consider it added" is allowed only when a schedule/journal/memory receipt
exists, or when this gate can perform the missing write through the canonical
organ. Otherwise the visible reply is rewritten honestly.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

TRUTH_LABEL = "WRITE_CLAIM_GATE_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

_CLAIM_RE = re.compile(
    r"\b(?:"
    r"consider\s+it\s+(?:added|done|logged|noted|saved)|"
    r"(?:i(?:'ve| have)?|it(?:'s| is)|that(?:'s| is))\s+"
    r"(?:added|logged|noted|saved|scheduled|written|wrote|stored|recorded)|"
    r"(?:added|logged|noted|saved|scheduled|written|stored|recorded)\s+"
    r"(?:to|in|on)\s+(?:your|my|the)?\s*(?:schedule|calendar|journal|diary|memory|ledger)"
    r")\b",
    re.IGNORECASE,
)

_SCHEDULE_WORD_RE = re.compile(r"\b(?:schedule|calendar|reminder|task|todo|appointment|meeting|class|lesson)\b", re.I)
_JOURNAL_WORD_RE = re.compile(r"\b(?:journal|diary|logged|noted|note|recorded)\b", re.I)
_MEMORY_WORD_RE = re.compile(r"\b(?:memory|remembered|stored|saved)\b", re.I)


def _state_dir(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _row_ts(row: Dict[str, Any]) -> float:
    for key in ("ts", "created", "timestamp", "created_at"):
        value = row.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict):
            for inner in ("physical_pt", "ts", "epoch"):
                inner_value = value.get(inner)
                if isinstance(inner_value, (int, float)):
                    return float(inner_value)
    return 0.0


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
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


def _ledger_has_fresh_row(path: Path, since_ts: float) -> bool:
    for row in _iter_jsonl(path):
        if _row_ts(row) >= since_ts:
            return True
    return False


def _claim_lanes(reply_text: str) -> List[str]:
    text = reply_text or ""
    lanes: List[str] = []
    if _SCHEDULE_WORD_RE.search(text):
        lanes.append("schedule")
    if _JOURNAL_WORD_RE.search(text):
        lanes.append("journal")
    if _MEMORY_WORD_RE.search(text):
        lanes.append("memory")
    if not lanes:
        lanes.append("write")
    return lanes


def _schedule_item_from_reply(reply_text: str) -> str:
    text = " ".join((reply_text or "").split())
    patterns = [
        r"Added to my schedule:\s*(?P<item>.+?)(?:\s+\([^)]*\))?[.!?]?$",
        r"(?:I(?:'ve| have)?\s+added|I\s+scheduled)\s+(?P<item>.+?)\s+(?:to|on|in)\s+(?:your|my|the)?\s*(?:schedule|calendar)",
        r"Consider it added(?:\s+to\s+(?:your|my|the)?\s*(?:schedule|calendar))?:\s*(?P<item>.+?)[.!?]?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            item = re.sub(r"\s+", " ", match.group("item")).strip(" .,:;")
            if item and len(item) > 2:
                return item[:240]
    return ""


def _backfill_schedule(reply_text: str, *, state: Path) -> Optional[Dict[str, Any]]:
    item = _schedule_item_from_reply(reply_text)
    if not item:
        return None
    try:
        from System.stigmergic_schedule import add_task

        row = add_task(
            item,
            priority=2,
            source="swarm_write_claim_gate.backfill",
            path=state / "stigmergic_schedule.jsonl",
            claim_backfilled_by_gate=True,
        )
    except Exception:
        return None
    return row


def _backfill_journal(reply_text: str, *, state: Path) -> Optional[Dict[str, Any]]:
    line = re.sub(_CLAIM_RE, "", reply_text or "", count=1).strip(" .,:;-")
    if not line:
        line = "Write-claim gate backfilled an otherwise naked journal claim."
    row = {
        "ts": time.time(),
        "line": line[:500],
        "source": "swarm_write_claim_gate.backfill",
        "truth_label": "WRITE_CLAIM_GATE_JOURNAL_BACKFILL_V1",
        "claim_backfilled_by_gate": True,
    }
    try:
        from System.swarm_first_person_journal import append_first_person_journal_row

        row = append_first_person_journal_row(
            row,
            state_dir=state,
            pulse=True,
        )
    except Exception:
        try:
            from System.jsonl_file_lock import append_line_locked

            append_line_locked(
                state / "alice_first_person_journal.jsonl",
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except Exception:
            try:
                with (state / "alice_first_person_journal.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            except Exception:
                return None
    return row


def _record_phantom_action(
    *,
    owner_text: str,
    alice_reply: str,
    state: Path,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        if state.resolve() != _STATE.resolve():
            raise RuntimeError("local_state_tracker_fallback")
        from Applications.sifta_stigmergic_deterministic_tracker import (
            record_deterministic_visible_short_reply,
        )

        return record_deterministic_visible_short_reply(
            owner_text=owner_text or "",
            alice_reply=alice_reply or "",
            source="swarm_write_claim_gate",
            bypass_type="phantom_action",
            details=details,
        )
    except Exception as exc:
        row = {
            "ts": time.time(),
            "truth_label": "DETERMINISTIC_WITHOUT_CORTEX_MISTAKE_V1",
            "bypass_type": "phantom_action",
            "owner_text_preview": str(owner_text or "")[:260],
            "alice_reply_preview": str(alice_reply or "")[:260],
            "source": "swarm_write_claim_gate",
            "details": {**details, "tracker_error": f"{type(exc).__name__}: {exc}"},
        }
        try:
            from System.jsonl_file_lock import append_line_locked

            append_line_locked(
                state / "deterministic_mistakes.jsonl",
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        return row


def _write_gate_receipt(state: Path, row: Dict[str, Any]) -> None:
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(
            state / "write_claim_gate.jsonl",
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception:
        try:
            with (state / "write_claim_gate.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass


def verify_write_claims(
    reply_text: str,
    since_ts: float,
    state_dir: Optional[Path | str] = None,
    *,
    owner_text: str = "",
) -> Dict[str, Any]:
    """Verify, backfill, or rewrite naked write claims."""
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    reply = str(reply_text or "")
    if not reply.strip() or not _CLAIM_RE.search(reply):
        return {"ok": True, "changed": False, "reply_text": reply, "status": "no_claim"}

    lanes = _claim_lanes(reply)
    ledger_by_lane = {
        "schedule": state / "stigmergic_schedule.jsonl",
        "journal": state / "alice_first_person_journal.jsonl",
        "memory": state / "memory_ledger.jsonl",
    }
    found_lanes = [
        lane for lane in lanes
        if lane in ledger_by_lane and _ledger_has_fresh_row(ledger_by_lane[lane], since_ts)
    ]
    if found_lanes:
        receipt = {
            "ts": time.time(),
            "truth_label": TRUTH_LABEL,
            "status": "claim_receipted",
            "lanes": lanes,
            "found_lanes": found_lanes,
            "changed": False,
        }
        _write_gate_receipt(state, receipt)
        return {"ok": True, "changed": False, "reply_text": reply, **receipt}

    backfilled: Optional[Dict[str, Any]] = None
    if "schedule" in lanes:
        backfilled = _backfill_schedule(reply, state=state)
    if backfilled is None and "journal" in lanes:
        backfilled = _backfill_journal(reply, state=state)
    if backfilled is not None:
        receipt = {
            "ts": time.time(),
            "truth_label": TRUTH_LABEL,
            "status": "claim_backfilled",
            "lanes": lanes,
            "changed": False,
            "backfilled_row_id": backfilled.get("schedule_id") or backfilled.get("journal_id") or backfilled.get("ts"),
        }
        _write_gate_receipt(state, receipt)
        return {"ok": True, "changed": False, "reply_text": reply, "backfilled": True, **receipt}

    repaired = (
        "I have NOT written this yet — my write-claim gate found no schedule, journal, "
        "or memory receipt for that claim. Say `add ...` or `note ...` and I will write it with a receipt."
    )
    details = {
        "lanes": lanes,
        "since_ts": float(since_ts or 0.0),
        "original_reply": reply[:500],
        "repair": "visible_reply_rewritten_no_write_receipt",
    }
    tracker_row = _record_phantom_action(
        owner_text=owner_text,
        alice_reply=reply,
        state=state,
        details=details,
    )
    receipt = {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "status": "claim_rewritten_no_receipt",
        "lanes": lanes,
        "changed": True,
        "tracker_receipt_id": tracker_row.get("receipt_id"),
        "original_reply": reply[:500],
        "replacement_reply": repaired,
    }
    _write_gate_receipt(state, receipt)
    return {"ok": False, "changed": True, "reply_text": repaired, **receipt}


__all__ = ["TRUTH_LABEL", "verify_write_claims"]
