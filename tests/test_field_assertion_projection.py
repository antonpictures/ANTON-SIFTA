"""Evidence revision must survive reordering, retries and contradictory reports."""
from dataclasses import replace
from itertools import permutations

import pytest

from System.swarm_observation_fusion import (
    Authority, FieldAssertion, Observation, project_field_assertions,
)


def observation(event_id="e1", **changes):
    base = Observation(event_id, event_id, 10, "n1", "audio", "physical",
                       "phone", Authority.AMBIENT_WORLD, web_session_id="s1",
                       confidence=0.4)
    return replace(base, **changes)


def assertion(assertion_id="a1", **changes):
    base = FieldAssertion(assertion_id, "n1", "s1", "sound", "source",
                          "speaker_media", ("e1",), 10, 100, confidence=0.9)
    return replace(base, **changes)


def project(obs, claims, **kwargs):
    return project_field_assertions(obs, claims, at=kwargs.pop("at", 30), **kwargs)


def test_conflicts_converge_under_every_order_and_duplicate_delivery():
    claims = [assertion(), assertion("a2", value="person"), assertion("a3")]
    expected = project([observation()], claims)
    for ordered in permutations(claims):
        assert project([observation()] * 2, [*ordered, ordered[0]]) == expected
    assert expected["beliefs"][0]["status"] == "conflict"
    assert all(r["confidence"] == 0.4 for r in expected["history"])
    assert expected["action_authority"] == "none"


def test_correction_preserves_history_and_expiry_does_not_resurrect_old_claim():
    claims = [assertion(), assertion("a2", valid_from=20, valid_until=40, value="radio")]
    correction = [("n1", "a2", "a1", "owner-correction-receipt")]
    out = project([observation()], claims, approved_corrections=correction)
    assert out["beliefs"][0]["values"] == ["radio"]
    assert [r["state"] for r in out["history"]] == ["superseded", "active"]
    expired = project([observation()], claims, approved_corrections=correction, at=50)
    assert expired["beliefs"] == []
    assert len(expired["history"]) == 2
    assert project([observation()], claims)["beliefs"][0]["status"] == "conflict"


def test_correction_cannot_rewrite_reports_or_other_nodes():
    claims = [assertion(kind="reported"), assertion("a2", valid_from=20, value="radio"),
              assertion(node="n2"), assertion("a2", node="n2", valid_from=20, value="radio")]
    out = project([observation(), observation(node="n2")], claims,
                  approved_corrections=[("n1", "a2", "a1", "r")])
    assert out["corrections"] == []
    assert all(b["status"] == "conflict" for b in out["beliefs"])


def test_approved_correction_is_node_scoped_even_with_identical_ids():
    claims = [assertion(node=node, assertion_id=identity, valid_from=start, value=value)
              for node in ("n1", "n2")
              for identity, start, value in (("a1", 10, "person"), ("a2", 20, "radio"))]
    out = project([observation(), observation(node="n2")], claims,
                  approved_corrections=[("n1", "a2", "a1", "r")])
    assert [(b["scope"][0], b["status"]) for b in out["beliefs"]] == [
        ("n1", "supported"), ("n2", "conflict")]


def test_correction_chain_converges_with_reversed_operation_order():
    claims = [assertion(), assertion("a2", valid_from=20, value="radio"),
              assertion("a3", valid_from=21, value="tv")]
    ops = [("n1", "a2", "a1", "r1"), ("n1", "a3", "a2", "r2")]
    expected = project([observation()], claims, approved_corrections=ops)
    assert expected == project([observation()], reversed(claims),
                               approved_corrections=[*reversed(ops), ops[0]])
    assert expected["beliefs"][0]["values"] == ["tv"]


@pytest.mark.parametrize("changed", [
    {"web_session_id": "other-phone"}, {"node": "n2"}, {"ts": float("nan")}, {"ts": 99},
])
def test_missing_wrong_device_session_and_invalid_time_cannot_support_claim(changed):
    out = project([observation(**changed)], [assertion()])
    assert out["beliefs"] == []
    assert out["diagnostics"]


def test_collision_is_retained_as_diagnostic_and_never_last_writer_wins():
    obs = [observation(), observation(confidence=1)]
    assert project(obs, [assertion()]) == project(reversed(obs), [assertion()])
    assert project(obs, [assertion()])["beliefs"] == []
    claims = [assertion(), assertion(value="other")]
    assert project([observation()], claims) == project([observation()], reversed(claims))
    assert project([observation()], claims)["beliefs"] == []


def test_competing_corrections_remain_conflicted_and_cycles_cannot_erase_both():
    claims = [assertion(), assertion("a2", valid_from=20, value="radio"),
              assertion("a3", valid_from=21, value="tv")]
    out = project([observation()], claims, approved_corrections=[
        ("n1", "a2", "a1", "r1"), ("n1", "a3", "a1", "r2"),
        ("n1", "a1", "a2", "r3"),
    ])
    assert out["beliefs"][0]["values"] == ["radio", "tv"]
    assert len(out["corrections"]) == 2


def test_coordinate_frames_stay_separate_and_unknown_is_explicit():
    out = project([observation()], [assertion(), assertion("a2", coordinate_frame="map:2")])
    assert len(out["beliefs"]) == 2
    assert {b["scope"][2] for b in out["beliefs"]} == {"unknown", "map:2"}


def test_invalid_intervals_and_unbounded_work_rejected():
    for changes in ({"valid_until": float("inf")}, {"valid_from": 100}, {"evidence_ids": ()}):
        with pytest.raises(ValueError):
            assertion(**changes)
    with pytest.raises(ValueError, match="capacity"):
        project([observation()] * 3, [], max_items=2)
    with pytest.raises(ValueError):
        project([], [], at=float("nan"))
