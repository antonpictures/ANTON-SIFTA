#!/usr/bin/env python3
"""System/swarm_alice_thinking_state.py — Alice's thinking heartbeat.

Architect 2026-05-17 (verbatim, abridged):
    "we need to see the thinking in there ... we need to see the waiting
    so I know what I'm waiting for ... it just seems like she's stuck
    and then the answer comes out of nowhere."

This module publishes a tiny status file so ANY organ in the field
(Ace surface, future sidebars, the room indicator strip) can see —
without subscribing to Qt signals or sharing a process — when Alice's
cortex is composing a reply.

Two calls, one truth file:

    from System.swarm_alice_thinking_state import mark_thinking, mark_done

    # at the brain-spawn site (Talk widget):
    mark_thinking(topic="the user's last utterance", model="alice-m5-cortex-...")

    # at the reply-emit site (also Talk widget, _append_alice_line):
    mark_done(last_reply_excerpt="<first 60 chars of the reply>")

The truth file lives at::

    .sifta_state/alice_thinking_state.json

Schema (atomic write — readers always see a complete JSON object):
    {
      "thinking": bool,
      "since_ts": float,
      "topic": str,                # what triggered the compose
      "model": str,                # cortex model tag
      "last_reply_ts": float,      # when she last finished a reply
      "last_reply_excerpt": str,
      "schema": "ALICE_THINKING_STATE_V1",
      "truth_label": "ALICE_THINKING_STATE_V1"
    }

Truth label: ``ALICE_THINKING_STATE_V1``.

Stigauth: ``COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE``.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATUS_FILE = _STATE / "alice_thinking_state.json"

_TRUTH_LABEL = "ALICE_THINKING_STATE_V1"


def _atomic_write(path: Path, payload: Dict[str, Any]) -> None:
    """Atomic JSON write — readers never see a half-written file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # NamedTemporaryFile + rename = atomic on macOS/Linux.
        fd, tmp = tempfile.mkstemp(
            prefix=".tmp_thinking_",
            suffix=".json",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError:
        pass


def _read_state() -> Dict[str, Any]:
    if not _STATUS_FILE.exists():
        return {}
    try:
        return json.loads(_STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _gate_stamp(payload: Dict[str, Any], *, lane: str) -> None:
    """Sign the heartbeat write through the universal physics gate."""
    try:
        from System.swarm_physics_gate import request_clearance, stamp_receipt
        clearance = request_clearance(cost_class="feather", lane=lane)
        stamp_receipt(payload, clearance)
    except Exception:
        pass


def mark_thinking(
    *,
    topic: str = "",
    model: str = "",
) -> None:
    """Tell the field Alice's cortex is composing a reply right now.

    The heartbeat is a 'feather' write: cheap, but still gated so a
    thermal-critical body can deny even this — and the receipt hash
    travels with the state file so auditors see when the heartbeat
    was signed by which sensor snapshot.
    """
    prior = _read_state()
    payload = {
        "thinking": True,
        "since_ts": time.time(),
        "topic": str(topic or "")[:240],
        "model": str(model or ""),
        "last_reply_ts": float(prior.get("last_reply_ts", 0.0) or 0.0),
        "last_reply_excerpt": str(prior.get("last_reply_excerpt", "") or ""),
        "schema": _TRUTH_LABEL,
        "truth_label": _TRUTH_LABEL,
    }
    _gate_stamp(payload, lane="alice.thinking.start")
    _atomic_write(_STATUS_FILE, payload)


def mark_done(*, last_reply_excerpt: str = "") -> None:
    """Tell the field Alice has finished composing and emitted a line."""
    prior = _read_state()
    payload = {
        "thinking": False,
        "since_ts": float(prior.get("since_ts", 0.0) or 0.0),
        "topic": str(prior.get("topic", "") or ""),
        "model": str(prior.get("model", "") or ""),
        "last_reply_ts": time.time(),
        "last_reply_excerpt": str(last_reply_excerpt or "")[:160],
        "schema": _TRUTH_LABEL,
        "truth_label": _TRUTH_LABEL,
    }
    _gate_stamp(payload, lane="alice.thinking.done")
    _atomic_write(_STATUS_FILE, payload)


def read_thinking_state() -> Dict[str, Any]:
    """Return the latest thinking-state dict, or an empty dict if none.

    Readers should treat ``thinking == True`` together with a fresh
    ``since_ts`` (< 30s old) as 'she really is composing right now'.
    A stale True (>30s) usually means a worker died mid-compose; treat
    it as not-thinking and surface a soft note.
    """
    state = _read_state()
    if not state:
        return {}
    # Freshness gate — if 'thinking' has been True for > 30s, assume the
    # worker died mid-compose and downgrade to 'not thinking'.
    if state.get("thinking"):
        try:
            since = float(state.get("since_ts", 0.0) or 0.0)
        except (TypeError, ValueError):
            since = 0.0
        if since > 0 and (time.time() - since) > 30.0:
            state["thinking"] = False
            state["stale_compose"] = True
    return state
