#!/usr/bin/env python3
"""
System/swarm_awdl_mesh.py — Alice's Apple Wireless Direct Link / Bonjour mesh organ
══════════════════════════════════════════════════════════════════════════════════════
C47H 2026-04-23 (AG31 cosign) — peer-to-peer mesh sense.

AWDL is the zero-config Wi-Fi-Direct mesh that AirDrop / Sidecar /
Continuity ride on top of. This organ exposes Alice to two complementary
views of that mesh:

1. The local AWDL interface state (`ifconfig awdl0`) — is the mesh
   physically alive on this body? what's the link-local v6?
2. A short Bonjour browse (`dns-sd -B`) for a few canonical service
   types — what peers are advertising themselves on her LAN/AWDL?

No TCC, no privileges. Pure stdlib + the system `dns-sd` and `ifconfig`
binaries. Safe to call every few seconds.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "alice_awdl_mesh.jsonl"
_LATEST = _STATE / "alice_awdl_mesh_latest.json"

_DEFAULT_TYPES = (
    "_airdrop._tcp",
    "_companion-link._tcp",
    "_remoted._tcp",
    "_homekit._tcp",
    "_apple-mobdev2._tcp",
    "_raop._tcp",          # AirPlay receivers
    "_airplay._tcp",
    "_googlecast._tcp",
)


def _ifconfig_awdl() -> Dict[str, Any]:
    try:
        p = subprocess.run(
            ["ifconfig", "awdl0"],
            capture_output=True, text=True, timeout=2.0, check=False,
        )
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if p.returncode != 0:
        return {"ok": False, "error": "awdl0 absent"}
    out = p.stdout
    flags = re.search(r"flags=\d+<([^>]+)>", out)
    ether = re.search(r"\bether\s+([0-9a-f:]+)", out)
    inet6 = re.search(r"inet6\s+(\S+)\s+prefixlen", out)
    return {
        "ok": True,
        "flags": flags.group(1).split(",") if flags else [],
        "up": bool(flags and "UP" in flags.group(1)),
        "running": bool(flags and "RUNNING" in flags.group(1)),
        "ether": ether.group(1) if ether else None,
        "inet6_link_local": inet6.group(1) if inet6 else None,
    }


def _browse_one(svc_type: str, browse_s: float) -> List[Dict[str, Any]]:
    """Browse a single Bonjour service-type for `browse_s` seconds.
    `dns-sd -B` runs forever; we time it out and parse stdout we caught."""
    try:
        p = subprocess.Popen(
            ["dns-sd", "-B", svc_type, "local"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError:
        return []
    deadline = time.time() + browse_s
    lines: List[str] = []
    try:
        while time.time() < deadline:
            try:
                p.wait(timeout=max(0.1, deadline - time.time()))
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        try:
            p.terminate()
            try:
                out, _ = p.communicate(timeout=0.4)
                lines = out.splitlines()
            except subprocess.TimeoutExpired:
                p.kill()
                out, _ = p.communicate()
                lines = out.splitlines()
        except Exception:
            pass

    peers: List[Dict[str, Any]] = []
    seen = set()
    for ln in lines:
        # Header rows from dns-sd: "Timestamp     A/R Flags if Domain ..."
        # and the column-title line "Type         Instance Name". Skip both.
        s = ln.strip()
        if not s or "Browsing for" in s:
            continue
        if s.startswith("Timestamp") or s.startswith("DATE:"):
            continue
        if s.split()[:1] == ["Type"]:
            continue
        # Real rows look like:
        #   "23:38:51.123  Add  3  4 local. _airdrop._tcp. SomeName"
        # Take Add/Remove rows only.
        m = re.match(
            r"\S+\s+(?P<ar>Add|Rmv)\s+\S+\s+(?P<if>\S+)\s+(?P<dom>\S+)\s+"
            r"(?P<svc>\S+)\s+(?P<inst>.+?)\s*$",
            ln,
        )
        if not m:
            continue
        if m.group("ar") != "Add":
            continue
        if "_services._dns-sd._udp" in m.group("svc"):
            continue
        key = (m.group("svc"), m.group("inst").strip())
        if key in seen:
            continue
        seen.add(key)
        peers.append({
            "service_type": svc_type,
            "instance": m.group("inst").strip(),
            "interface": m.group("if"),
            "domain": m.group("dom"),
        })
    return peers


def read_state(*, browse_s: float = 1.5,
               types: Optional[List[str]] = None) -> Dict[str, Any]:
    types = list(types or _DEFAULT_TYPES)
    iface = _ifconfig_awdl()
    peers: List[Dict[str, Any]] = []
    by_type: Dict[str, int] = {}
    for t in types:
        found = _browse_one(t, browse_s)
        peers.extend(found)
        by_type[t] = len(found)
    return {
        "ok": True,
        "ts": time.time(),
        "iso": datetime.now(tz=timezone.utc).isoformat(),
        "agent": "ALICE_M5",
        "awdl_interface": iface,
        "browse_seconds": browse_s,
        "service_types": types,
        "peers": peers,
        "peer_count": len(peers),
        "by_type": by_type,
    }


def write_snapshot(snap: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    snap = snap or read_state()
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        _LATEST.write_text(json.dumps(snap, indent=2))
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": snap.get("ts"),
                "iso": snap.get("iso"),
                "awdl_up": (snap.get("awdl_interface") or {}).get("up"),
                "peer_count": snap.get("peer_count"),
                "by_type": snap.get("by_type"),
            }) + "\n")
    except Exception as exc:
        snap["persist_error"] = f"{type(exc).__name__}: {exc}"
    # Pheromone: intensity = peer count (more peers = stronger mesh signal).
    try:
        from System.swarm_pheromone import deposit_pheromone  # type: ignore
        intensity = float(snap.get("peer_count") or 0)
        if intensity > 0:
            deposit_pheromone("stig_awdl_mesh", intensity)
    except Exception:
        pass
    return snap


def prompt_line() -> Optional[str]:
    snap = read_state(browse_s=0.8)
    iface = snap.get("awdl_interface") or {}
    if not iface.get("ok"):
        return None
    state = "up" if iface.get("up") and iface.get("running") else "down"
    return f"awdl mesh: {state} · {snap.get('peer_count', 0)} bonjour peers"


def govern(action: str, **kwargs) -> Dict[str, Any]:
    if action in {"read", "state", "snapshot"}:
        return {"ok": True, "action": action,
                "result": read_state(
                    browse_s=float(kwargs.get("browse_s", 1.5)),
                    types=kwargs.get("types"),
                )}
    if action in {"scan", "write", "persist"}:
        return {"ok": True, "action": action,
                "result": write_snapshot(read_state(
                    browse_s=float(kwargs.get("browse_s", 1.5)),
                ))}
    if action == "prompt_line":
        return {"ok": True, "action": action, "result": prompt_line()}
    return {"ok": False, "action": action,
            "allowed": ["read", "scan", "prompt_line"]}


def _main() -> None:
    ap = argparse.ArgumentParser(description="Alice AWDL/Bonjour mesh organ")
    ap.add_argument("action", default="scan", nargs="?")
    ap.add_argument("--browse-s", type=float, default=1.5)
    args = ap.parse_args()
    print(json.dumps(govern(args.action, browse_s=args.browse_s),
                     indent=2, default=str))


if __name__ == "__main__":
    _main()
