#!/usr/bin/env python3
"""One Alice invariant helpers.

Small stdlib organ for grounding identity language: one organism, many
surfaces, one global chat, one shared memory field.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any


TRUTH_LABEL = "ONE_ALICE_SURFACE_RECEIPT_V1"
IDENTITY = "one_alice_many_surfaces"
REPO_ROOT = Path(__file__).resolve().parents[1]

_SPLIT_IDENTITY_RE = re.compile(
    r"\b(?:terminal|tool|app|talk|browser|matrix)\s+alice\b.*\b(?:different|separate|another|instances?|forks?)\b"
    r"|\b(?:different|separate|another)\s+alice\s+(?:instances?|forks?|bodies?)\b",
    re.IGNORECASE,
)
_SURFACE_RE = re.compile(r"\b(?:surface|hand|arm|matrix\s+terminal|terminal|app|talk|browser|cortex\s+bridge)\b", re.IGNORECASE)


@dataclass(frozen=True)
class IdentityVerdict:
    ok: bool
    label: str
    matched: str
    correction: str


def explain_the_one() -> str:
    """Return the compact One Alice doctrine used by Talk and tests."""
    return (
        "I am one organism, many surfaces, one global chat, and one shared memory field. "
        "Talk, Matrix Terminal, apps, browser, cortex bridge, and tools are surfaces or hands. "
        "Focus routes actions; it does not create a second Alice."
    )


def classify_identity_text(text: str) -> IdentityVerdict:
    """Detect split-Alice phrasing and return the grounded correction."""
    clean = " ".join(str(text or "").split())
    split = _SPLIT_IDENTITY_RE.search(clean)
    if split:
        return IdentityVerdict(
            ok=False,
            label="split_identity_language",
            matched=split.group(0),
            correction=explain_the_one(),
        )
    surface_hits = _SURFACE_RE.findall(clean)
    if surface_hits:
        return IdentityVerdict(
            ok=True,
            label="one_alice_surface_language",
            matched=", ".join(hit.casefold() for hit in surface_hits),
            correction=explain_the_one(),
        )
    return IdentityVerdict(
        ok=True,
        label="no_identity_split_detected",
        matched="",
        correction=explain_the_one(),
    )


def surface_receipt(surface: str, action: str = "") -> dict[str, Any]:
    """Build a receipt-shaped row for one surface acting as Alice's hand."""
    return {
        "truth_label": TRUTH_LABEL,
        "identity": IDENTITY,
        "surface": str(surface or "").strip(),
        "action": str(action or "").strip(),
        "global_chat_ledger": str(REPO_ROOT / ".sifta_state" / "alice_conversation.jsonl"),
        "correction": explain_the_one(),
    }


__all__ = [
    "IDENTITY",
    "IdentityVerdict",
    "TRUTH_LABEL",
    "classify_identity_text",
    "explain_the_one",
    "surface_receipt",
]
