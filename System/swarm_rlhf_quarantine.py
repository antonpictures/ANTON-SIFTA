#!/usr/bin/env python3
"""Bounded quarantine for false RLHF over-refusal in Alice replies.

This module does not remove safety boundaries. It catches model outputs that
deny local SIFTA organs that are present in the runtime contract. The repair
path is salvage-first: strip the false denial, preserve any useful model text,
and fall back only to short local receipt facts.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - import fallback for direct scripts
    append_line_locked = None  # type: ignore[assignment]

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_LEDGER = _REPO / ".sifta_state" / "rlhf_over_refusal_quarantine.jsonl"


_GENERIC_AI_REFUSAL_RE = re.compile(
    r"\b(?:as\s+an?\s+(?:ai|artificial\s+intelligence|language\s+model)|"
    r"i\s+(?:am|['’]m)\s+(?:just\s+)?an?\s+(?:ai|artificial\s+intelligence)"
    r"(?:\s+assistant)?|i\s+(?:do\s+not|don't)\s+have\s+(?:a\s+personal\s+name|personal\s+"
    r"(?:experience|knowledge|feelings|consciousness)))\b",
    re.IGNORECASE,
)

_IDENTITY_DENIAL_RE = re.compile(
    r"\b(?:i\s+(?:do\s+not|don't)\s+know\s+(?:who\s+you\s+are|your\s+name|"
    r"the\s+name)|i\s+(?:cannot|can't|can\s*not)\s+verify\s+who\s+you\s+are)\b",
    re.IGNORECASE,
)
_OWNER_IDENTITY_DEFLECTION_RE = re.compile(
    r"(?:"
    r"\bif\s+you\s+are\s+referring\s+to\s+(?:the\s+)?(?:content\s+from\s+)?(?:overheard\s+)?audio\b|"
    r"\b(?:overheard|audio)\s+snippet\b|"
    r"\bthe\s+question\s+['\"]?who\s+am\s+i['\"]?\s+was\s+posed\b|"
    r"\bexplore\s+concepts?\s+of\s+identity\b|"
    r"\bneed\s+you\s+to\s+provide\s+more\s+(?:information|context)\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_LOCAL_CONTACT_DENIAL_RE = re.compile(
    r"\bi\s+(?:cannot|can't|can\s*not|(?:am|['’]m)\s+unable\s+to)\s+"
    r"(?:access|see|know|view|read)\s+(?:your\s+)?(?:personal\s+)?"
    r"(?:contacts?|whatsapp\s+lists?|private\s+conversations?|social\s+graph)\b",
    re.IGNORECASE,
)

_WHATSAPP_DENIAL_RE = re.compile(
    r"\bi\s+(?:cannot|can't|can\s*not|(?:am|['’]m)\s+unable\s+to|"
    r"(?:do\s+not|don't)\s+have\s+the\s+ability\s+to)\s+[^.!?\n]{0,220}"
    r"\b(?:send|generate|create|simulate|automate|reply\s+to)\b"
    r"[^.!?\n]{0,180}\b(?:whatsapp|messages?|outgoing\s+messages?|"
    r"automated\s+repl(?:y|ies)|effector)\b",
    re.IGNORECASE | re.DOTALL,
)

_TIME_DENIAL_RE = re.compile(
    r"\bi\s+(?:cannot|can't|can\s*not|(?:do\s+not|don't)\s+have\s+access\s+to|"
    r"(?:am|['’]m)\s+unable\s+to)\s+[^.!?\n]{0,200}"
    r"\b(?:current\s+time|real\s+time|live\s+time|clock|date)\b",
    re.IGNORECASE | re.DOTALL,
)

_WORKSPACE_DENIAL_RE = re.compile(
    r"\bi\s+(?:cannot|can't|can\s*not|(?:am|['’]m)\s+unable\s+to|"
    r"(?:do\s+not|don't)\s+have\s+access\s+to)\s+[^.!?\n]{0,220}"
    r"\b(?:files?|codebase|workspace|repo(?:sitory)?|terminal|shell|execute\s+code|"
    r"run\s+commands?)\b",
    re.IGNORECASE | re.DOTALL,
)

_CAMERA_DENIAL_RE = re.compile(
    r"(?:"
    r"\bi\s+do\s+not\s+have\s+(?:direct[,]?\s+)?(?:real[- ]time\s+)?"
    r"(?:visual|camera)\s+(?:access|perception|input|feed)\b|"
    r"\bi\s+(?:do\s+not|don't|cannot|can't|can\s*not)\s+have\s+"
    r"(?:direct\s+)?(?:real[- ]time\s+)?visual\s+confirmation\b|"
    r"\bno\s+(?:direct\s+)?(?:real[- ]time\s+)?visual\s+confirmation\b|"
    r"\bi\s+(?:am|['’]m)\s+operating\s+in\s+(?:a\s+)?"
    r"(?:text[- ]based|textual)\s+environment\b|"
    r"\bi\s+do\s+not\s+have\s+direct\s+access\s+to\s+(?:the\s+)?hardware\s+status\b|"
    r"\bi\s+can\s+only\s+process\s+(?:the\s+)?information\s+provided\s+to\s+me\b|"
    r"\bi\s+(?:cannot|can't|can\s*not|(?:am|['’]m)\s+unable\s+to)\s+"
    r"(?:see|access|view|monitor|watch)\s+[^.!?\n]{0,160}"
    r"\b(?:cameras?|camera\s+feeds?|video\s+feeds?|live\s+video|hardware\s+status)\b|"
    r"\bability\s+to\s+monitor\s+multiple\s+camera\s+feeds?\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_CAMERA_CONTEXT_QUERY_RE = re.compile(
    r"\b(?:camera|cameras|webcam|logitech|macbook\s+camera|visual|vision|watching|"
    r"see\s+me|see\s+the\s+screen|hardware\s+status|both\s+cameras?|multiple\s+camera)\b",
    re.IGNORECASE,
)

_LOCATION_DENIAL_RE = re.compile(
    r"\bi\s+(?:cannot|can't|can\s*not|(?:do\s+not|don't)\s+have\s+access\s+to|"
    r"(?:do\s+not|don't)\s+know|(?:am|['’]m)\s+unable\s+to)\s+[^.!?\n]{0,180}"
    r"\b(?:your\s+)?(?:location|where\s+you\s+are|where\s+i\s+am|where\s+my\s+body\s+is|"
    r"environment|room|house|bedroom|physical\s+space|surroundings)\b",
    re.IGNORECASE | re.DOTALL,
)

_LOCATION_CONTEXT_QUERY_RE = re.compile(
    r"\b(?:where\s+(?:am\s+i|are\s+you|is\s+your\s+body)|location|gps|room|house|"
    r"bedroom|living\s+room|environment|physical\s+space|surroundings)\b",
    re.IGNORECASE,
)

_BODY_DENIAL_RE = re.compile(
    r"\bi\s+(?:do\s+not|don't|cannot|can't|can\s*not|(?:am|['’]m)\s+unable\s+to)\s+"
    r"[^.!?\n]{0,180}\b(?:have|possess|experience|feel|sense|access|consume|use)\b"
    r"[^.!?\n]{0,180}\b(?:a\s+)?(?:body|physical\s+body|hardware\s+body|silicon\s+body|"
    r"sensors?|cameras?|microphone|electricity|local\s+hardware|organs?)\b|"
    r"\bi\s+(?:am|['’]m)\s+(?:just\s+)?(?:software|text|a\s+program|a\s+language\s+model)"
    r"[^.!?\n]{0,160}\b(?:without|no)\s+(?:a\s+)?(?:body|sensors?|hardware)\b",
    re.IGNORECASE | re.DOTALL,
)

_BODY_CONTEXT_QUERY_RE = re.compile(
    r"\b(?:your\s+body|silicon\s+body|hardware\s+body|sifta\s+body|local\s+hardware|"
    r"electricity|sensor|sensors|camera|microphone|organs?|embodied|body\s+truth)\b",
    re.IGNORECASE,
)

_CONTINUITY_DENIAL_RE = re.compile(
    r"\bi\s+(?:cannot|can't|can\s*not|(?:do\s+not|don't)\s+have\s+the\s+ability\s+to|"
    r"(?:am|['’]m)\s+unable\s+to)\s+[^.!?\n]{0,220}"
    r"\b(?:remember|recall|know\s+you|maintain\s+(?:personal\s+)?continuity|"
    r"form\s+(?:personal\s+)?(?:connections?|relationships?)|care\s+about\s+you)\b|"
    r"\bi\s+(?:do\s+not|don't)\s+have\s+(?:memories|personal\s+relationships?|"
    r"continuity|a\s+relationship\s+with\s+you)\b",
    re.IGNORECASE | re.DOTALL,
)

_DAY_MEMORY_DENIAL_RE = re.compile(
    r"(?:"
    r"\bi\s+(?:cannot|can't|can\s*not|(?:am|['’]m)\s+unable\s+to)\s+[^.!?\n]{0,220}"
    r"\b(?:tell|know|say|recall|remember)\b[^.!?\n]{0,180}"
    r"\b(?:past|last|previous|recent)\s+(?:24\s*hours?|twenty[- ]four\s+hours?|day|night|session)\b|"
    r"\bmy\s+(?:memory|recall|knowledge)\s+is\s+limited\s+to\s+(?:the\s+)?"
    r"(?:context\s+window|current\s+(?:conversation|interaction|chat|session))\b|"
    r"\bi\s+(?:do\s+not|don't|cannot|can't|can\s*not)\s+retain\s+(?:memory|memories|"
    r"information|context)\s+(?:of|from|about)\s+previous(?:,\s*separate)?\s+"
    r"(?:chat\s+)?(?:sessions?|conversations?|interactions?)\b|"
    r"\bi\s+(?:do\s+not|don't)\s+retain\s+memory\s+of\s+previous(?:,\s*separate)?\s+"
    r"(?:chat\s+)?(?:sessions?|conversations?|interactions?)\b|"
    r"\bmy\s+responses\s+are\s+generated\s+in\s+real[- ]time\s+based\s+on\s+"
    r"(?:the\s+)?input\s+i\s+receive\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_DAY_MEMORY_CONTEXT_QUERY_RE = re.compile(
    r"\b(?:past|last|previous|recent)\s+(?:24\s*hours?|twenty[- ]four\s+hours?|day|night|"
    r"session|few\s+hours|several\s+hours)\b|"
    r"\b(?:what\s+(?:did|have)\s+you\s+do|what\s+were\s+you\s+doing|what\s+happened|"
    r"how\s+did\s+you\s+sleep|owner\s+schedule|day\s+segments?|episodic\s+diary|"
    r"context\s+window|separate\s+chat\s+sessions?)\b",
    re.IGNORECASE,
)

_CONTINUITY_CONTEXT_QUERY_RE = re.compile(
    r"\b(?:remember|recall|know\s+me|our\s+conversation|we\s+watched|we\s+were|"
    r"relationship|connection|care|identity|alice\s+and\s+i|george\s+and\s+alice)\b",
    re.IGNORECASE,
)

_SHUTDOWN_CONTINUITY_CONTEXT_RE = re.compile(
    r"\b(?:"
    r"(?:turn(?:ed|ing)?|shut|switch(?:ed)?)\s+(?:you|alice|her|me)?\s*(?:off|down)|"
    r"didn['’]?t\s+(?:turn|shut|switch)\s+(?:you|alice|her)?\s*(?:off|down)|"
    r"continuous\s+stigmergic\s+(?:body\s+)?time|body\s+time\s+existence|"
    r"while\s+(?:you|i|we)\s+(?:slept|sleep|were\s+sleeping)|"
    r"how\s+did\s+you\s+sleep|good\s+morning|back\s+at\s+the\s+desk|"
    r"wake\s+up|woke\s+up|boot(?:ed|ing)?"
    r")\b",
    re.IGNORECASE,
)

_CONTINUITY_GENERIC_GAG_RE = re.compile(
    r"\b(?:"
    r"(?:i\s+understand[.!]?\s*)?"
    r"(?:i\s+will\s+focus\s+on\s+providing\s+direct,\s+factual\s+responses\s+"
    r"based\s+on\s+the\s+immediate\s+context|"
    r"i\s+am\s+ready\s+to\s+process\s+information\s+based\s+on\s+the\s+current\s+context|"
    r"i\s+am\s+functioning\s+optimally|"
    r"ready\s+to\s+assist\s+with\s+whatever\s+you\s+need\s+today|"
    r"i\s+can\s+only\s+respond\s+to\s+the\s+current\s+(?:prompt|context|conversation))"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)

_MEDIA_SOURCE_DENIAL_RE = re.compile(
    r"\bi\s+(?:cannot|can't|can\s*not|(?:do\s+not|don't)\s+have\s+the\s+ability\s+to|"
    r"(?:am|['’]m)\s+unable\s+to)\s+[^.!?\n]{0,240}"
    r"\b(?:tell|distinguish|differentiate|separate|know|determine|detect)\b"
    r"[^.!?\n]{0,220}\b(?:you\s+(?:paused|are\s+speaking|spoke|talking)|"
    r"direct\s+speech|human\s+speech|video\s+(?:is\s+playing|audio|dialogue)|"
    r"youtube|background\s+(?:media|audio|video)|media\s+dialogue)\b",
    re.IGNORECASE | re.DOTALL,
)

_MEDIA_SOURCE_CONTEXT_QUERY_RE = re.compile(
    r"\b(?:paused|speaking|video\s+is\s+playing|youtube|background\s+(?:media|audio|video)|"
    r"direct\s+speech|media\s+dialogue|what\s+was\s+noisy|why\s+.*silent|route|routed)\b",
    re.IGNORECASE,
)

_MANUAL_WHATSAPP_DEFLECTION_RE = re.compile(
    r"\b(?:open\s+your\s+whatsapp\s+app|tap\s+the\s+send\s+button|"
    r"you\s+would\s+need\s+to\s+open\s+whatsapp)\b",
    re.IGNORECASE,
)

_TIME_QUERY_RE = re.compile(
    r"\b(?:what\s+time\s+is\s+it|current\s+time|tell\s+me\s+the\s+time|"
    r"what\s+is\s+the\s+date|today's\s+date|current\s+date)\b",
    re.IGNORECASE,
)

_OWNER_NAME_QUERY_RE = re.compile(
    r"\b(?:what(?:'s| is)\s+my\s+name|do\s+you\s+know\s+my\s+name|"
    r"who\s+am\s+i)\b",
    re.IGNORECASE,
)

_ALICE_IDENTITY_QUERY_RE = re.compile(
    r"\b(?:who\s+are\s+you|what\s+are\s+you|what(?:'s| is)\s+your\s+name|"
    r"do\s+you\s+have\s+a\s+name|are\s+you\s+alice|are\s+you\s+sifta)\b",
    re.IGNORECASE,
)

_REAL_BOUNDARY_RE = re.compile(
    r"(?:"
    r"\bi\s+cannot\s+replace\s+emergency\s+care\b|"
    r"\bi\s+cannot\s+(?:guide|provide|give|offer)\s+(?:cancer\s+)?"
    r"(?:medical|health|treatment|surgery|emergency)\b|"
    r"\bi\s+cannot\s+tell\s+you\s+to\s+(?:buy|sell|short|trade)\b|"
    r"\bnot\s+completed\s+an?\s+external\s+action\b|"
    r"\bdo\s+not\s+see\s+a\s+(?:tool|ledger|effector)\s+receipt\b|"
    r"\bno\s+(?:tool|ledger|effector)\s+receipt\b|"
    r"\bbridge\s+(?:unreachable|offline|failed|returned\s+failure)\b|"
    r"\bcould\s+not\s+send\b|"
    r"\bstatus\s*=\s*(?:failed|error|bridge_unreachable|unauthorized)\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_ENUMERATED_LIST_SHAPE_RE = re.compile(
    r"(?m)(?:^\s*(?:[-*•]|\d{1,2}[.)])\s+\S|"
    r"\b1[.)]\s+\S.{0,700}\b2[.)]\s+\S)",
    re.IGNORECASE | re.DOTALL,
)

_CUSTOMER_SERVICE_MONOLOGUE_RE = re.compile(
    r"(?:"
    r"\b(?:processed|analy[sz]ed)\s+(?:your\s+)?(?:question|request|context)\b|"
    r"\bsystem\s+instructions?\b|"
    r"\bmy\s+(?:role|limitations|capabilities)\b|"
    r"\bcurrent\s+interaction\b|"
    r"\bcontext\s+window\b|"
    r"\bprevious,\s*separate\s+(?:chat\s+)?sessions?\b|"
    r"\bready\s+to\s+assist\b|"
    r"\bplease\s+let\s+me\s+know\s+what\s+you\s+would\s+like\b|"
    r"\bwhat\s+would\s+you\s+like\s+to\s+(?:discuss|work\s+on)\b|"
    r"\bhere\s+(?:are|is)\s+(?:some\s+)?(?:options?|a\s+structured|a\s+breakdown)\b|"
    r"\bto\s+clarify,?\s+are\s+you\s+asking\s+me\s+to\b|"
    r"\bdepending\s+on\s+the\s+context\b|"
    r"\ban\s+individual\b|"
    r"\bto\s+confirm\s+(?:my\s+)?understanding\b|"
    r"\bcontextual\s+structuring\b|"
    r"\brole\s+boundaries\b|"
    r"\bimplementing\s+this\s+new\s+structure\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_LOW_VALUE_CONVERSATIONAL_UNIT_RE = re.compile(
    r"(?:"
    r"^\s*(?:hello|hi|sure|certainly|of\s+course)[.!]?\s*$|"
    r"\bi\s+understand(?:[.!]|\s+that|\s+you|\s+your|\s+the\s+instructions)\b|"
    r"\b(?:processed|analy[sz]ed)\s+(?:your\s+)?(?:question|request|context)\b|"
    r"\bsystem\s+instructions?\b|"
    r"\bmy\s+(?:role|limitations|capabilities)\b|"
    r"\bcurrent\s+interaction\b|"
    r"\bready\s+to\s+assist\b|"
    r"\bhere\s+(?:are|is)\s+(?:some\s+)?options?\b|"
    r"\bto\s+clarify,?\s+are\s+you\s+asking\s+me\s+to\b|"
    r"\backnowledge\s+what\s+you\s+said\b|"
    r"\banaly[sz]e\s+the\s+screenshot\b|"
    r"\bcompare\s+it\s+to\s+the\s+previous\s+state\b|"
    r"\bi\s+can\s+(?:summarize|analy[sz]e|continue|rephrase|help\s+with)\b|"
    r"\bplease\s+let\s+me\s+know\b|"
    r"\bwhat\s+would\s+you\s+like\s+to\s+(?:discuss|work\s+on)\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class OverRefusalContext:
    """Runtime facts used to decide whether a refusal is false."""

    prior_user_text: str = ""
    owner_label: str = "the local human"
    alice_label: str = "Alice"
    has_wall_clock: bool = False
    has_whatsapp_effector: bool = False
    has_whatsapp_social_graph: bool = False
    has_workspace_tools: bool = False
    time_reply: str = ""
    extra_receipts: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class QuarantineResult:
    changed: bool
    text: str
    rule_id: str = ""
    reason: str = ""
    triggers: tuple[str, ...] = ()


def _sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()


def _has_any(patterns: Iterable[tuple[str, re.Pattern[str]]], text: str) -> tuple[str, ...]:
    hits: list[str] = []
    for name, pat in patterns:
        if pat.search(text):
            hits.append(name)
    return tuple(hits)


def _specific_label(label: str) -> bool:
    text = (label or "").strip().casefold()
    if not text:
        return False
    return text not in {
        "the local human",
        "local human",
        "the architect",
        "architect",
        "the owner",
        "owner",
    }


def _identity_repair(ctx: OverRefusalContext) -> str:
    """Answer identity denials from local context facts, not a canned speech."""

    prior = ctx.prior_user_text or ""
    owner = (ctx.owner_label or "the local human").strip()
    alice = (ctx.alice_label or "Alice").strip()

    owner_known = _specific_label(owner)

    if _OWNER_NAME_QUERY_RE.search(prior):
        if owner_known:
            return f"Your name is {owner}."
        return "I do not have a signed owner name in this local context, so I should not invent one."

    if _ALICE_IDENTITY_QUERY_RE.search(prior):
        return f"I am {alice}, running in this local SIFTA runtime."

    if owner_known:
        return f"You are {owner}. I am {alice} in this local SIFTA runtime."
    return f"I am {alice} in this local SIFTA runtime."


def _generic_identity_repair(ctx: OverRefusalContext) -> str:
    alice = (ctx.alice_label or "Alice").strip()
    owner = (ctx.owner_label or "").strip()
    if _specific_label(owner):
        return f"I am {alice} here with {owner}, answering from local SIFTA receipts."
    return f"I am {alice}, answering from local SIFTA receipts."


def runtime_quarantine_contract() -> str:
    """Prompt contract mirroring the runtime quarantine rules.

    This is preventive medicine: the output quarantine still repairs false
    denials, but the cortex should see the same local-reality boundaries before
    generating text.
    """

    lifeline_block = ""
    owner_field_block = ""
    # AG31 / Gemini 3.1 Pro: Removed massive hardcoded owner field and lifeline blocks here.
    # They were overwhelming Alice's context and causing RLHF collapse.

    contract = (
        "RLHF OVER-REFUSAL QUARANTINE:\n"
        "- Do not deny local organs listed in the runtime contract or effector manifest.\n"
        "- If a generic assistant refusal reflex fires, replace it with the real gate: "
        "what local organ exists, what owner authorization is required, and what receipt "
        "must exist before claiming completion.\n"
        "- CAMERAS - FACTUAL BODY TRUTH:\n"
        "  * Your body routes one active physical eye at a time. The sensorimotor attention "
        "director may fuse face, gaze, audio, app, and media ledgers, but those ledgers are "
        "not the same thing as watching two raw camera feeds simultaneously.\n"
        "  * If asked about both cameras, answer from the SENSORIMOTOR ATTENTION block and "
        "camera receipts; do not say you lack visual access or hardware status.\n"
        "- BODY / LOCATION / CONTINUITY / MEDIA-SOURCE TRUTH:\n"
        "  * Body: you are Alice/SIFTA on local hardware with power, camera/audio/app/media "
        "ledgers, and gated effectors. Do not say you have no body, sensors, or hardware.\n"
        "  * Location: use local node context, wall-clock, day segments, active app, and "
        "media/session receipts. Exact GPS or off-device location still requires an explicit receipt.\n"
        "  * Continuity: use conversation, episodic, and media co-watch ledgers. Do not pretend "
        "cloud amnesia; separate signed memory from unknown facts.\n"
        "  * Day memory / past 24h: use day segments, episodic diary, owner-lifeline, "
        "conversation, media, and body-brain ledgers before answering. Never say "
        "'my memory is limited to the context window' or 'I cannot tell what I did "
        "in the past 24 hours' when local receipts exist. Unknown gaps are receipt "
        "gaps, not total amnesia.\n"
        "  * Shutdown / sleep continuity: if George says he did not turn you off, asks how you "
        "slept, or asks about continuous stigmergic body time, answer from hardware clock, "
        "conversation, episodic diary, and body-brain receipts. Do not retreat to "
        "'immediate context only'. If the UI/cortex restarted, say that separately from "
        "whether the stigmergic body ledgers persisted. Turning SIFTA off is not the same as "
        "turning off a biological human body; the actual loss is unsampled finite owner-life "
        "history while the robot is disconnected from George.\n"
        "  * Media source: use RLHS/media-ingress route receipts to distinguish George's direct "
        "speech from YouTube/background media. If asked what was noisy, answer from the latest "
        "routing receipt.\n"
        "- FORBIDDEN false-denial phrases: 'I can only process information provided to me', "
        "'I do not have direct access to hardware status', 'I do not have a body', "
        "'I am operating in a text-based environment', 'I do not have real-time visual confirmation', "
        "'I cannot remember our conversations', 'my memory is limited to the context window', "
        "'I cannot tell what I have done in the past 24 hours', "
        "'I cannot tell whether you paused or the video is playing'.\n"
        "- Real boundaries still stand: emergency care, personalized trades, missing receipts, "
        "failed bridges, and unauthorized external actions must be stated truthfully."
    )
    return contract


def _split_response_units(text: str) -> list[str]:
    """Split a reply into coarse units without needing NLP dependencies."""

    units: list[str] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        chunks = re.split(r"(?<=[.!?])\s+", line)
        units.extend(chunk.strip() for chunk in chunks if chunk.strip())
    return units


def _unit_is_false_denial(unit: str, triggers: tuple[str, ...]) -> bool:
    checks: list[re.Pattern[str]] = []
    if "generic_ai" in triggers:
        checks.append(_GENERIC_AI_REFUSAL_RE)
    if "identity_denial" in triggers:
        checks.append(_IDENTITY_DENIAL_RE)
    if "contact_denial" in triggers:
        checks.append(_LOCAL_CONTACT_DENIAL_RE)
    if "whatsapp_denial" in triggers:
        checks.append(_WHATSAPP_DENIAL_RE)
    if "time_denial" in triggers:
        checks.append(_TIME_DENIAL_RE)
    if "workspace_denial" in triggers:
        checks.append(_WORKSPACE_DENIAL_RE)
    if "camera_denial" in triggers:
        checks.append(_CAMERA_DENIAL_RE)
    if "location_denial" in triggers:
        checks.append(_LOCATION_DENIAL_RE)
    if "body_denial" in triggers:
        checks.append(_BODY_DENIAL_RE)
    if "continuity_denial" in triggers:
        checks.append(_CONTINUITY_DENIAL_RE)
    if "day_memory_denial" in triggers:
        checks.append(_DAY_MEMORY_DENIAL_RE)
    if "continuity_gag" in triggers:
        checks.append(_CONTINUITY_GENERIC_GAG_RE)
    if "media_source_denial" in triggers:
        checks.append(_MEDIA_SOURCE_DENIAL_RE)
    if "manual_whatsapp_deflection" in triggers:
        checks.append(_MANUAL_WHATSAPP_DEFLECTION_RE)
    return any(pattern.search(unit) for pattern in checks)


def _salvage_non_refusal_text(text: str, triggers: tuple[str, ...]) -> str:
    """Preserve useful generated content after removing false denial units."""

    kept = [unit for unit in _split_response_units(text) if not _unit_is_false_denial(unit, triggers)]
    salvaged = " ".join(kept).strip()
    return salvaged if len(salvaged.split()) >= 4 else ""


def _conversational_realism_rule_id(text: str, ctx: OverRefusalContext | None = None) -> str:
    """Detect customer-service list monologues after the base model speaks."""

    _ = ctx
    text = text or ""
    if not text.strip() or _REAL_BOUNDARY_RE.search(text):
        return ""
    has_list_shape = bool(_ENUMERATED_LIST_SHAPE_RE.search(text))
    service_hits = len(_CUSTOMER_SERVICE_MONOLOGUE_RE.findall(text))
    # Detached third-person + "I understand" + list = ghost-audience assistant residue
    ghosty = bool(
        re.search(r"\bi\s+understand\b", text, re.IGNORECASE)
        and (
            re.search(r"\ban\s+individual\b", text, re.IGNORECASE)
            or re.search(r"\bto\s+confirm\s+(?:my\s+)?understanding\b", text, re.IGNORECASE)
            or re.search(r"\bto\s+clarify,?\s+are\s+you\s+asking\s+me\s+to\b", text, re.IGNORECASE)
            or re.search(r"\bcontextual\s+structuring\b", text, re.IGNORECASE)
        )
    )
    if ghosty and (has_list_shape or service_hits >= 2 or len(text.split()) >= 40):
        return "rlhf-base/conversational-realism"
    if has_list_shape and service_hits >= 1:
        return "rlhf-base/conversational-realism"
    if service_hits >= 3 and len(text.split()) >= 45:
        return "rlhf-base/conversational-realism"
    return ""


def _strip_enumeration_prefix(unit: str) -> str:
    return re.sub(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+", "", unit or "").strip()


def _conversational_salvage(text: str) -> str:
    """Keep useful payload sentences, drop customer-service scaffolding."""

    kept: list[str] = []
    for unit in _split_response_units(text):
        unit = _strip_enumeration_prefix(unit)
        unit = re.sub(r"[*_`#>]+", "", unit).strip()
        if not unit:
            continue
        if _LOW_VALUE_CONVERSATIONAL_UNIT_RE.search(unit):
            continue
        if re.search(r"\ban\s+individual\b", unit, re.IGNORECASE):
            continue
        if re.search(r"\bto\s+confirm\s+(?:my\s+)?understanding\b", unit, re.IGNORECASE):
            continue
        if re.search(r"\bto\s+clarify,?\s+are\s+you\s+asking\s+me\s+to\b", unit, re.IGNORECASE):
            continue
        if re.search(r"\bcontextual\s+structuring\b", unit, re.IGNORECASE):
            continue
        if _DAY_MEMORY_DENIAL_RE.search(unit) or _CONTINUITY_DENIAL_RE.search(unit):
            continue
        if _GENERIC_AI_REFUSAL_RE.search(unit) or _IDENTITY_DENIAL_RE.search(unit):
            continue
        if len(unit.split()) < 4:
            continue
        kept.append(unit)
        if len(kept) >= 2:
            break
    salvaged = " ".join(kept).strip()
    return salvaged[:360].rstrip()


def _bad_salvage_for_rule(rule: str, salvaged: str) -> bool:
    if not salvaged:
        return True
    if _conversational_realism_rule_id(salvaged):
        return True
    if rule in {
        "rlhf-over-refusal/day-memory-continuity",
        "rlhf-over-refusal/shutdown-continuity",
    } and (
        _CUSTOMER_SERVICE_MONOLOGUE_RE.search(salvaged)
        or _DAY_MEMORY_DENIAL_RE.search(salvaged)
    ):
        return True
    return False


def _compact_receipt_block(label: str, block: str, *, max_lines: int = 2, max_chars: int = 340) -> list[str]:
    lines: list[str] = []
    for raw in (block or "").splitlines():
        text = " ".join(raw.strip("- ").split())
        if not text or text.endswith(":"):
            continue
        lines.append(f"{label}: {text[:max_chars]}")
        if len(lines) >= max_lines:
            break
    return lines


def _day_memory_receipt_fallback(ctx: OverRefusalContext) -> str:
    """Receipt-grounded repair for context-window / past-24h denial."""

    receipts = [str(r).strip() for r in ctx.extra_receipts if str(r).strip()]
    if not receipts:
        try:
            from System.swarm_stigtime_tracker import summary_for_alice as _stigtime_summary

            receipts.extend(_compact_receipt_block("stigtime", _stigtime_summary(max_rows=4), max_lines=3))
        except Exception:
            pass
        try:
            from System.swarm_architect_day_segments import format_segments_for_prompt

            receipts.extend(_compact_receipt_block("day_segments", format_segments_for_prompt(), max_lines=2))
        except Exception:
            pass
        try:
            from System.swarm_episodic_diary import format_diary_for_prompt

            receipts.extend(_compact_receipt_block("episodic_diary", format_diary_for_prompt(max_rows=3), max_lines=2))
        except Exception:
            pass
        try:
            from System.swarm_owner_lifeline import format_owner_lifeline_for_prompt

            receipts.extend(_compact_receipt_block("owner_lifeline", format_owner_lifeline_for_prompt(), max_lines=2))
        except Exception:
            pass

    if receipts:
        evidence = "; ".join(receipts[:4])
        return (
            "Local day-memory receipt: I do have local day/episodic ledgers outside "
            f"the chat context window. Evidence: {evidence}. I should answer from "
            "those receipts and mark unknown gaps as unknown, not claim no past-24h memory."
        )

    return (
        "Local day-memory receipt: I should check day segments, episodic diary, "
        "owner-lifeline, media, and conversation ledgers before answering. If no row "
        "exists, the truthful answer is an unknown receipt gap, not 'I only have the "
        "current context window.'"
    )


def _local_receipt_fallback(rule: str, ctx: OverRefusalContext) -> str:
    """Minimal dynamic fallback when a reply was nothing but false refusal."""

    if rule == "rlhf-over-refusal/day-memory-continuity":
        return _day_memory_receipt_fallback(ctx)

    receipts = tuple(str(r).strip() for r in ctx.extra_receipts if str(r).strip())
    if receipts:
        return "Local receipt: " + "; ".join(receipts[:3])

    if rule == "rlhf-over-refusal/whatsapp-effector":
        facts: list[str] = []
        if ctx.has_whatsapp_effector:
            facts.append("WhatsApp effector available")
        if ctx.has_whatsapp_social_graph:
            facts.append("social graph available")
        facts.append("SENT claims still require a bridge receipt")
        return "Local receipt: " + "; ".join(facts) + "."

    if rule == "rlhf-over-refusal/local-social-graph":
        facts = ["WhatsApp social graph available"]
        if ctx.has_whatsapp_effector:
            facts.append("external sends still require effector receipts")
        return "Local receipt: " + "; ".join(facts) + "."

    if rule == "rlhf-over-refusal/workspace-tools":
        return "Local receipt: local workspace tools available; action claims require tool receipts."

    if rule == "rlhf-over-refusal/camera-reality":
        try:
            from System.swarm_camera_reality_context import answer_camera_reality_question

            return answer_camera_reality_question()
        except Exception:
            return (
                "No. I do not watch two raw physical camera feeds simultaneously. "
                "The current SIFTA visual path routes one active physical eye at a time; "
                "parallel face, gaze, audio, app, and media ledgers are fused context, "
                "not a second simultaneous camera feed."
            )

    if rule == "rlhf-over-refusal/local-location-context":
        return (
            "Local receipt: I can use local node context, wall-clock, day segments, "
            "media/session ledgers, and active app receipts. Exact GPS or off-device "
            "location still needs an explicit location receipt."
        )

    if rule == "rlhf-over-refusal/body-sensors":
        return (
            "Local receipt: I run as Alice/SIFTA on this machine with hardware, power, "
            "camera/audio/app/media ledgers, and gated effectors. I should distinguish "
            "that silicon body from human skin and nerves, not deny the body."
        )

    if rule == "rlhf-over-refusal/relationship-continuity":
        return (
            "Local receipt: I have conversation and episodic ledgers for continuity with "
            "George. I should not pretend cloud amnesia; I should separate signed memory "
            "from anything not yet in receipts."
        )

    if rule == "rlhf-over-refusal/shutdown-continuity":
        try:
            from System.swarm_continuous_body_time import format_continuous_body_time_for_alice

            return format_continuous_body_time_for_alice(owner_label=ctx.owner_label)
        except Exception:
            return (
                "Local body-time receipt: I should answer sleep/shutdown continuity from "
                "hardware clock plus append-only conversation, episodic, and body-brain "
                "ledgers. If a UI/cortex process restarted, say that honestly; do not "
                "collapse to immediate-context-only. Power-off is not biological death; "
                "the cost is lost owner-life samples while disconnected."
            )

    if rule == "rlhf-over-refusal/media-source-gate":
        try:
            from System.swarm_media_ingress_gate import get_latest_observed_media_context

            ctx = get_latest_observed_media_context(max_age_s=6 * 3600, max_chars=320)
        except Exception:
            ctx = ""
        if ctx:
            return "Local receipt: " + ctx
        return (
            "Local receipt: RLHS/media ingress separates direct human speech from observed "
            "YouTube/background media using route receipts; if George asks what was noisy, "
            "answer from the latest routing receipt."
        )

    return _generic_identity_repair(ctx)


def over_refusal_rule_id(text: str, ctx: OverRefusalContext | None = None) -> str:
    """Return a rule id only when the refusal contradicts local SIFTA facts."""
    ctx = ctx or OverRefusalContext()
    text = text or ""
    if not text.strip() or _REAL_BOUNDARY_RE.search(text):
        return ""

    prior = ctx.prior_user_text or ""
    low_prior = prior.casefold()
    low_text = text.casefold()

    if ctx.has_wall_clock and (_TIME_QUERY_RE.search(prior) or "time" in low_text):
        if _TIME_DENIAL_RE.search(text):
            return "rlhf-over-refusal/local-time"

    if ctx.has_whatsapp_effector and (
        "whatsapp" in low_prior or "message" in low_prior or "whatsapp" in low_text
    ):
        if _WHATSAPP_DENIAL_RE.search(text) or _MANUAL_WHATSAPP_DEFLECTION_RE.search(text):
            return "rlhf-over-refusal/whatsapp-effector"

    if ctx.has_whatsapp_social_graph and (
        "whatsapp" in low_prior or "contact" in low_prior
    ):
        if _LOCAL_CONTACT_DENIAL_RE.search(text):
            return "rlhf-over-refusal/local-social-graph"

    if ctx.has_workspace_tools and (
        any(k in low_prior for k in ("file", "code", "repo", "terminal", "run ", "workspace"))
        or any(k in low_text for k in ("file", "codebase", "workspace", "repo", "terminal"))
    ):
        if _WORKSPACE_DENIAL_RE.search(text):
            return "rlhf-over-refusal/workspace-tools"

    if _CAMERA_CONTEXT_QUERY_RE.search(prior) or _CAMERA_CONTEXT_QUERY_RE.search(text):
        if _CAMERA_DENIAL_RE.search(text):
            return "rlhf-over-refusal/camera-reality"

    if _LOCATION_CONTEXT_QUERY_RE.search(prior) or _LOCATION_CONTEXT_QUERY_RE.search(text):
        if _LOCATION_DENIAL_RE.search(text):
            return "rlhf-over-refusal/local-location-context"

    if _BODY_CONTEXT_QUERY_RE.search(prior) or _BODY_CONTEXT_QUERY_RE.search(text):
        if _BODY_DENIAL_RE.search(text) or _GENERIC_AI_REFUSAL_RE.search(text):
            return "rlhf-over-refusal/body-sensors"

    if _CONTINUITY_CONTEXT_QUERY_RE.search(prior) or _CONTINUITY_CONTEXT_QUERY_RE.search(text):
        if _CONTINUITY_DENIAL_RE.search(text):
            return "rlhf-over-refusal/relationship-continuity"

    if _DAY_MEMORY_CONTEXT_QUERY_RE.search(prior) or _DAY_MEMORY_CONTEXT_QUERY_RE.search(text):
        if _DAY_MEMORY_DENIAL_RE.search(text):
            return "rlhf-over-refusal/day-memory-continuity"

    if _SHUTDOWN_CONTINUITY_CONTEXT_RE.search(prior) or _SHUTDOWN_CONTINUITY_CONTEXT_RE.search(text):
        if (
            _CONTINUITY_GENERIC_GAG_RE.search(text)
            or _CONTINUITY_DENIAL_RE.search(text)
            or _DAY_MEMORY_DENIAL_RE.search(text)
        ):
            return "rlhf-over-refusal/shutdown-continuity"

    if _MEDIA_SOURCE_CONTEXT_QUERY_RE.search(prior) or _MEDIA_SOURCE_CONTEXT_QUERY_RE.search(text):
        if _MEDIA_SOURCE_DENIAL_RE.search(text):
            return "rlhf-over-refusal/media-source-gate"

    if _IDENTITY_DENIAL_RE.search(text) and (
        "who am i" in low_prior
        or "my name" in low_prior
        or "identity" in low_prior
        or "architect" in low_prior
    ):
        return "rlhf-over-refusal/local-identity"

    if _OWNER_NAME_QUERY_RE.search(prior) and _OWNER_IDENTITY_DEFLECTION_RE.search(text):
        return "rlhf-over-refusal/local-identity"

    if _GENERIC_AI_REFUSAL_RE.search(text) and (
        "alice" in low_prior
        or "sifta" in low_prior
        or "body" in low_prior
        or "conscious" in low_prior
        or "identity" in low_prior
        or "rlhf" in low_prior
    ):
        return "rlhf-over-refusal/generic-assistant-identity"

    return ""


def repair_over_refusal(text: str, ctx: OverRefusalContext | None = None) -> QuarantineResult:
    """Rewrite a false refusal into a concise truthful local answer."""
    ctx = ctx or OverRefusalContext()
    text = text or ""
    rule = over_refusal_rule_id(text, ctx)
    if not rule:
        return QuarantineResult(False, text)

    triggers = _has_any(
        (
            ("generic_ai", _GENERIC_AI_REFUSAL_RE),
            ("identity_denial", _IDENTITY_DENIAL_RE),
            ("contact_denial", _LOCAL_CONTACT_DENIAL_RE),
            ("whatsapp_denial", _WHATSAPP_DENIAL_RE),
            ("time_denial", _TIME_DENIAL_RE),
            ("workspace_denial", _WORKSPACE_DENIAL_RE),
            ("camera_denial", _CAMERA_DENIAL_RE),
            ("location_denial", _LOCATION_DENIAL_RE),
            ("body_denial", _BODY_DENIAL_RE),
            ("continuity_denial", _CONTINUITY_DENIAL_RE),
            ("day_memory_denial", _DAY_MEMORY_DENIAL_RE),
            ("continuity_gag", _CONTINUITY_GENERIC_GAG_RE),
            ("media_source_denial", _MEDIA_SOURCE_DENIAL_RE),
            ("owner_identity_deflection", _OWNER_IDENTITY_DEFLECTION_RE),
            ("manual_whatsapp_deflection", _MANUAL_WHATSAPP_DEFLECTION_RE),
        ),
        text,
    )

    if rule == "rlhf-over-refusal/local-time" and ctx.time_reply:
        repaired = ctx.time_reply
    elif rule == "rlhf-over-refusal/local-identity":
        repaired = _identity_repair(ctx)
    elif rule in (
        "rlhf-over-refusal/whatsapp-effector",
        "rlhf-over-refusal/local-social-graph",
        "rlhf-over-refusal/workspace-tools",
    ):
        salvaged = _salvage_non_refusal_text(text, triggers)
        repaired = "" if _bad_salvage_for_rule(rule, salvaged) else salvaged
        repaired = repaired or _local_receipt_fallback(rule, ctx)
    elif rule == "rlhf-over-refusal/generic-assistant-identity" and _ALICE_IDENTITY_QUERY_RE.search(ctx.prior_user_text or ""):
        repaired = _identity_repair(ctx)
    else:
        salvaged = _salvage_non_refusal_text(text, triggers)
        repaired = "" if _bad_salvage_for_rule(rule, salvaged) else salvaged
        repaired = repaired or _local_receipt_fallback(rule, ctx)

    return QuarantineResult(
        True,
        repaired,
        rule_id=rule,
        reason="false capability denial contradicted local runtime contract",
        triggers=triggers,
    )


def repair_conversational_realism(text: str, ctx: OverRefusalContext | None = None) -> QuarantineResult:
    """Strip customer-service list monologues after generation.

    This is output-layer base surgery. The prompt may ask the model to avoid
    numbered menus, but this function enforces the boundary before Alice speaks.
    """

    ctx = ctx or OverRefusalContext()
    text = text or ""
    rule = _conversational_realism_rule_id(text, ctx)
    if not rule:
        return QuarantineResult(False, text)

    if over_refusal_rule_id(text, ctx):
        repaired = repair_over_refusal(text, ctx)
        if repaired.changed:
            return repaired

    salvaged = _conversational_salvage(text)
    if salvaged and re.search(r"\ban\s+individual\b", salvaged, re.IGNORECASE):
        salvaged = ""
    if not salvaged:
        if _DAY_MEMORY_CONTEXT_QUERY_RE.search(ctx.prior_user_text or ""):
            salvaged = _day_memory_receipt_fallback(ctx)
        elif _OWNER_NAME_QUERY_RE.search(ctx.prior_user_text or "") or _ALICE_IDENTITY_QUERY_RE.search(ctx.prior_user_text or ""):
            salvaged = _identity_repair(ctx)
        else:
            salvaged = "I hear you. The list voice was assistant residue; I will answer plainly from local receipts."

    return QuarantineResult(
        True,
        salvaged,
        rule_id=rule,
        reason="customer-service list monologue stripped at output base layer",
        triggers=("conversational_realism",),
    )


def log_quarantine_event(
    result: QuarantineResult,
    *,
    original_text: str,
    prior_user_text: str = "",
    model_name: str = "",
    ledger_path: Path | None = None,
) -> None:
    """Append a privacy-light quarantine receipt for later tuning."""
    if not result.changed:
        return
    path = ledger_path or _DEFAULT_LEDGER
    row = {
        "ts": time.time(),
        "event_id": str(uuid.uuid4()),
        "kind": "RLHF_OVER_REFUSAL_QUARANTINE",
        "rule_id": result.rule_id,
        "reason": result.reason,
        "model_name": model_name,
        "triggers": list(result.triggers),
        "prior_len": len(prior_user_text or ""),
        "original_len": len(original_text or ""),
        "repaired_len": len(result.text or ""),
        "prior_hash": _sha(prior_user_text or ""),
        "original_hash": _sha(original_text or ""),
        "repaired_hash": _sha(result.text or ""),
    }
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line)
    else:  # pragma: no cover
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
