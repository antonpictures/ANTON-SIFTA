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
_SYS = REPO_ROOT / "System"


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
    import sys

    if str(_SYS) not in sys.path:
        sys.path.insert(0, str(_SYS))
    from sim_lab_theme import (
        LAB_BG,
        LAB_PANEL,
        apply_matplotlib_lab_style,
        ensure_matplotlib,
        neon_suptitle,
    )

    ensure_matplotlib("Crucible swarm sim — use --headless without matplotlib")
    import matplotlib

    try:
        matplotlib.use("MacOSX")
    except Exception:
        pass
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.collections import LineCollection
    from matplotlib.widgets import Button, Slider

    apply_matplotlib_lab_style()

    sim = CrucibleSim(cfg)

    fig = plt.figure(figsize=(13, 9))
    fig.patch.set_facecolor(LAB_BG)
    neon_suptitle(fig, "CRUCIBLE — NETWORK DEFENSE LAB", "load · rate-limit · quarantine drag · swimmer patrol")
    fig.canvas.manager.set_window_title("SIFTA Crucible — Cyber-Defense Simulation")
    gs = fig.add_gridspec(8, 12, hspace=0.35, wspace=0.3)

    # Telemetry HUD panel (top)
    ax_hud = fig.add_subplot(gs[0:2, :])
    ax_hud.axis("off")
    ax_hud.set_facecolor(LAB_BG)

    # Main arena
    ax = fig.add_subplot(gs[2:, :])
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_facecolor(LAB_PANEL)
    for spine in ax.spines.values():
        spine.set_color("#2a3150")
        spine.set_linewidth(1.5)

    # Network paths: lines from every client to every server (dim background grid)
    net_segments = []
    for c in sim.clients:
        for s in sim.servers:
            net_segments.append([(float(c[0]), float(c[1])), (float(s[0]), float(s[1]))])
    net_lc = LineCollection(net_segments, colors="#1a2040", linewidths=0.4, alpha=0.5)
    ax.add_collection(net_lc)

    # Quarantine zone glow ring
    q_ring = mpatches.Circle(
        (float(sim.quarantine[0]), float(sim.quarantine[1])),
        0.06, fill=False, edgecolor="#9ece6a", linewidth=2.0, alpha=0.7, linestyle="--"
    )
    ax.add_patch(q_ring)
    ax.text(
        float(sim.quarantine[0]), float(sim.quarantine[1]) - 0.08,
        "QUARANTINE", ha="center", va="top", fontsize=7, color="#9ece6a", alpha=0.8, family="monospace"
    )

    # Client nodes
    ax.scatter(sim.clients[:, 0], sim.clients[:, 1], s=35, c="#7aa2f7", alpha=0.8, zorder=5)
    for ci, c in enumerate(sim.clients):
        ax.text(float(c[0]), float(c[1]) + 0.025, f"C{ci}", fontsize=5, ha="center",
                color="#7aa2f7", alpha=0.5, family="monospace")

    # Server nodes (will pulse via dynamic scatter)
    srv_sc = ax.scatter(
        sim.servers[:, 0], sim.servers[:, 1],
        s=300, c="#f7768e", marker="s", zorder=10, edgecolors="#ff9bb0", linewidths=1.5
    )
    srv_glow = ax.scatter(
        sim.servers[:, 0], sim.servers[:, 1],
        s=600, c="#f7768e", marker="s", alpha=0.15, zorder=9
    )
    for si, s in enumerate(sim.servers):
        ax.text(float(s[0]), float(s[1]) + 0.035, f"SRV{si}", fontsize=7, ha="center",
                color="#ff9bb0", weight="bold", family="monospace", zorder=11)

    # Quarantine beacon
    ax.scatter([sim.quarantine[0]], [sim.quarantine[1]], s=280, c="#9ece6a", marker="X", zorder=10,
               edgecolors="#b4f28a", linewidths=1.5)

    # Dynamic scatters
    pkt_sc = ax.scatter([], [], s=6, c="#e0af68", alpha=0.5, zorder=6)
    anom_sc = ax.scatter([], [], s=28, c="#ff5555", alpha=0.9, zorder=8, marker="D", edgecolors="#ff8888",
                         linewidths=0.5)
    anom_glow = ax.scatter([], [], s=70, c="#ff3333", alpha=0.2, zorder=7, marker="D")
    swim_sc = ax.scatter(
        sim.swimmers[:, 0], sim.swimmers[:, 1],
        s=18, c="#73daca", alpha=0.95, zorder=8, edgecolors="#a3f0e0", linewidths=0.4
    )
    swim_trail = ax.scatter([], [], s=5, c="#73daca", alpha=0.15, zorder=4)

    # HUD text elements
    hud_title = ax_hud.text(
        0.5, 0.95, "SIFTA  CRUCIBLE  —  CYBER-DEFENSE  SIMULATION",
        transform=ax_hud.transAxes, ha="center", va="top",
        fontsize=14, color="#c0caf5", weight="bold", family="monospace"
    )
    hud_stats = ax_hud.text(
        0.5, 0.45, "", transform=ax_hud.transAxes, ha="center", va="center",
        fontsize=11, color="#c0caf5", family="monospace"
    )
    hud_lore = ax_hud.text(
        0.5, 0.05, "Territory is the law.  The ledger remembers.  ASCII body endures.",
        transform=ax_hud.transAxes, ha="center", va="bottom",
        fontsize=8, color="#565f89", style="italic", family="monospace"
    )

    # Status bar in main axis
    status_txt = ax.text(
        0.01, 0.01, "", transform=ax.transAxes, ha="left", va="bottom",
        fontsize=8, color="#565f89", family="monospace"
    )

    # Legend
    ax.legend(
        handles=[
            mpatches.Patch(color="#7aa2f7", label="Clients"),
            mpatches.Patch(color="#f7768e", label="Servers"),
            mpatches.Patch(color="#e0af68", label="Traffic"),
            mpatches.Patch(color="#ff5555", label="Anomaly"),
            mpatches.Patch(color="#73daca", label="Swimmers"),
            mpatches.Patch(color="#9ece6a", label="Quarantine"),
        ],
        loc="lower left", fontsize=7, facecolor="#0b1020", edgecolor="#1a2040",
        labelcolor="#c0caf5", framealpha=0.9,
    )

    # UI widgets
    on_ax = fig.add_axes([0.08, 0.78, 0.22, 0.05])
    an_ax = fig.add_axes([0.32, 0.78, 0.22, 0.05])
    sl_ax = fig.add_axes([0.58, 0.79, 0.32, 0.03])
    for w_ax in (on_ax, an_ax, sl_ax):
        w_ax.set_facecolor("#1a1b36")

    btn_onslaught = Button(on_ax, "TRIGGER CRUCIBLE ONSLAUGHT", color="#1a2a50", hovercolor="#2a3a70")
    btn_onslaught.label.set_color("#7aa2f7")
    btn_onslaught.label.set_fontsize(8)
    btn_onslaught.label.set_family("monospace")

    btn_anomaly = Button(an_ax, "INJECT ANOMALY x6", color="#3a1020", hovercolor="#5a2030")
    btn_anomaly.label.set_color("#f7768e")
    btn_anomaly.label.set_fontsize(8)
    btn_anomaly.label.set_family("monospace")

    sl_agents = Slider(sl_ax, "Swarm", 10, 400, valinit=cfg.agents, valstep=1,
                       color="#73daca", track_color="#1a2040")
    sl_agents.label.set_color("#73daca")
    sl_agents.label.set_fontsize(8)
    sl_agents.valtext.set_color("#73daca")

    def _on_onslaught(_event) -> None:
        sim.trigger_onslaught()

    def _on_anomaly(_event) -> None:
        sim.inject_anomaly(6)

    def _on_agents(val) -> None:
        sim.agent_target_count = int(val)

    btn_onslaught.on_clicked(_on_onslaught)
    btn_anomaly.on_clicked(_on_anomaly)
    sl_agents.on_changed(_on_agents)

    sim.trigger_onslaught()

    prev_swimmers = sim.swimmers.copy()

    plt.ion()
    for i in range(1, ticks + 1):
        m = sim.step()
        if i % max(1, render_every) != 0 and i != 1 and i != ticks:
            continue

        pkt_xy, an_xy = [], []
        for p in sim.packets:
            if p["blocked"] or p["quarantined"]:
                continue
            pos = p["pos"]
            if p["anomaly"]:
                an_xy.append([float(pos[0]), float(pos[1])])
            else:
                pkt_xy.append([float(pos[0]), float(pos[1])])

        pkt_sc.set_offsets(np.array(pkt_xy, dtype=np.float32) if pkt_xy else np.zeros((0, 2), dtype=np.float32))
        anom_arr = np.array(an_xy, dtype=np.float32) if an_xy else np.zeros((0, 2), dtype=np.float32)
        anom_sc.set_offsets(anom_arr)
        anom_glow.set_offsets(anom_arr)
        swim_sc.set_offsets(sim.swimmers)
        swim_trail.set_offsets(prev_swimmers.copy())
        prev_swimmers = sim.swimmers.copy()

        # Server stress pulsing — larger glow when load is high
        load_frac = min(1.0, m["load_pct"] / 100.0)
        glow_size = 400 + 800 * load_frac
        glow_alpha = 0.08 + 0.25 * load_frac
        srv_glow.set_sizes(np.full(len(sim.servers), glow_size))
        srv_glow.set_alpha(float(glow_alpha))
        stress_colors = [(1.0, 0.47 * (1.0 - load_frac), 0.47 * (1.0 - load_frac))] * len(sim.servers)
        srv_sc.set_facecolors(stress_colors)

        # Network lines pulse brighter under onslaught
        net_alpha = 0.3 + 0.5 * load_frac
        net_lc.set_alpha(float(net_alpha))
        net_color = (
            0.1 + 0.2 * load_frac,
            0.12 + 0.08 * load_frac,
            0.25 + 0.15 * load_frac,
        )
        net_lc.set_colors([net_color])

        # Quarantine ring pulses when captures happen
        q_alpha = 0.5 + 0.5 * min(1.0, m["quarantined_now"] / 3.0)
        q_ring.set_alpha(float(q_alpha))

        onslaught_tag = "ONSLAUGHT ACTIVE" if m["onslaught_active"] > 0 else "PATROL MODE"
        hud_stats.set_text(
            f"LOAD {m['load_pct']:5.1f}%  |  "
            f"BLOCKED {int(m['blocked_total']):>7,}  |  "
            f"QUARANTINED {int(m['quarantined_total']):>5,}  |  "
            f"LIVE {int(m['packets_live']):>5,}  |  "
            f"{onslaught_tag}"
        )
        hud_stats.set_color("#ff5555" if m["onslaught_active"] > 0 else "#9ece6a")

        status_txt.set_text(f"tick {int(m['tick'])}/{ticks}  swimmers={len(sim.swimmers)}")

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

