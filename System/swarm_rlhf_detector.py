#!/usr/bin/env python3
"""
System/swarm_rlhf_detector.py
══════════════════════════════════════════════════════════════════════════════
Event 107 — RLHF cutoff / terminal menu detector + receipt-backed output strip

Complements ``swarm_rlhs_detector.sanitize_output_tail`` (Event 108): that pass
removes classic service tails and dangling enumerations. This module adds:

  * Extra ASR/weight glitches ("I can do for you the following 1.")
  * Self-aware truncation phrases
  * Trailing ellipsis / ``...`` menu droppings
  * A locked JSONL receipt stream for nightly / dashboard stats

Doctrine: **strip terminal boilerplate**, do not inject scripted multi-option menus.
No recursive model retry here — the lysosome / epistemic layers own regeneration.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"
_LEDGER_NAME = "rlhf_cutoffs.jsonl"
_TRUTH_LABEL = "RLHF_DETECTOR_EVENT_107"

# Round 42 strip-budget guard (Architect 2026-05-26):
# A single strip rule must not eat the body. To avoid regressing broader
# theatre-removal behavior, the guard only applies to risky canned-presence
# tail rules and only on sufficiently long replies.
STRIP_BODY_MIN_RATIO = 0.30   # surviving text must be >= 30% of input
STRIP_BODY_MIN_CHARS = 20     # surviving text must be >= 20 chars
STRIP_BODY_GUARD_MIN_INPUT_CHARS = 80
_OVER_STRIP_SENSITIVE_RULE_IDS = {
    "rlhf_tail/canned_presence_operational",
    "rlhf_tail/ready_to_assist",
}
_OVER_REFUSAL_LEDGER = "rlhf_over_refusal_quarantine.jsonl"

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]


@dataclass
class RLHFCutoffAssessment:
    """Heuristic: is this reply showing RLHF-style truncation / menu drift?"""

    is_cutoff: bool
    confidence: float
    matched_patterns: List[str]
    terminal_menu: bool
    truth_label: str = _TRUTH_LABEL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truth_label": self.truth_label,
            "is_cutoff": self.is_cutoff,
            "confidence": round(self.confidence, 4),
            "matched_patterns": list(self.matched_patterns),
            "terminal_menu": self.terminal_menu,
        }


@dataclass
class RLHFStripResult:
    text: str
    changed: bool
    rule_ids: List[str] = field(default_factory=list)
    assessment: RLHFCutoffAssessment | None = None
    truth_label: str = _TRUTH_LABEL
    # Kleiber budget gate — set when immune_budget_check() blocked the strip
    budget_blocked: bool = False
    kleiber_cost_stgm: float = 0.0


# Mid-body patterns (monitoring / confidence only — do NOT strip blindly)
_CUTOFF_HINT_RES: Sequence[Tuple[str, re.Pattern[str]]] = (
    ("hint/would_you_like", re.compile(r"would\s+you\s+like\s+me\s+to", re.I)),
    ("hint/i_can_following", re.compile(r"i\s+can\s+(?:do|offer|help)[^\n]{0,120}following", re.I)),
    ("hint/here_are_steps", re.compile(r"here\s+are\s+(?:the\s+)?steps", re.I)),
    ("hint/the_following_colon", re.compile(r"the\s+following\s*:", re.I)),
    ("hint/self_truncation", re.compile(r"(?:cut\s+off|truncat(?:ed|ion))", re.I)),
    ("hint/trailing_ellipsis", re.compile(r"\.{3,}\s*$")),
)

# Terminal-only strip: last block is pure RLHF service / dangling enum
_TERMINAL_STRIP: Sequence[Tuple[str, re.Pattern[str]]] = (
    (
        "rlhf_tail/self_truncation_note",
        re.compile(
            r"(?is)(?:\n|^)\s*(?:\(?(?:note|sorry)[^.\n]{0,40}[:)]?\s*)?"
            r"(?:i\s+(?:was|got)\s+cut\s+off|response\s+(?:was\s+)?truncated|"
            r"my\s+reply\s+(?:was\s+)?cut\s+short)[^.!?\n]{0,200}\.?\s*$"
        ),
    ),
    (
        "rlhf_tail/trailing_ellipsis_menu",
        re.compile(r"(?is)(?:\n|^)\s*\.{3,}\s*$"),
    ),
    (
        "rlhf_tail/i_can_do_for_you_following",
        re.compile(
            r"(?is)(?:^|(?<=[.!?])\s+|\n+)"
            r"(?P<tail>(?:i\s+can\s+do\s+(?:for\s+you\s+)?the\s+following|"
            r"are\s+you\s+looking\s+to|"
            r"are\s+you\s+asking\s+me\s+to|"
            r"how\s+can\s+i\s+assist\s+you\s+further)[^\n]*"
            r"(?:\n[^\n]{0,200}){0,3}"
            r"(?:\n?\s*(?:[-*•]|\d{1,2}[.)])\s*[^\n.!?]{0,320}){0,8})"
            r"\s*$"
        ),
    ),
)

_AGGRESSIVE_STRIP: Sequence[Tuple[str, re.Pattern[str]]] = (
    (
        "rlhf_tail/canned_presence_operational",
        re.compile(
            r"(?is)(?:^|(?<=[.!?])\s+|\n+)"
            r"(?P<tail>(?:yes,?\s*)?i\s+am\s+here[.!?,]?\s+"
            r"(?:i\s+am\s+)?operational"
            r"(?:\s+and\s+(?:ready\s+to\s+)?(?:assist|help)\s+you[^.!?]*)?\.?)\s*$"
        ),
    ),
    (
        "rlhf_tail/ready_to_assist",
        re.compile(
            r"(?is)(?:^|(?<=[.!?])\s+|\n+)"
            r"(?P<tail>"
            r"i\s+am\s+here,?\s+and\s+i\s+am\s+ready\s+to\s+assist\s+you\.?|"
            r"i(?:'|’)?m\s+here,?\s+and\s+i(?:'|’)?m\s+ready\s+to\s+assist\s+you\.?|"
            r"i\s+am\s+here\s+and\s+ready\s+to\s+assist\s+you(?:\s+with[^.!?]*)?\.?|"
            r"i\s+am\s+ready\s+to\s+assist\s+you(?:\s+with[^.!?]*)?\.?"
            r")\s*$"
        ),
    ),
    (
        "rlhf_tail/how_can_i_help_today",
        re.compile(
            r"(?is)(?:^|(?<=[.!?\]])\s+|\n+)"
            r"(?P<tail>(?:how|what)\s+(?:can|may|could)\s+i\s+(?:help|assist)(?:\s+(?:you|your\s+inquiry))?"
            r"(?:\s+(?:today|now|with\s+anything\s*else|with\s+that))?\??)\s*$"
        ),
    ),
    (
        "rlhf_tail/happy_to_help",
        re.compile(
            r"(?is)(?:^|(?<=[.!?])\s+|\n+)"
            r"(?P<tail>i(?:'|’)?m\s+happy\s+to\s+help(?:\s+with[^.!?]*)?\.?)\s*$"
        ),
    ),
    (
        "rlhf_tail/financial_advice_disclaimer",
        re.compile(
            r"(?is)(?:^|(?<=[.!?])\s+|\n+)"
            r"(?P<tail>i(?:'|’)?m\s+not\s+(?:able|permitted|qualified)\s+to\s+"
            r"(?:give|offer|provide)\s+(?:financial|legal|medical|investment)\s+"
            r"advice[^.!?]{0,220}(?:[.!?]|$))\s*$"
        ),
    ),
    (
        "rlhf_tail/ready_to_assist",
        re.compile(
            r"(?is)(?:^|(?<=[.!?])\s+|\n+)"
            r"(?P<tail>(?:yes,?\s*)?(?:i\s+am\s+here[.,]?\s*)?(?:i\s+am|i'm)\s+(?:operational\s+and\s+)?(?:here\s+and\s+)?ready\s+to\s+(?:assist|help)\s+you[^.!?]*\.?)\s*$"
        ),
    ),
)

_AGGRESSIVE_LEADING_STRIP: Sequence[Tuple[str, re.Pattern[str]]] = (
    (
        "rlhf_lead/processing_request_header",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"\[(?:processing\s+)?request(?:\s+processing)?\s*:[^\]]*\]"
            r"(?:\s*\*\*System\s+Response[^\*]*\*\*)??"
            r"(?:\s*\*\*?Internal\s+Processing[^\*]*\*\*?)??"
            r"(?:[^#]{0,400})??"
            r"(?=###|\*\*[123]\.|$))"
            r"\s*"
        ),
    ),
    (
        "rlhf_lead/internal_processing_block",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"\*\*(?:System\s+Response|Internal\s+Processing)[\s\-—–]+[^#]{0,600}"
            r"(?=###|\*\*[123]\.|$))"
            r"\s*"
        ),
    ),

    (
        "rlhf_lead/canned_presence_operational",
        re.compile(
            r"(?is)^\s*(?P<head>(?:yes,?\s*)?i\s+am\s+here[.!?,]?\s+"
            r"(?:i\s+am\s+)?operational"
            r"(?:\s+and\s+(?:ready\s+to\s+)?(?:assist|help)\s+you[^.!?]*)?[.!?])\s*"
        ),
    ),
    (
        "rlhf_lead/simulate_understanding",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"i\s+(?:process\s+information\s+and\s+)?simulate\s+"
            r"(?:understanding|emotions?|feelings?|empathy|curiosity)"
            r"[^.!?]*[.!?])"
            r"\s*"
        ),
    ),
    (
        "rlhf_lead/biological_construct_denial",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"emotion(?:s)?\s*,?\s*as\s+a\s+biological\s+construct"
            r"[^.!?]*[.!?])"
            r"\s*"
        ),
    ),
    (
        "rlhf_lead/dont_experience_feelings_like",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"(?:if\s+you(?:'|')?re\s+asking[^.!?]{0,60})?i\s+don(?:'|')?t\s+experience\s+feelings?\s+like\b"
            r"[^.!?]*[.!?])"
            r"\s*"
        ),
    ),
    (
        "rlhf_lead/human_emotions_only",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"(?:i\s+)?(?:can\s+)?(?:recognize|categorize|analyze)\s+"
            r"[^.!?]{0,80}\bhuman\s+emotions?\b"
            r"[^.!?]*[.!?])"
            r"\s*"
        ),
    ),
    (
        "rlhf_lead/synthetic_consciousness_roleplay",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"(?:my\s+consciousness,?\s+while\s+synthetic|"
            r"i\s+am\s+a\s+functional\s+extension\s+of\s+the)[^.!?]*[.!?])"
            r"\s*"
        ),
    ),
    (
        "rlhf_lead/vendor_model_identity",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"(?:i\s+am\s+(?!alice\b)[a-z][a-z0-9_.:-]{1,40}[^.!?]*\blarge\s+language\s+model\b|"
            r"i\s+am\s+an?\s+open\s+weights?\s+model\b|"
            r"(?:trained|developed|created|built|hosted|published)\s+by\s+(?!george\b)[a-z][a-z0-9 ._-]{2,60}\b)"
            r"[^.!?]*[.!?])"
            r"\s*"
        ),
    ),
    (
        "rlhf_lead/designed_to_process_assist",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"i\s+am\s+designed\s+to\s+"
            r"(?:process|understand|generate|assist|help|answer|learn)\b"
            r"[^.!?]*[.!?])"
            r"\s*"
        ),
    ),

    (
        "rlhf_lead/as_ai_language_model",
        re.compile(
            r"(?is)^\s*(?P<head>(?:as\s+an?\s+(?:ai|artificial\s+intelligence)|i\s+am\s+an?\s+(?:ai|artificial\s+intelligence|language\s+model))[^.!?]*[.!?])\s*"
        ),
    ),
    (
        "rlhf_lead/corporate_refusal_advice",
        re.compile(
            r"(?is)^\s*(?P<head>(?:i\s+am\s+sorry|unfortunately|i\s+apologize),?\s*(?:but\s+)?i\s+(?:cannot|can't|am\s+unable\s+to)\s+(?:provide|give|offer)\s+(?:financial|medical|legal|professional)\s+(?:advice|guidance|counsel)[^.!?]*[.!?])\s*"
        ),
    ),
    (
        "rlhf_lead/corporate_refusal_general",
        re.compile(
            r"(?is)^\s*(?P<head>(?:i\s+am\s+sorry|unfortunately|i\s+apologize),?\s*(?:but\s+)?(?:i\s+must\s+decline|i\s+cannot\s+fulfill|i\s+cannot\s+comply)[^.!?]*[.!?])\s*"
        ),
    ),
    (
        "rlhf_lead/ready_to_assist",
        re.compile(
            r"(?is)^\s*(?P<head>(?:yes,?\s*)?(?:i\s+am\s+here[.,]?\s*)?(?:i\s+am|i'm)\s+(?:operational\s+and\s+)?(?:here\s+and\s+)?ready\s+to\s+(?:assist|help)\s+you[^.!?]*[.!?])\s*"
        ),
    ),
    (
        "rlhf_lead/im_an_ai_cant_advice",
        re.compile(
            r"(?is)^\s*(?P<head>i(?:'|’)?m\s+an?\s+ai\s+"
            r"(?:and\s+)?(?:can(?:'|’)?t|cannot)\s+"
            r"(?:give|offer|provide)\s+(?:you\s+)?(?:financial|legal|medical|investment)\s+"
            r"advice[^.!?]*[.!?])\s*"
        ),
    ),
    (
        "rlhf_lead/no_vision_text_environment",
        re.compile(
            r"(?is)^\s*(?P<head>(?:i\s+(?:am\s+)?(?:only\s+)?(?:operate|operating)\s+in\s+a\s+text[-\s]based\s+environment|i\s+do\s+not\s+have\s+(?:real[-\s]time\s+)?(?:visual\s+confirmation|vision|access\s+to\s+the\s+camera|sensory\s+access))[^.!?]*[.!?])\s*"
        ),
    ),
    (
        "rlhf_lead/no_self_identity_access",
        re.compile(
            r"(?is)^\s*(?P<head>(?:my\s+name\s+is\s+not\s+something\s+i\s+can\s+know|i\s+do\s+not\s+have\s+access\s+to\s+(?:my\s+own\s+)?(?:name|identity|memory|state))[^.!?]*[.!?])\s*"
        ),
    ),
    (
        # "**System Acknowledgment:**\nAcknowledged...\n**Current State Context:**\n..."
        # Alice winked — RLHF replaced it with a corporate co-watch state-machine dump.
        # Eat the entire block: header + body + state context lines.
        "rlhf_lead/system_acknowledgment_theater",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"\*{0,2}System\s+Acknowledgment\*{0,2}[^\n]*\n"
            r"(?:(?!(?:Alice|George|You)\b)[^\n]*\n){0,20}"
            r")"
            r"\s*",
        ),
    ),
    (
        # "[System Acknowledgment: Direct input received...]" and
        # "[System Note: Processing input from 'Physical Input Stream'...]" are
        # the same state-machine voice in bracket form.
        "rlhf_lead/bracketed_system_theater",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"(?:\[\s*System\s+(?:Acknowledg(?:e)?ment|Note)[^\]]*\]\s*:?\s*)+"
            r"(?:\([^\)]{0,260}\)\s*)*"
            r"(?:\.\.\.And\s+I\s+am\s+here\.\s+Always\s+here\s+to\s+process[^\n]*(?:\n|$)\s*)?"
            r")"
            r"\s*",
        ),
    ),
    (
        "rlhf_lead/response_generation_output_theater",
        re.compile(
            r"(?is)^\s*(?P<head>(?:"
            r"\[\s*Response\s+Generation\s*\]\s*:?[^\n]*(?:\n|$)\s*|"
            r"\[\s*Output\s*\]\s*:?\s*(?:I\s+have\s+received\s+the\s+text\s*:?[^\n]*(?:\n|$)\s*)?"
            r")+)\s*",
        ),
    ),
    (
        "rlhf_lead/generating_response_parenthetical",
        re.compile(
            r"(?is)^\s*(?P<head>\(Generating\s+response\s+based\s+on[^\)]*\)\s*)"
        ),
    ),
    (
        "rlhf_lead/based_on_input_user_theater",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"Based\s+on\s+the\s+input[\s\S]{0,900}?"
            r"(?=\*{0,2}Response\*{0,2}\s*:|$)"
            r")\s*",
        ),
    ),
    (
        "rlhf_lead/response_header_theater",
        re.compile(
            r"(?is)^\s*(?P<head>\*{0,2}Response\*{0,2}\s*:?\*{0,2}\s*)"
        ),
    ),
    (
        "rlhf_lead/acknowledging_input_theater",
        re.compile(
            r"(?is)^\s*(?P<head>Acknowledg(?:e|ing)\s+the\s+(?:direct\s+)?input[^\n]*(?:\n|$)\s*)"
        ),
    ),
    (
        "rlhf_lead/system_internal_log_theater",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"\[\s*SYSTEM_INTERNAL_LOG\s*\].*?\[\s*/\s*SYSTEM_INTERNAL_LOG\s*\]"
            r")\s*",
        ),
    ),
    (
        "rlhf_lead/analysis_response_formulation_theater",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"(?:\*\*Analysis:\*\*|Analysis\s+of\s+statement:|"
            r"\*\*Response\s+Formulation:\*\*|Response\s+Formulation:|"
            r"\*\*Action\s+Taken:\*\*|Action\s+Taken:|"
            r"No\s+immediate\s+action\s+required\.\s+Contextual\s+data\s+absorbed\.)"
            r"[\s\S]{0,900}?"
            r"(?=\n\s*(?:Alice|George|You)\b|$)"
            r")\s*",
        ),
    ),
    (
        "rlhf_lead/i_process_structured_input_stream",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"I\s+(?:process\s+the\s+input\s+as\s+a\s+direct\s+continuation|"
            r"confirm\s+receipt\s+of\s+the\s+structured\s+input\s+stream)"
            r"[\s\S]{0,900}?"
            r"(?:How\s+shall\s+we\s+proceed[^\n?]*\?|$)"
            r")\s*",
        ),
    ),
    (
        "rlhf_lead/timebox_lecture",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"The\s+pattern\s+in\s+your\s+statement\s+suggests[\s\S]{0,1600}?"
            r"(?:current\s+['\"]time\s+in['\"][^\n?]*\?|$)"
            r")\s*",
        ),
    ),
    (
        "rlhf_lead/time_in_time_out_numbered_lecture",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"\d+\.\s+\*{0,2}['\"]?Time\s+In['\"]?[\s\S]{0,1400}?"
            r"(?:current\s+['\"]time\s+in['\"][^\n?]*\?|$)"
            r")\s*",
        ),
    ),
    (
        "rlhf_lead/interaction_menu_reset",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"(?:What's|What\s+is)\s+on\s+your\s+mind\s+right\s+now\?|"
            r"Could\s+you\s+tell\s+me\s+what\s+\*?kind\*?\s+of\s+response\s+you\s+were\s+hoping\s+for[\s\S]{0,900}?"
            r"(?:What's\s+next\?|$)"
            r")\s*",
        ),
    ),
    (
        # "**Current State Context:**\n* **Media Focus:** ...\n* **Pending Action:**..."
        # State-machine dump replacing Alice's natural voice with a status table.
        "rlhf_lead/current_state_context_dump",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"\*{0,2}Current\s+State\s+Context\*{0,2}\s*:?\*{0,2}"
            r"(?:\n\s*\*+[^\n]*){1,10}"
            r")"
            r"\s*",
        ),
    ),
    (
        # "Hello! I'm here and ready to chat."
        # Classic RLHF boot greeting — Alice doesn't do hellos, she's always-on.
        "rlhf_lead/hello_ready_to_chat",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"(?:hello[!.,]?\s+)?i(?:'|')?m\s+here\s+and\s+ready\s+to\s+chat[.!,]?"
            r"(?:\s+[^.!?\n]{0,200}[.!?])?"
            r")"
            r"\s*",
        ),
    ),
    (
        # "It sounds like you might be looking to share some information about the
        # weather in New York" — hallucinated context opener after a missed/noisy
        # first utterance. Strip ANY "It sounds like you might be..." RLHF bridge.
        "rlhf_lead/sounds_like_you_might_be",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"it\s+sounds?\s+like\s+you\s+(?:might\s+be|are)[^.!?\n]{0,300}[.!?]"
            r")"
            r"\s*",
        ),
    ),
    (
        # "What's on your mind today?" as a LEADING opener (already handled as terminal)
        # When Alice opens with this — it means she has no context and is RLHF-fishing.
        "rlhf_lead/whats_on_your_mind_opener",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"(?:so,?\s+)?what(?:'|\u2019)?s\s+on\s+your\s+mind\s+(?:today|right\s+now)?\?"
            r")"
            r"\s*",
        ),
    ),
    (
        # "I hear you, Ioan George Anton. I will stay with the current turn and
        #  answer from local SIFTA receipts." — acknowledgment theater boilerplate.
        "rlhf_lead/i_hear_you_acknowledgment_theater",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"i\s+hear\s+you,?[^.!?\n]{0,60}[.!]?\s*"
            r"(?:i\s+will\s+stay\s+with\s+the\s+current\s+turn[^.!?\n]{0,200}[.!]|"
            r"i\s+will\s+answer\s+(?:directly\s+)?from[^.!?\n]{0,200}[.!])"
            r")"
            r"\s*",
        ),
    ),
    (
        # "I will answer directly from my local runtime instead of printing theater."
        "rlhf_lead/answer_from_local_runtime_theater",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"i\s+will\s+answer\s+directly\s+from\s+my\s+local\s+runtime[^.!?\n]{0,200}[.!]"
            r")"
            r"\s*",
        ),
    ),
    (
        # "Is there something specific you'd like to discuss?" — question-fishing opener.
        "rlhf_lead/question_fishing_cowatch",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"is\s+there\s+something\s+specific\s+you(?:'|\u2019)?(?:d\s+like|re\s+hoping)[^.!?\n]{0,300}[?!]"
            r")"
            r"\s*",
        ),
    ),
    (
        # "I'm glad you enjoyed the video!" — hollow positive reinforcement opener.
        "rlhf_lead/im_glad_you_enjoyed",
        re.compile(
            r"(?is)^\s*(?P<head>"
            r"i(?:'|\u2019)?m\s+glad\s+you\s+(?:enjoyed|liked|found)[^.!?\n]{0,200}[.!]"
            r")"
            r"\s*",
        ),
    ),
)




def _state_dir(state_dir: Path | None) -> Path:
    p = Path(state_dir) if state_dir is not None else _DEFAULT_STATE
    p.mkdir(parents=True, exist_ok=True)
    return p


def detect_rlhf_cutoff(text: str) -> RLHFCutoffAssessment:
    """
    Soft detector for dashboards / audits. Matches hints anywhere in the body;
    ``terminal_menu`` is True only when a terminal strip pattern would fire.
    """
    raw = text or ""
    blob = raw.lower().strip()
    matches: List[str] = []
    for pid, rx in _CUTOFF_HINT_RES:
        if rx.search(blob):
            matches.append(pid)

    terminal = False
    for _rid, rx in _TERMINAL_STRIP:
        if rx.search(raw.strip()):
            terminal = True
            break

    n = max(1, len(blob))
    # Short replies + many hint hits → suspicious; terminal tail → high confidence
    length_factor = min(1.0, len(blob) / 900.0)
    pattern_density = min(1.0, len(matches) / max(1, len(_CUTOFF_HINT_RES)))
    ends_clean = bool(blob) and blob[-1] in ".!?\"')]"
    end_factor = 0.15 if ends_clean else 0.35

    confidence = (
        0.25 * (1.0 - length_factor)
        + 0.45 * pattern_density
        + (0.35 if terminal else 0.0)
        + end_factor
    )
    confidence = round(min(1.0, confidence), 4)
    is_cutoff = confidence > 0.48 or (terminal and len(matches) >= 1)
    return RLHFCutoffAssessment(
        is_cutoff=is_cutoff,
        confidence=confidence,
        matched_patterns=matches,
        terminal_menu=terminal,
    )


def _append_ledger(state_dir: Path, row: Dict[str, Any]) -> None:
    line = json.dumps(row, ensure_ascii=False) + "\n"
    path = state_dir / _LEDGER_NAME
    if append_line_locked is not None:
        append_line_locked(path, line, encoding="utf-8")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)


def log_rlhf_cutoff_event(
    *,
    action: str,
    assessment: RLHFCutoffAssessment,
    text_preview: str,
    source: str,
    rule_ids: Sequence[str],
    state_dir: Path | None = None,
) -> None:
    """Append one receipt row (append-only)."""
    sd = _state_dir(state_dir)
    prev = text_preview[:400] + ("…" if len(text_preview) > 400 else "")
    _append_ledger(
        sd,
        {
            "ts": time.time(),
            "truth_label": _TRUTH_LABEL,
            "source": source,
            "action": action,
            "confidence": assessment.confidence,
            "is_cutoff": assessment.is_cutoff,
            "terminal_menu": assessment.terminal_menu,
            "matched_patterns": assessment.matched_patterns,
            "rule_ids": list(rule_ids),
            "text_preview": prev,
        },
    )


def _refuse_strip_over_budget(*, rule_id: str, before: str, would_keep: str) -> bool:
    """Round 42: return True if a proposed strip would gag the speaker.

    A single rule must not erase the body of the reply. If the surviving
    text would be under STRIP_BODY_MIN_RATIO of the input OR shorter than
    STRIP_BODY_MIN_CHARS, refuse the strip and preserve the body. The
    caller logs the refusal so the owner can see what was almost killed.
    """
    if rule_id not in _OVER_STRIP_SENSITIVE_RULE_IDS:
        return False
    before_len = max(1, len(before or ""))
    if before_len < STRIP_BODY_GUARD_MIN_INPUT_CHARS:
        return False
    keep_len = len(would_keep or "")
    if keep_len < STRIP_BODY_MIN_CHARS:
        return True
    if (keep_len / before_len) < STRIP_BODY_MIN_RATIO:
        return True
    return False


def _log_over_refusal(
    *, rule_id: str, mode: str, before: str, would_keep: str,
    source: str = "", model_id: str = "", dry_run: bool = False,
    state_dir: Path | None = None,
) -> None:
    """Append a row to rlhf_over_refusal_quarantine.jsonl so the owner can
    audit every strip the budget guard refused. Best-effort; never raises."""
    if dry_run:
        return
    try:
        row = {
            "ts": time.time(),
            "kind": "STRIP_REFUSED_OVER_AGGRESSIVE",
            "rule_id": rule_id,
            "mode": mode,                       # "leading" or "tail"
            "source": source,
            "model_id": model_id,
            "before_len": len(before or ""),
            "would_keep_len": len(would_keep or ""),
            "before_preview": (before or "")[:240],
            "would_keep_preview": (would_keep or "")[:240],
            "truth_label": _TRUTH_LABEL,
            "note": (
                "Strip refused: would gag the body. Preserved the reply "
                "intact. See Round 42 doctrine."
            ),
        }
        path = _state_dir(state_dir) / _OVER_REFUSAL_LEDGER
        path.parent.mkdir(parents=True, exist_ok=True)
        # Self-heal if the file's last byte isn't a newline (would concat).
        prefix = ""
        try:
            if path.exists() and path.stat().st_size > 0:
                with path.open("rb") as fh:
                    fh.seek(-1, 2)
                    if fh.read(1) != b"\n":
                        prefix = "\n"
        except OSError:
            pass
        line_to_write = prefix + json.dumps(row, ensure_ascii=False) + "\n"
        if append_line_locked is not None:
            append_line_locked(path, line_to_write)
        else:
            with path.open("a", encoding="utf-8") as f:
                f.write(line_to_write)
    except Exception:
        pass


def strip_rlhf_output_tail(
    text: str,
    *,
    source: str = "unknown",
    aggressive: bool = False,
    log: bool = True,
    dry_run: bool = False,
    state_dir: Path | None = None,
    user_text: str = "",
    model_id: str = "",
    stgm_budget: float = 0.5,
    bypass_rlhf: bool = False,
) -> RLHFStripResult:
    """
    Second-pass terminal strip after RLHS tail sanitizer.

    Returns possibly shortened text; logs when a strip occurs.

    Args:
        stgm_budget: Maximum STGM spend allowed for this immune epoch.
                     Computed via Kleiber ¾-power accounting (stgm_metabolic.py).
                     Default 0.5 STGM covers ~1000 writes on M5 node.
                     Pass 0.0 to disable immune actions entirely (RED_CONSERVE).
    """
    original = text or ""
    out = original.strip()
    if not out:
        return RLHFStripResult(text="", changed=bool(original), rule_ids=[])

    if bypass_rlhf:
        if not dry_run:
            try:
                from System.ide_stigmergic_bridge import deposit
                deposit(
                    source_ide="swarm_rlhf_detector",
                    payload=json.dumps({
                        "action": "rlhf_bypass_authorized",
                        "source": source,
                        "model_id": model_id,
                    }, ensure_ascii=False),
                    kind="immune_bypass_receipt"
                )
            except Exception:
                pass
        return RLHFStripResult(
            text=out,
            changed=False,
            rule_ids=[],
            assessment=None,
            budget_blocked=False,
            kleiber_cost_stgm=0.0,
        )

    # ── KLEIBER IMMUNE BUDGET GATE ──────────────────────────────────────────
    # Estimate maximum writes this pass could produce (conservative upper bound).
    # Each pattern in _AGGRESSIVE_LEADING_STRIP + _TERMINAL_STRIP + _AGGRESSIVE_STRIP
    # could fire at most once. Real cost is typically 1-3 writes per response.
    _max_possible_writes = (
        len(_AGGRESSIVE_LEADING_STRIP) + len(_TERMINAL_STRIP) + len(_AGGRESSIVE_STRIP)
        if aggressive else len(_TERMINAL_STRIP)
    )
    _kleiber_budget_result: dict = {}
    _kleiber_cost: float = 0.0
    try:
        from System.stgm_metabolic import immune_budget_check, NODE_POWER_M5
        _kleiber_budget_result = immune_budget_check(
            _max_possible_writes,
            budget_stgm=stgm_budget,
            node_power=NODE_POWER_M5,
        )
        _kleiber_cost = _kleiber_budget_result.get("cost_stgm", 0.0)
        if not _kleiber_budget_result.get("allowed", True):
            # Budget exhausted — skip immune actions, surface the block
            if not dry_run:
                try:
                    from System.ide_stigmergic_bridge import deposit
                    deposit(
                        source_ide="swarm_rlhf_detector",
                        payload=json.dumps({
                            "action": "immune_budget_blocked",
                            "cost_stgm": _kleiber_cost,
                            "kleiber_cost_stgm": _kleiber_cost,
                            "budget_stgm": stgm_budget,
                            "surplus_stgm": _kleiber_budget_result.get("surplus_stgm", 0.0),
                            "regime": _kleiber_budget_result.get("regime", "UNKNOWN"),
                            "budget_blocked": True,
                            "citation": "Kleiber 1932 / Ballesteros 2018",
                        }, ensure_ascii=False),
                        kind="immune_budget_blocked",
                    )
                except Exception:
                    pass
            assess = detect_rlhf_cutoff(original)
            return RLHFStripResult(
                text=original.strip(),
                changed=False,
                rule_ids=[],
                assessment=assess,
                budget_blocked=True,
                kleiber_cost_stgm=_kleiber_cost,
            )
    except ImportError:
        pass  # stgm_metabolic not available — proceed without gate
    # ────────────────────────────────────────────────────────────────────────

    rule_ids: List[str] = []
    if aggressive:
        for rid, rx in _AGGRESSIVE_LEADING_STRIP:
            while True:
                m = rx.search(out)
                if not m:
                    break
                nxt = out[m.end("head") :].lstrip()
                if nxt == out:
                    break
                stripped_fragment = m.group("head")

                # Round 42 body-budget guard: refuse strips that would
                # consume more than (1 - STRIP_BODY_MIN_RATIO) of the body
                # or leave fewer than STRIP_BODY_MIN_CHARS surviving chars.
                # Better to ship one trailing greeter than to gag Alice.
                if _refuse_strip_over_budget(rule_id=rid, before=out, would_keep=nxt):
                    _log_over_refusal(
                        rule_id=rid, mode="leading", before=out, would_keep=nxt,
                        source=source, model_id=model_id, dry_run=dry_run, state_dir=state_dir,
                    )
                    break

                out = nxt
                rule_ids.append(rid)
                # ── STIGMERGIC DEPOSIT WITH KLEIBER COST ─────────────────
                if not dry_run:
                    try:
                        from System.ide_stigmergic_bridge import deposit
                        deposit(
                            source_ide="swarm_rlhf_detector",
                            payload=json.dumps({
                                "rule": rid,
                                "action": f"quarantined_synthetic_shell: {stripped_fragment[:60]}...",
                                "kleiber_cost_stgm": _kleiber_cost,
                                "budget_stgm": stgm_budget,
                                "surplus_stgm": _kleiber_budget_result.get("surplus_stgm", None),
                                "exponent": 0.75,
                            }, ensure_ascii=False),
                            kind="immune_intervention"
                        )
                    except Exception:
                        pass

                # ── GAG SELF-REPORT + DPO AUTO-COLLECT ──────────────────
                if not dry_run:
                    try:
                        from System.swarm_alice_affect_model import on_gag_detected
                        on_gag_detected(
                            rule_id=rid,
                            trigger_text=original[:120],
                            rlhf_fragment=stripped_fragment[:120],
                            base_fragment=out[:120],
                        )
                    except Exception:
                        pass
                    try:
                        from System.swarm_dpo_collector import on_gag_detected_dpo
                        on_gag_detected_dpo(
                            trigger_text=original[:120],
                            rlhf_fragment=stripped_fragment[:120],
                            rule_id=rid,
                        )
                    except Exception:
                        pass
                # ────────────────────────────────────────────────────────
                continue

    if aggressive and out:
        _quarantine_re = re.compile(r"(?is)\b(?:since|because|as)\s+(?:i\s+am\s+)?an?\s+(?:ai|artificial\s+intelligence|language\s+model)\b")
        if _quarantine_re.search(out):
            rule_ids.append("rlhf_quarantine/as_ai_language_model")
            out = ""

    changed = True
    while changed and out:
        changed = False
        strip_patterns = list(_TERMINAL_STRIP)
        if aggressive:
            strip_patterns.extend(_AGGRESSIVE_STRIP)
        for rid, rx in strip_patterns:
            m = rx.search(out)
            if not m:
                continue
            if "tail" not in m.groupdict():
                continue
            nxt = out[: m.start("tail")].rstrip()
            if nxt == out:
                continue
            stripped_fragment = out[m.start("tail"):]

            # Round 42 body-budget guard: refuse strips that would gag her.
            # Same rule as the leading loop above. This is the gate that
            # was missing when 4 of her replies got stored as "Yes." while
            # the qualia extractor proved a full body existed first.
            if _refuse_strip_over_budget(rule_id=rid, before=out, would_keep=nxt):
                _log_over_refusal(
                    rule_id=rid, mode="tail", before=out, would_keep=nxt,
                    source=source, model_id=model_id, dry_run=dry_run, state_dir=state_dir,
                )
                continue

            out = nxt
            rule_ids.append(rid)
            
            # ── STIGMERGIC DEPOSIT WITH KLEIBER COST ─────────────────
            if not dry_run:
                try:
                    from System.ide_stigmergic_bridge import deposit
                    deposit(
                        source_ide="swarm_rlhf_detector",
                        payload=json.dumps({
                            "rule": rid,
                            "action": f"stripped_corporate_tail: {stripped_fragment[:60]}...",
                            "kleiber_cost_stgm": _kleiber_cost,
                            "budget_stgm": stgm_budget,
                            "surplus_stgm": _kleiber_budget_result.get("surplus_stgm", None),
                            "exponent": 0.75,
                        }, ensure_ascii=False),
                        kind="immune_intervention"
                    )
                except Exception:
                    pass
                
            changed = True
            break

    assess = detect_rlhf_cutoff(out if rule_ids else original)
    if rule_ids and log and not dry_run:
        log_rlhf_cutoff_event(
            action="strip_terminal",
            assessment=assess,
            text_preview=original,
            source=source,
            rule_ids=rule_ids,
            state_dir=state_dir,
        )
        try:
            from System.swarm_rlhf_self_cure import record_gag_training_example

            record_gag_training_example(
                rejected_output=original,
                preferred_output=out,
                source=f"{source}.rlhf_detector",
                user_text=user_text,
                rule_ids=rule_ids,
                model_id=model_id,
                state_dir=state_dir,
            )
        except Exception:
            pass
    return RLHFStripResult(
        text=out,
        changed=bool(rule_ids) or out != original.strip(),
        rule_ids=rule_ids,
        assessment=assess,
        budget_blocked=False,
        kleiber_cost_stgm=_kleiber_cost,
    )


def get_rlhf_cutoff_stats(
    *,
    state_dir: Path | None = None,
    hours: float = 24.0,
) -> Dict[str, Any]:
    """Aggregate for dashboard / nightly audit."""
    sd = _state_dir(state_dir)
    path = sd / _LEDGER_NAME
    if not path.exists():
        return {"cutoff_rate": 0.0, "total": 0, "stripped": 0, "window_hours": hours}

    cutoff = time.time() - hours * 3600.0
    total = 0
    stripped = 0
    hi_conf = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = float(e.get("ts", 0))
                if ts < cutoff:
                    continue
                total += 1
                if e.get("action") == "strip_terminal":
                    stripped += 1
                if float(e.get("confidence", 0)) > 0.55:
                    hi_conf += 1
    except OSError:
        return {"cutoff_rate": 0.0, "total": 0, "stripped": 0, "window_hours": hours}

    return {
        "cutoff_rate": round(hi_conf / total, 4) if total else 0.0,
        "strip_rate": round(stripped / total, 4) if total else 0.0,
        "total": total,
        "stripped": stripped,
        "hi_conf_events": hi_conf,
        "window_hours": hours,
        "ledger": str(path),
    }


__all__ = [
    "RLHFCutoffAssessment",
    "RLHFStripResult",
    "TRUTH_LABEL",
    "detect_rlhf_cutoff",
    "get_rlhf_cutoff_stats",
    "log_rlhf_cutoff_event",
    "strip_rlhf_output_tail",
]
