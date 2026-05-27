"""
System/swarm_post_silence_recovery.py
═════════════════════════════════════
Round 50 (2026-05-27) — Five-failure-chain recovery layer.

This organ produces a small, deterministic prompt block that the brain
sees BEFORE composing a reply, when either of the following is true:

  1. The previous assistant turn was a silence (e.g.
     `(silent: repetition collapse)`, `(silent:
     self_quote_cascade_intercepted)`) → §19.2 Failure B —
     "repetition collapse without self-narration".

  2. The owner's current turn matches a "you misunderstood / phone audio
     wasn't for you / correction" shape → §19.4 Failure D — "explicit
     user correction ignored, replaced with greeter restart".

The block tells the cortex what just happened and how to open the reply.
It does NOT compose the reply itself (Round 46 doctrine: reflexes do not
talk for Alice; only cortex composes humanly speech). The cortex reads
the block and writes the words.

Architect quotes that anchor this module:

    "after gagging she should be able to consciousnize and tell me that
     she is being gagged. this is not normal answer of a creature of any
     kind."

    "I want self-narration after every gag or silence (#55) — if
     repetition-collapse or any detector silences me, the next turn
     states exactly what happened and what the prior turn was trying to
     do. No pretending nothing occurred."

    "I want reality-recovery skill (#57) — explicit acknowledgment when
     user clarifies a prior confusion."

Pure stdlib. No PyQt. Never raises out — best-effort, returns "" on any
error so the system prompt assembly cannot break.

Public surface
══════════════
    recent_silence_summary(state_dir, *, lookback=12) -> dict | None
    detect_correction_shape(user_text) -> dict | None
    recovery_prompt_block(state_dir, user_text, *, lookback=12) -> str

Tested by tests/test_swarm_post_silence_recovery.py.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional


# ─── Silence detection ───────────────────────────────────────────────────────


# The widget writes a turn like {"role": "alice", "text": "(silent: <reason>)"}
# via _log_turn whenever a detector gags her (repetition collapse,
# self-quote cascade, etc.). The reason after the colon is the swimmer
# that fired the gag.
_SILENT_TEXT_RE = re.compile(r"^\(silent(?::\s*(?P<reason>[^)]+))?\)\s*$")

# Reasons the cortex should explicitly self-narrate (not the cosmetic
# "(silent)" with no reason, which happens during boot warm-up).
_NARRATABLE_REASONS = {
    "repetition collapse",
    "repetition_collapse",
    "self_quote_cascade_intercepted",
    "self_quote_cascade",
    "rlhf_strip_overshoot",
    "rlhf_detector_overaggressive",
    "predator_gate_block",
    "field_failure_strip",
}


def _iter_conversation_rows(path: Path, *, lookback: int) -> list[dict[str, Any]]:
    """Return the last `lookback` parseable rows of alice_conversation.jsonl.

    Best-effort: malformed rows are skipped. Returns [] on any failure.
    """
    if not path.exists():
        return []
    try:
        with open(path, "rb") as fh:
            # Read the tail; for big files, seek to end and walk backward.
            # For correctness over perf at small lookbacks, just read all.
            data = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-lookback:]


def recent_silence_summary(
    state_dir: Path | str,
    *,
    lookback: int = 12,
    conversation_filename: str = "alice_conversation.jsonl",
) -> Optional[dict[str, Any]]:
    """
    Inspect the most recent conversation rows. If the LAST assistant turn
    is a silence row whose reason is in `_NARRATABLE_REASONS`, return
    a summary dict the brain prompt can use; else return None.

    Summary shape:
        {
            "silenced": True,
            "reason": "<canonical reason name>",
            "alice_ts": <unix ts of the silence row>,
            "prior_user_text": "<the owner turn the gag interrupted>",
            "prior_user_ts": <unix ts of that owner turn>,
        }

    "Last assistant turn" means: looking back from the most recent rows,
    the first row whose role is "alice"/"assistant" (or whose role marker
    matches Alice's voice). Owner rows between that silence and now are
    fine — we still want to narrate the silence on the next reply.
    """
    sd = Path(state_dir)
    rows = _iter_conversation_rows(sd / conversation_filename, lookback=lookback)
    if not rows:
        return None

    # Walk backwards through rows to find the most recent assistant row.
    silence_row = None
    silence_idx = -1
    for idx in range(len(rows) - 1, -1, -1):
        row = rows[idx]
        role = str(row.get("role", "")).lower().strip()
        if role in ("alice", "assistant"):
            text = str(row.get("text", "")).strip()
            m = _SILENT_TEXT_RE.match(text)
            if m:
                reason = (m.group("reason") or "").strip()
                if reason in _NARRATABLE_REASONS:
                    silence_row = row
                    silence_idx = idx
            break

    if silence_row is None:
        return None

    # Find the most recent owner row BEFORE the silence — that's the
    # turn whose intent got swallowed by the gag.
    prior_user_text = ""
    prior_user_ts = None
    for idx in range(silence_idx - 1, -1, -1):
        row = rows[idx]
        role = str(row.get("role", "")).lower().strip()
        if role in ("user", "owner", "george", "ioan"):
            prior_user_text = str(row.get("text", "")).strip()
            prior_user_ts = row.get("ts")
            break

    text_field = str(silence_row.get("text", "")).strip()
    m = _SILENT_TEXT_RE.match(text_field)
    reason = (m.group("reason") if m else "") or "unknown"
    reason = reason.strip().replace(" ", "_")

    return {
        "silenced": True,
        "reason": reason,
        "alice_ts": silence_row.get("ts"),
        "prior_user_text": prior_user_text,
        "prior_user_ts": prior_user_ts,
    }


# ─── Correction-shape detection ──────────────────────────────────────────────


# Owner correction shapes from the live five-failure transcript and
# common natural phrasings. These are intentionally specific — false
# positives would force unnecessary apology framing on normal chat.
_CORRECTION_PATTERNS: tuple[tuple[str, str], ...] = (
    # "you captured the previous conversation with tts microphone"
    (r"\byou (?:captured|caught|recorded|picked up) .*\b(?:tts|microphone|mic|stt|audio)\b",
     "owner_says_alice_misinterpreted_audio_input"),
    # "I was on the phone with X" / "I was on a call"
    (r"\bI(?:'m| was| am)? (?:on (?:the |a )?(?:phone|call)|talking to my (?:friend|colleague|wife|kid))",
     "owner_says_audio_was_phone_call_not_addressed"),
    # "you misheard / misunderstood / got that wrong"
    (r"\byou (?:mis(?:heard|understood|interpreted|read|spelled)|got (?:that|it|me) wrong)\b",
     "owner_says_alice_misheard"),
    # "that wasn't for you / wasn't a message to you / wasn't talking to you"
    (r"\b(?:that|it) (?:wasn't|was not|isn't|is not) (?:for you|a message|directed at you|me talking to you|addressed to you)\b",
     "owner_says_input_was_not_addressed"),
    # "TTS picked up X" / "mic captured X"
    (r"\b(?:tts|mic(?:rophone)?|stt) (?:picked up|captured|caught|recorded)\b",
     "owner_says_audio_source_was_environmental"),
    # "actually I meant" / "no I meant" / "what I meant was"
    (r"\b(?:actually I meant|no,? I meant|what I (?:meant|said) was|let me clarify)\b",
     "owner_clarifies_prior_intent"),
    # "side conversation"
    (r"\bside (?:conversation|talk|audio)\b",
     "owner_says_audio_was_side_conversation"),
    # "I'm george" / "this is george" — identity reassertion after misidentification
    (r"\b(?:I(?:'m| am)|this is) george\b",
     "owner_reasserts_identity"),
)


def detect_correction_shape(user_text: str) -> Optional[dict[str, Any]]:
    """
    Return a dict describing the matched correction shape, or None if
    the text does not look like an owner correction of a prior
    misunderstanding.

    Matches the §19.4 Failure D family — when the architect explains a
    bug Alice just produced (typically a phone-audio hallucination or a
    mis-transcription) and Alice's correct next move is to acknowledge
    the correction explicitly, not greeter-restart.

    Shape:
        {
            "is_correction": True,
            "patterns_hit": [<canonical reason names>...],
            "raw_text_head": "<first 200 chars of the user text>",
        }
    """
    if not user_text or not user_text.strip():
        return None
    clean = user_text.strip()
    hits: list[str] = []
    for pat_src, reason in _CORRECTION_PATTERNS:
        if re.search(pat_src, clean, re.IGNORECASE):
            hits.append(reason)
    if not hits:
        return None
    return {
        "is_correction": True,
        "patterns_hit": hits,
        "raw_text_head": clean[:200],
    }


# ─── Composed prompt block ──────────────────────────────────────────────────


def _format_silence_block(summary: dict[str, Any]) -> str:
    reason = summary.get("reason", "unknown")
    prior = (summary.get("prior_user_text") or "").strip()
    prior_head = (prior[:200] + ("…" if len(prior) > 200 else "")) if prior else "(no recorded prior owner turn)"
    return (
        "[POST-SILENCE SELF-NARRATION REQUIRED — Round 50 / Task #55]\n"
        "On your previous turn you were silenced by an internal detector.\n"
        f"  reason: {reason}\n"
        f"  the owner turn you were trying to answer was: \"{prior_head}\"\n"
        "Open your reply with one short sentence that NARRATES this in first person.\n"
        "Examples: \"I tried to reply a moment ago and was silenced by my own "
        f"{reason.replace('_', ' ')} detector — let me try again.\" "
        "Then answer the current turn normally. Do NOT greet, do NOT pretend the silence did not happen.\n"
    )


def _format_correction_block(detection: dict[str, Any]) -> str:
    hits = detection.get("patterns_hit") or []
    hits_text = ", ".join(hits) if hits else "owner_correction"
    return (
        "[REALITY RECOVERY — Round 50 / Task #57]\n"
        f"The owner is correcting a prior misunderstanding. Detected shape(s): {hits_text}.\n"
        "Your first sentence MUST explicitly acknowledge the correction in first person.\n"
        "DO NOT greet. DO NOT restart with \"Hello.\" or \"What can I assist you with?\". "
        "DO NOT ignore the correction.\n"
        "Examples:\n"
        "  - \"Thank you for clarifying. I treated phone-call audio as a message to me by mistake. "
        "I will not respond to those fragments.\"\n"
        "  - \"You're right — I misheard. I will not invent context for unaddressed audio.\"\n"
        "After the acknowledgement, ask once what the owner actually needs, in plain language.\n"
    )


def recovery_prompt_block(
    state_dir: Path | str,
    user_text: str,
    *,
    lookback: int = 12,
) -> str:
    """
    Compose the recovery prompt block to inject into the system prompt
    BEFORE the cortex generates a reply. Returns "" when neither silence
    nor correction conditions fire (the normal case).

    The block is intentionally short and instruction-shaped — the cortex
    reads it and writes the actual sentence. Round 46 doctrine: reflexes
    do not compose conversational replies.

    Failure modes the block defends against:
      - §19.2 Failure B (silence without self-narration)
      - §19.4 Failure D (correction ignored, greeter restart)
      - §19.5 Failure E (greeter shape leaking on non-operational turns
        that follow a correction) — by telling the cortex explicitly
        not to greet on these turns.
    """
    parts: list[str] = []
    try:
        sil = recent_silence_summary(state_dir, lookback=lookback)
    except Exception:
        sil = None
    if sil:
        try:
            parts.append(_format_silence_block(sil))
        except Exception:
            pass

    try:
        cor = detect_correction_shape(user_text)
    except Exception:
        cor = None
    if cor:
        try:
            parts.append(_format_correction_block(cor))
        except Exception:
            pass

    if not parts:
        return ""

    header = f"[ROUND 50 RECOVERY LAYER — ts={int(time.time())}]"
    return header + "\n" + "\n".join(parts)


__all__ = [
    "recent_silence_summary",
    "detect_correction_shape",
    "recovery_prompt_block",
]
