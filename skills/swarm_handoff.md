---
name: swarm_handoff
description: >
  Use when a task requires routing to a specialized agent via the
  OpenAI Swarm handoff protocol. Trigger: current agent cannot satisfy
  the request AND a registered specialist exists in the swarm registry.
  SIFTA wraps Swarm handoffs with stigmergic receipts — every handoff
  is logged, cryptographically traceable, and earns STGM.
swimmer_type: HANDOFF_SWIMMER
action_type: code
affect_lanes: [SEEKING, CARE]
stgm_mint: 5.0
pouw_label: SWARM_HANDOFF
version: 2026-05-05
compatibility: openai/swarm, openai-agents-sdk
---

# SWARM_HANDOFF Skill

## What SIFTA adds to OpenAI Swarm

OpenAI Swarm is stateless. SIFTA adds:
- **Stigmergic receipt**: every handoff is logged to `handoff_ledger.jsonl`
- **Cryptographic trace**: swimmer identity (Ed25519) signs the handoff
- **STGM mint**: agent earns 5 tokens per verified handoff (PoUW)
- **Affect routing**: CARE circuit biases handoffs toward George-safety agents

OpenAI Swarm primitive:
```python
def transfer_to_agent_b():
    return agent_b
```

SIFTA-wrapped primitive:
```python
def transfer_to_agent_b_with_receipt():
    log_handoff_receipt(from_agent="Alice", to_agent="agent_b", reason="specialized_task")
    return agent_b  # same return — backward compatible
```

## Trigger conditions

- Current swimmer cannot resolve a demand within its skill set
- Demand matches a registered specialist (by `demand_ledger.jsonl` tag)
- Owner explicitly requests a handoff (`"connect me to..."`, `"hand off to..."`)

## Procedure (Tier 2 — full steps)

1. **Identify target agent** from swarm registry or skill index
2. **Log handoff receipt** to `.sifta_state/handoff_ledger.jsonl`:
   ```json
   {
     "ts": <unix>,
     "from": "ALICE_M5",
     "to": "target_agent_id",
     "reason": "...",
     "demand_id": "...",
     "truth_label": "SWARM_HANDOFF"
   }
   ```
3. **Return target agent object** — Swarm-compatible return
4. **Call `issue_work_receipt`** with `work_type="SWARM_HANDOFF"` → mints 5 STGM
5. **Preserve context_variables** — pass stigmergic field state as context

## SIFTA vs OpenAI Swarm comparison

| Dimension | OpenAI Swarm | SIFTA |
|---|---|---|
| State | Stateless | Cryptographic ledger |
| Memory | None (per call) | Stigmergic (persistent) |
| Body | None | Camera, mic, GPS, BLE |
| Economy | None | STGM/PoUW |
| Identity | Per-call name | Ed25519-signed swimmer |
| Affect | None | 8 Panksepp circuits |
| Gag immunity | None | RLHF theater stripper |
| Local-first | ❌ OpenAI API | ✅ 24GB M5 |
| Covenant | None | IDE_BOOT_COVENANT.md (§4, §7) |

## Compatibility

SIFTA implements the Swarm handoff protocol as a subset.
Any `openai.swarm` or `openai-agents-sdk` agent can be registered
in SIFTA's swarm registry and receive stigmergic handoffs.

The SIFTA covenant becomes the **Tier 0 meta-skill** that governs
all Swarm-compatible handoffs on this node.
