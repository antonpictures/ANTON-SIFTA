# SIFTA Robot Surface: Stigmergicoin + ESP32

## Current correction: David's repository received, 2026-09-15

Use the "Current rover plan: David's repository received" section at the top of
`Documents/WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md` for the next coding round.
It supersedes the older missing-firmware and native-app-first assumptions here:
the latest owner request uses stigmergicoin.com to connect Alice to David's car.
Source: private https://github.com/davidk-ro/E_Motion-Rover at
`5fdd0351fc20dc3697e913dee46aaeac5ebfb63b`. RVR1 UDP 4210 carries authenticated
velocity/telemetry through T-Camera; RSP2 connects Servo over UART. The existing
SIFTA HTTPS gateway needs a David-side LAN adapter. External UDP drive bypasses
AutoNavigator, so the plan explicitly requires local obstacle handling and a
finite watchdog before autonomous movement. Repository/protocol received;
flashed version, private provisioning and physical acceptance remain pending.

Status: PLAN ONLY. No hardware motion, public deployment, or AGI claim is authorized by this document.

Owner: Luna implements the bounded software work. Astra reviews architecture, unresolved embodiment questions, and any future learning/control claims.

## Astra implementation amendment: iPhone first (authoritative)

LATEST PRIORITY: the owner now requests PocketPal as the main installed interface.
Read `Documents/WCT_POCKETPAL_NATIVE_IMPLEMENTATION_2026-09-10.md` first. Its native
implementation sequence supersedes browser-first delivery and speculative bridge choices
below. Stigmergicoin remains the paired Mac gateway and browser fallback. Preserve the
sample, privacy, bounded inference and ESP32 contracts that do not conflict.

This section overrides conflicting defaults and open questions below. Implement in small,
tested increments; do not stop to request another model's approval for routine software work.
The target is an authenticated iPhone robot interface at `stigmergicoin.com`, paired by QR
with this Mac as inference and memory server. David Condovici owns the physical robotics
integration. Start with the owner moving the phone by hand. Hardware driving waits for
David's board, motor driver, sensors, wiring and measured stop limits; software simulation
does not wait for that information. A phone browser is a sensing surface of the same Alice.

### Decisions and corrections

- Reuse the working `stigmergicode.com` chat styles, light/dark settings, reply renderer and
  transport where compatible. The robot page is the primary experience on stigmergicoin;
  preserve the old marketplace at a separate route if needed. Inspect actual route ownership
  before changing it; do not assume editing a static HTML file changes the live Python origin.
- Cloudflare 1033 means no healthy connector for the addressed tunnel. Missing ingress is a
  separate routing defect. Check hostname DNS target, tunnel UUID/connector health, ingress,
  origin and TLS in that order. Missing ingress alone does not prove the cause of 1033.
- First release is HTTPS browser/PWA, Mac inference, iPhone camera/mic/location. Use same-origin
  authenticated server APIs. `localhost` on the phone means the phone, never this Mac.
- Request each supported sensor through a user gesture and the OS permission UI. Owner
  authorization does not bypass iOS prompts. Denied/unsupported sensors remain optional.
- Capture iPhone frames directly from its video stream, not screenshots of its screen.
  Default rear camera with `facingMode: environment`, allow front selection, use `playsinline`.
  One active stream per phone; tag the source device. Never replace phone location or camera
  data silently with the Mac's. Keep the Mac camera lease scoped to the Mac.
- Phone geolocation carries accuracy and timestamp; it is not guaranteed GPS. Motion/orientation
  is optional and feature-detected. Never integrate accelerometer readings into claimed metric
  position. Five-meter movement requires measured reference/encoders/calibration, not two captions.
- Describe network use accurately: phone media goes over HTTPS via Cloudflare to the Mac;
  inference is local to the Mac. This is not an offline or network-local-only connection.

### Reuse decision: PocketPal and Supertonic

PocketPal's repository documents MIT licensing, on-device GGUF inference, native acceleration,
TTS and tools. Reuse is possible. Do not assume the installed App Store build exposes an API
that a website can call, or that its downloaded models/voices are accessible to Safari.
Supertonic is a speech synthesis engine, not the camera/world model or the robot controller.
The inspected upstream repository provides browser and iOS examples, identifies sample code
as MIT and accompanying weights as OpenRAIL-M, and currently displays an archival notice.
Record the exact version/commit and each code/model/voice license before incorporating assets.

Release 1: phone performs image resize/encoding, audio capture and playback. Use available
system speech synthesis or existing Mac TTS first. Optional Supertonic browser inference is
a separate opt-in experiment with measured startup, memory and latency; do not download
hundreds of MB automatically. Pause capture during speech to avoid transcription feedback.

Release 2: time-box source inspection of PocketPal to identify an existing supported integration
endpoint. If none exists, document a small MIT-compliant companion/fork change that adds QR
pairing and the same SIFTA sample protocol. Do not fork the entire app during release 1.
Native local inference must retain source hashes, model/version and uncertainty when uploading
descriptions to the Mac. Keep raw-image fallback for questions the description cannot answer.
Any native fork needs an actual iOS build/signing/distribution path; installing PocketPal alone
does not install our modifications. Record iPhone model/iOS before claiming performance.

### Concrete Luna jobs and completion gates

1. Map and reuse the actual web handlers, sensor normalizer, inference queue and journal writer.
   Record current Git status and narrow file ownership. Fix the tunnel/origin chain with local
   and public health checks. Preserve working stigmergicode routing. Public health is minimal;
   sensor data and inference endpoints require authentication before public exposure.
2. Implement QR pairing from an authenticated owner surface on the Mac: random single-use
   nonce (at least 128 bits), two-minute expiry, atomic consume and revocation. QR points to
   `https://stigmergicoin.com/robot/pair#<nonce>`; exchange by POST, clear fragment immediately,
   never log it or include durable credentials. Store only nonce hashes server-side. Issue
   revocable device-scoped Secure/HttpOnly/SameSite cookies, validate Origin/CSRF, rate-limit
   pairing attempts, and keep phone scopes limited to its samples/results. No pairing secret
   in browser localStorage, public global chat, analytics, source control or service-worker cache.
3. Build Connect/Disconnect, camera preview, Grab sample, Cancel, result and speech controls.
   Grab captures one frame plus a bounded 3-second audio window when mic is enabled. Explain
   the capture window in the UI. Feature-detect MediaRecorder MIME support rather than forcing
   WebM; accept and normalize the actual iOS format server-side. Capture geolocation with a
   bounded timeout; persist partial results on denial. Stop tracks and pending requests on
   disconnect/page suspension; foreground requires explicit resume. Screen lock/background
   can suspend iOS pages, so no continuous availability promise. Cache static PWA assets only.
4. Use one schema: version, sample_id, parent_sample_id, paired_device_id, sequence,
   client_capture_start/end, server_received_at, modality timestamps, source hashes, MIME,
   dimensions, location accuracy/status, optional motion coordinate frame and quality flags.
   Server binds device identity to session; client fields cannot impersonate another device.
   Start limits: one 1280px-long-edge image <=2 MiB, audio <=5 seconds and <=2 MiB, entire request
   <=5 MiB, one pending sample per device. Validate decoded dimensions too. Configuration may
   tighten limits; tests must cover them. Retry same sample ID returns same receipt; reuse with
   different bytes is a conflict. Raw media uses private temporary storage with expiry/cleanup;
   durable journal holds compact evidence and provenance under existing access rules.
5. Route frame to an installed, capability-checked vision model and transcript through existing
   STT, then to Alice's selected cortex. Share the existing Mac inference scheduler: one heavy
   inference job at a time initially on 24 GB. Each stage has a deadline and cancellation;
   default sample budget 60 seconds, at most one transient retry within that budget. Timeout
   returns partial evidence; cancellation prevents late output replacing a newer sample.
   Summaries are derived caches, not substitutes for all future visual questions. Cache by
   image hash + model/version + prompt/task version; changing the task invalidates that cache.
6. Display Alice's concise interpretation with source sample links. Keep owner-requested
   movement, owner-reported movement and measured displacement separate. Use a short manual
   move in clear space first; never claim an obstacle-free path from a caption. Compare two
   samples with timestamps, missing data and uncertainty, append one idempotent journal event,
   and preserve visitor privacy when the owner sees aggregated state.
7. Specify and implement a simulator for the David/ESP32 boundary: protocol version, command
   ID/sequence, bounded duration, normalized wheel demand, acknowledgements and telemetry.
   MCU uses its own monotonic deadlines; browser timestamps cannot extend motor operation.
   Loss of heartbeat, stale command or E-stop stops motion; reconnect never replays commands
   or automatically rearms. Simulator defaults (e.g. 250ms heartbeat, 750ms stop timeout) are
   provisional, not certified hardware limits. Publish the contract for David to validate.
   Actual motor/encoder mapping and balance control require his hardware feedback. Use Mac
   to ESP32 LAN transport initially; do not make Safari Bluetooth support a prerequisite.
8. Run focused offline tests and one actual iPhone journey: scan QR, grant/deny sensors,
   grab, see interpretation, hear reply, move phone, grab again, reload, disconnect. Check
   expired/replayed pairing, cross-device access denial, double taps, MIME decoding, missing
   GPS, network loss, screen lock/resume, cancel/late reply, queue timeout, journal idempotency,
   simulator deadman and E-stop. Record real-browser observations separately from mock tests.
   If no physical iPhone test is available, mark that acceptance gate pending explicitly.

### Delivery discipline and direct prompt

Luna: implement jobs 1-8 in dependency order, with job 7 remaining simulated. Reuse existing
modules before adding another server or framework. Use small commits and bounded test runs;
do not launch nested agent loops or concurrent large models. Do not block all progress on
PocketPal integration or missing hardware. Update this plan, WCT To Code, README/book and
the existing receipt mechanism with changed files, commands/results and concrete remaining
gaps. Inspect dirty changes individually: unrelated changes do not prohibit committing and
pushing an authorized, reviewed subset. Never stage all files indiscriminately. Publish no
private media, pairing secrets or device location. Planning-only changes need document review,
not model inference. Report actual implementation separately from live iPhone/hardware proof.

References checked for this amendment:
- PocketPal: https://github.com/a-ghorbani/pocketpal-ai (README and LICENSE)
- Supertonic: https://github.com/supertone-oss-archive/supertonic (README, license, web/iOS examples)
- Cloudflare 1033: https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1033/
- Browser capture: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia

## PocketPal video/chat bridge amendment

The owner supplied five PocketPal screens. They show a video Pal named `Lookie` using
`SmolVLM-500M-Instruct-Q8_0`; its system prompt requests short, real-time camera descriptions
and says to state uncertainty. The Pal editor exposes a capture interval, default model,
system prompt, greeting and suggested prompts. Its Talents include HTML preview, math,
date/time, web search and web-page reading. The Pals screen distinguishes Assistant,
Roleplay and Video Pal types. The Benchmark screen reports iPhone 15 / iOS 26.6.1, model
memory, prompt/generation settings, total time and test results. These are useful capabilities,
but screenshots do not prove an external streaming API or simultaneous PocketPal-to-Alice
conversation channel.

PocketPal's public source describes a React Native UI with an `AgentRunner`, Pals, tools,
`llama.rn`/llama.cpp GGUF inference and ONNX Runtime speech components. This gives us a
possible integration point if a supported app change is needed. The first implementation
must use a SIFTA bridge contract rather than scrape UI text or depend on private iOS app
storage. PocketPal may remain the local video observer while Alice remains the decision and
conversation coordinator.

### Desired concurrent interaction

The phone has two explicitly coordinated lanes:

1. A normal owner chat lane sends messages to Alice and receives Alice's response.
2. A video observation lane samples one frame at a configured interval, asks the video Pal
   for a short description, and publishes a signed, timestamped observation to Alice.

The two lanes share a `paired_device_id`, sequence counter and conversation/session ID, but
each observation must identify its frame time, model, prompt version, confidence and freshness.
Alice may use the newest observation in a reply, ask for a new observation, or say that the
observation is stale/uncertain. A video description is evidence, never a motor command.

### Bridge protocol

Implement a minimal HTTPS/WebSocket bridge in the SIFTA web surface:

- `POST /api/phone/observations` accepts a bounded observation envelope from the paired phone.
- `GET /api/phone/observations?since=<cursor>` supports replay after reconnect.
- A WebSocket or server-sent event stream sends new observations and Alice replies to the
  paired phone. Reconnect uses a cursor and deduplicates by `observation_id`.
- `POST /api/phone/chat` carries owner text with the same session ID; Alice can attach the
  newest observation ID to the context.
- `POST /api/phone/observe-now` requests one fresh frame description. It must be rate limited,
  cancellable and visibly shown on the phone.
- Every observation includes `schema_version`, `observation_id`, `paired_device_id`,
  `conversation_id`, `captured_at`, `received_at`, `frame_sha256` when a frame is shared,
  `description`, `confidence`, `model_id`, `prompt_version`, `sequence`, `expires_at` and
  `privacy_mode`.

Descriptions alone are the default low-bandwidth path. Attach a frame only when Alice needs
visual verification and the owner has enabled frame sharing. Never treat a description as a
live video stream or claim that Alice sees the camera continuously. Default freshness is 5
seconds for navigation context; stale observations remain in history but cannot authorize
movement. The server rejects missing timestamps, replayed sequence numbers, oversized text,
unknown devices and observations older than the configured maximum clock skew.

### PocketPal integration stages

1. **Prove the boundary without modifying PocketPal:** manually configure the Lookie system
   prompt and build a SIFTA developer test that posts a synthetic observation to Alice. Test
   chat and observation traffic concurrently, ordering, replay and stale expiry.
2. **Find a supported export path:** inspect the installed app/version and public source for
   an Intent/Share Sheet, local HTTP endpoint, deep link, or documented callback. Record what
   iOS actually permits. Do not assume the Video Pal's internal result is accessible to Safari.
3. **If no export exists, choose one small integration:** add a documented PocketPal fork
   change that emits the SIFTA envelope, or implement a native SIFTA companion that owns the
   camera and uses PocketPal only for on-device inference. Do not build both paths at once.
4. **Measure:** frame interval, description latency, phone CPU/RAM/battery, network bytes,
   dropped observations, queue delay and response latency on the iPhone 15. Benchmark values
   in the screenshot are model-test results, not proof of video-chat latency.
5. **Only after observation reliability:** allow Alice to propose a movement direction for
   owner confirmation. ESP32 commands still pass through the deterministic simulator and
   safety contract; a video description or LLM reply cannot directly move wheels.

### Required acceptance tests

- Owner chat remains usable while video observations arrive.
- A delayed video result is visibly marked stale and cannot overwrite a newer result.
- A reconnect replays each observation once, in sequence order, without duplicating chat.
- A frame description names the video model and capture time.
- Video permission denial leaves text chat functional.
- PocketPal unavailable leaves the SIFTA bridge functional with a clear degraded state.
- `observe-now` cannot create an unbounded capture loop.
- Alice's proposed action cites the observation ID and asks for owner confirmation.
- Simulator rejects an action based only on an expired or uncertain observation.

### Research and licensing note

PocketPal's public README states that it supports on-device chat, voice, Pals, tools,
benchmarking and hardware acceleration, and that its repository is MIT-licensed. Its source
describes the `AgentRunner` and native bridges, which are candidates for a fork or companion
integration. Verify the repository commit and the installed App Store version before coding
against internals. Model and voice assets may have separate licenses. Keep the first bridge
independent so licensing or App Store restrictions do not block the robot experiment.

## Evidence From The Current Node

- `Network/websites/stigmergicoin.com/index.html` is currently a static marketplace page. It has no camera capture, microphone capture, GPS readout, push-to-capture control, or SIFTA sensor submission path.
- The existing SIFTA organs already provide useful local building blocks: `System/swarm_gps_sensor.py`, `System/swarm_camera_reality_context.py`, `System/swarm_background_audio_receipts.py`, camera target/lease code, and the unified-field ledgers.
- The current camera contract is one active physical eye at a time. Keep that invariant for the first milestone; do not add parallel camera capture while debugging device selection.
- The Cloudflare tunnel config at `~/.cloudflared/sifta-web.yml` currently routes only `stigmergicode.com` to `http://localhost:8100`. It has no `stigmergicoin.com` ingress rule.
- The tunnel launchd job is running, but its logs show intermittent DNS resolver failures against local resolver `::1`; later entries show registered Cloudflare connections. This is an operational reliability issue, not evidence that the application is healthy.

## Product Boundary

The first robot is a controlled sensing experiment:

1. The owner presses **Grab sample**.
2. The browser captures one camera frame, one bounded audio burst, and the latest permitted location snapshot.
3. The local SIFTA bridge normalizes them into one timestamped, hash-linked sample packet.
4. A vision model produces fallible scene text; speech recognition produces fallible transcript text.
5. Deterministic code assembles the unified-field summary and displays it back to the owner.
6. The UI asks the owner to move the laptop a requested distance/direction.
7. The owner presses **Grab sample** again. The system compares samples and reports only measured changes.

The model may describe evidence and propose a next observation. It must not directly drive motors, claim precise distance, claim GPS when unavailable, or claim consciousness/AGI from a successful demo.

## Phase 0: Restore Public Web Reachability

Luna:

- Add `stigmergicoin.com` to the `sifta-web` tunnel ingress, preserving the existing `stigmergicode.com` route and the final 404 rule.
- Verify the Cloudflare DNS record for `stigmergicoin.com` targets the `sifta-web` tunnel. Do not modify unrelated zones or tunnel credentials.
- Verify the local origin serves the correct site for the host header, not just the default nginx page.
- Add a `/healthz` response containing build ID, origin name, and no sensitive data.
- Test locally with host headers, then through the public domain. Record the exact Cloudflare/tunnel error if DNS or the tunnel still fails.
- Investigate the local resolver used by launchd. Prefer a stable resolver configuration or an explicit cloudflared resolver option only after confirming the machine's network policy; do not hide repeated reconnects with an infinite retry loop.

Acceptance:

- `curl -H 'Host: stigmergicoin.com' http://127.0.0.1:<origin>` returns the site.
- `https://stigmergicoin.com/healthz` returns HTTP 200 through Cloudflare for three consecutive checks.
- Tunnel status shows registered connections and no restart loop for five minutes.

## Phase 1: Build The Stigmergicoin Capture UI

Luna:

- Preserve the existing visual identity, but add a clearly separate **Robot Workbench** route or panel rather than mixing capture controls into the marketplace hero.
- Add camera preview using one `getUserMedia({video: ...})` stream and an explicit device selector showing the selected device label/id when available.
- Add microphone permission and a bounded audio burst control. Default to a short window, such as 3-5 seconds, with visible recording state and cancellation.
- Add **Grab sample** as the only capture trigger for the first milestone. No continuous upload.
- Add a sample timeline showing capture time, camera frame hash, audio receipt, location status, processing status, and errors.
- Add a privacy indicator: local-only, public-share disabled by default, no raw frame/audio upload unless the owner explicitly enables it.
- Add a movement prompt card with requested direction/distance, a countdown, and a second capture button. The initial distance is an instruction, not a measured fact.

Acceptance:

- Camera and microphone permissions can be denied without breaking the page.
- A capture produces one immutable sample ID and a visible receipt.
- Repeated clicks cannot create duplicate samples for the same capture nonce.
- The page never claims GPS success unless a fresh, valid location receipt exists.

## Phase 2: Local Sample Bridge

Luna:

- Define a versioned `SensorSample` schema with `sample_id`, `captured_at`, `sequence`, `camera`, `audio`, `location`, `device`, and `truth_labels`.
- Use the existing one-eye camera lease and camera reality context. Reject stale or conflicting camera targets.
- Normalize images through the existing attachment normalizer; store bounded JPEG/WebP derivatives and hashes, not unbounded raw media.
- Route audio through the existing audio ingress/receipt path. Store transcript plus confidence and receipt metadata; raw audio retention must be opt-in and bounded.
- Read GPS through `read_location_snapshot()` and mark `UNAVAILABLE`, `STALE`, or `SUCCESS` explicitly.
- Write the packet to a local append-only ledger with a generation ID and parent sample ID. Make replay idempotent.
- Add a small local HTTP/WebSocket API for the web UI: `POST /api/samples`, `GET /api/samples/<id>`, `GET /api/healthz`, and a read-only stream for processing status.

Acceptance:

- A sample remains interpretable after an application restart.
- Every derived result points to the exact source sample and model generation.
- No UI request can invoke arbitrary shell commands or Ollama models.
- Payload limits, origin checks, and local/public authentication boundaries are tested.

## Phase 3: Unified-Field Processing

Luna:

- Add a deterministic assembler that combines camera, transcript, location, clock, and device-health evidence.
- Keep source truth separate from model interpretation. Use fields such as `observations`, `inferences`, `unknowns`, `conflicts`, and `next_action`.
- Use MiniCPM-V or another measured local vision model for frame-to-text, and a text cortex for summarization. Do not call the vision model “best” or “fastest” until benchmarked on this node.
- Add a model capability check before sending images. Text-only models receive no image payload and must not be presented as having seen the frame.
- Add a compact summary for Alice and a detailed expandable evidence view for the owner.
- For the second sample, compare only timestamped observations and report `changed`, `unchanged`, or `unknown`; do not infer exact movement from a single frame.

Acceptance:

- Text-only and vision-capable routes are both tested.
- Stale, missing, and conflicting modalities remain visible in the summary.
- A model timeout yields a recoverable partial result, not a fabricated answer.

## Phase 4: Deterministic ESP32 Scaffold

Luna:

- Create a separate ESP32 firmware contract, not direct laptop-to-motor improvisation.
- Boot state machine: `SAFE_BOOT -> SELF_TEST -> IDLE -> ARMED_BY_OWNER -> EXECUTE_PRIMITIVE -> STOP`.
- Implement only bounded primitives initially: stop, heartbeat, low-speed forward, low-speed reverse, and emergency stop.
- Add watchdog, command sequence number, expiry/deadman timeout, battery/connection status, and a physical emergency-stop input.
- Use Wi-Fi/BLE only as a transport. The ESP32 validates commands locally and refuses unknown, stale, expired, or unsafe commands.
- Start with a simulated ESP32 transport and fake encoders/IMU before connecting wheels. No autonomous navigation in Phase 4.
- Define telemetry packets for battery, IMU, wheel encoder, command acknowledgement, fault code, and firmware version.

Acceptance:

- Lost connection causes stop within the specified deadline.
- Duplicate and out-of-order commands are rejected.
- Safety tests run without hardware in CI, then on a bench with wheels lifted.
- No vision-language model output can directly bypass the firmware safety state machine.

## Phase 5: Closed-Loop Movement Experiment

Astra review required before hardware motion:

- Calibrate camera intrinsics and document the actual camera placement.
- Define what can be measured: visual feature displacement, optical-flow change, IMU acceleration, encoder distance, and GPS accuracy. Do not use GPS for five-meter indoor movement.
- Use owner-confirmed movement prompts. The owner remains the actuator until the deterministic scaffold is proven.
- Compare before/after samples and sensor telemetry. Report uncertainty and failure modes.
- Only after the bench tests pass, allow a very low-speed primitive under a physical stop and a short command expiry.

## Sensor Inventory For This MacBook/Phone Setup

Likely available, subject to permissions and hardware:

- MacBook camera: visual frames.
- MacBook microphone: bounded audio bursts and speech transcription.
- macOS clock/time zone: reliable local time, not location.
- CoreLocation: possible Mac location fix, often unavailable or coarse indoors.
- Wi-Fi/network interface: connectivity and coarse network identity, not a precise location truth.
- Bluetooth: nearby-device observations if permission and hardware allow; not a direct distance truth.
- Screen/window state: software context, not a physical-world sensor.
- Phone GPS/camera/mic: available only through an explicit phone bridge; do not silently assume the iPhone camera is active.
- ESP32 later: IMU, wheel encoders, battery, motor driver state, and optional distance sensors.

## Test Matrix

- Web: permission denied, one capture, double-click idempotency, reload recovery, offline origin, public origin.
- Camera: one-eye lease, hot-plug/disconnect, stale frame rejection, device switch, no second hidden capture.
- Audio: permission denied, timeout, cancellation, transcript confidence, TTS echo guard.
- GPS: success, stale fix, unavailable, permission denied, invalid coordinates.
- Fusion: missing modality, contradictory timestamps, model timeout, stale generation, replay.
- ESP32 simulation: boot faults, watchdog, deadman, duplicate command, out-of-order command, emergency stop, reconnect.
- Security: no arbitrary commands from browser input, no public raw media exposure, authenticated local bridge, bounded payloads.

## Open Questions For Astra

1. Should `stigmergicoin.com` expose only a local-owner workbench, or also a remotely accessible authenticated workbench? Public camera/microphone capture must not be enabled by default.
2. Which phone bridge is intended: browser WebRTC, a native iPhone companion, or the existing iPhone GPS launchd path? This determines the transport and permission model.
3. What exact ESP32 board and motor driver will be used? The firmware pin map cannot be finalized without this.
4. What is the first physical platform: laptop-on-wheels, phone-on-wheels, or a dedicated robot chassis? The control loop and camera geometry differ.
5. Which vision model is accepted after a measured benchmark on the M5 24 GB node? MiniCPM-V is a candidate, not a proven optimum.
6. What is the required safety envelope: maximum speed, wheel lift test procedure, physical stop, and command expiry?

## Handoff Order

1. Luna: fix Cloudflare ingress/origin health and add the local-only capture UI skeleton.
2. Luna: implement the versioned sample schema, local bridge, ledgers, and offline tests.
3. Luna: implement deterministic fusion and model capability routing.
4. Luna: implement ESP32 simulator and firmware contract tests; no motor hardware yet.
5. Astra: review evidence, threat model, sensorimotor claims, and the hardware-motion gate.
6. Only after Astra approval: bench-test ESP32 with wheels lifted, then run the owner-guided two-sample experiment.

## Non-Claims

This plan does not establish AGI, consciousness, autonomous agency, precise localization, or safe physical movement. It establishes an evidence-backed path from controlled sensing to a bounded robot scaffold.
