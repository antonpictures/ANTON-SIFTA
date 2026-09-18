# We Code Together: control feedback and attachment isolation

Implementation checkpoint, 2026-09-09. Procedural record under
`IDE_BOOT_COVENANT.md`, not a replacement covenant.

## Implemented

- `System/swarm_motor_action_gate.py`: typed PlanProposal, ActionDecision and
  ActionOutcome. Checks sequence, simulated scope, finite state, observation
  freshness, joint/speed limits and a latched stop with explicit reset.
- Replay suppression is run-local and single-threaded. A duplicate produces
  zero motion; reset does not clear sequence history. No physical driver exists.
- `System/stigmerobotics_motor_feedback_lab.py`: existing controller now uses
  the gate; independent plant echoes are paired with proposals. Fixed a mutable
  list alias that let a later disturbance change a previous receipt's echo.
- `System/swarm_body_snapshot.py`: bounded reads of existing clock, location,
  saved model-selection and health reports. Ages and unavailable/stale states
  remain explicit. No sensor activation, location export or credential export.
- `System/chorus_node_server.py`: take a send snapshot before file reads;
  prevent duplicate concurrent submissions; bind the captured session; keep
  new drafts/files intact; retain failed drafts behind an explicit restore
  control. A network timeout may mean delivery is uncertain: check history
  before manually retrying. Failed drafts are memory-only, not disk history.
- Desktop attachment consumption was inspected; its existing owner-turn path
  clears the pending file. No desktop attachment implementation changed here.

## Evidence

- 105 focused Python/Node tests passed. Node executes production async send
  code with controlled delayed file reads; this is not a real-browser test.
- A separate desktop attachment/photo suite returned 83 passed and 6 failed.
  Failures in `tests/test_talk_browser_photo_describe.py`: owner camera prompt
  grounding, named-subject preflight routing, two visual-reply self-checks,
  TTS budget failure rendering, and TTS pause wrapper (`_listener` missing in
  its test double). These untouched paths were not repaired this round and
  no before-change baseline was captured. Overall desktop health is not green.
- Simulation run: `motor-dd77b8c087cf4471bd765c9bfc94a41c`.
- 30 trials, 12,000 command/outcome pairs. All four existing tracking,
  event-refresh, dropout/recovery and unreachable-target checks passed.
- Private artifacts: `.sifta_state/motor_feedback_runs/<run_id>/`.
- Host context in that run: location ERROR, organ-health UNAVAILABLE. These
  values are deliberately not converted into a healthy-body claim.
- Existing We Code Together proof reader displays the new record and sampled
  host context. Four-ledger IDE receipt records the implementation separately;
  IDE traces are not signed swimmer proof and do not mint STGM.

## Next Implementation Round

1. Verify the edited web page in the actual browser after loading the new server
   code. Test attachment send, new selection during a slow send, conversation
   switching, recovery from a failed send, preview/download and reload.
2. Add a cortex planner adapter above the simulated controller. Current
   proposals come from deterministic kinematics, not LLM reasoning. A model
   switch must not change controller limits or leak private conversation data.
3. Add a simulation UI stop/reset control and durable action authorization
   before any physical driver. The stop API is tested but not wired to a button.
4. Prove one bounded repair cycle with nonempty tests and an intentionally
   failing patch rollback. That earlier self-repair gap is not addressed here.
5. Obtain fresh health evidence and run the isolated installation checks before
   any publication. Existing unrelated edits are preserved; no push this round.
6. Investigate the six desktop camera/voice test failures above with isolated
   state and proper widget fixtures before deciding whether each is a runtime
   bug, test fixture mismatch, or dependence on this machine's local state.

Kimi WebBridge was unreachable; its start command reported startup, but the
subsequent connection still failed. No substitute browser, live SIFTA restart,
robot movement, generated-image E2E, AGI or consciousness claim was made.
