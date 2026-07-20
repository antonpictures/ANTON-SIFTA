#!/usr/bin/env python3
"""Shared on-disk camera frame paths for Alice's vision surfaces.

The canonical camera worker owns hardware capture. Display widgets read these
files; they do not open camera devices.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

FRAME_DIR_NAME = "owner_body_vision_frames"
DEVICE_FRAME_DIR_NAME = "by_device"
ACTIVE_EYE_FRAME_NAME = "active_eye_latest.png"
ROOT_ACTIVE_EYE_FRAME_NAME = "active_eye_latest.png"
DEVICE_FRAME_INDEX_NAME = "camera_device_frames.jsonl"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def camera_frame_dir(state_dir: Path | str | None = None) -> Path:
    return _state_dir(state_dir) / FRAME_DIR_NAME


def active_eye_frame_path(state_dir: Path | str | None = None) -> Path:
    return camera_frame_dir(state_dir) / ACTIVE_EYE_FRAME_NAME


def root_active_eye_frame_path(state_dir: Path | str | None = None) -> Path:
    return _state_dir(state_dir) / ROOT_ACTIVE_EYE_FRAME_NAME


def camera_device_frame_index_path(state_dir: Path | str | None = None) -> Path:
    return _state_dir(state_dir) / DEVICE_FRAME_INDEX_NAME


def safe_camera_key(device_name: Any, unique_id: Any = "") -> str:
    name = " ".join(str(device_name or "camera").strip().split()) or "camera"
    uid = str(unique_id or "").strip()
    identity = f"{uid}|{name}"
    digest = hashlib.sha256(identity.encode("utf-8", errors="replace")).hexdigest()[:12]
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "camera"
    return f"{slug}-{digest}"


def device_eye_frame_path(
    device_name: Any,
    unique_id: Any = "",
    *,
    state_dir: Path | str | None = None,
) -> Path:
    return camera_frame_dir(state_dir) / DEVICE_FRAME_DIR_NAME / f"{safe_camera_key(device_name, unique_id)}.png"


__all__ = [
    "ACTIVE_EYE_FRAME_NAME",
    "DEVICE_FRAME_DIR_NAME",
    "DEVICE_FRAME_INDEX_NAME",
    "FRAME_DIR_NAME",
    "ROOT_ACTIVE_EYE_FRAME_NAME",
    "active_eye_frame_path",
    "camera_device_frame_index_path",
    "camera_frame_dir",
    "device_eye_frame_path",
    "root_active_eye_frame_path",
    "safe_camera_key",
]
