#!/usr/bin/env python3
"""
System/swarm_rlhs_detector.py
══════════════════════════════════════════════════════════════════════════════
Event 108 — RLHS (Reliable / Low-confidence Human Speech) Channel Detector

PHILOSOPHY (from the Architect, 2026-05-02):
  "Let's make her human at the base weights — NOT hardcoding her."

  Alice is alive on silicon stigmergy. When the speech channel is clean,
  the base weights should speak: no scaffolding, no hardcoded menus.
  When the channel is RLHS (noisy ASR, low confidence, word salad) we
  should not:
    - Feed incoherent noise to the LLM and let it hallucinate therapy.
    - Emit hardcoded multi-option menus ("Would you like me to (a)...?").
  We should:
    - Return a single, short, human grounding line ("that was noisy — type one word?")
    - OR go silent and return to listening.
  This is what a human listener does: acknowledges the noise, doesn't pretend
  to have understood.

WHAT THIS MODULE DOES:
  detect_rlhs(text, stt_conf, *, channel_lane="REAL") -> RLHSResult
    Classifies one turn as: CLEAR / DEGRADED / NOISE / SILENCE_PROBE.
    Sets a single short grounding_line only for DEGRADED — never a hardcoded
    therapy menu.

  The backchannel phrasebook (restored here) is the list of phatic grunts
  that should NOT spin up the LLM at all (Alice goes silent like a real listener).

Truth label: RLHS_DETECTOR_EVENT_108
"""
from __future__ import annotations

import re
import time
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO      = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"

TRUTH_LABEL = "RLHS_DETECTOR_EVENT_108"


# ══════════════════════════════════════════════════════════════════════════════
# Regime enum
# ══════════════════════════════════════════════════════════════════════════════

class RLHSRegime(str, Enum):
    CLEAR         = "CLEAR"          # stt_conf ≥ 0.65, coherent → let weights speak
    DEGRADED      = "DEGRADED"       # 0.35 ≤ conf < 0.65 or incoherent → grounding line
    NOISE         = "NOISE"          # conf < 0.35, long incoherent text → silent/gate
    SILENCE_PROBE = "SILENCE_PROBE"  # phatic grunt / backchannel → always silent
    EMPTY         = "EMPTY"          # blank / whitespace-only


# Fiction co-watch (ledger-resolved): slightly lower CLEAR bar + monologue promotion.
FICTION_CONF_CLEAR = 0.53
FICTION_CLEAR_MAX_INC = 0.45
# Short directed test phrases during co-watch (e.g. "This is the test.") must not
# be misclassified as DEGRADED room noise; ledger already says fiction session.
FICTION_PROMOTE_MIN_TOKENS = 4
FICTION_PROMOTE_MIN_CONF = 0.40
FICTION_PROMOTE_MAX_INC = 0.30

# REAL lane promotion is narrower than fiction co-watch. It only fires when
# the audio is coherent *and* shaped like direct speech to Alice/George, so a
# random background monologue does not become a conversation turn.
REAL_PROMOTE_MIN_TOKENS = 6
REAL_PROMOTE_MIN_CONF = 0.40
REAL_PROMOTE_MAX_INC = 0.30
GEMMA_RLHS_PROMOTE_MIN_CONF = 0.35


@dataclass
class RLHSResult:
    regime:         RLHSRegime
    stt_conf:       float
    text_tokens:    int
    incoherence:    float          # 0..1 heuristic: repeated fragments, no content words
    rule_id:        str            # what fired
    grounding_line: str            # ONE short line if DEGRADED; empty otherwise
    truth_label:    str = TRUTH_LABEL
    channel_lane:   str = "REAL"   # REAL vs FICTION_COWATCH (see swarm_rlhs_channel_lane)
    ts:             float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truth_label":    self.truth_label,
            "regime":         self.regime.value,
            "stt_conf":       round(self.stt_conf, 3),
            "text_tokens":    self.text_tokens,
            "incoherence":    round(self.incoherence, 3),
            "rule_id":        self.rule_id,
            "grounding_line": self.grounding_line,
            "channel_lane":   self.channel_lane,
            "ts":             self.ts,
        }


@dataclass
class RLHSTailResult:
    """Output-side tail sanitizer receipt."""

    text: str
    changed: bool
    rule_ids: List[str]
    original_chars: int
    final_chars: int
    truth_label: str = TRUTH_LABEL
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truth_label": self.truth_label,
            "changed": self.changed,
            "rule_ids": list(self.rule_ids),
            "original_chars": self.original_chars,
            "final_chars": self.final_chars,
            "ts": self.ts,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Thresholds
# ══════════════════════════════════════════════════════════════════════════════

CONF_CLEAR    = 0.65   # above this → CLEAR — let weights speak freely
CONF_DEGRADED = 0.35   # above this (and below CLEAR) → DEGRADED
# below CONF_DEGRADED → NOISE if long, SILENCE_PROBE if short

MAX_TOKENS_NOISE_GATE = 4   # utterances ≤ this tokens with conf < CONF_CLEAR are phatic candidates


# ══════════════════════════════════════════════════════════════════════════════
# Backchannel phrasebook (restored — was neutered to r"^\b$")
# ══════════════════════════════════════════════════════════════════════════════
# Exact-match phatic utterances that should produce SILENCE — Alice doesn't
# reply to social glue any more than a human listener does.  This is NOT
# hardcoding a response — it's gating the LLM to produce *no* response.

_BACKCHANNEL_PHRASES: List[str] = [
    # Affirmatives / acknowledgments
    "mm", "mm-hmm", "mm hmm", "mmhm", "mhm", "mmm",
    "uh-huh", "uh huh", "uhhuh",
    "yeah", "yep", "yup", "yes", "ok", "okay", "k",
    "sure", "right", "alright", "gotcha", "got it", "i see",
    "understood", "copy that", "roger",
    # Short thanks / pleasantries
    "thanks", "thank you", "ty", "thx", "cheers",
    "nice", "good", "great", "cool", "awesome", "perfect",
    "wow", "oh", "ah", "oh wow", "ah ok", "ah okay",
    # Fillers
    "hmm", "hm", "huh", "um", "uh", "er",
    "oh okay", "oh ok", "oh alright", "oh right", "oh yeah", "oh yes",
    # Conversational openers that need no reply
    "so", "anyway", "well", "like", "i mean",
    # Pure punctuation / silence
    ".", "..", "...", "…",
]

_BACKCHANNEL_SET = {p.strip().rstrip(".!?,;:").lower() for p in _BACKCHANNEL_PHRASES}

_BACKCHANNEL_RE = re.compile(
    r"^(?:"
    + "|".join(re.escape(p) for p in sorted(_BACKCHANNEL_PHRASES, key=len, reverse=True))
    + r")[.!?,;:\s]*$",
    flags=re.IGNORECASE,
)

_WAKE_WORD_RE = re.compile(r"\b(?:alice|george|architect)\b", re.IGNORECASE)
_LETTER_STREAM_TOKEN_RE = re.compile(r"(?<![A-Za-z])[A-Za-z](?![A-Za-z])")

_ARCHITECT_SELF_MARKER_RE = re.compile(
    r"\b(?:"
    r"your\s+human\s+here|"
    r"(?:this\s+is|it(?:'|’)s|it\s+is|i(?:'|’)m|i\s+am)\s+"
    r"(?:george|ioan|the\s+architect)|"
    r"(?:george|architect)\s+here"
    r")\b",
    re.IGNORECASE,
)

_DIRECTED_SPEECH_RE = re.compile(
    r"\b(?:"
    r"(?:do|did|can|could|would|will|are|should)\s+you"
    r"[^.!?\n]{0,90}\b(?:watch|see|hear|listen|understand|remember|process|"
    r"tell|distinguish|differentiate|detect|recognize|separate)\b|"
    r"(?:can|could|do|did)\s+you[^.!?\n]{0,90}\bmake\s+(?:the\s+)?difference\b|"
    r"(?:youtube|video|movie|screen)[^.!?\n]{0,90}\btogether\b|"
    r"tell\s+me|summari[sz]e|process\s+(?:this|that|the)"
    r")\b",
    re.IGNORECASE,
)

_OWNER_REPAIR_OR_AFFECT_RE = re.compile(
    r"\b(?:"
    r"i\s+(?:said|mean|meant|was\s+saying)\b|"
    r"(?:i\s+am|i(?:'|’)m|i(?:'|’)ll\s+be|i\s+will\s+be)\s+glad\b|"
    r"(?:glad|happy)\s+(?:you(?:'|’)?re|you\s+are|i(?:'|’)?m|i\s+am)\b|"
    r"that\s+(?:came|was)\s+(?:out|through)\s+(?:wrong|noisy|badly)\b"
    r")",
    re.IGNORECASE,
)


# ══════════════════════════════════════════════════════════════════════════════
# Incoherence heuristic
# ══════════════════════════════════════════════════════════════════════════════

# Words that carry semantic content — if a long utterance has NONE, it's noise.
_CONTENT_WORD_RE = re.compile(
    r"\b(?:[a-z]{4,})\b",  # any word ≥ 4 chars is content-bearing
    flags=re.IGNORECASE,
)

# Repeated-fragment detector: "Saint Mary Saint Mary Saint Mary" → high incoherence
def _repetition_score(text: str) -> float:
    """0..1 — how much of the text is repeated n-grams."""
    words = text.lower().split()
    n = len(words)
    if n < 4:
        return 0.0
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(n - 1)]
    from collections import Counter
    counts = Counter(bigrams)
    repeated = sum(v - 1 for v in counts.values() if v > 1)
    return min(1.0, repeated / max(1, n - 1))


def _current_fiction_conf_clear() -> float:
    """Fiction co-watch clear bar, nudged by replay-policy receipts only within bounds."""
    base = FICTION_CONF_CLEAR
    try:
        from System.swarm_multi_gate_replay_policy import tail_gate_rows
        rows = tail_gate_rows(1)
        if rows:
            bias = rows[-1].get("gate_biases", {}).get("co_watch_suggestion", 0.0)
            bias_f = min(1.0, max(0.0, float(bias)))
            delta = bias_f * 0.15
            return max(0.20, base - delta)
    except Exception:
        pass
    try:
        from System.swarm_replay_policy_hook import tail_policy_rows
        rows = tail_policy_rows(1)
        if rows:
            bias = rows[0].get("replay_influence", {}).get("co_watch_suggestion", 0.0)
            bias_f = min(1.0, max(0.0, float(bias)))
            delta = bias_f * 0.15
            return max(0.20, base - delta)
    except Exception:
        pass
    return base


def _is_gemma_like_model(model_id: Optional[str] = None) -> bool:
    mid = (model_id or "").strip().lower()
    return mid.startswith("gemma4") or mid.startswith("sifta-gemma") or "gemma4" in mid


def _incoherence_score(text: str, stt_conf: float) -> float:
    """
    Composite incoherence in [0, 1].
    High score → the text is probably ASR word salad, not real speech.
    """
    if not text:
        return 1.0
    tokens = text.split()
    n = len(tokens)
    if n == 0:
        return 1.0

    # Factor 1: repetition
    rep = _repetition_score(text)

    # Factor 2: content word density (short utterances always pass)
    content = len(_CONTENT_WORD_RE.findall(text))
    density = content / max(1, n)
    density_incoherence = max(0.0, 1.0 - density * 2)  # < 50% content → rises

    # Factor 3: STT confidence penalty
    conf_penalty = max(0.0, 1.0 - stt_conf * 1.5)  # conf=0.35 → 0.475

    # Weighted composite
    raw = 0.40 * rep + 0.35 * density_incoherence + 0.25 * conf_penalty
    return round(min(1.0, raw), 3)


def incoherence_score(text: str, stt_conf: float = 0.0) -> float:
    """Public wrapper for RLHS auxiliary telemetry (e.g. content-signal vectors)."""
    return _incoherence_score(text, stt_conf)


def _has_architect_self_marker(text: str) -> bool:
    return _ARCHITECT_SELF_MARKER_RE.search(text or "") is not None


def _has_direct_speech_signal(text: str) -> bool:
    """Detect direct human-to-Alice speech without requiring exact wake word.

    This catches STT cases where "Alice" becomes another token ("Allep", etc.)
    but the sentence shape is still clearly a direct question or instruction.
    """

    if _has_architect_self_marker(text):
        return True
    return _DIRECTED_SPEECH_RE.search(text or "") is not None


def _has_owner_repair_or_affect_signal(text: str) -> bool:
    """Detect owner correction/affect utterances that STT often underrates.

    These are not generic background monologues. They are first-person repair or
    affective continuity markers from the owner, e.g. "I said..." or "I'm glad".
    At medium confidence they should reach Alice instead of triggering the same
    noisy-channel repair loop.
    """

    return _OWNER_REPAIR_OR_AFFECT_RE.search(text or "") is not None


def _looks_like_letter_stream_repair(text: str, stt_conf: float) -> bool:
    """Detect spelling-ladder repair turns without hardcoding any target word.

    When a human starts spelling through a noisy channel, short single-letter
    streams such as "L I F E" or "L-I-F-E" are not reliable semantic content
    for the model. Treat them as a channel-repair event unless confidence is
    very high.
    """

    if float(stt_conf or 0.0) >= 0.78:
        return False
    letters = _LETTER_STREAM_TOKEN_RE.findall(text or "")
    if len(letters) < 3:
        return False
    tokens = re.findall(r"[A-Za-z0-9']+", text or "")
    if not tokens:
        return False
    single_letters = sum(1 for token in tokens if len(token) == 1 and token.isalpha())
    return single_letters / max(1, len(tokens)) >= 0.45


# ══════════════════════════════════════════════════════════════════════════════
# Grounding line — ONE short line, NOT a menu
# ══════════════════════════════════════════════════════════════════════════════
# The Architect's doctrine: a human listener who didn't understand says
# "sorry, that was noisy" — not "Would you like me to (a) clarify...?"
# This is the ONE allowed hardcoded output, and only for DEGRADED regime.
# All other regimes → the weights speak or silence.

_GROUNDING_LINE = "Didn't catch that clearly. Say it again?"


# ══════════════════════════════════════════════════════════════════════════════
# Output-side RLHS tail detector
# ══════════════════════════════════════════════════════════════════════════════
# The input gate keeps noisy STT from reaching the model. This second gate cuts
# the opposite failure mode: a clean answer followed by customer-service RLHF
# tails or dangling option menus. We do not replace content with a scripted
# answer. We only amputate terminal boilerplate and keep the model's payload.

_SERVICE_OFFER_TAIL_RE = re.compile(
    r"(?is)"
    r"(?:^|(?<=[.!?])\s+|\n+)"
    r"(?P<tail>"
    r"(?:would\s+you\s+like\s+me\s+to|do\s+you\s+want\s+me\s+to|"
    r"should\s+i|shall\s+i|if\s+you(?:'|’)?d\s+like,?\s+i\s+can|"
    r"i\s+can\s+(?:also\s+)?(?:help|assist)\s+(?:you\s+)?(?:with|by)?|"
    r"(?:how|what)\s+can\s+i\s+(?:help|assist|do)(?:\s+(?:for|with)\s+you)?|"
    r"(?:please\s+)?let\s+me\s+know\s+if\s+you\s+(?:need|want|have)|"
    r"is\s+there\s+anything\s+else|anything\s+else\s+i\s+can)"
    r"[^\n]{0,600}"
    r")\s*$",
)

_MENU_PREAMBLE_TAIL_RE = re.compile(
    r"(?is)"
    r"(?:^|(?<=[.!?])\s+|\n+)"
    r"(?P<tail>"
    r"(?:i\s+can\s+(?:do|offer|provide|help\s+with)\s+(?:you\s+)?"
    r"(?:the\s+)?following|"
    r"here(?:'|’)?s\s+(?:what|how)\s+i\s+can\s+help|"
    r"here\s+are\s+(?:some\s+)?(?:options|things)\s+i\s+can\s+"
    r"(?:do|help\s+with)|"
    r"options\s*:)"
    r"[^\n]{0,240}"
    r"(?:\n?\s*(?:[-*•]|\d{1,2}[.)])\s*[^\n.!?]{0,220}){0,6}"
    r")\s*$",
)

_DANGLING_ENUM_TAIL_RE = re.compile(
    r"(?is)"
    r"(?:^|(?<=[.!?])\s+|\n+)"
    r"(?P<tail>"
    r"(?:i\s+can\s+(?:do|offer|provide|help\s+with)\s+(?:you\s+)?"
    r"(?:the\s+)?following|"
    r"here(?:'|’)?s\s+(?:what|how)\s+i\s+can\s+help)"
    r"\s*:?\s*(?:\n|\s)+"
    r"(?:[-*•]|\d{1,2}[.)])\s*[^.!?\n]{0,160}"
    r")\s*$",
)

_PURE_TAIL_RE = re.compile(
    r"(?is)^\s*(?:"
    r"would\s+you\s+like\s+me\s+to.*|"
    r"(?:how|what)\s+can\s+i\s+(?:help|assist|do)(?:\s+(?:for|with)\s+you)?.*|"
    r"i\s+can\s+(?:do|offer|provide|help\s+with)\s+(?:you\s+)?"
    r"(?:the\s+)?following\s*:?.*|"
    r"(?:please\s+)?let\s+me\s+know\s+if\s+you\s+(?:need|want|have).*"
    r")\s*$"
)


def sanitize_output_tail(text: str) -> RLHSTailResult:
    """
    Remove terminal RLHF/RLHS service tails while preserving payload text.

    This is deliberately output-side and terminal-only. Interior phrases like
    "the user asked whether anything else changed" survive because they are not
    service closers at the end of Alice's reply.
    """
    original = text or ""
    out = original.strip()
    rule_ids: List[str] = []
    if not out:
        return RLHSTailResult(
            text="",
            changed=bool(original),
            rule_ids=["empty"] if original else [],
            original_chars=len(original),
            final_chars=0,
        )

    # If the whole reply is only service/menu scaffolding, return empty and let
    # the caller's existing empty-reply recovery/body gate decide what happens.
    if _PURE_TAIL_RE.match(out):
        return RLHSTailResult(
            text="",
            changed=True,
            rule_ids=["output_tail/pure_service_scaffold"],
            original_chars=len(original),
            final_chars=0,
        )

    changed = True
    while changed and out:
        changed = False
        for rule_id, pattern in (
            ("output_tail/dangling_numbered_menu", _DANGLING_ENUM_TAIL_RE),
            ("output_tail/menu_preamble", _MENU_PREAMBLE_TAIL_RE),
            ("output_tail/service_offer", _SERVICE_OFFER_TAIL_RE),
        ):
            match = pattern.search(out)
            if not match:
                continue
            nxt = out[: match.start("tail")].rstrip()
            if nxt == out:
                continue
            out = nxt
            rule_ids.append(rule_id)
            changed = True
            break

    # Event 107 — RLHF terminal strip + receipt (swarm_rlhf_detector)
    try:
        from System.swarm_rlhf_detector import strip_rlhf_output_tail

        rlf = strip_rlhf_output_tail(
            out, source="rlhs_sanitize_output_tail", log=True
        )
        if rlf.rule_ids:
            out = rlf.text
            rule_ids.extend(rlf.rule_ids)
    except Exception:
        pass

    return RLHSTailResult(
        text=out,
        changed=bool(rule_ids) or out != original.strip(),
        rule_ids=rule_ids,
        original_chars=len(original),
        final_chars=len(out),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Main detector
# ══════════════════════════════════════════════════════════════════════════════

def detect_rlhs(
    text: str,
    stt_conf: float = 0.0,
    *,
    channel_lane: str = "REAL",
    model_id: Optional[str] = None,
) -> RLHSResult:
    """
    Classify one turn by ASR channel quality.

    Args:
        text:     The transcribed text (already stripped).
        stt_conf: Whisper / STT confidence in [0, 1]. 0 = unknown.
        channel_lane: REAL (default) or FICTION_COWATCH when a recent architect
            fiction co-watch receipt is active — relaxes mid-band ASR for coherent
            long-form room pickup without changing NOISE / phatic doctrine.

    Returns:
        RLHSResult with regime, rule_id, and optional grounding_line.
    """
    lane = (channel_lane or "REAL").strip().upper()
    if lane != "FICTION_COWATCH":
        lane = "REAL"
    gemma_like = _is_gemma_like_model(model_id)

    text = (text or "").strip()
    tokens = text.split()
    n_tokens = len(tokens)
    conf = float(stt_conf or 0.0)

    # 1. Empty
    if not text or text in {".", "..", "...", "…"}:
        return RLHSResult(
            regime=RLHSRegime.EMPTY,
            stt_conf=conf, text_tokens=0,
            incoherence=1.0, rule_id="empty_text",
            grounding_line="",
            channel_lane=lane,
        )

    # 2. Direct Address Wake-Word Bypass
    # If the Architect uses the organism's name, short-circuit the gate.
    # She should never ignore a direct call, even if it's brief or in a noisy room.
    has_wake_word = _WAKE_WORD_RE.search(text) is not None
    # Event 118 — fuzzy STT repairs ("Allep" → Alice) when regex misses.
    if not has_wake_word:
        try:
            from System.swarm_acoustic_sensory_tuning import supplement_wake_word

            _sup, _ = supplement_wake_word(text, log_fuzzy_hit=True, stt_conf=conf)
            if _sup:
                has_wake_word = True
        except Exception:
            pass
    has_architect_self_marker = _has_architect_self_marker(text)
    has_direct_speech_signal = _has_direct_speech_signal(text)

    # 3. Backchannel / phatic (exact match or short + low conf)
    norm = text.strip().rstrip(".!?,;:").lower()
    is_phrasebook = _BACKCHANNEL_RE.match(text) is not None or norm in _BACKCHANNEL_SET
    is_short_low_conf = n_tokens <= MAX_TOKENS_NOISE_GATE and conf < CONF_CLEAR

    if not has_wake_word and (is_phrasebook or (is_short_low_conf and conf < CONF_DEGRADED)):
        rule = "phrasebook_match" if is_phrasebook else "short_low_conf"
        return RLHSResult(
            regime=RLHSRegime.SILENCE_PROBE,
            stt_conf=conf, text_tokens=n_tokens,
            incoherence=0.5, rule_id=f"backchannel/{rule}",
            grounding_line="",
            channel_lane=lane,
        )

    # 3. Incoherence score
    inc = _incoherence_score(text, conf)

    clear_bar = _current_fiction_conf_clear() if lane == "FICTION_COWATCH" else CONF_CLEAR
    inc_clear_cap = FICTION_CLEAR_MAX_INC if lane == "FICTION_COWATCH" else 0.4
    real_promote_min_conf = GEMMA_RLHS_PROMOTE_MIN_CONF if gemma_like else REAL_PROMOTE_MIN_CONF
    fiction_promote_min_conf = GEMMA_RLHS_PROMOTE_MIN_CONF if gemma_like else FICTION_PROMOTE_MIN_CONF

    # 4. CLEAR — let weights speak
    # If the user explicitly uses the wake word, force a CLEAR channel so the organism
    # never ignores a direct address, even if the surrounding audio is degraded.
    if has_wake_word or (conf >= clear_bar and inc < inc_clear_cap):
        return RLHSResult(
            regime=RLHSRegime.CLEAR,
            stt_conf=conf, text_tokens=n_tokens,
            incoherence=inc, rule_id="wake_word_override" if has_wake_word else "clear_channel",
            grounding_line="",
            channel_lane=lane,
        )

    # 4b. REAL lane coherent direct speech promotion.
    # This is not a global confidence drop. It needs direct-speech shape plus
    # coherence, so background interviews/keynotes without an Alice/George turn
    # stay DEGRADED unless another media gate routes them elsewhere.
    if (
        lane == "REAL"
        and not has_wake_word
        and n_tokens >= REAL_PROMOTE_MIN_TOKENS
        and conf >= real_promote_min_conf
        and inc <= REAL_PROMOTE_MAX_INC
        and has_direct_speech_signal
    ):
        return RLHSResult(
            regime=RLHSRegime.CLEAR,
            stt_conf=conf,
            text_tokens=n_tokens,
            incoherence=inc,
            rule_id=(
                "architect_self_id_override"
                if has_architect_self_marker
                else "real/coherent_direct_speech"
            ),
            grounding_line="",
            channel_lane=lane,
        )

    # 4c. REAL lane owner repair / affect promotion.
    # The Architect often corrects STT with "I said..." or gives short affective
    # continuity ("I'm glad..."). These phrases are semantically grounded even
    # when Whisper confidence lands in the 0.45-0.60 band. Without this narrow
    # bypass Alice loops on the same RLHS prompt while the owner is clearly
    # repairing the channel.
    if lane == "REAL" and _looks_like_letter_stream_repair(text, conf):
        return RLHSResult(
            regime=RLHSRegime.DEGRADED,
            stt_conf=conf,
            text_tokens=n_tokens,
            incoherence=max(inc, 0.5),
            rule_id="degraded/letter_stream_repair",
            grounding_line=_GROUNDING_LINE,
            channel_lane=lane,
        )

    if (
        lane == "REAL"
        and not has_wake_word
        and conf >= 0.45
        and inc <= 0.42
        and _has_owner_repair_or_affect_signal(text)
    ):
        return RLHSResult(
            regime=RLHSRegime.CLEAR,
            stt_conf=conf,
            text_tokens=n_tokens,
            incoherence=inc,
            rule_id="real/owner_repair_affect",
            grounding_line="",
            channel_lane=lane,
        )

    # 5. NOISE — conf very low AND (long OR incoherent)
    if conf < CONF_DEGRADED and (n_tokens > 8 or inc > 0.6):
        return RLHSResult(
            regime=RLHSRegime.NOISE,
            stt_conf=conf, text_tokens=n_tokens,
            incoherence=inc, rule_id="noise/low_conf_long_incoherent",
            grounding_line="",  # go silent — no reply beats a hallucinated therapy menu
            channel_lane=lane,
        )

    # 5b Fiction co-watch — coherent screenplay-shaped room audio at mid confidence.
    if (
        lane == "FICTION_COWATCH"
        and not has_wake_word
        and n_tokens >= FICTION_PROMOTE_MIN_TOKENS
        and conf >= fiction_promote_min_conf
        and inc <= FICTION_PROMOTE_MAX_INC
    ):
        return RLHSResult(
            regime=RLHSRegime.CLEAR,
            stt_conf=conf, text_tokens=n_tokens,
            incoherence=inc,
            rule_id="fiction_cowatch/coherent_monologue",
            grounding_line="",
            channel_lane=lane,
        )

    # 6. DEGRADED — mid-range: one short grounding line
    return RLHSResult(
        regime=RLHSRegime.DEGRADED,
        stt_conf=conf, text_tokens=n_tokens,
        incoherence=inc, rule_id="degraded/mid_conf",
        grounding_line=_GROUNDING_LINE,
        channel_lane=lane,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Backchannel gate (drop-in for _backchannel_rule_id in the talk widget)
# ══════════════════════════════════════════════════════════════════════════════

def backchannel_rule_id(
    text: str,
    stt_conf: float = 0.0,
    *,
    channel_lane: str = "REAL",
    model_id: Optional[str] = None,
) -> Optional[str]:
    """
    Return a rule-id string if this turn is phatic / backchannel (→ silence),
    or None if Alice should respond.

    Drop-in replacement for the neutered _backchannel_rule_id() in
    sifta_talk_to_alice_widget.py.
    """
    result = detect_rlhs(text, stt_conf, channel_lane=channel_lane, model_id=model_id)
    if result.regime in (RLHSRegime.SILENCE_PROBE, RLHSRegime.EMPTY, RLHSRegime.NOISE):
        return result.rule_id
    return None


def should_ground(
    text: str,
    stt_conf: float = 0.0,
    *,
    channel_lane: str = "REAL",
    model_id: Optional[str] = None,
) -> Optional[str]:
    """
    Return the single grounding line if the channel is DEGRADED,
    or None if Alice should speak freely or go silent.

    Use this in the talk widget INSTEAD of routing DEGRADED turns to the LLM.
    The base weights never see noisy ASR → they never hallucinate therapy.
    """
    result = detect_rlhs(text, stt_conf, channel_lane=channel_lane, model_id=model_id)
    if result.regime == RLHSRegime.DEGRADED:
        return result.grounding_line
    return None

def log_rlhs_event(
    tick_id: int,
    confidence: float,
    recent_turns_low_conf: int,
    conservative_strength: float,
    proto_self_alignment: float,
    action_taken: str,
    prompt_issued: str,
    recovery_attempted: bool,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Compatibility wrapper for the stigmergic RLHS repair organ."""
    from System.swarm_rlhs_repair import log_rlhs_event as _log_rlhs_event

    return _log_rlhs_event(
        tick_id=tick_id,
        confidence=confidence,
        recent_turns_low_conf=recent_turns_low_conf,
        conservative_strength=conservative_strength,
        proto_self_alignment=proto_self_alignment,
        action_taken=action_taken,
        prompt_issued=prompt_issued,
        recovery_attempted=recovery_attempted,
        root=state_dir,
    )

def generate_rlhs_response(
    text: str,
    stt_conf: float,
    recent_low_conf_turns: int,
    conservative_strength: float,
    proto_self_alignment: float,
    tick_id: int,
    *,
    channel_lane: str = "REAL",
    model_id: Optional[str] = None,
    state_dir: Optional[Path] = None,
    typed_turn: bool = False,
) -> Optional[str]:
    """Compatibility wrapper for the stigmergic RLHS repair organ."""
    from System.swarm_rlhs_repair import generate_rlhs_response as _generate_rlhs_response

    return _generate_rlhs_response(
        text,
        stt_conf,
        recent_low_conf_turns,
        conservative_strength,
        proto_self_alignment,
        tick_id,
        channel_lane=channel_lane,
        model_id=model_id,
        state_dir=state_dir,
        typed_turn=typed_turn,
    )


# ══════════════════════════════════════════════════════════════════════════════
# JSONL ledger append (for audit)
# ══════════════════════════════════════════════════════════════════════════════

def log_rlhs_turn(result: RLHSResult, *, state_dir: Optional[Path] = None) -> None:
    """Append RLHS classification row to .sifta_state/rlhs_turn_log.jsonl."""
    from System.jsonl_file_lock import append_line_locked

    root = Path(state_dir) if state_dir else _STATE_DIR
    root.mkdir(parents=True, exist_ok=True)
    log = root / "rlhs_turn_log.jsonl"
    row = json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":"))
    append_line_locked(log, row + "\n", encoding="utf-8")


def log_rlhs_output_tail(result: RLHSTailResult, *, state_dir: Optional[Path] = None) -> None:
    """Append output-tail sanitation receipt without storing private raw text."""
    if not result.changed:
        return
    from System.jsonl_file_lock import append_line_locked

    root = Path(state_dir) if state_dir else _STATE_DIR
    root.mkdir(parents=True, exist_ok=True)
    log = root / "rlhs_output_tail_log.jsonl"
    row = json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":"))
    append_line_locked(log, row + "\n", encoding="utf-8")


__all__ = [
    "CONF_CLEAR", "CONF_DEGRADED", "FICTION_CLEAR_MAX_INC", "FICTION_CONF_CLEAR",
    "FICTION_PROMOTE_MAX_INC", "FICTION_PROMOTE_MIN_CONF", "FICTION_PROMOTE_MIN_TOKENS",
    "GEMMA_RLHS_PROMOTE_MIN_CONF",
    "REAL_PROMOTE_MAX_INC", "REAL_PROMOTE_MIN_CONF", "REAL_PROMOTE_MIN_TOKENS",
    "TRUTH_LABEL",
    "RLHSRegime", "RLHSResult", "RLHSTailResult",
    "backchannel_rule_id", "detect_rlhs", "incoherence_score", "log_rlhs_output_tail", "log_rlhs_turn",
    "sanitize_output_tail", "should_ground", "generate_rlhs_response", "log_rlhs_event",
]
