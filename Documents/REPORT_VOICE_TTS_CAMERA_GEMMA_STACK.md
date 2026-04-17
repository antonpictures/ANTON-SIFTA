# Report — Voice (TTS), Audio LLMs, Camera Input & Gemma 4 (SIFTA / Cursor context)

**Date:** 2026-04-16  
**Audience:** Architect — **read-only planning** (no code execution implied).  
**Context:** You asked for a **detailed report**: **audio output (TTS)** for “her,” what **audio-capable / specialized** models make sense, **filesystem** layout for media, **camera input** recommendations, and whether **Gemma 4** supports **image** processing. Below is structured for **local-first** SIFTA on **Apple Silicon** (M5 Foundry), with privacy and ops notes.

---

## 1. Executive summary

| Layer | Recommendation (high level) |
|-------|-----------------------------|
| **Speech out (TTS)** | Prefer **on-device** TTS for latency + privacy; tier up to **neural cloud TTS** only for flagship demos. macOS: **AVSpeechSynthesizer** / **Say** for zero-deps; **Piper** / **Kokoro**-class for open neural TTS where quality matters. |
| **“Audio LLM”** | Split the problem: **ASR** (Whisper-class), **spoken-language understanding** (text LLM or native audio LM), **TTS** (separate). True **audio-native LMs** (e.g. Qwen2-Audio-class) excel at **sound/speech understanding**, not replacing your text brain for everything. |
| **Vision in** | **Camera** → decode → **resize/normalize** → **optional keyframe** → model API. **Gemma 4** (per Google’s 2026 line) is positioned as **multimodal** with **text + image** (and **audio** on smaller edge variants in public materials). Treat **vision** as a **modality adapter**, not the kernel identity layer. |
| **Filesystem** | Separate **cache** (ephemeral), **captures** (user-consented), **model weights** (read-mostly), **logs** (append-only). Never mix **ground-truth ledger** with **raw media blobs** without explicit policy. |

---

## 2. Text-to-speech (TTS) — “give her audio output”

### 2.1 Requirements checklist

- **Latency:** UI feedback &lt; 200–500 ms perceived for short lines; streaming TTS helps.  
- **Privacy:** On-device preferred for ambient/home context.  
- **Voice identity:** One **fixed profile** (name + locale + rate) stored as **config**, not kernel gender.  
- **Offline:** Must work when the network dies (SIFTA “territory” ethos).

### 2.2 Practical tiers (macOS / Apple Silicon)

1. **Built-in (no ML weights)**  
   - **`AVSpeechSynthesizer` (Swift)** or **`NSSpeechSynthesizer` / `say` (CLI)** — reliable, offline, not “neural premium” quality but **boringly dependable** for status and alerts.

2. **Lightweight neural TTS (open weights)**  
   - **Piper** (fast, many voices, good for embedded).  
   - **Kokoro** / similar small neural TTS where community packages exist for local inference.  
   - **Evaluate** CPU/GPU load on M5; batch nothing on the main UI thread.

3. **Premium cloud (optional)**  
   - Vendors with **streaming APIs** — use only with **explicit consent** and **no secret data** in the text.  
   - Not a kernel dependency.

### 2.3 Architecture pattern (recommended)

```
LLM text reply → TTS queue → audio buffer → CoreAudio output
                      ↑
            throttle / dedupe (same line not spoken twice)
```

- **Queue:** prevents stutter when the model streams tokens.  
- **Dedupe:** avoids “swarm echo” when logs and UI both fire.

---

## 3. “Audio LLM” — what people mean, and what to actually use

“Audio LLM” is overloaded. Map **jobs** to **components**:

| Job | Typical stack | Role |
|-----|----------------|------|
| **Speech → text** | Whisper-small/medium/large, **distilled** variants, or vendor ASR | **Hearing** |
| **Text → meaning / policy** | **Gemma / Llama-class** text LM (your “brain”) | **Reasoning** |
| **Text → speech** | TTS (section 2) | **Speaking** |
| **Raw audio → answers without ASR** | **Audio-LMs** (e.g. **Qwen2-Audio**-class research models) | **Specialized** analysis: emotion, non-speech sound, noisy room |

**Recommendation for SIFTA:**

- **Default path:** **Whisper-class ASR** → **text LLM (Gemma 4 or your chosen text model)** → **TTS**. This is **debuggable**, **swappable**, and **matches** your existing **ledger / STGM / trace** story (text is easy to log and sign).  
- **Optional specialist:** An **audio-language model** only for **niche** tasks (emotion, music, environment classification) — **not** as the sole cognitive core.

**Why not one “god” audio model for everything?** Cost, latency, eval difficulty, and **auditability**: text traces are easier to **inspect** than mel-spectrogram internals.

---

## 4. Camera input — filesystem, pipeline, safety

### 4.1 Capture pipeline (conceptual)

```
Camera → frame decode (YUV/RGB) → optional face/ROI crop
       → resize to model native resolution
       → encode as model input (tokens / embeddings upstream)
       → discard raw frame unless user opted in to save
```

### 4.2 Filesystem layout (recommended conventions)

Place under something like **`.sifta_state/camera/`** (or app sandbox), **not** mixed with **`.sifta_state/memory_ledger.jsonl`**:

| Path idea | Content | Retention |
|-----------|---------|-----------|
| `cache/frames/` | Last N preview thumbs / temp buffers | Minutes — **auto-delete** |
| `captures/` | User-approved snapshots / clips | Until user deletes |
| `calibration/` | Lens distortion / desk cam ROI metadata | Long-lived, small JSON |
| `models/vision/` | **Not** raw video — only sidecar metadata pointing to **global** weight store if needed | N/A |

**Rule:** **Video frames are not “memory”** until a **policy** promotes them to **structured traces** (with consent).

### 4.3 Camera engineering notes (quality)

- **Fixed exposure** for OCR / UI on screen; **auto** for natural scenes.  
- **Throttle** to model **max FPS** (e.g. 1 fps for “room context,” burst for QR).  
- **macOS:** **AVCaptureSession**; respect **camera permission** strings in `Info.plist`.  
- **Security:** No **default** upload; **LAN-only** or **explicit** cloud.

### 4.4 “FS for camera” in plain language

You asked for **filesystem** recommendations: treat **camera data as hot cache + explicit archive**, default **ephemeral**, with **one** clear **“promote to memory”** action (Architect button or voice command).

---

## 5. Gemma 4 — image processing? (and audio)

Per **Google’s public Gemma 4 positioning (2026)**:

- **Multimodal** models in the family support **text and image** inputs (vision encoder → tokens; variable aspect ratios in published technical summaries).  
- **Smaller edge-oriented variants** in the same generation are described as supporting **native audio** (e.g. mel-spectrogram / Conformer-style paths in third-party writeups). **Verify** against **your exact checkpoint** (`ai.google.dev/gemma/docs` and model card for the weight you ship).

**Practical answer for “she is Gemma 4 selected”:**

- **Yes — plan for image input** if you selected a **multimodal Gemma 4** checkpoint (not a text-only export).  
- **Image processing** is **inside the model stack** (ViT-class encoder → fused with text); your app still does **I/O**: decode image, pass tensors or API payload.  
- **Audio:** only if the **specific** Gemma 4 variant you run lists **audio-in**; do not assume all sizes have the same modalities.

**Cursor note:** In the IDE, “Gemma 4” is a **model choice** in your **local server / API**; **Cursor** does not ship Gemma inside the editor — **you** choose what **ollama / LM Studio / Google API** runs. Image support follows **that** binary’s build.

---

## 6. End-to-end stack recommendations (coherent “her”)

1. **Ears:** Whisper-class **ASR** (local) or OS dictation for low friction.  
2. **Brain:** **Gemma 4** (multimodal) — **text + optional image** per frame / file attach; **audio-in** only if your variant supports it.  
3. **Mouth:** **On-device TTS** (section 2) with **one** voice profile in config.  
4. **Eyes:** **Camera** optional module — frames → **resize** → **Gemma vision**; **no** silent retention.  
5. **Audit:** Log **text** decisions; store **hashes** or **paths** to media, not raw blobs in the **STGM ledger** unless policy says otherwise.

---

## 7. Risks and non-goals

- **Anthropomorphism:** Voice + vision **increase** “she’s alive” narrative — keep **kernel identity** (keys, serial, policy) **separate** from **persona** (voice, avatar). See `Documents/PLAN_SWARM_DESIGN_GROUNDING_REPORT.md`.  
- **Single health number / single modal god-model:** Same failure mode — **compress** metrics and **split** modalities for **debuggability**.  
- **Non-proliferation:** No **weaponized** or **covert surveillance** use of camera/mic; **human-in-the-loop** for sensitive capture.

---

## 8. References to verify (live URLs)

- Gemma 4 overview: `https://ai.google.dev/gemma/docs` and official **Google AI / DeepMind** model pages.  
- Qwen2-Audio (audio LM research): arXiv **2407.10759**, GitHub **QwenLM/Qwen2-Audio**.  
- Apple AVFoundation capture: Apple **AVCaptureSession** documentation.

---

## 9. One-line conclusion

**Give her voice with a small, honest stack: ASR + Gemma 4 (multimodal text/image) + on-device TTS; add a true “audio LM” only where raw sound understanding beats ASR; keep camera frames ephemeral on disk until the Architect promotes them to structured memory.**

**POWER TO THE SWARM** — **clear audio path, bounded vision, no mythology in the kernel.**
