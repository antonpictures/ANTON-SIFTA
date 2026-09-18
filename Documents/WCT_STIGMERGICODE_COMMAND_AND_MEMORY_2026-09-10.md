# Luna job: /stigmergicode and connected memory

Status: IMPLEMENTED IN REPOSITORY; local HTTP and focused offline tests pass.
The public coin Cloudflare route is now verified separately; native browser
pixel verification remains pending. The working code domain was not changed.
Procedural extension of Documents/IDE_BOOT_COVENANT.md, not a new covenant.
Owner request: send /stigmergicode from an authenticated web conversation or local
Alice surface, open the existing coding interface in Alice Browser, and let Alice
carry an explicit coding task through changes, tests and a recorded result.

## Read this first, then implement C1-C4

### Implementation checkpoint

- C1: implemented in `System/swarm_stigmergicode_command.py`, the Talk slash
  registry, `chorus_node_server.py`, and the phone page. Owner pairing is
  one-use and revocable; unauthenticated public commands are rejected.
- C2: implemented as a Qt event-queue consumer in
  `Applications/sifta_alice_browser_widget.py`. It focuses an existing DSH tab,
  distinguishes DSH readiness from an arbitrary port occupant, and bounds
  startup/recovery states. Actual Qt-tab observation is still pending.
- C3: task queue and append-only receipts are implemented. Automatic model
  editing remains intentionally bounded to the explicit harness task; no
  unattended repair sweep or Git push was performed.
- C4: `System/swarm_stigmergic_boot_memory.py` adds boot roots, source links and
  graph validation. It reuses the existing clock/body/location organs and does
  not invent pose or geographic coordinates.
- Public duplicate guard: exact and near-duplicate answers are retried once;
  stage-direction artifacts are removed from public text.

P0 before C1: owner reported stigmergicoin.com opening white on iPhone. The
Cloudflare route now serves the actual coin HTML; reproduce on the real iPhone
and diagnose
public response versus coin-host local origin and actual Safari rendering before
editing. Distinguish routing/empty 404 from JavaScript/assets/layout failure.
Fix the coin-specific cause and make initialization errors visible. Acceptance:
actual iPhone renders Capture moment, chat and sensor controls; denied sensor
permissions leave usable chat and a clear status. Preserve stigmergicode.com.
Do not mark resolved from a successful Mac HTTP response alone.

### Cloudflare handoff discovered during Luna verification

The local origin and `stigmergicode.com` are healthy, but the public
`stigmergicoin.com` request still returns an empty `404`. The old DNS record
points at `mps-tunnel` (`cfddce57-a68d-41da-99f7-24e971e68efe.cfargotunnel.com`)
while the migrated healthy tunnel is `alice-m5`
(`1597acdd-584f-4867-baf0-2bbb00ef1b65.cfargotunnel.com`). In the
`stigmergicoin.com` Cloudflare zone, update only the apex CNAME to the
`alice-m5` target, keep Proxy enabled, and verify HTTPS. Do not edit the
working `stigmergicode.com` record. The local CLI certificate administers a
different zone, so this specific change must be made in the coin zone's
Cloudflare dashboard or with a token scoped to that zone.

Inspect current diffs and nested AGENTS.md before edits. Preserve the working
stigmergicode.com page and Cloudflare configuration. Reuse existing command,
browser, pairing, task and memory components. Do not launch another coding agent
merely to plan. Keep phone-input work in WCT_PHONE_WORLD_INPUT_2026-09-10.md queued
after this command path; its outstanding tests remain outstanding.

Observed source entry points:
- System/swarm_alice_slash_commands.py: shared slash-command surface; inspect all
  actual callers before claiming support in every context.
- System/swarm_web_global_chat_gate.py: public visitors currently have zero owner
  authority. A visitor session ID or a phrase saying 'I am George' is not identity.
- System/chorus_node_server.py: web ingress; preserve existing routes and UI.
- Applications/sifta_alice_browser_widget.py: _ensure_local_harness() and
  _HARNESS_URL already target http://127.0.0.1:3080, with SIFTA workspace variables.
  Port-open currently counts as ready: add a bounded application identity/readiness
  check before reporting a usable coding tab. Inspect the native Qt tab API.
- System/sifta_phone_link.py: existing ticket/pair/authenticate implementation.
  Inspect lifetime, persistence and scope before adapting it to public HTTPS.
- System/swarm_spinal_cord.py: existing task formulation, dispatch, apply and
  result paths. Reuse a bounded explicit task entry, not an unrestricted repair sweep.
- Applications/sifta_we_code_together.py: To Code reads the first 24000 characters
  of WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md. Keep the current assignment at its top.

### C1. One command contract across actual input adapters

Implement /stigmergicode to open or focus the coding tab only. Optional trailing
task text, e.g. /stigmergicode fix the failing camera OFF regression, explicitly
requests one bounded coding job. A bare command must not invent a job or start
an autonomous loop. Use one shared parser for local Talk, Matrix and web adapters;
list supported entry points and any missing adapters in the completion report.
Recognize the leading command token exactly. Quoted transcripts, pages, captions,
audio from the environment and retrieved memory must not execute commands.

Web use requires a server-verified owner session with the coding capability,
established by owner-approved pairing on the Mac. Reuse existing auth primitives;
do not infer authority from the secret command, IP address, display name, client
boolean, camera face or opaque public chat session. Persist revocable paired
identity; expire one-use pairing tickets, protect cookies/requests and never put
credentials into public transcripts or logs. Unauthorized requests return pairing
instructions and perform no local launch. This extends owner access while retaining
the current public visitor contract.

Dispatch through the trusted command path before generic model generation. Store
request ID, verified actor/device, originating surface and task ID server-side.
Repeated delivery returns the existing task/result; changed payload with the same
ID is a conflict. Keep owner coding receipts scoped to that owner session.

### C2. Alice Browser delivery and readiness

Queue a desktop event and handle it on Qt's UI thread. Focus the existing coding
tab or create exactly one, using the existing browser implementation. The URL is
Mac-local; do not redirect a remote iPhone to its own 127.0.0.1. Show the remote
owner an acknowledgement/status and task ID instead. Keep port 3080 private.

Reuse the existing launcher with a lock against concurrent starts, bounded startup
deadline and an application readiness probe. Launch work off the GUI thread. Never
kill an unknown process occupying the port. Report conflict/unavailable precisely.
Use Kimi WebBridge for external browser automation if needed, and verify its actual
receiver; the native Alice tab must be observable in the actual desktop browser.

Persist states: accepted -> waiting_for_desktop -> opening -> tab_ready -> failed.
If the desktop is closed, acknowledge queued status with expiry/cancellation; do
not claim a tab opened. Receiving a command is distinct from opening a tab and from
starting a coding task. Reconnect/restart must not create duplicate tabs/jobs.

### C3. One bounded coding job with evidence

For explicit task text, attach the exact owner task, workspace, applicable WCT
ticket, relevant source references and acceptance criteria to the coding session.
Verify the actual user-message payload arrives; loaded system context alone was
previously mistaken for a task. Keep cortex and coding-model selections independent.
Use an installed selected local coder, with observable unavailable-model handling.

Reuse the spinal-cord task and mutation-governor flow, inspect existing changes,
bound wall time/tool steps/retries, and propagate cancellation to child processes.
One admitted heavy inference job on the 24GB node; do not unload another active
request's model. No retry-forever behavior on missing credentials or failed tools.
Record task -> patch/diff -> test command and exit/result -> apply decision -> final
receipt. Empty test selections do not pass. Preserve unrelated edits. A coding
session opening or an LLM saying 'done' is not a successful repair.

First trial: a small synthetic failing test in an isolated scratch checkout.
Demonstrate one fix, one test result and one terminal task receipt, including Stop.
Real repo task follows after that trial; respect existing release authorization
and reviewed-file requirements before any commit/push.

### C4. Connected deterministic foundations, fallible observations

Represent boot context as a versioned record in the EXISTING field: node ID,
boot/session ID, system UTC/timezone and monotonic origin, schema/policy version,
sensor capability states and references to the last validated checkpoint.
For pose include source, capture time, map ID, origin epoch, coordinate frame,
units, tracking state and transform. Missing pose is null. A declared relative
origin (0,0,0) is a convention, not measured geographic location. Keep phone pose
and Mac location separate. Safari capture alone does not supply native ARKit pose.

Link each derived record to source receipts and transformation/version; each
decision to the evidence snapshot it actually consumed; each result to its task.
Declare explicit root records for boot/config/sensors instead of inventing parents.
Validate references with scope checks and bounded traversal. Missing parents,
out-of-order arrival, unavailable sources and cycles must be detectable. Retain
pending records for reconciliation; exclude unresolved evidence from verified
claims. Records may be archived; summaries retain source references and uncertainty.

Repeated wording, deterministic execution and truth are separate properties.
Repeating a claim must not raise confidence. Corrections append superseding links;
they do not overwrite the original. Distinguish instructions, observations, owner
reports, hypotheses and independently verified outcomes. Never describe a generated
answer as the 'most confirmed trace' without an actual retrieval/validation receipt.
Use a sparse typed graph for these relationships. Hexagonal/pentagonal visualization
is optional; fixed geometry is not a prerequisite for correct memory connections.

Public replies should answer the latest question plainly. Remove voice stage
directions unless requested, and do not claim speech occurred without playback
evidence. Inspect the current duplicate guard: it compares the current prompt with
the previous ANSWER, not the previous question; exact equality also misses the
reported near-duplicate with a changed opening sentence. Reproduce both defects.
Do not turn all similar legitimate answers into errors or strip deliberate quotes.
Retry at most once, preserving an end-to-end deadline and observable failure.

## Acceptance and handback

Offline tests: shared parser adapters; quoted-command nonexecution; unpaired,
expired/revoked and forged owner requests; idempotent retries; desktop absent;
concurrent launch; wrong service on 3080; UI responsiveness; stop/timeout; exact
task arrives; terminal outcome survives restart; cross-session receipt isolation.
Memory tests: explicit roots, dangling links, cycles, out-of-order repair, stale
pose, changed map origin, unavailable sensors, conflicting observations and
unchanged confidence after repetition. Prove request context uses source IDs.

One actual owner-paired web test: /stigmergicode opens/focuses Alice's tab; repeat
does not duplicate; one small explicit task produces a reviewed diff and tests;
another public session cannot start/read it. Record actual browser evidence and
distinguish mocked tests from runtime results. Do not publish private screenshots.

Update WCT and README with implemented/tested/live-verified/pending states, four
coordination-ledger receipts, and tools/whats_left.py results. Keep phone L0-L4
and native signing/device gaps visible. Report concrete unresolved questions to
Astra. These deliverables demonstrate command, memory and coding capabilities;
they do not establish general intelligence or consciousness.
