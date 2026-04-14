#!/usr/bin/env python3
"""Single safe source for Apple hardware serial (IOPlatformSerialNumber)."""
from __future__ import annotations

import subprocess


def read_apple_serial() -> str:
    """
    Read IOPlatformSerialNumber via ioreg with a fixed argv (no shell).
    Returns UNKNOWN_SERIAL on failure or non-macOS.
    """
    try:
        proc = subprocess.run(
            ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in proc.stdout.splitlines():
            if "IOPlatformSerialNumber" in line:
                return line.split('"')[-2].strip()
    except Exception:
        pass
    return "UNKNOWN_SERIAL"
