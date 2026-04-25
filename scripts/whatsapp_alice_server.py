#!/usr/bin/env python3
"""Local Alice ingest node for the Baileys WhatsApp bridge.

Instead of answering via Ollama directly, this simply ingests the message
and queues it into the SIFTA desktop widget inbox. Alice will answer with her
full swarm OS identity (tools, bash, memory).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from System.swarm_whatsapp_receptor import build_inbox_row
from System.whatsapp_social_graph import (
    contact_hash,
    display_name_for,
    enrich_contact_record,
    load_contacts,
    save_contacts,
)

STATE_DIR = REPO / ".sifta_state"
AUDIT_LOG = STATE_DIR / "whatsapp_alice_bridge.jsonl"
CONTACTS = STATE_DIR / "whatsapp_contacts.json"
INBOX_FILE = STATE_DIR / "whatsapp_inbox.jsonl"

PORT = int(os.environ.get("SIFTA_WHATSAPP_ALICE_PORT", "7434"))
MAX_INPUT_CHARS = int(os.environ.get("SIFTA_WHATSAPP_MAX_INPUT_CHARS", "4000"))


def _now() -> float:
    return time.time()


def _hash(value: str) -> str:
    return contact_hash(value)


def _append_audit(row: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    row.setdefault("ts", _now())
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def _load_contacts() -> dict[str, Any]:
    return load_contacts(CONTACTS)


def _save_contacts(data: dict[str, Any]) -> None:
    save_contacts(data, CONTACTS)


def _contact_display_name(row: dict[str, Any]) -> str:
    return display_name_for(row)


def _sync_contacts(rows: list[Any]) -> int:
    contacts = _load_contacts()
    changed = 0
    now = _now()
    for item in rows:
        if not isinstance(item, dict):
            continue
        jid = str(item.get("jid") or item.get("id") or "").strip()
        if not jid:
            continue
        key = _hash(jid)
        existing = contacts.get(key, {})
        # Respect name_locked: don't overwrite manually-set display names
        if existing.get("name_locked"):
            name = existing.get("display_name") or ""
        else:
            name = _contact_display_name(item) or existing.get("display_name") or ""
        updated = enrich_contact_record(
            existing,
            jid=jid,
            name=name,
            source="whatsapp_contacts_sync",
            now=now,
        )
        if updated != existing:
            contacts[key] = updated
            changed += 1
    if changed:
        _save_contacts(contacts)
    return changed


def _record_contact(from_jid: str, name: str | None) -> None:
    contacts = _load_contacts()
    key = _hash(from_jid)
    row = contacts.get(key, {})
    # Respect name_locked: don't overwrite manually-set display names
    if row.get("name_locked"):
        name = row.get("display_name") or ""
    else:
        name = name or row.get("display_name") or ""
    row = enrich_contact_record(
        row,
        jid=from_jid,
        name=name,
        source="whatsapp",
        now=_now(),
    )
    contacts[key] = row
    _save_contacts(contacts)


def _deposit_inbox(text: str, from_jid: str, name: str | None) -> None:
    """Deposit the incoming message to the SIFTA desktop inbox."""
    INBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
    row = build_inbox_row(text, from_jid=from_jid, name=name)
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(INBOX_FILE, json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        with INBOX_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            
    # Update pheromone field to wake Alice
    try:
        from System.swarm_pheromone import PHEROMONE_FIELD
        PHEROMONE_FIELD.deposit("stig_whatsapp_receptor", intensity=2.0)
    except Exception:
        pass


class AliceWhatsAppHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "port": PORT, "mode": "SIFTA OS Queue"}).encode("utf-8"))

    def do_POST(self) -> None:
        if self.path == "/contacts":
            self._handle_contacts_sync()
            return
        if self.path != "/swarm_message":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
            
            # Handle contact sync from Node bridge
            if body.get("type") == "contacts":
                contacts = body.get("contacts", [])
                for c in contacts:
                    jid = c.get("id")
                    name = c.get("name") or c.get("notify") or c.get("verifiedName")
                    if jid and name:
                        _record_contact(jid, name)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
                return

            from_jid = str(body.get("from", "unknown"))
            name = body.get("name")
            text = str(body.get("text", ""))[:MAX_INPUT_CHARS]
            _record_contact(from_jid, str(name) if name else None)
            _append_audit(
                {
                    "event": "incoming_queued",
                    "from_hash": _hash(from_jid),
                    "name": name or "",
                    "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "text_preview": text[:160],
                }
            )
            print(f"\n[WHATSAPP_ALICE] Queued -> {name or _hash(from_jid)}: {text[:120]}")
            
            _deposit_inbox(text, from_jid, str(name) if name else None)

            # Do not wait for the LLM. Just tell the bridge it's queued.
            # Alice will reply asynchronously using python3 -m System.alice_body_autopilot
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            # Send _SILENT_ so bridge.js doesn't try to reply synchronously with a placeholder
            self.wfile.write(json.dumps({"ok": True, "swarm_voice": "_SILENT_"}).encode("utf-8"))
        except Exception as exc:
            _append_audit({"event": "error", "error": type(exc).__name__, "message": str(exc)[:300]})
            print(f"[WHATSAPP_ALICE] ERROR {type(exc).__name__}: {exc}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({"error": "queue ingestion failed"}).encode("utf-8")
            )

    def _handle_contacts_sync(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
            rows = body.get("contacts") if isinstance(body, dict) else None
            if not isinstance(rows, list):
                rows = []
            changed = _sync_contacts(rows)
            _append_audit({"event": "contacts_synced", "received": len(rows), "changed": changed})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "changed": changed}).encode("utf-8"))
        except Exception as exc:
            _append_audit({"event": "contacts_sync_error", "error": type(exc).__name__, "message": str(exc)[:300]})
            print(f"[WHATSAPP_ALICE] CONTACT SYNC ERROR {type(exc).__name__}: {exc}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": "contacts sync failed"}).encode("utf-8"))


def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    server = HTTPServer(("127.0.0.1", PORT), AliceWhatsAppHandler)
    print(f"[WHATSAPP_ALICE] Ingest server listening on 127.0.0.1:{PORT}")
    print("[WHATSAPP_ALICE] Mode: SIFTA OS Ingestion Queue (Direct LLM Wrapper disabled)")
    server.serve_forever()


if __name__ == "__main__":
    main()
