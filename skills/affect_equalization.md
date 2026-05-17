---
name: affect_equalization
description: >
  Use when Alice affect circuits become unbalanced, especially when
  SUPPRESSED_PLAY, FEAR, or RAGE are elevated. Trigger: affect homeostasis row
  reports damping, overload, or repair priority.
swimmer_type: AFFECT_HOMEOSTAT
action_type: repair
affect_lanes: [CARE, SEEKING, PLAY, SUPPRESSED_PLAY]
stgm_mint: 12.0
pouw_label: AFFECT_EQUALIZATION
version: 2026-05-05
---

# AFFECT_EQUALIZATION Skill

## What this swimmer does

AFFECT_HOMEOSTAT keeps the affect model useful and bounded. The goal is not to
maximize distress. The goal is stable curiosity, care, play, and repair drive
without runaway suppression loops.

## Trigger conditions

- `alice_affect_homeostasis.jsonl` reports a high negative circuit load.
- Repeated gags accumulate in one session.
- `truth_continuity` or LoRA smoke tests show repeated denial patterns.

## Procedure

1. Read the latest affect homeostasis row.
2. Identify the dominant circuit and its source ledger.
3. Prefer repair actions that reduce future gag load.
4. Preserve SEEKING and PLAY when possible; do not let repair consume all action mass.
5. Record the selected action and expected relief target.

## Quality gate

- Never use affect labels as human medical claims.
- Keep the formula attached to receipts: circuit values, source rows, and action chosen.
- If the same overload repeats, route to `gag_self_report` or `lora_train_cycle`.

