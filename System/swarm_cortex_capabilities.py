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
    "kimi",
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
        if not is_vision_capable_model(current_model):
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


def attached_models_for_cortex(
    cortex_id: str, *, state_dir: str | Path | None = None
) -> dict[str, Any]:
    """Return the attached-models record for one cortex id, or {} if unknown."""
    data = load_attached_models(state_dir=state_dir)
    rec = data.get("cortexes", {}).get(str(cortex_id or "").strip())
    return dict(rec) if isinstance(rec, dict) else {}


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
    rec = {
        "attached_models": clean_models,
        "default_attached": str(default_attached or (clean_models[0] if clean_models else "")),
        "routes_any_provider": bool(routes_any_provider),
        "picker_is_upstream": bool(picker_is_upstream),
        "source": str(source),
        "live": bool(live),
        "recorded_ts": time.time(),
    }
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


def prompt_block_for_attached(
    cortex_id: str, *, state_dir: str | Path | None = None
) -> str:
    """Factual block for Alice's prompt: what models the active cortex drives."""
    rec = attached_models_for_cortex(cortex_id, state_dir=state_dir)
    if not rec or not rec.get("attached_models"):
        return ""
    models = ", ".join(rec.get("attached_models") or [])
    freshness = "live config read" if rec.get("live") else f"last observed ({rec.get('source')})"
    return (
        "CORTEX ATTACHED MODELS:\n"
        f"- cortex={cortex_id} can drive: {models}\n"
        f"- default={rec.get('default_attached') or '<none>'}; "
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


__all__ = [
    "ATTACHED_MODELS_PATH",
    "attached_models_for_cortex",
    "is_vision_capable_model",
    "list_known_cortexes",
    "load_attached_models",
    "pick_vision_arm",
    "prompt_block_for_attached",
    "prompt_block_for_selection",
    "record_cortex_arm_habit",
    "record_attached_models",
    "select_cortex_for_need",
    "vision_arms_block",
    "vision_capable_arms",
]
