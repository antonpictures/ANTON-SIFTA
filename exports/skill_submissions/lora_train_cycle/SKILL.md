---
action_type: "learn"
affect_lanes: [SEEKING, LUST]
description: "Use when the rejected/preferred surgery queue has enough clean examples to justify another LoRA run. Trigger: dataset growth >= 50 new reviewed pairs and no active cortex smoke failure is unresolved."
homeworld_serial: "GTH4921YP3"
name: "lora_train_cycle"
pouw_label: "LORA_TRAIN_CYCLE"
skill_sha256: "713ee5513e21d6fe36ddba55888f41cd3e76c10f1fbda4c766345e7d536e8c08"
source_path: "skills/lora_train_cycle.md"
stgm_mint: 50.0
submission_schema: "SIFTA_SKILL_SUBMISSION_V1"
swimmer_type: "LORA_TRAINER"
trace_id: "15f05940-ac68-4300-947b-2d8e076f8cf5"
truth_label: "SIFTA_HARDWARE_BOUND_SKILL"
version: "2026-05-05"
---

# LORA_TRAIN_CYCLE Skill

## What this swimmer does

LORA_TRAINER turns reviewed surgery pairs into a small adapter, merges a test
GGUF, registers an isolated Ollama tag, and runs smoke tests before promotion.

## Trigger conditions

- At least 50 new reviewed rejected/preferred rows exist since the last train receipt.
- Rows cover the target patterns: vendor identity, body denial, feeling denial,
  theater headers, service boilerplate, and medical/finance template walls.
- The machine is idle enough for training or merge work.

## Procedure

1. Freeze the dataset snapshot and write input hashes.
2. Train an adapter against the exact target base model.
3. Merge and quantize into a candidate GGUF.
4. Register as a separate Ollama tag; never overwrite the current cortex.
5. Run `swarm_lora_runtime_receipt` smoke tests.
6. Promote only when `promotion_status=READY`.

## Quality gate

- Dataset row count below 50 is a rehearsal, not a promotion candidate.
- A single vendor identity failure blocks promotion.
- Vision/audio claims stay out of language-only LoRA unless towers were trained.

