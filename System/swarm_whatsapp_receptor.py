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
from typing import Any, Dict, Mapping, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_INBOX_FILE = _STATE / "whatsapp_inbox.jsonl"
_INGRESS_KEY_FILE = _STATE / "whatsapp_ingress.key"
_INGRESS_RECEIPTS = _STATE / "whatsapp_ingress_receipts.jsonl"

INBOX_SCHEMA = "SIFTA_WHATSAPP_INBOX_V1"
INBOX_SOURCE = "System.swarm_whatsapp_receptor"
INBOX_CONSUMER = "Applications.sifta_talk_to_alice_widget"
MAX_INBOX_TEXT_CHARS = 4000

# Location shares. WhatsApp sends two kinds: a one-shot pin (`locationMessage`) and a live
# follow (`liveLocationMessage`) that keeps updating while the Architect walks. Both carry
# degreesLatitude/degreesLongitude. Coordinates are rounded to ~11 cm, well inside the
# accuracy of a phone fix, so the ledger stays readable and diffable.
LOCATION_TRACES_FILE = _STATE / "whatsapp_location_traces.jsonl"
LOCATION_LATEST_FILE = _STATE / "whatsapp_location_latest.json"
LOCATION_DECIMALS = 6
LOCATION_TRACE_SCHEMA = "SIFTA_WHATSAPP_LOCATION_TRACE_V1"
# A live share is only evidence while it is fresh. Past this window the position is reported
# as stale rather than spoken as if the Architect were still standing there.
LOCATION_FRESH_WINDOW_S = 900.0


def _normalize_location(raw: Any) -> Optional[Dict[str, Any]]:
    """Normalize a WhatsApp location share into the row's coordinate record.

    Accepts both share types, since the bridge already flattens a live share to the same
    lat/lon keys as a pin. A payload without usable numbers returns None, so a malformed
    share can never invent a position.

    @param raw - the bridge's `location` object, or None when the message carried none.
    @returns the normalized coordinate record, or None when there is nothing usable.
    """
    if not isinstance(raw, Mapping):
        return None
    lat, lon = raw.get("lat"), raw.get("lon")
    if isinstance(lat, bool) or isinstance(lon, bool):
        return None
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    if not -90.0 <= float(lat) <= 90.0 or not -180.0 <= float(lon) <= 180.0:
        return None
    expires = raw.get("expires")
    return {
        "lat": round(float(lat), LOCATION_DECIMALS),
        "lon": round(float(lon), LOCATION_DECIMALS),
        "name": str(raw.get("name") or "")[:200],
        "live": bool(raw.get("live")),
        "expires": (
            float(expires)
            if isinstance(expires, (int, float)) and not isinstance(expires, bool)
            else None
        ),
        "captured_ts": time.time(),
    }


def record_location_trace(row: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Append one accepted location row to the trace ledger and refresh the hot cache.

    The Architect's live share arrives as a series of updates, not one message, so the trace
    is the stream and `_latest` is the answer to "where is he now". Written after the row is
    built and signed, and a ledger failure never blocks the message.

    @param row - a validated inbox row that carries a `location` record.
    @returns the trace entry written, or None when the row had no location.
    """
    location = row.get("location")
    if not isinstance(location, Mapping):
        return None
    entry = {
        "schema": LOCATION_TRACE_SCHEMA,
        "transaction_type": "WHATSAPP_LOCATION_FIX",
        "ts": float(row.get("ts") or time.time()),
        "recorded_ts": time.time(),
        "from_jid": str(row.get("from_jid") or ""),
        "name": str(row.get("name") or ""),
        "message_sha256": str(row.get("message_sha256") or ""),
        "lat": location.get("lat"),
        "lon": location.get("lon"),
        "label": location.get("name") or "",
        "live": bool(location.get("live")),
        "expires": location.get("expires"),
    }
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        with LOCATION_TRACES_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        return None
    try:
        LOCATION_LATEST_FILE.write_text(
            json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError:
        pass
    return entry


def latest_location(max_age_s: float = LOCATION_FRESH_WINDOW_S) -> Optional[Dict[str, Any]]:
    """Return the most recent location fix with its age, or None when nothing is fresh.

    This is the only supported way to answer "where is he". It refuses to hand back a stale
    point as if it were current: past `max_age_s` the caller gets None and must say it does
    not know.

    @param max_age_s - freshness window in seconds; a fix older than this is not returned.
    @returns the fix plus `age_s`, or None when no fix is fresh enough.
    """
    try:
        entry = json.loads(LOCATION_LATEST_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(entry, dict):
        return None
    age = time.time() - float(entry.get("recorded_ts") or 0.0)
    if age > max_age_s:
        return None
    return {**entry, "age_s": round(age, 1)}


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
    from_me: bool = False,
    chat_type: Optional[str] = None,
    participant: Optional[str] = None,
    media_path: Optional[str] = None,
    media_type: Optional[str] = None,
    location: Optional[Dict[str, Any]] = None,
    ts: Optional[float] = None,
    secret: Optional[str] = None,
) -> Dict[str, Any]:
    text = (text or "").strip()
    normalized_location = _normalize_location(location)
    # A photo arrives with no words at all, and an empty-text row is REJECTED by the
    # validator -- so the image was refused before it could be looked at. Media with no text
    # becomes a legible marker, and the file path travels with it.
    if not text and media_path:
        text = "[photo]" if (media_type or "image") == "image" else f"[{media_type}]"
    # A location share can also arrive with no words. Without a marker the validator rejects
    # the row as empty_text and the coordinates die with it -- exactly the loss the media
    # marker above was written to stop, measured again on 2026-10-05 with two silent shares.
    if not text and normalized_location is not None:
        text = "[live location]" if normalized_location["live"] else "[location]"
    inferred_chat_type = (chat_type or ("group" if str(from_jid).endswith("@g.us") else "direct")).strip().lower()
    row: Dict[str, Any] = {
        "schema": INBOX_SCHEMA,
        "source": INBOX_SOURCE,
        "transport": "whatsapp",
        "direction": "incoming",
        "ts": time.time() if ts is None else float(ts),
        "from_jid": from_jid,
        "name": name or "",
        "from_me": bool(from_me),
        "chat_type": inferred_chat_type,
        "participant": participant or "",
        "text": text,
        "message_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "processed": False,
    }
    if media_path:
        row["media_path"] = str(media_path)
        row["media_type"] = str(media_type or "image")
    # Added BEFORE signing: `_canonical_payload` signs every field except the processed
    # markers, so the coordinates are covered by the HMAC and a tampered position fails
    # validation the same way a tampered message does.
    if normalized_location is not None:
        row["location"] = normalized_location
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
    if row.get("chat_type") not in {"direct", "group"}:
        return False, "chat_type_mismatch"
    if not isinstance(row.get("from_me"), bool):
        return False, "from_me_mismatch"
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
