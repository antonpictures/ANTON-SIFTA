"""
Event 131 — Five **scaffold** organs (entorhinal grid metaphor, global workspace,
active inference toy, glial LR scale, MHC-style self hash set).

**Truth label:** **SIMULATED** / **METAPHOR** — teaching kernels + JSON shapes;
not claims of biological fidelity or superintelligence.

**Dependencies:** ``numpy`` only (no ``scipy`` — softmax is stable numpy).

Primary literature (tournament spine):
  * Grid / MEC: Hafting *et al.* (2005) *Nature* [doi:10.1038/nature03721](https://doi.org/10.1038/nature03721)
  * GNW: Dehaene, Changeux (2011) *Physiology* [PMC3108466](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3108466/)
  * Active inference: Friston (2010) *Nat. Rev. Neurosci.* [PubMed 20231069](https://pubmed.ncbi.nlm.nih.gov/20231069/)
  * Astrocyte modulation (review): Volterra *et al.* (2014) *Nat. Rev. Neurosci.*
    [PubMed 24565288](https://pubmed.ncbi.nlm.nih.gov/24565288/)
  * MHC / self: Janeway's *Immunobiology* ( Garland / NCBI Bookshelf )

Kill-switch: ``SIFTA_SUPERINTELLIGENCE_ORGANS_DISABLE=1``.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from System.jsonl_file_lock import append_line_locked
from System.swarm_persistent_owner_history import state_dir

TRACE_NAME = "superintelligence_organs.jsonl"


def organ_trace_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / TRACE_NAME


def _disabled() -> bool:
    return os.environ.get("SIFTA_SUPERINTELLIGENCE_ORGANS_DISABLE", "").strip() == "1"


def _softmax(x: np.ndarray) -> np.ndarray:
    z = x - np.max(x)
    e = np.exp(z)
    return e / (np.sum(e) + 1e-12)


def _append_trace(row: Dict[str, Any], *, root: Optional[Path] = None) -> None:
    if _disabled():
        return
    row.setdefault("ts", time.time())
    row.setdefault("trace_id", str(uuid.uuid4()))
    append_line_locked(
        organ_trace_path(root),
        json.dumps(row, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


class EntorhinalGridNavigator:
    """Toroidal 2D integrator + coarse grid activation (not a full MEC model)."""

    def __init__(self, grid_size: int = 64, scale: float = 0.1, *, seed: int = 0):
        self.grid_size = int(grid_size)
        self.scale = float(scale)
        self.rng = np.random.default_rng(seed)
        self.grid_cells = np.zeros((self.grid_size, self.grid_size), dtype=np.float64)
        self.place_cells: Dict[str, np.ndarray] = {}
        self.velocity = np.zeros(2, dtype=np.float64)
        self.position = np.zeros(2, dtype=np.float64)

    def path_integrate(self, action_vector: np.ndarray) -> None:
        av = np.asarray(action_vector, dtype=np.float64).ravel()
        if av.size < 2:
            return
        self.velocity = av[:2] * self.scale
        self.position = np.mod(self.position + self.velocity, self.grid_size)

    def update_grid_cells(self) -> None:
        x, y = float(self.position[0]), float(self.position[1])
        phase = np.sin(2 * np.pi * (x + y) / max(1, self.grid_size))
        shift = int(np.clip(phase * 5, -4, 4))
        self.grid_cells = np.roll(self.grid_cells, shift, axis=(0, 1))

    def get_place_representation(self, state_id: str) -> np.ndarray:
        if state_id not in self.place_cells:
            self.place_cells[state_id] = self.rng.standard_normal(self.grid_size)
        return self.place_cells[state_id].copy()

    def navigate_to(self, target_state: str) -> np.ndarray:
        _ = self.get_place_representation(target_state)
        target_pos = self.rng.uniform(0, self.grid_size, size=2)
        direction = target_pos - self.position
        n = float(np.linalg.norm(direction)) + 1e-8
        return direction / n


class GlobalWorkspace:
    """Softmax competition + ignition threshold (GNW-style toy)."""

    def __init__(self, num_nodes: int = 12, broadcast_threshold: float = 0.65):
        self.num_nodes = int(num_nodes)
        self.workspace_activity = np.zeros(self.num_nodes, dtype=np.float64)
        self.broadcast_threshold = float(broadcast_threshold)

    def compete(self, node_activations: np.ndarray) -> int:
        v = np.asarray(node_activations, dtype=np.float64).ravel()
        if v.size != self.num_nodes:
            raise ValueError(f"expected {self.num_nodes} activations, got {v.size}")
        probs = _softmax(v)
        winner = int(np.argmax(probs))
        if float(probs[winner]) > self.broadcast_threshold:
            self.workspace_activity = np.zeros(self.num_nodes, dtype=np.float64)
            self.workspace_activity[winner] = 1.0
            return winner
        return -1

    def broadcast(self, content: Dict[str, Any]) -> Dict[str, Any]:
        bid = hashlib.sha256(f"{time.time()}|{uuid.uuid4()}".encode()).hexdigest()[:12]
        winner = int(np.argmax(self.workspace_activity)) if np.any(self.workspace_activity) else -1
        return {
            "broadcast_id": bid,
            "winner_node": winner,
            "content": content,
            "timestamp": time.time(),
            "conscious": winner >= 0,
        }


class ActiveInferenceEngine:
    """Tiny discrete belief vector + VFE-style scalar for policy scoring."""

    def __init__(self, state_dim: int = 64, *, seed: int = 0):
        self.state_dim = int(state_dim)
        self.rng = np.random.default_rng(seed)
        u = np.ones(self.state_dim, dtype=np.float64)
        self.beliefs = u / np.sum(u)
        self.prior = self.beliefs.copy()

    def compute_free_energy(self, observation: np.ndarray) -> float:
        o = np.asarray(observation, dtype=np.float64).ravel()
        if o.size != self.state_dim:
            raise ValueError("observation dim mismatch")
        o = np.clip(o, 1e-8, None)
        o = o / np.sum(o)
        b = np.clip(self.beliefs, 1e-12, None)
        p = np.clip(self.prior, 1e-12, None)
        kl = float(np.sum(b * (np.log(b) - np.log(p))))
        exp_ll = float(np.sum(b * np.log(o)))
        return float(kl - exp_ll)

    def update_beliefs(self, observation: np.ndarray, learning_rate: float = 0.1) -> None:
        o = np.asarray(observation, dtype=np.float64).ravel()
        if o.size != self.state_dim:
            raise ValueError("observation dim mismatch")
        o = np.clip(o, 0.0, None)
        o = o / (np.sum(o) + 1e-12)
        self.beliefs += float(learning_rate) * (o - self.beliefs)
        self.beliefs = np.clip(self.beliefs, 1e-12, None)
        self.beliefs /= np.sum(self.beliefs)

    def policy_selection(self, policies: List[np.ndarray]) -> int:
        if not policies:
            return -1
        efe_list: List[float] = []
        for pol in policies:
            pi = np.asarray(pol, dtype=np.float64).ravel()
            if pi.size != self.state_dim:
                raise ValueError("policy dim mismatch")
            predicted_obs = np.clip(pi * self.beliefs, 1e-12, None)
            predicted_obs = predicted_obs / np.sum(predicted_obs)
            efe_list.append(self.compute_free_energy(predicted_obs))
        return int(np.argmin(np.asarray(efe_list)))


class AstrocyticGlia:
    """Maps load + reward into a global LR multiplier (metaphorical heat)."""

    def __init__(self) -> None:
        self.metabolic_heat = 0.5
        self.caloric_cost = 0.0

    def update_metabolic_state(
        self, cpu_load: float, memory_usage: float, recent_reward: float
    ) -> None:
        load_factor = (float(cpu_load) + float(memory_usage)) / 2.0
        reward_factor = max(0.0, float(recent_reward)) * 0.3
        self.metabolic_heat = float(
            np.clip(0.3 + load_factor * 0.4 + reward_factor, 0.1, 0.95)
        )
        self.caloric_cost += load_factor * 0.05

    def modulate_learning_rate(self, base_lr: float) -> float:
        plasticity_factor = 0.7 + self.metabolic_heat * 0.6
        return float(base_lr) * float(plasticity_factor)

    def get_glial_state(self) -> Dict[str, Any]:
        return {
            "metabolic_heat": round(self.metabolic_heat, 3),
            "caloric_cost": round(self.caloric_cost, 2),
            "plasticity_multiplier": round(0.7 + self.metabolic_heat * 0.6, 3),
        }


class MHCImmuneSystem:
    """Self = set of sha256(payload) hex digests (full 64-char keys)."""

    def __init__(self, mhc_threshold: float = 0.75) -> None:
        self.self_hashes: set[str] = set()
        self.mhc_threshold = float(mhc_threshold)

    def register_self(self, signature: str) -> None:
        h = hashlib.sha256(signature.encode("utf-8")).hexdigest()
        self.self_hashes.add(h)

    def compute_binding_affinity(self, payload: str) -> float:
        ph = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if ph in self.self_hashes:
            return 0.98
        return 0.25

    def is_self(self, payload: str) -> bool:
        return self.compute_binding_affinity(payload) > self.mhc_threshold

    def immune_response(self, payload: str) -> Dict[str, Any]:
        aff = self.compute_binding_affinity(payload)
        if aff > self.mhc_threshold:
            return {"decision": "ALLOW", "affinity": aff}
        return {
            "decision": "QUARANTINE",
            "reason": "Non-Self pattern detected",
            "affinity": aff,
        }


def run_demo_trace(*, root: Optional[Path] = None) -> Dict[str, Any]:
    """One bundled receipt for dashboards / tests."""
    grid = EntorhinalGridNavigator(seed=1)
    grid.path_integrate(np.array([1.0, 0.5]))
    grid.update_grid_cells()
    gw = GlobalWorkspace(num_nodes=4, broadcast_threshold=0.35)
    w = gw.compete(np.array([0.2, 1.1, 0.4, 0.3]))
    br = gw.broadcast({"demo": True}) if w >= 0 else {"broadcast_id": None}
    ai = ActiveInferenceEngine(state_dim=8, seed=2)
    o = np.ones(8) / 8.0
    fe = ai.compute_free_energy(o)
    glia = AstrocyticGlia()
    glia.update_metabolic_state(0.6, 0.5, 0.2)
    mhc = MHCImmuneSystem()
    mhc.register_self("trusted_seed_phrase")
    immune = mhc.immune_response("trusted_seed_phrase")
    summary = {
        "kind": "SUPERINTELLIGENCE_ORGANS_DEMO",
        "grid_position": grid.position.tolist(),
        "workspace_winner": w,
        "broadcast": br,
        "free_energy_sample": round(fe, 6),
        "glia": glia.get_glial_state(),
        "immune": immune,
    }
    _append_trace(summary, root=root)
    return summary


__all__ = [
    "ActiveInferenceEngine",
    "AstrocyticGlia",
    "EntorhinalGridNavigator",
    "GlobalWorkspace",
    "MHCImmuneSystem",
    "organ_trace_path",
    "run_demo_trace",
]
