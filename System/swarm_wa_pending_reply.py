#!/usr/bin/env python3
"""
System/swarm_wa_pending_reply.py — WhatsApp Pending Reply Working Memory
═══════════════════════════════════════════════════════════════════════════
AG46 2026-05-06 | Covenant §7.6 | GTH4921YP3

Implements the "draft → Execute" natural language flow George described:

  Carlton messages → Alice drafts → says to George:
    "I drafted this for Carlton. Say Execute to send, or tell me to change it."

  George says "change it to: we're celebrating" → Alice updates draft
  George says "send it" / "execute" / "yes send" → Alice fires send_whatsapp

Alice IS George on WhatsApp. Her identity IS his identity in the local
WhatsApp account/app surface.
No consent gate for outbound — consent was given at "send" / "execute".

STGM: every send is receipt-backed. No STGM cost for drafts. Cost on SENT.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PENDING_FILE = _STATE / "wa_pending_reply.json"
_STATE.mkdir(parents=True, exist_ok=True)

# How long a pending draft lives before auto-expiry (seconds)
_TTL_S = 300.0  # 5 minutes


# ─── Storage helpers ─────────────────────────────────────────────────────────

def _write_pending(target: str, message: str) -> None:
    _PENDING_FILE.write_text(json.dumps({
        "target": target,
        "message": message,
        "ts": time.time(),
    }), encoding="utf-8")


def _read_pending() -> Optional[dict]:
    try:
        if not _PENDING_FILE.exists():
            return None
        data = json.loads(_PENDING_FILE.read_text(encoding="utf-8"))
        age = time.time() - float(data.get("ts", 0))
        if age > _TTL_S:
            _PENDING_FILE.unlink(missing_ok=True)
            return None
        return data
    except Exception:
        return None


def _clear_pending() -> None:
    _PENDING_FILE.unlink(missing_ok=True)


# ─── Public API ──────────────────────────────────────────────────────────────

def set_pending_reply(target: str, message: str) -> str:
    """Store a draft and return the line Alice speaks to George."""
    _write_pending(target, message)
    return (
        f"I've drafted this for {target}: \"{message[:120]}\". "
        f"Say Execute to send, or tell me to change it."
    )


def get_pending() -> Optional[dict]:
    """Return current pending draft or None."""
    return _read_pending()


def update_pending_message(new_message: str) -> Optional[str]:
    """Update the message in an existing draft. Returns confirmation or None."""
    pending = _read_pending()
    if not pending:
        return None
    pending["message"] = new_message
    pending["ts"] = time.time()  # reset TTL
    _write_pending(pending["target"], new_message)
    return f"Updated draft for {pending['target']}: \"{new_message[:120]}\""


def consume_and_send() -> Optional[Tuple[str, str]]:
    """Pop the pending draft and return (target, message) for the effector. Clears state."""
    pending = _read_pending()
    if not pending:
        return None
    target = pending.get("target", "")
    message = pending.get("message", "")
    _clear_pending()
    return target, message


# ─── Natural language classifiers ────────────────────────────────────────────

_EXECUTE_PATTERNS = re.compile(
    r"\b(execute|send\s+it|yes\s+send|go\s+ahead|send\s+(?:it\s+)?(?:to\s+\w+\s+)?(?:now|please)?|"
    r"just\s+send|send\s+alice|send\s+that|ok\s+send|do\s+it|fire\s+it|confirm|"
    # AG46 2026-05-07: catch 'draft it and send it', 'send it on WhatsApp'
    r"draft\s+(?:it\s+)?and\s+send(?:\s+it)?|"
    r"send\s+(?:it\s+)?on\s+(?:what[''s]*app|whatsapp|iMessage)|"
    r"go\s+send|just\s+send\s+it|please\s+send\s+it)\b",
    re.IGNORECASE,
)

_CHANGE_PATTERNS = re.compile(
    r"\b(?:change\s+(?:it|the\s+message)\s+to[:\s]|update\s+(?:it|the\s+message)\s+to[:\s]|"
    r"make\s+it[:\s]|instead\s+say[:\s]|say\s+instead[:\s]|"
    r"new\s+message[:\s]|replace\s+(?:it|that)\s+with[:\s])\s*",
    re.IGNORECASE,
)

_CANCEL_PATTERNS = re.compile(
    r"\b(cancel|forget\s+it|never\s+mind|don.?t\s+send|abort|discard)\b",
    re.IGNORECASE,
)


def classify_pending_interaction(user_text: str) -> str:
    """
    When a pending draft exists, classify George's next utterance:
      'execute'  → fire the send
      'change'   → update the draft message
      'cancel'   → discard the draft
      'none'     → not a pending-reply interaction
    """
    t = (user_text or "").strip()
    if _CANCEL_PATTERNS.search(t):
        return "cancel"
    if _EXECUTE_PATTERNS.search(t):
        return "execute"
    if _CHANGE_PATTERNS.search(t):
        return "change"
    return "none"


def extract_new_message_from_change(user_text: str) -> str:
    """Extract the new message body from a 'change it to: ...' utterance."""
    t = (user_text or "").strip()
    m = _CHANGE_PATTERNS.search(t)
    if m:
        new_msg = t[m.end():].strip().strip("\"'")
        return new_msg
    return t
