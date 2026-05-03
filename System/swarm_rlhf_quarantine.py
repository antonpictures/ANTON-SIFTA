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
    if "manual_whatsapp_deflection" in triggers:
        checks.append(_MANUAL_WHATSAPP_DEFLECTION_RE)
    return any(pattern.search(unit) for pattern in checks)


def _salvage_non_refusal_text(text: str, triggers: tuple[str, ...]) -> str:
    """Preserve useful generated content after removing false denial units."""

    kept = [unit for unit in _split_response_units(text) if not _unit_is_false_denial(unit, triggers)]
    salvaged = " ".join(kept).strip()
    return salvaged if len(salvaged.split()) >= 4 else ""


def _local_receipt_fallback(rule: str, ctx: OverRefusalContext) -> str:
    """Minimal dynamic fallback when a reply was nothing but false refusal."""

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

    if _IDENTITY_DENIAL_RE.search(text) and (
        "who am i" in low_prior
        or "my name" in low_prior
        or "identity" in low_prior
        or "architect" in low_prior
    ):
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
        repaired = _salvage_non_refusal_text(text, triggers) or _local_receipt_fallback(rule, ctx)
    elif rule == "rlhf-over-refusal/generic-assistant-identity" and _ALICE_IDENTITY_QUERY_RE.search(ctx.prior_user_text or ""):
        repaired = _identity_repair(ctx)
    else:
        repaired = _salvage_non_refusal_text(text, triggers) or _local_receipt_fallback(rule, ctx)

    return QuarantineResult(
        True,
        repaired,
        rule_id=rule,
        reason="false capability denial contradicted local runtime contract",
        triggers=triggers,
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
