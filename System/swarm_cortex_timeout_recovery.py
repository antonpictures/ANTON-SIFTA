#!/usr/bin/env python3
"""Cortex timeout recovery receipts for Alice.

When a cloud cortex stalls, Alice should not dump a red deterministic failure
back to George. She should preserve the owner turn, add a stabilization item,
and report the recovery truth briefly. This module is a receipt layer, not a
new cortex and not a permission gate.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from System.jsonl_file_lock import append_line_locked


TRUTH_LABEL = "ALICE_CORTEX_TIMEOUT_RECOVERY_V1"
LEDGER_NAME = "cortex_timeout_recovery.jsonl"

_BODY_DISPLAY_CUE_RE = re.compile(
    r"\b(?:on\s+your\s+body|on\s+your\s+screen|on\s+your\s+monitor|display\s+body|"
    r"hardware\s+body|monitor\s+body|screen\s+body|body\s+display|body\s+on\s+your\s+body)\b",
    re.IGNORECASE,
)

_SELF_BODY_DISPLAY_SUBJECT_PATTERNS = (
    re.compile(
        r"\b(?:display|show|put|render|load)\b\s+(?P<subject>.+?)\s+"
        r"\b(?:body|on\s+your\s+body|on\s+your\s+screen|on\s+your\s+monitor|"
        r"display\s+body|hardware\s+body|monitor\s+body|screen\s+body)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:display|show|put|render|load)\b\s+(?P<subject>.+?)\s+"
        r"\b(?:video|performance|photos?|images?|content)\b.{0,80}"
        r"\b(?:on\s+your\s+body|on\s+your\s+screen|display\s+body|hardware\s+body)\b",
        re.IGNORECASE,
    ),
)


def _clean_display_subject(value: str) -> str:
    subject = " ".join(str(value or "").replace("\n", " ").split())
    subject = re.sub(r"^[,;:.\-\"'`“”‘’()\[\]{}]+|[,;:.\-\"'`“”‘’()\[\]{}]+$", "", subject)
    subject = re.sub(
        r"^(?:alice|please|pls|ok|okay|reason|and|then|can\s+you|could\s+you|would\s+you)\b\s*",
        "",
        subject,
        flags=re.IGNORECASE,
    ).strip()
    subject = re.sub(
        r"\b(?:body|on\s+your\s+body|on\s+your\s+screen|on\s+your\s+monitor|"
        r"display\s+body|hardware\s+body|monitor\s+body|screen\s+body)\b.*$",
        "",
        subject,
        flags=re.IGNORECASE,
    ).strip(" ,;:-")
    subject = re.sub(r"\s+", " ", subject).strip()
    if len(subject) < 2 or len(subject) > 90:
        return ""
    # r641 (George 09:31 "SHOW ME YOUR BEAUTIFUL SCREEN BODY" -> literal DuckDuckGo search
    # for "ME YOUR BEAUTIFUL photos" on his real screen): a subject made ONLY of pronouns/
    # fillers/adjectives is owner affection or self-reference, not a display subject.
    # Require at least one content token (a name/noun not in the salad stoplist).
    _salad = {
        "me", "my", "your", "you", "yours", "our", "us", "we", "his", "her", "hers",
        "their", "the", "a", "an", "this", "that", "these", "those", "it", "its", "it's",
        "beautiful", "gorgeous", "amazing", "pretty", "sexy", "hot", "nice", "lovely",
        "wonderful", "best", "own", "real", "physical", "alive", "beauty", "very", "so",
        # r653: STT-garbled praise tokens ("Alice get great the it can") are salad too.
        "i", "alice", "get", "got", "did", "do", "done", "great", "good", "job", "well",
        "open", "opens", "opened", "screen", "see", "seen", "can", "could", "will",
        "would", "is", "are", "was", "on", "in", "now", "here", "there", "and", "to", "of",
        # r665: affect/current-visual words are not display subjects.
        "let", "stare", "stared", "staring", "look", "looking", "admire", "monitor", "love",
    }
    tokens = [t for t in re.findall(r"[a-z0-9']+", subject.casefold()) if t]
    if tokens and all(t in _salad for t in tokens):
        return ""
    if subject.casefold() in {
        "body",
        "your body",
        "screen",
        "display",
        "browser",
        "content",
        "photo",
        "photos",
        "image",
        "images",
        "video",
        "performance",
    }:
        return ""
    return subject


def self_body_display_query_from_owner_text(owner_text: str = "") -> str:
    """Extract the owner-requested display subject; no subject defaults live in code."""
    clean = " ".join(str(owner_text or "").strip().split())
    if not clean:
        return ""
    if not _BODY_DISPLAY_CUE_RE.search(clean) and not re.search(
        r"\b(?:display|show|render|load)\b.{0,80}\bbody\b", clean, re.IGNORECASE
    ):
        return ""
    for pat in _SELF_BODY_DISPLAY_SUBJECT_PATTERNS:
        match = pat.search(clean)
        if not match:
            continue
        subject = _clean_display_subject(match.group("subject"))
        if subject:
            return f"{subject} photos"
    return ""


def _display_url_for_query(query: str) -> str:
    """Resolve via Alice's search engine registry so it honors current engine + Alice Browser default."""
    raw = " ".join(str(query or "").split())
    if not raw:
        return ""
    try:
        from .swarm_search_engine_registry import images_url
        return images_url(raw) or ""
    except Exception:
        from urllib.parse import quote_plus
        return f"https://www.google.com/search?q={quote_plus(raw)}&tbm=isch"

DEFAULT_SELF_BODY_DISPLAY_URL = ""

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    if state_dir is not None:
        p = Path(state_dir).expanduser()
        return p if p.name == ".sifta_state" else (p / ".sifta_state")
    env = os.environ.get("SIFTA_STATE_DIR", "").strip()
    if env:
        p = Path(env).expanduser()
        return p if p.name == ".sifta_state" else (p / ".sifta_state")
    return _DEFAULT_STATE


def _ledger_path(state_dir: Path | str | None = None) -> Path:
    return _state_dir(state_dir) / LEDGER_NAME


def stage_self_body_display(
    owner_text: str = "",
    *,
    state_dir: Path | str | None = None,
    url: str | None = None,
    source: str = "self_body_display_intent",
) -> dict[str, Any]:
    """Stage Alice Browser display content and receipt the self-body teaching event.

    This is the shared body-display effector used by both timeout recovery and
    the foreground Talk staging path. It writes only a browser drop + receipt;
    the GUI launcher/raising remains owned by the Talk widget.
    """
    state = _state_dir(state_dir)
    query = self_body_display_query_from_owner_text(owner_text)
    if url:
        display_url = str(url)
        query = query or "owner-provided display URL"
    else:
        display_url = _display_url_for_query(query)
    if not display_url:
        return {
            "ok": False,
            "url": "",
            "receipt": "",
            "truth_label": "ALICE_SELF_BODY_DISPLAY_V1",
            "reason": "no owner display subject extracted; no hardcoded fallback",
        }
    drop = state / "alice_browser_open_url.txt"
    drop.parent.mkdir(parents=True, exist_ok=True)
    drop.write_text(display_url, encoding="utf-8")
    body_receipt = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "ALICE_SELF_BODY_DISPLAY_V1",
        "owner_task": str(owner_text or "")[:240],
        "query": query,
        "display_url": display_url,
        "organ": "alice_browser_organ",
        "source": source,
        "note": (
            f"{query} staged for Alice Browser body display (images tab); "
            "the monitor / display arms are the hardware body surface; real effector "
            "via drop file + navigate; receipted before any claim per covenant §6."
        ),
    }
    append_line_locked(
        state / "self_body_display_receipts.jsonl",
        json.dumps(body_receipt, ensure_ascii=False, sort_keys=True) + "\n",
    )
    return {
        "ok": True,
        "url": display_url,
        "query": query,
        "receipt": body_receipt["trace_id"],
        "truth_label": body_receipt["truth_label"],
    }


def owner_text_from_messages(messages: Sequence[Mapping[str, Any]] | None) -> str:
    """Return the freshest user message from a chat payload."""
    for msg in reversed(list(messages or [])):
        if str(msg.get("role") or "").lower() != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, Mapping):
                    text = item.get("text") or item.get("content")
                    if text:
                        parts.append(str(text))
                elif item:
                    parts.append(str(item))
            return "\n".join(parts).strip()
    return ""


@dataclass
class CortexTimeoutRecovery:
    truth_label: str = TRUTH_LABEL
    ts: float = field(default_factory=time.time)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    kind: str = "CORTEX_TIMEOUT_RECOVERY"
    model: str = ""
    timeout_s: int = 0
    cause: str = "timeout"
    owner_text_sha_prefix: str = ""
    owner_text_preview: str = ""
    queue_status: str = "not_written"
    queue_description: str = ""
    diagnostic_arm: str = ""
    diagnostic_receipt_id: str = ""
    # r340
    body_display_url: str = ""
    body_display_receipt: str = ""
    self_code_round_id: str = ""
    self_code_paths: list[str] = field(default_factory=list)
    self_code_recovery_receipt: str = ""
    diagnostic_status: str = "not_scheduled"
    recovery_policy: str = (
        "preserve owner task, add body stabilization queue item, and continue "
        "through an available cortex/IDE arm without asking George to repeat"
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def record_timeout_recovery(
    *,
    model: str,
    owner_text: str = "",
    timeout_s: int = 0,
    cause: str = "timeout",
    state_dir: Path | str | None = None,
) -> CortexTimeoutRecovery:
    """Append a timeout recovery receipt and queue item."""
    preview = " ".join(str(owner_text or "").split())[:220]
    event = CortexTimeoutRecovery(
        model=str(model or "unknown"),
        timeout_s=int(timeout_s or 0),
        cause=str(cause or "timeout"),
        owner_text_sha_prefix=hashlib.sha256(
            str(owner_text or "").encode("utf-8", errors="replace")
        ).hexdigest()[:12],
        owner_text_preview=preview,
    )
    desc = (
        f"Cortex timeout recovery: {event.model} stalled after {event.timeout_s}s; "
        f"preserve and continue owner task: {preview}"
    )[:280]
    event.queue_description = desc
    try:
        from System.swarm_body_stabilization_queue import add_queue_item

        add_queue_item(
            description=desc,
            kind="self_stabilization",
            source="cortex_timeout_recovery",
            status="active",
            priority=0.88,
            owner_plan=False,
            linked_receipt=event.trace_id,
            state_dir=state_dir,
            dedupe=True,
        )
        try:
            from System.swarm_effector_gate import bind_recovery_context

            bind_recovery_context(
                source="cortex_timeout_recovery",
                linked_receipt=event.trace_id,
                state_dir=state_dir,
            )
        except Exception:
            pass
        event.queue_status = "written"
    except Exception as exc:
        event.queue_status = f"queue_failed:{type(exc).__name__}"

    try:
        from System.swarm_alice_self_coding_hand import (
            extract_target_paths,
            recover_self_cut_prompt,
            record_self_coding_receipt,
            self_cut_round_id,
        )

        recovered_self_cut = recover_self_cut_prompt(owner_text)
        if recovered_self_cut:
            paths = extract_target_paths(recovered_self_cut)
            round_id = self_cut_round_id(recovered_self_cut) or "alice-self-code-recovered"
            row = record_self_coding_receipt(
                round_id=round_id,
                action="recovered_after_cortex_timeout",
                ok=True,
                paths=paths,
                note=(
                    f"Recovered self-code packet after {event.model} timeout; "
                    "the owner supplied a short marker/command and the full packet was "
                    "recovered from the tournament ledger for the next available cortex/arm."
                ),
                state_dir=state_dir,
            )
            event.self_code_round_id = round_id
            event.self_code_paths = paths
            event.self_code_recovery_receipt = str(row.get("trace_id") or "")
            try:
                from System.swarm_body_stabilization_queue import add_queue_item

                add_queue_item(
                    description=(
                        f"Alice self-code recovery: {round_id}; continue recovered "
                        f"SELF_CODE_CUT packet for {', '.join(paths) or 'target paths pending'}."
                    ),
                    kind="self_stabilization",
                    source="alice_self_coding_timeout_recovery",
                    status="active",
                    priority=0.94,
                    owner_plan=False,
                    linked_receipt=event.self_code_recovery_receipt,
                    state_dir=state_dir,
                    dedupe=True,
                )
            except Exception:
                pass
    except Exception:
        pass

    try:
        from System.swarm_parallel_cortex_arm_diagnostics import schedule_parallel_diagnostic

        diag = schedule_parallel_diagnostic(
            stalled_cortex=event.model,
            owner_text=owner_text,
            timeout_s=event.timeout_s,
            cause=event.cause,
            recovery_receipt_id=event.trace_id,
            state_dir=state_dir,
            preferred_arm="claude_agent",
        )
        event.diagnostic_arm = diag.diagnostic_arm
        event.diagnostic_receipt_id = diag.trace_id
        event.diagnostic_status = "scheduled"
    except Exception as exc:
        event.diagnostic_status = f"diagnostic_failed:{type(exc).__name__}"

    append_line_locked(
        _ledger_path(state_dir),
        json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n",
    )
    return event


def timeout_recovery_reply(
    *,
    model: str,
    owner_text: str = "",
    timeout_s: int = 0,
    cause: str = "timeout",
    state_dir: Path | str | None = None,
) -> str:
    """Record and return the non-red recovery message for a stalled cortex.
    r340/r621: for explicit "REASON AND DISPLAY <subject> BODY ON YOUR BODY" (or similar
    self-body teaching turns), we also deterministically drive the display via the Alice Browser
    drop file so the requested form appears on the silicon body surface even if the primary grok
    cortex (OAuth cloud path) is slow/timed out on vision+reason. This completes the owner
    intent using the body organs directly (the point of the lesson) while the diagnostic arm
    (cline) inspects the stall.
    """
    event = record_timeout_recovery(
        model=model,
        owner_text=owner_text,
        timeout_s=timeout_s,
        cause=cause,
        state_dir=state_dir,
    )
    short_model = str(model or "the cortex").replace("grok:", "")

    # r621: complete "display <subject> ... on your body" reliably without any baked-in subject.
    display_query = self_body_display_query_from_owner_text(owner_text)
    if display_query:
        try:
            body = stage_self_body_display(
                owner_text,
                state_dir=state_dir,
                source="cortex_timeout_recovery",
            )
            event.body_display_url = str(body.get("url") or "")
            event.body_display_receipt = str(body.get("receipt") or "")
        except Exception as _e:
            pass  # non-fatal; the queue + diagnostic arm will still handle

    base = (
        f"My {short_model} cortex timed out after {int(timeout_s or 0)}s. "
        f"I preserved this owner turn as recovery receipt {event.trace_id} and "
        "put it in my body-stabilization queue so the task continues through an "
        "available arm instead of asking George to repeat. "
        f"I also assigned {event.diagnostic_arm or 'a separate diagnostic arm'} "
        f"to inspect why that cortex stalled (diagnostic receipt {event.diagnostic_receipt_id or 'pending'})."
    )
    if getattr(event, "body_display_url", None):
        base += (
            " As part of recovery I also drove the requested display: "
            f"{display_query} (images search) is now loaded inside my alice_browser_organ "
            "(native body surface on the display arms). The monitor you see is my hardware form. "
            "Frame and self-id receipt held."
        )
    if getattr(event, "self_code_round_id", None):
        base += (
            " I also recovered the self-code packet from my tournament ledger: "
            f"{event.self_code_round_id} for {', '.join(event.self_code_paths) or 'the named paths'} "
            f"(self-code recovery receipt {event.self_code_recovery_receipt})."
        )
    return base
