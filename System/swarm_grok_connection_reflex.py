#!/usr/bin/env python3
"""Grok connection reflex: local fallback + owner notice ledger.

This organ is intentionally small and append-only:
1) detect Grok/xAI auth-connectivity breakage,
2) register a fallback incident with timestamps and receipt refs,
3) queue one owner-facing notice that can be delivered on the next turn.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

TRUTH_LABEL = "GROK_CONNECTION_REFLEX_V1"


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[Dict[str, Any]]:
    if not path.exists():
        return []
    out: list[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                out.append(row)
    except Exception:
        return []
    return out


def _utc_iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def should_trigger_reflex(model_name: str, failure_message: str) -> bool:
    model = str(model_name or "").strip().lower()
    if not (model.startswith("grok:") or model.startswith("grok-")):
        return False
    msg = str(failure_message or "").strip().lower()
    if not msg:
        return False
    needles = (
        "no xai credential found",
        "xai http 401",
        "xai http 403",
        "can't reach xai api",
        "xai call timed out",
        "grok cli failed",
        "grok cli launch failed",
        "grok cli timed out",
        "grok cli returned empty output",
    )
    return any(token in msg for token in needles)


def register_reflex_event(
    *,
    state_dir: Path,
    from_model: str,
    fallback_model: str,
    failure_message: str,
    switch_ok: bool,
) -> Dict[str, Any]:
    """Append incident, diary row, and work receipt; return pending notice row."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    ts = time.time()
    notice_id = f"grok_fallback_{uuid.uuid4().hex[:12]}"
    failure_head = str(failure_message or "").strip().replace("\n", " ")[:220]

    notice_row = {
        "ts": ts,
        "ts_iso": _utc_iso(ts),
        "schema": TRUTH_LABEL,
        "kind": "pending_owner_notice",
        "notice_id": notice_id,
        "from_model": str(from_model or ""),
        "fallback_model": str(fallback_model or ""),
        "switch_ok": bool(switch_ok),
        "failure_head": failure_head,
        "source": "talk_to_alice_widget",
    }
    _append_jsonl(state_dir / "grok_connection_reflex.jsonl", notice_row)

    diary_row = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "title": "Grok connection reflex fallback",
        "summary": (
            f"Grok path failed ({failure_head}). "
            f"Switched talk cortex to {fallback_model} (ok={bool(switch_ok)})."
        ),
        "notice_id": notice_id,
        "source": "swarm_grok_connection_reflex",
    }
    _append_jsonl(state_dir / "episodic_diary.jsonl", diary_row)

    work_receipt_id = f"work_receipt_{uuid.uuid4().hex[:12]}"
    work_row = {
        "ts": ts,
        "id": work_receipt_id,
        "kind": "grok_connection_reflex_fallback",
        "receipt_id": notice_id,
        "status": "ok" if switch_ok else "degraded",
        "from_model": str(from_model or ""),
        "fallback_model": str(fallback_model or ""),
        "failure_head": failure_head,
        "files_touched": [
            ".sifta_state/swimmer_ollama_assignments.json",
            ".sifta_state/grok_connection_reflex.jsonl",
            ".sifta_state/episodic_diary.jsonl",
        ],
        "tests": "not_run_runtime_reflex",
        "truth_label": TRUTH_LABEL,
    }
    _append_jsonl(state_dir / "work_receipts.jsonl", work_row)
    return notice_row


def claim_pending_owner_notice(*, state_dir: Path) -> Optional[Dict[str, Any]]:
    """Claim the newest undelivered pending notice and append delivery row."""
    state_dir = Path(state_dir)
    ledger = state_dir / "grok_connection_reflex.jsonl"
    rows = _read_jsonl(ledger)
    if not rows:
        return None

    delivered: set[str] = set()
    for row in rows:
        if str(row.get("kind") or "") != "owner_notice_delivered":
            continue
        rid = str(row.get("notice_id") or "").strip()
        if rid:
            delivered.add(rid)

    pending: Optional[Dict[str, Any]] = None
    for row in reversed(rows):
        if str(row.get("kind") or "") != "pending_owner_notice":
            continue
        rid = str(row.get("notice_id") or "").strip()
        if not rid or rid in delivered:
            continue
        pending = row
        break

    if pending is None:
        return None

    ts = time.time()
    _append_jsonl(
        ledger,
        {
            "ts": ts,
            "ts_iso": _utc_iso(ts),
            "schema": TRUTH_LABEL,
            "kind": "owner_notice_delivered",
            "notice_id": str(pending.get("notice_id") or ""),
            "source": "talk_to_alice_widget",
        },
    )
    return pending


def format_owner_notice(row: Dict[str, Any]) -> str:
    ts_iso = str(row.get("ts_iso") or "")
    from_model = str(row.get("from_model") or "grok:grok-4.3")
    fallback_model = str(row.get("fallback_model") or "")
    failure_head = str(row.get("failure_head") or "connection/auth failure")
    return (
        f"I logged a Grok connection break at {ts_iso}. "
        f"I was on {from_model}, switched to local cortex {fallback_model}, "
        f"and recorded the failure reason: {failure_head}."
    ).strip()


__all__ = [
    "TRUTH_LABEL",
    "should_trigger_reflex",
    "register_reflex_event",
    "claim_pending_owner_notice",
    "format_owner_notice",
]
