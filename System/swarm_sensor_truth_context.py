#!/usr/bin/env python3
"""Receipt-backed live sensor truth for Alice.

This module keeps device inventory separate from active perception.

Hardware manifests can list cameras and microphones while macOS TCC still
blocks capture. Acoustic fingerprints can mark near-field audio while still
failing to identify the speaker. This prompt block names that boundary so Alice
does not report seeing the owner or distinguishing owner speech from YouTube unless a
specific receipt exists.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

_ACTIVE_TARGET = "active_saccade_target.json"
_VISUAL_LOG = "visual_stigmergy.jsonl"
_AUDIO_INGRESS_LOG = "audio_ingress_log.jsonl"
_ACOUSTIC_FP_LOG = "acoustic_fingerprints.jsonl"
_YOUTUBE_LATEST = "youtube_context_latest.json"
_CORRECTIONS = "sensor_claim_corrections.jsonl"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _tail_jsonl(path: Path, n: int = 1, *, keep_bytes: int = 131072) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - keep_bytes))
            raw_rows = fh.read().splitlines()[-n:]
    except OSError:
        return []
    for raw in raw_rows:
        try:
            row = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _latest_jsonl(path: Path) -> dict[str, Any]:
    rows = _tail_jsonl(path, 1)
    return rows[-1] if rows else {}


def _age_text(ts: Any, *, now: float) -> tuple[float, str]:
    try:
        age = max(0.0, now - float(ts))
    except Exception:
        return float("inf"), "unknown"
    if age < 1:
        return age, "<1s"
    if age < 90:
        return age, f"{int(age)}s"
    if age < 7200:
        return age, f"{age / 60:.1f}m"
    return age, f"{age / 3600:.1f}h"


def _visual_capture_source(row: dict[str, Any]) -> str:
    for key in ("capture_source", "camera_source", "camera_name", "device_name", "source"):
        value = row.get(key)
        if value:
            return str(value)
    return "unlabeled_visual_stigmergy_row"


def build_sensor_truth_context(
    *,
    state_dir: Path | str = _STATE,
    now: float | None = None,
) -> dict[str, Any]:
    state = Path(state_dir)
    current = time.time() if now is None else float(now)
    target = _read_json(state / _ACTIVE_TARGET)
    visual = _latest_jsonl(state / _VISUAL_LOG)
    audio = _latest_jsonl(state / _AUDIO_INGRESS_LOG)
    acoustic = _latest_jsonl(state / _ACOUSTIC_FP_LOG)
    youtube = _read_json(state / _YOUTUBE_LATEST)
    correction = _latest_jsonl(state / _CORRECTIONS)

    target_age, target_age_s = _age_text(target.get("ts"), now=current)
    visual_age, visual_age_s = _age_text(visual.get("ts"), now=current)
    audio_age, audio_age_s = _age_text(audio.get("ts_captured", audio.get("ts")), now=current)
    acoustic_age, acoustic_age_s = _age_text(acoustic.get("ts"), now=current)

    visual_source = _visual_capture_source(visual) if visual else "none"
    explicit_camera_receipt = bool(
        visual
        and any(visual.get(k) for k in ("capture_source", "camera_source", "camera_name", "device_name"))
    )
    visual_fresh = bool(visual and visual_age <= 15.0)
    try:
        lease_active = target.get("lease_until") is not None and float(target.get("lease_until") or 0.0) >= current
    except Exception:
        lease_active = False
    target_fresh = bool(target and (target_age <= 60.0 or lease_active))
    try:
        frame_has_pixels = int(visual.get("w") or 0) > 0 and int(visual.get("h") or 0) > 0
    except Exception:
        frame_has_pixels = False
    if explicit_camera_receipt:
        camera_source_attribution = "explicit_visual_camera_receipt"
    elif target_fresh and (target.get("name") or target.get("index") is not None):
        camera_source_attribution = "inferred_from_active_eye_target"
    elif visual_fresh:
        camera_source_attribution = "unlabeled_visual_stigmergy_row"
    else:
        camera_source_attribution = "none"
    camera_live_capture_verified = bool(
        visual_fresh
        and frame_has_pixels
        and camera_source_attribution != "none"
    )

    fp = acoustic.get("playback_fingerprint")
    if not isinstance(fp, dict):
        fp = {}
    near = fp.get("nearfield_voice_likelihood", acoustic.get("nearfield_voice_likelihood"))
    far = fp.get("farfield_replay_likelihood", acoustic.get("farfield_replay_likelihood"))
    channel_cue = str(fp.get("channel_cue") or acoustic.get("channel_cue") or "none")
    acoustic_fresh = bool(acoustic and acoustic_age <= 30.0)

    speaker_identity_verified = False
    speaker_identity_reason = (
        "no dedicated owner voiceprint / diarization receipt; "
        "nearfield/farfield features are channel cues only"
    )

    return {
        "truth_label": "SENSOR_TRUTH_CONTEXT_V1",
        "ts": current,
        "active_eye_target": {
            "name": target.get("name") or "unknown",
            "index": target.get("index"),
            "writer": target.get("writer") or "unknown",
            "fresh": target_fresh,
            "age_text": target_age_s,
        },
        "visual_stigmergy": {
            "fresh": visual_fresh,
            "age_text": visual_age_s,
            "frame": f"{visual.get('w', '?')}x{visual.get('h', '?')}" if visual else "none",
            "source": visual_source,
            "explicit_camera_receipt": explicit_camera_receipt,
            "camera_source_attribution": camera_source_attribution,
        },
        "camera_live_capture_verified": camera_live_capture_verified,
        "audio_ingress": {
            "fresh": bool(audio and audio_age <= 30.0),
            "age_text": audio_age_s,
            "device": audio.get("device_name") or "unknown",
            "rms": audio.get("rms_amplitude"),
        },
        "acoustic_fingerprint": {
            "fresh": acoustic_fresh,
            "age_text": acoustic_age_s,
            "channel_cue": channel_cue,
            "nearfield_voice_likelihood": near,
            "farfield_replay_likelihood": far,
        },
        "speaker_identity_verified": speaker_identity_verified,
        "speaker_identity_reason": speaker_identity_reason,
        "youtube_context": {
            "title": youtube.get("title") or "",
            "dialogue_boundary": youtube.get("dialogue_boundary") or "",
            "ts": youtube.get("ts"),
        },
        "latest_owner_correction": correction,
    }


def summary_for_alice(
    *,
    state_dir: Path | str = _STATE,
    now: float | None = None,
) -> str:
    ctx = build_sensor_truth_context(state_dir=state_dir, now=now)
    eye = ctx["active_eye_target"]
    visual = ctx["visual_stigmergy"]
    audio = ctx["audio_ingress"]
    acoustic = ctx["acoustic_fingerprint"]
    yt = ctx["youtube_context"]
    correction = ctx.get("latest_owner_correction") or {}

    lines = [
        "SENSOR TRUTH CONTEXT (inventory is not perception):",
        (
            f"- active_eye_target={eye.get('name')} index={eye.get('index')} "
            f"writer={eye.get('writer')} fresh={str(eye.get('fresh')).lower()} age={eye.get('age_text')} ; "
            "target lease selects the eye; visual_stigmergy proves frames"
        ),
        (
            f"- visual_stigmergy=fresh:{str(visual.get('fresh')).lower()} "
            f"age={visual.get('age_text')} frame={visual.get('frame')} "
            f"source={visual.get('source')} explicit_camera_receipt={str(visual.get('explicit_camera_receipt')).lower()} "
            f"camera_source_attribution={visual.get('camera_source_attribution')}"
        ),
        f"- camera_live_capture_verified={str(ctx['camera_live_capture_verified']).lower()}",
        (
            f"- mic_feature_receipts=fresh:{str(audio.get('fresh')).lower()} "
            f"age={audio.get('age_text')} device={audio.get('device')} rms={audio.get('rms')}"
        ),
        (
            f"- acoustic_channel_cue=fresh:{str(acoustic.get('fresh')).lower()} "
            f"cue={acoustic.get('channel_cue')} nearfield={acoustic.get('nearfield_voice_likelihood')} "
            f"farfield={acoustic.get('farfield_replay_likelihood')}"
        ),
        (
            "- speaker_identity_verified=false ; "
            + str(ctx["speaker_identity_reason"])
        ),
    ]
    if yt.get("title") or yt.get("dialogue_boundary"):
        lines.append(
            f"- youtube_context_title={yt.get('title')!r} boundary={yt.get('dialogue_boundary')!r}"
        )
    if correction:
        lines.append(
            "- latest_owner_sensor_correction="
            f"{correction.get('claim', correction.get('note', 'present'))}: "
            f"{correction.get('observed', '')}"
        )
    lines.append(
        "- rule: fresh visual_stigmergy plus an active eye target proves live visual frames, "
        "not owner identity. Do not claim owner identity, hear the owner specifically, or "
        "distinguish the owner from YouTube unless the matching classifier/voiceprint receipt is present."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary_for_alice())
