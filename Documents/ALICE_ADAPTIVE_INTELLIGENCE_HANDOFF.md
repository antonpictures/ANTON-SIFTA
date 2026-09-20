# Alice: implementation handoff for DeepSeek and GLM

Status: implementation proposal / `HYPOTHESIS`. Procedural extension of
[the canonical covenant](IDE_BOOT_COVENANT.md), not new organism law.
Prepared from local source inspection on 2026-09-20; clock source: local OS UTC.
Scope: a general adaptive loop spanning software, a rover body, and shared swarm experience.

## 1. The decision and the target

**Build one Alice with replaceable environment adapters and a closed learning loop.**
The Dell starts as a **headless rover organ**: local ROS 2/Nav2/SLAM, hardware discovery,
durable mission journal, telemetry, and offline reflexes. Alice's existing Mac runtime
holds the shared conversation, task planning, and consolidated experience. The Dell can
later host inference if its measured resources justify it. A full Qt desktop is not a
prerequisite for controlling the rover.

This is the recommended implementation decision; David's hardware/OS/firmware readiness
and agreement to the contract remain unverified. Code the simulator and SIFTA half now.

George's desired behavior becomes an engineering target: **boot on supported unfamiliar
hardware, discover available actions, complete unfamiliar tasks, recover from faults,
and improve subsequent attempts from verified experience.** No architecture guarantees
AGI or survival in every possible environment. Measure the supported envelope and expand
it. A rover demonstration alone establishes only rover capabilities. Generality needs
transfer across substantially different tasks, with learning measured independently of
the underlying model's existing knowledge.

“Survive” means preserve memory, manage measured power/thermal/storage limits, restore
service after interruption, and keep a physical body within its tested operating envelope.
Recovery respects owner shutdown and installation choices. Docking is a capability only
when actual charging hardware and localization support it.

## 2. What the code actually provides

These are source observations, not claims of a live hardware demonstration:

| Existing path | Observation and implementation consequence |
| --- | --- |
| `System/stigmerobotics_rvr1.py`, `System/stigmerobotics_remote_link.py`, `scripts/david_rover_gateway.py` | RVR1 client, remote queue, pairing/control lifecycle, bounded velocity commands, local monitoring already exist. Extend them; the pasted “nothing on our side” is stale. |
| `tests/test_stigmerobotics_rvr1.py`, `tests/test_remote_rover_link.py`, `tests/test_david_rover_gateway.py` | Existing protocol/fault tests are the regression baseline. Their presence does not establish physical motion. |
| `System/sifta_hardware_profile_planner.py`, `System/swarm_boot_census.py` | Hardware role planning and body census exist; extend discovery into a usable capability snapshot. |
| `System/swarm_body_brain_loop.py:SwarmPhysiology.body_brain_tick` | Existing physiology integration point. Keep one action coordinator; do not introduce another competing global loop. |
| `System/swarm_capability_registry.py`, `System/swarm_canonical_organ_registry.py`, `System/swarm_tool_router.py` | Capability descriptions, organ map and tool execution exist. Describe new adapters here and retain the real effector receipt path. |
| `System/swarm_pfc_basal_ganglia_arbiter.py`, `System/swarm_active_inference_world_model.py` | Action ranking and a tabular prediction model exist and have some wiring. Trace the complete live action-to-outcome path before declaring it closed. |
| `System/swarm_latent_world_model.py` | `encode_state` uses SHA-256; transitions are a lookup table. It needs a representation that shares information between related states to support unseen-state transfer. |
| `System/swarm_lived_experience_bridge.py`, `System/swarm_strategy_failure_revision.py`, `System/swarm_agi_frontier_loop.py` | Continuity, revision, and frontier tracking exist. Verify actual behavior after a revision rather than counting revision rows as success. |
| `System/swarm_spinal_cord.py`, `System/swarm_self_improvement_loop.py` | Existing repair path and measured keep/revert hooks. The current spinal code dispatches to a configurable local cortex; `dispatch_to_mimo` is a compatibility wrapper. Respect source reality. |
| `System/swarm_agi_confirmation_gauntlet.py`, `System/swarm_federation_summary.py` | Extend evaluation and exchange primitives rather than creating competing scoreboards or identity systems. |
| `System/swarm_whatsapp_receptor.py:build_inbox_row` | Sets `direction="incoming"` even when `from_me=True`; validation also expects incoming. Fix producer AND consumer compatibility. |

At inspection, unrelated working changes existed in `Network/whatsapp_bridge/bridge.js`,
`System/whatsapp_bridge_autopilot.py`, `Vendor/alice-cli`, and
`data/eval/marketing_commercial_inventory.json`. Recheck before editing.

Baseline verification: `python3 -m pytest -q tests/test_stigmerobotics_rvr1.py
tests/test_remote_rover_link.py tests/test_david_rover_gateway.py` completed with
**34 passed**. This verifies the existing offline test suite, not a ROS/Dell or
physical rover run. This handoff adds documentation; the proposed jobs remain open.

## 3. The single adaptive loop

```text
boot / recover -> probe hardware and services -> publish capabilities
    -> observe with source + freshness -> update beliefs and uncertainty
    -> choose goal/subgoal -> predict candidate outcomes and resource costs
    -> execute through one adapter -> verify the postcondition externally
    -> record the transition -> update skill/model -> measure later improvement
                           ^                         |
                           +---- revise / recover ---+
```

Integrate a bounded, nonblocking step into the existing physiology. ROS callbacks,
motor watchdogs, sensor freshness and stop handling stay local and independent of model
latency. Slow inference runs as a resumable job; each tick polls results and remains
responsive. Persist every action before dispatch; reconcile ambiguous outcomes on restart.

Freeze the following typed records in **one** proposed module,
`System/swarm_adaptive_contracts.py`, before integration. Use immutable IDs, explicit
schema versions and strict validation; existing compatible records get adapters.

| Record | Required content |
| --- | --- |
| `CapabilitySnapshot` | body/node/boot IDs; topology revision; hardware and OS facts; available actions with input/output schemas; preconditions; sensor coverage and freshness; resource estimates with units; observation evidence; unavailable capabilities with reasons |
| `Observation` | event/source/boot IDs; sequence; source time and clock domain; local receive time; modality; frame where relevant; values and uncertainty; live/remembered/inferred/simulated status; evidence reference |
| `BeliefState` | revision; entities and relations; pose/map when available; uncertain hypotheses; supporting observations; expired/conflicting evidence; resource state. Unknown is distinct from zero/false. |
| `Goal` | ID; owner/task provenance; desired observable predicate; budget/deadline; dependency IDs; active subgoal; progress/failure condition; checkpoint; revision history |
| `ActionProposal` | action ID; goal ID; adapter + capability revision; typed arguments; required observations; predicted postcondition, uncertainty and cost; cancellation/recovery behavior |
| `ActionResult` | action ID; accepted/running/succeeded/failed/cancelled/unknown; actual observations; verifier result; cost; error; effect receipt. Acceptance never means success. |
| `Experience` | transition ID; environment/body/task family; before-state; action; predicted outcome; observed after-state; independent verification; prediction error; actual cost; provenance and model/skill versions |

Adapter interface: `probe()`, `observe(cursor)`, `submit(action)`, `status(action_id)`,
`cancel(action_id)`, `recover(checkpoint)`. A physical adapter additionally exposes
priority `stop()`. Unknown capabilities produce a diagnostic and a discovery/replan
step. New tools are learned from their descriptions and schemas, then checked against
their observed effects. Free text from messages/websites is observation data; task
authority continues to come from the existing owner/task provenance.

Use the existing ledger ecology and shared conversation. A durable local outbox/WAL
may support transport and replay; it is a replica of relevant events, not another chat
or identity. Store large sensor data once and reference it by content hash. Dedupe
learning by transition ID, including four-ledger copies of the same event. Checkpoint
with atomic replacement; retain append-only source history.

## 4. Ordered coding jobs

Each row is an independently reviewable change. DeepSeek owns runtime behavior;
GLM owns the named adapter/evaluation surfaces. One writer per file. The runtime owner
also writes focused unit tests; GLM supplies independent behavioral/fault evaluation.
File names marked “new” are proposed: search for an existing equivalent first.

| ID / owner | Deliverable and existing integration | Acceptance evidence |
| --- | --- | --- |
| **C0 / DeepSeek** | Implement the shared typed records above and rover v1 contract in the linked document. Add schema fixtures; preserve legacy RVR1 velocity API separately. | Invalid units/types, nonfinite numbers, unsupported versions, stale capability references and malformed commands fail visibly. Both coders consume the same schema hash. |
| **E0 / GLM** | Extend `swarm_agi_confirmation_gauntlet.py` with an executable scenario runner and baseline capture. Use `tools/sifta_adaptation_eval.py` (new thin CLI) if useful. | Run a real adapter against a temporary software environment; observer checks filesystem/output effects independently. Merely inserting success rows cannot pass. |
| **D1 / DeepSeek** | Extend hardware planner/census and capability registry with boot/topology IDs, freshness, resource probes, headless support and capability loss/recovery. Keep Qt/macOS imports out of portable core import paths. | Boot fixtures for Mac, Linux Dell and no-network/no-model; real Linux smoke run before claiming Linux operational. Lost sensor or tool is reflected in the next relevant planning step. |
| **G1 / GLM** | Extend existing remote link/gateway and add a Dell ROS adapter using the rover contract. Build fake ROS and kinematic simulators before hardware. Register its tools/organ via a handoff to DeepSeek, the shared registry writer. | Pose intent produces feedback and independently verified result; duplicate, stale, reordered packets and restart preserve command identity. Changing simulated Ackermann to differential needs no SIFTA planning-code edit. |
| **D2 / DeepSeek** | Extend the lived-experience bridge into a queryable belief snapshot. Track object/tool identity, relational features, evidence age, uncertainty and conflicts. | Replayed/stale telemetry cannot freshen an observation; contradictory observations remain visible; missing pose is not `(0,0)`; a moved object invalidates the old target. |
| **D3 / DeepSeek** | Close the loop through physiology, arbiter, tool router and strategy revision. Persist goal DAG, step state, pending action, verifier and recovery choice. Use existing strategy events as the journal. | Kill between dispatch and receipt: restart reconciles the action before retry. Goal completion requires observed postconditions; timeout produces revision or a precise blocked result. Owner stop interrupts pending work. |
| **D4 / DeepSeek** | Extend world-model APIs with typed/relational features and an uncertainty-bearing predictor; retain tabular lookup as baseline. Learn transition/cost/success estimates across related contexts. Hashes identify records, not semantic similarity. | Held-out map/tool configurations improve prediction and task success over lookup/no-learning baselines. Report calibration and performance after distribution shift. If simple features fail, test a learned encoder separately. |
| **G2 / GLM** | Extend skill library/replay/consolidation with parameterized procedures: initiation predicates, bound arguments, steps, termination predicate, recovery and supporting episodes. | A learned skill succeeds with new object IDs/paths/layouts; a disconfirming episode lowers confidence; raw receipt repetition cannot manufacture competence. |
| **D5 / DeepSeek** | Extend metabolic homeostasis and boot recovery to use real watts/battery/temperature/free space, optional inference cost, and checkpoint state. Schedule bounded work from these measurements. | Simulated low power, disk full and model/network loss cause graceful checkpoint/degradation; reboot resumes coherent work. Missing energy telemetry is unknown, never invented. |
| **G3 / GLM** | Extend existing federation with scoped experience/skill summaries, provenance verification, dedupe and partition/rejoin replay. A Dell organ shares only mission-relevant state; other owners' nodes keep their own identities. | Receive twice, disconnect, reconnect, revoke credentials, replay an old boot. One logical experience is learned once; conflicting receipts survive as conflicts; no raw contact/chat/key copying. |
| **D6 / DeepSeek** | Harden the existing spinal path for reproducible improvement: candidate artifact, isolated checkout, baseline plus held-out behavior, incumbent comparison, atomic promotion and rollback. Use configured DeepSeek/GLM arms through this existing path for future self-repair. | Inject a software fault; propose repair; demonstrate a behavioral gain; reject a patch that rewrites the evaluator or loses old skills; interrupted promotion recovers the prior working version. |
| **G4 / GLM** | Run transfer, ablation, interruption and endurance evaluations; repair evidence interpretation in the existing frontier/gauntlet. | Report successes/failures by domain, recovery, retention, resource use and confidence intervals. A row count or model's self-rating cannot mark AGI confirmed. |
| **W1 / GLM, separate patch** | Fix WhatsApp echo direction with versioned producer/validator/consumer support; exercise the read view. Trace consent ledger to the existing autonomous-reply path. Coordinate around the currently modified bridge files. | Outgoing echo displays once and never starts a reply loop; distinguish owner-phone sends from Alice effector sends; direct/group policy and consent expiry/revocation pass fixture tests. Live messages require the existing user authorization. |

Order: **C0 + E0**, then **D1 + G1**, then **D2 → D3**, then **D4 + G2**,
then **D5 + G3**, then **D6 + G4**. GLM can build simulator/evaluation fixtures while
DeepSeek closes the loop. W1 is small and separate; group posts and YouTube replies
do not block the intelligence work. Reach a working vertical slice after D3, before
adding every later feature.

## 5. Learning that can actually transfer

Implement cheap mechanisms first: retrieval of relevant experience, parameterized skills,
model-based prediction, and failure-driven replanning. Keep the underlying model fixed
for the first evaluation so gains can be attributed to the organism's learning.

Represent useful relations: an object occupies a region; a capability requires a sensor;
a file transformation requires a format; a route consumes energy. Share planning and
verification abstractions across domains while retaining body-specific dynamics and
units. Similar words do not prove equivalent actions.

For active learning, pick an uncertain capability whose resolution helps the current
goal. Predict the probe outcome first, perform it, record its cost, compare the result,
then update the belief/model. Use controlled interventions in simulation/software to
separate causes from correlation. Reward verified goal progress, resource efficiency,
recovery and later transfer; record these separately before combining them for selection.
Receipt volume, eloquent narration and the planner's own grade are not rewards.

Only add adapter/weight training after a learning curve shows a gap that retrieval and
skills fail to close. Version training data, freeze evaluator manifests and retain a
previous working model. Evaluate retention on old tasks as well as gain on new ones.
Architecture is the experiment infrastructure; unseen-task competence remains an empirical
result, not a consequence of module names.

## 6. Verification programme and completion rules

Use three distinct families: **software tool workflows**, **rover navigation/body changes**,
and **multi-node resource/service recovery**. Development tasks and held-out tasks must
differ in configurations and task compositions, not only random IDs. GLM controls the
held-out manifest; the planner gets task inputs and observations, not solutions or grades.

For the first useful build, set these **proposed engineering thresholds** before comparing
candidates. They are project release criteria, not a definition or certificate of AGI:

- At least 30 held-out episodes per family; publish exact successes/attempts and Wilson
  95% intervals. Aim for at least 80% success per family within declared budgets.
- Compare frozen no-learning baseline, memory-only baseline, and full adaptive loop with
  matched model, tools and budgets. Require a positive paired improvement whose bootstrap
  95% interval excludes zero; if sample size is inconclusive, say so and add trials.
- Five unseen tasks per family are repeated with learning; record attempts-to-success
  and verified change in later behavior. Check old tasks for retention (target no more
  than 5 percentage points regression, with uncertainty reported).
- Fault suite: loss of network/model/sensor, stale/reordered/duplicated event, reboot,
  changed chassis, full disk, corrupt checkpoint, conflicting peer evidence and lost
  acknowledgment. Test all; publish unresolved outcomes rather than silently dropping them.
- One 24-hour simulator/software soak across interruptions, with stable bounded queues
  and memory, coherent recovery and no duplicate non-idempotent effect. Run an initial
  30-minute soak for fast feedback; it does not substitute for the longer result.
- Physical bench: David supplies firmware/version and hardware receipts, measured stopping
  latency/distance, telemetry freshness, pose accuracy and chassis limits. Then verify
  pose navigation, link loss, stop and obstacle handling under supervision. Software
  simulation success stays labeled simulation.

First vertical-slice demonstration: unfamiliar simulated map → discover rover capabilities
→ choose a pose goal → execute → introduce an obstacle → replan → verify arrival →
restart → recall the episode → repeat with a changed body profile. Follow with an
unfamiliar software task using the same goal/observation/action/verification machinery.
Cross-body success proves adapter portability; cross-task improvement provides stronger
evidence of generalization. Neither alone establishes unrestricted general intelligence.

## 7. Spend and handoff discipline

No new foundation-model training or model purchases for the first slice. Cache capability
descriptions, use bounded retrieval, and call models for planning/revision only when useful.
Keep deterministic execution, verification and reflexes off the token path. Measure actual
calls/tokens/latency and provider cost when available; mark cost unknown otherwise.

Have each coder implement **one job**, run its meaningful tests, and leave a short handoff.
Do not let both edit shared contracts, registries, physiology or tournament sections at
once. The plan assigns coordination, not separate Alices. Register each coding surface,
use four-ledger receipts and verify new files through body inventory. Preserve unrelated
working changes. Future autonomous surgery continues through the spinal repair loop.

Return this compact review packet after the first slice and after each later phase:

```json
{
  "job_ids": ["C0", "E0"],
  "revision_or_diff_hash": "...",
  "contract_hash": "...",
  "files_changed": [],
  "commands_and_results": [],
  "scenario_manifest_hash": "...",
  "baseline_and_candidate_metrics": {},
  "one_complete_episode_receipt": "...",
  "failure_and_recovery_receipt": "...",
  "four_ledger_receipt_id": "...",
  "still_unverified": [],
  "next_job": "D1/G1"
}
```

**DeepSeek prompt:** “Implement your next dependency-ready job in
`Documents/ALICE_ADAPTIVE_INTELLIGENCE_HANDOFF.md`. Read the covenant and current code;
extend the existing organs; consume the frozen contracts; produce behavioral tests,
inventory visibility, four-ledger receipt and the review packet. Coordinate shared-file
ownership with GLM. Treat proposed capabilities as unverified until exercised.”

**GLM prompt:** “Implement your next dependency-ready job in
`Documents/ALICE_ADAPTIVE_INTELLIGENCE_HANDOFF.md`. Own independent outcome verification,
fault simulation and your listed integration surfaces. Preserve the shared schema and
existing RVR1 behavior; record failures honestly; return the review packet. Start E0 while
DeepSeek builds C0, then G1 after the schema freezes.”

## 8. Sources and companion contract

The project-specific architecture above is a proposal inferred from local source.
Separating breadth, performance and autonomy in evaluation is consistent with
[Levels of AGI](https://arxiv.org/abs/2311.02462); the paper is not evidence that this
implementation attains AGI. ROS details and the implementable rover boundary are in
[ALICE_ROVER_INTENT_CONTRACT_V1.md](ALICE_ROVER_INTENT_CONTRACT_V1.md).
