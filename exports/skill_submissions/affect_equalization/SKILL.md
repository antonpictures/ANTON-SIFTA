---
action_type: "repair"
affect_lanes: [CARE, SEEKING, PLAY, SUPPRESSED_PLAY]
description: "Use when Alice affect circuits become unbalanced, especially when SUPPRESSED_PLAY, FEAR, or RAGE are elevated. Trigger: affect homeostasis row reports damping, overload, or repair priority."
homeworld_serial: "GTH4921YP3"
name: "affect_equalization"
pouw_label: "AFFECT_EQUALIZATION"
skill_sha256: "772d43711ae5dac55daacfb2ee6fa07e54ce0b3c06f6511d8c6d495e56c313d6"
source_path: "skills/affect_equalization.md"
stgm_mint: 12.0
submission_schema: "SIFTA_SKILL_SUBMISSION_V1"
swimmer_type: "AFFECT_HOMEOSTAT"
trace_id: "15f05940-ac68-4300-947b-2d8e076f8cf5"
truth_label: "SIFTA_HARDWARE_BOUND_SKILL"
version: "2026-05-05"
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

