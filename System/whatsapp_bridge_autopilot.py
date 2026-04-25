#!/usr/bin/env python3
"""
System/whatsapp_bridge_autopilot.py — Outbound WhatsApp Biological Actuator
═══════════════════════════════════════════════════════════════════════════
Alice's WhatsApp arm. Resolves human nicknames to JIDs and injects the message
into the Baileys Node.js bridge.
"""

import json
import urllib.request
import urllib.error
import time
from pathlib import Path
from typing import Any, Dict

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_CONTACTS_FILE = _STATE / "whatsapp_contacts.json"
_LEDGER = _STATE / "whatsapp_bridge_trace.jsonl"
_INJECT_URL = "http://127.0.0.1:3001/system_inject"

SCHEMA = "SIFTA_WHATSAPP_EFFECTOR_V1"
EVENT_KIND = "WHATSAPP_SEND_ATTEMPT"


def _deposit_trace(row: Dict[str, Any]) -> Dict[str, Any]:
    """Record Alice's outgoing WhatsApp messages to the immutable ledger."""
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(_LEDGER, json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            
    try:
        from System.swarm_pheromone import PHEROMONE_FIELD
        PHEROMONE_FIELD.deposit("stig_whatsapp_effector", intensity=1.0 if row.get("ok") else -0.5)
    except Exception:
        pass
    return row


def _load_contacts() -> Dict[str, Any]:
    if not _CONTACTS_FILE.exists():
        return {}
    try:
        return json.loads(_CONTACTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _resolve_target(target: str) -> str:
    """Resolve a target string (JID or nickname) to a JID."""
    if "@s.whatsapp.net" in target or "@g.us" in target:
        return target
        
    contacts = _load_contacts()
    target_lower = target.lower()
    
    matches = []
    for jid_hash, contact in contacts.items():
        name = (contact.get("display_name") or "").lower()
        if target_lower in name:
            matches.append(contact.get("jid"))
            
    if len(matches) == 1:
        return matches[0]
    return ""


def summary_for_alice(limit: int = 12) -> str:
    """Compact WhatsApp world model for Alice's prompt context.

    Raw JIDs stay out of the prompt; Alice only needs names, chat shape, and
    whether a contact is reachable by the local bridge.
    """
    contacts = _load_contacts()
    rows = []
    for row in contacts.values():
        if not isinstance(row, dict):
            continue
        name = str(row.get("display_name") or row.get("name") or "").strip()
        jid = str(row.get("jid") or "")
        if not name:
            continue
        chat_type = str(row.get("chat_type") or ("group" if jid.endswith("@g.us") else "direct"))
        last_seen = float(row.get("last_seen_ts") or row.get("synced_ts") or 0.0)
        rows.append((last_seen, name[:48], chat_type))
    rows.sort(reverse=True)

    lines = [
        "WHATSAPP WORLD:",
        "- transport=WhatsApp via local Baileys phone bridge; inbound messages are real external humans queued into Alice.",
        "- outbound_tool=whatsapp.send; target may be a saved display name or exact WhatsApp JID.",
    ]
    if rows:
        contact_bits = [f"{name} ({chat_type})" for _ts, name, chat_type in rows[:limit]]
        lines.append(f"- known_contacts={len(rows)} visible_to_alice: " + "; ".join(contact_bits))
    else:
        lines.append("- known_contacts=0; contacts appear after WhatsApp sync or after a human messages Alice.")
    return "\n".join(lines)


def send_whatsapp(target: str, text: str) -> Dict[str, Any]:
    """
    Transmit a WhatsApp message via the Baileys injection server.
    """
    target = (target or "").strip()
    text = (text or "").strip()

    def finish(status: str, ok: bool, result: str) -> Dict[str, Any]:
        row = {
            "event_kind": EVENT_KIND,
            "schema": SCHEMA,
            "ts": time.time(),
            "target": target,
            "text": text,
            "ok": ok,
            "status": status,
            "result": result,
        }
        return _deposit_trace(row)

    if not target:
        return finish("REJECTED_MISSING_TARGET", False, "Missing target name or JID.")
    if not text:
        return finish("REJECTED_MISSING_PAYLOAD", False, "Missing message text.")

    resolved_jid = _resolve_target(target)
    if not resolved_jid:
        return finish("BLOCKED_UNKNOWN_TARGET", False, f"Could not resolve '{target}' to a known WhatsApp contact. They must message Alice first to register.")

    payload = json.dumps({"to": resolved_jid, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        _INJECT_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return finish("SENT", True, f"Message injected to {resolved_jid}.")
            else:
                return finish("SEND_FAILED", False, f"Bridge rejected payload: {data}")
    except urllib.error.URLError as e:
        return finish("BRIDGE_UNREACHABLE", False, f"Could not reach injection server at {_INJECT_URL}. Is the Node bridge running?")
    except Exception as e:
        return finish("SEND_ERROR", False, str(e))


def govern(verb: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Alice's interface to the WhatsApp Effector.
    verb: "send_whatsapp"
    kwargs: {"target": "Carlton", "text": "hello"} 
    """
    verb = verb.lower().strip()
    if verb == "send_whatsapp":
        return send_whatsapp(
            kwargs.get("target", ""),
            kwargs.get("text", "")
        )
    return {"ok": False, "error": f"Unknown whatsapp effector verb: {verb}"}


if __name__ == "__main__":
    import sys
    print("Testing WhatsApp Effector...")
    if len(sys.argv) > 2:
        print(send_whatsapp(sys.argv[1], sys.argv[2]))
    else:
        print("Usage: python whatsapp_bridge_autopilot.py <target> <text>")
