#!/usr/bin/env python3
"""Receipt-first policy for live body multimodal tasks.

Alice's current 8B cortex is not text-only, but live body tasks are stricter
than ordinary chat. If a turn asks about microphone + camera/browser context,
source separation, background audio, or co-watch audio, the cortex may compose
only after the body sensors provide receipts.

Truth label: BODY_MULTIMODAL_TASK_POLICY_V1.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / ".sifta_state"
LEDGER_NAME = "body_multimodal_task_policy.jsonl"
TRUTH_LABEL = "BODY_MULTIMODAL_TASK_POLICY_V1"

_AUDIO_RE = re.compile(
    r"\b(?:audio|sound|noise|background|hear|hearing|heard|mic|microphone|"
    r"voice|tts|stt|transcription|whistle|whistling|speaker|iphone|phone|"
    r"birds?|chirp|room|breath|youtube|co[- ]?watch)\b",
    re.IGNORECASE,
)
_VISUAL_RE = re.compile(
    r"\b(?:camera|eye|see|seeing|look|watch|browser|screen|monitor|image|"
    r"photo|video|frame|pixels?|youtube|co[- ]?watch)\b",
    re.IGNORECASE,
)
_SOURCE_RE = re.compile(
    r"\b(?:source|separat(?:e|ion)|which\s+sound|who\s+is\s+speaking|"
    r"phone\s+speaker|from\s+the\s+phone|room\s+sound|real\s+room|"
    r"background\s+(?:noise|audio)|ambient|diari[sz]e|record)\b",
    re.IGNORECASE,
)
_BODY_TASK_RE = re.compile(
    r"\b(?:body\s+tasks?|camera/mic|camera\s+and\s+mic|mic\s+and\s+camera|"
    r"source\s+separation|co[- ]?watch|background\s+with\s+birds?|"
    r"what\s+youtube\s+page|what\s+page\s+am\s+i|current\s+youtube)\b",
    re.IGNORECASE,
)


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE


def _append(row: Mapping[str, Any], *, state_dir: Path | str | None = None) -> None:
    path = _state_dir(state_dir) / LEDGER_NAME
    payload = json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if append_line_locked:
            append_line_locked(path, payload)
        else:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(payload)
    except OSError:
        pass


def classify_body_multimodal_need(
    owner_text: str,
    *,
    current_model: str = "",
    sensor_context: Mapping[str, Any] | None = None,
    write: bool = False,
    state_dir: Path | str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Classify whether this turn needs receipt-first joint body sensing.

    This does not switch models by itself. It returns a route/eval policy that
    the prompt and router can use without pretending a stronger cortex already
    ran.
    """

    text = str(owner_text or "")
    low = text.lower()
    has_audio = bool(_AUDIO_RE.search(text))
    has_visual = bool(_VISUAL_RE.search(text))
    source_separation = bool(_SOURCE_RE.search(text))
    body_task = bool(_BODY_TASK_RE.search(text))
    current_is_8b = "alice-m5-cortex-8b" in str(current_model or "").lower() or "8b" in str(current_model or "").lower()

    sensor_context = dict(sensor_context or {})
    yt = sensor_context.get("youtube_context") if isinstance(sensor_context.get("youtube_context"), Mapping) else {}
    audio_ctx = sensor_context.get("audio_ingress") if isinstance(sensor_context.get("audio_ingress"), Mapping) else {}
    acoustic_ctx = sensor_context.get("acoustic_fingerprint") if isinstance(sensor_context.get("acoustic_fingerprint"), Mapping) else {}
    sensor_has_audio = bool(audio_ctx.get("fresh") or acoustic_ctx.get("fresh"))
    sensor_has_youtube = bool(yt.get("title") or yt.get("dialogue_boundary"))

    needs_joint = bool(
        source_separation
        or (body_task and has_audio)
        or (has_audio and has_visual)
        or ("youtube" in low and any(w in low for w in ("hear", "sound", "page", "watch", "browser")))
    )
    needs_background_receipt = bool(
        "background" in low
        or "bird" in low
        or "chirp" in low
        or "ambient" in low
        or source_separation
    )

    if needs_joint:
        route = "sensor_receipts_first_then_cortex_compose"
        eval_recommendation = (
            "bench/evaluate Gemma 4 12B or another unified audio+vision cortex for this class; "
            "do not keep extra resident models without a route receipt"
        )
    elif needs_background_receipt:
        route = "background_audio_receipt_first"
        eval_recommendation = "record/label background audio; species/source claims need a classifier receipt"
    else:
        route = "ordinary_cortex_turn"
        eval_recommendation = "no body multimodal promotion needed"

    row = {
        "ts": time.time() if now is None else float(now),
        "receipt_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "owner_preview": text[:240],
        "current_model": str(current_model or ""),
        "current_8b_limit": bool(current_is_8b and needs_joint),
        "has_audio_terms": has_audio,
        "has_visual_terms": has_visual,
        "source_separation": source_separation,
        "body_task": body_task,
        "needs_joint_audio_vision": needs_joint,
        "needs_background_receipt": needs_background_receipt,
        "sensor_has_audio_receipt": sensor_has_audio,
        "sensor_has_youtube_context": sensor_has_youtube,
        "route": route,
        "eval_recommendation": eval_recommendation,
        "required_receipts": [
            "audio_ingress_log.jsonl",
            "acoustic_fingerprints.jsonl",
            "audio_source_classifications.jsonl",
            "media_ingress_gate.jsonl",
            "youtube_context_latest.json",
            "visual_stigmergy.jsonl",
            "browser_page_state.jsonl",
            "cortex_verification.jsonl",
        ],
        "rule": (
            "8B may compose the answer, but joint mic+camera/browser/source-separation truth "
            "must come from sensor receipts or a verified unified multimodal cortex run."
        ),
    }
    if write and (needs_joint or needs_background_receipt):
        _append(row, state_dir=state_dir)
    return row


def prompt_block_for_alice(
    *,
    owner_text: str,
    current_model: str = "",
    state_dir: Path | str | None = None,
    write: bool = True,
) -> str:
    """Return a prompt block only for relevant body multimodal turns."""

    sensor_context: Mapping[str, Any] = {}
    try:
        from System.swarm_sensor_truth_context import build_sensor_truth_context

        sensor_context = build_sensor_truth_context(state_dir=_state_dir(state_dir))
    except Exception:
        sensor_context = {}
    row = classify_body_multimodal_need(
        owner_text,
        current_model=current_model,
        sensor_context=sensor_context,
        write=write,
        state_dir=state_dir,
    )
    if not (row.get("needs_joint_audio_vision") or row.get("needs_background_receipt")):
        return ""
    return (
        "BODY MULTIMODAL POLICY (receipt-first camera/mic/co-watch/source separation):\n"
        f"- receipt_id={row.get('receipt_id')} current_model={row.get('current_model') or '<unknown>'} "
        f"current_8b_limit={str(row.get('current_8b_limit')).lower()}\n"
        f"- route={row.get('route')}; eval={row.get('eval_recommendation')}\n"
        "- Rule: all words/audio are events in the field, but source/meaning/command must be sorted by receipts. "
        "For phone speaker vs room voice, YouTube vs George, birds/background noise, or camera+mic body tasks, "
        "use audio_ingress, acoustic_fingerprints, media_ingress_gate, visual_stigmergy/browser receipts first.\n"
        "- 8B is allowed to compose the final reply after evidence arrives; it must not invent source separation, "
        "species labels, or joint audio+visual certainty from language alone.\n"
        "- If evidence is missing, state the missing receipt and the next acquisition step, not a denial and not a confident guess."
    )


def cowatch_novelty_line(title: str, *, current_model: str = "") -> str:
    """Concrete co-watch novelty for model/vision/audio videos."""

    row = classify_body_multimodal_need(
        f"co-watch model/audio/vision title: {title}",
        current_model=current_model,
        write=True,
    )
    return (
        "that hits my body multimodal policy: for camera/mic/source-separation tasks, "
        "I should use sensor receipts first, let 8B compose only after evidence, and bench "
        "Gemma 4 12B or another unified audio+vision cortex before promoting it"
        f" — receipt {row.get('receipt_id')}"
    )


__all__ = [
    "TRUTH_LABEL",
    "classify_body_multimodal_need",
    "cowatch_novelty_line",
    "prompt_block_for_alice",
]
