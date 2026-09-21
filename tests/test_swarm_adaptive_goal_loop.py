"""D3a: the adaptive goal loop's seams, refusals, and DAG discipline.

Every test here drives injected time, an injected verifier and an injected
adapter, and touches no live state directory, no network and no real clock.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from System.swarm_adaptive_contracts import ContractError  # noqa: E402
from System.swarm_adaptive_goal_loop import (  # noqa: E402
    AdapterBinding,
    GoalGraph,
    GoalGraphError,
    GoalLoop,
    LifecycleError,
    LifecycleLedger,
    ManualClock,
    NullVerifier,
    VerificationIntegrityError,
    VerifierResult,
)

SHA = "sha256:" + "a" * 64


def _gid(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"d3a.goal.{label}"))


def _aid(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"d3a.action.{label}"))


def _goal(label: str, deps=(), **overrides) -> dict:
    record = {
        "schema_version": "1.0.0",
        "goal_id": _gid(label),
        "owner_provenance": {"source": "owner", "owner_authorized": True, "task_id": "t1"},
        "task_family": "nav",
        "desired_observable": "at_dock",
        "predicate": "at_pose",
        "deadline_utc": None,
        "budget": None,
        "dependency_ids": [_gid(d) for d in deps],
        "active_subgoal": None,
        "progress_condition": "progress",
        "failure_condition": "failure",
        "checkpoint_ref": None,
        "revision_history": [{"revision": 0, "at_utc": "2026-01-01T00:00:00Z", "change": "created"}],
        "created_at_utc": "2026-01-01T00:00:00Z",
    }
    record.update(overrides)
    return record


def _proposal(label: str, goal_label: str, **overrides) -> dict:
    record = {
        "schema_version": "1.0.0",
        "action_id": _aid(label),
        "goal_id": _gid(goal_label),
        "adapter_id": "nav2",
        "capability_revision": SHA,
        "action_kind": "navigate_to_pose",
        "args": {"x_m": 1.0, "y_m": 1.0},
        "required_observation_ids": ["obs-1"],
        "predicted_postcondition": "at_pose",
        "predicted_uncertainty": 0.1,
        "predicted_cost": [],
        "cancellation_behavior": "stop",
        "recovery_behavior": "replan",
        "created_at_utc": "2026-01-01T00:00:00Z",
    }
    record.update(overrides)
    return record


def _result(label: str, status: str, **overrides) -> dict:
    record = {
        "schema_version": "1.0.0",
        "action_id": _aid(label),
        "status": status,
        "actual_observation_ids": [],
        "verifier_result": None,
        "cost": None,
        "error": None,
        "effect_receipt_id": None,
        "updated_at_utc": "2026-01-01T00:00:00Z",
    }
    record.update(overrides)
    return record


class _FakeAdapter:
    def probe(self):
        return {}

    def observe(self, cursor):
        return {}

    def submit(self, action):
        return "receipt-1"

    def status(self, action_id):
        return {}

    def cancel(self, action_id):
        return True

    def recover(self, checkpoint):
        return True


class _PhysicalAdapter(_FakeAdapter):
    def stop(self):
        return True


# --- frozen records -----------------------------------------------------------


def test_a_goal_is_validated_against_the_frozen_contract() -> None:
    broken = _goal("broken")
    del broken["predicate"]

    with pytest.raises(ContractError):
        GoalGraph([broken])


def test_a_goal_record_missing_a_field_is_never_half_consumed() -> None:
    broken = _goal("broken2")
    broken["desired_observable"] = ""

    with pytest.raises(ContractError):
        GoalGraph([broken])


def test_the_graph_reports_the_frozen_schema_version_it_validated() -> None:
    graph = GoalGraph([_goal("solo")])

    assert graph.node(_gid("solo")).record["schema_version"] == "1.0.0"


# --- DAG refusals -------------------------------------------------------------


def test_a_dependency_cycle_is_refused_by_name() -> None:
    a = _goal("cycle_a", deps=("cycle_b",))
    b = _goal("cycle_b", deps=("cycle_a",))

    with pytest.raises(GoalGraphError) as excinfo:
        GoalGraph([a, b])

    assert excinfo.value.code == "CYCLE"


def test_a_self_dependency_is_refused_by_the_frozen_contract_first() -> None:
    record = _goal("selfish")
    record["dependency_ids"] = [record["goal_id"]]

    # The C0 contract owns this rule and raises before any graph exists, so the
    # loop's own SELF_DEPENDENCY guard is defense-in-depth, not the first line.
    with pytest.raises(ContractError):
        GoalGraph([record])


def test_an_unknown_dependency_is_refused() -> None:
    with pytest.raises(GoalGraphError) as excinfo:
        GoalGraph([_goal("orphan", deps=("never_defined",))])

    assert excinfo.value.code == "MISSING_DEPENDENCY"


def test_a_duplicate_goal_id_is_refused() -> None:
    with pytest.raises(GoalGraphError) as excinfo:
        GoalGraph([_goal("twin"), _goal("twin")])

    assert excinfo.value.code == "DUPLICATE_GOAL_ID"


# --- DAG ordering -------------------------------------------------------------


def test_execution_order_places_every_goal_after_its_dependencies() -> None:
    graph = GoalGraph([_goal("third", deps=("second",)), _goal("second", deps=("first",)), _goal("first")])
    order = list(graph.execution_order)

    assert order.index(_gid("first")) < order.index(_gid("second"))
    assert order.index(_gid("second")) < order.index(_gid("third"))


def test_a_goal_is_not_ready_until_its_dependency_is_complete() -> None:
    graph = GoalGraph([_goal("root"), _goal("leaf", deps=("root",))])

    assert graph.ready([]) == (_gid("root"),)
    assert graph.ready([_gid("root")]) == (_gid("leaf"),)


def test_a_blocked_goal_names_the_exact_dependency_holding_it() -> None:
    graph = GoalGraph([_goal("root"), _goal("leaf", deps=("root",))])
    blocked = {entry["goal_id"]: entry["blocked_by"] for entry in graph.blocked([])}

    assert blocked[_gid("leaf")] == [_gid("root")]


def test_an_unrelated_completion_does_not_make_a_goal_ready() -> None:
    graph = GoalGraph([_goal("root"), _goal("leaf", deps=("root",)), _goal("other")])

    assert _gid("leaf") not in graph.ready([_gid("other")])


def test_completing_an_unknown_goal_is_refused() -> None:
    graph = GoalGraph([_goal("root")])

    with pytest.raises(GoalGraphError) as excinfo:
        graph.ready(["not-a-goal"])

    assert excinfo.value.code == "UNKNOWN_GOAL"


def test_roots_need_no_dependencies() -> None:
    graph = GoalGraph([_goal("root"), _goal("leaf", deps=("root",))])

    assert graph.roots() == (_gid("root"),)


# --- clock seam ---------------------------------------------------------------


def test_a_deadline_is_judged_by_the_injected_clock_alone() -> None:
    clock = ManualClock(utc="2026-01-01T00:00:00Z")
    graph = GoalGraph([_goal("timed", deadline_utc="2026-01-01T00:01:00Z")])

    assert graph.deadline_expired(_gid("timed"), clock) is False
    clock.advance(120)
    assert graph.deadline_expired(_gid("timed"), clock) is True


def test_a_goal_without_a_deadline_never_expires() -> None:
    clock = ManualClock(utc="2030-01-01T00:00:00Z")
    graph = GoalGraph([_goal("open")])

    assert graph.deadline_expired(_gid("open"), clock) is False


def test_the_injected_clock_is_the_one_the_loop_reads() -> None:
    clock = ManualClock(utc="2026-01-01T00:00:00Z")
    loop = GoalLoop(clock=clock)

    assert loop.clock is clock
    assert loop.clock.now_utc() == "2026-01-01T00:00:00Z"


# --- verifier seam ------------------------------------------------------------


def test_a_null_verifier_never_claims_success() -> None:
    loop = GoalLoop(graph=[_goal("root")])
    loop.propose(_proposal("act", "root"))

    outcome = loop.verify(_aid("act"))

    assert outcome.verified is False
    assert outcome.observation_ids == ()
    assert isinstance(loop.verifier, NullVerifier)


def test_a_success_claim_without_evidence_is_refused() -> None:
    with pytest.raises(VerificationIntegrityError) as excinfo:
        VerifierResult.from_payload(
            {"verified": True, "verifier": "lidar", "method": "dist", "observation_ids": []}
        )

    assert excinfo.value.code == "UNEVIDENCED_SUCCESS"


def test_a_verifier_result_that_is_not_a_mapping_is_refused() -> None:
    with pytest.raises(VerificationIntegrityError):
        VerifierResult.from_payload("verified")


def test_an_evidenced_verifier_result_is_read_unchanged() -> None:
    payload = {
        "verified": True,
        "verifier": "lidar",
        "method": "distance",
        "detail": None,
        "observation_ids": ["obs-9"],
    }

    assert VerifierResult.from_payload(payload).to_dict() == payload


def test_a_failure_without_evidence_is_still_readable() -> None:
    outcome = VerifierResult.from_payload(
        {"verified": False, "verifier": "lidar", "method": "distance", "observation_ids": []}
    )

    assert outcome.verified is False


def test_the_injected_verifier_is_the_one_the_loop_asks() -> None:
    seen = {}

    class _Verifier:
        def verify(self, request):
            seen.update(request)
            return {
                "verified": True,
                "verifier": "lidar",
                "method": "distance",
                "observation_ids": ["obs-1"],
            }

    loop = GoalLoop(graph=[_goal("root")], verifier=_Verifier())
    loop.propose(_proposal("act", "root"))
    outcome = loop.verify(_aid("act"))

    assert outcome.verified is True
    assert seen["action_id"] == _aid("act")
    assert seen["predicted_postcondition"] == "at_pose"


def test_verifying_an_action_that_was_never_proposed_is_refused() -> None:
    loop = GoalLoop()

    with pytest.raises(LifecycleError) as excinfo:
        loop.verify(_aid("ghost"))

    assert excinfo.value.code == "UNKNOWN_ACTION"


# --- action proposals ---------------------------------------------------------


def test_a_proposal_for_a_goal_with_unmet_dependencies_is_refused() -> None:
    loop = GoalLoop(graph=[_goal("root"), _goal("leaf", deps=("root",))])

    with pytest.raises(GoalGraphError) as excinfo:
        loop.propose(_proposal("act", "leaf"))

    assert excinfo.value.code == "GOAL_NOT_READY"
    assert _gid("leaf") in excinfo.value.detail
    assert _gid("root") in excinfo.value.detail


def test_a_proposal_becomes_legal_once_the_dependency_completes() -> None:
    loop = GoalLoop(graph=[_goal("root"), _goal("leaf", deps=("root",))])
    loop.mark_complete(_gid("root"))

    assert loop.propose(_proposal("act", "leaf"))["goal_id"] == _gid("leaf")


def test_a_proposal_for_an_unknown_goal_is_refused() -> None:
    loop = GoalLoop(graph=[_goal("root")])

    with pytest.raises(GoalGraphError) as excinfo:
        loop.propose(_proposal("act", "not_a_goal"))

    assert excinfo.value.code == "UNKNOWN_GOAL"


def test_a_proposal_asserting_an_out_of_range_uncertainty_is_refused() -> None:
    loop = GoalLoop(graph=[_goal("root")])

    with pytest.raises(ContractError):
        loop.propose(_proposal("act", "root", predicted_uncertainty=1.5))


# --- lifecycle discipline -----------------------------------------------------


def test_a_result_for_an_action_never_proposed_is_refused() -> None:
    loop = GoalLoop(graph=[_goal("root")])

    with pytest.raises(LifecycleError) as excinfo:
        loop.record_result(_result("act", "running"))

    assert excinfo.value.code == "UNKNOWN_ACTION"


def test_an_illegal_lifecycle_transition_is_refused() -> None:
    ledger = LifecycleLedger()
    ledger.observe("a1", "accepted")

    # 'received' is a legal lifecycle state that no action may return to.
    with pytest.raises(LifecycleError) as excinfo:
        ledger.observe("a1", "received")

    assert excinfo.value.code == "ILLEGAL_TRANSITION"
    assert ledger.state("a1") == "accepted"
    assert ledger.history("a1") == ("accepted",)


def test_a_terminal_action_state_admits_no_successor() -> None:
    loop = GoalLoop(graph=[_goal("root")])
    loop.propose(_proposal("act", "root"))
    loop.record_result(_result("act", "accepted"))
    loop.record_result(_result("act", "running"))
    loop.record_result(
        _result(
            "act",
            "succeeded",
            actual_observation_ids=["obs-1"],
            verifier_result={
                "verified": True,
                "verifier": "lidar",
                "method": "distance",
                "detail": None,
                "observation_ids": ["obs-1"],
            },
        )
    )

    with pytest.raises(LifecycleError) as excinfo:
        loop.record_result(_result("act", "failed"))

    assert excinfo.value.code == "ILLEGAL_TRANSITION"
    assert loop.lifecycle.state(_aid("act")) == "succeeded"


def test_an_action_result_may_not_claim_a_goal_only_state() -> None:
    loop = GoalLoop(graph=[_goal("root")])
    loop.propose(_proposal("act", "root"))

    # The frozen ActionResult.status enum is deliberately narrower than the goal
    # lifecycle: an action cannot report 'received', 'timed_out' or 'rejected'.
    for goal_only in ("received", "timed_out", "rejected"):
        with pytest.raises(ContractError):
            loop.record_result(_result("act", goal_only))
    assert loop.lifecycle.state(_aid("act")) is None


def test_a_succeeded_result_requires_evidence_by_contract() -> None:
    loop = GoalLoop(graph=[_goal("root")])
    loop.propose(_proposal("act", "root"))

    with pytest.raises(ContractError):
        loop.record_result(_result("act", "succeeded"))


def test_a_fully_evidenced_success_is_accepted() -> None:
    loop = GoalLoop(graph=[_goal("root")])
    loop.propose(_proposal("act", "root"))
    recorded = loop.record_result(
        _result(
            "act",
            "succeeded",
            actual_observation_ids=["obs-1"],
            verifier_result={
                "verified": True,
                "verifier": "lidar",
                "method": "distance",
                "detail": None,
                "observation_ids": ["obs-1"],
            },
        )
    )

    assert recorded["status"] == "succeeded"
    assert loop.lifecycle.state(_aid("act")) == "succeeded"
    assert loop.lifecycle.is_terminal("succeeded") is True


def test_unknown_is_not_terminal_and_stays_unresolved() -> None:
    loop = GoalLoop(graph=[_goal("root")])
    loop.propose(_proposal("act", "root"))
    loop.record_result(_result("act", "unknown"))

    assert loop.lifecycle.state(_aid("act")) == "unknown"
    assert loop.lifecycle.is_terminal("unknown") is False
    assert loop.unresolved_actions() == (_aid("act"),)


def test_an_unknown_result_may_not_carry_a_verifier_result() -> None:
    loop = GoalLoop(graph=[_goal("root")])
    loop.propose(_proposal("act", "root"))

    with pytest.raises(ContractError):
        loop.record_result(
            _result(
                "act",
                "unknown",
                verifier_result={
                    "verified": False,
                    "verifier": "lidar",
                    "method": "distance",
                    "detail": None,
                    "observation_ids": [],
                },
            )
        )


def test_a_status_outside_the_contract_is_refused() -> None:
    ledger = LifecycleLedger()

    with pytest.raises(LifecycleError) as excinfo:
        ledger.observe("a1", "nearly_done")

    assert excinfo.value.code == "UNKNOWN_STATE"


def test_a_repeated_identical_status_is_not_a_transition() -> None:
    ledger = LifecycleLedger()
    ledger.observe("a1", "running")

    assert ledger.observe("a1", "running") == "running"
    assert ledger.history("a1") == ("running",)


def test_every_lifecycle_state_is_reachable_from_unknown() -> None:
    for state in ("succeeded", "failed", "cancelled", "timed_out", "rejected", "accepted", "running"):
        ledger = LifecycleLedger()
        ledger.observe("a1", "unknown")
        assert ledger.observe("a1", state) == state


# --- adapter seam -------------------------------------------------------------


def test_a_complete_adapter_can_be_bound() -> None:
    binding = AdapterBinding.bind("nav2", _FakeAdapter(), capability_revision=SHA)

    assert binding.adapter_id == "nav2"
    assert binding.physical is False


def test_an_adapter_missing_a_contract_method_cannot_be_bound() -> None:
    class _Partial:
        def probe(self):
            return {}

    with pytest.raises(ContractError) as excinfo:
        AdapterBinding.bind("broken", _Partial())

    assert "submit" in excinfo.value.message


def test_a_physical_adapter_must_implement_stop() -> None:
    with pytest.raises(ContractError) as excinfo:
        AdapterBinding.bind("physical", _FakeAdapter(), physical=True)

    assert "stop" in excinfo.value.message


def test_a_physical_adapter_implementing_stop_binds() -> None:
    binding = AdapterBinding.bind("physical", _PhysicalAdapter(), physical=True)

    assert binding.physical is True


def test_a_nameless_adapter_is_refused() -> None:
    with pytest.raises(ContractError):
        AdapterBinding.bind("", _FakeAdapter())


# --- the loop as a whole ------------------------------------------------------


def test_the_loop_walks_a_three_goal_chain_in_dependency_order() -> None:
    loop = GoalLoop(graph=[_goal("c", deps=("b",)), _goal("b", deps=("a",)), _goal("a")])
    visited = []

    while True:
        ready = loop.ready_goals()
        if not ready:
            break
        visited.append(ready[0])
        loop.mark_complete(ready[0])

    assert visited == [_gid("a"), _gid("b"), _gid("c")]
    assert loop.ready_goals() == ()
    assert loop.blocked_goals() == ()


def test_a_registered_goal_revalidates_the_whole_graph() -> None:
    loop = GoalLoop(graph=[_goal("root")])
    loop.register_goal(_goal("leaf", deps=("root",)))

    assert set(loop.graph.goal_ids) == {_gid("root"), _gid("leaf")}


def test_registering_a_goal_with_an_unknown_dependency_is_refused_and_leaves_the_graph_intact() -> None:
    loop = GoalLoop(graph=[_goal("root")])

    with pytest.raises(GoalGraphError) as excinfo:
        loop.register_goal(_goal("leaf", deps=("never_defined",)))

    assert excinfo.value.code == "MISSING_DEPENDENCY"
    assert loop.graph.goal_ids == (_gid("root"),)
    assert loop.ready_goals() == (_gid("root"),)


def test_the_loop_reports_a_proposal_it_never_made_as_absent() -> None:
    loop = GoalLoop(graph=[_goal("root")])

    assert loop.proposal(_aid("nothing")) is None
    assert loop.result(_aid("nothing")) is None
