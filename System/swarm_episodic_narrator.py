#!/usr/bin/env python3
"""swarm_episodic_narrator.py — Explorer's Journal Organ (AG46, 2026-05-06)

Writes short first-person narrative diary entries after each conversation
turn. Like an explorer's journal — not mechanical logs, not category tags,
but actual first-person observations: what happened, who said what, what
Alice noticed, what the time was.

Written to: .sifta_state/alice_narrative_diary.jsonl
Read back by: format_narrative_for_prompt() → injected into Alice's system prompt

Design principles:
- NO LLM call: pure template synthesis from available signals
- Grounded: only writes facts that exist in ledgers or the current turn
- First-person: "I heard George say..." not "User input was..."
- Short: 1-3 sentences per entry maximum
- Append-only: §7.10.1 compliant
- Silent fail: never crashes the talk widget

Covenant §7.10.1: all entries truth_label=OBSERVED.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

try:
    from System.jsonl_file_lock import append_line_locked
    def _append(path: Path, row: dict) -> None:
        append_line_locked(path, json.dumps(row, ensure_ascii=False) + "\n")
except Exception:
    def _append(path: Path, row: dict) -> None:  # type: ignore[misc]
        with open(path, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "alice_narrative_diary.jsonl"

# ── Sensor readers (all silent-fail) ──────────────────────────────────────────

def _owner_name() -> str:
    try:
        from System.swarm_kernel_identity import owner_display_name
        return owner_display_name("George")
    except Exception:
        return "George"


def _local_hhmm() -> str:
    import datetime
    return datetime.datetime.now().strftime("%H:%M")


def _local_datetime() -> str:
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _clothing_observation() -> Optional[str]:
    """Return most recent clothing observation from memory swimmers."""
    try:
        ml = _STATE / "memory_ledger.jsonl"
        if not ml.exists():
            return None
        lines = ml.read_text().strip().splitlines()
        for line in reversed(lines[-80:]):
            try:
                r = json.loads(line)
                tags = r.get("tags", r.get("metadata", {}).get("tags", []))
                text = r.get("text", r.get("content", ""))
                if "clothing" in tags and text:
                    # Extract a short clothing phrase
                    m = re.search(
                        r"(?:wearing|shirt|jacket|hoodie|top|clothes?)[^.!?\n]{0,60}",
                        text, re.IGNORECASE
                    )
                    if m:
                        return m.group(0).strip()
            except Exception:
                pass
    except Exception:
        pass
    return None


def _cowatch_context() -> Optional[str]:
    """Return current co-watch video title/URL if active."""
    try:
        from System.swarm_media_ingress_gate import get_latest_observed_media_context
        ctx = get_latest_observed_media_context(max_age_s=3600, max_chars=120)
        if ctx:
            return ctx
    except Exception:
        pass
    try:
        mc = _STATE / "media_cowatch_state.jsonl"
        if mc.exists():
            lines = mc.read_text().strip().splitlines()
            if lines:
                r = json.loads(lines[-1])
                title = r.get("title", "") or r.get("url", "")
                if title:
                    return title[:100]
    except Exception:
        pass
    return None


def _phone_active() -> bool:
    """Return True if a phone call is in progress (no end logged after start)."""
    try:
        be = _STATE / "owner_body_events.jsonl"
        if not be.exists():
            return False
        last_phone_event = None
        for line in be.read_text().strip().splitlines()[-30:]:
            try:
                r = json.loads(line)
                et = r.get("event_type", "")
                if et.startswith("phone_call"):
                    last_phone_event = et
            except Exception:
                pass
        return last_phone_event in ("phone_call_active", "phone_call_start")
    except Exception:
        return False


def _recent_phone_note() -> Optional[str]:
    """Return the most recent phone call note if within last 30 min."""
    try:
        be = _STATE / "owner_body_events.jsonl"
        if not be.exists():
            return None
        now = time.time()
        for line in reversed(be.read_text().strip().splitlines()[-40:]):
            try:
                r = json.loads(line)
                if r.get("event_type", "").startswith("phone_call"):
                    if now - float(r.get("ts", 0)) < 1800:
                        return r.get("note", "")[:80]
            except Exception:
                pass
    except Exception:
        pass
    return None


# ── Narrative synthesis ───────────────────────────────────────────────────────

def _truncate_user_text(text: str, max_words: int = 18) -> str:
    """Return a truncated, readable paraphrase of what the user said."""
    text = (text or "").strip()
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


def _build_entry(
    *,
    user_text: str,
    alice_text: str,
    stt_conf: float,
    event_type: str = "turn",
    extra_facts: Optional[list[str]] = None,
) -> str:
    """Synthesize a 1-3 sentence first-person narrative entry."""
    owner = _owner_name()
    t = _local_hhmm()
    parts: list[str] = []

    # ── What George said ──────────────────────────────────────────────
    if user_text and stt_conf >= 0.60:
        short = _truncate_user_text(user_text, max_words=20)
        parts.append(f"{t} — {owner} said: \"{short}\"")
    elif user_text and stt_conf >= 0.40:
        short = _truncate_user_text(user_text, max_words=14)
        parts.append(f"{t} — {owner} (audio unclear, ~{int(stt_conf*100)}%): \"{short}\"")
    elif event_type == "boot":
        parts.append(f"{t} — System restarted. I came back online.")
    elif event_type == "phone_call_retroactive":
        parts.append(f"{t} — {owner} told me the earlier audio was a phone call, not him talking to me.")
    elif event_type == "phone_call_active":
        parts.append(f"{t} — {owner} is on a phone call.")
    elif event_type == "phone_call_end":
        parts.append(f"{t} — {owner}'s phone call ended.")

    # ── What Alice did ────────────────────────────────────────────────
    if alice_text and not alice_text.startswith("(silent"):
        alice_short = _truncate_user_text(alice_text, max_words=16)
        # Only write if alice actually said something substantive
        if len(alice_short.split()) >= 4:
            parts.append(f"I replied: \"{alice_short}\"")

    # ── Sensor context: clothing, media, phone ─────────────────────────
    context_bits: list[str] = []
    clothing = _clothing_observation()
    if clothing:
        context_bits.append(clothing)
    cowatch = _cowatch_context()
    if cowatch and "youtube" in cowatch.lower():
        # Trim URL/noise to just a readable note
        context_bits.append(f"watching YouTube co-watch")
    elif cowatch:
        context_bits.append(f"co-watch: {cowatch[:60]}")
    phone_note = _recent_phone_note()
    if phone_note:
        context_bits.append("phone call noted")
    if extra_facts:
        context_bits.extend(f[:60] for f in extra_facts)
    if context_bits:
        parts.append("Context: " + "; ".join(context_bits[:3]) + ".")

    return " ".join(parts) if parts else ""


# ── Public API ────────────────────────────────────────────────────────────────

def write_narrative_entry(
    *,
    user_text: str = "",
    alice_text: str = "",
    stt_conf: float = 0.0,
    event_type: str = "turn",
    extra_facts: Optional[list[str]] = None,
) -> Optional[str]:
    """Write one narrative entry to alice_narrative_diary.jsonl.

    Returns the entry string written, or None if nothing was written.
    Silent fail — never raises.
    """
    try:
        entry = _build_entry(
            user_text=user_text,
            alice_text=alice_text,
            stt_conf=stt_conf,
            event_type=event_type,
            extra_facts=extra_facts,
        )
        if not entry:
            return None

        row = {
            "ts": time.time(),
            "kind": "EPISODIC_NARRATIVE",
            "narrator": "ALICE_M5",
            "entry": entry,
            "stt_conf": round(float(stt_conf), 2),
            "event_type": event_type,
            "truth_label": "OBSERVED",
        }
        _append(_LEDGER, row)
        return entry
    except Exception:
        return None


def write_boot_entry() -> Optional[str]:
    """Write a boot narrative entry when SIFTA restarts."""
    try:
        t = _local_datetime()
        owner = _owner_name()
        parts = [f"{t} — System restarted. I came back online."]
        cowatch = _cowatch_context()
        if cowatch:
            parts.append(f"Last known co-watch context: {cowatch[:80]}.")
        entry = " ".join(parts)
        row = {
            "ts": time.time(),
            "kind": "EPISODIC_NARRATIVE",
            "narrator": "ALICE_M5",
            "entry": entry,
            "event_type": "boot",
            "truth_label": "OBSERVED",
        }
        _append(_LEDGER, row)
        return entry
    except Exception:
        return None


def format_narrative_for_prompt(max_rows: int = 8, max_age_hours: float = 24.0) -> str:
    """Return recent narrative entries for Alice's system prompt.

    This is Alice's first-person diary — she reads her own observations.
    """
    try:
        if not _LEDGER.exists():
            return ""
        cutoff = time.time() - max_age_hours * 3600
        rows = []
        for line in _LEDGER.read_text().strip().splitlines():
            try:
                r = json.loads(line)
                if float(r.get("ts", 0)) >= cutoff:
                    rows.append(r)
            except Exception:
                pass
        if not rows:
            return ""
        recent = rows[-max_rows:]
        lines_out = ["MY JOURNAL (first-person narrative memory — append-only):"]
        for r in recent:
            entry = r.get("entry", "").strip()
            if entry:
                lines_out.append(f"  {entry}")
        return "\n".join(lines_out) if len(lines_out) > 1 else ""
    except Exception:
        return ""


__all__ = [
    "write_narrative_entry",
    "write_boot_entry",
    "format_narrative_for_prompt",
]
