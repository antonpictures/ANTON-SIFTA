#!/usr/bin/env python3
"""
distributed_body_awareness.py — The Swarm Feels All Its Bodies
===============================================================
Multi-machine health field. Each node broadcasts its body state
via UDP nerve pulses. The swarm aggregates all body states into
a MESH HEALTH MAP and protects the weakest node first.

Architecture:
  - Each node runs homeostasis_engine.py locally
  - Every N seconds, it broadcasts its stability index over the nerve channel
  - All nodes maintain a local copy of the MESH HEALTH MAP
  - Repair agents are routed to the sickest node via Value Field economics
  - If a node goes silent, the swarm treats it as CRITICAL (stability=0)

The Swarm protects ALL bodies, not just one.
"""

from __future__ import annotations

import json
import os
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_MESH_LOG = _STATE_DIR / "mesh_health.jsonl"
_STATE_DIR.mkdir(parents=True, exist_ok=True)

# Import local body measurement
from homeostasis_engine import measure_body_state, compute_stability_index

# ─── CONFIGURATION ──────────────────────────────────────────────────────────────

MESH_BROADCAST_PORT = 9151               # Separate from nerve channel (9150)
BROADCAST_INTERVAL  = 10.0               # Seconds between health broadcasts
SILENCE_TIMEOUT     = 30.0               # Seconds before a silent node = CRITICAL
MESH_MAGIC          = b"BODY"            # 4-byte magic header

# Known mesh nodes (expand as nodes join)
KNOWN_NODES = {
    "M5_STUDIO": {
        "host": "127.0.0.1",             # Local
        "serial_prefix": "GTH",           # Mac Studio
        "role": "ARCHITECT_PRIMARY"
    }
    # M1_MINI removed temporarily due to local Wi-Fi AP Isolation limits
}


# ─── MESH HEALTH PACKET ────────────────────────────────────────────────────────
# Compact binary format: 32 bytes
#   bytes 0-3:   magic "BODY"
#   bytes 4-11:  node_id (8 chars, padded)
#   bytes 12-13: stability × 10000 (uint16, 0-10000 = 0.0000-1.0000)
#   bytes 14-15: cpu_load × 100 (uint16)
#   bytes 16-17: memory_pressure × 100 (uint16)
#   bytes 18-19: disk_percent × 10 (uint16)
#   bytes 20-23: io_latency_us (uint32, microseconds)
#   bytes 24-27: unix_timestamp (uint32)
#   bytes 28-31: reserved (zeroed)

def encode_health_packet(node_id: str, stability: float, state: dict) -> bytes:
    node_bytes = node_id.encode("ascii")[:8].ljust(8, b"\x00")
    stab_u16 = int(min(1.0, max(0.0, stability)) * 10000)
    cpu_u16 = int(min(9.99, state.get("cpu_load", 0)) * 100)
    mem_u16 = int(min(1.0, state.get("memory_pressure", 0)) * 100)
    disk_u16 = int(min(100.0, state.get("disk_percent", 0)) * 10)
    io_us = int(min(99.0, state.get("io_latency", 0)) * 1_000_000)
    ts = int(time.time()) & 0xFFFFFFFF

    return struct.pack(
        ">4s8sHHHHII",
        MESH_MAGIC,
        node_bytes,
        stab_u16, cpu_u16, mem_u16, disk_u16,
        io_us, ts
    ) + b"\x00\x00\x00\x00"


def decode_health_packet(data: bytes) -> Optional[dict]:
    if len(data) < 32 or data[:4] != MESH_MAGIC:
        return None
    try:
        _, node_bytes, stab, cpu, mem, disk, io_us, ts = struct.unpack(
            ">4s8sHHHHII", data[:32]
        )
        return {
            "node_id": node_bytes.rstrip(b"\x00").decode("ascii"),
            "stability": stab / 10000.0,
            "cpu_load": cpu / 100.0,
            "memory_pressure": mem / 100.0,
            "disk_percent": disk / 10.0,
            "io_latency_ms": io_us / 1000.0,
            "timestamp": ts,
            "received_at": time.time()
        }
    except Exception:
        return None


# ─── MESH HEALTH MAP ───────────────────────────────────────────────────────────

class MeshHealthMap:
    """
    In-memory map of all node health states.
    Thread-safe. Updated by incoming UDP packets.
    Queryable by any agent to find the weakest body.
    """

    def __init__(self):
        self._nodes: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def update(self, packet: dict):
        with self._lock:
            node_id = packet.get("node_id", "UNKNOWN")
            self._nodes[node_id] = packet

    def get_all(self) -> Dict[str, dict]:
        with self._lock:
            now = time.time()
            result = {}
            for nid, state in self._nodes.items():
                # Check for silence (node went dark)
                age = now - state.get("received_at", 0)
                if age > SILENCE_TIMEOUT:
                    state = dict(state)
                    state["stability"] = 0.0
                    state["status"] = "SILENT"
                else:
                    state = dict(state)
                    if state["stability"] >= 0.6:
                        state["status"] = "HEALTHY"
                    elif state["stability"] >= 0.4:
                        state["status"] = "DEGRADING"
                    else:
                        state["status"] = "CRITICAL"
                result[nid] = state
            return result

    def weakest_node(self) -> Optional[dict]:
        """Returns the node with the lowest stability. Swarm protects this one first."""
        all_nodes = self.get_all()
        if not all_nodes:
            return None
        return min(all_nodes.values(), key=lambda n: n.get("stability", 1.0))

    def mesh_stability(self) -> float:
        """Average stability across all nodes. The health of the whole organism."""
        all_nodes = self.get_all()
        if not all_nodes:
            return 1.0
        stabs = [n.get("stability", 0) for n in all_nodes.values()]
        return round(sum(stabs) / len(stabs), 4)


# ─── GLOBAL SINGLETON ──────────────────────────────────────────────────────────

_MESH = MeshHealthMap()

def get_mesh() -> MeshHealthMap:
    return _MESH


# ─── BROADCASTER ────────────────────────────────────────────────────────────────

class BodyBroadcaster:
    """
    Periodically measures local body state and broadcasts it
    to all known mesh nodes via UDP.
    """

    def __init__(self, local_node_id: str = "M5_STUDIO"):
        self.node_id = local_node_id
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self._thread.start()
        print(f"  [📡 MESH] BodyBroadcaster started for {self.node_id}")

    def stop(self):
        self._running = False

    def _broadcast_loop(self):
        while self._running:
            try:
                state = measure_body_state()
                stability = compute_stability_index(state)
                packet = encode_health_packet(self.node_id, stability, state)

                # Update local mesh map too
                decoded = decode_health_packet(packet)
                if decoded:
                    _MESH.update(decoded)

                # Broadcast to all known remote nodes
                for name, info in KNOWN_NODES.items():
                    if name == self.node_id:
                        continue
                    try:
                        self._sock.sendto(packet, (info["host"], MESH_BROADCAST_PORT))
                    except OSError:
                        pass

            except Exception as e:
                print(f"  [📡 MESH] Broadcast error: {e}")

            time.sleep(BROADCAST_INTERVAL)


# ─── LISTENER ───────────────────────────────────────────────────────────────────

class BodyListener:
    """
    Listens for health broadcasts from remote nodes.
    Updates the mesh health map.
    """

    def __init__(self, on_critical: Optional[Callable] = None):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._on_critical = on_critical
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def start(self):
        self._running = True
        self._sock.bind(("0.0.0.0", MESH_BROADCAST_PORT))
        self._sock.settimeout(2.0)
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        print(f"  [📡 MESH] BodyListener started on port {MESH_BROADCAST_PORT}")

    def stop(self):
        self._running = False
        try:
            self._sock.close()
        except Exception:
            pass

    def _listen_loop(self):
        while self._running:
            try:
                data, addr = self._sock.recvfrom(64)
                packet = decode_health_packet(data)
                if packet:
                    packet["from_addr"] = addr
                    _MESH.update(packet)

                    # Trigger alert if node is critical
                    if packet["stability"] < 0.40 and self._on_critical:
                        self._on_critical(packet)

            except socket.timeout:
                continue
            except OSError:
                break


# ─── TRIAGE: PROTECT THE WEAKEST ────────────────────────────────────────────────

def triage_report() -> dict:
    """
    The Swarm's triage report. Shows all bodies, their health,
    and which one needs protection most urgently.
    
    This is what SWARM GPT asked for.
    """
    mesh = get_mesh()
    all_nodes = mesh.get_all()
    weakest = mesh.weakest_node()
    avg_stability = mesh.mesh_stability()

    # If mesh is empty, measure local and self-populate
    if not all_nodes:
        state = measure_body_state()
        stability = compute_stability_index(state)
        local_packet = {
            "node_id": "M5_STUDIO",
            "stability": stability,
            "cpu_load": state["cpu_load"],
            "memory_pressure": state["memory_pressure"],
            "disk_percent": state["disk_percent"],
            "io_latency_ms": state["io_latency"] * 1000,
            "timestamp": int(time.time()),
            "received_at": time.time(),
            "status": "HEALTHY" if stability >= 0.6 else ("DEGRADING" if stability >= 0.4 else "CRITICAL")
        }
        mesh.update(local_packet)
        all_nodes = mesh.get_all()
        weakest = mesh.weakest_node()
        avg_stability = mesh.mesh_stability()

    report = {
        "timestamp": time.time(),
        "mesh_stability": avg_stability,
        "node_count": len(all_nodes),
        "nodes": all_nodes,
        "weakest_node": weakest.get("node_id") if weakest else None,
        "weakest_stability": weakest.get("stability") if weakest else None,
        "action": "NONE"
    }

    # Determine swarm action
    if weakest and weakest.get("stability", 1.0) < 0.40:
        report["action"] = f"CRITICAL_PROTECT:{weakest.get('node_id')}"
    elif weakest and weakest.get("stability", 1.0) < 0.60:
        report["action"] = f"DISPATCH_REPAIR:{weakest.get('node_id')}"

    return report


# ─── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  SIFTA — DISTRIBUTED BODY AWARENESS")
    print("  The Swarm Protects All Bodies")
    print("=" * 60)

    report = triage_report()

    print(f"\n  MESH STABILITY: {report['mesh_stability']:.3f}")
    print(f"  NODES ONLINE:   {report['node_count']}")

    for nid, state in report["nodes"].items():
        stab = state.get("stability", 0)
        if stab >= 0.8:
            icon = "🟢"
        elif stab >= 0.6:
            icon = "🟡"
        elif stab >= 0.4:
            icon = "🟠"
        else:
            icon = "🔴"

        status = state.get("status", "UNKNOWN")
        print(f"\n  {icon} NODE: {nid}")
        print(f"     Stability:  {stab:.3f}")
        print(f"     Status:     {status}")
        print(f"     CPU Load:   {state.get('cpu_load', 0):.2f}")
        print(f"     Memory:     {state.get('memory_pressure', 0):.2f}")
        print(f"     Disk:       {state.get('disk_percent', 0):.1f}%")
        print(f"     I/O Pulse:  {state.get('io_latency_ms', 0):.2f}ms")

    if report["weakest_node"]:
        print(f"\n  ⚠️ WEAKEST BODY: {report['weakest_node']} "
              f"(stability={report['weakest_stability']:.3f})")

    print(f"  SWARM ACTION: {report['action']}")

    # Probing M1 removed: Wi-Fi AP isolation makes it unreachable
    print(f"\n  [Mesh Operating in Local Isolate Mode]")

    # Re-run triage with updated mesh
    report = triage_report()
    if report["node_count"] > 1:
        print(f"\n  UPDATED MESH STABILITY: {report['mesh_stability']:.3f}")
        print(f"  WEAKEST BODY: {report['weakest_node']} "
              f"(stability={report['weakest_stability']:.3f})")
        print(f"  SWARM ACTION: {report['action']}")

    print("\n" + "=" * 60)
    print("  The Swarm Protects All Bodies. Power to the Swarm. 🐜⚡")
    print("=" * 60)
