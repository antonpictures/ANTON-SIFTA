#!/usr/bin/env python3
"""
System/swarm_stig_daemon.py
Wrapper daemon to run Alice's single-shot sensory organs in a continuous loop
for launchd supervision. Writes PID, status, and event traces.
"""
from __future__ import annotations

import importlib
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_EVENTS = _STATE / "stig_daemon_events.jsonl"
_STATUS = _STATE / "stig_daemon_status.json"
_STOP = False


def _pidfile_for_module(mod_name: str) -> Path:
    """Return the PID file Alice's autopilot already knows how to read."""
    if "ble_radar" in mod_name:
        return _STATE / "alice_ble_radar.pid"
    if "awdl_mesh" in mod_name:
        return _STATE / "alice_awdl_mesh.pid"
    if "unified_log" in mod_name:
        return _STATE / "alice_unified_log_daemon.pid"
    if "vocal_proprioception" in mod_name:
        return _STATE / "alice_vocal_proprioception.pid"
    return _STATE / f"{mod_name.replace('.', '_')}.pid"


def _write_jsonl(path: Path, row: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), **row}, default=str) + "\n")
    except Exception:
        pass


def _write_status(mod_name: str, action: str, pidfile: Path, **extra: Any) -> None:
    """Small machine-readable heartbeat for Alice's body autopilot."""
    row = {
        "module": mod_name,
        "action": action,
        "pid": os.getpid(),
        "pidfile": str(pidfile),
        **extra,
    }
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        existing: Dict[str, Any] = {}
        if _STATUS.exists():
            try:
                loaded = json.loads(_STATUS.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    existing = loaded
            except Exception:
                existing = {}
        existing[mod_name] = {"ts": time.time(), **row}
        tmp = _STATUS.with_suffix(".tmp")
        tmp.write_text(json.dumps(existing, indent=2, default=str) + "\n", encoding="utf-8")
        tmp.replace(_STATUS)
    except Exception:
        pass


def _handle_stop(signum, _frame) -> None:  # noqa: ANN001 - signal API
    global _STOP
    _STOP = True
    _write_jsonl(
        _EVENTS,
        {"event": "stop_requested", "pid": os.getpid(), "signal": signum},
    )


def _parse_args(argv: list[str]) -> tuple[str, str, float, bool]:
    once = False
    raw = list(argv)
    if "--once" in raw:
        raw.remove("--once")
        once = True
    if len(raw) != 3:
        raise SystemExit(
            "Usage: swarm_stig_daemon.py <module> <action> <interval> [--once]"
        )
    interval = float(raw[2])
    if interval <= 0:
        raise SystemExit("interval must be > 0")
    return raw[0], raw[1], interval, once


def _main() -> None:
    global _STOP
    mod_name, action, interval, once = _parse_args(sys.argv[1:])
    pidfile = _pidfile_for_module(mod_name)

    os.chdir(_REPO)
    _STATE.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(os.getpid()))
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    print(
        f"[{mod_name}] Daemon wrapper started. PID={os.getpid()}, tracking={pidfile}",
        flush=True,
    )
    _write_jsonl(
        _EVENTS,
        {"event": "started", "module": mod_name, "action": action, "pid": os.getpid()},
    )

    try:
        sys.path.insert(0, str(_REPO))
        mod = importlib.import_module(mod_name)
        govern = getattr(mod, "govern", None)
        if not callable(govern):
            raise RuntimeError(f"{mod_name} has no callable govern(action)")

        iteration = 0
        while not _STOP:
            iteration += 1
            try:
                result: Optional[Dict[str, Any]] = govern(action)
                ok = bool(result.get("ok", True)) if isinstance(result, dict) else True
                _write_status(
                    mod_name,
                    action,
                    pidfile,
                    ok=ok,
                    iteration=iteration,
                    last_error=None,
                )
            except Exception as exc:
                _write_status(
                    mod_name,
                    action,
                    pidfile,
                    ok=False,
                    iteration=iteration,
                    last_error=f"{type(exc).__name__}: {exc}",
                )
                _write_jsonl(
                    _EVENTS,
                    {
                        "event": "govern_error",
                        "module": mod_name,
                        "action": action,
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
                print(
                    f"[{mod_name}] Error in govern({action}): {exc}",
                    file=sys.stderr,
                    flush=True,
                )
            if once:
                break
            time.sleep(interval)
    finally:
        _write_jsonl(
            _EVENTS,
            {"event": "stopped", "module": mod_name, "action": action, "pid": os.getpid()},
        )
        pidfile.unlink(missing_ok=True)


if __name__ == "__main__":
    _main()
