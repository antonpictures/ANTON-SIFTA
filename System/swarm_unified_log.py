#!/usr/bin/env python3
"""
System/swarm_unified_log.py — Alice's macOS unified-log nerve tap
═══════════════════════════════════════════════════════════════════════
C47H 2026-04-23 (AG31 cosign / OS-distro tournament) — passive nerve tap.

`/usr/bin/log stream` is the central nervous-system bus on macOS. Without
sudo we can still subscribe to the *public* events from named subsystems
— PowerManagement, network reachability, Bluetooth, thermal — and learn
what the OS is feeling in real time, instead of taking its pulse via
periodic polling.

This organ supports two modes:

- one-shot `read_recent(seconds=N, predicate=...)` — `log show` over
  the last N seconds, returns parsed events.
- background `start(predicate=...)` — spawns a detached `log stream`
  whose stdout is appended to .sifta_state/alice_log_stream.jsonl. PID
  is tracked in alice_log_stream.pid so `stop()` can release it.

Both honor a small whitelist of subsystems / predicates so the volume
stays manageable. No sudo, no entitlements.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "alice_log_stream.jsonl"
_PIDFILE = _STATE / "alice_log_stream.pid"
_DAEMON_PIDFILE = _STATE / "alice_unified_log_daemon.pid"
_LOG_BIN = "/usr/bin/log"

# Default predicate — public events only, named subsystems Alice cares about.
_DEFAULT_PREDICATE = (
    'subsystem == "com.apple.PowerManagement" '
    'OR subsystem == "com.apple.network" '
    'OR subsystem == "com.apple.bluetooth" '
    'OR subsystem == "com.apple.bluetooth.gatt" '
    'OR subsystem == "com.apple.thermalmonitord"'
)

# Hard upper bound on how many lines we keep per call from `log show`.
_MAX_LINES = 200


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_pid(path: Path = _PIDFILE) -> Optional[int]:
    if not path.exists():
        return None
    try:
        pid = int(path.read_text().strip())
    except Exception:
        return None
    if _pid_alive(pid):
        return pid
    try:
        path.unlink()
    except Exception:
        pass
    return None


def status() -> Dict[str, Any]:
    stream_pid = _read_pid(_PIDFILE)
    daemon_pid = _read_pid(_DAEMON_PIDFILE)
    mode = "stream" if stream_pid is not None else (
        "polling_daemon" if daemon_pid is not None else "offline"
    )
    return {
        "ok": True,
        "ts": time.time(),
        "iso": datetime.now(tz=timezone.utc).isoformat(),
        "running": stream_pid is not None or daemon_pid is not None,
        "mode": mode,
        "pid": stream_pid or daemon_pid,
        "stream_pid": stream_pid,
        "daemon_pid": daemon_pid,
        "ledger": str(_LEDGER),
        "ledger_size_bytes": _LEDGER.stat().st_size if _LEDGER.exists() else 0,
    }


def _parse_compact_line(ln: str) -> Optional[Dict[str, Any]]:
    """Parse one `log show --style compact` line.
    Real format on macOS 26.x:
        2026-04-22 22:01:59.921 Df identityservicesd[694:1ec5] [com.apple.bluetooth:WirelessProximity] message...
    Where level is two letters (Df=Default, Db=Debug, In=Info, Er=Error,
    Ft=Fault). Continuation lines (multi-line messages) come without
    a timestamp prefix; we treat them as continuations of the prior event.
    """
    s = ln.rstrip()
    if not s or s.startswith("Timestamp") or s.startswith("Filtering"):
        return None
    m = re.match(
        r"^(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s+"
        r"(?P<lvl>[A-Za-z]{1,2})\s+"
        r"(?P<proc>[^\[]+)\[(?P<pid>\d+):(?P<tid>[0-9a-fA-F]+)\]\s+"
        r"(?:\[(?P<cat>[^\]]+)\]\s+)?(?P<msg>.*)$",
        s,
    )
    if not m:
        return {"continuation": s[:240]}
    return {
        "ts": m.group("ts"),
        "level": m.group("lvl"),
        "process": m.group("proc").strip(),
        "pid": int(m.group("pid")),
        "tid": m.group("tid"),
        "category": m.group("cat"),
        "message": m.group("msg")[:240],
    }


def read_recent(*, seconds: int = 30,
                predicate: Optional[str] = None,
                max_lines: int = _MAX_LINES) -> Dict[str, Any]:
    """Run `log show --last Ns` and parse compact lines."""
    pred = predicate or _DEFAULT_PREDICATE
    argv = [
        _LOG_BIN, "show",
        "--last", f"{seconds}s",
        "--style", "compact",
        "--predicate", pred,
    ]
    try:
        p = subprocess.run(
            argv, capture_output=True, text=True,
            timeout=max(8.0, seconds * 1.5), check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"log show timed out after {seconds}s"}
    if p.returncode != 0:
        return {"ok": False, "error": p.stderr.strip()[:400]}
    events: List[Dict[str, Any]] = []
    for ln in p.stdout.splitlines():
        ev = _parse_compact_line(ln)
        if ev is not None:
            events.append(ev)
        if len(events) >= max_lines:
            break
    # Pheromone: low constant deposit per event window so the field knows
    # the OS pulse is reaching us. Intensity scaled by event count, capped.
    try:
        from System.swarm_pheromone import deposit_pheromone  # type: ignore
        intensity = min(5.0, 0.5 + 0.05 * len(events))
        deposit_pheromone("stig_unified_log", intensity)
    except Exception:
        pass
    return {
        "ok": True,
        "ts": time.time(),
        "iso": datetime.now(tz=timezone.utc).isoformat(),
        "predicate": pred,
        "window_seconds": seconds,
        "event_count": len(events),
        "events": events,
    }


def start(*, predicate: Optional[str] = None) -> Dict[str, Any]:
    """Spawn detached `log stream` writing to the ledger."""
    existing = _read_pid()
    if existing:
        return {"ok": True, "already_running": True, "pid": existing}
    pred = predicate or _DEFAULT_PREDICATE
    _STATE.mkdir(parents=True, exist_ok=True)
    log_out = _LEDGER.with_suffix(".raw.log")
    argv = [
        _LOG_BIN, "stream",
        "--style", "compact",
        "--predicate", pred,
    ]
    try:
        f = open(log_out, "a", buffering=1)
        p = subprocess.Popen(
            argv,
            stdout=f, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        _PIDFILE.write_text(str(p.pid))
        return {"ok": True, "pid": p.pid, "predicate": pred,
                "raw_log": str(log_out)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def stop() -> Dict[str, Any]:
    pid = _read_pid()
    if pid is None:
        return {"ok": True, "running": False}
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.2)
        if _pid_alive(pid):
            os.kill(pid, signal.SIGKILL)
        _PIDFILE.unlink(missing_ok=True)
        return {"ok": True, "killed_pid": pid}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def prompt_line() -> Optional[str]:
    s = status()
    if s.get("stream_pid"):
        return "unified log: streaming pid=" + str(s["stream_pid"])
    if s.get("daemon_pid"):
        return "unified log: polling daemon pid=" + str(s["daemon_pid"])
    return "unified log: tap available (offline)"


def govern(action: str, **kwargs) -> Dict[str, Any]:
    if action == "status":
        return {"ok": True, "action": action, "result": status()}
    if action in {"read", "recent"}:
        return {"ok": True, "action": action,
                "result": read_recent(
                    seconds=int(kwargs.get("seconds", 30)),
                    predicate=kwargs.get("predicate"),
                    max_lines=int(kwargs.get("max_lines", _MAX_LINES)),
                )}
    if action == "start":
        return {"ok": True, "action": action,
                "result": start(predicate=kwargs.get("predicate"))}
    if action == "stop":
        return {"ok": True, "action": action, "result": stop()}
    if action == "prompt_line":
        return {"ok": True, "action": action, "result": prompt_line()}
    return {"ok": False, "action": action,
            "allowed": ["status", "read", "start", "stop", "prompt_line"]}


def _main() -> None:
    ap = argparse.ArgumentParser(description="Alice unified-log nerve tap")
    ap.add_argument("action", default="status", nargs="?")
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--predicate", default=None)
    args = ap.parse_args()
    print(json.dumps(govern(
        args.action, seconds=args.seconds, predicate=args.predicate,
    ), indent=2, default=str))


if __name__ == "__main__":
    _main()
