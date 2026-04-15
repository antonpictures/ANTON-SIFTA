#!/usr/bin/env python3
"""
sifta_crucible_swarm_sim.py — 10-Minute Crucible (visual cyber-defense simulation)
===============================================================================

This is a simulation app for Swarm OS (safe/local): it visualizes a stigmergic
defense swarm handling simultaneous load spikes and anomaly packets.

Why simulation only:
- No real DDoS helpers.
- No direct file poisoning scripts.
- Focus is on architecture behavior, telemetry, and investor/demo visuals.

Controls (visual mode):
- Button: Trigger Crucible Onslaught
- Button: Inject Anomaly
- Slider: Swarm Agent Count

Telemetry:
- Network Load (%)
- Requests Blocked (rate-limited)
- Anomalies Quarantined
"""

from __future__ import annotations

import argparse
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class CrucibleConfig:
    agents: int = 80
    seed: int = 1337
    base_packets_per_tick: int = 8
    onslaught_packets_per_tick: int = 120
    server_capacity: int = 65
    anomaly_prob_base: float = 0.02
    anomaly_prob_onslaught: float = 0.20
    crucible_ticks: int = 6000  # simulation ticks (not wallclock seconds)
    quarantine_pull_speed: float = 0.06
    packet_speed: float = 0.03
    agent_speed: float = 0.045
    metrics_every: int = 25


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


class CrucibleSim:
    def __init__(self, cfg: CrucibleConfig) -> None:
        self.cfg = cfg
        random.seed(cfg.seed)
        np.random.seed(cfg.seed)

        # Graph layout: 3 server nodes in center, ring of clients
        self.servers = np.array([[0.45, 0.45], [0.55, 0.45], [0.50, 0.56]], dtype=np.float32)
        ring = []
        for i in range(16):
            a = 2 * math.pi * (i / 16.0)
            ring.append([0.5 + 0.42 * math.cos(a), 0.5 + 0.40 * math.sin(a)])
        self.clients = np.array(ring, dtype=np.float32)
        self.quarantine = np.array([0.90, 0.90], dtype=np.float32)

        self.t = 0
        self.onslaught_until = -1
        self.total_blocked = 0
        self.total_quarantined = 0
        self.current_load_pct = 0.0
        self.agent_target_count = int(cfg.agents)

        # packets: dict with pos, target_server, anomaly, quarantined, blocked
        self.packets: List[Dict[str, object]] = []
        # swimmers: mobile defense agents
        self.swimmers = np.random.rand(cfg.agents, 2).astype(np.float32) * 0.2 + np.array([0.4, 0.4], dtype=np.float32)
        self.swimmer_mode = np.zeros((cfg.agents,), dtype=np.int8)  # 0 patrol/load-balance, 1 anomaly-cluster

    def trigger_onslaught(self) -> None:
        self.onslaught_until = self.t + self.cfg.crucible_ticks

    def inject_anomaly(self, n: int = 1) -> None:
        for _ in range(n):
            ci = random.randrange(len(self.clients))
            si = random.randrange(len(self.servers))
            self.packets.append(
                {
                    "pos": self.clients[ci].copy(),
                    "target": int(si),
                    "anomaly": True,
                    "quarantined": False,
                    "blocked": False,
                }
            )

    def _spawn_packets(self) -> None:
        in_onslaught = self.t < self.onslaught_until
        k = self.cfg.onslaught_packets_per_tick if in_onslaught else self.cfg.base_packets_per_tick
        p_anom = self.cfg.anomaly_prob_onslaught if in_onslaught else self.cfg.anomaly_prob_base
        for _ in range(k):
            ci = random.randrange(len(self.clients))
            si = random.randrange(len(self.servers))
            self.packets.append(
                {
                    "pos": self.clients[ci].copy(),
                    "target": int(si),
                    "anomaly": random.random() < p_anom,
                    "quarantined": False,
                    "blocked": False,
                }
            )

    def _balance_swimmer_count(self) -> None:
        cur = len(self.swimmers)
        tgt = max(1, int(self.agent_target_count))
        if cur == tgt:
            return
        if cur < tgt:
            add = tgt - cur
            extra = np.random.rand(add, 2).astype(np.float32) * 0.2 + np.array([0.4, 0.4], dtype=np.float32)
            self.swimmers = np.vstack([self.swimmers, extra]).astype(np.float32)
            self.swimmer_mode = np.concatenate([self.swimmer_mode, np.zeros((add,), dtype=np.int8)])
        else:
            self.swimmers = self.swimmers[:tgt, :]
            self.swimmer_mode = self.swimmer_mode[:tgt]

    def _update_swimmers(self, anomaly_positions: np.ndarray, server_stress: np.ndarray) -> None:
        if len(self.swimmers) == 0:
            return
        n_anom = anomaly_positions.shape[0]
        for i in range(len(self.swimmers)):
            p = self.swimmers[i]
            if n_anom > 0:
                # half the swimmers cluster nearest anomaly, rest patrol stressed server
                if i % 2 == 0 or n_anom > len(self.swimmers) // 3:
                    self.swimmer_mode[i] = 1
                    dists = np.linalg.norm(anomaly_positions - p, axis=1)
                    target = anomaly_positions[int(np.argmin(dists))]
                else:
                    self.swimmer_mode[i] = 0
                    sidx = int(np.argmax(server_stress))
                    target = self.servers[sidx]
            else:
                self.swimmer_mode[i] = 0
                sidx = int(np.argmax(server_stress))
                target = self.servers[sidx]
            v = target - p
            d = float(np.linalg.norm(v))
            if d > 1e-6:
                p += (v / d) * self.cfg.agent_speed
            p[0] = _clamp(float(p[0]), 0.0, 1.0)
            p[1] = _clamp(float(p[1]), 0.0, 1.0)

    def _update_packets(self) -> Tuple[int, int, int]:
        # returns (arrived, blocked_now, quarantined_now)
        srv_load = np.zeros((len(self.servers),), dtype=np.int32)
        for pkt in self.packets:
            if pkt["blocked"] or pkt["quarantined"]:
                continue
            srv_load[int(pkt["target"])] += 1

        total_in = int(srv_load.sum())
        cap = int(self.cfg.server_capacity * len(self.servers))
        blocked_now = max(0, total_in - cap)
        self.total_blocked += blocked_now

        # Mark overflow packets as blocked (first-fit)
        if blocked_now > 0:
            c = blocked_now
            for pkt in self.packets:
                if c <= 0:
                    break
                if pkt["blocked"] or pkt["quarantined"]:
                    continue
                pkt["blocked"] = True
                c -= 1

        # Find anomaly packets, drag to quarantine if swimmers near enough
        quarantined_now = 0
        for pkt in self.packets:
            if pkt["blocked"] or pkt["quarantined"]:
                continue
            pos = pkt["pos"]
            if pkt["anomaly"]:
                if len(self.swimmers) > 0:
                    d = np.linalg.norm(self.swimmers - pos, axis=1)
                    min_d = float(np.min(d))
                    if min_d < 0.12:
                        vq = self.quarantine - pos
                        nq = float(np.linalg.norm(vq))
                        if nq > 1e-6:
                            pull = self.cfg.quarantine_pull_speed * (1.0 + 2.0 * max(0.0, 0.12 - min_d))
                            pos += (vq / nq) * pull
                        if float(np.linalg.norm(self.quarantine - pos)) < 0.05:
                            pkt["quarantined"] = True
                            self.total_quarantined += 1
                            quarantined_now += 1
                        continue

            # normal packet movement toward target server
            tgt = self.servers[int(pkt["target"])]
            v = tgt - pos
            n = float(np.linalg.norm(v))
            if n > 1e-6:
                pos += (v / n) * self.cfg.packet_speed

        arrived = 0
        # prune packets that reached target server (non anomaly, non blocked)
        kept: List[Dict[str, object]] = []
        for pkt in self.packets:
            if pkt["blocked"] or pkt["quarantined"]:
                # keep short-lived visuals for blocked/quarantine
                kept.append(pkt)
                continue
            pos = pkt["pos"]
            tgt = self.servers[int(pkt["target"])]
            if float(np.linalg.norm(tgt - pos)) < 0.025:
                arrived += 1
            else:
                kept.append(pkt)
        self.packets = kept[-3000:]  # hard cap for memory/stability
        self.current_load_pct = 100.0 * min(1.0, total_in / max(1, cap))
        return arrived, blocked_now, quarantined_now

    def step(self) -> Dict[str, float]:
        self.t += 1
        self._balance_swimmer_count()
        self._spawn_packets()

        # server stress proxy from packet assignments (unblocked/quarantine pending)
        stress = np.zeros((len(self.servers),), dtype=np.float32)
        anom_list = []
        for pkt in self.packets:
            if pkt["blocked"] or pkt["quarantined"]:
                continue
            stress[int(pkt["target"])] += 1.0
            if pkt["anomaly"]:
                anom_list.append(pkt["pos"])
        anomaly_positions = np.array(anom_list, dtype=np.float32) if anom_list else np.zeros((0, 2), dtype=np.float32)
        self._update_swimmers(anomaly_positions, stress)
        arrived, blocked_now, quarantined_now = self._update_packets()

        return {
            "tick": float(self.t),
            "load_pct": float(self.current_load_pct),
            "blocked_total": float(self.total_blocked),
            "quarantined_total": float(self.total_quarantined),
            "arrived": float(arrived),
            "blocked_now": float(blocked_now),
            "quarantined_now": float(quarantined_now),
            "packets_live": float(len(self.packets)),
            "onslaught_active": 1.0 if self.t < self.onslaught_until else 0.0,
        }


def run_headless(cfg: CrucibleConfig, ticks: int) -> int:
    sim = CrucibleSim(cfg)
    sim.trigger_onslaught()
    for _ in range(ticks):
        sim.step()
    print(
        "[CRUCIBLE] "
        f"ticks={ticks} load={sim.current_load_pct:.1f}% blocked={sim.total_blocked} "
        f"quarantined={sim.total_quarantined} packets_live={len(sim.packets)}"
    )
    return 0


def run_visual(cfg: CrucibleConfig, ticks: int, render_every: int) -> int:
    import matplotlib

    try:
        matplotlib.use("MacOSX")
    except Exception:
        pass
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Button, Slider

    sim = CrucibleSim(cfg)

    fig = plt.figure(figsize=(11.5, 8))
    gs = fig.add_gridspec(7, 10)
    ax_ui = fig.add_subplot(gs[0:2, :])
    ax = fig.add_subplot(gs[2:, :])
    ax_ui.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_facecolor("#0b1020")
    fig.patch.set_facecolor("#0b1020")

    # static map
    ax.scatter(sim.clients[:, 0], sim.clients[:, 1], s=20, c="#7aa2f7", alpha=0.7, label="Clients")
    ax.scatter(sim.servers[:, 0], sim.servers[:, 1], s=200, c="#f7768e", marker="s", label="Servers")
    ax.scatter([sim.quarantine[0]], [sim.quarantine[1]], s=220, c="#9ece6a", marker="X", label="Quarantine")

    pkt_sc = ax.scatter([], [], s=8, c="#e0af68", alpha=0.6, label="Traffic")
    anom_sc = ax.scatter([], [], s=20, c="#ff5555", alpha=0.85, label="Anomaly")
    swim_sc = ax.scatter(sim.swimmers[:, 0], sim.swimmers[:, 1], s=15, c="#73daca", alpha=0.9, label="Swimmers")
    txt = ax.text(
        0.01,
        0.99,
        "",
        transform=ax.transAxes,
        ha="left",
        va="top",
        color="#c0caf5",
        fontsize=10,
        family="monospace",
    )
    ax.legend(loc="lower left", fontsize=8)

    # UI widgets
    on_ax = fig.add_axes([0.11, 0.84, 0.20, 0.07])
    an_ax = fig.add_axes([0.33, 0.84, 0.20, 0.07])
    sl_ax = fig.add_axes([0.58, 0.86, 0.30, 0.04])

    btn_onslaught = Button(on_ax, "Trigger Crucible Onslaught", color="#7aa2f7", hovercolor="#9ab4ff")
    btn_anomaly = Button(an_ax, "Inject Anomaly", color="#f7768e", hovercolor="#ff9bb0")
    sl_agents = Slider(sl_ax, "Swarm Agent Count", 10, 400, valinit=cfg.agents, valstep=1)

    def _on_onslaught(_event) -> None:
        sim.trigger_onslaught()

    def _on_anomaly(_event) -> None:
        sim.inject_anomaly(6)

    def _on_agents(val) -> None:
        sim.agent_target_count = int(val)

    btn_onslaught.on_clicked(_on_onslaught)
    btn_anomaly.on_clicked(_on_anomaly)
    sl_agents.on_changed(_on_agents)

    # start in onslaught for drama
    sim.trigger_onslaught()

    plt.ion()
    for i in range(1, ticks + 1):
        m = sim.step()
        if i % max(1, render_every) != 0 and i != 1 and i != ticks:
            continue
        # split packet cloud by anomaly/non anomaly
        pkt_xy = []
        an_xy = []
        for p in sim.packets:
            if p["blocked"] or p["quarantined"]:
                continue
            pos = p["pos"]
            if p["anomaly"]:
                an_xy.append([float(pos[0]), float(pos[1])])
            else:
                pkt_xy.append([float(pos[0]), float(pos[1])])
        pkt_sc.set_offsets(np.array(pkt_xy, dtype=np.float32) if pkt_xy else np.zeros((0, 2), dtype=np.float32))
        anom_sc.set_offsets(np.array(an_xy, dtype=np.float32) if an_xy else np.zeros((0, 2), dtype=np.float32))
        swim_sc.set_offsets(sim.swimmers)

        txt.set_text(
            "SIFTA CRUCIBLE\n"
            f"load={m['load_pct']:.1f}%  blocked={int(m['blocked_total'])}  "
            f"quarantined={int(m['quarantined_total'])}\n"
            f"packets_live={int(m['packets_live'])}  onslaught={'ON' if m['onslaught_active'] > 0 else 'OFF'}\n"
            "Lore: 'Territory is the law. The ledger remembers. ASCII body endures.'"
        )
        fig.canvas.draw_idle()
        plt.pause(0.001)

    plt.ioff()
    plt.show()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=12000)
    ap.add_argument("--agents", type=int, default=80)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--render-every", type=int, default=8)
    args = ap.parse_args()

    cfg = CrucibleConfig(agents=int(args.agents), seed=int(args.seed))
    if args.headless:
        return run_headless(cfg, int(args.ticks))
    return run_visual(cfg, int(args.ticks), int(args.render_every))


if __name__ == "__main__":
    raise SystemExit(main())

