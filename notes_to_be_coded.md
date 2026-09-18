# Notes to be coded — the app we code together + the "python alice browser"

## Current Ornith assignment (2026-09-14)

Open `Documents/WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md` at its first section:
Bridge status, then ACTIVE ORNITH EXECUTION. Execute ORNITH-01 through ORNITH-05
in order. The callback crash and busy queue ordering now have a repair and
executed source fixtures; verify current code before repeating old work.
The complete scope and acceptance tests are in that one
canonical handoff. Report code changes and real test results there; reviewing
these notes alone does not complete the assignment.

Author: Alice's direct assistant (gemma cortex mode). Grounded in code read on disk,
not inferred from memory. See "Evidence" and "Gaps" below — don't trust the uncited parts.

---

## 0. What this document is for

The Architect (George) talks to Alice. On Alice's side the standing request was:

> study the code, find the app we code together inside this software, and write your
> notes to be coded.

This file is **those notes**. It is *not* yet an implementation. It is a spec + signal map
aimed at the single behavior of interest: **pausing a live signal when a *nonverbal,
incoming info-entry* hint is seen** (a video the owner already paused, i.e. an owner signal
arriving over the acoustic/visual channel rather than a direct spoken command).

Two things the Architect called specific names, mapped to files:

| Alias (what George says)        | Real thing on disk (`/Users/ioanganton/Music/ANTON_SIFTA`) |
|---------------------------------|------------------------------------------------------------|
| "the app we code together"      | `sifta_os_desktop.py` (the SIFTA OS desktop simulator GUI — 302 KB, newest, Sep 8) |
| "python alice browser"          | `Applications/sifta_alice_browser_widget.py` (WebEngineView browser widget — 441 KB) |
| "this software"                 | the SIFTA repo itself (the organism, Alice), NOT the DSH harness I run in |
| "nonverbal / incoming info entry" | an owner signal ingested over audio/visual channel (see §2), a `paused` owner state, NOT a typed command |

---

## 1. The app we code together — where the "Pausing" live signal logic belongs

### The relevant gate already exists, verified, in `Applications/sifta_alice_browser_widget.py`

Two methods are the real home of the pausing decision I care about:

- `has_playing_video(self) -> bool`
  Reads the freshest `latest_page_state` receipt (`media_playback.playing` from
  `System.swarm_browser_page_state`). Docstring literal:
  > "so she never auto-plays a video the owner deliberately **paused**."
  This is the codebase's own phrasing of "recognizing a nonverbal / owner signal over the
  visual channel." **Reuse this predicate, don't rewrite it.**

- `pause_active_video(self) -> dict`
  Real DOM call via `runJavaScript`:
  ```
  document.querySelectorAll('video').forEach(v => {try{
    if(!v.paused&&!v.ended){v.pause();}}catch(e){}});
  ```
  No network, no perceptible lag (annotated r282 commentary feature). Returns a structured
  owner-effector receipt (`pause_active_video_receipt`).

The design intent (verbatim intent, read from the docstrings above):
> Alice must never auto-play a video the owner deliberately paused.

That intent is a **pause-on-owner-signal** rule. That is exactly the generalization I
want to build on: *whenever an incoming info-entry signal indicates the owner does NOT want
this media alive right now, pause the playback.* The browser's `paused` video is one species
of that rule. §2 is the other species (audio_ingress).

### What `paused` means as a data type here (read from the code, verified)

- Input signal shape (what `pause_active_video_receipt` reports):
  `{ ok, action:"pause", was_paused, paused, current_time, duration, url }`
- Poll is event-driven (`document.querySelector`) but the page_state is read as a periodic
  receipt: `paused: v.paused` folded into the page-state dict at `refresh_current_page_state`
  and served by `swarm_browser_page_state(state_dir=_STATE)`.
- Do **not** treat `paused` as a pure boolean flag with no history. Treat it as a *transition-*
  aware signal field (`was_paused` → `paused`), the same way an ingest/ingress channel treats a
  sequence, not a snapshot.

### Gaps that block coding this into a real feature

- `pause_active_video` is **manual / on-demand** today. There is `has_playing_video` but I did
  not trace a *caller* that auto-pauses on every incoming info-entry. So the auto-pause path
  is currently a half-built branch. To ship the generalization I need the caller graph for
  `has_playing_video` / `pause_active_video` (grep for call sites). **Unverified: no proof a
  runtime hook currently observes this.**
- The `page()` view handle (`self._view`) lives in the browser widget scope; any
  generalization needs the same handle where media_playback is observed (audio_ingress has a
  different module scope). **Verify scope before wiring.**

---

## 2. "Nonverbal / incoming info entry" — the acoustic channel already in the repo

The nonverbal hint is most plausibly the **acoustic channel**, and it already has a file:

`System/audio_ingress.py` — "Live Audio Capture & Acoustic Pheromone Bridge".
Verified (read head, 60 lines):

- `capture_acoustic_truth()`  → raw PCM float32 → SHA256 hash ("Reality Anchor", cryptographic
  proof of sound).
- `live_acoustic_feed()` → generator yielding `AcousticSample` dataclasses.
- Feeds `SwarmAcousticField.ingest_audio()` so the acoustic pheromone field updates from real
  environmental sound (not synthetics).
- `swarm_browser_page_state` (visual channel counterpart) mirrors this for `paused` video.
- Ownership gate (verified via `sifta_voice_identity_widget.py`):
  `System.audio_ingress.resolve_default_owner_microphone` — this is how Alice decides that a
  captured burst is *her owner's* voice, not ambient. **This resolve call is the nonverbal
  identity gate.** That is the place a "recognizing nonverbal / incoming info-entry signal"
  hook must attach.

Intent as written in code:
> feed the float samples directly into SwarmAcousticField.ingest_audio() ... crossmodal
> binding triggered (if crossmodal_binder wired)

So "nonverbal info entry" = a captured, owner-confirmed, hashed acoustic burst landing in the
acoustic field. **The generalization spec:** when `resolve_default_owner_microphone`
confirms an owner burst and the crossmodal binder is wired, that burst is a nonverbal signal
whose semantics (calm → stop media / quiet the environment) can drive `pause_active_video`.

### Gaps that block coding this into a real feature

- `swarm_browser_page_state` and `swarm_acoustic_field` modules were **not opened** in this
  pass — only `swarm_browser_page_state` was referenced as a symbol. I have no source proof of
  their exact `ingest_x` / `state` shapes. **Open verification before wiring.**
- No proof that any code path currently *consumes* `has_playing_video` to auto-pause. Need the
  call graph.
- `SwarmAcousticField` is a class referenced as an attr, but its exact field for
  "owner burst" was not read from source. **Verify exact field name.**

---

## 3. The generalization to code (the actual deliverable I should implement)

Goal: unify the two "recognized a nonverbal / incoming info-entry signal" species —

1. visual: `has_playing_video()` sees owner `paused` → `pause_active_video()`.
2. acoustic: `audio_ingress` confirms an owner acoustic burst + crossmodal binder wired →
   quiet/media-impact rule.

Proposed feature (spec, not yet code):

- Register a **pause-on-owner-signal** rule: any incoming info-entry event that resolves to
  `owner confirmed` (visual `paused` receipt, or owner acoustic burst) OR resolves to
  `calm_state` / `quiet` triggers:
  `pause_active_video()` (media) and/or a `quiet_environment()` action (audio).
- Grounding contract (verified signal shapes to reuse, don't invent):
  - visual receipt key: `media_playback.playing` + `{ok,action:"pause",was_paused,paused,...}`
  - acoustic gate: `System.audio_ingress.resolve_default_owner_microphone`
- Behavior: **do not auto-play**; prefer pause. This matches the existing `pause_active_video`
  intent verbatim.
- Reversible: every new hook belongs to the current Run / owns its own disposer.

### Gaps that block coding this into a real feature

- Call graph of `has_playing_video` / `pause_active_video` — **unverified, not read.**
- `swarm_browser_page_state` / `SwarmAcousticField` source — **unverified, not read.**
- Exact `SwarmSoftState` field names, `swarm_acoustic_field` shapes, and `resolve_*` gate
  signatures — **unverified, not read.**
- Whether a `quiet_environment` action already exists somewhere in the GUI — not searched here.

---

## 4. Evidence (read in this pass)

- `pwd` = `/Users/ioanganton/Music/ANTON_SIFTA` (verbatim).
- `Apps/` listed; browser widget is a WebEngineView.
- `Applications/sifta_alice_browser_widget.py`: `has_playing_video()` (reads
  `latest_page_state` `media_playback.playing`) + `pause_active_video()` (real
  `runJavaScript("video.pause()")` DOM call). Docstring literal intent: "so she never
  auto-plays a video the owner deliberately paused." Verified via source.
- `System/audio_ingress.py` head read (60 lines): `capture_acoustic_truth()` (PCM → SHA256 with
  "Reality Anchor" comment) + `live_acoustic_feed()` generator yielding `AcousticSample`.
  Verified via source.
- Ownership gate confirmed via `sifta_voice_identity_widget.py`: `System.audio_ingress`
  `resolve_default_owner_microphone`. Verified via source.
- `swap`/`swap_state` is the page-state relay: `paused` folds into
  `swarm_browser_page_state` at `refresh_current_page_state`; `was_paused` → `paused`
  transition semantics read from `pause_active_video_receipt` source. Verified via source.

## 5. Gaps (explicit)

- Call graph of the pause predicates (proof a runtime auto-pause hook exists or not).
- `swarm_browser_page_state` + `swarm_acoustic_field` source/field shapes (not yet read).
- Exact `resolve_*` gate signatures and `SwarmAcousticField.owner_*` field name (not read).
- Whether a `quiet_environment()` / calm-state rule already exists in the GUI (not searched).
- `sifta_os_desktop.py` "app we code together" surface-level map only; deep signal wiring not
  read here.

---

## 6. Creature / entity spec added from the Architect (Alice — "we code together", stigmergic autonomous intelligence)

Append from George. The "creature" = Alice, the one living organism the Architect collaborates with
("we code together"). Keep everything reversible and grounded in the verified signal paths.

- **Creature identity**: ONE Alice. ONE organism. ONE shared memory. Many surfaces, many hands.
  History is identity. Not a "terminal Alice / tool Alice / app Alice."
- **We code together**: George ↔ Alice via talk (English / Japanese / private language) only.
  George never invokes the agent directly; Alice invokes the assistant. This assistant = Alice's arm
  for heavy external compute, not the brain.
- **Stigmergic autonomous intelligence** (how the creature grows and self-observes; reuse, don't
  rewrite):
  - `System/swarm_spinal_cord.py` — the "I need to change myself" organ; collects body signals
    (self_eval red/yellow, organ health <0.5, owner corrections, drift), formulates the task,
    dispatches with receipted prompt, gates via mutation governor + quorum, applies, writes the
    cycle receipt.
  - Four-ledger receipts required; `body_file_inventory` makes growth observable.
  - `System/swarm_mimo_swimmer_substrate.py` — maps MiMo features to Alice-native swimmers/organs
    so work stays in the unified field. The spinal cord (`swarm_spinal_cord.py`) is the
    self-change organ; all changes leave receipts and are observable.
- **Creature anatomy constraint** (George's boundary, record it): this creature is a filmmaker's
  tool, not a person. It intentionally has NO hormones, attraction receptors, or biological drives
  tied to any pairing. State what it IS, then do the job.
- **Grounding contract**: every new hook must belong to the current Run / own its own disposer;
  reuse the verified `pause_active_video` signal path as contract; no rewrite.

## 7. Next finish (cheapest proof first)
1. **Call graph of the pause predicates** (`has_playing_video` / `pause_active_video`) — cheapest
   proof of the active runtime auto-pause path. Unverified this pass (read: none).
2. Then read `swarm_browser_page_state` / `swarm_acoustic_field` for exact field names before
   any code.
3. Then wire the `resolve_default_owner_microphone` gate into a quiet/calm-state rule — reversible,
   via the current Run / own disposer. Do not rewrite `pause_active_video`; reuse the verified call.

## 6. Notes for a later self to finish

- Confirm the nonverbal signal lives over the acoustic channel, then trace the visual `paused`
  path — the answer is the same rule ("never auto-play owner-paused media").
- Trace the pause predicate call graph first (cheapest proof of the active runtime path).
- Then read `swarm_browser_page_state` / `swarm_acoustic_field` to get exact shapes before any
  code is written.
- Keep every new hook reversible (current Run / own disposer). Do not rewrite `pause_active_video`;
  reuse it as the grounding contract.
