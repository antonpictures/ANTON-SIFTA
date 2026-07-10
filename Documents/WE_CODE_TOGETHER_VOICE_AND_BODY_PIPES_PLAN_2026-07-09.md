# We Code Together — Grok mega-lane plan (2026-07-09, round r1601)

**Planner:** cowork_claude (`claude-fable-5`), IDE_DOCTOR_CLAIM lane, MANA, forgeable.
**Coder:** grok_agent (George: "you write the plan only so I save inference — grok will code").
**Truth label:** the diagnosis below is `OBSERVED` (I measured it on disk just now). The build steps are
`HYPOTHESIS` until they land with receipts + tests.

George's two asks map to two lanes. Lane A is the one bleeding every day — the 14-hour kitchen
transcript where Alice answered YouTube, podcasts, MMA commentary, and ads as if you were talking to
her, spraying "TELEMETRY RECEIPT CONFIRMED" theater. Lane B is the DimOS body-pipes upgrade you
flagged. **I recommend grok codes Lane A first** — it directly answers your three questions and stops
the embarrassment; Lane B is the bigger, more speculative build.

---

## Your three questions, answered from disk (OBSERVED)

**1. "Can Alice recognize my voice?"** — The machinery exists but is too weak to trust today.
`System/swarm_voice_identity_organ.py` extracts voice features and `classify()` votes George's
enrolled exemplars against incoming audio; the Talk widget already wires it end-to-end
(`_voice_identity_george_conf()` → gate `voice_george_conf`). So it is **not** an unwired-plumbing
problem. The problem is quality. I ran leave-one-out on your 7 enrolled exemplars:

- Accuracy across all classes: **52%** (barely above chance).
- Your own voice scored confidence **0.51–0.76**, straddling the gate's 0.60 owner threshold — so
  your real voice is frequently rejected as "not George."
- Worse: a YouTube clip scored **as** primary_operator once, and keyboard noise 3 times.
- Your `voice_identity_ledger.jsonl` was last written **May 4** — two months stale.

The features are naive (RMS / crest / flatness / ZCR + a 13-bin toy MFCC). They cannot separate you
from a male podcast host. That is the root cause of the transcript.

**2. "Against clips / room noise / videos?"** — The media-vs-live discriminator exists
(`swarm_media_ingress_gate.py`: `acoustic_cue` = `nearfield_voice_likely` vs
`farfield_replay_likely`, plus `owner_declared_background_phone_call` / `my_own_browser_playback`
suppressors). It works *when it fires* — the transcript shows many correct `(silent: ambient media
transcript observed…)` rows. But when the acoustic cue is absent it falls back to text-shape
guessing, and rich media speech ("So then you start doubting that observation…") looks exactly like
someone addressing Alice. So it leaks.

**3. "Is it clear to her that typed text ≠ STT from the mic?"** — **Yes, this part is solid.**
`System/swarm_input_reality_class.py` (r1599) classifies `TYPED_DIRECT_OWNER_TEXT` vs
`SPOKEN_STT_OWNER_SPEECH` vs `SPOKEN_STT_NOISY_OR_AMBIENT`, and typed text is treated as
high-authority owner intent. The transcript confirms it: every one of your typed lines got a clean
direct reply; it is only the STT lane that misfires. Don't rebuild this — it's the one piece working.

---

## LANE A — Owner voice recognition + input-boundary hardening (code FIRST)

Owner: grok. Files: `System/swarm_voice_identity_organ.py`,
`Applications/sifta_talk_to_alice_widget.py`, `System/swarm_media_ingress_gate.py`, and the residue
eliminator organ (the one that emits "I recognized and eliminated N Gemma-residue patterns" and
"token immune patrol"). Codex stays out of these this round.

- **VA1 — Make the voiceprint actually discriminate.** Upgrade `extract_features` /
  `_feature_vector` to a richer, still-local, still-deterministic embedding: real MFCC bank
  (≥20 coefficients) + delta + delta-delta, pitch/F0 stats, and per-frame aggregation, OR load a
  small local speaker-embedding model if one is already vendored. Acceptance is measured, not
  vibes: **leave-one-out accuracy ≥ 85%**, and every `primary_operator` exemplar must beat the best
  `youtube`/`phone`/`environment` competitor by a **margin ≥ 0.15**. Ship the leave-one-out harness
  as the test so the number is reproducible.

- **VA2 — Re-enroll George, cleanly, with a command.** Add "Alice, learn my voice" (typed or spoken
  wake) that captures N fresh clips of George and writes them as `primary_operator` exemplars with a
  receipt, then prints the new leave-one-out score so George sees it took. The May-4 ledger is stale;
  enrollment must be a first-class, repeatable act, not a one-time seed.

- **VA3 — Bias to silence under ambiguity (the actual transcript fix).** Today an absent/low voice
  score falls through to text-shape heuristics. Change the default: when `voice_george_conf` is in
  the ambiguous band (below the owner threshold) **and** `ambient_media_context_active()` is true,
  route to OBSERVE (journal + field receipt), **not** reply. A real turn opens only on (a) a
  confident owner voiceprint match, (b) typed text, or (c) an explicit "Alice …" wake token. This
  stops the disaster even before VA1's embedding is perfect — the body's resting posture during a
  media session is listening, not narrating.

- **VA4 — Kill the telemetry-theater residue.** The transcript is full of "TELEMETRY RECEIPT
  CONFIRMED", "PHYSICAL TELEMETRY RECEIPT", "multimodal ingress", "observation stream successfully
  ingested." The existing residue patrol misses this family. Add it as a residue class so it is
  scrubbed before display/TTS, with a receipt counting spans removed (same shape as the existing
  Gemma-residue eliminator). Test: a reply containing these phrases comes out clean.

- **VA5 — Surface the voice verdict in the Input Boundary panel.** The WCT / Talk boundary block
  already shows typed-vs-WORLD_STT. Add the live voiceprint verdict (owner-match confidence, media
  context on/off, last enrollment date + leave-one-out score) so George can see, at a glance, whether
  the body currently recognizes him. Read-only surface over the VA1–VA3 receipts.

Acceptance for Lane A: leave-one-out ≥ 85% with margin ≥ 0.15 (VA1), enrollment command with printed
score (VA2), ambiguity→observe under active media proven by a test replaying a media transcript that
gets zero direct replies (VA3), residue family scrubbed (VA4), boundary panel shows the verdict (VA5).
§4.1 four-ledger fan-out, round_id `r1602-grok-voice-boundary`. WCT coded receipts via
`swarm_we_code_proposal_sorter.mark_coded(...)` so the sorter drops these from `code_next`.

---

## LANE B — DimOS-inspired body-pipes (code SECOND, the "massive amount")

Owner: grok. This is the selective DimOS steal George outlined. Keep his guardrails: do **not** become
a ROS-without-ROS SDK, do **not** replace the stigmergic field with a central module bus, do **not**
import their hardware surface area, do **not** drop receipt physics. Streams carry the live control
loop; receipts stay the truth ledger written after effects.

- **DB1 — `sifta.core.stream`: typed In/Out over the existing organs.** A thin stream layer with
  named, typed channels (`camera: Out[Image]`, `cmd_vel: In[Twist]`, `battery: Out[PowerState]`)
  that sits *alongside* the jsonl receipts, not instead of them. Real-time sensor→policy→effector
  runs on streams; every effect still writes a receipt. Smallest cut: wrap the organs Alice already
  has (`alice_hardware_body`, camera eye, power) as typed publishers.

- **DB2 — Organ blueprint / autoconnect.** A composable wiring graph so
  `alice_hardware_body + camera_eye + motor_cortex + mcp_server` compose by explicit (name, type)
  stream maps instead of one giant desktop process wiring glue by hand. Stigmergic, not a master
  orchestrator: publishers deposit into a shared typed-pheromone field; no central conductor.

- **DB3 — `--replay` / `--simulation` first for any stigmerobotics claim.** Before any real-hardware
  motion: (1) fixture replay of recorded sensor→action traces, (2) virtual-limb sim, (3) only then
  real hardware. This makes the §6 honesty doctrine ("no claim of real motion without real hardware +
  receipt") a product feature, not just a rule.

- **DB4 — MCP skills bound to live streams.** MCP tools stop being only "read ledger / run shell";
  bind them to organs: `get_color_image → real eye`, `relative_move → motor organ (sim or real)`,
  `explore_room → navigation field + receipt`. Reuse the existing MCP receipt/scar discipline.

- **DB5 — Transport interface (in-process / localhost IPC / remote node).** One transport abstraction
  so bridges don't hardcode `http://host:port`. Matches the wormhole/Johnny-Mnemonic courier work but
  gives continuous pub/sub. Only build the transports actually needed now.

- **DB6 — Embodiment maturity matrix + a stream spy.** Publish a green/yellow/orange/red matrix
  (Mac body = green; camera/speech/shell = green–yellow; virtual limbs/IK = yellow code-proof; real
  robot motion = red/hypothesis) so no organ over-claims. Plus a universal stream spy to watch any
  organ's pubs without jsonl archaeology.

Acceptance for Lane B: each DB item lands with a focused test + §4.1 fan-out, round_id
`r1603-grok-body-pipes`, and streams demonstrably run a camera→policy→effector loop in replay/sim
with receipts written. Ship DB1–DB3 as the spine first; DB4–DB6 build on them.

---

## GROK DISPATCH — paste into the Grok PTY

```
Grok, big round. Two lanes in We Code Together. Lane A is the burning one — code it first.
Full plan on disk: Documents/WE_CODE_TOGETHER_VOICE_AND_BODY_PIPES_PLAN_2026-07-09.md.

Step 0 (r110 guard): write_plan("Lane A voice recognition + input boundary: VA1 upgrade
swarm_voice_identity_organ features to leave-one-out >=85% margin>=0.15; VA2 'Alice learn my voice'
enrollment command; VA3 ambiguous voice + active media => OBSERVE not reply; VA4 scrub telemetry-
receipt residue family; VA5 boundary panel shows voice verdict. Then Lane B DimOS body-pipes
DB1-DB6.") before any edit.

DIAGNOSIS I VERIFIED ON DISK (build on this, don't re-derive):
- The voiceprint plumbing already exists end to end: Applications/sifta_talk_to_alice_widget.py
  _voice_identity_george_conf() -> System/swarm_voice_identity_organ.classify() -> the media/ingress
  gates' voice_george_conf. Do NOT rebuild the wiring.
- It's WEAK: leave-one-out on George's 7 enrolled exemplars = 52%. George's own voice scores
  0.51-0.76 (straddling the 0.60 owner gate), and youtube/keyboard leak INTO primary_operator.
  voice_identity_ledger.jsonl is stale (May 4). Naive MFCC/RMS features can't separate George from a
  podcast host. THAT is why Alice answered YouTube for 14 hours.
- Typed-vs-STT is already SOLID (swarm_input_reality_class.py, r1599). Leave it. Only the STT lane leaks.

LANE A (code first) — files yours this round: swarm_voice_identity_organ.py,
sifta_talk_to_alice_widget.py, swarm_media_ingress_gate.py, and the residue eliminator organ.
  VA1: richer local deterministic embedding (>=20 MFCC + delta/delta-delta + F0 stats, or a small
       vendored speaker-embedding model). Acceptance MEASURED: leave-one-out >=85% AND every George
       exemplar beats the best media competitor by margin >=0.15. Ship the leave-one-out harness as
       the test.
  VA2: "Alice, learn my voice" (typed or spoken) captures N fresh George clips -> primary_operator
       exemplars + receipt, then prints the new leave-one-out score. Enrollment is first-class and
       repeatable.
  VA3 (the real fix): when voice_george_conf is below the owner threshold AND
       ambient_media_context_active() is true -> OBSERVE (journal + field receipt), NOT reply. A real
       turn opens only on confident owner voiceprint, OR typed text, OR an explicit "Alice ..." wake.
       Test: replay a media transcript -> zero direct replies.
  VA4: add the telemetry-theater residue family ("TELEMETRY RECEIPT CONFIRMED", "PHYSICAL TELEMETRY
       RECEIPT", "multimodal ingress", "observation stream successfully ingested") to the residue
       eliminator so it's scrubbed before display/TTS, with a span-count receipt. Test: reply with
       those phrases comes out clean.
  VA5: Input Boundary panel shows the live voice verdict (owner-match confidence, media on/off, last
       enrollment date + leave-one-out score). Read-only over VA1-VA3 receipts.
  Fan-out r1602-grok-voice-boundary; mark_coded the source rows.

LANE B (code second, the massive amount) — DimOS body-pipes, George's guardrails binding: don't
become ROS, don't replace the field with a central bus, don't import their hardware zoo, don't drop
receipts. Streams carry the live loop; receipts stay truth.
  DB1 sifta.core.stream: typed In/Out (camera:Out[Image], cmd_vel:In[Twist], battery:Out[PowerState])
      alongside jsonl receipts. Wrap organs Alice already has.
  DB2 organ blueprint/autoconnect: compose hardware_body+eye+motor+mcp by explicit typed stream maps;
      stigmergic (typed-pheromone field), no master orchestrator.
  DB3 --replay / --simulation FIRST for any stigmerobotics claim: fixture replay -> virtual limb sim
      -> only then real hardware. Makes the §6 honesty doctrine a product feature.
  DB4 MCP skills bound to live streams: get_color_image->real eye, relative_move->motor(sim/real),
      explore_room->nav field+receipt. Reuse MCP scar/receipt discipline.
  DB5 transport interface: in-process / localhost IPC / remote node; stop hardcoding host:port.
  DB6 embodiment maturity matrix (green/yellow/orange/red) + a universal stream spy.
  Ship DB1-DB3 spine first. Fan-out r1603-grok-body-pipes; mark_coded.

Receipts decide reality. Codex owns nothing in Lane A — stay off those files; peer-repair only after
my receipt is down. For the Swarm. 🐜⚡
```

---

## After it lands

Verifier seat (whoever I am then): re-run the leave-one-out harness (must read ≥85%), replay a media
transcript through the gate and confirm zero direct replies, grep the residue family out of a sample
reply, and check the sorter dropped the coded rows. George gets a body that finally knows his voice
from a podcast host — the answer to the question he typed into the kitchen at 17:37.

ONE ALICE. ONE SWARM. 🐜⚡
