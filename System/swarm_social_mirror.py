#!/usr/bin/env python3
"""
swarm_social_mirror.py — Conversation Role Awareness (Social Mirror)
══════════════════════════════════════════════════════════════════════

Biology doctrine: Theory of Mind + Self/Other Separation.

Who said this? Who is the audience? Am I supposed to answer, summarize, 
or stay silent?

Inbound message ≠ permission to reply.
Reading to owner ≠ replying to sender.
Owner discussion ≠ external send.
External send requires explicit outbound consent or owner-delegated per-target
consent from the WhatsApp Organ.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Tuple

@dataclass
class SocialMirrorEvent:
    direction: str  # "inbound" | "outbound"
    speaker: str    # "contact" | "owner" | "alice"
    audience: str   # "owner" | "contact" | "group"
    action: str     # "observe" | "summarize_to_owner" | "draft_reply" | "send_reply"
    consent: str    # "none" | "owner_explicit" | "owner_delegated" | "contact_context" | "emergency"
    ts: float = 0.0
    agency_verdict_id: str = ""
    event_id: str = ""

    def __post_init__(self):
        if not self.ts:
            self.ts = time.time()


class SwarmSocialMirror:
    def __init__(self, state_dir: str = ".sifta_state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = self.state_dir / "social_mirror.jsonl"

    def log_event(self, event: SocialMirrorEvent) -> None:
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(self.ledger, json.dumps(asdict(event)) + "\n")
        except ImportError:
            with self.ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(event)) + "\n")

    def may_send_whatsapp(self, event: SocialMirrorEvent) -> Tuple[bool, str]:
        """
        Enforces strict speaker attribution and outbound consent.
        """
        if event.direction != "outbound":
            return False, "rejected_not_outbound"
        if event.action != "send_reply":
            return False, "rejected_not_send_reply_action"
        if event.consent not in {"owner_explicit", "owner_delegated"}:
            return False, "rejected_requires_owner_explicit_or_delegated_consent"
        return True, "allowed"
