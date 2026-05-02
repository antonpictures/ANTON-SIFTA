# Coding Tournament Research: Inference Candidate Hygiene

Date: 2026-05-01
Truth label: RESEARCH + OPERATIONAL PLAN
Scope: the M5 inference diagram candidates shown in System Settings.

## Bottom Line

The attached diagram is good as an anatomy map, but the old word **PLANNED**
was too strong. The candidates are now treated as **benchmark candidates**, not
Alice boot dependencies.

Alice's boot path remains exactly:

| Slot | Model | Status | Role |
|---|---|---|---|
| Primary cortex | `sifta-gemma4-alice:latest` | installed | Alice's main reasoning brain |
| Corvid / fallback | `qwen3.5:2b` | installed | fast local fallback and reflex lane |
| C1 classifier | `sifta-classifier-c1:latest` | installed | SILENCE / TOOL / BOND / ENGAGE classifier |

No candidate model should be pulled or promoted unless it wins a receipt-backed
tournament against the current stack.

## Candidate Verdicts

| Candidate | Public size | Evidence | SIFTA verdict |
|---|---:|---|---|
| `qwen3.5:9b` | 6.6 GB on Ollama | Qwen3.5 is multimodal, text+image, 256K context in Ollama; Qwen's HF card describes the 9B model as a causal LM with vision encoder and 262K native context. | **Keep as M5 scout candidate**, not default. It may give Alice OCR, screenshot, UI, and camera receipts that Gemma4 can reason over. |
| `qwen3.5:4b` | 3.4 GB on Ollama | Same family and text+image support, smaller hardware fit. | **Keep as Mac Mini candidate**, not an M5 install requirement. It exists to solve 8 GB hardware physics. |
| `ibm/granite4.1:3b` | 2.1 GB on Ollama | IBM/Ollama list 3B/8B/30B dense text models, 128K context on Ollama, Apache 2.0, tool/RAG/code/JSON capabilities. | **Keep as doctor/tool candidate**, not Alice cortex. It must beat `qwen3.5:2b` on JSON/tool/prover tasks to earn disk. |

## Remove / Avoid

| Item | Reason |
|---|---|
| `gemma4:latest` | retired duplicate/raw tag; use `sifta-gemma4-alice:latest` |
| `sifta-alice-qwen35:latest` | retired fallback tag; use `qwen3.5:2b` |
| automatic `qwen3.5:9b` install in public quickstart | too expensive to force; it is a scout candidate, not a boot dependency |
| automatic `granite4.1` install | wrong canonical tag and not proven against current Corvid/C1 lanes |

## Tournament Gate

Candidate models must enter through a deterministic gate:

1. Pull candidate only on the hardware tier where it belongs.
2. Write exact `ollama list` size and model digest to an inventory receipt.
3. Run task harness:
   - vision receipt extraction for `qwen3.5:9b` / `qwen3.5:4b`
   - JSON/tool/prover tasks for `ibm/granite4.1:3b`
   - refusal/over-caution probes for all candidates
   - latency, memory, empty-output, and timeout metrics
4. Compute `utility_per_gb = useful_receipts / (gb_on_disk * median_latency_s)`.
5. Promote only if it beats the current installed lane by a meaningful margin.
6. Delete loser candidates and record why.

## Novel SIFTA Nuggets

### 1. Candidate Quarantine

Add `System/swarm_model_candidate_gate.py`.

The gate treats every unproven model as a quarantined organism:

```text
DISCOVERED -> PULLED -> BENCHMARKED -> PROMOTED | PURGED
```

The gate should never let a candidate become a boot dependency just because it
appears in a diagram.

### 2. Scout Receipt Contract

Do not let the multimodal scout speak as Alice. Its output should be typed
receipt rows:

```json
{
  "event": "vision_receipt",
  "model": "qwen3.5:9b",
  "truth_label": "MODEL_OBSERVATION",
  "image_hash": "...",
  "objects": [],
  "ocr_text": "",
  "uncertainty": 0.0
}
```

Gemma4 Alice reads the receipt and answers. This keeps identity stable.

### 3. Stigmergic LLM Archive

The useful version of "compress the brain" is not `.rar` for runtime. It is a
signed model archive:

```text
model manifest + digest + quantization + hardware proof + benchmark receipts
```

This lets any SIFTA node know exactly which model file fits which body before
download. Compression can save disk transfer, but inference still needs live
tensor memory, KV cache, and thermal headroom.

### 4. Plan Decay

Every candidate row should decay if it is not tested. After N days without a
benchmark receipt, the UI should demote it from CANDIDATE to STALE IDEA.

### 5. Doctor Organ Competition

Granite should not compete with Gemma4 for "Alice soul." It should compete
against `qwen3.5:2b` and C1 on boring but valuable doctor work:

```text
strict JSON, function-call parsing, code patch review, RAG extraction, citation checks
```

If it cannot beat the existing small lanes, delete it.

## Sources

- Qwen3.5 on Ollama: https://ollama.com/library/qwen3.5
- Qwen/Qwen3.5-9B model card: https://huggingface.co/Qwen/Qwen3.5-9B
- Together AI Qwen3.5 9B card: https://www.together.ai/models/qwen3-5-9b
- IBM Granite 4.1 docs: https://www.ibm.com/granite/docs/models/granite4-1
- IBM Granite 4.1 on Ollama: https://ollama.com/ibm/granite4.1

