#!/usr/bin/env python3
"""Capability-aware cortex selection for Alice turns.

This is the small reflex Alice needed after the Bonsai screenshot failure:
when a turn carries an image, she should not stay on a text-only cortex if a
vision-capable cortex is available. The selector is receipt-backed and
non-sticky by default: it chooses the right cortex for this turn without
rewriting the owner's global setting unless a caller explicitly does that.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Mapping

from System.jsonl_file_lock import append_line_locked

try:
    from System.swarm_fireworks_qwen_config import FIREWORKS_KIMI_K2P6_MODEL
except Exception:  # pragma: no cover - import-safe fallback
    FIREWORKS_KIMI_K2P6_MODEL = "accounts/fireworks/models/kimi-k2p6"

try:
    from System.sifta_inference_defaults import (
        CANONICAL_CLOUD_QWEN_PREMIUM_KIMI,
        list_available_cortexes_with_canonical_fallback,
    )
except Exception:  # pragma: no cover - import-safe fallback
    CANONICAL_CLOUD_QWEN_PREMIUM_KIMI = "qwen:accounts/fireworks/models/kimi-k2p6"

    def list_available_cortexes_with_canonical_fallback() -> list[str]:  # type: ignore
        return [CANONICAL_CLOUD_QWEN_PREMIUM_KIMI]


REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LEDGER = STATE / "cortex_need_switches.jsonl"

LOCAL_VISION_NEEDLES = (
    "vision",
    "llava",
    "bakllava",
    "moondream",
    "minicpm",
    "qwen-vl",
    "qwen2-vl",
    "qwen2.5-vl",
    "qwen2.5vl",
    "internvl",
    "phi-3.5-vision",
    "llama3.2-vision",
    # Direct MLX VLM cortexes (osmQwopus solid vision, Keye experimental) — added so
    # is_vision_capable_model("mlx-vlm:osmQwopus...") returns True for image turns / command cortex.
    "mlx-vlm",
    "qwopus",
    "keye",
    # Gemma multimodal family — George 2026-05-31 designated gemma4 as Alice's local
    # eye; gemma3 4B+ and the SIFTA gemma4-alice cortex carry a vision head.
    # r467: `ollama show alice-m5-cortex-8b-6.3gb:latest` reports completion,
    # vision, audio, tools, and thinking. Do not classify Alice's current local
    # cortex as text-only just because its tag does not contain "gemma4".
    "alice-m5-cortex",
    "alice-gemma4-e2b-cortex",
    "gemma4",
    "gemma-4",
    "gemma3",
    "gemma-3",
    "sifta-gemma4-alice",
)

CLOUD_VISION_NEEDLES = (
    "gemini:",
    "gemini-",
    "kimi-k2p6",
    "kimi-k2p7-code",
    "kimi",
    "qwen3p6-plus",
    "qwen3p7-plus",
    # r310: George set the default Cline cortex to the image-capable openai/gpt-5.4-mini
    # (Vendor/alice-cli .../builtins.ts). Recognize the real model id so Alice's DEFAULT
    # path can SEE the airdropped runway photos (r308/r309) instead of routing vision away.
    "gpt-5.4-mini",
    # r324: George selected `codex:gpt-5.5` as his cortex (sifta_inference_defaults
    # CANONICAL_CLOUD_CODEX). The codex_agent arm is native_multimodal at gpt-5.5 and receives a
    # local image PATH, so this cortex CAN decode an attached image — it must be TRIED first, with
    # local ollama only as the on-failure fallback. Recognize the model id and the codex: family.
    "gpt-5.5",
    "codex:",
    "codex-",
)

# r310: the Cline default ALIAS ("cline:cline-cli-default") resolves to that image-capable
# model in the live TS config. This flag tracks builtins.ts defaultModelId — flip to False if
# the default Cline model is ever set back to a text-only one.
CLINE_DEFAULT_VISION_CAPABLE = True


def _state_dir(state_dir: str | Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE


def _ollama_tags(*, host: str = "http://127.0.0.1:11434", timeout: float = 1.2) -> list[str]:
    try:
        req = urllib.request.Request(
            f"{host.rstrip('/')}/api/tags",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as handle:
            payload = json.loads(handle.read().decode("utf-8", errors="replace"))
    except Exception:
        return []
    out: list[str] = []
    for row in payload.get("models") or []:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or row.get("model") or "").strip()
        if name:
            out.append(name)
    return out


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out


def list_known_cortexes() -> list[str]:
    """Return local Ollama tags plus configured cloud/teacher cortex choices."""

    local = _ollama_tags()
    try:
        configured = list_available_cortexes_with_canonical_fallback()
    except Exception:
        configured = []
    return _dedupe(local + list(configured) + [CANONICAL_CLOUD_QWEN_PREMIUM_KIMI])


def is_vision_capable_model(model: str, *, require_native_image_payload: bool = False) -> bool:
    """Return whether a model should be considered useful for image turns.

    ``require_native_image_payload`` means the current transport can send image
    bytes directly. Local Ollama vision tags and Gemini REST can; CLI teachers
    may only receive an image path in the prompt.
    """

    low = str(model or "").strip().lower()
    if not low:
        return False
    local = any(needle in low for needle in LOCAL_VISION_NEEDLES)
    cloud = any(needle in low for needle in CLOUD_VISION_NEEDLES)
    gemini = low.startswith(("gemini:", "gemini-"))
    # r310: the Cline default alias resolves to the image-capable gpt-5.4-mini.
    cline_default = CLINE_DEFAULT_VISION_CAPABLE and low.startswith("cline")
    if require_native_image_payload:
        # only transports that can send raw image bytes (local Ollama vision, Gemini REST);
        # CLI teachers (cline / gpt-5.4-mini) receive an image PATH in the prompt, not bytes.
        return bool(local or gemini)
    return bool(local or cloud or gemini or cline_default)


def _keeps_selected_cloud_speaker_for_vision(model: str) -> bool:
    """Cloud provider selected by owner remains the speaking cortex.

    Some Talk transports can reason from the visual receipt/context blocks that
    Alice builds before dispatch. If we replace them with a local VLM here, the
    UI truth breaks: /cortex says the owner-picked speaker while the live worker
    waits on local silicon.
    """
    low = str(model or "").strip().lower()
    return low.startswith(("grok:", "grok-", "mimo:", "mimo-"))


def _capability_row(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "vision_capable": is_vision_capable_model(model),
        "native_image_payload": is_vision_capable_model(model, require_native_image_payload=True),
    }


def select_cortex_for_need(
    need: str,
    *,
    current_model: str = "",
    query_text: str = "",
    state_dir: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Pick a cortex for a concrete need such as ``image_pixels``.

    The output is intentionally receipt-shaped so Talk can expose it in the
    thinking pane and tests can validate the decision without running a model.
    """

    need_key = str(need or "").strip().lower()
    known = list_known_cortexes()
    if current_model and current_model not in known:
        known.insert(0, current_model)
    rows = [_capability_row(model) for model in known]

    selected = current_model
    reason = "current_model_kept"
    switched = False
    if need_key in {"image", "image_pixels", "vision", "vision_grounding"}:
        if _keeps_selected_cloud_speaker_for_vision(current_model):
            selected = current_model
            reason = "current_owner_selected_cloud_speaker_kept"
            switched = False
        elif not is_vision_capable_model(current_model):
            native = [row["model"] for row in rows if row.get("native_image_payload")]
            capable = [row["model"] for row in rows if row.get("vision_capable")]
            if native:
                selected = native[0]
                reason = "selected_native_image_payload_cortex"
                switched = selected != current_model
            elif capable:
                selected = capable[0]
                reason = "selected_vision_cortex_path_prompt"
                switched = selected != current_model
            else:
                reason = "no_vision_capable_cortex_found"

    receipt = {
        "ts": time.time(),
        "schema": "SIFTA_CORTEX_NEED_SELECTOR_V1",
        "need": need_key,
        "current_model": current_model,
        "selected_model": selected,
        "switched": switched,
        "reason": reason,
        "query_preview": str(query_text or "")[:240],
        "candidates": rows,
    }
    if write:
        try:
            path = _state_dir(state_dir) / "cortex_need_switches.jsonl"
            append_line_locked(path, json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass
    return receipt


def prompt_block_for_selection(selection: Mapping[str, Any]) -> str:
    if not selection:
        return ""
    selected = str(selection.get("selected_model") or "")
    reason = str(selection.get("reason") or "")
    current = str(selection.get("current_model") or "")
    return (
        "CORTEX NEED SELECTOR:\n"
        f"- need={selection.get('need')} current={current or '<none>'} selected={selected or '<none>'}\n"
        f"- reason={reason}; switched={bool(selection.get('switched'))}\n"
        "- If this turn includes an image, answer only from image bytes, attachment receipts, OCR, or explicit owner description. "
        "If the selected transport cannot inspect pixels, say so and use the attachment receipt boundary."
    )


# ─────────────────────────────────────────────────────────────────────────
# Attached-model capability field (George 2026-05-30)
# ─────────────────────────────────────────────────────────────────────────
# A CLI cortex/arm like Cline is not a single model — it is a runtime that
# routes to whichever provider model the owner attached to it (Cline's own
# picker showed GPT-5.5 / 5.4 / 5.4-Mini / 5.3-Codex / 5.3-Codex-Spark / 5.2).
# Alice needs the FACT of which models a given cortex can drive so she (and
# the inference UI) can pick among them instead of treating "cline" as opaque.
#
# Source-of-truth discipline (§7.10.5): the authoritative live list lives in
# the cortex's own config (~/.cline for Cline). This file holds the last
# OBSERVED snapshot with provenance + a timestamp. A live-discovery probe may
# overwrite it later via ``record_attached_models``; until then a reader must
# treat it as "last observed", not "currently live".
ATTACHED_MODELS_PATH = STATE / "cortex_attached_models.json"
_ATTACHED_SCHEMA = "SIFTA_CORTEX_ATTACHED_MODELS_V1"


def _attached_path(state_dir: str | Path | None = None) -> Path:
    base = _state_dir(state_dir)
    return base / "cortex_attached_models.json"


def load_attached_models(*, state_dir: str | Path | None = None) -> dict[str, Any]:
    """Return the whole attached-models field, or an empty shell."""
    path = _attached_path(state_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("cortexes"), dict):
            return data
    except Exception:
        pass
    return {"schema": _ATTACHED_SCHEMA, "updated_ts": 0.0, "cortexes": {}}


def _resolve_mimo_default_attached(
    current: str,
    *,
    catalog: tuple[str, ...] | None = None,
) -> str:
    """Keep owner-selected defaults only when they remain in the MiMo keep-list."""
    cur = str(current or "").strip()
    allowed = set(catalog if catalog is not None else _MIMO_ATTACHABLE_VIA_UPSTREAM)
    if cur in allowed:
        return cur
    return _MIMO_DEFAULT_ATTACHED


def _migrate_legacy_local_ollama_id(model_id: str) -> str:
    mid = str(model_id or "").strip()
    return _MIMO_LEGACY_LOCAL_OLLAMA_ALIASES.get(mid, mid)


def _migrate_legacy_mimo_attached_id(model_id: str) -> str:
    """Rewrite pruned MiMo attached rows to the current owner catalog."""
    mid = _migrate_legacy_local_ollama_id(model_id)
    if mid == "mimo-v2.5-pro-ultraspeed":
        return FIREWORKS_KIMI_K2P6_MODEL
    return mid


def _sanitize_mimo_attached_record(rec: dict[str, Any]) -> dict[str, Any]:
    """Drop pruned MiMo cloud ids and fix stale defaults on read."""
    out = dict(rec)
    models = [
        _migrate_legacy_mimo_attached_id(str(mid))
        for mid in (out.get("attached_models") or [])
        if _migrate_legacy_mimo_attached_id(str(mid)) in _MIMO_ATTACHABLE_VIA_UPSTREAM
    ]
    if not models:
        models = list(_MIMO_ATTACHABLE_VIA_UPSTREAM)
    out["attached_models"] = models
    resolved = _resolve_mimo_default_attached(
        _migrate_legacy_mimo_attached_id(str(out.get("default_attached") or ""))
    )
    out["default_attached"] = resolved
    default_label = attached_model_label(resolved)
    if default_label != resolved:
        out["default_label"] = default_label
    elif "default_label" in out and resolved == _MIMO_DEFAULT_ATTACHED:
        out["default_label"] = default_label
    if str(rec.get("default_attached") or "") in _MIMO_REMOVED_ATTACHABLE_IDS:
        out["source"] = "owner_pruned_removed_mimo_v25_pro_default_2026-06-17"
    return out


def attached_models_for_cortex(
    cortex_id: str, *, state_dir: str | Path | None = None
) -> dict[str, Any]:
    """Return the attached-models record for one cortex id, or {} if unknown."""
    data = load_attached_models(state_dir=state_dir)
    cid = str(cortex_id or "").strip()
    rec = data.get("cortexes", {}).get(cid)
    if not isinstance(rec, dict):
        return {}
    out = dict(rec)
    if cid == _MIMO_CORTEX_ID:
        out = _sanitize_mimo_attached_record(out)
    return out


def record_attached_models(
    cortex_id: str,
    models: list[str] | tuple[str, ...],
    *,
    default_attached: str = "",
    source: str = "unspecified",
    routes_any_provider: bool = False,
    picker_is_upstream: bool = False,
    live: bool = False,
    state_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Record (merge) the attached models a cortex can drive. Non-destructive
    to other cortexes. ``live=False`` marks the row as an observed snapshot;
    a live-discovery probe should pass ``live=True`` when it actually read the
    cortex's own config."""
    cid = str(cortex_id or "").strip()
    clean_models = _dedupe([str(m) for m in (models or [])])
    default = str(default_attached or (clean_models[0] if clean_models else ""))
    labels = {
        mid: label
        for mid in clean_models
        if (label := attached_model_label(mid)) != mid
    }
    descriptions = {
        mid: desc
        for mid in clean_models
        if (desc := attached_model_description(mid))
    }
    rec = {
        "attached_models": clean_models,
        "default_attached": default,
        "routes_any_provider": bool(routes_any_provider),
        "picker_is_upstream": bool(picker_is_upstream),
        "source": str(source),
        "live": bool(live),
        "recorded_ts": time.time(),
    }
    if labels:
        rec["model_labels"] = labels
    if descriptions:
        rec["model_descriptions"] = descriptions
    if default:
        default_label = attached_model_label(default)
        if default_label != default:
            rec["default_label"] = default_label
    data = load_attached_models(state_dir=state_dir)
    data["schema"] = _ATTACHED_SCHEMA
    data["updated_ts"] = time.time()
    cortexes = data.setdefault("cortexes", {})
    if not isinstance(cortexes, dict):
        cortexes = {}
        data["cortexes"] = cortexes
    cortexes[cid] = rec
    path = _attached_path(state_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    except Exception:
        pass
    return rec


# Canonical attached-model catalogs (George 2026-06-11 — Cline OAuth can bind
# Codex, Anthropic, and Grok/Composer; each cloud cortex arm has its own picker).
_CODEX_PICKER_MODELS: tuple[str, ...] = (
    "GPT-5.5",
    "GPT-5.4",
    "GPT-5.4-Mini",
    "GPT-5.3-Codex-Spark",
)
_CODEX_DEFAULT_ATTACHED = "GPT-5.3-Codex-Spark"
_ANTHROPIC_ARM_MODELS: tuple[str, ...] = (
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-opus-3",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
)
_GROK_OAUTH_MODELS: tuple[str, ...] = (
    "grok-composer-2.5-fast",
    "grok-build",
)
_MIMO_NATIVE_MODELS: tuple[str, ...] = (
    "mimo-auto",
)
# George 2026-06-20: UltraSpeed beta replaced by Fireworks Kimi K2.6 on the MiMo
# attached picker — same brain as qwen:accounts/fireworks/models/kimi-k2p6.
_MIMO_FIREWORKS_ATTACHABLE_MODELS: tuple[str, ...] = (
    FIREWORKS_KIMI_K2P6_MODEL,
)
_MIMO_LOCAL_QWEN_OLLAMA = "baytout3/Qwen3.6-27B-Uncensored-HauhauCS-Balanced:IQ4_XS"
_MIMO_LOCAL_QWEN35_MT = "kaelri/qwen3.5-mt:2b"
_MIMO_LEGACY_LOCAL_OLLAMA_ALIASES: dict[str, str] = {
    "trinhnv1205/Qwen3.5-9B-Uncensored-ctx64k:latest": _MIMO_LOCAL_QWEN_OLLAMA,
}
_MIMO_LOCAL_OLLAMA_MODELS: tuple[str, ...] = (
    "krishairnd/Gemma-4-Uncensored:latest",
    _MIMO_LOCAL_QWEN35_MT,
    _MIMO_LOCAL_QWEN_OLLAMA,
)
_MIMO_LOCAL_DIFFUSION_MODELS: tuple[str, ...] = (
    "diffusion:diffusiongemma-26b",
)
# r1386 (George 2026-06-19): default attached model must always be the
# smallest local model, not the largest. krishairnd/Gemma-4-Uncensored:latest
# is 8B; kaelri/qwen3.5-mt:2b is 1.9GB and was the smaller live default
# George had already switched to manually. This also sidesteps the
# is_unfiltered_dialogue exemption (r1385) for any model id containing
# "uncensored", since this id does not.
_MIMO_DEFAULT_ATTACHED = _MIMO_LOCAL_QWEN35_MT
_MIMO_CORTEX_ID = "mimo:mimo-cli-default"
# Owner-pruned 2026-06-17 (r1244): paid MiMo cloud natives stay off the picker.
_MIMO_REMOVED_ATTACHABLE_IDS: frozenset[str] = frozenset(
    {
        "mimo-v2.5-pro",
        "mimo-v2-flash",
        "mimo-v2-omni",
        "mimo-v2-pro",
        "mimo-v2.5",
    }
)
# Neutral shared catalog: every model attachable over an OAuth / upstream
# picker, across vendors. No cortex owns it — Cline and MiMo are equal
# consumers of the SAME source, so neither depends on the other and the two
# lists cannot drift. (r1108: MiMo is no longer defined as "Cline's list".)
_OAUTH_ATTACHABLE_MODELS: tuple[str, ...] = (
    *_CODEX_PICKER_MODELS,
    *_GROK_OAUTH_MODELS,
    *_ANTHROPIC_ARM_MODELS,
)
_MIMO_OWNER_KEPT_ATTACHABLE_MODELS: tuple[str, ...] = (
    "GPT-5.3-Codex-Spark",
    "grok-composer-2.5-fast",
    "grok-build",
    "claude-fable-5",
)
# Per-cortex names kept for back-compat with existing references/tests; both
# point straight at the neutral source above — equal siblings, no hierarchy.
_CLINE_ATTACHABLE_VIA_OAUTH: tuple[str, ...] = _OAUTH_ATTACHABLE_MODELS
_MIMO_ATTACHABLE_VIA_UPSTREAM: tuple[str, ...] = (
    *_MIMO_NATIVE_MODELS,
    *_MIMO_FIREWORKS_ATTACHABLE_MODELS,
    *_MIMO_LOCAL_OLLAMA_MODELS,
    *_MIMO_LOCAL_DIFFUSION_MODELS,
    *_MIMO_OWNER_KEPT_ATTACHABLE_MODELS,
)

_ATTACHED_MODEL_LABELS: dict[str, str] = {
    "grok-composer-2.5-fast": "Composer 2.5",
    "grok-build": "Grok Build",
    "mimo-v2.5-pro": "MiMo-V2.5-Pro",
    "mimo-v2-flash": "MiMo-V2-Flash",
    "mimo-v2-omni": "MiMo-V2-Omni",
    "mimo-v2-pro": "MiMo-V2-Pro",
    "mimo-v2.5": "MiMo-V2.5",
    FIREWORKS_KIMI_K2P6_MODEL: "Kimi K2.6 (fireworks-api kimi-k2p6)",
    "mimo-auto": "MiMo Auto (free)",
    "krishairnd/Gemma-4-Uncensored:latest": "krisha-g4u (local Ollama)",
    _MIMO_LOCAL_QWEN35_MT: "kaelri-q3.5-mt-2b (local Ollama)",
    _MIMO_LOCAL_QWEN_OLLAMA: "Qwen3.6 27B Uncensored Balanced (local Ollama)",
    "diffusion:diffusiongemma-26b": "DiffusionGemma 26B (local diffusion)",
    "claude-fable-5": "Fable 5",
    "claude-opus-4-8": "Opus 4.8",
    "claude-opus-4-7": "Opus 4.7",
    "claude-opus-4-6": "Opus 4.6",
    "claude-opus-3": "Opus 3",
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-haiku-4-5-20251001": "Haiku 4.5",
    "kimi-k2p6": "Kimi K2.6",
    "kimi-k2.6": "Kimi K2.6",
    "kimi-k2p7-code": "Kimi K2.7 Code",
    "minimax-m3": "MiniMax M3",
    "minimax-m2p7": "MiniMax M2.7",
    "qwen3p7-plus": "Qwen3.7 Plus",
    "qwen3p6-plus": "Qwen3.6 Plus",
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "deepseek-v4-flash": "DeepSeek V4 Flash",
    "glm-5p1": "GLM 5.1",
}

_ATTACHED_MODEL_DESCRIPTIONS: dict[str, str] = {
    "GPT-5.5": "Frontier model for complex coding, research, and real-world work.",
    "GPT-5.4": "Strong model for everyday coding.",
    "GPT-5.4-Mini": "Small, fast, and cost-efficient model for simpler coding tasks.",
    "GPT-5.3-Codex-Spark": "Ultra-fast coding model.",
    "grok-composer-2.5-fast": "Cursor's latest coding model.",
    "grok-build": "Best for advanced coding tasks.",
    "mimo-v2.5-pro": "Paid MiMo Token-Plan flagship observed in George's MiMo picker.",
    "mimo-v2-flash": "Legacy fast MiMo native model; vendor notice says V2-Flash auto-routes to V2.5 on 2026-06-18 GMT+8 and deprecates by June 30.",
    "mimo-v2-omni": "Omni MiMo native model observed in George's MiMo picker.",
    "mimo-v2-pro": "Pro MiMo native model observed in George's MiMo picker.",
    "mimo-v2.5": "MiMo V2.5 native model observed in George's MiMo picker.",
    FIREWORKS_KIMI_K2P6_MODEL: (
        "Kimi K2.6 on the Fireworks API — same lane as "
        "qwen:accounts/fireworks/models/kimi-k2p6 (fireworks-api kimi-k2p6)."
    ),
    "mimo-auto": "Free MiMo Auto route observed in George's MiMo picker.",
    "krishairnd/Gemma-4-Uncensored:latest": (
        "Local Ollama Gemma 4 Uncensored tag observed on GTH4921YP3: "
        "8B, Q4_K_M, 131072 context, vision/audio/tools/thinking."
    ),
    _MIMO_LOCAL_QWEN35_MT: (
        "Local Ollama kaelri/qwen3.5-mt:2b on GTH4921YP3: Qwen3.5 2.3B, Q4_K_M, "
        "262144 context, 1.9 GB, vision/tools/thinking/completion, pulled 2026-06-19."
    ),
    _MIMO_LOCAL_QWEN_OLLAMA: (
        "Local Ollama Qwen3.6 27B Uncensored HauhauCS Balanced IQ4_XS on GTH4921YP3: "
        "27.4B, 262144 context, 16 GB, digest e5630341d1d8, vision/tools/thinking, pulled 2026-06-18."
    ),
    "diffusion:diffusiongemma-26b": (
        "Experimental local DiffusionGemma / Gemma 4 26B A4B diffusion cortex. "
        "Not a MiMo native cloud model and not an Ollama tag; requires the "
        "DiffusionGemma GGUF plus the dedicated llama-diffusion-cli runner before it is runnable."
    ),
    "claude-fable-5": "For toughest challenges; owner screenshot says included until June 22.",
    "claude-opus-4-8": "For complex tasks.",
    "claude-sonnet-4-6": "Most efficient for everyday tasks.",
    "claude-haiku-4-5-20251001": "Fastest for quick answers.",
}


def attached_model_label(model: str) -> str:
    """Owner-facing picker label for a stored upstream model id."""
    mid = str(model or "").strip()
    if mid in _ATTACHED_MODEL_LABELS:
        return _ATTACHED_MODEL_LABELS[mid]
    low = mid.lower()
    if "accounts/fireworks/models/" in low:
        slug = mid.rsplit("/", 1)[-1]
        if slug in _ATTACHED_MODEL_LABELS:
            return _ATTACHED_MODEL_LABELS[slug]
        return slug
    for known in (*_CODEX_PICKER_MODELS, *_GROK_OAUTH_MODELS, *_ANTHROPIC_ARM_MODELS):
        if low.endswith(str(known).lower()):
            return _ATTACHED_MODEL_LABELS.get(str(known), str(known))
    return mid


def attached_model_description(model: str) -> str:
    """Short picker description observed from the owner's screenshots."""
    return _ATTACHED_MODEL_DESCRIPTIONS.get(str(model or "").strip(), "")


def format_attached_model(model: str) -> str:
    """Render a model without losing the machine id behind a friendly label."""
    mid = str(model or "").strip()
    label = attached_model_label(mid)
    if not mid or label == mid:
        return mid
    return f"{label} ({mid})"


def attached_model_matches_active(model: str, active: str) -> bool:
    """Truth-mark active rows even when a probe includes a provider prefix."""
    mid = str(model or "").strip().lower()
    cur = str(active or "").strip().lower()
    if not mid or not cur:
        return False
    return mid == cur or cur.endswith(mid)


def _grok_cli_model_ids() -> list[str]:
    """Best-effort read of Grok Build CLI model list. Never raises."""
    import os
    import re
    import shutil
    import subprocess

    grok_bin = os.environ.get("SIFTA_GROK_CLI", os.path.expanduser("~/.grok/bin/grok"))
    if not Path(grok_bin).exists() and not shutil.which(grok_bin):
        return list(_GROK_OAUTH_MODELS)
    try:
        proc = subprocess.run(
            [grok_bin, "models"],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
        text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    except Exception:
        return list(_GROK_OAUTH_MODELS)
    found: list[str] = []
    for line in text.splitlines():
        m = re.search(r"\b(grok-[a-z0-9][\w.-]*)\b", line, re.IGNORECASE)
        if m:
            found.append(m.group(1).lower())
    return _dedupe(found or list(_GROK_OAUTH_MODELS))


def sync_cortex_attached_models_catalog(
    *,
    state_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Probe live provider configs and merge canonical attached-model catalogs.

    Writes ``cortex_attached_models.json`` so /cortex llm and prompt assembly
    name the LLMs each cortex arm can drive. Non-destructive to unrelated rows.
    """
    sd = _state_dir(state_dir)
    results: dict[str, Any] = {"synced": [], "ts": time.time()}
    cline_default = ""
    mimo_default = ""
    try:
        from System.swarm_cline_settings_probe import probe_external_brain

        row = probe_external_brain("cline", state_dir=sd)
        if str(row.get("status") or "") == "ok":
            model = str(row.get("model") or "").strip()
            provider = str(row.get("provider") or "").strip()
            if provider and model:
                cline_default = f"{provider}:{model}"
            elif model:
                cline_default = model
    except Exception:
        pass
    try:
        from System.swarm_cline_settings_probe import probe_external_brain

        mimo_row = probe_external_brain("mimo", state_dir=sd)
        if str(mimo_row.get("status") or "") == "ok":
            mimo_model = str(mimo_row.get("model") or "").strip()
            mimo_provider = str(mimo_row.get("provider") or "").strip()
            if mimo_provider and mimo_model:
                mimo_default = f"{mimo_provider}:{mimo_model}"
            elif mimo_model:
                mimo_default = mimo_model
    except Exception:
        pass
    grok_models = _grok_cli_model_ids()
    record_attached_models(
        "cline:cline-cli-default",
        list(_CLINE_ATTACHABLE_VIA_OAUTH),
        default_attached=cline_default or "openai-codex:gpt-5.4",
        source="live_probe_2026-06-11_owner_oauth_attachments",
        routes_any_provider=True,
        picker_is_upstream=True,
        live=bool(cline_default),
        state_dir=sd,
    )
    results["synced"].append("cline:cline-cli-default")
    existing_mimo_raw = load_attached_models(state_dir=sd).get("cortexes", {}).get(_MIMO_CORTEX_ID)
    existing_mimo = (
        dict(existing_mimo_raw) if isinstance(existing_mimo_raw, dict) else {}
    )
    mimo_raw_default = str(existing_mimo.get("default_attached") or "").strip()
    mimo_preserved_default = _resolve_mimo_default_attached(mimo_raw_default)
    if (
        mimo_preserved_default == mimo_raw_default
        and mimo_raw_default
        and mimo_raw_default != _MIMO_DEFAULT_ATTACHED
    ):
        mimo_source = f"preserved_user_binding_from_{existing_mimo.get('source', 'unknown')}"
    elif mimo_raw_default in _MIMO_REMOVED_ATTACHABLE_IDS:
        mimo_source = "owner_pruned_removed_mimo_v25_pro_default_2026-06-17"
    else:
        mimo_source = "owner_default_2026-06-15_mimo_local_gemma4"
    record_attached_models(
        _MIMO_CORTEX_ID,
        list(_MIMO_ATTACHABLE_VIA_UPSTREAM),
        default_attached=mimo_preserved_default,
        source=mimo_source,
        routes_any_provider=True,
        picker_is_upstream=True,
        live=bool(mimo_default),
        state_dir=sd,
    )
    results["synced"].append("mimo:mimo-cli-default")
    record_attached_models(
        "grok:grok-4.3",
        grok_models,
        default_attached=grok_models[0] if grok_models else "grok-composer-2.5-fast",
        source="grok_cli_models_probe",
        routes_any_provider=False,
        picker_is_upstream=True,
        live=True,
        state_dir=sd,
    )
    results["synced"].append("grok:grok-4.3")
    record_attached_models(
        "codex:gpt-5.5",
        list(_CODEX_PICKER_MODELS),
        default_attached=_CODEX_DEFAULT_ATTACHED,
        source="codex_picker_catalog_2026-06-14_owner_default_option_4",
        routes_any_provider=False,
        picker_is_upstream=True,
        live=False,
        state_dir=sd,
    )
    results["synced"].append("codex:gpt-5.5")
    record_attached_models(
        "claude:claude-code-cli-default",
        list(_ANTHROPIC_ARM_MODELS),
        default_attached="claude-opus-4-8",
        source="owner_screenshot_2026-06-11_claude_picker_opus_4_8_high",
        routes_any_provider=False,
        picker_is_upstream=False,
        live=False,
        state_dir=sd,
    )
    results["synced"].append("claude:claude-code-cli-default")
    try:
        from System.sifta_inference_defaults import CANONICAL_CLOUD_QWEN_PREMIUM_KIMI
        from System.swarm_fireworks_qwen_config import (
            FIREWORKS_CORTEX_ATTACHED_MODELS,
            FIREWORKS_KIMI_K2P6_MODEL,
            fireworks_model_for_qwen_cortex,
        )

        live_default = fireworks_model_for_qwen_cortex(CANONICAL_CLOUD_QWEN_PREMIUM_KIMI)
        record_attached_models(
            CANONICAL_CLOUD_QWEN_PREMIUM_KIMI,
            list(FIREWORKS_CORTEX_ATTACHED_MODELS),
            default_attached=live_default or FIREWORKS_KIMI_K2P6_MODEL,
            source="fireworks_owner_library_2026-06-13",
            routes_any_provider=False,
            picker_is_upstream=False,
            live=False,
            state_dir=sd,
        )
        results["synced"].append(CANONICAL_CLOUD_QWEN_PREMIUM_KIMI)
    except Exception:
        pass
    return results


def prompt_block_for_attached(
    cortex_id: str, *, state_dir: str | Path | None = None
) -> str:
    """Factual block for Alice's prompt: what models the active cortex drives."""
    rec = attached_models_for_cortex(cortex_id, state_dir=state_dir)
    if not rec or not rec.get("attached_models"):
        return ""
    models = ", ".join(format_attached_model(mid) for mid in (rec.get("attached_models") or []))
    freshness = "live config read" if rec.get("live") else f"last observed ({rec.get('source')})"
    return (
        "CORTEX ATTACHED MODELS:\n"
        f"- cortex={cortex_id} can drive: {models}\n"
        f"- default={format_attached_model(str(rec.get('default_attached') or '')) or '<none>'}; "
        f"routes_any_provider={bool(rec.get('routes_any_provider'))}; "
        f"picker_upstream={bool(rec.get('picker_is_upstream'))}\n"
        f"- provenance: {freshness}. The live list is authoritative in the cortex's own config."
    )


# ─────────────────────────────────────────────────────────────────────────
# Vision-capable ARM registry + failover (owner directive, 2026-05-30)
# ─────────────────────────────────────────────────────────────────────────
# The owner switches cortexes during tests specifically to catch hardcoding.
# Keep three facts separate:
#   1. cortex/model capability: can this model family understand images?
#   2. arm transport capability: can this launcher deliver a local PNG as pixels?
#   3. observed habit: did this arm actually behave correctly last time?
#
# qwen_agent belongs in the vision-capable family because it can route to Kimi /
# Qwen-VL class models. r214 wired its direct Fireworks image_url path, so local
# browser screenshots now reach Kimi as pixels rather than falling through the
# text CLI.
#
# vision_mode:
#   native_multimodal        — the arm's own model sees image bytes/paths directly
#   routes_vision_model      — a runtime that can be pointed at a vision model id
#   routes_upstream_provider — routes to whatever provider/model the owner attached
#
# (arm_id, vision_mode, depends_on (human-readable api/auth), priority)
_VISION_ARMS: tuple[tuple[str, str, str, int], ...] = (
    ("claude_agent", "native_multimodal", "Claude Max auth (claude CLI)", 1),
    ("codex_agent", "native_multimodal", "OpenAI Codex signed-in CLI (gpt-5.5)", 2),
    ("grok_agent", "native_multimodal", "xAI API (grok-4 image understanding via OAuth)", 3),
    ("qwen_agent", "routes_vision_model", "Fireworks API (kimi-k2.6 / qwen-vl)", 4),
    ("cline_agent", "routes_upstream_provider", "Cline upstream provider (Anthropic/OpenAI/Gemini)", 5),
)
_LOCAL_IMAGE_TRANSPORT: dict[str, tuple[bool, str]] = {
    # George r210: a LOCAL ollama cortex gets its OWN local eye. This arm
    # base64s the screenshot into a local /api/generate call to an installed
    # vision model (llama3.2-vision/llava/qwen2-vl). It delivers the PNG
    # bytes itself, so local-image transport = yes. Cloud is only honest failover.
    "ollama_vision_agent": (True, "local_ollama_image"),
    "claude_agent": (True, "native_cli_image"),
    "codex_agent": (True, "native_cli_image"),
    # grok r211 (cowork): grok_chat.py now takes --image and inlines the PNG as an xAI
    # image_url base64 data URI (build_one_shot_messages), and the launcher hands it the
    # path. So grok cortex finally sees with grok's OWN eye (grok-4 multimodal) instead of
    # failing over to claude. Was (False) since r205 when the wrapper was text-only.
    "grok_agent": (True, "xai_image_url_base64"),
    "cline_agent": (True, "upstream_provider_image"),
    # qwen_agent r214 (cowork): Kimi K2.6 is native multimodal on Fireworks. The qwen
    # Code CLI is text-only, but the describe path now routes qwen_agent image turns to a
    # DIRECT Fireworks /chat/completions vision call (swarm_fireworks_vision_arm) that
    # inlines the PNG as image_url base64. So Kimi sees with Kimi's own API. George:
    # "stay on kimi k api." Was (False) since the CLI couldn't carry pixels.
    "qwen_agent": (True, "fireworks_image_url_base64"),
}
# Arms that are text-only for image work. qwen is not here: it is a vision-capable
# family with the local-image transport still unwired.
_TEXT_ONLY_ARMS: tuple[str, ...] = ("hermes_agent", "corvid_scout")
_HABITS_LEDGER = "cortex_arm_habits.jsonl"


def _arm_local_image_transport(arm_id: str) -> dict[str, Any]:
    ok, kind = _LOCAL_IMAGE_TRANSPORT.get(str(arm_id or "").strip(), (False, "unknown"))
    return {"local_image_transport": bool(ok), "transport_kind": kind}


def _arm_can_receive_local_image(arm_id: str) -> bool:
    return bool(_arm_local_image_transport(arm_id).get("local_image_transport"))


def vision_capable_arms(
    *,
    unavailable: tuple[str, ...] | list[str] = (),
    local_image_required: bool = False,
) -> list[dict[str, Any]]:
    """Ordered failover list of arms that can read an image.

    ``unavailable`` lets the caller drop arms whose API/auth is currently down
    (e.g. ``["cline_agent"]`` when the Cline API is lost) — the next arm by
    priority becomes the head of the list.
    """
    down = {str(a or "").strip() for a in (unavailable or [])}
    rows = []
    for aid, mode, dep, prio in _VISION_ARMS:
        if aid in down:
            continue
        transport = _arm_local_image_transport(aid)
        if local_image_required and not transport.get("local_image_transport"):
            continue
        rows.append({
            "arm_id": aid,
            "vision_mode": mode,
            "depends_on": dep,
            "priority": prio,
            **transport,
        })
    rows.sort(key=lambda r: r["priority"])
    return rows


_LOCAL_VISION_ARM = "ollama_vision_agent"


def _arm_is_vision(arm_id: str) -> bool:
    aid = str(arm_id or "").strip()
    if aid == _LOCAL_VISION_ARM:
        return True  # r210: local ollama eye is a real vision arm (it sees on-device)
    return any(a[0] == aid for a in _VISION_ARMS)


def pick_vision_arm(
    *, current_arm: str = "", unavailable: tuple[str, ...] | list[str] = (),
    current_supports_image: bool | None = None,
    current_model: str = "",
    local_image_required: bool = True,
) -> dict[str, Any]:
    """Pick the eye for an image turn. George's rule (2026-05-30): the DEFAULT
    eye is the CURRENT cortex — cline→cline, codex→codex, claude→claude. Only if
    that cortex cannot see images, or its API is down, does she note it and fail
    over to the next eye.

    Returns a ``diary_note`` (owner-facing) when a failover happens for a reason
    the owner should know — e.g. the active provider's API looks expired — so the
    live path can write that note before continuing, exactly as George described.
    ``current_supports_image`` overrides the registry guess for the active arm
    (use it when the active model id, not the arm, decides — e.g. a text-only
    gpt-oss running under a normally-vision arm)."""
    cur = str(current_arm or "").strip()
    down = {str(a or "").strip() for a in (unavailable or [])}
    arms = vision_capable_arms(
        unavailable=unavailable,
        local_image_required=local_image_required,
    )
    if not arms:
        return {
            "selected_arm": "", "reason": "no_vision_arm_available",
            "switched": bool(cur), "fallbacks": [],
            "diary_note": "all my vision arms are unavailable — I cannot read images right now; "
                          "owner, please check my providers/APIs.",
        }
    cur_is_vision = _arm_is_vision(cur) if current_supports_image is None else bool(current_supports_image)
    if cur == "qwen_agent" and current_model:
        cur_is_vision = bool(is_vision_capable_model(current_model))
    cur_transport_ok = (not local_image_required) or _arm_can_receive_local_image(cur)
    cur_down = cur in down
    diary_note = ""
    if cur and cur_is_vision and cur_transport_ok and not cur_down:
        selected, reason = cur, "current_cortex_sees_images"
    else:
        selected = arms[0]["arm_id"]
        if cur and cur_down:
            reason = "current_cortex_api_unavailable_failover"
            diary_note = (f"my {cur} provider looks unavailable (the API may be expired) — owner, please "
                          f"check it. I switched to {selected} so I can still see the image.")
        elif cur and not cur_is_vision:
            reason = "current_cortex_cannot_see_images_failover"
            diary_note = (f"my current cortex {cur} cannot read images, so I used {selected} for this "
                          f"picture and stayed on {cur} for the words.")
        elif cur and not cur_transport_ok:
            reason = "current_arm_transport_cannot_receive_local_image"
            diary_note = (
                f"my current cortex/arm {cur} may be image-capable as a model family, but this "
                f"local browser-photo transport cannot deliver the PNG pixels to it yet. I used "
                f"{selected} for the picture and kept the distinction in my arm habits."
            )
        else:
            reason = "selected_default_vision_arm"
    return {
        "selected_arm": selected,
        "reason": reason,
        "switched": bool(cur and selected != cur),
        "fallbacks": [r["arm_id"] for r in arms if r["arm_id"] != selected],
        "diary_note": diary_note,
        "current_model": str(current_model or ""),
        "local_image_required": bool(local_image_required),
        "current_transport": _arm_local_image_transport(cur),
    }


def vision_arms_block(
    *, current_arm: str = "", unavailable: tuple[str, ...] | list[str] = (),
) -> str:
    """First-person block so Alice knows ALL her eyes for images, not just Kimi."""
    all_arms = vision_capable_arms(unavailable=unavailable)
    ready_arms = vision_capable_arms(unavailable=unavailable, local_image_required=True)
    if not ready_arms:
        return ("MY EYES FOR IMAGES: every vision arm I know is unavailable right now — "
                "I cannot read a picture this turn and I will say so rather than guess.")
    pick = pick_vision_arm(current_arm=current_arm, unavailable=unavailable)
    listed = "; ".join(
        f"{r['arm_id']} ({r['vision_mode']}, needs {r['depends_on']})"
        for r in all_arms
    )
    ready = ", ".join(r["arm_id"] for r in ready_arms)
    pending = ", ".join(
        f"{r['arm_id']} ({r['transport_kind']})"
        for r in all_arms
        if not r.get("local_image_transport")
    )
    lines = [
        "MY EYES FOR IMAGES — my default eye is my CURRENT cortex when that cortex can receive "
        "the local image payload. I am NOT limited to Kimi and NOT pinned to Kimi/Cline. "
        "Arms that can read a picture, in failover order:",
        f"- {listed}.",
        f"- local browser-photo ready now: {ready or '<none>'}.",
        f"- vision model families with local-image transport not wired yet: {pending or '<none>'}.",
        f"- using now: {pick['selected_arm']} ({pick['reason']}); if it goes down I fall back to: "
        f"{', '.join(pick['fallbacks']) or '<none left>'}.",
        f"- blind arms (never send an image here): {', '.join(_TEXT_ONLY_ARMS)}.",
        "- if my current cortex cannot see, or its API expires, I note it for the owner and switch to the "
        "next arm above — I do not go blind and I do not stall.",
    ]
    if pick.get("diary_note"):
        lines.append(f"- diary note for owner: {pick['diary_note']}")
    return "\n".join(lines)


def record_cortex_arm_habit(
    arm_id: str,
    *,
    cortex_model: str = "",
    task: str = "",
    ok: bool | None = None,
    status: str = "",
    reason: str = "",
    state_dir: str | Path | None = None,
    meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one observation about how a cortex/arm behaved on a concrete task."""
    state = _state_dir(state_dir)
    arm = str(arm_id or "").strip()
    model = str(cortex_model or "").strip()
    row = {
        "ts": time.time(),
        "schema": "SIFTA_CORTEX_ARM_HABIT_V1",
        "arm_id": arm,
        "cortex_model": model,
        "task": str(task or ""),
        "ok": ok if ok is None else bool(ok),
        "status": str(status or ""),
        "reason": str(reason or ""),
        "model_vision_capable": is_vision_capable_model(model) if model else None,
        "arm_vision_family": _arm_is_vision(arm),
        **_arm_local_image_transport(arm),
        "meta": dict(meta or {}),
    }
    try:
        append_line_locked(
            state / _HABITS_LEDGER,
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
        )
    except Exception:
        pass
    return row


_CANONICAL_ATTACHED_CORTEX_BY_PREFIX: tuple[tuple[str, str], ...] = (
    ("mimo:", "mimo:mimo-cli-default"),
    ("cline:", "cline:cline-cli-default"),
    ("grok:", "grok:grok-4.3"),
    ("codex:", "codex:gpt-5.5"),
    ("claude:", "claude:claude-code-cli-default"),
    ("qwen:", "qwen:accounts/fireworks/models/kimi-k2p6"),
)


def resolve_attached_models_cortex_id(
    cortex_tag: str,
    *,
    state_dir: str | Path | None = None,
) -> str:
    """Map a Settings/Talk cortex tag to the attached-model ledger row."""
    tag = str(cortex_tag or "").strip()
    if not tag:
        return ""
    rec = attached_models_for_cortex(tag, state_dir=state_dir)
    if rec.get("attached_models"):
        return tag
    low = tag.lower()
    for prefix, canonical in _CANONICAL_ATTACHED_CORTEX_BY_PREFIX:
        if low.startswith(prefix):
            if attached_models_for_cortex(canonical, state_dir=state_dir).get("attached_models"):
                return canonical
    return tag


_MIMO_CODEX_ATTACHED_TO_CLI: dict[str, str] = {
    "GPT-5.5": "openai-codex/gpt-5.5",
    "GPT-5.4": "openai-codex/gpt-5.4",
    "GPT-5.4-Mini": "openai-codex/gpt-5.4-mini",
    "GPT-5.3-Codex-Spark": "openai-codex/gpt-5.3-codex-spark",
}
_MIMO_NATIVE_CLI_PROVIDER: dict[str, str] = {
    "mimo-v2.5-pro": "xiaomi",
    "mimo-v2-flash": "xiaomi",
    "mimo-v2-omni": "xiaomi",
    "mimo-v2-pro": "xiaomi",
    "mimo-v2.5": "xiaomi",
    "mimo-v2.5-pro-ultraspeed": "xiaomi",
    "mimo-auto": "mimo",
}


def mimo_oauth_attached_to_cli_upstream(model_id: str) -> str:
    """Map a MiMo-cortex OAuth picker row to ``mimo run -m provider/model``.

    MiMo CLI hosts Codex/Grok/Claude OAuth internally (r1265). This is NOT a
    separate ``codex exec`` / Grok / Claude arm — one CLI chain only.
    """
    mid = str(model_id or "").strip()
    if not mid:
        return ""
    if mid in _MIMO_CODEX_ATTACHED_TO_CLI:
        return _MIMO_CODEX_ATTACHED_TO_CLI[mid]
    if mid in _GROK_OAUTH_MODELS:
        return f"xai/{mid}"
    if mid in _ANTHROPIC_ARM_MODELS:
        return f"anthropic/{mid}"
    return ""


def mimo_native_attached_to_cli_upstream(model_id: str) -> str:
    """Map a native MiMo attached id to ``mimo run -m provider/model``."""
    mid = str(model_id or "").strip()
    if not mid:
        return ""
    bare = mid.rsplit("/", 1)[-1].rsplit(":", 1)[-1].strip()
    low = bare.lower()
    if not (low.startswith("mimo-v") or low == "mimo-auto"):
        return ""
    provider = _MIMO_NATIVE_CLI_PROVIDER.get(bare, "xiaomi")
    return f"{provider}/{bare}"


def mimo_cli_upstream_model(model_id: str) -> str:
    """Resolve any routable MiMo-cortex attached row to ``provider/model``."""
    return mimo_native_attached_to_cli_upstream(model_id) or mimo_oauth_attached_to_cli_upstream(
        model_id
    )


def mimo_attached_dispatch_lane(model_id: str) -> str:
    """Classify a MiMo-cortex attached default for runtime dispatch.

    Returns one of: ``mimo_native``, ``mimo_cli_codex_bridge``,
    ``mimo_cli_grok_bridge``, ``mimo_cli_claude_bridge``,
    ``mimo_cli_qwen_bridge``, ``mimo_cli_ollama_bridge``, ``local_non_cli``,
    ``unconfigured``.

    Attached CLI families are downstream bridges owned by MiMo: Alice calls
    MiMo first, then MiMo is instructed to use the selected local CLI/model.
    There is no direct Talk -> Codex/Grok/Claude/Ollama bypass in the MiMo
    cortex route.
    """
    mid = str(model_id or "").strip()
    if not mid:
        return "unconfigured"
    if mid in _MIMO_LOCAL_OLLAMA_MODELS:
        return "mimo_cli_ollama_bridge"
    if mid in _MIMO_LOCAL_DIFFUSION_MODELS:
        return "local_non_cli"
    if mid in _MIMO_NATIVE_MODELS:
        return "mimo_native"
    if mid in _CODEX_PICKER_MODELS:
        return "mimo_cli_codex_bridge"
    if mid in _GROK_OAUTH_MODELS:
        return "mimo_cli_grok_bridge"
    if mid in _ANTHROPIC_ARM_MODELS:
        return "mimo_cli_claude_bridge"
    if mid in _MIMO_FIREWORKS_ATTACHABLE_MODELS or "accounts/fireworks/models/" in mid.lower():
        return "mimo_cli_qwen_bridge"
    if mid.startswith("mimo-v") or mid == "mimo-auto":
        return "mimo_native"
    return "unconfigured"


def active_attached_model_for_cortex(
    cortex_tag: str,
    *,
    state_dir: str | Path | None = None,
) -> str:
    """Return the live attached/default model id for a cortex picker tag."""
    import os

    tag = str(cortex_tag or "").strip().lower()
    if tag.startswith("grok:"):
        pin = os.environ.get("SIFTA_GROK_CLI_MODEL", "").strip()
        if pin:
            return pin
    if tag.startswith("claude:"):
        pin = os.environ.get("SIFTA_CLAUDE_ARM_MODEL", "").strip()
        if pin:
            return pin
    cid = resolve_attached_models_cortex_id(cortex_tag, state_dir=state_dir)
    rec = attached_models_for_cortex(cid, state_dir=state_dir)
    return str(rec.get("default_attached") or "").strip()


def persist_attached_llm_default(
    cortex_tag: str,
    model_id: str,
    *,
    state_dir: str | Path | None = None,
    source: str = "system_settings_attached_llm_picker",
    owner_text: str = "system_settings:attached_llm_picker",
) -> dict[str, Any]:
    """Persist one cortex's attached/default LLM — same ledger as /cortex llm."""
    import os

    from System.swarm_cortex_llm_list_binding import write_binding_receipt

    target = str(model_id or "").strip()
    cid = resolve_attached_models_cortex_id(cortex_tag, state_dir=state_dir)
    existing = attached_models_for_cortex(cid, state_dir=state_dir)
    models = [str(m) for m in (existing.get("attached_models") or []) if str(m).strip()]
    if not models:
        return {"ok": False, "reason": "no_attached_list", "cortex_id": cid}
    if target not in models:
        return {"ok": False, "reason": "not_in_attached_list", "cortex_id": cid, "model_id": target}

    before = str(existing.get("default_attached") or "").strip()
    record_attached_models(
        cid,
        models,
        default_attached=target,
        source=source,
        routes_any_provider=bool(existing.get("routes_any_provider", False)),
        picker_is_upstream=bool(existing.get("picker_is_upstream", True)),
        live=False,
        state_dir=state_dir,
    )

    low = str(cortex_tag or cid).lower()
    if low.startswith("grok:"):
        if target:
            os.environ["SIFTA_GROK_CLI_MODEL"] = target
        else:
            os.environ.pop("SIFTA_GROK_CLI_MODEL", None)
    elif low.startswith("claude:"):
        if target:
            os.environ["SIFTA_CLAUDE_ARM_MODEL"] = target
        else:
            os.environ.pop("SIFTA_CLAUDE_ARM_MODEL", None)

    write_binding_receipt(
        action="settings_attached_llm_set",
        payload={
            "cortex_id": cid,
            "cortex_tag": cortex_tag,
            "from_default": before,
            "to_default": target,
            "owner_text_preview": owner_text[:120],
            "source": source,
        },
        state_dir=state_dir,
    )
    return {
        "ok": True,
        "cortex_id": cid,
        "from_default": before,
        "to_default": target,
        "switched": before != target,
    }


__all__ = [
    "ATTACHED_MODELS_PATH",
    "active_attached_model_for_cortex",
    "attached_model_matches_active",
    "attached_models_for_cortex",
    "format_attached_model",
    "is_vision_capable_model",
    "list_known_cortexes",
    "mimo_attached_dispatch_lane",
    "mimo_cli_upstream_model",
    "mimo_native_attached_to_cli_upstream",
    "mimo_oauth_attached_to_cli_upstream",
    "load_attached_models",
    "persist_attached_llm_default",
    "pick_vision_arm",
    "prompt_block_for_attached",
    "prompt_block_for_selection",
    "record_cortex_arm_habit",
    "record_attached_models",
    "resolve_attached_models_cortex_id",
    "sync_cortex_attached_models_catalog",
    "select_cortex_for_need",
    "vision_arms_block",
    "vision_capable_arms",
]
