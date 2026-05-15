#!/usr/bin/env python3
"""Recognize screenshots of Alice's own SIFTA OS surfaces.

Attachment vision already proves file metadata and OCR/layout. This module adds
one narrower inference layer:

    "This attached image appears to be my own SIFTA OS/UI state."

It is not a general vision model and not unmediated sight. It only consumes OCR
rows and layout labels produced by the local attachment vision lane.

Truth label: SELF_SCREENSHOT_RECOGNITION_V1.
Ledger: .sifta_state/self_screenshot_evidence.jsonl
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
LEDGER_NAME = "self_screenshot_evidence.jsonl"
TRUTH_LABEL = "SELF_SCREENSHOT_RECOGNITION_V1"
EVIDENCE_KIND = "SELF_SCREENSHOT_EVIDENCE"
TRUTH_BOUNDARY = (
    "OCR/layout evidence only. This recognizer classifies SIFTA UI artifacts "
    "from local attachment receipts; it does not claim full pixel-level vision."
)


_SELF_SURFACE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("sifta_os", r"\bsifta(?:\s+python\s+gui)?\s+os\b|\bsifta\b"),
    ("alice_alive", r"\balice\s+alive\b|\balice\s+is\s+listening\b"),
    ("talk_widget", r"\btype\s+to\s+alice\b|\bhearing\s+you\b|\blistening\s+-\s+just\s+talk\b"),
    ("swarm_app_store", r"\bswarm\s+app\s+store\b"),
    ("app_focus", r"\bmesh:\s*global\s+mode\b|\bsaliency:\s*on\b"),
    ("sifta_ledger", r"\bmemory_ledger\b|\bide_stigmergic_trace\b|\bwork_receipts\b"),
    ("stgm_receipt", r"\bstgm\b|\breceipt\b|\btrace_id\b"),
    ("writer", r"\bstigmergic\s+writer\b|\.sifta\.md\b"),
    ("acer", r"\bacer\b|\bletters\s+of\s+my\s+alphabet\b"),
    ("mammal", r"\bmammal\b|\bdrug\s+discovery\b"),
    ("tsp", r"\btraveling\s+salesman\b|\btsplib\b"),
)

_DOCTOR_PATTERNS: tuple[tuple[str, str], ...] = (
    ("codex", r"\bcodex\b|\bgpt-5\b|\bgpt\s*5\b"),
    ("claude", r"\bclaude\b|\bopus\b|\bcowork\b"),
    ("cursor", r"\bcursor\b"),
    ("antigravity", r"\bantigravity\b|\bag31\b|\bag46\b"),
)

_EXTERNAL_MEDIA_PATTERNS = re.compile(
    r"\byoutube\b|\bsubscribe\b|\bviews\b|\bcomment\b|\btranscript\b|\bskip navigation\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SelfScreenshotEvidence:
    ok: bool
    evidence_kind: str = EVIDENCE_KIND
    truth_label: str = TRUTH_LABEL
    confidence: float = 0.0
    surface_kind: str = "unknown_image"
    self_labels: tuple[str, ...] = ()
    doctor_labels: tuple[str, ...] = ()
    zones: dict[str, list[str]] = field(default_factory=dict)
    evidence_terms: tuple[str, ...] = ()
    image_path: str = ""
    image_sha256: str = ""
    reply_hint: str = ""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _state_dir(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else STATE_DIR


def _compact(text: Any, limit: int = 120) -> str:
    return " ".join(str(text or "").split())[:limit]


def _texts_from_ocr(ocr_rows: Sequence[Mapping[str, Any]] | None) -> list[str]:
    texts: list[str] = []
    for row in ocr_rows or []:
        if not isinstance(row, Mapping):
            continue
        text = _compact(row.get("text"), 220)
        if text:
            texts.append(text)
    return texts


def _labels_from_zones(zone_labels: Mapping[str, Any] | None) -> tuple[dict[str, list[str]], list[str]]:
    zones: dict[str, list[str]] = {}
    labels: list[str] = []
    if not isinstance(zone_labels, Mapping):
        return zones, labels
    for zone in ("left", "middle", "right"):
        raw = zone_labels.get(zone)
        if isinstance(raw, list):
            values = [_compact(v, 80) for v in raw if _compact(v, 80)]
        elif raw:
            values = [_compact(raw, 80)]
        else:
            values = []
        if values:
            zones[zone] = values
            labels.extend(values)
    return zones, labels


def _match_patterns(text: str, patterns: Sequence[tuple[str, str]]) -> list[str]:
    found: list[str] = []
    for label, pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            found.append(label)
    return found


def _surface_kind(self_labels: Sequence[str], doctor_labels: Sequence[str]) -> str:
    s = set(self_labels)
    if doctor_labels and s:
        return "sifta_os_with_doctor_panes"
    if {"alice_alive", "talk_widget"} & s:
        return "alice_talk_surface"
    if {"acer", "writer", "mammal", "tsp"} & s:
        return "sifta_app_surface"
    if s:
        return "sifta_os_surface"
    if doctor_labels:
        return "doctor_workbench"
    return "unknown_image"


def _reply(evidence: SelfScreenshotEvidence) -> str:
    if not evidence.ok:
        return (
            "I inspected the attachment evidence, but I do not have enough "
            "OCR/layout proof to call it my own SIFTA surface."
        )
    pieces = [
        "I recognize this as a screenshot of my own SIFTA OS surface.",
        "This is evidence about my current body/UI state, not random external media.",
    ]
    if evidence.surface_kind:
        pieces.append(f"Surface class: {evidence.surface_kind}.")
    if evidence.zones:
        zone_bits = "; ".join(
            f"{zone}: {', '.join(labels)}" for zone, labels in evidence.zones.items()
        )
        pieces.append(f"Layout evidence: {zone_bits}.")
    if evidence.doctor_labels:
        pieces.append(f"Doctor panes detected: {', '.join(evidence.doctor_labels)}.")
    pieces.append("Boundary: OCR/layout evidence only; I will not fabricate hidden pixels.")
    return " ".join(pieces)


def _with_sha(evidence: SelfScreenshotEvidence) -> SelfScreenshotEvidence:
    body = evidence.to_dict()
    body.pop("sha256", None)
    body.pop("reply_hint", None)
    sha = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return SelfScreenshotEvidence(**{**evidence.to_dict(), "sha256": sha})


def recognize_self_screenshot(
    *,
    ocr_rows: Sequence[Mapping[str, Any]] | None = None,
    zone_labels: Mapping[str, Any] | None = None,
    image_path: str | Path = "",
    image_sha256: str = "",
    user_text: str = "",
    state_dir: str | Path | None = None,
    write: bool = False,
    now: float | None = None,
) -> SelfScreenshotEvidence:
    """Classify whether attachment OCR/layout points to Alice's own UI."""
    zones, zone_text_labels = _labels_from_zones(zone_labels)
    ocr_texts = _texts_from_ocr(ocr_rows)
    joined = "\n".join([*ocr_texts, *zone_text_labels, _compact(user_text, 500)])

    self_labels = sorted(set(_match_patterns(joined, _SELF_SURFACE_PATTERNS)))
    doctor_labels = sorted(set(_match_patterns(joined, _DOCTOR_PATTERNS)))
    zone_self_hit = any("alice/sifta" in label.casefold() for label in zone_text_labels)
    external_media = bool(_EXTERNAL_MEDIA_PATTERNS.search(joined))

    score = 0.0
    score += min(0.55, 0.125 * len(self_labels))
    score += min(0.25, 0.08 * len(doctor_labels))
    score += 0.20 if zone_self_hit else 0.0
    if external_media and not self_labels:
        score -= 0.25
    confidence = round(max(0.0, min(1.0, score)), 4)
    ok = bool(confidence >= 0.25 and (self_labels or zone_self_hit))
    surface = _surface_kind(self_labels, doctor_labels)

    evidence = SelfScreenshotEvidence(
        ok=ok,
        confidence=confidence,
        surface_kind=surface,
        self_labels=tuple(self_labels),
        doctor_labels=tuple(doctor_labels),
        zones=zones,
        evidence_terms=tuple([*self_labels, *doctor_labels]),
        image_path=str(image_path),
        image_sha256=str(image_sha256 or ""),
    )
    evidence = SelfScreenshotEvidence(**{**evidence.to_dict(), "reply_hint": _reply(evidence)})
    evidence = _with_sha(evidence)
    if write:
        write_self_screenshot_evidence(evidence, state_dir=state_dir, now=now)
    return evidence


def write_self_screenshot_evidence(
    evidence: SelfScreenshotEvidence,
    *,
    state_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    row = {
        "schema": "SIFTA_SELF_SCREENSHOT_EVIDENCE_V1",
        "ts": float(now if now is not None else time.time()),
        "kind": EVIDENCE_KIND,
        "truth_label": evidence.truth_label,
        "trace_id": evidence.trace_id,
        "sha256": evidence.sha256,
        "payload": evidence.to_dict(),
        "truth_boundary": TRUTH_BOUNDARY,
    }
    append_line_locked(
        _state_dir(state_dir) / LEDGER_NAME,
        json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n",
    )
    return row


__all__ = [
    "EVIDENCE_KIND",
    "LEDGER_NAME",
    "SelfScreenshotEvidence",
    "TRUTH_BOUNDARY",
    "TRUTH_LABEL",
    "recognize_self_screenshot",
    "write_self_screenshot_evidence",
]
