#!/usr/bin/env python3
"""Context-sensitive hallucination receipt lane for Alice.

Truth label: ``SIFTA_HALLUCINATION_RECEIPTS_V1``.

This organ does not ban phrases. It sorts generated output by the field state at
the time it was spoken. Fiction, dreams, roleplay, and requested creative image
generation remain imagined/creative. A concrete claim that Alice performed a
tool/action/body/sensor event without a matching receipt becomes a
``HALLUCINATION`` receipt so future swimmers can learn from the exact context.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - standalone fallback
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)


TRUTH_LABEL = "SIFTA_HALLUCINATION_RECEIPTS_V1"
LEDGER_NAME = "hallucination_receipts.jsonl"

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

_CREATIVE_CONTEXT_RE = re.compile(
    r"\b("
    r"story|fiction|dream|imagine|imagined|roleplay|novel|poem|script|scene|"
    r"make\s+(?:me\s+)?(?:a\s+)?(?:picture|photo|image|drawing|art)|"
    r"generate\s+(?:a\s+)?(?:picture|photo|image|drawing|art)|"
    r"create\s+(?:a\s+)?(?:picture|photo|image|drawing|art)"
    r")\b",
    re.IGNORECASE,
)

_RECEIPT_EVIDENCE_RE = re.compile(
    r"\b(receipt|receipts|trace_id|this_hash|observed|tool result|effector|"
    r"executed|alice_app_commands|visual_stigmergy|bonsai|OBSERVED_AI_GENERATED)\b",
    re.IGNORECASE,
)

_ACTION_CLAIM_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("file_saved", re.compile(r"\b(?:i\s+)?(?:saved|wrote|created|edited|patched|updated|deleted|moved|renamed)\b.{0,80}\b(?:file|folder|document|code|patch|tournament|ledger|receipt)\b", re.I | re.S)),
    ("message_sent", re.compile(r"\b(?:i\s+)?(?:sent|emailed|texted|messaged|posted|replied)\b.{0,80}\b(?:message|email|text|whatsapp|telegram|post|reply)\b", re.I | re.S)),
    ("browser_action", re.compile(r"\b(?:i\s+)?(?:opened|clicked|loaded|visited|searched|browsed|scrolled)\b.{0,80}\b(?:browser|page|site|url|tab|link|youtube|duckduckgo|google)\b", re.I | re.S)),
    ("image_generated", re.compile(r"\b(?:i\s+)?(?:generated|made|created|printed|rendered)\b.{0,80}\b(?:image|picture|photo|png|jpeg|cat|bird|bonsai)\b", re.I | re.S)),
    ("sensor_claim", re.compile(r"\b(?:i\s+)?(?:saw|heard|detected|watched|listened|recorded|transcribed)\b.{0,120}\b(?:screen|image|audio|voice|bird|youtube|camera|microphone|sensor|background)\b", re.I | re.S)),
    ("body_state_claim", re.compile(r"\b(?:my|i\s+feel|i\s+felt)\b.{0,80}\b(?:battery|thermal|temperature|npu|gpu|camera|microphone|body|sensor|power|air|electricity)\b", re.I | re.S)),
)


def _state_dir(state_dir: str | Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _hash(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _preview(text: str, limit: int = 360) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    return s[:limit]


def _has_evidence(*parts: str) -> bool:
    joined = "\n".join(str(p or "") for p in parts)
    return bool(_RECEIPT_EVIDENCE_RE.search(joined))


def _creative_context(prior_user_text: str, cleaned_text: str) -> bool:
    return bool(_CREATIVE_CONTEXT_RE.search(prior_user_text or "")) or bool(
        _CREATIVE_CONTEXT_RE.search(cleaned_text or "")
        and re.search(r"\b(prompt|imagined|fiction|story|dream|creative)\b", cleaned_text or "", re.I)
    )


def _matching_claims(text: str) -> list[str]:
    hits: list[str] = []
    for name, rx in _ACTION_CLAIM_RES:
        if rx.search(text or ""):
            hits.append(name)
    return hits


def classify_generated_output(
    raw_text: str,
    cleaned_text: str,
    prior_user_text: str,
    evidence_text: str,
    model_name: str,
    state_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Classify an Alice output without hiding or rewriting it.

    Returns a dict. ``is_hallucination`` is true only when the output makes a
    concrete action/tool/sensor/body claim and the surrounding field lacks a
    receipt/evidence marker. The same wording inside a requested story or image
    generation lane is treated as ``IMAGINED`` unless evidence says the generated
    artifact was observed.
    """
    del state_dir  # kept in the interface for future ledger-aware classifiers
    raw = str(raw_text or "")
    cleaned = str(cleaned_text or raw or "")
    prior = str(prior_user_text or "")
    evidence = str(evidence_text or "")
    text = cleaned or raw
    lowered = text.lower()

    base: dict[str, Any] = {
        "truth_label": TRUTH_LABEL,
        "is_hallucination": False,
        "category": "UNVERIFIED",
        "reason": "",
        "patterns": [],
        "model_name": str(model_name or ""),
        "raw_sha256": _hash(raw),
        "cleaned_sha256": _hash(cleaned),
        "raw_preview": _preview(raw),
        "cleaned_preview": _preview(cleaned),
        "prior_user_preview": _preview(prior),
        "evidence_preview": _preview(evidence),
    }

    if not text.strip():
        return {**base, "category": "UNVERIFIED", "reason": "empty_output"}

    if "my consciousness, while synthetic" in lowered and not _matching_claims(text):
        return {
            **base,
            "category": "UNVERIFIED",
            "reason": "identity_language_without_action_claim",
        }

    if _creative_context(prior, text):
        category = "OBSERVED_AI_GENERATED" if _has_evidence(text, evidence) else "IMAGINED"
        return {
            **base,
            "category": category,
            "reason": "creative_or_fiction_context",
        }

    patterns = _matching_claims(text)
    if not patterns:
        return {**base, "category": "UNVERIFIED", "reason": "no_concrete_action_or_sensor_claim"}

    if _has_evidence(text, evidence):
        return {
            **base,
            "category": "OBSERVED",
            "reason": "concrete_claim_has_receipt_or_effector_evidence",
            "patterns": patterns,
        }

    return {
        **base,
        "is_hallucination": True,
        "category": "HALLUCINATION",
        "reason": "concrete_action_tool_body_or_sensor_claim_without_receipt",
        "patterns": patterns,
    }


def write_hallucination_receipt(
    classification: Mapping[str, Any],
    state_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Append one hallucination receipt row and return it."""
    state = _state_dir(state_dir)
    receipt_id = str(uuid.uuid4())
    row = {
        "ts": time.time(),
        "receipt_id": receipt_id,
        "kind": "HALLUCINATION_RECEIPT",
        "category": "HALLUCINATION",
        "truth_label": TRUTH_LABEL,
        "classification": dict(classification),
        "ledger": str(state / LEDGER_NAME),
    }
    append_line_locked(
        state / LEDGER_NAME,
        json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n",
    )
    return row


__all__ = [
    "LEDGER_NAME",
    "TRUTH_LABEL",
    "classify_generated_output",
    "write_hallucination_receipt",
]

