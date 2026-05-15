"""Code-first input lane for Talk → Alice (no LLM).

Classifies a user turn so multimodal preprocessing can stamp structured
telemetry before base weights see raw social / vision tokens.
"""
from __future__ import annotations

from enum import Enum


class InputRealityLane(str, Enum):
    """How this turn should be framed for receipt-backed grounding."""

    LOCAL_SENSOR_OR_PASTE = "LOCAL_SENSOR_OR_PASTE"
    REMOTE_URL_PRESENT = "REMOTE_URL_PRESENT"
    SHORT_ROOM_SPEECH = "SHORT_ROOM_SPEECH"


def classify_user_turn(
    raw_text: str,
    *,
    has_image: bool,
    long_paste_chars: int = 150,
) -> InputRealityLane:
    t = raw_text or ""
    s = t.strip()
    if has_image:
        return InputRealityLane.LOCAL_SENSOR_OR_PASTE
    if len(s) >= long_paste_chars:
        return InputRealityLane.LOCAL_SENSOR_OR_PASTE
    if "]" in t:
        return InputRealityLane.LOCAL_SENSOR_OR_PASTE
    low = s.lower()
    if "http://" in low or "https://" in low:
        return InputRealityLane.REMOTE_URL_PRESENT
    return InputRealityLane.SHORT_ROOM_SPEECH


def format_lane_banner(lane: InputRealityLane) -> str:
    """Single-line machine banner prepended inside the telemetry receipt."""
    if lane is InputRealityLane.LOCAL_SENSOR_OR_PASTE:
        return (
            "ingress_lane=LOCAL_SENSOR_OR_PASTE; "
            "truth_label=OBSERVED; meaning=direct node-local observation stream "
            "(sensor frame and/or paste captured on this machine)."
        )
    if lane is InputRealityLane.REMOTE_URL_PRESENT:
        return (
            "ingress_lane=REMOTE_URL_PRESENT; "
            "truth_label=OBSERVED; meaning=URL tokens are citations inside a local paste "
            "event on this machine, not proof the model visited those hosts."
        )
    return (
        "ingress_lane=SHORT_ROOM_SPEECH; "
        "truth_label=OBSERVED; meaning=short direct room turn (no bulk paste envelope)."
    )
