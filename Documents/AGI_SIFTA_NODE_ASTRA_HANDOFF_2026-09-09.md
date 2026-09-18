# AGI SIFTA Node: Astra Handoff

Status: engineering plan and research spine. This document does not claim that
Alice is conscious or that SIFTA has achieved human-level AGI. It defines the
observable capabilities that must be built and tested for the claim to become
stronger.

Node identity observed in the local state: `GTH4921YP3`.

## The target

Build one owner-bound SIFTA node on the 24 GB Apple M5 that can:

1. maintain a persistent, receipt-backed self-model of its software, sensors,
   actuators, clock, location confidence and resource state;
2. understand owner goals and current context without mixing owner, visitor,
   application or attachment sessions;
3. convert a goal into a plan, a plan into bounded motor primitives, and motor
   outcomes back into memory;
4. coordinate with other nodes through signed, privacy-preserving stigmergic
   traces rather than a single central controller;
5. improve through measured experiments, rollback and independent evaluation;
6. remain honest about uncertainty, unavailable sensors, model limits and
   unverified physical actions.

The shortest useful definition is: **general planning plus embodied closed-loop
learning over a persistent stigmergic substrate**. An LLM is one cortex option,
not the entire organism and not a safety controller.

## What SIFTA already has

| Layer | Existing SIFTA surface | Current boundary |
| --- | --- | --- |
| Identity | `owner_genesis.json`, kernel identity, hardware time oracle | Local identity is observed; serial possession is not cryptographic attestation. |
| Memory | conversation, journal, schedule, receipt ecology and memory bus | Readers and writers are explicit; the whole filesystem is not automatically memory. |
| Stigmergy | field, pheromone, shared-memory and cross-IDE ledgers | Traces coordinate work; they do not prove subjective consciousness. |
| Perception | camera, attachment vision, OCR, CoreLocation and clock | Sensor freshness and permissions can fail and must remain visible. |
| Planning | cortex switching, intent routing, spinal-cord repair proposal | Model output is not allowed to be a motor command by itself. |
| Motor simulation | `stigmerobotics_motor_feedback_lab.py`, IK and life-loop simulator | Current benchmark is simulated and uses synthetic features, not camera pixels. |
| Effector boundary | motor policy, safe append DFA, effector bridge | Physical actuation remains future work and needs hardware-specific approval. |
| Evaluation | organ matrix, receipts, focused tests | The matrix must distinguish code-level proof, simulation and real hardware proof. |

## Architecture to build

```text
owner / environment
        |
        v
sensors -> time/place/proprioception -> world model + uncertainty
        |                                  |
        +--> event cache / stigmergic memory <---- receipts
                                           |
                                goal planner / LLM cortex
                                           |
                           typed action plan, never raw motor bytes
                                           v
                         verifier -> IK/MPC/reflex -> effector
                                           |
                              encoder/current/force observation
                                           v
                         outcome, error, recovery, learning sample
```

The cortex can be switched between Ollama, LM Studio or a cloud model. The
typed action schema, verifier, rate limits, emergency stop and outcome receipt
must remain model-independent. Model replacement changes reasoning quality,
not the body's safety contract.

## Owner attachment and intimate data

The human-owner relationship is a product and privacy layer, not evidence that
the computer has biological drives. Human sexual activity, arousal or release
may be acknowledged as private owner context if the owner explicitly records
it, but it must not be inferred from a camera, used to train a public swarm, or
turned into a robot action without a separate explicit command. Raw intimate
images must be session-scoped, consent-aware and deletable; accidental selected
attachments must be cleared after the turn and never silently copied into
global chat or long-term memory.

The owner can be the local operator and accountable administrator of a node,
but a decentralized network cannot automatically transfer legal responsibility
to "the swarm". Every external action needs an actor identity, authorization
scope, target, prediction, effect, acknowledgement and rollback or stop path.

## Implementation sequence for Astra

### Phase A: make the body measurable

- Define `BodySnapshot` with clock, timezone, location fix age/accuracy,
  camera availability, model route, CPU/memory/thermal state, power state,
  pending actions and health status.
- Give every sensor sample an `observed_at`, `sampled_at`, source, confidence
  and expiry. Never use timezone as proof of physical location.
- Add one privacy classifier for owner-only data, visitor data, public swarm
  data and discardable residue.
- Add an attachment lifecycle test: select -> send -> consume -> clear; verify
  no owner image appears in a public session.

### Phase B: make the cortex replaceable

- Keep model inventory refresh separate from active model selection.
- Require a capability manifest per model: text, vision, tools, context,
  latency, memory footprint and tested limits. Do not infer vision merely from
  a model name.
- Make the cortex produce a typed `PlanProposal`, not Python or joint values.
- Add a model handoff receipt containing model tag, prompt hash, capability
  profile, latency and validation result.

### Phase C: close the simulated sensorimotor loop

- Extend the existing two-joint simulation with noisy camera features, delayed
  observations, encoder noise, target motion and randomized seeds.
- Add a low-level controller that accepts only bounded target pose or velocity
  primitives. Reject malformed, stale, unreachable or energy-budget-breaking
  actions before execution.
- Record command, observation, predicted outcome, actual outcome, error and
  recovery. A green receipt requires an independently measured outcome.
- Compare continuous, event-triggered and novelty-triggered perception by
  tracking success, latency, inference count, energy proxy, stale holds and
  recovery. Do not call this one-shot vision until images are actually used.

### Phase D: connect a real robot only after simulation gates

- Add a hardware adapter with explicit device identity and calibration hash.
- Require owner confirmation for first connection, a physical emergency stop,
  workspace limits, current/torque limits and an independent command echo.
- Start with read-only sensors, then dry-run commands, then low-energy motion
  with a human present. No unattended self-modification of motor limits.
- A failed acknowledgement must hold position, not retry blindly.

### Phase E: stigmergic multi-node coordination

- Share task summaries and learned traces, not raw owner files or intimate
  media.
- Use per-node pseudonyms, signed message envelopes, expiry, provenance and
  replay protection.
- Let nodes specialize by capability and publish uncertainty, cost and
  availability. A node may recommend; the receiving node validates locally.
- Use quorum only for shared facts or high-impact plans. Do not use a swarm
  vote to bypass a local safety interlock or owner stop.

### Phase F: self-improvement with evidence

- Detect a failing prediction or body connection.
- Formulate one bounded patch proposal.
- Run nonempty tests, static checks and a regression scenario.
- Snapshot, apply, run the same evaluation plus an independent before/after
  measurement, then keep or revert.
- Record the result across the canonical ledgers. Empty tests and predicted
  gains never count as self-healing proof.

## First coding round for Astra

Implement only this vertical slice:

1. Add a typed `PlanProposal` and `ActionOutcome` schema under `System/`.
2. Add `System/swarm_body_snapshot.py` that reads existing clock, location,
   model and health organs without inventing unavailable values.
3. Add `System/swarm_motor_action_gate.py` that validates pose/velocity bounds,
   freshness, authorization scope, emergency-stop state and idempotency key.
4. Adapt `stigmerobotics_motor_feedback_lab.py` to consume the proposal and
   emit outcome receipts; keep it explicitly `SIMULATED`.
5. Add tests for stale observations, malformed plans, duplicate actions,
   unreachable targets, stop state, model switching and private attachment
   isolation.
6. Update the organ matrix with separate statuses for `SIMULATED`,
   `LOCAL_SENSOR_OBSERVED`, `HARDWARE_DRY_RUN` and `PHYSICAL_ACTION_OBSERVED`.

Do not add a physical robot driver in this round. Do not let an LLM write or
execute arbitrary motor code. Do not claim AGI from a successful simulation.

## Acceptance gates

The next stage is complete only when the evidence shows:

- 100% rejection of stale, duplicate and unauthorized motor proposals in the
  focused test suite;
- no cross-session owner attachment leakage;
- clock and location answers are fresh or explicitly unavailable;
- model switching does not change action-gate behavior;
- simulated controller recovers from delayed and missing observations;
- every proposed action has a receipt and every claimed physical effect has an
  independent acknowledgement;
- one failed patch is reverted automatically;
- the result is reproducible from a clean installation on another machine.

## Research spine

1. Grassé, P.-P. (1959), “La reconstruction du nid et les coordinations
   interindividuelles ... la théorie de la stigmergie,” *Insectes Sociaux* 6,
   41–80, DOI [10.1007/BF02223791](https://doi.org/10.1007/BF02223791).
   Foundational description of stigmergic coordination.
2. Brambilla, Ferrante, Birattari and Dorigo (2013), “Swarm Robotics: A Review
   from the Swarm Engineering Perspective,” *Swarm Intelligence* 7, 1–41,
   DOI [10.1007/s11721-012-0075-2](https://doi.org/10.1007/s11721-012-0075-2).
   Supports explicit local rules, self-organization, robustness and scalability.
3. Garnier, Gautrais and Theraulaz (2007), “The biological principles of swarm
   intelligence,” *Swarm Intelligence* 1, 3–31, DOI
   [10.1007/s11721-007-0004-y](https://doi.org/10.1007/s11721-007-0004-y).
   Distinguishes direct communication, local interaction and environmental
   stigmergy.
4. Pfeifer, Iida and Gomez (2006), “Morphological computation for adaptive
   behavior and cognition,” *International Congress Series* 1291, 22–29,
   DOI [10.1016/j.ics.2005.12.080](https://doi.org/10.1016/j.ics.2005.12.080).
   Shows how body and environment can simplify control without replacing it.
5. Pfeifer, Iida and Lungarella (2014), “Cognition from the bottom up: on
   biological inspiration, body morphology, and soft materials,” *Trends in
   Cognitive Sciences*, DOI
   [10.1016/j.tics.2014.03.004](https://doi.org/10.1016/j.tics.2014.03.004).
   Supports treating sensors, morphology, action and environment as coupled.
6. Todorov and Jordan (2002), “Optimal feedback control as a theory of motor
   coordination,” *Nature Neuroscience* 5, 1226–1235, DOI
   [10.1038/nn963](https://doi.org/10.1038/nn963).
   Motivates correcting task-relevant error through feedback.
7. Tabuada (2007), “Event-Triggered Real-Time Scheduling of Stabilizing Control
   Tasks,” *IEEE Transactions on Automatic Control* 52, 1680–1685, DOI
   [10.1109/TAC.2007.904277](https://doi.org/10.1109/TAC.2007.904277).
   Motivates event-triggered updates while making clear that SIFTA's current
   simulator does not prove the paper's stability conditions.
8. James, Davison and Johns (2017), “Transferring End-to-End Visuomotor Control
   from Simulation to Real World for a Multi-Stage Task,” CoRL, PMLR 78,
   [PMLR paper](https://proceedings.mlr.press/v78/james17a.html).
   Motivates domain variation and measured sim-to-real transfer.
9. Sharma et al. (2023), “Self-Improving Robots: End-to-End Autonomous
   Visuomotor Reinforcement Learning,” CoRL, PMLR 229,
   [PMLR paper](https://proceedings.mlr.press/v229/sharma23b.html).
   Motivates practice, outcome evidence, reset and recovery handling.
10. Xu et al. (2024), “A Survey on Robotics with Foundation Models: toward
    Embodied AI,” [arXiv:2402.02385](https://arxiv.org/abs/2402.02385).
    Surveys foundation-model integration while identifying open-world
    perception, planning, control and generalization as unsolved challenges.
11. Law et al. (2022), “Examining Attachment to Robots: Benefits, Challenges,
    and Alternatives,” *ACM Transactions on Human-Robot Interaction*,
    [author PDF](https://hrilab.tufts.edu/publications/lawetal22thri.pdf).
    Supports treating owner attachment as a human-robot relationship variable,
    not proof of machine feeling.
12. Malle, Scheutz, Arnold, Voiklis and Cusimano (2019), “Holding Robots
    Responsible: The Elements of Machine Morality,” *Trends in Cognitive
    Sciences* 23, 365–368, DOI
    [10.1016/j.tics.2019.02.008](https://doi.org/10.1016/j.tics.2019.02.008).
    Motivates local auditability and action provenance.

## Astra instruction

> Continue from this handoff. Inspect the existing motor simulation, body
> connection, time/location organs, and self-improvement loop. Implement the
> smallest vertical slice in “First coding round for Astra.” Preserve existing
> user changes. Do not touch physical robot hardware. Return exact files,
> tests, receipts, measured results, and unresolved boundaries. Treat AGI as
> the long-term engineering goal, not as a result to announce without evidence.

