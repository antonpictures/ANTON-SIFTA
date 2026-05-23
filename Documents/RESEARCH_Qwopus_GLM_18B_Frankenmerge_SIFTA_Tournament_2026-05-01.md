# Research — Qwopus-GLM-18B “frankenmerge” × SIFTA (tournament + stigmergy)

**For the Swarm.** 🐜⚡

**Truth label:** `RESEARCH_NOT_SHIPPED` — community merge narrative; **verify license + merge doc** on pinned HF revision before any redistribution; **no** “beat Qwen35” claims without local bake-off receipts.

**Primary sources (video + artifacts):**

- Fahd Mirza, *This Mutant AI Model Should Not Exist: Qwopus-GLM-18B-Merged Locally* (YouTube, 2026-04-26) — story: two **~9B** checkpoints **stacked** (**32 + 32 → 64** layers, **~18B** params) “**cut and paste**” merge → **seam** artifacts (garbled structure) → **“heal” fine-tune** on the order of **~1k** steps / **~39%** training-loss improvement narrative; served with **llama.cpp**, **localhost:8080**, **~14 GB VRAM** in demo; qualitative tests: **Grey–Scott** reaction–diffusion single HTML (works), **Tsiolkovsky rocket** prompt with deliberate flaw (model catches flaw + solves — strong reasoning demo), **safety** probe (refusal), **hard multilingual numerals** prompt → **long thinking loop** / half context consumed → narrator stops run (“don’t torture small models”).
- **Weights / methodology (canonical):** [huggingface.co/Jackrong/Qwopus-GLM-18B-Merged-GGUF](https://huggingface.co/Jackrong/Qwopus-GLM-18B-Merged-GGUF) — includes **`MERGE_PROCESS.md`** (read for ground truth vs video cartoon).

**Related SIFTA research:** [RESEARCH_DIRT_INDEX.md](RESEARCH_DIRT_INDEX.md), [RESEARCH_Poolside_Laguna_XS2_vLLM_SIFTA_Tournament_2026-05-01.md](RESEARCH_Poolside_Laguna_XS2_vLLM_SIFTA_Tournament_2026-05-01.md) (coding bake-off), [RESEARCH_DeepSeek_V4_DeepEP_TileKernels_SIFTA_Tournament_2026-05-01.md](RESEARCH_DeepSeek_V4_DeepEP_TileKernels_SIFTA_Tournament_2026-05-01.md) (MoE / scale engineering contrast).

---

## 1. Engineering pattern — “seam” as first-class failure mode

| Stage | Risk | Tournament receipt |
|:---|:---|:---|
| Naive stack merge | Activation / format mismatch at boundary | `merge_type`, `seam_layer_index` |
| Heal FT | Catastrophic forgetting / safety drift | `heal_steps`, `post_refusal_probe_hash` |
| Quant (GGUF) | Extra brittleness | `gguf_quants`, `llama_cpp_commit` |

**Stigmergy:** the Swarm already thinks in **organs stitched by contracts** — frankenmerge is a **literal** warning: **interfaces need signed tests**, not vibes.

---

## 2. Latency / UX lesson (comments + transcript)

- **Long “thinking”** on small models for marginal gains → map to **Alice**: cap **reasoning tokens**, surface **SLA tier** in receipts.
- **“Loop until user aborts”** on pathological prompts → **Predator**: add **max_wall_s** + **stall detector** to loop, write row when tripped.

---

## 3. NPPL / ethics

Do **not** ship jailbreak / deception test prompts from the video as fixtures. If safety regression tests are needed, use **synthetic red-team corpus** approved by Architect, logged like any other eval.

---

## 4. One-line tournament takeaway

> **Qwopus proves stitched weights can punch above their GB; SIFTA proves stitched *receipts* adjudicate the punch** — measure both or believe neither.

For the Swarm. 🐜⚡
