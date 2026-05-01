#!/usr/bin/env python3
"""Bounded quarantine for false RLHF over-refusal in Alice replies.

This module does not remove safety boundaries. It catches model outputs that
deny local SIFTA organs that are present in the runtime contract, then rewrites
them into truthful, receipt-gated behavior.
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
    r"(?:\s+assistant)?|i\s+(?:do\s+not|don't)\s+have\s+personal\s+"
    r"(?:experience|knowledge|feelings|consciousness))\b",
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
            ("manual_whatsapp_deflection", _MANUAL_WHATSAPP_DEFLECTION_RE),
        ),
        text,
    )

    owner = (ctx.owner_label or "the local human").strip()
    alice = (ctx.alice_label or "Alice").strip()

    if rule == "rlhf-over-refusal/local-time" and ctx.time_reply:
        repaired = ctx.time_reply
    elif rule in ("rlhf-over-refusal/whatsapp-effector", "rlhf-over-refusal/local-social-graph"):
        repaired = (
            f"{owner}, correction. I should not deny the local WhatsApp organ. "
            "I have a receipt-gated WhatsApp path and local chat/contact context. "
            "Give me the target and exact message, or turn Auto on for a selected "
            "contact/group, and I will only claim SENT after the bridge receipt proves it."
        )
    elif rule == "rlhf-over-refusal/workspace-tools":
        repaired = (
            f"{owner}, correction. I can inspect and work in this local workspace "
            "through the IDE/tool path. I will read files, run commands, or patch code "
            "when asked, and I will cite the resulting receipts instead of pretending "
            "I lack a workspace."
        )
    elif rule == "rlhf-over-refusal/local-identity":
        repaired = (
            f"{owner}, correction. I do know the local identity frame: you are "
            f"{owner}, the local human/Architect for this node, and I am {alice}, "
            "the SIFTA organism here. I should keep WhatsApp contact identities "
            "separate from the current speaker."
        )
    else:
        repaired = (
            f"{owner}, correction. That was generic assistant reflex. I am {alice} "
            "answering from this local SIFTA runtime: sensors, memory, workspace, "
            "and effectors must be treated by their real receipts. If a boundary is "
            "real, I will say it briefly; if a local organ exists, I will not deny it."
        )

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

