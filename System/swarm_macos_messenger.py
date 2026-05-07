#!/usr/bin/env python3
"""
System/swarm_macos_messenger.py — Alice Native macOS Messenger
═══════════════════════════════════════════════════════════════
AG46 2026-05-06 | Covenant §7.6 | GTH4921YP3

Alice sends messages via the SAME apps George uses on his Mac.
No Baileys. No JID resolution. No bridge server.
WhatsApp Desktop is installed and logged in as George → Alice uses it.

Supported channels (in priority order):
  1. WhatsApp Desktop  — via URL scheme + osascript UI automation
  2. iMessage          — via osascript Messages.app
  3. Telegram          — via URL scheme (if installed)

Contact resolution:
  - Check local name→phone cache (.sifta_state/macos_contacts_cache.json)
  - Query macOS Contacts.app for phone number by name
  - Fall back to treating the "name" as a raw phone number

CLI usage:
  python3 -m System.swarm_macos_messenger send --to Carlton --msg "we did it"
  python3 -m System.swarm_macos_messenger send --to Carlton --msg "..." --via whatsapp
  python3 -m System.swarm_macos_messenger lookup Carlton
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_CONTACTS_CACHE = _STATE / "macos_contacts_cache.json"
_SEND_LOG = _STATE / "macos_messenger_sends.jsonl"
_STATE.mkdir(parents=True, exist_ok=True)


# ─── Contact cache ────────────────────────────────────────────────────────────

def _load_cache() -> Dict[str, str]:
    """name_lower → phone (E.164 or raw)"""
    try:
        if _CONTACTS_CACHE.exists():
            return json.loads(_CONTACTS_CACHE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_cache(cache: Dict[str, str]) -> None:
    try:
        _CONTACTS_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception:
        pass


def _normalize_phone(raw: str) -> str:
    """Strip formatting, keep digits and leading +."""
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    return digits


def _contacts_lookup_applescript(name: str) -> List[Tuple[str, str]]:
    """
    Fast AppleScript lookup by name — returns [(full_name, phone), ...]
    Uses 'whose name contains' filter so we don't iterate all contacts.
    """
    script = f'''
tell application "Contacts"
    set matches to (every person whose name contains "{name}")
    set res to {{}}
    repeat with p in matches
        set nm to name of p
        repeat with ph in (every phone of p)
            set res to res & {{nm & "::" & value of ph}}
        end repeat
    end repeat
    return res
end tell
'''
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=8
        )
        raw = r.stdout.strip()
        if not raw:
            return []
        results = []
        for item in raw.split(", "):
            item = item.strip()
            if "::" in item:
                nm, ph = item.split("::", 1)
                results.append((nm.strip(), _normalize_phone(ph.strip())))
        return results
    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []


def resolve_contact(name: str) -> Optional[str]:
    """
    Resolve a human name to a phone number.
    Priority: cache → Contacts.app → treat name as phone.
    Returns the phone number string or None.
    """
    key = name.strip().lower()
    cache = _load_cache()

    if key in cache:
        return cache[key]

    # Try Contacts.app lookup
    matches = _contacts_lookup_applescript(name)
    if matches:
        # Prefer mobile numbers
        mobile = None
        for nm, ph in matches:
            if ph and not mobile:
                mobile = ph
        if mobile:
            cache[key] = mobile
            _save_cache(cache)
            return mobile

    # If name looks like a phone number already
    cleaned = _normalize_phone(name)
    if len(cleaned) >= 7:
        cache[key] = cleaned
        _save_cache(cache)
        return cleaned

    return None


def add_contact(name: str, phone: str) -> None:
    """Manually register a name→phone mapping in the local cache."""
    cache = _load_cache()
    cache[name.strip().lower()] = _normalize_phone(phone)
    _save_cache(cache)
    print(f"✅ Registered: {name} → {_normalize_phone(phone)}")


# ─── Receipt logging ──────────────────────────────────────────────────────────

def _log_send(channel: str, target: str, phone: str, message: str,
              ok: bool, status: str, note: str = "") -> Dict[str, Any]:
    row = {
        "ts": time.time(),
        "schema": "SIFTA_MACOS_MESSENGER_V1",
        "channel": channel,
        "target": target,
        "phone": phone,
        "message_len": len(message),
        "ok": ok,
        "status": status,
        "note": note,
        "truth_note": "ok=True only when osascript completed send action without error.",
    }
    try:
        with _SEND_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return row


# ─── WhatsApp Desktop ─────────────────────────────────────────────────────────

def send_whatsapp_native(target: str, message: str) -> Dict[str, Any]:
    """
    Send a WhatsApp message via the installed WhatsApp Desktop app.
    Uses the whatsapp:// URL scheme which opens the app and pre-fills the
    conversation, then osascript types and sends the message.

    Requires: WhatsApp Desktop installed and logged in as George.
    """
    phone = resolve_contact(target)
    if not phone:
        return _log_send("whatsapp", target, "", message, False,
                         "CONTACT_NOT_FOUND",
                         f"Could not resolve '{target}' to a phone number. "
                         f"Run: python3 -m System.swarm_macos_messenger register '{target}' +1XXXXXXXXXX")

    # Strip non-digits for URL (keep leading +)
    phone_url = re.sub(r"[^\d]", "", phone)

    # Encode message for URL
    msg_encoded = urllib.parse.quote(message)
    wa_url = f"whatsapp://send?phone={phone_url}&text={msg_encoded}"

    script = f'''
tell application "WhatsApp"
    activate
end tell
delay 1.0
open location "{wa_url}"
delay 2.5
tell application "System Events"
    tell process "WhatsApp"
        keystroke return
    end tell
end tell
delay 0.5
return "sent"
'''
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0 and "sent" in r.stdout:
            return _log_send("whatsapp", target, phone, message, True, "SENT")
        else:
            err = (r.stderr or r.stdout or "unknown").strip()[:200]
            return _log_send("whatsapp", target, phone, message, False,
                             "OSASCRIPT_ERROR", err)
    except subprocess.TimeoutExpired:
        return _log_send("whatsapp", target, phone, message, False,
                         "TIMEOUT", "osascript timed out after 15s")
    except Exception as e:
        return _log_send("whatsapp", target, phone, message, False,
                         "EXCEPTION", str(e)[:200])


# ─── iMessage ────────────────────────────────────────────────────────────────

def send_imessage(target: str, message: str) -> Dict[str, Any]:
    """
    Send via macOS Messages.app (iMessage or SMS fallback).
    Target can be a phone number or Apple ID email.
    """
    phone = resolve_contact(target) or target

    # Escape double quotes in message
    safe_msg = message.replace('"', '\\"')
    script = f'''
tell application "Messages"
    set targetBuddy to "{phone}"
    set targetService to 1st service whose service type = iMessage
    set theBuddy to buddy targetBuddy of targetService
    send "{safe_msg}" to theBuddy
end tell
'''
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            return _log_send("imessage", target, phone, message, True, "SENT")
        else:
            err = (r.stderr or "").strip()[:200]
            return _log_send("imessage", target, phone, message, False,
                             "OSASCRIPT_ERROR", err)
    except subprocess.TimeoutExpired:
        return _log_send("imessage", target, phone, message, False,
                         "TIMEOUT", "Messages.app timed out")
    except Exception as e:
        return _log_send("imessage", target, phone, message, False,
                         "EXCEPTION", str(e)[:200])


# ─── Telegram ────────────────────────────────────────────────────────────────

def send_telegram(target: str, message: str) -> Dict[str, Any]:
    """
    Send via Telegram (URL scheme). Target should be a username (@handle).
    """
    msg_encoded = urllib.parse.quote(message)
    tg_url = f"tg://resolve?domain={target.lstrip('@')}&text={msg_encoded}"
    script = f'''
open location "{tg_url}"
delay 2.0
tell application "System Events"
    tell process "Telegram"
        keystroke return
    end tell
end tell
return "sent"
'''
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            return _log_send("telegram", target, target, message, True, "SENT")
        err = (r.stderr or r.stdout or "").strip()[:200]
        return _log_send("telegram", target, target, message, False,
                         "OSASCRIPT_ERROR", err)
    except Exception as e:
        return _log_send("telegram", target, target, message, False,
                         "EXCEPTION", str(e)[:200])


# ─── Unified send ────────────────────────────────────────────────────────────

CHANNEL_MAP = {
    "whatsapp": send_whatsapp_native,
    "wa": send_whatsapp_native,
    "imessage": send_imessage,
    "sms": send_imessage,
    "telegram": send_telegram,
    "tg": send_telegram,
}

def send_message(target: str, message: str,
                 via: str = "whatsapp") -> Dict[str, Any]:
    """
    Unified entry point. via = 'whatsapp' | 'imessage' | 'telegram'
    Logs a receipt regardless of outcome.
    """
    channel = (via or "whatsapp").lower().strip()
    fn = CHANNEL_MAP.get(channel)
    if not fn:
        return _log_send(channel, target, "", message, False,
                         "UNKNOWN_CHANNEL",
                         f"Channel '{channel}' not supported. Use: whatsapp, imessage, telegram")
    return fn(target, message)


# ─── CLI ─────────────────────────────────────────────────────────────────────

def _print_result(result: Dict[str, Any]) -> None:
    ok = result.get("ok", False)
    status = result.get("status", "?")
    channel = result.get("channel", "?")
    target = result.get("target", "?")
    note = result.get("note", "")
    icon = "✅" if ok else "❌"
    print(f"\n{icon} [{channel}] → {target} | {status}")
    if note:
        print(f"   {note}")
    print(f"   Truth: {result.get('truth_note', '')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Alice macOS Messenger — sends via WhatsApp, iMessage, Telegram"
    )
    sub = parser.add_subparsers(dest="cmd")

    # send
    p_send = sub.add_parser("send", help="Send a message")
    p_send.add_argument("--to", required=True, help="Contact name or phone number")
    p_send.add_argument("--msg", required=True, help="Message text")
    p_send.add_argument("--via", default="whatsapp",
                        help="Channel: whatsapp (default), imessage, telegram")

    # lookup
    p_look = sub.add_parser("lookup", help="Look up a contact's phone number")
    p_look.add_argument("name", help="Contact name to look up")

    # register
    p_reg = sub.add_parser("register", help="Manually register name→phone mapping")
    p_reg.add_argument("name", help="Contact name")
    p_reg.add_argument("phone", help="Phone number (E.164 preferred: +1XXXXXXXXXX)")

    # list
    sub.add_parser("list", help="List all cached contacts")

    args = parser.parse_args()

    if args.cmd == "send":
        result = send_message(args.to, args.msg, via=args.via)
        _print_result(result)

    elif args.cmd == "lookup":
        phone = resolve_contact(args.name)
        if phone:
            print(f"✅ {args.name} → {phone}")
        else:
            print(f"❌ Could not resolve '{args.name}'. Try: register '{args.name}' +1XXXXXXXXXX")

    elif args.cmd == "register":
        add_contact(args.name, args.phone)

    elif args.cmd == "list":
        cache = _load_cache()
        if not cache:
            print("(no contacts registered)")
        else:
            for name, phone in sorted(cache.items()):
                print(f"  {name:<25} → {phone}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
