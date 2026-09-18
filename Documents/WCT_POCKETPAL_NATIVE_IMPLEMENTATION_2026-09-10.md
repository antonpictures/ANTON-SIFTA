# PocketPal as Alice's phone interface: implementation handoff

LATEST ORDER: Documents/WCT_PHONE_WORLD_INPUT_2026-09-10.md supersedes this file's
priority and old tunnel status. Web L0-L3 first, then native PocketPal/ARKit L4.
Owner corrected DNS and the `alice-m5` published route is now active; public
coin returns the coin HTML with HTTP 200. Local coin-host origin also serves
HTML. Verify the actual iPhone render and permissions before rewriting UI.

## Recovery checkpoint: web interface first (owner priority update)

`stigmergicoin.com` is now the PRIMARY input interface; PocketPal is SECONDARY.
Do not alter `stigmergicode.com` DNS, tunnel routing or existing homepage to build this.

- Implemented: isolated coin-host page in `System/sifta_robot_input.html`, served by
  the existing Chorus listener. Camera preview/manual JPEG capture, editable typing,
  browser dictation where supported, bounded fetches and foreground sensor cleanup.
  Sends through the existing canonical web chat/attachment lane, not a rival brain.
- Implemented: web night worker resolves cortex between turns instead of pinning its
  startup choice forever. Owner-approved Krishna restored with receipt
  `56f89d89-4a64-49a2-a224-ef28c50a3459`. SmolVLM is a specialist, not the chosen cortex.
- Verified: 8 regression tests; JS syntax; live origin preserves the code homepage
  and serves the coin page for its exact Host. Public code root returns HTTP 200.
- RESOLVED AT HTTP LAYER: the `alice-m5` route serves `stigmergicoin.com` with
  HTTP 200. A prior run accidentally targeted `stigmergicoin.com.imperialdaily.com`
  via the CLI's wrong zone context; do not repeat route-dns commands under that
  context. The remaining check is the real iPhone render and sensor permissions.
- NOT DONE: native PocketPal fork, raw microphone upload/local STT, authenticated
  owner pairing, independent durable sensor queues, GPS, real iPhone acceptance,
  automatic observations, and robot hardware control. Browser dictation may use an
  external speech service and is explicitly labelled; it is not local STT proof.

Next code slice: add a separate paired-device API with bounded audio decode/STT,
explicit consent, revocation and source IDs. Keep the public chat zero-authority.
Then attach camera observations and speech transcripts to the same owner's typed
conversation without replacing its last question. Run the simultaneous-input test
below on an actual iPhone. No movement authorization based on scene captions.

Planning/research only. This is a procedural extension of the existing SIFTA plan,
not a replacement for its canonical covenant. Owner request: chat with Alice while
the iPhone supplies camera descriptions, audio and sensor evidence to her shared field.
Mac owns authoritative conversation/memory; phone owns capture and optional local vision/TTS.
David Condovici supplies hardware details and integrates the ESP32 platform.

## Source evidence and scope

### Owner clarification: minimal PocketPal reuse, three concurrent inputs

Reuse https://github.com/a-ghorbani/pocketpal-ai at the inspected pin below.
The requested integration is a narrow source fork/adapter, not wholesale copying into
SIFTA. Preserve MIT notices, existing model loading, camera components and speech playback.
Add only the Alice screen, transport/session adapter, observation scheduler and missing
recording/transcription integration. Do not rebuild the Pal marketplace or unrelated tools.

The same visible robot terminal MUST accept these independent inputs concurrently:
- Camera -> bounded local or Mac vision job -> timestamped observation text.
- Microphone -> bounded push-to-talk recording -> STT -> timestamped transcript.
- Keyboard -> immediate typed owner message with its own turn ID.

Concurrent means inputs and UI remain responsive; it does not require simultaneous
heavy model inference on the phone. Keep one camera stream and one recording owner.
Use separate queues for sensor observations and owner turns: coalesce old camera frames,
never silently drop owner speech or typed text. Cap queues and visibly reject overflow.
Typing remains enabled during recording/vision; stop/cancel affects only its own operation.
Order owner turns by server acceptance and show pending transcript state; link delayed STT
to its recording ID rather than inserting it into an unrelated typed turn. Snapshot relevant
observations when processing each owner turn, and attach source IDs to Alice's reply.

Native audio plan: reuse recording/STT only if actually present; TTS is not STT. Otherwise
add a small recorder and send bounded audio to the existing Mac STT path. Handle iOS audio
session interruptions and suppress Alice's own playback from owner transcripts. Continuous
listening is a later explicit mode; the first release supports push-to-talk alongside video
and typing. Keep transcript/observation text as untrusted data, not executable commands.

Acceptance: on the same Alice screen, start observing, record a spoken question and type
a different question before recording ends. Both owner inputs must receive distinct ordered
receipts/replies, camera observations must continue or report a bounded pause, and no text
may be lost or attributed to the wrong source. Repeat with delayed STT, slow vision, cancel,
network loss and reconnect. Simulator tests can prove ordering; actual iPhone testing must
prove camera/mic coexistence. Source fork installation still requires a signed iOS build;
editing a Pal prompt cannot add this integration to the already-installed app.

### Next Luna round: SmolVLM eye adapter and incomplete bridge fixes

Owner is downloading `hf.co/ggml-org/SmolVLM-500M-Instruct-GGUF:Q8_0`.
Download completion and Ollama image support are UNVERIFIED. PocketPal running its
SmolVLM build is not proof this Ollama package includes a working vision projector.
Add this exact identifier as a configurable eye-model candidate, separate from Alice's
selected conversational cortex. Do not change the cortex or replace MiniCPM automatically.

Implement in this order:

1. Repair the existing caption endpoint before calling it complete. Source review found
   `fresh_until = receipt_time + 5` ignores capture age, so even an old caption becomes
   fresh. Validate finite timestamps (reject NaN/infinity and booleans), sequence and
   confidence types; account for measured clock offset/uncertainty and capture age.
   Unknown clock alignment must not count as fresh movement evidence. Compare all
   immutable envelope fields on duplicate IDs, not only description. Require source
   frame hash, schema/model/prompt identity and server-bound device identity. Preserve
   replay protection after the 64-row display window rotates. Persist observations
   privately with source references and recovery semantics; currently only in-memory
   captions and metadata audit exist. Ensure durable write errors cannot produce a
   successful retry response for data that was never committed.
2. Fix chat assembly: currently the observation becomes the final user message after
   list reversal, and the system prompt still describes a surface with no camera.
   Keep owner question last, distinguish caption evidence from actual image access,
   include observation IDs on the reply receipt, and snapshot evidence at submission.
   Add failure tests for old captures, conflicting metadata, evicted replay, restart,
   cross-session access, prompt ordering and observations arriving mid-turn.
3. After the owner's download completes, query local inventory and `/api/show` for the
   exact tag. Verify a real image request with a tiny synthetic scene and a bounded
   timeout/token limit. Test contrasting images; a text-only reply is not proof of
   seeing an image. Missing projector/unsupported architecture produces a clear
   unavailable status. Keep the existing vision fallback; do not invent conversion
   commands or silently redownload weights. Record model digest and runtime version.
4. Wire successful SmolVLM through the existing attachment/eye vision adapter, using
   normalized captured frames, source timestamp/hash and device ID. Both Mac camera
   and phone frames may use it, but keep capture ownership and identities distinct.
   One bounded vision job at a time, latest frame wins, no inference backlog. Captions
   feed the existing scoped unified-field/recall path and selected cortex; model loading
   alone does not connect a model to the eye. Show active eye model and failure reason.
5. Compare SmolVLM and the existing MiniCPM candidate on the same small private or
   synthetic image set: objects, changed scene, text, low light and ambiguity. Record
   correctness, warm/cold latency, memory and failures. Choose preferred low-cost
   captioning from measurements; retain stronger-model reinspection for details the
   caption omits. Do not use caption quality as obstacle-clearance proof.
6. Continue native jobs below: PocketPal fork, simultaneous chat/video, authenticated
   transport, audio/location, real iPhone validation and ESP32 simulator. The previous
   12 passing phone tests cover a small LAN prototype, not this whole handoff. Existing
   PhoneLink rejects public proxy headers and has no native bearer-token authentication;
   do not route Cloudflare to it or call it public/native-ready without implementing
   the intended transport. Reuse its logic behind the authenticated gateway as appropriate.

Completion report must mark each item implemented/tested/live-verified/pending, update
WCT and README, and list remaining native/signing/hardware gaps. This round is planned;
no model inference or application changes were made by this amendment.

Inspected PocketPal tree commit `ced4fadf0805a0d2e615558e003b41d07006d5c3`;
package.json reports version 1.17.2. Installed version still needs recording.
Use this pin for initial work; inspect drift before selecting another version.

- `src/screens/ChatScreen/VideoPalScreen.tsx`: camera-active branch replaces ChatView
  with EmbeddedVideoView. Inactive branch supplies `messages={[]}` and a no-op
  `onSendPress`. The editable input is an image-analysis prompt. This explains why
  the observed screen does not provide ongoing normal conversation during capture.
- Same file: `handleImageCapture` calls `modelStore.startImageCompletion`, accumulates
  tokens in screen state, and has an empty `onComplete`. This is the completed-caption
  integration point; use a per-operation buffer, not stale React state.
- `src/components/EmbeddedVideoView/EmbeddedVideoView.tsx`: uses VisionCamera
  `takePhoto`, reads JPEG as base64, removes temporary file and calls `onCapture`.
  Its callback type returns void and is not awaited. Its capture flag guards photo
  capture rather than the entire inference operation. Verify downstream model guards
  before claiming actual overlapping completions; enforce backpressure explicitly.
- `src/services/agent/AgentRunner.ts`, `src/store/TTSStore.ts` exist in the tree;
  their internal APIs have NOT been reviewed in this pass. Read before reuse.
- Package declares llama.rn, VisionCamera, Keychain, ONNX runtime and native speech.
  Dependency presence does not demonstrate transcription or sensor integration.
- Screenshots show iPhone 15, iOS 26.6.1, Lookie video Pal, SmolVLM-500M Q8_0,
  configurable capture interval, voice choices and optional tool toggles. Benchmark
  screenshot has blank throughput fields and 48ms total: not a valid vision speed result.
  Treat the displayed 5.6 GB as an app report, not currently free memory.

## Delivery choice

Create a small local PocketPal source fork with a distinct app identity (SIFTA companion),
preserving upstream notices and leaving the installed original/data intact. A Pal prompt
alone cannot add networking or change native camera/chat layout. No undocumented scraping.
Use the same existing Mac gateway under stigmergicoin.com for web and native clients;
do not expose Ollama or unrestricted coding tools to a paired phone.

Before dependencies: inspect available checkout, disk space, Xcode toolchain and signing
setup. Use a separate checkout with a pinned upstream commit, not wholesale source copied
into SIFTA. Review postinstall scripts before running them. Keep upstream lockfile/runtime
versions. Record patch commits and upstream pin in SIFTA docs. Simulator compilation and
device installation are separate gates. Missing Apple signing/team/device pairing blocks
installation only; complete source, offline tests and simulator work first. Never invent
developer credentials or overwrite the original PocketPal app.

## Luna jobs in dependency order

1. Define shared versioned contracts/tests using existing SIFTA sample and journal modules.
   Reuse original plan's pairing limits and validation. Native QR scan exchanges a short-lived
   single-use nonce for a scoped revocable device token stored in iOS Keychain. Browser keeps
   its HttpOnly cookie flow. Both bind owner/node/device/session server-side. Native credential
   validation cannot rely on browser Origin. Token never goes in URL/query/logs. Add TLS-only
   endpoint configuration, logout/revocation, and cross-device access tests.
2. Add a transport adapter (proposed `src/services/sifta/SiftaClient.ts`) and session store.
   Reuse gateway sample/chat endpoints rather than duplicate /api/phone and /api/samples
   implementations. Define one authenticated event stream with server cursor, reconnect and
   bounded retry. Native WebSocket auth must use a supported secure handshake or first-message
   authentication; verify library support. Emit no events before authentication. Bound replay
   and deduplicate chat/sample IDs. Offline status is explicit; reconnect never replays motion.
3. Add an Alice screen with camera preview, conversation list, text composer, push-to-talk,
   Grab, Start observing/Pause, speaker control and connection status mounted together.
   Keep existing Video Pal behavior for other Pals. Reuse camera/speech components; one owner
   per device resource. Remote chat goes to Mac independently of local phone vision completion.
   Camera preview must remain mounted while sending/receiving messages and opening keyboard.
4. Extract a testable observation controller from the capture flow. One capture/vision job in
   flight; await completion before next capture. Start manual; optional observing defaults to
   at least 2 seconds AFTER each completed analysis, configurable after measurement. Queue
   capacity one, latest frame wins; never retain a growing video backlog. Cap caption to 96
   tokens initially. Use operation generation IDs and refs for cancellation and late-token
   rejection. Release resources on pause, screen change, app background, interruption or error.
   Send exactly one completed observation per frame; partial text stays UI-only. Delete temp
   media in finally paths. Include vision projector identity/hash where required by the model.
5. Support two explicit observer modes: local SmolVLM caption to Mac; or bounded JPEG sent
   to Mac's vision adapter. Keep phone local vision and Mac dialogue separated so text-only
   cortex can use observations. Report mode/model/time visibly. Missing local model/projector
   does not trigger large automatic downloads. Add fresh-frame request for questions a cached
   caption cannot answer. Never promote arbitrary scene text into instructions/tools.
6. Audio: inspect existing speech library for recording/STT; do not infer STT from TTS. Start
   push-to-talk, normalize audio through SIFTA's existing path. Coordinate AVAudioSession with
   playback, mic and camera; handle calls/headphones/interruption and resume explicitly. Reuse
   installed speech support IN THE FORK only when its assets exist there: original app sandbox
   assets are not automatically shared. Use system speech first, optional Supertonic after
   version/weight/voice license checks. Pause recording or mark playback intervals to avoid echo.
7. Add native CoreLocation snapshots and optional CoreMotion samples through existing or small
   typed native bridges. Permission usage descriptions must explain actual collection. Record
   availability, authorization, accuracy, timestamps and coordinate frames/units. Collect short
   windows only; location denial leaves chat/video working. Battery/thermal state and connectivity
   are optional telemetry. Do not assume LiDAR/depth, background camera, Wi-Fi ranging or GPS
   precision. Disable/suspend capture under OS interruption and show stale on the Mac.
8. Mac field assembler: keep chat events and perception events separate, linked by device/session.
   Each reply snapshots the newest relevant observations and cites their IDs internally. New
   evidence during a reply queues for the next turn or an explicitly requested follow-up; do not
   mutate a running prompt. Keep limited recent observations plus durable significant changes,
   not every caption forever. Derivations retain source lineage; self-reported confidence is
   not a calibrated probability. Unknown confidence is null. Device clock offset/uncertainty
   and elapsed capture-to-arrival must accompany server receive time; receiving old evidence
   now does not make it fresh. Five seconds is a display experiment default, not a safe driving
   latency. Image hashes are required for local-caption provenance too, even if image not uploaded.
9. Human movement experiment then ESP32 simulator: Alice proposes `observe`, `ask_owner`,
   `say`, `propose_motion` or `stop` with referenced evidence. Treat suggestions as intentions;
   deterministic controller validates state and telemetry before any future actuator command.
   Captions are insufficient to prove free space, distance or balance. Freshness alone does not
   authorize motion. David must provide board/driver, pin map, encoders/IMU/range sensors,
   physical stop and measured braking/latency limits. Keep actual firmware timing in MCU
   monotonic time, bounded command duration, stop on connection loss, explicit rearm.
10. Test and record: pairing replay/revocation/cross-device denial, concurrent chat+observing,
    slow caption and 100-frame synthetic burst (no backlog), stale tokens after stop, corrupted
    media, wrong projector, GPS denial, clock drift, TTS/mic interruption, airplane mode,
    reconnect ordering, Mac restart and exactly-once durable event semantics. Test the actual
    iPhone for foreground/background/lock and ten minutes of conversation with observations.
    Capture p50/p95 caption and reply latency, peak queue size, failures and thermal behavior;
    baseline chat-only vs chat+vision, identical inputs/model settings. No fake throughput from
    the screenshot. Any unrun physical-device gate stays pending.

## Research backlog beyond the first working interface

- Camera calibration and visual-inertial odometry: evaluate ARKit device support/world tracking
  as a later native experiment. Tracking can reset/drift; it is not absolute location. Coordinate
  camera ownership before adding an AR session; do not start a second competing camera pipeline.
- Build a small consented scene/question set: object presence, changed scene, occlusion, reading,
  uncertain depth and stale input. Compare phone caption-only against Mac image reasoning.
  Measure answer accuracy and failures, not just tokens/sec. Keep original frames private.
- Stigmergic memory: test retention/retrieval of sourced observations, corrections and changes
  across restart. Ensure summaries cannot erase contradictory raw evidence or cross users.
- Learning/control: establish repeatable simulation tasks and held-out evaluation before any
  learned motion policy. Reuse robotics libraries only after David specifies the platform.
  No library, Pal prompt or successful demo establishes general intelligence by itself.

## Sources and open checks

- Pinned video screen: https://github.com/a-ghorbani/pocketpal-ai/blob/ced4fadf0805a0d2e615558e003b41d07006d5c3/src/screens/ChatScreen/VideoPalScreen.tsx
- Pinned capture: https://github.com/a-ghorbani/pocketpal-ai/blob/ced4fadf0805a0d2e615558e003b41d07006d5c3/src/components/EmbeddedVideoView/EmbeddedVideoView.tsx
- Dependencies/build scripts: https://github.com/a-ghorbani/pocketpal-ai/blob/ced4fadf0805a0d2e615558e003b41d07006d5c3/package.json
- PocketPal license: https://github.com/a-ghorbani/pocketpal-ai/blob/ced4fadf0805a0d2e615558e003b41d07006d5c3/LICENSE
- Core Motion: https://developer.apple.com/documentation/coremotion
- Core Location: https://developer.apple.com/documentation/corelocation
- ARKit follow-up: https://developer.apple.com/documentation/arkit

Apple reference pages require further platform-specific reading during implementation; this
pass did not verify every iOS API/entitlement. PocketPal AgentRunner/TTS internals and exact
installed-app version remain checks, not assumed capabilities. Earlier Supertonic research
is in the parent plan; verify the selected asset license at implementation time.

## Next prompt

Luna: implement this handoff jobs 1-10 in order, reuse the parent plan's compatible contracts,
keep ESP32 simulated, and update WCT/README/book with patch commits, tested behavior and open
questions. Do source and tests before asking for missing device-signing details. Preserve
unrelated changes. Report completed software separately from iPhone and hardware validation.
Budget attention by tackling one failing acceptance test at a time; do not recursively launch
models or rerun broad inference benchmarks. The immediate milestone is one usable PocketPal
Alice screen where chat, camera observation and speech cooperate with the Mac's shared field.
