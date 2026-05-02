# Research — MiMo-V2.5-ASR (Xiaomi) × SIFTA (tournament + stigmergy)

**For the Swarm.** 🐜⚡

**Truth label:** `RESEARCH_NOT_SHIPPED` — patterns and citations only; no weights vendored until **Architect GO + license review + pytest + Predator row**.

**Primary sources (video + code):**

- Fahd Mirza, *MiMo-V2.5-ASR: Xiaomi Just Silenced Everyone With This Free Speech AI* (YouTube, 2026-04-30) — local clone, `pip`/venv install, **Gradio** demo, first-run model download, **~18 GB VRAM** for **8B** ASR on demo hardware, service on **localhost (video cites port ~7898)**, tests: EN↔ZH code-switch, low-quality **multi-speaker meeting** (no **diarization** — single transcript blob), clean single-speaker EN/ZH.
- **Upstream (canonical):**
  - GitHub: [XiaomiMiMo/MiMo-V2.5-ASR](https://github.com/XiaomiMiMo/MiMo-V2.5-ASR)
  - Hugging Face: [huggingface.co/XiaomiMiMo/MiMo-V2.5-ASR](https://huggingface.co/XiaomiMiMo/MiMo-V2.5-ASR)
- **License (verify in-tree before ship):** upstream README points to Apache-2.0 style terms — **re-read `LICENSE` on pinned commit** before any redistribution or bundled weights.

**Related SIFTA research:** [RESEARCH_Semble_MCP_Coding_Tournament_2026-05-01.md](RESEARCH_Semble_MCP_Coding_Tournament_2026-05-01.md) (entropy routing), [RESEARCH_Hermes_LMStudio_SIFTA_Tournament_2026-05-01.md](RESEARCH_Hermes_LMStudio_SIFTA_Tournament_2026-05-01.md) (local inference + ctx receipts), [RESEARCH_DIRT_INDEX.md](RESEARCH_DIRT_INDEX.md) (master dirt ledger).

---

## 1. Claims from transcript (verify; do not trust leaderboard hype blindly)

| Claim (as narrated) | Risk | Honest SIFTA stance |
|:---|:---|:---|
| Three-stage train: massive audio pretrain → quality SFT → **RL** “self-correct” | Standard modern stack; RL details need paper/repo | Map RL stage to **Swarm tournament**: policy patches that **improve under measured loss** (pytest + receipts), not vibes. |
| Beats Whisper Large V3 / Gemini on dialect / Open ASR leaderboard | Benchmark gaming / domain shift | **Receipt:** run same audio fixtures on Foundry + log WER/CER + **wall time + VRAM** to `work_receipts.jsonl` (or dedicated ASR eval JSONL). |
| Code-switching “without configuration” | True only for supported language pairs | SIFTA **Alice** locales: if we ever pipe meeting audio, **declare language prior** in receipt metadata even if model is “end-to-end.” |
| Multi-speaker meeting: one flat transcript | **No speaker IDs** in demo | **Gap for Swarm:** diarization is a separate organ; combine MiMo text + **pyannote-style** diarization later if Architect wants quorum-by-speaker. |
| “Censorship” (comment) | Vendor policy / alignment | NPPL + covenant: **no surveillance mass-ingest**; optional **local** ASR for consent-gated channels only. |

---

## 2. Stigmergic nuggets — audio as high-entropy trail

1. **Semble-class analogy:** raw long-form audio is **grep-the-universe** for the ear. ASR is **retrieval into text** — same honesty move as BM25+embeddings: compress world into **evidence spans** the policy model can cite.
2. **Receipt fields (proposed):** `asr_model_id`, `asr_commit`, `audio_duration_s`, `rtf`, `vram_peak_gb`, `language_guess`, `diarization=false`, `input_hash` (never store raw audio in git without GO).
3. **Borrowed inference:** heavy ASR on **Foundry GPU**; Sentry / field nodes post **JSONL receipts** only — aligns with [ALICE_HARDWARE_ANATOMY.md](ALICE_HARDWARE_ANATOMY.md) borrowed-inference doctrine.
4. **Tournament hook:** “24 min STT took 2 h on weak HW” (comment) — publish **SLA tier** in Predator docs: **Pi-class** = batch overnight; **Foundry** = interactive; receipts prevent lying about which tier ran.
5. **Lysosome / speech organ:** README already treats **Talk to Alice** as Broca — local ASR could feed **cochlea**-class ingress **if** consent + trace; never silent exfil.

---

## 3. Engineering spikes (Architect GO)

| Spike | Outcome |
|:---|:---|
| Disposable venv + Gradio from upstream | Confirm VRAM on M5 Studio vs video’s H100 narrative |
| 10 fixed clips (code-switch, meeting noise, clean EN) | WER table + RTF row for Predator |
| Optional MCP tool `transcribe_local` | Wrap CLI/HTTP boundary; **stdio MCP** only after threat model |

---

## 4. One-line tournament takeaway

> **MiMo sells messy-world ASR; SIFTA sells messy-world receipts.** Pair them only where **consent + append-only trace + hardware tier** are explicit.

For the Swarm. 🐜⚡
