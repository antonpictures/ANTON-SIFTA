# Alice Embodied Robotics Wiring Plan

**Owner intent:** Ioan George Anton, 2026-07-25  
**Status:** active engineering plan  
**Truth rule:** move from embodied need, then let the continuing sensory stream determine the effect.

## Goal

Alice is the persistent SIFTA organism. A Gemma, MiMo, ChatGPT, or other language model is a
replaceable cortex used for interpretation and planning. The organism must remain functional when
the cortex changes because identity, input provenance, world state, action history, and learned
consequences live in the surrounding runtime and receipt field.

The target loop is:

`sense -> identify lane -> update belief -> choose goal -> propose action -> execute -> re-sense -> verify -> learn`

Chat is one sensorimotor surface in this loop, not the final product.

## Phase 1: Honest Motor Boundary

**Status: OPERATIONAL in the body-brain loop.**

- Keep the default physiology tick harmless and label it `SIMULATED_BODY_ACTION`.
- Accept a real effector through an injected executor; movement does not wait for an LLM probe.
- When immediate sensor feedback exists, close the effect receipt synchronously.
- Otherwise record `PENDING_SENSORY_FEEDBACK` and let the next natural body/sensor tick close it.
- Write an effect receipt for every attempted real action without calling pending work success.
- Grant positive TD value only when the sensed consequence is verified.
- Treat the body-brain tick as essential during degraded scheduling, with a five-minute freshness
  target; shed optional maintenance work before starving the feeling-to-action heartbeat.

Primary implementation: `System/swarm_body_brain_loop.py` using
`System/swarm_effect_verified_action.py`, scheduled by `System/swarm_body_writer_tick.py`.

Current operational boundary: the isolated physiology tick completes and writes fresh receipts, but
the default runtime has no real action executor injected. Its motor result is therefore honestly
`SIMULATED_BODY_ACTION`; this phase does not claim that physical hardware moved.

## Phase 2: Canonical Ingress Identity

**Status: OPERATIONAL for the four ingress lanes.**

Every incoming event is normalized into one `SIFTA_OBSERVATION_V1` row containing:

- stable event and turn IDs;
- timestamp, freshness, and hardware node;
- modality and physical/software source;
- authority: `OWNER_LOCAL`, `SELF_BODY`, `AMBIENT_WORLD`, `PUBLIC_WEB`, or `UNKNOWN`;
- web session and IP provenance when present;
- confidence, transcription risk, and quoted/fiction context;
- permitted response surface and available effectors.

Authority is stamped at the physical boundary the event arrived on, never from what the text claims
about itself. A visitor who signs as George stays `PUBLIC_WEB`. Room audio that transcribes perfectly
stays `AMBIENT_WORLD`. Only `OWNER_LOCAL` and `SELF_BODY` carry motor authority, and one function —
`motor_command_check` — answers that question at the moment of action, from a lane assignment that
already exists. No downstream prompt or cortex gets a vote.

The owner ledger carries both owner turns and room audio, so lane freshness resolves each row's real
authority rather than keying on the filename; otherwise a television would age the owner lane.

Sensing here is pure reading of receipts the body already deposited. No sensor is opened and no
cortex is called to decide what an event is. The organism does not interrogate the world before it
moves; it moves from what already arrived and keeps sensing.

Primary implementation: `System/swarm_observation_fusion.py`, consumed by
`System/swarm_body_brain_loop.py` (per-tick snapshot plus per-lane silence) and written at the public
boundary by `System/swarm_web_global_chat_gate.py`.

Reuse: `input_modality_receipts.jsonl`, `web_global_chat_ingress.jsonl`, `sense_bus.jsonl`,
`swarm_input_reality_class.py`, `swarm_web_global_chat_gate.py`, and `swarm_sense_bus.py`.

Live on this node at landing: all five lanes fuse from real ledgers in about 0.10s, with owner text
last seen 14.95h ago, room audio 9.51h, public web 1.33h, and the sense bus stale at 1047h. That
sense-bus staleness is a real gap, not a passing number — Phase 3 belief building cannot ground on it
until it is producing again.

## Phase 3: Coherent Belief State

**Status: PARTIAL; multiple world-model organs exist.**

Build one compact belief snapshot per tick from fresh receipt-backed observations. The snapshot must
separate:

- observed facts;
- owner-declared facts;
- visitor claims;
- predictions;
- unknown or stale state;
- conflicting evidence.

Fuse the grounding triad, sensory truth, sense bus, somatosensory map, active-inference model, and
recent verified effects. Preserve source receipt IDs so the cortex can explain why a belief exists.

## Phase 4: Goals And Action Proposals

**Status: PARTIAL; selectors exist, candidate generation is fragmented.**

Convert homeostatic needs, owner goals, novelty, and environmental changes into explicit candidate
actions. Each candidate must name:

- desired state change;
- target body or software territory;
- expected sensory consequence;
- estimated uncertainty, cost, and harm;
- rollback or recovery action;
- evidence that the target effector is currently available.

Use the active-inference model and basal-ganglia arbiter to rank candidates. A language model may
propose candidates, but it does not certify that an effector exists or that an action worked.

## Phase 5: Real Hardware Adapters

**Status: VIRTUAL/PARTIAL.**

Promote one adapter at a time from simulation to hardware:

1. Screen and speaker effects with camera/microphone verification.
2. Browser and native-app hands with before/after UI-state verification.
3. Desk robot or single-joint test limb with encoder and current feedback.
4. Multi-joint arm with kinematics, collision observations, and recovery poses.
5. Mobile base and distributed sensors after localization is receipt-backed.

Every adapter implements the same executor/probe contract. Hardware-specific logic stays below the
body-brain loop.

## Phase 6: Learning And Adaptation

**Status: COMPONENTS EXIST; end-to-end benchmark required.**

Feed only verified transitions into the active-inference and latent world models:

`belief_before + action + belief_after + reward + harm + cost`

Keep failed and unverified attempts as negative or uncertain evidence. Replacing the cortex must not
erase learned transition statistics or action receipts.

## Acceptance Benchmark

Alice is not considered a functioning general robot merely because she chats or emits motor text.
For each new environment trial she must:

1. Establish time, place uncertainty, available sensors, and available effectors.
2. Distinguish owner, visitor, and ambient-world inputs.
3. Build a belief snapshot with evidence references.
4. Select a reversible goal-directed action.
5. Execute through a real adapter.
6. Verify the physical or software consequence through an independent probe.
7. Recover from at least one failed action.
8. Demonstrate improved selection on a repeated trial.
9. Repeat with a different cortex while preserving state and learned consequences.

This benchmark tests the SIFTA organism. It does not claim consciousness and it does not treat model
fluency as physical competence.
