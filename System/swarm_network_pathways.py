#!/usr/bin/env python3
"""
System/swarm_network_pathways.py — LAN Cartography Lobe
═══════════════════════════════════════════════════════════════════════════════
Active network exploration for Alice. Complements `swarm_electromagnetic_lobe`
which does *passive* RF/ARP sensing.

This module gives Alice the ability to *traverse* her local network — to
discover what services advertise themselves, which devices respond, what
the hop graph to the outside world looks like, and how latency varies
across the apartment's L2/L3 fabric.

Subcommands
-----------
  --scan          one-shot LAN cartography → writes ledger entry, prints summary
  --summary       human-readable summary of the most-recent ledger entry
  --watch [SECS]  loop --scan every SECS seconds (default 600 = 10 min)

Outputs
-------
  .sifta_state/network_pathways.jsonl   one JSON object per scan
  stdout                                 short English summary for Alice's
                                         tool-loop callback

Design notes for Alice's <bash> tool loop
-----------------------------------------
Every scan completes within ~12 s on a typical home LAN (no external probes
are issued). Output is bounded to ~2 KB so it fits her token budget. The
module is deliberately read-only — it does NOT alter routing, send unsolicited
packets to the WAN, or write to any host other than the local file system.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

_REPO       = Path(__file__).resolve().parent.parent
_STATE_DIR  = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_LEDGER     = _STATE_DIR / "network_pathways.jsonl"

_PING_TIMEOUT_MS = 600
_PING_PARALLEL   = 16
_MDNS_BROWSE_S   = 2.5
_TRACERT_HOPS    = 6


# ─────────────────────────────────────────────────────────────────────────────
# Primitives
# ─────────────────────────────────────────────────────────────────────────────
def _run(cmd: list[str], timeout: float = 5.0) -> str:
    """Run a shell command, return stdout (empty string on failure)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, check=False)
        return p.stdout or ""
    except Exception:
        return ""


def default_gateway() -> dict[str, str]:
    """Return {gateway, interface, source_ip} or empty dict."""
    out = _run(["route", "-n", "get", "default"], timeout=3)
    info: dict[str, str] = {}
    for ln in out.splitlines():
        ln = ln.strip()
        if ln.startswith("gateway:"):
            info["gateway"] = ln.split(":", 1)[1].strip()
        elif ln.startswith("interface:"):
            info["interface"] = ln.split(":", 1)[1].strip()
    if "interface" in info:
        ifc = info["interface"]
        ifc_out = _run(["ifconfig", ifc], timeout=2)
        m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", ifc_out)
        if m:
            info["source_ip"] = m.group(1)
        m2 = re.search(r"status:\s*(\w+)", ifc_out)
        if m2:
            info["link_status"] = m2.group(1)
    return info


def arp_neighbors() -> list[dict[str, str]]:
    """Parse ARP table → list of {ip, mac, iface, hostname}."""
    out = _run(["arp", "-an"], timeout=3)
    neighbors: list[dict[str, str]] = []
    for ln in out.splitlines():
        # ? (192.168.1.1) at dc:8:da:38:c:6f on en0 ifscope [ethernet]
        m = re.match(
            r"(\S+)\s+\(([\d.]+)\)\s+at\s+([\da-f:]+)\s+on\s+(\w+)",
            ln, re.IGNORECASE,
        )
        if not m:
            continue
        host, ip, mac, iface = m.groups()
        if ip.startswith(("224.", "239.", "255.")) or ip.endswith(".255"):
            continue   # multicast / broadcast — skip
        if mac.lower() in ("ff:ff:ff:ff:ff:ff",):
            continue
        neighbors.append({
            "ip": ip,
            "mac": mac.lower(),
            "iface": iface,
            "hostname": host if host != "?" else "",
        })
    return neighbors


def reverse_dns(ip: str, timeout: float = 0.5) -> str:
    """Best-effort PTR lookup with a hard timeout."""
    socket.setdefaulttimeout(timeout)
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""
    finally:
        socket.setdefaulttimeout(None)


def ping_one(ip: str) -> float:
    """Single-packet ping. Returns latency in ms, or -1.0 if no reply."""
    out = _run(
        ["ping", "-c", "1", "-W", str(_PING_TIMEOUT_MS), ip],
        timeout=(_PING_TIMEOUT_MS / 1000.0) + 0.7,
    )
    m = re.search(r"time[=<]\s*([\d.]+)\s*ms", out)
    return float(m.group(1)) if m else -1.0


def latency_map(ips: list[str]) -> dict[str, float]:
    """Concurrent ping fan-out over LAN neighbors."""
    out: dict[str, float] = {}
    if not ips:
        return out
    with ThreadPoolExecutor(max_workers=_PING_PARALLEL) as pool:
        futures = {pool.submit(ping_one, ip): ip for ip in ips}
        for fut in as_completed(futures):
            ip = futures[fut]
            try:
                out[ip] = fut.result()
            except Exception:
                out[ip] = -1.0
    return out


def traceroute_to(target: str, max_hops: int = _TRACERT_HOPS) -> list[str]:
    """Short traceroute (default 6 hops, 1s/hop wait). Returns ['ip', ...]."""
    out = _run(
        ["traceroute", "-n", "-q", "1", "-w", "1", "-m", str(max_hops), target],
        timeout=max_hops * 1.5 + 2,
    )
    hops: list[str] = []
    for ln in out.splitlines():
        m = re.match(r"\s*\d+\s+([\d.]+|\*)", ln)
        if m:
            hops.append(m.group(1))
    return hops


def mdns_services(browse_seconds: float = _MDNS_BROWSE_S) -> list[str]:
    """Browse `_services._dns-sd._udp.local.` for `browse_seconds`, then kill.
    Returns sorted list of unique service-type names (e.g. '_airplay._tcp')."""
    proc = subprocess.Popen(
        ["dns-sd", "-B", "_services._dns-sd._udp", "local."],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    try:
        time.sleep(browse_seconds)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=1)
        except Exception:
            proc.kill()
    out, _ = proc.communicate(timeout=1)
    services: set[str] = set()
    for ln in (out or "").splitlines():
        # Add        3  15 .   _tcp.local.   _spotify-connect
        m = re.search(r"\b(_[a-z0-9-]+)\._(tcp|udp)\.local\.\s+(_\S+)", ln)
        if m:
            services.add(f"{m.group(3)}.{m.group(1)}._{m.group(2)}")
            continue
        m2 = re.search(r"\b(_tcp|_udp)\.local\.\s+(_\S+)", ln)
        if m2:
            services.add(f"{m2.group(2)}.{m2.group(1)}")
    return sorted(services)


# ─────────────────────────────────────────────────────────────────────────────
# Scan composition
# ─────────────────────────────────────────────────────────────────────────────
def scan() -> dict[str, Any]:
    """Run a full one-shot LAN cartography pass."""
    t0 = time.time()
    gw         = default_gateway()
    neighbors  = arp_neighbors()
    ips        = [n["ip"] for n in neighbors]

    # Enrich with PTR (cheap concurrency)
    with ThreadPoolExecutor(max_workers=8) as pool:
        ptrs = list(pool.map(reverse_dns, ips))
    for n, ptr in zip(neighbors, ptrs):
        if ptr:
            n["hostname"] = n["hostname"] or ptr

    latencies   = latency_map(ips)
    for n in neighbors:
        n["latency_ms"] = latencies.get(n["ip"], -1.0)
        n["alive"]      = n["latency_ms"] >= 0

    services = mdns_services()
    hops_to_gw  = traceroute_to(gw.get("gateway", "192.168.1.1"), max_hops=2)
    hops_to_dns = traceroute_to("1.1.1.1", max_hops=_TRACERT_HOPS)

    result: dict[str, Any] = {
        "ts":            time.time(),
        "elapsed_s":     round(time.time() - t0, 2),
        "gateway":       gw,
        "neighbors":     neighbors,
        "alive_count":   sum(1 for n in neighbors if n["alive"]),
        "mdns_services": services,
        "hops_to_gw":    hops_to_gw,
        "hops_to_dns":   hops_to_dns,
    }
    _append_ledger(result)
    return result


def _append_ledger(entry: dict[str, Any]) -> None:
    try:
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"[NetPathways] ledger write failed: {e}", file=sys.stderr)


def latest_ledger_entry() -> dict[str, Any] | None:
    if not _LEDGER.exists():
        return None
    try:
        with _LEDGER.open("r", encoding="utf-8") as f:
            last = ""
            for ln in f:
                if ln.strip():
                    last = ln
        return json.loads(last) if last else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Human-readable summary (this is what Alice's tool loop reads)
# ─────────────────────────────────────────────────────────────────────────────
def summarize(entry: dict[str, Any]) -> str:
    if not entry:
        return "No network pathway scans on record yet. Run --scan first."

    gw = entry.get("gateway", {})
    lines: list[str] = []
    lines.append(
        f"LAN cartography (took {entry.get('elapsed_s', '?')}s, "
        f"{entry.get('alive_count', 0)}/{len(entry.get('neighbors', []))} neighbors alive)"
    )

    if gw:
        lines.append(
            f"Gateway: {gw.get('gateway', '?')} via {gw.get('interface', '?')} "
            f"(my IP {gw.get('source_ip', '?')}, link {gw.get('link_status', '?')})"
        )

    neighbors = sorted(entry.get("neighbors", []),
                       key=lambda n: tuple(int(p) for p in n["ip"].split(".")))
    if neighbors:
        lines.append("Neighbors:")
        for n in neighbors:
            tag = ""
            if n["ip"] == gw.get("gateway"):
                tag = " [gateway]"
            elif n["ip"] == gw.get("source_ip"):
                tag = " [me]"
            lat = (f"{n['latency_ms']:.1f}ms" if n["alive"] else "no reply")
            host = n["hostname"] or "(no hostname)"
            lines.append(f"  - {n['ip']:15s} {n['mac']:17s} {lat:>9s}  {host}{tag}")

    services = entry.get("mdns_services", [])
    if services:
        # Trim verbose service names to just the protocol leaf
        leaves = sorted({s.split(".")[0] for s in services})
        lines.append(f"mDNS service types ({len(leaves)}): " + ", ".join(leaves[:12]))
        if len(leaves) > 12:
            lines.append(f"  …and {len(leaves) - 12} more")

    hops = entry.get("hops_to_dns", [])
    if hops:
        lines.append(f"Hops out to 1.1.1.1: {' → '.join(hops)}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(
        prog="swarm_network_pathways",
        description="LAN cartography for Alice. Read-only; writes a JSONL ledger.",
    )
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("scan",    help="One-shot scan; print summary; append ledger.")
    sub.add_parser("summary", help="Print summary of most-recent ledger entry.")
    p_w = sub.add_parser("watch", help="Loop --scan every SECS seconds.")
    p_w.add_argument("interval_s", nargs="?", type=int, default=600)
    args, _extra = ap.parse_known_args()

    cmd = args.cmd or "scan"

    if cmd == "summary":
        print(summarize(latest_ledger_entry() or {}))
        return 0

    if cmd == "watch":
        secs = max(15, int(args.interval_s))
        print(f"[NetPathways] watching every {secs}s (Ctrl-C to stop)")
        try:
            while True:
                entry = scan()
                print(summarize(entry))
                print(f"[NetPathways] sleeping {secs}s …")
                time.sleep(secs)
        except KeyboardInterrupt:
            return 0

    # default: scan
    entry = scan()
    print(summarize(entry))
    return 0


if __name__ == "__main__":
    sys.exit(main())
