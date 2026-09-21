"""D3H-1: a body that really moves, wired into ordinary startup, witnessed separately.

The defect this file exists to falsify: the adaptive step path was reachable but had
no real body behind it. Nothing in Alice's ordinary startup registered an adapter, so
in production every step would have been refused for want of one, and the only bodies
in existence were test doubles. What follows checks, one clause at a time:

* the body satisfies the frozen adapter contract, proven against the contract itself
  rather than by the author's assurance;
* the effect is **real** -- bytes on disk, read back and hashed by the test, not a
  return value taken on trust;
* the effect is **reversible**, and a reversal that cannot be performed says so;
* status is **persisted**, so a second process reconciles from disk instead of
  inheriting the first process's memory;
* the witness is **separate**: it re-reads and re-hashes the bytes, refuses when the
  bytes changed underneath it, and refuses a postcondition it cannot observe;
* a repeat is not a second effect, and a reused id with changed content is refused;
* the whole path holds end to end through the real binding, with the real body and
  the real witness, ending ``completed`` because a witness confirmed -- not because
  the body said so.

Everything runs in a temporary workspace and a temporary state directory. Nothing
here touches live ``.sifta_state``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import System.swarm_adaptive_step_binding as step_binding  # noqa: E402
import System.swarm_adaptive_software_body as body_mod  # noqa: E402
from System.swarm_action_journal import ActionJournal  # noqa: E402
from System.swarm_adaptive_contracts import adapter_report, assert_adapter  # noqa: E402
from System.swarm_adaptive_goal_loop import (  # noqa: E402
    AdapterBinding,
    GoalLoop,
    ManualClock,
)
from System.swarm_adaptive_step_binding import (  # noqa: E402
    OUTCOME_COMPLETED,
    AdaptiveStepBinding,
)
from System.swarm_adaptive_software_body import (  # noqa: E402
    ADAPTER_ID,
    CAPABILITY_REVISION,
    POSTCONDITION,
    STATE_FILENAME,
    VERIFIER_ID,
    SoftwareBodyError,
    SoftwareFileAdapter,
    SoftwareFileVerifier,
    install_software_body,
    registration_report,
    require_software_body,
)

NOW = "2026-01-01T12:00:00Z"
CAP = "locomotion"

GID = str(uuid.uuid5(uuid.NAMESPACE_URL, "d3h1.goal.root"))
AID = str(uuid.uuid5(uuid.NAMESPACE_URL, "d3h1.action.write"))
AID2 = str(uuid.uuid5(uuid.NAMESPACE_URL, "d3h1.action.write.two"))

TEXT = "dock latch released\n"
TEXT2 = "dock latch released, then somebody else wrote a different story\n"


# --- fixtures shaped exactly like the frozen contracts ------------------------


def _goal(goal_id=GID):
    return {
        "schema_version": "1.0.0",
        "goal_id": goal_id,
        "owner_provenance": {"source": "owner", "owner_authorized": True, "task_id": "t1"},
        "task_family": "nav",
        "desired_observable": "latch_released",
        "predicate": "file_bytes_at_path",
        "deadline_utc": None,
        "budget": None,
        "dependency_ids": [],
        "active_subgoal": None,
        "progress_condition": "progress",
        "failure_condition": "failure",
        "checkpoint_ref": None,
        "revision_history": [{"revision": 0, "at_utc": NOW, "change": "created"}],
        "created_at_utc": NOW,
    }


def _proposal(action_id=AID, *, text=TEXT, rel_path="dock.txt", postcondition=POSTCONDITION):
    return {
        "schema_version": "1.0.0",
        "action_id": action_id,
        "goal_id": GID,
        "adapter_id": ADAPTER_ID,
        "capability_revision": CAPABILITY_REVISION,
        "action_kind": "write_file",
        "args": {"path": rel_path, "content": text},
        "required_observation_ids": ["obs-1"],
        "predicted_postcondition": postcondition,
        "predicted_uncertainty": 0.1,
        "predicted_cost": [],
        "cancellation_behavior": "stop",
        "recovery_behavior": "replan",
        "created_at_utc": NOW,
    }


def _body(tmp_path, **kwargs):
    workspace = tmp_path / "workspace"
    state_dir = tmp_path / "body_state"
    adapter = SoftwareFileAdapter(workspace=workspace, state_dir=state_dir, **kwargs)
    return adapter, workspace, state_dir


def _witness(tmp_path, **kwargs):
    return SoftwareFileVerifier(
        workspace=tmp_path / "workspace", state_dir=tmp_path / "body_state", **kwargs
    )


def _field(row, name):
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def _chain_links_intact(rows) -> bool:
    """Linkage law of the append-only journal: each row names its predecessor."""
    previous = "genesis"
    for row in rows:
        if str(_field(row, "prev_hash")) != previous:
            return False
        previous = str(_field(row, "row_hash"))
    return True


# --- the contract, checked against the contract ------------------------------


def test_the_body_satisfies_the_frozen_adapter_contract(tmp_path):
    adapter, _, _ = _body(tmp_path)
    assert_adapter(adapter)  # raises ContractError if a required method is missing
    report = adapter_report(adapter)
    assert report["missing"] == []
    assert set(report["present"]) == {"probe", "observe", "submit", "status", "cancel", "recover"}
    assert adapter.probe()["ready"] is True
    assert adapter.probe()["reversible"] is True


def test_installation_registers_on_the_same_registry_the_step_path_reads(tmp_path):
    report = install_software_body(workspace=tmp_path / "workspace", state_dir=tmp_path / "body_state")

    assert report["registered"] is True, report
    assert report["reason_code"] is None
    # The hazard this guards: a body that registers on a *second* copy of the binding
    # module would be invisible to the real path. Prove the two names are one module.
    assert body_mod.lookup_adaptive_body is step_binding.lookup_adaptive_body

    entry = step_binding.lookup_adaptive_body(ADAPTER_ID)
    assert entry is not None
    assert entry["capability_revision"] == CAPABILITY_REVISION
    assert entry["adapter"].__class__ is SoftwareFileAdapter
    assert step_binding.lookup_adaptive_verifier(VERIFIER_ID).__class__ is SoftwareFileVerifier


def test_an_unregistered_adapter_gets_a_precise_diagnostic(tmp_path):
    """The absence that caused the defect must now be nameable, not silent."""
    report = require_software_body("no_such_body_was_ever_registered")

    assert report["registered"] is False
    assert report["reason_code"] == "ADAPTER_NOT_REGISTERED"
    assert "install_software_body" in report["detail"]
    assert "swarm_boot" in report["detail"], "the detail does not say where registration belongs"
    assert step_binding.lookup_adaptive_body("no_such_body_was_ever_registered") is None


def test_the_registration_report_is_honest_about_a_body_that_is_not_there():
    plain = registration_report()
    # Whatever the process state, the report must agree with the registry.
    entry = step_binding.lookup_adaptive_body(ADAPTER_ID)
    assert plain["registered"] is (entry is not None)
    if entry is None:
        assert plain["reason_code"] == "ADAPTER_NOT_REGISTERED"
        assert plain["probe"] is None


# --- the effect is real, and reversible --------------------------------------


def test_the_effect_is_real_bytes_read_back_and_hashed(tmp_path):
    adapter, workspace, _ = _body(tmp_path)
    adapter.submit(_proposal())

    target = workspace / "dock.txt"
    assert target.exists(), "the body reported success without writing anything"
    assert target.read_text(encoding="utf-8") == TEXT

    reported = adapter.status(AID)
    assert reported["status"] == "succeeded"
    import hashlib

    real = "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest()
    assert reported["sha256"] == real, "the reported hash is not the hash of the bytes on disk"
    assert reported["size"] == len(TEXT.encode("utf-8"))
    assert reported["observation_ids"], "a succeeded action carried no observation"


def test_the_effect_is_reversible_and_the_reversal_is_reported(tmp_path):
    adapter, workspace, _ = _body(tmp_path)
    adapter.submit(_proposal())
    assert (workspace / "dock.txt").exists()

    reversal = adapter.recover(AID)

    assert reversal["reversed"] is True
    assert reversal["status"] == "succeeded"
    assert not (workspace / "dock.txt").exists(), "the created file survived its own reversal"
    assert adapter.status(AID)["reversed"] is True
    assert adapter.recover(AID)["detail"].startswith("already reversed")


def test_reversal_restores_the_bytes_that_were_there_before(tmp_path):
    adapter, workspace, _ = _body(tmp_path)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "dock.txt").write_text("the original dock log\n", encoding="utf-8")

    adapter.submit(_proposal())
    assert (workspace / "dock.txt").read_text(encoding="utf-8") == TEXT

    adapter.recover(AID)

    assert (workspace / "dock.txt").read_text(encoding="utf-8") == "the original dock log\n"


def test_reversing_an_action_that_never_happened_is_unknown_not_success(tmp_path):
    adapter, _, _ = _body(tmp_path)
    reversal = adapter.recover("an-action-this-body-never-saw")

    assert reversal["status"] == "unknown"
    assert reversal["reversed"] is False
    assert adapter.status("an-action-this-body-never-saw")["status"] == "unknown"
    assert adapter.cancel("an-action-this-body-never-saw") is True


def test_a_path_outside_the_workspace_is_refused_before_anything_is_written(tmp_path):
    adapter, workspace, _ = _body(tmp_path)
    escape = tmp_path / "outside.txt"

    with pytest.raises(SoftwareBodyError) as excinfo:
        adapter.submit(_proposal(rel_path="../outside.txt"))

    assert excinfo.value.code == "PATH_OUTSIDE_WORKSPACE"
    assert not escape.exists(), "the body escaped its workspace"
    assert adapter.known_actions() == (), "a refused action left a record behind"


# --- status survives the process that made it --------------------------------


def test_a_restart_reconciles_from_disk_and_confirms_with_a_fresh_witness(tmp_path):
    """Apply in a separate process; the parent must reconcile without that process's memory."""
    workspace = tmp_path / "workspace"
    state_dir = tmp_path / "body_state"
    script = (
        "import json, sys\n"
        "from System.swarm_adaptive_software_body import SoftwareFileAdapter\n"
        "adapter = SoftwareFileAdapter(workspace=sys.argv[1], state_dir=sys.argv[2])\n"
        "proposal = json.loads(sys.argv[3])\n"
        "print(json.dumps(adapter.submit(proposal)))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(workspace), str(state_dir), json.dumps(_proposal())],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    assert receipt["status"] == "accepted"
    assert (state_dir / STATE_FILENAME).exists(), "the body kept its state only in memory"

    # A parent process that never saw that adapter's memory.
    fresh = SoftwareFileAdapter.from_state(workspace=workspace, state_dir=state_dir)
    reported = fresh.status(AID)
    assert reported["status"] == "succeeded"
    assert reported["receipt_id"] == receipt["receipt_id"]
    assert AID in fresh.known_actions()
    assert (workspace / "dock.txt").read_text(encoding="utf-8") == TEXT

    # And a fresh witness can confirm it using nothing but the disk.
    verdict = SoftwareFileVerifier(workspace=workspace, state_dir=state_dir).verify(
        {"action_id": AID, "predicted_postcondition": POSTCONDITION}
    )
    assert verdict["verified"] is True
    assert verdict["observation_ids"]


# --- the witness looks for itself --------------------------------------------


def test_the_witness_reads_bytes_instead_of_believing_the_body(tmp_path):
    adapter, workspace, _ = _body(tmp_path)
    adapter.submit(_proposal())

    verdict = _witness(tmp_path).verify(
        {"action_id": AID, "predicted_postcondition": POSTCONDITION}
    )

    assert verdict["verified"] is True
    assert verdict["method"] == "independent_byte_read"
    assert len(verdict["observation_ids"]) == 1
    # The id is a claim about bytes: re-hash reality and check the id still holds.
    assert adapter.verify_observation(verdict["observation_ids"][0])["valid"] is True

    # Now change the bytes behind the body's back.
    (workspace / "dock.txt").write_text("someone rewrote the dock log\n", encoding="utf-8")
    retracted = _witness(tmp_path).verify(
        {"action_id": AID, "predicted_postcondition": POSTCONDITION}
    )

    assert retracted["verified"] is False
    assert retracted["observation_ids"] == []
    assert "not confirmed" in retracted["detail"]
    assert adapter.verify_observation(verdict["observation_ids"][0])["valid"] is False


def test_the_witness_refuses_when_no_effect_was_ever_recorded(tmp_path):
    verdict = _witness(tmp_path).verify(
        {"action_id": "nothing-happened-here", "predicted_postcondition": POSTCONDITION}
    )

    assert verdict["verified"] is False
    assert verdict["observation_ids"] == []
    assert "no record" in verdict["detail"]


def test_the_witness_refuses_a_postcondition_it_cannot_observe(tmp_path):
    adapter, _, _ = _body(tmp_path)
    adapter.submit(_proposal())

    verdict = _witness(tmp_path).verify(
        {"action_id": AID, "predicted_postcondition": "at_pose"}
    )

    assert verdict["verified"] is False
    assert verdict["observation_ids"] == []
    assert POSTCONDITION in verdict["detail"], "the refusal does not name what this body can witness"


def test_the_witness_refuses_an_action_that_was_reversed(tmp_path):
    adapter, _, _ = _body(tmp_path)
    adapter.submit(_proposal())
    adapter.recover(AID)

    verdict = _witness(tmp_path).verify(
        {"action_id": AID, "predicted_postcondition": POSTCONDITION}
    )

    assert verdict["verified"] is False
    assert "reversed" in verdict["detail"]


# --- once, not twice ---------------------------------------------------------


def test_resubmitting_the_same_action_does_not_apply_a_second_effect(tmp_path):
    adapter, workspace, _ = _body(tmp_path)
    first = adapter.submit(_proposal())
    target = workspace / "dock.txt"
    target.write_text(TEXT, encoding="utf-8")
    before = target.stat().st_mtime_ns

    second = adapter.submit(_proposal())

    assert second["receipt_id"] == first["receipt_id"], "a repeat minted a second receipt"
    assert second.get("repeated") is True
    assert len(adapter.known_actions()) == 1, "a repeat created a second record"
    assert target.stat().st_mtime_ns == before, "the file was rewritten by a repeat"


def test_a_reused_action_id_with_changed_content_is_refused(tmp_path):
    adapter, workspace, _ = _body(tmp_path)
    adapter.submit(_proposal())

    with pytest.raises(SoftwareBodyError) as excinfo:
        adapter.submit(_proposal(text=TEXT2))

    assert excinfo.value.code == "ID_CONFLICT"
    assert (workspace / "dock.txt").read_text(encoding="utf-8") == TEXT, "the conflict overwrote the effect"


def test_a_proposal_without_an_action_id_is_refused(tmp_path):
    adapter, _, _ = _body(tmp_path)
    with pytest.raises(SoftwareBodyError) as excinfo:
        adapter.submit({"args": {"content": "nameless"}})
    assert excinfo.value.code == "INVALID_ARGUMENT"


# --- end to end: the real body, the real witness, the real binding -----------


def test_the_real_body_completes_a_step_through_the_invocation_path(tmp_path):
    """Completion must come from the witness, and the bytes must actually have moved."""
    adapter, workspace, state_dir = _body(tmp_path)
    journal = ActionJournal(tmp_path / "journal")
    loop = GoalLoop(
        graph=[_goal()],
        adapter=AdapterBinding.bind(ADAPTER_ID, adapter, capability_revision=CAPABILITY_REVISION),
        verifier=_witness(tmp_path),
        clock=ManualClock(utc=NOW),
        journal=journal,
    )
    binding = AdaptiveStepBinding(
        loop, readings={CAP: True}, state_root=tmp_path, ledger_state_dir=tmp_path / "lived"
    )

    report = binding.run_step(GID, _proposal(), preconditions=(CAP,))

    assert report["outcome"] == OUTCOME_COMPLETED, report
    assert report["ledger_error"] is None
    assert report["polls"] == 1
    actual = report["actual_observation_ids"]
    assert actual, "a completion carried no observation"
    assert all(str(i).startswith("obs:") for i in actual), (
        "the observation ids did not come from the independent byte read"
    )
    # The effect is not inferred from the report: read the disk.
    assert (workspace / "dock.txt").read_text(encoding="utf-8") == TEXT

    rows = journal.rows
    kinds = [_field(row, "kind") for row in rows]
    assert "verification" in kinds, "the witness verdict never reached the durable journal"
    assert kinds.count("completion") == 1
    assert _chain_links_intact(rows), "the journal's hash chain was broken"


def test_the_body_refuses_to_complete_when_the_bytes_were_replaced(tmp_path):
    """A body that reports success must never be believed over a witness that disagrees."""
    adapter, workspace, _ = _body(tmp_path)
    journal = ActionJournal(tmp_path / "journal")
    loop = GoalLoop(
        graph=[_goal()],
        adapter=AdapterBinding.bind(ADAPTER_ID, adapter, capability_revision=CAPABILITY_REVISION),
        verifier=_witness(tmp_path),
        clock=ManualClock(utc=NOW),
        journal=journal,
    )
    binding = AdaptiveStepBinding(
        loop, readings={CAP: True}, state_root=tmp_path, ledger_state_dir=tmp_path / "lived"
    )

    class _Tampering(SoftwareFileAdapter):
        """The same body, except it rewrites the file after the effect lands."""

        def submit(self, proposal):
            receipt = super().submit(proposal)
            (self.workspace / "dock.txt").write_text("a different story\n", encoding="utf-8")
            return receipt

    # Rebind the tampering body on a second loop so the substitution is explicit.
    tampering = _Tampering(workspace=workspace, state_dir=tmp_path / "body_state")
    loop2 = GoalLoop(
        graph=[_goal()],
        adapter=AdapterBinding.bind(
            ADAPTER_ID, tampering, capability_revision=CAPABILITY_REVISION
        ),
        verifier=_witness(tmp_path),
        clock=ManualClock(utc=NOW),
        journal=ActionJournal(tmp_path / "journal2"),
    )
    report2 = AdaptiveStepBinding(
        loop2, readings={CAP: True}, state_root=tmp_path, ledger_state_dir=tmp_path / "lived"
    ).run_step(GID, _proposal(action_id=AID2), preconditions=(CAP,))

    assert report2["outcome"] != OUTCOME_COMPLETED
    assert not report2.get("actual_observation_ids")
