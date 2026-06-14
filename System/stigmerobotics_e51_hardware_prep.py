#!/usr/bin/env python3
"""
System/stigmerobotics_e51_hardware_prep.py
==========================================

E51 — Physical robot hardware-prep safety chain (ABB IRB 2400 + NAO ARKOMA).

Defines the receipt chain required before any *physical* robot effector row is
considered prep-complete. Virtual bodies (E49/E50) remain OPERATIONAL; metal
motion stays HYPOTHESIS until lab/hardware receipts close the chain.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

_REPO = Path(__file__).resolve().parent.parent
_FIXTURE_GOOD = _REPO / "tests" / "fixtures" / "stigmero_e51_hardware_prep_good.jsonl"
_FIXTURE_GOOD_NAO = _REPO / "tests" / "fixtures" / "stigmero_e51_hardware_prep_nao_good.jsonl"
_FIXTURE_MISSING = _REPO / "tests" / "fixtures" / "stigmero_e51_hardware_prep_missing.jsonl"

ROBOT_REGISTRATION_KIND = "ROBOT_HARDWARE_REGISTRATION"
ROBOT_CLEARANCE_KIND = "ROBOT_SAFETY_CLEARANCE"
ROBOT_SENSOR_KIND = "ROBOT_SENSOR_RECEIPT"
ROBOT_INTENT_KIND = "ROBOT_EFFECTOR_INTENT"

ROBOT_PREP_KINDS = frozenset(
    {
        ROBOT_REGISTRATION_KIND,
        ROBOT_CLEARANCE_KIND,
        ROBOT_SENSOR_KIND,
        ROBOT_INTENT_KIND,
    }
)

REQUIRED_CLEARANCE_KEYS = frozenset(
    {
        "e34_gate_checked",
        "human_review_required",
        "virtual_dry_run_ok",
    }
)

REQUIRED_SENSOR_KEYS = frozenset(
    {
        "body_id",
        "sensor_class",
        "measurement_hash",
        "truth_label",
    }
)

PHYSICAL_BODY_MAP: dict[str, dict[str, Any]] = {
    "abb_irb2400_physical": {
        "virtual_body_id": "abb_irb2400_virtual",
        "robot_model": "ABB_IRB2400",
        "dof": 6,
        "dataset": "luisatencio/abb-irb-2400-arm-robot-kinematics-dataset",
    },
    "nao_arkoma_physical": {
        "virtual_body_id": "nao_arkoma_virtual",
        "robot_model": "NAO_H25_v3.3",
        "dof": 5,
        "dataset": "10.17632/brg4dz8nbb.1",
    },
}

_FIXTURE_GOOD_BY_BODY = {
    "abb_irb2400_physical": _FIXTURE_GOOD,
    "nao_arkoma_physical": _FIXTURE_GOOD_NAO,
}

CHAIN_STEPS: tuple[str, ...] = (
    "1. ROBOT_HARDWARE_REGISTRATION for (homeworld_serial, source_ide)",
    "2. ROBOT_SAFETY_CLEARANCE with E34 gate + human_review_required",
    "3. ROBOT_SENSOR_RECEIPT from virtual dry-run echo",
    "4. ROBOT_EFFECTOR_INTENT — human-review-ready only, not execution",
    "5. Physical effector_request/effector_receipt — HYPOTHESIS until hardware GO",
)


@dataclass(frozen=True)
class HardwarePrepViolation:
    row_index: int
    kind: str
    reason: str


@dataclass(frozen=True)
class HardwarePrepReport:
    body_id: str
    virtual_body_id: str
    steps_present: dict[str, bool]
    violations: tuple[HardwarePrepViolation, ...]
    chain_steps: tuple[str, ...] = CHAIN_STEPS
    truth_label: str = "HYPOTHESIS"

    @property
    def ok(self) -> bool:
        return not self.violations and all(self.steps_present.values())

    @property
    def proof_of_property(self) -> dict[str, Any]:
        return {
            "E51": "Physical robot hardware-prep safety chain",
            "body_id": self.body_id,
            "virtual_body_id": self.virtual_body_id,
            "steps_present": dict(self.steps_present),
            "violation_count": len(self.violations),
            "falsifier": "missing registration/clearance/sensor/intent on same channel",
            "truth_label": self.truth_label,
            "physical_motion_label": "HYPOTHESIS",
        }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _channel(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("homeworld_serial", "")), str(row.get("source_ide", "")))


def _payload_keys_ok(payload: Mapping[str, Any], required: frozenset[str]) -> bool:
    return required.issubset(set(payload.keys()))


def validate_hardware_prep_trace(
    rows: Iterable[Mapping[str, Any]],
    *,
    target_body_id: str,
) -> HardwarePrepReport:
    spec = PHYSICAL_BODY_MAP.get(target_body_id)
    if spec is None:
        return HardwarePrepReport(
            body_id=target_body_id,
            virtual_body_id="",
            steps_present={},
            violations=(
                HardwarePrepViolation(-1, "config", f"unknown physical body_id {target_body_id}"),
            ),
        )

    indexed = list(rows)
    steps = {
        ROBOT_REGISTRATION_KIND: False,
        ROBOT_CLEARANCE_KIND: False,
        ROBOT_SENSOR_KIND: False,
        ROBOT_INTENT_KIND: False,
    }
    violations: list[HardwarePrepViolation] = []
    registrations: set[tuple[str, str]] = set()
    clearances: set[tuple[str, str]] = set()
    sensors: set[tuple[str, str]] = set()

    for idx, row in enumerate(indexed):
        kind = str(row.get("kind", ""))
        if kind not in ROBOT_PREP_KINDS:
            continue
        channel = _channel(row)
        payload = dict(row.get("payload", {}))
        body = str(payload.get("body_id", row.get("target_body_id", "")))

        if kind == ROBOT_REGISTRATION_KIND:
            if body == target_body_id:
                registrations.add(channel)
                steps[kind] = True
        elif kind == ROBOT_CLEARANCE_KIND:
            if body == target_body_id and _payload_keys_ok(payload, REQUIRED_CLEARANCE_KEYS):
                if channel in registrations:
                    clearances.add(channel)
                    steps[kind] = True
                else:
                    violations.append(
                        HardwarePrepViolation(idx, kind, "clearance_without_registration")
                    )
            elif body == target_body_id:
                violations.append(HardwarePrepViolation(idx, kind, "clearance_payload_incomplete"))
        elif kind == ROBOT_SENSOR_KIND:
            if (
                body == spec["virtual_body_id"]
                and _payload_keys_ok(payload, REQUIRED_SENSOR_KEYS)
                and channel in clearances
            ):
                sensors.add(channel)
                steps[kind] = True
            elif body == spec["virtual_body_id"]:
                violations.append(HardwarePrepViolation(idx, kind, "sensor_payload_or_order_invalid"))
        elif kind == ROBOT_INTENT_KIND:
            if body == target_body_id and channel in sensors:
                if payload.get("human_review_ready") is True and payload.get("execute") is False:
                    steps[kind] = True
                else:
                    violations.append(
                        HardwarePrepViolation(idx, kind, "intent_must_be_human_review_only")
                    )
            elif body == target_body_id:
                violations.append(HardwarePrepViolation(idx, kind, "intent_without_sensor_prereq"))

    for kind, present in steps.items():
        if not present:
            violations.append(HardwarePrepViolation(-1, kind, "missing_step"))

    return HardwarePrepReport(
        body_id=target_body_id,
        virtual_body_id=str(spec["virtual_body_id"]),
        steps_present=steps,
        violations=tuple(violations),
    )


def fixture_hardware_prep(path: Path | None = None, *, target_body_id: str) -> HardwarePrepReport:
    fixture = path or _FIXTURE_GOOD_BY_BODY.get(target_body_id, _FIXTURE_GOOD)
    return validate_hardware_prep_trace(load_jsonl(fixture), target_body_id=target_body_id)


def hardware_prep_ok(path: Path, *, target_body_id: str) -> bool:
    return fixture_hardware_prep(path, target_body_id=target_body_id).ok


def list_physical_bodies() -> tuple[str, ...]:
    return tuple(PHYSICAL_BODY_MAP.keys())
