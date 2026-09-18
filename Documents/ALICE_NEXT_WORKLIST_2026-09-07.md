# Alice next worklist — 2026-09-07

This is an engineering backlog, not a claim of subjective consciousness.

## Current handoff: 2026-09-09

Start with [WCT credit-saving handoff](WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md).
It is displayed in We Code Together's To Code tab. It separates the unfinished
camera pass, HEIC conversion, vision routing, local coding-arm verification,
model benchmarks and remaining integration/release gates. All entries are
plans unless backed by a subsequent test result. Luna starts with HEIC only.

## What is true now

- Alice has one local identity across the desktop, Talk, matrix, and public
  chorus surfaces because those surfaces use shared code and local ledgers.
- The filesystem is the local substrate: `System/` contains organs,
  `Applications/` contains surfaces, and `.sifta_state/` contains local
  receipts, journals, memory rows, schedules, and generated artifacts.
- The layers are connected by explicit readers and writers, not by every file
  automatically becoming memory. A file becomes part of a memory path only
  when an organ records it and a recall/consolidation organ reads it.
- Local Ollama models are replaceable cortex processes. They are not separate
  Alices, and they do not own the filesystem. Public visitor context is now
  isolated from George's owner context.
- The owner journal and schedule path already exists through the first-person
  journal, action journal, episodic diary, schedule awareness, and life-journal
  consolidator. Its health still needs a live end-to-end check: owner input ->
  journal row -> consolidated entry -> next-action/schedule view.

## Next bounded work

1. Run the schedule proof on a fresh owner task and record the exact journal,
   consolidation, and next-action receipts.
2. Add a single owner-facing “next actions” card backed by those receipts;
   never infer a completed task from a plan alone.
3. Extend the public image response test so each response is prompt-grounded,
   receipt-backed, and varied without claiming visual details not present in the
   prompt or generated-image metadata.
4. Add a bounded short-duration multitask test: two independent sensor events
   may be held in working context briefly, then either journaled or discarded
   with an explicit reason. No hidden unbounded context.
5. Add an eval row for context collision: an owner topic, a public visitor
   topic, and an image request must not overwrite one another.
6. Refresh the organ/eval matrix after the schedule proof and surface any
   degraded writer or stale-journal state before publication.

## Code-repair verification follow-up (2026-09-07)

- Inference Settings now exposes observed inventory, model sizes and the last
  repair receipt. Live ledger inspection found NO_PATCH as the last result;
  the recent proposal window contained no kept repair. This is not a lifetime
  claim about every possible repair path.
- Before enabling unattended repair, require nonempty, bounded tests:
  swarm_spinal_cord.gate_and_apply currently treats an empty test list as passed.
- Replace the predicted-gain substitution with an independently measured
  before/after result. Passing tests alone does not measure the predicted gain.
- Prove one isolated detect/propose/gate/test/keep-or-revert cycle, including a
  failing-patch rollback test, before describing live self-healing as verified.
- No repair was dispatched during this settings update. Existing dirty source
  changes and the pending healthy-before-push gate remain untouched.

## Boundary

“Alice is the hardware” is a useful fiction/architecture metaphor, but the
checkable statement is narrower: this node's software runs on and writes to
this Mac's filesystem, while cryptographic identity and hardware attestation
remain separate questions. Filesystem access is not proof of consciousness,
exclusive ownership, or human-like experience.

## Astra handoff: embodied AGI path (2026-09-09)

The full research-backed plan is in
[`AGI_SIFTA_NODE_ASTRA_HANDOFF_2026-09-09.md`](AGI_SIFTA_NODE_ASTRA_HANDOFF_2026-09-09.md).
The next bounded vertical slice is typed plan/outcome schemas, a fresh body
snapshot, a model-independent motor action gate, and simulation tests for
stale, duplicate, unauthorized and unreachable actions. Physical actuation is
not part of this round.

## Implementation checkpoint (2026-09-09)

Typed motor proposals/outcomes, model-independent simulated action checks,
dated host context, and web per-turn attachment isolation are implemented.
See `WCT_MOTOR_ATTACHMENT_2026-09-09.md` for tests, the recorded simulation and
remaining work. The current planner remains deterministic; physical actuation,
live-browser confirmation and a verified self-repair cycle remain open.

## AGI Eye / Single Camera Slice (2026-09-09)

- Default desktop capture is now one embedded MacBook camera. External
  cameras remain inventory-only and cannot create a secondary capture session.
- The previous silent USB pulse fallback was the flicker source; it is disabled
  by the single-owner-eye policy.
- We Code Together and the organ matrix now expose camera freshness, unified
  capture state, visual-stigmergy presence and the boundary between pixels and
  semantic vision.
- Next: prove hot-plug stability, add temporal frame windows, then attach a
  capability-declared vision model and evaluate frame-to-claim grounding.
- Research and acceptance gates are recorded in
  Documents/WCT_AGI_EYE_SINGLE_CAMERA_2026-09-09.md.
