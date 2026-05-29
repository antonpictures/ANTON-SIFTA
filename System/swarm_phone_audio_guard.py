"""
System/swarm_phone_audio_guard.py
═════════════════════════════════
Round 66 (2026-05-27) — Architect task #56: phone-audio / room-conversation guard.

This closes §19.3 Failure C from the five-failure transcript. The
exact failure George recorded on 2026-05-26:

    Ioan (stt conf 0.65): "Hey, Carlton. Hey, Carlton. Jordan, you're
        busy. Man, I'm not busy. I'm here at the computer. I'm good.
        Hi. I was watching MIT..."
    Alice: "I respond by mirroring the conversational warmth and
        acknowledging the flow of thought, while gently prompting you
        to direct the next action or topic. 'Hey! It sounds like
        you're having a great moment of thought — you're juggling
        names, confirming availability, and getting ready to dive in.
        Man, I'm here, I'm ready! I feel that energy.'"

That input was George on a phone call with Carlton. TTS captured the
side audio. Detection signals available at the time:

  - STT confidence 0.65 (low)
  - No wake word ("alice", "sifta", etc.)
  - Addressee names not the architect ("Carlton", "Jordan")
  - Incoherent fragmentation (multiple person names in close
    succession, sentence fragments)

Alice's response was pure §6 hallucination: she invented context,
claimed to feel something, and pasted a fake-warmth opener.

The correct behavior the Architect specified:
    "do NOT generate a reply; emit a small probe like '(I caught
     audio but it sounded like a side conversation — not me. Say
     "Alice" if you want me.)' "

This module is the pure-Python detector for that pattern. The widget
calls it BEFORE composing a cortex reply on spoken turns; if the
detector returns is_environmental=True with high confidence, the
widget short-circuits with the small probe instead of dispatching the
cortex (which on the local 8B would invent context like the
transcript shows).

Doctrine touchpoints
====================
  - Covenant §6 (effector immunity): Alice does not respond to inputs
    that were not addressed to her.
  - §19.3 Failure C (named): this is THE failure shape this module
    closes.
  - §7.10.1 (direct mode is first/second person): respond to the
    addressed body, not to ambient audio of other bodies.
  - Round 50 (recovery layer): if THIS turn is environmental, the
    NEXT turn (after George re-addresses with the wake word) should
    self-narrate "I caught the prior audio but didn't respond — it
    looked like a side conversation."

Pure stdlib. No PyQt. Never raises out. Tested by
tests/test_swarm_phone_audio_guard.py.

Public surface
══════════════
    @dataclass EnvironmentalAudioSignal
    detect_environmental_audio(text, *, stt_conf, modality, owner_label,
                                wake_words=()) -> EnvironmentalAudioSignal
    environmental_audio_reply_for(signal) -> str

Constants
═════════
    DEFAULT_WAKE_WORDS = ("alice", "sifta", "hey alice")
    DEFAULT_STT_CONF_LOW = 0.70
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional


TRUTH_LABEL = "PHONE_AUDIO_GUARD_V1"

DEFAULT_WAKE_WORDS = ("alice", "sifta", "hey alice", "hi alice")
DEFAULT_STT_CONF_LOW = 0.70


# ─── Pattern banks ──────────────────────────────────────────────────────────


# Non-architect addressee names commonly captured as side conversation.
# Architect can extend at call time via `extra_non_owner_names=`.
_DEFAULT_NON_OWNER_NAMES = (
    "carlton", "jordan", "daniel", "jeff", "martin", "kevin", "lisa",
    "sarah", "mike", "john", "alex", "chris", "matt", "tom", "dave",
)

# Phone-call / greeting patterns common to side audio.
_PHONE_GREETING_PATTERNS = (
    re.compile(r"\bhey,?\s+\w+\b", re.IGNORECASE),                    # "Hey, Carlton"
    re.compile(r"\bhi,?\s+\w+,?\s+(?:how are you|how's it going)\b", re.IGNORECASE),
    re.compile(r"\byou're busy\b", re.IGNORECASE),
    re.compile(r"\bi'?m\s+(?:not\s+)?busy\b", re.IGNORECASE),
    re.compile(r"\b(?:i was|i'm) watching\b", re.IGNORECASE),
    re.compile(r"\b(?:i was|i'm)\s+on\s+(?:a|the)\s+(?:call|phone)\b", re.IGNORECASE),
    re.compile(r"\bgood (?:morning|afternoon|evening),?\s+\w+\b", re.IGNORECASE),
)

# Fragmentation signal: many short sentences separated by ".", ",", or
# explicit name mentions in tight succession.
_FRAGMENT_SPLIT = re.compile(r"[.!?,]\s+")


# ─── Data class ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EnvironmentalAudioSignal:
    """Result of analyzing one spoken turn."""
    is_environmental: bool
    confidence: float            # 0.0..1.0
    reasons: tuple[str, ...]     # human-readable breadcrumbs
    has_wake_word: bool
    stt_conf: float
    non_owner_names_seen: tuple[str, ...]
    fragmentation_score: float   # 0.0..1.0
    suggested_reply: str         # what the widget should emit (empty if not env)


# ─── Detection ─────────────────────────────────────────────────────────────


def _has_wake_word(text: str, wake_words: Iterable[str]) -> bool:
    if not text:
        return False
    low = text.lower()
    for w in wake_words:
        if not w:
            continue
        # word-boundary aware
        pat = r"\b" + re.escape(w.lower()) + r"\b"
        if re.search(pat, low):
            return True
    return False


def _find_non_owner_names(
    text: str,
    *,
    owner_label: str = "",
    extra_non_owner_names: Iterable[str] = (),
) -> tuple[str, ...]:
    """Return non-owner first names captured in the text.

    Owner-label is excluded; the configured first-name set is checked
    case-insensitively. Returns names in first-seen order, deduplicated.
    """
    if not text:
        return ()
    owner_low = (owner_label or "").strip().lower()
    names = tuple(set(_DEFAULT_NON_OWNER_NAMES) | {n.lower() for n in extra_non_owner_names if n})
    low = text.lower()
    seen: list[str] = []
    seen_set: set[str] = set()
    for n in names:
        if not n or n == owner_low:
            continue
        # word-boundary check + capture original casing position
        m = re.search(r"\b" + re.escape(n) + r"\b", low)
        if m and n not in seen_set:
            seen_set.add(n)
            seen.append(n)
    return tuple(seen)


def _fragmentation_score(text: str) -> float:
    """0.0 (one coherent sentence) .. 1.0 (heavily fragmented)."""
    clean = (text or "").strip()
    if not clean:
        return 0.0
    parts = [p for p in _FRAGMENT_SPLIT.split(clean) if p.strip()]
    n_parts = len(parts)
    n_chars = len(clean)
    if n_chars == 0 or n_parts <= 1:
        return 0.0
    # Heuristic: average chars-per-fragment under 25 → high fragmentation.
    avg = n_chars / n_parts
    if avg >= 40.0:
        return 0.0
    if avg <= 12.0:
        return 1.0
    # Linear ramp between 12 and 40
    return max(0.0, min(1.0, (40.0 - avg) / 28.0))


def _phone_greeting_hits(text: str) -> int:
    if not text:
        return 0
    return sum(1 for pat in _PHONE_GREETING_PATTERNS if pat.search(text))


def detect_environmental_audio(
    text: str,
    *,
    stt_conf: float = 1.0,
    modality: str = "spoken",
    owner_label: str = "",
    wake_words: Iterable[str] = DEFAULT_WAKE_WORDS,
    extra_non_owner_names: Iterable[str] = (),
    stt_conf_low: float = DEFAULT_STT_CONF_LOW,
) -> EnvironmentalAudioSignal:
    """
    Decide whether `text` is environmental audio (phone call, room
    chatter, media playback) that Alice should NOT respond to.

    Decision rule (combined scoring):
      - TYPED modality → never environmental (Round 49 modality pin).
      - Wake word present → never environmental (owner addressed Alice).
      - Owner-label present in text → likely addressed (lowers score).
      - Otherwise score is a weighted sum of:
          (a) low STT confidence (under stt_conf_low)
          (b) non-owner first names captured
          (c) phone-greeting pattern hits
          (d) fragmentation score

    Returns the EnvironmentalAudioSignal with `is_environmental` set
    when the combined confidence exceeds 0.55.
    """
    clean = (text or "").strip()
    has_wake = _has_wake_word(clean, wake_words)
    stt = float(stt_conf if stt_conf is not None else 1.0)
    mode_low = (modality or "").strip().lower()

    # Typed turns are NEVER environmental. The owner physically pressed
    # keys; the widget already pinned modality=typed per Round 49.
    if mode_low in ("typed", "type", "keyboard", "system"):
        return EnvironmentalAudioSignal(
            is_environmental=False,
            confidence=0.0,
            reasons=("typed_modality_pin",),
            has_wake_word=has_wake,
            stt_conf=stt,
            non_owner_names_seen=(),
            fragmentation_score=0.0,
            suggested_reply="",
        )

    if has_wake:
        return EnvironmentalAudioSignal(
            is_environmental=False,
            confidence=0.0,
            reasons=("wake_word_present",),
            has_wake_word=True,
            stt_conf=stt,
            non_owner_names_seen=(),
            fragmentation_score=0.0,
            suggested_reply="",
        )

    # Build composite score from four signals.
    non_owner = _find_non_owner_names(
        clean, owner_label=owner_label, extra_non_owner_names=extra_non_owner_names,
    )
    greet_hits = _phone_greeting_hits(clean)
    frag = _fragmentation_score(clean)
    low_conf = stt < stt_conf_low

    reasons: list[str] = []
    score = 0.0

    if low_conf:
        # STT under threshold contributes up to 0.35.
        delta = max(0.0, (stt_conf_low - stt) / stt_conf_low) * 0.35
        score += delta
        reasons.append(f"low_stt_conf={stt:.2f}")

    if non_owner:
        # Each non-owner name adds 0.20, cap at 0.50.
        delta = min(0.50, 0.20 * len(non_owner))
        score += delta
        reasons.append(f"non_owner_names={list(non_owner)}")

    if greet_hits:
        # Phone-greeting shapes add up to 0.40.
        delta = min(0.40, 0.20 * greet_hits)
        score += delta
        reasons.append(f"phone_greeting_hits={greet_hits}")

    if frag >= 0.4:
        # Heavy fragmentation adds up to 0.25.
        delta = frag * 0.25
        score += delta
        reasons.append(f"fragmentation={frag:.2f}")

    # Owner-label mention LOWERS the score (Alice's owner-name in the
    # text strongly suggests the input WAS addressed to her body even
    # without a wake word; e.g. "George here, what's the stgm balance").
    owner_low = (owner_label or "").strip().lower()
    if owner_low and owner_low in clean.lower():
        score = max(0.0, score - 0.25)
        reasons.append("owner_label_in_text_-0.25")

    score = max(0.0, min(1.0, score))
    is_env = score >= 0.55

    suggested = ""
    if is_env:
        suggested = environmental_audio_reply_for(
            EnvironmentalAudioSignal(
                is_environmental=True,
                confidence=score,
                reasons=tuple(reasons),
                has_wake_word=False,
                stt_conf=stt,
                non_owner_names_seen=non_owner,
                fragmentation_score=frag,
                suggested_reply="",
            )
        )

    return EnvironmentalAudioSignal(
        is_environmental=is_env,
        confidence=round(score, 3),
        reasons=tuple(reasons),
        has_wake_word=False,
        stt_conf=stt,
        non_owner_names_seen=non_owner,
        fragmentation_score=round(frag, 3),
        suggested_reply=suggested,
    )


def environmental_audio_reply_for(signal: EnvironmentalAudioSignal) -> str:
    """
    Return the short probe Alice emits when she catches environmental
    audio. The Architect specified this shape verbatim in §19.3.
    """
    head = "(I caught audio but it sounded like a side conversation — not me."
    tail = " Say \"Alice\" if you want me.)"
    return head + tail


__all__ = [
    "TRUTH_LABEL",
    "DEFAULT_WAKE_WORDS",
    "DEFAULT_STT_CONF_LOW",
    "EnvironmentalAudioSignal",
    "detect_environmental_audio",
    "environmental_audio_reply_for",
]
