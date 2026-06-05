---
name: claude_swimmer_arm
description: >
  Use when Alice needs the Claude swimmer arm alias or local Claude Code
  substrate brief, with execution kept as Alice-owned swimmers and receipts.
swimmer_type: CLAUDE_ARM_SWIMMER
action_type: code
affect_lanes: [SEEKING, CARE]
stgm_mint: 4.0
pouw_label: CLAUDE_SWIMMER_ARM
version: 2026-06-05
---

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
