"""C0 tests — SIFTA adaptive contracts (frozen typed records + rover intent/event v1).

Covers the five contract laws and the admission/dedupe/receipt logic that the
rover bridge and the adaptive cortex both depend on.
"""
from __future__ import annotations

import copy
import json
import os

import pytest

from System import swarm_adaptive_contracts as C


def _uuid(label: str) -> str:
    import uuid as _u
    return str(_u.uuid5(_u.NAMESPACE_URL, f"c0.test.{label}"))


SHA_A = "sha256:" + ("a" * 64)
SHA_B = "sha256:" + ("b" * 64)


def _intent(kind="stop", args=None, **over):
    base = {
        "schema": C.INTENT_SCHEMA,
        "command_id": _uuid("cmd"),
        "goal_id": _uuid("goal"),
        "body_id": "rvr1",
        "expected_boot_id": _uuid("boot"),
        "control_epoch": 3,
        "capability_revision": SHA_A,
        "issued_at_utc": "2025-01-01T00:00:00Z",
        "admission_ttl_ms": 3000,
        "execution_timeout_ms": 60000,
        "kind": kind,
        "args": args if args is not None else {"reason": "owner asked to stop"},
    }
    base.update(over)
    return base


def _pose_args(**over):
    a = {
        "map_id": "map_lab", "map_revision": SHA_A, "frame_id": "map",
        "x_m": 1.0, "y_m": 2.0, "yaw_rad": 0.0,
        "position_tolerance_m": 0.15, "yaw_tolerance_rad": 0.2,
    }
    a.update(over)
    return a


def _event(kind="telemetry", payload=None, **over):
    base = {
        "schema": C.EVENT_SCHEMA,
        "event_id": _uuid("evt"),
        "body_id": "rvr1",
        "boot_id": _uuid("boot"),
        "control_epoch": 3,
        "seq": 1,
        "kind": kind,
        "source_time": {"value": 10.0, "domain": "utc"},
        "source_age_ms": 12,
        "payload": payload if payload is not None else {
            "pose": None, "twist": None, "battery_fraction": 0.75,
            "localization_status": "ok", "active_command_id": None,
            "sensors": {}, "estop_active": False,
            "control_lease_remaining_ms": 900, "faults": [],
        },
        "evidence_refs": [_uuid("evid")],
    }
    base.update(over)
    return base


# --- Law: frozen, version-locked schema ---

def test_schema_hash_is_stable_across_processes():
    """Hash must not depend on dict/set iteration order (PYTHONHASHSEED)."""
    import subprocess, sys
    outs = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        r = subprocess.run(
            [sys.executable, "-m", "System.swarm_adaptive_contracts", "--schema-hash"],
            capture_output=True, text=True, check=True, env=env,
        )
        outs.add(r.stdout.strip())
    assert len(outs) == 1, outs
    assert C.SCHEMA_HASH == outs.pop()


def test_published_schemas_declares_every_frozen_record():
    pub = C.published_schemas()
    assert set(pub["records"]) == set(C.RECORD_SPECS) == {
        "capability_snapshot", "observation", "belief_state", "goal",
        "action_proposal", "action_result", "experience",
    }
    assert pub["records_schema_version"] == C.RECORDS_SCHEMA_VERSION
    assert pub["intent_schema"] == "sifta.rover.intent/1"
    assert pub["event_schema"] == "sifta.rover.event/1"
    assert pub["terminal_states"] == list(C.TERMINAL_STATES)
    assert pub["max_message_bytes"] == C.MAX_MESSAGE_BYTES


def test_reason_codes_cover_lifecycle_semantics():
    assert "OUTCOME_UNKNOWN" in C.REASON_CODES
    assert "ARRIVED" in C.REASON_CODES
    assert "STOP_REQUESTED" in C.REASON_CODES
    assert set(C.LIFECYCLE_STATES) >= set(C.TERMINAL_STATES) | {"unknown"}


def test_terminal_states_have_no_outgoing_lifecycle_edges():
    for state in C.TERMINAL_STATES:
        assert state not in C.LIFECYCLE_TRANSITIONS


# --- Law: fixtures round-trip ---

def test_emitted_fixtures_all_validate(tmp_path):
    manifest = C.emit_fixtures(str(tmp_path))
    assert manifest["schema_hash"] == C.SCHEMA_HASH
    assert os.path.exists(tmp_path / "manifest.json")
    for name, fname in manifest["files"].items():
        raw = json.loads((tmp_path / fname).read_text())
        if name.startswith("intent_"):
            wire = ("intent",)
        elif name.startswith("event_"):
            wire = ("event",)
        else:
            wire = ("record", name)
        C._validate_wire(wire, raw)


def test_fixture_emit_is_deterministic(tmp_path):
    a = C.emit_fixtures(str(tmp_path / "a"))
    b = C.emit_fixtures(str(tmp_path / "b"))
    assert a["files"] == b["files"]
    for fname in a["files"].values():
        assert (tmp_path / "a" / fname).read_text() == (tmp_path / "b" / fname).read_text()


# --- Law: unknown is null, never absent ---

def test_missing_required_field_is_rejected_not_defaulted():
    raw = _intent()
    del raw["body_id"]
    with pytest.raises(C.ContractError) as e:
        C._validate_wire(("intent",), raw)
    assert e.value.code == "INVALID_ARGUMENT"
    assert "body_id" in e.value.path


def test_explicit_null_is_accepted_where_nullable():
    raw = _event(kind="command_state", payload={
        "state": "running", "reason_code": None, "progress": 0.4,
        "result": None, "effect_receipt_id": None,
    })
    C._validate_wire(("event",), raw)


def test_unknown_command_state_requires_outcome_unknown_reason():
    good = _event(kind="command_state", payload={
        "state": "unknown", "reason_code": "OUTCOME_UNKNOWN", "progress": None,
        "result": None, "effect_receipt_id": None,
    })
    C._validate_wire(("event",), good)

    bad = copy.deepcopy(good)
    bad["payload"]["reason_code"] = "TIMEOUT"
    with pytest.raises(C.ContractError) as e:
        C._validate_wire(("event",), bad)
    assert "OUTCOME_UNKNOWN" in e.value.message


def test_unknown_resource_reading_must_carry_a_reason():
    belief = {
        "schema_version": C.RECORDS_SCHEMA_VERSION, "belief_id": _uuid("bel"),
        "revision": 0, "body_id": "rvr1", "created_at_utc": "2025-01-01T00:00:00Z",
        "entities": [], "relations": [], "pose": None, "map_ref": None,
        "hypotheses": [], "supporting_observation_ids": [], "expired_evidence_ids": [],
        "conflicting_evidence": [],
        "resource_state": [{"resource": "battery", "value": None, "unit": None,
                            "source_age_ms": None, "reason": None}],
    }
    with pytest.raises(C.ContractError) as e:
        C._validate_wire(("record", "belief_state"), belief)
    assert "resource_state" in e.value.path

    belief["resource_state"][0]["reason"] = "SENSOR_STALE"
    C._validate_wire(("record", "belief_state"), belief)


# --- Law: no non-finite numbers on the wire ---

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_refused(bad):
    raw = _intent("navigate_to_pose", _pose_args(x_m=bad))
    with pytest.raises(C.ContractError) as e:
        C._validate_wire(("intent",), raw)
    assert "Non-finite" in e.value.message


def test_non_finite_is_refused_when_nested():
    raw = _event(kind="telemetry", payload={
        "pose": {"map_id": "m", "map_revision": SHA_A, "frame_id": "map",
                 "x_m": float("inf"), "y_m": 0.0, "yaw_rad": 0.0,
                 "covariance": [0.0] * 9},
        "twist": None, "battery_fraction": 1.0, "localization_status": "ok",
        "active_command_id": None, "sensors": {}, "estop_active": False,
        "control_lease_remaining_ms": 10, "faults": [],
    })
    with pytest.raises(C.ContractError):
        C._validate_wire(("event",), raw)


# --- Law: strict fields and schema versioning ---

def test_unknown_fields_are_refused_inside_intent():
    raw = _intent()
    raw["surprise"] = 1
    with pytest.raises(C.ContractError) as e:
        C._validate_wire(("intent",), raw)
    assert e.value.code == "UNKNOWN_FIELD"


def test_wrong_schema_version_reports_unsupported():
    raw = _intent()
    raw["schema"] = "sifta.rover.intent/2"
    with pytest.raises(C.ContractError) as e:
        C._validate_wire(("intent",), raw)
    assert e.value.code == "UNSUPPORTED"


def test_unknown_intent_kind_is_refused():
    raw = _intent("backflip", {"reason": "nope"})
    with pytest.raises(C.ContractError):
        C._validate_wire(("intent",), raw)


def test_tolerance_must_be_strictly_positive():
    raw = _intent("navigate_to_pose", _pose_args(position_tolerance_m=0.0))
    with pytest.raises(C.ContractError) as e:
        C._validate_wire(("intent",), raw)
    assert e.value.path.endswith("position_tolerance_m")


def test_oversized_payload_is_refused():
    raw = _intent("stop", {"reason": "x" * (C.MAX_MESSAGE_BYTES + 10)})
    with pytest.raises(C.ContractError) as e:
        C._validate_wire(("intent",), raw)
    assert "exceeds max" in e.value.message


# --- Law: acceptance is not success; success needs verified postconditions ---

def test_succeeded_action_result_requires_verification():
    result = {
        "schema_version": C.RECORDS_SCHEMA_VERSION, "action_id": _uuid("act"),
        "status": "succeeded", "actual_observation_ids": [_uuid("obs")],
        "verifier_result": None, "cost": [], "error": None,
        "effect_receipt_id": None, "updated_at_utc": "2025-01-01T00:00:00Z",
    }
    with pytest.raises(C.ContractError) as e:
        C._validate_wire(("record", "action_result"), result)
    assert "verified" in e.value.message

    result["verifier_result"] = {
        "verified": True, "verifier": "nav2_goal_checker", "method": "pose_within_tolerance",
        "detail": None, "observation_ids": [_uuid("obs")],
    }
    C._validate_wire(("record", "action_result"), result)


def test_unverified_verifier_result_does_not_count_as_success():
    result = {
        "schema_version": C.RECORDS_SCHEMA_VERSION, "action_id": _uuid("act"),
        "status": "succeeded", "actual_observation_ids": [_uuid("obs")],
        "verifier_result": {"verified": False, "verifier": "v", "method": "m",
                            "detail": "still 0.4 m short", "observation_ids": [_uuid("obs")]},
        "cost": [], "error": None, "effect_receipt_id": None,
        "updated_at_utc": "2025-01-01T00:00:00Z",
    }
    with pytest.raises(C.ContractError):
        C._validate_wire(("record", "action_result"), result)


def test_unknown_action_result_must_not_carry_a_verifier_result():
    result = {
        "schema_version": C.RECORDS_SCHEMA_VERSION, "action_id": _uuid("act"),
        "status": "unknown", "actual_observation_ids": [],
        "verifier_result": {"verified": True, "verifier": "v", "method": "m",
                            "detail": None, "observation_ids": [_uuid("obs")]},
        "cost": None,
        "error": {"reason_code": "OUTCOME_UNKNOWN", "detail": "link dropped mid-motion"},
        "effect_receipt_id": None, "updated_at_utc": "2025-01-01T00:00:00Z",
    }
    with pytest.raises(C.ContractError) as e:
        C._validate_wire(("record", "action_result"), result)
    assert "unknown" in e.value.message


def test_command_state_succeeded_requires_verified_result():
    bad = _event(kind="command_state", payload={
        "state": "succeeded", "reason_code": "ARRIVED", "progress": 1.0,
        "result": {"postcondition_verified": False, "verifier": "v",
                   "observation_ids": [_uuid("obs")], "duration_s": 1.0,
                   "distance_m": 1.0, "actual_cost": [], "diagnostics": []},
        "effect_receipt_id": "receipt_1",
    })
    with pytest.raises(C.ContractError) as e:
        C._validate_wire(("event",), bad)
    assert "verified" in e.value.message

    good = copy.deepcopy(bad)
    good["payload"]["result"]["postcondition_verified"] = True
    C._validate_wire(("event",), good)


def test_command_result_requires_at_least_one_observation():
    bad = _event(kind="command_state", payload={
        "state": "succeeded", "reason_code": "ARRIVED", "progress": 1.0,
        "result": {"postcondition_verified": True, "verifier": "v", "observation_ids": [],
                   "duration_s": 1.0, "distance_m": 1.0, "actual_cost": [], "diagnostics": []},
        "effect_receipt_id": None,
    })
    with pytest.raises(C.ContractError):
        C._validate_wire(("event",), bad)


# --- Admission control ---

def _admit(intent, **over):
    kw = dict(body_id="rvr1", boot_id=intent["expected_boot_id"], control_epoch=3,
              capability_revision=SHA_A, lease_remaining_ms=900, consumed_ms=0)
    kw.update(over)
    return C.check_admission(C.RoverIntent.from_dict(intent), **kw)


def test_admission_accepts_a_fresh_matching_intent():
    out = _admit(_intent())
    assert out["admitted"] is True
    assert out["remaining_ttl_ms"] == 3000


def test_admission_refuses_wrong_body():
    with pytest.raises(C.ContractError) as e:
        _admit(_intent(), body_id="husky")
    assert e.value.code == "WRONG_BODY"


def test_admission_refuses_stale_boot():
    with pytest.raises(C.ContractError) as e:
        _admit(_intent(), boot_id=_uuid("other_boot"))
    assert e.value.code == "STALE_BOOT"


def test_admission_refuses_stale_capability_revision():
    with pytest.raises(C.ContractError) as e:
        _admit(_intent("navigate_to_pose", _pose_args()), capability_revision=SHA_B)
    assert e.value.code == "STALE_CAPABILITY"


def test_stop_is_admitted_even_when_capability_revision_is_stale():
    out = _admit(_intent("stop"), capability_revision=SHA_B)
    assert out["admitted"] is True


def test_admission_refuses_without_a_control_lease():
    with pytest.raises(C.ContractError) as e:
        _admit(_intent(), lease_remaining_ms=0)
    assert e.value.code == "LEASE_LOST"
    with pytest.raises(C.ContractError) as e:
        _admit(_intent(), lease_remaining_ms=None)
    assert e.value.code == "LEASE_LOST"


def test_admission_refuses_expired_ttl():
    with pytest.raises(C.ContractError) as e:
        _admit(_intent(), consumed_ms=3000)
    assert e.value.code == "EXPIRED"
    assert _admit(_intent(), consumed_ms=2999)["remaining_ttl_ms"] == 1


# --- Dedupe and receipts ---

def test_identical_resend_is_a_duplicate_not_an_error():
    raw = _intent()
    h = C.intent_payload_hash(raw)
    assert C.dedupe_decision(h, C.RoverIntent.from_dict(raw)) == "duplicate"


def test_same_command_id_with_different_payload_is_id_conflict():
    first = _intent()
    second = copy.deepcopy(first)
    second["args"] = {"reason": "different words, same command id"}
    with pytest.raises(C.ContractError) as e:
        C.dedupe_decision(C.intent_payload_hash(first), C.RoverIntent.from_dict(second))
    assert e.value.code == "ID_CONFLICT"


def test_intent_hash_is_canonical_and_key_order_independent():
    raw = _intent()
    shuffled = {k: raw[k] for k in reversed(list(raw))}
    assert C.intent_payload_hash(raw) == C.intent_payload_hash(shuffled)
    assert C.intent_payload_hash(raw).startswith("sha256:")


def test_stamp_received_adds_receiver_side_evidence():
    stamped = C.stamp_received(_event(), at_utc="2025-01-01T00:00:05Z",
                              monotonic_s=42.5, receiver_boot_id=_uuid("recv_boot"))
    assert stamped["received_at_utc"] == "2025-01-01T00:00:05Z"
    assert stamped["received_monotonic_s"] == 42.5
    assert stamped["receiver_boot_id"] == _uuid("recv_boot")
    # the adapter's own clock is untouched
    assert stamped["source_time"] == {"value": 10.0, "domain": "utc"}
    C._validate_wire(("event",), stamped)


def test_stamp_received_refuses_bad_receiver_clock():
    with pytest.raises(C.ContractError):
        C.stamp_received(_event(), at_utc="not-a-time", monotonic_s=1.0,
                         receiver_boot_id=_uuid("recv_boot"))


# --- Wire objects ---

def test_rover_intent_round_trips_and_is_frozen():
    raw = _intent("navigate_to_pose", _pose_args())
    intent = C.RoverIntent.from_dict(raw)
    out = intent.to_dict()
    # every field the wire carried survives unchanged...
    for k, v in raw.items():
        assert out[k] == v
    # ...and an omitted optional field appears as explicit null, never absent
    assert out["extensions"] is None
    # the canonical form is a fixed point, and hashes to itself
    assert C.RoverIntent.from_dict(out).to_dict() == out
    assert C.intent_payload_hash(raw) == C.intent_payload_hash(out)
    assert json.loads(intent.to_json()) == out
    with pytest.raises(Exception):
        intent.body_id = "someone else"


def test_rover_event_defaults_absent_receiver_stamps_to_null():
    ev = C.RoverEvent.from_dict(_event())
    d = ev.to_dict()
    assert d["received_at_utc"] is None
    assert d["received_monotonic_s"] is None
    assert d["receiver_boot_id"] is None


def test_wire_objects_do_not_leak_shared_references():
    raw = _intent()
    intent = C.RoverIntent.from_dict(raw)
    out = intent.to_dict()
    out["args"]["reason"] = "mutated copy"
    assert intent.to_dict()["args"]["reason"] == "owner asked to stop"


def test_from_dict_rejects_before_constructing():
    raw = _intent()
    del raw["command_id"]
    with pytest.raises(C.ContractError):
        C.RoverIntent.from_dict(raw)


# --- Adapter interface ---

class _FullAdapter:
    def probe(self): return {}
    def observe(self, cursor): return {}
    def submit(self, action): return "id"
    def status(self, action_id): return {}
    def cancel(self, action_id): return True
    def recover(self, checkpoint): return True
    def stop(self): return True


class _CrippledAdapter(_FullAdapter):
    def __delattr__(self, name):  # pragma: no cover - safety net
        raise AssertionError("unexpected delete")


def test_full_physical_adapter_passes():
    assert C.assert_adapter(_FullAdapter(), physical=True) is None
    assert C.adapter_report(_FullAdapter())["missing"] == []


def test_missing_recover_is_reported_not_guessed():
    class Partial:
        def probe(self): return {}
        def observe(self, cursor): return {}
        def submit(self, action): return "id"
        def status(self, action_id): return {}
        def cancel(self, action_id): return True

    rep = C.adapter_report(Partial())
    assert rep["missing"] == ["recover"]
    with pytest.raises(C.ContractError) as e:
        C.assert_adapter(Partial())
    assert e.value.code == "UNSUPPORTED"


def test_physical_adapter_must_expose_stop():
    class Logical:
        def probe(self): return {}
        def observe(self, cursor): return {}
        def submit(self, action): return "id"
        def status(self, action_id): return {}
        def cancel(self, action_id): return True
        def recover(self, checkpoint): return True

    assert C.assert_adapter(Logical()) is None
    with pytest.raises(C.ContractError) as e:
        C.assert_adapter(Logical(), physical=True)
    assert "stop" in e.value.message
    assert C.PHYSICAL_ADAPTER_METHODS[-1] == "stop"


# --- Frozen legacy boundary ---

def test_legacy_rvr1_boundary_is_frozen_and_fully_exposed():
    rep = C.legacy_rvr1_api_report()
    assert "error" not in rep, rep
    assert rep["source_sha256_matches_frozen"] is True, rep
    assert rep["missing_api"] == []
    assert set(rep["present_api"]) == set(C.LEGACY_RVR1_API)


def test_legacy_rvr1_module_is_untouched_by_the_new_contract():
    """C0 must add a contract, never rewrite the working rover bridge."""
    rep = C.legacy_rvr1_api_report()
    assert rep["source_sha256"] == "sha256:" + C.LEGACY_RVR1_SOURCE_SHA256
