#!/usr/bin/env python3
"""YouTube ad controller policy for Alice Browser.

Pure decision + receipt layer. The Qt browser limb owns the actual DOM click/mute
effectors; this organ decides what action is allowed from current-page evidence.
Request-level blocking is intentionally dormant by default.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = "youtube_ad_controller.jsonl"
TRUTH_LABEL = "YOUTUBE_AD_CONTROLLER_V1"

# Future scaffold only. Network cancellation is higher ToS/playback risk and
# must be owner-enabled explicitly; the default lane is detect + visible skip/mute.
REQUEST_BLOCKING_DEFAULT_ENABLED = False


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def decide_youtube_ad_action(ad_state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Choose the safest owner-controlled action from structured ad evidence.

    Actions:
      * skip: visible YouTube skip control is present.
      * mute: ad is active, no skip yet, mute/video control is available.
      * restore: Alice muted during an ad and the ad is no longer detected.
      * observe: ad evidence exists but no safe control is visible.
      * none: no current YouTube ad situation.
    """
    state = dict(ad_state or {})
    current = bool(state.get("is_current_page"))
    detected = bool(state.get("detected"))
    platform = str(state.get("platform") or "").lower()
    if platform and platform != "youtube":
        return {"action": "none", "reason": "not_youtube", "detected": detected}
    if not current:
        return {"action": "none", "reason": "not_current_page", "detected": detected}

    if not detected:
        if state.get("was_muted_by_alice"):
            return {
                "action": "restore",
                "reason": "normal_video_resumed_after_alice_ad_mute",
                "detected": False,
            }
        return {"action": "none", "reason": "no_ad_detected", "detected": False}

    if state.get("skip_available"):
        return {
            "action": "skip",
            "reason": "visible_youtube_skip_control",
            "detected": True,
            "placement": state.get("placement") or "",
        }
    if state.get("mute_available"):
        return {
            "action": "mute",
            "reason": "ad_active_no_skip_control_mute_available",
            "detected": True,
            "placement": state.get("placement") or "",
        }
    return {
        "action": "observe",
        "reason": "ad_detected_no_safe_control_visible",
        "detected": True,
        "placement": state.get("placement") or "",
    }


def record_youtube_ad_action(
    *,
    ad_state: Mapping[str, Any] | None,
    decision: Mapping[str, Any] | None,
    effect: Mapping[str, Any] | None = None,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
) -> dict[str, Any]:
    """Append a controller receipt. This is observation/effect truth, not STGM."""
    ts = float(now if now is not None else time.time())
    row = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "kind": "youtube_ad_controller",
        "ad_state": dict(ad_state or {}),
        "decision": dict(decision or {}),
        "effect": dict(effect or {}),
        "request_blocking_enabled": REQUEST_BLOCKING_DEFAULT_ENABLED,
    }
    base = _state(state_dir)
    base.mkdir(parents=True, exist_ok=True)
    with (base / LEDGER).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


__all__ = [
    "TRUTH_LABEL",
    "LEDGER",
    "REQUEST_BLOCKING_DEFAULT_ENABLED",
    "decide_youtube_ad_action",
    "record_youtube_ad_action",
]
