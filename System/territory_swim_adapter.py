#!/usr/bin/env python3
"""
territory_swim_adapter.py — SWIM LOOP INTEGRATION LAYER
=========================================================
Bridges territory_consciousness + territory_intrinsic_reward
+ interference_layer + mycelial_genome + mutation_governor INTO the live swim loop (repair.py).

This is not a standalone module. It is CALLED by the swim loop.

Lifecycle:
  BEFORE SWIM:  adapter.before_swim(state, target_dir)
                → patrols territory, snapshots state, starts wavefield

  PER FILE:     adapter.on_file(state, file_path, changed)
                → deposits pheromone, emits interference wave, computes reward
                → genome.visit() — file gains resonance in pressure field

  AFTER SWIM:   adapter.after_swim(state, fixed_count)
                → genome.step() — decay, persist; mesh interference report

Mutation path: genome.propose_mutation → MutationGovernor.allow → Kernel.propose (SCAR) → Governor.commit
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_ADAPTER_STATE = _STATE_DIR / "territory_swim_state.json"

# ─── DECAY / REWARD CONSTANTS ──────────────────────────────────────────────────

PHEROMONE_DEPOSIT  = 0.15     # Pheromone dropped per file visited
PHEROMONE_REPAIR   = 0.40     # Extra pheromone for a REPAIRED file
DECAY_FACTOR       = 0.997    # Per-step pheromone decay
BETA_START         = 1.0
BETA_MIN           = 0.05
BETA_ANNEAL        = 0.998

# System-zone dampening (agent can't farm novelty from its own logs)
SYSTEM_PREFIXES = {
    ".sifta_state", "System", "__pycache__", ".git", "node_modules", "proposals"
}
SYSTEM_DAMPEN = 0.10


# ─── WELFORD NORMALIZER ────────────────────────────────────────────────────────

class _Normalizer:
    __slots__ = ("count", "mean", "m2", "beta")

    def __init__(self):
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0
        self.beta = BETA_START

    def update(self, x: float):
        self.count += 1
        d = x - self.mean
        self.mean += d / self.count
        d2 = x - self.mean
        self.m2 += d * d2

    @property
    def std(self) -> float:
        return max(math.sqrt(self.m2 / max(self.count - 1, 1)), 1e-8)

    def normalize(self, x: float) -> float:
        return (x - self.mean) / self.std

    def scale(self, x: float) -> float:
        self.update(x)
        return self.beta * self.normalize(x)

    def anneal(self):
        self.beta = max(BETA_MIN, self.beta * BETA_ANNEAL)

    def to_dict(self) -> dict:
        return {"count": self.count, "mean": self.mean, "m2": self.m2, "beta": self.beta}

    def from_dict(self, d: dict):
        self.count = d.get("count", 0)
        self.mean = d.get("mean", 0.0)
        self.m2 = d.get("m2", 0.0)
        self.beta = d.get("beta", BETA_START)


# ─── THE ADAPTER ───────────────────────────────────────────────────────────────

class TerritorySwimAdapter:
    """
    Bridges territory consciousness + intrinsic reward
    into the live swim loop.

    NOT standalone. Called by repair.py at three points:
      1. before_swim()  — snapshot territory before repair
      2. on_file()      — per-file pheromone + reward
      3. after_swim()   — summary, anneal, persist
    """

    def __init__(self):
        self._pheromone: Dict[str, float] = {}   # zone → intensity
        self._zone_hashes: Dict[str, str] = {}   # zone → content hash
        self._snap_before: Dict[str, str] = {}   # pre-swim hashes
        self._normalizer = _Normalizer()
        self._step_rewards: list = []
        self._zones_visited: set = set()
        self._step = 0
        self._genome = None
        self._governor = None
        try:
            from System.mycelial_genome import MycelialGenome
            self._genome = MycelialGenome()
        except Exception:
            pass
        try:
            from System.mutation_governor import MutationGovernor
            self._governor = MutationGovernor()
        except Exception:
            pass
        self._load()

    # ── 1. BEFORE SWIM ────────────────────────────────────────────────────

    def before_swim(self, state: dict, target_dir: str):
        """
        Called once at the start of swim_and_repair.
        Snapshots the territory so we can measure real delta after.
        """
        self._snap_before = dict(self._zone_hashes)
        self._step_rewards = []
        self._zones_visited = set()
        self._step = 0

        # Decay all pheromone (time passed since last swim)
        for z in list(self._pheromone.keys()):
            self._pheromone[z] *= DECAY_FACTOR
            if self._pheromone[z] < 1e-6:
                del self._pheromone[z]

        agent_id = state.get("id", "?")
        n_zones = len(self._pheromone)

        # Start interference wavefield (background propagation)
        try:
            from interference_layer import start_interference_background
            start_interference_background()
        except Exception:
            pass

        print(f"  [🗺️ TERRITORY] Adapter armed for {agent_id}. "
              f"Tracking {n_zones} pheromone zones. Wavefield active.")

    # ── 2. PER-FILE STEP ──────────────────────────────────────────────────

    def on_file(self, state: dict, file_path: str, was_changed: bool) -> float:
        """
        Called for EVERY file the swimmer touches.
        Returns the intrinsic reward for this step.

        This is the temporal fusion point:
          - territory consciousness updates its map
          - intrinsic reward computes the signal
          - pheromone is deposited
          - all in one atomic step inside the swim loop
        """
        self._step += 1

        # Compute zone from file path
        try:
            rel = str(Path(file_path).relative_to(_REPO))
        except ValueError:
            rel = file_path
        zone = str(Path(rel).parent)

        self._zones_visited.add(zone)

        # ── PHEROMONE DEPOSIT ─────────────────────────────────────────
        deposit = PHEROMONE_REPAIR if was_changed else PHEROMONE_DEPOSIT
        self._pheromone[zone] = min(1.0, self._pheromone.get(zone, 0.0) + deposit)

        # ── CONTENT HASH (for graded novelty) ─────────────────────────
        try:
            content = Path(file_path).read_bytes()
            new_hash = hashlib.md5(content).hexdigest()[:12]
        except Exception:
            new_hash = ""

        old_hash = self._zone_hashes.get(rel, "")
        self._zone_hashes[rel] = new_hash

        # ── GRADED NOVELTY ────────────────────────────────────────────
        novelty = 0.0
        if old_hash and old_hash != new_hash:
            # File actually changed — graded by whether it was agent-driven
            is_system = any(zone.startswith(p) for p in SYSTEM_PREFIXES)
            dampen = SYSTEM_DAMPEN if is_system else 1.0
            novelty = dampen * 1.0
        elif not old_hash:
            # First time seeing this file
            novelty = 0.3

        # ── EXPLORATION BONUS ─────────────────────────────────────────
        pheromone = self._pheromone.get(zone, 0.0)
        exploration = 0.0
        if pheromone < 0.3:
            exploration = 0.5 * (1.0 - pheromone / 0.3)

        # ── MYCELIAL GENOME — file-level resonance deposit ─────────────
        if self._genome:
            try:
                intensity = 1.5 if was_changed else 1.0
                self._genome.visit(file_path, intensity=intensity)

                # High-resonance files propose mutations to the Neural Gate.
                # These are NOT applied directly; they must pass SCAR consensus.
                mutation = self._genome.propose_mutation(file_path)
                if mutation:
                    if self._governor and not self._governor.allow(file_path, mutation):
                        print(
                            f"  [🧬 GOVERNOR] Mutation blocked "
                            f"{os.path.basename(file_path)} ({self._governor.last_reject_reason})"
                        )
                    else:
                        import sys
                        _kernel_path = str(_REPO / "Kernel")
                        if _kernel_path not in sys.path:
                            sys.path.insert(0, _kernel_path)
                        import scar_kernel
                        k = scar_kernel.Kernel()
                        sid = k.propose(target=file_path, content=mutation)
                        if self._governor:
                            self._governor.commit(file_path, mutation)
                        print(
                            f"  [🧬 GENOME] Mutation proposed for "
                            f"{os.path.basename(file_path)} (ScarID: {sid[:8]})"
                        )
            except Exception:
                # Genome is a passive observer; Kernel/Governor fail gracefully
                pass

        # ── INTERFERENCE WAVE EMISSION ─────────────────────────────────
        # Every file touch emits a wave into the shared interference field.
        # Repair = REPAIR frequency. Scout = SCOUT frequency.
        # Multi-agent coupling emerges from wave superposition.
        try:
            from interference_layer import emit_swim_wave
            intent = "REPAIR" if was_changed else "SCOUT"
            strength = 0.8 if was_changed else 0.3
            emit_swim_wave(state, zone, intent, strength)
        except Exception:
            pass

        # ── RAW → NORMALIZED → SCALED ────────────────────────────────
        raw = novelty + exploration
        scaled = self._normalizer.scale(raw) if raw > 0 else 0.0

        self._step_rewards.append(scaled)
        return scaled

    # ── 3. AFTER SWIM ─────────────────────────────────────────────────────

    def after_swim(self, state: dict, fixed_count: int) -> dict:
        """
        Called once at the end of swim_and_repair.
        Anneals β, computes summary, persists state.
        """
        self._normalizer.anneal()

        total_reward = sum(self._step_rewards)
        mean_reward = total_reward / max(len(self._step_rewards), 1)

        report = {
            "steps": self._step,
            "zones_visited": len(self._zones_visited),
            "total_intrinsic_reward": round(total_reward, 4),
            "mean_intrinsic_reward": round(mean_reward, 4),
            "beta": round(self._normalizer.beta, 4),
            "pheromone_zones": len(self._pheromone),
            "files_repaired": fixed_count,
        }

        # ── MYCELIAL GENOME — decay tick + persist ──────────────────
        if self._genome:
            try:
                self._genome.step()
                self._genome.persist()
                active = self._genome.get_active_files()
                report["genome_active_files"] = len(active)
                report["genome_total_resonance"] = round(sum(active.values()), 2)
            except Exception:
                pass

        self._save()

        agent_id = state.get("id", "?")
        print(f"  [🗺️ TERRITORY] Swim complete. {self._step} steps, "
              f"{len(self._zones_visited)} zones, "
              f"intrinsic_r={total_reward:.4f}, β={self._normalizer.beta:.4f}")

        # ── INTERFERENCE MESH REPORT ──────────────────────────────────
        try:
            from interference_layer import get_interference_field
            mesh = get_interference_field().mesh_report()
            coupling = mesh.get("global_coupling", 0)
            waves = mesh.get("total_waves", 0)
            territories = mesh.get("active_territories", 0)
            if waves > 0:
                print(f"  [🌊 INTERFERENCE] Global coupling: {coupling:.4f} | "
                      f"{waves} waves across {territories} territories")
            report["global_coupling"] = coupling
            report["active_waves"] = waves
        except Exception:
            pass

        return report

    # ── PERSISTENCE ───────────────────────────────────────────────────────

    def _save(self):
        data = {
            "pheromone": dict(self._pheromone),
            "zone_hashes": dict(self._zone_hashes),
            "normalizer": self._normalizer.to_dict(),
        }
        try:
            _ADAPTER_STATE.write_text(json.dumps(data, indent=1))
        except Exception:
            pass

    def _load(self):
        try:
            if _ADAPTER_STATE.exists():
                data = json.loads(_ADAPTER_STATE.read_text())
                self._pheromone = data.get("pheromone", {})
                self._zone_hashes = data.get("zone_hashes", {})
                self._normalizer.from_dict(data.get("normalizer", {}))
        except Exception:
            pass


# ─── SINGLETON ──────────────────────────────────────────────────────────────────
# One adapter per process. Persisted across swims.

_ADAPTER: Optional[TerritorySwimAdapter] = None

def get_adapter() -> TerritorySwimAdapter:
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = TerritorySwimAdapter()
    return _ADAPTER
