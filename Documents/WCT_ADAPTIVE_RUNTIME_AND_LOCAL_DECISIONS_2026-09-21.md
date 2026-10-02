# We code together — runtime closure and local decisions

Current review: 2026-09-21, starting HEAD `e215a78ac`. This supersedes the current-status
claims in the September 20 adaptive audit; the original design and remaining D4–D6,
G1–G4 and W1 jobs remain in scope. Follow the [canonical covenant](IDE_BOOT_COVENANT.md).

## Verdict and code repaired in this pass

The reported C0/D1/D2/R1–R3/D3/V1/D3g commits exist. **The adaptive runtime is not yet
complete.** A registered tool plus tests with an injected body do not establish an
operating physiology/arbiter loop. No production caller of `register_adaptive_body`
was found. `max_polls` bounds scheduled waits, not hung adapter calls. Owner stop is a
binding method, not yet a complete reachable control path for a concurrent live job.

Astra reproduced and repaired three additional execution defects:

1. **Crash replay:** the old code wrote an intent, called `submit`, then recorded that
   submission was attempted. A process dying after the effect but before the second
   write left an “unattempted” intent; restarting submitted it again. A scratch probe
   produced **two effects**. Now the durable intent reserves dispatch before the call;
   a missing acknowledgment means reconciliation. Legacy intent-only rows are treated
   conservatively the same way.
2. **Concurrent journals:** two instances with cached empty tails appended conflicting
   sequence-1 rows. Replay raised `CHAIN_BROKEN`. Now claims and appends use a shared OS
   file lock, refresh the tail before writing, and report contention as `JOURNAL_BUSY`.
   No adapter call holds that lock. Reusing a claimed ID with changed proposal content
   returns `ID_CONFLICT`. Unrepaired torn tails cannot be extended silently.
3. **Admission bypass:** an expired goal sent through `AdaptiveStepBinding.run_step`
   still reached the adapter. `GoalLoop.submit` now checks the existing deadline/budget
   policy itself. An already recorded owner stop also prevents subsequent dispatch,
   including after restart.

Changed runtime: `System/swarm_action_journal.py`, `System/swarm_adaptive_goal_loop.py`.
Regression coverage: `tests/test_swarm_action_journal.py`. These are local working-tree
changes from this pass, not a new claimed commit. No foundation-model change was made.

Verification: **361 passed in 4.11s**, covering these explicit test files:

```text
tests/test_swarm_action_journal.py
tests/test_swarm_action_reconciliation.py
tests/test_swarm_action_stop_and_deadline.py
tests/test_swarm_adaptive_contracts.py
tests/test_swarm_adaptive_goal_loop.py
tests/test_swarm_adaptive_step_binding.py
tests/test_swarm_boot_identity.py
tests/test_swarm_lived_experience_belief.py
tests/test_swarm_model_body_self_knowledge.py
tests/test_swarm_outcome_verifier.py
tests/test_swarm_verifier_completion.py
tests/test_stigmerobotics_rvr1.py
tests/test_remote_rover_link.py
tests/test_david_rover_gateway.py
```

The new tests include actual `os._exit` after an effect, two independent competing
processes, stale journal instances, changed action content, fsync failure, torn tail,
expired goal, and stop-before-dispatch followed by restart. All use temporary state.
The OS lock implementation targets the current Mac/Linux bodies; unsupported lock
platforms report `LOCK_UNAVAILABLE` rather than pretend to serialize writes.

This does not make arbitrary side effects exactly-once. It prevents a blind resend of
the same journalled action through cooperating callers. A crash before dispatch may
also leave an unresolved reservation; query the adapter or issue a new policy-authorized
attempt after reconciliation. A renamed action ID is a new attempt, not deduplication.
Per-body single ownership, late effects after timeout and stop/dispatch races still need
the runtime work below. Hash chaining alone is not cryptographic authentication.

## Next coding order: close D3 before D4

One writer per surface. DeepSeek owns runtime files; GLM owns independent evaluations,
local scoring and its classifier integration. Each job ends with a small patch, focused
tests and receipts. Work may continue through dependency-ready jobs without another
planning round; do not claim closure based on test counts alone.

| Job / owner | Concrete change | Completion evidence |
| --- | --- | --- |
| **D3H-1 / DeepSeek** | Add one real reversible software adapter and a separately observing verifier. Register them from a real startup path using the canonical package import. Scope file work to the actual task's output directory; persist adapter action identity/status so restart can reconcile. | Ordinary startup, without a test registering a mock, exposes the adapter. An owner task changes a real temporary file; the verifier reads the resulting bytes/hash. Missing registration produces a precise diagnostic. |
| **D3H-2 / DeepSeek** | Give existing physiology ownership of a per-body execution service and persistent pending-goal state. Tool calls enqueue/query it; each physiology tick returns promptly. Reconcile existing intents before considering submission. Preserve goal DAG, revisions and completed-goal state across restart. | `adaptive_goal_step` called twice on a running action reports/reconciles that action instead of stopping at `RESEND_FORBIDDEN`; changed content refuses. No duplicate effect or duplicate global scheduler. Completion survives restart and enables the next DAG dependency. |
| **D3H-3 / DeepSeek** | Expose reachable status and owner-stop routes for the same service. Use bounded adapter I/O and a separate cancellation/control channel; finite worker and queue counts. Represent timeout as unknown while an effect may still occur. Invalidate old control epochs at the adapter/actuator before admitting replacement movement. | A deliberately hung submit/status/verify cannot freeze physiology or the stop route. No thread accumulation or late timed-out effect restarting motion. Test stop before, during and after dispatch, journal failure, lease loss and process death. A Python thread timeout alone is insufficient evidence. |
| **D3H-4 / DeepSeek** | Connect planning and revision to authoritative adapter capability/precondition data. The caller may add requirements but cannot omit a tool's declared requirements. Resolve adapter/capability revision and goal/action IDs; use live evidence, not caller-provided health assertions. | Omitting a known prerequisite, wrong adapter, stale capability, expired evidence and changed body all refuse or enter discovery before effect. Poll exhaustion routes through bounded revision/block state; it cannot silently create unlimited new IDs. |
| **E0 / GLM** | Build the previously missing independent executable scenario runner, preferably `tools/sifta_adaptation_eval.py` over the existing gauntlet. Own hold-out task manifests and effect verification. | Normal startup→goal→real software effect→independent observation→receipt→restart→next dependent goal. Fault injection at every dispatch/journal/ack boundary and a hung-worker case. No success by fabricating receipt rows. |
| **INV-2 / GLM** | Keep D3g's recent-file view; add exact-path lookup and deterministic pagination/coverage metadata for full inventory. | An old organ remains discoverable after more than 50 newer files exist; generated output churn cannot hide a requested source file. Tie order deterministic; no false “whole body” claim from a 50-row sample. |

**D3g review:** moving the bound after the walk fixes alphabetical exclusion. It remains
a recency view; 8/8 visible today does not guarantee future visibility. Preserve the
improvement. Treat the reported 257/445 ms timings as one local measurement rather than
a universal speed ratio. INV-2 completes the targeted/paginated requirement.

After D3H/E0: **D4 + G2** (measured transfer and parameterized skills), **D5 + G3**
(resource recovery and scoped federation), **D6 + G4** (measured repair, retention and
independent endurance). **G1** continues against the frozen rover schema with David's
actual ROS/firmware/body profile; physical motion still needs bench evidence. **W1**
remains the separate WhatsApp echo/consent/read-view job. Preserve all phone/audio,
README, deployment and delivery items from the earlier WCT.

## TypeSafe / OpenJev: correct the claim, then implement the local organ

Observed locally: `swarm_typesafe_decision.py` is a cloud client; `classify_visitor`
still uses keyword/regex logic. This review did not replay paid cloud calls or verify
the six reported network responses independently. The 6/6 report is useful pilot
evidence, not a held-out generalization or calibration result.

TypeSafe distinguishes probability calibration across groups from correctness of any
individual answer. Its Choice confidence summarizes distribution concentration, not
an independent guarantee that the answer is correct. See its official
[System One](https://docs.typesafe.ai/concepts/system-one) and
[confidence documentation](https://docs.typesafe.ai/confidence).

The candidate matching the single-pass/WebGPU description is
[TheoLeeCJ/SemIf, formerly OpenJev](https://github.com/TheoLeeCJ/SemIf). Its README
explicitly reproduces the **interface pattern**, not Jev's undisclosed model/training.
It reads declared option logits; its probabilities are conditional on supplied options.
There are several unrelated projects named OpenJev. Pin the exact repository commit,
model revision, tokenizer, license and backend before evaluating one. Upstream docs
describe evolving backend/calibration work; verify the pinned checkout on this Mac
rather than copying a CUDA claim into a local receipt.

| Job / owner | Concrete change | Acceptance |
| --- | --- | --- |
| **J0 / GLM — DELIVERED** | Commit `dd8944bbe`: local Aries GGUF via llama.cpp b9700, next-token forward pass, tokenizer table, no-collision check and 512→1024 top-K ladder. | `tools/sifta_local_logits_probe.py` exit 0; 3 messages × 4 labels finite. Artifact digest, prompt hash and raw status recorded in receipt `31b3841d-1785-4ecc-84a6-ae96c3f10c05`. Raw option-relative scores are explicitly not calibrated. |
| **J1 / GLM — DELIVERED LOCALLY** | Added `System/swarm_calibrated_decision.py`: typed Choice-shaped result, `LlamaServerBackend`, full distributions, raw/calibrated status, model/prompt/label-order hashes, latency, artifact id, abstention, cache identity and explicit error receipts. No automatic cloud failover. | 7 focused tests pass. Test backend covers raw output, low-margin abstention, measured calibration artifact, cache identity/order, invalid/nonfinite output and backend outage. J1 is not wired into `classify_visitor`; that is J3 after J2 hold-out measurement. |
| **J2 / GLM** | Build representative labelled visitor-message data, separate fit/validation/test sets, and a calibration/evaluation CLI. Include benign security work, quoted attacks, insults, sarcasm, mixed intent and Romanian/English. | Report per-class precision/recall, confusion matrix, Brier/NLL, calibration error, abstention/coverage and latency p50/p95. Fit calibration only on the fit split; freeze thresholds before held-out testing. Six demonstration messages remain a smoke set. |
| **J3 / GLM** | Wire the local verdict into `classify_visitor` behind a tested rollout setting. Initially record shadow decisions with existing routing unchanged; promote only after J2 demonstrates better held-out behavior. | Every route says local model, calibrated local, abstained or keyword fallback. Unavailable/slow backend preserves response service. Classification changes conversational routing, never credentials, consent or physical authority. Existing caller return shape remains compatible. |
| **J4 / DeepSeek after J3** | Reuse the decision interface for candidate relevance, skill applicability and low-cost hypothesis ranking inside the adaptive loop. Preserve the main planner for multi-step reasoning and the independent verifier for effects. | Matched-budget ablation measures improved task outcomes or lower cost/latency. Decisions cite the state revision; stale judgments cannot act on a changed body. |

Do not label raw softmax scores “calibrated.” In single-token scoring, prove that each
label is one token in the exact prompt/tokenizer context; otherwise use an explicitly
documented sequence scorer. Option probabilities are relative to supplied alternatives;
include missing/none/ambiguous coverage. Do not use Jev's answers as unquestioned ground
truth for the held-out set. Keep cloud Jev as an optional fixed-budget comparison.

## J0/J1 return packet — 2026-09-22

GLM's J0 commit `dd8944bbe` is observed at HEAD and its report is consistent with the
local probe output: real llama.cpp forward-pass logits, no generated JSON confidence,
option-relative raw probabilities, and a truthful top-K failure mode. The J0 receipt is
`31b3841d-1785-4ecc-84a6-ae96c3f10c05`; the separate WSF ingest receipt remains
commentary, not ground truth.

This pass added J1 in the working tree. It reads the same server protocol through
`LlamaServerBackend`, refuses token collisions or missing/nonfinite options, emits a
full distribution and explicit raw/calibrated status, and hashes the model, prompt and
ordered labels. It caches only on the full message/options/model/template/calibration
identity. Cache hits receive a new receipt id. Backend outages produce a refusal receipt
and exception; no cloud call is attempted. The current J1 tests use a fake local backend
for deterministic behavior; the J0 evidence remains the real forward pass. J2 must fit
and test calibration before any calibrated artifact is used.

J1 remains an interpretation organ. It cannot stop a motor, bypass owner consent, or
replace the independent verifier. For a stuck robot, local Nav2/ESP32 progress sensing,
watchdog and stop remain authoritative; this organ may rank a bounded recovery choice
from fresh observations.

## Completion and receipts

“All handoff work complete” remains false while D3H/E0, learning, robotics and the other
listed jobs are open. The engineering objective is measured general adaptation across
different tasks and bodies; no module name or classifier result certifies AGI.

Retrospective four-ledger rows document the later verification/backfill time. They do
not establish that the original mutation was registered at the time it occurred.
Keep this distinction and the actual test commands in future packets. No need to rewrite
history. Checkpoint code on disk after each small slice to avoid the earlier narration loop.

Return: job ID, diff/commit hash, schema+implementation hash, test command/exit code,
independent effect evidence, failure/recovery evidence, real-vs-simulated status,
receipt ID, current gaps, and the next concrete write. Preserve unrelated dirty files.
Whole-directory pytest remains separately blocked by the recorded integrity mismatch;
track the reported truth-navigation prompt failure independently instead of blessing
the manifest or claiming the whole suite passed.
