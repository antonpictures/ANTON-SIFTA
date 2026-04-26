#!/usr/bin/env python3
"""
System/swarm_whatsapp_receptor.py
═══════════════════════════════════════════════════════════════════════════
The WhatsApp Ingress Queue
Reads validated inbound WhatsApp messages from `.sifta_state/whatsapp_inbox.jsonl`.
"""

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_INBOX_FILE = _STATE / "whatsapp_inbox.jsonl"
_INGRESS_KEY_FILE = _STATE / "whatsapp_ingress.key"
_INGRESS_RECEIPTS = _STATE / "whatsapp_ingress_receipts.jsonl"

INBOX_SCHEMA = "SIFTA_WHATSAPP_INBOX_V1"
INBOX_SOURCE = "System.swarm_whatsapp_receptor"
INBOX_CONSUMER = "Applications.sifta_talk_to_alice_widget"
MAX_INBOX_TEXT_CHARS = 4000


def _canonical_payload(row: Dict[str, Any]) -> str:
    stripped = {
        k: v for k, v in row.items()
        if k not in {
            "signature",
            "processed",
            "processed_ts",
            "processed_by",
            "processed_status",
            "consume_receipt_hash",
        }
    }
    return json.dumps(stripped, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_ingress_secret(secret: Optional[str] = None) -> str:
    """Return the local shared secret used to authenticate inbox rows."""
    if secret:
        return secret
    _INGRESS_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _INGRESS_KEY_FILE.exists():
        _INGRESS_KEY_FILE.write_text(secrets.token_hex(32), encoding="utf-8")
        try:
            os.chmod(_INGRESS_KEY_FILE, 0o600)
        except OSError:
            pass
    return _INGRESS_KEY_FILE.read_text(encoding="utf-8").strip()


def sign_inbox_row(row: Dict[str, Any], *, secret: Optional[str] = None) -> str:
    key = _read_ingress_secret(secret).encode("utf-8")
    body = _canonical_payload(row).encode("utf-8")
    return hmac.new(key, body, hashlib.sha256).hexdigest()


def build_inbox_row(
    text: str,
    *,
    from_jid: str,
    name: Optional[str] = None,
    ts: Optional[float] = None,
    secret: Optional[str] = None,
) -> Dict[str, Any]:
    text = (text or "").strip()
    row: Dict[str, Any] = {
        "schema": INBOX_SCHEMA,
        "source": INBOX_SOURCE,
        "transport": "whatsapp",
        "direction": "incoming",
        "ts": time.time() if ts is None else float(ts),
        "from_jid": from_jid,
        "name": name or "",
        "text": text,
        "message_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "processed": False,
    }
    row["signature"] = sign_inbox_row(row, secret=secret)
    return row


def validate_inbox_row(row: Any, *, secret: Optional[str] = None) -> tuple[bool, str]:
    if not isinstance(row, dict):
        return False, "row_not_object"
    if row.get("schema") != INBOX_SCHEMA:
        return False, "schema_mismatch"
    if row.get("source") != INBOX_SOURCE:
        return False, "source_mismatch"
    if row.get("transport") != "whatsapp" or row.get("direction") != "incoming":
        return False, "transport_mismatch"
    text = row.get("text")
    if not isinstance(text, str) or not text.strip():
        return False, "empty_text"
    if len(text) > MAX_INBOX_TEXT_CHARS:
        return False, "text_too_long"
    expected_text_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
    if row.get("message_sha256") != expected_text_hash:
        return False, "message_hash_mismatch"
    signature = row.get("signature")
    if not isinstance(signature, str) or len(signature) != 64:
        return False, "missing_signature"
    expected_signature = sign_inbox_row(row, secret=secret)
    if not hmac.compare_digest(signature, expected_signature):
        return False, "signature_mismatch"
    return True, "ok"


def _receipt_for(row: Dict[str, Any], *, dry_run: bool, now: float) -> Dict[str, Any]:
    receipt = {
        "event_kind": "WHATSAPP_INGRESS_CONSUME",
        "ts": now,
        "schema": INBOX_SCHEMA,
        "source": INBOX_SOURCE,
        "consumer": INBOX_CONSUMER,
        "from_jid": row.get("from_jid"),
        "message_sha256": row.get("message_sha256"),
        "inbox_signature": row.get("signature"),
        "dry_run": bool(dry_run),
        "accepted": True,
    }
    receipt["receipt_hash"] = hashlib.sha256(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return receipt


def consume_next_inbox_message(
    inbox_file: Path = _INBOX_FILE,
    *,
    receipt_file: Path = _INGRESS_RECEIPTS,
    dry_run: bool = False,
    secret: Optional[str] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "accepted": False,
        "reason": "empty",
        "text": "",
        "row": None,
        "receipt": None,
        "dry_run": bool(dry_run),
        "invalid_count": 0,
        "duplicate_count": 0,
    }
    if not inbox_file.exists():
        return result

    raw_lines = inbox_file.read_text(encoding="utf-8", errors="replace").splitlines()
    if not raw_lines:
        return result

    parsed: list[tuple[str, Optional[Dict[str, Any]], bool, str]] = []
    consumed_signatures: set[str] = set()
    for line in raw_lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            parsed.append((line, None, False, "json_decode"))
            result["invalid_count"] += 1
            continue
        ok, reason = validate_inbox_row(row, secret=secret)
        if ok and row.get("processed"):
            consumed_signatures.add(str(row.get("signature")))
        elif not ok:
            result["invalid_count"] += 1
        parsed.append((line, row if isinstance(row, dict) else None, ok, reason))

    # Build a set of recently-consumed text hashes (within 30s window)
    # to catch the same message arriving from both personal JID and group JID.
    _TEXT_DEDUP_WINDOW_S = 30.0
    _now = time.time() if now is None else float(now)
    consumed_text_hashes: set[str] = set()
    for _line, row, ok, _reason in parsed:
        if row and ok and row.get("processed"):
            row_ts = float(row.get("ts", 0))
            if _now - row_ts < _TEXT_DEDUP_WINDOW_S:
                consumed_text_hashes.add(str(row.get("message_sha256", "")))

    selected_index: Optional[int] = None
    selected_row: Optional[Dict[str, Any]] = None
    for idx, (_line, row, ok, reason) in enumerate(parsed):
        if not ok or row is None or row.get("processed"):
            continue
        sig = str(row.get("signature"))
        text_hash = str(row.get("message_sha256", ""))
        # Dedup: same signature OR same text within 30s window
        if sig in consumed_signatures or text_hash in consumed_text_hashes:
            result["duplicate_count"] += 1
            row["processed"] = True
            row["processed_ts"] = now or time.time()
            row["processed_by"] = INBOX_CONSUMER
            row["processed_status"] = "duplicate"
            consumed_text_hashes.add(text_hash)
            continue
        selected_index = idx
        selected_row = row
        # Mark this text as consumed so subsequent identical rows are also deduped
        consumed_text_hashes.add(text_hash)
        break

    if selected_row is None or selected_index is None:
        result["reason"] = "no_valid_unprocessed_message"
        if not dry_run:
            new_lines = []
            for line, row, _ok, _reason in parsed:
                new_lines.append(json.dumps(row, ensure_ascii=False) if row is not None else line)
            inbox_file.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")
        return result

    t = time.time() if now is None else float(now)
    receipt = _receipt_for(selected_row, dry_run=dry_run, now=t)
    if not dry_run:
        selected_row["processed"] = True
        selected_row["processed_ts"] = t
        selected_row["processed_by"] = INBOX_CONSUMER
        selected_row["processed_status"] = "accepted"
        selected_row["consume_receipt_hash"] = receipt["receipt_hash"]

        new_lines = []
        for line, row, _ok, _reason in parsed:
            new_lines.append(json.dumps(row, ensure_ascii=False) if row is not None else line)
        inbox_file.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")

        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(receipt_file, json.dumps(receipt, ensure_ascii=False) + "\n")
        except Exception:
            receipt_file.parent.mkdir(parents=True, exist_ok=True)
            with receipt_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(receipt, ensure_ascii=False) + "\n")

    result.update({
        "accepted": True,
        "reason": "accepted",
        "text": selected_row["text"].strip(),
        "name": selected_row.get("name", ""),
        "row": selected_row,
        "receipt": receipt,
    })
    return result
