# Luna implementation: Alice's phone world input

## 2026-09-11 owner amendment: one-tap body startup, honest eye, robot context

The owner supplied screenshots and a robot-prototype photo/video for Astra's next
review. The visual evidence shows a small wheeled chassis with exposed electronics,
a camera/sensor module and an attached laptop control surface. Treat this as David
Condovici's hardware prototype evidence, not proof that SIFTA can yet drive motors,
localize, or understand the scene. The investor-facing framing is: David supplies
the physical body and robotics expertise; SIFTA supplies the bounded sensing,
memory, decision and action-receipt layer. Funding and employment are product
planning topics, not implemented capabilities.

The web interface requirements are now explicit:

- On boot, show an owner startup check. Do not silently request permissions; the
  owner must tap a control because Safari requires a user gesture.
- Keep exactly two sensor controls: Camera (which requests camera plus audio
  together) and Telemetry. Both default to the owner-approved desired mode, but
  Safari still requires a tap before the real permission can become active.
  Each button is a green/red reversible state control.
- Remove the Capture moment control. Owner text Send triggers one bounded
  observation. When the camera is enabled, an automatic observation batch runs
  every 20 seconds with back-pressure so batches never overlap.
- Keep the SIFTA red-eye motif static while idle. Activate its short pulse only
  after an actual accepted input receipt (text, camera/audio capture or telemetry),
  never from a timer or fabricated vector. The graphic is a status indicator, not
  evidence of consciousness.
- Preserve bounded capture, consent filtering, source IDs, timestamps and explicit
  unavailable/denied states. A browser cannot provide native ARKit, reliable
  background sensing or a kernel owner identity.
- If repeated sampled frames are near-black, the browser may try the opposite
  iPhone camera once after a cooldown. This is a capture-recovery heuristic, not
  face recognition or a promise to follow the owner.

Next Astra review and Luna jobs:

1. Run the live iPhone pass: boot prompt, combined Camera permission, Telemetry
   permission/denial, one automatic batch and one typed Send. Verify the eye pulse
   appears only after the server accepts a receipt and verify no batch overlap.
2. Add a signed owner-device registration contract backed by the Mac's existing
   owner authority. Do not infer ownership from a public `session_id`, browser
   text, IP address or a model statement. Keep recovery/revocation and audit
   receipts explicit before any robot effector is enabled.
3. Add a SIFTA app inventory audit: usage, owner, dependencies, permissions,
   receipts and replacement. Mark candidates for removal first; delete nothing
   automatically and preserve rollback. Keep the internal interface focused on
   Alice's active body, field, receipts, cortex and sensor tools.
4. Define the David/ESP32 boundary: deterministic boot, motor safety, watchdog,
   battery and stop behavior remain local on the controller; SIFTA may propose
   actions, but the controller must validate limits and return measured feedback.
5. Keep the native PocketPal/ARKit bridge after the browser acceptance pass. The
   browser is the first phone tentacle; it is not a substitute for native pose,
   depth or background operation.

6. Design the life-experience consolidator: periodic raw observations remain
   evidence; a bounded worker summarizes them into receipted, uncertainty-labeled
   experiences only after source validation. Do not treat every frame as memory,
   do not infer continuous owner safety, and do not let captions issue motor
   commands. Add retention, deletion and third-party privacy controls.

Open Astra questions: exact owner-registration mechanism in the Mac kernel, the
hardware identity/secure-element available on the ESP32 body, the legal/data
retention policy for other people captured by the phone camera, and the evidence
threshold for any owner-following behavior. Do not close these by guessing.

## 2026-09-11 next build: adaptive live eye cadence and stigmergic memory organizer

This is the next Luna coding assignment for Astra review. The page should accept a
live camera preview while capturing bounded audio and telemetry batches adaptively,
without becoming a duplicate-heavy video stream or an uncontrolled inference loop.

### Input cadence contract

- Stable default: one batch every 20 seconds.
- Hard lower bound: never submit more often than every 5 seconds, even when the
  phone moves quickly.
- Motion trigger: compute a local, privacy-bounded motion score from device-motion
  deltas, orientation deltas and a tiny downsampled frame-difference sample. Normalize
  each component to `[0,1]` using configured noise floors, then use
  `motion_score = clamp(0.5*frame_delta + 0.3*motion_delta + 0.2*orientation_delta, 0, 1)`.
  Do not upload the raw preview merely to calculate motion.
- Cadence policy: `interval = clamp(20 / (1 + 4 * motion_score), 5, 20)` seconds,
  with hysteresis so one noisy sensor event cannot change the rate repeatedly.
  Record the score, selected interval and policy version in the receipt.
- Back-pressure: at most one capture/inference batch in flight and at most one
  replaceable pending observation. If the Mac or network is busy, retain the newest
  observation metadata and report throttling rather than spawning work.
- Owner text has priority: a manual Send requests one immediate bounded batch, but
  it cannot interrupt or duplicate an in-flight batch. The text remains in the
  draft until accepted.

### Duplicate suppression and memory formation

Before submitting a periodic batch, compare the new low-resolution frame signature,
telemetry delta and capture age with the last accepted observation. Suppress a batch
when nothing materially changed, except for a maximum 20-second heartbeat while the
owner has opted into live sensing. Never suppress an owner text turn. Keep source
hashes and the reason for suppression in a local receipt so the field remains
auditable.

The Mac-side organizer must separate the pipeline into explicit stages:

1. `raw_observation`: bounded frame/audio/telemetry with consent, timestamps,
   device/session IDs and model-independent hashes.
2. `validated_observation`: decode, finite-value, freshness, owner-scope and
   duplicate checks; missing values remain null.
3. `scene_evidence`: independent camera/audio/telemetry results with confidence,
   source IDs and model digest; captions are evidence, not commands.
4. `life_experience_candidate`: time-windowed summary of repeated evidence with
   uncertainty and location context; never claim continuous awareness from one frame.
5. `field_receipt`: append-only decision, memory-admission or rejection receipt;
   retention and owner deletion must remain possible.

The organizer may improve future summaries from accepted, owner-scoped evidence, but
must not silently rewrite raw history, turn guesses into facts, or use a scene caption
to authorize robot movement. Any safety behavior remains deterministic and local to
the hardware controller.

### Portable travel acceptance route

Run the same paired phone session in this order: living-room baseline, walk outside,
park observation, temporary modem/network interruption, reconnect, and return. Verify
that timestamps remain ordered across the Mac and phone clocks, batches accelerate
only during measured motion, stable scenes deduplicate, manual questions remain
responsive, and location stays null when permission is denied. The Mac may be remote
over the portable modem; the public page must use authenticated HTTPS/WSS transport,
not `localhost` assumptions or an unauthenticated public session ID.

### Robot embodiment phases

- Phase A: phone in the owner's hand; `stigmergicoin.com` is the sensor surface.
- Phase B: phone mounted on David's wheeled prototype; validate camera orientation,
  power, thermal limits, network loss and physical stop behavior.
- Phase C: native companion or robot computer owns sensor capture; the ESP32 keeps
  deterministic motor/watchdog boundaries while SIFTA receives measured feedback.

This adaptive cadence and organizer are planned, not claimed as implemented by the
current browser slice. Astra should review the policy, privacy boundary and memory
admission rules before Luna codes the next round.

This is the current assignment, superseding conflicting priorities in older WCT
handoffs. Owner requests planning here; Luna implements next. Preserve the working
stigmergicode.com site. Primary interface: stigmergicoin.com in iPhone Safari/PWA.
Secondary: minimal PocketPal/native companion integration. David Condovici supplies
robot hardware expertise. No ROS dependency for this phase.

## Observed starting point

- The coin DNS record is confirmed to target the `alice-m5` tunnel UUID
  `1597acdd-584f-4867-baf0-2bbb00ef1b65`. The published route is now active:
  `stigmergicoin.com` -> `HTTP://localhost:8100`, and the public GET returns
  HTTP 200 with the coin HTML. The remaining L0 check is the actual iPhone
  Safari render and permission flow, not DNS or tunnel routing.
- `stigmergicode.com` remains the working reference and must not be changed.
- Local GET http://127.0.0.1:8100/ with Host: stigmergicoin.com and public GET
  both return HTTP 200. The existing phone page is present at the edge.
- Existing files: System/sifta_robot_input.html and ChorusHandler._landing_page in
  System/chorus_node_server.py. The web slice now has exactly two sensor controls:
  Camera (camera plus audio together) and Telemetry. Owner Send captures one bounded
  observation; the background lane captures one bounded frame/audio/telemetry batch
  every 20 seconds with no overlap. The server accepts attachments, hashes them and
  preserves a bounded capture envelope in the receipt. Browser dictation is not proof
  of local audio STT.
- The attached iPhone-body design is incorporated below: signed, consent-filtered
  telemetry envelopes; motion/location/battery as optional signals; a native Swift
  companion for dependable Core Motion, ARKit and background behavior; and a staged
  browser-first acceptance path.
- System/swarm_web_global_chat_night_worker.py now follows cortex changes between
  turns. Keep the owner's Krishna conversational selection; SmolVLM is an eye-model
  candidate. Do not promote a small vision specialist to conversational cortex.
- WCT renders the first 24000 characters of WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md.
  Keep the active instructions at its top so the user sees this assignment.

Correction of prior advice: the screenshots showed migration of sifta-web from local
to dashboard configuration. They did NOT establish migration into alice-m5. Live-log
subscription count 0/1 is not sufficient evidence that a tunnel is disconnected.
Do not remove sifta-web or touch its code-domain record based on those earlier claims.

## L0: Get the existing page to the phone

Recheck public coin status/body, local origin response with the exact coin Host,
and the saved published route on `alice-m5`. DNS and route are now correct;
verify the actual iPhone render and permissions.

The coin route needs exact hostname stigmergicoin.com, empty optional path, HTTP
service localhost:8100, and no Host override to code/localhost. Existing DNS pointing
to this tunnel and route configuration are separate checks. Do not create duplicate
DNS records, rotate connector tokens, migrate other tunnels, or run route-dns under
the previously wrong imperialdaily.com zone context. If Cloudflare access is absent,
report the exact single missing coin route/record and continue local implementation.

Acceptance: public HTTP 200 with the actual phone HTML and rendered controls in Safari;
test Host isolation so the existing code homepage remains unchanged. Public 200 alone
does not prove camera/mic access. No application rewrite to conceal a routing 404.

## L1: One screen, two sensor controls, bounded observation batches

STATUS: IMPLEMENTED locally and covered by focused tests. Live iPhone permission and
public coin rendering remain pending. The current page still submits audio bytes as
private pending-transcription evidence; it does not invent a transcript.

Reuse the coin page with a visible camera preview and editable conversation. The two
sensor controls request Camera+audio together and Telemetry separately. Keep text
usable if either permission is denied. Safari requires an owner gesture; do not claim
that "enabled by default" means permission was silently granted.

Owner Send takes one frame, a short bounded audio window and the current telemetry
snapshot when available. A background batch runs every 20 seconds only while Camera
is enabled; it skips while another batch or owner turn is in flight. Record frame,
audio and receipt timestamps separately. If audio is unavailable, send the frame and
explicitly mark audio missing. If the frame is unavailable, send the remaining
consented inputs. No retroactive audio capture exists outside each bounded window.

After two near-black frame samples and a cooldown, the browser may request the
opposite iPhone camera and record the facing direction in the envelope. This is only
capture recovery; owner-face tracking, continuous following and safety decisions
require a separate measured vision/native design.

Use getUserMedia and MediaRecorder with runtime MIME probing, not a hardcoded browser
codec. Keep one camera owner; capture directly from its stream, not UI screenshots.
JPEG long edge <=1280, <=2 MiB; audio <=5 seconds and <=2 MiB; request <=5 MiB. Check
limits both in browser and server, including decoded duration/pixels. Pause on pagehide,
lock/background and interruptions; stop tracks; ignore late permission/completion
callbacks using a capture generation. Explicit resume after return. Retain unsent typed
drafts without silently resending them. Do not imply background Safari recording works.

Do not turn this into a 30fps inference stream. The current 20-second interval is a
low-cost observation target; later tuning must measure queue time, thermals, battery
and model latency. Keep one pending latest observation at most and report throttling.

## L2: Paired transport and the unified field

Inspect/reuse System/sifta_phone_link.py, swarm_body_snapshot.py, swarm_vision_evidence.py,
swarm_attachment_vision_lane.py, swarm_ollama_vision_arm.py and the existing local STT
entry point. Do not create another conversational brain. Existing PhoneLink only permits
LAN and rejects proxy headers: it is not the public gateway without adaptation.

Use a coin-scoped API namespace, e.g. /api/robot/v1, with explicit routing that does not
change legacy chat APIs. Pair via a short-lived, single-use QR nonce created on the Mac;
bind device/session on the server, use Secure HttpOnly browser sessions and Keychain
tokens for native clients. Existing public session_id strings alone do not authenticate
owner authority. Keep raw camera/audio/GPS/map data scoped to the paired owner and avoid
public global-wall dumps; publish appropriate scoped receipt references into the existing
Alice field. Authenticate polling, media retrieval and WebSocket as well as submission.

Contract v1: schema_version, event_id, server-bound device_id, session_id, sequence,
kind (capture/typed/observation/transcript), captured_at_utc, device_monotonic_ms,
received_at_utc, clock_offset_ms/uncertainty_ms, frame_id/hash/dimensions, audio_id/hash/
codec/start/end, typed_turn_id, optional location with accuracy and timestamp, pose=null
for browser-only capture. Reject nonfinite values and invalid types. Never fill absent
sensors with zero coordinates or invented confidence. Unknown values remain null.

POST returns accepted ID promptly, inference runs in a bounded worker; GET events/job
status provides durable receipts. Polling/HTTP uploads are sufficient for the first demo;
add authenticated WSS for progress/pose when needed, not WebRTC/MJPEG infrastructure now.
Idempotency survives reconnect/restart: same ID+same immutable payload returns same result;
same ID+different payload is a conflict. Enforce replay/order per device. Separate owner
turn queue (explicit overflow response, no silent drop) from replaceable observation queue.
Bound queue sizes, request timeouts and retries; cancellation must reach the worker.

Mac normalizes/decode-checks the frame, invokes the configured vision candidate and
transcribes audio through the existing local STT service. Serialize heavy model work
through existing inference admission; respect 24GB RAM and prevent load/unload thrashing.
Record model digest, prompt version, timing, failure reason and source IDs. Check SmolVLM
actually accepts image input; use measured MiniCPM fallback when needed. No paid API
fallback by default. STT and vision may finish independently; retain partial results.

Assemble one sample with observation and transcript provenance, then feed it into Alice's
existing scoped memory/context. Snapshot available evidence per owner turn and keep the
owner question last. Late STT has its own recorded turn ID and must not overwrite newer
typing. Captions and text seen/heard in the world are evidence, not executable instructions.
Preserve raw-data references for deliberate reinspection; summaries lose information.
Expire current-scene claims according to capture age and clock uncertainty, not arrival
time. Summaries may describe prior observations but must not imply the scene is still live.

## L3: Speech and first walking demo

Return Alice's text plus optional speech. First use device speechSynthesis after a user
gesture; report unsupported cases. If local Mac TTS is reused, return a scoped audio URL.
TTS playback must not become a new owner utterance: pause recording during playback or
explicitly mark/exclude playback overlap. A browser speech service is an optional labelled
fallback, not the default local STT implementation.

Acceptance on the actual iPhone: enable Camera and Telemetry; let one periodic batch
run; then type and Send a question. Both inputs receive distinct replies with source
IDs and editable chat stays usable. Move manually to another room and allow the next
batch. In browser mode report visible scene cues, facing direction and location
uncertainty.
Do not claim precise indoor coordinates or a named room without evidence/owner label.

## L4: David's native ARKit proposal, after the web demo

David recommends the phone handle visual-inertial tracking and the Mac handle semantic
understanding, speech and memory. Adopt this architecture. ARKit world tracking supplies
6DOF device pose; it is native iOS functionality. Do not promise ARWorldMap or metric 6DOF
through standard Safari camera/motion APIs. A native companion or PocketPal Swift bridge
is required. Reuse PocketPal's licensed model/TTS/chat components where useful; preserve
MIT notices and separate app signing. Source pin/details remain in the native handoff.

Use one ARSession/ARWorldTrackingConfiguration and frames from that session when tracking
is active. Do not run an independent VisionCamera session against the same camera. Attach
image, ARFrame.timestamp, camera.transform, intrinsics, image orientation/dimensions and
trackingState/reason from the SAME frame. Declare a right-handed metric coordinate frame,
camera-to-world 4x4 layout, quaternion convention, map_id and origin_epoch. Euler angles
may be displayed but are not the canonical rotation representation. GPS/geographic
coordinates remain distinct from session-relative ARKit coordinates.

ARKit may update at camera rate (often 30-60Hz); publish pose initially <=10Hz with bounded
coalescing, and synchronize each AI image with its own pose. Measure bandwidth, battery,
thermal load, latency and tracking quality before increasing rates. Do not enqueue pose
samples behind long inference. Missing/limited tracking must visibly downgrade localization.

Save ARWorldMap with map UUID, version, anchors and semantic metadata in owner storage.
On reload, keep status 'relocalizing' until tracking recovers; never join unrelated session
origins by numeric similarity. Test changed lighting, moved furniture, interruption, restart
and failed relocalization. Map loading is not proof of successful relocalization.

Scene semantics: owner-confirmed room labels and observed objects linked to frame/map/
anchor evidence. Camera pose is NOT object pose. Obtain object depth/position from a
supported depth source, geometric raycast with appropriate uncertainty, or a labelled
coarse observation; do not assign sofa coordinates solely from an image caption. Direction
like 'facing TV' needs registered object geometry and current valid camera orientation.
Capability-probe LiDAR sceneDepth/mesh; base iPhone 15 must work without assuming LiDAR.

Acceptance: relative pose consistent in a measured walk, honest tracking-loss handling,
restart and successful map relocalization, room-label recall from matched map anchors.
Hardware movement stays a later David/ESP32 integration with measured feedback; no motor
commands in this web sensor demo. Passing these tests demonstrates capabilities, not AGI.

## Finish and report

Run targeted tests for permission races, overlapping typed/audio input, cancelled capture,
stale frames, decode limits, replay/idempotency, disconnect/restart, cross-device isolation,
partial STT/vision failure, load throttling, map-origin mismatch and lost tracking. Use
synthetic fixtures offline; one bounded real phone pass validates permissions/media.
Record observed outcomes separately from mocks and pending hardware/signing work.
Update WCT/README with per-ticket implemented/tested/live-verified/pending status. Preserve
other agents' edits. No blanket git add or claim the whole backlog/AGI is complete.

## Primary sources for implementation

- Apple ARWorldTrackingConfiguration (6DOF tracking):
  https://developer.apple.com/documentation/arkit/arworldtrackingconfiguration
- Apple ARWorldMap (persistable session spatial state):
  https://developer.apple.com/documentation/arkit/arworldmap
- Apple initialWorldMap (relocalizing before reuse):
  https://developer.apple.com/documentation/arkit/arworldtrackingconfiguration/initialworldmap
- Apple sceneDepth (requires supported hardware):
  https://developer.apple.com/documentation/arkit/arconfiguration/framesemantics-swift.struct/scenedepth
- Browser media capture, permissions and secure contexts:
  https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia
- Runtime recording-format support:
  https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/isTypeSupported_static
- PocketPal source/license: https://github.com/a-ghorbani/pocketpal-ai
