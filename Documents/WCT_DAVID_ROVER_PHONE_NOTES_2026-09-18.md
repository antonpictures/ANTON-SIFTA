# WCT Notes — rover lane + phone world input (2026-09-18)

## State: David's rover connection

The transport stack exists and is tested (34 focused tests): stigmergicoin.com
rover API lane (pair/telemetry/command/ack, motion and telemetry credentials
separate), RVR1 UDP adapter with the corrected axis contract (X lateral /
Y forward, eight-point scan), front-LiDAR safety gate, and David-side
`scripts/david_rover_gateway.py` (strict command schema, finite TTL, one-time
claim, ack, never touches Alice's owner credential).

What is missing before Alice drives the rover in David's home:
1. David provisions his side: runs the gateway on his LAN with the rover's LAN
   address + private RVR1 key + SIFTA pairing token; confirms flashed firmware
   commit and supervised low-speed acceptance.
2. Rover controls on the stigmergicoin phone page (arm/disarm, drive/turn,
   live telemetry) — the API lane exists server-side; the phone UI does not yet.
3. Alice cortex -> rover lane thin client ("drive to the sofa" via the command
   queue), then supervised first drives with the stop button in hand.

## Phone world input (George's iPhone, live now)

- Keyboard dismiss + single-screen fit: DONE (scrollable phone layout).
- Caption overlay: DONE — after a batch is processed, Alice's first-person
  description is written on the photo itself (dark pill over the preview),
  like the example George attached.
- BLOCKER for real batches: HTTP 403. The phone posts observations with
  `capture.source=stigmergicoin-web`, and the server requires the phone to be
  PAIRED: `_phone_principal()` authenticates the SIFTA owner token; without it
  every batch is refused 403 "Pair this phone before sending sensor
  observations." FIX: pair the phone in Alice Settings > Network > Telefon
  local (QR pairing sets the owner cookie for stigmergicoin.com). After
  pairing, batches flow and the caption overlay fills with descriptions.

## Faces recognized by name?

- Detection: already live — the page reports face present/absent.
- Name recognition: possible, but with three honest boundaries. (1) The
  browser FaceDetector only detects faces; naming needs Alice's vision lane
  (a vision model) with an ENROLLED name list (owner-consented). (2) On the
  PUBLIC web surface, visitors must stay unnamed — naming strangers is a
  privacy harm; only owner-enrolled people (George himself, David with his
  consent) may be named. (3) Name claims are model interpretations, not
  verified world facts — the reply already labels summaries honestly, and
  enrolled-name matches should carry the same caveat ("I believe this is
  George, enrolled by the owner").

Implementation path: pair George's phone (owner token) -> batches run with
owner authority -> Alice's vision lane matches the frame against enrolled
face templates (photo + name supplied by George only) -> the caption can then
say "George at his desk" instead of "a person with glasses". Until enrollment
exists, captions stay generic — honest by design.
