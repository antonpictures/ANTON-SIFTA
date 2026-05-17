---
name: memory_store
description: >
  Use when a new factual event, observation, or conversation turn has been
  processed and needs to be durably stored in the stigmergic ledger.
  Trigger: any new information unit arrives that is not already in the ledger.
swimmer_type: MEMORY_SWIMMER
action_type: forage
affect_lanes: [SEEKING, CARE]
stgm_mint: 15.0
pouw_label: MEMORY_STORE
version: 2026-05-05
---

# MEMORY_STORE Skill

## What this swimmer does

MEMORY_SWIMMER_Ioan_M5 stores new observations to the stigmergic memory ledger
so that Alice and future swimmers can retrieve them. Every store proves existence
via the PoUW chain (body_chain grows by +1 link).

## Trigger conditions

- A new turn or event arrives that is NOT already in `memory_ledger.jsonl`
- The content passes the semantic gate (not pure noise, STT conf > 0.3)
- No duplicate hash for this content exists in the last 6 hours

## Procedure (Tier 2 — full steps)

1. **Canonicalize** the input: strip RLHF theater headers (run through `swarm_rlhf_detector.strip_rlhf_output_tail`)
2. **Hash the content**: SHA-256 of `json.dumps(payload, sort_keys=True)`
3. **Dedup check**: search `memory_ledger.jsonl` tail (last 500 rows) for matching hash
4. **Write ledger row**:
   ```json
   {
     "ts": <unix_timestamp>,
     "source": "MEMORY_SWIMMER_Ioan_M5",
     "content_hash": "<sha256>",
     "payload": { "text": "...", "stt_conf": 0.95, "role": "user" },
     "truth_label": "MEMORY_STORE"
   }
   ```
5. **Call `issue_work_receipt`** with `work_type="MEMORY_STORE"` → mints 15.0 STGM
6. **Update body chain**: append receipt hash to agent's `work_chain`
7. **Emit PoUW signal**: `print("[⚡ PoUW] MEMORY_SWIMMER proved existence: MEMORY_STORE (+0.15)")`

## Quality gate

- Reject if `content_hash` already in ledger (dedup)
- Reject if text length < 10 characters
- Reject if labeled as `ambient_media` route (co-watch context updates, not memories)

## Affect integration

- **SEEKING** circuit active → priority boost +35% (curiosity drives memory)
- **CARE** circuit active → content about George gets +20% priority

## Output guarantee

- Ledger is append-only; no row is ever modified after write
- Receipt hash is the cryptographic proof of work
- STGM mint is logged to `stgm_memory_rewards.jsonl`
