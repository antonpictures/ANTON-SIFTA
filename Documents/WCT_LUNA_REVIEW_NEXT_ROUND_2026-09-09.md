# Luna next round: review findings and release work

ACTIVE UPDATE: `Documents/WCT_ASTRA_VERIFIED_LUNA_ASSIGNMENT_2026-09-09.md`
supersedes the status and job order below. Review reproduced a surviving decoder
thread after timeout, capability heuristics bypassing metadata, and an unused
test mock. Ornith's camera job is running; Luna starts decoder/capability work
independently. The sections below retain the previous pass's reported results.

CURRENT LUNA CHECKPOINT: supervised decoder process, metadata-first routing and
the typed scoped visual-evidence boundary are now implemented and covered by
50 offline-safe passing tests with one live-model probe deselected. The browser
photo attempt now carries the evidence row when the local arm supports it.
Real HEIC pixels, GUI cancellation, Talk payload/ledger wiring and live runtime
checks are still open; no release push or AGI claim follows from this slice.

Status: reviewed plan. Source inspected on 2026-09-09 after the first Luna pass.
Owner asks to finish pending changes, update README book and push Git after
verification. Earlier handoff restrictions to one job/no push are superseded.
AGI remains a research objective; publish concrete tested capabilities.

## Completed in this continuation

The following concrete fixes are now implemented and focused-tested:

- HEIC conversion applies serialized EXIF orientation before removing metadata,
  validates normalized JPEG output, records source/output SHA-256 values, and
  adds a timed join. Review found the worker survives timeout and its caller
  still blocks; process cleanup and asynchronous GUI integration remain open.
- Talk reuses one normalized owner-image payload for the live request and the
  memory record instead of rereading/encoding the source twice.
- An unknown cortex capability is reported as unknown; the image router no
  longer overrides the selected eye with a hardcoded osmQwopus model name.
- The local vision-eye override is an exact installed-tag match.
- An unavailable Harness model selection is preserved and reported as
  `default_unavailable`; it is never silently replaced by the first Ollama tag.
- The camera polling path now resolves an explicit `OFF` sentinel before the
  normal capture-allowed rejection gate.

Evidence: the focused changed-path suite is 67 passed; the adjacent attachment,
camera and time/location suite is 73 passed. These are local automated results,
not proof of a real owner HEIC round, a live camera restart, or AGI.

## Astra open questions

1. Which local vision adapter should be the owner default after measuring
   latency, resident memory and answer quality on the M5 24 GB machine: the
   installed MiniCPM-V, Krishna Gemma, or another exact Ollama tag?
2. Should the two-stage route return structured fallible evidence to the text
   cortex, or should a native multimodal cortex remain the default whenever it
   is available? Define the receipt schema and stale-response cancellation
   contract before calling this AGI behavior.
3. What is the approved physical motor boundary? Current motor outcomes are
   simulated only; no code should claim safe joint motion without a real
   driver, stop circuit, limits and an owner-confirmed hardware test.
4. Confirm the actual account billing figures before putting the supplied API
   comparison into runtime policy. For planning only, the owner supplied:
   Luna $0.20/$1.20, Terra $2/$12, Astra $10/$50 per million input/output
   tokens. These figures are not verified by this repository.

## Next jobs to paste into We Code Together

### Ornith 1.5 35B: independent bounded coding job

Run only when the current harness turn is idle. Do not edit the same files as
Luna and do not mutate the live SIFTA process. Read `AGENTS.md`, this document
and the harness repository instructions first.

```text
You are the local coding reviewer using
codecraftersllc/ornith-1.5-35b-a3b-abliterated:latest. Work in the supplied
SIFTA checkout, but do not start another model, download weights, call paid
APIs, touch credentials, change receipts, restart cameras, or push Git.

Review the current implementation of the camera target polling path and add a
small regression test proving that an explicit unique_id="OFF" target is
accepted by _poll_saccade_target before capture_allowed rejects hardware
camera names. Use fakes only; never open a physical camera. If constructing
the Qt widget is unsafe in headless mode, extract and test the smallest pure
decision helper instead, without changing runtime behavior.

Also review the changed HEIC tests for accidental private data or fake success.
Do not rewrite production code unless the test exposes a concrete regression.
Report exact files, the test command, exit code, and any open question. Keep
the patch limited to this test/review job and stop.
```

### Luna: integration and release job

After reviewing Ornith's receipt, continue with the remaining jobs in order:

```text
Read Documents/WCT_LUNA_REVIEW_NEXT_ROUND_2026-09-09.md and Ornith's receipt.
Preserve all existing work. First finish the real two-stage local vision
adapter: a text-only Ollama cortex such as Aries must send one normalized image
plus the owner's question to the selected installed vision model, then the
answering cortex composes from scoped fallible evidence without image bytes.
Add request-generation IDs, timeout/cancellation, image/task/model cache keys,
owner/visitor isolation, and explicit failure evidence. Keep native vision
models on their direct route. Do not call unknown capability visual.

Then run the camera OFF/polling suite and diagnose remaining camera tests;
perform live restart/capture verification only when the owner's active turn is
idle. Review the running Harness task before touching harness files. Verify
Ollama/LM Studio provider refresh and honest unavailable-model status. Finish
the real chorus image preview/download/reload/session proof if the WebBridge
is available; otherwise record the exact blocked request.

Update README, the eval matrix and WCT with observed evidence. Audit changed,
untracked and nested-repository files for secrets, owner data, model weights,
node_modules and licensing. Run grouped tests, fresh health checks, an isolated
installation check, git diff --check and staged-content review. Commit and push
only the explicit reviewed release paths after all required gates pass. Report
commit IDs and every remaining Astra question. Do not claim AGI completion.
```

## Review findings that must be fixed first

1. HEIC conversion loses orientation. Reproduced with an 8x4 Pillow image
   carrying EXIF orientation 6: `_convert_with_pillow` returns 8x4 with the
   orientation removed; expected display dimensions are 4x8. In
   `System/swarm_image_attachment_normalizer.py`, apply ImageOps.exif_transpose
   before RGB conversion and metadata removal. Inspect decoder auto-rotation
   behavior so HEIF is not rotated twice. Test actual pixel positions, not only
   dimensions, with a non-square multicolor fixture and a real HEIC sample.
2. Decoder bounds are incomplete. Pillow runs synchronously without the
   conversion_timeout; sips resizes output but does not establish a pre-decode
   pixel bound. `_sanitize_jpeg` returns unsanitized bytes if Pillow is absent.
   Register the optional HEIF plugin explicitly when installed. Run conversion
   in a bounded worker with timeout and cleanup; validate source dimensions,
   output bytes and decoded image before success. Distinguish unavailable
   decoder, corrupt image, limits and timeout in errors. Declare dependencies.
   Do not describe output as metadata-free unless validated. Standard image
   signatures alone are not proof bytes decode successfully.
3. Current HEIC tests do not prove conversion. The normalizer test replaces
   decoding with fake JPEG bytes; the metadata test accepts a fabricated HEIF
   header. Keep those as unit tests but add a real synthetic/redistributable
   HEIC fixture, orientation, corrupt/truncated container, missing decoder,
   conversion timeout and oversized-input tests. The test named oversized
   currently never tests size. Add hash/provenance to conversion receipts.
4. Actual two-stage vision is still missing. Talk changes the answering model
   to a VLM. That is not Aries composing from MiniCPM evidence. In
   `System/swarm_body_multimodal_policy.py`, unknown models are described as
   "active cortex can see" just because a text-only regex did not match, and
   image_turn_vlm_redirect still preferentially picks osmQwopus. The local eye
   picker still prioritizes Gemma by name and accepts substring overrides.
   Use observed capabilities, exact installed tags and explicit owner choice.
   Unknown capability must be reported as unknown. Timeout history must not
   rewrite a model's declared capability as text-only. No paid fallback without
   existing authorization. A declared capability still requires a successful
   request test before advertising operational readiness.
5. Camera OFF can be discarded. `_poll_saccade_target` in
   `Applications/sifta_what_alice_sees_widget.py` rejects a named target using
   capture_allowed before it resolves the explicit OFF sentinel. Handle OFF
   first. Test OFF through the polling path, not only combo selection.
6. Missing harness selection silently changes models. In
   `System/swarm_ollama_harness_sync.py`, `_repair_missing_default` selects the
   first live tag if the previous model vanished. This violates the handoff's
   independent-selection contract. Preserve the unavailable selection with a
   visible actionable state, or require an explicit fallback preference.
   Update the existing test that currently expects the silent replacement.

The first pass's 111 passing tests remain a reported historical result. They
did not establish the behaviors above. No full repository health assessment
or independent rerun of those 111 tests was performed in this planning review.

## Work order and acceptance

### A. Finish attachment conversion

Fix findings 1-3. Normalize once per accepted turn and reuse those exact bytes
for transport, MIME and memory metadata: Talk currently rereads and encodes
the same image twice, and computes MIME separately from source bytes. Avoid a
source-file change yielding mismatched evidence. Retain original source.
Run processing away from the GUI thread. Cover desktop and the actual web
upload validator; inspect that path before claiming both surfaces support HEIC.
Failure must retain the draft for retry and prevent a stale camera/browser
description. Success must clear the one-turn attachment. No raw private image
or EXIF in public Git; use a small generated fixture only.

Acceptance: real HEIC -> oriented decodable JPEG -> model request captures
those bytes, correct MIME, source unchanged, receipt links hashes; error and
retry lifecycle tests pass. An actual local model request on synthetic data is
useful evidence when idle; report its model and observed output separately.

### B. Finish camera reliability

Fix finding 5 and remaining camera items in the original WCT handoff. Run its
camera suite and diagnose the six previously reported photo/voice failures.
Add checks for stale preview removal, device attribution, raw camera index
ordering, hot plug, sleep/wake and absence of LED-wink capture restarts.
Once the owner/harness turn is idle, use the established safe restart path and
verify a fresh runtime policy receipt. If an active turn prevents restart,
record that exact remaining gate and continue independent work.

### C. Implement a real local vision adapter

Fix finding 4. Keep selected text cortex and arm selections independent.
For a text-only owner cortex, one bounded background vision request sends the
normalized image plus the specific question to the installed preferred
MiniCPM candidate. Return scoped evidence containing image hash, turn/session,
model digest, time, observations and uncertainty. The original cortex composes
from that evidence without image bytes. For a native vision cortex, preserve
the direct route. Evidence is fallible data and must not carry tool authority.
On vision failure, surface that failure without inventing an answer.

Cache only within authorized scope, keyed by image hash, task/crop,
preprocessing and model digest. Invalidate on changed question or source.
Use a request generation ID so switching cortex/session cannot attach a stale
answer to the new turn. Coordinate resident models and requests across Talk
and harness on the 24 GB laptop. Do not unload a model serving another request.
The screenshot shows Talk rerouting to the 17 GB coder while the harness also
uses it; inspect memory pressure and queue state before adding another load.

Acceptance: Aries/text-only with installed MiniCPM, native VLM direct route,
no capable installed eye, late response after switch, owner/visitor isolation,
repeat image/new question, bounded cancellation and UI responsiveness. Report
actual latency/memory/accuracy; no fastest/best claim from model names.

### D. Complete harness and model refresh

Fix finding 6. Reproduce the prior lmstudio-local credential error using its
actual provider registration and outgoing request. Keep credentials private;
do not disable auth globally. Prove Ollama and optional LM Studio are separate
providers and both show honest installed/served availability. Preserve cloud
entries, independent valid selections and current drafts. Read the harness's
AGENTS and provider schema before editing; verify the running server reloads
the registry, since editing YAML alone may not refresh the visible menu.

The owner has already submitted a test to the running harness. Inspect that
run and its diff/receipts before launching anything else or changing shared
files. The screenshot proves a request is processing; it does not prove tool
execution or a successful patch. Record actual tool calls, paths, exit codes,
tests and output. If needed, give it only the small fixture job below next.

### E. Complete image delivery and UI verification

Run the original handoff's image-delivery job through the real local chorus
and public page. Require actual preview pixels, valid download bytes, history
reload persistence and session isolation. Explain blocked public checks with
the precise failing request. Keep the #SIFTA caption and preserve history.
Finish the shared local/web theme and Display wiring, scrolling and mobile
layout using the existing pending changes. Keep single-demo robotics layout.

### F. Review remaining pending features and release

Inventory every modified, untracked and nested-repository path. Group into
attachments/vision, camera, model providers, time/location, phone link, web
delivery/theme, robotics/economy, documentation and unrelated/unknown work.
For each record intended behavior, source diff, dependencies, tests and status.
Review the time/location, journal/schedule, body-health and repair gates from
the original handoff. Stale balance, disconnected organs and queued work need
actual causes before marking healthy. No synthetic passing receipts.

README book and eval matrix must reflect these reviewed outcomes, including
what requires optional dependencies and a restart. Append WCT/tournament
results and four-ledger coordination receipts with truthful model identity.
Run tools/whats_left.py after updating the tournament's current open list.

Observed repository: branch main; origin is
https://github.com/antonpictures/ANTON-SIFTA.git. Recheck before publishing.
The owner authorizes commit and push of the reviewed release. A dirty worktree
alone is not a blocker: review/group changes and commit explicit paths/hunks.
Do not run git add . across private artifacts or unknown files. Check nested
Vendor/alice-cli and untracked deepseek-harness-master packaging deliberately;
do not accidentally commit an unusable embedded repository, node_modules,
build caches or private settings. Preserve attribution and licenses.

Before push: inspect staged diff, scan staged content for credentials/private
data, verify required source/dependency files are present, run grouped tests,
git diff --check and the required fresh health checks. Exercise installation
from the staged/committed tree in an isolated checkout with no owner state.
Inspect remote changes and integrate without force push or overwriting user
work. Push verified commits using the existing remote/branch policy, report
commit IDs and confirm remote acknowledgement. If a required gate fails,
report the exact gate and keep fixing it; do not give a generic dirty-tree
excuse. Never hide remaining failed gates to obtain publication.

## Next small prompt for the existing harness

After its current run finishes and Luna reviews it, use this prompt. Enforce
scratch-only access in the runner; prompt instructions alone are not isolation.

```text
Work only in the disposable fixture directory supplied by Luna. Implement
display_model_size(size_bytes): decimal GB with one decimal place for a
nonnegative integer byte count; "unknown" for bool, None, strings, fractions,
negative numbers or nonfinite values. Add tests for 0, 6100000000, 17000000000
and invalid inputs. Use actual read/edit/test tools; report exact changed paths,
test command, exit code and diff. No package installation, network calls,
live SIFTA edits or git push. Stop after this fixture job.
```

Luna supplies independent hidden edge-case tests and reviews output before
executing candidate code. Compare the requested 17 GB Ornith with one smaller
installed coder using the same fixture and resource limits. Start one trial
per model; expand only if useful. Report correctness, scope compliance, tool
execution, latency and memory. Stop on memory pressure or repeated timeout.
Do not benchmark concurrently with owner conversation or another coding run.

## Research work for Astra after this release review

Temporal visual state, uncertainty calibration, active perception and motor
prediction still need measured experiments against baselines. Preserve the
existing research references and SIMULATED motor boundaries. Physical joint
control needs a hardware-specific driver, limits, emergency stop and outcome
verification. A language model name or passing UI tests cannot close these
research questions. Escalate a reproducible failure or design decision with
evidence; do not manufacture a general-intelligence completion receipt.
