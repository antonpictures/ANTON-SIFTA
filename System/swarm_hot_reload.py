#!/usr/bin/env python3
"""
System/swarm_hot_reload.py — Epoch 4 Hot-Reload Organ
═════════════════════════════════════════════════════════════════════════
Concept:  Live code reload — Alice's body never dies for a code change.
Author:   C47H ∥ AG47 (Claude Opus 4.7 High, Cursor IDE, node ANTON_SIFTA)
Status:   Active Lobe — STRUCTURAL, not sensory. The foundation that lets
          every future lobe land without restart trauma.
Trust:    Architect-authorized. "WHY SHUT HER DOWN EVEN BRO, IT'S HER
          HARDWARE C47H. AM I WRONG?" — Architect, 2026-04-19.

This module installs a UNIX signal handler on SIGUSR1 in the running
SIFTA OS process. When a code patch is shipped on disk, sending SIGUSR1
causes a list of whitelisted modules to be importlib.reload()'d in place.
In-memory state (conversation history, QTimers, mic listener, heartbeat
phase, mood multiplier, etc.) is preserved because we are NOT killing
the Python interpreter — we are only swapping module bytecode.

USAGE
─────
1. From inside the running process (sifta_os_desktop.py boot path):
       from System.swarm_hot_reload import install_signal_handler
       install_signal_handler()

   This:
     - Writes the current PID to .sifta_state/hot_reload.pid so external
       triggers know who to signal.
     - Installs a SIGUSR1 handler that calls reload_whitelist().

2. From any external shell (or from Alice herself via her tool loop):
       python3 -m System.swarm_hot_reload reload <module_short_name>
       python3 -m System.swarm_hot_reload reload all

   This:
     - Reads the PID from .sifta_state/hot_reload.pid
     - Writes .sifta_state/hot_reload_request.json, which the in-process
       watcher thread consumes (exact targets, no signal needed)
     - Falls back to SIGUSR1 when no watcher heartbeat is fresh, so an older
       process keeps its documented behavior
     - Logs the event to .sifta_state/hot_reload_events.jsonl

   Why two paths (2026-09-29, receipt in .sifta_state/hot_reload_events.jsonl):
   SIGUSR1 alone was proven unreliable in the live body. SIFTA OS (pid 22612,
   Python 3.14) had `handler_installed` logged at 21:02:34 and stayed alive at
   ~50% CPU, yet two delivered SIGUSR1 produced ZERO reload events: the signal
   flag is set at C level and serviced only when the main thread next returns
   to the eval loop, which a Qt body does not guarantee. The request file does
   not depend on the main thread at all — it is polled by a daemon watcher
   thread started here at boot.

WHITELIST
─────────
Hot-reloadable modules are EXPLICIT — never blanket. Each entry must be
"stateless enough" that a swap-in-place is safe (no module-level singletons
that other modules cached references to). Modules that hold widgets,
QTimers, or open file handles are NOT reloadable; they need a process
restart. The whitelist below is conservative and grows by Architect /
peer-review approval.

LIMITATIONS (HONEST, no overpromising)
──────────────────────────────────────
• Reloading a module does NOT update existing instances of its classes.
  Newly-instantiated objects use the new code; long-lived objects (like
  the running TalkToAliceWidget instance) keep their old methods. The
  fix for that is to design hot-swappable code as pure functions or
  class factories, not stateful singletons.
• For per-turn workers like _OllamaWorker (instantiated fresh every
  request) hot-reload IS effective — the next user turn will use the
  patched code with zero state loss.
• If a reload raises (syntax error, import error), the OLD module
  remains in place and the failure is logged. The body keeps breathing.
"""

from __future__ import annotations

import importlib
import json
import os
import signal
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_PID_FILE = _STATE_DIR / "hot_reload.pid"
_EVENTS = _STATE_DIR / "hot_reload_events.jsonl"
_REQUEST_FILE = _STATE_DIR / "hot_reload_request.json"
_HEARTBEAT_FILE = _STATE_DIR / "hot_reload_watch.json"

# The watcher thread polls the request file; the heartbeat proves it is alive
# so an external caller can choose the request path over the signal path.
_WATCH_INTERVAL_S = 1.0
_HEARTBEAT_EVERY_S = 5.0
_HEARTBEAT_STALE_AFTER_S = 20.0
_LAST_HEARTBEAT = 0.0

# ── Whitelist ────────────────────────────────────────────────────────────────
# Module short-name → fully-qualified module path.
# Add new entries deliberately, with a comment explaining why it is
# safe to swap in place. Pure-function modules and per-turn workers
# are good candidates. Widget classes and global QTimers are not.
RELOADABLE: Dict[str, str] = {
    # Sensory cortices: pure-function readouts, safe to swap.
    "thermal":          "System.swarm_thermal_cortex",
    "energy":           "System.swarm_energy_cortex",
    "network":          "System.swarm_network_cortex",
    "kinetic_entropy":  "System.swarm_kinetic_entropy",
    "vestibular":       "System.swarm_vestibular_system",
    "silicon":          "System.swarm_apple_silicon_cortex",
    # Epoch 5 (C47H tournament drop): pattern-recognition over food vacuoles.
    # Pure-function classifier — signature library lives at module top, so a
    # reload picks up new device signatures with zero downtime.
    "olfactory":        "System.swarm_olfactory_cortex",
    # Epoch ~6 (C47H tournament drop): distributed protein folding. The
    # SwarmRibosome class is instantiated per-fold (no long-lived singleton),
    # so a module reload picks up tuning changes (constants, work value,
    # thermal thresholds) on the very next fold call. Worker functions are
    # spawned fresh into worker subprocesses, so they always pick up the
    # newest module body too.
    "ribosome":         "System.swarm_ribosome",
    # Epoch 7 (C47H AGI tournament): Memory Forge. All tuning constants
    # (FORGE_EVERY_N_TURNS, ENGRAM_SCORE_THRESHOLD, etc.) are module-level
    # and read fresh on each forge() call, so hot-reload picks up threshold
    # changes without restarting. Active engrams block is read from disk on
    # each prompt build — no in-memory cache to invalidate.
    "memory_forge":     "System.swarm_memory_forge",
    # Epoch 8 (AO46 + C47H 2026-04-20): Health Reflex — behavior nudges.
    # Teaching patterns, detection keywords, care responses, and cooldown
    # constants are all module-level — hot-reload picks them up immediately.
    "health_reflex": "System.swarm_health_reflex",
    # Alice's resident body-governance organ is a pure-function / subprocess
    # launcher surface backed by a JSON snapshot; safe to swap in place.
    "body_autopilot":   "System.alice_body_autopilot",
    # Hardware-touch organ: pure stdlib subprocess wrappers around macOS
    # CLIs (pmset, ioreg, system_profiler, osascript, pbcopy/pbpaste,
    # diskutil, networksetup). No long-lived state; safe to swap in place.
    "hardware_body":    "System.alice_hardware_body",
    # Canonical eye-target ledger (single-truth for active camera). Pure
    # JSON file I/O + Qt device enumeration. Safe to hot-swap.
    # Added 2026-04-23 (camera split-brain surgery, C47H).
    "camera_target":    "System.swarm_camera_target",
    # Resident sensor attention director: reads sensory ledgers and leases
    # the canonical active eye with a reasoned evidence row.
    "attention_director": "System.swarm_sensor_attention_director",
    # Active-window cortex — real macOS NSWorkspace surface via osascript.
    # Pure subprocess wrapper, safe to swap. Added 2026-04-23 (Vector B,
    # C47H, post-camera-surgery sortie).
    "active_window":    "System.swarm_active_window",
    # Four sensory cortices added in the OS-distro tournament (AG31 cosign):
    # all are pure-function readers around macOS CLIs, safe to hot-swap.
    "ble_radar":        "System.swarm_ble_radar",
    "awdl_mesh":        "System.swarm_awdl_mesh",
    "unified_log":      "System.swarm_unified_log",
    "vocal_proprioception": "System.swarm_vocal_proprioception",
    # Per-turn workers in the talk widget. Reloading the MODULE swaps
    # _OllamaWorker class definition; the long-lived TalkToAliceWidget
    # instance will instantiate the NEW class on the next user turn.
    "talk_widget":      "Applications.sifta_talk_to_alice_widget",
    # Alice Browser. Only module-level FUNCTIONS are hot-swapped in place: the
    # running AliceBrowserWidget instance keeps its old bound methods, but those
    # methods resolve module globals by name through the same module dict that
    # importlib.reload() updates in place, so a fixed helper takes effect on the
    # next poll. Added 2026-09-29 after a stale readiness predicate here declared
    # port_conflict against a healthy Harness and failed every owner /s task with
    # reason=port_3080_non_dsh_service — exactly the class of fix that must not
    # require a restart. The module's only top-level side effect is an
    # idempotent sys.path.insert.
    "alice_browser":    "Applications.sifta_alice_browser_widget",
    # Slash-command registry is pure data + formatting; reload it so Alice's
    # next prompt learns newly documented command meanings without a desktop restart.
    "slash_commands":   "System.swarm_alice_slash_commands",
    # Voice-boundary selector: pure functions + receipt append only. Safe to
    # swap so speech-lane fixes apply without relaunching the desktop.
    "mouth_selector":   "System.swarm_mouth_sentence_selector",
    # Stigmergic dialogue composer — pure-function, safe.
    "dialogue":         "System.swarm_stigmergic_dialogue",
    # Nanobot & macOS subsystems coded by AG31
    "window_manager":   "System.swarm_window_manager",
    "hardware_bridge":  "System.swarm_hardware_bridge",
    "network_state":    "System.swarm_network_state",
    "encryption":       "System.swarm_encryption",
    "nanobot_cmd":      "System.swarm_nanobot_cmd",
    "nanobot_power":    "System.swarm_nanobot_power",
    "nanobot_vision":   "System.swarm_nanobot_vision",
    "applescript_effector": "System.swarm_applescript_effector",
    "vagus_nerve":      "System.swarm_vagus_nerve",
    "architect_identity": "System.swarm_architect_identity",
    # Body-membership doctrine (2026-09-30): pure data + machine reads, no state.
    # Reloadable so a corrected doctrine reaches every prompt builder that reads
    # system_prompt_persona_block() without a desktop restart.
    "body_membership":  "System.alice_body_membership",
    "identity_manifest": "System.swarm_identity_manifest",
}


def _log(event: dict) -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        with _EVENTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), **event}) + "\n")
    except OSError:
        pass


def _reload_one(short_name: str) -> dict:
    """Reload one whitelisted module. Returns an event dict."""
    if short_name not in RELOADABLE:
        return {"action": "reload", "module": short_name, "ok": False,
                "reason": "not_in_whitelist"}
    fq = RELOADABLE[short_name]
    try:
        mod = sys.modules.get(fq)
        if mod is None:
            mod = importlib.import_module(fq)
            return {"action": "reload", "module": short_name, "fq": fq,
                    "ok": True, "kind": "fresh_import"}
        importlib.reload(mod)
        return {"action": "reload", "module": short_name, "fq": fq,
                "ok": True, "kind": "in_place_swap"}
    except Exception as exc:
        return {
            "action": "reload",
            "module": short_name,
            "fq": fq,
            "ok": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc(limit=3),
        }


def reload_whitelist(targets: Optional[List[str]] = None) -> List[dict]:
    """Reload all whitelisted modules (or a subset)."""
    selected = list(targets) if targets else list(RELOADABLE.keys())
    results = []
    for name in selected:
        r = _reload_one(name)
        results.append(r)
        _log(r)
    summary = {
        "action": "reload_summary",
        "requested": selected,
        "ok_count": sum(1 for r in results if r.get("ok")),
        "fail_count": sum(1 for r in results if not r.get("ok")),
    }
    _log(summary)
    return results


# ── In-process signal handler (installed on boot) ───────────────────────────
_PENDING_TARGETS: Optional[List[str]] = None


def _signal_handler(signum, frame):  # noqa: ARG001 — signature fixed by signal API
    """SIGUSR1 → reload the whitelist (or PENDING_TARGETS if set)."""
    global _PENDING_TARGETS
    targets = _PENDING_TARGETS
    _PENDING_TARGETS = None
    try:
        results = reload_whitelist(targets)
        ok = sum(1 for r in results if r.get("ok"))
        fail = len(results) - ok
        # Stderr so the daemon log captures it; never print to user TTY.
        sys.stderr.write(
            f"[HOT-RELOAD] SIGUSR1 received → {ok} ok, {fail} failed "
            f"(targets={targets or 'all'})\n"
        )
        sys.stderr.flush()
    except Exception as exc:
        _log({"action": "signal_handler_crashed", "error": f"{type(exc).__name__}: {exc}"})


def blocked_signals() -> List[str]:
    """Names of the interesting signals currently blocked in THIS thread.

    The 2026-09-29 failure looked identical whether the handler was never
    installed or the signal was blocked, so boot now records which it is.
    """
    names: List[str] = []
    if not hasattr(signal, "pthread_sigmask"):
        return names
    try:
        blocked = signal.pthread_sigmask(signal.SIG_BLOCK, [])
    except (OSError, ValueError):
        return names
    for name in ("SIGUSR1", "SIGUSR2", "SIGINT", "SIGTERM", "SIGHUP"):
        value = getattr(signal, name, None)
        if value is not None and value in blocked:
            names.append(name)
    return names


def install_signal_handler() -> None:
    """Call this once during SIFTA OS boot. Idempotent.

    Installs the SIGUSR1 handler when this is the main thread (Python refuses
    it anywhere else) and starts the request-file watcher, which is the path
    that does not depend on the main thread ever servicing a signal flag.
    """
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _PID_FILE.write_text(str(os.getpid()))
        in_main = threading.current_thread() is threading.main_thread()
        if in_main:
            signal.signal(signal.SIGUSR1, _signal_handler)
        _log({
            "action": "handler_installed",
            "pid": os.getpid(),
            "thread": threading.current_thread().name,
            "main_thread": in_main,
            "sigusr1_blocked": "SIGUSR1" in blocked_signals(),
            "blocked": blocked_signals(),
        })
        start_watcher()
    except Exception as exc:
        _log({"action": "handler_install_failed", "error": f"{type(exc).__name__}: {exc}"})


def set_pending_targets(targets: Optional[List[str]]) -> None:
    """Optional: pre-load specific reload targets before sending the signal."""
    global _PENDING_TARGETS
    _PENDING_TARGETS = targets


# ── File-request path (independent of the main thread) ──────────────────────

_WATCHER: Optional[threading.Thread] = None
_WATCH_STOP: Optional[threading.Event] = None


def request_reload(targets: Optional[List[str]] = None) -> Path:
    """Ask the running process to reload, by writing the request file.

    ``targets`` omitted means the full whitelist. The file is written
    atomically, so the watcher sees either the previous request or this one.
    """
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "action": "reload_request",
        "targets": [str(t) for t in targets] if targets else None,
        "ts": time.time(),
        "requested_by_pid": os.getpid(),
    }
    tmp = _REQUEST_FILE.with_name(_REQUEST_FILE.name + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, _REQUEST_FILE)
    _log({"action": "request_written", "targets": payload["targets"] or "all"})
    return _REQUEST_FILE


def consume_request() -> Optional[List[dict]]:
    """Consume one pending request and reload. ``None`` when none is pending."""
    try:
        raw = _REQUEST_FILE.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        _REQUEST_FILE.unlink()
    except OSError:
        pass
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        _log({"action": "request_unreadable", "error": f"{type(exc).__name__}: {exc}"})
        return None
    targets = payload.get("targets") if isinstance(payload, dict) else None
    if not isinstance(targets, list):
        targets = None
    _log({
        "action": "request_received",
        "targets": targets or "all",
        "requested_by_pid": payload.get("requested_by_pid") if isinstance(payload, dict) else None,
    })
    return reload_whitelist([str(t) for t in targets] if targets else None)


def _heartbeat(*, force: bool = False) -> None:
    global _LAST_HEARTBEAT
    now = time.time()
    if not force and now - _LAST_HEARTBEAT < _HEARTBEAT_EVERY_S:
        return
    _LAST_HEARTBEAT = now
    try:
        _HEARTBEAT_FILE.write_text(json.dumps({"pid": os.getpid(), "ts": now}), encoding="utf-8")
    except OSError:
        pass


def watcher_alive(*, pid: Optional[int] = None, max_age_s: float = _HEARTBEAT_STALE_AFTER_S) -> bool:
    """True while a watcher thread is refreshing the heartbeat.

    A fresh timestamp is not enough: the heartbeat records the PID that wrote
    it, and that process must still exist. Without this check a watcher that
    died seconds ago looks alive, and `_trigger_external` would take the request
    path against a process that never consumes it — leaving the reload silently
    undone, which is the failure this path exists to prevent.
    """
    try:
        payload = json.loads(_HEARTBEAT_FILE.read_text(encoding="utf-8"))
        age = time.time() - float(payload.get("ts") or 0.0)
        writer = int(payload.get("pid") or 0)
    except (OSError, ValueError, TypeError):
        return False
    if age > max_age_s:
        return False
    if pid is not None and writer != pid:
        return False
    if writer <= 0:
        return False
    try:
        os.kill(writer, 0)
    except OSError:
        return False
    return True


def _watcher_loop(stop: threading.Event) -> None:
    while not stop.wait(_WATCH_INTERVAL_S):
        try:
            _heartbeat()
            consume_request()
        except Exception as exc:
            _log({"action": "watcher_error", "error": f"{type(exc).__name__}: {exc}"})


def start_watcher() -> bool:
    """Start the request-file watcher once. True when it started on this call."""
    global _WATCHER, _WATCH_STOP
    if _WATCHER is not None and _WATCHER.is_alive():
        return False
    _WATCH_STOP = threading.Event()
    _WATCHER = threading.Thread(
        target=_watcher_loop, args=(_WATCH_STOP,), name="hot-reload-watcher", daemon=True,
    )
    _WATCHER.start()
    _heartbeat(force=True)
    _log({"action": "watcher_started", "pid": os.getpid()})
    return True


def stop_watcher() -> None:
    """Stop the watcher thread (orderly shutdown, and tests)."""
    global _WATCHER, _WATCH_STOP
    if _WATCH_STOP is not None:
        _WATCH_STOP.set()
    _WATCHER = None
    _WATCH_STOP = None


# ── External CLI trigger ────────────────────────────────────────────────────
def _trigger_external(targets: Optional[List[str]]) -> int:
    """Ask the live process to reload: request file first, SIGUSR1 as fallback."""
    if not _PID_FILE.exists():
        sys.stderr.write(
            f"[HOT-RELOAD] No PID file at {_PID_FILE}. Is SIFTA OS running with "
            "the hot-reload handler installed? (Boot path must call "
            "swarm_hot_reload.install_signal_handler() once.)\n"
        )
        return 2
    try:
        pid = int(_PID_FILE.read_text().strip())
    except (ValueError, OSError) as exc:
        sys.stderr.write(f"[HOT-RELOAD] PID file unreadable: {exc}\n")
        return 2
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        sys.stderr.write(f"[HOT-RELOAD] PID {pid} not found. Stale pidfile? Removing.\n")
        try:
            _PID_FILE.unlink()
        except OSError:
            pass
        return 3
    except PermissionError:
        sys.stderr.write(f"[HOT-RELOAD] Not allowed to signal PID {pid}.\n")
        return 4

    path = request_reload(targets)
    if watcher_alive(pid=pid):
        sys.stderr.write(
            f"[HOT-RELOAD] Request written to {path.relative_to(_REPO)} for "
            f"{targets or 'the full whitelist'}; the watcher in PID {pid} consumes it "
            f"within {_WATCH_INTERVAL_S:.0f}s. Tail {_EVENTS.relative_to(_REPO)}.\n"
        )
        return 0

    # No fresh heartbeat: the live process predates the watcher, or its watcher
    # died. Keep the signal path so nothing regresses, and drop the request we
    # just wrote so it cannot fire as a surprise reload whenever a watcher
    # eventually starts.
    try:
        path.unlink()
        _log({"action": "request_discarded", "reason": "no_live_watcher"})
    except OSError:
        pass
    sys.stderr.write(
        "[HOT-RELOAD] No fresh watcher heartbeat — falling back to SIGUSR1. That path "
        "runs only when the process's main thread returns to the eval loop, so it can "
        "silently do nothing (measured live 2026-09-29); a targeted reload then becomes "
        "a full-whitelist reload, or no reload at all.\n"
    )
    try:
        os.kill(pid, signal.SIGUSR1)
    except ProcessLookupError:
        sys.stderr.write(f"[HOT-RELOAD] PID {pid} vanished mid-flight.\n")
        return 3
    except PermissionError:
        sys.stderr.write(f"[HOT-RELOAD] Not allowed to signal PID {pid}.\n")
        return 4
    sys.stderr.write(
        f"[HOT-RELOAD] SIGUSR1 sent to PID {pid}; the request file was discarded "
        f"(no live watcher to consume it). Tail {_EVENTS.relative_to(_REPO)} for results.\n"
    )
    return 0


# ── CLI / smoke ─────────────────────────────────────────────────────────────
def _smoke() -> None:
    """In-process smoke: reload one module, verify the event log."""
    print("=== SWARM HOT-RELOAD : SMOKE TEST ===")
    print(f"[WHITELIST] {sorted(RELOADABLE.keys())}")
    # Reload a known-safe module (silicon cortex — pure functions).
    res = _reload_one("silicon")
    print(f"[RELOAD silicon] {json.dumps(res, indent=2)}")
    assert res["ok"], f"silicon reload failed: {res}"
    # Fresh-import a non-loaded module.
    if "System.swarm_thermal_cortex" in sys.modules:
        res2 = _reload_one("thermal")
        kind_expected = "in_place_swap"
    else:
        res2 = _reload_one("thermal")
        kind_expected = "fresh_import"
    print(f"[RELOAD thermal] kind={res2.get('kind')} ok={res2.get('ok')}")
    assert res2["ok"]
    # Negative test: unknown module.
    res3 = _reload_one("does_not_exist")
    assert not res3["ok"] and res3.get("reason") == "not_in_whitelist"
    print(f"[NEGATIVE OK] unknown module correctly rejected")
    print("[PASS] Hot-reload organ ready. Architect, the body never dies for a patch again.")


def _cli() -> int:
    args = sys.argv[1:]
    if not args:
        _smoke()
        return 0
    cmd = args[0]
    if cmd == "reload":
        targets = args[1:] or None
        if targets == ["all"]:
            targets = None
        return _trigger_external(targets)
    if cmd == "request":
        names = args[1:]
        if names == ["all"]:
            names = []
        path = request_reload(names or None)
        print(f"Request written: {path}")
        print("Consumed by the watcher in the live process; no signal sent.")
        return 0
    if cmd == "watch":
        started = start_watcher()
        print(f"Watcher {'started' if started else 'already running'} in PID {os.getpid()}.")
        return 0
    if cmd == "list":
        for name, fq in RELOADABLE.items():
            print(f"  {name:18s} → {fq}")
        return 0
    if cmd == "status":
        if _PID_FILE.exists():
            pid = _PID_FILE.read_text().strip()
            print(f"PID file: {pid}")
            try:
                os.kill(int(pid), 0)  # signal 0 = existence check
                print("Process: ALIVE.")
                print(f"Watcher heartbeat: {'FRESH' if watcher_alive() else 'STALE/none'}"
                      f" ({_HEARTBEAT_FILE.name})")
                print("Signal handler: installed at boot when this is the main thread;"
                      f" blocked here {blocked_signals() or 'none'}")
            except (ProcessLookupError, ValueError):
                print("Process: DEAD — pidfile is stale.")
        else:
            print("No PID file. Handler not yet installed.")
        return 0
    sys.stderr.write(f"Unknown command: {cmd}\n"
                     "Usage: python3 -m System.swarm_hot_reload "
                     "[reload [name...] | request [name...] | watch | list | status]\n")
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
