#!/usr/bin/env python3
"""Reality/fiction boundary for Alice speech.

Normal SIFTA reality cannot invent scenes. Alice may write dreams, fiction, or
screenplays only when the user explicitly asks for that lane, and the output
must be labeled as fiction/dream/script instead of observation.

This organ is intentionally small and conservative. It does not try to solve
vision. It only blocks high-risk phrases where a reply presents an unreceipted
scene as observed reality.

Truth label: REALITY_FICTION_BOUNDARY_V1.
Ledger: .sifta_state/reality_fiction_boundary.jsonl
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - standalone fallback
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "reality_fiction_boundary.jsonl"
TRUTH_LABEL = "REALITY_FICTION_BOUNDARY_V1"

FICTION_LANE = "FICTION_OR_DREAM_LANE"
REALITY_LANE = "RECEIPT_REALITY_LANE"

_FICTION_REQUEST_RE = re.compile(
    r"\b("
    r"fiction\s+(?:couch|lounge|mode)|"
    r"dream\s+(?:mode|lane|organ|story|scene)|"
    r"screenplay|movie\s+script|write\s+(?:a\s+)?(?:story|scene|fiction|script)|"
    r"make\s+up\s+(?:a\s+)?(?:story|scene)|"
    r"imagine\s+(?:a\s+)?(?:scene|story)"
    r")\b",
    re.IGNORECASE,
)

_FICTION_LABEL_RE = re.compile(
    r"^\s*(?:\[(?:FICTION|DREAM|SCREENPLAY|SCRIPT)\]|(?:FICTION|DREAM|SCREENPLAY|SCRIPT)\s*:)",
    re.IGNORECASE,
)

_SCENE_TERMS: tuple[str, ...] = (
    "kitchen",
    "window",
    "couch",
    "lounge",
    "bedroom",
    "bathroom",
    "hallway",
    "street",
    "garden",
    "forest",
    "beach",
    "sunlight",
    "smoke",
    "ashtray",
    "table",
    "chair",
)

_SCENE_ALT = "|".join(re.escape(term) for term in _SCENE_TERMS)

_OBSERVED_SCENE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "first_person_visual_scene_claim",
        re.compile(
            rf"\bI\s+(?:can\s+)?(?:see|saw|observe|notice|recognize|spot|watch|watched)\b"
            rf"(?:(?!\n).){{0,160}}\b(?:{_SCENE_ALT})\b",
            re.IGNORECASE,
        ),
    ),
    (
        "camera_visual_scene_claim",
        re.compile(
            rf"\b(?:the\s+)?(?:camera|webcam|screen|screenshot|image|picture)\b"
            rf"(?:(?!\n).){{0,80}}\b(?:shows?|showed|captures?|contains?|reveals?)\b"
            rf"(?:(?!\n).){{0,160}}\b(?:{_SCENE_ALT})\b",
            re.IGNORECASE,
        ),
    ),
    (
        "asserted_scene_presence",
        re.compile(
            rf"\b(?:there\s+is|there\s+are|I\s+am\s+in|we\s+are\s+in)\b"
            rf"(?:(?!\n).){{0,80}}\b(?:{_SCENE_ALT})\b",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True)
class RealityFictionAudit:
    ok: bool
    lane: str
    truth_label: str = TRUTH_LABEL
    forbidden: bool = False
    needs_label: bool = False
    patterns: tuple[str, ...] = ()
    scene_terms: tuple[str, ...] = ()
    replacement: str = ""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _state_dir(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else STATE_DIR


def classify_request(text: str) -> str:
    """Return the speech lane requested by the user/context text."""
    return FICTION_LANE if _FICTION_REQUEST_RE.search(text or "") else REALITY_LANE


def _terms_in_text(text: str) -> tuple[str, ...]:
    low = (text or "").casefold()
    found: list[str] = []
    for term in _SCENE_TERMS:
        if term not in low:
            continue
        if term == "window" and re.search(
            r"\b(?:chat|talk|app|application|sifta|os|desktop|browser|writer)\s+window\b",
            low,
        ):
            continue
        found.append(term)
    return tuple(found)


def _evidence_covers_terms(terms: Sequence[str], evidence_text: str) -> bool:
    if not terms:
        return True
    evidence_low = (evidence_text or "").casefold()
    return all(term.casefold() in evidence_low for term in terms)


def _with_sha(audit: RealityFictionAudit) -> RealityFictionAudit:
    body = audit.to_dict()
    body.pop("sha256", None)
    sha = hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return RealityFictionAudit(**{**audit.to_dict(), "sha256": sha})


def audit_output(
    text: str,
    *,
    prior_user_text: str = "",
    evidence_text: str = "",
    state_dir: str | Path | None = None,
    write: bool = False,
    now: float | None = None,
) -> RealityFictionAudit:
    """Audit one candidate Alice reply for invented observed-scene leakage."""
    reply = text or ""
    lane = classify_request(prior_user_text)
    labeled = bool(_FICTION_LABEL_RE.search(reply))

    if lane == FICTION_LANE:
        audit = RealityFictionAudit(
            ok=True,
            lane=lane,
            needs_label=bool(reply.strip() and not labeled),
            replacement="" if labeled else "[FICTION]\n" + reply.lstrip(),
        )
        audit = _with_sha(audit)
        if write:
            write_boundary_receipt(audit, original_text=reply, state_dir=state_dir, now=now)
        return audit

    patterns: list[str] = []
    terms: set[str] = set()
    for name, rx in _OBSERVED_SCENE_PATTERNS:
        if rx.search(reply):
            patterns.append(name)
            terms.update(_terms_in_text(rx.search(reply).group(0)))

    covered = _evidence_covers_terms(tuple(sorted(terms)), evidence_text)
    forbidden = bool(patterns and not covered)
    replacement = ""
    if forbidden:
        replacement = (
            "I do not have a receipt for that scene. I can describe only the "
            "SIFTA OS/chat/screenshot evidence I actually have, or I can switch "
            "to labeled fiction, dream, or screenplay mode if you ask for that."
        )

    audit = RealityFictionAudit(
        ok=not forbidden,
        lane=lane,
        forbidden=forbidden,
        patterns=tuple(dict.fromkeys(patterns)),
        scene_terms=tuple(sorted(terms)),
        replacement=replacement,
    )
    audit = _with_sha(audit)
    if write and (forbidden or patterns):
        write_boundary_receipt(audit, original_text=reply, state_dir=state_dir, now=now)
    return audit


def write_boundary_receipt(
    audit: RealityFictionAudit,
    *,
    original_text: str = "",
    state_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    row = {
        "schema": "SIFTA_REALITY_FICTION_BOUNDARY_V1",
        "ts": float(now if now is not None else time.time()),
        "kind": "REALITY_FICTION_BOUNDARY",
        "truth_label": audit.truth_label,
        "trace_id": audit.trace_id,
        "sha256": audit.sha256,
        "payload": audit.to_dict(),
        "original_preview": " ".join((original_text or "").split())[:260],
    }
    append_line_locked(
        _state_dir(state_dir) / LEDGER_NAME,
        json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n",
    )
    return row


def reality_fiction_prompt_block() -> str:
    return "\n".join(
        [
            "[reality-fiction] Scenes in normal SIFTA reality sort to a receipt: camera, OCR, layout, or file evidence, not weight-prior imagination.",
            "[reality-fiction] Fiction or dream sorts to an explicit owner ask; when that receipt exists, I label the reply FICTION, DREAM, or SCREENPLAY.",
            "[reality-fiction] If I lack camera/OCR/layout/file receipt for a kitchen, window, room, person, or object, I say I do not have a receipt.",
        ]
    )


__all__ = [
    "FICTION_LANE",
    "LEDGER_NAME",
    "REALITY_LANE",
    "RealityFictionAudit",
    "TRUTH_LABEL",
    "audit_output",
    "classify_request",
    "reality_fiction_prompt_block",
    "write_boundary_receipt",
]


if __name__ == "__main__":
    import sys

    sample = " ".join(sys.argv[1:]) or "I see a kitchen window in the screenshot."
    print(json.dumps(audit_output(sample).to_dict(), indent=2, sort_keys=True))
