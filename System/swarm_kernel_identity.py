"""
Phase 1: Kernel Identity Accessor.
Single source of truth for hardware binding and ownership in the SIFTA architecture.
"""
import json
import subprocess
from pathlib import Path

_STATE = Path(__file__).resolve().parent.parent / ".sifta_state"
_GENESIS_FILE = _STATE / "owner_genesis.json"

def owner_genesis_present() -> bool:
    return _GENESIS_FILE.exists()

def _read_genesis() -> dict:
    if not owner_genesis_present():
        return {}
    try:
        data = json.loads(_GENESIS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _detect_silicon() -> str:
    """Fallback if genesis hasn't occurred."""
    try:
        res = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=2
        )
        for line in res.stdout.splitlines():
            if "Serial Number (system)" in line:
                return line.split(":")[-1].strip()
    except Exception:
        pass
    return "UNKNOWN"

def owner_silicon() -> str:
    gen = _read_genesis()
    if gen and "silicon" in gen:
        return str(gen["silicon"])
    return _detect_silicon()

def owner_name() -> str:
    gen = _read_genesis()
    if gen and "owner_name" in gen:
        return str(gen["owner_name"])
    return "<unclaimed>"

def ai_default_name() -> str:
    gen = _read_genesis()
    if gen and "ai_display_name" in gen:
        return str(gen["ai_display_name"])
    return "Alice"

def is_owner_machine(serial: str) -> bool:
    return bool(serial and serial == owner_silicon())
