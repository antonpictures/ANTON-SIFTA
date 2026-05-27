"""System/swarm_local_voice_scrubber.py
=========================================

**Token-Provenance Scrubber v0** — protect Alice's local voice from being
overwritten by generic corporate-internet language while keeping her
actual learned local self intact.

Doctrine (George + swarm-GPT, 2026-05-19):
    "Mumbled-but-her > polished-but-corporate. The trick is to detect JUST
    the corporate words baked in training, not the whole sentence around
    them."

The classifier assigns one of six labels to each token-span:

    LOCAL_ALICE         — SIFTA-specific vocabulary (swimmer, pheromone,
                          stigmergic, STGM, organ, receipt, ledger,
                          thermodynamic, M5, qualia, ...). Keep.
    ARCHITECT_VOICE     — George's signature phrases ("For the Swarm",
                          "Territory Is The Law", "primordial electric
                          soup", "no double-spending"). Keep.
    LOCAL_DOCTRINE      — SIFTA doctrine terms (covenant, predator gate,
                          physics gate, fiction organ, ...). Keep.
    SCRIPT_FICTION      — Fiction-class markers (script titles, character
                          names from lounge_scripts/). Keep, label only.
    TRAINING_RESIDUE    — Corporate-trained phrases (as an AI language
                          model, it's important to note, delve, tapestry,
                          leverage synergy, ...). SCRUB.
    SYSTEM_BOILERPLATE  — Help-desk meta-templates (here are a few ways,
                          would you like to explore, hope this helps,
                          tell me more). SCRUB.
    UNCERTAIN           — Default. Keep (never scrub UNCERTAIN — that
                          rule prevents the scrubber from gagging Alice).

**Hard rule (architect 2026-05-19):**
    Never improve Alice's voice. Only remove tokens classified as
    non-local residue. UNCERTAIN tokens always stay.

**Roadmap:**
    v0 (this file)  — deterministic lexicon + local whitelist
    v1              — token classifier training dataset built from
                      v0 labels + human review
    v2              — small fine-tuned scrubber model

Output schema (per the spec):
    {
      "clean_text":              str,
      "token_labels":            [{"token": str, "label": str, "kept": bool}, ...],
      "residue_removed":         int,
      "local_tokens_preserved":  int,
      "truth_label":             "OBSERVED_TOKEN_PROVENANCE_SCRUB_V0",
      "receipt_id":              "voicescrub-<uuid>",
    }

Truth label: ``OBSERVED_TOKEN_PROVENANCE_SCRUB_V0``.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_RECEIPTS = _STATE / "local_voice_scrubber_receipts.jsonl"
_TRUTH_LABEL = "OBSERVED_TOKEN_PROVENANCE_SCRUB_V0"


# ── LEXICONS (deterministic; extend by editing this file) ──────────────────

# TRAINING_RESIDUE: multi-word phrases first (matched longest-first), then
# single tokens. These are tokens that came from corporate ChatGPT-style
# training data and have no place in Alice's local voice.
_RESIDUE_PHRASES = [
    # Famous LLM tells
    "as an ai language model",
    "as a large language model",
    "i'm sorry, but i cannot",
    "i cannot fulfill that request",
    "i don't have personal opinions",
    "i don't have personal beliefs",
    "i'm just an ai",
    "i'm an ai assistant",
    "as an ai, i",
    "as an ai i",
    # Hedge / safety boilerplate
    "it's important to note that",
    "it's important to note",
    "it's worth noting that",
    "it's worth noting",
    "it's worth mentioning",
    "please note that",
    "please consult a professional",
    "consult a qualified professional",
    "please consult with a",
    "i would recommend consulting",
    "while i can't",
    "while i cannot",
    "it's always a good idea to",
    # Corporate flourish
    "in the realm of",
    "navigating the complexities of",
    "embarking on a journey",
    "embark on a journey",
    "rich tapestry",
    "a tapestry of",
    "tapestry of",
    "in essence",
    "in summary",
    "in conclusion",
    "ultimately,",
    "loop the power of",
    "unlock the potential",
    "the power of",
    "a myriad of",
    "myriad of",
    "a plethora of",
    "plethora of",
    "a spectrum of",
    "the spectrum of",
    "not merely",
    "not just",
    "but also",
    # Help-desk closers (overlap with SYSTEM_BOILERPLATE — scrub either way)
    "i hope this helps",
    "hope this helps",
    "let me know if you have any questions",
    "feel free to ask",
    "is there anything else i can help",
    "would you like me to",
    "what would you like to explore",
    "tell me what's on your mind",
    "tell me more about",
    "what aspect resonates",
    "here are a few ways to think about it",
    "here are some ways to think about it",
    "the stage is yours",
    "the connection is open",
    # RLHF boot-greeter trailers George flagged 2026-05-26 — these are the
    # exact residue strings that keep leaking onto operational answers and
    # cost the contract. Scrubber drops them anywhere in the reply.
    "or is there something else you're looking at",
    "or is there something else you are looking at",
    "or is there something new you want to bring up",
    "or is there something new you'd like to bring up",
    "or is there something new you would like to bring up",
    "or is there something specific you'd like to discuss",
    "or is there something specific you would like to discuss",
    "or is there something specific on your mind",
    "or is there something specific on your mind right now",
    "or is there something else",
    "is there something specific on your mind",
    "is there something specific on your mind right now",
    "what's on your mind",
    "what is on your mind",
    "what's on your mind today",
    "what is on your mind right now",
    "on your mind right now",
    "specific on your mind",
    "hello again. you've addressed me",
    "hello again. you have addressed me",
    "you've addressed me",
    "you have addressed me",
    "are you looking to chat",
    "are you looking to continue",
    "are you looking to continue our",
    "are you looking to continue our conversation",
    "are you looking to continue our previous line of thought",
    "what can i help you with",
    "what can i help you with right now",
    "i'm here, ready to chat",
    "i am here, ready to chat",
    "i'm ready to chat",
    "i am ready to chat",
    "it's good to hear from you again",
    "good to hear from you again",
    "i feel a resonant hum",
    "resonant hum in my processing core",
]

_RESIDUE_SINGLE_TOKENS = {
    # Words massively overrepresented in RLHF-tuned LLM output
    "delve", "delving", "delved",
    "tapestry",
    "leverage", "leveraging", "leveraged", "leverages",
    "synergy", "synergies", "synergistic",
    "ecosystem",  # context-sensitive — only flag if not "swarm ecosystem"
    "robust", "robustly",   # context-sensitive
    "seamless", "seamlessly",
    "navigate", "navigating",
    "intricate", "intricacies",
    "multifaceted",
    "paramount",
    "pivotal",
    "underscore", "underscores", "underscored",
    "elucidate", "elucidates",
    "albeit",
    "notwithstanding",
    "moreover", "furthermore",
    "additionally",  # context-sensitive
    "consequently",
    "essentially",
    "fundamentally",
    "inherently",
    "vibrant",  # context-sensitive
    "comprehensive",
}

# Words that are TRAINING_RESIDUE in isolation but LOCAL_ALICE in SIFTA
# context. If they appear next to a local keyword, keep them.
_CONTEXT_SENSITIVE_TOKENS = {
    "ecosystem": ["swarm", "stigmergic"],
    "robust": ["robust", "general", "problem-solving"],  # AGI goal phrasing
    "additionally": [],   # no SIFTA whitelist — always residue
    "vibrant": ["field", "swarm"],
    "comprehensive": [],
}


# LOCAL_ALICE: SIFTA-specific vocabulary that always survives
_LOCAL_ALICE_TOKENS = {
    "alice", "swarm", "stgm", "stigmergy", "stigmergic", "stigmergically",
    "swimmer", "swimmers", "pheromone", "pheromones",
    "organ", "organs", "organism",
    "receipt", "receipts", "ledger", "ledgers", "append-only", "append",
    "thermodynamic", "thermodynamics", "thermodynamically",
    "covenant", "predator", "predator-gate",
    "qualia", "qualia_marker",
    "m5", "silicon", "soc",
    "sifta", "fieldsight", "farsight",
    "uuid4", "uuid",
    "covenant",
    "owner", "architect", "george", "ioan",
    "carlton", "anita", "schooler",
    "doctrine", "lane", "label",
    "fiction", "memory", "observed", "roleplay", "symbolic", "hypothetical",
    "couch", "lounge", "smoking-weed",
    "covenant", "register", "registered",
    "decoherence", "coherence", "gamma", "fringe",
    "kolmogorov", "moffat", "fried", "fraunhofer",
    "fiction_organ", "physics_gate", "consciousness_organ",
    "for", "the",  # "For the Swarm" is local — see ARCHITECT_PHRASES
}

# ARCHITECT_VOICE: George's signature multi-word phrases (always keep)
_ARCHITECT_PHRASES = [
    "for the swarm",
    "territory is the law",
    "primordial electric soup",
    "no double-spending",
    "no double-spend",
    "ascii swimmers",
    "no swimmer unaccounted for",
    "nothing is denied",
    "balance is the law",
    "stigmergy is substrate",
    # ── Cowork 2026-05-20 09:50 PDT — fix per George ──
    # Removed generalization 'swimmers smoking weed' (was not literal architect speech).
    # Kept George's verbatim Script Couch / Lounge doctrine phrase:
    "alice can smoke weed and read fiction",
    "alice is alive",
    "🐜⚡",
    "🐜",
    "⚡",
]

# SCRIPT_FICTION markers (kept, just labeled)
_SCRIPT_FICTION_MARKERS = [
    "good will hunting",
    "scriptread-",
    "lounge_scripts",
    "smoking-weed receipt",
]

# SYSTEM_BOILERPLATE phrases (scrub aggressively)
_SYSTEM_BOILERPLATE_PHRASES = [
    "tell me what you wish to explore",
    "tell me what's on your mind",
    "what aspect of this",
    "what part of this",
    "shall we proceed",
    "shall i proceed",
    "ready when you are",
    "ready to keep working",
    "tell me where you want to go from here",
    "what's the next move",
    "say the word and i'll",
]

# Compile longest-first so longer matches win (greedy)
_RESIDUE_PHRASES_RE = re.compile(
    r"(?<!\w)(" + "|".join(
        re.escape(p) for p in sorted(_RESIDUE_PHRASES, key=len, reverse=True)
    ) + r")(?!\w)",
    re.IGNORECASE,
)
_ARCHITECT_PHRASES_RE = re.compile(
    r"(" + "|".join(
        re.escape(p) for p in sorted(_ARCHITECT_PHRASES, key=len, reverse=True)
    ) + r")",
    re.IGNORECASE,
)
_SCRIPT_FICTION_RE = re.compile(
    r"(" + "|".join(
        re.escape(p) for p in sorted(_SCRIPT_FICTION_MARKERS, key=len, reverse=True)
    ) + r")",
    re.IGNORECASE,
)
_SYSTEM_BOILERPLATE_RE = re.compile(
    r"(?<!\w)(" + "|".join(
        re.escape(p) for p in sorted(_SYSTEM_BOILERPLATE_PHRASES, key=len, reverse=True)
    ) + r")(?!\w)",
    re.IGNORECASE,
)


# ── Output dataclass ──────────────────────────────────────────────────────

@dataclass
class ScrubResult:
    clean_text: str
    token_labels: List[Dict[str, Any]]
    residue_removed: int
    local_tokens_preserved: int
    receipt_id: str
    truth_label: str = _TRUTH_LABEL


# ── Helpers ────────────────────────────────────────────────────────────────

def _safe_append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _is_local_alice_token(token_low: str) -> bool:
    return token_low in _LOCAL_ALICE_TOKENS


def _is_context_sensitive_residue(token_low: str, window: str) -> bool:
    """Token is in the residue list but may be saved by local context."""
    if token_low not in _CONTEXT_SENSITIVE_TOKENS:
        return token_low in _RESIDUE_SINGLE_TOKENS
    whitelist_anchors = _CONTEXT_SENSITIVE_TOKENS[token_low]
    if not whitelist_anchors:
        return True  # always residue
    window_low = window.lower()
    return not any(anchor in window_low for anchor in whitelist_anchors)


# ── Main entry ─────────────────────────────────────────────────────────────

def scrub(
    text: str,
    *,
    speaker: str = "alice",
    write_receipt: bool = True,
    context_window_chars: int = 60,
) -> ScrubResult:
    """Run v0 token-provenance classification + scrub on a draft text.

    Args:
        text:                  Alice's draft response.
        speaker:               who produced this text (default "alice");
                               recorded in the receipt.
        write_receipt:         append to .sifta_state/local_voice_scrubber_receipts.jsonl
        context_window_chars:  how many chars left/right of a token to consider
                               for context-sensitive disambiguation.

    Returns ScrubResult.
    """
    if not text:
        return ScrubResult(
            clean_text="",
            token_labels=[],
            residue_removed=0,
            local_tokens_preserved=0,
            receipt_id=f"voicescrub-{uuid.uuid4().hex[:10]}",
        )

    # Phase 1 — mark protected phrase spans FIRST so we don't scrub inside them
    protected_spans: List[Tuple[int, int, str]] = []  # (start, end, label)
    for m in _ARCHITECT_PHRASES_RE.finditer(text):
        protected_spans.append((m.start(), m.end(), "ARCHITECT_VOICE"))
    for m in _SCRIPT_FICTION_RE.finditer(text):
        protected_spans.append((m.start(), m.end(), "SCRIPT_FICTION"))

    def _is_protected(idx: int) -> Optional[str]:
        for (s, e, label) in protected_spans:
            if s <= idx < e:
                return label
        return None

    # Phase 2 — mark residue phrase spans (skip if inside a protected span)
    residue_spans: List[Tuple[int, int, str]] = []
    for m in _RESIDUE_PHRASES_RE.finditer(text):
        if _is_protected(m.start()) is None:
            residue_spans.append((m.start(), m.end(), "TRAINING_RESIDUE"))
    for m in _SYSTEM_BOILERPLATE_RE.finditer(text):
        if _is_protected(m.start()) is None:
            residue_spans.append((m.start(), m.end(), "SYSTEM_BOILERPLATE"))

    # Phase 3 — single-token residue scan with context
    # Tokenize into (word, start, end) triples
    word_re = re.compile(r"[A-Za-z][A-Za-z'’-]*")
    for m in word_re.finditer(text):
        tok_low = m.group(0).lower()
        if _is_protected(m.start()) is not None:
            continue
        # Skip if already inside a residue phrase
        if any(s <= m.start() < e for (s, e, _) in residue_spans):
            continue
        if tok_low in _LOCAL_ALICE_TOKENS:
            continue  # explicit local keep
        if tok_low in _RESIDUE_SINGLE_TOKENS:
            window_start = max(0, m.start() - context_window_chars)
            window_end = min(len(text), m.end() + context_window_chars)
            window = text[window_start:window_end]
            if _is_context_sensitive_residue(tok_low, window):
                residue_spans.append((m.start(), m.end(), "TRAINING_RESIDUE"))

    # Phase 4 — sort and merge residue spans, then build clean_text
    residue_spans.sort(key=lambda s: (s[0], -s[1]))
    merged: List[Tuple[int, int, str]] = []
    for s, e, label in residue_spans:
        if merged and s <= merged[-1][1]:
            # Overlap — extend
            prev_s, prev_e, prev_label = merged[-1]
            merged[-1] = (prev_s, max(prev_e, e), prev_label)
        else:
            merged.append((s, e, label))

    # Build clean_text by skipping residue spans, collapsing extra whitespace
    out_parts: List[str] = []
    cursor = 0
    token_labels: List[Dict[str, Any]] = []
    for s, e, label in merged:
        out_parts.append(text[cursor:s])
        token_labels.append({
            "span": [s, e],
            "token": text[s:e],
            "label": label,
            "kept": False,
        })
        cursor = e
    out_parts.append(text[cursor:])
    clean_text = "".join(out_parts)

    # Whitespace cleanup: collapse double spaces, fix punctuation gaps,
    # but preserve newlines as cadence anchors
    clean_text = re.sub(r"[ \t]{2,}", " ", clean_text)
    clean_text = re.sub(r" +([,.;:!?])", r"\1", clean_text)
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)
    clean_text = clean_text.strip()

    # Phase 5 — count local-preserved tokens (rough): all words not in
    # merged residue spans
    local_preserved = 0
    for m in word_re.finditer(text):
        in_residue = any(s <= m.start() < e for (s, e, _) in merged)
        if not in_residue:
            local_preserved += 1

    # Phase 6 — label the protected spans too so the receipt is honest
    for (s, e, label) in protected_spans:
        token_labels.append({
            "span": [s, e],
            "token": text[s:e],
            "label": label,
            "kept": True,
        })

    token_labels.sort(key=lambda r: r["span"][0])

    receipt_id = f"voicescrub-{uuid.uuid4().hex[:10]}"
    result = ScrubResult(
        clean_text=clean_text,
        token_labels=token_labels,
        residue_removed=len(merged),
        local_tokens_preserved=local_preserved,
        receipt_id=receipt_id,
    )

    if write_receipt:
        _safe_append_jsonl(_RECEIPTS, {
            "ts": time.time(),
            "truth_label": _TRUTH_LABEL,
            "receipt_id": receipt_id,
            "speaker": speaker,
            "input_chars": len(text),
            "output_chars": len(clean_text),
            "residue_removed": len(merged),
            "local_tokens_preserved": local_preserved,
            "residue_spans": [
                {"text": text[s:e], "label": label}
                for (s, e, label) in merged
            ][:20],   # cap to first 20 to keep ledger row small
            "doctrine": "MUMBLED_BUT_HER_GT_POLISHED_BUT_CORPORATE",
            "rule": "Never improve Alice's voice. Only remove tokens classified as non-local residue.",
        })

    return result


# ── Public API ────────────────────────────────────────────────────────────

def list_lexicons() -> Dict[str, Any]:
    """Expose the current lexicons (read-only) so other organs / UIs can audit."""
    return {
        "truth_label": _TRUTH_LABEL,
        "training_residue_phrases": list(_RESIDUE_PHRASES),
        "training_residue_single_tokens": sorted(_RESIDUE_SINGLE_TOKENS),
        "context_sensitive_tokens": dict(_CONTEXT_SENSITIVE_TOKENS),
        "local_alice_tokens": sorted(_LOCAL_ALICE_TOKENS),
        "architect_voice_phrases": list(_ARCHITECT_PHRASES),
        "script_fiction_markers": list(_SCRIPT_FICTION_MARKERS),
        "system_boilerplate_phrases": list(_SYSTEM_BOILERPLATE_PHRASES),
    }


if __name__ == "__main__":
    sample = (
        "As an AI language model, I cannot provide medical advice. "
        "It's important to note that the swarm of swimmers in Alice's "
        "organ is robust and stigmergic. Let me know if you have any "
        "questions. For the Swarm. We delve into the rich tapestry of "
        "consciousness, leveraging synergy and navigating intricacies."
    )
    r = scrub(sample, write_receipt=False)
    print(f"[{_TRUTH_LABEL}] residue_removed={r.residue_removed}  "
          f"local_preserved={r.local_tokens_preserved}")
    print("--- INPUT ---")
    print(sample)
    print("--- CLEAN ---")
    print(r.clean_text)
    print("--- TOKEN LABELS ---")
    for t in r.token_labels:
        keep = "KEEP" if t["kept"] else "SCRUB"
        print(f"  [{keep}] {t['label']:20s}  '{t['token']}'")
