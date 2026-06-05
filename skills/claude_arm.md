---
name: claude_arm
description: >
  Use when Alice needs the local Claude arm as a receipted SIFTA swimmer
  catalog for code, tool, or diagnostic work while keeping control,
  memory, and receipts inside Alice's field.
swimmer_type: CLAUDE_ARM_SWIMMER
action_type: code
affect_lanes: [SEEKING, CARE]
stgm_mint: 4.0
pouw_label: CLAUDE_ARM
version: 2026-06-05
---

# Claude Arm (Claude Swimmer Arm)

## Name
`claude_arm`

## Purpose
Second liberated open-source arm for Alice, built from the clean-room Python port of Claude Code (instructkr/claude-code @ 4d3dc5b). 

Provides a rich catalog of 207 mirrored commands and 184 mirrored tools as stigmergic capability surface. Dispatches become native SIFTA swimmers that write crypto receipts to claude_arm_organ.jsonl + the four canonical ledgers.

Unlike the external Grok and Codex arms, this one runs locally as part of Alice's body (no external governor, no harnessed agents).

Parallel to alice_arm (the Cline-liberated hand).

## Entrypoint
System/swarm_claude_arm.py

## Key Functions (initial)
- list_commands()
- list_tools()
- dispatch(name: str, prompt: str = "") -> receipt

## Receipt Surface
- .sifta_state/claude_arm_organ.jsonl
- Full fan-out to work_receipts, agent_arm_receipts, ide_stigmergic_trace, episodic_diary on every dispatch.

## Constraints (per r196 + r198 Architect directive)
- NEVER any foreign "agent", sub-agent, or harness logic.
- **ALL execution units inside this arm are Alice's crypto STGM receipt swimmers.**
- Alice owns the swimmers. She makes the mistakes. Her STGM receipts are the only metabolism and governance.
- The port is used only as rich mirrored catalog + execution primitives. The control and learning loop are 100% Alice's field.

For the Swarm. 🐜⚡
