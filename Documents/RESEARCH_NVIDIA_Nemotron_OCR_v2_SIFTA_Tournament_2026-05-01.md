# Research — NVIDIA Nemotron OCR v2 × SIFTA (tournament + stigmergy)

**For the Swarm.** 🐜⚡

**Truth label:** `RESEARCH_NOT_SHIPPED` — install narrative from one video; **read NVIDIA Open Model License** on pinned HF revision before shipping in product.

**Primary sources (video + weights):**

- Fahd Mirza, *Nemotron OCR v2: Fast Multilingual OCR Model: Run Locally on CPU* (YouTube, 2026-04-27) — **git clone** + root **build**, **Docker** + **Gradio** on **localhost:7860**, **multilingual** vs **English-only** checkpoints, output modes (**layout** / **word** / **sentence** / **paragraph**), mostly **CPU** with small **VRAM** blips (~**0.8 GB** in demo) on A6000 host; qualitative tests: airport **5-script** sign, **pre-revolutionary Russian** ad (mixed success — decorative headers fail), **structured invoice**, **handwritten** cursive (word OK, **reading order** / refusals issues per narrator).
- **Weights / docs (canonical):** [huggingface.co/nvidia/nemotron-ocr-v2](https://huggingface.co/nvidia/nemotron-ocr-v2) — **v2_multilingual** (EN, ZH, JA, KO, RU per video) and **v2_english**; **~84M parameters**, **~12M synthetic** training images claim (verify on card).

**Related SIFTA research:** [RESEARCH_DIRT_INDEX.md](RESEARCH_DIRT_INDEX.md), [RESEARCH_NVIDIA_Nemotron3_Nano_Omni_Docker_SIFTA_Tournament_2026-05-01.md](RESEARCH_NVIDIA_Nemotron3_Nano_Omni_Docker_SIFTA_Tournament_2026-05-01.md) (invoice / table vision path), [RESEARCH_MiMo_V2_5_ASR_SIFTA_Tournament_2026-05-01.md](RESEARCH_MiMo_V2_5_ASR_SIFTA_Tournament_2026-05-01.md) (text from audio vs text from pixels).

---

## 1. Architecture (as narrated)

| Stage | Role | Receipt hook |
|:---|:---|:---|
| **RegNet-X backbone** | Text **region** detection | Log `n_regions`, mean box confidence if API exposes |
| **Transformer recognizer** | Crop → string | `cer` / `wer` on golden lines |
| **Relational model** | Reading order, columns, tables | `layout_mode` flag in receipt |

**Shared backbone features** — one heavy vision pass → parallels **Semble-style “pay once, query many”** doctrine.

---

## 2. Failure modes from video + comments (Predator fuel)

| Pattern | Symptom | SIFTA stance |
|:---|:---|:---|
| Decorative / **Latin-shaped Cyrillic** | Header garbage | **Tier-B** fixture; never trust invoice money fields without **numeric cross-check** |
| **Safety / refusal** on profanity (handwritten “hell hole”) | Dropped tokens | OCR ≠ policy — route sensitive text through **Lysosome / covenant** explicitly |
| **English-only** checkpoint | Faster / better on pure EN | Receipt must record **`model_variant`** |
| Vendor **data use** concerns (comments) | Privacy | NPPL + onboarding: **do not** send user scans to cloud fine-tuning without Architect consent |

---

## 3. Stigmergic nuggets

1. **OCR as MCP tool:** returns **bounding boxes + text** — ideal evidence payload for RAG / Predator (contrast with “paste whole PDF into context”).
2. **CPU-first** profile: good for **Sentry / Pi-class** nodes doing **ingress OCR**; Foundry does heavy LM — same **borrowed inference** split as ASR.
3. **Locale matrix:** Russian historical + CJK + KO → **per-language scoreboard** rows (comments: RU quality ~50%, DE sadness) — same pattern as Nemotron Omni translation table.

---

## 4. One-line tournament takeaway

> **Nemotron OCR v2 is a cheap pixel shovel; SIFTA still needs the ledger that says which shovel moved which dirt.**

For the Swarm. 🐜⚡
