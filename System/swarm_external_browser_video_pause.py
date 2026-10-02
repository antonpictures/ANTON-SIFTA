#!/usr/bin/env python3
"""Integrate browser-aware external video pause with the existing cowatch trigger.

Truth label: EXTERNAL_BROWSER_VIDEO_PAUSE_V2

Knows which browser is on and which one is playing. Degrades gracefully: if the
external browser is unreachable, Alice still speaks and the Alice-Browser pause still works.
"""
from __future__ import annotations

from typing import Any, Mapping

TRUTH_LABEL = "EXTERNAL_BROWSER_VIDEO_PAUSE_V2"


def try_pause_external_video(url: str = "", port: int = 9222) -> tuple[bool, dict[str, Any]]:
    """Pause video in whichever external browser is playing one. Never raises."""
    try:
        from System.swarm_external_browser_pause import pause_video_anywhere

        receipt = pause_video_anywhere(url)
        return bool(receipt.get("ok")), receipt
    except Exception as e:
        return False, {"ok": False, "action": "pause", "reason": "error", "details": str(e)}


def try_pause_external_video_if_playing(
    url: str = "", port: int = 9222
) -> tuple[bool, dict[str, Any]]:
    """Speech-path pause: only when a video is genuinely playing. Never raises.

    Use this from the speech path, not `try_pause_external_video`: the plain variant
    will happily "pause" an already-paused tab (pick_video_browser falls back to any
    video tab), and the matching resume would then PLAY it — starting a video the
    owner had deliberately stopped.
    """
    try:
        from System.swarm_external_browser_pause import pause_only_if_playing

        receipt = pause_only_if_playing(url)
        return bool(receipt.get("ok")), receipt
    except Exception as e:
        return False, {"ok": False, "action": "pause", "reason": "error", "details": str(e)}


def try_resume_external_video(url: str = "", port: int = 9222) -> tuple[bool, dict[str, Any]]:
    """Resume video in whichever external browser was paused. Never raises."""
    try:
        from System.swarm_external_browser_pause import resume_video_anywhere

        receipt = resume_video_anywhere(url)
        return bool(receipt.get("ok")), receipt
    except Exception as e:
        return False, {"ok": False, "action": "play", "reason": "error", "details": str(e)}


def enrich_cowatch_body_loop(
    url: str, receipt: Mapping[str, Any], port: int = 9222
) -> Mapping[str, Any]:
    """Augment the Alice-Browser cowatch receipt with the external-browser attempt.

    Alice-Browser stays primary; external is additive. `ok` is true if EITHER succeeded,
    so a missing external browser never blocks Alice from talking.
    """
    external_ok, external_receipt = try_pause_external_video(url, port)

    merged = dict(receipt)
    merged["external"] = external_receipt
    merged["external_ok"] = external_ok
    merged["external_browser"] = external_receipt.get("browser")
    merged["external_effector"] = external_receipt.get("effector")
    merged["external_reason"] = external_receipt.get("reason") or None
    merged["ok"] = bool(receipt.get("ok")) or external_ok
    return merged


def detect_external_video_tab(url: str = "", port: int = 9222) -> Mapping[str, Any]:
    """Detection helper: which browser holds a video right now."""
    try:
        from System.swarm_external_browser_pause import detect_external_video_tab as _d

        return _d(url, port)
    except Exception as e:
        return {"detected": False, "count": 0, "targets": [], "reason": str(e)}


def browser_awareness() -> Mapping[str, Any]:
    """Computer-use awareness: running browsers, frontmost app, playing video tabs."""
    try:
        from System.swarm_external_browser_pause import browser_awareness_snapshot

        return browser_awareness_snapshot()
    except Exception as e:
        return {"running_browsers": [], "frontmost_app": "", "video_tabs": [], "reason": str(e)}


__all__ = [
    "TRUTH_LABEL",
    "try_pause_external_video",
    "try_pause_external_video_if_playing",
    "try_resume_external_video",
    "enrich_cowatch_body_loop",
    "detect_external_video_tab",
    "browser_awareness",
]
