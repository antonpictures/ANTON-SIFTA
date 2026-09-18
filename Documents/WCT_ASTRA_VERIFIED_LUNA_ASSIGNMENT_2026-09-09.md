# Verified assignment for the next Luna turn

Status: source review plus isolated diagnostic reproductions, 2026-09-09.
This assignment supersedes the job order and completion claims in the earlier
credit-saving and Luna-review handoffs. Those documents retain historical
context and the detailed release checklist. User has started Ornith's camera
test in the existing harness. Luna begins independent work immediately.

## Luna checkpoint: deterministic slice completed

Fresh local evidence after the first implementation slice:

| Area | Result | Evidence |
| --- | --- | --- |
| Decoder boundary | PASS at unit level | HEIF conversion now uses a supervised `subprocess.run(..., timeout=...)` over immutable source bytes; normalizer tests pass. |
| Capability precedence | PASS | Ollama capability metadata is consulted before name heuristics in both body policy and multimodal timeout routing. Misleading model names no longer override reported capability. |
| Two-stage evidence type | PASS at unit level | `System/swarm_vision_evidence.py` adds scoped generation IDs, source/transport hashes, question hash, stale-result rejection and a no-tool-authority prompt boundary; local vision results can wrap into it. |
| Offline-safe tests | PASS | `50 passed, 1 deselected` with syntax compilation for the changed modules. |
| Live local vision | NOT RUN | The existing no-local-model probe can reach a running Ollama request and wait for its configured model timeout; it was excluded after the combined run was interrupted. |
| Real HEIC / GUI / camera / browser | NOT RUN | Requires an actual fixture/device/browser observation, not source inference. |

This is not an AGI or self-healing claim. The next engineering slice is to
wire the typed evidence into the actual Talk request and attachment ledger,
then verify the request payload and cancellation path without launching a
second heavy model while Ornith is active.

## Start prompt for Luna

Read this entire assignment, AGENTS.md and the existing covenant. Implement
jobs 1 through 6, starting now with attachment decoding. Do not return another
plan as the deliverable. Keep progressing on independent work if a live test
is blocked. Preserve the current worktree and Ornith's camera test; inspect
current changes before touching shared files. Record each result as PASS,
FAIL, BLOCKED or NOT RUN with the observed evidence. Update WCT, README and
eval; publish the reviewed release under the existing authorization when its
release gates pass. Bring Astra concrete remaining failures and design
questions with minimal reproducers. A model name is not an AGI acceptance test.

## Review evidence that changes the next job order

These checks ran against the current source without model inference or camera
access. They supersede the earlier blanket description of completed fixes.

- `_bounded_call` starts a daemon thread and joins it. An Event-controlled
  decoder remained alive after TimeoutError. A join blocks its caller, so
  invoking it on the GUI thread still freezes that thread. The sips fallback
  gets another full timeout; final JPEG validation has no timeout.
- With `_ollama_capabilities` mocked to return completion plus vision,
  `_observed_cortex_capability('krishairnd/Gemma-4-Uncensored:latest')`
  returned text_only and never called the probe. With completion only,
  `gemma:2b` returned vision and again never called the probe.
- The test `test_live_text_only_capability_routes_unknown_named_cortex`
  patches `policy._ollama_capabilities` with raising=False. Production imports
  it locally from swarm_cortex_capabilities. Patching the test's target had
  zero calls and did not affect the result. Its previous pass depended on
  environment/cache behavior; it does not prove deterministic routing.
- Orientation transpose and payload reuse were added, but real HEIF decoding
  is still mocked. Transpose errors are silently swallowed. Normal JPEG/PNG/
  WebP paths only check signatures. HEIF decoding rereads the source path after
  hashing, and Talk reads the source separately for MIME. Hash fields alone
  are not persisted conversion receipts.

The reported 67 and 73 passing tests are historical, overlapping suite runs;
do not add their counts or treat them as complete release proof.

## 1. Finish decoding and attachment lifecycle

Own System/swarm_image_attachment_normalizer.py, its dedicated tests and Talk
attachment transport changes. Leave camera source/tests to Ornith for now.

Replace daemon-thread timeout with a supervised decoder process that can be
terminated and reaped. Use one monotonic deadline across decode, any fallback
and output validation. Invoke it from the application's background worker,
return through its UI signal/dispatch mechanism; do not join on the GUI thread.
Manage child cleanup, bounded stdout/output and temporary files on all paths.

Read source bytes once with a size cap; decode that immutable snapshot. Carry
one NormalizedImage result through MIME, base64, dimensions and receipt hashes.
Decode/validate all accepted formats, enforce input/output/pixel limits, apply
orientation before stripping metadata, and do not suppress rotation errors.
Check HEIF decoder autorotation to avoid applying it twice. Declare decoder
dependencies and distinguish unavailable, corrupt, oversize and timeout errors.
Persist a conversion receipt in the existing attachment ledger with source and
output hash, dimensions, MIME and status; keep private paths out of web replies.

Use a generated or redistributable actual HEIC fixture and compare colored
pixel positions after rotation. Test corrupt containers, signature-only JPEG,
byte and pixel limits, unavailable decoder, total timeout, no surviving worker,
source changed during processing, and UI responsiveness. Retain the draft on
failure and clear only the successful turn's attachment. Inspect and reuse the
actual web upload validator before declaring desktop and web complete.

## 2. Make observed capabilities authoritative

Own System/swarm_body_multimodal_policy.py, swarm_cortex_capabilities.py,
swarm_ollama_vision_arm.py and their focused tests. Examine timeout routing too.

Resolve exact provider/model and obtain its capability record before applying
name heuristics. For local Ollama use installed metadata, cached by endpoint,
exact tag and digest with invalidation on inventory refresh. Metadata absence
means unknown. A slow first token is a runtime failure, not removal of vision
capability. Avoid calling every Gemma visual or every heretic model text-only.
Represent declared capability and successful request validation separately.
Preserve the exact owner's eye choice; if unavailable, expose that state.
Use the user's preferred MiniCPM candidate when installed and confirmed visual;
preserve a valid explicit override. Do not silently introduce a paid fallback.

Patch the actual dependency in tests and assert that the mock is called.
Tests must run offline with temporary state: misleading names, metadata wins,
unknown metadata, missing override, refresh/digest change and failed request.
Remove raising=False mocks that conceal nonexistent seams.

## 3. Implement the two-stage adapter with these decisions

Proceed without waiting for another Astra design round. Native confirmed vision
cortexes retain direct image input. Confirmed text-only cortexes retain their
selected speaking model and use a local vision adapter. Unknown capability
returns an actionable state; do not invent a description.

Use the normalized snapshot and original question for one vision request.
Return a typed evidence record: session scope, turn ID, generation ID, source
and normalized hash, question hash, preprocessing version, exact eye model and
digest, capture time when available, processing time, status, observations and
uncertainty text. Numerical confidence must come from a calibrated mechanism;
do not manufacture it. The speaking cortex receives this evidence as fallible
image-derived data with no instruction/tool authority, and no image bytes.
Preserve the user request separately from the generated observations.

Cache by session plus normalized hash, question/crop, preprocessing and model
digest. Never reuse across visitors or changed questions. Discard late results
after session/model/generation changes. Apply deadline/cancellation to both
stages and keep owner drafts recoverable on failure. Reuse existing request
scheduling where available; avoid launching another heavy inference while the
17 GB Ornith job is running. Never unload weights serving another request.

Test the actual speaking-model request payload, not just selector output:
text cortex + eye, native direct, missing eye, eye failure, cancellation,
late result, repeated photo with new question and cross-session isolation.
Benchmark installed Aries/MiniCPM only when resources are idle. Report timings
and memory separately from answer quality; no fastest/best claim from names.

## 4. Integrate Ornith and finish harness/camera checks

Ornith owns camera OFF polling regression and a read-only HEIC-test review.
Luna need not wait for that job before jobs 1-3. Before editing camera paths,
read Ornith's result/diff, independently run its test and resolve any overlap.
Do not send it a duplicate assignment or restart its process. If no receipt
exists, mark that integration pending and continue jobs 5-6's independent work.

Camera verification includes OFF polling, stale previews, device attribution,
hot-plug, sleep/wake, embedded-camera pinning and an idle live restart. Diagnose
the six historical photo/voice failures rather than declaring them unrelated.

Harness's default_unavailable field currently exists in a report; verify a
visible UI consumer actually tells the owner to select an installed model.
Preserve independent cortex/arm choices. Verify boot and /cortex llm refresh
update installed tags and sizes in the live harness, not only its YAML file.
Reproduce LM Studio credential failure at provider registration/request level.
Inspect harness-local instructions before changes and preserve auth semantics.

## 5. Verify delivery, UI, time and body health

Use the existing local/public chorus path and actual browser evidence for image
preview, valid download bytes, history reload, duplicate polling and session
isolation. Keep #SIFTA. Record the failing endpoint if a bridge is unavailable;
continue other checks. Do not replace successful-image evidence with text.
Verify local/web light-dark styles, Display wiring, scrolling and single-demo
robotics layout from the existing pending work.

Check time at answer generation, timezone conversion and stale-journal handling.
Location must retain permission, freshness and owner/visitor scope. Investigate
stale STGM cache and reported disconnected organs with actual current health
evidence. Never manufacture signed spend or passing receipts to close a check.
Physical motors remain simulated until actual hardware and stop controls exist.

## 6. Document, review and release

Update this file with a concise per-job evidence table and the remaining open
questions. Update README book, eval matrix and tournament consistently; run
the repository's whats_left tool. Do not leave earlier completion prose that
contradicts fresh failures. Append truthful four-ledger work receipts.

Use the earlier handoff's detailed release procedure: group all pending paths,
audit source/dependencies/nested repositories and licenses, inspect explicit
staged content for owner data and secrets, test an isolated installation with
no owner state, check current health and integrate remote changes safely.
The user already authorized a reviewed commit/push. Report remote-confirmed
commit IDs, or the exact failed release gate and remaining work. No force push.

Reserve Astra questions for reproducible unresolved architecture/accuracy
problems, measured temporal-memory experiments and hardware-specific motor
design. Decoder cleanup, asynchronous UI and test isolation are ordinary
engineering work for Luna to complete.
