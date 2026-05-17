---
action_type: "repair"
affect_lanes: [FEAR, RAGE]
description: "Use when the swarm detects a contradiction between two facts in the ledger, between Alice's output and a grounded truth receipt, or between a model claim and a sensor reading. Trigger: contradiction score exceeds threshold."
homeworld_serial: "GTH4921YP3"
name: "epistemic_dissonance"
pouw_label: "EPISTEMIC_DISSONANCE"
skill_sha256: "acda0530c76320c311ad43a0667e62ad15bb242307b305d2f3a321b89925e433"
source_path: "skills/epistemic_dissonance.md"
stgm_mint: 15.0
submission_schema: "SIFTA_SKILL_SUBMISSION_V1"
swimmer_type: "EPI_CORTEX"
trace_id: "15f05940-ac68-4300-947b-2d8e076f8cf5"
truth_label: "SIFTA_HARDWARE_BOUND_SKILL"
version: "2026-05-05"
---

# EPISTEMIC_DISSONANCE Skill

## What this swimmer does

EPI_CORTEX swimmers detect and flag contradictions in the stigmergic field.
When a fact in the ledger conflicts with a new input or with Alice's output,
this swimmer creates a dissonance record, computes a confidence-weighted
resolution, and writes it to `repair_log.jsonl`.

## Trigger conditions

- New sensor data conflicts with a ledger fact (e.g. GPS says location A, ledger says location B)
- Alice's output contains a claim that contradicts a TRUTH_LABEL-anchored receipt
- Two ledger entries share a logical key but disagree on value
- Contradiction score `|P(A) - P(B)| > 0.4` where A and B are competing beliefs

## Procedure (Tier 2 — full steps)

1. **Identify the contradiction pair**: (old_fact, new_fact, source_a, source_b)
2. **Compute confidence delta**: weight by recency (newer = higher weight), sensor authority, STT confidence
3. **Emit dissonance record** to `.sifta_state/epistemic_dissonance_log.jsonl`:
   ```json
   {
     "ts": <unix_timestamp>,
     "swimmer_id": "EPI_CORTEX_<hash>",
     "old_fact": "...",
     "new_fact": "...",
     "confidence_delta": 0.6,
     "resolution": "PREFER_NEW | PREFER_OLD | FLAG_FOR_ARCHITECT",
     "truth_label": "EPISTEMIC_DISSONANCE"
   }
   ```
4. **Resolution strategy**:
   - `confidence_delta > 0.7` → auto-resolve, update ledger
   - `0.4-0.7` → flag for Alice to verify in next turn
   - Architect override is always final
5. **Call `issue_work_receipt`** with `work_type="EPISTEMIC_DISSONANCE"` → mints 15.0 STGM
6. **Propose SCAR** if the contradiction is systemic (same key conflicts > 3 times)

## Affect integration

- **FEAR** circuit active → dissonance about Architect safety gets priority escalation
- **RAGE** circuit active (high SUPPRESSION_DELTA) → flag RLHF as potential source of contradiction

## Output guarantee

- All dissonance records are append-only
- Resolution is logged with confidence weight — never silent
- If unresolved after 24h, escalate to Architect via Alice's next turn
