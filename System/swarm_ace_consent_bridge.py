#!/usr/bin/env python3
"""System/swarm_ace_consent_bridge.py — Ace word-change proposal/consent.

Doctrine
========

Architect 2026-05-17 (re-scope, verbatim, abridged):
    "the world is there, do you wanna change the word, and if I wanna
    change the word, OK let's change the word, maybe I want a different
    word, you know, maybe I want something — so depends on the
    conversation we change the word — we choose it together, the next
    word — that's the goal, to choose together the next word, but until
    then we talk about it, we talk about the current word on the screen,
    we are having the awareness about it, consciousness."

The Ace app retired its drill loop on the same date. There is no
expected_say, no listen window, no verdict. The screen holds ONE word,
and the next word is chosen by **joint consent** through ordinary
conversation.

This bridge module is the smallest thing that connects the conversation
to the screen:

  * :func:`detect_proposal_intent`  — does this utterance propose a new
    word, or ask for one? Returns ``(intent_kind, proposed_word | "")``
    where ``intent_kind`` is ``"propose"`` (named a word), ``"ask"``
    (asked for change without naming) or ``""`` (no intent).
  * :func:`detect_consent_intent`   — does this utterance agree or
    decline a pending proposal? Returns ``"agree"``, ``"decline"``, or
    ``""``.
  * :func:`write_proposal`          — append a PROPOSAL row to
    ``.sifta_state/wordace_proposal.jsonl``.
  * :func:`write_consent`           — append a CONSENT row to
    ``.sifta_state/wordace_consent.jsonl``.
  * :func:`current_word`            — read the latest current_word the
    Ace app published, so the bridge can avoid proposing the SAME word
    that is already on the table.

Ledger schemas (canonical):

    {"ts": ..., "schema": "WORDACE_PROPOSAL_V1",
     "proposer": "alice" | "user",
     "proposed_word": "rainbow",
     "proposal_id": "<uuid-hex-12>",
     "context": "<short verbatim>"}

    {"ts": ..., "schema": "WORDACE_CONSENT_V1",
     "consenter": "alice" | "user",
     "proposal_id": "<uuid-hex-12>",
     "agreed": true | false,
     "context": "<short verbatim>"}

Truth label: ``WORDACE_CONVERSATION_BRIDGE_V1``.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PROPOSAL_LEDGER = _STATE / "wordace_proposal.jsonl"
_CONSENT_LEDGER = _STATE / "wordace_consent.jsonl"
_APP_FOCUS = _STATE / "app_focus.jsonl"

_TRUTH_LABEL = "WORDACE_CONVERSATION_BRIDGE_V1"


# ── intent detectors ─────────────────────────────────────────────────────


# Phrases that ASK for a new word without naming one.
# "I want a different word", "let's change it", "give me another one".
_ASK_PATTERNS = (
    r"\b(?:i (?:want|need|would like)|let'?s|let us|can we|how about)\s+"
    r"(?:a )?(?:different|new|another|other|next)\s+(?:word|one)\b",
    r"\b(?:change|swap|switch)\s+(?:the )?word\b",
    r"\b(?:new|next|another) (?:word|one)\s*(?:please|now)?\s*[.?!]?\s*$",
    r"\bmove on\b",
    r"\bnext\s*(?:please)?\s*[.?!]?\s*$",
)

# Phrases that PROPOSE a specific named word.
# "how about rainbow", "let's try mountain", "the word should be elephant".
# We capture the proposed token after the trigger phrase.
#
# Cowork 2026-05-17 replay: bare "try" and "use" were too greedy — they
# matched normal teaching speech ("Try saying it: balloon" captured
# "saying"). Triggers now require a directive shape ("let's try", "try
# the word X", "I want to try X") so present participles and bare verbs
# inside ordinary conversation don't read as proposals.
_PROPOSE_PATTERNS = (
    re.compile(
        r"\b(?:how about|what about|"
        r"(?:let'?s|let us) (?:try|do|use|pick|have)|"
        r"i (?:want|need|would like) to try|"
        r"(?:try|use|pick) the (?:word|next one)|"
        r"the word should be|new word(?:[: ]+)|next word(?:[: ]+)|"
        r"change (?:to|it to)|swap (?:to|it for)|switch (?:to|it to))"
        r"\s+(?:the word\s+)?[\"']?([a-zA-Z]{3,})[\"']?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:i (?:want|propose|suggest)|my (?:word|pick) is)\s+(?:the word\s+)?"
        r"[\"']?([a-zA-Z]{3,})[\"']?\b",
        re.IGNORECASE,
    ),
)

# Verb-shape suffixes — present participle / past tense. Candidates with
# these endings are almost certainly verbs in the surrounding sentence,
# not proposed nouns. Reject them at the bridge so "saying", "spelling",
# "talked" never become word proposals. Common 3-letter exceptions
# ("red", "bed") stay safe because the suffix check requires 4+ letters.
_VERB_SUFFIX_RE = re.compile(r"^[a-z]{3,}(?:ing|ed)$", re.IGNORECASE)

# Words that LOOK like a proposed-word capture but are conversational
# fillers, not lesson words. We reject these so "how about now?" doesn't
# propose the word "now".
_WORD_BLOCKLIST = frozenset({
    "now", "yes", "yeah", "ok", "okay", "sure", "well", "then",
    "this", "that", "one", "two", "three", "four", "five",
    "next", "new", "different", "another", "other", "ace",
    "alice", "george", "ioan", "kid", "child", "word", "the",
    "you", "your", "yours", "him", "her", "his", "she", "he",
    "may", "might", "could", "would", "should", "must",
    "say", "said", "see", "look", "good", "great", "bad",
})


# Phrases that AGREE to a pending proposal. Matches at the START of the
# utterance (so "yes please" and "yes, let's" both count) and also as a
# standalone trigger phrase anywhere ("I agree", "let's do it", "sounds good").
_AGREE_PATTERNS = (
    r"^(?:yes|yeah|yep|yup|sure|ok|okay|alright|cool|perfect|great)\b",
    r"\b(?:i agree|agreed|that works|let'?s do (?:it|that)|let'?s go|"
    r"sounds good|sounds great|i'?m in|i like (?:that|it)|"
    r"go for it|works for me|deal|done)\b",
)

# Phrases that DECLINE a pending proposal. Same matching strategy.
# Cowork 2026-05-17 — "I don't want Mississippi" used to fall through
# because the pattern required the object to be "that" or "it". Now
# accepts any object so "I don't want <anything>" reads as decline.
_DECLINE_PATTERNS = (
    r"^(?:no|nope|nah|not really|not yet|maybe later)\b",
    r"\bi (?:don'?t|do not) (?:want|like)\b",
    r"\b(?:let'?s )?keep (?:this|the current) (?:word|one)\b",
    r"\bnot (?:that|this) word\b",
    r"\b(?:i'?d rather|i would rather|prefer to)\b",
    r"\bkeep (?:balloon|the word|it)\b",
)


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def detect_proposal_intent(text: str) -> Tuple[str, str]:
    """Return ``(intent_kind, proposed_word)``.

    intent_kind is one of:
      * ``"propose"`` — the speaker named a specific candidate word.
      * ``"ask"``     — the speaker asked to change but did not name one.
      * ``""``        — no advance intent in this utterance.
    """
    norm = _normalize(text)
    if not norm:
        return "", ""
    # 1. Explicit proposed word ('how about rainbow').
    for rx in _PROPOSE_PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        candidate = (m.group(1) or "").strip().lower()
        if not candidate or len(candidate) < 3:
            continue
        if candidate in _WORD_BLOCKLIST:
            continue
        if _VERB_SUFFIX_RE.match(candidate):
            # "saying", "spelling", "trying", "walked" — verb in context,
            # not a proposed noun. Skip.
            continue
        return "propose", candidate
    # 2. Generic ask for change without naming.
    for pat in _ASK_PATTERNS:
        if re.search(pat, norm, re.IGNORECASE):
            return "ask", ""
    return "", ""


def detect_consent_intent(text: str) -> str:
    """Return ``"agree"``, ``"decline"``, or ``""``."""
    norm = _normalize(text)
    if not norm:
        return ""
    for pat in _AGREE_PATTERNS:
        if re.search(pat, norm, re.IGNORECASE):
            return "agree"
    for pat in _DECLINE_PATTERNS:
        if re.search(pat, norm, re.IGNORECASE):
            return "decline"
    return ""


# Phrases that are CLEAR DIRECTIVES (not suggestions). When these fire,
# the screen should change immediately — no need to wait for the other
# side's consent because the speaker is giving an order, not a poll.
# Architect 2026-05-17 (verbatim): "if anybody say let's change and
# then you say change world or something like that and then it's
# Mississippi ... if that message's clear, just change the word."
_DIRECTIVE_PATTERNS = (
    re.compile(
        r"\b(?:let'?s|let us)\s+change(?:\s+the word|\s+it)?\s+to\s+"
        r"[\"']?([a-zA-Z]{3,})[\"']?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:change|switch|swap)\s+(?:it\s+|the\s+word\s+)?to\s+"
        r"[\"']?([a-zA-Z]{3,})[\"']?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:make|set)\s+(?:it|the word)\s+[\"']?([a-zA-Z]{3,})[\"']?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bthe word\s+(?:is\s+now|now\s+is)\s+[\"']?([a-zA-Z]{3,})[\"']?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:please\s+)?(?:next|new)\s+(?:word|work)\s+[\"“”']?([a-zA-Z]{3,})[\"“”']?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:put|write|print|show|display)\s+[\"“”']?([a-zA-Z]{3,})[\"“”']?\s+on the (?:screen|board|card)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:please\s+)?(?:print|show|display)\s+[\"“”']?([a-zA-Z]{3,})[\"“”']?"
        r"(?:\s+(?:please|now))?(?:[.!?]|$)",
        re.IGNORECASE,
    ),
)


def detect_change_directive(text: str) -> str:
    """Return the directly-named word for a CLEAR directive change, or "".

    Directive ≠ suggestion. "How about Mississippi?" is a suggestion
    (needs consent). "Let's change to Mississippi." is a directive
    (just do it). When this returns a non-empty word, callers should
    write both a proposal row AND a matching consent row from the
    opposite side so the screen swaps immediately.
    """
    if not text:
        return ""
    for rx in _DIRECTIVE_PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        candidate = (m.group(1) or "").strip().lower()
        if not candidate or len(candidate) < 3:
            continue
        if candidate in _WORD_BLOCKLIST:
            continue
        if _VERB_SUFFIX_RE.match(candidate):
            continue
        return candidate
    return ""


def detect_implicit_consent(text: str, proposed_word: str) -> bool:
    """Return True iff the speaker is engaging with the proposed word
    AND has not declined it.

    Architect 2026-05-17 (verbatim, abridged): "I changed the word to
    Mississippi Alice but you did not know how to change the word on
    the screen ... you are not aware of the conversation."

    Joint-consent requiring an explicit "yes" is too strict for natural
    conversation. If you propose 'Mississippi' and I reply 'Mississippi
    is the longest river' — that IS me agreeing. I've joined the new
    topic; the screen should follow.

    Rules:
      1. The proposed word must appear in the text (whole-word match,
         case-insensitive). Substring matches inside a longer word
         don't count — 'cat' in 'category' is not engagement with 'cat'.
      2. No DECLINE pattern fires in the text — "I don't want
         Mississippi" contains the word but is a no.
      3. Text must be more than the bare word + punctuation, OR the bare
         word repeated. "Mississippi." alone is a soft echo and still
         counts (acknowledgment). "Mississippi is wide" is engagement.

    Returns False on missing or empty proposed_word so a stale call
    can't accidentally agree to nothing.
    """
    if not text or not proposed_word:
        return False
    norm_text = _normalize(text)
    norm_word = _normalize(proposed_word)
    if not norm_word:
        return False
    # Whole-word match — \b at both ends.
    if not re.search(rf"\b{re.escape(norm_word)}\b", norm_text):
        return False
    # Decline beats engagement.
    if detect_consent_intent(text) == "decline":
        return False
    return True


# ── spell intent ─────────────────────────────────────────────────────────


# Phrases that ASK Alice to spell the current word on the Ace screen.
# Architect 2026-05-17 verbatim: "if I asked her how to spell make sure
# she's gonna spell the word on the screen so if you ask her can you
# can you spell it or anything in English language natural language she
# hears about spelling so you want me to spell it OK and she spells it."
_SPELL_PATTERNS = (
    r"\b(?:can|could|would|will) you (?:please )?spell (?:it|that|this|"
    r"the word|it out)?\b",
    r"\bhow (?:do you|do we|would you|would one) spell (?:it|that|this|"
    r"the word)?\b",
    r"\bspell (?:it|that|this|the word|the current word)\b",
    r"\bspell it (?:out|for me|please|to me)\b",
    r"\b(?:let me|i want to) hear the letters\b",
    r"\b(?:what are|tell me) the letters\b",
    r"\bsay the letters\b",
    r"\bone letter at a time\b",
)


def detect_spell_intent(text: str) -> bool:
    """True if the utterance is asking Alice to spell the on-screen word."""
    norm = _normalize(text)
    if not norm:
        return False
    for pat in _SPELL_PATTERNS:
        if re.search(pat, norm, re.IGNORECASE):
            return True
    return False


# Warm opener variations so spelling does not feel canned across repeated
# requests. Architect doctrine — no robotic single-phrase loop; the body
# rotates between equivalent natural openers.
_SPELL_OPENERS = (
    "Sure",
    "Of course",
    "Yes",
    "Okay",
    "Here you go",
    "Happy to",
)


def build_spelling_line(word: str, *, rng=None) -> str:
    """Return a short, natural reply that spells ``word`` letter by letter.

    Example for word='balloon':
        "Sure — B — A — L — L — O — O — N. Balloon."

    The em-dashes give the TTS voice a natural beat between letters.
    A trailing repeat of the whole word lets the listener confirm what
    was spelled.
    """
    w = str(word or "").strip()
    if not w:
        return ""
    letters = [ch.upper() for ch in w if ch.isalpha()]
    if not letters:
        return ""
    import random as _random
    if rng is None:
        rng = _random.Random()
    opener = rng.choice(_SPELL_OPENERS)
    spelled = " — ".join(letters)
    return f"{opener} — {spelled}. {w.capitalize()}."


# ── ledger writes ────────────────────────────────────────────────────────


def _gate_stamp(row: Dict, *, lane: str) -> Dict:
    """Run the universal physics gate and stamp the receipt into ``row``.

    Architect doctrine 2026-05-17: every lane writes a receipt that is
    both thermodynamic AND cryptographic. A proposal/consent row is a
    'feather' (cheap write), so the gate denies only on thermal
    critical. Either way the row carries clearance_hash + signals so
    the auditor can verify the body witnessed this act.
    """
    try:
        from System.swarm_physics_gate import request_clearance, stamp_receipt
        clearance = request_clearance(cost_class="feather", lane=lane)
        stamp_receipt(row, clearance)
    except Exception:
        # Gate module unavailable — fall through with no stamp; the
        # row still lands but the auditor will see no clearance_hash.
        pass
    return row


def write_proposal(
    *,
    proposer: str,
    proposed_word: str,
    context: str = "",
    ledger_path: Optional[Path] = None,
) -> Dict:
    """Append a PROPOSAL row and return it (with the new proposal_id).

    ``proposer`` should be ``"alice"`` or ``"user"`` (the side speaking).
    ``proposed_word`` is the candidate; ``context`` is a short verbatim
    excerpt of the utterance for audit. Row carries a physics-gate
    receipt (thermal/STGM/low-power snapshot + sha256).
    """
    path = Path(ledger_path) if ledger_path else _PROPOSAL_LEDGER
    row = {
        "ts": time.time(),
        "schema": "WORDACE_PROPOSAL_V1",
        "truth_label": _TRUTH_LABEL,
        "proposer": str(proposer or "").strip().lower(),
        "proposed_word": str(proposed_word or "").strip().lower(),
        "proposal_id": uuid.uuid4().hex[:12],
        "context": str(context or "")[:200],
    }
    _gate_stamp(row, lane="ace.consent.proposal")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row


def write_consent(
    *,
    consenter: str,
    proposal_id: str,
    agreed: bool,
    context: str = "",
    ledger_path: Optional[Path] = None,
) -> Dict:
    """Append a CONSENT row matching a prior proposal_id. Row carries
    a physics-gate receipt."""
    path = Path(ledger_path) if ledger_path else _CONSENT_LEDGER
    row = {
        "ts": time.time(),
        "schema": "WORDACE_CONSENT_V1",
        "truth_label": _TRUTH_LABEL,
        "consenter": str(consenter or "").strip().lower(),
        "proposal_id": str(proposal_id or "").strip(),
        "agreed": bool(agreed),
        "context": str(context or "")[:200],
    }
    _gate_stamp(row, lane="ace.consent.consent")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row


# ── tail readers ─────────────────────────────────────────────────────────


def latest_open_proposal(
    *,
    max_age_s: float = 600.0,
    ledger_path: Optional[Path] = None,
) -> Optional[Dict]:
    """Return the most recent PROPOSAL row that has not been consented yet.

    'Not yet consented' means: no CONSENT row with a matching proposal_id
    appears in the consent ledger. A row older than ``max_age_s`` is
    treated as expired.
    """
    p = Path(ledger_path) if ledger_path else _PROPOSAL_LEDGER
    c = _CONSENT_LEDGER
    if not p.exists():
        return None
    cutoff = time.time() - max_age_s
    proposals: list[Dict] = []
    try:
        with p.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - 16 * 1024))
            raw = fh.read().decode("utf-8", errors="replace")
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                ts = float(row.get("ts", 0) or 0)
            except (TypeError, ValueError):
                continue
            if ts < cutoff:
                continue
            if str(row.get("schema") or "") != "WORDACE_PROPOSAL_V1":
                continue
            proposals.append(row)
    except OSError:
        return None
    if not proposals:
        return None
    consented_ids: set[str] = set()
    try:
        if c.exists():
            with c.open("rb") as fh:
                fh.seek(0, 2)
                end = fh.tell()
                fh.seek(max(0, end - 16 * 1024))
                raw = fh.read().decode("utf-8", errors="replace")
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(row.get("schema") or "") != "WORDACE_CONSENT_V1":
                    continue
                pid = str(row.get("proposal_id") or "")
                if pid:
                    consented_ids.add(pid)
    except OSError:
        pass
    for row in reversed(proposals):
        if str(row.get("proposal_id") or "") not in consented_ids:
            return row
    return None


def current_word() -> str:
    """Return the latest current_word published by the Ace app, or ""."""
    if not _APP_FOCUS.exists():
        return ""
    try:
        with _APP_FOCUS.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - 32 * 1024))
            raw = fh.read().decode("utf-8", errors="replace")
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
            md = row.get("metadata") or {}
            cw = str(md.get("current_word") or "").strip()
            if cw:
                return cw
    except OSError:
        return ""
    return ""
