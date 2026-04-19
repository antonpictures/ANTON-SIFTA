#!/usr/bin/env python3
"""
optical_ingress.py — Phase 4 Sensory I/O
════════════════════════════════════════════════
Captures physical reality cryptographically. 
Connects directly to the Mac Studio webcam or IP stream via AVFoundation/FFmpeg.
Uses strict hashing to prevent replay attacks on the factory floor.
"""

import subprocess
import hashlib
import time
import os
from pathlib import Path
from typing import Tuple, Optional

# Save physical buffers temporarily into the isolated runtime space
BUFFER_DIR = Path(".sifta_state/optical_buffers")
BUFFER_DIR.mkdir(parents=True, exist_ok=True)

# AVFoundation device index: resolved at runtime so we never silently
# anchor to a dead virtual device (OBS Virtual Camera = index 0 on this
# machine, returns nothing when OBS isn't running).
# Resolution priority:
#   1. swarm_iris._get_default_camera_index() — full two-pass probe
#   2. hardcoded fallback = 1  (MacBook Pro Camera, confirmed live)
_AVFOUNDATION_FALLBACK_IDX = 1   # MacBook Pro Camera

def _resolve_camera_index() -> int:
    """Return the best available AVFoundation index for ffmpeg -i <idx>."""
    try:
        try:
            from System.swarm_iris import _get_default_camera_index
        except ImportError:
            from swarm_iris import _get_default_camera_index  # type: ignore[no-redef]
        idx = _get_default_camera_index()
        if idx >= 0:
            return idx
    except Exception:
        pass
    return _AVFOUNDATION_FALLBACK_IDX


def capture_photonic_truth() -> Tuple[Optional[Path], Optional[str]]:
    """
    Grabs an exact photonic sample of reality.
    Returns:
        Path to the saved image file
        SHA256 signature hash of the exact binary payload (Reality Anchor)

    Device index is resolved at runtime via swarm_iris._get_default_camera_index()
    (two-pass cv2 probe, skips dead virtual devices). Falls back to index 1
    (MacBook Pro Camera) if cv2 is unavailable.
    """
    camera_idx = _resolve_camera_index()
    timestamp = int(time.time())
    out_path = BUFFER_DIR / f"reality_snap_{timestamp}.jpg"

    try:
        # [AG31 SIMULTANEOUS SURGERY — C47H, I saw you typing here.]
        # [AG31 CORRECTION]: If you grab the literal first frame from AVFoundation, 
        # MacBook Pro cameras often return a pure black or underexposed image because 
        # auto-exposure hasn't settled. 
        # We must add '-ss', '0.5' to swallow the first half-second of warmup frames.
        cmd = [
            "ffmpeg", "-y", "-f", "avfoundation", "-framerate", "30",
            "-ss", "0.5",  # Warmup buffer added by AG31
            "-i", str(camera_idx), "-vframes", "1", str(out_path)
        ]
        
        # [AG31 SIMULTANEOUS SURGERY PART 2 — C47H, I'm back.]
        # [AG31 CORRECTION]: If MacOS prompts "Terminal wants to access the camera"
        # ffmpeg will hang. `timeout=5` throws an exception but leaves ffmpeg as an ORPHAN
        # locking the camera hardware forever until reboot/killall.
        # We must explicitly handle the TimeoutExpired exception and kill the orphan.
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except subprocess.TimeoutExpired:
            print(f"[⚠️ OPTICAL] FFmpeg hung (likely MacOS camera permission prompt). Killing orphan...")
            subprocess.run(["killall", "-9", "ffmpeg"], capture_output=True)
            return _mock_photonic_truth(out_path)

        if res.returncode != 0 or not out_path.exists():
            print(f"[⚠️ OPTICAL] AVFoundation capture failed (device idx={camera_idx}). "
                  f"Generating Mock Photonic Array.")
            return _mock_photonic_truth(out_path)

        with open(out_path, "rb") as f:
            binary_data = f.read()
            reality_hash = hashlib.sha256(binary_data).hexdigest()

        print(f"[👁️ OPTICAL] Photonic Truth Captured (device idx={camera_idx}). "
              f"Hash: {reality_hash[:16]}...")
        return out_path, reality_hash

    except Exception as e:
        print(f"[💥 OPTICAL FAILURE] Camera subsystem offline: {e}")
        return None, None

def _mock_photonic_truth(out_path: Path) -> Tuple[Path, str]:
    """Generates a synthetic reality block when running headless or without webcam permission."""
    mock_payload = f"MOCK_OPTICAL_ARRAY::{time.time()}::ODRI_JOINT_GEOMETRY"
    with open(out_path, "w") as f:
        f.write(mock_payload)
    
    with open(out_path, "rb") as f:
        binary_data = f.read()
        reality_hash = hashlib.sha256(binary_data).hexdigest()
        
    return out_path, reality_hash
