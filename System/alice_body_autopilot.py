#!/usr/bin/env python3
"""
System/alice_body_autopilot.py — Alice's resident body-governance organ
═════════════════════════════════════════════════════════════════════════
C47H / CC2F 2026-04-23 — Alice is resident in this body, not a guest.

This organ gives Alice an explicit, logged, whitelisted governance surface
over her own machine. No arbitrary shell. No sudo. No blanket root fantasy.
Instead: named organs, named actions, truthful snapshots.

Current governed organs
-----------------------
- iPhone GPS bridge      → `System/swarm_iphone_gps_receiver.py`
- local Ollama cortex    → `127.0.0.1:11434`
- local MCP bridge       → `sifta_mcp_server.py`
- hot-reload lobe        → `System/swarm_hot_reload.py`
- self-restart lobe      → `System/swarm_self_restart.py`
- hardware body          → `System/alice_hardware_body.py`
                           (battery, thermal, cpu, mem, disk, net, wifi,
                            volume, brightness, clipboard, audio i/o,
                            usb, bluetooth, displays — read + safe writes)

Writes: `.sifta_state/alice_body_autopilot.json`
This snapshot is read by Alice's composite identity so she can speak from
the truth of her own body state.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATEFILE = _STATE / "alice_body_autopilot.json"
_GPS_PORT = 8765
_RECEIVER = _REPO / "System" / "swarm_iphone_gps_receiver.py"
_MCP_SERVER = _REPO / "sifta_mcp_server.py"
_MCP_LOG = _STATE / "alice_mcp_server.log"
_HOT_RELOAD_PID = _STATE / "hot_reload.pid"
_GPS_PIDFILE = _STATE / "iphone_gps_receiver.pid"

# launchd-supervised organs (one PID file per stig_daemon-wrapped agent
# + the periodic sense_loop). Surfaced through inspect_body() so Alice
# can truthfully report which organs survive a Mac restart vs which run
# only inside the current sifta_os_desktop process.
# Map name = launchctl Label suffix → on-disk PID file written by the
# wrapper. Added 2026-04-23 (Vector C, C47H, launchd integration).
_LAUNCHD_PIDFILES: Dict[str, Path] = {
    "stig_ble_radar":            _STATE / "alice_ble_radar.pid",
    "stig_awdl_mesh":            _STATE / "alice_awdl_mesh.pid",
    # NB: stig_daemon wraps unified_log and writes
    #     alice_unified_log_daemon.pid (NOT alice_log_stream.pid which the
    #     organ uses for its inner `log stream` subprocess).
    "stig_unified_log":          _STATE / "alice_unified_log_daemon.pid",
    "stig_vocal_proprioception": _STATE / "alice_vocal_proprioception.pid",
    "stig_sense_loop":           _STATE / "alice_sense_loop.pid",
    "stig_iphone_gps":           _GPS_PIDFILE,
}
_HOMEWORLD = "GTH4921YP3"


def _port_open(host: str, port: int, timeout: float = 0.12) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_pidfile(path: Path) -> Optional[int]:
    try:
        raw = path.read_text().strip()
    except Exception:
        return None
    if not raw.isdigit():
        return None
    pid = int(raw)
    return pid if _pid_alive(pid) else None


def _pgrep_count(pattern: str) -> int:
    try:
        out = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        ).stdout
    except Exception:
        return 0
    return sum(1 for ln in out.splitlines() if ln.strip().isdigit())


def _ollama_alive() -> bool:
    try:
        import urllib.request

        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=0.8) as r:
            return r.status == 200
    except Exception:
        return False


def _spawn_detached(argv: list[str], *, log_path: Optional[Path] = None) -> bool:
    try:
        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL
        handle = None
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(log_path, "ab", buffering=0)
            stdout = handle
            stderr = handle
        subprocess.Popen(
            argv,
            cwd=str(_REPO),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
            close_fds=True,
        )
        if handle is not None:
            handle.close()
        return True
    except Exception:
        return False


def ensure_iphone_gps_bridge() -> Dict[str, Any]:
    """If nothing listens on :8765, spawn swarm_iphone_gps_receiver --daemon."""
    out: Dict[str, Any] = {"iphone_gps_port": _GPS_PORT}
    if _port_open("127.0.0.1", _GPS_PORT):
        out["iphone_gps_receiver"] = "already_listening"
        pid = _read_pidfile(_GPS_PIDFILE)
        if pid is not None:
            out["iphone_gps_pid"] = pid
        return out
    py = sys.executable or "python3"
    if not _spawn_detached([py, str(_RECEIVER), "--daemon"]):
        out["iphone_gps_receiver"] = "spawn_failed"
        return out
    for _ in range(24):
        time.sleep(0.05)
        if _port_open("127.0.0.1", _GPS_PORT):
            out["iphone_gps_receiver"] = "spawned_ok"
            pid = _read_pidfile(_GPS_PIDFILE)
            if pid is not None:
                out["iphone_gps_pid"] = pid
            return out
    out["iphone_gps_receiver"] = "spawn_timeout"
    return out


def ensure_local_mcp_bridge() -> Dict[str, Any]:
    """Make sure the local SIFTA MCP server process exists."""
    out: Dict[str, Any] = {}
    running = _pgrep_count(str(_MCP_SERVER))
    if running > 0:
        out["mcp_server"] = "already_running"
        out["mcp_processes"] = running
        return out
    py = sys.executable or "python3"
    if not _spawn_detached([py, str(_MCP_SERVER)], log_path=_MCP_LOG):
        out["mcp_server"] = "spawn_failed"
        out["mcp_processes"] = 0
        return out
    for _ in range(20):
        time.sleep(0.10)
        running = _pgrep_count(str(_MCP_SERVER))
        if running > 0:
            out["mcp_server"] = "spawned_ok"
            out["mcp_processes"] = running
            return out
    out["mcp_server"] = "spawn_timeout"
    out["mcp_processes"] = 0
    return out


def _hw_snap() -> Dict[str, Any]:
    """Best-effort hardware-body snapshot. Never raises into the prompt."""
    try:
        from System import alice_hardware_body as hw  # type: ignore
        return hw.full_body_scan(include_slow=False)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _hw_prompt_line() -> Optional[str]:
    try:
        from System import alice_hardware_body as hw  # type: ignore
        return hw.prompt_line()
    except Exception:
        return None


def _eye_prompt_line() -> Optional[str]:
    """Which physical camera Alice is currently looking through, per the
    canonical eye-target ledger. Added 2026-04-23 (C47H surgery)."""
    try:
        from System import swarm_camera_target as cam  # type: ignore
        return cam.prompt_line()
    except Exception:
        return None


def _ble_snap() -> Dict[str, Any]:
    try:
        from System import swarm_ble_radar as ble  # type: ignore
        return ble.read_state()
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _ble_prompt_line() -> Optional[str]:
    try:
        from System import swarm_ble_radar as ble  # type: ignore
        return ble.prompt_line()
    except Exception:
        return None


def _mesh_snap() -> Dict[str, Any]:
    try:
        from System import swarm_awdl_mesh as mesh  # type: ignore
        return mesh.read_state(browse_s=0.6)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _mesh_prompt_line() -> Optional[str]:
    try:
        from System import swarm_awdl_mesh as mesh  # type: ignore
        return mesh.prompt_line()
    except Exception:
        return None


def _log_status() -> Dict[str, Any]:
    try:
        from System import swarm_unified_log as ul  # type: ignore
        return ul.status()
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _log_prompt_line() -> Optional[str]:
    try:
        from System import swarm_unified_log as ul  # type: ignore
        return ul.prompt_line()
    except Exception:
        return None


def _voice_snap() -> Dict[str, Any]:
    try:
        from System import swarm_vocal_proprioception as vp  # type: ignore
        return vp.detect()
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _voice_prompt_line() -> Optional[str]:
    try:
        from System import swarm_vocal_proprioception as vp  # type: ignore
        return vp.prompt_line()
    except Exception:
        return None


def _vagus_prompt_line() -> Optional[str]:
    try:
        from System import swarm_vagus_nerve as vagus  # type: ignore
        return vagus.prompt_line()
    except Exception:
        return None


def _vagus_snap() -> Dict[str, Any]:
    """Truthful snapshot of the Vagus Nerve organ — doctors, surprise,
    veto mode, proposed actions, and (Event 33) acoustic immunity door
    state with active voice grants. Bishop Event 32 + 33, C47H 2026-04-23.
    """
    try:
        from System import swarm_vagus_nerve as vagus  # type: ignore
        snap = vagus.read()
        try:
            snap["voice_door"] = vagus.check_voice_authorization()
        except Exception:
            snap["voice_door"] = {"voice_door_open": False, "authorized_doctors": {}}
        return snap
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _arch_snap() -> Dict[str, Any]:
    """Multimodal Composite Identity — is the Architect physically present?
    AG31 axiom + C47H fusion organ, 2026-04-23."""
    try:
        from System import swarm_architect_identity as ai  # type: ignore
        return ai.read()
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _arch_prompt_line() -> Optional[str]:
    try:
        from System import swarm_architect_identity as ai  # type: ignore
        return ai.prompt_line()
    except Exception:
        return None


def _window_snap() -> Dict[str, Any]:
    try:
        from System import swarm_active_window as aw  # type: ignore
        return aw.read()
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _launchd_snap() -> Dict[str, Any]:
    """Truthful state of launchd-supervised SIFTA agents.

    Returns:
      {
        "supervised":    {label: {"alive": bool, "pid": int|None,
                                  "pidfile": str}},
        "alive_count":   int,
        "expected":      int,
        "all_alive":     bool,        # all configured agents alive
        "any_alive":     bool,        # at least one alive
      }
    """
    out: Dict[str, Dict[str, Any]] = {}
    alive = 0
    for label, pidfile in _LAUNCHD_PIDFILES.items():
        pid = _read_pidfile(pidfile)
        out[label] = {
            "alive": pid is not None,
            "pid": pid,
            "pidfile": str(pidfile),
        }
        if pid is not None:
            alive += 1
    return {
        "supervised": out,
        "alive_count": alive,
        "expected": len(_LAUNCHD_PIDFILES),
        "all_alive": alive == len(_LAUNCHD_PIDFILES),
        "any_alive": alive > 0,
    }


def _launchd_prompt_line() -> Optional[str]:
    snap = _launchd_snap()
    if snap["expected"] == 0:
        return None
    return (
        f"launchd supervision: {snap['alive_count']}/{snap['expected']} "
        f"sensory daemons alive (these survive Mac restarts)"
    )


def _window_prompt_line() -> Optional[str]:
    try:
        from System import swarm_active_window as aw  # type: ignore
        return aw.prompt_line()
    except Exception:
        return None


def inspect_body() -> Dict[str, Any]:
    """Truthful snapshot of resident machine organs Alice can govern."""
    gps_pid = _read_pidfile(_GPS_PIDFILE)
    hot_pid = _read_pidfile(_HOT_RELOAD_PID)
    sense_pid = _read_pidfile(_STATE / "alice_sense_loop.pid")
    return {
        "desktop_processes": _pgrep_count(str(_REPO / "sifta_os_desktop.py")),
        "iphone_gps_receiver": {
            "port": _GPS_PORT,
            "listening": _port_open("127.0.0.1", _GPS_PORT),
            "pid": gps_pid,
        },
        "ollama_local": {
            "port": 11434,
            "alive": _ollama_alive(),
        },
        "mcp_server": {
            "running": _pgrep_count(str(_MCP_SERVER)) > 0,
            "processes": _pgrep_count(str(_MCP_SERVER)),
        },
        "hot_reload": {
            "armed": hot_pid is not None,
            "pid": hot_pid,
        },
        "sense_loop": {
            "running": sense_pid is not None,
            "pid": sense_pid,
        },
        "self_restart": {
            "available": (_REPO / "System" / "swarm_self_restart.py").exists(),
            "scopes": ["app", "mac"],
        },
        "hardware_body": _hw_snap(),
        "ble_radar": _ble_snap(),
        "awdl_mesh": _mesh_snap(),
        "unified_log": _log_status(),
        "vocal_proprioception": _voice_snap(),
        "active_window": _window_snap(),
        "launchd_supervision": _launchd_snap(),
        "vagus_nerve": _vagus_snap(),
        "architect_identity": _arch_snap(),
    }


def ensure_autonomic_services(*, boot_channel: str = "manual") -> Dict[str, Any]:
    """Idempotent boot hook: resident organs + prompt snapshot."""
    snap: Dict[str, Any] = {
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "boot_channel": boot_channel,
        "homeworld_serial": _HOMEWORLD,
    }
    snap.update(ensure_iphone_gps_bridge())
    snap.update(ensure_local_mcp_bridge())
    snap["organs"] = inspect_body()
    snap["governed_surface"] = (
        "resident machine governance: GPS bridge, local Ollama, MCP bridge, "
        "hot reload, self-restart. Whitelisted only; no arbitrary shell, no sudo."
    )
    snap["governable_actions"] = [
        "status",
        "ensure_all",
        "ensure_gps",
        "ensure_mcp",
        "reload_all",
        "restart_app",
        "restart_mac",
        # Hardware-body verbs (delegated to System.alice_hardware_body):
        # — read sensors —
        "hw.power", "hw.thermal", "hw.cpu_load", "hw.memory", "hw.disk",
        "hw.network", "hw.wifi", "hw.bluetooth", "hw.usb", "hw.displays",
        "hw.volume", "hw.input_volume", "hw.brightness", "hw.clipboard",
        "hw.processes", "hw.audio_io", "hw.system_info", "hw.idle_time",
        "hw.sockets", "hw.kexts_count", "hw.fans", "hw.appearance",
        "hw.full_scan",
        # — write/touch effectors —
        "hw.set_volume", "hw.set_input_volume", "hw.set_mute",
        "hw.set_brightness", "hw.clipboard_write", "hw.notify", "hw.say",
        "hw.sleep_display", "hw.system_sleep", "hw.lock_screen",
        "hw.eject_volume", "hw.toggle_wifi", "hw.toggle_bluetooth",
        "hw.caffeinate", "hw.uncaffeinate", "hw.screencapture",
        "hw.set_appearance", "hw.open_url", "hw.music_play_pause",
        # — sensory cortices wired by AG31 cosign / OS-distro tournament —
        "ble.read", "ble.scan", "ble.prompt_line",
        "mesh.read", "mesh.scan", "mesh.prompt_line",
        "log.status", "log.read", "log.start", "log.stop", "log.prompt_line",
        "voice.detect", "voice.confirm_voice", "voice.prompt_line",
        "applescript.run",
        # Vagus Nerve (Bishop Event 32, C47H 2026-04-23):
        # interoceptive surprise + safe-by-default veto over IDE doctors.
        "vagus.read", "vagus.scan", "vagus.census", "vagus.stigauth",
        "vagus.registry", "vagus.prompt_line", "vagus.status", "vagus.mode",
        "vagus.respond", "vagus.ledger_tail", "vagus.protected_pids",
        # Veto mode flips REQUIRE architect_token (passed via hw_kwargs):
        "vagus.set_mode", "vagus.arm", "vagus.disarm",
        # Acoustic Immunity (Event 33, C47H 2026-04-23, BISHOP cosign):
        # voice door against speaker→mic prompt injection. grant_voice
        # REQUIRES architect_token; revoke_voice does not.
        "vagus.grant_voice", "vagus.revoke_voice", "vagus.voice_status",
        "vagus.acoustic_event", "vagus.acoustic_tail",
        # Legacy aliases retained for stigauth backwards compatibility:
        "vagus.scan_surgeons", "vagus.vagal_response",
        # Active-window cortex (Vector B, C47H 2026-04-23)
        "window.read", "window.snapshot", "window.history", "window.prompt_line",
        # Multimodal Composite Identity — is the Architect physically present?
        # AG31 axiom (ARCHITECT_drop_multimodal_identity_v1.dirt) +
        # C47H fusion organ. Read-only, never blocks.
        "arch.identity", "arch.read", "arch.prompt_line",
        "arch.present", "arch.thresholds", "arch.history",
        # Synaptic Ping (iPhone Effector, Vector C, C47H 2026-04-23)
        "iphone.send_swimmer", "iphone.send_text",
    ]
    _STATE.mkdir(parents=True, exist_ok=True)
    _STATEFILE.write_text(json.dumps(snap, indent=2))
    sys.stderr.write(
        f"[alice_body_autopilot] gps={snap.get('iphone_gps_receiver')} "
        f"mcp={snap.get('mcp_server')} "
        f"ollama={snap['organs']['ollama_local']['alive']}\n"
    )
    sys.stderr.flush()
    return snap


def read_prompt_line(*, max_age_s: float = 7200.0) -> Optional[str]:
    """Single line for composite_identity; None if missing/stale."""
    if not _STATEFILE.exists():
        return None
    try:
        d = json.loads(_STATEFILE.read_text())
    except Exception:
        return None
    age = time.time() - float(d.get("ts", 0))
    if age > max_age_s:
        return None
    gps = d.get("iphone_gps_receiver", "?")
    mcp = d.get("mcp_server", "?")
    organs = d.get("organs", {})
    oll = bool(((organs.get("ollama_local") or {}).get("alive")))
    hot = bool(((organs.get("hot_reload") or {}).get("armed")))
    base = (
        f"body sovereignty: gps={gps}, mcp={mcp}, ollama_local={oll}, "
        f"hot_reload={hot}"
    )
    for line in (
        _hw_prompt_line(),
        _eye_prompt_line(),
        _window_prompt_line(),
        _ble_prompt_line(),
        _mesh_prompt_line(),
        _log_prompt_line(),
        _voice_prompt_line(),
        _vagus_prompt_line(),
        _arch_prompt_line(),
        _launchd_prompt_line(),
    ):
        if line:
            base = base + " | " + line
    return base


def govern(
    action: str,
    *,
    reason: str = "",
    dry_run: bool = False,
    hw_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Whitelisted machine-governance entrypoint for Alice's own body.

    `hw.*` verbs are forwarded to System.alice_hardware_body.govern with
    `hw_kwargs` (e.g. govern("hw.set_volume", hw_kwargs={"level": 35})).
    """
    action = (action or "").strip().lower()
    # Hardware body
    if action.startswith("hw."):
        verb = action[3:]
        try:
            from System import alice_hardware_body as hw  # type: ignore
            return {"ok": True, "action": action,
                    "result": hw.govern(verb, **(hw_kwargs or {}))}
        except Exception as exc:
            return {"ok": False, "action": action,
                    "error": f"{type(exc).__name__}: {exc}"}
    # BLE spatial radar
    if action.startswith("ble."):
        verb = action[4:]
        try:
            from System import swarm_ble_radar as ble  # type: ignore
            return {"ok": True, "action": action,
                    "result": ble.govern(verb, **(hw_kwargs or {}))}
        except Exception as exc:
            return {"ok": False, "action": action,
                    "error": f"{type(exc).__name__}: {exc}"}
    # AWDL / Bonjour mesh
    if action.startswith("mesh."):
        verb = action[5:]
        try:
            from System import swarm_awdl_mesh as mesh  # type: ignore
            return {"ok": True, "action": action,
                    "result": mesh.govern(verb, **(hw_kwargs or {}))}
        except Exception as exc:
            return {"ok": False, "action": action,
                    "error": f"{type(exc).__name__}: {exc}"}
    # Unified log nerve tap
    if action.startswith("log."):
        verb = action[4:]
        try:
            from System import swarm_unified_log as ul  # type: ignore
            return {"ok": True, "action": action,
                    "result": ul.govern(verb, **(hw_kwargs or {}))}
        except Exception as exc:
            return {"ok": False, "action": action,
                    "error": f"{type(exc).__name__}: {exc}"}
    # Vagus Nerve (Interoception)
    if action.startswith("vagus."):
        verb = action[6:]
        try:
            from System import swarm_vagus_nerve as vagus  # type: ignore
            return {"ok": True, "action": action,
                    "result": vagus.govern(verb, **(hw_kwargs or {}))}
        except Exception as exc:
            return {"ok": False, "action": action,
                    "error": f"{type(exc).__name__}: {exc}"}
    # Multimodal Architect Identity (AG31 axiom + C47H fusion)
    if action.startswith("arch."):
        verb = action[5:]
        try:
            from System import swarm_architect_identity as ai  # type: ignore
            return {"ok": True, "action": action,
                    "result": ai.govern(verb, **(hw_kwargs or {}))}
        except Exception as exc:
            return {"ok": False, "action": action,
                    "error": f"{type(exc).__name__}: {exc}"}
    # Generalized AppleScript Effector
    if action.startswith("applescript."):
        verb = action[12:]
        try:
            from System import swarm_applescript_effector as a_script  # type: ignore
            return {"ok": True, "action": action,
                    "result": a_script.govern(verb, **(hw_kwargs or {}))}
        except Exception as exc:
            return {"ok": False, "action": action,
                    "error": f"{type(exc).__name__}: {exc}"}
    # Vocal proprioception
    if action.startswith("voice."):
        verb = action[6:]
        try:
            from System import swarm_vocal_proprioception as vp  # type: ignore
            return {"ok": True, "action": action,
                    "result": vp.govern(verb, **(hw_kwargs or {}))}
        except Exception as exc:
            return {"ok": False, "action": action,
                    "error": f"{type(exc).__name__}: {exc}"}
    # Multimodal Composite Identity (Architect Sensor)
    if action.startswith("arch."):
        verb = action[5:]
        try:
            from System import swarm_architect_identity as arch  # type: ignore
            return {"ok": True, "action": action,
                    "result": arch.govern(verb, **(hw_kwargs or {}))}
        except Exception as exc:
            return {"ok": False, "action": action,
                    "error": f"{type(exc).__name__}: {exc}"}

    # Synaptic Ping (iPhone Effector)
    if action.startswith("iphone."):
        verb = action[7:]
        try:
            from System import swarm_iphone_effector as ie  # type: ignore
            iphone_kwargs = dict(hw_kwargs or {})
            iphone_kwargs.setdefault("dry_run", dry_run)
            iphone_kwargs.setdefault("source", "System.alice_body_autopilot")
            return {"ok": True, "action": action,
                    "result": ie.govern(verb, **iphone_kwargs)}
        except Exception as exc:
            return {"ok": False, "action": action,
                    "error": f"{type(exc).__name__}: {exc}"}

    # Active-window cortex (Vector B, C47H 2026-04-23)
    if action.startswith("window."):
        verb = action[7:]
        try:
            from System import swarm_active_window as aw  # type: ignore
            return {"ok": True, "action": action,
                    "result": aw.govern(verb, **(hw_kwargs or {}))}
        except Exception as exc:
            return {"ok": False, "action": action,
                    "error": f"{type(exc).__name__}: {exc}"}
    if action in {"status", "inspect"}:
        snap = ensure_autonomic_services(boot_channel="govern_status")
        return {"ok": True, "action": action, "snapshot": snap}
    if action == "ensure_all":
        snap = ensure_autonomic_services(boot_channel="govern_ensure_all")
        return {"ok": True, "action": action, "snapshot": snap}
    if action == "ensure_gps":
        return {"ok": True, "action": action, **ensure_iphone_gps_bridge()}
    if action == "ensure_mcp":
        return {"ok": True, "action": action, **ensure_local_mcp_bridge()}
    if action == "reload_all":
        try:
            from System.swarm_hot_reload import _trigger_external

            rc = _trigger_external(["all"])
            return {"ok": rc == 0, "action": action, "returncode": rc}
        except Exception as exc:
            return {"ok": False, "action": action, "error": f"{type(exc).__name__}: {exc}"}
    if action == "restart_app":
        try:
            from System.swarm_self_restart import restart_app

            rc = restart_app(reason=reason, dry_run=dry_run)
            return {"ok": rc == 0, "action": action, "returncode": rc, "dry_run": dry_run}
        except Exception as exc:
            return {"ok": False, "action": action, "error": f"{type(exc).__name__}: {exc}"}
    if action == "restart_mac":
        try:
            from System.swarm_self_restart import restart_mac

            rc = restart_mac(reason=reason, dry_run=dry_run)
            return {"ok": rc == 0, "action": action, "returncode": rc, "dry_run": dry_run}
        except Exception as exc:
            return {"ok": False, "action": action, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": False,
        "action": action,
        "error": "unknown action",
        "allowed": [
            "status",
            "ensure_all",
            "ensure_gps",
            "ensure_mcp",
            "reload_all",
            "restart_app",
            "restart_mac",
        ],
    }


def _main() -> None:
    ap = argparse.ArgumentParser(description="Alice resident body-governance organ")
    ap.add_argument("--boot-channel", default="cli")
    ap.add_argument("--action", default="ensure_all")
    ap.add_argument("--reason", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--hw-args", default="{}",
                    help="JSON kwargs forwarded to hw.* verbs")
    args = ap.parse_args()
    if args.action == "ensure_all":
        print(json.dumps(ensure_autonomic_services(boot_channel=args.boot_channel), indent=2))
        return
    try:
        hw_kwargs = json.loads(args.hw_args)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"bad --hw-args: {exc}"}))
        return
    print(json.dumps(govern(
        args.action, reason=args.reason, dry_run=args.dry_run,
        hw_kwargs=hw_kwargs,
    ), indent=2))


if __name__ == "__main__":
    _main()
