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
        "id": "gemma-4-12b",
        "display": "Gemma 4 12B Unified (encoder-free multimodal)",
        "params": "12B",
        "arch": "gemma4 (encoder-free unified)",
        "context": "256K",
        "modalities": ("text", "image", "audio", "video"),
        "capabilities": ("reasoning", "tool_use", "vision", "native_audio", "ocr", "multilingual_140"),
        "install_target": "huggingface_gguf",
        "source_url": "https://huggingface.co/lmstudio-community/gemma-4-12B-it-GGUF",
        "owner_added": "2026-06-03 (George)",
        "note": """Released 2026-06-03 (Google/DeepMind, Apache-2.0). Encoder-free: image patches + 16kHz audio frames project straight into the LLM space - native vision AND audio in one pass, no separate encoders. 256K context, 140+ languages, nears 26B-MoE quality at <half the memory, runs on ~16GB unified memory. STRONG fit for Alice's local multimodal body (camera + mic) on the M5. GGUF, full-GPU-offload-possible. Candidate to download + evaluate as her primary or vision/audio cortex.

Owner wants Q6_K (~9.79 GB). Pure terminal (no LM Studio): Robust pure-python (no CLI, works even if huggingface-cli not in PATH): `python3 -c 'from huggingface_hub import snapshot_download; import os; snapshot_download(repo_id="lmstudio-community/gemma-4-12B-it-GGUF", local_dir=os.path.expanduser("~/models/gemma-4-12b-gguf"), allow_patterns=["*Q6_K.gguf"]); print("Q6_K download complete")'` (huggingface_hub already present per your run; this bypasses all PATH/CLI module issues; local_dir_use_symlinks deprecated/ignored).

For best M5 vision right now (Apple Silicon optimized, already wired in SIFTA via swarm_mlx_vlm_brain): `python3 -m mlx_vlm.generate --model SuperagenticAI/gemma-4-12b-it-8bit-mlx --max-tokens 100 --temperature 0.0 --prompt 'Describe this image.' --image /absolute/path/to/image.jpg` (this auto-downloads the MLX weights to HF cache on first run; first `python3 -m pip install -U mlx-vlm`).

After download (the Q6_K file is at /Users/ioanganton/models/gemma-4-12b-gguf/gemma-4-12B-it-Q6_K.gguf from your ls), restart Desktop/Talk. To register the GGUF in ollama (so it appears in `ollama list` and the gemma-4-12b catalog entry flips to installed via r502 autoscan): use this exact one-liner (copy only the command lines, not the comments): ollama create gemma-4-12b-q6k -f <(echo "FROM /Users/ioanganton/models/gemma-4-12b-gguf/gemma-4-12B-it-Q6_K.gguf"). Or with a Modelfile for cleanliness (project style like alice-phc-cure): cat > /tmp/gemma4-12b-q6k.Modelfile << 'EOM'
FROM /Users/ioanganton/models/gemma-4-12b-gguf/gemma-4-12B-it-Q6_K.gguf
EOM
ollama create gemma-4-12b-q6k -f /tmp/gemma4-12b-q6k.Modelfile. The tag 'gemma-4-12b-q6k' contains 'gemma-4-12b' so the catalog entry will report installed. Then run `ollama list` to confirm.

Note: GGUF from this repo is text-only in many runtimes (as seen in your chat UI 'This model does not support images' for the q6k). For vision on M5, use the MLX version (SuperagenticAI/gemma-4-12b-it-8bit-mlx) wired in SIFTA. For the Melody1437 NSFW text model (the beautiful waifu card you like), use ReadyArt/Melody1437-12B-v0.4-GGUF repo with similar snapshot + ollama create.

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


# r536/r538 fold of r535 "what is genuinely good for SIFTA" (model_allowlist.json from gallery).
# Each exact model match may carry estimatedPeakMemoryInBytes + recommended sampling defaults
# so the picker and Alice's eval see "how much RAM?" and good Gemma sampling up front.
# Important: generic "gemma" fallback may copy sampling defaults, but MUST NOT copy RAM from
# a different Gemma family (e.g. Gemma-3n-E2B into Gemma-4-12B).
def _load_model_allowlist_ram_and_sampling() -> dict[str, Any]:
    """Return {model_name: {"estimated_peak_memory_bytes": int, "recommended_sampling": dict, ...}}."""
    candidates = [
        _REPO / "gallery-main" / "model_allowlist.json",
        _REPO / ".sifta_state" / "model_allowlist.json",
        _REPO / "models" / "model_allowlist.json",
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
