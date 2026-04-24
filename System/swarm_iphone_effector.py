#!/usr/bin/env python3
"""
System/swarm_iphone_effector.py — The Synaptic Ping
═══════════════════════════════════════════════════════════════════════════
Alice's iPhone Governance Organ (Vector C, C47H 2026-04-23).

Sends a payload-bearing iMessage ("Swimmer") to the Architect's phone number
via the local macOS Messages app. This natively wakes the iPhone and triggers
a Personal Automation in iOS Shortcuts.

Usage:
  Alice calls `iphone.send_swimmer` with `hw_kwargs={"payload": "FLASHLIGHT:ON"}`

Configuration:
  Create `.sifta_state/architect_imessage_id.txt` with your Apple ID or phone 
  number (e.g. "+15551234567" or "youremail@icloud.com").
"""

import json
import hashlib
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_ID_FILE = _STATE / "architect_imessage_id.txt"
_LEDGER = _STATE / "iphone_effector_trace.jsonl"
_ALLOWLIST_FILE = _STATE / "iphone_effector_allowlist.json"

SCHEMA = "SIFTA_IPHONE_EFFECTOR_V1"
EVENT_KIND = "IPHONE_EFFECTOR_ATTEMPT"
MAX_PAYLOAD_CHARS = 500

_DEFAULT_SWIMMER_ALLOWLIST = {
    "PING",
    "STATUS:REQUEST",
    "FLASHLIGHT:ON",
    "FLASHLIGHT:OFF",
    "VOLUME:MUTE",
    "VOLUME:LOW",
    "VOLUME:MEDIUM",
    "VOLUME:HIGH",
}

_DEFAULT_AUTHORIZED_SOURCES = {
    "architect",
    "system.alice_body_autopilot",
    "applications.sifta_talk_to_alice_widget",
    "test",
}


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _applescript_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    return f'"{escaped}"'


def _authorized_sources() -> set[str]:
    raw = os.environ.get("SIFTA_IPHONE_EFFECTOR_AUTHORIZED_SOURCES", "")
    extra = {x.strip().lower() for x in raw.split(",") if x.strip()}
    return set(_DEFAULT_AUTHORIZED_SOURCES) | extra


def _source_authorized(source: str) -> bool:
    return (source or "").strip().lower() in _authorized_sources()


def _allowed_swimmer_payloads() -> set[str]:
    allowed = set(_DEFAULT_SWIMMER_ALLOWLIST)
    try:
        raw = json.loads(_ALLOWLIST_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            allowed |= {str(x).strip().upper() for x in raw if str(x).strip()}
        elif isinstance(raw, dict):
            values = raw.get("swimmer_payloads") or raw.get("allowed") or []
            if isinstance(values, list):
                allowed |= {str(x).strip().upper() for x in values if str(x).strip()}
    except Exception:
        pass
    return allowed


def _payload_allowed(payload: str) -> bool:
    return payload.strip().upper() in _allowed_swimmer_payloads()


def _request_hash(action: str, target_id: str, full_message: str, source: str) -> str:
    return _hash_text(_canonical_json({
        "action": action,
        "target_sha256": _hash_text(target_id),
        "full_message": full_message,
        "source": source,
    }))


def _read_target_id() -> Optional[str]:
    """Read the target Apple ID / Phone Number from configuration."""
    if not _ID_FILE.exists():
        return None
    val = _ID_FILE.read_text().strip()
    return val if val else None


def _already_sent(request_hash: str, *, ledger_path: Path = _LEDGER) -> bool:
    if not ledger_path.exists():
        return False
    try:
        for line in ledger_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if (
                isinstance(row, dict)
                and row.get("request_hash") == request_hash
                and row.get("status") == "SENT"
                and row.get("ok") is True
            ):
                return True
    except Exception:
        return False
    return False


def _deposit_trace(row: Dict[str, Any], *, ledger_path: Path = _LEDGER) -> Dict[str, Any]:
    """Record Alice's outgoing swimmers to the immutable ledger."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    unsigned = {k: v for k, v in row.items() if k != "receipt_hash"}
    row["receipt_hash"] = _hash_text(_canonical_json(unsigned))
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(ledger_path, json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        with ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            
    try:
        from System.swarm_pheromone import PHEROMONE_FIELD
        PHEROMONE_FIELD.deposit("stig_iphone_effector", intensity=1.5 if row.get("ok") else -0.5)
    except Exception:
        pass
    return row


def send_swimmer(
    payload: str,
    *,
    prefix: bool = True,
    dry_run: bool = True,
    allow_send: bool = False,
    source: str = "unspecified",
    allow_duplicate: bool = False,
    allow_plain_text: bool = False,
    target_id: Optional[str] = None,
    ledger_path: Path = _LEDGER,
) -> Dict[str, Any]:
    """
    Transmit the Synaptic Ping via AppleScript -> Messages.app.
    If prefix is True, prepends the payload with SIFTA_SWIM: to ensure clean iOS filtering.
    """
    action = "send_swimmer" if prefix else "send_text"
    source = (source or "unspecified").strip()
    dry_run = _truthy(dry_run)
    allow_send = _truthy(allow_send) or _truthy(os.environ.get("SIFTA_IPHONE_EFFECTOR_ALLOW_SEND"))
    allow_plain_text = _truthy(allow_plain_text)
    allow_duplicate = _truthy(allow_duplicate)
    payload = (payload or "").strip()

    def finish(status: str, ok: bool, result: str, **extra: Any) -> Dict[str, Any]:
        row = {
            "event_kind": EVENT_KIND,
            "schema": SCHEMA,
            "ts": time.time(),
            "action": action,
            "source": source,
            "payload": payload,
            "full_message": extra.get("full_message", ""),
            "target_sha256": _hash_text(extra.get("target_id", "")) if extra.get("target_id") else "",
            "dry_run": dry_run,
            "allow_send": allow_send,
            "authorized_source": _source_authorized(source),
            "allow_duplicate": allow_duplicate,
            "ok": ok,
            "status": status,
            "result": result,
            "request_hash": extra.get("request_hash", ""),
        }
        row = _deposit_trace(row, ledger_path=ledger_path)
        response = dict(row)
        response.pop("target_sha256", None)
        if not ok:
            response["error"] = result
        return response

    if not payload:
        return finish("REJECTED_MISSING_PAYLOAD", False, "Missing 'payload' kwarg.")
    if len(payload) > MAX_PAYLOAD_CHARS:
        return finish("REJECTED_PAYLOAD_TOO_LONG", False, f"Payload exceeds {MAX_PAYLOAD_CHARS} chars.")

    target_id = target_id or _read_target_id()
    if not target_id:
        msg = (
            "No Apple ID configured. The Architect must create "
            "`.sifta_state/architect_imessage_id.txt` containing their "
            "iMessage email or phone number before you can send swimmers."
        )
        return finish("BLOCKED_NO_TARGET", False, msg)

    full_message = f"SIFTA_SWIM:{payload}" if prefix else payload
    request_hash = _request_hash(action, target_id, full_message, source)

    if prefix and not _payload_allowed(payload):
        return finish(
            "BLOCKED_NOT_ALLOWLISTED",
            False,
            f"Payload is not in the swimmer allowlist: {payload!r}",
            target_id=target_id,
            full_message=full_message,
            request_hash=request_hash,
        )

    if not prefix and not allow_plain_text:
        return finish(
            "BLOCKED_PLAIN_TEXT_REQUIRES_OPT_IN",
            False,
            "Plain outbound text requires allow_plain_text=True.",
            target_id=target_id,
            full_message=full_message,
            request_hash=request_hash,
        )

    if allow_send and not _source_authorized(source):
        return finish(
            "BLOCKED_UNAUTHORIZED_SOURCE",
            False,
            f"Source is not authorized to send via Messages.app: {source!r}",
            target_id=target_id,
            full_message=full_message,
            request_hash=request_hash,
        )

    if _already_sent(request_hash, ledger_path=ledger_path) and not allow_duplicate:
        return finish(
            "DUPLICATE_SUPPRESSED",
            True,
            "Identical outbound request was already sent; suppressed duplicate.",
            target_id=target_id,
            full_message=full_message,
            request_hash=request_hash,
        )

    if dry_run or not allow_send:
        return finish(
            "DRY_RUN",
            True,
            "Dry run only; no Messages.app send executed.",
            target_id=target_id,
            full_message=full_message,
            request_hash=request_hash,
        )
    
    # Send via AppleScript
    # We use 'service 1' which is almost always the active iMessage service
    # or explicitly "iMessage" / "SMS". If "iMessage" fails, fallback to generic.
    target_literal = _applescript_string(target_id)
    message_literal = _applescript_string(full_message)
    script = f'''
    tell application "Messages"
        try
            set targetService to 1st service whose service type = iMessage
        on error
            set targetService to 1st service
        end try
        set theBuddy to buddy {target_literal} of targetService
        send {message_literal} to theBuddy
    end tell
    '''
    
    try:
        out = subprocess.check_output(
            ["osascript", "-e", script],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=8.0
        ).strip()
        row = finish(
            "SENT",
            True,
            "Message dispatched via AppleScript.",
            target_id=target_id,
            full_message=full_message,
            request_hash=request_hash,
        )
        row["osascript_output"] = out
        return row
    except subprocess.CalledProcessError as e:
        return finish(
            "SEND_FAILED",
            False,
            e.output.strip(),
            target_id=target_id,
            full_message=full_message,
            request_hash=request_hash,
        )
    except subprocess.TimeoutExpired:
        return finish(
            "SEND_TIMEOUT",
            False,
            "AppleScript execution timed out.",
            target_id=target_id,
            full_message=full_message,
            request_hash=request_hash,
        )
    except Exception as e:
        return finish(
            "SEND_FAILED",
            False,
            str(e),
            target_id=target_id,
            full_message=full_message,
            request_hash=request_hash,
        )


def govern(verb: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Alice's interface to the iPhone Effector.
    verb: "send_swimmer"
    kwargs: {"payload": "FLASHLIGHT:ON"} 
    """
    verb = verb.lower().strip()
    payload = str(kwargs.get("payload", "")).strip()
    dry_run = kwargs.get("dry_run", True)
    allow_send = kwargs.get("allow_send", False)
    source = str(kwargs.get("source", "unspecified"))
    allow_duplicate = kwargs.get("allow_duplicate", False)
    if verb == "send_swimmer":
        return send_swimmer(
            payload,
            prefix=True,
            dry_run=dry_run,
            allow_send=allow_send,
            source=source,
            allow_duplicate=allow_duplicate,
        )
    if verb == "send_text":
        return send_swimmer(
            payload,
            prefix=False,
            dry_run=dry_run,
            allow_send=allow_send,
            source=source,
            allow_duplicate=allow_duplicate,
            allow_plain_text=kwargs.get("allow_plain_text", False),
        )
        
    return {"ok": False, "error": f"Unknown iphone_effector verb: {verb}"}


if __name__ == "__main__":
    # Smoke test module (dry run if no ID configured)
    import sys
    print("Testing iPhone Effector...")
    target = _read_target_id()
    if not target:
        print("SKIP: `.sifta_state/architect_imessage_id.txt` missing.")
        sys.exit(0)
    print(f"Configured target: {target}")
    # We will NOT actually send a ping on smoke test to avoid spamming the user.
    print("Smoke test complete.")
