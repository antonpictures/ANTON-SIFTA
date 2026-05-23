# SIFTA Learning-Loop Trace — Hearing Pairs to Weights

**Date:** 2026-05-21  
**Body:** GTH4921YP3  
**Trace lane:** Codex desktop / GPT-5 fixer pass  
**Scope:** Verify whether the stigmergic-memory to LoRA loop is closed for `hear_training_pairs.jsonl`.

## Grounded Chain

1. **Data exists:** `.sifta_state/hear_training_pairs.jsonl` exists and currently contains 1 labeled hearing pair.
2. **Dataset ingestion is now wired:** `System/swarm_lora_dataset_builder.extract_hear_training_pairs()` converts each labeled hearing row into a transcript-correction SFT pair:
   - user: `Correct this local microphone transcript for Alice's hearing model...`
   - assistant: `ground_truth`
3. **Builder inclusion is now wired:** `build_dataset()` includes `.sifta_state/hear_training_pairs.jsonl` and reports the source count under `sources["hear_training_pairs"]`.
4. **Probe result:** a temp dataset build produced `total_pairs=1734` and `hear_training_pairs=1`; train/valid JSONL files were written in the temp output directory.
5. **Tests:** `tests/test_lora_dataset_hear_pairs.py` proves the extraction path and missing-ground-truth guard.

## Honest Limit

This closes the **data ingestion** link: hearing corrections now feed the LoRA dataset builder.

It does **not** yet prove automatic continuous learning or behavior improvement. The remaining unproven links are:

- automatic trigger from accumulated `hear_training_pairs` to a training run,
- successful adapter training on the correct unquantized Gemma lineage,
- runtime promotion that passes smoke tests,
- fresh before/after Talk or hearing eval showing the score actually moved.

Existing `lora_runtime_receipts.jsonl` rows show both prior successes and quarantines; the latest receipts include promotion blockers such as candidate metadata unavailable, architecture mismatch, capability regressions, tokenizer byte garble, or smoke residue. Therefore the honest claim is: **dataset ingestion is closed; automatic, promoted, behavior-improving learning remains unproven until a new adapter run passes smoke and moves an eval.**
