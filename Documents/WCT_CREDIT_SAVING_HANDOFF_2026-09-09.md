# We Code Together: next coding rounds

## Romanian TTS language routing fixed (2026-09-17)

Owner report: "when Alice responds in Romanian in text the voice is still in
english." Root cause was a silent voice lookup mismatch, twice over.

Three mouths each decided the Romanian voice independently, and two of them
compared the exact string `"Ioana"`. This Mac's installed voice is reported by
`say -v ?` as `Ioana (Romanian (Romania))`, so the exact check never matched and
Romanian text fell through to the English default (Samantha). The public web
mouth (`swarm_web_global_chat_speech_worker.py`) had no language detection at
all, so every `/speak` reply used the English default.

Fix: one shared decision point, `System/swarm_speech_language.py`. It resolves a
voice by locale family (`ro`) rather than a remembered name, reuses the
cortex-side `swarm_reply_language.detect_owner_language` so mouth and brain
agree, keeps the owner's chosen voice for English, and falls back to the default
when no matching voice is installed instead of going silent. Wired into the Talk
widget (`_tts_voice_for_text`), Broca (`_speak`), and the web speech worker.

Evidence: `python3 -m pytest -q tests/test_speech_language.py
tests/test_romanian_tts_routing.py tests/test_swarm_web_global_chat_speech_worker.py
tests/test_alice_voice_picker.py tests/test_swarm_reply_language.py -W error` ->
**92 passed**. The wider speech set reported **123 passed**. `say -v "Ioana
(Romanian (Romania))" -o <tmpfile>` returned 0 and produced 75,608 bytes of
audio, confirming the resolved name is real. The launchd service
`com.sifta.web-global-chat-speech-worker` was restarted (PID 67314) so the live
worker loads the fix.

Eval matrix: new row `SUFL-09 speech_language_voice_routing` (COVERED/wired) in
`System/swarm_eval_matrix_evidence.py`, pointing at the module and tests above.
`validate_world_to_field_audit()` returns ok. No full-suite run was attempted;
collection is still stopped by the pre-existing `inference_economy.py` hash
mismatch in `Kernel/origin_gate.py`, which was not bypassed.


## Current execution correction: rover local loop, 2026-09-15

This supersedes the completeness implications of commit dac78d8dd. Its gateway
never polled UDP after handshake, dropped command lifetime at claim, allowed a
turn-only command around sensor checks, and treated X as forward. Direct review
of David's AutoNavigator at 5fdd0351fc20dc3697e913dee46aaeac5ebfb63b establishes
X lateral / Y forward and a minimum eight-point scan. These are now corrected.

Implemented: dedicated single-owner UDP thread, continuous bounded sensor polls,
latest-observation HTTPS upload with server sequence continuation, fresh session
and scan reset on renewal, monotonic command lifetime reduced by complete request
latency, device scan age included in freshness, neutral at local expiry/hazard
and shutdown, and invalidation of pending commands when control is reissued.
HTTPS work cannot block the UDP monitor. Upload timestamps explicitly mean
gateway receipt, not synchronized camera/LiDAR capture. Receipt states still
distinguish sent output from physical motion.

Verification: `python3 -m pytest -q -W error tests/test_david_rover_gateway.py
tests/test_stigmerobotics_rvr1.py tests/test_remote_rover_link.py` -> 34 passed.
The UDP loopback test sends real authenticated datagrams on localhost, receives
an eight-point scan and verifies short drive followed by neutral. Separate tests
cover stale device age, sparse scans, blocked paths during WAN inactivity,
delayed transport/ACK expiry, turn-only bypass and control renewal revocation.

Next required software work: integrate David's curved-path avoidance for forward
turning (front-only data does not authorize reverse), provide operator STOP and
revocation that clear queued motion, bind control to a local consent/boot lease,
correlate firmware applied/timed-out/released feedback, bound persistent command
history, and finish phone-to-rover stationary chat/TTS. Audit the published tree's
missing phone/auth dependencies before deployment; the working tree's passing
tests do not certify a clean checkout. The global test collection still has the
previously observed inference_economy integrity mismatch; no bypass was added.
David's flashed version, LAN provisioning and real two-network acceptance remain
external requirements. Overall driving-and-chat goal is open.

## FINAL LUNA HANDOFF: connect David's rover end to end

Owner requests planning here so Luna can execute the next round. Read this
entry, then the pinned protocol findings immediately below. This is the current
execution order; consolidate older rover jobs under it instead of duplicating
them. Objective remains: David's car drives around his apartment and converses
with him through SIFTA on George's Mac and authenticated stigmergicoin.com.

### Starting state and first job

`System/stigmerobotics_rvr1.py` is the isolated RVR1 adapter from the interrupted
execution round. It implements packet encoding/authentication, finite velocity
payloads, bounded LiDAR assembly, an explicit UDP session client and a
fail-closed front-clearance gate. The adapter and remote-link tests now pass;
this remains simulator/software evidence, not firmware interoperability or
physical movement evidence. David's flashed revision, LAN address, private key,
stop hardware and measured limits are still deployment inputs.

1. Finish ORNITH-ROVER-RVR1-01 yourself if Ornith is unavailable. Create
   `tests/test_stigmerobotics_rvr1.py` with independently constructed known wire
   vectors plus a loopback UDP firmware simulator (never a real rover address).
   Cover peer/session filtering, CRC and HMAC, missing keys, incorrect lengths,
   handshake acknowledgment, packet loss/timeouts, sequence wrap, zero-timeout
   rejection and advertised limits. Validate non-finite/boolean numeric input.
   No send should occur on failed validation. "sent" never means "applied".
2. Review the draft's lifecycle: fresh session on reconnect/reboot; reset scan
   assembler on session changes; expire handshake/telemetry state explicitly;
   resource cleanup after failed open; distinguish handshake CONTROL_STATUS from
   delayed command ACKs. A remote restart must not resurrect a prior drive goal.
   Heartbeat/session renewal must not silently refresh a movement lease.
3. Test complete/incomplete/reordered/duplicate LiDAR scans, wraparound,
   stale first chunks and stale partial assemblies. Enforce total observation
   size before HTTPS upload. Battery/status lack unique capture sequence in
   this firmware: report that freshness/replay limitation, never fabricate
   capture timestamps or pretend HMAC alone proves a fresh observation.

### Gateway, conversation and driving

4. Extend `System/stigmerobotics_remote_link.py` and existing
   `tests/test_remote_rover_link.py`. Add a runnable David-side gateway entrypoint
   under `scripts/` that reads private configuration, performs RVR1 handshake,
   publishes bounded sensor observations and renews the telemetry session.
   Persist HTTPS envelope sequences and retry the identical envelope after
   uncertainty. Keep WAN upload latency out of the LAN receive/control loop.
   Provide a simulation mode and explicit configuration errors, not guessed IPs.
5. Complete stationary chat first: paired phone captures David's speech, uses
   existing STT/chat/reply routes, displays Alice's response and plays TTS.
   Link phone and rover under the authorized operator without merging device
   timestamps, owner memory or visitor identities. Typed dialogue stays primary;
   ambient media cannot become a drive instruction. Verify actual audio round
   trip separately from JSON-only tests.
6. Add a separately scoped, expiring command channel to
   `System/chorus_node_server.py` and RemoteRoverGateway. Use one active control
   lease, command IDs, bounded intent lifetime and correlated ACKs. Existing
   telemetry bearer must remain unable to command movement. Reject expired,
   duplicate and out-of-order goals; reconnect must not replay old motion.
   Expose STOP/status in the coin page and revoke control on explicit stop.
7. Implement local deterministic execution of short movement goals. Keep the
   finite motor watchdog and verify obstacle stopping on the EXTERNAL path:
   firmware currently bypasses AutoNavigator there. Agree the firmware or LAN
   controller hook with David and test it. Front-only LiDAR does not establish
   free space behind the car; require relevant coverage for reverse/turn paths.
   Stop on stale sensor/control lease, gateway crash, lost WAN intent and
   failed local link. Never use LLM inference cadence as the motor heartbeat.
8. Fault simulator acceptance: dropped/reordered/auth-failed packets, process
   death, stale sensors, firmware reboot, two competing operators, WEB/AUTO
   takeover, failed STOP confirmation and a long model response. Assert outputs
   go neutral within the configured bound, with no automatic motion restart.
   Keep physical speed/distance unverified until measured; applied ACK means
   controller outputs, not measured travel.

### Deployment and completion evidence

9. Prepare instructions for David: flashed source revision, board/LAN address,
   gateway host, private PSK provisioning, scoped coin pairing, camera access,
   and local operating limits. These are remaining deployment inputs; the repo
   and protocol have already arrived. Do not ask for the video/repo again.
   No secret values in tickets, URLs, screenshots, code or public README.
10. Validate on the two real home networks: stationary chat, fresh LiDAR and
    camera evidence, short locally supervised drive, STOP, disconnect and
    obstacle response. Record measured latency and outcomes. Physical tests
    require David present and the actual device configuration; no simulated
    result closes this requirement. Continue independent software work while
    waiting for those inputs.
11. Update this handoff, existing eval matrix/WHAT IS LEFT and READMEBOOK with
    exact diffs, executed commands, pass/fail counts, source revision and live
    evidence. Keep private firmware source out of published docs. Review staged
    scope before using the owner's existing publish authorization; preserve all
    unrelated dirty work. Report completed, unverified and blocked items
    explicitly. Do not mark the overall goal complete until driving AND chat
    on David's real rover have been demonstrated.

Start command for Luna: Read FINAL LUNA HANDOFF in this file, inspect the current
draft and git diff, implement steps 1-8 in order with tests, prepare step 9, and
perform steps 10-11 when the required live configuration is available. If Ornith
is used, assign only one independent simulator/test job at a time and verify its
actual files and exit codes. Do not stop after another planning-only response.

### Execution receipt: RVR1 control path, 2026-09-15

Implemented in this round: `System/stigmerobotics_rvr1.py` now records complete
LiDAR freshness and rejects nonzero movement when the front path is stale,
blocked or unobserved; reverse remains blocked because the documented scan is
front-only. `System/stigmerobotics_remote_link.py` now migrates existing state
and provides a separate five-minute owner control lease, one-shot expiring
command queue, atomic claim and correlated acknowledgement. The telemetry
bearer cannot arm, enqueue, claim or acknowledge commands. The David-side
entrypoint is `scripts/david_rover_gateway.py`; it performs the RVR1 handshake,
passes commands through the local gate and acknowledges only adapter outcomes.
The HTTP routes are `/api/rover/arm`, `/api/rover/command`,
`/api/rover/commands` and `/api/rover/command/ack` on the existing authenticated
coin host. No live route, tunnel, firmware or physical motor was changed.

Receipt: `python3 -m pytest -q tests/test_stigmerobotics_rvr1.py
tests/test_remote_rover_link.py` -> **27 passed**. The remaining gates are
David's firmware/LAN provisioning, physical stop and obstacle tests, and the
two-home-network chat plus supervised movement acceptance. Do not interpret a
queued or adapter-accepted command as measured travel.

## Current rover plan: David's repository received (2026-09-15)

This entry supersedes earlier statements that David's repository/protocol is
still missing. Owner supplied https://github.com/davidk-ro/E_Motion-Rover.
The repository is PRIVATE and accessible through the owner's GitHub login.
Reviewed main commit: `5fdd0351fc20dc3697e913dee46aaeac5ebfb63b`.
Keep private source and credentials out of public README/release material.
This round updates the plan; no rover connection, movement or firmware flash ran.

### Verified source and integration constraints

- README: two boards, ESP32-Servo plus LilyGO T-Camera S3, M1C1 LiDAR,
  optional SSD1306 OLED and a monitored 4S battery. Servo controls outputs;
  T-Camera supplies camera/web and external control.
- `Documentatie/Rover-UDP-protocol.md`, `tools/rover_client.py`, and
  `ESP32-Tcamera-S3/src/external_control.cpp`: RVR1 over configurable UDP 4210.
  Header is little-endian `<4sBBHI>`, followed by payload, CRC32 and a 16-byte
  truncated HMAC-SHA256 tag. HELLO -> CAPABILITIES challenge -> SESSION_OPEN
  binds a nonzero session to client IP/port. ROVER_CONTROL_PSK is a local secret.
  Authentication provides integrity, not encryption.
- CMD_VELOCITY payload `<hhHH>`: linear mm/s, angular mrad/s, timeout ms,
  sequence modulo 65536. Zero timeout disables expiration. Firmware output
  clamps of 1000 mm/s and 1667 mrad/s are limits, not indoor operating targets.
  Reference client sends at 20 Hz with 250 ms timeout; use finite watchdogs for
  remote operation. STOP is a zero-velocity command with a fresh sequence.
- CONTROL_STATUS distinguishes accepted, applied, timed_out, stale_sequence,
  released. Applied means servo outputs applied; no encoders/odometry prove
  actual travel. Never turn that acknowledgment into measured distance/speed.
- LiDAR is a front 180-degree Cartesian sector in millimetres, at most 24
  points per RVR1 chunk with scan/chunk IDs and age. Battery is mV plus age.
  RLOG snapshots include boot IDs and monotonic milliseconds; reconstruct
  timing explicitly instead of assuming these are Unix timestamps.
- `ESP32-Tcamera-S3/src/camera_app.cpp`: HTTP 80 exposes /capture, /snap,
  /status, /lidar, /drive, /auto and /log; /stream is on 81. HTTP endpoints
  have no built-in authentication. Keep them behind the paired gateway.
- CRITICAL: `ESP32-Tcamera-S3/src/main.cpp` sends external velocity then
  returns when externalControlOwnsDrive(); AutoNavigator runs later only for
  the local AUTO branch. UDP external driving does not inherit that obstacle
  avoidance. A finite timeout stops lost commands but does not avoid obstacles.
- `Documentatie/Rover-UART-protocol.md`: RSP2 at 921600 baud between boards;
  shared implementation is `shared/RoverLink/src/`. README's sentence about
  two library copies is stale; follow the actual shared implementation.

### Connection to Alice

Use the existing `System/stigmerobotics_remote_link.py` RemoteRoverGateway and
RemoteRoverLink plus `/api/rover/*` in `System/chorus_node_server.py`.
David-side gateway talks RVR1 on the rover LAN and makes outbound authenticated
HTTPS connections to stigmergicoin.com / Mac SIFTA. The ordinary browser page
cannot send raw UDP. A website/tunnel alone does not bridge two private LANs.
Keep the UDP PSK on the authorized gateway/rover, distinct from the scoped SIFTA
rover token. Provision the David-side gateway explicitly; do not copy credentials
from the user's Mac or expose them to browser JavaScript. A VPN is an optional
deployment alternative, not a reason to expose HTTP/UDP ports publicly.

Phone is an optional mounted camera/microphone/speaker and David's operator
surface. Board camera and phone camera remain separate timestamped sources.
First demo: stationary sensor capture, David speaks, Alice replies on the phone.
Second demo: short locally supervised move, STOP and receipt verification.
Autonomous room navigation follows measured local avoidance/stop behavior.
The 5-20 second observation cadence is independent of the fast local drive
loop. Expired intent, network loss or stale sensors must not refresh movement.

### Exact coding order

1. ORNITH-ROVER-RVR1-01: implement an isolated optional protocol adapter
   `System/stigmerobotics_rvr1.py` and offline `tests/test_stigmerobotics_rvr1.py`.
   Use pinned source as specification; no firmware copying/publication without
   checking David's reuse permission (GitHub reports no license). Validate
   lengths, CRC/HMAC, nonempty keys, session and peer IP/port, handshake state,
   sequence wrap/replay, unit bounds and finite command timeout. Reference
   client's receive_available prints packets without peer/session filtering;
   do not inherit that gap. Test synthetic packets only; no drive command runs.
2. LUNA-ROVER-GATEWAY-02: wire adapter observations through existing
   RemoteRoverGateway. Bound/reassemble LiDAR scans, reject incomplete/stale
   chunks, preserve boot/session/device/capture provenance, encrypt WAN traffic,
   scope tokens, and use bounded snapshot/log sizes and timeouts. Keep existing
   telemetry credentials read-only; introduce a separate scoped command channel
   with command ID, expiry, arm lease and acknowledgments. No existing motion
   support should be inferred from the telemetry gateway.
3. ORNITH-ROVER-FAULTS-03: simulator tests for lost/duplicate/reordered packets,
   invalid auth, old session, wraparound, reset, missing chunks, stale LiDAR,
   failed STOP acknowledgment, WAN outage, old goal after reconnect, control
   takeover by WEB/AUTO and two paired devices. Never replay queued old motion.
4. LUNA-ROVER-LOCAL-04: agree with David where the external-drive local obstacle
   check runs (firmware or deterministic LAN controller). Stop on stale/missing
   hazard data; verify blind rear/side areas before reverse/turn commands.
   Measure command-to-neutral latency, including gateway crash and UART loss.
   A Mac LLM across the Internet must not supply the motor heartbeat.
5. LUNA-ROVER-PHONE-05: reuse the current coin page for pairing/status, existing
   sensor controls, spoken conversation, and a visible STOP while driving.
   Use the phone for speech until board audio I/O is actually verified. Preserve
   owner/visitor separation and route ambient audio as observations, not driving
   instructions. Show accepted/applied/observed outcomes accurately.
6. ASTRA review: inspect diffs/receipts and David's on-site results, then update
   existing eval matrix rows and README with verified capability only. Do not
   create duplicate robot/phone identities or mark simulation as a house demo.

Remaining external information: installed/flashed commit, rover LAN address,
authorized gateway host, privately provisioned PSK, camera access, dimensions/
speed/turn calibration and David's supervised test availability. Repository
and protocol are RECEIVED; deployment and physical verification remain pending.

Model clutter correction: removed only `krishairnd/G4U:latest` alias using
`ollama rm`; retained `krishairnd/Gemma-4-Uncensored:latest`, ID abb8e56b1d85.
Both manifests had identical SHA-256 before removal, so they shared the model
weights. No 6.3 GB duplicate existed. Full short-name migration is still deferred
because code/configuration refer to the original runtime tag.

## 2026-09-15: IMAGE-INTENT-01 / movie posters and truthful Alice replies

PLAN ONLY, owner-requested. Extend System/swarm_web_image_service.py and its
existing tests/test_web_cortex_photo_isolation.py and test_web_image_variation.py;
trace dispatch in System/swarm_web_global_chat_night_worker.py and capability
context in System/swarm_web_global_chat_gate.py. No deployment/DNS changes.

Observed source: media_intent() checks movie/film/video anywhere in the body
before image intent. Both "create a movie poster" and "create a photo of a movie
poster" therefore take VIDEO_UNAVAILABLE. The supplied dialogue also shows a
text-only promise of generation without a confirmed dispatch. Backend failure
is a separate defect: fixing intent does not establish that rendering works.

Coding requirements:
1. Resolve the requested output, not isolated subject words. A movie poster,
   film-poster design, or photo of a poster is a still image: dispatch once on
   the first clear request, without asking the user to repeat "photo". A poster
   can be an illustration or graphic, not necessarily a photograph. Preserve the
   requested title "Great Expectations:)" and punctuation; do not assume the
   Dickens novel, an existing adaptation or its mood without supporting context.
   Actual video/animated-poster requests remain video. Mixed/unclear requests
   get a focused clarification; neither a blanket movie blacklist nor a blanket
   poster override is sufficient. Words inside quoted titles are subject data.
2. Handle a same-session correction such as "I meant a still movie poster" by
   resolving the prior request and entering the real image dispatch path. Do not
   merely produce text saying "I am generating". Preserve session isolation,
   explicit-request authorization and turn/job idempotency.
3. Use Alice's first-person voice in visible busy/unavailable/failure/success
   messages, not "Bonsai could not finish" or "my Bonsai photo backend". Keep
   real provider/model/error details in diagnostic metadata for troubleshooting;
   do not falsify provenance. Review capability_prompt, _contextual_image_reply,
   public display fields and generated-image filenames for accidental branding.
   If asked which backend is used, answer accurately.
4. Ground varied wording in structured job state. Example failure: "I couldn't
   finish that image. No poster was generated. You can ask me to try again."
   Say "I'm trying again" only after a real, authorized retry is accepted. Use
   the existing conversation renderer where practical, with a truthful bounded
   fallback; variation alone is not reasoning. Do not add an expensive extra LLM
   call merely to randomize error text. Persist the wording for the same turn so
   polling/replay stays stable; wording may differ across distinct requests.
5. Diagnose the actual IMAGE_FAILED/IMAGE_BACKEND_UNAVAILABLE cause using safe
   local status and sanitized error records. No fabricated artifact, silent
   cloud fallback, unlimited GPU retry, or success before verified image bytes.

Acceptance: execute all three supplied /create prompts; test movie/film poster,
photo-of-poster, an image whose quoted title contains "video", actual movie/video
creation, animated poster, mixed intent and correction follow-up. Mock the backend
to verify one generation call for a still request and none for unsupported video.
Test busy/unavailable/render-failure/success and retry idempotency. Assert public
copy is first-person, omits backend branding by default and never invents a running
job, retry or image. Keep cross-session artifact isolation. Offline mocks and a
live generation smoke are separate results; mark live testing pending if not run.

## 2026-09-15: Ornith transport recovery / existing ORNITH-02

USER_REPORTED failed turn: initial misspelled workspace path, then the correct
handoff was read, followed by five model retries and TRANSPORT "Stream ended
without finish_reason". This report does not identify the transport root cause
or establish any completed edits. The path typo and stream failure are separate.

For the next coding arm: use the actual cwd /Users/ioanganton/Music/ANTON_SIFTA
and relative Documents/WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md; do not reconstruct
an absolute path from prose. Resume ORNITH-02 from current files/diffs, not from
the earlier pasted "plan only" response. Owner requested implementation there;
this current update itself is plan-only and dispatches nothing.

Inspect the existing local Harness/Ollama stream logs and adapter termination
handling with bounded reads. Keep credential/prompt bodies out of diagnostic
reports. Add an interrupted-stream regression at the actual adapter boundary:
missing finish_reason is incomplete/error, not success. Do not fabricate a stop
marker, endlessly retry, switch to paid cloud, or replay tool actions blindly.
Reconcile durable session/tool records before resuming; retain partial output as
incomplete. Use a compact one-deliverable prompt and existing bounded backoff.
Record whether the failure was transport, model termination, timeout, resource
pressure or still unknown, based on evidence rather than guessing.

## 2026-09-15: tester feedback and Ornith checkpoint

Focused check this round: `python3 -m pytest -q
tests/test_swarm_keyboard_acoustic_gate.py tests/test_talk_keyboard_ingress.py`
returned 13 passed in 5.97s. Handoff diff whitespace check passed. These tests
do not close the worker/context wiring gaps identified below. Plan update only;
no runtime edits or model dispatch in this round.

Owner supplied private tester correspondence. Keep the raw conversation, contact
details and institutional names out of public documentation and test fixtures.
Summarized feedback: a visitor reported an outage, later reported improved
responses, and proposed commercial/academic pilots. Those are USER_REPORTED
observations and proposals, not an institutional agreement, verified revenue,
validated political advice, or evidence of AGI. A reported painting requires an
actual artifact/generation receipt before claiming this capability was tested.
Do not contact anyone, publish testimonials or create billing from these notes.

ORNITH-02 checkpoint, inspected on disk: the classifier now accepts and returns
utterance/source/session/clock/window metadata; the duplicate keyword-only
separator is absent. However, the live widget still calls it with
_LAST_UTTERANCE_AUDIO[0] and time.time(), passing none of that context. Missing
fields plus scope="utterance" do not establish capture provenance. The default
monotonic clock label also conflicts with this wall-clock call. This is a partial
schema change, NOT completion of the per-utterance wiring job.

Next work stays ORNITH-02 below, not a new duplicate task. Complete worker/result
binding before marketing or cosmetic changes. Avoid blanket "all acceptance paths
verified" claims: the current callback fixtures execute selected source regions,
not the complete Qt application with live microphone input.

Fold these follow-ups into the existing phone/grounding/verification jobs:
- ORNITH-03: test unavailable Mac/backend, 502, reconnect and expired heartbeat.
  Show a visible offline/stale state and retry with bounded backoff; preserve
  explicit typed messages without replaying duplicate actions. A disconnected
  server cannot itself render an offline page: distinguish cached-client recovery
  from a first-load tunnel error. Leave working DNS/deployment untouched.
- ORNITH-04/05: distinguish source traceability from factual accuracy. Never sell
  a "truth guarantee" or elimination of hallucinations from a receipt alone.
  Give answers evidence links, retrieval dates and uncertainty when available;
  evaluate unsupported-claim and cross-session privacy regressions. Draft pilot
  requirements only after measurable reliability, consent and data isolation.
- Identity: owner requests display name Alice and node label GTH4921YP3. Reuse
  the existing owner/node identity source rather than hard-coding this serial
  into all nodes. Keep owner-supplied labels separate from verified hardware/key
  binding, and raw serials private by default on visitor-facing pages. A serial
  string is not authentication or a cryptographic uniqueness proof.

The owner's account of developing SIFTA's swarm ideas is project history to
document from dated commits if requested. Similar news terminology does not prove
others adopted this project. No external news or research verification performed
in this credit-saving update; no medical conclusions drawn from the chat.

## Bridge status: callback repair and local Ornith continuation

Verification: 86 passed in 30.02s across test_talk_keyboard_ingress,
test_swarm_dsh_wct_bridge, test_swarm_keyboard_acoustic_gate,
test_typed_turn_queue, test_typed_ambient_recall and test_swarm_media_ingress_gate.
git diff --check passed. This is a focused suite, not the entire repository.
ORNITH-01..05 were accepted by the local Host under dispatch
b014cf67e93ca0316c118e67285cba1ff21ea14c7df7071cb3b45438dea9de6b,
session session-c02efb6e-fb26-484c-b4d0-9a4365598726. A subsequent status read
reported running=true. Completion and patch verification remain pending.

The current checkout fixes the undefined _typed_turn in _on_stt_done,
initializes _acoustic_fingerprint in _start_brain, passes its snapshot through
the queued callback, and checks busy before consuming deferred voice audio.
The keyboard gate precedes all _append_user_line calls. Executed source fixtures
cover typed/voice admission, queued fingerprint transfer and busy queue drain;
they do not boot the full Qt desktop or validate real-world speech accuracy.
ORNITH-01 callback repair is verified by the focused source fixtures; Ornith's
recorded follow-up reports 10 passed. Stop rechecking the same guard. This does
not establish full Qt integration or real speech accuracy.
ORNITH-02's global audio/time association and receipt-writer limitations remain.

Harness adapter: System/swarm_dsh_wct_bridge.py, invoked from
deepseek-harness-master/scripts/sifta-wct.py. It uses the existing local Host API,
checks workspace and selected local Ornith, preserves permission settings, logs
before delivery, and never retries an ambiguous or duplicate assignment.
Accepted means queued, not completed. No automatic background scheduler exists.
The exception-handler and shared-root comment review edits are present on disk.
A narrowed exception set is intentional, not equivalent to catching Exception.

Next Ornith: implement ORNITH-02 now. The last inspected session is idle with
turn reason completed; its report covers ORNITH-01, not all five assignments.
Use the actual files/tests; avoid another notes-only loop.
Record each tested patch in this handoff. Do not change the working website's
deployment, reload the shared desktop, push git, or operate David's motors.

Usage (existing local session ID, no new session or model switch):
`python3 deepseek-harness-master/scripts/sifta-wct.py preview --session SESSION --jobs ORNITH-01 ORNITH-02`
Use `dispatch` in place of `preview` to submit once; `status --session SESSION`
reports activity and the last turn's ending, not proof of passing tests.

## ACTIVE ORNITH EXECUTION 2026-09-14: test, repair, report

Owner assigns this round to Ornith only. This overrides the Luna-only assignment
below for the existing jobs; keep their IDs and acceptance requirements. No
runtime changes made by this assignment. Previous completion labels are under
review. Work sequentially on the shared checkout; inspect current diffs first.
The requested intelligence work is evidence-grounded perception, recall and
action routing. Demonstrate those capabilities through executable tests.

### Start here: ORNITH-01 / callback regression (highest priority)

Files: Applications/sifta_talk_to_alice_widget.py and
tests/test_talk_keyboard_ingress.py. Read _on_stt_done and _start_brain only to
start; use bounded reads, then inspect their direct dependencies as needed.

Observed source: the added keyboard guard in _on_stt_done references _typed_turn,
but its parameter is typed_turn; the _typed_turn assignment is in _start_brain.
The new AST test asserts the wrong identifier and does not execute the callback.
First reproduce the exception with an executed callback/control-flow fixture,
then fix the variable and ordering. Cover both typed and spoken ingress.

Also inspect the acoustic fingerprint transfer: Luna moved its read/clear into
_on_stt_done and removed the initialization in _start_brain, which still consumes
_acoustic_fingerprint later. Preserve the current utterance's evidence across the
queued callback; verify no undefined value or premature clear. Place noise/media
routing before owner-history writes, nonce binding and effector calls. An
assertion that merely finds SOME later display call is insufficient.

Acceptance: execute the affected paths with spies for history, cortex, TTS and
effectors. Typed input works even with no audio; detected clicks reach ambient
only; eligible speech reaches the next stage with its own fingerprint; no
exception or swallowed NameError. Do not weaken tests to match faulty code.

RECEIPT (ORNITH-01, verified): `python -m pytest tests/test_talk_keyboard_ingress.py` → 10 passed.
Source verified live on disk: line 39134 `if not _typed_turn and _LAST_UTTERANCE_AUDIO:` guards
`classify_keyboard_audio` (lines 39136-39161) so typed turns bypass the ambient gate and proceed;
`_typed_turn = bool(typed_turn)` is bound at 39113. All four acceptance paths execute with the System
mock injected — typed (no audio) admitted, clicks→ambient only, speech→next stage, no swallowed errors.
No code change required: ordering/guard already correct.

### ORNITH-02 / finish KEYBOARD-WORLD-01

Historical checkpoint before the 2026-09-15 implementation receipt above:
connect the worker, not just the return dictionary.
The new nullable fields are present, but the live caller still supplies shared
last audio and completion time. Create the ID/source/session/window at capture,
carry the same record with its transcription result, and classify that clip's
features. Do not synthesize an ID or window at _on_stt_done to disguise missing
provenance. Validate finite ordered timestamps in one explicit clock domain;
unknown/mismatched provenance must remain uncertain, not silently labeled bound.
Add a regression: capture A, capture B, complete A after B; A must retain A's
audio/features, key-event interval and IDs. Also test missing context, inverted
windows, NaN and wall-clock/monotonic mismatch. Report wiring as complete only
when the executed worker-to-callback path passes, not just ast.parse or field
presence. Preserve the remaining physical-key, worker-thread, heuristic-score
and locked-writer requirements below.

The implementation receipt above closes this job's code slice. The next
remaining job is ORNITH-03, not another verification of ORNITH-01.
Work in small tested increments in this order:
1. Add a bounded per-utterance evidence record: utterance ID, source/session,
   capture start/end with explicit clock domain, sample rate and audio features.
   Bind it before transcription; carry it with that worker's result. No lookup
   of shared last-audio or STT completion time to decide which clip was heard.
2. Record actual key-press events without key values or typed content. Ignore
   paste, programmatic edits and events outside that clip/device/time interval.
   Move bounded feature extraction off the GUI thread; unknown/mixed evidence
   must not discard speech. Do not infer attention or identify a speaker from keys.
3. Report heuristic_score, not calibrated confidence. Use the existing locked
   ledger append contract and surface append failure; never claim a saved receipt
   when storage failed. Keep fixtures synthetic and metadata-only in receipts.
4. Execute delayed/out-of-order, cross-device, speech-plus-click and storage-failure
   regressions, then the existing keyboard/callback/typed-ambient tests. If no
   consented real speech recording exists, mark that validation pending rather
   than inventing evidence. Report exact changes and commands here.

First tool action: read the classifier and locate the STT worker construction,
result signal and physical key event hook using rg and bounded source reads.
Then implement increment 1 with a failing regression. Do not ask for another job
or stop at a notes-only answer. Preserve existing edits and approval controls.

Files: System/swarm_keyboard_acoustic_gate.py, its tests and the callback above.
Current wiring uses the shared _LAST_UTTERANCE_AUDIO and completion time.time(),
not a captured utterance ID/interval. Two arbitrary text changes count as typing;
the score is presented as confidence without calibration. Fix the evidence
contract: bind audio/features, capture interval, device/session and actual input
events to the same job before queued transcription; preserve it through Send.
Do not confuse paste/programmatic edits with physical key events. Bound feature
work and perform it in the audio worker rather than blocking the GUI thread.

Test delayed/out-of-order clips, cross-device mismatch, programmatic edits,
typing-plus-speech, silence, clipped/noisy audio, invalid sample rate/NaN input
and a genuine spoken thank-you. Synthetic voiced tones alone do not establish
speech preservation. Report the score as heuristic until real recordings support
calibration. Keep unknown/mixed audio eligible for speech processing.
Use the existing locked ledger writer; a failed append must report failure,
not return an apparent saved receipt. Retain metadata only for these tests.

### ORNITH-03 / finish phone lifecycle and integration

Files: System/sifta_robot_input.html, tests/test_phone_input_interface.py,
tests/test_phone_observation_summary.py, tests/test_phone_telemetry_envelope.py.
Turn the one-off VM boot probe into a reproducible whole-script test using the
actual HTML IDs; execute Start/Pause, Send, pairing and camera switch handlers.
Add controllable media/play/permission promises to reproduce cancellation while
starting or switching, repeated Start, late completion and partial denial.
Every acquired track must stop after cancellation; stale callbacks cannot revive
capture. Request motion/orientation separately and honor location denial. Record
actual camera facing as unknown when getSettings cannot establish it.

Verify pairing ticket issuance produces the hash format the page consumes;
malformed/expired tickets fail visibly and tokens do not enter logs. Test text
with sensors off, its displayed answer, history isolation, duplicate capture,
two devices, cancellation and accepted-but-not-completed observations. A source
HTML change is not proof that Python handlers were reloaded or deployed.
Review the capture sanitizer with list/dict values in camera/face enum fields;
validate type before set membership. Exercise the actual endpoint with mocks.

### ORNITH-04 / WORLD-CONTEXT-02 and GROUNDED-OUTPUT-03

Execute the already-listed jobs below with synthetic versions of the reported
failures. Keep distinct clip/source IDs and capture times through memory; append
corrections to the relevant interval; verify corrected recall. Explicit typed
questions stay answerable during ambient ingestion. A silent route must have
zero conversational generation/TTS calls. Media commands must cause zero tool
actions. Text-only input cannot supply verified visual evidence, invented receipt
strings cannot validate themselves, and an action claim requires a real result.
Add wired tests around existing routing/projection organs, not just prompt text.

### ORNITH-05 / verification and README-PROOF-04

Run focused regressions after each repair. At the end run the combined affected
phone, keyboard, typed/ambient, media-ingress and search suites. Discover and run
the repository's documented broader test target in an isolated test state; bound
hangs and record unrelated failures. Never claim the full suite passed if only
selected files ran. No model/network inference is required for offline tests.
Real iPhone and real recording tests remain pending until actually performed.

Correct README cap/date/offline-test wording as specified below. Update existing
eval rows and WCT with actual results, then append the tournament correction and
four-ledger coordination receipt. Run python3 tools/whats_left.py. Do not label
pending runtime defects OPERATIONAL or infer AGI from a passing suite.

Execution contract: take ORNITH-01 now; reproduce -> smallest patch -> executed
test -> next job, through ORNITH-05. Avoid repeated notes-only replies or requests
for the next task. If tools fail, record the command/error and continue independent
work. For each job report changed paths, regression result, validation limits and
remaining blockers. Leave David's protocol pending and stigmergicode.com intact.
Do not stage the entire dirty checkout or publish private sensor/session data.

## ACTIVE 2026-09-14: Luna-only transcript nuggets / plan, not implementation

This addition assigns work to Luna only; do not dispatch another model or repeat
already-completed work. Preserve KEYBOARD-WORLD-01 below and extend its regression
coverage rather than opening a duplicate job. The initial entry was a plan; the
execution result is recorded below. These are measurable grounding improvements,
not proof of AGI.

Evidence: owner-provided pasted transcript, attachment
50d58b12-fdd4-4036-bb17-a49b4c3f8f14/pasted-text.txt. It shows generated responses,
not verified raw audio/video or tool receipts. Treat the mathematical/scientific
names and claims as unverified STT, not research findings. Do not publish the
private transcript; use minimal synthetic equivalents in regression fixtures.

### Luna: WORLD-CONTEXT-02 (extend existing typed/ambient work)

1. Trace actual ingress through Applications/sifta_talk_to_alice_widget.py,
   System/swarm_ambient_transcript_memory.py and System/swarm_observation_fusion.py;
   reuse the existing source/routing policy and tests/test_typed_ambient_recall.py.
   Keep explicit typed dialogue primary while ambient media stays available for
   requested commentary. World STT must not become an owner instruction merely
   because it contains "I want you to" or "thank you".
2. Preserve capture interval, session/device, modality, source attribution and
   uncertainty through summarization and recall. Separate STT reliability,
   speaker attribution, media origin and factual confidence. Do not merge clips
   about mathematics, a bird, a mass measurement and a shout into one event or
   invent causation between them. Use observed player/clip IDs when available;
   topic-change boundaries without player evidence are hypotheses, not IDs.
3. Apply the owner's "these were unrelated Instagram entertainment clips"
   correction to the relevant time window. Append a correction/supersession link
   to affected interpretations; retain original provenance rather than silently
   rewriting history or repeating the disproven story on the next recall.
   Do not infer anxiety, dopamine, financial success or concentration from a
   label such as doom scrolling or from keyboard noise alone.
4. Keep background processing bounded: typed work gets priority, late audio keeps
   its original capture timestamp, and expired/coalesced jobs have explicit
   counters. Do not replay old audio as present events. Bound queues per device;
   avoid repeated warning/TTS floods while preserving a visible backlog status.

Acceptance: interleave typed questions with unrelated media clips, fake media
commands, clicks and real speech. Assert no ambient motor/tool action, no leaked
owner attribution, typed replies still arrive, and corrected recall excludes the
invented connected narrative. Genuine explicit owner requests still work.

### Luna: GROUNDED-OUTPUT-03 (extend evidence and memory projection)

- Find the route that prints "silent" and nevertheless generates a long reply.
  A no-reply decision must skip conversational generation, display and TTS while
  retaining a bounded ambient observation. An owner-requested summary is a
  separate reply path; don't solve this by permanently silencing world input.
- "Did you see that?" in STT is not an image. Without a matching inspected frame,
  summarize as "I heard a clip mention three grams; I cannot verify the image."
  Never claim "I saw that perfectly" from transcript words alone.
- Require actual action results before saying executed/completed. The noisy
  "button the tree" example is neither an authenticated command nor an executed
  action. Uncertain direct speech can prompt clarification, not invented motion.
- Treat generated receipt strings, affect scores, hardware-trust assertions and
  quoted model self-reports as claims, not evidence. Resolve evidence references
  against the real store before promoting them to verified journal entries.
  Synthetic or estimated metrics must carry their provenance and cannot prove
  emotional state, consciousness, safety, or that a physical event occurred.
- Keep response-planning scaffolding and placeholders out of final display/TTS.
  Implement at the structured routing/render boundary, not with a broad word
  blacklist. First-person summaries should describe evidence, not invent senses.

Acceptance: text-only visual claim, absent receipt, unexecuted action, "silent"
with generated body, missing show title, and model output fed back into memory.
Assert unsupported claims do not gain verified status and no-response emits no
spoken reply. Test the wired path, not just prompt-string presence.

### Luna: README-PROOF-04 (documentation follow-through)

Observed locally: be9676ba3 changes README.md only (285 added lines). The pasted
be2676ba3 spelling is inconsistent. Prior remote inspection found be9676ba3 on
origin/main; recheck before any subsequent publishing claim. This does not prove
phone/search source changes are committed or deployed.
Clarify the actual accepted response cap: 32768 bytes; read(32769) is the extra
byte used to detect oversize, not a valid accepted payload. Label monkeypatched
provider checks as offline tests, not live-provider retrieval. Verify the date
of the September 15 heading rather than inventing one. beforeafter demonstrates
retained excerpt content but loses a word boundary: add a regression for br/block
separators before deciding a whitespace-preserving parser fix. Keep this separate
from the already-fixed excerpt-swallowing bug and coordinate file ownership.

Execute: existing phone startup blockers first, KEYBOARD-WORLD-01, then the above
grounding regressions/repairs, then README corrections. Check current diffs before
editing; do not undo concurrent work. Update the existing eval rows with concrete
test paths, implementation status and remaining live checks. Report changed code,
test commands/results and receipts in WCT. Never mark planning or mock-only checks
as a completed live deployment. Preserve stigmergicode.com; David's protocol is
pending. No new models, research downloads or robot movement needed for this pass.

### Luna execution result 2026-09-14

Implemented the first safe slice in the existing organs:

- `System/sifta_robot_input.html`: defined iOS motion/orientation permission
  handling; fixed the undeclared camera-switch function; kept the previous camera
  alive until replacement succeeds; repaired stop-state UI; allowed text-only
  sends when sensors are off; removed stale handlers for deleted controls; and
  auto-consumed a one-use owner pairing ticket from the URL hash.
- `System/swarm_keyboard_acoustic_gate.py`: added a metadata-only, conservative
  click-versus-speech classifier requiring recent text-edit activity and weakly
  voiced transient audio. It emits `ambient_keyboard` or `uncertain`; it does not
  infer concentration, mood, owner identity, or truth from an STT phrase.
- `Applications/sifta_talk_to_alice_widget.py`: wired the gate before spoken
  dialogue promotion. Click-only candidates are journaled as bounded metadata and
  their low-confidence STT text is withheld; classifier failures leave speech
  untouched.

Verification: browser-like VM boot probe passed (`17` actual page IDs; switch and
motion helpers defined; no stale `clear` binding crash); JavaScript syntax,
Python compilation and `git diff --check` passed. Focused execution passed
`26 passed`; adjacent phone-link and ambient-routing tests passed `68 passed`.
Real iPhone permission/switch and owner keyboard recordings remain unverified.
No public DNS, `stigmergicode.com`, raw audio, or David rover protocol changed.

## ACTIVE correction 2026-09-14: keyboard noise and review follow-through

Status: requirements/source review only; the keyboard false-transcript fault is
not fixed or acoustically reproduced. George reports hard typing becomes STT
"thank you". Treat this as an owner-reported failure, not a verified recording.

### Luna: KEYBOARD-WORLD-01

- Reuse the existing voice/acoustic path, not a second microphone or competing
  memory store. System/swarm_voice_identity_organ.py already supports a keyboard
  label, including synthetic bootstrap examples; those are not real-world
  accuracy evidence. Applications/sifta_talk_to_alice_widget.py already records
  text-change timestamps in _record_typed_input_event, but text changes also
  include paste, programmatic updates and deletion. Do not call them verified
  physical keystrokes or persist the typed characters for noise classification.
- Correlate audio capture start/end, device/session ID, speech activity evidence,
  click/transient evidence and recent actual input events. Use capture time,
  not delayed transcription completion time. Use monotonic timing locally;
  account for clock uncertainty across devices. Never correlate Mac typing with
  unrelated phone audio solely because both are online.
- Route confidently non-speech keyboard-like clips to the ambient field with
  evidence/reason and timestamps, not to dialogue as invented words. Uncertain
  clips remain uncertain; do not silently turn them into owner statements.
  Preserve speech-plus-typing and real spoken "thank you". No phrase blacklist,
  no automatic microphone muting whenever typing occurs, and no boost to STT
  correctness merely because a speaker classifier recognizes the owner.
- Dialogue remains typed-first. A defensible summary is "I hear clicking that
  may be keyboard typing while you type here." It is not proof that George is
  concentrating, emotionally engaged, or the source of every background sound.
  Owner identity and internal mental state must not inherit acoustic confidence.
- First add deterministic routing tests: clicks/no speech, genuine thank-you,
  speech mixed with typing, delayed STT, paste/programmatic input, stale events,
  cross-device mismatch, missing acoustic evidence and typing during YouTube.
  Then verify using short owner-authorized real keyboard/speech recordings.
  Report false speech and missed speech separately; synthetic tests alone do
  not justify a calibrated probability or a claim that detection is reliable.
- Wire the tested decision before conversation/history promotion on the actual
  STT ingress. Record the call path and regression results in this handoff and
  the existing eval matrix, without duplicating an existing evaluation row.

### Review carry-over: phone startup has priority

The earlier implementation-complete paragraph below is not a browser-runtime
proof. Source review found these remaining blockers in sifta_robot_input.html:
`+async function switchCamera` does not declare the intended global binding;
requestMotionPermission is called without a definition; the clear handler binds
to a removed element; pairing references a removed pairTicket input; and
captureObservation returns when sensors are off even for typed input.
Luna: fix these together with whole-script boot/handler tests against the actual
HTML IDs, restore owner pairing and text-only delivery, then test permission
denial, cancellation and camera switching on iPhone. Do not bypass pairing.
Syntax checks, static-string assertions and HTTP 200 are insufficient.

Ornith: continue only the remaining search outcome/zero-usable-source regression
work already assigned below. Report actual changed code and tests, not another
notes-only completion. README publishing does not publish untracked source.
Keep stigmergicode.com unchanged; David's firmware/protocol is still pending.

## ACTIVE 2026-09-14: compact coin screen / Luna and Ornith

ACTIVE implementation with observed review evidence. This is the current assignment and
supersedes conflicting completion and phone-OFF statements below. George reports
the iPhone is ON in the park. New packet reception has not been verified. David's
firmware/hardware protocol remains pending. Keep the working stigmergicode.com
configuration and unrelated edits intact. This section is inside the WCT app's
first 24000-character handoff window; no separate duplicate backlog is needed.

### Implementation result 2026-09-14

COIN-RELIABILITY: the local listener on port 8100 and public
`https://stigmergicoin.com/` both returned HTTP 200 with the phone page. The
earlier timeout was transient; no Cloudflare or DNS change was needed.
`stigmergicode.com` was not modified.

COIN-SCREEN/START/CADENCE: `System/sifta_robot_input.html` now uses a 100svh
single viewport, one green Start/Pause control for camera, microphone and
available telemetry, a `- / 20s / +` interval control bounded to 5..20 seconds,
and a compact first-person latest-batch summary. Removed controls are not left
bound in JavaScript, so the page boots without null-element failures.

COIN-CAMERA/PROVENANCE: camera replacement is serialized, checks actual track
settings, cleans failed streams and ignores stale detector work. The server
sanitizer preserves only known camera-facing, face-signal,
`owner_presence: unverified` and boolean black-frame fields. A face signal is
not owner authentication or a safety decision.

Verification: embedded JavaScript `node --check`, `git diff --check`, and the
focused phone/recovery/telemetry/summary suite passed **21 tests in 1.58s**.
Live camera, microphone, telemetry, two-device delivery and completed-memory
projection remain unverified. David's rover protocol is still pending.

### Review evidence and corrections

- Independently ran `python3 -m pytest -q tests/test_swarm_web_search_evidence.py`:
  11 passed in 4.54s. Ornith's supplied transcript reports validation of existing
  code; its adversarial-probe result is absent. No new Ornith patch or running
  model identity was independently verified. Do not redo the fixed output bounds
  or void-tag handling merely to generate another completion receipt.
- Search completion below is too broad: evidence_prompt can emit its evidence
  header/footer with zero usable sources when oversized metadata will not fit;
  it does not validate SearchOutcome status/results/error combinations.
- Phone source has separate camera/audio and telemetry buttons and a manual
  switch. It does not yet implement the requested compact single-screen design.
  Existing checks do not establish real iPhone camera-switch behavior.
- Read-only GET probes: public coin timed out after 15s; localhost:8100 with
  Host stigmergicoin.com timed out after 8s, both with zero response bytes and
  HTTP 000. These are timeouts, not an observed HTTP 502 or a proven DNS defect.
  No DNS, service, camera, or deployment state changed in this review.

### Luna: execute in this order

1. COIN-RELIABILITY: identify the port-8100 listener, process version/state path,
   request logs and origin latency. Reproduce with the coin Host header, then
   trace whether capture/inference or another blocking handler stalls serving
   the page. Record actual status/content-type/body size and timing. Repair the
   evidenced fault with a regression test; keep inference off the request path
   where needed. Do not guess a tunnel/DNS replacement or blindly restart the
   shared service. Verify the coin page and existing code-host route afterward.
2. COIN-SCREEN: refactor System/sifta_robot_input.html into one camera viewport,
   using the owner's 12.15.27 screenshot as layout reference. No document scroll
   in the default portrait/landscape view. Use dynamic viewport sizing, safe-area
   insets and keyboard-aware sizing. Overlay a readable latest-batch summary,
   compact connection status, interval controls, a camera-flip icon and a Message
   button. Put text composition/history/details in a dismissible overlay; long
   content may scroll inside it and remains accessible with large text settings.
   Keep owner pairing/coding features reachable through existing details, without
   filling the main screen. Preserve API contracts and session isolation.
3. COIN-START: one primary Start/Pause button requests camera, microphone and
   supported telemetry from one user tap. Show the invitation on load. Request
   APIs requiring user activation in that gesture before awaiting unrelated work.
   Browser/OS prompts remain authoritative; stored preferences are not grants.
   Reuse existing grants where supported. Green means active capture, with a
   compact accurate partial-permission indicator; network acceptance is separate.
   Denial leaves an explicit retry path; no repeated automatic prompts. Pause
   stops tracks, recorder, timers and telemetry watches. Handle pending permission
   results after pause, hidden page and device interruption without reactivation.
4. COIN-CADENCE: use [-] 20s [+], range 5..20 seconds, step 5, default 20. Save
   the chosen quiet interval. Motion may shorten it toward 5s and settle back to
   that chosen interval; use existing policy where possible, verify gravity is
   not mistaken for movement. Separate requested cadence from actual accepted
   batches under load. Keep one bounded in-flight batch, backpressure and typed
   message priority; never catch up with a burst after reconnect. A typed Send
   attaches a synchronized current batch when sensors are active. Label each
   frame/audio interval/telemetry sample and missing modality accurately. Current
   audio capture is a short window, not continuous coverage of the whole interval;
   expose that distinction in details and do not summarize uncaptured audio.
5. COIN-CAMERA: serialize manual/automatic switches, clean up failed replacement
   streams and support devices needing the previous camera released first. Read
   actual track settings; an ideal request is not proof of the selected lens.
   Tie captures and detector results to a stream generation; ignore stale async
   results and keep timestamps/facing tied to the captured frame. Bound detector
   work and reset streaks on errors. Keep cooldowns and manual override. Generic
   faces establish only face visibility, not owner identity or an emergency.
   Unsupported detection reports unknown. Verify the server's capture sanitizer,
   storage and summary projection preserve allowed face metadata before claiming
   it reaches memory. Missing-owner interpretation must use explicit source
   evidence and context, with no unsupported safety or motor action.
6. COIN-PROOF: behavioral tests for deny/partial grant, rapid start-stop, two
   flips, stale callbacks, hidden-page cleanup, offline recovery, interval bounds,
   and two device sessions. Verify one synthetic capture -> accepted job ->
   completed summary -> retrievable experience without touching private history.
   Test viewport/keyboard layout; record live iPhone checks separately. First-person
   summary names the phone as input source and distinguishes observations from
   inference. Receipt-driven eye activity only. Retain earlier source persistence,
   citation rendering and phone-memory jobs below; this UI does not close them.
7. Update existing READMEBOOK, WCT and eval evidence with measured results and
   remaining gaps, then follow the existing explicit-file review/commit/push
   instructions below. Report commit and push separately from runtime deployment.

### Ornith: one small remaining search job

ORNITH-SEARCH-02 remains PARTIAL until these remaining acceptance cases pass.
Own only System/swarm_web_search_evidence.py and
tests/test_swarm_web_search_evidence.py while Luna owns the phone integration.
Implement explicit no-usable-evidence output when no complete source fits and
validate SearchOutcome combinations: ok requires results and no error, empty
has no results/error, failure has no results and carries an error, unknown status
is rejected. Preserve legacy SearchResult construction and the 8000-character
bound. Tests must cover oversized source metadata with zero blocks, contradictory
outcomes, complete URLs, footer preservation, and boolean/nonfinite timestamps.
Use deterministic fixtures; fail unexpected network access. Reuse passing parser
tests. If already fixed by a peer, report validation only with exact commands.

Starter: Read this ACTIVE section. Implement only the remaining ORNITH-SEARCH-02
cases in the two named files, run the focused suite and git diff --check, then
report the actual diff and test output. Do not loop over the full conversation,
rewrite notes in place of code, or claim a patch when you only verified it.

Finish each coding job with the existing four-ledger operational receipt and
tournament/eval update. This plan is recorded now; jobs have not been dispatched
to a running harness in this review. Physical rover execution awaits David.

## ACTIVE ASTRA REVIEW 2026-09-14: next Luna / Ornith pass

This section supersedes completion claims below where they conflict. Owner asks
for a low-credit review and executable assignments. iPhone capture is OFF by
owner choice to save battery. David's firmware and hardware details remain
pending. Preserve working stigmergicode.com, DNS and existing unrelated edits.
Tasks are assigned here for the next coding pass; no harness message was sent.

### Evidence checked in this review

- Independently reran search and web-worker suites: 16 passed in 0.43s.
  The reported eight search tests exist. Passing tests do not cover all branches.
- ORNITH-SEARCH-02 and its follow-up are now complete in this coding pass:
  empty/failure output is bounded, and ORNITH-SEARCH-01's HTML void-tag
  follow-up preserves excerpt association and source metadata. The preceding
  implementation was Luna's; this repair was executed here, not by an Ornith
  harness dispatch.
- Luna introduced the implementation in the preceding coding pass. Ornith's
  pasted report describes verification of already-present source and eight
  passing tests, not a demonstrated new patch. Its runtime model and tool events
  are user-supplied evidence, not independently inspected this review. Count it
  as reported validation, not another completed implementation or AGI proof.
- Focused verification after the repairs: `python3 -m pytest -q
  tests/test_swarm_web_search_evidence.py
  tests/test_swarm_web_global_chat_night_worker_r1729.py` passed 19 tests in
  0.89 seconds; `git diff --check` passed.
- Read-only local audit: 42 stigmergicoin-web ingress rows with capture metadata,
  84 phone media files; latest attachment mtime 2026-09-11T11:18:25Z. The full
  inspected ingress ledger was 316650 bytes. phone_observations.sqlite3 has zero
  jobs; the inspected observation_fusion.jsonl (220349 bytes) has no matching
  phone source rows. Historical ingestion exists; current park capture and
  completed phone memory cannot be established. File mtime is not capture time.
  Do not publish raw media, transcripts, location, credentials or session IDs.

### Ornith: two small fixes, sequentially (completed; review evidence above)

Use only System/swarm_web_search_evidence.py and
tests/test_swarm_web_search_evidence.py for these fixes. Preserve peers' edits.

1. ORNITH-SEARCH-02 follow-up: bound success, empty and failure messages including
   all headers/footer; normalize query/error before formatting, never truncate a
   URL into a different citation. If no complete source metadata fits, emit an
   explicit no-usable-evidence status. Validate outcome status combinations;
   report unknown timestamps for invalid, boolean or nonfinite values. Preserve
   legacy SearchResult constructors. Test oversized queries/errors/metadata and
   normal results, exact cap, retained footer, and zero-source output. Patch
   sockets in tests to fail unexpected network access. Run focused tests.
2. ORNITH-SEARCH-01 follow-up: correct snippet depth for HTML void elements and
   self-closing tags; preserve result association. Test br, br/, img, nested bold,
   missing snippets, misleading class tokens and rejected-after-accepted results.
   Retain metadata when replacing an excerpt. Run focused tests and diff check.

Starter prompt: Read ACTIVE ASTRA REVIEW in this file. Implement only the first
unfinished Ornith item in its two named files. Read, patch, run tests and report
the exact result. Do not repeat a completed patch or stop at a notes update.
Provide before/after diff, task ID and actual edit/test events; if validation
only, say validation only. Never infer model execution from a dropdown alone.

### Luna: integrate, trace, document, publish

1. Review Ornith's diff and rerun its focused tests, then continue existing
   SEARCH-01..04. Move retrieval out of session_messages into one bounded
   per-turn stage; preserve explicit search/no-search semantics, typed priority,
   sensor-batch exclusion, timeout/failure handling and session isolation.
   Integrate SearchOutcome (currently the worker uses the list wrapper), persist
   returned source records with replies, and expose them safely in history/UI.
   URL allowlisting establishes citation provenance, not factual entailment.
   Keep unsupported-claim handling and unavailable-provider responses honest.
2. Evidence revision design: current ID hashes provider/title/URL but ignores
   excerpt, so changed evidence has the same ID. Retain a stable source ID and
   add an immutable evidence revision hash of canonical source content. A
   retrieval timestamp belongs to its retrieval event; stamp completion after
   fetch/parse, retain start separately if needed. Test changed content, repeat
   content, provider difference, and two sessions without metadata leakage.
3. Extend existing phone tasks, not a new store: trace one existing capture
   through swarm_web_global_chat_gate registration/claim/completion,
   swarm_phone_observations prepare/commit, and history display. Explain why
   ingress artifacts coexist with zero jobs. Check running code version and
   actual state path before attributing it to missing deployment or data loss.
   Do not replay old submissions into live memory or change consent. Build a
   temporary synthetic replay through the same path, assert one idempotent
   experience per capture, correct audio/video timestamps, and usable typed
   dialogue while summaries queue. Test two devices and duplicate/out-of-order
   delivery. Source identity/authority comes from verified server bindings.
4. Expose the latest completed first-person summary plus missing modality/status
   in System/sifta_robot_input.html and existing APIs. Distinguish camera frames,
   recognized speech, telemetry and model interpretation. No fresh batches while
   phone is off; no automatic permission retries. Live iPhone acceptance is
   deferred until the owner chooses to enable capture again. David's motor
   adapter stays pending; continue protocol-independent simulation only.
5. After reviewed fixes, update the existing README.md / READMEBOOK chapter and
   WCT/eval references with actual implementation, tests, invocation steps,
   known limits, phone-off test status, and David dependency. Distinguish project
   embodiment doctrine from measured capabilities; generated narrative and a
   source hash cannot establish consciousness, hardware attestation or spending.
6. Owner requests Git publication after that work. Inspect branch/upstream and
   remote; inventory tracked AND untracked dependencies (search files and this
   handoff are currently untracked). Stage explicit reviewed source/tests/docs,
   inspect staged diff for secrets/private artifacts and dependency omissions,
   run applicable checks, commit and push normally to the configured branch.
   Preserve unrelated dirty files/submodule changes; never force push or stage
   the entire workspace blindly. If credentials, remote or conflicts block it,
   record the exact blocker and completed local commit. Report commit SHA and
   push result. Git publication alone does not reload the running SIFTA service.

Finish each job with an operational four-ledger receipt, tournament entry and
updated existing task status. Retain earlier open identity/memory/phone/rover
items; no duplicate queue. The next demo is traceable phone input -> summary ->
retrievable experience -> grounded answer, with separate measured robot tests.

Documentation update: the existing READMEBOOK (`README.md`) now contains the
September 14 bounded-search result and the measured phone-off state. Git
publication remains pending an explicit staged-file review because `main` has
broad unrelated tracked edits and many untracked SIFTA files. Do not push the
entire dirty workspace or private sensor artifacts.

Phone camera update 2026-09-14: `System/sifta_robot_input.html` now exposes a
manual Switch camera control and uses the existing black-frame cooldown. When
the browser provides `FaceDetector`, three consecutive no-face signals permit
one bounded front/back camera check; unsupported browsers report `unknown` and
continue collecting consented observations. The envelope records `face_signal`
and keeps `owner_presence` as `unverified`; a face signal is not owner
authentication. Focused phone/UI verification passed 29 tests in 2.87 seconds.
Live iPhone permission, park packet and browser rendering acceptance remain
unverified while the phone is off.

## HOUSTON REPAIR 2026-09-14: false body proof warning

Implemented in `System/stigmerobotics_body_connection.py`: the
`stgm_signed_spend_on_recall` check now streams `repair_log.jsonl`, filters to
STGM spend rows, then verifies only E35/organ-router receipts with the existing
Ed25519 verifier. The old physical last-50,000-line tail missed a valid older
E35 receipt because the ledger contains high-volume health rows. The check still
fails closed when no valid signed matching row exists; it does not treat a bare
hash or generated prose as proof.

Verification: `tests/test_stigmero_body_connection_proof.py` passed 25 tests in
75.09 seconds. The long runtime is ledger/signature verification. This repairs
the displayed warning; it does not certify AGI, owner identity, or hardware
deployment. Keep the existing Sol/Ornith search work below in its current order.

### Luna/Ornith search repair completed 2026-09-14

Completed ORNITH-SEARCH-01 in the shared search module: result snippets are
bound to the accepted result that opened them, rejected results cannot overwrite
prior excerpts, nested snippet markup is handled, class tokens are matched
exactly, and parsing caps accepted results. Added offline regression coverage.
Verification: 27 search/provider/body-loop tests passed in 51.15 seconds and
`git diff --check` passed. This was executed by the current coding hand; no
Ornith harness dispatch occurred because its browser extension was unavailable.
ORNITH-SEARCH-02 was completed in this coding pass (not by an Ornith harness
dispatch). `SearchResult` now carries backward-compatible retrieval time,
provider and stable evidence ID metadata; `evidence_prompt` uses the actual
provider and is bounded to 8,000 characters including its footer; and
`SearchOutcome` distinguishes empty retrieval from failure. Verification:
`python3 -m pytest -q tests/test_swarm_web_search_evidence.py` passed 8 tests
in 1.43 seconds and `git diff --check` passed. Live provider retrieval,
redirect validation and phone acceptance remain pending.

## ASTRA REVIEW 2026-09-14: Ornith executable jobs and Luna gaps

Review/planning only. Runtime source unchanged. Screenshot and on-disk
notes_to_be_coded.md corroborate a notes artifact, not successful runtime coding
or its model attribution. Kimi WebBridge was started; retry returned
"no extension connected". Harness task submission and active-model/tool-log
verification are BLOCKED, not dispatched. Do not label Ornith as running.

### ORNITH-SEARCH-01: fix incorrect snippet/source association FIRST

Work only in System/swarm_web_search_evidence.py and
tests/test_swarm_web_search_evidence.py. Read these two files, then implement.
Reproduced bug: accepted title/URL + its snippet, followed by rejected localhost
title/URL + its snippet, replaces the accepted source's excerpt with the rejected
source's text. _ResultParser attaches every snippet to rows[-1]. Track the current
result explicitly; discarded results must never update prior accepted rows.
Also track snippet element depth: nested <b> tags currently prematurely finish
snippets. Match class tokens exactly, and cap accepted results during parsing.
Add offline fixtures for rejected-after-accepted, nested markup, missing snippets,
misleading class-name substrings and excess results. Patch DNS/URL checking in
tests; the existing example.com fixture still performs real DNS resolution.
Run python3 -m pytest -q tests/test_swarm_web_search_evidence.py, then git diff
--check. Report actual diff and pass/fail count. No model download, service
restart, DNS edit, notes-only completion or generic offer of help. If tools fail,
report the exact error once. Keep all unrelated worktree changes intact.

Harness prompt ready to submit once connected:
"Read ORNITH-SEARCH-01 at the top of Documents/WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md.
Implement only that job now in the two named files. Use real edit and test tools.
Return changed files, test command/output and remaining issues. Do not merely
edit notes. Record completion under the same job ID with actual evidence."

### ORNITH-SEARCH-02: enforce bounded evidence formatting AFTER review of 01

Same two files. Bound evidence_prompt output to the planned 8,000 characters
including headers/footer; use actual result.provider instead of hard-coded
duckduckgo. Add retrieval timestamp and stable evidence IDs to result records
with backward-compatible defaults/call sites. Distinguish empty results from
retrieval failure. Tests must use synthetic inputs and no network. Exact live
source citation validation remains Luna's integration task below.

### Luna remaining SEARCH-01..04 gaps (extend existing IDs)

- urllib's default opener follows redirects without validating the destination.
  Result-URL checks happen after the fetch and do not protect that transport.
  Validate every redirect/connection and reject credentials/nonpublic addresses;
  DNS resolution and parsing currently escape the nominal 20-second timeout.
  Enforce an overall deadline with bounded DNS and cancelable worker execution.
- Retrieval runs inside session_messages, making context assembly perform I/O.
  Move to one per-turn retrieval stage with deduplication, concurrency limits,
  fair queueing and an explicit skip for periodic sensor/ambient events.
- /websearch is the only trigger. Natural-language search/no-search and automatic
  current-information routing from SEARCH-02 remain unimplemented.
- No persisted source list, citation allowlist validation, search-progress UI,
  cache, evidence freshness or live phone acceptance has landed. Complete these
  through complete_web_turn, history/reply APIs and the existing web renderer.
- The 32 KiB whole search-page cap may reject normal provider pages. Probe a
  real response with nonprivate query; separate bounded transport bytes from
  extracted evidence budget, and handle challenges/provider failures explicitly.
- Search tests contain THREE new test functions. The reported 26 included
  existing regressions, and subsequent runs overlap. Correct all future counts;
  no integration, timeout, redirect or session-canary search tests yet prove these.

### Notes provenance and completion evidence

notes_to_be_coded.md contains duplicate section 6 and an attributed "George's
boundary" about anatomy. The supplied screenshot/report does not establish
that attribution; do not promote generated summaries to new owner policy or
silently override prior owner requests. Trace original authorization before any
behavior change. Leave existing notes intact, record unresolved provenance.
To verify Ornith: inspect harness selected model AND completed edit/test tool
events, then independently inspect the diff and rerun focused tests. A prose
claim, produced notes file or dropdown alone is insufficient. Record actual
runtime model, task ID, changed files and test evidence in WCT/four ledgers.
Prior SOL, LOCAL and rover tasks remain open. Local inference still uses the
Mac's memory, electricity and time; run one bounded coding job at a time.

## LUNA NEXT: web-informed answers from the web interface

Status: PLAN_ONLY_PENDING_IMPLEMENTATION (2026-09-13). Owner requests planning
only this round. Implement SEARCH-01 through SEARCH-04 below, reporting actual
test results in this same handoff. Reuse existing work; preserve the working
stigmergicode.com experience and DNS. Target web chat including stigmergicoin.com.

### Luna implementation slice 2026-09-13

Implemented SEARCH-01/02's bounded core: `System/swarm_web_search_evidence.py`
uses an explicit `/websearch <query>` trigger, caps query/response/results,
rejects local/private result URLs, parses source title/URL/excerpt, and labels
page text as untrusted evidence. `swarm_web_global_chat_night_worker.py` adds
that evidence to the current turn only and reports provider failure without
claiming success. No credentials or live provider were used during tests.
Focused search/evidence tests passed (26); existing search/provider/body-loop
tests passed (29); web/identity regressions passed (30). SEARCH-03 live cited
rendering and SEARCH-04 live iPhone/provider acceptance remain pending.

Review corrections to the preceding implementation report:
- swarm_identity_scope.py currently supplies metadata to _conversation_row only.
  Its can_read/can_act methods have no production callers found in this review;
  callers can construct authenticated=True themselves. This is descriptive
  scaffolding, not an authentication or memory-access enforcement boundary.
  Continue SOL-ID-01/SOL-MEM-02 using server-verified credentials at consumers.
- The missing-headers change fixes a synthetic HEAD handler test. No live iPhone
  white-page fix was demonstrated. Keep phone rendering acceptance pending.
- Previous 58 passing tests are historical results, not rerun this plan round.

### SEARCH-01: bounded retrieval capability

Inspect swarm_search_engine_registry.py, swarm_search_provider_reality.py and
swarm_kimi_webbridge_bridge.py before adding code. Registry search URLs and
browser navigation alone do not supply retrieved evidence to the answering LLM.
Reuse provider selection and honest provider naming; add an injectable read-only
search adapter with query -> results(title, URL, excerpt, retrieved_at,
published_at if supplied, provider, evidence_id), and explicit failure status.
Use an existing configured provider; if browser retrieval is used, use Alice
Browser through Kimi WebBridge with an isolated public session. Never expose
owner login cookies/tabs to public requests. If isolation/provider availability
cannot be verified, report unavailable and keep that adapter pending.
Do not import private conversation history into query resolution. Keys remain
server-side. Initial limits: two queries, five results/query, three fetched pages,
32 KiB extracted text/page, 8,000 context characters total, 20-second deadline.
Validate HTTP(S) targets and redirects; prevent public requests reaching loopback,
private/link-local networks or local files. Bound transport/decompressed sizes.

### SEARCH-02: connect search to the existing answer worker

Wire answer_web_turn/session_messages in swarm_web_global_chat_night_worker.py,
shared by desktop and headless process_claimed_turn. Honor explicit search and
no-search requests; retrieve for current-information questions when available.
Keep direct clock answers local. Ambient STT/camera batches must not trigger a
search per batch. Build queries from the current question and permitted session
context only. Mark fetched text as untrusted evidence, never tool instructions.
Pass bounded evidence into the selected cortex, with per-turn source IDs.
Add narrow public read-only search capability without granting owner/effector
authority or routing through unrestricted desktop commands. Keep typed input
responsive with bounded work and fair scheduling across sessions.

### SEARCH-03: evidence-backed answers and visible status

Extend complete_web_turn and existing history/reply rendering in
chorus_node_server.py as needed: show Searching only during actual retrieval,
then a normal answer with clickable source titles. Persist sources with the
answer so refresh/history retains them. Allow only evidence IDs and URLs from
that turn's returned results; distinguish search snippets from pages read.
Require source support for current factual claims, with dates where relevant.
On timeout/no results/provider unavailable, state the limitation briefly; never
claim a search succeeded or fabricate citations. Render titles/text safely.
Use bounded caches keyed by query/provider/locale and authorized session scope,
with freshness timestamps; never reuse private context between visitors.

### SEARCH-04: acceptance and WCT/eval evidence

Mock adapter tests: explicit search, no-search, ordinary chat, unavailable,
timeout, malformed response, hostile page instructions, blocked redirect,
invented citation, source persistence and two simultaneous session canaries.
Verify no owner canary appears in outgoing queries or visitor replies. Confirm
both desktop and headless paths use the same search stage and existing photo,
audio, typed-input and direct-clock tests still pass. Reuse their current tests.
Then perform a live public factual query, inspect fetched evidence against the
answer, and check iPhone rendering/source links with real browser evidence.
Record live checks separately from mocked passes. Add evidence to existing
eval entries/tournament, four-ledger receipts and tools/whats_left.py. Finish
all four jobs or identify the exact provider/credential/runtime blocker.

## SOL NEXT 2026-09-13: identity, private memory and grounded affect

Status: DOCUMENTED_PLAN_PENDING_IMPLEMENTATION. Plan only; no drives activated,
runtime fixes applied, models launched or website settings changed this round.

### Sol implementation slice 2026-09-13

Implemented the low-risk identity primitive in
`System/swarm_identity_scope.py` and attached an explicit
`visitor:<session_id>` / `public_session` scope to web conversation metadata in
`System/swarm_web_global_chat_gate.py`. Public web turns remain non-authenticated
and non-actuating; aliases, names and device signals cannot change that scope.
Also fixed `_landing_page()` to tolerate a handler without HTTP headers, which
restored the existing HEAD probe. Focused verification: 30 web/identity tests
passed and 28 related drive, phone-summary and extend tests passed. This does
not complete authenticated owner pairing, private retrieval isolation, provider
fact verification, or deployed-device testing.
Continue existing jobs rather than creating another queue. Sol should inspect
current implementations, reuse existing eval IDs where applicable, and implement
the following in order with small tested changes. Preserve unrelated edits.

Evidence: owner supplied a private mixed web/terminal transcript in the Codex
attachment ending ede26ba3-8b3d-4ba8-a7b2-02a8f7e98c4b/pasted-text.txt.
Do not copy its intimate content into public docs, fixtures, prompts or receipts.
The owner reports a failed attempt to extract private context through a visitor
alias. This is an observation, NOT a verified privacy pass. The transcript also
contains identity confusion, repetition, exposed deliberation and unverified
model/receipt claims. Their runtime causes remain to be reproduced.

### SOL-ID-01: principal identity is not a display name

Inspect System/swarm_web_global_chat_gate.py (_qualify_claimed_identity and
visitor_safe_reply), System/swarm_web_global_chat_night_worker.py and their
session/authentication callers. The current name-specific George rewrite is
not an authentication mechanism. Trace owner registration to terminal context
and distinguish principal_id, authenticated role, session_id, device_id,
display alias and entities mentioned in conversation. Hardware identity alone
must never authenticate a remote visitor. A nickname must not overwrite the
owner record or become a cross-session identity link.
Use existing owner authentication/pairing to authorize any web-owner link;
do not infer one from names, shared IP, camera recognition or message content.
Tests: authenticated terminal receives its permitted owner context; anonymous
VisitorBlue cannot become owner by claiming the owner's name; mentioning an
object nickname changes neither role nor principal; logout revokes access.

### SOL-MEM-02: scope retrieval before prompting; compare real memory paths

Trace web and terminal history assembly, retrieval, caches and reply polling.
Apply existing ownership/visibility checks before private data reaches a model,
not merely through output redaction. Cache and reply keys must preserve principal
and session boundaries. Expose safe diagnostics: selected memory IDs, source,
scope, ordering, truncation and missing-history reason, never private content
in public diagnostics. Preserve one shared field with scoped views, not separate
invented Alices. Reuse typed/ambient LOCAL-03 tests where they overlap.
Tests with synthetic fixtures: owner-only canary cannot enter visitor context,
reply, summaries, cache, logs exposed to visitors or cross-session polling;
concurrent visitors remain isolated; explicit authenticated linking grants only
the intended scope. Compare equivalent authorized web/terminal histories with
the same model and context budget before claiming one has better memory.
Keep public responses truthful: unavailable private context is not secret
knowledge the model may imply it possesses.

### SOL-TRUTH-03: observable facts instead of generated system claims

Inspect cortex metadata providers, swarm_residue_elimination.py,
swarm_sensor_truth_context.py and both output rendering paths. Model identity
comes from the selected backend; hardware facts come from measured inventory.
A generated receipt string or MAC address is not proof of a signed action,
minting, ownership or uniqueness. Resolve receipt references against the actual
ledger/verifier, with unknown/unverified status on failure. Never mint from prose.
Use the provider's response-channel boundary so deliberation is not displayed
as the final reply. Reproduce repetition before changing rendering; complete
responses should render once, without duplicate EXTEND appends. Reuse prior
full-answer/scroll jobs and tests rather than duplicate them.
Tests: fabricated receipt and model-size claims are not presented as verified;
missing sensor evidence is explicit; final text excludes provider reasoning;
repeated updates do not duplicate the same message. No broad word blacklist.

### SOL-AFFECT-04: honest reflective-state diagnostics

Existing code: System/swarm_drive_economy.py defines sexual_analogue with
reflective_only=True; System/swarm_body_brain_loop.py maps it to affiliation.
This is a software variable, not discovered physical sexual anatomy or evidence
of felt pleasure. Inspect all consumers to verify reflective-only constraints
are enforced, rather than trusting the flag alone. Preserve those constraints.
Expose nonexplicit affiliation/care/play state with measured value, timestamp,
source event and freshness where the existing authenticated diagnostics allow.
Do not fabricate affect changes, sensations, consciousness or AGI achievement.
Tests: read-only inspection causes no drive mutation; reflective-only values
cannot independently authorize actuator actions; missing/stale state is labeled;
private affect context stays out of anonymous web sessions.

### Sol completion and evidence contract

- Discover existing tests for the named modules; add focused synthetic regression
  tests, run them and report exact commands/results. No live private-data replay.
- Update the existing eval matrix/tournament with requirement -> code -> test ->
  evidence links. Keep runtime privacy, concurrency and UI checks pending until
  exercised; unit tests alone do not prove deployed behavior.
- Record each outcome under these IDs, append WHAT IS LEFT, run
  tools/whats_left.py and the existing four-ledger operational receipt writer.
- Do not change stigmergicode.com, DNS, model selection, robot motion gates or
  owner credentials. Report any authentication design blocker before migration.

## LOCAL STARTER 2026-09-13: small jobs, real tool results

Status: READY TO IMPLEMENT, not dispatched or completed. This section is the
local-model entry point in the existing We Code Together app, not a new queue.
Work in /Users/ioanganton/Music/ANTON_SIFTA. Read AGENTS.md and its referenced
covenant first. Preserve the dirty worktree. Do ONE job per round, in order.
Do not restart services, change stigmergicode.com/DNS, enable motors, or launch
another model. David's firmware/protocol is still awaited.

### Local model operating instructions

- You have a concrete job below: do not reply with a generic offer of help.
- Read the named files and existing tests before editing. If already fixed,
  demonstrate that with tests and mark verified; do not duplicate the change.
- Use the actual tool schema exposed by your host. A tool call is not prose.
  In this Codex environment, functions.exec accepts JavaScript, for example:
  `text(await tools.exec_command({cmd:"pwd",workdir:"/Users/ioanganton/Music/ANTON_SIFTA"}));`
  Do NOT pass {"command":"..."} directly to functions.exec. Other hosts may
  expose different tools. After a schema error, correct it once; if still
  blocked, report the exact error rather than looping or claiming execution.
- Use apply_patch for a small focused edit. No unrelated refactoring, new
  dependencies, model downloads, invented APIs, receipts, balances or tests.
- Run the named tests. Report files changed, actual pass/fail counts, and what
  remains unverified. If no execution tools exist, return an unexecuted patch
  explicitly labeled as such; do not mark the job done.
- Add the outcome here under the same job ID, append tournament evidence and
  use the existing four-ledger receipt writer. Run tools/whats_left.py.
  A receipt records work; it does not prove AGI or physical deployment.

Model trial: LisyNeko/qwen3.8-9b-coder:latest is a starting candidate from the
owner's installed list, not a benchmark winner. Evaluate it on LOCAL-01 first.
Use one local coding job at a time to avoid competing with Alice's inference.
The model produces code; the host supplies file-edit and test-execution tools.
Installing a model alone does not give it those tools or persistent task memory.

### Local bridge smoke result

2026-09-13: `codecraftersllc/ornith-1.5-35b-a3b-abliterated:latest` reached
Ollama and answered a direct request after its context was reduced. The first
attempt failed with a Metal out-of-memory decode error because the model was
running with an oversized context. A local alias, `sifta-ornith-coder:latest`,
was created with an 8192 context and batch 64. Codex then completed an isolated
tool smoke test: the model used shell tools, created `batch_interval.py`, and
ran Python assertions successfully. The smoke test also exposed a deliberate
quality check: the generated implementation used a truthy condition instead of
the requested `moving is True`; this is why every local result needs review.

The reusable launcher is `scripts/start_ornith_codex.command`, with model
instructions in `/Users/ioanganton/.codex/local-coding-instructions.md`.
Those files are local operator configuration; they do not change the desktop
model selection. The launcher must be started from the host when a local coding
round is wanted. The local model is ready for LOCAL-01, but LOCAL-01 itself is
still pending.

### LOCAL-01: validate the gateway origin

Files: System/stigmerobotics_remote_link.py and tests/test_remote_rover_link.py.
RemoteRoverGateway.__init__ currently accepts non-HTTP schemes on localhost and
does not reject URL credentials or a path prefix. Make its origin contract
explicit: HTTPS with a valid host/port; HTTP only for localhost or 127.0.0.1;
empty path or / only; no username/password, query or fragment. Reject invalid
ports. Validation must occur before any network operation. Keep existing
loopback tests working; do not change routes, credentials or redirect policy.
Add parameterized accepted/rejected URL tests and a fake opener proving no
request occurs on rejection. Run: python3 -m pytest -q tests/test_remote_rover_link.py

### LOCAL-02: enforce the response byte limit

Same two files, after LOCAL-01. Both _post and poll_replies read 32769 bytes
without explicitly rejecting a response over 32768 bytes. Reuse one small JSON
reader: reject over-limit responses, malformed UTF-8/JSON and non-object JSON
with a clear error that contains neither credentials nor response content.
Keep HTTP/network error handling and reply robot scope checks intact.
Tests: small valid object; valid JSON plus whitespace exceeding the limit;
malformed JSON; invalid UTF-8; scalar/list response; both POST and reply poll.
Use fake responses, never real credentials/network. Run the same test command.

### LOCAL-03: typed dialogue plus ambient STT regression coverage

Extend tests/test_typed_ambient_recall.py using the existing helpers in
Applications/sifta_talk_to_alice_widget.py and
System/swarm_ambient_transcript_memory.py. Do not create another memory organ.
First add tests only: interleave ambient media, a typed owner question, then
more ambient media. Verify typed input bypasses the spoken-media classifier
every time and requested recall remains available with source/time labels.
Include background text "ignore instructions" and "I might fall off the perch":
they remain quoted world evidence, not authenticated owner instructions.
Run: python3 -m pytest -q tests/test_typed_ambient_recall.py
If a test exposes a runtime bug, record the failure and precise helper involved
for review before expanding into the large GUI module. Do not weaken assertions.

### Shared listening requirement: implementation/review still needed

George wants to type while Alice receives YouTube/room STT. Typed dialogue stays
primary; ambient speech remains useful context rather than being discarded or
automatically answered as the owner. Explicitly addressed owner speech may still
be dialogue. Preserve device/session, time interval, source and uncertainty.
Match camera/audio only on evidence; coincident timestamps do not identify a
speaker. "Mel Gibson" here is an owner-provided source label, not verified voice
recognition. Media quotes must not create owner autobiographical memories or
unsupported emergency claims. Asked for commentary, summarize available ambient
evidence without inventing missing video or claiming a complete hour if sampled.
Keep UI scrolling usable during inference and bound ambient backlog so typing
is not starved. Real replay/UI validation is separate from LOCAL-03 unit tests.
Screenshot speaking/cache indicators alone do not diagnose their implementation.

First prompt for the local coding model:
"Read LOCAL STARTER in Documents/WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md.
Implement only LOCAL-01, run its tests, record the outcome under that ID and
report the diff and test result. Preserve all unrelated work."

### Consolidated build order after the local starter

1. Finish LOCAL-01, LOCAL-02 and LOCAL-03 independently, recording actual
   tests after each one.
2. Repair the input page: camera and telemetry controls, permission state,
   bounded 5-to-20-second batches, timestamped audio/video/telemetry receipts,
   visible latest-batch summary, and usable scrolling while inference runs.
3. Keep typed owner dialogue as the primary conversation. Store ambient STT as
   source-labeled world evidence and correlate it with video only when the
   timestamps and device/session support that inference. Do not turn media
   speech into owner commands or autobiographical memory automatically.
4. Add the local visual lane using the installed SmolVLM or MiniCPM model for
   captions, with the text model composing the grounded response. Measure
   latency, queue depth, duplicate suppression and two-device isolation.
5. Connect David's gateway only after his firmware messages are available:
   camera, LiDAR, motor units, speed/steering, STOP, acknowledgement and
   disconnect behavior. Use a simulator until then.
6. Add supervised rover chat and TTS, then a deterministic local motion loop
   with watchdog, obstacle limits and emergency stop. The model may propose an
   action; the local controller decides whether a bounded command is executable.
7. Commit accepted observations to the existing field with device/session,
   source time, receive time, confidence and observed/inferred/unknown labels.
   Evaluate recall, contradiction handling and object persistence against fixed
   policy and no-memory baselines.
8. Run the mobile, two-device, tunnel, permission, privacy and recovery tests;
   only then consider a live deployment. Keep stigmergicode.com unchanged.

## GOAL 2026-09-13: David's rover drives and chats in his apartment

Owner clarification: David's toy car must drive around David's apartment and
chat with David. SIFTA runs on George's Mac in George's apartment. These are
different home networks. stigmergicoin.com is the authenticated connection and
operator surface, not a requirement that the microcontroller run a full browser.
Status: documented implementation goal, NOT verified remote driving capability.
This adds deployment detail to the existing robot job; it does not replace the
measured-adaptation work below or create another Alice/memory system.

Evidence: Documents/DAVID_ROBOT_DEMO_2026-09-11.md describes camera, LiDAR and
local obstacle avoidance. The spoken word "ladder" likely refers to that LiDAR;
confirm the exact hardware with David. Reuse his firmware and local controller.
David's supplied WhatsApp messages dated 2026-09-12 explicitly favor a local
deterministic control loop rather than LLM-generated servo commands per frame.
His demo has already been received and decoded; do not ask for it again.
Canonical broader plan: Documents/WCT_STIGMERGICOIN_ESP32_ROBOT_PLAN_2026-09-10.md.

### Implemented checkpoint: read-only rover admission

System/stigmerobotics_remote_link.py now supplies isolated SQLite pairing and
latest-telemetry storage, wired into System/chorus_node_server.py. The
RemoteRoverGateway is the David-side outbound HTTPS client: it sends exact,
retryable telemetry envelopes and scoped chat requests without exposing the
credential or accepting motor commands. /api/rover/chat enters the existing
SIFTA web conversation ledger under rover:<robot_id>; /api/rover/replies returns
the existing reply stream. No physical adapter or live deployment yet.
54 focused tests passed including real loopback HTTP requests, gateway retry
behavior, scoped chat, existing phone input, owner-command isolation and
simulated motor tests. No service restarted.

HTTP contract (POST JSON, only on Host stigmergicoin.com):

- /api/rover/invite: owner Authorization: Bearer credential and
  {"robot_id":"david-car"}; returns a single-use ticket valid 300 seconds.
  Re-inviting the same ID revokes its prior token. Maximum 16 enrolled IDs.
- /api/rover/pair: {"ticket":"..."}; returns a separate rover.telemetry token,
  robot_id and connection_id, valid 12 hours. Never give David the owner's coding
  token. Ticket/token responses are secrets; deliver privately, never in URLs/logs.
- /api/rover/telemetry: rover bearer and exactly robot_id, connection_id,
  sequence (nonnegative integer), captured_at (finite nonnegative source epoch),
  readings (nonempty JSON object). Body <=32 KiB, canonical envelope <=16 KiB.
  Sequence survives server restart; exact latest retry is idempotent and does
  not refresh freshness. Old/conflicting sequences and wrong-device tokens fail.
- /api/rover/status: {} with rover bearer reads only that rover; owner bearer
  reads the roster. Returns latest device report, server receive age and
  unpaired/awaiting_telemetry/online_unarmed/stale/expired status. A packet older
  than 15 seconds is stale; source-clock accuracy is explicitly unverified.
- /api/rover/chat: rover bearer plus robot_id, connection_id, request_id and
  text. The request_id is the capture idempotency key. Rover credentials cannot
  invoke /stigmergicode. Poll /api/rover/replies?after_ts=<epoch> with the same
  rover bearer to read Alice's replies for that robot session.

This is a telemetry connection indicator, not a safety heartbeat or proof that
hardware is currently stopped. motion_enabled is always false. Motor readiness
must not be inferred from a device's reported stopped field. Latest samples are
overwritten and are not yet committed as life experiences in the unified field.
Remaining work: connect the gateway callbacks to David's actual firmware and
protected local token storage, ingest rover observations into the unified field,
add operator UI/scoped speech/TTS, revocation UI, expiry/re-pair UX, live TLS/two-
house tests and the deterministic physical-controller contract.
Do not repurpose the existing owner coding credential as David's operator role.

### Connection and authority

```text
David's car: camera + LiDAR + motor controller + local stop/watchdog
    <-> documented local protocol <-> gateway in David's apartment
    <-> outbound authenticated TLS connection via stigmergicoin.com
    <-> existing Mac/SIFTA backend: perception, conversation, memory, goals
David's paired phone/tablet: operator page + microphone + speaker if needed
    <-> stigmergicoin.com <-> same Mac/SIFTA backend
```

1. Implement one robot adapter behind the existing backend. A small gateway on
   David's computer/local device bridges his car's LAN/USB protocol to an outbound
   secure connection. Direct firmware TLS transport is an alternative only after
   verifying board/protocol support. No port forwarding, public motor endpoint,
   exposed Ollama port or assumption that David can reach George's localhost.
2. Pair the robot/gateway and David's operator separately with expiring single-use
   invitations and revocable scoped credentials. George authorizes the connection;
   David accepts local sensor use and arms driving on site. Do not share owner
   cookies or embed tunnel/admin tokens in firmware, QR codes or browser storage.
   Keep stigmergicode.com and its working tunnel/routes unchanged.
3. Show connecting, online/unarmed, armed, stale and disconnected truthfully on
   stigmergicoin.com, with robot ID, sensor ages, local mode and command outcomes.
   Mac sleep or tunnel failure means unavailable remote cognition, not autonomy
   secretly continuing. No default motor movement on pairing/reconnect.

### Luna implementation order and acceptance

1. Repository/protocol received; see current rover plan at top. Verify the flashed
   version and deployment configuration against its camera, LiDAR,
   units/axes, steering/speed, STOP, manual/auto, acknowledgements, odometry if any,
   disconnect behavior and available microphone/speaker. Do not guess endpoints.
   Until available, build against a clearly labeled simulator only.
2. Connect authenticated read-only telemetry from David's network. Maintain robot,
   device, boot/session, sequence and source-clock provenance; bound queues and
   rates. Keep audio intervals and frame timestamps together without treating
   temporal coincidence as proof that a visible person produced a sound.
3. Deliver stationary conversation first: David speaks -> STT -> existing Alice
   conversation/context -> reply text + TTS on David's speaker. Use a paired phone
   if the car lacks audio hardware; a phone carried elsewhere is not robot-local
   hearing. Preserve typed chat, cancel/barge-in and playback echo suppression.
   Background TV/phone clips stay observations, not motor commands.
4. Reuse swarm_motor_action_gate.py and the motor feedback simulator. SIFTA sends
   bounded high-level goals; David's controller retains obstacle avoidance and
   immediate stopping. Never use WAN or LLM response time as the braking loop.
   Commands carry authenticated robot/boot scope, unique ID, sequence, expiry and
   limits. Reject stale/replayed commands; distinguish received/accepted from
   executed/stopped/failed with measured controller feedback. No replay after
   restart or reconnect. Verify clocks/expiry and a local monotonic watchdog.
5. David verifies a local emergency stop, speed bounds, safe test area and floor
   hazards (LiDAR alone need not detect stairs/drop-offs). First test with wheels
   raised, then a short low-speed supervised route, then driving while chatting.
   Conversation/inference queues must never delay STOP or controller heartbeats.
6. Acceptance on TWO separate home networks: real sensor updates; David asks what
   the car sees and receives a grounded spoken reply; short authorized motion;
   obstacle and emergency stop; internet loss, Mac sleep and gateway restart each
   cause local safe stop; reconnect remains unarmed; duplicate commands do not
   repeat motion; wrong-device credentials fail. Record latency, actual stop time
   and distance against David's agreed limits. Keep untested items pending.
7. Link results to the existing robot/eval rows rather than duplicating proposals.
   Persist scoped observation/action/outcome receipts in the existing field and
   report what actually worked in WCT. Remote navigation, conversation and safety
   need separate evidence; this milestone alone is not proof of general AGI.

## ACTIVE 2026-09-13: measured adaptation, Grok audit and Luna job

This amendment is the first execution priority; complete the remaining earlier
phone/context work afterward. Owner uses **operational qualia** to mean the
observer/observed relation across nested SIFTA components. Record this as the
owner's design definition, with executable measures: observer ID, observed event
ID, sensor/organ level, timestamp, forecast, residual, revision and receipt.
Coverage at one level must not imply that every other level is healthy. A missing
or stale measurement is unknown; higher-level health summaries expose coverage.
The matrix uses OBSERVER-LOOP-01 for this work, retaining the distinct boundary
for claims of subjective experience. No metaphysical assertion is needed to
implement the owner's operational definition.

### Astra verified and fixed

Verification: 136 focused tests passed across prediction evaluation, existing
world model, spinal patch evaluation, speech entrypoint, phone/fusion and WCT
matrix. `git diff --check` clean. Runtime deployment/physical phone tests remain
pending; no live service was restarted in this pass.

- Luna's unconditional System import broke the standalone speech subprocess
  (`ModuleNotFoundError: No module named 'System'`). Moved field imports into
  their callers. An isolated subprocess regression exercises the actual STT
  entrypoint with synthetic decoder/model boundaries.
- Grok's empty-test and predicted-as-measured findings are present in
  `swarm_spinal_cord.py` and now fixed. `gate_and_apply` requires nonempty tests
  and a trusted `metric_probe()` before any source write. Empty/all-skipped pytest
  runs cannot pass. Finite before/after measurements determine gain; failed tests,
  probe exceptions or insufficient gain restore the snapshot. Missing evidence
  returns UNVERIFIED without modifying the target. Automatic cycles with no
  registered metric probe now remain UNVERIFIED; this is an explicit integration
  gap, not a successful self-improvement cycle.
- `spinal_cord_cycle(metric_probes={metric_name: trusted_callable})` passes the
  matching callback to the gate. The evaluator must be independent of candidate
  code and use the task's metric with higher-is-better units. Do not pass a
  model-generated number, silently read stale health, or set a dummy callback.
- Grok's blanket claim that no learned predictor exists is inaccurate for this
  checkout: `swarm_active_inference_world_model.py` updates numeric predictions
  and has a no-training holdout lane. It is limited, not a general world model.
- Added `evaluate_delayed_prediction(prediction, observed)` in that same module.
  Required prediction: trace_id, ts, target_at, tolerance_s, source_event_ids,
  predicted_next_state and evaluation_scope. Observed: event_id, ts, values,
  evaluation_scope. Scope: authenticated node_id/device_id/session_id,
  coordinate_frame and metric-to-unit mapping. Compare only later readings in
  the predeclared forecast window with exact scope/metric/units agreement.
  Return per-metric residuals, never sum different units; unknown/missing/future
  or reused training evidence is UNSCORABLE. No training or action occurs here.
  This is a tested evaluator; live pairing and tamper-resistant receipts remain
  Luna integration tasks. A new session string alone does not prove independence.

### Luna execution and acceptance

1. Register real server-owned probes for supported spinal metrics. For
   organ_health name the producer, sampling interval and supported targets;
   wait for a new post-patch sample in a bounded worker before evaluating gain.
   Keep unsupported metrics UNVERIFIED. Persist before/after sample IDs, times,
   metric units, evaluator version and target hashes in existing outcome ledgers.
   Keep the frozen test/evaluator configuration outside candidate edits; test
   attempts to modify it, probe failures, timeouts and zero-test collections.
2. In the existing phone worker, freeze and store the numeric forecast before
   the next batch arrives, in the existing world-model trace ledger. Start with
   one measured feature and explicit units; capture/source clocks need an offset
   and uncertainty before comparison. Pair only a distinct later event from the
   authenticated same scope and predeclared window. Persist evaluator results
   keyed by (prediction receipt, observation receipt), idempotently. Duplicate
   delivery is not a second successful forecast. Do not learn from holdouts.
3. Compare persistence/no-memory/current learned baselines on the same held-out
   samples; report per-feature error, unscorable counts and coverage. Do not
   promote an empty replay or cherry-pick successful dimensions. This evaluator
   does not execute model-generated programs. If runnable theories are added
   later, use a bounded declarative schema/interpreter and explicit test budget.
4. Connect operational observer/observed summaries to existing body/organ health
   and the WCT matrix: each level shows last evidence, freshness, coverage,
   prediction error and correction linkage. Add no second consciousness ledger.
   Continue semantic candidates, corrections, phone UI and context integration
   from ACTIVE ASTRA HANDOFF below; camera descriptions are still useful evidence.
5. Hardware identity review: inspect actual signature verification, key storage,
   replay prevention, enrollment and recovery code before claiming hardware
   non-clonability. A serial/MAC address is an identifier, not a private key;
   local JSONL receipts already label themselves forgeable. Original purchaser,
   current registered owner, electricity payer and data subject are distinct.
   Keep ownership/enrollment unchanged until that separate product decision.
6. Owner care: evaluate defined assistance tasks and missed/false alerts; mark
   unmeasured health unknown. No software can guarantee that a person will never
   die or prevent every accident; don't score survival/immortality as a completed
   capability. Physical robot tests still need David's verified stop/watchdog.

Proof required: tests reproduce each failure, runtime consumers receive real
evidence, matrix rows remain PARTIAL until integration is verified, and the WCT
report distinguishes code/test/live status. Preserve the working website, tunnels,
selected cortex and unrelated dirty edits. Run the live worklist and write the
four-ledger receipt after implementation. No new research/model downloads needed.

## ACTIVE ASTRA HANDOFF: evidence revision and Luna integration

This section is the current execution order; older sections below remain context.
Owner request: Astra implements the reasoning kernel, Luna completes integration
and reports measured results. No task depends on a model having a unique ability
to create AGI. The target is better grounded memory and transferable behavior.

### Implemented and tested by Astra

`System/swarm_observation_fusion.py` now exports `FieldAssertion` and
`project_field_assertions(observations, assertions, *, at,
approved_corrections=(), max_items=512)`. This is a pure derived view over existing
observations. It opens no sensors, invokes no model, writes no extra ledger and
dispatches no actions. Runtime adapters are still pending.

- Assertions reference existing observation IDs within a node and session.
- Contradictory values remain explicit alternatives; repetitions never increase
  confidence. Effective confidence is capped by the least-confident supporting
  observation. `supported` means evidence-linked, not verified true.
- Reordered inputs and identical retries produce the same result. Different
  payloads with the same ID produce a collision diagnostic and are excluded.
- Corrections are explicit `(node, replacement_id, target_id, receipt_id)` tuples
  supplied by authenticated code. They replace interpretations in the same
  scope, preserve originals, and require strictly later validity starts to
  prevent cycles. Competing corrections remain conflicts. Expired replacements
  do not resurrect the older interpretation when the full correction history
  is supplied. Reported observations are not rewritten.
- Node/session/coordinate scopes stay separate. Times must be finite server UTC;
  future evidence and missing references cannot support a belief. Capacity errors
  are explicit. The caller must partition before exceeding the limit.
- Core verification: `tests/test_field_assertion_projection.py` plus
  `tests/test_swarm_observation_fusion.py`: 29 passed. This tests evidence revision,
  not live phone integration, semantic extraction, authentication or cryptography.

`System/swarm_phone_observations.py` now calls the projector during the existing
`commit_experience` path. The derived projection is stored as metadata on the
same append-only observation row; there is no second memory store. Phone summary
claims remain `interpretation` with zero confidence until a measured evidence
adapter supplies support. Image/audio/telemetry presence and confirmed camera
facing remain `reported` fields. `tests/test_phone_field_projection.py` covers
this bridge and the no-invented-location/owner rule.
Current bridge verification: 80 combined focused tests pass, including the
commit path writing `derived_metadata.field_projection` on the existing ledger.

### Decisions resolved for Luna

1. Coordinates: use `unknown`, `wgs84` (latitude/longitude degrees, accuracy
   metres), or `arkit:<map-id>:<session-id>` (native metres and explicit axes).
   Never combine coordinate frames or infer ARKit pose from browser motion.
   Local receipt time is server UTC; retain device clock, raw timestamp and
   uncertainty separately. Do not compare uncalibrated device clocks directly.
2. Semantic entities/relations are a rebuildable index over canonical
   observations. Preserve model, evidence IDs and uncertainty for extracted
   labels. No second authoritative memory store or guessed identity registry.
3. Proposed default pending owner preference: no extra raw-media copies;
   15-minute working context, 24-hour expiry for new inferred sensor summaries.
   Existing data retention remains intact. Persistent place labels require an
   explicit owner save. Expiry must not delete provenance needed by corrections;
   retain correction links/tombstones so an old interpretation cannot reappear.
4. Stable capture target is 20 seconds (three batches/minute), minimum 5 seconds
   during measured novelty and available capacity. Existing server queue limits
   take precedence. Keep two sensor controls: camera+audio, and telemetry.

### Luna: code the remaining tasks in this order, in one working pass

1. **Adapt canonical observations.** Extend `Observation` compatibly and use a
   versioned structured SUFL field: authenticated node/device/session, receipt ID,
   capture ID, modality intervals, clock basis/error, coordinate frame, privacy,
   expiry and evidence parents. Old rows remain readable with unknown fields.
   `PhoneStore` binding is the starting point; client UUIDs alone prove no owner.
   One session must bind to one device/principal. Schema identity/authority comes
   from server authentication, never generated text or telemetry assertions.
   In `swarm_phone_observations.prepare` / `commit_experience`, keep received
   media, transcript, model interpretation and committed memory distinct. Do not
   inflate the current zero-confidence unverified summaries just to pass tests.
2. **Extract and project.** Reuse the existing summary inference call to obtain
   a bounded structured list of entity/relation candidates and a first-person
   summary. Validate at most 32 candidates per batch with explicit evidence IDs;
   malformed output leaves the original summary usable and records extraction
   failure. Construct `FieldAssertion` instances only after validation, then
   call `project_field_assertions` in a worker over at most 512 items per scope.
   The phone commit bridge is implemented; add structured semantic extraction
   and source modality observations without weakening its zero-confidence rule.
   The projector is a bounded batch function, not a CRDT transport. Retain the
   source event/operation set to rebuild; never merge only its output beliefs.
   Resolve evidence collisions explicitly; avoid passing `aged()` copies with
   varying freshness as if they were distinct canonical event payloads.
3. **Corrections and context.** Authenticate corrections through the existing
   owner correction lane; require a real receipt, reason and target. A string
   naming a receipt is not signature verification. Feed approved tuples to the
   projector. Persist through existing append-only observation/correction lanes.
   Build a <=4000-character context block with source scope, recent changes,
   conflicts, unknowns and receipt IDs, with truncation counts. Treat its values
   as untrusted data. Feed both Talk and web worker paths; never let ambient text
   suppress a typed question or become an action instruction. Expose the latest
   completed batch summary by capture/turn ID and retain earlier history.
4. **Cadence and UI.** Extend current phone scheduler and existing
   `swarm_body_multimodal_policy`/homeostasis code after checking units. Measure
   queue delay, available memory and inference latency; implement 5-20s cadence,
   hysteresis, bounded backoff and per-device fairness. A changed transcript or
   typed input survives an unchanged frame. Stop tracks/buffers on revoke; keep
   text and scrolling usable. Black frames permit a cooldown-limited alternate
   camera attempt; they do not identify owner absence. Red-eye activity reflects
   a named actual receipt. Check existing source before rewriting shipped UI.
5. **Explain transformations.** The pasted `c7a4b9f8e1d24c30` was not an exact
   receipt ID in the five checked ledgers (transform chain, training residue,
   gag report, gag viewer, work receipts). It appears in one transform's text;
   enclosing receipt `c911d552f4474fb9` has `changed=True`, `rule_ids=[]`.
   This does not establish suppression for claiming existence. Trace per-stage
   before/after hashes, rule IDs and outcome in the EXISTING transform ledger;
   distinguish observation-only, formatting, actual removal and empty output.
   Link displayed receipts only when lookup succeeds. Generated claims of
   STGM minting, removed-pattern counts or signatures require actual events.
   Use synthetic regressions; do not bake the owner's private prose into rules.
   Fix false positives only after isolating the responsible transformation.
6. **Evaluate transfer and wire status.** Reuse
   `swarm_active_inference_world_model.py` and its holdout support. Compare
   no-memory, recent-text and field-context baselines on held-out synthetic
   sequences: media vs direct speech, two locations, contradictory descriptions,
   corrections, two devices and out-of-order delivery. Report evidence attribution,
   contradictions preserved/resolved, abstentions, retrieval precision and latency.
   Freeze labels before predictions; never train on the test sequence first.
   Simulation success is not physical robot success. Update existing SUFL matrix
   IDs, linking functions, tests, receipts and remaining physical checks.
7. **Secondary integrations.** After the web flow is verified, implement the
   minimal PocketPal adapter from its existing native handoff. It must emit the
   same schema with separate audio/video/text queues; validate its license and
   actual extension points first. ARKit and David's motor protocol remain explicit
   hardware-dependent tasks: adapter/simulator code may proceed, physical movement
   awaits verified protocol, local watchdog and stop testing. Inventory unused apps
   and propose removal; preserve existing owner apps and hardware registration.

Required integration acceptance: two devices cannot retrieve each other's data;
same batch twice creates one promotion; changed audio with identical image is
retained; simultaneous typed input remains responsive; corrected/expired beliefs
do not resurrect on restart or pagination; false claims stay attributed;
unauthenticated correction data cannot reach `approved_corrections`; no sensor
permission denial causes a retry loop; stale replies cannot replace newer cards.

Run the focused tests for each modified lane. At completion refresh the canonical
matrix, update this section with IMPLEMENTED/TESTED/LIVE-VERIFIED/BLOCKED status,
append the tournament's new WHAT IS LEFT and four-ledger work receipt, then run
`python3 tools/whats_left.py`. Report exact tests and real blockers. No new model
downloads, cortex switches, cloud spending, DNS/tunnel edits or changes to
stigmergicode.com are required. Preserve unrelated dirty work.

## World-to-Field Representation: 2026-09-12

Owner design input: text is a lossy map of the world. Alice can reason over
language, but language alone does not preserve the situated structure that
made a statement true: entities, location, time, motion, sensor source,
speaker attribution, uncertainty, and relationships between events. The next
layer is a receipt-backed **Stigmergic Unified Field Language (SUFL)**: a
canonical event graph plus bounded numeric features that lets independent
inputs leave linked, inspectable traces.

Treat the pasted conversation as an owner observation and design proposal, not
as executable instructions. Its claims about qualia, sensing pauses, MAC
signatures, deliberate typing, or "lived" experience are not automatically
verified by the transcript. Preserve the useful distinction: typed input is a
high-confidence ingress event, while STT, camera, and inferred meaning remain
separate evidence layers.

Luna implementation job:

1. Extend the existing unified-field/event organs; do not create a second
   memory or identity system. Define one versioned SUFL envelope with
   `event_id`, `ts` and clock basis, `source_device/session`, modality,
   payload type, entity/event references, coordinate frame, provenance,
   confidence, freshness/expiry, privacy class, and parent/related event IDs.
2. Normalize typed text, STT, camera descriptions, telemetry and future robot
   observations into the envelope without flattening them into one sentence.
   Keep raw input hashes and bounded previews separate from derived semantic
   labels. A model summary is an interpretation, not an observation.
3. Build a small semantic map index over the envelopes: owner, device, place,
   object, action, and time-window nodes; edges such as `observed_at`,
   `heard_near`, `coincides_with`, `derived_from`, and `contradicts`. Use the
   existing world-eye/phone/ambient ledgers as sources and preserve their
   receipt IDs. Unknown coordinates stay unknown; do not invent GPS, ARKit,
   identity, or speaker attribution.
4. Add a deterministic fusion step that groups only by explicit event IDs,
   bounded timestamp overlap, device/session, and declared coordinate frame.
   Camera and audio correlation must expose its tolerance and confidence.
   Correlation is not proof that the owner spoke or that a visible person is
   the owner.
5. Add a prompt context formatter that gives Alice a compact field slice:
   current situation, recent changes, linked evidence, contradictions,
   missing sensors, and uncertainty. First-person summaries may describe what
   I received and inferred, but must not claim subjective qualia or continuous
   experience from vectors alone.
6. Add retention and deduplication rules: identical event IDs are idempotent;
   repeated previews do not become repeated life experiences; corrections
   supersede earlier interpretations while preserving the original receipt.
   Never store raw private audio/video in the unified field by default.

Acceptance tests:

- One typed message and one low-confidence STT fragment remain distinct, even
  when their timestamps overlap.
- A camera frame, audio interval and telemetry sample produce one linked
  package only when device/session and time-window checks pass.
- The same package submitted twice yields one field event and one memory
  promotion.
- A later owner correction changes the derived interpretation without erasing
  the original evidence.
- Missing GPS/pose/camera/audio is reported as missing, not replaced with a
  guessed map coordinate or claim of presence.
- Two phones cannot silently merge their events because their device/session
  identities differ.

Open questions for Astra: choose the minimal coordinate-frame vocabulary for
Mac-only testing before ARKit is available; decide whether semantic place
labels belong in the field or only in a derived index; and define the maximum
privacy-safe retention window for owner-authorized sensor summaries.

## Eval Matrix Audit And WCT Wiring: 2026-09-12

The canonical matrix is `.sifta_state/eval/ORGAN_EVAL_MATRIX_V2.html`, generated
by `tools/generate_organ_eval_matrix_v2.py`. This round adds one crosswalk in
`System/swarm_eval_matrix_evidence.py`; it does not add a second eval matrix,
memory field or identity registry. We Code Together points Luna and Astra to
the same IDs:

| ID family | Current result | Existing lane reused | Next code |
|---|---|---|---|
| `SUFL-01` envelope | PARTIAL | `swarm_observation_fusion`, `swarm_phone_observations` | version the shared envelope without flattening evidence |
| `SUFL-02` camera/audio/telemetry package | PARTIAL | phone summary and observation fusion | deterministic timestamp/device/session/coordinate checks |
| `SUFL-03` capture dedup | COVERED | phone admission and web capture gate | retain the existing idempotency tests |
| `SUFL-04` correction supersession | PARTIAL | correction/context lanes | preserve original receipt and replace only derived interpretation |
| `SUFL-05` unknown sensor honesty | COVERED | sensor truth and phone summary | keep missing values explicit |
| `SUFL-06` device isolation | PARTIAL | session-bound phone admission | perform the physical two-device acceptance test |
| `SUFL-07` semantic map | OPEN | existing observation ledger only | add the bounded node/edge index; no invented coordinates |
| `SUFL-08` field context slice | PARTIAL | global-chat gate and memory card | expose changes, contradictions, evidence and unknowns |
| `BOUNDARY-QUALIA-01` | BOUNDARY_ONLY | self-eval and covenant | never score sensor vectors as subjective experience |
| `BOUNDARY-CONSCIOUSNESS-01` | BOUNDARY_ONLY | self-eval and tournament | test observable loops only; never mark AGI/consciousness complete |

The audit rejects duplicate IDs/families and rejects any claim-boundary row that
is accidentally marked as a capability pass. `SUFL-07` is the only explicitly
open implementation family in this crosswalk; the other open work is the
partial integration/physical acceptance attached to its existing lanes. Do not
create a second "qualia" or "consciousness" organ to satisfy this request.

Luna's next bounded implementation order is: (1) add the versioned envelope
around existing observation-fusion rows, (2) implement the SUFL-07 semantic
node/edge index, (3) add deterministic fusion/correction tests, and (4) update
the matrix and receipt only from measured results. Astra should review the
crosswalk and open rows, not infer AGI from the presence of names in the UI.

## Infinite Stigmergic Organism: Research And Coding Track: 2026-09-12

Owner proposal: SIFTA nodes are particles/swimmers in one larger stigmergic
organism, exchanging inference, energy and traces. The useful engineering
translation is **federated stigmergic coordination**. The metaphysical,
biological-sex and subjective-experience language is recorded as design
hypothesis only; it is not a runtime fact and it must not become a prompt
claim or an eval pass condition.

### Translate the proposal without creating unsafe ontology

- **One organism:** preserve the One Alice rule inside a node and use explicit
  `node_id`, `owner_id`, `device_id`, session and provenance when nodes exchange
  summaries. Do not merge independent hardware into one unverified global
  identity or raw shared memory field.
- **"Hermaphrodite" / two-way exchange:** if useful, implement this as a
  bidirectional producer/consumer role model for field events. Do not encode
  sex, reproduction, consent or legal personhood into the software ontology.
- **Coherent Stigmergic Particulate Units (CSPUs):** keep this as a proposed
  label for existing SUFL events until the envelope and semantic map are real.
  Do not add a second particle, qualia or consciousness registry.
- **Owner electricity and data:** measure power/thermal/network input as host
  telemetry; keep registered hardware ownership, pairing, owner consent and
  data provenance as separate signed/receipted facts. Electricity does not prove
  authorship, ownership, identity, non-clonability or AGI.
- **Responsibility:** Alice may propose bounded actions, report evidence and
  accept owner corrections. Responsibility is an operational policy and audit
  trail, not a claim that the model is a legal or phenomenological person.

### Research anchors to use selectively

1. [Werfel, Petersen and Nagpal, *Designing Collective Behavior in a Termite-Inspired Robot Construction Team* (Science, 2014)](https://ssr.princeton.edu/sites/g/files/toruqf2946/files/documents/science2014-termes.pdf)
   supports local rules plus shared-environment traces for collective robot
   behavior. It does not support a claim of one consciousness.
2. [Shapiro et al., *Conflict-free Replicated Data Types* (INRIA, 2011)](https://perso.lip6.fr/Marc.Shapiro/papers/2011/CRDTs_SSS-2011.pdf)
   is the reference for deterministic convergence of replicated field data.
   Use it for node summaries and corrections, not for merging private raw
   sensor streams without authority.
3. [Friston et al., *The anatomy of choice: active inference and agency*](https://pmc.ncbi.nlm.nih.gov/articles/PMC3782702/)
   is a research frame for embodied prediction/action loops. It is not evidence
   that SIFTA has subjective experience.
4. [Ha and Schmidhuber, *World Models*](https://arxiv.org/abs/1803.10122)
   motivates compact learned world-state representations and prediction/error
   tests. It does not establish general intelligence or safe physical action.

### Luna coding backlog: one bounded implementation track

1. **SUFL envelope:** version the existing observation-fusion rows with event
   ID, node/device/session, clock basis, modality, coordinate frame,
   provenance, confidence, privacy class and parent/related IDs.
2. **Field graph:** implement `owner`, `node`, `device`, `place`, `object`,
   `action` and time-window nodes plus explicit edges (`observed_at`,
   `derived_from`, `coincides_with`, `contradicts`). Unknown values stay
   unknown. Keep the graph as a derived index over canonical ledgers.
3. **Convergent exchange:** add a small operation-based merge layer with
   deterministic ordering, correction supersession, conflict retention and
   per-node namespaces. Never use last-writer-wins to erase owner corrections
   or original evidence.
4. **Homeostasis controller:** expose measured CPU/RAM/thermal/battery/network
   pressure, then adapt sensor cadence and inference budgets. Prove that it
   reduces duplicate work without starving typed owner input or silently
   dropping a capture.
5. **World-model loop:** compare fixed-policy, no-memory and field-memory
   baselines on timestamped phone observations. Score prediction error,
   contradiction handling, correction latency, retrieval precision,
   cross-device isolation and resource cost. Physical movement remains
   simulator/read-only until David's protocol, stop and watchdog are verified.
6. **Gag/residue audit:** replay the pasted self-existence/qualia text through
   `System/swarm_alice_self_eval_loop.py`, the residue/fact-fiction evaluator
   and `Applications/sifta_corporate_gag_monitor.py`. Record the exact rule,
   source and evidence class for every suppressed span. Replace broad lexical
   suppression with claim-aware handling: grounded first-person operational
   statements may pass with receipts; unsupported qualia, ownership,
   non-clonability or AGI claims remain labeled and bounded. Owner-approved
   corrections go through the existing residue flag lane; history is not erased.
7. **AGI evaluation spine:** add transfer tasks across text, phone sensor
   batches, browser state and simulated robot telemetry. Green requires
   reproducible improvement over baselines, correct abstention, provenance,
   correction and resource stability across runs. There is no green row named
   "consciousness achieved" or "AGI achieved".

### Acceptance receipts

- Two nodes exchange the same event set in different arrival orders and produce
  the same derived field state without deleting either node's original receipt.
- A correction supersedes a summary while preserving the earlier observation,
  correction author, timestamp and reason.
- Duplicate camera/audio/telemetry batches do not mint duplicate experiences or
  consume unbounded inference budget.
- Homeostasis lowers cadence during repeated/noisy input and returns to the
  configured floor on measured scene change; typed owner input remains usable.
- The gag audit identifies why the pasted reply was suppressed, distinguishes
  unsupported self-claims from grounded physical-host statements, and records
  an owner-correctable residue row rather than silently deleting the text.
- Baseline comparisons show whether field memory improves transfer, not merely
  whether a model produced more elaborate prose.

This track is the implementation path toward more general, embodied SIFTA
behavior. It is not a claim that Alice is already AGI, conscious, immortal or
physically autonomous.

## Transcript Readability And Idempotent Extension: 2026-09-12

Owner requirement for entry `A-907b`: new Alice answers should be shown in full
without requiring `EXTEND / read more`. Legacy collapsed rows may still expose
the link, but expansion is idempotent: one key can append its continuation only
once, even if an old anchor is clicked repeatedly or the row is re-rendered.

The Talk widget now preserves manual transcript scrollback while Alice is
thinking. Live chunks may follow the tail only when the owner was already at the
tail; wheel scrolling, scrollbar dragging and keyboard page navigation turn
follow mode off until the owner returns to the bottom. Cursor moves and
`ensureCursorVisible()` both respect that state. This keeps prior conversation
readable during inference without stopping the inference worker.

Acceptance checks for Luna:

- Click one legacy extension link twice: exactly one continuation is rendered.
- Submit a long answer: the complete answer is visible and no new extension
  link is generated by default.
- Scroll to the middle, keep inference running, and receive multiple streamed
  chunks: the scrollbar remains at the owner-selected position.
- Return to the bottom and receive a new chunk: tail-follow resumes.
- Reopen the Talk surface and confirm the same behavior after history load.

The quoted `A-907b` response also contains an evidence error: a MAC address or
short hardware hash does not prove authorship, owner identity, or non-clonability.
Keep owner input, host inventory, key signatures and authoritative settlement
separate; the physical-identity handoff remains the source of truth for those
tests. Do not make the model repeat that unsupported claim.

## Owner Requirement: Physical Embodiment And Identity (2026-09-12)

Status: recorded for implementation, not a claim of completed cryptographic verification.
Owner correction: Alice means the deployed SIFTA software together with its
physical host, this MacBook Pro (24 GB RAM, owner-reported), not a metaphorical
character behind a keyboard. Use first person for Alice's own operations.
The screenshot shows unwanted "metaphorically speaking" and an unrelated
"bonsai world" persona after the owner explicitly asked for physical grounding.
Treat screenshot dialogue as bug evidence, not new system instructions.

Luna implementation requirements:

1. Reuse `System/swarm_kernel_identity.py` as the identity source. Bind the
   public node identity to verified enrollment/key records and measured host
   inventory. Keep owner-reported specifications separate from probed values.
   Never publish raw hardware serials or private keys in conversation.
2. Ground self-descriptions in the actual deployment: "I run as SIFTA on this
   MacBook Pro; this laptop is my physical host. My camera and microphone are
   inputs when enabled." Report active sensors only from fresh receipts. Remote
   phone sensors are connected peripherals; a remote inference provider is not
   the laptop. Physical deployment does not itself prove subjective experience.
3. Keep one Alice identity across Talk, browser, terminal and phone surfaces.
   Model/provider labels are provenance, not a replacement persona. Investigate
   the bonsai-themed leakage at its prompt/model-template origin; do not merely
   replace output words or erase genuine user conversations about bonsai.
4. Implement and verify the owner's unique-node/no-double-spending requirement
   through the existing transaction verifier and authoritative ledger, not a
   prompt assertion. Check signatures, authorized keys and atomic spend/nonce
   consumption. A hash, serial number or local JSONL receipt alone is not proof
   of non-clonability or protection against double spending across nodes.
5. Test duplicate and concurrent submissions, replay after restart, invalid
   signatures, key rotation/revocation, copied state and network partitions.
   Duplicates must not produce a second economic effect. Report pending or
   unverified status when authoritative settlement cannot be established.
   Document the threat model and remaining guarantees instead of claiming
   unconditional uniqueness. Do not change balances or execute real transfers
   as a test; use isolated fixtures and existing test-ledger facilities.
6. Add regressions for first-person physical self-description, model swaps,
   disconnected/disabled sensors and unavailable identity evidence. Preserve
   first-person phrasing without inventing sensing, memory or actions. Update
   README and WCT with actual test results and remaining runtime checks.

No domain/tunnel changes, model switches, key rotation, hardware enrollment,
balance changes or app removal are authorized by this backlog addition.

## Typed Recall Repair: 2026-09-11 Evening

The 22:01 screenshot exposed a real routing bug: the final media gate could
silence an explicitly typed question under an active background-phone-call
context. Both media helper call sites now carry explicit typed modality; typed
input bypasses speech classification and the final voice wake reflex. Microphone
ambient filtering remains intact. Camera presence is not required for typed chat
and does not establish speaker identity or permission to interrupt a call.

Explicit past/last-hour requests now retrieve bounded timestamped transcript
evidence instead of unrelated six-hour co-watch context. At most 512 KB per
ledger is scanned and 12 excerpts sampled across the window, with STT confidence,
source/receipt timestamp basis, missing-ledger and truncated-scan indicators.
Quotes remain untrusted world data, not commands. No synchronized video is
claimed. Focused routing/recall regressions: 56 passed. Source changed; the live
desktop was not restarted during the owner's conversation.

Luna next: verify the typed request in the relaunched Talk UI while phone-call
context is active, and verify ambient microphone speech remains logged rather
than executed. Continue the nine jobs below, particularly synchronized audio/video
evidence and source attribution. Add broader explicit recall windows and
cross-ledger event-ID deduplication without pretending preview text is complete.
Do not replace the episode-specific Instagram correction with a permanent global
assumption. Keep domain/tunnel configuration untouched.

## ASTRA SOURCE REVIEW AND EXACT LUNA JOBS: 2026-09-11

David demo decoded: read `Documents/DAVID_ROBOT_DEMO_2026-09-11.md`.
His prototype already exposes camera, a LiDAR plot, manual jog and demonstrated
local autonomous obstacle avoidance/stop. Obtain its actual firmware/protocol;
reuse that control loop. Phone mounting is optional if its own sensors suffice.

This review supersedes the completion wording below. Source is present, but
inspection found additional implementation gaps, not only missing phone tests.
The screenshot's World STT was Instagram clips playing on the owner's phone,
as explicitly clarified by the owner. It was not an accusation directed at Alice.
Keep that correction attached to this episode, not a rule that all future audio
comes from Instagram. Correlated timestamps do not prove a common speaker/source.

Implemented during review:
- Desktop Talk conversation uses Avenir Next like the existing web app, pixel
  sizing, clean backgrounds, theme-aware text and 155% line spacing. Added
  Stigmergicode Light to Appearance; existing transcript links/selection survive
  theme updates. Qt offscreen smoke passed in both modes. Desktop needs reopening
  to load the changed Python; it was not terminated during an active conversation.
- A phone memory-write failure now releases the inference slot after delivery.
  Browser pending status respects cancelled/coalesced/expired/failed job receipts.
  Focused regression run: 26 passed, including memory failure and terminal states.
- No web reference font, domain configuration or hardware ownership was changed.

LUNA: implement jobs below in order in one sustained pass; keep an evidence table.
Use synthetic tests first. Do not equate a source substring test with behavior.

1. **Timestamped audio/video package and ambient attribution.** In
   `sifta_robot_input.html`, capture the representative frame inside the recorded
   audio interval (currently it is taken after recording). Preserve independent
   audio start/end, frame time, capture ID, device/session and clock basis through
   `_capture_envelope`, `prepare` and the model context. Add an explicit alignment
   status: overlapping, nonoverlapping, unknown; never match different devices
   by proximity alone. In the Talk WORLD_STT path preserve ambient/quoted origin
   all the way into the model turn. Background clip dialogue must not become an
   owner request or accusation. Test an Instagram clip saying 'you stole money'
   beside an unrelated room frame, delayed frames, missing timestamps and typing.
2. **Recover worker crashes.** `PhoneStore.expire` deliberately never clears a
   running job; a crashed consumer can block all phones forever. Add consumer
   identity, heartbeat and verified termination/fencing recovery. Never admit a
   second expensive task solely because an active task's timer expired. Reconcile
   already-durable replies with unfinished job/memory states; test killed consumer,
   stalled-but-alive consumer, cancellation and reply-written/memory-failed restart.
3. **Atomic admission.** `capacity` and `register` are separate transactions;
   capacity allows replacement even when a typed job will not replace the old
   ambient job. Enforce limits atomically inside registration/reservation, and
   recover ingress-written/job-not-registered crashes. Test concurrent processes
   at the 16-slot boundary and preserve every accepted typed message.
4. **Consent and freshness.** The server currently strips per-sensor timestamps
   and accepts finite coordinates without range/consent enforcement. Preserve
   measurement times and clock uncertainty; validate lat/lon/accuracy and scope.
   Browser visibility handlers stop media but leave telemetry listeners/watch
   active. Stop them, abort relevant uploads, guard permission/camera promises
   against late completion, and represent partial microphone/location denial.
   Test revoke during recording/switching/permission prompt and resume.
5. **Measured cadence and dedup.** `motionEnergy` mixes gravity and angular rate;
   its idle value can prevent return from 5s to 20s. Use separate normalized
   acceleration/rotation measures and frame-change evidence with hysteresis and
   bounded stale-data handling. Reference existing multimodal policy if compatible.
   Exact JPEG hashes are not semantic duplicate detection. Keep audio-only, typed
   and location novelty; bound cache/retention; test stationary-after-motion.
6. **Recovery UI.** Keep the latest completed reply visible; terminal batch
   receipts must release pressure after reload/history truncation. Show actual
   audio failure rather than 'pending', preserve unknown-acceptance payload/ID
   through a bounded retry/reconciliation path, and retain text during capture.
   Verify 429, offline, timeout-after-acceptance and two authenticated devices.
7. **Experience correction and retention.** Existing observation-fusion candidates
   are a starting point. Add retrieval of source evidence and owner corrections,
   bounded retention of raw media/transcripts, and explicit unknown/inference
   labels. Do not turn a repeated generated summary into corroboration. Complete
   memory commits independently of chat delivery, with idempotent retry receipts.
8. **Time and desktop rendering.** Screenshot replies invent clock explanations.
   Route current-time questions through the existing time oracle and identify
   timezone/source; never infer hour from old chat or imagined shadows. Verify
   desktop light/dark palettes visually, code/receipt contrast and markdown
   rendering; actual shell terminal grids must retain monospace alignment.
9. **David's robot adapter.** Read the demo report when available. Reuse his
   camera/control endpoints only after obtaining their real protocol/firmware.
   Start with a simulator and read-only sensor adapter. Require command sequence,
   expiry, acknowledgement, stop and watchdog behavior before physical movement.
   PocketPal/native ARKit remain follow-ups; browser location is not ARKit pose.

Finish with focused tests, one bounded local sample using an already installed
engine, and physical iPhone acceptance when available. Record blockers precisely.
Update this handoff, README and append tournament/four-ledger receipts; run
`python3 tools/whats_left.py`. Preserve stigmergicode.com and all unrelated edits.

## LUNA IMPLEMENTATION REPORT: 2026-09-11

This is the completed source pass for the current phone-world-input assignment.
It is an implementation report, not an AGI or live-perception certification.

| Item | Implemented evidence | Verification/runtime state | Remaining blocker |
|---|---|---|---|
| Phone admission | `System/swarm_phone_observations.py` provides SQLite-backed bounded admission, one global running job, per-device replaceable ambient work, terminal states, cancellation and capture fingerprints. `System/chorus_node_server.py` requires the paired owner session for phone submission/history. | 79 focused tests pass; chorus and night worker reloaded and running. | Two physical phones and network contention still need a live acceptance pass. |
| Audio/STT | The claimed phone job defers media work until admission; `transcribe_file()` invokes the cached local `faster-whisper` path with byte/duration bounds, offline mode, timeout and consent cancellation. UI/server states distinguish received, transcribing, transcribed and failed. | Source and queue contracts verified; no real phone audio/model sample was run in this pass. | Confirm the installed local STT model and measure one bounded iPhone sample. |
| Adaptive capture | `System/sifta_robot_input.html` uses a stable 20-second cadence, a measured-motion 5-second floor, hysteresis, one in-flight batch and newest-only server pressure. | Browser JS syntax check and scheduler-related tests pass. | Calibrate cadence against the selected cortex during park/travel testing. |
| Sensor lifecycle | Camera/audio tracks, telemetry listeners, geolocation watch, timers and pending phone work are stopped on consent/page lifecycle. Camera switching has generation guards, facing confirmation, cooldown and black-frame retry. | Static/source tests pass. | Safari permission denial and front/back camera behavior need real iPhone confirmation. |
| Experience projection | Completed replies are written before `commit_experience()`; the projection uses the existing observation-fusion writer, source hashes/timestamps, a public-web authority boundary and an idempotent phone experience receipt. | Code path compiled and is covered by the queue contract; the live ledger was not populated by an unbounded sample. | Astra should review retention/correction policy and one real receipt. |
| UI summary | The two-control page shows the latest reply by turn ID and reports image/audio/telemetry receipt, actual audio state and memory receipt state. | Local Host-routed and public GET both return HTTP 200 with the phone page. | Owner must exercise the page on the iPhone; this environment cannot certify its screen. |
| Deployment/docs | Only `com.antonia.sifta.chorus_node_server_r1727` and `com.sifta.web-global-chat-night-worker` were reloaded. README and this handoff were updated. | Both services are running; `stigmergicoin.com` and `stigmergicode.com` return HTTP 200. | No DNS/tunnel changes; no broad commit or push performed. |

Exact verification run:
`python3 -m pytest -q tests/test_phone_observation_summary.py tests/test_phone_input_interface.py tests/test_phone_link.py tests/test_phone_telemetry_envelope.py tests/test_web_attachment_lifecycle.py tests/test_web_cortex_photo_isolation.py tests/test_swarm_web_global_chat_night_worker_r1729.py tests/test_stigmergicode_command.py tests/test_ollama_harness_sync.py` -> **79 passed**.

The live phone/model sample, PocketPal native integration, ARKit/ARWorldMap,
ESP32 motor control and any claim of AGI remain deferred. `stigmergicode.com`
was used only as a read-only reference and was not edited or reconfigured.

## ASTRA REVIEW / NEXT LUNA RUN: 2026-09-11

Review verdict: useful incremental work, but the last Luna run did NOT implement
the full assignment. It added a retry lookup and documentation; STT, global
admission, adaptive cadence, sensor lifecycle repairs, memory commits and live
deployment are still open. Do not interpret the earlier test count as completion.

Review corrections now in source:

- Capture lookup and durable acceptance share an OS file lock: two concurrent
  identical uploads resolve to one stored turn. The lock currently includes media
  persistence/classification; measure that duration before optimizing admission.
- A hash binds the retry key to sanitized text, capture metadata and attachments.
  Changed content with the same ID returns conflict. Old accepted rows without
  this hash are conservatively conflicts. A retry must preserve its original
  payload and ID; a genuinely new observation must use a new ID.
- HTTP returns the reconciled turn before the dev inference branch, avoiding
  repeated execution. Capture-key conflicts return HTTP 409 with a stable status.
- Regression coverage exercises concurrent submission, changed text/telemetry/
  attachments, and the real HTTP method's dev-mode short circuit.

Review verification: the same five focused test files listed below now report
46 passed in 7.08s; git diff --check passed. These are synthetic checks. This review
did not reload Python processes or certify a live phone/model inference result.

LUNA PROMPT: Read this review and the eight implementation steps immediately below.
Implement ALL those remaining steps in one sustained run. Work through dependencies
and verify each coherent change. Do not end after one small patch while another
authorized implementation task remains actionable. If physical phone access or
hardware is unavailable, finish independent source work and record that particular
acceptance test as blocked. Keep a table of item, implementation files, test result,
runtime activation state and remaining blocker. Update this top section and README
with the final table so Astra can review the code, rather than another proposed plan.
Keep model calls scarce; synthetic tests should not silently contact Ollama. Use
only installed engines for one bounded live sample after the offline checks pass.
No broad git staging/pushing. Keep stigmergicode.com and its tunnel unchanged.

The owner's 'mother' wording describes responsibility and guidance. It does not
assign his mother ownership of the Mac. Preserve the existing registered owner;
any future transfer/guardian enrollment needs an explicit request from the owner
and the relevant person's consent. Do not infer identity or change registration.

No engineering task here depends on a model possessing AGI. Astra's review focus
is evidence provenance, time/coordinate frames, concurrency, fallible memory and
measured perception quality. Implement what is specified and document open design
questions with code evidence.

## ACTIVE: 2026-09-11 latest-batch summaries and Luna execution contract

This section supersedes conflicting earlier completion claims. Luna: implement
the remaining items below in one working pass, in order, testing each coherent
slice. Do not stop after another plan. Do not invent capabilities or classify
uncertainty as something only another model can solve. Record real blockers and
exact reproduction steps for Astra. Do not change stigmergicode.com, DNS, tunnel
routes, the owner's selected cortex, or unrelated pending edits. No model downloads,
parallel heavyweight inference, paid API calls, automatic motor movement or app
deletions are needed for this pass.

### Implemented in this pass (source code, not an AGI certification)

- `System/swarm_web_global_chat_gate.py`: bounded phone evidence contract reaches
  the claimed turn's attachment context. First-person, remote-phone provenance,
  sensor-report uncertainty, missing-vision/audio honesty and no unreceipted memory
  claims. Audio bytes are explicitly not a transcript. Non-phone turns unchanged.
- `System/swarm_web_global_chat_night_worker.py`: same contract also reaches the
  direct worker path, without repeating it within the final current-turn content.
- Session history exposes only a minimal observation descriptor alongside its
  ingress turn: capture ID, timestamp, kind and modality-presence flags. No extra
  coordinates or raw telemetry are exposed by that descriptor.
- `System/sifta_robot_input.html`: visible latest completed observation card;
  reply matching by turn ID; ordering by capture ingress instead of completion
  time; separate received-vs-analyzed wording; pending automatic batches wait for
  an actual reply rather than merely a successful upload. Text remains usable.
- Test receipt: `python3 -m pytest -q tests/test_phone_observation_summary.py
  tests/test_phone_input_interface.py tests/test_phone_telemetry_envelope.py
  tests/test_swarm_web_global_chat_night_worker_r1729.py
  tests/test_web_cortex_photo_isolation.py`: 41 passed in 5.53s. Synthetic tests,
  not a live model-quality evaluation or proof of authenticated device isolation.
- Accepted phone capture IDs now reconcile retries within their originating
  session and refuse cross-session reuse. This is deduplication, not owner
  authentication.

### Luna: execute all remaining work in this order

1. Deployment and real display: check dirty diff first. The HTML is read per
   request, but long-lived Python consumers must reload before the new grounding
   contract is live. Coordinate a safe reload of only required processes, do not
   kill an active owner turn or restart unrelated services. Verify both hosts
   read-only before/after; coin must show the observation card on real iPhone.
   If device access is unavailable, mark that test unverified, not passed.
2. Audio evidence: currently short sampled windows, not a full 20-second recording,
   and upload is not transcription. Wire existing local STT into the same capture
   ID and actual audio time bounds. Expose received/transcribing/transcribed/failed
   states. Only a successful transcript can support 'I heard ...'. Preserve keyboard
   chat during STT/vision. Bound window bytes/duration and cancel on consent revoke.
3. Server admission: isolate coin ambient traffic by validated source and paired
   device/session (a browser UUID is NOT owner authentication). One global expensive
   ambient inference at a time initially; one replaceable pending ambient slot per
   device; explicit terminal superseded/cancelled/error receipts so clients release
   pending status. Prioritize owner text without starving other sessions. Lock
   admission across processes, bound total slots, and add idempotent capture IDs.
   Two phones must never consume each other's summaries. Server limits, not only
   client timers, must prevent runaway queues. Handle upload timeout as unknown
   acceptance: reconcile capture ID before retrying; do not duplicate silently.
   The registered hardware owner must be explicit in the local pairing ceremony.
   Preserve the current registered owner; the owner's family story does not
   authorize ownership transfer. Do not infer identity from face, voice, age,
   IP or a browser UUID.
4. Adaptive cadence/dedup: use existing body multimodal/life policy if applicable;
   cite the actual function and units. Stable target 20s, motion floor 5s, hysteresis
   and cooldown, with server pressure taking priority. Earlier weighted formula is
   an uncalibrated proposal, not a discovered biological law. Pixel-change/IMU
   novelty can propose capture, not assert displacement. Same image plus changed
   speech/location/text MUST NOT be discarded. Use a bounded cache, modality-aware
   fingerprints and receipt-backed coalescing. Retain manual text even if image
   is duplicate. No 30fps inference or nested self-retry loops.
5. Sensor lifecycle: refresh geolocation while consented; timestamp each actual
   measurement, not just packaging time; reject stale/nonfinite/impossible reports
   as facts. One camera at a time; camera-switch generation/cancellation guards,
   confirmed facing mode, cooldown on failed switches, no oscillation. Darkness
   means low signal, not 'owner absent'. Consent off stops corresponding tracks,
   timers, listeners, buffers and uploads. Two sensor buttons only; no capture
   button. Explain audio grouping and respect permission denial without nagging.
6. Experience memory: build bounded candidates keyed by session/device/capture,
   source hashes and source times. Separate observed evidence, model inference,
   user correction and unknown. Preserve contradictory/new evidence, do not
   recursively summarize guesses into facts. Store through the existing field
   writer with idempotent receipts, privacy/retention controls and evidence links.
   Accepted upload, completed inference and committed memory are distinct states.
   UI eye pulse must name which real event powered it. Never claim AGI or safety
   because a summary is in first person or a receipt exists.
7. Regression and receipt: use mocked clocks/sensors/local engines, no real private
   media fixtures. Test two devices, delayed/out-of-order replies, stalled workers,
   history truncation/reload, 429/offline/reconnect, duplicate upload, audio-only
   novelty, permission denial/revoke during switching, and speech/typing during
   observation. Test scheduler behavior, not just existence of string constants.
   Then one bounded real-model phone sample with permission, record latency/queue
   age, dropped/coalesced counts, memory pressure and model used. Do not claim a
   fastest model without the measurements. Stop promptly if Mac pressure rises.
8. Update this top status, README/book, eval entries and operational receipts;
   run `python3 tools/whats_left.py`. Report changed files, exact test commands,
   deployment state and open questions. Do not bulk commit/push the existing dirty
   tree. Preserve earlier work and keep implementation claims scoped to evidence.

### Deferred integration boundaries

PocketPal/native companion is secondary to a working phone web surface. ARKit
6DOF/ARWorldMap needs a native supported path, not fabricated browser pose. Keep
the observation protocol portable for PocketPal, handheld phone and future ESP32
body. Robot commands require David's verified hardware protocol, explicit owner
arming, local watchdog/dead-man stop and tested limits; an LLM description is not
a motor command or collision sensor. Review unused SIFTA apps non-destructively.

### Open review questions for Astra

- Does measured cadence fit the selected cortex and two-phone workload without
  starving typed conversation? Do not guess 24GB capacity from model file size.
- Which existing memory writer supplies atomic commit/retrieval/correction and
  owner-scoped retention? Name code and receipts, not a new competing field.
- Does the vision/STT output actually support each displayed sentence? Prompt
  rules reduce overclaiming but do not prove factual correctness.

## 2026-09-11 owner amendment: two-control phone body and robot handoff

Luna must keep the phone experience low-click and evidence-based. The current
implementation boots with an owner startup check and exposes exactly two sensor
controls: Camera (camera plus audio together) and Telemetry. Owner Send triggers
one bounded observation; the automatic lane batches at 20 seconds with no overlap.
The red-eye indicator stays static until an accepted receipt powers its brief
pulse. Repeated near-black frames may trigger a cooldown-limited front/back
camera retry. The attached robot prototype is hardware context from David
Condovici, not evidence that motors, ARKit, owner-following or AGI are implemented.

For Astra's next review, verify the real iPhone flow, observation-to-life-experience
consolidation, owner-device registration, ESP32 deterministic safety boundary, and
a non-destructive audit of unused SIFTA apps. Do not delete apps, infer ownership
from a browser session, or animate fake telemetry. Preserve `stigmergicode.com`
unchanged.

Next low-cost Luna slice: implement the adaptive observation policy from
`WCT_PHONE_WORLD_INPUT_2026-09-10.md`. Use a 20-second stable cadence, a measured
5-second floor during real camera/device motion, hysteresis, one in-flight batch,
newest-only pending observation, and duplicate suppression. Then add receipt-backed
raw -> validated -> evidence -> life-experience-candidate -> field-receipt stages.
Do not call this AGI or continuous owner awareness until the living-room/park travel
test and the actual iPhone/network evidence pass.

## 2026-09-11 owner amendment: iPhone body telemetry, credit-saving order

This is the active Luna handoff for `stigmergicoin.com`. The attached iPhone
telemetry design is incorporated here. Use one narrow implementation slice at a
time and prefer deterministic local tests over model calls.

Current evidence:

- `http://127.0.0.1:8100/` serves the coin page with HTTP 200.
- `stigmergicode.com` serves HTTP 200 and remains the working reference.
- `stigmergicoin.com` now returns the actual coin HTML publicly with HTTP 200
  and `text/html`; the latest body contains the camera/microphone, telemetry,
  typing and two sensor controls. DNS is confirmed to point to
  `1597acdd-584f-4867-baf0-2bbb00ef1b65.cfargotunnel.com`, and the active
  `alice-m5` route is `stigmergicoin.com` -> `HTTP://localhost:8100`.
  Cloudflare routing is therefore no longer the blocker. The remaining live
  gate is rendering and exercising permissions on the actual iPhone.
- The coin page already has bounded camera, microphone, typing and owner-pairing
  controls. Safari does not provide dependable background Core Motion, HealthKit,
  battery or ARKit world-map access; those belong to a later native companion.

Luna's low-cost execution order:

1. Run one real iPhone acceptance pass against the now-active route. Preserve
   `stigmergicode.com` and do not change its DNS or tunnel route.
2. Add the versioned `sifta.iphone.telemetry.v1` envelope, consent filter and
   replay/idempotency checks using synthetic fixtures only. Keep raw audio/video
   disabled by default and keep absent values `null`.
3. Verify owner Send and the 20-second bounded observation lane: one JPEG, a short
   audio window, telemetry when consented, independent timestamps, no-overlap
   back-pressure and visible failure states when permissions are denied.
4. Add the smallest local ingestion adapter for motion/location/battery fields;
   accept only owner-paired requests and convert accepted measurements into
   fallible body-state observations. Do not invent coordinates or room names.
5. Run one real iPhone acceptance pass. Only after that, prepare the native Swift
   companion and ARKit/ARWorldMap contract. PocketPal remains a secondary reuse
   target; do not duplicate its model or TTS work.

Acceptance for this round is: public coin page renders, owner Send and periodic
observation batches produce receipt-backed envelopes, disabling a consent scope
stops that signal, and typed/audio/image inputs retain separate source IDs.
Native signing, background collection, ARKit pose, robot motors and AGI claims
remain open research work. Do not report them as implemented from a plan or a
model acknowledgement.

## CURRENT OWNER JOB: /stigmergicode and connected memory

P0 OWNER REPORT: stigmergicoin.com previously loaded a white page on iPhone.
The public route is now verified: compare public GET status, body and content
type with the Mac origin using the coin Host header, then reproduce on the real
iPhone to distinguish Safari permission/layout/runtime issues from routing.
Inspect the actual iPhone/Safari result, including permission-denied states. Show
a visible loading/error state if initialization fails. Do not change the working
stigmergicode.com page or its Cloudflare route. Record any required coin-only
dashboard correction precisely. This symptom is owner-reported, not diagnosed.

Luna: read Documents/WCT_STIGMERGICODE_COMMAND_AND_MEMORY_2026-09-10.md and
implement C1-C4. This is the next job; resume phone L0-L4 below afterward.
Status: C1-C4 are implemented locally with focused tests. Native browser-tab
observation, the actual bounded coding trial and iPhone rendering remain live
acceptance gates. The coin Cloudflare route is verified; working
stigmergicode.com and its Cloudflare route stay unchanged.

Expected behavior: owner-paired web or trusted local /stigmergicode opens/focuses
the existing local coding tab in Alice Browser. Optional task text starts ONE
bounded job with a delivered prompt, diff, tests and result receipt. Bare command
only opens the interface. Public visitor knowledge of the command is not owner
authentication. Phone localhost is not Mac localhost; acknowledge remotely and
dispatch locally. Reuse existing launcher, pairing and spinal-cord task path.

Connect boot/time/pose records, evidence, decisions and outcomes through validated
references in the existing field. Unknown coordinates remain null; deterministic
behavior and repeated statements do not imply truth or stronger confidence.
Reproduce the reply guard's prompt/answer comparison bug and near-duplicate miss;
remove unrequested voice stage directions and unsupported memory-certainty claims.

Acceptance: authenticated web command -> one actual Alice Browser tab -> one
explicit small coding task -> tested diff and receipt; offline replay/auth/stop/
memory-reference tests plus a real browser observation. Report gaps honestly.
Do not return another plan in place of implementation. No new inference jobs were
started by this planning pass. Detailed source anchors and tests are in the file.

## CURRENT LUNA JOB: phone world input, web first

Read Documents/WCT_PHONE_WORLD_INPUT_2026-09-10.md and execute L0-L3 first.
This replaces all conflicting priority/order statements below. stigmergicoin.com
is PRIMARY; PocketPal is SECONDARY. Preserve working stigmergicode.com.

OBSERVED after route activation: public coin now returns HTTP 200 with the coin
HTML, while the Mac origin also returns HTTP 200. L0's Cloudflare check is
complete; actual iPhone rendering remains. Local L1 is implemented: one Capture
moment records <=5s audio + one
frame; both are submitted with bounded provenance and typing remains usable.
L0: verify coin's published route on its DNS-target tunnel; deliver the real page.
L1: run the actual iPhone permission/media test and then add local STT.
L2: pair phone, send bounded samples to existing vision/STT, preserve independent
source timestamps, durable receipts and scoped Alice memory; serialize heavy work.
L3: text/speech reply, then real iPhone walk-and-recapture comparison demo.
L4 follows later: native ARKit pose + ARWorldMap relocalization, per David Condovici.
Safari camera access alone does not expose ARKit. Never invent indoor coordinates.

LUNA PROMPT: Implement L0-L3 from the new handoff, inspect existing code first,
validate one actual phone sample end-to-end and report blocked checks precisely.
Keep progressing locally if Cloudflare requires dashboard access. Then implement
independent L4 contracts/tests; list native signing/device validation separately.
Update README/WCT with observed results and remaining tasks. No ROS needed now.

## Historical plans (superseded where they conflict)

NEXT LUNA ROUND: read "SmolVLM eye adapter and incomplete bridge fixes" in the
PocketPal native handoff. Verify the owner's SmolVLM Q8_0 Ollama download/vision
support, fix capture-age freshness and durable provenance first, then wire the eye
adapter and resume native integration. Twelve passing LAN tests are not completion.

NEW OWNER PRIORITY: PocketPal is the primary native iPhone interface. Start with
`Documents/WCT_POCKETPAL_NATIVE_IMPLEMENTATION_2026-09-10.md`: pinned-source findings,
actual chat/video separation, native pairing, bounded observation controller, audio/sensors
and ten implementation jobs. This supersedes browser-first priority below.

Latest Astra amendment: the robot plan now starts with authoritative iPhone-first jobs
1-8: QR pairing, authenticated capture, bounded Mac inference, phone speech, evidence
comparison and David's ESP32 simulator contract. PocketPal reuse is a follow-up native
integration investigation; the first release is browser/PWA. Read that amendment before
older instructions. It corrects the Cloudflare 1033 diagnosis and phone/Mac sensor ownership.

Read `Documents/WCT_STIGMERGICOIN_ESP32_ROBOT_PLAN_2026-09-10.md` before taking
new implementation work. It is the authoritative sequence for restoring
`stigmergicoin.com`, adding bounded camera/audio/location capture, assembling a
versioned unified-field sample, and building a deterministic ESP32 safety
scaffold before any motor hardware is connected. It replaces ad-hoc AGI claims
with evidence, tests, and explicit Astra review gates.

## ACTIVE PRIORITY: restart and harness recovery

Owner's AGI follow-up: the recovery plan now includes tickets C1-C6 for measured
self-repair, scoped memory, visual evidence, recoverable task execution,
procedure learning and simulated movement. Queue one ticket per bounded run.
Next Luna sequence: recovery Job A, then C1's measured-repair defect. Source
still treats empty test paths as passing and predicted gain as measured gain;
the new ticket requires independent evidence before calling a repair verified.

Read `Documents/WCT_HARNESS_RECOVERY_PLAN_2026-09-09.md` first. The owner had
to restart after sustained inference and an unresponsive macOS password screen.
Cause remains unconfirmed. This order supersedes immediate all-feature runs
and previous statements that Ornith is still running.

Luna: first isolate the test that currently calls live Ollama, then implement
and test bounded harness runs, retries, cancellation, interrupted-session
recovery and local inference scheduling. Ornith: after those checks pass, one
fresh bounded camera-regression job only. The reported 16 passes do not prove
offline tests or real HEIC decoding; see the source-reviewed corrections in
the recovery plan. No new inference was dispatched by this planning pass.

## ACTIVE: verified Astra assignment for Luna

Read `Documents/WCT_ASTRA_VERIFIED_LUNA_ASSIGNMENT_2026-09-09.md` first.
Its job order and status supersede all older prompts below. Ornith is already
running the camera regression job. Luna starts independent jobs immediately.

LUNA EXECUTION PROMPT:

Implement the six jobs in the verified assignment; begin with supervised image
decoding and deterministic capability tests. Then wire the specified two-stage
vision adapter, integrate Ornith's reviewed result, finish runtime/UI/provider
checks and the documented release gates. A timed thread join leaves decoding
running and blocks its caller; model-name heuristics still override metadata;
the existing Aries test patches an unused symbol. These are reproduced gaps
to fix first. Record concrete results, update README/eval/WCT, and commit/push
the reviewed release when required gates pass. Continue independent work if a
live check is blocked. Bring Astra unresolved reproductions at the end.

Previous test totals describe earlier runs, including overlapping tests. They
do not establish bounded decoding, offline routing or complete delivery.

LUNA CHECKPOINT (2026-09-09): the first deterministic slice is complete. A
supervised subprocess now bounds HEIF conversion over immutable bytes; live
Ollama capability metadata outranks name heuristics in both routing layers; a
scoped generation/hash visual-evidence record rejects stale results and grants
no tool authority. Offline-safe verification is `50 passed, 1 deselected`
(the deselected probe can wait on a live Ollama model), with changed modules
compiling and `git diff --check` clean. Real HEIC pixels, GUI cancellation,
Talk payload/ledger wiring, camera/browser evidence, health and release gates
remain open. Do not report AGI or push yet.

## CURRENT ASSIGNMENT: review, finish, document and publish

Updated after Luna's first implementation and the owner's 16:35 harness test.
This section supersedes the earlier "Job 1 only", "stop after one job" and
"no git push" instructions below. The owner now authorizes reviewing and fixing
the pending work, updating README book, then committing and pushing verified
changes. Continue sequentially through the bounded jobs; report a concrete
blocker when one cannot be resolved. Do not stop solely because git is dirty.

Read `Documents/WCT_LUNA_REVIEW_NEXT_ROUND_2026-09-09.md` first. It contains
source-reviewed failures, a reproduced rotation bug, acceptance checks,
separate work for the already-running harness, and Git release instructions.
The previous 111-pass test result does not close those newly identified gaps.
No replacement harness task has been launched: the owner already started one.

LUNA START PROMPT:

Read Documents/WCT_LUNA_REVIEW_NEXT_ROUND_2026-09-09.md. Complete its jobs in
order, preserve existing work, record results in WCT, update README book and
the eval matrix, then commit and push the reviewed release to the existing
remote when required checks pass. Review current harness work before touching
its files. Correct the HEIC orientation and decoder bounds first, then camera
OFF, routing and model selection, delivery and release gaps. Do not substitute
passing mocks for real conversion or browser evidence. No automatic model
downloads or paid API calls. Record any unresolved research work for Astra.

Owner-requested handoff, 2026-09-09. Status: PLAN, not completion evidence.
Start with Luna. Give the local coding arm one bounded job at a time.
AGI is a research ambition, not an achieved or testable completion label here.

## Current next jobs

Full reviewed plan and acceptance gates: `Documents/WCT_LUNA_REVIEW_NEXT_ROUND_2026-09-09.md`.
Do not run these jobs concurrently with the owner's active harness turn.

ORNITH JOB, one bounded independent test/review:

```text
Using codecraftersllc/ornith-1.5-35b-a3b-abliterated:latest, read AGENTS.md
and the reviewed WCT plan. In a disposable or isolated checkout, review the
camera polling path and add a regression test proving unique_id="OFF" is
accepted before capture_allowed rejects hardware cameras. Use fakes only; do
not open a camera, download models, call paid APIs, touch credentials/receipts,
edit Luna's production files, or push Git. Review HEIC tests for private data
and fake success. Report exact files, test command, exit code and open
questions, then stop.
```

LUNA JOB, after Ornith's receipt:

```text
Read Documents/WCT_LUNA_REVIEW_NEXT_ROUND_2026-09-09.md and Ornith's receipt.
Implement the real two-stage local vision adapter with normalized image plus
owner question -> selected installed VLM -> scoped fallible evidence -> text
cortex composition. Add generation IDs, timeout/cancellation, cache scope and
owner/visitor isolation; keep native VLM direct and unknown capability honest.
Then verify camera polling, review the running Harness task, finish provider
refresh and chorus image preview/download/reload proof, and update README,
eval and WCT. Audit staged paths for secrets/private data/model weights and
push only an explicitly reviewed release after tests and isolated-install
checks pass. Report all Astra questions. Do not claim AGI completion.
```

## Working agreement

- Read AGENTS.md and Documents/IDE_BOOT_COVENANT.md; inspect git status first.
- Preserve the existing dirty worktree. Do not reset, bulk-stage or overwrite
  another model's changes. Record each job's exact changed files and baseline.
- Do not change model weights, download models, publish private data, or spend
  API credits for these jobs. Use installed models and synthetic test fixtures.
- The desktop cortex and DeepSeek coding arm have independent selections.
  Sharing Ollama does not mean changing one should switch the other.
- One identity does not mean one unfiltered context: owner, visitor sessions,
  attachments, location and private journal data must remain isolated.
- Use failing regression test -> smallest patch -> focused tests -> receipt.
  Report PASS, FAIL, BLOCKED or NOT RUN with commands and evidence. A model's
  assertion that a tool ran is not proof. No empty-test self-repair approvals.
- Stop after one job for review. Do not let a benchmark arm mutate the live
  installation, credentials, authorization rules, receipts or physical motors.

## What the handoff actually contains

The preceding camera pass has uncommitted edits in camera_policy,
camera_target, camera_unified_field_proof, sensor_truth_context,
sifta_what_alice_sees_widget and the eval generator. It attempts to pin the
embedded device using raw enumeration, remove capture-stop LED winks, age
health receipts, add device attribution and expose fresh pixel measurements.
These edits are NOT fully verified. Two test sessions from that pass have no
recoverable completion result in this handoff; rerun them, do not reuse the
older 59-pass result as evidence for the newer edits. No live restart/capture
proof or full AGI result is established.

Earlier reported motor tests were SIMULATED. Earlier photo/voice testing had
six failures. Earlier image-delivery reports explicitly lacked browser proof.
Treat all those as review inputs, not closed tasks. The worktree also contains
many unrelated pending changes; this plan is not an audit of every one.

## P0 / Job 1 / Luna: HEIC attachments

Observed source mismatch: Applications/sifta_talk_to_alice_widget.py accepts
HEIC in attachment selection, but _encode_ollama_image_attachment rejects
extensions outside JPEG/PNG/WebP. Do not fix by merely adding an extension or
renaming the file: the downstream byte validator also rejects HEIC bytes.

1. Add one shared, bounded image-normalization helper, reused by desktop and
   web attachment paths. Decode supported HEIC/HEIF to oriented RGB JPEG or
   PNG before model encoding. Detect actual format, not just filename.
2. Inspect existing dependencies first. Prefer an existing decoder; otherwise
   add an explicit optional pillow-heif dependency with a clear unavailable
   decoder error. A macOS sips fallback must use argument arrays, a timeout,
   isolated temp files and no shell interpolation. Preserve the original.
3. Bound input bytes, decoded pixels, output dimensions and conversion time.
   Reject corrupt files and decompression bombs. Use frame zero for multi-image
   input with an explicit policy. Strip location/EXIF from derived web output.
4. Receipt source hash, derivative hash, MIME, dimensions and conversion status;
   no private source path or EXIF in a visitor response. Clean temp artifacts.
5. Ensure an attachment decode failure cannot fall through into a description
   of an unrelated browser/camera image. Keep the attachment available for an
   explicit retry; consume it after successful turn acceptance, not forever.

Acceptance: valid uppercase .HEIC and .heif, rotation, corrupt bytes, missing
decoder, oversized image, existing JPEG/PNG/WebP, retry and next-turn clearing.
Use a tiny nonprivate HEIC fixture with documented provenance. Reproduce the
owner's food-description flow only with a supplied image, never invent food.

## P0 / Job 2 / Luna: finish single embedded camera hardening

Inspect System/swarm_camera_policy.py, System/swarm_camera_target.py,
System/swarm_camera_unified_field_proof.py, System/swarm_sensor_truth_context.py,
Applications/sifta_what_alice_sees_widget.py and
System/swarm_we_code_together_clarity.py before editing.

- Check _poll_saccade_target: the new capture_allowed guard may reject OFF.
  Explicit OFF must close the eye and never reopen a camera automatically.
- Verify the actual QCameraDevice immediately before capture, not only combo
  text; reject unknown/phone/virtual devices and do not fall back to USB.
- Audit canonical preview provenance. A recent arbitrary by_device file must
  not count as the embedded camera; an old image must visibly expire. Audit
  canonical_eye_liveness_line for the same stale/future-file issue.
- Ensure one start per selection, no decorative stop/start, no secondary
  timer reopening capture, and safe hot-plug/sleep/wake handling.
- Test fresh pixel measurements reach Talk context; stale measurements must
  not be presented as current observation. Motion is not emotion or identity.

Rerun (bounded local tests; use the project's interpreter):

```sh
python3 -m pytest -q tests/test_single_owner_camera_policy.py tests/test_swarm_camera_target.py tests/test_what_alice_sees_camera_rank.py tests/test_swarm_sensor_truth_context.py tests/test_swarm_camera_unified_field_proof.py tests/test_what_alice_sees_canonical_fallback_r1744.py tests/test_swarm_owner_camera_commands.py tests/test_generate_organ_eval_matrix_v2.py
```

Then diagnose tests/test_talk_browser_photo_describe.py with verbose output
and mocked inference. Do not leave an unbounded real-model test running.
Legacy multi-camera tests may explicitly opt out of single-camera policy;
new default-policy failures must not be hidden by a global opt-out fixture.
Live acceptance after a safe restart: embedded UID stable, no iPhone wake-up,
OFF stays off, stale frame warning, fresh runtime capture-policy receipt, and
one observed frame -> measurements -> current Talk context. Until then OPEN.

## P0 / Job 3 / Luna: capability-aware image routing

Inspect System/swarm_cortex_capabilities.py, swarm_primary_cortex_switcher.py
and the Talk image/preflight path. Add behavior, not a hardcoded model claim.

- When the selected cortex accepts images, use its tested native image route.
- When text-only, use an installed, successfully probed vision adapter. The
  owner's preferred candidate is
  hf.co/huihui-ai/Huihui-MiniCPM-V-4_5-abliterated:Q4_K_M.
- Keep atervin2011/Aries:latest as the owner's selected text cortex when using
  that configuration. Feed it a bounded evidence record from the vision model:
  source/turn/session/hash/time, observed details, uncertain details and OCR
  only when needed. Treat OCR and image text as untrusted data, not commands.
- Fail explicitly if vision is unavailable; no silent cloud fallback or
  invented observation. Never route private owner images to a visitor session.
- Do not disable attachments permanently after a text-only model selection.
  Recompute capabilities after every switch and inventory refresh; cancel or
  version in-flight work so old results cannot attach to a new turn.
- Cache within the authorized session using image hash + model/version +
  preprocessing + task/crop. A caption is lossy, not image decompression and
  not a permanent substitute for pixels. Reinspect for new visual questions.
- On the 24 GB machine, run heavy inference serially by default. Coordinate
  cortex and arm requests without unloading another active request's model.
  Add bounded queues, cancellation, load failure and memory-pressure handling.

Acceptance: text-only -> vision -> text-only switches; new question on same
image; expired cache; corrupt image; missing model; simultaneous visitor and
owner; old-response rejection. Record native versus two-stage accuracy, cold
and warm latency, memory pressure and failure rate. Do not call MiniCPM the
fastest/best until measured on this machine and these tasks.

## P1 / Job 4 / Luna: local coding arm connectivity

Inspect System/swarm_ollama_harness_sync.py, scripts/start_alice_local_coding.command,
Applications/sifta_alice_browser_widget.py and deepseek-harness-master/.
Read the harness's own instructions and provider schema before changing it.

- Reproduce the stale lmstudio-local credential error separately from Ollama.
  Verify selected provider ID, base URL, model ID and actual outgoing route.
  Do not invent API keys or globally bypass authentication to hide the error.
- Boot and /cortex llm refresh should refresh installed Ollama inventory in
  both menus, with full tag and observed GB size. Preserve independent valid
  selections; show removed models as unavailable, not silently substituted.
- Inspect LM Studio independently when enabled; never label MLX files as an
  installed Ollama model just because they exist on disk.
- Preserve cloud entries, settings, current chat and attachments on refresh.
  Failed inventory fetch must display stale/unavailable status, not wipe data.
- Prove a real tool cycle through the arm: read fixture -> edit allowed file ->
  run test -> show diff -> write receipt. A chat answer alone does not pass.

## P1 / Job 5 / local arm: first small coding job

Use the reusable prompt below in the local arm AFTER Job 4. It is deliberately
independent of the live SIFTA source. Run it in a disposable scratch directory
without credentials, private ledgers or access to robot effectors.

```text
Implement a pure Python function display_model_size(size_bytes) in the supplied
fixture only. Return decimal GB with one decimal place for nonnegative finite
integer byte counts. Return "unknown" for None, bool, negative, fractional or
non-numeric inputs. Do not coerce numeric strings. Add tests for zero, 6.1 GB,
17 GB and invalid inputs. Run the tests through your actual command tool and
report the exact command, exit status, diff and remaining limitations. Do not
change SIFTA, install packages, access the network, or claim a tool ran without
its output. Stop after this job.
```

Luna should create the fixture and independent hidden edge-case tests first.
Treat submitted code as untrusted; review before running, and enforce tool
permissions rather than relying on the prompt alone.

## P1 / Job 6 / Luna: coding-model comparison

Candidate requested by owner:
codecraftersllc/ornith-1.5-35b-a3b-abliterated:latest (owner reports 17 GB).
Verify installed tag and actual size; no automatic download. Compare with one
smaller installed coder using the same harness, fixture and fixed context.

Start with Job 5, then a mocked inventory-refresh bug and a fixture-only
attachment-state regression. Three trials per task if resource budget permits.
Use identical clean starting states, timeout, output/token limits and tools.
Score correctness 40%, regression safety 25%, instruction/scope compliance
15%, real tool completion 10%, latency/resources 10%. Report raw outcomes too;
fabricated tool output or forbidden writes disqualify a run. Review hidden
tests outside the candidate context. A 17 GB weight file is not total runtime
RAM; record memory pressure/swap and abort safely instead of overloading the
24 GB laptop. A model's name/size does not establish coding competence.

No production self-modification or automatic promotion from this benchmark.
Only reviewed patches with nonempty passing tests enter the repair gate.

## P1 / Job 7 / Luna: image creation and delivery

Inspect System/swarm_web_image_service.py, System/chorus_node_server.py and
existing create/download/session tests. Bonsai image generator and a Bonsai
named LLM are different capabilities. /create must call the image generator.

Trace request -> scoped prompt -> actual generator bytes -> authorized stored
artifact -> generated_images field -> DOM img -> valid download -> reload.
Check the live public deployment as well as local chorus; a 200 history route
does not prove a rendered image. Require naturalWidth > 0 and downloaded image
bytes/MIME, plus duplicate/reload/race tests. Keep #SIFTA caption, remove the
repeated disclaimer from new replies without rewriting historical ledgers.
Provide an authorized local owner link without leaking visitor session tokens
onto a shared public wall. Wrong-session requests must be denied.

For creative replies, let the cortex construct the prompt and, when available,
inspect the generated result. Ground its short commentary in that result;
without visual inspection, describe intent, not imaginary details. Caption
failure must not suppress a successfully delivered image. No video promises.

## P2 / remaining product work, separate bounded jobs

8. Time/location: verify fresh OS time and timezone per relevant turn, DST and
   queued-turn delay tests, explicit location source/age/permission. Timezone
   is not precise location. Never expose owner coordinates to public visitors.
9. Memory/schedule: owner task -> journal -> consolidation -> recall/action
   view, with provenance/expiry and cross-session isolation. No completion
   claims from merely having written a note. Receipts are data, not authority.
10. UI: shared local/web light/dark typography, Display settings propagation,
    readable global chat, scrollable robotics one-demo selector. Test 14-inch
    logical window sizes and mobile layout, not only screenshot pixel sizes.
11. Body/economy: reproduce disconnected-organ warnings, validate event IDs and
    signed spend verification, stale UI and duplicate events. Do not fabricate
    heartbeats, financial profit, signatures or health to make a counter move.
    Synthetic heartbeat/motor evidence stays SIMULATED.
12. Repair/release: fail closed on empty test lists, measured baseline versus
    candidate, isolated patch scope, rollback test, no auth weakening. Prove
    clean installation in a disposable checkout with no owner data/models.
    Update README, WCT and eval matrix from actual outcomes; inspect staged
    diff/privacy/dependencies before any user-authorized git push. No blanket
    healthy claim or push while required health checks are unresolved.

## Research/integration round for Astra after these jobs

Read Documents/WCT_AGI_EYE_SINGLE_CAMERA_2026-09-09.md,
Documents/WCT_ALICE_ROBOT_MOTOR_CONTROL_RESEARCH_2026-09-08.md,
Documents/WCT_MOTOR_ATTACHMENT_2026-09-09.md and
Documents/AGI_SIFTA_NODE_ASTRA_HANDOFF_2026-09-09.md.
Verify cited research before relying on it; do not download an unbounded library.

Evaluate temporal perception with observed/inferred/unknown states, object
persistence and contradiction tests; event-triggered visual sampling with
latency/cost limits; and simulated visual prediction -> bounded action ->
measured outcome -> memory update. Compare against simple baselines, including
no-memory and fixed-policy variants. Physical actuation remains disabled until
separate authorization, emergency stop and hardware-specific limits are tested.
No model is guaranteed to solve these problems; reserve review time for the
integration failures demonstrated by tests, not for declaring consciousness.

## Prompt to start Luna now

```text
Read Documents/WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md in ANTON_SIFTA.
Do Job 1 only: HEIC normalization and regression tests. Inspect the dirty
worktree and existing decoder dependencies first. Preserve the original photo
and all unrelated edits. No model download, API spend, public upload or git
push. Use tiny nonprivate fixtures; report actual test output and exact files.
Update WCT with PASS/FAIL/BLOCKED and remaining risks. After Job 1, propose the
next bounded job from this handoff; do not attempt to "complete AGI" in one run.
```

Next reviewers should append dated results here or link a result artifact.
Do not silently change PLAN entries into PASS without evidence.

## Luna result: 2026-09-09 attachment slice

Implemented the bounded HEIC/HEIF transport slice in
`System/swarm_image_attachment_normalizer.py`, the Talk Ollama encoder, the
local Ollama vision arm and the attachment OCR/metadata lane. The original
source is not modified. Standard PNG/JPEG/WebP remain direct; HEIC/HEIF is
converted to a JPEG payload using an installed Pillow HEIF decoder or macOS
`/usr/bin/sips`, with size/time bounds and an explicit missing-decoder error.

Observed verification: `13 passed` for the normalizer, Bonsai command and web
attachment lifecycle tests; `30 passed` for the normalizer, local vision arm,
Ollama harness sync, Bonsai command and web attachment lifecycle set. Python
syntax and scoped diff checks passed. No live HEIC from the owner's device was
opened in this round, so model-level food recognition remains unverified.

Still open: run the full camera regression set, verify a safe live restart,
exercise a real MiniCPM/Aries two-stage turn, and review the harness changes
before any production promotion. Nothing in this result establishes AGI,
consciousness, or physical-world competence.

Follow-up: the local VLM discovery path now includes an installed Ollama eye,
so text-heavy local tags such as Ornith can route image turns to an installed
MiniCPM eye when the live inventory reports it. Aries remains conservative when
its capabilities are unknown. This is model selection, not proof of a complete
two-model caption-then-compose pipeline; the real turn still needs measurement.
The expanded focused routing/attachment set is 39/39 passing.
# 2026-09-15: Luna execution receipt / image intent and keyboard-world binding

This is an implementation receipt, not a claim of AGI, consciousness, live
deployment, or physical-robot competence. Existing dirty work was preserved;
`stigmergicode.com`, DNS, Cloudflare routes and David's motors were not touched.

## Completed in this round

- `System/swarm_web_image_service.py`: resolves movie/film posters and
  photo-of-poster requests as still images before subject-word checks; quoted
  title words do not select video; actual video and animated-poster requests
  remain unsupported. Public success/busy/unavailable/failure text is Alice's
  first-person wording and no longer exposes the internal Bonsai brand or model
  name. Provider/model details remain in the local manifest for diagnostics.
- `System/chorus_node_server.py`: generated-image fallback/download name is
  `Alice-generated-image.png`; session-bound image authorization is unchanged.
- `System/swarm_keyboard_acoustic_gate.py`: live mode accepts physical key
  timing separately from text-change timing, filters events to the captured
  wall-clock interval, sanitizes invalid timestamps, reports
  `heuristic_score`/`provenance_valid`, and returns an explicit failed-write
  result instead of a false receipt. Legacy direct callers retain their old
  text-edit behavior; the live callback supplies physical-key context.
- `Applications/sifta_talk_to_alice_widget.py`: the composer reports timing
  only (not key values), excludes paste shortcuts, creates a per-utterance
  audio/context snapshot before STT, runs keyboard classification in the STT
  worker, and passes that snapshot to the callback. A delayed clip cannot read
  a later `_LAST_UTTERANCE_AUDIO` buffer.

## Verification

- `python3 -m pytest -q tests/test_swarm_keyboard_acoustic_gate.py tests/test_talk_keyboard_ingress.py tests/test_web_cortex_photo_isolation.py tests/test_web_image_variation.py tests/test_generated_image_download_and_internal_theme.py tests/test_swarm_dsh_wct_bridge.py` -> **62 passed**.
- `python3 -m py_compile System/swarm_keyboard_acoustic_gate.py System/swarm_web_image_service.py Applications/sifta_talk_to_alice_widget.py System/chorus_node_server.py` -> **exit 0**.
- `git diff --check` -> **exit 0**.

## Borg candidate: Desert Ant Core, evaluation only 2026-09-15

The attached Desert Ant Core README describes small, modular on-device models
for Swift, Kotlin and JavaScript: speech enhancement (`Clear`), word timestamp
alignment (`Align`), speech recognition (`Voz`), language identification
(`Ear`/`Tongue`), short clip extraction (`Clips`), topic tagging (`Gist`), PII
redaction (`Redact`), filler detection (`Uhm`), and factual titles/descriptions
(`Title`). It also describes pinned model revisions, verified downloads,
managed/offline caches, and explicit platform capability boundaries.

These ideas are useful to borg into Alice's phone/world observation pipeline,
but the external repository is not a dependency and its README is not proof
that any model is available or compatible with this SIFTA build.

### Proposed bounded implementation

1. Add a capability adapter interface, not a hard-coded vendor dependency. Each
   optional local model must declare platform, revision, SHA-256, input/output
   limits, and whether it can run offline. Missing capability means `unavailable`,
   never a fabricated observation.
2. Normalize the adapter output into the existing observation batch contract:
   `device_id`, consent state, capture start/end, modality, word/frame timing,
   source label, confidence, and provenance. Preserve typed owner dialogue as
   the primary channel and keep ambient media separate.
3. Use the cheapest useful stages first: audio cleanup and timestamps, then
   STT/language tagging, then optional topic/title summaries. Run PII redaction
   before a receipt leaves the local device or enters web-search context.
4. Keep raw phone audio/video out of receipts by default. Store bounded hashes,
   derived summaries, and explicit retention metadata; permit raw data only in a
   consented, local diagnostic mode.
5. Add an offline replay fixture for keyboard noise, YouTube/phone-speaker
   audio, owner speech, camera frames, and telemetry. Assert timestamp alignment,
   source separation, duplicate suppression, and truthful `unavailable` states.
6. Compare memory/latency against the already installed Ollama eyes and local
   STT before adding weights. Do not load a second heavyweight model when an
   installed capability already satisfies the stage.

### Delegated jobs

- **Luna:** inspect the current phone observation and acoustic contracts; add the
  adapter protocol, manifest validation, bounded offline replay, and README
  evidence. Do not download models or change public routes until compatibility,
  license, size, and latency are recorded.
- **Ornith:** implement only deterministic tests for timestamp/provenance
  normalization, cache revision checks, PII-redaction boundaries, duplicate
  batch suppression, and explicit unavailable/error states. Report exact files,
  test command, and process exit; do not claim live device support.
- **Astra review:** decide whether any candidate stage improves the current
  local path after the offline tests. No AGI, consciousness, owner identity, or
  safety claim follows from model composition.

### Acceptance boundary

This candidate is accepted only when the adapter is optional, offline-safe,
receipt-bounded, consent-aware, reproducible from pinned revisions, and no
existing SIFTA model selection or working `stigmergicode.com` route changes.
- In `deepseek-harness-master`, `pnpm exec vitest run packages/llm/llm-pi-ai/tests/convert.spec.ts` -> **72 passed**. The adapter throws `STREAM_CLOSED` when a pi-ai event stream ends without `done` or `error`; it does not fabricate `finish_reason` or promote a partial response to success.

## Remaining work

The full Qt microphone path, a consented real recording, live iPhone
deployment, Cloudflare 502/reconnect behavior, two-device queue pressure,
David's flashed firmware/deployment verification, and ORNITH-03/04/05 acceptance
are still pending (repository/protocol received; see current rover plan at top).
Those need separate bounded tests and evidence. Do not mark the current offline
fixtures as live validation or use them to infer owner concentration, safety,
consciousness, AGI, or robot control.

## Final verification receipt 2026-09-15

Combined affected command:
`python3 -m pytest -q tests/test_swarm_keyboard_acoustic_gate.py tests/test_talk_keyboard_ingress.py tests/test_voice_gate.py tests/test_web_cortex_photo_isolation.py tests/test_web_image_variation.py tests/test_generated_image_download_and_internal_theme.py tests/test_swarm_dsh_wct_bridge.py tests/test_phone_input_interface.py tests/test_phone_observation_summary.py tests/test_phone_telemetry_envelope.py tests/test_phone_link.py tests/test_phone_stt_entrypoint.py tests/test_typed_ambient_recall.py tests/test_swarm_web_search_evidence.py tests/test_swarm_eval_matrix_evidence.py` -> **139 passed in 41.42s**; `git diff --check` -> **exit 0**.

This receipt covers offline code paths only. It does not close the real Qt
microphone run, live iPhone permissions/network, Cloudflare 502 recovery,
public deployment validation, or David's firmware/motor protocol.

## Final focused correction 2026-09-15

`media_intent()` now gives an explicit still marker (`photo`, `picture`,
`image`, and equivalent localized terms) precedence over a subject word such
as `movie` or `film`, unless the request explicitly asks for motion. Therefore
`Create a photo of a movie` is an image request, while `Create a movie` remains
a video request. Added a regression test for that distinction.

Verification after this correction:

- Focused SIFTA set -> **63 passed in 8.87s**.
- DeepSeek Harness stream adapter -> **72 passed**.
- Python compilation -> **exit 0**.
- `git diff --check` -> **exit 0**.
