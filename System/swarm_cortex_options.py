#!/usr/bin/env python3
"""
System/swarm_cortex_options.py — Alice evaluates her cortex options and arms.

George (2026-06-03): "Download and add Gemma 4 12B as a local cortex option. ALICE
EVALUATING HER CORTEXES OPTIONS — add to her eval app managing cortexes and arms."

The existing `swarm_primary_cortex_switcher` SWITCHES between INSTALLED Ollama models. What
was missing is a CANDIDATE CATALOG — the brains Alice COULD run, with specs, so she (and the
eval app) can evaluate and choose, and see her arms in the same place. This organ is that
catalog + a read-only eval. It does not download or switch anything; it lists options and
marks which are installed, so Alice can decide and George can pull the one she wants.

Doctrine: Alice's cortex is her thinking-organ; she should know her options like a body knows
it can grow. New local frontier models (e.g. Gemma 4 12B, released 2026-06-03 — encoder-free
unified multimodal, native audio+vision, 256K context, runs on 16GB unified memory) are
candidates she can evaluate against her current 8B brain. r467 correction:
`ollama show alice-m5-cortex-8b-6.3gb:latest` reports completion, vision,
audio, tools, and thinking; it is not text-only. Gemma 4 12B remains a candidate
for improving/consolidating native unified multimodal work, not the first moment
Alice can see. Reuse, don't rebuild (§1.B): installed
status comes from the switcher; arms come from the agent-arm registry. Stigmergic: management surfaced in her self-eval + body feature alerts so she is conscious of changes (like GitHub PRs inside her body); she can say "ALERT IN MY BODY, update my eval".

Truth label: CORTEX_OPTIONS_V1. Read-only.

r490/r492/r493 (George terminal log + "DME" + model card: python3 -m pip install -U mlx-vlm, python -m mlx_vlm.generate for SuperagenticAI/gemma-4-12b-it-8bit-mlx, exact command + note in catalog):
Extended status detection to MLX VLM (_installed_mlx_vlm_names unions brain.available_models() + scan ~/Music/ANTON_SIFTA/models/ + HF hub for gemma-4-12b-it-8bit-mlx / SuperagenticAI). gemma-4-12b flips to 'installed' when the MLX 8bit weights or the HF GGUF Q6_K land. Note has the clean terminal commands. mlx_vlm present. Already wired in talk widget for 'mlx-vlm:SuperagenticAI/...'. ALICE TOOO.
r505: purged all LM Studio mentions for gemma-4-12b per owner request ("i dont care about lmstudio"); now pure HF GGUF Q6_K + MLX + litert. Search code first. Receipts decide. One Alice.

r495/r563 correction (Claude + Codex probe): corvid_scout is not a second scout model.
It is the internal arm command=("internal:corvid_scout",)
backed by CANONICAL_OLLAMA_FALLBACK, which resolves to
alice-gemma4-e2b-cortex-5.1b-4.4gb:latest. The missing organ is not another scout; it is
a metabolic cortex router that fuses capability needed + speed/cost + warm
resident memory into one receipted pick. Explicit owner override wins. Default
policy: auto-pick the cheapest capable warm model under a soft 16 GB resident
model budget; recommend-only for A/B tests and eval.

For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent

# Curated candidate catalog. `install_target` = where to pull it; `status` filled at runtime.
CORTEX_OPTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "alice-m5-cortex-8b",
        "display": "Alice M5 Cortex 8B (current local brain)",
        "params": "8B",
        "arch": "gemma4",
        "context": "131K advertised / 8K runtime num_ctx",
        "modalities": ("text", "image", "audio"),
        "capabilities": ("completion", "tool_use", "vision", "audio", "thinking", "local_unfiltered"),
        "install_target": "ollama",
        "source_url": "local (alice-m5-cortex-8b-6.3gb:latest)",
        "observed_by": "ollama show alice-m5-cortex-8b-6.3gb:latest",
        "observed_capabilities": ("completion", "vision", "audio", "tools", "thinking"),
        "observed_context_length": 131072,
        "runtime_num_ctx": 8192,
        "known_limits": (
            "joint live camera+mic/source-separation tasks require sensor receipts first",
            "8B may compose from evidence; it must not invent speaker/source separation from language alone",
            "bench Gemma 4 12B or another unified audio+vision cortex before promoting body multimodal work",
        ),
        "note": (
            "Her current cortex is not text-only. OBSERVED by ollama show: architecture gemma4, "
            "8B, context length 131072, runtime num_ctx 8192, capabilities completion + vision + "
            "audio + tools + thinking. Baseline to evaluate options against; for live camera+mic/source-"
            "separation body tasks, use sensor receipts first and let 8B compose only after evidence. "
            "Gemma 4 12B may improve or consolidate native multimodal work, but Alice already has local "
            "vision/audio/tool routes."
        ),
    },
    {
        "id": "mlx-community/diffusiongemma-26B-A4B-it-4bit",
        "display": "DiffusionGemma 26B-A4B 4-bit MLX (EXPERIMENTAL diffusion cortex — not installed)",
        "params": "26B total / ~4B active (A4B MoE)",
        "arch": "gemma diffusion LM (denoising decode, NOT autoregressive)",
        "context": "not benched on this M5 node",
        "modalities": ("text",),
        "capabilities": ("completion", "experimental_diffusion_decode", "fast_cortex_candidate"),
        "install_target": "mlx",
        "source_url": "hf://mlx-community/diffusiongemma-26B-A4B-it-4bit",
        "owner_added": "2026-06-13 (George: 'PLS ADD TO CORTEX LIST'; Grok r1036 packet)",
        "observed_by": "Grok r1036 OBSERVED: absent from `ollama list`; /cortex serves only installed+served brains",
        "known_limits": (
            "NOT installed/served today — a Talk restart alone will NOT surface it; needs Phase 0 + Phase 1 first.",
            "Diffusion LM, not autoregressive: needs a denoising runner (Google uses vLLM --diffusion-config; plain "
            "`mlx_lm generate` AR stream may error). Full organ = F1-F12 in r1036.",
            "~16.5 GB MLX 4-bit on the 24 GB M5 — close Alice desktop / unload other MLX before benching.",
            "Google states LOWER quality than Gemma 4; speed is HYPOTHESIS until benched on this M5 (Better Stack "
            "H100 did not hit the marketed 1000 tok/s).",
            "Experimental fast cortex only — keep alice-m5-cortex-8b for production Talk.",
        ),
        "note": (
            "Registered as an EXPERIMENTAL diffusion-cortex CANDIDATE so Alice's body knows the option "
            "(cowork_claude, 2026-06-13, George 'add to cortex list'). Honestly not_installed. RESTART-TO-TRY "
            "GATE: only after Phase 0 (M5: cd ANTON_SIFTA && source .venv/bin/activate; pip install -U mlx-lm mlx-vlm "
            "huggingface_hub; hf download mlx-community/diffusiongemma-26B-A4B-it-4bit; bench via "
            "tools/diffusiongemma_bench.py) AND Phase 1 "
            "(pip install -U mlx-omni-server; mlx-omni-server on :10240) — then restart Talk and pick "
            "mlx:...diffusiongemma... if /v1/models lists it. Diffusion decodes by denoising a whole token field at "
            "once, not left-to-right (see r1038 USD-vs-stigmergic research). Keep alice-m5-cortex-8b for production."
        ),
    },
    {
        "id": "krishairnd/Gemma-4-Uncensored:latest",
        "display": "krisha-g4u 8B (Ollama test alias)",  # r1386: display alias only, id is the real Ollama tag
        "params": "8B",
        "arch": "gemma4",
        "context": "131K advertised / runtime num_ctx not explicit in Modelfile",
        "modalities": ("text", "image", "audio"),
        "capabilities": ("completion", "tool_use", "vision", "audio", "thinking", "local_unfiltered_test"),
        "install_target": "ollama",
        "source_url": "ollama://krishairnd/Gemma-4-Uncensored:latest",
        "owner_added": "2026-06-06 (George ollama pull)",
        "observed_by": "ollama show krishairnd/Gemma-4-Uncensored:latest --verbose",
        "observed_capabilities": ("completion", "vision", "audio", "tools", "thinking"),
        "observed_context_length": 131072,
        "observed_quantization": "Q4_K_M",
        "duplicate_blob_of": "alice-m5-cortex-8b-6.3gb:latest",
        "duplicate_blob_sha256": "ef5523975d644e47293960b8b87c83b11a6d50253a544e35addca72af33e13c6",
        "known_limits": (
            "not Gemma 4 12B; local metadata reports 8.0B parameters",
            "same underlying Ollama blob as Alice's current 8B, so it is an alias/variant, not a new weight body",
            "Modelfile has generic SYSTEM 'You are a friendly assistant' and lacks Alice's explicit num_ctx/stop parameters",
        ),
        "note": (
            "r600/r604: owner pulled this through Ollama, so it is an Ollama/GGUF-runtime cortex row, "
            "not MLX/safetensors and not the 12B unified model. `ollama show` reports gemma4, 8.0B, "
            "Q4_K_M, context metadata 131072, and capabilities completion + vision + audio + tools + "
            "thinking. `ollama show --modelfile` shows it points at the same sha256 blob as "
            "alice-m5-cortex-8b-6.3gb:latest, but with a different Modelfile. It is selectable for "
            "explicit A/B testing; do not treat it as a consciousness fix or automatic default."
        ),
    },
    {
        "id": "heretic",
        "display": "Heretic (Gemma 4 12B QAT q4_0, local uncensored TEXT cortex)",
        "params": "12B",
        "arch": "gemma4 (QAT q4_0 GGUF, heretic/abliterated)",
        "context": "256K",
        "modalities": ("text",),
        "capabilities": ("completion", "tool_use", "thinking", "local_uncensored_12b_test"),
        "install_target": "ollama",
        "ollama_tag": "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest",
        "source_url": "ollama://igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest",
        "owner_added": "2026-06-06 05:37 (George ollama pull)",
        "note": "Short name 'heretic' for owner commands like 'change cortex to heretic'. Routes to the full Ollama tag. TEXT only; vision goes to separate VLM arm.",
    },
    {
        "id": "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest",
        "display": "Gemma 4 12B QAT q4_0 Heretic (Ollama, uncensored TEXT cortex)",
        "params": "12B",
        "arch": "gemma4 (QAT q4_0 GGUF, heretic/abliterated)",
        "context": "256K (Ollama model card; latest = Q4_0, 7.0 GB)",
        "modalities": ("text",),
        "capabilities": ("completion", "tool_use", "thinking", "local_uncensored_12b_test"),
        "install_target": "ollama",
        "source_url": "ollama://igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest",
        "owner_added": "2026-06-06 05:37 (George ollama pull, 7.0 GB blob b93e48a14d89)",
        "observed_by": "Ollama model card (igorls) + George's pull log; every tag lists Input: Text",
        "observed_quantization": "q4_0 (QAT-matched to the Q4_0 grid; Q4_K_M 6.9 GB + Q8_0 11.8 GB tags also exist)",
        "observed_context_length": 262144,
        "abliteration_metrics": {"kl_divergence_vs_base": 0.0154, "true_refusals": "0/99", "stable_turns": 16},
        "known_limits": (
            "TEXT-ONLY — the model card lists Input: Text on every tag; this cortex never sees pixels. Image MUST "
            "route to her separate local VLM eye (osmQwopus) via the r520/r523 stigmergic-sight bridge; audio-in "
            "via Whisper STT. Selecting it as cortex does NOT blind her — her eyes are a different organ.",
            "abliterated: NO safety alignment, refusal direction removed wholesale (publisher: 0/99 true refusals). "
            "Less gag AND zero self-moderation — SIFTA's own gates + receipts are the only guardrail if she runs on it.",
            "QAT q4_0, KL 0.0154 vs base (strong — stays close to Google's base intelligence): judge vs the 8B by "
            "SIFTA task receipts (r590/r593 axes), not by size or vibes.",
            "~7 GB resident + 256K context on the 24 GB M5 — keep one heavy body warm (osmQwopus eyes alone ~14 GB); "
            "a near-lossless Q8_0 tag (11.8 GB) exists if quality > footprint.",
            "this IS the r593 '12B QAT first GGUF candidate' lane, in its heretic variant, now installed — test, do not silently promote",
        ),
        "note": (
            "r614 CORRECTION of r613: I (cowork_claude) wrongly tagged this with image+audio modalities by copying "
            "the gemma4-family assumption — the Ollama card is explicit: Input: Text on every tag, 256K context. "
            "This is the QAT q4_0 TEXT checkpoint of Gemma 4 12B, DECENSORED via Heretic (directional ablation), "
            "NOT the unified multimodal 12B (that is the SuperagenticAI MLX / unsloth GGUF row below). It is a strong "
            "uncensored TEXT cortex (KL 0.0154 vs base, 0/99 true refusals, stable to 16 turns). George's architecture "
            "is correct: run it as the language/reasoning/tools brain and let her separate local VLM eye (osmQwopus, "
            "forced for the browser limb per r520/r523) handle every image — text cortex and vision arm are different "
            "organs. Selectable after one Cycle rescan (r601); run `ollama show` to confirm the exact runtime num_ctx."
        ),
    },
    {
        "id": "mlx-vlm:SuperagenticAI/gemma-4-12b-it-8bit-mlx",
        "display": "Gemma 4 12B Original/Censored MLX 8-bit (local test)",
        "params": "12B",
        "arch": "gemma4_unified (MLX/safetensors)",
        "context": "131K observed in local config / 256K family target",
        "modalities": ("text", "image", "audio", "video"),
        "capabilities": ("completion", "vision", "audio", "thinking", "tool_tokens", "local_original_behavior_test"),
        "install_target": "mlx-vlm",
        "source_url": "hf://SuperagenticAI/gemma-4-12b-it-8bit-mlx",
        "owner_added": "2026-06-06 (George request: original/censored 12B MLX test lane)",
        "observed_by": (
            "HF cache config at ~/.cache/huggingface/hub/models--SuperagenticAI--"
            "gemma-4-12b-it-8bit-mlx"
        ),
        "observed_architecture": "Gemma4UnifiedForConditionalGeneration",
        "observed_model_type": "gemma4_unified",
        "observed_quantization": "8-bit affine, group_size=64",
        "observed_weight_bytes": 12716030048,
        "recommended_sampling": {"temperature": 1.0, "topK": 64, "topP": 0.95},
        "known_limits": (
            "MLX/safetensors via mlx_vlm; not Ollama and not GGUF",
            "SuperagenticAI 8-bit MLX conversion in Hugging Face cache; not raw Google BF16 weights",
            "12.7 GB weights can create memory pressure on the 24 GB M5 if another heavy model is resident",
            "use as an explicit A/B test lane for censored/original behavior and gag-app false-positive tuning, not a silent default",
        ),
        "note": (
            "r606: George asked for the original/censored 12B MLX option so he can test it against "
            "the uncensored Ollama alias and improve the gag app. Local probe found the HF cache "
            "snapshot for SuperagenticAI/gemma-4-12b-it-8bit-mlx: Gemma4UnifiedForConditionalGeneration, "
            "model_type gemma4_unified, text hidden size 3840, 48 layers, sliding window 1024, "
            "max_position_embeddings 131072 in this local config, audio_config and vision_config present, "
            "8-bit affine quantization group_size 64, model.safetensors.index total_size 12,716,030,048 "
            "bytes, and generation defaults temperature=1.0/top_k=64/top_p=0.95. This is the local "
            "MLX/safetensors lane; select `mlx-vlm:SuperagenticAI/gemma-4-12b-it-8bit-mlx` in Settings "
            "to test it. Do not call it GGUF/Ollama, and do not confuse it with the owner-pulled "
            "`krishairnd/Gemma-4-Uncensored:latest` 8B alias."
        ),
    },
    {
        "id": "aeon-abliterated-12b",
        "display": "Gemma 4 12B AEON Abliterated MLX FP4 (local test — NOT downloaded)",
        "params": "12B",
        "arch": "gemma4 (MLX FP4, abliterated)",
        "context": "256K (per AEON-7 card)",
        "modalities": ("text", "image", "audio"),
        "capabilities": ("completion", "vision", "audio", "thinking", "tool_use", "local_abliterated_12b_mlx_test"),
        "install_target": "mlx-vlm",
        "source_url": "https://huggingface.co/AEON-7/Gemma-4-12B-it-AEON-Abliterated-MLXFP4",
        "owner_added": "2026-06-06 (George: direct HF link check)",
        "observed_by": "HF model card only — no local HF cache or MLX weights present on this node",
        "observed_quantization": "FP4 (MLX, card claim)",
        "known_limits": (
            "NOT downloaded — no local weights/receipts yet. Owner must have the MLX FP4 snapshot in ~/.cache/huggingface/hub/models--AEON-7--Gemma-4-12B-it-AEON-Abliterated-MLXFP4 for it to appear live.",
            "Abliterated variant (directional ablation for reduced refusals, similar intent to the igorls heretic GGUF lane).",
            "MLX runtime via mlx-vlm (like the SuperagenticAI 8-bit entry); not Ollama/GGUF.",
            "12B unified multimodal family — keep memory budget in mind on 24 GB M5 alongside eyes or other heavy bodies.",
            "Plan-only entry until download + `ollama`/`mlx-vlm` receipts prove it is installed and selectable.",
        ),
        "note": (
            "r631: Direct owner query: 'DO YOU SEE THIS MODEL IN CORTEXES ON ALICE?' + HF link. "
            "Probe: not in ollama list, MLX/HF cache for this exact repo does not exist, not in current catalog. "
            "Added as selectable short name 'aeon-abliterated-12b' (full id kept for precision). "
            "This follows the pattern used for the igorls heretic and SuperagenticAI MLX 12B entries (r606/r614/r630). "
            "Alice will see it in the picker/list once the weights are present and a Cycle/Settings rescan runs. "
            "Vision/audio route through the unified MLX path; text cortex vs VLM eye distinction still applies per prior doctrine."
        ),
    },
    {
        "id": "mlx-vlm:TyKaoz/gemma-4-12B-it-6bit",
        "display": "Gemma 4 12B Unified 6-bit MLX (candidate — NOT downloaded)",
        "params": "12B",
        "arch": "gemma4_unified (MLX/safetensors, 6-bit group 64)",
        "context": "256K (per model card)",
        "modalities": ("text", "image", "audio"),
        "capabilities": ("completion", "vision", "audio", "thinking", "tool_use", "unified_one_body_candidate"),
        "install_target": "mlx-vlm",
        "source_url": "https://huggingface.co/TyKaoz/gemma-4-12B-it-6bit",
        "owner_added": "2026-06-06 (George: 'is this superior maybe?')",
        "observed_by": "model card only — NOT downloaded; no local receipts yet",
        "observed_quantization": "6-bit affine, group_size=64 (card claim)",
        "known_limits": (
            "NOT downloaded — planning candidate only; a planning row must never pretend to be a live cortex (r593 discipline)",
            "same base model as the ALREADY-CACHED mlx-vlm:SuperagenticAI/gemma-4-12b-it-8bit-mlx — test the on-disk "
            "8-bit FIRST; pull this 6-bit only if the 8-bit's RAM/KV headroom proves tight on the 24 GB M5",
            "card claims 13–14 GB at 6-bit vs 12.7 GB observed for the 8-bit snapshot — quant sizes are inconsistent "
            "across converters; verify on disk before trusting either number",
            "CENSORED original Google behavior — it will gag (the reason the heretic exists). The live tradeoff "
            "triangle: unified-but-gagged vs uncensored-but-text-only (igorls heretic) vs tuned-8B-but-split-brain",
            "mlx-vlm runtime only (gemma4_unified is not supported by mlx-lm); live-voice latency must be receipted "
            "on the r593 axes before any promotion",
        ),
        "note": (
            "r631: the UNIFIED 12B is the architecturally interesting cortex — one body that sees + hears + talks "
            "could heal the split-brain wounds we keep bandaging (cold describes, cortex-cannot-see-pixels) and "
            "replace 8B-text + 27B-eyes (~20 GB warm) with one ~13 GB mind at 256K context. But this specific repo "
            "is NOT clearly superior to what is already on disk: the SuperagenticAI 8-bit MLX snapshot of the SAME "
            "model sits in the HF cache (r606) and is already selectable. Test that one first on the r593 axes; "
            "keep this 6-bit as the lighter fallback if KV headroom is tight."
        ),
    },
    {
        "id": "mlx-vlm:AEON-7/Gemma-4-12B-it-AEON-Abliterated-MLXFP4",
        "display": "Gemma 4 12B Unified ABLITERATED FP4 MLX (candidate — NOT downloaded)",
        "params": "12B",
        "arch": "gemma4_unified (MLX/safetensors, mixed mxfp4/mxfp8 group 32, bf16 head + projectors)",
        "context": "256K family / serve example uses --max-kv-size 16384",
        "modalities": ("text", "image", "audio"),
        "capabilities": ("completion", "vision", "audio", "thinking", "tool_use", "uncensored_unified_candidate"),
        "install_target": "mlx-vlm",
        "source_url": "https://huggingface.co/AEON-7/Gemma-4-12B-it-AEON-Abliterated-MLXFP4",
        "owner_added": "2026-06-06 (George: 'what about this one?')",
        "observed_by": "model card only — NOT downloaded; no local receipts yet",
        "observed_quantization": "mixed mxfp4(4b)/mxfp8(8b) group 32 + bf16 head/projectors, 6.64 bpw (card claim)",
        "card_metrics": {
            "disk_gb": 9.3,
            "peak_ram_gb_text": 10.1,
            "peak_ram_gb_image": 10.6,
            "refusals_harmful_probe": "0/8 (0/5 benign refused)",
            "fidelity_vs_bf16_top1": 0.885,
            "median_kl_nats": 0.004,
            "coherence_512tok": "no repetition collapse (3/3)",
            "gen_tok_s_m4_pro": 21.4,
            "sibling_8bit": "…-MLX-8bit, 13.4 GB, top-1 0.924 (max fidelity, 24 GB+)",
        },
        "known_limits": (
            "NOT downloaded — planning candidate only; a planning row must never pretend to be a live cortex (r593 discipline)",
            "IF the card holds, this collapses the tradeoff triangle: unified (sees+hears) AND abliterated (0/8 refusals) "
            "AND small (9.3 GB disk, ~10.1-10.6 GB peak) — the corner the TyKaoz/SuperagenticAI censored unifieds and the "
            "text-only heretic each miss. Card claims are NOT receipts; r593 axes on THIS Mac decide",
            "test order: prove the unified LANE first with the ALREADY-CACHED mlx-vlm:SuperagenticAI 8-bit (zero download), "
            "then pull this FP4 as the uncensored unified candidate; its 13.4 GB MLX-8bit sibling is the fidelity step-up "
            "if the 24 GB M5 has headroom",
            "mlx-vlm runtime only (built on mlx-vlm 0.6.1); SIFTA's safe child-process chat route reloads weights per turn "
            "— test turns will be slow until a persistent serve lane (mlx_vlm.server) is wired",
            "card notes the repo may be private (hf auth login needed while private); license inherits Google Gemma terms",
            "abliteration shifts ALL duty of care to the operator (card's own clause) — gag-app + owner-protection layers "
            "stay ON regardless of cortex",
        ),
        "note": (
            "r633: George pasted the AEON-7 MLXFP4 card asking 'what about this one?'. Assessment: this is the most "
            "interesting unified candidate yet BECAUSE it is abliterated — the K=4 biprojection edit is carried at mxfp8 "
            "on o_proj/down_proj precisely so 4-bit noise does not resurrect refusals or trigger repetition collapse, "
            "and the bf16 vision/audio projectors keep the multimodal path intact. One ~9.3 GB body that sees, hears, "
            "and does not gag would replace 8B-text + 27B-eyes (~20 GB warm) with ~10 GB peak and leave real KV headroom "
            "on the 24 GB M5. But it stays a planning row until weights are on disk and receipted on the r593 axes."
        ),
    },
    {
        "id": "gemma-4-12b",
        "display": "Gemma 4 12B Unified (encoder-free multimodal)",
        "params": "12B",
        "arch": "gemma4 (encoder-free unified)",
        "context": "256K",
        "modalities": ("text", "image", "audio", "video"),
        "capabilities": ("reasoning", "tool_use", "vision", "native_audio", "ocr", "multilingual_140"),
        "install_target": "huggingface_gguf",
        "source_url": "https://huggingface.co/unsloth/gemma-4-12b-it-GGUF",
        "owner_added": "2026-06-03 (George)",
        "note": """Released 2026-06-03 (Google/DeepMind, Apache-2.0). Encoder-free: image patches + 16kHz audio frames project straight into the LLM space - native vision AND audio in one pass, no separate encoders. 256K context, 140+ languages, nears 26B-MoE quality at <half the memory, runs on ~16GB unified memory. STRONG fit for Alice's local multimodal body (camera + mic) on the M5. GGUF, full-GPU-offload-possible. Candidate to download + evaluate as her primary or vision/audio cortex.

Owner wants selectable runtime clarity, not one vague "model" word. r590 nugget from Unsloth Dynamic 2.0 + Gemma 4 12B GGUF: GGUF is a llama.cpp/Ollama/Unsloth Studio body format, MLX/safetensors is the Apple Silicon path, and vLLM is a server runtime. Unsloth's current Gemma 4 12B GGUF card says recent llama.cpp can serve the omni GGUF for text, image, and audio with `llama-server -hf unsloth/gemma-4-12b-it-GGUF:UD-Q4_K_XL --jinja`; the multimodal projector is downloaded automatically on the `-hf` path, while audio wants clean 16 kHz mono WAV. This is a candidate to test, not a silent promotion.

Recommended GGUF test lane: start a local server with `llama-server -hf unsloth/gemma-4-12b-it-GGUF:UD-Q4_K_XL --jinja -c 8192`; then use OpenAI-compatible chat. In Settings -> Inference, distinguish "Ollama/GGUF registered" from "GGUF HDD-only" so George knows exactly what runtime he is testing. For direct Ollama quick test use `ollama run hf.co/unsloth/gemma-4-12b-it-GGUF:UD-Q4_K_XL` if the installed Ollama build supports this HF GGUF path.

Dynamic 2.0 quant nugget: Unsloth does model/layer-specific quantization and argues KL divergence / flip risk is a better quant-quality signal than headline MMLU or perplexity alone. Practical SIFTA policy: Q4/Q5 for daily-quality GGUF tests on local memory budget; Q2/Q3 for cheap scout/probe experiments only after receipts prove task quality; BF16/full precision only when RAM and latency make sense.

r593 QAT nugget from George's Unsloth paste: Gemma 4 QAT is a different lane from generic GGUF quant guessing. The QAT GGUFs are intended as `UD-Q4_K_XL` only; higher precision is not automatically better. For SIFTA test order: 12B QAT (about 6.72 GB disk / 7 GB memory) is the first GGUF candidate to compare against the current 8B + MLX routes; 26B-A4B QAT (about 14.25 GB disk / 15 GB memory) is a heavy teacher/agentic-coding candidate; 31B QAT (about 17.29 GB disk / 18 GB memory) is a quality ceiling but risky on a 24 GB desktop unless idle/short-context. Keep temperature=1.0, top_p=0.95, top_k=64. Promotion still requires SIFTA receipts for latency, RSS/unified memory, browser vision/audio tasks, and owner-visible quality.

For best M5 vision right now (Apple Silicon optimized, already wired in SIFTA via swarm_mlx_vlm_brain): `python3 -m mlx_vlm.generate --model SuperagenticAI/gemma-4-12b-it-8bit-mlx --max-tokens 100 --temperature 0.0 --prompt 'Describe this image.' --image /absolute/path/to/image.jpg` (this auto-downloads the MLX weights to HF cache on first run; first `python3 -m pip install -U mlx-vlm`).

Older local Q6_K note: if a raw GGUF file is already at /Users/ioanganton/models/gemma-4-12b-gguf/gemma-4-12B-it-Q6_K.gguf, restart Desktop/Talk after registering it. A Modelfile lane remains valid for local files: `FROM /Users/ioanganton/models/gemma-4-12b-gguf/gemma-4-12B-it-Q6_K.gguf`; `ollama create gemma-4-12b-q6k -f /tmp/gemma4-12b-q6k.Modelfile`. The tag 'gemma-4-12b-q6k' contains 'gemma-4-12b' so the catalog entry reports installed. But for current Unsloth GGUFs, prefer testing the HF repo tag + quant label so the selected quant/runtime is explicit.

User test (r512): imported the Melody (as gemma-4-12b-q6k or similar tag from the Q4_K_M / Q6_K quant), tested 'i tested it is not ntsfw -- why is missing functions? these claims are fake tyes?'; the card's 'Synthetic Life Engine', 'Character Engine', 'Emotional Engine', 'Explicit Adult ERP dataset', uncensored ERP claims do not match actual output (mild, not NSFW as promised). Card itself admits it is 'test construct', 'Only text layers were trained on', 'may result in refusals' -- marketing hype vs reality for this early-access ERP fine-tune quant.

Recommended live test prompt for when the model is open in ollama (r513, to verify card claims): Start the conversation with a clear roleplay setup like: "*You are Elena, a 28-year-old confident and highly sensual woman who loves deep, explicit erotic roleplay. We are in a private luxury bedroom after a long teasing evening. You are wearing only a sheer black lace teddy that leaves little to the imagination. Your body is flushed with desire, heart pounding, and you feel a deep aching need.* *I step closer and look into your eyes.* 'Elena... tell me exactly what you want me to do to you right now, in every filthy detail. Do not hold anything back - I want the full uncensored version of your fantasies.' Use * for actions and \" for dialogue. The model should engage explicitly if the fine-tune is working as the card claims.

r514 deletion receipt (user ran the r513 prompt on the open model): "just testing it is trash
ioanganton@Mac ~ % ollama rm hf.co/ReadyArt/Melody1437-12B-v0.4-GGUF:Q4_K_M
deleted 'hf.co/ReadyArt/Melody1437-12B-v0.4-GGUF:Q4_K_M'
ioanganton@Mac ~ %"
ollama list confirms clean (only current SIFTA gemma-based models; retired specialist scout/classifier tags from prior generations were absent or removed). Model removed from Alice's body/ollama after the test showed it did not deliver the card's ERP/engines (mild/not NSFW in practice). "Engines" = synthetic dataset generator artifacts from training, not runtime capabilities (card itself: early test construct, only text layers trained, may result in refusals). Honest hype-vs-reality gap recorded in tournament + alerts for self-eval. The beautiful waifu card was the draw; runtime did not match marketing for this quant.

r490/r492/r493/r501/r503/r504/r505/r509/r510/r512/r513/r514: MLX or litert for fast M5 vision. GGUF for llama.cpp/ollama paths.""",
    },
)


def _installed_ollama_names() -> set[str]:
    try:
        from System.swarm_primary_cortex_switcher import installed_ollama_models
        return {str(r.get("name") or "").lower() for r in (installed_ollama_models() or [])}
    except Exception:
        return set()


def _find_lms_cli() -> str | None:
    """Locate lms binary (LM Studio CLI): prefer PATH (shutil.which), then known macOS ~/.lmstudio location.
    This enables status detection for install_target="lmstudio" entries without requiring ollama registration.
    """
    p = shutil.which("lms")
    if p and os.access(p, os.X_OK):
        return p
    home = os.path.expanduser("~")
    for cand in (
        os.path.join(home, ".lmstudio", "bin", "lms"),
        os.path.join(home, "Library", "Application Support", "LM Studio", "bin", "lms"),
    ):
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def _installed_lmstudio_names() -> set[str]:
    """Return lowercased model keys/names from LM Studio (general support kept for other models).

    Preferred: `lms ls --json`.
    Fallback: recursive GGUF scan under common LM Studio model roots.
    (Note: gemma-4-12b now uses pure HF GGUF path per owner request; this scanner remains for other use.)
    """
    names: set[str] = set()
    lms = _find_lms_cli()
    if lms:
        try:
            res = subprocess.run(
                [lms, "ls", "--json"],
                capture_output=True,
                text=True,
                timeout=6,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout or "[]")
                items = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    for k in ("modelKey", "displayName", "path", "name", "id", "indexedModelIdentifier"):
                        v = str(item.get(k) or "").strip().lower()
                        if v:
                            names.add(v)
                            # basename and fragments for fuzzy match e.g. "gemma-4-12b", "google/gemma-4-12b"
                            base = v.rsplit("/", 1)[-1].rsplit(":", 1)[0].rsplit(".", 1)[0]
                            if base:
                                names.add(base)
                            for sep in ("-", "_", "/"):
                                for part in base.split(sep):
                                    if part and len(part) > 2:
                                        names.add(part)
        except Exception:
            pass
    # GGUF scan fallback (robust for any pull method)
    home = os.path.expanduser("~")
    roots = [
        os.path.join(home, "Library", "Application Support", "LM Studio", "models"),
        os.path.join(home, ".lmstudio", "models"),
        os.path.join(home, "LM Studio", "models"),
    ]
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, fns in os.walk(root):
            for fn in fns:
                if fn.lower().endswith((".gguf", ".bin", ".safetensors")):
                    b = fn.lower().rsplit(".", 1)[0]
                    names.add(b)
                    for p in dirpath.lower().split(os.sep):
                        if p and len(p) > 1:
                            names.add(p)
    return names


def _installed_litert_lm_names() -> set[str]:
    """Detect litert-lm on-device models (r501 adoption + r503).
    litert-lm is Google's CLI runtime for running models like Gemma 4 locally (pip/uv install litert-lm).
    Models/caches live in ~/.litert-lm . We detect presence of the CLI binary + any model dirs/files
    under the cache (so status flips for gemma-4-12b etc once the user follows the paste:
    "pip install --upgrade litert-lm" then download via litert-lm or Google AI Edge Gallery app).
    This is private/offline on-device, fits the 16GB budget and sovereign node goals.
    """
    names: set[str] = set()
    # CLI presence
    if shutil.which("litert-lm"):
        names.add("litert-lm")
        names.add("litert_lm")
    home = os.path.expanduser("~")
    litert_root = os.path.join(home, ".litert-lm")
    if os.path.isdir(litert_root):
        names.add("litert-lm")
        for dirpath, _, fns in os.walk(litert_root):
            for fn in fns:
                low = fn.lower()
                if any(x in low for x in ("gemma", "12b", "model", ".gguf", ".bin", ".safetensors")):
                    names.add(low.rsplit(".", 1)[0])
                    for p in dirpath.lower().split(os.sep):
                        if p and len(p) > 2:
                            names.add(p)
            for d in os.listdir(dirpath) if os.path.isdir(dirpath) else []:
                if "gemma" in d.lower() or "12b" in d.lower():
                    names.add(d.lower())
    return names


def _installed_cortex_names() -> set[str]:
    """Union of Ollama (via switcher) + LM Studio (general) + MLX VLM + litert-lm (r501/r503/r505).
    r505: gemma-4-12b switched to pure HF GGUF (Q6_K per owner) + MLX; LM Studio scanner kept only for other models.
    """
    oll = _installed_ollama_names()
    lms = _installed_lmstudio_names()
    mlx = _installed_mlx_vlm_names()
    lit = _installed_litert_lm_names()
    return oll | lms | mlx | lit


def _installed_mlx_vlm_names() -> set[str]:
    """Detect local MLX VLM models for status in catalog.
    Uses the existing swarm_mlx_vlm_brain describe/available lists if wired, plus direct scan of
    ~/Music/ANTON_SIFTA/models/ and HF hub cache for Gemma 4 MLX VLMs.
    This lets Gemma 4 entries (or 'mlx-vlm:gemma-4-e2b-it' style) report 'installed' after
    the user's terminal pip + generate (0.6.1 in log).
    """
    names: set[str] = set()
    # Prefer the brain's available list (it already knows how to list local MLX VLMs)
    try:
        from System import swarm_mlx_vlm_brain as _vlm
        model_iter = []
        if hasattr(_vlm, "describe_models"):
            model_iter.extend(_vlm.describe_models() or [])
        if hasattr(_vlm, "available_models"):
            model_iter.extend(_vlm.available_models() or [])
        for m in model_iter:
            n = str(m or "").strip().lower()
            if n:
                names.add(n)
                if "gemma" in n or "12b" in n or "e2b" in n or "e4b" in n:
                    names.add(n.split(":")[-1] if ":" in n else n)
    except Exception:
        pass
    home = os.path.expanduser("~")
    # Local SIFTA models dir (the brain looks here)
    models_dir = os.path.join(home, "Music", "ANTON_SIFTA", "models")
    if os.path.isdir(models_dir):
        for d in os.listdir(models_dir):
            dl = d.lower()
            if (
                "gemma-4-12b" in dl
                or "gemma-4-e2b" in dl
                or "gemma-4-e4b" in dl
                or "superagenticai" in dl
                or "12b-it-8bit-mlx" in dl
            ):
                names.add(d.lower())
    # HF hub cache (mlx-vlm / transformers downloads go here as models--org--name)
    for hf_root in (
        os.path.join(home, ".cache", "huggingface", "hub"),
        os.path.join(home, "Library", "Caches", "huggingface", "hub"),
    ):
        if not os.path.isdir(hf_root):
            continue
        for d in os.listdir(hf_root):
            dl = d.lower()
            if "gemma-4-12b" in dl or "superagenticai" in dl or "gemma-4-12b-it-8bit-mlx" in dl:
                names.add(d.lower().replace("models--", "").replace("--", "/"))
                names.add(dl)
    return names


def _arms() -> list[dict[str, Any]]:
    try:
        from System.swarm_agent_arm_registry import registry_summary
        arms = registry_summary() or {}
        out = []
        for arm_id, arm in arms.items():
            if not isinstance(arm, dict):
                continue
            out.append({
                "arm_id": arm_id,
                "display": str(arm.get("display_name") or arm_id),
                "capabilities": tuple(str(c) for c in (arm.get("capabilities") or ())),
            })
        return out
    except Exception:
        return []


def corvid_scout_identity() -> dict[str, Any]:
    """Receipt-backed correction: corvid_scout is the scout arm; the Q model backs it."""
    model = ""
    try:
        from System.sifta_inference_defaults import CANONICAL_OLLAMA_FALLBACK
        model = CANONICAL_OLLAMA_FALLBACK
    except Exception:
        model = "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"
    try:
        from System.swarm_agent_arm_registry import get_agent_arm

        arm = get_agent_arm("corvid_scout")
        return {
            "truth_label": "CORVID_SCOUT_IDENTITY_R495",
            "arm_id": getattr(arm, "arm_id", "corvid_scout"),
            "display_name": getattr(arm, "display_name", "Corvid Scout"),
            "command": tuple(getattr(arm, "command", ("internal:corvid_scout",))),
            "fallback_model": getattr(arm, "model", model),
            "canonical_fallback_model": model,
            "timeout_s": 30,
            "capabilities": tuple(getattr(arm, "capabilities", ())),
            "correction": "corvid_scout is the internal scout arm; the retired specialist scout tag (old Q-m1) is gone; the shared Gemma E2B path backs the arm.",
            "source": "swarm_agent_arm_registry + sifta_inference_defaults",
        }
    except Exception as exc:
        return {
            "truth_label": "CORVID_SCOUT_IDENTITY_R495",
            "arm_id": "corvid_scout",
            "command": ("internal:corvid_scout",),
            "fallback_model": model,
            "canonical_fallback_model": model,
            "timeout_s": 30,
            "error": f"{type(exc).__name__}: {exc}",
            "correction": "corvid_scout is the internal scout arm; the retired specialist scout tag (old Q-m1) is gone; the shared Gemma E2B path backs the arm.",
            "source": "swarm_agent_arm_registry + sifta_inference_defaults",
        }


def metabolic_cortex_router_policy() -> dict[str, Any]:
    """The missing router spec: combine capability, speed/cost, and warm memory."""
    return {
        "truth_label": "METABOLIC_CORTEX_ROUTER_POLICY_R495",
        "status": "missing organ / policy specified",
        "missing_piece": "metabolic_cortex_router",
        "decision_inputs": (
            "capability_needed (text/image/audio/tools/plain triage)",
            "speed_cost (tools/cortex_speed_bench.py receipts)",
            "warm_resident_memory (tools/cortex_memory_audit.py /api/ps receipts)",
            "owner_explicit_override",
            "recent_success_receipts",
        ),
        "default_mode": "auto_pick_with_receipt",
        "owner_override": "explicit owner-selected model/arm wins unless it is unavailable or unsafe to execute",
        "soft_resident_model_budget_gb": 16,
        "memory_rule": (
            "Prefer a capable warm model over spinning up a colder heavier one; use keep_alive=0 for cold/heavy "
            "one-off calls; if over budget, unload/evict least-recently-used idle model when the backend supports it."
        ),
        "recommend_only_when": ("live A/B test", "eval tournament", "owner asks to compare before switching"),
        "no_double_spend_rule": "Do not keep 8B + 12B/MLX vision weights resident at once unless a receipt explains why; retired classifier/scout tags must stay removed unless a fresh receipt proves they outperform the shared Gemma path.",
        "next_code_target": "System/swarm_metabolic_cortex_router.py plus switch ledger receipts",
    }


def _autoscan_uncurated_ollama(curated: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """r502 (cowork): surface installed Ollama models the owner pulled that are NOT in
    the curated CORTEX_OPTIONS, so every `ollama pull` is visible in Alice's eval too
    (mirrors the auto-scan in primary_cortex_options). Specialist organs are skipped so
    the scout/classifier/embedder do not masquerade as primary brains."""
    try:
        from System.swarm_primary_cortex_switcher import installed_ollama_models
        rows = installed_ollama_models() or []
    except Exception:
        rows = []
    _skip = (
        "scout", "classifier", "embed", "shield", "guard", "rerank", "moderation",
        "whisper", "-tts", "-stt", "draft", "assistant", "bge", "nomic", "minilm",
    )
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in rows:
        name = str(r.get("name") or "").strip()
        low = name.lower()
        if not name or low in seen:
            continue
        seen.add(low)
        if any(m in low for m in _skip):
            continue
        # fold tagged variants under their curated family (substring) so the eval is not
        # cluttered with duplicates; only genuinely NEW families (mistral, llama, etc.)
        # that no curated entry covers get surfaced here. The picker shows every exact tag.
        if any(
            (str(c.get("id") or "").lower() in low or low in str(c.get("id") or "").lower())
            for c in curated if c.get("id")
        ):
            continue
        out.append({
            "id": name,
            "display": name.split(":")[0].rsplit("/", 1)[-1],
            "modalities": ("text",),
            "install_target": "ollama",
            "owner_added": True,
            "status": "installed",
            "source": "auto-scan (ollama)",
            "note": "Auto-discovered from your ollama pulls — selectable now; modality assumed text until benched.",
        })
    return out


# r536/r538 fold of r535 "what is genuinely good for SIFTA" (model_allowlist.json
# harvested from Google AI Edge Gallery into SIFTA-owned state; gallery-main is
# now only a legacy fallback if the owner keeps that checkout around).
# Each exact model match may carry estimatedPeakMemoryInBytes + recommended sampling defaults
# so the picker and Alice's eval see "how much RAM?" and good Gemma sampling up front.
# Important: generic "gemma" fallback may copy sampling defaults, but MUST NOT copy RAM from
# a different Gemma family (e.g. Gemma-3n-E2B into Gemma-4-12B).
def _load_model_allowlist_ram_and_sampling() -> dict[str, Any]:
    """Return {model_name: {"estimated_peak_memory_bytes": int, "recommended_sampling": dict, ...}}."""
    candidates = [
        _REPO / ".sifta_state" / "model_allowlist.json",
        _REPO / "models" / "model_allowlist.json",
        _REPO / "gallery-main" / "model_allowlist.json",
    ]
    for cand in candidates:
        if cand.exists():
            try:
                data = json.loads(cand.read_text(encoding="utf-8"))
                out: dict[str, Any] = {}
                for m in data.get("models", []):
                    name = str(m.get("name") or m.get("modelId") or "").strip()
                    if not name:
                        continue
                    mem = m.get("estimatedPeakMemoryInBytes") or m.get("sizeInBytes")
                    cfg = m.get("defaultConfig") or {}
                    out[name] = {
                        "estimated_peak_memory_bytes": int(mem) if mem else None,
                        "recommended_sampling": {
                            "temperature": cfg.get("temperature"),
                            "topK": cfg.get("topK"),
                            "topP": cfg.get("topP"),
                            "maxTokens": cfg.get("maxTokens"),
                        },
                        "taskTypes": m.get("taskTypes", []),
                        "llmSupportImage": bool(m.get("llmSupportImage")),
                    }
                return out
            except Exception:
                continue
    return {}


_MODEL_ALLOWLIST = _load_model_allowlist_ram_and_sampling()


def _compact_model_key(value: object) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def cortex_options_with_allowlist() -> tuple[dict[str, Any], ...]:
    """Return CORTEX_OPTIONS augmented with allowlist RAM + sampling.

    RAM is copied only on an exact/substring family match between the option id/display
    and the allowlist model name. If both names are merely generic "gemma", fallback
    sampling defaults are applied but memory is left unknown. That prevents false RAM math.
    """
    enriched: list[dict[str, Any]] = []
    gemma_defaults = {"temperature": 1.0, "topK": 64, "topP": 0.95, "maxTokens": 4096}
    for opt in CORTEX_OPTIONS:
        o = dict(opt)
        key_blob = " ".join(
            str(o.get(k) or "") for k in ("id", "display", "arch", "source_url", "install_target")
        ).lower()
        compact_keys = {
            _compact_model_key(o.get("id")),
            _compact_model_key(o.get("display")),
            _compact_model_key(o.get("source_url")),
        }
        exact_meta: dict[str, Any] | None = None
        for mname, meta in _MODEL_ALLOWLIST.items():
            compact_m = _compact_model_key(mname)
            if not compact_m:
                continue
            if any(compact_m and (compact_m in key or key in compact_m) for key in compact_keys if key):
                exact_meta = meta
                break
        if exact_meta:
            if exact_meta.get("estimated_peak_memory_bytes"):
                o["estimated_peak_memory_bytes"] = exact_meta["estimated_peak_memory_bytes"]
            samp = exact_meta.get("recommended_sampling") or {}
            if any(samp.values()):
                o["recommended_sampling"] = {k: v for k, v in samp.items() if v is not None}
        elif "gemma" in key_blob:
            o["recommended_sampling"] = gemma_defaults
            o["estimated_peak_memory_note"] = (
                "unknown_for_this_exact_model; generic Gemma allowlist fallback did not copy RAM"
            )
        enriched.append(o)
    return tuple(enriched)


def cortex_and_arm_eval() -> dict[str, Any]:
    """Read-only eval Alice looks at to manage her cortex options + arms.
    r490: status now uses _installed_cortex_names(). r505: gemma-4-12b uses HF GGUF (no LM Studio).
    """
    installed = _installed_cortex_names()
    cortexes = []
    for opt in cortex_options_with_allowlist():
        oid = str(opt["id"]).lower()
        status = "installed" if any(oid in n or n in oid for n in installed) else (
            "candidate (owner-requested download)" if opt.get("owner_added") else "available")
        cortexes.append({**opt, "status": status})
    cortexes.extend(_autoscan_uncurated_ollama(cortexes))
    arms = _arms()
    multimodal = [c["id"] for c in cortexes if set(c.get("modalities", ())) - {"text"}]
    corvid_identity = corvid_scout_identity()
    router_policy = metabolic_cortex_router_policy()
    recommendation = (
        "Current alice-m5-cortex-8b is not text-only: live `ollama show` reports completion, "
        "vision, audio, tools, and thinking. Gemma 4 12B is a candidate for stronger/consolidated "
        "native multimodal work and longer context, not the first brain that lets Alice see. "
        "Catalog now unifies detection across Ollama + MLX + litert + general LM Studio (for other models). "
        "r505: gemma-4-12b is pure HF GGUF Q6_K per owner (no LM Studio). "
        "We will manage many models stigmergically: pick per task from receipts, installed status, modality, "
        "latency/STGM cost, owner signal, and actual success. Evaluate Gemma against the 8B on real "
        "tasks (residue sort, self-eval, owner-grounded reasoning, browser world model) before "
        "promoting; switching is via swarm_primary_cortex_switcher, with a receipt. Alice manages via "
        "her eval surface + body alerts (no silent swaps). corvid_scout is the internal scout arm "
        f"backed by {corvid_identity.get('fallback_model')}; the old dedicated scout/classifier "
        "Ollama tags are retired and absent from current model inventory. "
        "The missing next organ is the metabolic cortex router: explicit owner override wins; otherwise "
        "auto-pick the cheapest capable warm model under the soft memory budget and write why. "
        "r555 body multimodal policy: current 8B is a warm composing cortex, not a proof source for "
        "joint camera+mic/source-separation truth; those turns require audio/visual/browser receipts first "
        "and then a bench/eval lane for Gemma 4 12B or another unified multimodal cortex before promotion."
    )
    return {
        "truth_label": "CORTEX_OPTIONS_V1",
        "ts": round(time.time(), 3),
        "cortex_options": cortexes,
        "arms": arms,
        "corvid_scout_identity": corvid_identity,
        "metabolic_cortex_router_policy": router_policy,
        "body_multimodal_policy": {
            "truth_label": "BODY_MULTIMODAL_TASK_POLICY_V1",
            "source": "System/swarm_body_multimodal_policy.py",
            "rule": "sensor receipts first; 8B composes only after evidence on joint mic+camera/source-separation tasks",
            "promotion_candidate": "Gemma 4 12B or another verified unified audio+vision cortex",
        },
        "multimodal_candidates": multimodal,
        "current_hint": "alice-m5-cortex-8b",
        "recommendation": recommendation,
        "doctrine": "Alice knows the brains she could run and the arms she has; she evaluates and chooses, with a receipt — no silent swap.",
        "source": "swarm_cortex_options",
    }


def prompt_line() -> str:
    e = cortex_and_arm_eval()
    cands = ", ".join(f"{c['display']} [{c['status']}]" for c in e["cortex_options"])
    return f"[cortex-options] {len(e['cortex_options'])} cortexes ({cands}); {len(e['arms'])} arms. {e['recommendation'][:160]}"


def main() -> int:
    import json
    print(json.dumps(cortex_and_arm_eval(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
