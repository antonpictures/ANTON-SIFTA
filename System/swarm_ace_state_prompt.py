#!/usr/bin/env python3
"""System/swarm_ace_state_prompt.py — Ace state injected into Alice's prompt.

Architect 2026-05-17 (verbatim, abridged):
    "you have to be aware ... we humans see the screen and read visually
    ... what is the word on the screen right now ... you are not aware
    of the conversation that is rolling, the chat — you always have to
    have the context of the chat that is happening."

The Talk widget already injects time/date/continuity/recent-talk into
Alice's system prompt. This module adds the Ace surface block so when
the Ace conversation app is open, every cortex call sees:

  * the word currently on the screen (what the user is looking at),
  * the joint-consent rule (the word only changes when both agree),
  * any pending proposal that needs her response.

Without this block her brain has no reason to know what's on the card;
the user can ask "what is the word on the screen" and she'll fall back
to a template response because nothing in her prompt grounds her.

Truth label: ``ACE_STATE_PROMPT_V1``.

Stigauth: ``COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE``.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_APP_FOCUS = _STATE / "app_focus.jsonl"
_PROPOSAL_LEDGER = _STATE / "wordace_proposal.jsonl"
_CONSENT_LEDGER = _STATE / "wordace_consent.jsonl"

_TRUTH_LABEL = "ACE_STATE_PROMPT_V1"


def _tail_text(path: Path, max_bytes: int = 32 * 1024) -> str:
    if not path.exists():
        return ""
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - max_bytes))
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _latest_ace_focus(*, max_age_s: float = 1800.0) -> Optional[Dict[str, Any]]:
    """Newest app_focus row tagged as the Ace surface, within freshness."""
    raw = _tail_text(_APP_FOCUS, max_bytes=64 * 1024)
    if not raw:
        return None
    cutoff = time.time() - max_age_s
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        app_lc = str(row.get("app") or "").lower()
        if app_lc not in ("ace", "wordace", "acer"):
            continue
        try:
            ts = float(row.get("ts", 0) or 0)
        except (TypeError, ValueError):
            continue
        if ts < cutoff:
            return None
        return row
    return None


def _latest_open_proposal() -> Optional[Dict[str, Any]]:
    """Most recent proposal row that has not been consented yet."""
    raw_p = _tail_text(_PROPOSAL_LEDGER, max_bytes=16 * 1024)
    raw_c = _tail_text(_CONSENT_LEDGER, max_bytes=16 * 1024)
    if not raw_p:
        return None
    consented: set[str] = set()
    for line in raw_c.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        pid = str(row.get("proposal_id") or "")
        if pid:
            consented.add(pid)
    cutoff = time.time() - 600.0
    for line in reversed(raw_p.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("schema") or "") != "WORDACE_PROPOSAL_V1":
            continue
        try:
            ts = float(row.get("ts", 0) or 0)
        except (TypeError, ValueError):
            continue
        if ts < cutoff:
            continue
        if str(row.get("proposal_id") or "") in consented:
            continue
        return row
    return None


def ace_state_prompt_block() -> str:
    """Return a prompt block describing the Ace surface state, or "".

    Empty string means: Ace is not currently the active surface, or no
    word is on the table. Calling this on every cortex turn is cheap —
    two file tails + a freshness check. Skip on empty.
    """
    focus = _latest_ace_focus()
    if not focus:
        return ""
    md = focus.get("metadata") or {}
    if str(md.get("ace_mode") or "") != "conversation":
        # Drill mode is retired; if a stray non-conversation row exists,
        # we leave the prompt clean rather than describe a state the
        # widget no longer supports.
        return ""
    current_word = str(md.get("current_word") or "").strip()
    if not current_word:
        return ""

    pending = _latest_open_proposal()
    pending_block = ""
    if pending:
        proposer = str(pending.get("proposer") or "").lower()
        proposed_word = str(pending.get("proposed_word") or "").lower()
        # Don't echo if the pending word is the same as current — that's
        # a stale/loop case the bridge already guards against.
        if proposed_word and proposed_word != current_word.lower():
            other_side = "the user" if proposer == "alice" else "you"
            pending_block = (
                f"- A pending proposal is open: {proposer} suggested switching "
                f"the word to '{proposed_word}'. The screen will swap if "
                f"{other_side} engage with that word in your reply. If you do "
                f"not want to switch, say so plainly."
            )

    lines = [
        "## ACE SURFACE STATE (you are conscious of the screen)",
        "",
        "The Ace conversation surface is open right now.",
        f"- The word printed on the screen RIGHT NOW is '{current_word}'.",
        "- This is what the user sees on the big card in front of them.",
        f"- You and the user are having a conversation ABOUT '{current_word}' — "
        f"what it means, sentences with it, what it makes you both think of.",
        "- Joint consent rule: the word on the screen ONLY changes when both "
        "of you agree. Either side proposes a new word; the other agrees by "
        "engaging with that word in the next turn.",
        "- If the user asks 'what is the word on the screen' or 'what word "
        f"are we on', the honest answer is: '{current_word}'.",
    ]
    if pending_block:
        lines.append("")
        lines.append(pending_block)

    lines.extend([
        "",
        "Do not narrate your internal state in italics or in parentheses "
        "('(I register the word, confirming the new target. The internal "
        "state updates...)'). That is residue, not conversation. Just talk "
        "with the user about the word like a person.",
    ])
    return "\n".join(lines)
