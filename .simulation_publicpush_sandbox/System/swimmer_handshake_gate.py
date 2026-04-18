#!/usr/bin/env python3
"""
swimmer_handshake_gate.py — Policy gate before a “payload” mutates substrate (SIFTA, not vasculature)
══════════════════════════════════════════════════════════════════════════════════════════════════

Speculative **nanomedical** stories often mix: (i) real **targeted therapy** (ADCs, antibodies),
(ii) micro/nanorobotics research, (iii) **cryptographic** metaphors. This module implements only (iii)
for the **repo**: optional HMAC handshake + JSON policy so automated jobs do not execute destructive
writes without an approved **context fingerprint**.

Literature anchors: DYOR §21 (Palagi & Fischer 2018; ADC reviews; p53 stress/apoptosis framing).

**Not** a medical device. **Not** treating humans. Governance for Alice/Swarm scripts only.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
POLICY_PATH = _STATE / "swimmer_release_policy.json"
_DENY_LOG = _STATE / "swimmer_handshake_denials.jsonl"

_ENV_SECRET = "SIFTA_SWIMMER_HMAC_KEY"


@dataclass(frozen=True)
class HandshakeVerdict:
    allowed: bool
    reason: str


def _load_policy() -> Dict[str, Any]:
    if not POLICY_PATH.exists():
        return {"routes": {}, "require_hmac": False}
    try:
        return json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"routes": {}, "require_hmac": False}


def _append_denial(route: str, detail: str) -> None:
    from System.jsonl_file_lock import append_line_locked

    row = {"event_id": str(uuid.uuid4()), "ts": time.time(), "route": route, "detail": detail}
    _STATE.mkdir(parents=True, exist_ok=True)
    append_line_locked(_DENY_LOG, json.dumps(row, ensure_ascii=False) + "\n")


def evaluate_release(
    *,
    route: str,
    context_token: str,
    presented_mac: Optional[str] = None,
) -> HandshakeVerdict:
    """
    If `swimmer_release_policy.json` lists allowed prefix patterns for `route`, `context_token`
    must start with one of them. If `require_hmac` is true, `presented_mac` must be
    hex(HMAC-SHA256(key, route + '\\n' + context_token)).
    """
    pol = _load_policy()
    routes = pol.get("routes") or {}
    cfg = routes.get(route)
    if not cfg:
        return HandshakeVerdict(True, "no policy for route — allowed (configure policy to harden)")

    prefixes = list(cfg.get("prefix_allowlist") or [])
    ok_prefix = any(context_token.startswith(p) for p in prefixes)
    if not ok_prefix:
        _append_denial(route, "prefix mismatch")
        return HandshakeVerdict(False, "context_token not in prefix_allowlist")

    if pol.get("require_hmac") and os.environ.get(_ENV_SECRET):
        if not presented_mac:
            _append_denial(route, "missing MAC")
            return HandshakeVerdict(False, "HMAC required")
        key = os.environ[_ENV_SECRET].encode("utf-8")
        msg = f"{route}\n{context_token}".encode("utf-8")
        expect = hmac.new(key, msg, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, presented_mac.strip().lower()):
            _append_denial(route, "bad MAC")
            return HandshakeVerdict(False, "HMAC mismatch")

    return HandshakeVerdict(True, "handshake ok")


def default_policy_template() -> Dict[str, Any]:
    """Example structure for the Architect to edit."""
    return {
        "require_hmac": False,
        "routes": {
            "immune_quarantine_release": {"prefix_allowlist": ["architect_approved:", "m5_foundry:"]},
        },
    }


__all__ = ["HandshakeVerdict", "POLICY_PATH", "default_policy_template", "evaluate_release"]
