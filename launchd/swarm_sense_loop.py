#!/usr/bin/env python3
"""
launchd/swarm_sense_loop.py
═══════════════════════════════════════════════════════════════════════════
Periodic snapshot loop for on-demand SIFTA sensory organs.

Some organs (window manager, hardware bridge, network state, power) do not
need persistent streams. This LaunchAgent polls them, writes a heartbeat, and
exits cleanly under launchd stop signals.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PIDFILE = _STATE / "alice_sense_loop.pid"
_EVENTS = _STATE / "sense_loop_events.jsonl"
_STATUS = _STATE / "sense_loop_status.json"
_STOP = False

Poller = Tuple[str, Callable[[], None]]


def _write_jsonl(path: Path, row: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), **row}, default=str) + "\n")
    except Exception:
        pass


def _write_status(row: Dict[str, Any]) -> None:
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        tmp = _STATUS.with_suffix(".tmp")
        tmp.write_text(json.dumps({"ts": time.time(), **row}, indent=2, default=str) + "\n")
        tmp.replace(_STATUS)
    except Exception:
        pass


def _handle_stop(signum, _frame) -> None:  # noqa: ANN001 - signal API
    global _STOP
    _STOP = True
    _write_jsonl(_EVENTS, {"event": "stop_requested", "pid": os.getpid(), "signal": signum})


def _load_pollers() -> List[Poller]:
    """Load each organ independently so one bad import does not blind all."""
    pollers: List[Poller] = []
    imports = (
        ("window_focus", "System.swarm_active_window", "write_snapshot"),
        ("usb_devices", "System.swarm_hardware_bridge", "poll_usb_devices"),
        ("network_interfaces", "System.swarm_network_state", "poll_network_interfaces"),
        ("power_state", "System.swarm_nanobot_power", "poll_power_state"),
    )
    for name, module_name, func_name in imports:
        try:
            module = __import__(module_name, fromlist=[func_name])
            func = getattr(module, func_name)
            if callable(func):
                pollers.append((name, func))
        except Exception as exc:
            _write_jsonl(
                _EVENTS,
                {
                    "event": "poller_import_failed",
                    "poller": name,
                    "module": module_name,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
    return pollers


def main(argv: list[str] | None = None) -> int:
    global _STOP
    parser = argparse.ArgumentParser(description="SIFTA LaunchAgent sense loop")
    parser.add_argument("--interval", type=float, default=15.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    if args.interval <= 0:
        parser.error("--interval must be > 0")

    os.chdir(_REPO)
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    _STATE.mkdir(parents=True, exist_ok=True)
    _PIDFILE.write_text(str(os.getpid()))
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    print(f"[SenseLoop] Started. PID={os.getpid()}", flush=True)
    _write_jsonl(_EVENTS, {"event": "started", "pid": os.getpid()})

    try:
        pollers = _load_pollers()
        iteration = 0
        while not _STOP:
            iteration += 1
            results: Dict[str, str] = {}
            for name, func in pollers:
                try:
                    func()
                    results[name] = "ok"
                except Exception as exc:
                    results[name] = f"{type(exc).__name__}: {exc}"
                    _write_jsonl(
                        _EVENTS,
                        {
                            "event": "poller_error",
                            "poller": name,
                            "error": results[name],
                        },
                    )
                    print(f"[SenseLoop] {name} error: {exc}", flush=True)
            _write_status(
                {
                    "pid": os.getpid(),
                    "iteration": iteration,
                    "pollers": list(results.keys()),
                    "results": results,
                    "ok": bool(pollers),
                }
            )
            if args.once:
                break
            time.sleep(args.interval)
        return 0
    finally:
        _write_jsonl(_EVENTS, {"event": "stopped", "pid": os.getpid()})
        _PIDFILE.unlink(missing_ok=True)
        print("[SenseLoop] Exited cleanly.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
