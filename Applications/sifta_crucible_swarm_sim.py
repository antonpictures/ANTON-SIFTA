#!/usr/bin/env python3
"""
sifta_crucible_swarm_sim.py — 10-Minute Crucible (visual cyber-defense simulation)
===============================================================================

This is a simulation app for Swarm OS (safe/local): it visualizes a stigmergic
defense swarm handling simultaneous load spikes and anomaly packets. With
--embodied-gaze, it also forwards the computed gaze peak into Alice's canonical
active camera target state.

Why safe/local:
- No real DDoS helpers.
- No direct file poisoning scripts.
- Focus is on architecture behavior, telemetry, and investor/demo visuals.
- Optional embodied gaze writes only the local active_saccade_target ledger.

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
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
_SYS = REPO_ROOT / "System"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from swarmrl.tasks.stigmergic_entropy_gate import EntropyGateConfig, StigmergicEntropyGate
from System.swarm_foveated_saccades import FoveatedSaccadeConfig, FoveatedSwarmSaccades
from System.swarm_immune_quorum import ImmuneQuorumConfig, SwarmImmuneQuorum
from System.swarm_unified_field_engine import UnifiedFieldConfig, UnifiedFieldEngine
from System import swarm_camera_target as camera_target


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
    stigmergic_deposit_strength: float = 0.2
    stigmergic_decay: float = 0.97
    stigmergic_follow_strength: float = 0.012
    immune_grid_size: int = 96
    immune_damage_radius: float = 0.035
    immune_damage_max_centers: int = 48
    immune_follow_strength: float = 0.010
    gaze_grid_size: int = 96
    gaze_every: int = 5
    gaze_saliency_threshold: float = 0.05
    gaze_follow_strength: float = 0.014
    gaze_stigmergic_deposit: float = 0.35
    unified_field_grid_size: int = 96
    unified_field_follow_strength: float = 0.010
    unified_prediction_sigma: float = 0.018
    embodied_gaze: bool = False
    embodied_gaze_every: int = 2
    embodied_gaze_min_salience: float = 0.05
    embodied_gaze_writer: str = "crucible_unified_field"
    embodied_gaze_priority: int = 50
    embodied_gaze_lease_s: float = 2.5
    glyph_every: int = 25


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
        self.swimmer_rewards = np.zeros((cfg.agents,), dtype=np.float32)
        self.swimmer_field_sense = np.zeros((cfg.agents,), dtype=np.float32)
        self.stigmergic_task = StigmergicEntropyGate(
            EntropyGateConfig(
                decay=cfg.stigmergic_decay,
                deposit_strength=cfg.stigmergic_deposit_strength,
            )
        )
        self.tasks = [self.stigmergic_task]
        self.stigmergic_field_max = 0.0
        self.stigmergic_reward_mean = 0.0
        self.stigmergic_reward_max = 0.0
        self.immune_quorum = SwarmImmuneQuorum(
            ImmuneQuorumConfig(
                grid_size=cfg.immune_grid_size,
                decay=0.985,
                diffusion=0.05,
            )
        )
        self.immune_rewards = np.zeros((cfg.agents,), dtype=np.float32)
        self.immune_sense = np.zeros((cfg.agents, 3), dtype=np.float32)
        self.immune_danger_max = 0.0
        self.immune_repair_max = 0.0
        self.immune_signal_max = 0.0
        self.immune_reward_mean = 0.0
        self.foveated_gaze = FoveatedSwarmSaccades(
            cfg.gaze_grid_size,
            cfg.gaze_grid_size,
            FoveatedSaccadeConfig(
                scouts=64,
                foveal_agents=160,
                peripheral_steps=8,
                foveal_steps=10,
                peripheral_sigma=4.0,
                foveal_sigma=3.0,
                scout_jump=10,
                inhibition_radius=12,
                saliency_threshold=cfg.gaze_saliency_threshold,
                seed=cfg.seed,
            ),
        )
        self.gaze_saliency_peak = 0.0
        self.gaze_saccades = 0
        self.gaze_target = np.array([-1.0, -1.0], dtype=np.float32)
        self.gaze_foveal_count = 0
        self.unified_field = UnifiedFieldEngine(
            UnifiedFieldConfig(
                grid_size=cfg.unified_field_grid_size,
                diffusion=0.03,
            )
        )
        self.unified_field_max = 0.0
        self.unified_field_min = 0.0
        self.unified_gradient_mean = 0.0
        self.unified_peak = np.array([-1.0, -1.0], dtype=np.float32)
        self.embodied_gaze_writes = 0
        self.embodied_camera_index = -1
        self.embodied_camera_name = ""
        self.embodied_gaze_last_target = np.array([-1.0, -1.0], dtype=np.float32)

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
            self.swimmer_rewards = np.concatenate([self.swimmer_rewards, np.zeros((add,), dtype=np.float32)])
            self.swimmer_field_sense = np.concatenate([self.swimmer_field_sense, np.zeros((add,), dtype=np.float32)])
            self.immune_rewards = np.concatenate([self.immune_rewards, np.zeros((add,), dtype=np.float32)])
            self.immune_sense = np.vstack([self.immune_sense, np.zeros((add, 3), dtype=np.float32)])
        else:
            self.swimmers = self.swimmers[:tgt, :]
            self.swimmer_mode = self.swimmer_mode[:tgt]
            self.swimmer_rewards = self.swimmer_rewards[:tgt]
            self.swimmer_field_sense = self.swimmer_field_sense[:tgt]
            self.immune_rewards = self.immune_rewards[:tgt]
            self.immune_sense = self.immune_sense[:tgt, :]

        prev = self.stigmergic_task.prev_positions
        if prev is not None and prev.shape[0] != len(self.swimmers):
            self.stigmergic_task.reset()
        immune_prev = self.immune_quorum.prev_positions
        if immune_prev is not None and immune_prev.shape[0] != len(self.swimmers):
            self.immune_quorum.reset()

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

    def _stigmergic_gradient(self, pos: np.ndarray) -> np.ndarray:
        i, j = self.stigmergic_task._idx(pos)
        field = self.stigmergic_task.field
        g = self.stigmergic_task.cfg.grid_size
        left = float(field[max(0, i - 1), j])
        right = float(field[min(g - 1, i + 1), j])
        down = float(field[i, max(0, j - 1)])
        up = float(field[i, min(g - 1, j + 1)])
        grad = np.array([right - left, up - down], dtype=np.float32)
        norm = float(np.linalg.norm(grad))
        if norm <= 1e-8:
            return np.zeros((2,), dtype=np.float32)
        return grad / norm

    def _apply_stigmergic_entropy_gate(self) -> None:
        if len(self.swimmers) == 0:
            return
        positions = self.swimmers[:, :2].astype(np.float32, copy=True)
        rewards = self.stigmergic_task.step(positions)
        self.swimmer_rewards = rewards.astype(np.float32, copy=True)

        for i, p in enumerate(self.swimmers):
            cell_i, cell_j = self.stigmergic_task._idx(p)
            self.swimmer_field_sense[i] = float(self.stigmergic_task.field[cell_i, cell_j])
            grad = self._stigmergic_gradient(p)
            if float(np.linalg.norm(grad)) > 0.0:
                reward_gain = 0.75 + max(0.0, float(self.swimmer_rewards[i]))
                p += grad * self.cfg.stigmergic_follow_strength * reward_gain
                p[0] = _clamp(float(p[0]), 0.0, 1.0)
                p[1] = _clamp(float(p[1]), 0.0, 1.0)

        self.stigmergic_field_max = float(self.stigmergic_task.field.max())
        self.stigmergic_reward_mean = float(np.mean(self.swimmer_rewards)) if len(self.swimmer_rewards) else 0.0
        self.stigmergic_reward_max = float(np.max(self.swimmer_rewards)) if len(self.swimmer_rewards) else 0.0

    def _field_gradient(self, field: np.ndarray, pos: np.ndarray) -> np.ndarray:
        i, j = self.immune_quorum._idx(pos)
        g = self.immune_quorum.cfg.grid_size
        left = float(field[max(0, i - 1), j])
        right = float(field[min(g - 1, i + 1), j])
        down = float(field[i, max(0, j - 1)])
        up = float(field[i, min(g - 1, j + 1)])
        grad = np.array([right - left, up - down], dtype=np.float32)
        norm = float(np.linalg.norm(grad))
        if norm <= 1e-8:
            return np.zeros((2,), dtype=np.float32)
        return grad / norm

    def _apply_immune_quorum(self, anomaly_positions: np.ndarray) -> None:
        if len(self.swimmers) == 0:
            return
        if anomaly_positions.size:
            centers = anomaly_positions[:, :2]
            max_centers = max(1, int(self.cfg.immune_damage_max_centers))
            if len(centers) > max_centers:
                idx = np.linspace(0, len(centers) - 1, max_centers).astype(int)
                centers = centers[idx]
            self.immune_quorum.inject_damage(centers, radius=self.cfg.immune_damage_radius)

        positions = self.swimmers[:, :2].astype(np.float32, copy=True)
        rewards = self.immune_quorum.step(positions)
        self.immune_rewards = rewards.astype(np.float32, copy=True)
        self.immune_sense = self.immune_quorum.sense(positions)

        immune_field = self.immune_quorum.danger + self.immune_quorum.repair
        for i, p in enumerate(self.swimmers):
            grad = self._field_gradient(immune_field, p)
            if float(np.linalg.norm(grad)) <= 0.0:
                continue
            reward_gain = 0.75 + max(0.0, float(self.immune_rewards[i]))
            p += grad * self.cfg.immune_follow_strength * reward_gain
            p[0] = _clamp(float(p[0]), 0.0, 1.0)
            p[1] = _clamp(float(p[1]), 0.0, 1.0)

        self.immune_danger_max = float(self.immune_quorum.danger.max())
        self.immune_repair_max = float(self.immune_quorum.repair.max())
        self.immune_signal_max = float(self.immune_quorum.signal.max())
        self.immune_reward_mean = float(np.mean(self.immune_rewards)) if len(self.immune_rewards) else 0.0

    @staticmethod
    def _normalize_field(field: np.ndarray) -> np.ndarray:
        arr = np.asarray(field, dtype=np.float32)
        max_value = float(arr.max()) if arr.size else 0.0
        if max_value <= 1e-8:
            return np.zeros_like(arr, dtype=np.float32)
        return (arr / max_value).astype(np.float32)

    @staticmethod
    def _resize_field(field: np.ndarray, size: int) -> np.ndarray:
        arr = np.asarray(field, dtype=np.float32)
        if arr.shape == (size, size):
            return arr.copy()
        y_idx = np.linspace(0, arr.shape[0] - 1, size).round().astype(int)
        x_idx = np.linspace(0, arr.shape[1] - 1, size).round().astype(int)
        return arr[np.ix_(y_idx, x_idx)].astype(np.float32)

    def _splat_normalized(self, centers: np.ndarray, weights: np.ndarray, size: int, sigma: float) -> np.ndarray:
        field = np.zeros((size, size), dtype=np.float32)
        centers = np.asarray(centers, dtype=np.float32)
        weights = np.asarray(weights, dtype=np.float32)
        if centers.size == 0:
            return field

        axis = np.linspace(0.0, 1.0, size, dtype=np.float32)
        grid_x, grid_y = np.meshgrid(axis, axis, indexing="ij")
        sigma = max(float(sigma), 1.0 / max(1, size - 1))
        denom = 2.0 * sigma * sigma
        for center, weight in zip(centers[:, :2], weights):
            clipped = np.clip(center[:2], 0.0, 1.0)
            dx = grid_x - float(clipped[0])
            dy = grid_y - float(clipped[1])
            field += max(0.0, float(weight)) * np.exp(-((dx * dx + dy * dy) / denom)).astype(np.float32)
        return field

    def _build_gaze_frame(self, anomaly_positions: np.ndarray) -> np.ndarray:
        g = int(self.cfg.gaze_grid_size)
        frame = np.zeros((g, g), dtype=np.float32)

        # Internal fields index normalized coordinates as [x, y]. The gaze
        # image uses conventional image coordinates [row=y, col=x].
        frame += 0.65 * self._resize_field(self._normalize_field(self.stigmergic_task.field).T, g)
        frame += 1.15 * self._resize_field(self._normalize_field(self.immune_quorum.danger).T, g)
        frame += 0.45 * self._resize_field(self._normalize_field(self.immune_quorum.repair).T, g)

        for pos in anomaly_positions[:, :2] if anomaly_positions.size else []:
            x = int(_clamp(float(pos[0]), 0.0, 1.0) * (g - 1))
            y = int(_clamp(float(pos[1]), 0.0, 1.0) * (g - 1))
            y0 = max(0, y - 1)
            y1 = min(g, y + 2)
            x0 = max(0, x - 1)
            x1 = min(g, x + 2)
            frame[y0:y1, x0:x1] += 1.0

        return np.clip(frame, 0.0, None).astype(np.float32)

    def _apply_foveated_gaze(self, anomaly_positions: np.ndarray) -> None:
        if len(self.swimmers) == 0:
            return
        if self.t % max(1, int(self.cfg.gaze_every)) != 0:
            return

        frame = self._build_gaze_frame(anomaly_positions)
        result = self.foveated_gaze.observe(frame)
        self.gaze_saliency_peak = float(result["saliency_peak"])
        self.gaze_saccades = int(result["saccade_count"])
        self.gaze_foveal_count = int(len(result["foveal_points"]))

        target_xy = np.array(result["target_norm"], dtype=np.float32)
        if not bool(result["saccade_fired"]):
            self.gaze_target = np.array([-1.0, -1.0], dtype=np.float32)
            return

        self.gaze_target = target_xy
        self.stigmergic_task.field[self.stigmergic_task._idx(target_xy)] += self.cfg.gaze_stigmergic_deposit

        for p in self.swimmers:
            delta = target_xy - p
            dist = float(np.linalg.norm(delta))
            if dist <= 1e-8:
                continue
            gain = self.cfg.gaze_follow_strength * (0.75 + self.gaze_saliency_peak)
            p += (delta / dist) * gain
            p[0] = _clamp(float(p[0]), 0.0, 1.0)
            p[1] = _clamp(float(p[1]), 0.0, 1.0)

    def _build_prediction_field(self, anomaly_positions: np.ndarray, server_stress: np.ndarray) -> np.ndarray:
        g = int(self.cfg.unified_field_grid_size)
        stress = np.asarray(server_stress, dtype=np.float32)
        max_stress = float(stress.max()) if stress.size else 0.0
        if max_stress > 0.0:
            server_weights = stress / max_stress
        else:
            server_weights = np.zeros((len(self.servers),), dtype=np.float32)

        prediction = self._splat_normalized(
            self.servers,
            server_weights,
            g,
            sigma=max(self.cfg.unified_prediction_sigma * 1.5, 0.02),
        )

        if anomaly_positions.size:
            anomaly_weights = np.ones((len(anomaly_positions),), dtype=np.float32)
            prediction += 0.85 * self._splat_normalized(
                anomaly_positions[:, :2],
                anomaly_weights,
                g,
                sigma=self.cfg.unified_prediction_sigma,
            )
            prediction += 0.55 * self._splat_normalized(
                self.quarantine.reshape(1, 2),
                np.ones((1,), dtype=np.float32),
                g,
                sigma=0.045,
            )

        return prediction.astype(np.float32)

    def _apply_unified_field(self, anomaly_positions: np.ndarray, server_stress: np.ndarray) -> None:
        if len(self.swimmers) == 0:
            return

        g = int(self.cfg.unified_field_grid_size)
        memory = self._resize_field(self.stigmergic_task.field, g)
        prediction = self._build_prediction_field(anomaly_positions, server_stress)
        salience = self._resize_field(self.foveated_gaze.saliency.T, g)
        danger = self._resize_field(self.immune_quorum.danger, g)
        repair = self._resize_field(self.immune_quorum.repair, g)

        total = self.unified_field.update(
            memory=memory,
            prediction=prediction,
            salience=salience,
            danger=danger,
            repair=repair,
            positions=self.swimmers[:, :2],
        )

        grad_norms = []
        for p in self.swimmers:
            grad = self.unified_field.gradient_at(p)
            norm = float(np.linalg.norm(grad))
            grad_norms.append(norm)
            if norm <= 0.0:
                continue
            grad = grad / norm
            field_gain = 0.75 + max(0.0, float(self.unified_field.total[self.unified_field._idx(p)]))
            p += grad * self.cfg.unified_field_follow_strength * field_gain
            p[0] = _clamp(float(p[0]), 0.0, 1.0)
            p[1] = _clamp(float(p[1]), 0.0, 1.0)

        peak_x, peak_y, _peak_value = self.unified_field.peak()
        self.unified_peak = np.array([peak_x, peak_y], dtype=np.float32)
        self.unified_field_max = float(total.max()) if total.size else 0.0
        self.unified_field_min = float(total.min()) if total.size else 0.0
        self.unified_gradient_mean = float(np.mean(grad_norms)) if grad_norms else 0.0

    @staticmethod
    def _target_is_valid(target: np.ndarray) -> bool:
        arr = np.asarray(target, dtype=np.float32)
        return bool(arr.shape == (2,) and np.all(np.isfinite(arr)) and np.all(arr >= 0.0) and np.all(arr <= 1.0))

    @staticmethod
    def _camera_index_from_gaze(target_xy: np.ndarray) -> int:
        x = _clamp(float(target_xy[0]), 0.0, 1.0)
        y = _clamp(float(target_xy[1]), 0.0, 1.0)
        if y >= 0.82:
            return 6 if x >= 0.5 else 5
        if x < 0.20:
            return 0
        if x < 0.40:
            return 1
        if x < 0.60:
            return 2
        if x < 0.80:
            return 3
        return 4

    def _select_embodied_gaze_target(self) -> np.ndarray | None:
        if (
            self._target_is_valid(self.gaze_target)
            and self.gaze_saliency_peak >= float(self.cfg.embodied_gaze_min_salience)
        ):
            return self.gaze_target.copy()
        if self._target_is_valid(self.unified_peak) and self.unified_field_max > 0.0:
            return self.unified_peak.copy()
        return None

    def _apply_embodied_gaze(self) -> None:
        if not self.cfg.embodied_gaze:
            return
        if self.t % max(1, int(self.cfg.embodied_gaze_every)) != 0:
            return

        target = self._select_embodied_gaze_target()
        if target is None:
            return

        idx = self._camera_index_from_gaze(target)
        name = camera_target.name_for_index(idx)
        rec = camera_target.write_target(
            name=name,
            index=idx,
            writer=self.cfg.embodied_gaze_writer,
            priority=int(self.cfg.embodied_gaze_priority),
            lease_s=float(self.cfg.embodied_gaze_lease_s),
        )

        self.embodied_gaze_writes += 1
        self.embodied_camera_index = int(rec["index"]) if rec.get("index") is not None else -1
        self.embodied_camera_name = str(rec.get("name") or "")
        self.embodied_gaze_last_target = target.astype(np.float32, copy=True)

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
        self._apply_stigmergic_entropy_gate()
        self._apply_immune_quorum(anomaly_positions)
        self._apply_foveated_gaze(anomaly_positions)
        self._apply_unified_field(anomaly_positions, stress)
        self._apply_embodied_gaze()
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
            "stig_field_max": float(self.stigmergic_field_max),
            "stig_reward_mean": float(self.stigmergic_reward_mean),
            "stig_reward_max": float(self.stigmergic_reward_max),
            "immune_danger_max": float(self.immune_danger_max),
            "immune_repair_max": float(self.immune_repair_max),
            "immune_signal_max": float(self.immune_signal_max),
            "immune_reward_mean": float(self.immune_reward_mean),
            "gaze_saliency_peak": float(self.gaze_saliency_peak),
            "gaze_saccades": float(self.gaze_saccades),
            "gaze_target_x": float(self.gaze_target[0]),
            "gaze_target_y": float(self.gaze_target[1]),
            "gaze_foveal_count": float(self.gaze_foveal_count),
            "unified_field_max": float(self.unified_field_max),
            "unified_field_min": float(self.unified_field_min),
            "unified_gradient_mean": float(self.unified_gradient_mean),
            "unified_peak_x": float(self.unified_peak[0]),
            "unified_peak_y": float(self.unified_peak[1]),
            "embodied_gaze_writes": float(self.embodied_gaze_writes),
            "embodied_camera_index": float(self.embodied_camera_index),
            "embodied_gaze_target_x": float(self.embodied_gaze_last_target[0]),
            "embodied_gaze_target_y": float(self.embodied_gaze_last_target[1]),
        }


def _print_stigmergic_glyph(sim: CrucibleSim) -> None:
    print("\033[H\033[J", end="")
    print(sim.stigmergic_task.glyph() or "(stigmergic field empty)")
    print(
        f"field max: {sim.stigmergic_field_max:.4f}  "
        f"reward mean: {sim.stigmergic_reward_mean:.4f}  "
        f"reward max: {sim.stigmergic_reward_max:.4f}"
    )


def _print_immune_glyph(sim: CrucibleSim) -> None:
    print("\033[H\033[J", end="")
    print(sim.immune_quorum.glyph() or "(immune quorum field empty)")
    print(
        f"danger max: {sim.immune_danger_max:.4f}  "
        f"repair max: {sim.immune_repair_max:.4f}  "
        f"signal max: {sim.immune_signal_max:.4f}  "
        f"reward mean: {sim.immune_reward_mean:.4f}"
    )


def _print_gaze_glyph(sim: CrucibleSim) -> None:
    print("\033[H\033[J", end="")
    print(sim.foveated_gaze.glyph("saliency") or "(foveated gaze field empty)")
    print(
        f"saliency peak: {sim.gaze_saliency_peak:.4f}  "
        f"saccades: {sim.gaze_saccades}  "
        f"target: ({sim.gaze_target[0]:.3f}, {sim.gaze_target[1]:.3f})  "
        f"foveal agents: {sim.gaze_foveal_count}"
    )


def _print_unified_glyph(sim: CrucibleSim) -> None:
    print("\033[H\033[J", end="")
    print(sim.unified_field.glyph("total") or "(unified field empty)")
    print(
        f"field min/max: {sim.unified_field_min:.4f}/{sim.unified_field_max:.4f}  "
        f"gradient mean: {sim.unified_gradient_mean:.4f}  "
        f"peak: ({sim.unified_peak[0]:.3f}, {sim.unified_peak[1]:.3f})  "
        f"eye: {sim.embodied_camera_index if sim.cfg.embodied_gaze else 'local'}"
    )


def run_headless(
    cfg: CrucibleConfig,
    ticks: int,
    show_glyph: bool = False,
    show_immune_glyph: bool = False,
    show_gaze_glyph: bool = False,
    show_unified_glyph: bool = False,
) -> int:
    sim = CrucibleSim(cfg)
    sim.trigger_onslaught()
    for _ in range(ticks):
        sim.step()
        if show_glyph and sim.t % max(1, cfg.glyph_every) == 0:
            _print_stigmergic_glyph(sim)
        if show_immune_glyph and sim.t % max(1, cfg.glyph_every) == 0:
            _print_immune_glyph(sim)
        if show_gaze_glyph and sim.t % max(1, cfg.glyph_every) == 0:
            _print_gaze_glyph(sim)
        if show_unified_glyph and sim.t % max(1, cfg.glyph_every) == 0:
            _print_unified_glyph(sim)
    print(
        "[CRUCIBLE] "
        f"ticks={ticks} load={sim.current_load_pct:.1f}% blocked={sim.total_blocked} "
        f"quarantined={sim.total_quarantined} packets_live={len(sim.packets)} "
        f"stig_field_max={sim.stigmergic_field_max:.4f} "
        f"stig_reward_mean={sim.stigmergic_reward_mean:.4f} "
        f"immune_danger_max={sim.immune_danger_max:.4f} "
        f"immune_repair_max={sim.immune_repair_max:.4f} "
        f"gaze_saccades={sim.gaze_saccades} "
        f"gaze_saliency_peak={sim.gaze_saliency_peak:.4f} "
        f"unified_field_max={sim.unified_field_max:.4f} "
        f"unified_gradient_mean={sim.unified_gradient_mean:.4f} "
        f"embodied_gaze_writes={sim.embodied_gaze_writes} "
        f"camera_index={sim.embodied_camera_index}"
    )
    return 0


def run_visual(
    cfg: CrucibleConfig,
    ticks: int,
    render_every: int,
    show_glyph: bool = False,
    show_immune_glyph: bool = False,
    show_gaze_glyph: bool = False,
    show_unified_glyph: bool = False,
) -> int:
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
        if show_glyph and sim.t % max(1, cfg.glyph_every) == 0:
            _print_stigmergic_glyph(sim)
        if show_immune_glyph and sim.t % max(1, cfg.glyph_every) == 0:
            _print_immune_glyph(sim)
        if show_gaze_glyph and sim.t % max(1, cfg.glyph_every) == 0:
            _print_gaze_glyph(sim)
        if show_unified_glyph and sim.t % max(1, cfg.glyph_every) == 0:
            _print_unified_glyph(sim)
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

        status_txt.set_text(
            f"tick {int(m['tick'])}/{ticks}  swimmers={len(sim.swimmers)}  "
            f"stig_field={m['stig_field_max']:.3f}  "
            f"immune_danger={m['immune_danger_max']:.3f}  immune_repair={m['immune_repair_max']:.3f}  "
            f"gaze={m['gaze_saliency_peak']:.3f}@({m['gaze_target_x']:.2f},{m['gaze_target_y']:.2f})  "
            f"unified={m['unified_field_max']:.3f}@({m['unified_peak_x']:.2f},{m['unified_peak_y']:.2f})  "
            f"eye={int(m['embodied_camera_index']) if cfg.embodied_gaze else 'local'}"
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
    ap.add_argument("--glyph", action="store_true", help="print the stigmergic field glyph every glyph interval")
    ap.add_argument("--immune-glyph", action="store_true", help="print the immune quorum composite glyph")
    ap.add_argument("--gaze-glyph", action="store_true", help="print the foveated gaze saliency glyph")
    ap.add_argument("--unified-glyph", action="store_true", help="print the unified field glyph")
    ap.add_argument(
        "--embodied-gaze",
        action="store_true",
        help="forward foveated/unified gaze into the canonical active camera target state",
    )
    ap.add_argument("--embodied-gaze-every", type=int, default=CrucibleConfig.embodied_gaze_every)
    ap.add_argument("--embodied-gaze-min-salience", type=float, default=0.05)
    ap.add_argument("--embodied-gaze-priority", type=int, default=CrucibleConfig.embodied_gaze_priority)
    ap.add_argument("--embodied-gaze-lease-s", type=float, default=CrucibleConfig.embodied_gaze_lease_s)
    ap.add_argument("--glyph-every", type=int, default=25)
    args = ap.parse_args()

    cfg = CrucibleConfig(
        agents=int(args.agents),
        seed=int(args.seed),
        glyph_every=int(args.glyph_every),
        embodied_gaze=bool(args.embodied_gaze),
        embodied_gaze_every=int(args.embodied_gaze_every),
        embodied_gaze_min_salience=float(args.embodied_gaze_min_salience),
        embodied_gaze_priority=int(args.embodied_gaze_priority),
        embodied_gaze_lease_s=float(args.embodied_gaze_lease_s),
    )
    if args.headless:
        return run_headless(
            cfg,
            int(args.ticks),
            bool(args.glyph),
            bool(args.immune_glyph),
            bool(args.gaze_glyph),
            bool(args.unified_glyph),
        )
    return run_visual(
        cfg,
        int(args.ticks),
        int(args.render_every),
        bool(args.glyph),
        bool(args.immune_glyph),
        bool(args.gaze_glyph),
        bool(args.unified_glyph),
    )


if __name__ == "__main__":
    raise SystemExit(main())
