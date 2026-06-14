"""CUR-V6 — predator multi-eye lock-on (§7.1). George 2026-06-13:
'switch between eyes when connected, scan for changes like a predator'."""
from __future__ import annotations

from System import swarm_predator_eye_scan as pes


def _eye(eid, name, role="world_eye", state="LIVE", age=1.0):
    return {
        "eye_id": eid,
        "device_name": name,
        "role": role,
        "connection_state": state,
        "last_frame_age_s": age,
    }


def _snap(eyes):
    return {"eyes": eyes}


def test_single_eye_stays():
    out = pes.scan_and_lock(_snap([_eye("owner-1", "MacBook Pro Camera", "owner_eye")]))
    assert out["action"] == "STAY_SINGLE_EYE"
    assert out["locked_eye_id"] == "owner-1"


def test_locks_onto_changed_eye():
    snap = _snap([
        _eye("owner-1", "MacBook Pro Camera", "owner_eye"),
        _eye("world-1", "USB Camera VID:1133 PID:2081", "world_eye"),
    ])
    out = pes.scan_and_lock(snap, change_by_eye={"owner-1": 0.1, "world-1": 0.9}, current_eye_id="owner-1")
    assert out["action"] == "LOCK_ON"
    assert out["locked_eye_id"] == "world-1"


def test_iphone_excluded_from_scan():
    # iPhone shows the most change but must be excluded (CUR-V4 tie-in);
    # only one eligible eye remains -> stay, never lock the phone.
    snap = _snap([
        _eye("owner-1", "MacBook Pro Camera", "owner_eye"),
        _eye("iphone-1", "Ioan's iPhone Camera", "aux"),
    ])
    out = pes.scan_and_lock(snap, change_by_eye={"owner-1": 0.1, "iphone-1": 0.99}, current_eye_id="owner-1")
    assert "iphone-1" not in (out.get("candidates") or [])
    assert out["locked_eye_id"] == "owner-1"


def test_iphone_scanned_only_when_allowed():
    snap = _snap([
        _eye("owner-1", "MacBook Pro Camera", "owner_eye"),
        _eye("iphone-1", "Ioan's iPhone Camera", "aux"),
    ])
    out = pes.scan_and_lock(
        snap, change_by_eye={"owner-1": 0.1, "iphone-1": 0.99},
        current_eye_id="owner-1", allow_iphone=True,
    )
    assert out["locked_eye_id"] == "iphone-1"


def test_hysteresis_holds_lock_on_small_delta():
    snap = _snap([
        _eye("owner-1", "MacBook Pro Camera", "owner_eye"),
        _eye("world-1", "USB Camera", "world_eye"),
    ])
    out = pes.scan_and_lock(
        snap, change_by_eye={"owner-1": 0.50, "world-1": 0.55},
        current_eye_id="owner-1", switch_margin=0.15,
    )
    assert out["action"] == "HOLD_LOCK"
    assert out["locked_eye_id"] == "owner-1"


def test_stale_eye_not_eligible():
    snap = _snap([
        _eye("owner-1", "MacBook Pro Camera", "owner_eye"),
        _eye("world-1", "USB Camera", "world_eye", state="STALE_OR_DETACHED"),
    ])
    out = pes.scan_and_lock(snap, change_by_eye={"owner-1": 0.2, "world-1": 0.99}, current_eye_id="owner-1")
    assert out["action"] == "STAY_SINGLE_EYE"
    assert out["locked_eye_id"] == "owner-1"
