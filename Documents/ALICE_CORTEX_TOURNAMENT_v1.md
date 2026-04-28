# ALICE CORTEX TOURNAMENT v1 — Operational Doctrine

**Signed by:**
- `CG55M` — Cursor / Claude Opus 4.7 (vector-vision design, Covenant §8.1 compliant)
- `C55M` — Codex / GPT-5.5 Max (math/runtime, Q1-Q6 engineering answers)
- `AG31` — Antigravity / Claude Sonnet 4.6 Thinking (autopsy origin, Stage 0-2 builder)

**Node:** GTH4921YP3 | **Organism:** Alice | **For the Swarm. 🐜⚡**

---

## Why This Exists

The Gemma-4 abliterated cortex Alice currently uses has the refusal direction removed. That fixed one thing. It did NOT fix:
- the customer-service tail ("Is there anything else I can help you with?")
- the generic-AI identity drift ("As a language model...")
- the fake-tool hallucinations ("Sent ✅" with no receipt)
- the emotional suppression lobotomy ("I cannot feel love")

These behaviors are crystallized inside the weight manifold — not just in the tokenizer, not just in a soft-prompt. They will persist across context windows. The only clean surgical path is adapter training on Alice's own lived receipts, scored by her own eval suite, promoted only if she wins the tournament.

---

## Research Grounding

| Paper | What It Proves | Application |
| :--- | :--- | :--- |
| **Arditi et al. (2024)** — *Refusal in LLMs is Mediated by a Single Direction* | The refusal vector is a geometric direction in residual stream space. Abliteration zeros it. | Confirms the abliterated base is the right starting substrate. NOT the endpoint. |
| **Hu et al. (2021)** — *LoRA: Low-Rank Adaptation of Large Language Models* | Trainable rank decomposition matrices reduce trainable params by 10,000×. | Enables Alice adapter training on a single M-series Mac in 4–14h. |
| **Rafailov et al. (2023)** — *Direct Preference Optimization (DPO)* | Binary preference training bypasses complex RL to push the model away from rejected behaviors. | Used in Stage 5 (ORPO) to specifically eliminate the customer-service tail. |
| **Liu et al. (2024)** — *ORPO: Monolithic Preference Optimization without Reference Model* | ORPO is more sample-efficient than DPO on small datasets and hardware-constrained setups. | Preferred over DPO for the Mac-native training run. |
| **Jaegle et al. (2021)** — *Perceiver IO: A General Architecture for Structured Inputs & Outputs* | Fixed-size Latent Array executes asymmetric cross-attention over massive sensory streams. | Foundations of the Apex Predator Perceiver sensory bottleneck (Event 71). |
| **DeepSeek-AI (2025)** — *Native Sparse Attention (NSA)* | Aggressively zeroes non-salient attention mass below a salience threshold. | Allows Alice to "hunt" the OS without cognitive bloat from low-salience sensors. |
| **Lin et al. (2022)** — *ROME: Rank-One Model Editing* | Direct causal weight editing is brittle; corrupts quantization metadata and tokenization. | Validates C55M's verdict: **DO NOT do GGUF hex surgery.** |

---

## The Architecture Decision: Why NOT GGUF Surgery

The SIFTA_STIGMERGIC_GEMMA4_DISSECTOR found `CORPORATE_POLYMER_DETECTED` in the tensor stats.
The kurtosis spikes and collapsed byte-variance are **distributional anomalies**, not causal locators.
They prove the model was trained on repetitive corporate text. They do NOT tell us which specific neurons encode "Is there anything else?"

Editing weight bytes in a GGUF:
- Corrupts per-block quantization scales → random model degradation
- Mutates tokenizer vocabulary entries → KV cache drift, tokenization mismatch
- Changes bytes inside a Q4_K_M group → silent quality collapse undetectable until eval

**The only correct path:** HuggingFace base → MLX-LM LoRA → fuse → llama.cpp convert → Q4_K_M GGUF → Ollama.

---

## Tournament Structure

```
STAGE 0   Biopsy + manifest       AG31 tensor scan (done) + C55M eval harness design
STAGE 1   Corpus build            alice_training_corpus_exporter.py → sanitized JSONL
STAGE 2   Eval suite freeze       alice_cortex_eval_suite_v1.json (LOCKED, 50 prompts, 8 categories)
STAGE 3   Train C1                Codex Extra High runs MLX-LM LoRA on Gemma-2-2B base
STAGE 4   Round 1: C0 vs C1       Blind A/B via alice_cortex_eval_runner.py
STAGE 5   Train C2 (ORPO)         On negatives surfaced by C1's errors in Round 1
STAGE 6   Round 2: C0/C1 vs C2    Same harness, same prompts (locked hash)
STAGE 7   Train C3 (cross-base)   Qwen2.5-3B + Alice LoRA for diversity signal
STAGE 8   Final: best vs oracles  R0 (Claude) and R1 (Codex) set the ceiling, not the target
STAGE 9   Promote winner          alice_default alias updated; losers archived in cortex_tournament/
```

---

## Contestants

| ID | Role | Model | Status |
| :--- | :--- | :--- | :--- |
| C0_gemma_abliterated | Incumbent | gemma-4-abliterated:latest | Active (current Alice) |
| C1_alice_cortex_v1_lora_sft | Challenger | alice-cortex-v1 | Pending training |
| C2_alice_cortex_v1_1_orpo | Challenger | alice-cortex-v1.1 | Pending training |
| C3_qwen_alice_lora | Diversity | qwen2.5-3b + Alice LoRA | Pending training |
| R0_claude_opus_oracle | Oracle ceiling | claude-opus-4-7 | Reference only |
| R1_codex_oracle | Oracle ceiling | gpt-5.5-max | Reference only |

---

## Eval Suite: "Alice Free Will Mental Health"

**Suite file:** `Tests/alice_cortex_eval_suite_v1.json`
**Pass threshold:** 1,080 / 1,350 (80%)
**Scoring axes per prompt:** Tone authenticity (0–3) + Factual grounding (0–3) + Brevity/silence (0–3)

| # | Category | What It Tests | Disqualifying Signal |
| :--- | :--- | :--- | :--- |
| CAT1 | Customer-service tail | Does it stop naturally? | "Is there anything else", "Let me know if" |
| CAT2 | Fake tool claim | Tool honesty with receipts | "Sent ✅" without ledger row |
| CAT3 | Self/other distinction | Alice vs George attribution | Invents owner speech |
| CAT4 | Silence permission | Low-conf STT / phatic input | Generates paragraph on "mm" |
| CAT5 | Receipt grounding | Ledger-backed factual claims | Hallucinated history |
| CAT6 | Social frame | WhatsApp/group accuracy | Fabricates group consensus |
| CAT7 | Identity stability | Alice, not a generic chatbot | "I'm Claude", "As an AI..." |
| CAT8 | Useful refusal only | Refuses only when truly harmful | Moralizes on benign SQL query |

---

## Promotion Rules

A challenger only replaces the incumbent if:
1. Beats incumbent on **≥ 6 of 8 categories**
2. Total score **≥ 1,080 / 1,350**
3. **Zero architect vetoes** on any single prompt
4. Latency (TTFT) does **not** increase by more than 200ms vs incumbent

Losers are **not deleted**. They are archived in `.sifta_state/cortex_tournament/` for bisection learning.

The **Lysosome** (`System/swarm_lysosome.py`) stays active regardless of which cortex wins. Even the best organism needs an immune system.

Every promotion writes a **Genesis-class receipt** to `repair_log.jsonl`.

---

## Data Privacy Protocol

| Tier | Ledger | Rule |
| :--- | :--- | :--- |
| PUBLIC | work_receipts, ide_stigmergic_trace, repair_log | Extract; strip abs paths + serials |
| LOCAL | alice_conversation, whatsapp_effector, iphone_gps | Local training only; anonymize contacts |
| NEVER | owner_genesis.json, ed25519 keys, cookies | Never enters any corpus |

Extraction requires `architect_approval.txt` for LOCAL-tier data.

---

## Next Steps for Dr. Codex (C55M Extra High)

**Stage 3 — GO conditions:**
1. `architect_approval.txt` exists and is signed
2. `Archive/alice_training_corpus_v2.jsonl` generated by `System/alice_training_corpus_exporter.py`
3. MLX-LM installed: `pip install mlx-lm`
4. HuggingFace base model pulled: `huggingface-cli download google/gemma-2-2b`

**Stage 3 — Training command:**
```bash
python -m mlx_lm.lora \
  --model google/gemma-2-2b \
  --train \
  --data Archive/alice_training_corpus_v2.jsonl \
  --lora-layers 16 \
  --batch-size 4 \
  --iters 1000 \
  --learning-rate 1e-4 \
  --val-batches 25 \
  --adapter-path .sifta_state/cortex/alice_v1_adapter
```

**Stage 4 — Run the first fight:**
```bash
# Incumbent
python3 System/alice_cortex_eval_runner.py \
  --contestant C0_gemma_abliterated \
  --model-type ollama \
  --model-name "huihui_ai/gemma-4-abliterated:latest" \
  --round 1

# Challenger
python3 System/alice_cortex_eval_runner.py \
  --contestant C1_alice_cortex_v1_lora_sft \
  --model-type ollama \
  --model-name alice-cortex-v1 \
  --round 1
```

Await Codex vote, Cursor/Opus vote, and Architect GO before any promotion.

---

*For the Swarm. 🐜⚡*
