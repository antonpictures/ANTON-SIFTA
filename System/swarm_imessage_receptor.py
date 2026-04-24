#!/usr/bin/env python3
"""
System/swarm_imessage_receptor.py
═══════════════════════════════════════════════════════════════════════════
The Synaptic Tap (Two-Way iMessage Telepathy) — C47H 2026-04-23

A background daemon that monitors the local macOS Messages SQLite database
(`chat.db`) for incoming texts from the Architect.

When a new text arrives, it drops it into `.sifta_state/imessage_inbox.jsonl`
for Alice's brain to read and respond to natively.
"""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_ID_FILE = _STATE / "architect_imessage_id.txt"
_INBOX_FILE = _STATE / "imessage_inbox.jsonl"
_INGRESS_KEY_FILE = _STATE / "imessage_ingress.key"
_INGRESS_RECEIPTS = _STATE / "imessage_ingress_receipts.jsonl"
_STATE_FILE = _STATE / "imessage_receptor_state.json"
_CHAT_DB = Path.home() / "Library/Messages/chat.db"

INBOX_SCHEMA = "SIFTA_IMESSAGE_INBOX_V1"
INBOX_SOURCE = "System.swarm_imessage_receptor"
INBOX_CONSUMER = "Applications.sifta_talk_to_alice_widget"
MAX_INBOX_TEXT_CHARS = 4000
_LOOP_PREFIXES = ("SIFTA_SWIM:",)


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
    env_secret = os.environ.get("SIFTA_IMESSAGE_INGRESS_SECRET", "").strip()
    if env_secret:
        return env_secret
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
    rowid: int,
    handle_id: int,
    is_from_me: int = 0,
    ts: Optional[float] = None,
    secret: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a schema-bound, HMAC-signed inbox ligand for the UI consumer."""
    text = (text or "").strip()
    handle_fingerprint = hashlib.sha256(str(handle_id).encode("utf-8")).hexdigest()[:24]
    row: Dict[str, Any] = {
        "schema": INBOX_SCHEMA,
        "source": INBOX_SOURCE,
        "transport": "imessage",
        "direction": "incoming",
        "ts": time.time() if ts is None else float(ts),
        "rowid": int(rowid),
        "source_handle_sha256": handle_fingerprint,
        "is_from_me": int(is_from_me),
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
    if row.get("transport") != "imessage" or row.get("direction") != "incoming":
        return False, "transport_mismatch"
    text = row.get("text")
    if not isinstance(text, str) or not text.strip():
        return False, "empty_text"
    if len(text) > MAX_INBOX_TEXT_CHARS:
        return False, "text_too_long"
    if text.startswith(_LOOP_PREFIXES):
        return False, "loop_prefix"
    if not isinstance(row.get("rowid"), int) or row["rowid"] <= 0:
        return False, "bad_rowid"
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
        "event_kind": "IMESSAGE_INGRESS_CONSUME",
        "ts": now,
        "schema": INBOX_SCHEMA,
        "source": INBOX_SOURCE,
        "consumer": INBOX_CONSUMER,
        "rowid": row.get("rowid"),
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
    """
    Validate, consume, and receipt exactly one inbox row.

    Invalid rows are preserved but ignored. Duplicate signed rows are marked
    processed as duplicates once an identical signed row has already been
    consumed, preventing replay loops across timer ticks.
    """
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

    selected_index: Optional[int] = None
    selected_row: Optional[Dict[str, Any]] = None
    for idx, (_line, row, ok, reason) in enumerate(parsed):
        if not ok or row is None or row.get("processed"):
            continue
        sig = str(row.get("signature"))
        if sig in consumed_signatures:
            result["duplicate_count"] += 1
            row["processed"] = True
            row["processed_ts"] = now or time.time()
            row["processed_by"] = INBOX_CONSUMER
            row["processed_status"] = "duplicate"
            continue
        selected_index = idx
        selected_row = row
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
        "row": selected_row,
        "receipt": receipt,
    })
    return result


def _get_architect_handle(conn: sqlite3.Connection) -> int:
    """Resolve the Architect's target string to a SQLite handle_id."""
    if not _ID_FILE.exists():
        return -1
    raw_id = _ID_FILE.read_text().strip()
    if not raw_id:
        return -1
        
    # SQLite LIKE search to match variations (+1323..., 323...)
    # We strip the '+' or leading '1' for a broader match.
    search_term = raw_id.replace("+1", "").replace("+", "").replace("-", "").replace(" ", "")
    
    cur = conn.cursor()
    cur.execute("SELECT ROWID FROM handle WHERE id LIKE ? OR uncanonicalized_id LIKE ?", (f"%{search_term}%", f"%{search_term}%"))
    row = cur.fetchone()
    if row:
        return row[0]
    return -1


def _read_last_rowid() -> int:
    if not _STATE_FILE.exists():
        return -1
    try:
        return json.loads(_STATE_FILE.read_text()).get("last_rowid", -1)
    except Exception:
        return -1


def _write_last_rowid(rowid: int) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps({"last_rowid": rowid}))


def _deposit_inbox(text: str, *, rowid: int, handle_id: int, is_from_me: int = 0) -> None:
    """Deposit the incoming message to the inbox."""
    _INBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
    row = build_inbox_row(text, rowid=rowid, handle_id=handle_id, is_from_me=is_from_me)
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(_INBOX_FILE, json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        with _INBOX_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            
    # Update pheromone field to wake Alice
    try:
        from System.swarm_pheromone import PHEROMONE_FIELD
        PHEROMONE_FIELD.deposit("stig_imessage_receptor", intensity=2.0)
    except Exception:
        pass


def sense_loop() -> None:
    """Main daemon loop."""
    print(f"[imessage_receptor] Starting tap on {_CHAT_DB}")
    if not _CHAT_DB.exists():
        print(f"[imessage_receptor] ERROR: {_CHAT_DB} not found.")
        return

    # To avoid blasting Alice with old history on first run, we fast-forward
    last_rowid = _read_last_rowid()
    if last_rowid == -1:
        try:
            with sqlite3.connect(f"file:{_CHAT_DB}?mode=ro", uri=True) as conn:
                cur = conn.cursor()
                cur.execute("SELECT MAX(ROWID) FROM message")
                row = cur.fetchone()
                if row and row[0]:
                    last_rowid = row[0]
                    _write_last_rowid(last_rowid)
                    print(f"[imessage_receptor] Fast-forwarded to ROWID {last_rowid}")
        except Exception as e:
            print(f"[imessage_receptor] ERROR during fast-forward: {e}")

    consecutive_errors = 0
    while True:
        try:
            with sqlite3.connect(f"file:{_CHAT_DB}?mode=ro", uri=True) as conn:
                handle_id = _get_architect_handle(conn)
                if handle_id == -1:
                    time.sleep(5)
                    continue

                cur = conn.cursor()
                # is_from_me = 0 means incoming message
                # Note: if the Architect texts their own Apple ID from their iPhone,
                # macOS Messages might treat it as incoming (0) or outgoing (1).
                # We check `handle_id` to be sure. 
                query = """
                    SELECT ROWID, text, is_from_me 
                    FROM message 
                    WHERE handle_id = ? AND ROWID > ? AND text IS NOT NULL
                    ORDER BY ROWID ASC
                """
                cur.execute(query, (handle_id, last_rowid))
                rows = cur.fetchall()
                
                for row in rows:
                    r_id, text, is_from_me = row
                    
                    # We only ingest messages that are not system-generated swimmers
                    # AND we ensure they don't start with SIFTA_SWIM: to prevent feedback loops.
                    if text and not text.startswith("SIFTA_SWIM:"):
                        # If the Architect sends a message from their iPhone to the Mac's account
                        # we ingest it. 
                        print(f"[imessage_receptor] New message intercepted: {text}")
                        _deposit_inbox(text, rowid=r_id, handle_id=handle_id, is_from_me=is_from_me)
                    
                    last_rowid = r_id
                    _write_last_rowid(last_rowid)
                    
            consecutive_errors = 0
            
        except sqlite3.OperationalError as e:
            # chat.db might be locked temporarily by imagent
            consecutive_errors += 1
            if consecutive_errors > 5:
                print(f"[imessage_receptor] SQLite Error (Needs Full Disk Access?): {e}")
        except Exception as e:
            print(f"[imessage_receptor] Loop error: {e}")
            
        time.sleep(2.0)


if __name__ == "__main__":
    sense_loop()
