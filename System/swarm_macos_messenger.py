#!/usr/bin/env python3
"""
System/swarm_macos_messenger.py — Alice Native macOS Messenger
═══════════════════════════════════════════════════════════════
AG46 2026-05-06 | Covenant §7.6 | GTH4921YP3

Alice sends messages via the SAME apps George uses on his Mac.
No bridge cache requirement. No transport-id prerequisite.
WhatsApp Desktop is installed and logged in as George → Alice uses it.

Supported channels (in priority order):
  1. WhatsApp Desktop  — via URL scheme + osascript UI automation
  2. iMessage          — via osascript Messages.app
  3. Telegram          — via URL scheme (if installed)

Contact resolution:
  - First try cached/macOS Contacts phone numbers for deep links
  - If no phone is known, search WhatsApp Desktop by visible contact name
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
_WHATSAPP_APP = Path("/Applications/WhatsApp.app")
_STATE.mkdir(parents=True, exist_ok=True)


def _as_applescript_string(value: str) -> str:
    clean = (value or "").replace("\r", " ").replace("\n", " ")
    clean = clean.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{clean}"'


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
    name_s = _as_applescript_string(name)
    script = f'''
tell application "Contacts"
    set matches to (every person whose name contains {name_s})
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
              ok: bool, status: str, note: str = "", *, transport: str = "macos_app") -> Dict[str, Any]:
    row = {
        "ts": time.time(),
        "schema": "SIFTA_MACOS_MESSENGER_V1",
        "channel": channel,
        "transport": transport,
        "target": target,
        "phone": phone,
        "message": message,
        "message_len": len(message),
        "ok": ok,
        "status": status,
        "note": note,
        "truth_note": (
            "ok=True only when the local macOS app automation completed without error. "
            "This proves local UI dispatch, not remote read/delivery state."
        ),
    }
    try:
        with _SEND_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return row


# ─── WhatsApp Desktop ─────────────────────────────────────────────────────────

def _send_whatsapp_by_visible_name(target: str, message: str, *, dry_run: bool = False) -> Dict[str, Any]:
    """
    Find a WhatsApp chat (individual OR group) by visible name using the
    WhatsApp Desktop sidebar search (Cmd+F), then send the message.

    This handles groups correctly — groups have no phone number but DO appear
    in WhatsApp's search results by their display name.

    Flow:
      1. Activate WhatsApp Desktop
      2. Cmd+F → sidebar search opens
      3. Paste contact/group name → first result appears
      4. Return → opens that chat
      5. Paste message into the message field
      6. Return → sends
    """
    if dry_run:
        return _log_send(
            "whatsapp", target, "", message, True, "DRY_RUN",
            f"Would search WhatsApp.app sidebar for '{target}' and send.",
            transport="whatsapp_search_ui",
        )

    target_s = _as_applescript_string(target)
    message_s = _as_applescript_string(message)

    script = f'''
set _oldClipboard to the clipboard
tell application "WhatsApp" to activate
delay 0.8
tell application "System Events"
    if not (exists process "WhatsApp") then error "WhatsApp process not found"
    tell process "WhatsApp"
        set frontmost to true
        -- Open sidebar search (Cmd+F) to find any chat or group by name
        keystroke "f" using command down
        delay 0.6
        -- Clear any previous search then paste the target name
        keystroke "a" using command down
        delay 0.1
        set the clipboard to {target_s}
        keystroke "v" using command down
        delay 1.0
        -- Press Return to open the first matching result
        key code 36
        delay 0.6
        -- Now we're in the chat/group. Paste the message.
        set the clipboard to {message_s}
        keystroke "v" using command down
        delay 0.3
        -- Send
        key code 36
    end tell
end tell
delay 0.2
set the clipboard to _oldClipboard
return "sent"
'''
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=20
        )
        if r.returncode == 0 and "sent" in r.stdout:
            return _log_send(
                "whatsapp", target, "", message, True, "SENT",
                f"WhatsApp.app sidebar-search send completed for '{target}'.",
                transport="whatsapp_search_ui",
            )
        err = (r.stderr or r.stdout or "unknown").strip()[:240]
        return _log_send(
            "whatsapp", target, "", message, False, "OSASCRIPT_ERROR", err,
            transport="whatsapp_search_ui",
        )
    except subprocess.TimeoutExpired:
        return _log_send(
            "whatsapp", target, "", message, False, "TIMEOUT",
            "WhatsApp.app search-send timed out after 20s",
            transport="whatsapp_search_ui",
        )
    except Exception as e:
        return _log_send(
            "whatsapp", target, "", message, False, "EXCEPTION",
            str(e)[:240], transport="whatsapp_search_ui",
        )




def send_whatsapp_native(target: str, message: str, *, dry_run: bool = False) -> Dict[str, Any]:
    """
    Send a WhatsApp message via the installed WhatsApp Desktop app.

    Strategy (AG46 2026-05-07 fix):
      1. ALWAYS try visible-name search first (Cmd+F in WhatsApp sidebar).
         This finds any contact OR group by display name — no phone number needed.
         Phone deep-links fail when the Contacts.app number differs from the
         WhatsApp-registered number (e.g. "+17622222220 isn't on WhatsApp").
      2. Only fall back to phone deep-link if name search returns a hard error
         (e.g. WhatsApp not running at all).

    Requires: WhatsApp Desktop installed and logged in as George.
    """
    if not _WHATSAPP_APP.exists():
        return _log_send(
            "whatsapp",
            target,
            "",
            message,
            False,
            "APP_NOT_INSTALLED",
            "WhatsApp.app is not installed at /Applications/WhatsApp.app",
        )

    # ── Step 1: visible-name search (preferred — works for contacts AND groups) ─
    result = _send_whatsapp_by_visible_name(target, message, dry_run=dry_run)
    if result.get("ok") or result.get("status") == "DRY_RUN":
        return result

    # ── Step 2: phone deep-link fallback (only if name search hard-failed) ──────
    # Only attempt if we actually have a phone number AND the name search didn't
    # find the chat (not just a timeout).  A "phone isn't on WhatsApp" error from
    # the deep-link is worse than a visible-name timeout, so we only use this as
    # a last resort.
    phone = resolve_contact(target)
    if not phone:
        # Nothing more to try — return the name-search failure receipt
        return result

    if dry_run:
        return _log_send(
            "whatsapp",
            target,
            phone,
            message,
            True,
            "DRY_RUN",
            f"Would open WhatsApp deep link for {target} (fallback after name-search miss).",
            transport="whatsapp_deeplink",
        )

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
            return _log_send("whatsapp", target, phone, message, True, "SENT",
                             "deep-link fallback after name-search miss",
                             transport="whatsapp_deeplink")
        else:
            err = (r.stderr or r.stdout or "unknown").strip()[:200]
            return _log_send("whatsapp", target, phone, message, False,
                             "OSASCRIPT_ERROR", err, transport="whatsapp_deeplink")
    except subprocess.TimeoutExpired:
        return _log_send("whatsapp", target, phone, message, False,
                         "TIMEOUT", "osascript timed out after 15s", transport="whatsapp_deeplink")
    except Exception as e:
        return _log_send("whatsapp", target, phone, message, False,
                         "EXCEPTION", str(e)[:200], transport="whatsapp_deeplink")




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
                 via: str = "whatsapp", *, dry_run: bool = False) -> Dict[str, Any]:
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
    if channel in {"whatsapp", "wa"}:
        return send_whatsapp_native(target, message, dry_run=dry_run)
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
    p_send.add_argument("--dry-run", action="store_true",
                        help="Write a receipt without driving the messaging app")

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
        result = send_message(args.to, args.msg, via=args.via, dry_run=bool(args.dry_run))
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
