#!/usr/bin/env python3
"""Stigmergic truth-navigation field.

This organ turns George's doctrine into a concrete routing surface:
Alice survives real environments by separating OBSERVED truth from memory,
doctrine, inference, and hallucination before she navigates.

It does not replace the visual, physics, causal, or hallucination organs.
It asks which organs must witness a claim before the claim can be used as
real-world navigation truth.

Ledger: .sifta_state/truth_navigation_receipts.jsonl
Truth label: SIFTA_TRUTH_NAVIGATION_FIELD_V1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ModuleNotFoundError:  # pragma: no cover - direct script fallback
    import sys

    _SCRIPT_REPO = Path(__file__).resolve().parent.parent
    if str(_SCRIPT_REPO) not in sys.path:
        sys.path.insert(0, str(_SCRIPT_REPO))
    from System.jsonl_file_lock import append_line_locked, read_text_locked


_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "SIFTA_TRUTH_NAVIGATION_FIELD_V1"
LEDGER_NAME = "truth_navigation_receipts.jsonl"

DIMENSIONS: dict[str, dict[str, Any]] = {
    "image_truth": {
        "keywords": (
            "image",
            "photo",
            "picture",
            "screenshot",
            "camera",
            "see",
            "visual",
            "room",
            "object",
        ),
        "evidence_kinds": (
            "body_screen_eye",
            "visual_confirmation",
            "screenshot",
            "camera",
            "ocr",
            "image_hash",
            "visual_receipt",
        ),
        "next_probe": "capture/attach image, run visual confirmation or OCR, record screenshot/image hash",
    },
    "physics_truth": {
        "keywords": (
            "physics",
            "physical",
            "power",
            "electricity",
            "temperature",
            "motion",
            "force",
            "battery",
            "hardware",
        ),
        "evidence_kinds": (
            "body_screen_eye",
            "physics_gate",
            "thermal",
            "energy",
            "hardware",
            "sensor",
            "measurement",
        ),
        "next_probe": "read hardware/sensor/physics-gate receipts before using the claim as physical truth",
    },
    "distance_truth": {
        "keywords": (
            "distance",
            "near",
            "far",
            "close",
            "address",
            "gps",
            "location",
            "street",
            "room",
            "navigate",
            "environment",
        ),
        "evidence_kinds": (
            "gps",
            "location_receipt",
            "map",
            "distance_measurement",
            "visual_confirmation",
        ),
        "next_probe": "verify location/distance with GPS/map/sensor or explicit owner-stated memory label",
    },
    "people_truth": {
        "keywords": (
            "people",
            "person",
            "human",
            "owner",
            "george",
            "ioan",
            "face",
            "voice",
            "contact",
        ),
        "evidence_kinds": (
            "owner_statement",
            "voice_identity",
            "face_detection",
            "contact_memory",
            "social_reference",
        ),
        "next_probe": "use owner statement, voice/face/contact receipts, or label as memory instead of observation",
    },
    "environment_truth": {
        "keywords": (
            "environment",
            "wake up",
            "adapt",
            "function",
            "navigation",
            "world",
            "real world",
            "room",
            "house",
            "outside",
        ),
        "evidence_kinds": (
            "body_screen_eye",
            "app_focus",
            "sensor_journal",
            "visual_confirmation",
            "gps",
            "network",
            "hardware",
        ),
        "next_probe": "collect current sensor/app-focus/environment receipts before acting as if the scene is known",
    },
}

DOCTRINE_RE = re.compile(
    r"\b(agi|ascii swimmers|truth|hallucination|survive|wake up|adapt|function|observer|observed)\b",
    re.IGNORECASE,
)


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _stable_hash(payload: Mapping[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _normalize_kind(packet: Mapping[str, Any]) -> str:
    raw = (
        packet.get("kind")
        or packet.get("truth_label")
        or packet.get("source")
        or packet.get("lane")
        or ""
    )
    return re.sub(r"[^a-z0-9_]+", "_", str(raw).casefold()).strip("_")


def _has_receipt_markers(packet: Mapping[str, Any]) -> bool:
    if packet.get("observed") is True:
        return True
    for key in (
        "receipt_id",
        "trace_id",
        "sha256",
        "screenshot_hash",
        "clearance_hash",
        "ledger",
    ):
        if packet.get(key):
            return True
    label = str(packet.get("truth_label") or "").upper()
    return label in {"OBSERVED", "OPERATIONAL", "VISUAL_CONFIRMATION", "PHYSICS_GATE_V1"}


def _detect_dimensions(claim_text: str) -> list[str]:
    low = str(claim_text or "").casefold()
    dims = []
    for dimension, spec in DIMENSIONS.items():
        if any(str(word).casefold() in low for word in spec["keywords"]):
            dims.append(dimension)
    if not dims and claim_text.strip():
        dims.append("environment_truth")
    return dims


def _supporting_packets(
    dimension: str,
    packets: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    kinds = tuple(str(k).casefold() for k in DIMENSIONS[dimension]["evidence_kinds"])
    support: list[dict[str, Any]] = []
    for packet in packets:
        kind = _normalize_kind(packet)
        if any(expected in kind for expected in kinds) or any(kind in expected for expected in kinds):
            support.append(
                {
                    "kind": kind,
                    "has_receipt_marker": _has_receipt_markers(packet),
                    "preview": str(packet.get("preview") or packet.get("text") or packet.get("notes") or "")[:180],
                }
            )
    return support


def truth_navigation_assessment(
    claim_text: str,
    *,
    evidence_packets: Iterable[Mapping[str, Any]] | None = None,
    state_dir: Path | str | None = None,
    write: bool = False,
    now: float | None = None,
) -> dict[str, Any]:
    """Classify a real-world claim by the evidence organs needed to trust it."""
    packets = [dict(p) for p in (evidence_packets or []) if isinstance(p, Mapping)]
    dimensions = _detect_dimensions(claim_text)
    dimension_rows = []
    missing = []
    for dimension in dimensions:
        support = _supporting_packets(dimension, packets)
        observed = bool(support) and all(row["has_receipt_marker"] for row in support)
        row = {
            "dimension": dimension,
            "status": "OBSERVED" if observed else "NEEDS_PROBE",
            "support": support,
            "next_probe": "" if observed else DIMENSIONS[dimension]["next_probe"],
        }
        dimension_rows.append(row)
        if not observed:
            missing.append(dimension)

    doctrine = bool(DOCTRINE_RE.search(claim_text or ""))
    if missing:
        verdict = "ARCHITECT_DOCTRINE_WITH_OPEN_PROBES" if doctrine else "HYPOTHESIS_NEEDS_PROBE"
    else:
        verdict = "OBSERVED"

    row: dict[str, Any] = {
        "ts": float(now if now is not None else time.time()),
        "trace_id": str(uuid.uuid4()),
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "kind": "TRUTH_NAVIGATION_ASSESSMENT",
        "claim_preview": re.sub(r"\s+", " ", str(claim_text or "")).strip()[:500],
        "architect_doctrine_detected": doctrine,
        "verdict": verdict,
        "dimensions": dimension_rows,
        "missing_probe_dimensions": missing,
        "ledger": str(_state_dir(state_dir) / LEDGER_NAME),
    }
    row["sha256"] = _stable_hash({k: v for k, v in row.items() if k != "sha256"})

    if write:
        append_line_locked(
            _state_dir(state_dir) / LEDGER_NAME,
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def latest_assessments(
    *,
    state_dir: Path | str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    path = _state_dir(state_dir) / LEDGER_NAME
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        text = read_text_locked(path, encoding="utf-8", errors="replace")
    except Exception:
        return []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows[-max(1, int(limit)) :]


def summary_for_prompt(*, state_dir: Path | str | None = None) -> str:
    rows = latest_assessments(state_dir=state_dir, limit=1)
    if not rows:
        return ""
    row = rows[-1]
    missing = row.get("missing_probe_dimensions") or []
    return (
        "TRUTH NAVIGATION FIELD:\n"
        f"- last_verdict={row.get('verdict')} missing={', '.join(missing) or 'none'}\n"
        "- Use OBSERVED receipts for image/physics/distance/person/environment claims before navigation."
    )


def prompt_block_for_claim(
    claim_text: str = "",
    *,
    state_dir: Path | str | None = None,
    write: bool = False,
) -> str:
    """Prompt-ready truth-navigation block for the current owner turn."""
    lines = [
        "TRUTH NAVIGATION FIELD:",
        "- Real-world navigation truth is stigmergic: image, physics, distance, people, and environment claims need matching receipts before I use them as OBSERVED.",
        "- Owner statements and Architect doctrine are valid memory/doctrine, but they are not camera/GPS/physics proof unless another organ witnessed them.",
        "- If probes are missing, I say what is missing and ask/act to collect the receipt instead of hallucinating certainty.",
    ]
    if claim_text.strip():
        row = truth_navigation_assessment(
            claim_text,
            state_dir=state_dir,
            write=write,
        )
        missing = row.get("missing_probe_dimensions") or []
        dims = ", ".join(d["dimension"] for d in row.get("dimensions") or [])
        lines.extend(
            [
                f"- current_turn_verdict={row.get('verdict')}",
                f"- current_turn_dimensions={dims or 'none'}",
                f"- current_turn_missing_probes={', '.join(missing) or 'none'}",
            ]
        )
    else:
        latest = summary_for_prompt(state_dir=state_dir).strip()
        if latest:
            lines.append(latest)
    return "\n".join(lines)


def doctrine_backlog() -> list[dict[str, str]]:
    return [
        {
            "task_id": "truth_nav_image_grounding",
            "task": "Route image/room/object claims through visual confirmation/OCR/image hash before speech or action.",
        },
        {
            "task_id": "truth_nav_physics_distance",
            "task": "Route physics, hardware, distance, and location claims through sensors/GPS/map/physics-gate receipts.",
        },
        {
            "task_id": "truth_nav_people_provenance",
            "task": "Route people/owner/social claims through owner statement, voice/face/contact provenance labels.",
        },
        {
            "task_id": "truth_nav_adaptive_environment_loop",
            "task": "On wake in a new environment, collect sensor/app-focus/visual/location receipts, then adapt policy from the field.",
        },
    ]


def _parse_evidence_json(text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    value = json.loads(text)
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        return [dict(value)]
    return []


def cli() -> int:
    parser = argparse.ArgumentParser(description="Stigmergic truth-navigation field")
    sub = parser.add_subparsers(dest="cmd")
    assess = sub.add_parser("assess", help="Assess a claim and optionally write a receipt")
    assess.add_argument("claim", help="Claim text")
    assess.add_argument("--evidence-json", default="", help="Evidence packet or list as JSON")
    assess.add_argument("--write", action="store_true", help="Append receipt")
    sub.add_parser("summary", help="Print latest prompt summary")
    sub.add_parser("backlog", help="Print doctrine-derived coding backlog")
    args = parser.parse_args()

    cmd = args.cmd or "summary"
    if cmd == "assess":
        row = truth_navigation_assessment(
            args.claim,
            evidence_packets=_parse_evidence_json(args.evidence_json),
            write=args.write,
        )
        print(json.dumps(row, indent=2, ensure_ascii=False))
        return 0
    if cmd == "summary":
        print(summary_for_prompt())
        return 0
    if cmd == "backlog":
        print(json.dumps(doctrine_backlog(), indent=2, ensure_ascii=False))
        return 0
    parser.print_help()
    return 2


__all__ = [
    "DIMENSIONS",
    "LEDGER_NAME",
    "TRUTH_LABEL",
    "doctrine_backlog",
    "latest_assessments",
    "prompt_block_for_claim",
    "summary_for_prompt",
    "truth_navigation_assessment",
]


if __name__ == "__main__":
    raise SystemExit(cli())
