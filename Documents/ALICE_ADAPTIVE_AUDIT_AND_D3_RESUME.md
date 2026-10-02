# Adaptive build: audit and concrete continuation

**Current status (2026-09-21):** D3 and R1–R3 have since been implemented; the
September 20 absence/repair assignments below are historical. The D3f tool path
exists, but live runtime integration remains incomplete. Follow
[the current WCT queue](WCT_ADAPTIVE_RUNTIME_AND_LOCAL_DECISIONS_2026-09-21.md),
including this review's local dispatch repairs and **361 passing tests**.

Status: observed review at HEAD `49f21d05c`, 2026-09-20; local OS clock.
This updates [the original handoff](ALICE_ADAPTIVE_INTELLIGENCE_HANDOFF.md), under
[the canonical covenant](IDE_BOOT_COVENANT.md). Runtime repairs below are assigned work,
not changes implemented by this review. Earlier completion reports remain historical.

## Verified state

| Work | Disk evidence | Status |
| --- | --- | --- |
| C0 | `fb3a9869c`; adaptive contracts, fixtures, tests, C0 handoff | Implemented; semantic limits below |
| D1 | `6afb85d96`; boot identity, census and capability summary integration | Implemented; R1 required; real Linux/sensor smoke open |
| D2 | `49f21d05c`; belief APIs and tests | Implemented; R2/R3 required; live ingestion/integration still open |
| D3 | `System/swarm_adaptive_goal_loop.py` and `tests/test_swarm_adaptive_goal_loop.py` absent | Not implemented |
| E0 | Proposed `tools/sifta_adaptation_eval.py` absent | Independent scenario-runner completion unverified; GLM must establish it |
| D4–D6, G1–G4, W1 | No completion established by this review | Keep the original jobs open; existing rover gateway remains the baseline |

Verified commands:

```text
python3 -m pytest -q tests/test_swarm_adaptive_contracts.py tests/test_swarm_boot_identity.py tests/test_swarm_lived_experience_belief.py
103 passed in 1.12s

python3 -m pytest -q tests/test_stigmerobotics_rvr1.py tests/test_remote_rover_link.py tests/test_david_rover_gateway.py tests/test_swarm_lived_experience_bridge.py tests/test_swarm_boot_census.py tests/test_swarm_stationary_belief_r1744.py
51 passed in 4.41s
```

The current published schema hash reproduces the C0 handoff:
`sha256:c2b1a7cb8ed76b18837d9ebedb745110ac22e50b466915ed5e364e385096d15f`.
The hash describes `published_schemas()`; it does not attest to all validator or
adapter behavior. Record the implementation revision alongside it.

The pasted output-limit messages establish an interrupted writer, not a completed
module. The scheduler's “armed” state does not prove code exists or work progressed;
its current state was not inspected in this review.

## Repairs before trusting the adaptive loop

All behavioral probes below ran with temporary state directories and no actuation.
They expose gaps not exercised by the 103 passing tests.

### R1 / DeepSeek — fresh health evidence must supersede old recovery (P1)

`System/swarm_boot_identity.py:capability_health` replays the ledger, then uses
`setdefault` for fresh probes. Reproduction:

```text
mark_recovered("camera", now=100)
planning_view([{name:"navigate", preconditions:["camera"]}],
              now=103, readings={camera:False})
Observed: navigate remains available; unavailable=[]
```

Fix evidence precedence by source, capability and freshness: an authoritative current
sensor failure must supersede an older recovery for that sensor. A sensor probe must
not erase an unrelated tool fault. Unknown readings remain distinct from explicit
failure; stale/unknown dependencies need an actionable discovery state. Include boot
identity and age when carrying health forward. Tests: present→failed→recovered, stale
recovery versus fresh failure, unknown reading, unrelated tool fault, and restart.

Integration caveat: `capability_availability_gate` is currently called from
`capability_field_summary`, not the new adaptive planner. D3 must explicitly consume
the corrected planning view before every dependent action; a dashboard count is not
an execution-time check.

### R2 / DeepSeek — observation lifetimes belong to each observation (P1)

`System/swarm_lived_experience_bridge.py:entity_belief` takes the newest row's TTL
and applies it to every earlier row. Reproduction:

```text
old: observed_at=100, ttl_s=1, attributes={colour:"red"}, observation_id="old"
new: observed_at=102, ttl_s=1000, attributes={}, observation_id="new"
query at 103 -> support=["old","new"], colour still taken from "old"
```

Expired evidence is revived without a new observation of the attribute. Separately,
`ttl_s=0` becomes the default **900 seconds** through `value or DEFAULT` and is fresh
at time 101 after observation time 100.

Expire each row using its own source timestamp and TTL. Define zero as no reusable
freshness (or reject it explicitly); never replace it with the default. Keep expired
history visible without including it in live support. Test mixed TTLs, zero TTL,
delayed/reordered delivery, duplicate IDs and per-attribute expiry. Extend the source
timestamp/boot provenance when wiring actual telemetry so receipt time cannot renew it.

### R3 / DeepSeek — unknown uncertainty must not become precision (P1 before motion)

`_project_pose` converts absent `uncertainty_m` to `0.0`, then emits x/y variance
`1e-9`. A scratch observation at `(1,2)` with no uncertainty produced that value.
That encodes approximately 0.032 mm standard deviation without a measurement basis.
Measured heading was preserved in the probe; there is no demonstrated heading-loss bug.
However, heading variance is currently derived from position variance when heading exists,
which confuses square metres with square radians.

Carry position and angular uncertainty independently with their evidence. If the frozen
v1 pose cannot honestly express the available measurement, project `pose=null`, preserve
partial coordinates/unknown-status in entity attributes, and exclude that partial pose
from motion/postcondition verification. A documented conservative prior may be introduced
only as inferred uncertainty with provenance, not sensor precision. Coordinate any v1.1
schema extension with GLM. Test unknown position accuracy, unknown heading, and independently
specified angular accuracy. Explicit zero must not mean “sensor did not supply a value.”

### V1 / DeepSeek + GLM — C0 validation is not outcome verification (P2)

Two record probes were accepted by `ActionResult.from_dict`:

- `status="unknown"`, `verifier_result=null`, `error=null` (the C0 handoff says this
  requires `OUTCOME_UNKNOWN`, but the record cross-check does not enforce it).
- `status="succeeded"`, `verified=true`, nonempty `actual_observation_ids`, but an
  empty `verifier_result.observation_ids` list.

Retain frozen v1 compatibility while D3 adds its own outcome verifier: resolve evidence
IDs to actual records, check goal/action/body/frame/time association and freshness,
evaluate the observable predicate, and require the verifier's evidence to support the
claimed result. Unknown outcomes receive `OUTCOME_UNKNOWN` with a precise detail.
Do not promote a result because an adapter supplies `verified=true`. A coordinated
contract revision can strengthen cross-checks; never silently change a frozen contract
while the other coder implements it. Add wrong-ID, stale-evidence and forged-success tests.

## D3: six small writes, each leaving usable files

No further full contract reread is needed: frozen example records already exist in
`data/contracts/goal.v1.json`, `action_proposal.v1.json`, `action_result.v1.json`.
Tests can load and deep-copy those, then explicitly change IDs and timestamps. Nullable
fields remain present. Persist C0 records inside a separately versioned journal envelope;
runtime state such as `BLOCKED` is not an invented C0 wire status.

Keep each edit to a modest patch, roughly 80–150 added lines. After a tool write, inspect
the file and compile the changed module. These are practical batching targets, not known
provider token limits. Put progress and exact next action in the handoff after each slice.
Finish with a short result, not another large planned file printed into chat.

| Slice | Implement now | Required check before the next slice |
| --- | --- | --- |
| **D3a** | Create `swarm_adaptive_goal_loop.py` with injected adapter, verifier, clock and state directory; validate Goal/ActionProposal inputs; create journal envelope/version and goal DAG state. | Module exists and imports; reject missing dependency and dependency cycles; tests use temporary state. |
| **D3b** | Durable action journal/outbox: write and flush/fsync dispatch intent before `submit`; single-writer/process ownership; persist action ID, capability revision and uncertain outcome. | Kill/fault before journal commit sends nothing; failure after submit never triggers blind resend. Test truncated final write and disk errors explicitly. |
| **D3c** | `recover`/`status` reconciliation for every pending action before any new dispatch; stable action IDs; checkpoint replay. | Kill between submit and receipt, restart, resolve one outcome without a second non-idempotent effect. If remote status is unknown, retain unknown and stop/block precisely. |
| **D3d** | Independent observable-postcondition verifier (V1), C0 ActionResult persistence, goal-step advancement and strategy events. | Acceptance alone cannot complete; stale/wrong/absent evidence cannot complete; a real verified software effect completes once. |
| **D3e** | Deadlines/budgets, timeout→bounded revision or precise blocked state; owner stop immediately calls local stop/cancel without probe, inference or network discovery. | Hung/raising probe cannot delay stop; stop path remains available on journal failure; restart does not reset deadline; exhausted revisions stop retrying. Cancellation acknowledgment alone is not physical-rest proof. |
| **D3e — DONE** | `GoalLoop.owner_stop` / `deadline_status` / `revise` / `require_attemptable` / `blocked_state` / `revision_count` in `System/swarm_adaptive_goal_loop.py` (`sha256:e8816a1a8cf1e360f1906df07922ae1f28219f395ea93275f6209b420cd9edd4`); additive `stop`/`revision` kinds in `System/swarm_action_journal.py` (`sha256:3687bfe5f6a5b5a4d4249d4bfeb48441b1ad7e90050a4d2051b811ac3528583a`). Commit `235383d1d`. | `tests/test_swarm_action_stop_and_deadline.py` → **33 passed**; 8-file regression → **245 passed**, exit 0. Independent: a body whose `probe`/`observe`/`status`/`recover` all raise is stopped with `calls_during_stop == ["cancel"]` and `probe_called: false`; a fresh interpreter on the same journal inherits `revision_count == 2` and `BUDGET_EXHAUSTED` from disk. **Gap:** `cancel` itself is unbounded — a `cancel` that never returns still blocks the stop; no timeout seam exists yet (the report stays truthful as `unknown` in that case). |
| **D3f** | Wire bounded nonblocking steps into existing physiology/arbiter/tool routing and strategy revision, using corrected D1/D2; register/inventory visibility and full receipt packet. | One real invocation path reaches the loop; failure, recovery and completion reach shared ledgers; no duplicate global coordinator. A standalone class test does not close D3. |
| **D3f — tool path implemented; runtime closure open** | `System/swarm_adaptive_step_binding.py` (`sha256:b4cff16264ffd37454c7d4b6051b198694b0137d3b88721a401195406a683050`): `planning_gate()` consumes the corrected D1/R1 view *now* on every call; `AdaptiveStepBinding.run_step()` runs gate → propose → submit → bounded poll → `confirm`; `request_stop()` issues the stop immediately, not at the next boundary. Registered as `adaptive_goal_step` in `System/swarm_tool_router.py` (**additive only: 131 insertions, 0 deletions**) — the one real invocation path, no second coordinator and no second goal store. Commit `6f2b939c0`. | `tests/test_swarm_adaptive_step_binding.py` → **23 passed**; 9-file regression → **277 passed**, exit 0. Independent, through the tool router itself: a live organ yields `outcome: "completed"` with `actual_observation_ids: ["obs-1"]` and journal kinds `intent, submit, status, result, verification, result, completion` with an intact hash chain, and `adaptive_step_completed` lands in `lived_experience_events.jsonl`; the same path on an undeclared precondition yields `outcome: "blocked"`, `reason_code: "UNSUPPORTED"`, `discovery_required[0].state: "unreported"`, **no journal file at all** (nothing was submitted) and a body that raises if touched was never touched. **Gaps:** (1) the poll bound covers the wait schedule, not a single adapter call that never returns; (2) the gate's evidence comes from real `run_probes`, so the tool exposes no readings override — deliberate, since such a seam would let a caller report health it does not have; (3) no physiology/arbiter organ registers itself yet, so `register_adaptive_body()` currently has no live caller. |

Preserve the original four acceptance behaviors: crash reconciliation, observed completion,
timeout revision/blocking, and owner stop. Add an independent GLM integration test for
each. Slow adapter work runs outside the physiology/stop path; every poll is bounded.
At most one movement owner per body. Physical watchdogs stay local.

DeepSeek sequence: **R1 → R2 → R3 → D3a–f (including V1) → D4 → D5 → D6**.
GLM sequence: **E0 and regression cases now; G1 against the frozen contract; then G2/G3/G4**
at the original dependency points. Keep W1 separate. The 24-hour soak and real Dell run
remain completion criteria, not reasons to delay the next small software patch.

Resume instruction to paste:

> Read `Documents/ALICE_ADAPTIVE_AUDIT_AND_D3_RESUME.md`. Confirm current HEAD and peer
> ownership. Implement the next unfinished repair/slice, writing the first small patch
> before any repeated full-file reconnaissance. Run its focused behavioral tests, update
> the saved progress and four-ledger receipt, then continue through dependency-ready slices.
> Keep tests in temporary state. Do not mark D3 complete until D3f integration is exercised.
> Preserve unrelated edits and frozen-contract compatibility; report exact remaining work.

## Remaining items from the pasted report

- **Full-suite failures:** not certified green. A direct hash check confirms
  `Kernel/inference_economy.py` differs from `Kernel/integrity_manifest.json`:
  expected `513dbf6c…`, actual `28f9a5dd…`. Source last changed in `c3b2f01f9`,
  manifest in `3af924ce9`. Review the intended source changes and normal integrity
  maintenance procedure as a separate job. Do not mask the failure or regenerate the
  trust baseline merely to make tests green. This does not block isolated D3 tests.
- **Grounding-window failure:** reported in D1's handoff, not reproduced this review.
  GLM should run that one named test with a bounded timeout and captured output, then
  fix prompt-budget retention using its actual failure. Avoid recollecting the entire
  suite for a narrow job; use explicit test paths and keep exit codes/JUnit results.
- **Fixture pollution:** `tests/test_r1016_effector_gate_and_improve_loop.py` explicitly
  points `_repo_root` at the live checkout and appends `# r1016 dry-run receipt line`.
  That is an observed pollution path and a plausible source of the current duplicate,
  not proof of which process wrote this occurrence. GLM should copy the fixture into
  `tmp_path` and route test mutation there. Preserve the existing unrelated diff.
- **Inventory decision:** retain a bounded prompt sample; add targeted path lookup and
  paginated/deterministic inventory traversal with explicit truncation/count metadata.
  Register new module paths directly. Current `sorted(rglob(...))[:200]` per directory
  followed by `out[:50]` is a sample, not a completeness proof. This is an engineering
  choice within the requested work, not a reason to wait for another user decision.
- **David's README:** GLM should write a concrete Dell install/diagnostic guide using
  discovered OS/ROS versions and a no-actuation simulator smoke test. Clearly mark any
  untested deployment command. Firmware, sensor and physical stop measurements remain open.
- **Git push and WhatsApp instructions:** pending delivery items, not implied evidence
  of deployment or sending. Prepare the scoped patch/README/message draft; the pasted
  queue is not an instruction to contact David from this audit task.
- **D1/D2 hardware:** fixture success is not live Linux or sensor proof. Preserve this
  distinction in their completion reports. Existing phone/audio/deployment tasks from
  the tournament remain open independently.

Review return packet: job/slice IDs, actual file diff, focused test command and exit code,
independent behavioral evidence, schema + implementation hash, four-ledger receipt,
remaining gaps and the exact next write. No full test-suite run required for each slice.
