#!/usr/bin/env python3
"""D2 acceptance tests: the lived-experience bridge as a queryable belief snapshot.

Every test writes to a temporary state directory.  No test may touch live state.
The four acceptance laws are each pinned by at least one test:

  1. replayed / stale telemetry cannot freshen an observation
  2. contradictory observations remain visible
  3. a missing pose is null, never (0, 0)
  4. a moved object invalidates the old target
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from System.swarm_adaptive_contracts import BeliefState  # noqa: E402
from System.swarm_lived_experience_bridge import (  # noqa: E402
    BELIEF_LEDGER,
    BELIEF_TRUTH_LABEL,
    DEFAULT_EVIDENCE_TTL_S,
    DEFAULT_MOVED_THRESHOLD_M,
    POSE_VARIANCE_UNKNOWN,
    _row_expired,
    _row_ttl,
    belief_content_hash,
    belief_snapshot,
    entity_belief,
    observe_entity,
    target_is_stale,
)


def _observe(state: Path, entity_id: str = "mug_1", **kwargs):
    kwargs.setdefault("source", "camera_front")
    kwargs.setdefault("evidence_links", ["frame-0001"])
    return observe_entity(entity_id, state_dir=state, **kwargs)


def _pose(x: float, y: float, frame: str = "map") -> dict[str, float | str]:
    return {"x": x, "y": y, "frame": frame}


def test_observation_is_appended_to_its_own_ledger(tmp_path: Path) -> None:
    row = _observe(tmp_path, pose=_pose(1.0, 2.0), attributes={"colour": "red"})
    assert row["truth_label"] == BELIEF_TRUTH_LABEL
    assert row["freshens"] is True
    assert row["record_class"] == "FRESH"
    assert row["may_authorize_action"] is False
    assert (tmp_path / BELIEF_LEDGER).exists()
    written = json.loads((tmp_path / BELIEF_LEDGER).read_text(encoding="utf-8").strip())
    assert written["observation_id"] == row["observation_id"]
    assert written["receipt_hash"] == row["receipt_hash"]


def test_replaying_the_same_observation_cannot_freshen_the_belief(tmp_path: Path) -> None:
    first = _observe(tmp_path, observed_at=1000.0, pose=_pose(0.0, 0.0), now=1000.0)
    replay = _observe(tmp_path, observed_at=1000.0, pose=_pose(0.0, 0.0), now=2000.0)
    assert first["freshens"] is True
    assert replay["freshens"] is False
    assert replay["record_class"] == "DUPLICATE_REPLAY"
    assert "already recorded" in replay["replay_reason"]

    belief = entity_belief("mug_1", now=1500.0, state_dir=tmp_path)
    assert belief["supporting_observation_ids"] == [first["observation_id"]]
    assert belief["rejected_observation_ids"] == [replay["observation_id"]]
    assert belief["evidence_age_s"] == pytest.approx(500.0), "the replay did not refresh the age"
    assert belief["stale"] is False
    assert belief["last_seen"] == 1000.0
    assert belief["observation_count"] == 2


def test_older_telemetry_is_kept_as_history_but_never_freshens(tmp_path: Path) -> None:
    fresh = _observe(tmp_path, observed_at=5000.0, pose=_pose(4.0, 1.0), now=5000.0)
    stale = _observe(tmp_path, observed_at=4000.0, pose=_pose(0.5, 0.5), now=6000.0)
    assert stale["freshens"] is False
    assert stale["record_class"] == "STALE_REPLAY"
    assert stale["prior_observation_id"] == fresh["observation_id"]

    belief = entity_belief("mug_1", now=6000.0, state_dir=tmp_path)
    assert belief["pose"]["x"] == 4.0
    assert stale["observation_id"] not in belief["supporting_observation_ids"]
    assert stale["observation_id"] in belief["rejected_observation_ids"]
    assert belief["moved_count"] == 0, "a stale replay must not register as movement"
    assert belief["conflicts"] == [], "a stale replay must not create a contradiction"


def test_an_entity_with_only_replays_reports_itself_as_unknown(tmp_path: Path) -> None:
    _observe(tmp_path, observed_at=900.0, now=900.0)
    replay = _observe(tmp_path, observed_at=900.0, now=1000.0)
    state = tmp_path
    # wipe the single fresh row by rewriting the ledger with only the replay
    rows = [json.loads(line) for line in (state / BELIEF_LEDGER).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 2
    replay_only = [rows[1]]
    (state / BELIEF_LEDGER).write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in replay_only), encoding="utf-8"
    )
    belief = entity_belief("mug_1", now=1000.0, state_dir=state)
    assert belief["known"] is False
    assert belief["pose"] is None
    assert belief["uncertainty"] == 1.0
    assert belief["rejected_observation_ids"] == [replay["observation_id"]]


def test_missing_pose_stays_null_and_is_never_an_invented_origin(tmp_path: Path) -> None:
    row = _observe(tmp_path, attributes={"graspable": True})
    assert row["pose"] is None
    assert row["pose_known"] is False

    belief = entity_belief("mug_1", now=1000.0, state_dir=tmp_path)
    assert belief["known"] is True
    assert belief["pose"] is None
    assert belief["pose_known"] is False
    assert belief["pose"] != {"x": 0.0, "y": 0.0}

    snapshot = belief_snapshot(body_id="rover-1", now=1000.0, state_dir=tmp_path)
    assert snapshot["entities"][0]["pose"] is None
    assert snapshot["entities"][0]["attributes"]["belief.pose_known"] is False
    assert snapshot["pose"] is None, "an unobserved body pose must not become (0, 0)"


def test_a_half_specified_pose_is_rejected_rather_than_completed_with_zeros(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"pose\.y is missing"):
        _observe(tmp_path, pose={"x": 1.0, "frame": "map"})
    with pytest.raises(ValueError, match="pose requires a frame name"):
        _observe(tmp_path, pose={"x": 1.0, "y": 2.0})


def test_non_finite_geometry_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be finite"):
        _observe(tmp_path, pose={"x": float("inf"), "y": 0.0, "frame": "map"})
    with pytest.raises(ValueError, match="must be finite"):
        _observe(tmp_path, pose={"x": float("nan"), "y": 0.0, "frame": "map"})


def test_a_contradictory_attribute_stays_visible_on_both_sides(tmp_path: Path) -> None:
    first = _observe(tmp_path, observed_at=100.0, attributes={"colour": "red"}, now=100.0)
    second = _observe(tmp_path, observed_at=200.0, attributes={"colour": "blue"}, now=200.0)

    belief = entity_belief("mug_1", now=200.0, state_dir=tmp_path)
    assert belief["contested"] is True
    assert belief["attributes"]["colour"]["value"] == "blue", "the newest live value wins the view"
    conflicts = [item for item in belief["conflicts"] if item["field"] == "attribute:colour"]
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict["prior_value"] == "red"
    assert conflict["new_value"] == "blue"
    assert conflict["prior_observation_id"] == first["observation_id"]
    assert conflict["new_observation_id"] == second["observation_id"]
    assert conflict["resolution"] == "UNRESOLVED"
    assert belief["revision"] >= 1
    assert first["observation_id"] in belief["supporting_observation_ids"], "history is not deleted"
    assert belief["uncertainty_components"]["open_conflicts"] > 0.0


def test_a_contradiction_is_reported_in_the_snapshot(tmp_path: Path) -> None:
    _observe(tmp_path, observed_at=100.0, attributes={"state": "closed"}, now=100.0)
    _observe(tmp_path, observed_at=200.0, attributes={"state": "open"}, now=200.0)
    snapshot = belief_snapshot(body_id="rover-1", now=200.0, state_dir=tmp_path)
    details = [item["detail"] for item in snapshot["conflicting_evidence"]]
    assert any("attribute:state" in text for text in details), details
    assert any("unresolved" in text for text in details), "the conflict stays visibly unresolved"
    assert all(len(item["observation_ids"]) >= 2 for item in snapshot["conflicting_evidence"])
    assert snapshot["entities"][0]["attributes"]["belief.contested"] is True


def test_a_moved_object_invalidates_the_old_target(tmp_path: Path) -> None:
    first = _observe(tmp_path, observed_at=100.0, pose=_pose(0.0, 0.0), now=100.0)
    second = _observe(tmp_path, observed_at=200.0, pose=_pose(3.0, 0.0), now=200.0)

    belief = entity_belief("mug_1", now=200.0, state_dir=tmp_path)
    assert belief["moved_count"] == 1
    assert belief["revision"] >= 1
    assert first["observation_id"] in belief["superseded_observation_ids"]
    assert belief["pose"]["x"] == 3.0
    assert belief["pose"]["moved_from"]["distance_m"] == pytest.approx(3.0)
    assert belief["pose"]["moved_from"]["observation_id"] == first["observation_id"]
    pose_conflicts = [item for item in belief["conflicts"] if item["field"] == "pose"]
    assert len(pose_conflicts) == 1
    assert pose_conflicts[0]["resolution"] == "UNRESOLVED"

    stale = target_is_stale("mug_1", target_observation_id=first["observation_id"], now=200.0, state_dir=tmp_path)
    assert stale["target_stale"] is True
    assert stale["reason"] == "a later observation moved the entity"
    assert stale["current_observation_id"] == second["observation_id"]

    current = target_is_stale("mug_1", target_observation_id=second["observation_id"], now=200.0, state_dir=tmp_path)
    assert current["target_stale"] is False


def test_a_small_nudge_is_not_a_move(tmp_path: Path) -> None:
    _observe(tmp_path, observed_at=100.0, pose=_pose(0.0, 0.0), now=100.0)
    _observe(tmp_path, observed_at=200.0, pose=_pose(DEFAULT_MOVED_THRESHOLD_M / 4.0, 0.0), now=200.0)
    belief = entity_belief("mug_1", now=200.0, state_dir=tmp_path)
    assert belief["moved_count"] == 0
    assert belief["conflicts"] == []
    assert belief["superseded_observation_ids"] == []


def test_a_pose_frame_change_is_not_silently_compared(tmp_path: Path) -> None:
    _observe(tmp_path, observed_at=100.0, pose=_pose(0.0, 0.0, frame="map"), now=100.0)
    _observe(tmp_path, observed_at=200.0, pose=_pose(9.0, 9.0, frame="odom"), now=200.0)
    belief = entity_belief("mug_1", now=200.0, state_dir=tmp_path)
    assert belief["moved_count"] == 0, "distance across frames is not a comparable measurement"
    assert belief["pose"]["frame"] == "odom"
    assert belief["revision"] >= 1, "but gaining a pose in a new frame is still a revision"


def test_expired_evidence_is_reported_and_leaves_the_live_view(tmp_path: Path) -> None:
    old = _observe(tmp_path, observed_at=100.0, ttl_s=10.0, attributes={"seen": True}, now=100.0)
    belief = entity_belief("mug_1", now=1000.0, state_dir=tmp_path)
    assert belief["known"] is True
    assert belief["stale"] is True
    assert belief["evidence_age_s"] == pytest.approx(900.0)
    assert belief["expired_evidence_ids"] == [old["observation_id"]]
    assert belief["supporting_observation_ids"] == []

    snapshot = belief_snapshot(body_id="rover-1", now=1000.0, state_dir=tmp_path)
    assert snapshot["expired_evidence_ids"] == [old["observation_id"]]
    assert snapshot["supporting_observation_ids"] == []

    stale = target_is_stale("mug_1", target_observation_id=old["observation_id"], now=1000.0, state_dir=tmp_path)
    assert stale["target_stale"] is True


def test_belief_of_an_entity_nobody_observed_is_explicitly_unknown(tmp_path: Path) -> None:
    belief = entity_belief("never_seen", now=1000.0, state_dir=tmp_path)
    assert belief["known"] is False
    assert belief["pose"] is None
    assert belief["attributes"] == {}
    assert belief["supporting_observation_ids"] == []
    assert belief["uncertainty"] == 1.0


def test_a_relation_change_is_a_contradiction(tmp_path: Path) -> None:
    _observe(tmp_path, observed_at=100.0, relations=[{"predicate": "on", "object": "table_a"}], now=100.0)
    _observe(tmp_path, observed_at=200.0, relations=[{"predicate": "on", "object": "table_b"}], now=200.0)
    belief = entity_belief("mug_1", now=200.0, state_dir=tmp_path)
    fields = {item["field"] for item in belief["conflicts"]}
    assert "relations" in fields
    assert belief["relations"][-1]["object"] == "table_b"
    assert belief["relations"][-1]["observation_id"]


def test_unbacked_claims_are_downgraded_before_they_enter_the_belief(tmp_path: Path) -> None:
    row = observe_entity(
        "mug_1",
        source="owner_say",
        epistemic_status="DIRECT_OBSERVED",
        confidence=0.99,
        state_dir=tmp_path,
        now=100.0,
    )
    assert row["requested_epistemic_status"] == "DIRECT_OBSERVED"
    assert row["epistemic_status"] == "UNKNOWN"
    assert row["downgrade_reason"] == "required_evidence_missing"
    assert row["confidence"] <= 0.25
    assert row["may_authorize_action"] is False


def test_the_snapshot_validates_against_the_c0_belief_state_record(tmp_path: Path) -> None:
    _observe(tmp_path, entity_id="mug_1", observed_at=100.0, pose=_pose(1.0, 1.0), attributes={"colour": "red"}, now=100.0)
    _observe(tmp_path, entity_id="crate_9", observed_at=100.0, attributes={"colour": "blue"}, now=100.0)
    _observe(tmp_path, entity_id="crate_9", observed_at=200.0, attributes={"colour": "green"}, now=200.0)
    snapshot = belief_snapshot(
        body_id="rover-1",
        pose=_pose(0.5, 0.5),
        map_ref={"map_id": "lab", "map_revision": "sha256:" + "a" * 64},
        hypotheses=["crate_9 may be the same crate as crate_8"],
        resource_state=[{"name": "battery", "value": 0.8}],
        now=200.0,
        state_dir=tmp_path,
    )
    assert BeliefState.from_dict(snapshot).verify() is None
    assert snapshot["schema_version"] == "1.0.0"
    assert snapshot["body_id"] == "rover-1"
    assert snapshot["pose"]["frame_id"] == "map"
    assert snapshot["pose"]["x_m"] == 0.5
    assert len(snapshot["pose"]["covariance"]) == 9
    assert len(snapshot["entities"]) == 2
    assert snapshot["revision"] >= 1
    assert snapshot["belief_id"]
    assert len(snapshot["map_ref"]["map_revision"]) == 71
    assert {entity["entity_id"] for entity in snapshot["entities"]} == {"mug_1", "crate_9"}
    assert snapshot["resource_state"][0]["resource"] == "battery"
    assert snapshot["resource_state"][0]["value"] == 0.8
    assert snapshot["resource_state"][0]["source_age_ms"] is None
    assert snapshot["hypotheses"][0]["confidence"] == 0.5
    assert snapshot["hypotheses"][0]["hypothesis_id"]
    assert belief_content_hash(snapshot) == belief_content_hash(snapshot)


def test_a_pose_without_a_map_identity_is_refused_rather_than_invented(tmp_path: Path) -> None:
    _observe(tmp_path, pose=_pose(1.0, 1.0), now=100.0)
    with pytest.raises(ValueError, match="no map_ref was supplied"):
        belief_snapshot(body_id="rover-1", now=100.0, state_dir=tmp_path)
    with pytest.raises(ValueError, match="map_revision must be a sha256"):
        belief_snapshot(
            body_id="rover-1",
            map_ref={"map_id": "lab", "map_revision": "3"},
            now=100.0,
            state_dir=tmp_path,
        )


def test_the_snapshot_is_deterministic_for_identical_evidence(tmp_path: Path) -> None:
    other = tmp_path / "other"
    for state in (tmp_path, other):
        _observe(state, entity_id="mug_1", observation_id="obs-mug-a", observed_at=100.0, pose=_pose(1.0, 1.0), now=100.0)
        _observe(state, entity_id="mug_1", observation_id="obs-mug-b", observed_at=200.0, pose=_pose(1.1, 1.0), now=200.0)
        _observe(state, entity_id="crate_9", observation_id="obs-crate", observed_at=150.0, attributes={"a": 1}, now=150.0)
    map_ref = {"map_id": "lab", "map_revision": "sha256:" + "b" * 64}
    left = belief_snapshot(body_id="rover-1", map_ref=map_ref, now=300.0, state_dir=tmp_path)
    right = belief_snapshot(body_id="rover-1", map_ref=map_ref, now=300.0, state_dir=other)
    assert left["entities"] == right["entities"]
    assert left["relations"] == right["relations"]
    assert left["conflicting_evidence"] == right["conflicting_evidence"]
    assert left["revision"] == right["revision"]
    assert belief_content_hash(left) == belief_content_hash(right), "same evidence, same content"
    assert left["belief_id"] != right["belief_id"], "identity of a snapshot is not its content"


def test_observation_and_snapshot_never_grant_effector_authority(tmp_path: Path) -> None:
    row = _observe(tmp_path, now=100.0)
    belief = entity_belief("mug_1", now=100.0, state_dir=tmp_path)
    snapshot = belief_snapshot(body_id="rover-1", now=100.0, state_dir=tmp_path)
    for payload in (row, belief):
        assert payload["action_policy"] == "context_only_no_effector_authority"
        assert payload["effectors_allowed"] == []
    assert snapshot["pose"] is None, "the contract record carries no body pose here"
    assert "action_policy" not in snapshot, "the frozen C0 record has no effector surface at all"
    for entity in snapshot["entities"]:
        assert "effectors_allowed" not in entity


def test_invalid_entity_identifiers_and_kinds_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="entity_id must be non-empty"):
        observe_entity("", source="camera_front", state_dir=tmp_path)
    with pytest.raises(ValueError, match="source must be non-empty"):
        observe_entity("mug_1", source="", state_dir=tmp_path)
    with pytest.raises(ValueError, match="unknown entity kind"):
        _observe(tmp_path, kind="ghost")
    with pytest.raises(ValueError, match="body_id must be non-empty"):
        belief_snapshot(body_id="", state_dir=tmp_path)


# --- R2: an observation's lifetime belongs to that observation -------------------


def test_a_newer_observation_cannot_revive_expired_neighbour_evidence(tmp_path: Path) -> None:
    """A long lifetime on the newest row must not extend an older row's lifetime."""
    short = _observe(
        tmp_path, observed_at=100.0, ttl_s=1.0, attributes={"colour": "red"}, now=100.0
    )
    _observe(tmp_path, observed_at=102.0, ttl_s=1000.0, now=102.0)
    belief = entity_belief("mug_1", now=103.0, state_dir=tmp_path)

    assert belief["expired_evidence_ids"] == [short["observation_id"]]
    assert short["observation_id"] not in belief["supporting_observation_ids"]
    assert belief["attributes"] == {}, "expired evidence must not carry into the live view"


def test_each_observation_expires_on_its_own_clock(tmp_path: Path) -> None:
    """Mixed lifetimes in one ledger: three rows, three independent verdicts."""
    quick = _observe(tmp_path, observed_at=100.0, ttl_s=1.0, now=100.0)
    slow = _observe(tmp_path, observed_at=101.0, ttl_s=50.0, now=101.0)
    durable = _observe(tmp_path, observed_at=102.0, ttl_s=5000.0, now=102.0)

    belief = entity_belief("mug_1", now=110.0, state_dir=tmp_path)

    assert belief["expired_evidence_ids"] == [quick["observation_id"]]
    assert belief["supporting_observation_ids"] == [slow["observation_id"], durable["observation_id"]]
    assert belief["stale"] is False, "the belief rests on live evidence"


def test_a_zero_lifetime_is_no_reusable_freshness_not_the_default(tmp_path: Path) -> None:
    """ttl_s=0.0 must never be rewritten into DEFAULT_EVIDENCE_TTL_S."""
    assert _row_ttl({"evidence_ttl_s": 0.0}) == 0.0
    assert _row_ttl({"evidence_ttl_s": 0}) == 0.0
    assert _row_ttl({"evidence_ttl_s": None}) == DEFAULT_EVIDENCE_TTL_S
    assert _row_ttl({}) == DEFAULT_EVIDENCE_TTL_S

    instant = _observe(tmp_path, observed_at=100.0, ttl_s=0.0, now=100.0)
    belief = entity_belief("mug_1", now=100.5, state_dir=tmp_path)

    assert _row_expired({"observed_at": 100.0, "evidence_ttl_s": 0.0}, 100.5) is True
    assert belief["expired_evidence_ids"] == [instant["observation_id"]]
    assert belief["supporting_observation_ids"] == []
    assert belief["evidence_ttl_s"] == 0.0, "the declared lifetime is reported, not the default"
    assert belief["stale"] is True
    assert belief["uncertainty"] == 1.0, "no reusable freshness means no confidence"


def test_receipt_time_cannot_renew_an_old_source_timestamp(tmp_path: Path) -> None:
    """Late delivery of old telemetry stays old: age follows the source clock."""
    row = _observe(tmp_path, observed_at=100.0, ttl_s=5.0, now=900.0)
    assert row["observed_at"] == pytest.approx(100.0)
    assert row["recorded_at"] == pytest.approx(900.0)

    late = entity_belief("mug_1", now=901.0, state_dir=tmp_path)

    assert late["evidence_age_s"] == pytest.approx(801.0)
    assert late["expired_evidence_ids"] == [row["observation_id"]]
    assert late["stale"] is True


def test_the_newest_arrival_still_expires_on_its_own_clock(tmp_path: Path) -> None:
    """Arrival order must not decide expiry: the last row written can expire first."""
    durable = _observe(tmp_path, observed_at=100.0, ttl_s=1000.0, now=100.0)
    brief = _observe(tmp_path, observed_at=105.0, ttl_s=1.0, now=105.0)

    belief = entity_belief("mug_1", now=110.0, state_dir=tmp_path)

    assert belief["expired_evidence_ids"] == [brief["observation_id"]]
    assert belief["supporting_observation_ids"] == [durable["observation_id"]]
    assert belief["evidence_age_s"] == pytest.approx(10.0), "age follows the newest live row"
    assert belief["stale"] is False


def test_an_out_of_order_older_source_is_a_replay_not_expired_evidence(tmp_path: Path) -> None:
    """Late delivery of an older source timestamp is rejected, not silently freshened."""
    newest = _observe(tmp_path, observed_at=200.0, ttl_s=1000.0, now=200.0)
    late = _observe(tmp_path, observed_at=100.0, ttl_s=5.0, now=300.0)

    assert late["freshens"] is False
    assert late["record_class"] == "STALE_REPLAY"
    belief = entity_belief("mug_1", now=301.0, state_dir=tmp_path)
    assert late["observation_id"] in belief["rejected_observation_ids"]
    assert belief["supporting_observation_ids"] == [newest["observation_id"]]
    assert belief["expired_evidence_ids"] == [], "a rejected replay is not expiry bookkeeping"


def test_a_replayed_observation_id_cannot_renew_the_evidence(tmp_path: Path) -> None:
    """Duplicate IDs are rejected outright, so a replay cannot reset the clock."""
    original = _observe(tmp_path, observed_at=100.0, ttl_s=1.0, now=100.0)
    replay = _observe(
        tmp_path,
        observed_at=100.0,
        ttl_s=1.0,
        now=500.0,
        observation_id=original["observation_id"],
    )

    assert replay["freshens"] is False
    assert replay["record_class"] == "DUPLICATE_REPLAY"
    belief = entity_belief("mug_1", now=501.0, state_dir=tmp_path)
    assert belief["expired_evidence_ids"] == [original["observation_id"]]
    assert belief["supporting_observation_ids"] == []
    assert belief["stale"] is True


def test_each_attribute_expires_with_the_row_that_reported_it(tmp_path: Path) -> None:
    """Per-attribute expiry: a stale attribute leaves, a fresh peer stays."""
    _observe(tmp_path, observed_at=100.0, ttl_s=2.0, attributes={"colour": "red"}, now=100.0)
    kept = _observe(
        tmp_path, observed_at=101.0, ttl_s=1000.0, attributes={"weight_kg": 0.4}, now=101.0
    )
    belief = entity_belief("mug_1", now=110.0, state_dir=tmp_path)

    assert set(belief["attributes"]) == {"weight_kg"}
    assert belief["attributes"]["weight_kg"]["observation_id"] == kept["observation_id"]
    assert belief["supporting_observation_ids"] == [kept["observation_id"]]
    assert len(belief["expired_evidence_ids"]) == 1, "expired history stays visible"


# --- R3: unknown uncertainty is never false precision ---------------------------


def _pose_with_yaw(x: float, y: float, yaw_rad: float) -> dict:
    """R3-local: a measured heading, which the shared _pose helper does not build."""
    pose = _pose(x, y)
    pose["yaw_rad"] = yaw_rad
    return pose


def _pose_covariance(tmp_path: Path, pose: dict, **kwargs) -> list[float]:
    _observe(tmp_path, pose=pose, now=100.0, **kwargs)
    snapshot = belief_snapshot(
        body_id="rover-1",
        map_ref={"map_id": "m1", "map_revision": "sha256:" + "a" * 64},
        now=100.0,
        state_dir=tmp_path,
    )
    return snapshot["entities"][0]["pose"]["covariance"]


def test_an_unreported_position_uncertainty_is_unknown_not_zero(tmp_path: Path) -> None:
    """Silence is not precision: the old code wrote 1e-9, i.e. near-certainty."""
    covariance = _pose_covariance(tmp_path, _pose(1.0, 2.0))

    assert covariance[0] == POSE_VARIANCE_UNKNOWN
    assert covariance[4] == POSE_VARIANCE_UNKNOWN
    assert covariance[0] != pytest.approx(1e-9), "an absence must not read as near-certainty"
    assert len(covariance) == 9


def test_position_and_angular_uncertainty_are_independent(tmp_path: Path) -> None:
    """R3: the heading slot must not borrow the position variance."""
    covariance = _pose_covariance(
        tmp_path,
        _pose_with_yaw(1.0, 2.0, 0.3),
        pose_uncertainty_m=0.5,
        pose_uncertainty_rad=0.05,
    )

    assert covariance[0] == pytest.approx(0.25), "position variance is its own squared value"
    assert covariance[8] == pytest.approx(0.0025), "heading variance is its own squared value"
    assert covariance[8] != pytest.approx(covariance[0]), "the two axes are not interchangeable"


def test_an_angular_uncertainty_never_leaks_into_the_position_slot(tmp_path: Path) -> None:
    covariance = _pose_covariance(
        tmp_path, _pose_with_yaw(1.0, 2.0, 0.3), pose_uncertainty_rad=0.25
    )

    assert covariance[0] == POSE_VARIANCE_UNKNOWN, "an angular figure is not a position figure"
    assert covariance[8] == pytest.approx(0.0625)


def test_a_measured_heading_without_angular_uncertainty_stays_unknown(tmp_path: Path) -> None:
    """A measured angle with no reported spread is unknown spread, not position spread."""
    covariance = _pose_covariance(
        tmp_path, _pose_with_yaw(1.0, 2.0, 0.3), pose_uncertainty_m=0.5
    )

    assert covariance[0] == pytest.approx(0.25)
    assert covariance[8] == POSE_VARIANCE_UNKNOWN


def test_an_unmeasured_heading_keeps_its_maximum_entropy_variance(tmp_path: Path) -> None:
    """The established heading convention is preserved: no yaw means (pi/2)^2."""
    covariance = _pose_covariance(tmp_path, _pose(1.0, 2.0), pose_uncertainty_m=0.1)

    assert covariance[8] == pytest.approx((math.pi / 2.0) ** 2)
    assert covariance[0] == pytest.approx(0.01)


def test_a_reported_zero_uncertainty_is_not_inflated_by_a_floor(tmp_path: Path) -> None:
    """An explicit 0.0 is the source's claim to make, and it is preserved."""
    covariance = _pose_covariance(tmp_path, _pose(1.0, 2.0), pose_uncertainty_m=0.0)

    assert covariance[0] == pytest.approx(0.0)
    assert covariance[0] != pytest.approx(1e-9)


def test_an_unreported_uncertainty_is_absent_from_the_belief_pose(tmp_path: Path) -> None:
    """The belief must not invent an uncertainty field nobody measured."""
    _observe(tmp_path, pose=_pose(1.0, 2.0), now=100.0)
    pose = entity_belief("mug_1", now=100.0, state_dir=tmp_path)["pose"]

    assert "uncertainty_m" not in pose
    assert "uncertainty_rad" not in pose


def test_a_reported_angular_uncertainty_reaches_the_belief_pose(tmp_path: Path) -> None:
    _observe(
        tmp_path, pose=_pose_with_yaw(1.0, 2.0, 0.3), pose_uncertainty_rad=0.05, now=100.0
    )
    pose = entity_belief("mug_1", now=100.0, state_dir=tmp_path)["pose"]

    assert pose["uncertainty_rad"] == pytest.approx(0.05)
    assert "uncertainty_m" not in pose, "the axes stay independent end to end"
