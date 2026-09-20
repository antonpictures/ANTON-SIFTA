"""SIFTA adaptive contracts (job C0) — frozen typed records + rover intent/event v1.

This module implements the rigorous validation engine, typed records, and wire contracts
for Alice's adaptive intelligence. It ensures that all signals crossing the boundary
between the intelligence cortex and physical adapters are strictly typed, non-finite-free,
and version-locked.

Contract Laws:
1. Unknown values must be expressed as explicit nulls (None), never absent keys or empty strings.
2. Non-finite numbers (NaN, Inf) are strictly forbidden on the wire.
3. Every record must be version-locked via a schema hash.
4. State transitions are immutable once terminal.
5. Acceptance of a command is not success; success requires verified postconditions.
"""

from __future__ import annotations

import argparse
import copy
import datetime as _dt
import hashlib
import json
import math
import re
import sys
import uuid
from dataclasses import dataclass, field, fields as dc_fields
from typing import Any, ClassVar, Optional, Sequence, Union, Mapping

# --- Constants ---
RECORDS_SCHEMA_VERSION = "1.0.0"
INTENT_SCHEMA = "sifta.rover.intent/1"
EVENT_SCHEMA = "sifta.rover.event/1"
SUPPORTED_INTENT_SCHEMAS = (INTENT_SCHEMA,)
SUPPORTED_EVENT_SCHEMAS = (EVENT_SCHEMA,)
MAX_MESSAGE_BYTES = 65536

_REASON_BASE = (
    "UNSUPPORTED", "INVALID_ARGUMENT", "ID_CONFLICT", "WRONG_BODY", 
    "STALE_BOOT", "STALE_CAPABILITY", "EXPIRED", "BUSY", "LEASE_LOST", 
    "MAP_MISMATCH", "LOCALIZATION_LOST", "TARGET_UNKNOWN", "TARGET_STALE", 
    "SENSOR_STALE", "BLOCKED", "CONTROLLER_FAILED", "CANCELLED", "TIMEOUT", 
    "OUTCOME_UNKNOWN", "STOP_UNVERIFIED"
)
_SUCCESS_REASONS = ("ARRIVED", "COVERAGE_REACHED", "STOPPED_VERIFIED")
_PARTIAL_REASONS = ("BUDGET_EXHAUSTED",)
REASON_CODES = frozenset(_REASON_BASE + _SUCCESS_REASONS + _PARTIAL_REASONS + ("STOP_REQUESTED",))
VALIDATION_CODES = frozenset(REASON_CODES | {"UNKNOWN_FIELD", "SCHEMA_MISMATCH"})
# Deterministic enum tuples: frozenset iteration order varies per process (hash randomisation).
REASON_CODE_ENUM = tuple(sorted(REASON_CODES))

LIFECYCLE_STATES = ("received", "accepted", "running", "succeeded", "failed", "cancelled", "timed_out", "rejected", "unknown")
TERMINAL_STATES = ("succeeded", "failed", "cancelled", "timed_out", "rejected")
UNRESOLVED_STATE = "unknown"

LIFECYCLE_TRANSITIONS = {
    "received": ("accepted", "rejected", "cancelled", "unknown"),
    "accepted": ("running", "cancelled", "timed_out", "failed", "unknown"),
    "running": ("succeeded", "failed", "cancelled", "timed_out", "unknown"),
    "unknown": ("succeeded", "failed", "cancelled", "timed_out", "rejected", "accepted", "running"),
}

LEGACY_RVR1_MODULE = "System.stigmerobotics_rvr1"
LEGACY_RVR1_SOURCE_SHA256 = "04b1eb448723d5f561839493e55052f0317d1d79931351f307be3789df30026b"
LEGACY_RVR1_API = ("HEADER", "STATUS", "integer", "Packet", "encode", "decode", "sequence_is_newer", "velocity_payload", "Observations", "RoverClient")

class ContractError(ValueError):
    """Raised when a wire payload violates the SIFTA contract."""
    def __init__(self, code: str, path: str, message: str):
        super().__init__(f"[{code}] at {path}: {message}")
        self.code = code
        self.path = path
        self.message = message

# --- Spec Helpers ---
def _decorate(spec, nullable=False, required=True):
    if nullable:
        spec["nullable"] = True
    if not required:
        spec["required"] = False
    return spec

def _id(**kw): return _decorate({"t": "str", "nonempty": True}, **kw)
def _uuid(**kw): return _decorate({"t": "str", "pattern": "uuid"}, **kw)
def _sha(**kw): return _decorate({"t": "str", "pattern": "sha256"}, **kw)
def _utc(**kw): return _decorate({"t": "str", "pattern": "utc_iso"}, **kw)
def _n(min=None, max=None, exclusive_min=False, exclusive_max=False, **kw):
    return _decorate({"t": "num", "min": min, "max": max, "exclusive_min": exclusive_min,
                      "exclusive_max": exclusive_max}, **kw)
def _i(min=None, max=None, exclusive_min=False, exclusive_max=False, **kw):
    return _decorate({"t": "int", "min": min, "max": max, "exclusive_min": exclusive_min,
                      "exclusive_max": exclusive_max}, **kw)
def _b(**kw): return _decorate({"t": "bool"}, **kw)
def _obj(keys=None, allow_extra=False, extra_spec=None, **kw):
    return _decorate({"t": "obj", "keys": keys or {}, "allow_extra": allow_extra,
                      "extra_spec": extra_spec}, **kw)
def _arr(item, minitems=0, maxitems=None, **kw):
    return _decorate({"t": "arr", "item": item, "minitems": minitems, "maxitems": maxitems}, **kw)
def _opt(spec, required=True): return _decorate(dict(spec), nullable=True, required=required)
def _map_any(**kw): return _obj(allow_extra=True, extra_spec={"t": "any"}, **kw)
def _map_str(**kw): return _obj(allow_extra=True, extra_spec={"t": "str"}, **kw)

# --- Validation Engine ---
def _reject_nonfinite(value, path):
    if isinstance(value, bool): return
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ContractError("INVALID_ARGUMENT", path, f"Non-finite number {value} forbidden")
    elif isinstance(value, dict):
        for k, v in value.items(): _reject_nonfinite(v, f"{path}.{k}")
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value): _reject_nonfinite(v, f"{path}[{i}]")

def _check(value, spec, path):
    t = spec.get("t")
    if t == "any":
        return

    if value is None:
        if spec.get("nullable"): return
        raise ContractError("INVALID_ARGUMENT", path, "Null is not allowed here; unknown must be explicit")

    # Type check
    if t == "num":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ContractError("INVALID_ARGUMENT", path, f"Expected number, got {type(value).__name__}")
    elif t == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ContractError("INVALID_ARGUMENT", path, f"Expected integer, got {type(value).__name__}")
    elif t == "str":
        if not isinstance(value, str):
            raise ContractError("INVALID_ARGUMENT", path, f"Expected string, got {type(value).__name__}")
    elif t == "bool":
        if not isinstance(value, bool):
            raise ContractError("INVALID_ARGUMENT", path, f"Expected boolean, got {type(value).__name__}")
    elif t == "obj":
        if not isinstance(value, dict):
            raise ContractError("INVALID_ARGUMENT", path, f"Expected object, got {type(value).__name__}")
    elif t == "arr":
        if not isinstance(value, (list, tuple)):
            raise ContractError("INVALID_ARGUMENT", path, f"Expected array, got {type(value).__name__}")
    
    # Constraint check
    if t == "str":
        if spec.get("nonempty") and not value:
            raise ContractError("INVALID_ARGUMENT", path, "String must be non-empty")
        if "maxlen" in spec and len(value) > spec["maxlen"]:
            raise ContractError("INVALID_ARGUMENT", path, f"String exceeds max length {spec['maxlen']}")
        if "enum" in spec and value not in spec["enum"]:
            raise ContractError("INVALID_ARGUMENT", path, f"Value {value} not in enum {spec['enum']}")
        if "const" in spec and value != spec["const"]:
            code = spec.get("const_code", "INVALID_ARGUMENT")
            raise ContractError(code, path, f"Expected constant {spec['const']}, got {value}")
        if "pattern" in spec:
            p = spec["pattern"]
            if p == "uuid":
                try: uuid.UUID(value); 
                except: raise ContractError("INVALID_ARGUMENT", path, f"Invalid UUID: {value}")
            elif p == "sha256":
                if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
                    raise ContractError("INVALID_ARGUMENT", path, f"Invalid SHA256: {value}")
            elif p == "utc_iso":
                try: _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
                except: raise ContractError("INVALID_ARGUMENT", path, f"Invalid UTC ISO date: {value}")

    elif t in ("num", "int"):
        if spec.get("min") is not None:
            m = spec["min"]
            if spec.get("exclusive_min") and value <= m:
                raise ContractError("INVALID_ARGUMENT", path, f"Value {value} must be > {m}")
            if not spec.get("exclusive_min") and value < m:
                raise ContractError("INVALID_ARGUMENT", path, f"Value {value} must be >= {m}")
        if spec.get("max") is not None:
            m = spec["max"]
            if spec.get("exclusive_max") and value >= m:
                raise ContractError("INVALID_ARGUMENT", path, f"Value {value} must be < {m}")
            if not spec.get("exclusive_max") and value > m:
                raise ContractError("INVALID_ARGUMENT", path, f"Value {value} must be <= {m}")

    elif t == "obj":
        keys = spec.get("keys", {})
        for k, ks in keys.items():
            if k in value:
                _check(value[k], ks, f"{path}.{k}")
            elif ks.get("required", True) and not ks.get("default"):
                raise ContractError("INVALID_ARGUMENT", f"{path}.{k}", "Required field missing")
        
        extras = [k for k in value if k not in keys]
        if extras:
            if not spec.get("allow_extra"):
                raise ContractError("UNKNOWN_FIELD", path, f"Unknown field(s): {sorted(extras)}")
            else:
                extra_spec = spec.get("extra_spec") or {"t": "any"}
                for k in extras: _check(value[k], extra_spec, f"{path}.{k}")

    elif t == "arr":
        item_spec = spec.get("item")
        if spec.get("minitems") and len(value) < spec["minitems"]:
            raise ContractError("INVALID_ARGUMENT", path, f"Array too short: min {spec['minitems']}")
        if spec.get("maxitems") is not None and len(value) > spec["maxitems"]:
            raise ContractError("INVALID_ARGUMENT", path, f"Array too long: max {spec['maxitems']}")
        if item_spec:
            for i, v in enumerate(value): _check(v, item_spec, f"{path}[{i}]")

# --- Sub-Specs ---
POSE = _obj({
    "map_id": _id(), "map_revision": _sha(), "frame_id": _id(),
    "x_m": _n(), "y_m": _n(), "yaw_rad": _n(),
    "covariance": _arr(_n(), minitems=9, maxitems=9)
})
TWIST = _obj({"linear_m_s": _n(), "angular_rad_s": _n()})
COST_ITEM = _obj({"resource": _id(), "amount": _n(min=0), "unit": _id(), "measured": _b()})
RESOURCE_ESTIMATE = _obj({"resource": _id(), "value": _n(), "unit": _id(), "uncertainty": _n(nullable=True), "evidence_ref": _id(nullable=True)})
RESOURCE_STATE = _obj({"resource": _id(), "value": _n(nullable=True), "unit": _id(nullable=True), "source_age_ms": _i(min=0, nullable=True), "reason": _id(nullable=True)})
ACTION_DESCRIPTOR = _obj({"name": _id(), "input_schema": _map_any(), "output_schema": _map_any(), "preconditions": _arr(_id()), "adapter_id": _id()})
SENSOR_COVERAGE = _obj({"sensor_id": _id(), "modality": _id(), "coverage": _id(nullable=True), "freshness_ms": _i(min=0, nullable=True), "source_id": _id()})
UNAVAILABLE_CAP = _obj({"name": _id(), "reason_code": {"t":"str", "enum": REASON_CODE_ENUM}, "detail": _id(nullable=True)})
SENSOR_HEALTH = _obj({"health": {"t":"str", "enum": ("ok", "degraded", "failed", "unknown")}, "coverage": _n(min=0, max=1, nullable=True), "age_ms": _i(min=0, nullable=True), "source_id": _id()})
FAULT_ENTRY = _obj({"code": _id(), "capability": _id(nullable=True), "evidence_refs": _arr(_id(), minitems=1), "recovery_status": {"t":"str", "enum": ("none", "pending", "recovered", "unrecoverable")}})
ENTITY = _obj({"entity_id": _id(), "kind": _id(), "pose": _opt(POSE), "region": _obj({"map_id": _id(), "map_revision": _sha(), "polygon": _arr(_arr(_n(), minitems=2, maxitems=2), minitems=3)}, nullable=True), "attributes": _map_any()})
RELATION = _obj({"relation": _id(), "subject_id": _id(), "object_id": _id()})
HYPOTHESIS = _obj({"hypothesis_id": _id(), "statement": _id(), "confidence": _n(min=0, max=1), "supporting_observation_ids": _arr(_id())})
CONFLICT = _obj({"observation_ids": _arr(_id(), minitems=2), "detail": _id()})
BUDGET = _obj({"resource": _id(), "amount": _n(min=0), "unit": _id()})
REVISION_ENTRY = _obj({"revision": _i(min=0), "at_utc": _utc(), "change": _id()})
VERIFIER_RESULT = _obj({"verified": _b(), "verifier": _id(), "method": _id(), "detail": _id(nullable=True), "observation_ids": _arr(_id())})
ERROR_OBJ = _obj({"reason_code": {"t":"str", "enum": REASON_CODE_ENUM}, "detail": _id()})
PREDICTED_OUTCOME = _obj({"postcondition": _id(), "uncertainty": _n(min=0, max=1), "cost": _arr(COST_ITEM)})
COMMAND_RESULT = _obj({"postcondition_verified": _b(), "verifier": _id(), "observation_ids": _arr(_id(), minitems=1), "duration_s": _n(min=0, nullable=True), "distance_m": _n(min=0, nullable=True), "actual_cost": _arr(COST_ITEM, nullable=True), "diagnostics": _arr(_id())})
PROVENANCE = _obj({"source": _id(), "owner_authorized": _b(), "task_id": _id(nullable=True)})

# --- Records Specs ---
RECORD_SPECS = {
    "capability_snapshot": _obj({
        "schema_version": {"t":"str", "const": RECORDS_SCHEMA_VERSION},
        "snapshot_id": _uuid(), "body_id": _id(), "node_id": _id(), "boot_id": _uuid(),
        "topology_revision": _id(), "captured_at_utc": _utc(), "hardware": _map_any(),
        "os_facts": _map_str(), "available_actions": _arr(ACTION_DESCRIPTOR),
        "sensor_coverage": _arr(SENSOR_COVERAGE), "resource_estimates": _arr(RESOURCE_ESTIMATE),
        "observation_evidence_refs": _arr(_id()), "unavailable_capabilities": _arr(UNAVAILABLE_CAP)
    }),
    "observation": _obj({
        "schema_version": {"t":"str", "const": RECORDS_SCHEMA_VERSION},
        "observation_id": _uuid(), "event_id": _uuid(), "source_id": _id(), "boot_id": _uuid(),
        "seq": _i(min=0), "source_time": _obj({"value": _n(), "domain": _id()}),
        "local_receive_time_utc": _utc(), "local_receive_monotonic_s": _n(),
        "modality": _id(), "frame_id": _id(nullable=True), "values": _map_any(),
        "uncertainty": _map_any(nullable=True), "status": {"t":"str", "enum": ("live", "remembered", "inferred", "simulated")},
        "evidence_ref": _id()
    }),
    "belief_state": _obj({
        "schema_version": {"t":"str", "const": RECORDS_SCHEMA_VERSION},
        "belief_id": _uuid(), "revision": _i(min=0), "body_id": _id(), "created_at_utc": _utc(),
        "entities": _arr(ENTITY), "relations": _arr(RELATION), "pose": _opt(POSE),
        "map_ref": _obj({"map_id": _id(), "map_revision": _sha()}, nullable=True),
        "hypotheses": _arr(HYPOTHESIS), "supporting_observation_ids": _arr(_id()),
        "expired_evidence_ids": _arr(_id()), "conflicting_evidence": _arr(CONFLICT),
        "resource_state": _arr(RESOURCE_STATE)
    }),
    "goal": _obj({
        "schema_version": {"t":"str", "const": RECORDS_SCHEMA_VERSION},
        "goal_id": _uuid(), "owner_provenance": PROVENANCE, "task_family": _id(),
        "desired_observable": _id(), "predicate": _id(), "deadline_utc": _utc(nullable=True),
        "budget": _opt(BUDGET), "dependency_ids": _arr(_id()), "active_subgoal": _uuid(nullable=True),
        "progress_condition": _id(), "failure_condition": _id(), "checkpoint_ref": _id(nullable=True),
        "revision_history": _arr(REVISION_ENTRY, minitems=1), "created_at_utc": _utc()
    }),
    "action_proposal": _obj({
        "schema_version": {"t":"str", "const": RECORDS_SCHEMA_VERSION},
        "action_id": _uuid(), "goal_id": _uuid(), "adapter_id": _id(), "capability_revision": _sha(),
        "action_kind": _id(), "args": _map_any(), "required_observation_ids": _arr(_id()),
        "predicted_postcondition": _id(), "predicted_uncertainty": _n(min=0, max=1),
        "predicted_cost": _arr(COST_ITEM), "cancellation_behavior": _id(),
        "recovery_behavior": _id(), "created_at_utc": _utc()
    }),
    "action_result": _obj({
        "schema_version": {"t":"str", "const": RECORDS_SCHEMA_VERSION},
        "action_id": _uuid(), "status": {"t":"str", "enum": ("accepted", "running", "succeeded", "failed", "cancelled", "unknown")},
        "actual_observation_ids": _arr(_id()), "verifier_result": _opt(VERIFIER_RESULT),
        "cost": _arr(COST_ITEM, nullable=True), "error": _opt(ERROR_OBJ),
        "effect_receipt_id": _id(nullable=True), "updated_at_utc": _utc()
    }),
    "experience": _obj({
        "schema_version": {"t":"str", "const": RECORDS_SCHEMA_VERSION},
        "transition_id": _uuid(), "environment_id": _id(), "body_id": _id(), "task_family": _id(),
        "before_state_ref": _id(), "action_ref": _id(), "predicted_outcome": PREDICTED_OUTCOME,
        "observed_after_state_ref": _id(), "verification": VERIFIER_RESULT, "prediction_error": _n(min=0, nullable=True),
        "actual_cost": _arr(COST_ITEM), "provenance": PROVENANCE, "model_versions": _map_str(),
        "skill_versions": _map_str(), "created_at_utc": _utc()
    }),
}

# --- Intent & Event Specs ---
INTENT_ARGS_SPECS = {
    "navigate_to_pose": _obj({
        "map_id": _id(), "map_revision": _sha(), "frame_id": {"t":"str", "const":"map"},
        "x_m": _n(), "y_m": _n(), "yaw_rad": _n(),
        "position_tolerance_m": _n(min=0, exclusive_min=True),
        "yaw_tolerance_rad": _n(min=0, exclusive_min=True)
    }),
    "navigate_to_object": _obj({
        "object_id": _id(), "observation_id": _id(), "max_observation_age_ms": _i(min=0),
        "standoff_m": _n(min=0, exclusive_min=True), "position_tolerance_m": _n(min=0, exclusive_min=True)
    }),
    "explore": _obj({
        "map_id": _id(), "map_revision": _sha(), "frame_id": {"t":"str", "const":"map"},
        "boundary_xy_m": _arr(_arr(_n(), minitems=2, maxitems=2), minitems=3),
        "max_distance_m": _n(min=0, exclusive_min=True), "coverage_target": _n(min=0, max=1, exclusive_min=True)
    }),
    "stop": _obj({"reason": {"t":"str", "nonempty": True, "maxlen": 256}})
}

ENVELOPE_INTENT = _obj({
    "schema": {"t":"str", "const": INTENT_SCHEMA, "const_code": "UNSUPPORTED"},
    "command_id": _uuid(), "goal_id": _uuid(), "body_id": _id(), "expected_boot_id": _uuid(),
    "control_epoch": _i(min=0), "capability_revision": _sha(), "issued_at_utc": _utc(),
    "admission_ttl_ms": _i(min=0, exclusive_min=True), "execution_timeout_ms": _i(min=0, exclusive_min=True),
    "kind": {"t":"str", "enum": tuple(INTENT_ARGS_SPECS.keys())},
    "args": _obj(allow_extra=True), "extensions": _obj(allow_extra=True, nullable=True, required=False)
})

EVENT_PAYLOAD_SPECS = {
    "telemetry": _obj({
        "pose": _opt(POSE), "twist": _opt(TWIST), "battery_fraction": _n(min=0, max=1, nullable=True),
        "localization_status": _id(nullable=True), "active_command_id": _uuid(nullable=True),
        "sensors": _obj(allow_extra=True, extra_spec=SENSOR_HEALTH, nullable=True),
        "estop_active": _b(nullable=True), "control_lease_remaining_ms": _i(min=0, nullable=True),
        "faults": _arr(FAULT_ENTRY, nullable=True)
    }),
    "command_state": _obj({
        "state": {"t":"str", "enum": LIFECYCLE_STATES}, "reason_code": {"t":"str", "enum": REASON_CODE_ENUM, "nullable": True},
        "progress": _n(min=0, max=1, nullable=True), "result": _opt(COMMAND_RESULT),
        "effect_receipt_id": _id(nullable=True)
    }),
    "capabilities": _obj({
        "body_profile": _obj({"body_id": _id(), "boot_id": _uuid(), "topology_revision": _id(), "footprint": _obj({"length_m": _n(exclusive_min=0), "width_m": _n(exclusive_min=0)}, nullable=True)}),
        "ros_distribution": _id(), "package_versions": _map_str(), "firmware": _obj({"hash": _sha(), "version": _id()}),
        "schema_versions": _obj({"records": _id(), "intent": _id(), "event": _id()}),
        "map_identity": _obj({"map_id": _id(), "map_revision": _sha()}, nullable=True),
        "available_actions": _arr(ACTION_DESCRIPTOR)
    }),
    "fault": _obj({
        "code": _id(), "capability": _id(nullable=True), "evidence_refs": _arr(_id(), minitems=1),
        "recovery_status": {"t":"str", "enum": ("none", "pending", "recovered", "unrecoverable")}
    })
}

ENVELOPE_EVENT = _obj({
    "schema": {"t":"str", "const": EVENT_SCHEMA, "const_code": "UNSUPPORTED"},
    "event_id": _uuid(), "body_id": _id(), "boot_id": _uuid(), "control_epoch": _i(min=0), "seq": _i(min=0),
    "command_id": _uuid(nullable=True, required=False), "kind": {"t":"str", "enum": tuple(EVENT_PAYLOAD_SPECS.keys())},
    "source_time": _obj({"value": _n(), "domain": _id()}), "source_age_ms": _i(min=0),
    "payload": _obj(allow_extra=True), "evidence_refs": _arr(_id()),
    "received_at_utc": _utc(nullable=True, required=False), "received_monotonic_s": _n(min=0, nullable=True, required=False),
    "receiver_boot_id": _uuid(nullable=True, required=False)
})

# --- Wire Base & Records ---
class _Wire:
    WIRE: ClassVar[tuple] = ()
    _payload: ClassVar[Any] = None

    def __post_init__(self):
        if type(self)._payload is None or getattr(self, "_payload", None) is None:
            payload = {f.name: getattr(self, f.name) for f in dc_fields(self) if not f.name.startswith("_")}
            object.__setattr__(self, "_payload", payload)
        self.verify()

    def verify(self):
        _validate_wire(self.WIRE, self._payload)

    @classmethod
    def from_dict(cls, raw):
        _validate_wire(cls.WIRE, raw)
        names = [f.name for f in dc_fields(cls) if not f.name.startswith("_")]
        init_args = {k: v for k, v in raw.items() if k in names}
        obj = cls(**init_args)
        # Rebuild from the declared fields, not from the raw payload: a field the wire
        # omitted must still appear as an explicit null. Unknown is null, never absent.
        payload = {n: getattr(obj, n) for n in names}
        object.__setattr__(obj, "_payload", payload)
        obj.verify()
        return obj

    def to_dict(self): return copy.deepcopy(self._payload)
    def to_json(self) -> str: return json.dumps(self._payload, sort_keys=True, separators=(",", ":"))

@dataclass(frozen=True)
class CapabilitySnapshot(_Wire):
    WIRE = ("record", "capability_snapshot")
    snapshot_id: str = ""
    body_id: str = ""
    node_id: str = ""
    boot_id: str = ""
    topology_revision: str = ""
    captured_at_utc: str = ""
    hardware: dict = field(default_factory=dict)
    os_facts: dict = field(default_factory=dict)
    available_actions: list = field(default_factory=list)
    sensor_coverage: list = field(default_factory=list)
    resource_estimates: list = field(default_factory=list)
    observation_evidence_refs: list = field(default_factory=list)
    unavailable_capabilities: list = field(default_factory=list)
    schema_version: str = RECORDS_SCHEMA_VERSION

@dataclass(frozen=True)
class Observation(_Wire):
    WIRE = ("record", "observation")
    observation_id: str = ""
    event_id: str = ""
    source_id: str = ""
    boot_id: str = ""
    seq: int = 0
    source_time: dict = field(default_factory=dict)
    local_receive_time_utc: str = ""
    local_receive_monotonic_s: float = 0.0
    modality: str = ""
    frame_id: Optional[str] = None
    values: dict = field(default_factory=dict)
    uncertainty: Optional[dict] = None
    status: str = ""
    evidence_ref: str = ""
    schema_version: str = RECORDS_SCHEMA_VERSION

@dataclass(frozen=True)
class BeliefState(_Wire):
    WIRE = ("record", "belief_state")
    belief_id: str = ""
    revision: int = 0
    body_id: str = ""
    created_at_utc: str = ""
    entities: list = field(default_factory=list)
    relations: list = field(default_factory=list)
    pose: Optional[dict] = None
    map_ref: Optional[dict] = None
    hypotheses: list = field(default_factory=list)
    supporting_observation_ids: list = field(default_factory=list)
    expired_evidence_ids: list = field(default_factory=list)
    conflicting_evidence: list = field(default_factory=list)
    resource_state: list = field(default_factory=list)
    schema_version: str = RECORDS_SCHEMA_VERSION

@dataclass(frozen=True)
class Goal(_Wire):
    WIRE = ("record", "goal")
    goal_id: str = ""
    owner_provenance: dict = field(default_factory=dict)
    task_family: str = ""
    desired_observable: str = ""
    predicate: str = ""
    deadline_utc: Optional[str] = None
    budget: Optional[dict] = None
    dependency_ids: list = field(default_factory=list)
    active_subgoal: Optional[str] = None
    progress_condition: str = ""
    failure_condition: str = ""
    checkpoint_ref: Optional[str] = None
    revision_history: list = field(default_factory=list)
    created_at_utc: str = ""
    schema_version: str = RECORDS_SCHEMA_VERSION

@dataclass(frozen=True)
class ActionProposal(_Wire):
    WIRE = ("record", "action_proposal")
    action_id: str = ""
    goal_id: str = ""
    adapter_id: str = ""
    capability_revision: str = ""
    action_kind: str = ""
    args: dict = field(default_factory=dict)
    required_observation_ids: list = field(default_factory=list)
    predicted_postcondition: str = ""
    predicted_uncertainty: float = 0.0
    predicted_cost: list = field(default_factory=list)
    cancellation_behavior: str = ""
    recovery_behavior: str = ""
    created_at_utc: str = ""
    schema_version: str = RECORDS_SCHEMA_VERSION

@dataclass(frozen=True)
class ActionResult(_Wire):
    WIRE = ("record", "action_result")
    action_id: str = ""
    status: str = ""
    actual_observation_ids: list = field(default_factory=list)
    verifier_result: Optional[dict] = None
    cost: Optional[list] = None
    error: Optional[dict] = None
    effect_receipt_id: Optional[str] = None
    updated_at_utc: str = ""
    schema_version: str = RECORDS_SCHEMA_VERSION

@dataclass(frozen=True)
class Experience(_Wire):
    WIRE = ("record", "experience")
    transition_id: str = ""
    environment_id: str = ""
    body_id: str = ""
    task_family: str = ""
    before_state_ref: str = ""
    action_ref: str = ""
    predicted_outcome: dict = field(default_factory=dict)
    observed_after_state_ref: str = ""
    verification: dict = field(default_factory=dict)
    prediction_error: Optional[float] = None
    actual_cost: list = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    model_versions: dict = field(default_factory=dict)
    skill_versions: dict = field(default_factory=dict)
    created_at_utc: str = ""
    schema_version: str = RECORDS_SCHEMA_VERSION

@dataclass(frozen=True)
class RoverIntent(_Wire):
    WIRE = ("intent",)
    command_id: str = ""
    goal_id: str = ""
    body_id: str = ""
    expected_boot_id: str = ""
    control_epoch: int = 0
    capability_revision: str = ""
    issued_at_utc: str = ""
    admission_ttl_ms: int = 3000
    execution_timeout_ms: int = 60000
    kind: str = ""
    args: dict = field(default_factory=dict)
    schema: str = INTENT_SCHEMA
    extensions: Optional[dict] = None

@dataclass(frozen=True)
class RoverEvent(_Wire):
    WIRE = ("event",)
    event_id: str = ""
    body_id: str = ""
    boot_id: str = ""
    control_epoch: int = 0
    seq: int = 0
    kind: str = ""
    source_time: dict = field(default_factory=dict)
    source_age_ms: int = 0
    payload: dict = field(default_factory=dict)
    evidence_refs: list = field(default_factory=list)
    command_id: Optional[str] = None
    received_at_utc: Optional[str] = None
    received_monotonic_s: Optional[float] = None
    receiver_boot_id: Optional[str] = None
    schema: str = EVENT_SCHEMA

# --- Core Logic ---
def _validate_wire(wire, raw):
    if not isinstance(raw, dict):
        raise ContractError("INVALID_ARGUMENT", str(wire), "Payload must be a JSON object")
    
    _reject_nonfinite(raw, str(wire))
    
    # Wire size check
    try:
        size = len(json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))
        if size > MAX_MESSAGE_BYTES:
            raise ContractError("INVALID_ARGUMENT", str(wire), f"Payload size {size} exceeds max {MAX_MESSAGE_BYTES}")
    except ValueError as e:
        raise ContractError("INVALID_ARGUMENT", str(wire), f"Serialization failed: {e}")

    if isinstance(wire, tuple) and wire[0] == "record":
        name = wire[1]
        spec = RECORD_SPECS[name]
        _check(raw, spec, name)
        _record_cross_checks(name, raw)
    elif wire == ("intent",):
        _check(raw, ENVELOPE_INTENT, "intent")
        kind = raw["kind"]
        args_spec = INTENT_ARGS_SPECS[kind]
        _check(raw["args"], args_spec, f"intent.args[{kind}]")
    elif wire == ("event",):
        _check(raw, ENVELOPE_EVENT, "event")
        kind = raw["kind"]
        payload_spec = EVENT_PAYLOAD_SPECS[kind]
        _check(raw["payload"], payload_spec, f"event.payload[{kind}]")
        _event_cross_checks(raw)
    
    return copy.deepcopy(raw)

def _record_cross_checks(name, payload):
    if name == "action_result":
        status = payload["status"]
        if status == "succeeded":
            res = payload.get("verifier_result")
            if not res or not res.get("verified") or not payload.get("actual_observation_ids"):
                raise ContractError("INVALID_ARGUMENT", "action_result", "succeeded status requires verified result and observations")
        elif status == "unknown":
            if payload.get("verifier_result") is not None:
                raise ContractError("INVALID_ARGUMENT", "action_result", "unknown status must not carry a verifier result")
    elif name == "goal":
        gid = payload["goal_id"]
        if gid in payload.get("dependency_ids", []):
            raise ContractError("INVALID_ARGUMENT", "goal", "Goal cannot depend on itself")
    elif name == "belief_state":
        for i, rs in enumerate(payload.get("resource_state", [])):
            if rs.get("value") is None and not rs.get("reason"):
                raise ContractError("INVALID_ARGUMENT", f"belief_state.resource_state[{i}]", "Unknown resource value must have a reason")

def _event_cross_checks(raw):
    payload = raw["payload"]
    kind = raw["kind"]
    if kind == "command_state":
        state = payload["state"]
        if state == "succeeded":
            res = payload.get("result")
            if not res or not res.get("postcondition_verified") or not res.get("observation_ids"):
                raise ContractError("INVALID_ARGUMENT", "event.payload", "succeeded command_state requires verified result")
        elif state == "unknown":
            if payload.get("reason_code") != "OUTCOME_UNKNOWN":
                raise ContractError("INVALID_ARGUMENT", "event.payload", "unknown state requires OUTCOME_UNKNOWN reason")

def check_admission(intent: RoverIntent, *, body_id: str, boot_id: str, control_epoch: int, capability_revision: str, lease_remaining_ms: Optional[int], consumed_ms: int = 0):
    if intent.body_id != body_id:
        raise ContractError("WRONG_BODY", "admission", f"Intent for {intent.body_id}, but body is {body_id}")
    if intent.expected_boot_id != boot_id:
        raise ContractError("STALE_BOOT", "admission", f"Intent expected boot {intent.expected_boot_id}, got {boot_id}")
    if intent.control_epoch != control_epoch:
        raise ContractError("STALE_BOOT", "admission", "Control epoch mismatch")
    
    if intent.kind != "stop":
        if intent.capability_revision != capability_revision:
            raise ContractError("STALE_CAPABILITY", "admission", "Capability revision mismatch")
            
    if lease_remaining_ms is None or lease_remaining_ms <= 0:
        raise ContractError("LEASE_LOST", "admission", "No active control lease")
        
    if consumed_ms >= intent.admission_ttl_ms:
        raise ContractError("EXPIRED", "admission", "Admission TTL exceeded")
        
    return {"admitted": True, "remaining_ttl_ms": intent.admission_ttl_ms - consumed_ms}

def dedupe_decision(stored_payload_hash: str, incoming: RoverIntent):
    incoming_hash = intent_payload_hash(incoming)
    if stored_payload_hash == incoming_hash:
        return "duplicate"
    raise ContractError("ID_CONFLICT", "dedupe", "Same command ID but different payload")

def intent_payload_hash(intent: Union[RoverIntent, dict]):
    # Canonicalize through the frozen envelope so that an omitted optional field and
    # an explicit null hash identically: absent and null are the same wire fact, and a
    # resend that merely spells out its nulls must not look like an ID_CONFLICT.
    obj = intent if isinstance(intent, RoverIntent) else RoverIntent.from_dict(intent)
    canonical = json.dumps(obj.to_dict(), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

def stamp_received(event: Union[RoverEvent, dict], *, at_utc: str, monotonic_s: float, receiver_boot_id: str):
    raw = event.to_dict() if isinstance(event, RoverEvent) else copy.deepcopy(event)
    raw["received_at_utc"] = at_utc
    raw["received_monotonic_s"] = monotonic_s
    raw["receiver_boot_id"] = receiver_boot_id
    return _validate_wire(("event",), raw)

# --- Adapter Interface ---
ADAPTER_METHODS = ("probe", "observe", "submit", "status", "cancel", "recover")
PHYSICAL_ADAPTER_METHODS = ADAPTER_METHODS + ("stop",)

class AdapterInterface:
    """Base interface for all rover adapters. Implementations must be non-blocking."""
    def probe(self) -> dict: raise NotImplementedError
    def observe(self, cursor: str) -> dict: raise NotImplementedError
    def submit(self, action: dict) -> str: raise NotImplementedError
    def status(self, action_id: str) -> dict: raise NotImplementedError
    def cancel(self, action_id: str) -> bool: raise NotImplementedError
    def recover(self, checkpoint: str) -> bool: raise NotImplementedError

class PhysicalAdapter(AdapterInterface):
    """Adapters with direct hardware control must implement stop()."""
    def stop(self): raise NotImplementedError

def adapter_report(obj, physical=False):
    methods = PHYSICAL_ADAPTER_METHODS if physical else ADAPTER_METHODS
    present = [m for m in methods if hasattr(obj, m) and callable(getattr(obj, m))]
    return {"present": present, "missing": [m for m in methods if m not in present]}

def assert_adapter(obj, physical=False):
    rep = adapter_report(obj, physical)
    if rep["missing"]:
        raise ContractError("UNSUPPORTED", "adapter", f"Missing required methods: {rep['missing']}")

# --- Publication & Fixtures ---
def published_schemas():
    return {
        "records_schema_version": RECORDS_SCHEMA_VERSION,
        "intent_schema": INTENT_SCHEMA,
        "event_schema": EVENT_SCHEMA,
        "records": RECORD_SPECS,
        "intent_envelope": ENVELOPE_INTENT,
        "intent_args": INTENT_ARGS_SPECS,
        "event_payload": EVENT_PAYLOAD_SPECS,
        "lifecycle_states": list(LIFECYCLE_STATES),
        "terminal_states": list(TERMINAL_STATES),
        "lifecycle_transitions": {k: list(v) for k, v in LIFECYCLE_TRANSITIONS.items()},
        "reason_codes": sorted(list(REASON_CODES)),
        "success_reasons": sorted(list(_SUCCESS_REASONS)),
        "max_message_bytes": MAX_MESSAGE_BYTES
    }

def schema_hash():
    canonical = json.dumps(published_schemas(), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

SCHEMA_HASH = schema_hash()

def _fx(label): return str(uuid.uuid5(uuid.NAMESPACE_URL, f"sifta.alice.contracts.v1.{label}"))

def emit_fixtures(directory):
    import os
    os.makedirs(directory, exist_ok=True)
    
    def _build_intent(kind, args):
        return {
            "schema": INTENT_SCHEMA, "command_id": _fx("cmd"), "goal_id": _fx("goal"),
            "body_id": "body_0", "expected_boot_id": _fx("boot"), "control_epoch": 0,
            "capability_revision": "sha256:"+("a"*64), "issued_at_utc": "2025-01-01T00:00:00Z",
            "admission_ttl_ms": 3000, "execution_timeout_ms": 60000, "kind": kind, "args": args
        }

    def _build_event(kind, payload):
        return {
            "event_id": _fx("evt"), "body_id": "body_0", "boot_id": _fx("boot"),
            "control_epoch": 0, "seq": 0, "kind": kind, "source_time": {"value": 0.0, "domain": "utc"},
            "source_age_ms": 0, "payload": payload, "evidence_refs": [_fx("evid")],
            "command_id": _fx("cmd"), "schema": EVENT_SCHEMA
        }

    payloads = {
        "intent_navigate_to_pose": _build_intent("navigate_to_pose", {"map_id":"m1","map_revision":"sha256:"+("a"*64),"frame_id":"map","x_m":1.0,"y_m":1.0,"yaw_rad":0.0,"position_tolerance_m":0.1,"yaw_tolerance_rad":0.1}),
        "intent_navigate_to_object": _build_intent("navigate_to_object", {"object_id":"o1","observation_id":"obs1","max_observation_age_ms":1000,"standoff_m":0.5,"position_tolerance_m":0.1}),
        "intent_explore": _build_intent("explore", {"map_id":"m1","map_revision":"sha256:"+("a"*64),"frame_id":"map","boundary_xy_m":[[0,0],[1,0],[1,1],[0,1]],"max_distance_m":10.0,"coverage_target":0.8}),
        "intent_stop": _build_intent("stop", {"reason": "User requested stop"}),
        "event_telemetry": _build_event("telemetry", {"pose": None, "twist": None, "battery_fraction": 0.8, "localization_status": "ok", "active_command_id": None, "sensors": {}, "estop_active": False, "control_lease_remaining_ms": 1000, "faults": []}),
        "event_command_state": _build_event("command_state", {"state": "succeeded", "reason_code": "ARRIVED", "progress": 1.0, "result": {"postcondition_verified": True, "verifier": "lidar", "observation_ids": [_fx("obs")], "duration_s": 10.0, "distance_m": 5.0, "actual_cost": [], "diagnostics": []}, "effect_receipt_id": "rec1"}),
        "event_capabilities": _build_event("capabilities", {"body_profile": {"body_id":"b1","boot_id":_fx("boot"),"topology_revision":"v1","footprint":None}, "ros_distribution": "humble", "package_versions": {}, "firmware": {"hash":"sha256:"+("a"*64),"version":"1.0"}, "schema_versions": {"records":RECORDS_SCHEMA_VERSION,"intent":INTENT_SCHEMA,"event":EVENT_SCHEMA}, "map_identity": None, "available_actions": []}),
        "event_fault": _build_event("fault", {"code": "MOTOR_OVERHEAT", "capability": "drive", "evidence_refs": [_fx("evid")], "recovery_status": "pending"}),
        "capability_snapshot": {"schema_version":RECORDS_SCHEMA_VERSION, "snapshot_id":_fx("s"), "body_id":"b1","node_id":"n1","boot_id":_fx("b"),"topology_revision":"v1","captured_at_utc":"2025-01-01T00:00:00Z","hardware":{},"os_facts":{},"available_actions":[],"sensor_coverage":[],"resource_estimates":[],"observation_evidence_refs":[],"unavailable_capabilities":[]},
        "observation": {"schema_version":RECORDS_SCHEMA_VERSION, "observation_id":_fx("o"), "event_id":_fx("e"),"source_id":"s1","boot_id":_fx("b"),"seq":0,"source_time":{"value":0.0,"domain":"utc"},"local_receive_time_utc":"2025-01-01T00:00:00Z","local_receive_monotonic_s":0.0,"modality":"lidar","frame_id":"map","values":{},"uncertainty":None,"status":"live","evidence_ref":_fx("evid")},
        "belief_state": {"schema_version":RECORDS_SCHEMA_VERSION, "belief_id":_fx("b"), "revision":0,"body_id":"b1","created_at_utc":"2025-01-01T00:00:00Z","entities":[],"relations":[],"pose":None,"map_ref":None,"hypotheses":[],"supporting_observation_ids":[],"expired_evidence_ids":[],"conflicting_evidence":[],"resource_state":[]},
        "goal": {"schema_version":RECORDS_SCHEMA_VERSION, "goal_id":_fx("g"), "owner_provenance":{"source":"george","owner_authorized":True,"task_id":None},"task_family":"nav","desired_observable":"at_pose","predicate":"is_near","deadline_utc":None,"budget":None,"dependency_ids":[],"active_subgoal":None,"progress_condition":"dist < 0.1","failure_condition":"timeout","checkpoint_ref":None,"revision_history": [{"revision":0,"at_utc":"2025-01-01T00:00:00Z","change":"init"}],"created_at_utc":"2025-01-01T00:00:00Z"},
        "action_proposal": {"schema_version":RECORDS_SCHEMA_VERSION, "action_id":_fx("a"), "goal_id":_fx("g"),"adapter_id":"nav2","capability_revision":"sha256:"+("a"*64),"action_kind":"navigate_to_pose","args":{"map_id":"m1","map_revision":"sha256:"+("a"*64),"frame_id":"map","x_m":1.0,"y_m":1.0,"yaw_rad":0.0,"position_tolerance_m":0.1,"yaw_tolerance_rad":0.1},"required_observation_ids":[],"predicted_postcondition":"at_pose","predicted_uncertainty":0.1,"predicted_cost":[],"cancellation_behavior":"stop","recovery_behavior":"replan","created_at_utc":"2025-01-01T00:00:00Z"},
        "action_result": {"schema_version":RECORDS_SCHEMA_VERSION, "action_id":_fx("a"), "status":"succeeded","actual_observation_ids":[_fx("o")],"verifier_result":{"verified":True,"verifier":"lidar","method":"dist","detail":None,"observation_ids":[_fx("o")]},"cost":[],"error":None,"effect_receipt_id":"rec1","updated_at_utc":"2025-01-01T00:00:00Z"},
        "experience": {"schema_version":RECORDS_SCHEMA_VERSION, "transition_id":_fx("t"), "environment_id":"env1","body_id":"b1","task_family":"nav","before_state_ref":"b1","action_ref":"a1","predicted_outcome":{"postcondition":"at_pose","uncertainty":0.1,"cost":[]},"observed_after_state_ref":"a1","verification":{"verified":True,"verifier":"lidar","method":"dist","detail":None,"observation_ids":[_fx("o")]},"prediction_error":0.0,"actual_cost":[],"provenance":{"source":"alice","owner_authorized":True,"task_id":"t1"},"model_versions":{},"skill_versions":{},"created_at_utc":"2025-01-01T00:00:00Z"},
    }

    files = {}
    for name, payload in payloads.items():
        path = f"{name}.v1.json"
        with open(os.path.join(directory, path), "w") as f:
            json.dump(payload, f, sort_keys=True)
        files[name] = path
    
    manifest = {
        "schema_hash": SCHEMA_HASH,
        "generated_by": "System.swarm_adaptive_contracts",
        "records_schema_version": RECORDS_SCHEMA_VERSION,
        "files": files
    }
    with open(os.path.join(directory, "manifest.json"), "w") as f:
        json.dump(manifest, f, sort_keys=True)
    return manifest

def legacy_rvr1_api_report(module_path=None):
    try:
        import System.stigmerobotics_rvr1 as rvr1
        import inspect
        import hashlib
        
        src_path = inspect.getsourcefile(rvr1)
        with open(src_path, "rb") as f:
            actual_sha = "sha256:" + hashlib.sha256(f.read()).hexdigest()
            
        present_api = [n for n in dir(rvr1) if n in LEGACY_RVR1_API]
        missing_api = [n for n in LEGACY_RVR1_API if n not in present_api]
        
        return {
            "module": LEGACY_RVR1_MODULE,
            "source_sha256": actual_sha,
            "frozen_sha256": LEGACY_RVR1_SOURCE_SHA256,
            "source_sha256_matches_frozen": actual_sha.removeprefix("sha256:") == LEGACY_RVR1_SOURCE_SHA256,
            "present_api": present_api,
            "missing_api": missing_api
        }
    except Exception as e:
        return {"error": str(e)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-hash", action="store_true")
    parser.add_argument("--emit-fixtures", type=str, help="Directory to emit fixtures")
    parser.add_argument("--selfcheck", type=str, help="Directory to check fixtures")
    parser.add_argument("--legacy-report", action="store_true")
    args = parser.parse_args()
    
    if args.schema_hash:
        print(SCHEMA_HASH)
    elif args.emit_fixtures:
        manifest = emit_fixtures(args.emit_fixtures)
        print(json.dumps(manifest, indent=2))
    elif args.selfcheck:
        import os
        manifest_path = os.path.join(args.selfcheck, "manifest.json")
        if not os.path.exists(manifest_path):
            print("Manifest missing")
            sys.exit(1)
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        if manifest["schema_hash"] != SCHEMA_HASH:
            print(f"Hash mismatch: {manifest['schema_hash']} vs {SCHEMA_HASH}")
            sys.exit(1)
        for name, path in manifest["files"].items():
            with open(os.path.join(args.selfcheck, path), "r") as f:
                raw = json.load(f)
            try:
                if "intent_" in name: _validate_wire(("intent",), raw)
                elif "event_" in name: _validate_wire(("event",), raw)
                else: _validate_wire(("record", name), raw)
            except ContractError as e:
                print(f"Fixture {name} failed: {e}")
                sys.exit(1)
        print("All fixtures valid.")
    elif args.legacy_report:
        print(json.dumps(legacy_rvr1_api_report(), indent=2))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
