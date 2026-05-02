# Research — NVIDIA Nemotron 3 Nano Omni + Docker / vLLM × SIFTA (tournament + stigmergy)

**For the Swarm.** 🐜⚡

**Truth label:** `RESEARCH_NOT_SHIPPED` — notes from one public install video; **no weights** in-repo; **Architect GO + license pin + threat model** before wiring into Alice media organs.

**Primary sources (video + weights):**

- Fahd Mirza, *NVIDIA Nemotron 3 Nano Omni — See, Hear & Read Everything Locally* (YouTube, 2026-04-28) — **Dockerized vLLM** pull, **Hugging Face CLI** + read token, **FP8 weight download** path, long **Docker run** flags (`--ipc=host`, **`--shm-size` 16G**, port publish, read-only weight bind-mount, **128k** `max-model-len`, **tensor-parallel 1**, **video pruning rate 0.5**, **~2 fps / max 256 frames** media sampling, **Nemotron reasoning parser**, **KV cache FP8**), observed **~61.5 GB VRAM** at steady load in demo.
- **Weights (canonical examples — pin revision for any bake-off):**
  - [nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-FP8](https://huggingface.co/nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-FP8)
  - BF16 sibling (higher VRAM): [nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16](https://huggingface.co/nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16) (see HF + [vLLM recipes](https://recipes.vllm.ai/nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16)).
- **Vendor / stack context:** [vLLM blog — Nemotron 3 Nano](https://blog.vllm.ai/2025/12/15/run-nvidia-nemotron-3-nano.html) (integration notes; verify version against your Docker tag).

**Related SIFTA research:** [RESEARCH_DIRT_INDEX.md](RESEARCH_DIRT_INDEX.md), [RESEARCH_MiMo_V2_5_ASR_SIFTA_Tournament_2026-05-01.md](RESEARCH_MiMo_V2_5_ASR_SIFTA_Tournament_2026-05-01.md) (dedicated ASR vs omni ASR), [RESEARCH_Poolside_Laguna_XS2_vLLM_SIFTA_Tournament_2026-05-01.md](RESEARCH_Poolside_Laguna_XS2_vLLM_SIFTA_Tournament_2026-05-01.md) (coding bake-off discipline), [RESEARCH_Semble_MCP_Coding_Tournament_2026-05-01.md](RESEARCH_Semble_MCP_Coding_Tournament_2026-05-01.md), [ALICE_HARDWARE_ANATOMY.md](ALICE_HARDWARE_ANATOMY.md) (borrowed inference).

---

## 1. Product shape (as narrated)

| Axis | Content |
|:---|:---|
| **I/O** | Audio, video, image, **text in** → **text out** (no native **streaming speech audio out** — commenters; treat as **TTS gap** vs speech stack). |
| **Scale** | **30B total**, **~3B active** MoE-class story (video table); **three precision SKUs** on HF: **BF16** (narrator: ~**61 GB** headline), **FP8** (~**32 GB** headline), **NVFP4** (~**21 GB** headline) — **card ≠ always measured VRAM**; demo still showed **~61.5 GB** after FP8 pull → **receipt must log actual `nvidia-smi` peak**. |
| **Encoders** | **Parakeet** (audio chunks → LLM tokens), **Cosmos** (vision; native resolution image/video), **Conf3** frame fusion (narrator: ~half temporal tokens for paired frames), **video pruning** (e.g. keep **50%** of video tokens), fixed **fps cap + max frames**. |
| **Reasoning** | NVIDIA **reasoning parser** (chain-of-thought style), not “borrowed Hermes parser” (video contrast). |

---

## 2. Empirical tests in the video (tournament fixtures)

| Modality | Prompt class | Outcome (narrator) | Receipt idea |
|:---|:---|:---|:---|
| Image | Invoice extraction | Strong field match | `ocr_confidence` optional; **hash input image** |
| Image | Math / convergence table | Fast, concise analysis | Good **Predator “evidence span”** canary |
| Image | 30+ script OCR → EN + language ID | Mixed; narrator admits errors | **Per-locale scoreboard** (comments: Tamil failure = **hallucination class**) |
| Audio | Hindi/Urdu clip | Transcribe + metadata | Compare to [MiMo ASR](RESEARCH_MiMo_V2_5_ASR_SIFTA_Tournament_2026-05-01.md) on **same clip** |
| Audio | Long meme / in-joke clip | Rich scene + prosody description | **Subjective quality** → need **human_signals** or quorum, not one YouTuber |
| Video | Short AI clip (snow / candle) | Detailed cinematography read | Log **pruning_rate**, **fps**, **frame cap**, **duration_s** |
| Code | Single-file **Pomodoro** HTML/JS/CSS | Works (timer, pause, SVG ring) | Lighter than Laguna “Flask+WS mega” — **tiered harness** again |

---

## 3. Stigmergic nuggets for SIFTA

1. **One omni model ≠ one policy:** translation hallucination on low-resource locales is **exactly** why Swarm needs **multi-prover / locale-tagged receipts**, not a single “omni said so.”
2. **Docker + IPC + shm:** operational complexity is **part of the score** — tournament row should include **`docker_image_digest`**, **`shm_size`**, **`max_model_len`**, **`video_pruning_rate`**.
3. **NPPL / covenant:** “see hear read everything” is **vendor marketing**; SIFTA ships **consent-gated sensors** and **append-only traces** — omni ingress only where IDE_BOOT covenant allows.
4. **Efficiency claims (9.2× / 7.4× vs other omni):** treat as **vendor benchmark** until reproduced on **Foundry** with pinned workload — same stance as Laguna scoreboard skepticism.
5. **Borrowed inference:** omni at **61 GB** belongs on **Foundry**; field nodes post **text receipts** + **capability tags** (`omni_nemotron_fp8_v1`), not raw video.

---

## 4. One-line tournament takeaway

> **Nemotron sells unified perception; SIFTA sells unified receipts** — pair them only with **modality metadata + per-locale tests + hardware truth**.

For the Swarm. 🐜⚡
