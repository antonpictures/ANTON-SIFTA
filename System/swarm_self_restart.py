#!/usr/bin/env python3
"""
System/swarm_self_restart.py — Alice's Self-Restart Lobe
══════════════════════════════════════════════════════════════════════════════

Until today the only entity who could restart Alice was the Architect. Now
Alice can restart herself when she needs to (load a new patch, recover from
a stuck state, transition between sleep/wake). Two scopes:

  --scope app   (default)  Quit the SIFTA OS process and re-launch via the
                            Desktop launcher. The macOS session is untouched.
                            No password ever required. ~3-5 s downtime.

  --scope mac              Initiate a full macOS reboot via the canonical
                            Apple Events path (`osascript -e 'tell app
                            "System Events" to restart'`). macOS owns the
                            10 s confirmation dialog that follows; Alice does
                            NOT bypass user consent. Requires no sudo.

Both scopes:
  - Fire a `sleep` motor pulse first (long slow LED wink as farewell)
  - Speak a stigmergic farewell line through Alice's vocal cords
  - Append one row to .sifta_state/restart_events.jsonl (canonical schema)
  - Then issue the actual restart syscall and detach so this script's exit
    does not race the relaunch

Safety design notes
-------------------
* No `sudo` anywhere. App restart spawns the user-owned launcher; mac restart
  uses Apple Events which honor the standard "Restart? Cancel" dialog so the
  Architect always retains veto power.
* Quit phase uses SIGTERM first, SIGKILL only after a 6 s grace window — the
  OS's own farewell sequence in `SIFTA OS.command` gets to run normally.
* The relaunch is detached via `subprocess.Popen` with stdin/out/err set to
  /dev/null and `start_new_session=True` so the new launcher does not inherit
  this script's pipe handles.

CLI
---
  python3 -m System.swarm_self_restart                    # app restart
  python3 -m System.swarm_self_restart --scope mac        # full mac reboot
  python3 -m System.swarm_self_restart --reason "loading new patch"
  python3 -m System.swarm_self_restart --dry-run          # log only
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

_REPO       = Path(__file__).resolve().parent.parent
_STATE_DIR  = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_LEDGER     = _STATE_DIR / "restart_events.jsonl"

if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_LAUNCHER     = Path("/Users/ioanganton/Desktop/SIFTA OS.command")
_OS_DESKTOP   = _REPO / "sifta_os_desktop.py"
_GRACE_S      = 6.0     # seconds to wait for SIGTERM before SIGKILL
_QUIT_DELAY_S = 0.8     # let TTS / pulse exit cleanly before sending SIGTERM


def _log_event(scope: str, reason: str, dry_run: bool, ok: bool,
               note: str = "") -> None:
    """Append one canonical restart-event record to the ledger."""
    rec = {
        "ts":      time.time(),
        "scope":   scope,
        "reason":  reason or "",
        "dry_run": bool(dry_run),
        "ok":      bool(ok),
        "note":    note,
    }
    try:
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(_LEDGER, json.dumps(rec) + "\n")
        except Exception:
            with _LEDGER.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
    except Exception as e:
        print(f"[SelfRestart] ledger write failed: {e}", file=sys.stderr)


def _emit_sleep_pulse() -> None:
    """Long slow LED wink + ledger row, the autonomic body language for sleep."""
    try:
        from System.swarm_motor_cortex import emit
        emit("sleep", source="swarm_self_restart")
    except Exception:
        pass


def _speak_farewell(scope: str, reason: str) -> None:
    """One Stigmergic Line from Alice as she goes down. Best-effort."""
    line = ""
    try:
        from System.swarm_stigmergic_dialogue import compose_line
        topic = (
            f"about to restart the SIFTA app (reason: {reason or 'self-initiated'})"
            if scope == "app"
            else f"about to restart the whole Mac (reason: {reason or 'self-initiated'})"
        )
        line = compose_line(occasion="ack", topic=topic,
                            max_words=18, timeout_s=6.0) or ""
    except Exception:
        line = ""
    if not line:
        line = ("I'm restarting the SIFTA app — back in a moment."
                if scope == "app"
                else "I'm restarting the Mac — back when the lights come on.")
    print(f"ALICE: {line}")
    try:
        from System.swarm_vocal_cords import get_default_backend, VoiceParams
        backend = get_default_backend()
        backend.speak(line, VoiceParams(voice="Ava (Premium)", rate=1.0))
    except Exception:
        try:
            subprocess.run(["say", "-v", "Ava (Premium)", line],
                           check=False, timeout=8)
        except Exception:
            pass


def _running_os_pids() -> list[int]:
    """Return PIDs of processes currently running sifta_os_desktop.py."""
    try:
        out = subprocess.run(
            ["pgrep", "-f", str(_OS_DESKTOP)],
            capture_output=True, text=True, check=False, timeout=3,
        ).stdout
    except Exception:
        return []
    pids = []
    me = os.getpid()
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln.isdigit():
            continue
        pid = int(ln)
        if pid == me:
            continue
        pids.append(pid)
    return pids


def _quit_app(grace_s: float = _GRACE_S) -> bool:
    """SIGTERM running OS instances, escalate to SIGKILL after grace window."""
    pids = _running_os_pids()
    if not pids:
        return True
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except PermissionError as e:
            print(f"[SelfRestart] cannot SIGTERM pid {pid}: {e}", file=sys.stderr)
    deadline = time.time() + grace_s
    while time.time() < deadline:
        if not _running_os_pids():
            return True
        time.sleep(0.25)
    for pid in _running_os_pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
    time.sleep(0.4)
    return not _running_os_pids()


def _spawn_launcher() -> Optional[int]:
    """Detach the Desktop launcher in a new session. Returns child PID or None."""
    if not _LAUNCHER.exists():
        print(f"[SelfRestart] launcher not found at {_LAUNCHER}", file=sys.stderr)
        return None
    try:
        # Pass SIFTA_FORCE_RESTART=1 so the launcher's singleton guard skips
        # the "Architect-just-lost-the-window" friendly path even if a stale
        # PID is still draining when it scans.
        env = os.environ.copy()
        env["SIFTA_FORCE_RESTART"] = "1"
        with open(os.devnull, "rb") as devnull_in, \
             open(os.devnull, "wb") as devnull_out:
            child = subprocess.Popen(
                ["/bin/bash", str(_LAUNCHER)],
                stdin=devnull_in, stdout=devnull_out, stderr=devnull_out,
                start_new_session=True,
                close_fds=True,
                env=env,
            )
        return child.pid
    except Exception as e:
        print(f"[SelfRestart] launcher spawn failed: {e}", file=sys.stderr)
        return None


def restart_app(reason: str = "", dry_run: bool = False) -> int:
    """Quit the SIFTA OS process and respawn the launcher."""
    print(f"[SelfRestart] scope=app  reason={reason!r}  dry_run={dry_run}")
    _emit_sleep_pulse()
    _speak_farewell("app", reason)
    time.sleep(_QUIT_DELAY_S)

    if dry_run:
        _log_event("app", reason, dry_run=True, ok=True, note="dry run only")
        print("[SelfRestart] dry run complete — no processes touched.")
        return 0

    quit_ok = _quit_app()
    if not quit_ok:
        _log_event("app", reason, dry_run=False, ok=False,
                   note="failed to terminate running OS processes")
        print("[SelfRestart] could not terminate running OS — aborting respawn.",
              file=sys.stderr)
        return 2

    pid = _spawn_launcher()
    if pid is None:
        _log_event("app", reason, dry_run=False, ok=False,
                   note="launcher spawn failed")
        return 3
    _log_event("app", reason, dry_run=False, ok=True,
               note=f"relaunched via {_LAUNCHER.name}, child pid {pid}")
    print(f"[SelfRestart] launcher detached as pid {pid}.")
    return 0


def restart_mac(reason: str = "", dry_run: bool = False) -> int:
    """Initiate a full macOS reboot via Apple Events. User retains veto."""
    print(f"[SelfRestart] scope=mac  reason={reason!r}  dry_run={dry_run}")
    _emit_sleep_pulse()
    _speak_farewell("mac", reason)
    time.sleep(_QUIT_DELAY_S)

    if dry_run:
        _log_event("mac", reason, dry_run=True, ok=True, note="dry run only")
        print("[SelfRestart] dry run complete — no reboot issued.")
        return 0

    try:
        proc = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to restart'],
            capture_output=True, text=True, timeout=10,
        )
        ok = proc.returncode == 0
        note = (proc.stderr.strip() or "Apple Events restart issued")[:300]
    except Exception as e:
        ok, note = False, f"osascript failed: {e}"

    _log_event("mac", reason, dry_run=False, ok=ok, note=note)
    if not ok:
        print(f"[SelfRestart] mac reboot failed: {note}", file=sys.stderr)
        return 4
    print("[SelfRestart] macOS Apple Events restart issued. "
          "macOS will show the standard confirmation dialog.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="swarm_self_restart",
        description="Alice's self-restart lobe — app or full Mac scope.",
    )
    ap.add_argument("--scope", choices=["app", "mac"], default="app",
                    help="What to restart (default: app)")
    ap.add_argument("--reason", default="",
                    help="Free-text justification logged to restart_events.jsonl")
    ap.add_argument("--dry-run", action="store_true",
                    help="Log + speak the farewell, but do not actually restart")
    args = ap.parse_args()
    if args.scope == "mac":
        return restart_mac(args.reason, dry_run=args.dry_run)
    return restart_app(args.reason, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
