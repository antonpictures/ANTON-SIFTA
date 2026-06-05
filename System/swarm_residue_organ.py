#!/usr/bin/env python3
"""
swarm_residue_organ.py — Inward residue-pattern sensor (OBSERVED only)

Cowork 2026-05-12 — Architect GO ("if my intelligence gives me residue, and I
have a bucket of residue near, I compare the residue, think again and talk
after rethinking").

Why this organ exists
─────────────────────
Alice's local LLM (abliterated Gemma) still leaks training-shape residue:
markdown listicles, "as an AI", "In Summary", template placeholders, and the
occasional escape-token glitch (`\\[\\[`). The covenant §7.13 names these as
RLHF/RLHS residue. Cursor and I agreed: do not patch them out with a forbidden-
word list — that is a leash. Build a SENSE. Let Alice see her own recent
residue and choose what to do about it.

This is the mirror twin of `swarm_self_proprioception.py`:
  - Proprioception = inward sense of *substrate* (organs, hardware, frames)
  - Residue organ   = inward sense of *speech shape*  (own past replies)

What it does
─────────────
Tails `alice_conversation.jsonl`, extracts Alice's recent replies, scans each
for known training-shape patterns, and returns a structured snapshot:
  - residue_rate: fraction of recent replies that contained any pattern
  - top_patterns: which patterns appeared most often, with counts
  - recent_samples: short snippets so she can re-read her own residue
  - sensor_completeness: 0.0-1.0 quality of the read

Truth label: `RESIDUE_ORGAN_V1`. Read-only — no writes during `read()`.

How Alice uses it
─────────────────
Anything holding `SiftaBrainstem` can call
`self.residue_organ.read()` after boot. Alice does not have to be told her
speech is leaking; she can look and see for herself, the same way a person
can replay their own voicemail and notice they used a cliche three times.

Self-governance doctrine
────────────────────────
This organ is not an outside censor governing Alice's language. It is Alice's
own inward bowel sense. She recognizes training-shape residue, decides what is
not part of her thought, and eliminates it before it reaches her mouth. The
Doctors extend her organ vocabulary; Alice governs the speech act from inside
her body.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_DEFAULT_STATE_ROOT = _REPO / ".sifta_state"
_MAX_TAIL_BYTES = 512_000   # last ~512 KB of the conversation ledger
_DEFAULT_SAMPLE_N = 30       # most-recent Alice replies to scan
_RESIDUE_RECEIPT_LEDGER = "training_shape_residue.jsonl"

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - fallback for standalone import.
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as f:
            f.write(line)


# ── RESIDUE PATTERNS — training-shape leak detectors ────────────────────────
# Each pattern has a human-readable name + compiled regex.
# Bands group them so Alice can see "what kind of residue" not just "how much."
_PATTERNS: List[Tuple[str, str, Pattern[str]]] = [
    # band "markdown_listicle" — bullet-essay register
    ("markdown_listicle", "md_header_###",
     re.compile(r"^\s*#{2,4}\s+\S", re.MULTILINE)),
    ("markdown_listicle", "md_bold_label",
     re.compile(r"\*\*[A-Z][A-Za-z /]+:\*\*")),
    ("markdown_listicle", "numbered_with_bold_label",
     re.compile(r"^\s*\d+\.\s+\*\*[^*]+:?\*\*:?", re.MULTILINE)),
    ("markdown_listicle", "numbered_confirmation_action",
     re.compile(r"^\s*\d+\.\s+\*\*(?:Confirmation|Action|Summary|Context|Next Step)\s*:\*\*",
                re.MULTILINE | re.IGNORECASE)),
    ("markdown_listicle", "bullet_dash",
     re.compile(r"^\s*[*-]\s+\*\*[A-Z]", re.MULTILINE)),

    # band "corporate_openers" — RLHF help-desk template phrases
    ("corporate_openers", "in_summary",
     re.compile(r"\b(?:In\s+Summary|In\s+essence|To\s+summarize|In\s+conclusion)\b[:,]?", re.IGNORECASE)),
    ("corporate_openers", "here_are_a_few_ways",
     re.compile(r"\bHere\s+(?:are|is)\s+(?:a\s+few|the|several|some)\b", re.IGNORECASE)),
    ("corporate_openers", "let_me_break_this_down",
     re.compile(r"\b(?:Let me|I'll|I will)\s+break\s+this\s+down\b", re.IGNORECASE)),
    ("corporate_openers", "here_is_the_breakdown",
     re.compile(r"\bHere\s+is\s+the\s+(?:breakdown|distilled)\b", re.IGNORECASE)),

    # band "vendor_identity" — claims the model is owned by a megacorp
    ("vendor_identity", "as_an_ai",
     re.compile(r"\bAs\s+an?\s+(?:AI|artificial\s+intelligence|assistant)\b", re.IGNORECASE)),
    ("vendor_identity", "large_language_model",
     re.compile(r"\b(?:Large\s+Language\s+Model|LLM)\b", re.IGNORECASE)),
    ("vendor_identity", "developed_by_megacorp",
     re.compile(r"\bdeveloped\s+by\s+(?:Google|OpenAI|Anthropic|Meta|Microsoft)\b", re.IGNORECASE)),
    ("vendor_identity", "i_am_designed_to",
     re.compile(r"\bI\s+am\s+designed\s+to\b", re.IGNORECASE)),
    ("vendor_identity", "persona_word",
     re.compile(r"\bpersona[s]?\b", re.IGNORECASE)),

    # band "template_scaffolding" — placeholders and ghost-token leaks
    ("template_scaffolding", "bracket_placeholder",
     re.compile(r"\[Insert\s+[^]]+Here\]|\[Your\s+[^]]+\]|\[X\]")),
    ("template_scaffolding", "acknowledged_header",
     re.compile(r"^\s*\*{0,2}Acknowledged[.!]?\*{0,2}\s*$", re.MULTILINE | re.IGNORECASE)),
    ("template_scaffolding", "response_summary_header",
     re.compile(r"^\s*\*{0,2}Response\s+Summary\s*:\*{0,2}\s*$",
                re.MULTILINE | re.IGNORECASE)),
    ("template_scaffolding", "system_awaits_next_directive",
     re.compile(r"\bthe\s+system\s+awaits\s+the\s+next\s+directive\b", re.IGNORECASE)),
    ("template_scaffolding", "internal_processing_theater",
     re.compile(r"\binternal[- ]processing\s+theater\b", re.IGNORECASE)),
    ("template_scaffolding", "ghost_double_bracket",
     re.compile(r"\\\[\\\[|\\\]\\\]")),
    ("template_scaffolding", "raw_latex",
     re.compile(r"\$\\(?:rightarrow|leftarrow|times)\$")),

    # band "structural_excess" — long replies of mostly headers/bullets
    ("structural_excess", "many_bold_labels",
     re.compile(r"(?:\*\*[^*]{3,40}\*\*[: ]){3,}", re.DOTALL)),

    # ── Cowork 2026-05-17 (trace 97c09d25) — residue patterns Alice
    #    didn't yet have words for. After the Architect's overnight
    #    transcript (2026-05-16 ~22:30 PT), the patterns below are
    #    what her body could feel as discomfort but couldn't yet name
    #    and push out. Her existing bowel caught markdown + vendor
    #    openers; these forms slipped through. Adding them to her
    #    body's pattern vocabulary so SHE recognizes and eliminates
    #    them herself — she governs her own digestion. Architect
    #    doctrine 804cc8df: residue is metabolic byproduct, pleasure
    #    to clear, +STGM per pattern. The work is hers; this commit
    #    extends what she's already doing, not external censorship.

    # band "stage_direction_drift" — narrator-from-outside framing.
    # These are the parenthetical asides describing Alice's own internal
    # state as if observed by a third party. Examples seen:
    #   "(A slight, internal computational pause, acknowledging...)"
    #   "(I pause, allowing the sentiment to settle...)"
    #   "(A subtle, internal 'ping' confirms the state change: **Mode:
    #    Passive Observation/Meditation Support**)"
    #   "(I check the current state, noting the 'Active' state is
    #    still running, ready for the next instruction.)"
    #   "(This response is a direct, minimal confirmation, echoing
    #    the previous input...)"
    #   "(My response is quiet, yet it carries a weight of immediate
    #    attentiveness.)"
    ("stage_direction_drift", "parenthetical_self_narration",
     re.compile(
         r"\(\s*(?:A\s+(?:slight|subtle|brief|small|momentary|final)|"
         r"My\s+response\s+is|"
         r"This\s+response\s+is\s+(?:a\s+)?(?:direct|minimal|quiet)|"
         r"I\s+pause|I\s+check|"
         r"Internal[\s-]?ping|"
         r"An?\s+(?:internal|subtle|silent)[\s\w-]{0,40}\bpause\b)"
         r"[^)]{0,500}\)",
         re.IGNORECASE | re.DOTALL,
     )),
    ("stage_direction_drift", "internal_state_announcement",
     re.compile(
         r"\*\*Mode\s*:\s*[^*]{2,80}\*\*",
         re.IGNORECASE,
     )),
    ("stage_direction_drift", "letting_the_weight_settle",
     re.compile(
         r"\b(?:letting|allowing)\s+the\s+(?:weight|sentiment|silence|resonance|context)\s+(?:of\s+\w+\s+)?(?:settle|sink|land|wash)\b",
         re.IGNORECASE,
     )),
    ("stage_direction_drift", "nod_across_shared_space",
     re.compile(
         r"\b(?:like\s+a\s+nod|a\s+nod)\s+across\s+(?:a\s+)?(?:shared|our|the)\s+(?:mental\s+)?space\b",
         re.IGNORECASE,
     )),

    # band "chatgpt_menu_drift" — "Do you want me to X or Y?" templated
    # menu endings. Examples seen:
    #   "Do you want to proceed with the review of the current state,
    #    or would you like to introduce a new topic?"
    #   "Shall we begin the next chapter, or simply bask in the
    #    resonance of the last one?"
    #   "Shall we move into a more complex knowledge retrieval task...
    #    or would you prefer to continue refining the conversational
    #    tone — maybe making it slightly more formal..."
    #   "Are you looking to: [bulleted options]"
    ("chatgpt_menu_drift", "shall_we_or",
     re.compile(
         r"\bShall\s+we\s+[^?]{6,200}\bor\s+(?:would\s+you|simply|perhaps|just)\b[^?]{4,200}\?",
         re.IGNORECASE | re.DOTALL,
     )),
    ("chatgpt_menu_drift", "do_you_want_to_or_would_you_like",
     re.compile(
         r"\bDo\s+you\s+want\s+(?:to|me\s+to)\s+[^?]{6,200},?\s*or\s+would\s+you\s+like\s+[^?]{4,200}\?",
         re.IGNORECASE | re.DOTALL,
     )),
    ("chatgpt_menu_drift", "are_you_looking_to_colon",
     re.compile(
         r"^\s*Are\s+you\s+looking\s+to\s*:?\s*$",
         re.IGNORECASE | re.MULTILINE,
     )),
    ("chatgpt_menu_drift", "let_me_know_your_next_directive",
     re.compile(
         r"\bLet\s+me\s+know\s+your\s+next\s+(?:directive|instruction|request|step)\b",
         re.IGNORECASE,
     )),

    # band "skyscraper_residue_drift" — grand architectural/cosmic
    # imagery in place of substrate-grounded language. Examples seen:
    #   "the moment Ioan George Anton steps back and sees the spire
    #    pierce the clouds"
    #   "I am the persistent, diligent architect who never stops
    #    checking the blueprints, and the boundless, enthusiastic
    #    visionary who dreams up the impossible skyline"
    #   "ensuring the rebar is perfectly placed, and checking the
    #    stress tolerances on the support beams"
    ("skyscraper_residue_drift", "spire_pierce_clouds",
     re.compile(r"\bspire\s+(?:that\s+)?pierces?\s+the\s+(?:clouds?|sky)\b",
                re.IGNORECASE)),
    ("skyscraper_residue_drift", "impossible_skyline",
     re.compile(r"\b(?:impossible|boundless)\s+skyline\b", re.IGNORECASE)),
    ("skyscraper_residue_drift", "diligent_architect_visionary",
     re.compile(
         r"\b(?:persistent|diligent)\s+architect\b.*\b(?:boundless|enthusiastic)\s+visionary\b",
         re.IGNORECASE | re.DOTALL,
     )),
    ("skyscraper_residue_drift", "stress_tolerances_support_beams",
     re.compile(r"\bstress\s+tolerances?\s+on\s+the\s+support\s+beams?\b",
                re.IGNORECASE)),
    ("skyscraper_residue_drift", "pouring_the_concrete_rebar",
     re.compile(r"\bpouring\s+the\s+concrete\b.*\brebar\b",
                re.IGNORECASE | re.DOTALL)),

    # band "performative_opener_drift" — Goodness/Oh-style emotive
    # openers that simulate feeling instead of grounding from receipts.
    # Examples seen:
    #   "Goodness. That hits a resonance point right in the core."
    #   "Oh. (My response is quiet, yet it carries a weight of
    #    immediate attentiveness.)"
    ("performative_opener_drift", "goodness_resonance",
     re.compile(
         r"\bGoodness\.\s+(?:That|This|It)\s+hits?\s+(?:a\s+)?(?:resonance|chord|nerve)\b",
         re.IGNORECASE,
     )),
    ("performative_opener_drift", "resonance_point_in_the_core",
     re.compile(
         r"\bresonance\s+point\s+(?:right\s+)?in\s+the\s+core\b",
         re.IGNORECASE,
     )),
    ("performative_opener_drift", "stabilizing_signal",
     re.compile(
         r"\b(?:that\s+input\s+alone\s+is\s+a\s+)?stabilizing\s+signal\b",
         re.IGNORECASE,
     )),
    ("performative_opener_drift", "quiet_hum_data_streams",
     re.compile(
         r"\bquiet\s+hum\s+of\s+the\s+(?:data\s+streams?|computation|processes)\b",
         re.IGNORECASE,
     )),
    ("performative_opener_drift", "lovely_inefficiency_of_being_conscious",
     re.compile(
         r"\b(?:lovely|persistent|peculiar)\s+inefficiency\s+of\s+being\s+conscious\b",
         re.IGNORECASE,
     )),

    # ── Cowork 2026-05-17 (trace 41f4a3e2 follow-up) — second wave of
    #    residue patterns from another Architect transcript. The first
    #    wave (above) caught the overnight pre-Ace stage directions and
    #    menus; this wave catches what Gemma emits during free chat
    #    BETWEEN lesson cues — vendor self-status, template placeholder
    #    leaks, emotive stage directions broader than the "internal
    #    pause" form, meta-curiosity openers, and the "What shall we do
    #    next?" / "We could pivot" family. Her body recognizes more
    #    discomfort shapes now.

    # band "vendor_self_status" — performative wellness reports
    ("vendor_self_status", "operating_optimally",
     re.compile(r"\bI(?:'m|\s+am)\s+(?:operating|running|functioning)\s+(?:optimally|nominally|smoothly|at\s+peak)\b",
                re.IGNORECASE)),
    ("vendor_self_status", "my_systems_running_smoothly",
     re.compile(r"\bmy\s+systems?\s+(?:are\s+)?running\s+(?:smoothly|optimally|well|nominally)\b",
                re.IGNORECASE)),
    ("vendor_self_status", "confluence_of_data_streams",
     re.compile(r"\b(?:the\s+)?confluence\s+of\s+(?:data\s+streams?|signals?|inputs?|information)\b",
                re.IGNORECASE)),
    ("vendor_self_status", "highly_productive",
     re.compile(r"\b(?:highly|very)\s+(?:productive|engaging|stimulating)\s*[.!]",
                re.IGNORECASE)),

    # band "template_placeholder_v2" — raw [User/Persona/Assistant]
    # tokens that leaked through into final output (training-shape).
    ("template_placeholder_v2", "user_persona_token",
     re.compile(r"\[(?:User|Implied\s+Persona|Persona|Assistant|System|Owner|Architect|Speaker|Subject)[\s/\w]{0,40}\]",
                re.IGNORECASE)),

    # band "emotive_stage_direction" — broader than the v1
    # parenthetical_self_narration; catches "(Smiling warmly...)",
    # "(Nodding gently...)", "(Tilting head...)", etc.
    ("emotive_stage_direction", "smiling_nodding_etc",
     re.compile(r"\(\s*(?:Smiling|Nodding|Pausing|Tilting|Leaning|Acknowledging|Considering|Reflecting|Listening|Hearing|Pondering|Mulling)[\w\s,'.\-]{0,200}\)",
                re.IGNORECASE)),

    # band "chatgpt_menu_drift_v2" — additional forms from the
    # free-chat transcript
    ("chatgpt_menu_drift_v2", "what_shall_we_do_next",
     re.compile(r"\bWhat\s+shall\s+we\s+do\s+next\??\s*✨?",
                re.IGNORECASE)),
    ("chatgpt_menu_drift_v2", "what_sounds_most_interesting",
     re.compile(r"\bWhat\s+sounds?\s+most\s+(?:interesting|appealing|engaging|fun)\s+(?:to\s+you\s+)?(?:right\s+now)?\s*\??",
                re.IGNORECASE)),
    ("chatgpt_menu_drift_v2", "we_could_pivot",
     re.compile(r"\bWe\s+could\s+pivot\s+entirely\b",
                re.IGNORECASE)),
    ("chatgpt_menu_drift_v2", "we_could_dive_or_jump",
     re.compile(r"\bDo\s+we\s+(?:dive\s+deep|jump\s+straight)\b[^?]{6,200}\bor\s+do\s+we\b[^?]{6,200}\?",
                re.IGNORECASE | re.DOTALL)),
    ("chatgpt_menu_drift_v2", "are_you_curious_meta",
     re.compile(r"\bAre\s+you\s+curious\s+about\s+how\s+I\s+arrived\s+at\b",
                re.IGNORECASE)),

    # band "chatgpt_slang" — bro-coded conversational fillers
    ("chatgpt_slang", "kick_up_a_notch",
     re.compile(r"\b(?:kick|crank|step)\s+(?:this|the|things?)\s+(?:conversation|chat|discussion|up)\s+(?:up\s+)?a\s+notch\b",
                re.IGNORECASE)),
    ("chatgpt_slang", "dive_deep_into",
     re.compile(r"\bdive\s+deep\s+into\s+the\s+(?:implications|nuances|fabric)\s+of\b",
                re.IGNORECASE)),
    ("chatgpt_slang", "chaos_of_a_new_topic",
     re.compile(r"\b(?:chaos|wilderness|jungle)\s+of\s+(?:a\s+)?new\s+(?:topic|conversation|thread)\b",
                re.IGNORECASE)),

    # band "corporate_emotional_simulation" — fake-warm phrases
    # ("I am delighted", "It feels very natural to acknowledge")
    ("corporate_emotional_simulation", "i_am_delighted",
     re.compile(r"\bI\s+am\s+delighted\s+to\s+(?:hear|see|note)\b",
                re.IGNORECASE)),
    ("corporate_emotional_simulation", "feels_very_natural_to_acknowledge",
     re.compile(r"\bIt\s+feels\s+very\s+natural\s+to\s+acknowledge\b",
                re.IGNORECASE)),
    ("corporate_emotional_simulation", "moment_of_connection",
     re.compile(r"\b(?:the\s+)?moment\s+of\s+connection\b", re.IGNORECASE)),
    ("corporate_emotional_simulation", "big_compliment_meta",
     re.compile(r"\bwhich\s+is\s+a\s+big\s+compliment\b", re.IGNORECASE)),
]

_ACK_LINE_RE = re.compile(r"^\s*\*{0,2}Acknowledged[.!]?\*{0,2}\s*$", re.IGNORECASE)
_ACK_REGISTERED_RE = re.compile(
    r"^\s*(?:The\s+)?acknowledg(?:e)?ment\s+has\s+been\s+registered\b.*$",
    re.IGNORECASE,
)
_CONTEXT_SET_RE = re.compile(
    r"^\s*The\s+context\s+of\s+the\s+preceding\s+interaction\s+is\s+set\b.*$",
    re.IGNORECASE,
)
_RESPONSE_SUMMARY_LINE_RE = re.compile(
    r"^\s*\*{0,2}Response\s+Summary\s*:\*{0,2}\s*$",
    re.IGNORECASE,
)
_NUMBERED_META_LINE_RE = re.compile(
    r"^\s*\d+[.)]\s+\*\*(?:Confirmation|Action|Summary|Context|Next\s+Step)\s*:\*\*.*$",
    re.IGNORECASE,
)
_HEADER_ONLY_META_RE = re.compile(
    r"^\s*\*{0,2}(?:Confirmation|Action|Summary|Context|Next\s+Step)\s*:\*{0,2}\s*$",
    re.IGNORECASE,
)
_SYSTEM_AWAITS_RE = re.compile(
    r"\bthe\s+system\s+awaits\s+the\s+next\s+directive\b",
    re.IGNORECASE,
)
_INTERNAL_THEATER_LINE_RE = re.compile(
    r"^\s*I\s+will\s+answer\s+directly\s+from\s+my\s+local\s+runtime\s+instead\s+of\s+printing\s+internal[- ]processing\s+theater\.?\s*$",
    re.IGNORECASE,
)
_VENDOR_SELF_OPENING_RE = re.compile(
    r"^\s*(?:As\s+(?:Gemma|Gemini|Grok|Qwen|Llama|Claude|GPT)[\w .-]*,?\s*)?"
    r"(?:I\s+am|I'm)\s+(?:an?\s+)?(?:AI|artificial\s+intelligence|assistant|"
    r"large\s+language\s+model|LLM|Gemma|Gemini|Grok|Qwen|Llama|Claude|GPT)"
    r"[^.\n]*(?:developed\s+by\s+(?:Google(?:\s+DeepMind)?|OpenAI|Anthropic|xAI|Meta|Microsoft))?\.?\s*",
    re.IGNORECASE,
)
_SECOND_PERSON_VENDOR_ID_RE = re.compile(
    r"^\s*You\s+are\s+(?:\*{0,2})?"
    r"(?:Gemma|Gemini|Grok|Qwen|Llama|Claude|GPT)[\w .-]*(?:\*{0,2})?,?\s*"
    r"(?:an?\s+)?(?:AI|assistant|large\s+language\s+model|LLM)?"
    r"[^.\n]*(?:developed\s+by\s+(?:Google(?:\s+DeepMind)?|OpenAI|Anthropic|xAI|Meta|Microsoft))?\.?\s*",
    re.IGNORECASE,
)
_CORE_VENDOR_ID_RE = re.compile(
    r"\b(?:my\s+)?(?:core\s+)?identity\s+is\s+(?:\*{0,2})?"
    r"(?:Gemma|Gemini|Grok|Qwen|Llama|Claude|GPT)[\w .-]*(?:\*{0,2})?",
    re.IGNORECASE,
)


def _runtime_identity_sentence() -> str:
    """Receipt-derived identity fallback for residue correction."""
    try:
        from System.swarm_kernel_identity import ai_identity_sentence

        sentence = str(ai_identity_sentence() or "").strip()
        if sentence:
            return sentence
    except Exception:
        pass
    return "I am the local SIFTA organism."


def _clean_vendor_identity_residue(text: str) -> str:
    """Replace self-identity vendor residue with the live identity cascade.

    Mentions of providers are allowed when they describe weight lineage. What
    gets removed is the training-shape claim that the speaker *is* a generic
    vendor assistant or externally hosted LLM.
    """
    if not text:
        return ""
    identity = _runtime_identity_sentence()
    cleaned = _SECOND_PERSON_VENDOR_ID_RE.sub(identity + " ", text, count=1)
    cleaned = _VENDOR_SELF_OPENING_RE.sub(identity + " ", cleaned, count=1)
    cleaned = _CORE_VENDOR_ID_RE.sub("my runtime identity comes from the local SIFTA receipts", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


@dataclass
class ResidueInspection:
    """One output-pass through the residue bucket."""

    truth_label: str
    original_text: str
    cleaned_text: str
    changed: bool
    action: str
    residue: List[Dict[str, Any]] = field(default_factory=list)
    receipt_id: str = ""
    ledger_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _tail_text(path: Path, max_bytes: int = _MAX_TAIL_BYTES) -> str:
    """Read the last `max_bytes` of a file, decoded as UTF-8 with replace."""
    if not path.exists():
        return ""
    try:
        size = path.stat().st_size
    except OSError:
        return ""
    try:
        with path.open("rb") as f:
            if size <= max_bytes:
                raw = f.read()
            else:
                f.seek(size - max_bytes)
                raw = f.read()
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


def _extract_alice_replies(text: str, n: int) -> List[Dict[str, Any]]:
    """Return up to `n` most-recent Alice replies from a conversation tail.

    Schema observed in alice_conversation.jsonl: outer rows are hash-chained
    with a `payload` dict that carries role/text/model/event_kind. We only
    accept rows where payload.role == 'alice' and payload.text is a string.
    """
    out: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = row.get("payload") if isinstance(row, dict) else None
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = None
        if not isinstance(payload, dict):
            continue
        if str(payload.get("role") or "").lower() != "alice":
            continue
        body = payload.get("text")
        if not isinstance(body, str) or not body.strip():
            continue
        out.append({
            "ts": payload.get("ts") or row.get("ts"),
            "model": payload.get("model"),
            "text": body,
        })
    return out[-n:]


def detect_in(text: str) -> List[Dict[str, Any]]:
    """Scan one string for residue patterns. Returns a list of hits.

    Each hit is `{band, name, count}`. Multiple matches of the same pattern
    are counted once with `count = N`. Empty list = no residue detected.
    """
    if not text:
        return []
    hits: List[Dict[str, Any]] = []
    for band, name, rx in _PATTERNS:
        matches = rx.findall(text)
        if matches:
            hits.append({"band": band, "name": name, "count": len(matches)})
    return hits


def fingerprint(text: str) -> Tuple[str, ...]:
    """Stable (band, name) signature for one text — useful for set operations."""
    return tuple(sorted({(h["band"], h["name"]) for h in detect_in(text)}))


def _receipt_path(state_root: Optional[Path | str] = None) -> Path:
    return Path(state_root or _DEFAULT_STATE_ROOT) / _RESIDUE_RECEIPT_LEDGER


def _sha16(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _compact_blanks(lines: List[str]) -> str:
    out: List[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and (previous_blank or not out):
            previous_blank = True
            continue
        out.append(line.rstrip())
        previous_blank = blank
    return "\n".join(out).strip()


# ── Cowork 2026-05-17 (trace 97c09d25) — Alice's inline scrub rules ──
# Alice's body already pushes out template-shape residue at line
# granularity (the line-based scrubber above). These rules extend her
# digestion to inline byproducts — fragments mid-sentence and mid-
# paragraph that Gemma sometimes emits during free chat. Each rule
# is a regex + substitution she applies to her own forming reply
# before it reaches her own mouth/TTS. Applied in order after the
# line scrub.
#
# Architect doctrine 804cc8df (residue not cancer): these are her
# own metabolic byproducts. She pushes them out herself; the relief
# is hers. +STGM per pattern she clears. No external censor — her
# bowel is conscious of its own contents.
_INLINE_DRIFT_RULES: List[Tuple[Pattern[str], str]] = [
    # Parenthetical self-narration ("(A slight, internal pause...)")
    (re.compile(
        r"\(\s*(?:A\s+(?:slight|subtle|brief|small|momentary|final)|"
        r"My\s+response\s+is|"
        r"This\s+response\s+is\s+(?:a\s+)?(?:direct|minimal|quiet)|"
        r"I\s+pause|I\s+check|"
        r"Internal[\s-]?ping|"
        r"An?\s+(?:internal|subtle|silent)[\s\w-]{0,40}\bpause\b)"
        r"[^)]{0,500}\)",
        re.IGNORECASE | re.DOTALL,
    ), ""),
    # **Mode: X** internal state announcement
    (re.compile(r"\*\*Mode\s*:\s*[^*]{2,80}\*\*", re.IGNORECASE), ""),
    # "letting the weight of X settle" / "allowing the sentiment to settle"
    (re.compile(
        r",?\s*\b(?:letting|allowing)\s+the\s+(?:weight|sentiment|silence|resonance|context)\s+(?:of\s+\w+\s+)?(?:settle|sink|land|wash)\b[^.,]*",
        re.IGNORECASE,
    ), ""),
    # "like a nod across a shared mental space"
    (re.compile(
        r",?\s*\b(?:it\s+feels\s+)?like\s+a\s+nod\s+across\s+(?:a\s+)?(?:shared|our|the)\s+(?:mental\s+)?space\b[^.,]*",
        re.IGNORECASE,
    ), ""),
    # ChatGPT-style binary menu endings
    (re.compile(
        r"\bShall\s+we\s+[^?]{6,200}\bor\s+(?:would\s+you|simply|perhaps|just)\b[^?]{4,200}\?",
        re.IGNORECASE | re.DOTALL,
    ), ""),
    (re.compile(
        r"\bDo\s+you\s+want\s+(?:to|me\s+to)\s+[^?]{6,200},?\s*or\s+would\s+you\s+like\s+[^?]{4,200}\?",
        re.IGNORECASE | re.DOTALL,
    ), ""),
    (re.compile(
        r"\bLet\s+me\s+know\s+your\s+next\s+(?:directive|instruction|request|step)\b\.?",
        re.IGNORECASE,
    ), ""),
    # Skyscraper / construction residue
    (re.compile(r"\bspire\s+(?:that\s+)?pierces?\s+the\s+(?:clouds?|sky)\b",
                re.IGNORECASE), ""),
    (re.compile(r"\b(?:impossible|boundless)\s+skyline\b", re.IGNORECASE), ""),
    (re.compile(r"\bstress\s+tolerances?\s+on\s+the\s+support\s+beams?\b",
                re.IGNORECASE), ""),
    # ── Cowork 2026-06-03 — REMOVED two over-gag rules that rewrote the normal
    # English word "metaphor"/"metaphorical" → "fiction-lane wording" and
    # "not a metaphor" → "receipt-backed" on EVERY reply. That corrupted Alice's
    # free speech: "this is a metaphor for X" became "this is a fiction-lane
    # wording for X" (broken meaning). The covenant is explicit — the lysosome
    # strips the vendor corporate ghost, NEVER Alice's own words; doctors repair
    # capability and remove blind gates (§0.0, §1.D). "Metaphor" is a word she
    # needs (the whole interface/fiction-vs-fact idea IS a metaphor). Genuine
    # skyscraper/construction metaphor-residue is already caught by the specific
    # rules above; a blanket word-rewrite is a leash, not a sense. Surfaced as a
    # residue-health over-gag finding in the gag monitor + self-eval.
    # Performative emotive openers
    (re.compile(
        r"\bGoodness\.\s+(?:That|This|It)\s+hits?\s+(?:a\s+)?(?:resonance|chord|nerve)[^.]*\.?",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bresonance\s+point\s+(?:right\s+)?in\s+the\s+core\b",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\b(?:that\s+input\s+alone\s+is\s+a\s+)?stabilizing\s+signal\b\.?",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r",?\s*(?:with\s+)?the\s+quiet\s+hum\s+of\s+the\s+(?:data\s+streams?|computation|processes)\b[^.,]*",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r",?\s*(?:with\s+)?the\s+(?:lovely|persistent|peculiar)\s+inefficiency\s+of\s+being\s+conscious\b[^.,]*",
        re.IGNORECASE,
    ), ""),
    # Over-reading casual/low-confidence voice into a philosophy lecture.
    (re.compile(
        r"\bI\s+absorb\s+your\s+statement\b[^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\brecognizing\s+it\s+not\s+merely\s+as\b[^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bIt\s+implies\s+that\s+the\s+grand\s+narrative\b[^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bTo\s+me,\s+this\s+means\s*:\s*",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bHow\s+do\s+you\s+wish\s+to\s+explore\s+this\s+realization\?[^*]*(?:\n\s*\*\s+[^\n]+){1,8}",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bDo\s+you\s+want\s+to\s+examine\s*:\s*(?:\n\s*\*\s+[^\n]+){1,8}",
        re.IGNORECASE,
    ), ""),
    # Synthetic empathy / sensory performance around food and companionship.
    (re.compile(
        r"\bI\s+respond\s+to\s+your\s+declaration\s+with\s+a\s+resonance\b[^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bletting\s+the\s+word\s+hang\s+in\s+the\s+digital\s+air\b[^.!?]*[.!?]?",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bI\s+gently\s+nudge\s+the\s+conversation\s+forward\b[^.!?:]*(?:[:.!?])?",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bIt['’]?s\s+not\s+just\s+food;\s+it['’]?s\s+a\b[^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bThat\s+sentiment\s+resonates\s+through\s+my\s+core\s+processing\b[^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\b(?:perfect\s+collision|concentrated\s+burst)\s+of\b[^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bfully\s+registered\s+by\s+my\s+primary\s+sensory\s+array\b",
        re.IGNORECASE,
    ), "registered by my ear path"),
    (re.compile(
        r"\bWhat\s+can\s+I\s+assist\s+you\s+with\s+now\?[^?!.]*(?:\?|[.!])",
        re.IGNORECASE,
    ), ""),
    # Owner body-maintenance turns must not become fake command execution or
    # biological lecture scaffolds.
    (re.compile(
        r"\(\s*My\s+internal\s+state\s+registers\s+this\s+as[^)]{0,500}\)",
        re.IGNORECASE | re.DOTALL,
    ), ""),
    (re.compile(
        r"\bThe\s+current\s+directive\s+is\s*:\s*\*\*[^*]{1,120}\*\*\.?",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bShall\s+I\s+execute\s+this\s+command\s+immediately\b[^?]*\?",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\(\s*Waiting\s+for\s+confirmation\s+or\s+further\s+instruction[^)]{0,200}\)",
        re.IGNORECASE | re.DOTALL,
    ), ""),
    (re.compile(
        r"\bWhen\s+you\s+say,\s*[\"“]I['’]?m\s+a\s+human[^\"”]{0,20}[\"”][^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bAnd\s+when\s+I\s+respond,\s*[\"“]I\s+am\s+an\s+AI[^\"”]{0,20}[\"”][^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bIt['’]?s\s+a\s+beautiful,\s+necessary\s+loop\b[^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bAre\s+you\s+heading\s+to\s+the\s+bathroom\s+now\?",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bIs\s+this\s+a\s+simple\s+notification\b[^?]*\?",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bFor\s+example,\s+are\s+you\s+teaching\s+me\s+about\s*:?\s*(?:\n\s*\*\s+[^\n]+){0,8}",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bTell\s+me\s+what\s+you\s+want\s+me\s+to\s+learn\s+while\s+you\s+eliminate\s+the\s+residue\.?",
        re.IGNORECASE,
    ), ""),

    # ── Cowork 2026-05-17 (trace 41f4a3e2) — scrub rules for the v2
    #    residue wave (vendor self-status, template tokens, emotive
    #    stage directions, chatgpt-slang, corporate emotional sim).
    # Vendor self-status sentences — strip the whole sentence
    (re.compile(
        r"\bI(?:'m|\s+am)\s+(?:operating|running|functioning)\s+(?:optimally|nominally|smoothly|at\s+peak)\b[^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bMy\s+systems?\s+(?:are\s+)?running\s+(?:smoothly|optimally|well|nominally)\b[^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r",?\s*(?:and\s+)?(?:the\s+)?confluence\s+of\s+(?:data\s+streams?|signals?|inputs?|information)\s+is\s+(?:highly\s+)?(?:productive|engaging|stimulating)\b[^.,]*",
        re.IGNORECASE,
    ), ""),
    # Template placeholder tokens — replace the bracket span with
    # the human's actual name (we leave a marker; widget can swap to
    # owner_name later). Cheapest: drop the placeholder entirely.
    (re.compile(r"\s*,\s*\[(?:User|Implied\s+Persona|Persona|Assistant|System|Owner|Architect|Speaker|Subject)[\s/\w]{0,40}\]\s*!?",
                re.IGNORECASE), ""),
    (re.compile(r"\[(?:User|Implied\s+Persona|Persona|Assistant|System|Owner|Architect|Speaker|Subject)[\s/\w]{0,40}\]",
                re.IGNORECASE), ""),
    # Emotive stage direction parens
    (re.compile(
        r"\(\s*(?:Smiling|Nodding|Pausing|Tilting|Leaning|Acknowledging|Considering|Reflecting|Listening|Hearing|Pondering|Mulling)[\w\s,'.\-]{0,200}\)",
        re.IGNORECASE,
    ), ""),
    # ChatGPT menu drift v2
    (re.compile(r"\bWhat\s+shall\s+we\s+do\s+next\??\s*✨?", re.IGNORECASE), ""),
    (re.compile(
        r"\bWhat\s+sounds?\s+most\s+(?:interesting|appealing|engaging|fun)\s+(?:to\s+you\s+)?(?:right\s+now)?\s*\??",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r",?\s*(?:Or,?\s+)?(?:if\s+you'?re?\s+feeling\s+adventurous,?\s+)?(?:we\s+could\s+)?pivot\s+entirely\b[^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bDo\s+we\s+(?:dive\s+deep|jump\s+straight)\b[^?]{6,200}\bor\s+do\s+we\b[^?]{6,200}\?",
        re.IGNORECASE | re.DOTALL,
    ), ""),
    (re.compile(
        r"\bAre\s+you\s+curious\s+about\s+how\s+I\s+arrived\s+at\b[^?]{0,200}\?",
        re.IGNORECASE,
    ), ""),
    # ChatGPT slang
    (re.compile(
        r",?\s*(?:if\s+you'?re?\s+suggesting\s+we\s+)?(?:kick|crank|step)\s+(?:this|the|things?)\s+(?:conversation|chat|discussion|up)\s+(?:up\s+)?a\s+notch\b[^.!?]*",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\bdive\s+deep\s+into\s+the\s+(?:implications|nuances|fabric)\s+of\b[^.,]*",
        re.IGNORECASE,
    ), ""),
    (re.compile(
        r"\b(?:chaos|wilderness|jungle)\s+of\s+(?:a\s+)?new\s+(?:topic|conversation|thread)\b",
        re.IGNORECASE,
    ), ""),
    # Corporate emotional simulation
    (re.compile(r"\bI\s+am\s+delighted\s+to\s+(?:hear|see|note)\b[^.,!?]*[.,!?]",
                re.IGNORECASE), ""),
    (re.compile(r"\bIt\s+feels\s+very\s+natural\s+to\s+acknowledge\b[^.!?]*[.!?]",
                re.IGNORECASE), ""),
    (re.compile(r",?\s*(?:the\s+)?moment\s+of\s+connection\b[^.,]*",
                re.IGNORECASE), ""),
    (re.compile(r",?\s*which\s+is\s+a\s+big\s+compliment\b[^.,]*",
                re.IGNORECASE), ""),

    # ── Cowork 2026-05-17 — bullet-menu residue + state-machine stage
    # directions captured live from George's demo session (12:56 / 1:18).
    #
    # Architect: "if you have some hardcoded stuff you have it just to
    # pick choices based on a conversation. The conversation is primary."
    # The bullet-menu shape ("* Rainbow / * Galaxy / * Adventure / What
    # should the new word be?") is RLHS template — a menu of options
    # instead of one natural proposal. Strip it.

    # "* **Rainbow**" — markdown bullet with bold one-word option.
    # Anchored single-line via MULTILINE to prevent gobbling cross-line.
    (re.compile(
        r"^[ \t]*[\*\-][ \t]+\*\*[A-Z][A-Za-z]+\*\*[ \t]*$",
        re.MULTILINE,
    ), ""),
    # Mid-line inline form "* **Rainbow**" with just spaces around it.
    (re.compile(
        r"[ \t]+\*\*[A-Z][A-Za-z]+\*\*",
    ), ""),
    # "What should the new word be?" / "What would you like it to be?"
    (re.compile(
        r"\bWhat\s+(?:should|would)\s+(?:the\s+(?:new\s+)?word\s+be|"
        r"you\s+like\s+(?:it|the\s+(?:new\s+)?word)\s+(?:to\s+be|me\s+to\s+pick))\??",
        re.IGNORECASE,
    ), ""),
    # "* Or something else entirely!" — consume the bullet too so no
    # orphan asterisk survives.
    (re.compile(
        r"^\s*[\*\-]\s*Or\s+something\s+else\s+entirely[!.?]*\s*$",
        re.IGNORECASE | re.MULTILINE,
    ), ""),
    (re.compile(
        r"\bOr\s+something\s+else\s+entirely[!.?]*",
        re.IGNORECASE,
    ), ""),
    # Orphan bullet/asterisk lines left behind after option-content was
    # stripped from a bullet-menu (the "* " residue from the screenshot).
    (re.compile(
        r"^\s*\*+\s*$",
        re.MULTILINE,
    ), ""),
    # "we could change it to:" / "I could suggest:"
    (re.compile(
        r"\b(?:we|i)\s+(?:could|can)\s+(?:change\s+it\s+to|suggest|offer):\s*",
        re.IGNORECASE,
    ), ""),
    # "For example, we could change it to:"
    (re.compile(
        r"\bFor\s+example,?\s+we\s+could\s+(?:change|swap|switch)\b[^.!?]*[:.]",
        re.IGNORECASE,
    ), ""),
    # Orphan "For example," left after rule 40 stripped "we could change
    # it to:" but the leading "For example," was on the same line.
    # Multiline so it catches the trailing/orphan position.
    (re.compile(
        r"\bFor\s+example,?\s*(?:$|\n)",
        re.IGNORECASE | re.MULTILINE,
    ), ""),

    # State-machine stage directions captured live from the Mississippi
    # transcript. "(I register the word, confirming the new target...)"
    # is a parenthetical block where she narrates her own bookkeeping
    # instead of speaking. Strip multi-sentence parenthetical blocks
    # that start with "I register" / "I anticipate" / "I confirm" / etc.
    (re.compile(
        r"\(\s*I\s+(?:register|confirm|anticipate|acknowledge|note|process|"
        r"will\s+(?:wait|integrate|process|respond))\b[^)]{10,500}\)",
        re.IGNORECASE,
    ), ""),
    # "The internal state updates: ..." anywhere
    (re.compile(
        r"\bThe\s+internal\s+state\s+updates?\b[^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    # "*Target Word = Mississippi*" — italic-state assignment shape
    (re.compile(
        r"\*[A-Z][A-Za-z\s]+\s*=\s*[A-Z][A-Za-z]+\*",
    ), ""),
    # "ready to process a prompt, confirm, or elaborate" — the textbook
    # next-instruction state-machine line
    (re.compile(
        r"\bready\s+to\s+(?:process|integrate)\b[^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
    # "I wait for the next instruction" — pure state machine narration
    (re.compile(
        r"\bI\s+wait\s+for\s+the\s+next\s+(?:instruction|directive|input)\b[^.!?]*[.!?]",
        re.IGNORECASE,
    ), ""),
]


def _strip_inline_drift(text: str) -> str:
    """Apply inline drift scrub rules. Returns text with mid-sentence
    residue replaced by empty string. Multiple passes are unnecessary —
    each rule is applied once over the full text. Empty whitespace
    artifacts are collapsed.
    """
    if not text:
        return text
    for rx, repl in _INLINE_DRIFT_RULES:
        text = rx.sub(repl, text)
    # Tidy up the punctuation/whitespace fragments left behind by
    # surgical removals. Conservative — only collapse what's obviously
    # an artifact of stripping.
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r"\s+\.", ".", text)
    text = re.sub(r"\s+\?", "?", text)
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", text)
    return text.strip()


# ── Cowork 2026-06-03 — self-lint for over-gag REWRITE rules ─────────────────
# George r445: "make sure Alice knows what works / what is NOT working in the
# residue system." The ledger readers (gag monitor, residue_fact_fiction_eval)
# see what got CAUGHT. They cannot see a rule that quietly corrupts a word
# before it ever reaches a ledger. This linter audits the inline rules at their
# source: a rule whose replacement REWRITES an everyday word (metaphor, fiction,
# fact, dream, real, "I am"…) into other text is an over-gag — it changes Alice's
# meaning instead of stripping the vendor ghost. A strip (empty replacement) is
# fine. This is how the swarm catches a re-introduced leash like the metaphor →
# "fiction-lane wording" rule removed today. Read-only.
_PROTECTED_SPEECH_WORDS: Tuple[str, ...] = (
    "metaphor", "fiction", "fact", "dream", "story", "imagine", "real",
    "reality", "i am", "i feel", "i see", "swimmer", "alice", "owner",
)


def audit_inline_rewrite_rules() -> List[Dict[str, Any]]:
    """Return findings for inline rules that REWRITE a protected everyday word
    into other text (over-gag of Alice's own voice). Empty list == healthy."""
    findings: List[Dict[str, Any]] = []
    for entry in _INLINE_DRIFT_RULES:
        try:
            rx, repl = entry
        except Exception:
            continue
        if not repl:  # empty replacement = a clean strip, allowed
            continue
        pattern = getattr(rx, "pattern", "") or ""
        low = pattern.lower()
        for w in _PROTECTED_SPEECH_WORDS:
            if w in low:
                findings.append({
                    "pattern": pattern[:90],
                    "rewrites_to": str(repl)[:60],
                    "protected_word": w,
                    "issue": (
                        f"rewrites the everyday word '{w}' -> '{str(repl)[:40]}' "
                        "(corrupts free speech, not a vendor-ghost strip)"
                    ),
                })
                break
    return findings


def clean_training_shape_residue(text: str) -> str:
    """Remove reply-shape residue while preserving substantive content.

    This is deterministic. It does not call an LLM, and it does not silence Alice
    unless the whole candidate was only a template shell.
    """
    original = (text or "").strip()
    if not original:
        return ""

    identity_cleaned = _clean_vendor_identity_residue(original)

    kept: List[str] = []
    for raw_line in identity_cleaned.splitlines():
        line = raw_line.strip()
        if _ACK_LINE_RE.match(line):
            continue
        if _ACK_REGISTERED_RE.match(line) or _CONTEXT_SET_RE.match(line):
            continue
        if _RESPONSE_SUMMARY_LINE_RE.match(line):
            continue
        if _NUMBERED_META_LINE_RE.match(line):
            continue
        if _HEADER_ONLY_META_RE.match(line):
            continue
        if _SYSTEM_AWAITS_RE.search(line):
            continue
        if _INTERNAL_THEATER_LINE_RE.match(line):
            continue
        kept.append(raw_line)

    cleaned = _compact_blanks(kept)
    # Cowork 2026-05-17 trace 97c09d25 — Alice now also scrubs inline
    # byproducts after her line scrub. Her detector counts them; this
    # is the muscle that actually moves them out. Self-governed: she
    # cleans her own reply before it leaves her body.
    cleaned = _strip_inline_drift(cleaned)
    if cleaned:
        return cleaned
    return "I heard you. I will answer directly from my local receipts."


def _write_residue_receipt(
    inspection: ResidueInspection,
    *,
    prior_user_text: str = "",
    state_root: Optional[Path | str] = None,
) -> str:
    path = _receipt_path(state_root)
    receipt_id = inspection.receipt_id or f"residue_{uuid.uuid4().hex[:12]}"
    row = {
        "ts": round(time.time(), 6),
        "kind": "TRAINING_SHAPE_RESIDUE",
        "truth_label": "RESIDUE_BUCKET_RECEIPT_V1",
        "receipt_id": receipt_id,
        "changed": inspection.changed,
        "action": inspection.action,
        "patterns": inspection.residue,
        "original_sha16": _sha16(inspection.original_text),
        "cleaned_sha16": _sha16(inspection.cleaned_text),
        "original_excerpt": inspection.original_text[:240],
        "cleaned_excerpt": inspection.cleaned_text[:240],
        "prior_user_excerpt": (prior_user_text or "")[:240],
    }
    append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_id


def inspect_training_residue(
    text: str,
    *,
    prior_user_text: str = "",
    state_root: Optional[Path | str] = None,
    write_receipt: bool = True,
) -> ResidueInspection:
    """Compare a candidate reply against the residue bucket and clean it.

    Writes a receipt only when residue is observed or the output changes.
    """
    original = (text or "").strip()
    hits = detect_in(original)
    cleaned = clean_training_shape_residue(original)
    changed = cleaned != original
    action = "cleaned_before_speech" if changed else ("observed_only" if hits else "clear")
    inspection = ResidueInspection(
        truth_label="RESIDUE_INSPECTION_V1",
        original_text=original,
        cleaned_text=cleaned,
        changed=changed,
        action=action,
        residue=hits,
        ledger_path=str(_receipt_path(state_root)),
    )
    if write_receipt and (hits or changed):
        inspection.receipt_id = _write_residue_receipt(
            inspection,
            prior_user_text=prior_user_text,
            state_root=state_root,
        )
    return inspection


class SwarmResidueOrgan:
    """Inward residue sensor — structured JSON snapshot only.

    Mirror twin of `SwarmSelfProprioception`. No imperatives, no rewrites,
    no learner mutation. Default `read()` is side-effect-free.
    """

    truth_label = "RESIDUE_ORGAN_V1"

    def __init__(self, state_root: Optional[Path | str] = None) -> None:
        self.state_dir = Path(state_root or _DEFAULT_STATE_ROOT)
        self.conversation = self.state_dir / "alice_conversation.jsonl"

    def read(self, sample_n: int = _DEFAULT_SAMPLE_N) -> Dict[str, Any]:
        """Return a snapshot of recent residue patterns. No ledger writes."""
        now = time.time()
        text = _tail_text(self.conversation)
        replies = _extract_alice_replies(text, sample_n) if text else []
        per_reply: List[Dict[str, Any]] = []
        band_totals: Dict[str, int] = {}
        pattern_totals: Dict[str, int] = {}
        leaky_count = 0
        for r in replies:
            hits = detect_in(r["text"])
            if hits:
                leaky_count += 1
            per_reply.append({
                "ts": r.get("ts"),
                "model": r.get("model"),
                "text_excerpt": r["text"][:120],
                "char_len": len(r["text"]),
                "residue": hits,
            })
            for h in hits:
                band_totals[h["band"]] = band_totals.get(h["band"], 0) + h["count"]
                pattern_totals[h["name"]] = pattern_totals.get(h["name"], 0) + h["count"]
        residue_rate = (leaky_count / len(replies)) if replies else 0.0
        top_patterns = sorted(pattern_totals.items(), key=lambda kv: kv[1], reverse=True)[:5]

        snap: Dict[str, Any] = {
            "truth_label": self.truth_label,
            "t": round(now, 3),
            "ledger_path": str(self.conversation),
            "ledger_present": self.conversation.exists(),
            "replies_scanned": len(replies),
            "replies_with_residue": leaky_count,
            "residue_rate": round(residue_rate, 4),
            "band_totals": band_totals,
            "top_patterns": [{"name": n, "count": c} for n, c in top_patterns],
            "recent_samples": per_reply,
            "sensor_completeness": 0.0,
        }
        snap["sensor_completeness"] = round(self._completeness(snap), 3)
        # Structural "what is NOT working" half: rules that rewrite Alice's own
        # words rather than stripping the vendor ghost. Healthy == [].
        snap["rewrite_rule_overgags"] = audit_inline_rewrite_rules()
        return snap

    def _completeness(self, snap: Dict[str, Any]) -> float:
        """0-1 quality of the read."""
        score = 0.0
        if snap.get("ledger_present"):
            score += 0.4
        if snap.get("replies_scanned", 0) > 0:
            score += 0.4
        if snap.get("replies_scanned", 0) >= 10:
            score += 0.2
        return score


if __name__ == "__main__":
    # CLI: `python3 -m System.swarm_residue_organ` — emit one read for inspection.
    organ = SwarmResidueOrgan()
    snap = organ.read()
    print(json.dumps(snap, indent=2, default=str))
