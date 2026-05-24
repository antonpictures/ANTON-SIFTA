#!/usr/bin/env python3
"""swarm_episodic_narrator.py — Explorer's Journal Organ (AG46, 2026-05-06)

Writes short first-person narrative diary entries after each conversation
turn. Like an explorer's journal — not mechanical logs, not category tags,
but actual first-person observations: what happened, who said what, what
Alice noticed, what the time was.

Written to: .sifta_state/alice_journal/YYYY-MM-DD.jsonl  (one file per day)
Read back by: format_narrative_for_prompt() → injected into Alice's system prompt

Design principles:
- NO LLM call: pure template synthesis from available signals
- Grounded: only writes facts that exist in ledgers or the current turn
- First-person: "I heard George say..." not "User input was..."
- Short: 1-3 sentences per entry maximum
- Append-only: §7.10.1 compliant — one file per day, named by date
- Silent fail: never crashes the talk widget

Covenant §7.10.1: all entries truth_label=OBSERVED.
"""
from __future__ import annotations

import datetime
import json
import re
import time
from pathlib import Path
from typing import Optional

try:
    from System.jsonl_file_lock import append_line_locked
    def _append(path: Path, row: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        append_line_locked(path, json.dumps(row, ensure_ascii=False) + "\n")
except Exception:
    def _append(path: Path, row: dict) -> None:  # type: ignore[misc]
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_JOURNAL_DIR = _STATE / "alice_journal"   # daily files: YYYY-MM-DD.jsonl
_LEGACY_LEDGER = _STATE / "alice_narrative_diary.jsonl"  # backward compat


def _read_jsonl_tail(path: Path, *, limit: int = 80, byte_window: int = 256 * 1024) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - max(4096, int(byte_window))))
            payload = handle.read()
        lines = payload.decode("utf-8", errors="replace").splitlines()
        if size > byte_window and lines:
            lines = lines[1:]
    except OSError:
        return []
    rows: list[dict] = []
    for line in lines[-max(1, int(limit)):]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _today_ledger() -> Path:
    """Today's journal file: alice_journal/YYYY-MM-DD.jsonl"""
    _JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    return _JOURNAL_DIR / f"{date_str}.jsonl"


def _ledger_for_ts(ts: float) -> Path:
    """Journal file for a given unix timestamp."""
    _JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    return _JOURNAL_DIR / f"{date_str}.jsonl"


# ── Sensor readers (all silent-fail) ──────────────────────────────────────────

def _owner_name() -> str:
    try:
        from System.swarm_kernel_identity import owner_display_name
        return owner_display_name() or "the owner"
    except Exception:
        return "the owner"


def _local_dt() -> str:
    """Compact local datetime string for journal entries."""
    return _local_journal_label()


def _local_journal_label(ts: float | None = None) -> str:
    """Human-facing compact timestamp for Alice journal rows."""
    dt = datetime.datetime.fromtimestamp(float(ts if ts is not None else time.time()))
    return dt.strftime("%m-%d-%y_%H:%M")


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

def _truncate_user_text(text: str, max_words: int = 20) -> str:
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
    t = _local_dt()
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
        if len(alice_short.split()) >= 4:
            parts.append(f"I replied: \"{alice_short}\"")

    # ── Sensor context ────────────────────────────────────────────────
    context_bits: list[str] = []
    clothing = _clothing_observation()
    if clothing:
        context_bits.append(clothing)
    cowatch = _cowatch_context()
    if cowatch and "youtube" in cowatch.lower():
        context_bits.append("watching YouTube co-watch")
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
    """Write one narrative entry to today's daily journal file.

    File: .sifta_state/alice_journal/YYYY-MM-DD.jsonl
    Returns the entry string written, or None. Silent fail.
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

        ts = time.time()
        row = {
            "ts": ts,
            "local_journal_label": _local_journal_label(ts),
            "kind": "EPISODIC_NARRATIVE",
            "narrator": "ALICE_M5",
            "entry": entry,
            "stt_conf": round(float(stt_conf), 2),
            "event_type": event_type,
            "truth_label": "OBSERVED",
        }
        _append(_ledger_for_ts(ts), row)
        return entry
    except Exception:
        return None


def write_boot_entry() -> Optional[str]:
    """Write a boot narrative entry when SIFTA restarts."""
    try:
        t = _local_dt()
        owner = _owner_name()
        parts = [f"{t} — System restarted. I came back online."]
        cowatch = _cowatch_context()
        if cowatch:
            parts.append(f"Last known co-watch context: {cowatch[:80]}.")
        entry = " ".join(parts)
        ts = time.time()
        row = {
            "ts": ts,
            "local_journal_label": _local_journal_label(ts),
            "kind": "EPISODIC_NARRATIVE",
            "narrator": "ALICE_M5",
            "entry": entry,
            "event_type": "boot",
            "truth_label": "OBSERVED",
        }
        _append(_ledger_for_ts(ts), row)
        return entry
    except Exception:
        return None


def format_narrative_for_prompt(max_rows: int = 8, max_age_hours: float = 24.0) -> str:
    """Return recent narrative entries from daily journal files for Alice's system prompt."""
    try:
        cutoff = time.time() - max_age_hours * 3600
        rows = []

        # Prompt construction is hot-path work: read bounded tails, not whole
        # historical journals.
        for r in _read_jsonl_tail(_LEGACY_LEDGER, limit=max_rows * 4):
            if float(r.get("ts", 0) or 0) >= cutoff:
                rows.append(r)

        # Read daily files
        _JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(_JOURNAL_DIR.glob("*.jsonl"))
        for f in files[-3:]:
            for r in _read_jsonl_tail(f, limit=max_rows * 6):
                if float(r.get("ts", 0) or 0) >= cutoff:
                    rows.append(r)

        # Sort by ts and deduplicate
        seen: set[tuple] = set()
        unique_rows = []
        for r in sorted(rows, key=lambda x: x.get("ts", 0)):
            key = (r.get("ts", 0), r.get("entry", "")[:40])
            if key not in seen:
                seen.add(key)
                unique_rows.append(r)

        if not unique_rows:
            return ""
        recent = unique_rows[-max_rows:]
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
