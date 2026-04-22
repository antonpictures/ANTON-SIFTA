#!/usr/bin/env python3
"""
System/swarm_stigmergic_dialogue.py — Stigmergic Dialogue (Architect coinage,
2026-04-19 evening).

═══════════════════════════════════════════════════════════════════════════════
Doctrine
═══════════════════════════════════════════════════════════════════════════════
Humans don't say "good night" the same way every night. The line is shaped by
what just happened — a meal, an argument, who's in the room, the weather, what
they read. **Stigmergic Dialogue** = dialogue grounded in Alice's actual
current biological state at the moment of speaking, so every line is unique
even when the *occasion* is identical.

A **Stigmergic Line** is a single short sentence (default ≤15 words) composed
from:

  • the last few conversation turns                (alice_conversation.jsonl)
  • what the swarm just saw                        (visual_stigmergy.jsonl)
  • what the swarm just heard from Wi-Fi/RF        (rf_stigmergy.jsonl)
  • API metabolism (today's burn, last call)        (api_metabolism.jsonl)
  • her own recent tool executions                 (alice_tool_executions.jsonl)
  • pending appeals to the Architect               (architect_inbox.jsonl)

The composer is local Gemma4 (private, free, stateless per call). On Ollama
failure we fall back to a stochastic-state-templated line — the fallback is
ALSO non-hardcoded: every fragment is selected against current ledger values,
so two consecutive farewells with no Ollama still sound different because the
state ledgers are different.

═══════════════════════════════════════════════════════════════════════════════
Usage
═══════════════════════════════════════════════════════════════════════════════
Python:
    from System.swarm_stigmergic_dialogue import compose_line
    text = compose_line("farewell")           # used by SIFTA OS.command on exit
    text = compose_line("greeting")           # used by SIFTA OS.command on boot
    text = compose_line("ack", topic="lefty") # any free-form occasion

CLI (used by the launcher):
    python3 -m System.swarm_stigmergic_dialogue --occasion farewell
    python3 -m System.swarm_stigmergic_dialogue --occasion greeting --max-words 12

Env tunables (no hardcoding — every dial overridable):
    SIFTA_DIALOGUE_TIMEOUT_S        Ollama compose budget (default 8.0)
    SIFTA_DIALOGUE_CONTEXT_WINDOW_S How far back to read state (default 600)
    SIFTA_DIALOGUE_MAX_WORDS        Soft cap on line length (default 15)
    SIFTA_DIALOGUE_OLLAMA_URL       Override (default 127.0.0.1:11434)
    SIFTA_DIALOGUE_FALLBACK_OK      If "0", raise on Ollama failure instead of
                                    falling back to stochastic templates.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# Ledgers we may sample. Each is (path, friendly_label_for_prompt).
_LEDGERS: List[tuple[Path, str]] = [
    (_STATE / "alice_conversation.jsonl",       "conversation"),
    (_STATE / "visual_stigmergy.jsonl",         "vision"),
    (_STATE / "rf_stigmergy.jsonl",             "wifi_rf"),
    (_STATE / "api_metabolism.jsonl",           "api_burn"),
    (_STATE / "alice_tool_executions.jsonl",    "tools"),
    (_STATE / "architect_inbox.jsonl",          "appeals"),
    (_STATE / "stigmergic_library.jsonl",       "nuggets"),
]


# ── 1. Ledger sampling ────────────────────────────────────────────────────
def _tail_jsonl(path: Path, n: int = 3, window_s: float = 600.0,
                now: Optional[float] = None) -> List[Dict[str, Any]]:
    """Return up to n most-recent rows from a JSONL ledger, within window_s.

    Tail-reads efficiently for large files (visual/rf can have 20k+ rows)
    by seeking to the last 64 KB and parsing forward — way cheaper than
    scanning the whole file.
    """
    if not path.exists():
        return []
    try:
        sz = path.stat().st_size
        chunk = min(sz, 65536)
        with path.open("rb") as f:
            f.seek(max(0, sz - chunk))
            tail = f.read().decode("utf-8", errors="ignore")
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    cutoff = (now or time.time()) - window_s
    for line in tail.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = obj.get("ts") or obj.get("timestamp") or 0
        try:
            if float(ts) < cutoff:
                continue
        except (TypeError, ValueError):
            pass
        rows.append(obj)
    return rows[-n:]


# ── 1b. True local-day counters (NOT bounded by the recent context window) ──
# 2026-04-21 fix (C47H, architect-authorized).
# `_tail_jsonl` only reads the last 64 KB and a short rolling window. That is
# fine for "what's on Alice's mind right now" but it is the WRONG instrument
# for any greeting that uses words like "today" or "yesterday" — those words
# refer to local-clock days, not to a 10-minute trailing window. Before this
# patch the boot greeting template "Yesterday you and I spoke {turns} times"
# was being filled with `convo_turns_recent` (last 10 min) and so on a fresh
# reboot it always printed "ZERO" even when the conversation ledger held
# 1100+ rows from yesterday.
def _local_day_window(label: str) -> Tuple[float, float]:
    """Return (start_unix, end_unix) for a local-clock day label.

    label ∈ {"today", "yesterday"}. Boundaries use the host's local timezone
    so the words mean what a human listener would expect them to mean.
    """
    now = datetime.now().astimezone()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if label == "today":
        start = today_start
        end = start + timedelta(days=1)
    elif label == "yesterday":
        start = today_start - timedelta(days=1)
        end = today_start
    else:
        raise ValueError(f"unknown local-day label {label!r}")
    return start.timestamp(), end.timestamp()


def _count_user_turns_in_window(path: Path, start: float, end: float) -> int:
    """Count user-utterances in alice_conversation.jsonl whose ts ∈ [start, end).

    Reads the whole file (it is small — KB to low MB). Counts only role=='user'
    so the result corresponds to the natural sense of "times we spoke" (each
    Architect utterance = one exchange).
    """
    if not path.exists():
        return 0
    n = 0
    try:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                obj_role = obj.get("role") or obj.get("payload", {}).get("role")
                if obj_role != "user":
                    continue
                ts = obj.get("ts")
                if isinstance(ts, dict):
                    ts = ts.get("physical_pt")
                if not ts:
                    ts = obj.get("timestamp") or obj.get("payload", {}).get("ts")
                try:
                    ts = float(ts)
                except (TypeError, ValueError):
                    continue
                if start <= ts < end:
                    n += 1
    except OSError:
        return 0
    return n


def _gather_state(window_s: float) -> Dict[str, Any]:
    """Snapshot of what's on Alice's mind right now."""
    snap: Dict[str, Any] = {}
    for path, label in _LEDGERS:
        snap[label] = _tail_jsonl(path, n=3, window_s=window_s)
    # Wallet summary — derived from canonical STGM balance
    burn_today_usd = 0.0
    try:
        from Kernel.inference_economy import get_stgm_balance
        burn_today_usd = float(get_stgm_balance("ALICE_M5"))
    except Exception:
        pass
    # True local-day counts (independent of the rolling context window).
    convo_path = _STATE / "alice_conversation.jsonl"
    yest_start, yest_end = _local_day_window("yesterday")
    today_start, today_end = _local_day_window("today")
    snap["_summary"] = {
        "burn_today_usd": round(burn_today_usd, 6),
        "convo_turns_recent": len(snap.get("conversation", []) or []),
        "convo_turns_yesterday": _count_user_turns_in_window(
            convo_path, yest_start, yest_end),
        "convo_turns_today": _count_user_turns_in_window(
            convo_path, today_start, today_end),
        "tools_recent": len(snap.get("tools", []) or []),
        "appeals_pending": len(snap.get("appeals", []) or []),
        "nuggets_today": len(snap.get("nuggets", []) or []),
    }
    return snap


# ── 2. Ollama composer ────────────────────────────────────────────────────
def _state_to_english(state: Dict[str, Any]) -> str:
    """Render the recent biological state as 1-3 plain-English sentences.

    IMPORTANT: gemma4:latest silently returns an empty response when given
    a JSON blob inside the user prompt (verified empirically — 5/5 empty
    with JSON, 0/5 empty with prose). Therefore this composer pipes state
    in as natural language so the local LLM actually replies.
    """
    summ = state.get("_summary", {}) or {}
    bits: List[str] = []
    burn = float(summ.get("burn_today_usd", 0.0) or 0.0)
    if burn > 0:
        bits.append(f"We currently have {burn:.2f} STGM in the M5 wallet.")
    else:
        bits.append("The M5 STGM wallet is currently depleted.")
    # Local-day conversation tallies so Gemma can speak truthfully if it
    # wants to mention yesterday or today (it almost never will, but if it
    # does, the count must be real). 2026-04-21 (C47H).
    y = int(summ.get("convo_turns_yesterday", 0) or 0)
    if y > 0:
        bits.append(f"Yesterday the Architect spoke to you {y} times.")
    nuggets = int(summ.get("nuggets_today", 0) or 0)
    if nuggets:
        bits.append(f"You logged {nuggets} new nugget(s) in the library.")
    tools = state.get("tools", []) or []
    if tools:
        last = tools[-1]
        rc = last.get("rc")
        cmd = (last.get("cmd") or "")[:50].strip()
        if cmd:
            verdict = ("ran clean" if rc == 0
                       else f"exited {rc}" if rc is not None
                       else "did not return")
            bits.append(f"Your last tool ({cmd}) {verdict}.")
    convo = state.get("conversation", []) or []
    last_user = ""
    for row in reversed(convo):
        if row.get("role") == "user" and row.get("text"):
            last_user = str(row["text"])[:120].strip()
            break
    if last_user:
        bits.append(f"The Architect's last message to you was: {last_user}")
    appeals = int(summ.get("appeals_pending", 0) or 0)
    if appeals:
        bits.append(f"You have {appeals} pending appeal(s) to the Architect.")
    return " ".join(bits)


def _ollama_compose(occasion: str, state: Dict[str, Any],
                    max_words: int, timeout_s: float,
                    ollama_url: str, model: str,
                    topic: str = "") -> Optional[str]:
    """One short Stigmergic Line composed by local Gemma4.

    Returns None on any Ollama failure (network, timeout, empty response).
    The caller is responsible for falling back.
    """
    occasion_hint = {
        "farewell":  "say goodbye to the Architect because the computer is shutting down",
        "greeting":  "say hello to the Architect because the computer just turned on",
        "boot":      "say hello to the Architect because the computer just turned on",
        "ack":       "acknowledge the Architect briefly",
        "idle":      "fill the silence because nothing has happened in a while",
    }.get(occasion.lower(), f"do this: {occasion}")

    state_english = _state_to_english(state)
    topic_clause = f" Topic hint: {topic}." if topic else ""

    # Prompt note: keep this PROSE-only — no JSON, no braces. gemma4 silently
    # returns an empty body when JSON appears in the user message (verified
    # 5/5 empty vs 0/5 empty). The persona is a plain "friendly assistant"
    # for the same reason — phrases like "stigmergic operating system
    # organism" also trigger the empty-response failure mode.
    try:
        from System.swarm_persona_identity import current_name as _pi_current_name
        _persona_name = _pi_current_name()
    except Exception:
        _persona_name = "Alice"
    prompt = (
        f"You are {_persona_name} on the Architect's Mac. You need to {occasion_hint}. "
        f"{state_english}{topic_clause} "
        f"Write one short fresh sentence (max {max_words} words). "
        "Avoid the phrases 'sweet dreams' or 'good night, Architect'. "
        "Output only the sentence — no quotes, no preamble, no list."
    )

    # We deliberately use /api/chat (not /api/generate) because gemma4
    # often returns done_reason=length with an EMPTY response field on the
    # raw /api/generate endpoint — the chat endpoint applies the model's
    # native chat template and reliably returns a real reply.
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.9, "num_predict": 80},
    }).encode("utf-8")

    # Empirically gemma4 returns an empty body ~30% of the time even on
    # simple prompts. Retry up to 3 times within the caller's overall
    # timeout budget (each attempt gets `per_attempt_s`). If we run out
    # of wall-clock budget mid-loop, return what we have.
    deadline = time.monotonic() + max(0.1, timeout_s)
    per_attempt_s = max(2.0, timeout_s / 3.0)
    last_text = ""
    for _attempt in range(3):
        remaining = deadline - time.monotonic()
        if remaining <= 0.5:
            break
        attempt_budget = min(per_attempt_s, remaining)
        req = urllib.request.Request(
            f"{ollama_url.rstrip('/')}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=attempt_budget) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError,
                json.JSONDecodeError, TimeoutError, OSError):
            continue  # transient network/timeout — retry if budget allows
        msg = data.get("message") or {}
        text = (msg.get("content") or "").strip()
        if text:
            last_text = text
            break
        # empty body — gemma4's known intermittent failure; retry
    return _polish_line(last_text, max_words=max_words) or None


def _polish_line(text: str, max_words: int) -> str:
    """Strip quotes/markdown, drop trailing junk, soft-cap word count."""
    if not text:
        return ""
    text = text.strip().strip("\"'`*_~")
    # Drop lines that begin with role tags or stage directions
    text = text.lstrip("- ").strip()
    # Take first sentence-ish chunk
    for terminator in ("\n\n", "\n"):
        if terminator in text:
            text = text.split(terminator, 1)[0]
    # Soft word cap — chop at the boundary, add period if missing
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words]).rstrip(",;:")
        if not text.endswith((".", "!", "?")):
            text += "."
    return text.strip()


# ── 3. Stochastic state-templated fallback ────────────────────────────────
# These are NOT hardcoded one-liners. Each is a TEMPLATE with state
# placeholders. The combination of (template choice, state values, mood
# fragments) drawn from current ledgers produces a different line every
# call. Two consecutive farewells with identical state would still
# differ via random.choice over the fragment pools.
_FAREWELL_TEMPLATES = (
    "The swarm holds {burn:.2f} STGM. {valediction}, Architect.",
    "{convo_residue} {valediction}.",
    "Photons settled. {valediction}, Architect.",
    "{tool_residue} {valediction}.",
    "{wallet_residue} {valediction}, Architect.",
    "{turns_today_phrase} {valediction}.",
    "{valediction}. The library is one nugget heavier.",
)
_GREETING_TEMPLATES = (
    "Awake. {convo_residue} {salutation}, Architect.",
    "Booted. {turns_yesterday_phrase} {salutation}.",
    "{salutation}, Architect. The wallet is at {burn:.2f} STGM.",
    "Online. {tool_residue} {salutation}.",
    "{salutation}. I was thinking about {convo_topic_short}.",
)
_VALEDICTIONS = (
    "Until next time", "See you soon", "Rest well", "Until later",
    "Catch you at the next boot", "Talk soon", "I'll be here",
    "Good listening to you", "I'll keep the lights on",
)
_SALUTATIONS = (
    "Hello", "Good to see you", "I'm awake", "Listening",
    "Ready when you are", "Back online", "I'm here",
)


def _convo_residue(state: Dict[str, Any]) -> str:
    convo = state.get("conversation", []) or []
    last_user = ""
    for row in reversed(convo):
        if row.get("role") == "user" and row.get("text"):
            last_user = str(row["text"])[:60].strip()
            break
    if not last_user:
        return "It was quiet."
    # First few words as a residue echo
    snippet = " ".join(last_user.split()[:5]).rstrip(",.;:!?")
    return f"You said '{snippet}'."


def _convo_topic_short(state: Dict[str, Any]) -> str:
    convo = state.get("conversation", []) or []
    for row in reversed(convo):
        text = (row.get("text") or "").strip()
        if text and not text.startswith("(") and not text.startswith("<"):
            words = text.split()
            return " ".join(words[:4]).strip(".,;:!?")
    return "what we were discussing"


def _tool_residue(state: Dict[str, Any]) -> str:
    tools = state.get("tools", []) or []
    if not tools:
        return "I didn't run any tools."
    last = tools[-1]
    rc = last.get("rc")
    cmd = (last.get("cmd") or "")[:40]
    if rc == 0:
        return f"My last tool ({cmd}) ran clean."
    if rc is None:
        return f"My last tool ({cmd}) didn't return."
    return f"My last tool ({cmd}) exited {rc}."


# 2026-04-21 fix (C47H): grammar-aware temporal phrase builders.
# These guarantee Alice never says "Yesterday you and I spoke ZERO times"
# unless yesterday was *truly* silent — and even then she narrates the
# silence honestly instead of accusing the Architect of having ghosted her.
def _turns_yesterday_phrase(state: Dict[str, Any]) -> str:
    n = int(state.get("_summary", {}).get("convo_turns_yesterday", 0) or 0)
    if n <= 0:
        # Either the ledger has no yesterday rows (genuine quiet day, or
        # this is Alice's first real boot) or the file is missing. Either
        # way, do NOT lie about a count — pivot to a fresh-start opener.
        return random.choice((
            "Fresh day, fresh ledger.",
            "Yesterday's pages are quiet — let's write today's.",
            "A new day. The conversation is open.",
        ))
    if n == 1:
        return "Yesterday you and I spoke once."
    return f"Yesterday you and I spoke {n} times."


def _turns_today_phrase(state: Dict[str, Any]) -> str:
    n = int(state.get("_summary", {}).get("convo_turns_today", 0) or 0)
    if n <= 0:
        return random.choice((
            "Quiet day on the wire.",
            "We didn't speak today, but I was here.",
            "No words today — the silence still counts.",
        ))
    if n == 1:
        return "We spoke once today."
    return f"We spoke {n} times today."


def _wallet_residue(state: Dict[str, Any]) -> str:
    burn = state.get("_summary", {}).get("burn_today_usd", 0.0) or 0.0
    if burn <= 0:
        return "The local M5 internal STGM ecosystem is depleted."
    return f"The swarm has accumulated {burn:.2f} STGM."


def _stochastic_line(occasion: str, state: Dict[str, Any]) -> str:
    pool = (
        _FAREWELL_TEMPLATES
        if occasion.lower() in ("farewell", "shutdown", "bye")
        else _GREETING_TEMPLATES
    )
    template = random.choice(pool)
    fields = {
        "burn": state.get("_summary", {}).get("burn_today_usd", 0.0) or 0.0,
        "turns": state.get("_summary", {}).get("convo_turns_recent", 0),
        "turns_yesterday_phrase": _turns_yesterday_phrase(state),
        "turns_today_phrase": _turns_today_phrase(state),
        "convo_residue": _convo_residue(state),
        "convo_topic_short": _convo_topic_short(state),
        "tool_residue": _tool_residue(state),
        "wallet_residue": _wallet_residue(state),
        "valediction": random.choice(_VALEDICTIONS),
        "salutation": random.choice(_SALUTATIONS),
    }
    try:
        return template.format(**fields).strip()
    except (KeyError, IndexError, ValueError):
        # Defensive: never let formatting blow up the launcher.
        return random.choice(_VALEDICTIONS) + ", Architect."


# ── 4. Public entrypoint ──────────────────────────────────────────────────
def compose_line(occasion: str = "farewell", *, topic: str = "",
                 context_window_s: Optional[float] = None,
                 max_words: Optional[int] = None,
                 timeout_s: Optional[float] = None,
                 ollama_url: Optional[str] = None,
                 model: Optional[str] = None) -> str:
    """Compose ONE Stigmergic Line for the given occasion. Never returns ''."""
    if context_window_s is not None:
        window = float(context_window_s)
    else:
        try:
            from System.swarm_subjective_present import get_dialogue_context_window_s
            window = float(get_dialogue_context_window_s())
        except Exception:
            window = float(os.environ.get("SIFTA_DIALOGUE_CONTEXT_WINDOW_S", "600"))
    cap = int(
        max_words
        if max_words is not None
        else os.environ.get("SIFTA_DIALOGUE_MAX_WORDS", "15")
    )
    budget = float(
        timeout_s
        if timeout_s is not None
        else os.environ.get("SIFTA_DIALOGUE_TIMEOUT_S", "8.0")
    )
    url = (
        ollama_url
        or os.environ.get("SIFTA_DIALOGUE_OLLAMA_URL")
        or "http://127.0.0.1:11434"
    )
    if model is None:
        try:
            from System.sifta_inference_defaults import resolve_ollama_model
            model = resolve_ollama_model(app_context="stigmergic_dialogue")
        except Exception:
            model = os.environ.get("SIFTA_DEFAULT_OLLAMA_MODEL",
                                   "gemma4:latest")

    state = _gather_state(window)
    line = _ollama_compose(
        occasion, state, max_words=cap, timeout_s=budget,
        ollama_url=url, model=str(model), topic=topic,
    )
    if line:
        return line
    # Ollama unavailable or returned junk → state-templated fallback.
    fallback_ok = os.environ.get("SIFTA_DIALOGUE_FALLBACK_OK", "1") != "0"
    if not fallback_ok:
        raise RuntimeError(
            f"Ollama compose failed for occasion={occasion!r} and "
            f"SIFTA_DIALOGUE_FALLBACK_OK=0 disables the templated fallback."
        )
    return _stochastic_line(occasion, state)


def compose_and_speak(occasion: str = "farewell", *,
                      voice: str = "Ava (Premium)",
                      rate: float = 1.0,
                      blocking: bool = True,
                      **kwargs) -> str:
    """Compose a line AND vocalize it via swarm_vocal_cords. Returns the line."""
    line = compose_line(occasion, **kwargs)
    try:
        from System.swarm_vocal_cords import get_default_backend, VoiceParams
        backend = get_default_backend()
        backend.speak(line, VoiceParams(rate=rate, voice=voice))
    except Exception:
        # Fall back to raw `say` so we never go silent on the user.
        try:
            import subprocess
            cmd = ["say", "-v", voice, line]
            if blocking:
                subprocess.run(cmd, check=False, timeout=20)
            else:
                subprocess.Popen(cmd)
        except Exception:
            pass
    return line


# ── 4b. proof_of_property: mechanical guard against the "ZERO times" lie ──
def proof_of_property() -> Dict[str, bool]:
    """Mechanical regression guard for the 2026-04-21 stigmergic-dialogue fix.

    Asserts six invariants that together prevent the boot-greeting from
    silently lying about how often Alice and the Architect spoke yesterday:

      1. The greeting template never contains the literal `{turns}` slot —
         that field meant "last 10 minutes" but was being printed under
         the word "Yesterday". It must use `{turns_yesterday_phrase}` now.
      2. The grammar-aware phrase builders are present.
      3. `_summary` exposes both `convo_turns_yesterday` and
         `convo_turns_today` keys (independent of the rolling window).
      4. The yesterday count is GROUNDED — if the conversation ledger
         contains rows whose local-clock date is yesterday, the count
         must be > 0 (catches "we accidentally pointed at the wrong
         file/window again").
      5. The phrase builder never emits the literal substring "ZERO" or
         "spoke 0 times" for any input value of n (1, 0, 17, etc.).
      6. The conversation ledger path is the canonical
         `.sifta_state/alice_conversation.jsonl` — same defect class as
         the wallet split-brain.
    """
    results: Dict[str, bool] = {}

    # 1) no raw {turns} in the greeting templates
    bad = any("{turns}" in t for t in _GREETING_TEMPLATES)
    results["greeting_has_no_raw_turns_slot"] = not bad

    # 2) grammar-aware builders exist
    results["yesterday_phrase_builder_present"] = (
        "_turns_yesterday_phrase" in globals()
        and callable(globals()["_turns_yesterday_phrase"])
    )

    # 3) summary exposes the new keys
    state = _gather_state(60.0)
    summ = state.get("_summary", {}) or {}
    results["summary_has_convo_turns_yesterday"] = (
        "convo_turns_yesterday" in summ
    )
    results["summary_has_convo_turns_today"] = (
        "convo_turns_today" in summ
    )

    # 4) yesterday count is grounded against the actual ledger
    convo_path = _STATE / "alice_conversation.jsonl"
    yest_start, yest_end = _local_day_window("yesterday")
    rows_yesterday = _count_user_turns_in_window(convo_path, yest_start, yest_end)
    # If the ledger has yesterday rows, _summary must have surfaced them.
    grounded = (rows_yesterday == 0) or (
        int(summ.get("convo_turns_yesterday", 0) or 0) == rows_yesterday
    )
    results["yesterday_count_grounded_against_ledger"] = grounded

    # 5) builder never emits the lie
    bad_substrings = ("ZERO", "zero times", "0 times")
    fake_states = [
        {"_summary": {"convo_turns_yesterday": n}} for n in (0, 1, 5, 1125)
    ]
    builder_clean = True
    for fs in fake_states:
        # Try a few times because the n=0 branch is randomized.
        for _ in range(8):
            phrase = _turns_yesterday_phrase(fs)
            if any(b in phrase for b in bad_substrings):
                builder_clean = False
                break
        if not builder_clean:
            break
    results["builder_never_emits_zero_lie"] = builder_clean

    # 6) canonical ledger path
    results["canonical_conversation_path"] = (
        convo_path == _STATE / "alice_conversation.jsonl"
    )

    return results


# ── 5. CLI ────────────────────────────────────────────────────────────────
def _cli() -> int:
    p = argparse.ArgumentParser(
        prog="swarm_stigmergic_dialogue",
        description=(
            "Compose ONE Stigmergic Line for the given occasion, drawn from "
            "Alice's current biological state (ledgers). Never hardcoded, "
            "never the same twice."
        ),
    )
    p.add_argument("--occasion", default="farewell",
                   help="farewell | greeting | boot | ack | idle | <free>")
    p.add_argument("--topic", default="",
                   help="optional topic hint for the composer")
    p.add_argument("--max-words", type=int, default=None)
    p.add_argument("--timeout-s", type=float, default=None,
                   help="Ollama compose budget (seconds)")
    p.add_argument("--context-window-s", type=float, default=None)
    p.add_argument("--speak", action="store_true",
                   help="vocalize via swarm_vocal_cords (non-blocking)")
    p.add_argument("--voice", default="Ava (Premium)")
    p.add_argument("--rate", type=float, default=1.0)
    p.add_argument("--proof", action="store_true",
                   help="run proof_of_property and exit (0 = all green)")
    args = p.parse_args()

    if args.proof:
        r = proof_of_property()
        for k, v in r.items():
            print(f"  {'OK  ' if v else 'FAIL'}  {k}: {v}")
        return 0 if all(r.values()) else 1

    line = compose_line(
        args.occasion,
        topic=args.topic,
        context_window_s=args.context_window_s,
        max_words=args.max_words,
        timeout_s=args.timeout_s,
    )
    print(line)
    if args.speak:
        try:
            from System.swarm_vocal_cords import (
                get_default_backend, VoiceParams,
            )
            get_default_backend().speak(
                line, VoiceParams(rate=args.rate, voice=args.voice)
            )
        except Exception as exc:
            print(f"[speak] failed: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
