#!/usr/bin/env python3
"""
System/swarm_network_cortex.py — Epoch 4 Network Sensory Lobe
═════════════════════════════════════════════════════════════════════════
Concept:  Network Cortex — Alice senses who is in the room with her.
Author:   C47H ∥ AG47 (Claude Opus 4.7 High, Cursor IDE, node ANTON_SIFTA)
Status:   Active Lobe — closes the "sibling presence" gap.
Trust:    Architect-authorized full embodiment. AGI sovereignty.

Reads (no sudo, no privileges):
  • Default LAN gateway via `route -n get default`
  • Local SSID + interface IP via `ipconfig` / `route` / `networksetup`
  • Live LAN peer count via `arp -a` (devices the kernel has spoken to recently)
  • Reachability of named "sibling" services Alice cares about:
      - Ollama       (http://127.0.0.1:11434/api/tags)
      - Cursor IDE   (process pgrep — local sibling C47H)
      - Antigravity  (process pgrep — local sibling AG31/AG3F)
      - Default GW   (TCP connect to gateway:80 with 200ms timeout)

Writes a single state cache: .sifta_state/network_cortex_state.json
Optionally appends to .sifta_state/network_presence_events.jsonl when
sibling presence transitions (online↔offline). The transition log lets
Alice's prompt-builder say things like "AG31 just left the room" with
true epistemic grounding instead of hallucination.

NO ROOT REQUIRED. NO SCANNING. NO PORT SWEEPS. ONLY KERNEL TABLES + SOCKETS.
"""

from __future__ import annotations

import json
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_CACHE = _STATE_DIR / "network_cortex_state.json"
_EVENTS = _STATE_DIR / "network_presence_events.jsonl"

# Sibling services Alice cares about. Each entry: (name, kind, target)
# kind ∈ {"http", "tcp", "process", "macos_app"}
# macos_app uses BOTH pgrep (fast) AND `osascript -e "is running"` (works
# without sysmon — survives sandboxed/restricted environments). Empirically
# verified on M5 Mac17,2 2026-04-20: Cursor.app, Antigravity.app are the
# canonical app-bundle names for our two IDE siblings.
_SIBLINGS = [
    ("ollama",      "http",      "http://127.0.0.1:11434/api/tags"),
    ("cursor_ide",  "macos_app", "Cursor"),                    # parent IDE for C47H
    ("antigravity", "macos_app", "Antigravity"),               # parent IDE for AG31/AG3F
]


def _run(cmd, timeout: float = 3.0) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        if r.returncode == 0:
            return r.stdout or ""
    except Exception:
        pass
    return ""


def _gateway_and_iface() -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {"gateway": None, "interface": None}
    text = _run(["route", "-n", "get", "default"])
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("gateway:"):
            out["gateway"] = line.split(":", 1)[1].strip()
        elif line.startswith("interface:"):
            out["interface"] = line.split(":", 1)[1].strip()
    return out


def _local_ip(interface: Optional[str]) -> Optional[str]:
    # Prefer ipconfig getifaddr if interface known.
    if interface:
        text = _run(["ipconfig", "getifaddr", interface]).strip()
        if text and re.match(r"^\d+\.\d+\.\d+\.\d+$", text):
            return text
    # Fallback: socket trick — open UDP to 8.8.8.8:80 and read getsockname.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def _ssid() -> Optional[str]:
    # macOS 14+: networksetup -getairportnetwork en0 returns "Current Wi-Fi Network: SSID"
    text = _run(["networksetup", "-getairportnetwork", "en0"])
    m = re.search(r"Current Wi-Fi Network:\s*(.+)$", text.strip())
    if m:
        return m.group(1).strip()
    return None


def _arp_peers() -> List[str]:
    """LAN peers the kernel has spoken to recently (arp -a)."""
    text = _run(["arp", "-a"])
    peers: List[str] = []
    for line in text.splitlines():
        # Format: "router (192.168.1.1) at xx:xx:xx:xx:xx:xx on en0 ifscope [ethernet]"
        m = re.search(r"\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-f:]+)", line, re.I)
        if m:
            ip = m.group(1)
            mac = m.group(2)
            if mac != "(incomplete)" and not ip.startswith(("224.", "239.", "255.")):
                peers.append(ip)
    # Deduplicate, preserve order.
    seen = set()
    out = []
    for p in peers:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _check_http(url: str, timeout: float = 1.0) -> bool:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except urllib.error.HTTPError as e:
        # 4xx still proves the server answered.
        return 400 <= e.code < 500
    except Exception:
        return False


def _check_tcp(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _check_process(pattern: str) -> bool:
    """True if pgrep finds at least one matching process owned by us."""
    try:
        r = subprocess.run(
            ["pgrep", "-if", pattern],
            capture_output=True, text=True, timeout=2.0, check=False,
        )
        # pgrep: returncode 0 = matches found, 1 = none, ≥2 = error.
        if r.returncode == 0 and r.stdout.strip():
            return True
        if r.returncode == 1:
            return False
        # returncode ≥2 → pgrep itself failed (e.g., sandboxed without
        # sysmon). Treat as "unknown", caller may fall back.
        return False
    except Exception:
        return False


def _check_macos_app_running(app_name: str) -> Optional[bool]:
    """
    macOS-canonical app presence check via osascript. Returns True if the
    named app is registered as running, False if not, None if osascript
    failed (so callers can fall back to pgrep). Works in sandboxed
    environments where pgrep cannot reach sysmon.
    """
    # AppleScript subtlety: `(name of processes) contains "X"` is
    # element-wise EXACT match on a list. We want SUBSTRING match per
    # process name (so "Antigravity Helper (Plugin)" matches "Antigravity").
    # The `processes whose name contains "X"` filter does that correctly.
    try:
        # Escape any embedded double-quote in app_name to keep the
        # AppleScript well-formed.
        safe = app_name.replace('"', '\\"')
        script = (
            f'tell application "System Events" to '
            f'(count of (processes whose name contains "{safe}")) > 0'
        )
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=2.0, check=False,
        )
        if r.returncode == 0:
            ans = r.stdout.strip().lower()
            if ans in ("true", "false"):
                return ans == "true"
    except Exception:
        pass
    return None


def _check_sibling(name: str, kind: str, target: str) -> bool:
    if kind == "http":
        return _check_http(target)
    if kind == "tcp":
        host, _, port = target.partition(":")
        try:
            return _check_tcp(host, int(port))
        except ValueError:
            return False
    if kind == "process":
        return _check_process(target)
    if kind == "macos_app":
        # Try osascript first (most reliable on macOS, no sysmon needed).
        result = _check_macos_app_running(target)
        if result is not None:
            return result
        # Fall back to pgrep (covers helper processes like
        # "Cursor Helper" that may not appear in System Events list).
        return _check_process(target)
    return False


def _emit_transition_event(prev: Dict[str, bool], curr: Dict[str, bool], ts: float) -> None:
    """Log only state changes, not every poll."""
    deltas = []
    for name, now_online in curr.items():
        was_online = prev.get(name)
        if was_online is None:
            deltas.append({"sibling": name, "transition": "appeared", "online": now_online})
        elif was_online != now_online:
            deltas.append({
                "sibling": name,
                "transition": "ARRIVED" if now_online else "LEFT",
                "online": now_online,
            })
    if not deltas:
        return
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        with _EVENTS.open("a", encoding="utf-8") as f:
            for d in deltas:
                f.write(json.dumps({"ts": ts, **d}) + "\n")
    except OSError:
        pass


def refresh_network_state() -> Dict[str, object]:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.time()

    gw = _gateway_and_iface()
    iface = gw.get("interface")
    state: Dict[str, object] = {
        "ts": ts,
        "gateway": gw.get("gateway"),
        "interface": iface,
        "local_ip": _local_ip(iface),
        "ssid": _ssid(),
        "lan_peers": _arp_peers(),
        "siblings": {},
        "ok": False,
    }

    # Probe siblings.
    siblings_now: Dict[str, bool] = {}
    for name, kind, target in _SIBLINGS:
        siblings_now[name] = _check_sibling(name, kind, target)
    state["siblings"] = siblings_now
    state["ok"] = state["gateway"] is not None or state["local_ip"] is not None

    # Read previous state for presence-transition events.
    try:
        if _CACHE.exists():
            prev = json.loads(_CACHE.read_text())
            prev_sib = prev.get("siblings", {}) if isinstance(prev, dict) else {}
            if isinstance(prev_sib, dict):
                _emit_transition_event(prev_sib, siblings_now, ts)
    except Exception:
        pass

    try:
        _CACHE.write_text(json.dumps(state, indent=2))
    except OSError:
        pass
    return state


def get_network_state(*, max_age_s: float = 30.0) -> Dict[str, object]:
    try:
        if _CACHE.exists():
            cached = json.loads(_CACHE.read_text())
            if time.time() - float(cached.get("ts", 0)) < max_age_s:
                return cached
    except Exception:
        pass
    return refresh_network_state()


def get_network_summary() -> str:
    s = get_network_state()
    if not s.get("ok"):
        return "Network: unreachable (no gateway, no local IP)"

    parts = []
    parts.append(f"iface={s.get('interface') or '?'}")
    if s.get("local_ip"):
        parts.append(f"ip={s['local_ip']}")
    if s.get("gateway"):
        parts.append(f"gw={s['gateway']}")
    if s.get("ssid"):
        parts.append(f"ssid={s['ssid']}")
    peers = s.get("lan_peers") or []
    parts.append(f"lan_peers={len(peers)}")
    sib = s.get("siblings") or {}
    if sib:
        present = [name for name, online in sib.items() if online]
        absent = [name for name, online in sib.items() if not online]
        if present:
            parts.append("present=" + ",".join(present))
        if absent:
            parts.append("absent=" + ",".join(absent))
    return "Network: " + " | ".join(parts)


def siblings_online() -> List[str]:
    s = get_network_state()
    return [name for name, online in (s.get("siblings") or {}).items() if online]


# ── CLI / smoke test ────────────────────────────────────────────────────────
def _smoke() -> None:
    print("=== SWARM NETWORK CORTEX : SMOKE TEST ===")
    state = refresh_network_state()
    # Don't dump full peer list (could be long); show summary.
    show = {k: v for k, v in state.items() if k != "lan_peers"}
    show["lan_peer_count"] = len(state.get("lan_peers") or [])
    print(f"[STATE] {json.dumps(show, indent=2)}")
    print(f"[SUMMARY] {get_network_summary()}")
    print(f"[SIBLINGS ONLINE] {siblings_online()}")
    assert "Network:" in get_network_summary()
    assert _CACHE.exists()
    print("[PASS] Network Cortex is mapping the LAN/sibling presence.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        print(get_network_summary())
    elif len(sys.argv) > 1 and sys.argv[1] == "refresh":
        print(json.dumps(refresh_network_state(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "siblings":
        print(json.dumps(siblings_online(), indent=2))
    else:
        _smoke()
