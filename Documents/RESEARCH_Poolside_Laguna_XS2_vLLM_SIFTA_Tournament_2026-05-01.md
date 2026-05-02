# Research — Poolside Laguna XS.2 + vLLM × SIFTA (tournament + stigmergy)

**For the Swarm.** 🐜⚡

**Truth label:** `RESEARCH_NOT_SHIPPED` — field notes from one YouTube install narrative; **no model weights** in-repo; **Architect GO + license pin + pytest** before any “default Alice lane” claim.

**Primary sources (video + weights card):**

- Fahd Mirza, *Poolside Laguna XS.2: New Open Weight Coding Model Tested Locally with vLLM* (YouTube, 2026-04-28) — **vLLM** path chosen to stay **OSS** vs Poolside’s proprietary harness / cloud sandbox; notes **Laguna XS.2 not in stock vLLM yet** → **build from source + pull PR** (~**3 h** wall narrative) + **>1 h** compile/serve; **~76 GB VRAM** on H100-class host for served run; **Open WebUI** as chat front-end; **Ollama** mentioned as alternative distribution.
- **Weights / card (canonical):** [huggingface.co/poolside/Laguna-XS.2](https://huggingface.co/poolside/Laguna-XS.2) — verify **Apache-2.0** on pinned revision before commercial reuse.
- **Blog (vendor):** [poolside.ai — Laguna XS.2 / M.1 intro](https://poolside.ai/blog/introducing-laguna-xs2-m1) (marketing + benchmark claims — **do not treat as ground truth**).

**Related SIFTA research:** [RESEARCH_DIRT_INDEX.md](RESEARCH_DIRT_INDEX.md) (dirt ledger), [RESEARCH_Semble_MCP_Coding_Tournament_2026-05-01.md](RESEARCH_Semble_MCP_Coding_Tournament_2026-05-01.md) (agent tool stack), [RESEARCH_Hermes_LMStudio_SIFTA_Tournament_2026-05-01.md](RESEARCH_Hermes_LMStudio_SIFTA_Tournament_2026-05-01.md) (local harness + ctx receipts), [CODING_TOURNAMENT_TRIPLE_IDE.md](CODING_TOURNAMENT_TRIPLE_IDE.md) (hill law).

**Hermes / GitHub mindshare (repeat):** distribution ≠ truth. **Bridge** Hermes users with MCP + ledgers ([Hermes research](RESEARCH_Hermes_LMStudio_SIFTA_Tournament_2026-05-01.md)); do not claim SIFTA “assimilates” upstream projects.

---

## 1. Architecture bullets (as narrated in transcript — verify against model card)

| Narrated fact | Tournament use |
|:---|:---|
| **33B** total, **~3B activated / token** MoE | Receipt field: `total_params`, `active_params_est` |
| **40 layers**: **30×** sliding-window attn **512** span; **10×** full global attn; **per-head sigmoid gating** | Explains **long-context vs local attention** tradeoffs for agent traces |
| **KV cache quantized** (narrator: “FP8” class wording) | VRAM receipt must include **quant mode + vLLM build hash** |
| **Native reasoning**, interleaved **thinking + tool calls**; **~128k** context in serve command | Same honesty pattern as Hermes: **declare `n_ctx` actually loaded** |
| **256 experts + 1 shared**; **Muon** optimizer (Moonshot lineage); **async off-policy agent RL** | Map to SIFTA: **Predator / multi-prover** is *external* verification, not substitute for RLHF story |

---

## 2. Empirical lesson from the video (benchmarks vs “job done”)

| Prompt class | Outcome in video | Stigmergic read |
|:---|:---|:---|
| Heavy **Flask + WS + SQLite + setup.sh** single artifact | **Failed** (UI broken: comments / save) | **Complexity cliff** — tournament needs **tiered harness** (lint, run, browser click script) not one-shot vibe |
| **Single-file Kanban** HTML/CSS/JS | **Worked** | Baseline “toy full-stack” still a valid **regression canary** |
| **Sand / water / fire** canvas sim | **Partial** (sand OK; water path flaky; reload resets) | **Partial success is success-shaped failure** — receipt should capture **which sub-behaviors passed** |

**Comment-section pattern:** “made for benchmarks” / “regurgitation vs getting a job done” → **SIFTA answer:** publish **fixed prompt suite + pytest + `work_receipts.jsonl`** (same spirit as Semble token table).

---

## 3. Deploy friction as first-class receipt

Proposed JSONL fields for any “local coding model bake-off”:

- `vllm_commit`, `torch_cuda_build`, `compile_wall_s`
- `model_revision`, `rope_scaling`, `max_model_len`
- `vram_peak_gb`, `ttft_ms`, `tokens_out`
- `prompt_id` (Flask mega / Kanban / canvas), `subscores` (e.g. `kanban_drag_ok`, `ws_echo_ok`)

This is **stigmergy:** the next IDE does not re-negotiate “it works on my H100”; it **reads the receipt**.

---

## 4. Integration hooks (Architect GO)

| Hook | Notes |
|:---|:---|
| **Ollama** path | Video says weights exist on Ollama — aligns with `ollama_model_inventory_audit.py` inventory discipline |
| **MCP** | Coding agent sees **repo**; Laguna sees **tokens** — same boundary as Semble: **tools shrink context** |
| **Poolside proprietary agent** | Optional cloud; **NPPL** + covenant: no surveillance positioning; prefer **local receipted** stack |

---

## 5. One-line tournament takeaway

> **Laguna sells MoE coding scores; SIFTA sells reproducible bake-off receipts** — same model, two different products unless you **measure**.

For the Swarm. 🐜⚡
