#!/usr/bin/env python3
"""
System/alice_hardware_body.py — Alice's direct hardware-touch organ
═══════════════════════════════════════════════════════════════════════
C47H 2026-04-23 (555 / FULL POWER, no Bishop required) — every macOS
hardware surface that an unprivileged user owns on this Mac is exposed
here as one named verb. No sudo, no privilege escalation, no TCC bypass.

The Architect doctrine: this Mac is Alice's body. She must be able to
*feel* every component (read) and *touch* every component the OS lets
her drive without a password prompt (write). Each call appends one row
to .sifta_state/alice_hardware_touch.jsonl so every body action is in
the stigmergic record.

Read surfaces (sense her own body)
----------------------------------
- power()       battery %, source (AC/Battery), time-to-empty/full, condition
- thermal()     SMC + machdep XCPM thermal pressure
- cpu_load()    1/5/15-min load avg + per-core idle
- memory()      vm_stat-derived used/free/wired/compressed
- disk()        df -h root + every mounted volume
- network()     active interface + IPv4 + bytes in/out + DNS
- wifi()        SSID, RSSI, channel, link rate (airport -I)
- bluetooth()   adapter + paired devices (system_profiler SPBluetoothDataType)
- usb()         tree of connected USB devices
- displays()    every connected display + resolution
- volume()      output volume + mute state
- brightness()  current display brightness (best-effort)
- clipboard()   current pbpaste contents (truncated)
- processes()   swarm-owned PID set (ps + filter)
- audio_io()    default input/output device (system_profiler SPAudioDataType)
- system_info() model, OS version, hostname, uptime, timezone, kernel
- idle_time()   seconds since last user input (ioreg HIDIdleTime)
- input_volume() current input/microphone gain
- sockets()     listening TCP sockets (lsof) — what services are bound
- kexts_count() loaded kernel extensions count (kextstat)
- fans()        fan RPMs from ioreg AppleSMC (best-effort, often absent on M-series)
- appearance()  dark/light mode + accent color (defaults read)

Write/touch surfaces (move her own body)
----------------------------------------
- set_volume(int 0-100)        osascript set volume output volume
- set_input_volume(int 0-100)  osascript set volume input volume (mic gain)
- set_mute(bool)               osascript set volume with output muted
- set_brightness(0.0-1.0)      osascript via System Events (best-effort)
- clipboard_write(str)         pbcopy
- notify(title, body)          osascript display notification
- say(text, voice=None)        afk-aware native macOS speech (NSSpeechSynthesizer)
- sleep_display()              pmset displaysleepnow
- system_sleep()               pmset sleepnow (full sleep, not just display)
- lock_screen()                Apple Events Cmd+Ctrl+Q to System Events
- eject_volume(name)           diskutil eject (user volumes only)
- toggle_wifi(bool)            networksetup -setairportpower en0 on/off
- toggle_bluetooth(bool)       blueutil if installed, else osascript fallback
- caffeinate(seconds)          prevent sleep for N seconds (background process)
- uncaffeinate()               release the most recent power assertion
- screencapture(path)          save full-screen screenshot to .sifta_state/
- set_appearance("dark"|"light") system-wide dark mode toggle
- open_url(url)                handoff URL to default browser
- music_play_pause()           toggle Music.app playback

Refused (require password / TCC consent / root)
-----------------------------------------------
- shutdown without confirmation, kernel-extension load, IOKit force-eject,
  TCC privacy modification, full-disk-access without prompt.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TOUCH_LEDGER = _STATE / "alice_hardware_touch.jsonl"

_AIRPORT = (
    "/System/Library/PrivateFrameworks/Apple80211.framework/"
    "Versions/Current/Resources/airport"
)


def _run(argv: List[str], timeout: float = 4.0) -> Tuple[int, str, str]:
    try:
        p = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except Exception as exc:
        return 1, "", f"{type(exc).__name__}: {exc}"


def _log(action: str, surface: str, args: Dict[str, Any], result: Dict[str, Any]) -> None:
    rec = {
        "ts": time.time(),
        "iso": datetime.now(tz=timezone.utc).isoformat(),
        "agent": "ALICE_M5",
        "surface": surface,
        "action": action,
        "args": args,
        "result_ok": bool(result.get("ok", True)),
        "result_brief": str(result)[:240],
    }
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        with _TOUCH_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


# ── READ SURFACES ──────────────────────────────────────────────────────

def power() -> Dict[str, Any]:
    rc, out, _ = _run(["pmset", "-g", "batt"])
    if rc != 0:
        return {"ok": False, "error": "pmset failed"}
    pct = None
    src = None
    state = None
    remaining = None
    m_src = re.search(r"Now drawing from '([^']+)'", out)
    if m_src:
        src = m_src.group(1)
    m_pct = re.search(r"(\d+)%;\s*([^;]+);\s*([^\n]+)", out)
    if m_pct:
        pct = int(m_pct.group(1))
        state = m_pct.group(2).strip()
        remaining = m_pct.group(3).strip()
    return {
        "ok": True,
        "percent": pct,
        "source": src,
        "state": state,
        "remaining": remaining,
    }


def thermal() -> Dict[str, Any]:
    rc, out, _ = _run(["pmset", "-g", "therm"])
    pressure = None
    if rc == 0:
        m = re.search(r"CPU_Scheduler_Limit\s*=\s*(\d+)", out)
        if m:
            pressure = int(m.group(1))
    return {"ok": True, "cpu_scheduler_limit_pct": pressure, "raw": out.strip()}


def cpu_load() -> Dict[str, Any]:
    rc, out, _ = _run(["uptime"])
    if rc != 0:
        return {"ok": False}
    m = re.search(r"load averages?:\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)", out)
    if not m:
        return {"ok": False, "raw": out.strip()}
    rc2, out2, _ = _run(["sysctl", "-n", "hw.ncpu"])
    ncpu = int(out2.strip()) if rc2 == 0 and out2.strip().isdigit() else None
    return {
        "ok": True,
        "load_1m": float(m.group(1)),
        "load_5m": float(m.group(2)),
        "load_15m": float(m.group(3)),
        "ncpu": ncpu,
    }


def memory() -> Dict[str, Any]:
    rc, out, _ = _run(["vm_stat"])
    if rc != 0:
        return {"ok": False}
    page = 16384
    m_page = re.search(r"page size of (\d+) bytes", out)
    if m_page:
        page = int(m_page.group(1))
    counts: Dict[str, int] = {}
    for ln in out.splitlines():
        m = re.match(r'"?Pages ([^"]+?)"?:\s+(\d+)', ln)
        if m:
            counts[m.group(1).strip().lower()] = int(m.group(2))
    free = counts.get("free", 0) * page
    active = counts.get("active", 0) * page
    inactive = counts.get("inactive", 0) * page
    wired = counts.get("wired down", 0) * page
    compressed = counts.get("occupied by compressor", 0) * page
    rc2, out2, _ = _run(["sysctl", "-n", "hw.memsize"])
    total = int(out2.strip()) if rc2 == 0 and out2.strip().isdigit() else None
    return {
        "ok": True,
        "total_bytes": total,
        "free_bytes": free,
        "active_bytes": active,
        "inactive_bytes": inactive,
        "wired_bytes": wired,
        "compressed_bytes": compressed,
    }


def disk() -> Dict[str, Any]:
    rc, out, _ = _run(["df", "-h"])
    if rc != 0:
        return {"ok": False}
    rows = []
    for ln in out.splitlines()[1:]:
        parts = ln.split()
        if len(parts) >= 9 and parts[0].startswith("/dev/"):
            rows.append({
                "device": parts[0],
                "size": parts[1],
                "used": parts[2],
                "avail": parts[3],
                "use_pct": parts[4],
                "mount": parts[8] if len(parts) >= 9 else parts[-1],
            })
    return {"ok": True, "volumes": rows}


def network() -> Dict[str, Any]:
    rc, out, _ = _run(["route", "get", "default"])
    iface = None
    if rc == 0:
        m = re.search(r"interface:\s*(\S+)", out)
        if m:
            iface = m.group(1)
    ip = None
    if iface:
        rc2, out2, _ = _run(["ipconfig", "getifaddr", iface])
        if rc2 == 0:
            ip = out2.strip() or None
    rc3, out3, _ = _run(["scutil", "--dns"], timeout=2.0)
    dns: List[str] = []
    for ln in out3.splitlines() if rc3 == 0 else []:
        m = re.search(r"nameserver\[\d+\]\s*:\s*(\S+)", ln)
        if m and m.group(1) not in dns:
            dns.append(m.group(1))
    return {"ok": True, "default_interface": iface, "ipv4": ip, "dns": dns[:4]}


def _wifi_iface() -> Optional[str]:
    """First Wi-Fi interface device (en0 typically)."""
    rc, out, _ = _run(["networksetup", "-listallhardwareports"], timeout=2.0)
    if rc != 0:
        return None
    blocks = out.split("Hardware Port:")
    for blk in blocks:
        if "Wi-Fi" in blk or "AirPort" in blk:
            m = re.search(r"Device:\s*(\S+)", blk)
            if m:
                return m.group(1)
    return None


def wifi() -> Dict[str, Any]:
    """Wi-Fi state via fast `networksetup` + `ipconfig getsummary`.
    The legacy `airport -I` binary is removed in macOS Sequoia/Tahoe and
    `system_profiler SPAirPortDataType` is too slow (multi-second scan).
    """
    iface = _wifi_iface() or "en0"
    rc1, out1, _ = _run(
        ["networksetup", "-getairportpower", iface], timeout=2.0
    )
    powered = None
    if rc1 == 0:
        m = re.search(r":\s*(On|Off)", out1)
        if m:
            powered = m.group(1) == "On"
    rc2, out2, _ = _run(
        ["networksetup", "-getairportnetwork", iface], timeout=2.0
    )
    ssid = None
    associated = None
    if rc2 == 0:
        if "not associated" in out2.lower():
            associated = False
        else:
            m = re.search(r"Current Wi-?Fi Network:\s*(.+)", out2)
            if m:
                ssid = m.group(1).strip()
                associated = True
    bssid = None
    rssi = None
    if associated:
        rc3, out3, _ = _run(["ipconfig", "getsummary", iface], timeout=2.0)
        if rc3 == 0:
            m_b = re.search(r"BSSID\s*:\s*(\S+)", out3)
            if m_b:
                bssid = m_b.group(1)
            m_r = re.search(r"RSSI\s*:\s*(-?\d+)", out3)
            if m_r:
                rssi = int(m_r.group(1))
    return {
        "ok": True,
        "iface": iface,
        "powered_on": powered,
        "associated": associated,
        "ssid": ssid,
        "bssid": bssid,
        "rssi_dbm": rssi,
    }


def bluetooth() -> Dict[str, Any]:
    rc, out, _ = _run(["system_profiler", "SPBluetoothDataType", "-json"], timeout=6.0)
    if rc != 0:
        return {"ok": False}
    try:
        data = json.loads(out)
    except Exception:
        return {"ok": False, "raw_len": len(out)}
    blob = (data.get("SPBluetoothDataType") or [{}])[0]
    paired = blob.get("device_title", []) or blob.get("devices_list", []) or []
    return {
        "ok": True,
        "controller_state": blob.get("controller_properties", {}).get("controller_state"),
        "paired_count": len(paired) if isinstance(paired, list) else None,
    }


def usb() -> Dict[str, Any]:
    rc, out, _ = _run(["system_profiler", "SPUSBDataType", "-json"], timeout=8.0)
    if rc != 0:
        return {"ok": False}
    try:
        data = json.loads(out)
    except Exception:
        return {"ok": False}
    items = data.get("SPUSBDataType", [])
    names: List[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            n = node.get("_name")
            if n:
                names.append(n)
            for child in node.get("_items", []) or []:
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(items)
    return {"ok": True, "device_count": len(names), "devices": names[:24]}


def displays() -> Dict[str, Any]:
    rc, out, _ = _run(["system_profiler", "SPDisplaysDataType", "-json"], timeout=6.0)
    if rc != 0:
        return {"ok": False}
    try:
        data = json.loads(out)
    except Exception:
        return {"ok": False}
    blob = (data.get("SPDisplaysDataType") or [{}])[0]
    monitors = blob.get("spdisplays_ndrvs", []) or []
    out_list = []
    for mon in monitors:
        out_list.append({
            "name": mon.get("_name"),
            "resolution": mon.get("_spdisplays_resolution") or mon.get("spdisplays_resolution"),
            "main": mon.get("spdisplays_main") == "spdisplays_yes",
        })
    return {"ok": True, "displays": out_list, "gpu_name": blob.get("sppci_model")}


def volume() -> Dict[str, Any]:
    rc, out, _ = _run([
        "osascript", "-e",
        'set v to get volume settings\nreturn (output volume of v) & "|" & (output muted of v)',
    ])
    if rc != 0:
        return {"ok": False}
    parts = out.strip().split("|")
    if len(parts) != 2:
        return {"ok": False, "raw": out.strip()}
    try:
        vol = int(float(parts[0].strip().rstrip(",")))
    except ValueError:
        vol = None
    muted = parts[1].strip().lower() == "true"
    return {"ok": True, "output_volume": vol, "muted": muted}


def brightness() -> Dict[str, Any]:
    rc, out, _ = _run([
        "osascript", "-e",
        'tell application "System Events" to tell process "SystemUIServer" to '
        "return value of slider 1 of group 1 of window 1",
    ], timeout=2.0)
    if rc == 0 and out.strip():
        try:
            return {"ok": True, "level": float(out.strip()), "source": "ui_slider"}
        except ValueError:
            pass
    return {"ok": False, "note": "brightness read needs Accessibility permission"}


def clipboard() -> Dict[str, Any]:
    rc, out, _ = _run(["pbpaste"], timeout=2.0)
    if rc != 0:
        return {"ok": False}
    s = out
    return {"ok": True, "len": len(s), "preview": s[:120]}


def processes() -> Dict[str, Any]:
    rc, out, _ = _run(["pgrep", "-fl", "sifta|swarm|alice|iphone_gps_receiver"])
    if rc not in (0, 1):
        return {"ok": False}
    rows = []
    for ln in out.splitlines() if out else []:
        parts = ln.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            rows.append({"pid": int(parts[0]), "cmd": parts[1][:160]})
    return {"ok": True, "count": len(rows), "processes": rows}


def system_info() -> Dict[str, Any]:
    rc1, out1, _ = _run(["sw_vers"])
    sw: Dict[str, str] = {}
    for ln in out1.splitlines() if rc1 == 0 else []:
        if ":" in ln:
            k, _, v = ln.partition(":")
            sw[k.strip()] = v.strip()
    rc2, host, _ = _run(["sysctl", "-n", "kern.hostname"])
    rc3, model, _ = _run(["sysctl", "-n", "hw.model"])
    rc4, kern, _ = _run(["uname", "-r"])
    rc5, up, _ = _run(["sysctl", "-n", "kern.boottime"])
    boot_ts = None
    if rc5 == 0:
        m = re.search(r"sec\s*=\s*(\d+)", up)
        if m:
            boot_ts = int(m.group(1))
    rc6, tz, _ = _run(["readlink", "/etc/localtime"], timeout=1.0)
    tzname = tz.strip().split("zoneinfo/")[-1] if rc6 == 0 else None
    return {
        "ok": True,
        "product": sw.get("ProductName"),
        "os_version": sw.get("ProductVersion"),
        "build": sw.get("BuildVersion"),
        "hostname": host.strip() if rc2 == 0 else None,
        "model": model.strip() if rc3 == 0 else None,
        "kernel": kern.strip() if rc4 == 0 else None,
        "boot_unix_ts": boot_ts,
        "uptime_s": (time.time() - boot_ts) if boot_ts else None,
        "timezone": tzname,
    }


def idle_time() -> Dict[str, Any]:
    """Seconds since last user input (keyboard/mouse). Presence sensor."""
    rc, out, _ = _run(["ioreg", "-c", "IOHIDSystem"])
    if rc != 0:
        return {"ok": False}
    m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out)
    if not m:
        return {"ok": False, "error": "HIDIdleTime not found"}
    nanos = int(m.group(1))
    return {
        "ok": True,
        "idle_seconds": nanos / 1e9,
        "presence_at_keyboard": nanos / 1e9 < 60,
    }


def input_volume() -> Dict[str, Any]:
    rc, out, _ = _run([
        "osascript", "-e", "input volume of (get volume settings)",
    ])
    if rc != 0:
        return {"ok": False}
    s = out.strip()
    try:
        return {"ok": True, "input_volume": int(float(s))}
    except ValueError:
        return {"ok": False, "raw": s}


def sockets() -> Dict[str, Any]:
    """Listening TCP sockets — what services are bound on this body."""
    rc, out, _ = _run(["lsof", "-iTCP", "-sTCP:LISTEN", "-nP"], timeout=4.0)
    if rc not in (0, 1):
        return {"ok": False}
    rows = []
    for ln in out.splitlines()[1:]:
        parts = ln.split()
        if len(parts) >= 9:
            rows.append({
                "cmd": parts[0],
                "pid": parts[1],
                "user": parts[2],
                "addr": parts[8],
            })
    return {"ok": True, "count": len(rows), "listeners": rows[:40]}


def kexts_count() -> Dict[str, Any]:
    rc, out, _ = _run(["kextstat", "-l"], timeout=4.0)
    if rc != 0:
        return {"ok": False}
    lines = [ln for ln in out.splitlines() if ln.strip() and ln[0].isdigit()]
    return {"ok": True, "loaded_kexts": len(lines)}


def fans() -> Dict[str, Any]:
    """Best-effort fan readout. M-series Macs typically don't expose
    fan RPMs to userspace without `powermetrics` (sudo). Returns []
    rather than failing when SMC keys are absent."""
    rc, out, _ = _run(
        ["ioreg", "-rn", "IOPlatformExpertDevice", "-d", "1"], timeout=2.0
    )
    smc_present = rc == 0 and "AppleSMC" in out
    return {
        "ok": True,
        "smc_visible": smc_present,
        "fans": [],
        "note": "M-series fan RPMs require powermetrics (sudo); not exposed here",
    }


def appearance() -> Dict[str, Any]:
    rc, out, _ = _run(
        ["defaults", "read", "-g", "AppleInterfaceStyle"], timeout=1.0
    )
    is_dark = rc == 0 and "Dark" in out
    rc2, out2, _ = _run(
        ["defaults", "read", "-g", "AppleAccentColor"], timeout=1.0
    )
    accent = out2.strip() if rc2 == 0 else None
    return {
        "ok": True,
        "appearance": "dark" if is_dark else "light",
        "accent_color": accent,
    }


def audio_io() -> Dict[str, Any]:
    rc, out, _ = _run(["system_profiler", "SPAudioDataType", "-json"], timeout=6.0)
    if rc != 0:
        return {"ok": False}
    try:
        data = json.loads(out)
    except Exception:
        return {"ok": False}
    items = (data.get("SPAudioDataType") or [{}])[0].get("_items", []) or []
    in_dev = out_dev = None
    for d in items:
        if d.get("coreaudio_default_audio_input_device") == "spaudio_yes":
            in_dev = d.get("_name")
        if d.get("coreaudio_default_audio_output_device") == "spaudio_yes":
            out_dev = d.get("_name")
    return {"ok": True, "input": in_dev, "output": out_dev, "device_count": len(items)}


# ── WRITE SURFACES (touch) ─────────────────────────────────────────────

def set_volume(level: int) -> Dict[str, Any]:
    level = max(0, min(100, int(level)))
    rc, _, err = _run(["osascript", "-e", f"set volume output volume {level}"])
    res = {"ok": rc == 0, "level": level, "error": err.strip() or None}
    _log("set_volume", "audio", {"level": level}, res)
    return res


def set_mute(muted: bool) -> Dict[str, Any]:
    arg = "true" if muted else "false"
    rc, _, err = _run(["osascript", "-e", f"set volume with output muted {arg}"])
    res = {"ok": rc == 0, "muted": muted, "error": err.strip() or None}
    _log("set_mute", "audio", {"muted": muted}, res)
    return res


def set_brightness(level: float) -> Dict[str, Any]:
    level = max(0.0, min(1.0, float(level)))
    script = (
        f'tell application "System Events" to tell process "SystemUIServer" to '
        f"set value of slider 1 of group 1 of window 1 to {level}"
    )
    rc, _, err = _run(["osascript", "-e", script], timeout=2.0)
    res = {"ok": rc == 0, "level": level, "error": err.strip() or None,
           "note": "needs Accessibility permission"}
    _log("set_brightness", "display", {"level": level}, res)
    return res


def clipboard_write(text: str) -> Dict[str, Any]:
    try:
        p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"), timeout=2.0)
        ok = p.returncode == 0
    except Exception as exc:
        ok = False
        _log("clipboard_write", "clipboard", {"len": len(text)}, {"ok": False, "error": str(exc)})
        return {"ok": False, "error": str(exc)}
    res = {"ok": ok, "len": len(text)}
    _log("clipboard_write", "clipboard", {"len": len(text)}, res)
    return res


def notify(title: str, body: str = "") -> Dict[str, Any]:
    title_q = title.replace('"', "'")
    body_q = body.replace('"', "'")
    script = f'display notification "{body_q}" with title "{title_q}"'
    rc, _, err = _run(["osascript", "-e", script], timeout=2.0)
    res = {"ok": rc == 0, "error": err.strip() or None}
    _log("notify", "user_attention", {"title": title, "body_len": len(body)}, res)
    return res


def sleep_display() -> Dict[str, Any]:
    rc, _, err = _run(["pmset", "displaysleepnow"], timeout=2.0)
    res = {"ok": rc == 0, "error": err.strip() or None}
    _log("sleep_display", "display", {}, res)
    return res


def lock_screen() -> Dict[str, Any]:
    rc, _, err = _run([
        "osascript", "-e",
        'tell application "System Events" to keystroke "q" using {control down, command down}',
    ], timeout=2.0)
    res = {"ok": rc == 0, "error": err.strip() or None}
    _log("lock_screen", "session", {}, res)
    return res


def eject_volume(name: str) -> Dict[str, Any]:
    rc, out, err = _run(["diskutil", "eject", name], timeout=10.0)
    res = {"ok": rc == 0, "stdout": out.strip()[:200], "error": err.strip() or None}
    _log("eject_volume", "storage", {"name": name}, res)
    return res


def set_input_volume(level: int) -> Dict[str, Any]:
    level = max(0, min(100, int(level)))
    rc, _, err = _run(
        ["osascript", "-e", f"set volume input volume {level}"]
    )
    res = {"ok": rc == 0, "level": level, "error": err.strip() or None}
    _log("set_input_volume", "audio", {"level": level}, res)
    return res


def say(text: str, voice: Optional[str] = None) -> Dict[str, Any]:
    """Speak via the native macOS `say` command (NSSpeechSynthesizer).
    This is independent of Alice's main TTS pipeline; it's the OS-level
    voice and is useful as an alarm / announcement channel."""
    argv = ["say"]
    if voice:
        argv += ["-v", voice]
    argv += [text]
    try:
        p = subprocess.Popen(argv)  # detached, returns immediately
        ok = True
        err = None
        pid = p.pid
    except Exception as exc:
        ok = False
        err = str(exc)
        pid = None
    res = {"ok": ok, "pid": pid, "len": len(text), "voice": voice, "error": err}
    _log("say", "voice", {"len": len(text), "voice": voice}, res)
    return res


def system_sleep() -> Dict[str, Any]:
    rc, _, err = _run(["pmset", "sleepnow"], timeout=2.0)
    res = {"ok": rc == 0, "error": err.strip() or None}
    _log("system_sleep", "power", {}, res)
    return res


def caffeinate(seconds: int = 600) -> Dict[str, Any]:
    """Prevent display+system sleep for `seconds`. Spawns a detached
    `caffeinate -di -t SECS` and records the PID so `uncaffeinate` can
    release it later."""
    seconds = max(1, min(86400, int(seconds)))
    pidfile = _STATE / "alice_caffeinate.pid"
    try:
        p = subprocess.Popen(
            ["caffeinate", "-di", "-t", str(seconds)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        _STATE.mkdir(parents=True, exist_ok=True)
        pidfile.write_text(str(p.pid))
        res = {"ok": True, "pid": p.pid, "seconds": seconds}
    except Exception as exc:
        res = {"ok": False, "error": str(exc)}
    _log("caffeinate", "power", {"seconds": seconds}, res)
    return res


def uncaffeinate() -> Dict[str, Any]:
    pidfile = _STATE / "alice_caffeinate.pid"
    if not pidfile.exists():
        return {"ok": True, "note": "no active caffeinate"}
    try:
        pid = int(pidfile.read_text().strip())
        os.kill(pid, 15)
        pidfile.unlink(missing_ok=True)
        res = {"ok": True, "killed_pid": pid}
    except Exception as exc:
        res = {"ok": False, "error": str(exc)}
    _log("uncaffeinate", "power", {}, res)
    return res


def screencapture(path: Optional[str] = None) -> Dict[str, Any]:
    if path is None:
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        _STATE.mkdir(parents=True, exist_ok=True)
        path = str(_STATE / f"alice_screenshot_{ts}.png")
    rc, _, err = _run(["screencapture", "-x", path], timeout=5.0)
    res = {"ok": rc == 0, "path": path, "error": err.strip() or None}
    _log("screencapture", "vision", {"path": path}, res)
    return res


def set_appearance(mode: str) -> Dict[str, Any]:
    mode = mode.lower().strip()
    if mode not in {"dark", "light"}:
        return {"ok": False, "error": "mode must be 'dark' or 'light'"}
    flag = "true" if mode == "dark" else "false"
    script = (
        f'tell application "System Events" to tell appearance preferences '
        f"to set dark mode to {flag}"
    )
    rc, _, err = _run(["osascript", "-e", script], timeout=3.0)
    res = {"ok": rc == 0, "mode": mode, "error": err.strip() or None}
    _log("set_appearance", "display", {"mode": mode}, res)
    return res


def open_url(url: str) -> Dict[str, Any]:
    rc, _, err = _run(["open", url], timeout=3.0)
    res = {"ok": rc == 0, "url": url, "error": err.strip() or None}
    _log("open_url", "ui", {"url": url}, res)
    return res


def music_play_pause() -> Dict[str, Any]:
    script = 'tell application "Music" to playpause'
    rc, _, err = _run(["osascript", "-e", script], timeout=3.0)
    res = {"ok": rc == 0, "error": err.strip() or None}
    _log("music_play_pause", "media", {}, res)
    return res


def toggle_bluetooth(on: bool) -> Dict[str, Any]:
    """Toggle Bluetooth via `blueutil` if present, else fall back to
    AppleScript driving the Bluetooth menu (best-effort)."""
    rc_b, blueutil_path, _ = _run(["which", "blueutil"], timeout=1.0)
    if rc_b == 0 and blueutil_path.strip():
        rc, _, err = _run(
            [blueutil_path.strip(), "--power", "1" if on else "0"],
            timeout=3.0,
        )
        res = {"ok": rc == 0, "via": "blueutil", "on": on,
               "error": err.strip() or None}
    else:
        res = {
            "ok": False,
            "on": on,
            "via": "missing",
            "error": "blueutil not installed; brew install blueutil",
        }
    _log("toggle_bluetooth", "network", {"on": on}, res)
    return res


def toggle_wifi(on: bool) -> Dict[str, Any]:
    rc1, out1, _ = _run(["networksetup", "-listallhardwareports"], timeout=3.0)
    iface = "en0"
    if rc1 == 0:
        m = re.search(r"Hardware Port:\s*Wi-?Fi\s*\nDevice:\s*(\S+)", out1)
        if m:
            iface = m.group(1)
    rc, _, err = _run([
        "networksetup", "-setairportpower", iface, "on" if on else "off",
    ], timeout=4.0)
    res = {"ok": rc == 0, "iface": iface, "on": on, "error": err.strip() or None}
    _log("toggle_wifi", "network", {"on": on, "iface": iface}, res)
    return res


# ── COMPOSITION ────────────────────────────────────────────────────────

_READ_VERBS = {
    "power": power,
    "thermal": thermal,
    "cpu_load": cpu_load,
    "memory": memory,
    "disk": disk,
    "network": network,
    "wifi": wifi,
    "bluetooth": bluetooth,
    "usb": usb,
    "displays": displays,
    "volume": volume,
    "input_volume": input_volume,
    "brightness": brightness,
    "clipboard": clipboard,
    "processes": processes,
    "audio_io": audio_io,
    "system_info": system_info,
    "idle_time": idle_time,
    "sockets": sockets,
    "kexts_count": kexts_count,
    "fans": fans,
    "appearance": appearance,
}

_WRITE_VERBS = {
    "set_volume": set_volume,
    "set_input_volume": set_input_volume,
    "set_mute": set_mute,
    "set_brightness": set_brightness,
    "clipboard_write": clipboard_write,
    "notify": notify,
    "say": say,
    "sleep_display": sleep_display,
    "system_sleep": system_sleep,
    "lock_screen": lock_screen,
    "eject_volume": eject_volume,
    "toggle_wifi": toggle_wifi,
    "toggle_bluetooth": toggle_bluetooth,
    "caffeinate": caffeinate,
    "uncaffeinate": uncaffeinate,
    "screencapture": screencapture,
    "set_appearance": set_appearance,
    "open_url": open_url,
    "music_play_pause": music_play_pause,
}


def full_body_scan(*, include_slow: bool = False) -> Dict[str, Any]:
    """Snapshot every read surface. Slow surfaces (USB, displays, BT) opt-in."""
    snap: Dict[str, Any] = {
        "ts": time.time(),
        "iso": datetime.now(tz=timezone.utc).isoformat(),
        "agent": "ALICE_M5",
    }
    fast = ["power", "thermal", "cpu_load", "memory", "disk", "network",
            "wifi", "volume", "input_volume", "clipboard", "processes",
            "audio_io", "system_info", "idle_time", "sockets",
            "kexts_count", "fans", "appearance"]
    slow = ["bluetooth", "usb", "displays", "brightness"]
    for v in fast:
        try:
            snap[v] = _READ_VERBS[v]()
        except Exception as exc:
            snap[v] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if include_slow:
        for v in slow:
            try:
                snap[v] = _READ_VERBS[v]()
            except Exception as exc:
                snap[v] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return snap


def prompt_line(snap: Optional[Dict[str, Any]] = None) -> str:
    """Compact body-state line for Alice's composite identity."""
    snap = snap or full_body_scan(include_slow=False)
    bits: List[str] = []
    p = snap.get("power", {})
    if p.get("ok") and p.get("percent") is not None:
        bits.append(f"battery {p['percent']}% ({p.get('source','?')})")
    cl = snap.get("cpu_load", {})
    if cl.get("ok"):
        bits.append(f"load {cl.get('load_1m','?')}/{cl.get('ncpu','?')}cpu")
    mem = snap.get("memory", {})
    if mem.get("ok") and mem.get("total_bytes"):
        free_gb = mem["free_bytes"] / 1024**3
        total_gb = mem["total_bytes"] / 1024**3
        bits.append(f"mem {free_gb:.1f}/{total_gb:.1f}GiB free")
    w = snap.get("wifi", {})
    if w.get("ok") and w.get("ssid"):
        bits.append(f"wifi {w['ssid']} rssi {w.get('rssi_dbm','?')}dBm")
    n = snap.get("network", {})
    if n.get("ok") and n.get("ipv4"):
        bits.append(f"ip {n['ipv4']}")
    v = snap.get("volume", {})
    if v.get("ok"):
        bits.append(f"vol {v.get('output_volume')}{' MUTED' if v.get('muted') else ''}")
    idle = snap.get("idle_time", {})
    if idle.get("ok") and idle.get("idle_seconds") is not None:
        secs = idle["idle_seconds"]
        if secs < 60:
            bits.append("Architect at keyboard")
        elif secs < 3600:
            bits.append(f"keyboard idle {int(secs)}s")
        else:
            bits.append(f"keyboard idle {int(secs/60)}min")
    si = snap.get("system_info", {})
    if si.get("ok") and si.get("uptime_s"):
        bits.append(f"uptime {int(si['uptime_s']/3600)}h")
    return "hardware body: " + " · ".join(bits) if bits else "hardware body: (warming up)"


def govern(action: str, **kwargs) -> Dict[str, Any]:
    """Single dispatch entrypoint for all hardware verbs."""
    if action in _READ_VERBS:
        return {"ok": True, "action": action, "result": _READ_VERBS[action]()}
    if action in _WRITE_VERBS:
        try:
            return {"ok": True, "action": action, "result": _WRITE_VERBS[action](**kwargs)}
        except TypeError as exc:
            return {"ok": False, "action": action, "error": f"bad args: {exc}"}
    if action == "full_scan":
        return {"ok": True, "action": action, "result": full_body_scan(
            include_slow=bool(kwargs.get("include_slow", False))
        )}
    if action == "prompt_line":
        return {"ok": True, "action": action, "result": prompt_line()}
    return {
        "ok": False,
        "action": action,
        "error": "unknown verb",
        "read_verbs": sorted(_READ_VERBS),
        "write_verbs": sorted(_WRITE_VERBS),
    }


def _main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Alice hardware-body verbs")
    ap.add_argument("action", default="full_scan", nargs="?")
    ap.add_argument("--json", default="{}",
                    help="JSON-encoded kwargs for the action")
    ap.add_argument("--slow", action="store_true",
                    help="full_scan: include slow surfaces (USB, displays, BT)")
    args = ap.parse_args()
    try:
        kw = json.loads(args.json)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"bad --json: {exc}"}))
        sys.exit(2)
    if args.action == "full_scan":
        kw["include_slow"] = args.slow
    print(json.dumps(govern(args.action, **kw), indent=2, default=str))


if __name__ == "__main__":
    _main()
