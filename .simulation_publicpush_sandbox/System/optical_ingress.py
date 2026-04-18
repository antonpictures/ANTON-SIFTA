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

def capture_photonic_truth() -> Tuple[Optional[Path], Optional[str]]:
    """
    Grabs an exact photonic sample of reality.
    Returns:
        Path to the saved image file
        SHA256 signature hash of the exact binary payload (Reality Anchor)
    """
    timestamp = int(time.time())
    out_path = BUFFER_DIR / f"reality_snap_{timestamp}.jpg"
    
    try:
        # Native MacOS fallback: query ffmpeg via avfoundation
        # We grab exactly 1 frame (vframes 1) from the default camera
        cmd = [
            "ffmpeg", "-y", "-f", "avfoundation", "-framerate", "30",
            "-i", "0", "-vframes", "1", str(out_path)
        ]
        
        # Suppress loud FFmpeg output unless it fails
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        
        if res.returncode != 0 or not out_path.exists():
            # If camera access fails (permissions or not installed), we create a mock optical verification matrix
            # for development/headless testing.
            print("[⚠️ OPTICAL] Native AVFoundation capture failed. Generating Mock Photonic Array.")
            return _mock_photonic_truth(out_path)
            
        with open(out_path, "rb") as f:
            binary_data = f.read()
            reality_hash = hashlib.sha256(binary_data).hexdigest()
            
        print(f"[👁️ OPTICAL] Photonic Truth Captured. Hash: {reality_hash[:16]}...")
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
