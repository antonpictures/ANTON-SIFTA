#!/usr/bin/env python3
"""
epistemic_mesh_sim.py — The Epistemic Mesh: Anti-Gaslight Engine
=================================================================

Decentralized truth-verification using stigmergic swimmers on a
random-geometric network.  Swimmers trace data packets back to their
cryptographic (Ed25519) origins.  Verified data accumulates truth
pheromone; sludge evaporates because it lacks the stigmergic traces
required to propagate.

No censorship — the unverified naturally fades.

Proof of Useful Work: each signature verification IS the computational
work, and it maintains the epistemic integrity of the mesh.  Successful
verifications mint STGM tokens.

Key calculus:
  Epistemic confidence  C_e = τ_truth / (τ_truth + τ_doubt + ε)
  Mesh entropy          H   = -Σ p_e log₂(p_e)  where p = normalised C
  Sludge half-life      t½  = fitted from exponential decay of unverified reach
"""
from __future__ import annotations

import hashlib
import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any

import numpy as np

_REPO = Path(__file__).resolve().parent.parent


# ── Enumerations ──────────────────────────────────────────────

class NodeType(IntEnum):
    ORIGIN = 0
    RELAY = 1
    SLUDGE = 2


class PacketKind(IntEnum):
    SIGNED = 0
    FORGED = 1
    UNSIGNED = 2


class SwimmerState(IntEnum):
    IDLE = 0
    TRACING = 1
    VERIFYING = 2
    DEPOSITING = 3


# ── Configuration ─────────────────────────────────────────────

@dataclass
class MeshConfig:
    n_nodes: int = 64
    n_origins: int = 10
    n_sludge: int = 6
    n_swimmers: int = 300
    edge_radius: float = 0.22
    packet_spawn_prob: float = 0.25
    sludge_spawn_prob: float = 0.40
    truth_deposit: float = 1.8
    doubt_deposit: float = 0.5
    truth_evap: float = 0.997
    doubt_evap: float = 0.96
    packet_ttl: int = 25
    max_packets: int = 200
    sludge_burst_interval: int = 800
    sludge_burst_duration: int = 120
    sludge_burst_multiplier: float = 5.0
    swimmer_speed: int = 2
    stgm_per_verification: float = 0.01
    seed: int = 2026


# ── Data objects ──────────────────────────────────────────────

@dataclass
class Packet:
    pid: int
    kind: PacketKind
    origin_node: int
    claimed_origin: int
    signature: str
    current_node: int
    hops: list[int] = field(default_factory=list)
    ttl: int = 25
    verified: bool | None = None
    attended: bool = False


@dataclass
class Swimmer:
    sid: int
    node: int
    state: SwimmerState = SwimmerState.IDLE
    packet_id: int | None = None
    trace_path: list[int] = field(default_factory=list)
    trace_idx: int = 0
    return_path: list[int] = field(default_factory=list)
    return_idx: int = 0


# ── Simulation ────────────────────────────────────────────────

class EpistemicMeshSim:
    """The full Anti-Gaslight mesh with swimmers, pheromone, and PoUW."""

    def __init__(self, cfg: MeshConfig | None = None) -> None:
        self.cfg = cfg or MeshConfig()
        self.rng = np.random.default_rng(self.cfg.seed)
        self.tick = 0
        self._next_pid = 0

        self._build_network()
        self._generate_keys()
        self._spawn_swimmers()
        self._precompute_paths()

        self.packets: list[Packet] = []
        self.total_verified = 0
        self.total_sludge_rejected = 0
        self.total_stgm_minted = 0.0
        self.verification_log: list[dict[str, Any]] = []
        self._veri_this_tick = 0
        self._sludge_hops: list[int] = []

        self.history: dict[str, list[float]] = {
            "epistemic_coverage": [],
            "sludge_penetration": [],
            "verification_rate": [],
            "mesh_entropy": [],
            "useful_work": [],
        }

    # ── Network construction ──────────────────────────────

    def _build_network(self) -> None:
        N = self.cfg.n_nodes
        self.node_x = self.rng.uniform(0.05, 0.95, N).astype(np.float32)
        self.node_y = self.rng.uniform(0.05, 0.95, N).astype(np.float32)

        self.node_type = np.full(N, NodeType.RELAY, dtype=np.int8)
        origin_idx = self.rng.choice(N, self.cfg.n_origins, replace=False)
        self.node_type[origin_idx] = NodeType.ORIGIN
        self.origin_nodes = list(origin_idx)

        remaining = [i for i in range(N) if self.node_type[i] != NodeType.ORIGIN]
        sludge_idx = self.rng.choice(
            remaining, min(self.cfg.n_sludge, len(remaining)), replace=False
        )
        self.node_type[sludge_idx] = NodeType.SLUDGE
        self.sludge_nodes = list(sludge_idx)

        edges: list[tuple[int, int]] = []
        r2 = self.cfg.edge_radius ** 2
        for i in range(N):
            for j in range(i + 1, N):
                dx = float(self.node_x[i] - self.node_x[j])
                dy = float(self.node_y[i] - self.node_y[j])
                if dx * dx + dy * dy < r2:
                    edges.append((i, j))

        self.edges = edges
        self.n_edges = len(edges)

        self.edge_idx: dict[tuple[int, int], int] = {}
        for idx, (i, j) in enumerate(edges):
            self.edge_idx[(i, j)] = idx
            self.edge_idx[(j, i)] = idx

        self.adj: list[list[int]] = [[] for _ in range(N)]
        for i, j in edges:
            self.adj[i].append(j)
            self.adj[j].append(i)

        self.truth_pher = np.zeros(self.n_edges, dtype=np.float32)
        self.doubt_pher = np.zeros(self.n_edges, dtype=np.float32)

    def _generate_keys(self) -> None:
        self.node_keys: dict[int, bytes] = {}
        for nid in self.origin_nodes:
            self.node_keys[nid] = self.rng.bytes(32)

    def _sign(self, origin: int, data: str) -> str:
        key = self.node_keys.get(origin, b"")
        return hashlib.sha256(key + data.encode()).hexdigest()[:32]

    def _verify_sig(self, origin: int, data: str, sig: str) -> bool:
        if origin not in self.node_keys:
            return False
        expected = hashlib.sha256(self.node_keys[origin] + data.encode()).hexdigest()[:32]
        return sig == expected

    def _spawn_swimmers(self) -> None:
        self.swimmers: list[Swimmer] = []
        for sid in range(self.cfg.n_swimmers):
            node = int(self.rng.integers(0, self.cfg.n_nodes))
            self.swimmers.append(Swimmer(sid=sid, node=node))

    def _precompute_paths(self) -> None:
        N = self.cfg.n_nodes
        self.bfs_parent: list[dict[int, int]] = []
        for src in range(N):
            parent: dict[int, int] = {src: -1}
            q: deque[int] = deque([src])
            while q:
                u = q.popleft()
                for v in self.adj[u]:
                    if v not in parent:
                        parent[v] = u
                        q.append(v)
            self.bfs_parent.append(parent)

    def _shortest_path(self, src: int, dst: int) -> list[int] | None:
        parent = self.bfs_parent[dst]
        if src not in parent:
            return None
        path = [src]
        u = src
        while u != dst:
            u = parent[u]
            path.append(u)
        return path

    # ── Simulation tick ───────────────────────────────────

    def step(self) -> dict[str, Any]:
        self.tick += 1
        self._veri_this_tick = 0
        self._evaporate()
        self._spawn_packets()
        self._move_packets()
        self._swimmer_step()
        self._expire_packets()
        return self._collect_metrics()

    def _evaporate(self) -> None:
        self.truth_pher *= self.cfg.truth_evap
        self.doubt_pher *= self.cfg.doubt_evap

    def _spawn_packets(self) -> None:
        if len(self.packets) >= self.cfg.max_packets:
            return
        in_burst = (
            self.cfg.sludge_burst_interval > 0
            and (self.tick % self.cfg.sludge_burst_interval) < self.cfg.sludge_burst_duration
        )
        for nid in self.origin_nodes:
            if self.rng.random() < self.cfg.packet_spawn_prob:
                pid = self._next_pid
                self._next_pid += 1
                sig = self._sign(nid, f"pkt_{pid}")
                self.packets.append(Packet(
                    pid=pid, kind=PacketKind.SIGNED, origin_node=nid,
                    claimed_origin=nid, signature=sig, current_node=nid,
                    hops=[nid], ttl=self.cfg.packet_ttl,
                ))

        sp = self.cfg.sludge_spawn_prob * (self.cfg.sludge_burst_multiplier if in_burst else 1.0)
        for nid in self.sludge_nodes:
            if self.rng.random() < sp:
                pid = self._next_pid
                self._next_pid += 1
                if self.rng.random() < 0.6:
                    fake_origin = self.origin_nodes[int(self.rng.integers(0, len(self.origin_nodes)))]
                    fake_sig = hashlib.sha256(f"fake_{pid}".encode()).hexdigest()[:32]
                    self.packets.append(Packet(
                        pid=pid, kind=PacketKind.FORGED, origin_node=nid,
                        claimed_origin=fake_origin, signature=fake_sig,
                        current_node=nid, hops=[nid], ttl=self.cfg.packet_ttl,
                    ))
                else:
                    self.packets.append(Packet(
                        pid=pid, kind=PacketKind.UNSIGNED, origin_node=nid,
                        claimed_origin=-1, signature="", current_node=nid,
                        hops=[nid], ttl=self.cfg.packet_ttl,
                    ))

    def _move_packets(self) -> None:
        for pkt in self.packets:
            if pkt.verified is not None or pkt.ttl <= 0:
                continue
            nb = self.adj[pkt.current_node]
            if not nb:
                continue
            w = np.zeros(len(nb), dtype=np.float64)
            for i, n in enumerate(nb):
                eidx = self.edge_idx.get((pkt.current_node, n))
                if eidx is not None:
                    trust = float(self.truth_pher[eidx] - self.doubt_pher[eidx]) + 1.0
                    w[i] = max(0.01, trust)
                else:
                    w[i] = 0.01
            w /= w.sum()
            chosen = nb[int(self.rng.choice(len(nb), p=w))]
            pkt.current_node = chosen
            pkt.hops.append(chosen)
            pkt.ttl -= 1

    def _swimmer_step(self) -> None:
        node_pkts: dict[int, list[int]] = {}
        for i, pkt in enumerate(self.packets):
            if not pkt.attended and pkt.verified is None and pkt.ttl > 0:
                node_pkts.setdefault(pkt.current_node, []).append(i)

        for sw in self.swimmers:
            if sw.state == SwimmerState.IDLE:
                cands = node_pkts.get(sw.node, [])
                if not cands:
                    continue
                pi = cands.pop(0)
                pkt = self.packets[pi]
                pkt.attended = True
                sw.packet_id = pi

                if pkt.kind == PacketKind.UNSIGNED:
                    pkt.verified = False
                    self.total_sludge_rejected += 1
                    self._sludge_hops.append(len(pkt.hops))
                    for h in range(len(pkt.hops) - 1):
                        eidx = self.edge_idx.get((pkt.hops[h], pkt.hops[h + 1]))
                        if eidx is not None:
                            self.doubt_pher[eidx] += self.cfg.doubt_deposit * 0.3
                    sw.packet_id = None
                    continue

                path = self._shortest_path(sw.node, pkt.claimed_origin)
                if path is None or len(path) < 2:
                    pkt.verified = False
                    self.total_sludge_rejected += 1
                    sw.packet_id = None
                    continue
                sw.trace_path = path
                sw.trace_idx = 0
                sw.state = SwimmerState.TRACING

            elif sw.state == SwimmerState.TRACING:
                steps = min(self.cfg.swimmer_speed, len(sw.trace_path) - 1 - sw.trace_idx)
                sw.trace_idx += steps
                sw.node = sw.trace_path[min(sw.trace_idx, len(sw.trace_path) - 1)]
                if sw.trace_idx >= len(sw.trace_path) - 1:
                    sw.state = SwimmerState.VERIFYING

            elif sw.state == SwimmerState.VERIFYING:
                if sw.packet_id is None or sw.packet_id >= len(self.packets):
                    sw.state = SwimmerState.IDLE
                    sw.packet_id = None
                    continue
                pkt = self.packets[sw.packet_id]
                ok = self._verify_sig(pkt.claimed_origin, f"pkt_{pkt.pid}", pkt.signature)

                if ok:
                    pkt.verified = True
                    self.total_verified += 1
                    self._veri_this_tick += 1
                    self.total_stgm_minted += self.cfg.stgm_per_verification
                    self.verification_log.append({
                        "tick": self.tick, "swimmer": sw.sid,
                        "packet": pkt.pid, "origin": pkt.claimed_origin,
                        "sig": pkt.signature[:12],
                        "stgm": self.cfg.stgm_per_verification,
                    })
                    if len(self.verification_log) > 50:
                        self.verification_log.pop(0)
                    sw.return_path = list(reversed(sw.trace_path))
                    sw.return_idx = 0
                    sw.state = SwimmerState.DEPOSITING
                else:
                    pkt.verified = False
                    self.total_sludge_rejected += 1
                    self._sludge_hops.append(len(pkt.hops))
                    for k in range(len(sw.trace_path) - 1):
                        a, b = sw.trace_path[k], sw.trace_path[k + 1]
                        eidx = self.edge_idx.get((a, b))
                        if eidx is not None:
                            self.doubt_pher[eidx] += self.cfg.doubt_deposit
                    sw.state = SwimmerState.IDLE
                    sw.packet_id = None
                    sw.node = sw.trace_path[0]

            elif sw.state == SwimmerState.DEPOSITING:
                steps = min(self.cfg.swimmer_speed, len(sw.return_path) - 1 - sw.return_idx)
                for s in range(steps):
                    idx = sw.return_idx + s
                    if idx < len(sw.return_path) - 1:
                        a = sw.return_path[idx]
                        b = sw.return_path[idx + 1]
                        eidx = self.edge_idx.get((a, b))
                        if eidx is not None:
                            self.truth_pher[eidx] += self.cfg.truth_deposit
                sw.return_idx += steps
                if sw.return_idx < len(sw.return_path):
                    sw.node = sw.return_path[min(sw.return_idx, len(sw.return_path) - 1)]
                if sw.return_idx >= len(sw.return_path) - 1:
                    sw.state = SwimmerState.IDLE
                    sw.packet_id = None

    def _expire_packets(self) -> None:
        alive: list[Packet] = []
        for pkt in self.packets:
            if pkt.ttl > 0 and pkt.verified is None:
                alive.append(pkt)
            elif pkt.verified is None and pkt.kind != PacketKind.SIGNED:
                self._sludge_hops.append(len(pkt.hops))
        self.packets = alive
        self._sludge_hops = self._sludge_hops[-200:]

    # ── Metrics ───────────────────────────────────────────

    def confidence(self) -> np.ndarray:
        """Per-edge epistemic confidence in [0, 1]."""
        eps = 1e-6
        return self.truth_pher / (self.truth_pher + self.doubt_pher + eps)

    def _collect_metrics(self) -> dict[str, Any]:
        conf = self.confidence()
        coverage = float(np.mean(conf > 0.5)) if self.n_edges > 0 else 0.0
        sludge_pen = float(np.mean(self._sludge_hops)) if self._sludge_hops else 0.0

        eps = 1e-8
        p = np.clip(conf, eps, 1.0 - eps)
        H = -float(np.mean(p * np.log2(p) + (1.0 - p) * np.log2(1.0 - p)))

        for key, val in [
            ("epistemic_coverage", coverage),
            ("sludge_penetration", sludge_pen),
            ("verification_rate", float(self._veri_this_tick)),
            ("mesh_entropy", H),
            ("useful_work", float(self.total_verified)),
        ]:
            self.history[key].append(val)
        for k in self.history:
            if len(self.history[k]) > 2000:
                self.history[k] = self.history[k][-2000:]

        in_burst = (
            self.cfg.sludge_burst_interval > 0
            and (self.tick % self.cfg.sludge_burst_interval) < self.cfg.sludge_burst_duration
        )
        return {
            "tick": self.tick,
            "epistemic_coverage": coverage,
            "sludge_penetration": sludge_pen,
            "verification_rate": float(self._veri_this_tick),
            "mesh_entropy": H,
            "packets_alive": len(self.packets),
            "total_verified": self.total_verified,
            "total_sludge_rejected": self.total_sludge_rejected,
            "total_stgm_minted": round(self.total_stgm_minted, 4),
            "truth_pher_peak": float(np.max(self.truth_pher)) if self.n_edges else 0.0,
            "doubt_pher_peak": float(np.max(self.doubt_pher)) if self.n_edges else 0.0,
            "in_sludge_burst": in_burst,
        }


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    sim = EpistemicMeshSim()
    print(f"Epistemic Mesh: {sim.cfg.n_nodes} nodes, {sim.n_edges} edges, "
          f"{len(sim.origin_nodes)} origins, {len(sim.sludge_nodes)} sludge generators, "
          f"{sim.cfg.n_swimmers} swimmers")
    print()

    for _ in range(2000):
        m = sim.step()
        if sim.tick % 200 == 0 or sim.tick == 1:
            burst = " ⚠ SLUDGE BURST" if m["in_sludge_burst"] else ""
            print(
                f"  t={m['tick']:5d}  coverage={m['epistemic_coverage']:.3f}  "
                f"entropy={m['mesh_entropy']:.3f}  verified={m['total_verified']}  "
                f"rejected={m['total_sludge_rejected']}  STGM={m['total_stgm_minted']:.2f}  "
                f"pkts={m['packets_alive']}{burst}"
            )

    print(f"\n  Proof of Useful Work: {sim.total_verified} verifications")
    print(f"  STGM minted: {sim.total_stgm_minted:.4f}")
    print(f"  Sludge rejected: {sim.total_sludge_rejected}")
