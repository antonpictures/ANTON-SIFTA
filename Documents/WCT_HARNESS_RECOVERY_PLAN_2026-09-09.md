# Harness recovery and next bounded coding jobs

Status: PLAN plus source review. No runtime changes or inference dispatched in
this review. This recovery order supersedes earlier instructions to run all six
feature jobs immediately. Preserve the unfinished feature backlog.

## Incident and evidence

The owner reports sustained local-model activity, an unresponsive macOS password
screen and a forced restart. Cause is UNCONFIRMED. Possible contributors include
memory pressure, repeated requests, concurrent inference, or a macOS/display
problem. Current post-restart swap usage was 0 MB; it cannot reconstruct pressure
before the restart. A model's 17 GB disk size is not its full runtime memory cost:
context/KV cache, runtime buffers and other applications also occupy memory.

Source observations:

- `deepseek-harness-master/packages/llm/llm-pi-ai/src/config.ts` defaults the
  stream idle timeout to 300,000 ms; omitted retry policy means five retries.
  Repeated idle timeouts can take roughly 30 minutes plus backoff for six
  attempts. Active streaming can exceed that because idle is not a total deadline.
- `packages/llm/llm-retry/src/index.ts` supports `mode: always`; only normal
  mode applies maxRetries. This exists in source; the incident's effective
  retry configuration has NOT been established.
- The inspected agent-loop settings schema exposes parallel tool-call count.
  Audit other lifecycle/budget plugins before claiming there is no total limit.
- `System/swarm_cortex_resource_field.py` uses a rough text-based thermal proxy.
  Missing powermetrics output falls through to zero. This is insufficient as a
  reliable resource admission signal; unavailable must remain unavailable.
- In the prior Luna tool history, the same waiting pytest command was launched
  twice. Both were subsequently stopped. Treat this as a possible extra load
  source, not proof of the incident cause. Resume/poll an existing test process;
  never start a duplicate because its output went quiet.

## Review of Ornith's reported 16 passes

The owner's pasted report says 16 tests passed. This review did not rerun that
command or recover its exact revision, output and process exit receipt. Treat
the count as REPORTED until tied to the tested files.

The current checkout contradicts the claim that all network calls are mocked:
`tests/test_swarm_ollama_vision_arm.py::test_describe_no_local_model_is_honest_failure`
calls describe_image_local with no mocked picker or request. It may discover
a real model and invoke inference. The previous run demonstrably waited in a
socket call. Tiny fixture bytes do not make this test offline.

Other material limitations:

- `test_decoder_timeout_terminates_child_process` mocks the conversion helper
  to raise TimeoutError. It does not start, terminate or reap a child process.
- `test_heic_reports_missing_decoder` patches the old `_convert_with_pillow`
  seam; production calls `_convert_with_pillow_subprocess`.
- `test_rejects_fake_heic_and_oversized_source` tests invalid bytes only; it
  does not exercise an oversized source despite its name.
- The orientation test mocks Image.open and calls the in-process helper. It
  does not prove the production subprocess or a real HEIC decoder's rotation.
- HEIF metadata accepting an ftyp stub proves recognition only, not decoding.
- SHA string-length checks should become content equality checks.

Ornith's explanation of the OFF fake is consistent with current production:
unique_id=OFF explicitly bypasses the capture_allowed check. A blocked hardware
fixture must have a hardware ID. No persisted `_poll_saccade_target` regression
test was found in the current tests search. Obtain the actual file/diff before
claiming the camera job landed. Keep camera tests separate from HEIC tests.

## Job A: Luna, offline tests and harness recovery

Read AGENTS.md and nested harness instructions. Implement this job before more
local-model benchmarks. Start with a snapshot of diffs and identify existing
processes without printing credentials or full private session content.

1. Make the no-model unit test deterministic: fake an empty installed-model
   picker and fail immediately if a network request is attempted. Mock the
   actual production seams. Keep any live probe separately marked, opt-in and
   timeout-bound. Add a suite-level network denial for these unit tests without
   changing other suites' behavior. Run one test process at a time.
2. Read the incident session's final events and effective provider settings in
   bounded slices. Report request IDs, durations, retry count, tool-call count,
   stop reason, model and context sizes. Do not dump conversations or keys into
   public docs. Distinguish still streaming, retrying and repeating tool calls.
3. Find existing run budgets and Stop/cancel wiring. Extend them with a local
   coding profile: initially 10-minute total run budget, at most 8 model steps,
   12 tool calls, one transient retry, and one active coding job. These are
   proposed recovery defaults, adjustable settings, not claims already active.
   Use normal retry mode. Authentication/configuration errors must end without
   repeated retries. Total deadline includes backoff, inference and tool waits.
4. Detect three consecutive identical tool+argument+failure outcomes with no
   progress. End with a checkpoint listing the actual blocker. Never count
   repeated wording alone as failure, or auto-replay mutating commands.
5. Propagate cancellation through the existing abort signal to fetch/stream,
   retries and owned child processes. Stop should visibly settle within two
   seconds; use a short cleanup grace for owned children. Prevent late results
   from restarting the run. Check Ollama cancellation separately: client abort
   alone is not proof server work stopped. Do not kill all Python/Node/Ollama
   processes or unload a model used by another request.
6. Persist interrupted state on crash/restart. Reopen with Resume/Review/Cancel
   and the draft intact; do not automatically replay the previous coding turn.
   Add sleep/wake handling through existing lifecycle hooks. Preserve normal
   macOS locking and authentication. Never solve this by disabling the lock.
7. Coordinate local inference admission across Talk, coding arm and vision using
   the existing scheduling/resource mechanism. Keep their model selections
   independent. Initially serialize heavy local work, allow cancellation and
   display queue reasons. Use measured memory-pressure/swap/loaded-model data;
   unknown telemetry cannot mean healthy. Make no fixed RAM-fit promise.

Acceptance: mocked repeating provider, never-ending stream, transient failure,
auth failure, stuck tool, Stop during backoff, late completion, restart and
two simultaneous local requests. All must finish predictably without inference.
Capture a reviewed diff and exact exit status. Do not dispatch a local trial
until those tests pass.

## Job B: Ornith, only after Job A passes

Start a fresh small session; archive/checkpoint the old long context. First
read the actual camera regression patch if it exists. Target one test file and
three cases only: explicit OFF bypasses the hardware gate; a rejected hardware
ID is blocked; an allowed embedded camera reaches selection. Use fakes, temporary
paths and no physical capture. No model downloads, background workers, runtime
restarts or Git push. One test run; at most one correction and rerun. Then report
diff, command, exit status, and what was not tested. Stop instead of asking for
another task or starting another loop. If no patch exists, write the regression
in a dedicated camera test file, not in HEIC tests.

Trial admission: idle host and no competing heavy inference. Apply Job A's
budgets. Record memory/elapsed time, then independently review the patch. A
successful small task permits a later task; it does not justify an unbounded run.

## Resume feature backlog after recovery

Finish real HEIC validation and process-cleanup tests; remove unbounded sips
postprocessing in the parent. Wire visual evidence into the actual text-cortex
request with session/turn identity, request-start generation, model digest and
late-result rejection. Current helper types alone do not provide runtime
session isolation or cancellation. Then camera/runtime verification, image
delivery/download, settings, health and isolated installation remain required.

Update WCT, README and eval with observed results. Preserve historical receipts
and append corrections. Publish only after the existing healthy-before-push
release gates pass. No production fixes, lock-screen diagnosis, camera pass,
or AGI completion is claimed by this planning round.

## General-purpose behavior: next implementation queue

Owner requested more work toward AGI. Extend the existing roadmap in
`Documents/AGI_SIFTA_NODE_ASTRA_HANDOFF_2026-09-09.md`; do not create a second
planner or parallel memory store. Recovery Job A remains first. Assign one
bounded ticket per coding run; a large backlog is not one unattended prompt.
These are measurable engineering milestones, not an AGI certification scale.

### C1. Repair outcomes must be measured (Luna)

Source rechecked: `System/swarm_spinal_cord.py` sets tests_passed=True before
checking for test_paths and assigns measured_gain=task.predicted_gain when
checks pass. This remains an observed defect in the current checkout.

Extend the existing repair pipeline and self-improvement loop. Require a
nonempty, actually executed relevant test set with a verified exit result;
zero collected tests, timeout and skipped-only runs are inconclusive. Measure
the same named outcome before and after on fixed fixtures outside the patch's
control. Keep predicted_gain separate; missing measurement stays unavailable.
Do not let the model's TESTS_PASSED text certify its own patch. Evaluate a
candidate in isolation and use the existing snapshot/rollback mechanism;
rollback must not overwrite concurrent edits by another worker.

Acceptance uses a tiny synthetic broken module: empty tests cannot yield a
verified repair; syntax-only success cannot prove improvement; a wrong patch
is rejected; a real fix passes a held-out case and records measured improvement;
a concurrent edit survives a rejected proposal. No live self-patching run yet.

### C2. Remember the right facts for the right task (Luna)

Trace existing journal, recall and session-scoping consumers first. Retain
source, observation time, audience, validity and superseded-by links for facts.
An owner correction supersedes the relevant belief without deleting history.
No background publication of private context. Current time comes from the
clock; location and camera claims must retain sample age and uncertainty.

Acceptance: interleave an owner planning a meal, visitor A asking about a
lottery, and visitor B requesting an image. Each answer uses only its permitted
context. Change an owner preference, restart, and verify the correction is
retrieved while the older version is labeled historical. Repeat with missing
and conflicting receipts. Score actual retrieval/output, not prompt presence.

### C3. Finish seeing while keeping the chosen speaking cortex (Luna)

Use the existing vision assignment's two-stage adapter. Allocate generation
identity before work starts. Pass normalized image plus the actual question
to the selected installed eye; pass scoped observations to the selected text
cortex. Native vision stays direct. Read evidence age on use, reject old
session/model results, and preserve drafts on failure. Exercise the real
request builder with fakes before an idle-host model trial.

### C4. Complete and recover a multi-step task (Luna, then Astra review)

Reuse existing task/schedule and action-result types. Persist the goal,
current step, prerequisites, expected observation, actual outcome and next
checkpoint. External tool results decide whether a step completed. After a
crash, inspect the effect before retrying a non-idempotent action. Stop settles
the task; it must not silently resume because a delayed callback arrives.

Acceptance in a disposable workspace: read a synthetic pantry image, prepare
a shopping note using a saved preference, create a local reminder, and recover
after a simulated interruption. Include unavailable vision and an unwritable
destination. No real purchase or outgoing message is needed for this trial.

### C5. Learn a reusable procedure (Astra experiment, Luna plumbing)

Compare the same task family before and after an explicit owner correction.
Store a candidate procedure using the existing skill/memory mechanism with
provenance and versioning. Evaluate on held-out wording and changed inputs,
including cases where the procedure should not apply. Revert a regression.
Separate memory-assisted improvement from weight training; count success,
incorrect actions, requests for clarification, latency and inference calls.
The model that proposes the procedure must not write its acceptance answers.

### C6. Ground future movement (simulation first)

Extend the existing motor feedback lab with perception delays, missing samples,
unexpected target changes and measured state feedback. Compare predicted and
observed motion. Test stop and stale-observation handling independently of the
LLM. Physical trials remain pending a named robot, calibration, actual feedback
and working stop controls. A laptop camera alone cannot establish joint control.

### Shared evaluation and handoff

For each ticket, WCT should show implementation status, tested revision,
scenario, observed result and next failure. Report per-scenario success and
regressions across memory, perception, planning, recovery and transfer; do not
collapse them into an invented AGI percentage. Preserve failed and unrun cases.
Keep all trials local and synthetic until specifically exercising a live
capability. Apply the harness recovery budgets to every local coding trial.

NEXT LUNA PROMPT: Read this recovery plan. Complete Job A first. Once verified,
implement C1 with a synthetic module and held-out outcome tests; report the
reviewable diff, executed checks and unresolved failures. Leave C2-C6 queued.
Do not start a local inference job just to inspect or edit Python tests.
