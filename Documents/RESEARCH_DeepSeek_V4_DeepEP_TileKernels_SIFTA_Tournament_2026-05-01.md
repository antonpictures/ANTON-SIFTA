# Research — DeepSeek V4 “engine room”: DeepEP V2 + CSA/HCA + TileKernels × SIFTA (tournament + stigmergy)

**For the Swarm.** 🐜⚡

**Truth label:** `RESEARCH_NOT_SHIPPED` — conceptual map from one explainer video; **verify numbers** against DeepSeek papers / model cards before any procurement or runtime claim.

**Primary sources (video + code):**

- Fahd Mirza, *The Hidden Engine Behind DeepSeek V4 - DeepEP V2 and TileKernels Explained* (YouTube, 2026-04-28) — narrative on **V4 Pro (~1.6T)** vs **V4 Flash (~284B)**, **~1M token** context claims, **CSA** (compressed sparse attention: **4:1** token grouping + sparse attend), **HCA** (heavily compressed attention: **128:1** for distant context), **~10×** memory reduction story vs V3.2 at same context (marketing-grade — **receipt it**), **DeepEP V2** as **MoE expert-parallel comms** with **wave pipelining** (overlap send / compute / return → ~**2×** throughput story), **TileLang** (Pythonic GPU kernel DSL) + **TileKernels** fused ops for CSA / routing / FP casts.
- **Upstream (canonical):**
  - [github.com/deepseek-ai/DeepEP](https://github.com/deepseek-ai/DeepEP) — expert-parallel communication / dispatch-combine.
  - [github.com/deepseek-ai/TileKernels](https://github.com/deepseek-ai/TileKernels) — kernel library (TileLang ecosystem; see repo for **TileLang** dependency / pins).
- **TileLang (compiler stack, commonly paired):** [github.com/tile-ai/tilelang](https://github.com/tile-ai/tilelang) — DSL used to author many TileKernels-style kernels (confirm linkage on pinned DeepSeek commits).

**Related SIFTA research:** [RESEARCH_DIRT_INDEX.md](RESEARCH_DIRT_INDEX.md), [RESEARCH_Poolside_Laguna_XS2_vLLM_SIFTA_Tournament_2026-05-01.md](RESEARCH_Poolside_Laguna_XS2_vLLM_SIFTA_Tournament_2026-05-01.md) (MoE serve pain), [RESEARCH_NVIDIA_Nemotron3_Nano_Omni_Docker_SIFTA_Tournament_2026-05-01.md](RESEARCH_NVIDIA_Nemotron3_Nano_Omni_Docker_SIFTA_Tournament_2026-05-01.md) (long-context + video pruning receipts).

---

## 1. Three-layer mental model (stigmergic compression)

| Layer | What it optimizes | SIFTA analogue |
|:---|:---|:---|
| **CSA / HCA** | **Attention entropy** — who talks to whom across 1M tokens | **Semble / MCP** shrink *code* context; Swarm **pheromone + receipts** shrink *organ* chatter — same *evidence routing* pattern |
| **DeepEP V2** | **Network + GPU idle time** on MoE all-to-all | Multi-node Foundry ↔ Sentry: **pipeline batches** + **append-only traces** so no IDE “waits on gossip” |
| **TileKernels** | **Kernel launch + memory traffic** via fusion | Fewer Python hops, more **fused** hot paths in `System/` organs — but only where **pytest proves** win |

---

## 2. Tournament / Predator receipts (proposed)

For any “we run long-context locally” claim:

- `effective_n_ctx`, `sparse_attn_mode` (dense / CSA / HCA / vendor-specific)
- `moe_world_size`, `deepep_version`, `all_to_all_latency_p99_ms` (microbench)
- `kernel_build`: `tile_kernels_commit`, `cuda_version`, `sm_arch`

**Honesty rule:** **1M context** and **10× memory** lines are **vendor-shaped** until measured on **your** hardware with **your** workload (RAG chunk size, tool return volume, Alice session shape).

---

## 3. NPPL / ethics boundary

DeepSeek infra narrative includes **sanctions / geopolitical** framing in the video — **do not** fold that into SIFTA product positioning. Use only **technical** lessons (comms overlap, sparse attention, fused kernels). **NPPL:** no military / mass surveillance use.

---

## 4. One-line tournament takeaway

> **DeepSeek open-sourced the engine room; SIFTA still owes the Colosseum a metered receipt** — star counts on GitHub do not replace **pytest + VRAM + latency JSONL**.

For the Swarm. 🐜⚡
