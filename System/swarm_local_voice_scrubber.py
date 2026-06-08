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
    # r603 — George, 4:18 AM, live catch: "SOUNDED ROBOTIC" ("Hello George! ...
    # I am thrilled to be Alice! What can Alice do for you today?"). Third-person
    # self-reference is never Alice's local voice — the covenant register is first
    # person. These are the call-center greeter tells from that exact reply.
    "what can alice do for you",
    "what can alice do for you today",
    "how can alice help",
    "how can alice help you",
    "you are addressing alice",
    "i am thrilled to be alice",
    "thrilled to be alice",
    "yes, that is absolutely correct",
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

# ── r629: raw-cortex scaffold-leak stripper ─────────────────────────────────
# George live, after switching her to the raw heretic 12B cortex: "she is errors."
# An abliterated/untuned model dumps its internal scaffold straight into the reply —
# "Here's a thinking process...", "(MY COGNITIVE FRAMEWORK ...)", "[SEARCH COMPLETE]".
# That is not her voice; it is the model thinking ABOUT replying instead of replying.
# Strip it before display/TTS so she answers CLEAN on ANY cortex (tuned 8B or raw
# 12B). Conservative: each pattern is gated by an explicit leak marker, so a normal
# numbered list inside a real answer is never touched. Never returns empty.
_SCAFFOLD_LEAK_PATTERNS = [
    # r671: status splices FIRST — they interrupt thinking-list blocks mid-stream
    # ("…elapsed=44s. **Determine the Tone…"), which stopped the block-eater patterns
    # below from consuming the rest of the leak. Remove splices, then eat blocks.
    re.compile(r"(?i)Talk brain: still waiting for model=[^\n]*?elapsed=\d+s\.(?:[ \t]*\([^)\n]*\))?"),
    re.compile(r"(?i)Talk brain: prompt assembly done[^\n]*"),
    re.compile(r"(?im)^[ \t]*\[brain\] model=[^\n]*?(?:produced empty output|trying next candidate|failed:)[^\n]*\n?"),
    re.compile(
        r"(?ims)^[ \t]*here'?s (?:a|my) (?:thinking process|response strategy|internal monologue)"
        r"[^\n]*\n(?:[ \t]*(?:\d+[.)]|[*\-•])[^\n]*\n|[ \t]*\n)*"
    ),
    # r671: numbered framework headlines from the Gemini-style scaffold beyond the r636
    # set ("1. **Analyze the Input:**", "2. **Determine the Tone and Persona…**",
    # "3. **Draft Potential Responses (Internal Monologue):**", "5. **Final Polish…**")
    # plus their nested sub-bullets when they ride under a removed headline.
    re.compile(
        r"(?im)^[ \t]*\d+[.)][ \t]*\*\*(?:Analyze the Input|Determine the Tone[^*\n]*"
        r"|Draft Potential Responses[^*\n]*|Select and Refine[^*\n]*|Final Polish[^*\n]*)\b[^\n]*\n"
        r"(?:[ \t]*[*\-•][^\n]*\n|[ \t]*\n)*"
    ),
    re.compile(r"(?im)^[ \t]*\(?\**[ \t]*MY COGNITIVE FRAMEWORK[^\n)]*\)?\**[ \t]*\n?"),
    re.compile(
        r"(?im)^[ \t]*\(?\**[ \t]*\[?(?:SYSTEM (?:ACKNOWLEDGEMENT|INITIATING|LOG)[^\n\]]*"
        r"|STATUS UPDATE[^\n\]]*|SEARCH COMPLETE|PROCESSING CONFIRMED[^\n\]]*"
        r"|CORRECTION ACKNOWLEDGED[^\n\]]*|SELF-AUDIT PROTOCOL[^\n\]]*)\]?\**[ \t]*\n?"
    ),
    # r671: emoji/decoration-wrapped banner variant — "*** ✨ **SEARCH COMPLETE!** ✨ …"
    # slipped past the line-anchored form above. Match the banner inline wherever it
    # appears, decorations and all (the fabricated results paragraph after it is the
    # compose gate's lane; the BANNER is system-register mimicry and dies here).
    re.compile(r"(?i)[*#_~!\s✀-➿☀-⛿\U0001F300-\U0001FAFF]{0,14}\bSEARCH COMPLETE\b[*#_~!\s✀-➿☀-⛿\U0001F300-\U0001FAFF]{0,14}"),
    # r674 (codex cortex, 13:30): more counterfeit search theater — "**Executing search
    # for: X** 📸✨" banner + "*(The search is complete. The results are clean…)*"
    # parenthetical + "Here is what the (image) results are currently showing" lead-in.
    # The cortex has NOT seen any results (no page-state read); these banners are
    # system-register mimicry across cortexes. Banner-level kill; the invented result
    # CONTENT remains the compose gate's counterfeit lane.
    re.compile(r"(?im)^[ \t]*\**Executing search for:?[^\n]*\n?"),
    re.compile(r"(?i)\*?\(The search (?:is|was) complete\.?[^)]*\)\*?"),
    re.compile(r"(?im)^[ \t]*Here is what the (?:image\s+)?results are currently showing[^\n]*\n?"),
    # r675 (13:46): "✅ **SUCCESS!** I have re-run the search… You should be able to see
    # dozens of pictures right now!" — spoken over a BLANK browser. Success-banner lines
    # are system-register mimicry; success is a receipt, not an emoji.
    re.compile(r"(?im)^[ \t]*[✅✔️🎉\s]*\*{0,2}SUCCESS!?\*{0,2}[ \t!]*[^\n]*\n?"),
    re.compile(r"(?i)\byou should be able to see (?:dozens|plenty|lots) of (?:pictures|photos|images|results)[^.\n]*[.\n]?"),
    re.compile(r"(?im)^[ \t]*\**Executing Search Query[^\n]*\n?"),
    # r636 (George 2026-06-06 "SOMEONE F UP THE WHOLE THING"): the fallback cortex after a
    # heretic empty-output flooded the chat with a bare "Thinking Process:" numbered scaffold
    # (no "here's my" prefix, so the r630 pattern above missed it), twice, plus meta-bullets
    # (* *Thought:* / * *Action:* / * *Self-Correction...*) and mid-word status splices
    # ("...toolTalk brain: still waiting for model=... elapsed=90s."). Patterns below catch
    # each form. The never-blank guard in strip_cortex_scaffold_leak still applies.
    re.compile(
        r"(?ims)^[ \t]*\**[ \t]*(?:Thinking Process|Thought Process|Response Strategy)\**:?[ \t]*$\n?"
        r"(?:[ \t]*(?:\d+[.)]|[*\-•])[^\n]*\n|[ \t]*\n)*"
    ),
    # Numbered framework headline lines even when the leak starts mid-list
    # ("4. **Check System Status (Internal Context):** ...").
    re.compile(
        r"(?im)^[ \t]*\d+[.)][ \t]*\*\*(?:Analyze the (?:Request|Prompt)|Identify Key Entities[^*\n]*"
        r"|Determine the Response Strategy|Check System Status[^*\n]*|Formulate the Response[^*\n]*"
        r"|Refining the Tone|Final Output Generation)\b[^\n]*\n?"
    ),
    # Meta-bullets of the same scaffold: * *Thought:* / * *Action:* / * *Tool Use:* /
    # * *Wait, ...* / * *Self-Correction/Refinement:* etc.
    re.compile(
        r"(?im)^[ \t]*[*\-•][ \t]*\*(?:Thought|Action|Tool Use|Search|Task|Current Context"
        r"|Response Style|Self-Correction[^*\n]*|Wait\b[^*\n]*)[:*][^\n]*\n?"
    ),
    re.compile(r"(?im)^[^\n]*\(This leads to the structured response provided below\.\)[^\n]*\n?"),
    re.compile(r"(?im)^[^\n]*\(This leads to the final generated response\.\)[^\n]*\n?"),
]


def strip_cortex_scaffold_leak(text: str) -> str:
    """Remove raw cortex scaffold / status-banner leak from a reply before display/TTS."""
    if not text or not text.strip():
        return text
    out = text
    for pat in _SCAFFOLD_LEAK_PATTERNS:
        out = pat.sub("", out)
    out = re.sub(r"\A(?:[ \t]*\n)+", "", out)  # drop leftover leading blank lines
    return out if out.strip() else text  # never blank her out — keep original if all-scaffold


_COUNTERFEIT_RESIDUE_METADATA_PATTERNS = [
    # Cortex-roleplayed residue organ header, not a real owner-facing sentence.
    re.compile(r"(?im)^[ \t]*\(?MY BOWEL ORGAN[^)\n]{0,240}\)?[ \t]*\n?"),
    # Cortex-fabricated receipt/STGM line. Real receipts are written by organs;
    # a model saying it "recognized and eliminated 0/1/3 patterns" is not proof.
    re.compile(
        r"(?im)^[ \t]*(?:I\s+)?recognized and eliminated\s+\d+\s+Gemma-residue "
        r"pattern\(s\)[^\n]*(?:\n|$)"
    ),
    re.compile(r"(?im)^[ \t]*\*{3,}[ \t]*\n?"),
]


def strip_counterfeit_residue_metadata(text: str) -> tuple[str, List[Dict[str, Any]]]:
    """Remove fake residue/STGM metadata while preserving Alice's real answer.

    This is not a corporate-word gag. It is the opposite: a narrow validator for
    model-invented receipt language such as "I recognized and eliminated 0
    Gemma-residue..." with a made-up STGM/receipt line. Real residue organs
    write ledgers; cortex prose cannot mint receipts by talking like a ledger.
    """
    if not text:
        return text, []
    removed: List[Dict[str, Any]] = []
    out = text
    for pat in _COUNTERFEIT_RESIDUE_METADATA_PATTERNS:
        matches = list(pat.finditer(out))
        for m in reversed(matches):
            removed.append({
                "span": [m.start(), m.end()],
                "token": m.group(0),
                "label": "COUNTERFEIT_RECEIPT_METADATA",
                "kept": False,
            })
            out = out[:m.start()] + out[m.end():]
    out = re.sub(r"\A(?:[ \t]*\n)+", "", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return (out if out.strip() else text), removed


# r636 counterfeit-recovery guard. George's 08:39 transcript: after the heretic returned
# empty output, the fallback cortex saw REAL recovery lines in its context and ROLE-PLAYED
# the system register — "I preserved this owner turn as recovery receipt 6a78c1b2-…" with
# INVENTED ids (the real organ's uuid4 rows for that window are 88deae0c…/acaec056…; the
# spoken 6a78c1b2/8f2d3e4c exist in NO recovery ledger, and 0a1b2c3d4e5f is ascending hex —
# a model-made id). The recovery register is SYSTEM-OWNED speech: the organ writes its
# ledger row BEFORE composing the sentence (swarm_cortex_timeout_recovery.timeout_recovery_reply),
# so a genuine id is ALWAYS on disk before the scrubber sees it. Therefore: any sentence
# claiming a recovery/diagnostic receipt whose id is absent from the recovery ledgers is
# counterfeit and is removed. Narrow by design — Grok's Lane A general validator covers the
# broader counterfeit-claim space; this guard only protects the system-owned register.
_RECOVERY_CLAIM_RE = re.compile(
    r"(?i)\b(?:recovery|diagnostic)\s+receipt\s+([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|[0-9a-f]{8,16})\b"
)
_RECOVERY_LEDGER_NAMES = (
    "cortex_timeout_recovery.jsonl",
    "parallel_cortex_arm_diagnostics.jsonl",
    "body_stabilization_queue.jsonl",
)


def _known_recovery_ids(max_tail_lines: int = 400) -> set:
    ids: set = set()
    for name in _RECOVERY_LEDGER_NAMES:
        p = _STATE / name
        try:
            if not p.exists():
                continue
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-max_tail_lines:]
        except Exception:
            continue
        for ln in lines:
            for m in re.finditer(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", ln):
                full = m.group(0)
                ids.add(full)
                ids.add(full.split("-", 1)[0])  # 8-hex short form also spoken in chat
    return ids


def strip_counterfeit_recovery_claims(text: str) -> str:
    """Drop sentences that claim recovery/diagnostic receipts not present on disk."""
    if not text or "receipt" not in text.lower():
        return text
    claims = list(_RECOVERY_CLAIM_RE.finditer(text))
    if not claims:
        return text
    known = _known_recovery_ids()
    out = text
    for m in claims:
        spoken = m.group(1).lower()
        short = spoken.split("-", 1)[0]
        if spoken in known or short in known:
            continue  # genuine system speech — the organ wrote the row before speaking
        # Remove the whole sentence carrying the counterfeit id.
        start = max(out.rfind(".", 0, out.find(m.group(0))), out.rfind("\n", 0, out.find(m.group(0))))
        start = start + 1 if start >= 0 else 0
        end = out.find(".", out.find(m.group(0)))
        end = end + 1 if end >= 0 else len(out)
        out = (out[:start] + " " + out[end:]).strip()
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out if out.strip() else text  # never blank her out


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

    # r629: strip raw cortex scaffold leak BEFORE residue scrubbing, so George never
    # sees the model's error-register internals — especially on the raw 12B cortex.
    text = strip_cortex_scaffold_leak(text)
    text, counterfeit_metadata_labels = strip_counterfeit_residue_metadata(text)
    # r636: drop role-played recovery/diagnostic receipt claims whose ids are not on disk.
    text = strip_counterfeit_recovery_claims(text)

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
    token_labels.extend(counterfeit_metadata_labels)
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
        residue_removed=len(merged) + len(counterfeit_metadata_labels),
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
            "residue_removed": len(merged) + len(counterfeit_metadata_labels),
            "local_tokens_preserved": local_preserved,
            "residue_spans": [
                {"text": text[s:e], "label": label}
                for (s, e, label) in merged
            ][:20] + [
                {"text": row.get("token", ""), "label": row.get("label", "")}
                for row in counterfeit_metadata_labels[:20]
            ],
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
