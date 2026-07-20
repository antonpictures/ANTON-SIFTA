#!/usr/bin/env python3
"""Receipt-gated round state for Alice Browser <-> Grok dialogue.

A browser dialogue turn is treated like a robot joint move: signal, receipt,
proof, and an explicit next state. Predecessor receipts may be referenced many
times as history, but spend_receipts are consumed once to advance the round.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "GROK_BROWSER_ROUND_STATE_V1"
BAD_TRUTH_LABEL = "GROK_BROWSER_ROUND_BAD_EXECUTION_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE_FILE = "grok_browser_round_state.json"
_LEDGER = "grok_browser_round_state.jsonl"


def state_dir_path(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def clean_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def clean_text_sha256(text: str) -> str:
    return hashlib.sha256(clean_text(text).encode("utf-8")).hexdigest()


def _load_state(sd: Path) -> dict[str, Any]:
    path = sd / _STATE_FILE
    if not path.exists():
        return {"schema": TRUTH_LABEL, "truth_label": TRUTH_LABEL, "spent_receipts": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("spent_receipts", {})
            return data
    except Exception:
        pass
    return {"schema": TRUTH_LABEL, "truth_label": TRUTH_LABEL, "spent_receipts": {}}


def _save_state(sd: Path, state: dict[str, Any]) -> None:
    state["ts"] = time.time()
    (sd / _STATE_FILE).write_text(
        json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )


def _append(sd: Path, row: dict[str, Any]) -> None:
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    for name in (_LEDGER, "work_receipts.jsonl"):
        try:
            with (sd / name).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass


def _compact_receipts(values: list[str] | tuple[str, ...] | None) -> list[str]:
    out: list[str] = []
    for value in values or []:
        v = str(value or "").strip()
        if v and v not in out:
            out.append(v)
    return out


def current_round_state(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    return _load_state(state_dir_path(state_dir))


def record_round_transition(
    *,
    state: str,
    event: str,
    round_number: int = 0,
    ok: bool = True,
    predecessor_receipts: list[str] | tuple[str, ...] | None = None,
    spend_receipts: list[str] | tuple[str, ...] | None = None,
    payload_text: str = "",
    payload_sha256: str = "",
    details: Optional[dict[str, Any]] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Append one round-state transition and enforce spend-once receipts."""
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    local = _load_state(sd)
    predecessor_ids = _compact_receipts(list(predecessor_receipts or []))
    spend_ids = _compact_receipts(list(spend_receipts or []))
    spent = dict(local.get("spent_receipts") or {})
    conflicts = {rid: spent.get(rid) for rid in spend_ids if spent.get(rid)}

    receipt_id = f"grok-round-{uuid.uuid4().hex[:12]}"
    payload_hash = str(payload_sha256 or "").strip()
    if not payload_hash and payload_text:
        payload_hash = clean_text_sha256(payload_text)

    row = {
        "schema": TRUTH_LABEL if ok and not conflicts else BAD_TRUTH_LABEL,
        "truth_label": TRUTH_LABEL if ok and not conflicts else BAD_TRUTH_LABEL,
        "ts": time.time(),
        "receipt_id": receipt_id,
        "round_number": int(round_number or local.get("round_number") or 0),
        "state": str(state or ""),
        "event": str(event or ""),
        "ok": bool(ok and not conflicts),
        "predecessor_receipts": predecessor_ids,
        "spend_receipts": spend_ids,
        "payload_sha256": payload_hash,
        "payload_preview": clean_text(payload_text)[:240] if payload_text else "",
        "details": dict(details or {}),
    }
    if conflicts:
        row["status"] = "double_spend_blocked"
        row["double_spend_conflicts"] = conflicts
    else:
        row["status"] = "transition_recorded" if ok else "bad_execution_recorded"
        for rid in spend_ids:
            spent[rid] = receipt_id
        local["current_state"] = row["state"]
        local["round_number"] = row["round_number"]
        local["last_transition_receipt"] = receipt_id
        local["last_event"] = row["event"]
        local["last_payload_sha256"] = payload_hash
        local["spent_receipts"] = spent
        _save_state(sd, local)
    _append(sd, row)
    return row


def latest_round_lines(*, state_dir: Optional[Path | str] = None, limit: int = 8) -> list[str]:
    sd = state_dir_path(state_dir)
    path = sd / _LEDGER
    if not path.exists():
        return ["  Live state ledger: no round-state transitions yet."]
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, limit):]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except Exception:
            continue
    if not rows:
        return ["  Live state ledger: no readable round-state transitions yet."]
    lines = ["LIVE ROUND-STATE LEDGER:"]
    for row in rows[-limit:]:
        ok = "OK" if row.get("ok") else "BAD"
        preds = ",".join(row.get("predecessor_receipts") or [])[:80]
        spends = ",".join(row.get("spend_receipts") or [])[:80]
        lines.append(
            f"  R{int(row.get('round_number') or 0)} {row.get('state')} {ok} "
            f"event={row.get('event')} receipt={row.get('receipt_id')} "
            f"pred=[{preds}] spend=[{spends}]"
        )
    return lines


__all__ = [
    "BAD_TRUTH_LABEL",
    "TRUTH_LABEL",
    "clean_text",
    "clean_text_sha256",
    "current_round_state",
    "latest_round_lines",
    "record_round_transition",
    "state_dir_path",
]
