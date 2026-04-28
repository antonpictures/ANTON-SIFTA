"""sensor_gate.py – sensory lock‑on utility for SIFTA.

Provides a simple wrapper that attempts to open a list of device indices for a given
sensor type (camera, microphone, BLE). The first successful device is returned and
the attempt log is written to the stigmergic trace.
"""

import subprocess
import json
import time
import uuid
from pathlib import Path
from typing import List, Tuple, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TRACE = _STATE / "ide_stigmergic_trace.jsonl"
_LOCK_STATE = _STATE / "sensor_gate_lock.json"

_TRACE.parent.mkdir(parents=True, exist_ok=True)

def _log_trace(event: dict) -> None:
    """Append a trace row to the stigmergic bus.
    The caller should provide keys: ts, trace_id, kind, action, details.
    """
    event.setdefault("ts", time.time())
    event.setdefault("trace_id", str(uuid.uuid4()))
    with open(_TRACE, "a") as f:
        f.write(json.dumps(event) + "\n")


def _write_lock_state(
    *,
    locked: bool,
    reason: str,
    description: str,
    device_index: Optional[int] = None,
    logs: Optional[List[str]] = None,
) -> None:
    """Persist current Sensor Gate truth for the Body Monitor."""
    row = {
        "ts": time.time(),
        "locked": bool(locked),
        "reason": reason,
        "description": description,
        "device_index": device_index,
        "logs": logs or [],
    }
    _LOCK_STATE.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOCK_STATE, "w") as f:
        json.dump(row, f, indent=2)


def ensure_lock_state(description: str = "Sensor Gate") -> dict:
    """Return current lock state without creating a fake lock-attempt ledger."""
    if not _LOCK_STATE.exists():
        return {
            "ts": time.time(),
            "locked": False,
            "reason": "not_attempted",
            "description": description,
            "device_index": None,
            "logs": ["Sensor gate has not attempted a lock-on in this runtime yet."],
        }
    try:
        return json.loads(_LOCK_STATE.read_text())
    except (OSError, json.JSONDecodeError):
        return {
            "ts": time.time(),
            "locked": False,
            "reason": "state_corrupt",
            "description": description,
            "device_index": None,
            "logs": ["Sensor gate state was unreadable."],
        }


def lock_on_devices(device_cmd: List[str], description: str) -> Tuple[Optional[int], List[str]]:
    """Iterate over a series of shell commands that attempt to open a device.

    Parameters
    ----------
    device_cmd: List[str]
        Each entry is a shell command that should succeed (exit code 0) if the device
        is available. The command may be something like ``"ffmpeg -f avfoundation -list_devices true"``
        for macOS camera enumeration, but for simplicity we just run the provided
        command and check return code.
    description: str
        Human‑readable description for logging.

    Returns
    -------
    Tuple[Optional[int], List[str]]
        The index of the first successful command (0‑based) and a list of log
        messages describing each attempt.
    """
    logs = []
    for idx, cmd in enumerate(device_cmd):
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                logs.append(f"{description} device {idx} succeeded.")
                _log_trace({
                    "kind": "sensor_lock_on",
                    "action": "lock_success",
                    "description": description,
                    "device_index": idx,
                    "stdout": result.stdout.strip(),
                })
                _write_lock_state(
                    locked=True,
                    reason="lock_success",
                    description=description,
                    device_index=idx,
                    logs=logs,
                )
                return idx, logs
            else:
                logs.append(
                    f"{description} device {idx} failed (code {result.returncode})."
                )
        except Exception as e:
            logs.append(f"{description} device {idx} exception: {e}")
        # Log each failure
        _log_trace({
            "kind": "sensor_lock_on",
            "action": "lock_fail",
            "description": description,
            "device_index": idx,
            "error": logs[-1],
        })
    # No device succeeded
    _log_trace({
        "kind": "sensor_lock_on",
        "action": "lock_all_failed",
        "description": description,
        "error": "All candidates failed",
    })
    _write_lock_state(
        locked=False,
        reason="lock_all_failed",
        description=description,
        logs=logs,
    )
    return None, logs

# Example usage (not executed automatically):
# camera_cmds = ["ffmpeg -f avfoundation -i 0 -t 0.1 -y /dev/null", "ffmpeg -f avfoundation -i 1 -t 0.1 -y /dev/null"]
# idx, logs = lock_on_devices(camera_cmds, "Camera")
# print(logs)
