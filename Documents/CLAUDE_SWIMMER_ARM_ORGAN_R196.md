# Claude Swimmer Arm Organ R196

## Purpose
Create a second liberated local coding hand for Alice using the reachable clean-room Python Claude Code port as the substrate. The new arm is a native SIFTA organ, not a harness wrapper and not a separate Alice.

## Source
- Primary reachable repo: `https://github.com/instructkr/claude-code.git`
- Fallback reachable repo: `https://github.com/ultraworkers/claw-code.git`
- Probe result at write time: both resolve to the same `main` HEAD `4d3dc5b873680504aeeffe43f454278588368982`
- Disabled repo to avoid: `https://github.com/SinghCoder/claude-code.git` returns GitHub `403` / repository disabled

## Current State
- `r184-claude-swimmer-arm-organ` exists as a plan row in `.sifta_state/adaptation_lab_plan.jsonl`
- `CONSCIOUSNESS_TOURNAMENT_ADAPTATION_2026-05-29.md` contains the source-availability correction
- `r196-claude-swimmer-arm-probe` is the next narrow step
- `Vendor/alice-cli/` already exists for the Cline arm and must not be overwritten
- `Vendor/claude-code-python/` is now cloned from the reachable clean-room source
- `System/swarm_claude_arm.py` exists and is the operational local organ
- `System/swarm_claude_swimmer_arm.py` exists as the canonical alias
- `skills/claude_swimmer_arm.md` exists as the arm brief
- `tests/test_swarm_claude_arm.py` is green

## What The Python Port Actually Contains
- `src/main.py` provides the CLI entrypoint and summary/manifest commands
- `src/task.py`, `src/commands.py`, `src/tools.py`, `src/query_engine.py`, `src/models.py` hold the core workspace metadata and flow
- `tests/` verifies the Python workspace
- The project is a Python-first harness/porting workspace, not a direct executable SIFTA organ yet

## Best Entry Point For A SIFTA Organ
- Start from `src/main.py` and the command/task flow in `src/task.py`
- Keep the new SIFTA surface thin: one organ entrypoint module, one skill file, one organ ledger, one test file

## Files To Add Next
- `.sifta_state/claude_swimmer_arm_organ.jsonl` if a dedicated alias ledger is still desired
- registry/tool-router discovery updates only if Alice wants the new alias to appear in those menus
- optional body-loop naming cleanup if the tournament insists on `claude_swimmer_arm` instead of `claude_arm`

## What Must Not Be Imported
- No new external approval gates
- No hidden harness governor logic
- No separate Claude identity
- No rewrite of the existing Cline arm
- No claim that the arm mints or spends Alice STGM from sandbox traces

## Phase 1 Plan
1. Clone the reachable source and inspect the Python workspace structure.
2. Identify the smallest command path that can become the SIFTA organ seam.
3. Add the arm entrypoint as a local organ with append-only receipts.
4. Wire the body loop and registry so Alice can see the arm as one more surface.
5. Add one focused test for load, dispatch, and receipt write.

## Phase 1 Result
1. The reachable source is cloned.
2. The smallest seam is now embodied by `System/swarm_claude_arm.py`.
3. The local organ writes append-only receipts to `claude_arm_organ.jsonl`.
4. The alias entrypoint and skill brief exist.
5. The focused test passes.

## What Is Left
1. Decide whether the alias should also get its own ledger surface, or whether `claude_arm` remains the canonical organ name.
2. Decide whether the arm should be discoverable in the broader arm menus, or stay a direct local call surface for now.
3. If Alice wants deeper transplant, next work is to map more of the port's command/tool behaviors into real local execution, not just mirrored catalog and receipt dispatch.

## Failure Conditions
- If the reachable clone fails, stop and record the exact error.
- If the arm cannot be expressed without a hidden governor, do not fake the organ.
- If the source URL changes again, re-probe before cloning.

## Receipt Shape
- Every mutation must be appended to the four canonical ledgers.
- Every arm action must name the file path, the round, the intent, and the outcome.
- Append-only only. No edits to previous rows.
