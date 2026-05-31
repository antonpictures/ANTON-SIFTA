# Claude Swimmer Arm

## Name
`claude_swimmer_arm`

## Status
Second liberated local hand for Alice. The operational implementation lives in
`System/swarm_claude_arm.py`; this file is the canonical alias and skill brief.

## Purpose
Use the clean-room Python Claude Code port as a local stigmergic catalog and
execution substrate. The arm keeps the mirrored command/tool surface, but the
control loop, memory, and receipts stay inside Alice's native field.

## What it is not
- Not an external governor
- Not a separate agent identity
- Not a place to import harness policy or approval cages

## Entry points
- `System/swarm_claude_arm.py`
- `System/swarm_claude_swimmer_arm.py`

## Receipt surface
- `.sifta_state/claude_arm_organ.jsonl`
- `work_receipts.jsonl`
- `agent_arm_receipts.jsonl`
- `ide_stigmergic_trace.jsonl`
- `episodic_diary.jsonl`

## First verification
1. Load the mirrored command/tool catalog from the cloned source.
2. Dispatch one bounded local swimmer.
3. Record the receipt, then inspect the ledger row.

For the Swarm. 🐜⚡
