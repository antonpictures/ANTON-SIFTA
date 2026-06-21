#!/usr/bin/env python3
"""Single safe source for Apple hardware serial (IOPlatformSerialNumber)."""
from __future__ import annotations

import os
import subprocess

_SERIAL_CACHE: str | None = None


def read_apple_serial() -> str:
    """
    Read IOPlatformSerialNumber via ioreg with a fixed argv (no shell).
    Returns UNKNOWN_SERIAL on failure or non-macOS.
    """
    global _SERIAL_CACHE
    if _SERIAL_CACHE:
        return _SERIAL_CACHE
    override = os.environ.get("SIFTA_HOMEWORLD_SERIAL", "").strip()
    if override:
        _SERIAL_CACHE = override
        return _SERIAL_CACHE
    try:
        proc = subprocess.run(
            ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in proc.stdout.splitlines():
            if "IOPlatformSerialNumber" in line:
                serial = line.split('"')[-2].strip()
                if serial:
                    _SERIAL_CACHE = serial
                    return _SERIAL_CACHE
    except Exception:
        pass
    _SERIAL_CACHE = "UNKNOWN_SERIAL"
    return _SERIAL_CACHE


def reset_serial_cache_for_test() -> None:
    global _SERIAL_CACHE
    _SERIAL_CACHE = None
