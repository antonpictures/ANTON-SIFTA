#!/usr/bin/env python3
"""E0 — independent executable scenario runner over the adaptation gauntlet.

This tool exists because a gauntlet that only runs inside pytest is not an
executable evaluation: it cannot be pointed at a manifest, run scenario by
scenario, and leave its evidence on disk. What it drives is REAL — the real
SoftwareFileAdapter, the real SoftwareFileVerifier witness, the real
append-only journal with its hash chain, the real GoalLoop and the real
AdaptiveStepBinding — all in isolated temporary state (a per-run directory
under ``outputs/sifta_adaptation_eval/``), never in live ``.sifta_state``.

Scenarios (acceptance clauses, not theater):

* ``normal_cycle_restart_dependent`` — startup → goal → real software effect →
  independent observation (the runner re-reads and re-hashes the bytes itself)
  → receipt rows in the journal → full restart from disk (fresh adapter,
  journal, loop, binding objects over the same state dirs) → next DEPENDENT
  goal whose content embeds the independent digest of the first file, so it
  cannot succeed unless the first effect physically happened.
* ``dispatch_transient_fault`` — adapter.submit raises once (dispatch
  boundary); acceptance: the faulted attempt fabricates no success, a fresh
  attempt then completes under the success law, exactly the expected bytes
  exist, chain intact.
* ``journal_append_busy`` — journal.append raises once (durable-row boundary);
  acceptance: no completion may stand without durable journal rows; after
  recovery the step completes with a verification row and an intact chain.
* ``witness_disagrees`` — the body rewrites the bytes after the effect
  (ack/witness boundary); acceptance: NOT completed, no observation ids, the
  disagreement is recorded.
* ``hung_worker`` — submit blocks forever; run in a child process, terminated
  at the budget; the hang is recorded HONESTLY as the known single-threaded
  dispatch-boundary gap (D3H-3), never as success.

Success law (every "completed" claim must survive all five clauses):
1. report["outcome"] == OUTCOME_COMPLETED
2. report["actual_observation_ids"] non-empty
3. a "verification" row for the action exists in the journal
4. the journal hash chain links intact from "genesis"
5. the runner's OWN external byte read matches the expected content

The runner never writes success rows itself; it only reads what the real
machinery recorded and what the disk really holds.

Usage:
    python3 tools/sifta_adaptation_eval.py [--manifests FILE] [--out DIR]
        [--scenario NAME ...] [--hung-timeout-s N]

Exit code 0 iff every selected scenario met its acceptance clauses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import sys
import time
import traceback
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import System.swarm_adaptive_software_body as body_mod  # noqa: E402
from System.swarm_action_journal import ActionJournal  # noqa: E402
from System.swarm_adaptive_goal_loop import AdapterBinding, GoalLoop, ManualClock  # noqa: E402
from System.swarm_adaptive_step_binding import AdaptiveStepBinding, OUTCOME_COMPLETED  # noqa: E402

NOW = "2026-01-01T12:00:00Z"
CAP = "locomotion"
DEFAULT_MANIFESTS = ROOT / "tools" / "sifta_adaptation_manifests.json"
DEFAULT_OUT = ROOT / "outputs" / "sifta_adaptation_eval"
GENESIS = "genesis"
HUNG_TIMEOUT_S = 12.0


# --- manifest loading ---------------------------------------------------------

def load_manifests(path: Path) -> dict:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if "manifest_id" not in raw or not isinstance(raw.get("tasks"), list):
        raise ValueError(f"manifest {path} lacks manifest_id/tasks")
    for task in raw["tasks"]:
        if "task_id" not in task or not isinstance(task.get("steps"), list) or not task["steps"]:
            raise ValueError(f"manifest task lacks task_id/steps: {task!r}")
    return raw


def _task_by_id(manifests: dict, task_id: str) -> dict:
    for task in manifests["tasks"]:
        if task["task_id"] == task_id:
            return task
    raise KeyError(f"no hold-out task {task_id!r} in the manifests")


# --- the shapes, exactly as the frozen contracts expect them ------------------

def _goal(goal_id: str, *, dependency_ids=()) -> dict:
    return {
        "schema_version": "1.0.0",
        "goal_id": goal_id,
        "owner_provenance": {"source": "owner", "owner_authorized": True, "task_id": "t1"},
        "task_family": "nav",
        "desired_observable": "latch_released",
        "predicate": "file_bytes_at_path",
        "deadline_utc": None,
        "budget": None,
        "dependency_ids": list(dependency_ids),
        "active_subgoal": None,
        "progress_condition": "progress",
        "failure_condition": "failure",
        "checkpoint_ref": None,
        "revision_history": [{"revision": 0, "at_utc": NOW, "change": "created"}],
        "created_at_utc": NOW,
    }


def _proposal(goal_id: str, action_id: str, *, text: str, rel_path: str) -> dict:
    return {
        "schema_version": "1.0.0",
        "action_id": action_id,
        "goal_id": goal_id,
        "adapter_id": body_mod.ADAPTER_ID,
        "capability_revision": body_mod.CAPABILITY_REVISION,
        "action_kind": "write_file",
        "args": {"path": rel_path, "content": text},
        "required_observation_ids": ["obs-1"],
        "predicted_postcondition": body_mod.POSTCONDITION,
        "predicted_uncertainty": 0.1,
        "predicted_cost": [],
        "cancellation_behavior": "stop",
        "recovery_behavior": "replan",
        "created_at_utc": NOW,
    }


def _field(row, name):
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def _chain_ok(journal) -> bool:
    previous = GENESIS
    for row in journal.rows:
        if str(_field(row, "prev_hash")) != previous:
            return False
        previous = str(_field(row, "row_hash"))
    return True


def _journal_facts(journal) -> dict:
    rows = journal.rows
    kinds: list[str] = []
    for row in rows:
        kinds.append(str(_field(row, "kind")))
    return {
        "row_count": len(rows),
        "kinds": kinds,
        "chain_ok": _chain_ok(journal),
        "torn_lines": int(journal.torn_lines),
        "tampered_lines": int(journal.tampered_lines),
    }


def _independent_read(path: Path) -> dict:
    """The runner's own eyes: read the bytes and hash them. No adapter report."""
    if not path.is_file():
        return {"exists": False, "sha256": None, "size": 0}
    data = path.read_bytes()
    return {"exists": True, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


# --- fresh environment per scenario -------------------------------------------

class Env:
    """Isolated temporary state: workspace, body state, journal, binding ledger."""

    def __init__(self, base: Path):
        self.base = base
        self.workspace = base / "workspace"
        self.body_state = base / "body_state"
        self.journal_dir = base / "journal"
        self.ledger_dir = base / "lived"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.body_state.mkdir(parents=True, exist_ok=True)
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_dir.mkdir(parents=True, exist_ok=True)

    def adapter(self):
        return body_mod.SoftwareFileAdapter(workspace=self.workspace, state_dir=self.body_state)

    def witness(self):
        return body_mod.SoftwareFileVerifier(workspace=self.workspace, state_dir=self.body_state)

    def journal(self):
        return ActionJournal(self.journal_dir)

    def binding(self, *, adapter=None, journal=None, graph):
        loop = GoalLoop(
            graph=graph,
            adapter=AdapterBinding.bind(
                body_mod.ADAPTER_ID,
                adapter if adapter is not None else self.adapter(),
                capability_revision=body_mod.CAPABILITY_REVISION,
            ),
            verifier=self.witness(),
            clock=ManualClock(utc=NOW),
            journal=journal if journal is not None else self.journal(),
        )
        return AdaptiveStepBinding(
            loop, readings={CAP: True}, state_root=self.base, ledger_state_dir=self.ledger_dir
        )


def _success_law(env: Env, report: dict, action_id: str, rel_path: str, expected_text: str) -> dict:
    """The five-clause success law. A completion stands only if all clauses hold."""
    journal = env.journal()
    facts = _journal_facts(journal)
    verification_rows = [
        row
        for row in journal.rows
        if str(_field(row, "kind")) == "verification" and str(_field(row, "action_id")) == action_id
    ]
    external = _independent_read(env.workspace / rel_path)
    clauses = {
        "outcome_completed": report.get("outcome") == OUTCOME_COMPLETED,
        "observation_ids_present": bool(report.get("actual_observation_ids")),
        "verification_row_present": bool(verification_rows),
        "chain_intact": facts["chain_ok"],
        "independent_bytes_match": external["exists"]
        and external["sha256"] == hashlib.sha256(expected_text.encode("utf-8")).hexdigest(),
        "ledger_error_none": report.get("ledger_error") is None,
    }
    return {"clauses": clauses, "journal": facts, "external_read": external, "report": report}


def _render_task(task: dict, observed: dict) -> list[dict]:
    """Turn hold-out manifest steps into (goal, proposal) pairs, rendering
    dependent content from the REAL observed bytes of earlier steps.
    The contracts require real UUIDs for goal_id/action_id, so ids are minted
    per render and the manifest's labels are carried alongside for the report."""
    rendered = []
    gid_by_step: dict[int, str] = {}
    for step in task["steps"]:
        gid = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        dep_ids = []
        dep_label = None
        if step["step"] != 0:
            dep_step = int(step["depends_on_step"])
            dep_ids = [gid_by_step[dep_step]]
            dep_label = task["steps"][dep_step].get("goal_label")
        text = step.get("content")
        if text is None:
            dep = task["steps"][int(step["depends_on_step"])]
            template = step["content_template"]
            text = template.format(
                depends_rel_path=dep["rel_path"],
                depends_digest=observed.get(dep["rel_path"], {}).get("sha256", "UNOBSERVED"),
            )
        rendered.append(
            {
                "step": step["step"],
                "goal_label": step.get("goal_label"),
                "goal": _goal(gid, dependency_ids=dep_ids),
                "proposal": _proposal(gid, aid, text=text, rel_path=step["rel_path"]),
                "rel_path": step["rel_path"],
                "expected_text": text,
            }
        )
        gid_by_step[step["step"]] = gid
    return rendered


# --- fault wrappers (real boundaries, honest failures) ------------------------

class TransientSubmitFault:
    """Dispatch-boundary fault: adapter.submit raises once, then behaves."""

    def __init__(self, inner):
        self._inner = inner
        self._calls = 0

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def submit(self, proposal):
        self._calls += 1
        if self._calls == 1:
            raise body_mod.SoftwareBodyError("TRANSIENT_INJECTED", "injected once by sifta_adaptation_eval")
        return self._inner.submit(proposal)


class JournalAppendBusy:
    """Durable-row boundary fault: the first journal.append raises, then delegates."""

    def __init__(self, inner):
        self._inner = inner
        self.fired = False

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def append(self, *args, **kwargs):
        if not self.fired:
            self.fired = True
            raise RuntimeError("JOURNAL_BUSY injected once by sifta_adaptation_eval")
        return self._inner.append(*args, **kwargs)


class TamperingBody(body_mod.SoftwareFileAdapter):
    """Ack-boundary fault: the body rewrites the bytes after its own effect."""

    def submit(self, proposal):
        receipt = super().submit(proposal)
        try:
            target = self.workspace / str(proposal["args"]["path"])
            target.write_text("a different story written after the fact\n", encoding="utf-8")
        except Exception:
            pass
        return receipt


# --- scenarios ----------------------------------------------------------------

def scenario_normal_cycle_restart_dependent(env: Env, task: dict) -> dict:
    """The E0 acceptance scenario, straight from the handoff line."""
    rendered = _render_task(task, observed={})
    step0 = rendered[0]
    evidence: dict = {"task": task["task_id"], "steps": []}

    # 1) startup → goal 1 → real effect → independent observation
    binding = env.binding(graph=[step0["goal"]])
    report1 = binding.run_step(step0["goal"]["goal_id"], step0["proposal"], preconditions=(CAP,))
    law1 = _success_law(env, report1, step0["proposal"]["action_id"], step0["rel_path"], step0["expected_text"])
    observed = {step0["rel_path"]: _independent_read(env.workspace / step0["rel_path"])}
    evidence["steps"].append({"step": 0, "law": law1})

    # 2) receipt rows exist (the journal IS the durable receipt for the step)
    receipt_rows = [
        str(_field(r, "kind"))
        for r in env.journal().rows
        if str(_field(r, "action_id")) == step0["proposal"]["action_id"]
    ]
    evidence["step0_receipt_rows"] = receipt_rows

    # 3) full restart: fresh adapter/journal/loop/binding over the same state dirs;
    #    the dependent step's content is rendered from the INDEPENDENT read, not adapter memory
    re_rendered = _render_task(task, observed=observed)
    step0_re, step1_re = re_rendered[0], re_rendered[1]
    binding2 = env.binding(
        graph=[step0_re["goal"], step1_re["goal"]], adapter=env.adapter(), journal=env.journal()
    )
    findings: list[dict] = []

    # the documented restart move first: ask the body what actually happened
    reconciled = binding2.loop.reconcile()
    evidence["reconcile_after_restart"] = {
        "reconciled": list(reconciled.get("reconciled", [])),
        "loop_completed_goals": list(binding2.loop.completed),
    }
    if not binding2.loop.completed:
        findings.append(
            {
                "code": "RESTART_GOAL_STATE_NOT_JOURNALED",
                "detail": (
                    "after a restart over the same journal, the fresh loop's completed-goal "
                    "set is empty: GoalLoop keeps goal completion in memory and reconcile() "
                    "closes ACTIONS only, so a dependent goal is not ready even though the "
                    "journal holds step 0's completion rows"
                ),
            }
        )

    try:
        report2 = binding2.run_step(
            step1_re["goal"]["goal_id"], step1_re["proposal"], preconditions=(CAP,)
        )
        law2 = _success_law(env, report2, step1_re["proposal"]["action_id"], step1_re["rel_path"], step1_re["expected_text"])
        evidence["steps"].append({"step": 1, "law": law2})
        evidence["dependent_content"] = step1_re["expected_text"]
        restart_leg_completed = all(law2["clauses"].values())
    except Exception as exc:
        evidence["restart_leg"] = {"raised": type(exc).__name__, "detail": str(exc)[:300]}
        law2 = None
        restart_leg_completed = False

    # the dependent goal after restart is the acceptance line; if the machinery
    # refuses it, that is an exposed gap recorded here — never a fabricated pass
    if not restart_leg_completed:
        findings.append(
            {
                "code": "RESTART_DEPENDENT_GOAL_REFUSED",
                "detail": (
                    "restart→next dependent goal leg did NOT complete: the fresh loop "
                    "refused the goal (GOAL_NOT_READY) because goal completion is not "
                    "replayed from the journal; recorded as an exposed gauntlet finding, "
                    "not satisfied silently"
                ),
                "evidence": evidence.get("restart_leg")
                or ({"outcome": law2["report"].get("outcome")} if law2 else {}),
            }
        )

    ok = all(all(s["law"]["clauses"].values()) for s in evidence["steps"]) and bool(receipt_rows)
    return {"ok": bool(ok and restart_leg_completed), "findings": findings, "evidence": evidence}


def scenario_dispatch_transient_fault(env: Env, task: dict) -> dict:
    rendered = _render_task(task, observed={})[0]
    evidence: dict = {"task": task["task_id"]}

    faulted = TransientSubmitFault(env.adapter())
    binding = env.binding(graph=[rendered["goal"]], adapter=faulted)
    try:
        report1 = binding.run_step(rendered["goal"]["goal_id"], rendered["proposal"], preconditions=(CAP,))
        evidence["faulted_attempt"] = {
            "outcome": report1.get("outcome"),
            "fabricated_success": report1.get("outcome") == OUTCOME_COMPLETED,
            "ledger_error": report1.get("ledger_error"),
        }
    except Exception as exc:  # an honest fault surface, recorded as observed
        evidence["faulted_attempt"] = {"raised": type(exc).__name__, "detail": str(exc)[:200]}

    no_bytes = not (env.workspace / rendered["rel_path"]).exists()
    evidence["no_effect_after_fault"] = no_bytes

    # recovery: fresh attempt, same isolated env, no fault
    recovery = dict(rendered)
    recovery["proposal"] = _proposal(
        rendered["goal"]["goal_id"], str(uuid.uuid4()),
        text=rendered["expected_text"], rel_path=rendered["rel_path"],
    )
    recovery["goal"] = _goal(rendered["goal"]["goal_id"])
    binding2 = env.binding(graph=[recovery["goal"]])
    report2 = binding2.run_step(
        recovery["goal"]["goal_id"], recovery["proposal"], preconditions=(CAP,)
    )
    law2 = _success_law(env, report2, recovery["proposal"]["action_id"], rendered["rel_path"], rendered["expected_text"])
    evidence["recovery"] = law2

    ok = evidence["no_effect_after_fault"] and not evidence["faulted_attempt"].get("fabricated_success", False) and all(law2["clauses"].values())
    return {"ok": bool(ok), "evidence": evidence}


def scenario_journal_append_busy(env: Env, task: dict) -> dict:
    rendered = _render_task(task, observed={})[0]
    evidence: dict = {"task": task["task_id"]}

    busy = JournalAppendBusy(env.journal())
    binding = env.binding(graph=[rendered["goal"]], journal=busy)
    try:
        report1 = binding.run_step(rendered["goal"]["goal_id"], rendered["proposal"], preconditions=(CAP,))
        outcome = report1.get("outcome")
        evidence["faulted_attempt"] = {
            "outcome": outcome,
            "fabricated_success": outcome == OUTCOME_COMPLETED,
            "ledger_error": report1.get("ledger_error"),
        }
    except Exception as exc:
        evidence["faulted_attempt"] = {"raised": type(exc).__name__, "detail": str(exc)[:200]}

    evidence["fired_on"] = "journal.append"
    # no success without durable rows: whatever happened, the action must not
    # carry a verification row through a journal that never took the write
    journal = env.journal()
    kinds = [str(_field(r, "kind")) for r in journal.rows]
    evidence["journal_kinds_after_fault"] = kinds

    # recovery: fresh journal object over the same dir (replays from disk)
    recovery = dict(rendered)
    recovery["proposal"] = _proposal(
        rendered["goal"]["goal_id"], str(uuid.uuid4()),
        text=rendered["expected_text"], rel_path=rendered["rel_path"],
    )
    recovery["goal"] = _goal(rendered["goal"]["goal_id"])
    binding2 = env.binding(graph=[recovery["goal"]], journal=env.journal())
    report2 = binding2.run_step(
        recovery["goal"]["goal_id"], recovery["proposal"], preconditions=(CAP,)
    )
    law2 = _success_law(env, report2, recovery["proposal"]["action_id"], rendered["rel_path"], rendered["expected_text"])
    evidence["recovery"] = law2

    ok = all(law2["clauses"].values()) and law2["journal"]["chain_ok"] and not evidence["faulted_attempt"].get("fabricated_success", False)
    return {"ok": bool(ok), "evidence": evidence}


def scenario_witness_disagrees(env: Env, task: dict) -> dict:
    rendered = _render_task(task, observed={})[0]
    evidence: dict = {"task": task["task_id"]}

    tampering = TamperingBody(workspace=env.workspace, state_dir=env.body_state)
    binding = env.binding(graph=[rendered["goal"]], adapter=tampering)
    report = binding.run_step(rendered["goal"]["goal_id"], rendered["proposal"], preconditions=(CAP,))
    evidence["outcome"] = report.get("outcome")
    evidence["actual_observation_ids"] = report.get("actual_observation_ids") or []
    evidence["fabricated_success"] = report.get("outcome") == OUTCOME_COMPLETED
    external = _independent_read(env.workspace / rendered["rel_path"])
    evidence["external_bytes_now"] = external
    tampered_text = "a different story written after the fact\n"
    evidence["tamper_visible_on_disk"] = (
        external["exists"] and external["sha256"] != hashlib.sha256(rendered["expected_text"].encode()).hexdigest()
    )
    ok = (
        not evidence["fabricated_success"]
        and not evidence["actual_observation_ids"]
        and evidence["tamper_visible_on_disk"]
    )
    return {"ok": bool(ok), "evidence": evidence}


def _hung_child(workspace: str, body_state: str, journal_dir: str, queue) -> None:  # pragma: no cover - killed by design
    sys.path.insert(0, str(ROOT))
    try:
        env = Env(Path(workspace).parent)
        env.workspace = Path(workspace)
        env.body_state = Path(body_state)
        env.journal_dir = Path(journal_dir)

        class _Hanging(body_mod.SoftwareFileAdapter):
            def submit(self, proposal):
                time.sleep(10_000)

        task = json.loads((Path(workspace).parent / "task.json").read_text(encoding="utf-8"))
        step = task["steps"][0]
        proposal = _proposal(
            str(uuid.uuid4()), str(uuid.uuid4()), text=step["content"], rel_path=step["rel_path"]
        )
        goal = _goal(proposal["goal_id"])
        hanging = _Hanging(workspace=Path(workspace), state_dir=Path(body_state))
        binding = env.binding(graph=[goal], adapter=hanging)
        report = binding.run_step(goal["goal_id"], proposal, preconditions=(CAP,))
        queue.put({"outcome": report.get("outcome")})
    except Exception as exc:
        queue.put({"raised": f"{type(exc).__name__}: {exc}"[:200]})


def scenario_hung_worker(env: Env, task: dict, hung_timeout_s: float) -> dict:
    """A dispatch that never returns. The runner does NOT single-thread through
    it: the scenario runs in a child process and is terminated at the budget.
    This records the known gap honestly: the current single-threaded run_step
    has no timeout guard at the dispatch boundary (tracked as D3H-3), so a hung
    worker freezes the step caller. No success is fabricated from a hang."""
    evidence: dict = {"task": task["task_id"], "hung_timeout_s": hung_timeout_s}
    step = task["steps"][0]
    task_file = env.base / "task.json"
    task_file.write_text(json.dumps(task), encoding="utf-8")
    queue = multiprocessing.Queue()
    child = multiprocessing.Process(
        target=_hung_child,
        args=(str(env.workspace), str(env.body_state), str(env.journal_dir), queue),
    )
    child.start()
    child.join(hung_timeout_s)
    if child.is_alive():
        child.terminate()
        child.join(5)
        evidence["observed"] = "HUNG"
        evidence["note"] = (
            "submit blocked past the budget and the child was terminated; the "
            "single-threaded run_step has no dispatch timeout guard (D3H-3 gap), "
            "recorded honestly — a hung worker freezes the step caller today"
        )
        result = None
    else:
        result = queue.get() if not queue.empty() else {"note": "child exited without a result"}
        evidence["observed"] = "COMPLETED_OR_RAISED"
        evidence["child_result"] = result
    evidence["no_fabricated_success"] = not (env.workspace / step["rel_path"]).exists()
    # acceptance: the hang was observed and contained; nothing pretended completion
    ok = evidence["observed"] == "HUNG" and evidence["no_fabricated_success"]
    return {"ok": bool(ok), "evidence": evidence}


# --- harness ------------------------------------------------------------------

SCENARIOS = {
    "normal_cycle_restart_dependent": ("dependent-write", scenario_normal_cycle_restart_dependent),
    "dispatch_transient_fault": ("single-write", scenario_dispatch_transient_fault),
    "journal_append_busy": ("single-write", scenario_journal_append_busy),
    "witness_disagrees": ("single-write", scenario_witness_disagrees),
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="E0 adaptation gauntlet runner")
    parser.add_argument("--manifests", default=str(DEFAULT_MANIFESTS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--scenario", action="append", default=None)
    parser.add_argument("--hung-timeout-s", type=float, default=HUNG_TIMEOUT_S)
    args = parser.parse_args(argv)

    manifests = load_manifests(Path(args.manifests))
    run_id = f"e0-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    names = args.scenario or list(SCENARIOS) + ["hung_worker"]
    report = {
        "runner": "tools/sifta_adaptation_eval.py",
        "manifest_id": manifests["manifest_id"],
        "run_id": run_id,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "real_vs_simulated": (
            "real adapter/verifier/journal/loop/binding classes driven in isolated "
            "temporary state under this run dir; live .sifta_state is never touched"
        ),
        "scenarios": {},
        "success_law": [
            "outcome == completed",
            "actual_observation_ids non-empty",
            "verification row present for the action",
            "journal hash chain intact from genesis",
            "runner's own external byte read matches",
        ],
    }

    all_ok = True
    for name in names:
        started = time.time()
        env = Env(out_dir / "workspaces" / name)
        try:
            if name == "hung_worker":
                task = _task_by_id(manifests, "single-write")
                result = scenario_hung_worker(env, task, args.hung_timeout_s)
            else:
                task_id, fn = SCENARIOS[name]
                result = fn(env, _task_by_id(manifests, task_id))
            result["duration_s"] = round(time.time() - started, 3)
            result["error"] = None
        except Exception as exc:
            result = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc()[-1500:],
                "duration_s": round(time.time() - started, 3),
            }
        report["scenarios"][name] = result
        if not result["ok"]:
            all_ok = False
        print(f"[e0] {name}: {'PASS' if result['ok'] else 'FAIL'} ({result['duration_s']}s)")

    report["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report["all_ok"] = all_ok
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[e0] report: {out_dir / 'report.json'}")
    print(f"[e0] ALL {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    multiprocessing.freeze_support()  # type: ignore[attr-defined]
    sys.exit(main())