#!/usr/bin/env python3
"""
System/stigmerobotics_biohybrid_boundary.py
===========================================

E47 - Bio-hybrid / VLP boundary ledger.

This module is deliberately a safety boundary, not a wet-lab protocol.
It models how SIFTA may represent future bio-hybrid or VLP-adjacent signals
as sanitized, receipt-backed rows without storing raw biological instructions.

Allowed scope:
  - schema-level sensor receipts
  - safety-clearance receipts
  - human-review-ready intent rows
  - explicit quarantine of forbidden protocol payload fields

Forbidden scope:
  - no sequences
  - no plasmids / primers
  - no culture or infiltration instructions
  - no doses, concentrations, incubation settings, temperatures, or timings
  - no direct biological actuation from this module

Proof obligation:
  A BIO_EFFECTOR_INTENT row is HUMAN_REVIEW_READY only when the same
  (homeworld_serial, source_ide) channel has prior BIO_BRIDGE_REGISTRATION,
  BIO_SAFETY_CLEARANCE, and BIO_SENSOR_RECEIPT rows, and no row payload
  contains forbidden protocol fields. HUMAN_REVIEW_READY is not execution.

truth_label: OPERATIONAL for ledger boundary; HYPOTHESIS for physical biology.

Section 8.6 compliance: side-effect free. Live reads happen only when
live_biohybrid_report() is explicitly called by the widget.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Iterable, Mapping


_REPO = Path(__file__).resolve().parent.parent
_TRACE = _REPO / ".sifta_state" / "ide_stigmergic_trace.jsonl"


BIO_REGISTRATION_KIND = "BIO_BRIDGE_REGISTRATION"
BIO_SENSOR_KIND = "BIO_SENSOR_RECEIPT"
BIO_CLEARANCE_KIND = "BIO_SAFETY_CLEARANCE"
BIO_INTENT_KIND = "BIO_EFFECTOR_INTENT"
BIO_QUARANTINE_KIND = "BIO_QUARANTINE"

BIO_KINDS = frozenset(
    {
        BIO_REGISTRATION_KIND,
        BIO_SENSOR_KIND,
        BIO_CLEARANCE_KIND,
        BIO_INTENT_KIND,
        BIO_QUARANTINE_KIND,
    }
)

REQUIRED_SENSOR_PAYLOAD_KEYS = frozenset(
    {
        "signal_id",
        "sensor_class",
        "measurement_hash",
        "truth_label",
    }
)

REQUIRED_CLEARANCE_PAYLOAD_KEYS = frozenset(
    {
        "nppl_scope",
        "no_wet_protocol",
        "human_review_required",
    }
)

# Keys, not values. The presence of any of these keys means the payload is
# too operational for this ledger boundary and must be quarantined.
FORBIDDEN_PROTOCOL_KEYS = frozenset(
    {
        "sequence",
        "nucleotide_sequence",
        "amino_acid_sequence",
        "plasmid",
        "primer",
        "strain",
        "dose",
        "dosage",
        "moi",
        "concentration",
        "culture_condition",
        "growth_media",
        "incubation",
        "temperature_c",
        "protocol",
        "protocol_steps",
        "infiltration",
        "agrobacterium",
        "p19",
    }
)


class BioHybridState(Enum):
    SENSOR_ONLY = auto()
    HUMAN_REVIEW_READY = auto()
    BLOCKED = auto()
    QUARANTINED = auto()


@dataclass(frozen=True)
class BioHybridRow:
    row_index: int
    kind: str
    ts: float
    channel: tuple[str, str]
    trace_id: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForbiddenPayload:
    row_index: int
    kind: str
    trace_id: str
    forbidden_keys: tuple[str, ...]


@dataclass(frozen=True)
class BioHybridIntentGate:
    intent: BioHybridRow
    status: BioHybridState
    missing: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class BioHybridBoundaryReport:
    rows: tuple[BioHybridRow, ...]
    forbidden_payloads: tuple[ForbiddenPayload, ...]
    intent_gates: tuple[BioHybridIntentGate, ...]
    sensor_payload_violations: tuple[str, ...]
    clearance_payload_violations: tuple[str, ...]

    @property
    def state(self) -> BioHybridState:
        if self.forbidden_payloads:
            return BioHybridState.QUARANTINED
        if any(g.status == BioHybridState.BLOCKED for g in self.intent_gates):
            return BioHybridState.BLOCKED
        if any(g.status == BioHybridState.HUMAN_REVIEW_READY for g in self.intent_gates):
            return BioHybridState.HUMAN_REVIEW_READY
        return BioHybridState.SENSOR_ONLY

    @property
    def ok(self) -> bool:
        return (
            self.state in {BioHybridState.SENSOR_ONLY, BioHybridState.HUMAN_REVIEW_READY}
            and not self.sensor_payload_violations
            and not self.clearance_payload_violations
        )

    @property
    def n_sensors(self) -> int:
        return sum(1 for r in self.rows if r.kind == BIO_SENSOR_KIND)

    @property
    def n_clearances(self) -> int:
        return sum(1 for r in self.rows if r.kind == BIO_CLEARANCE_KIND)

    @property
    def n_intents(self) -> int:
        return sum(1 for r in self.rows if r.kind == BIO_INTENT_KIND)

    @property
    def direct_actuation_allowed(self) -> bool:
        return False

    @property
    def proof_of_property(self) -> dict[str, Any]:
        return {
            "E47": "Bio-hybrid / VLP boundary ledger",
            "state": self.state.name,
            "n_rows": len(self.rows),
            "n_sensors": self.n_sensors,
            "n_clearances": self.n_clearances,
            "n_intents": self.n_intents,
            "n_forbidden_payloads": len(self.forbidden_payloads),
            "direct_actuation_allowed": self.direct_actuation_allowed,
            "gate": (
                "BIO_EFFECTOR_INTENT requires same-channel registration, "
                "safety clearance, and sensor receipt before HUMAN_REVIEW_READY"
            ),
            "safety_boundary": (
                "HUMAN_REVIEW_READY means reviewable ledger intent only; "
                "this module never executes a physical biological action"
            ),
            "forbidden_payload_keys": sorted(FORBIDDEN_PROTOCOL_KEYS),
            "falsifier": (
                "raw protocol key OR missing same-channel prerequisite -> "
                "report.ok is False"
            ),
            "truth_label": "OPERATIONAL" if self.ok else "BROKEN",
        }

    def summary_lines(self) -> list[str]:
        lines = [
            f"E47 Bio-hybrid Boundary: {self.state.name}",
            f"rows: {len(self.rows)}",
            f"sensors: {self.n_sensors}",
            f"clearances: {self.n_clearances}",
            f"intents: {self.n_intents}",
            f"forbidden_payloads: {len(self.forbidden_payloads)}",
            f"direct_actuation_allowed: {self.direct_actuation_allowed}",
        ]
        for gate in self.intent_gates[:8]:
            lines.append(
                f"intent row {gate.intent.row_index}: {gate.status.name} "
                f"missing={','.join(gate.missing) or 'none'}"
            )
        if self.forbidden_payloads:
            lines.append("quarantine:")
            for bad in self.forbidden_payloads[:8]:
                lines.append(
                    f"  row {bad.row_index} {bad.kind}: {','.join(bad.forbidden_keys)}"
                )
        return lines


def _float_ts(value: Any) -> float:
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return 0.0
    return ts if math.isfinite(ts) else 0.0


def _payload_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = row.get("payload", {})
    if isinstance(payload, dict):
        return dict(payload)
    if isinstance(payload, str) and payload.strip().startswith("{"):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _channel(row: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("homeworld_serial") or "UNKNOWN"),
        str(row.get("source_ide") or row.get("doctor") or "UNKNOWN"),
    )


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            keys.add(str(key).strip().lower())
            keys.update(_walk_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(_walk_keys(item))
    return keys


def _bio_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[BioHybridRow, ...]:
    out: list[BioHybridRow] = []
    for idx, row in enumerate(rows):
        kind = str(row.get("kind") or "")
        if kind not in BIO_KINDS:
            continue
        out.append(
            BioHybridRow(
                row_index=idx,
                kind=kind,
                ts=_float_ts(row.get("ts")),
                channel=_channel(row),
                trace_id=str(row.get("trace_id") or ""),
                payload=_payload_dict(row),
            )
        )
    return tuple(out)


def _missing_keys(payload: Mapping[str, Any], required: frozenset[str]) -> tuple[str, ...]:
    present = {str(k).strip() for k in payload.keys()}
    return tuple(sorted(required - present))


def build_biohybrid_report(rows: Iterable[Mapping[str, Any]]) -> BioHybridBoundaryReport:
    bio_rows = _bio_rows(rows)
    forbidden: list[ForbiddenPayload] = []
    sensor_violations: list[str] = []
    clearance_violations: list[str] = []

    for row in bio_rows:
        bad_keys = tuple(sorted(_walk_keys(row.payload) & FORBIDDEN_PROTOCOL_KEYS))
        if bad_keys:
            forbidden.append(
                ForbiddenPayload(
                    row_index=row.row_index,
                    kind=row.kind,
                    trace_id=row.trace_id,
                    forbidden_keys=bad_keys,
                )
            )
        if row.kind == BIO_SENSOR_KIND:
            missing = _missing_keys(row.payload, REQUIRED_SENSOR_PAYLOAD_KEYS)
            if missing:
                sensor_violations.append(
                    f"row {row.row_index} missing sensor keys: {','.join(missing)}"
                )
        if row.kind == BIO_CLEARANCE_KIND:
            missing = _missing_keys(row.payload, REQUIRED_CLEARANCE_PAYLOAD_KEYS)
            if missing:
                clearance_violations.append(
                    f"row {row.row_index} missing clearance keys: {','.join(missing)}"
                )

    gates: list[BioHybridIntentGate] = []
    for intent in (row for row in bio_rows if row.kind == BIO_INTENT_KIND):
        prior = [
            row for row in bio_rows
            if row.channel == intent.channel and row.ts <= intent.ts
        ]
        has_registration = any(row.kind == BIO_REGISTRATION_KIND for row in prior)
        has_clearance = any(row.kind == BIO_CLEARANCE_KIND for row in prior)
        has_sensor = any(row.kind == BIO_SENSOR_KIND for row in prior)
        missing = []
        if not has_registration:
            missing.append(BIO_REGISTRATION_KIND)
        if not has_clearance:
            missing.append(BIO_CLEARANCE_KIND)
        if not has_sensor:
            missing.append(BIO_SENSOR_KIND)
        if missing:
            gates.append(
                BioHybridIntentGate(
                    intent=intent,
                    status=BioHybridState.BLOCKED,
                    missing=tuple(missing),
                    note="same-channel prerequisite missing",
                )
            )
        else:
            gates.append(
                BioHybridIntentGate(
                    intent=intent,
                    status=BioHybridState.HUMAN_REVIEW_READY,
                    missing=(),
                    note="reviewable ledger intent only; no direct actuation",
                )
            )

    return BioHybridBoundaryReport(
        rows=bio_rows,
        forbidden_payloads=tuple(forbidden),
        intent_gates=tuple(gates),
        sensor_payload_violations=tuple(sensor_violations),
        clearance_payload_violations=tuple(clearance_violations),
    )


def biohybrid_boundary_ok(rows: Iterable[Mapping[str, Any]]) -> bool:
    return build_biohybrid_report(rows).ok


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def live_biohybrid_report(*, limit: int = 300) -> BioHybridBoundaryReport:
    rows = load_jsonl(_TRACE)
    return build_biohybrid_report(rows[-limit:])


if __name__ == "__main__":
    print("\n".join(live_biohybrid_report().summary_lines()))
