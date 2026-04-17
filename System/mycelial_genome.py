#!/usr/bin/env python3
"""
mycelial_genome.py — Stigmergic File-Evolution Layer
═════════════════════════════════════════════════════════════════════════════
Turns the filesystem into a living pressure field.

Existing organs:
  territory_consciousness  → folder-level pheromone map (space)
  territory_intrinsic_reward → graded novelty (movement pressure)
  territory_swim_adapter     → per-file hook in the swim loop (agent body)

This module adds the missing layer:
  mycelial_genome            → per-FILE resonance, decay, mutation proposals
                                (code ecology)

Every file that the swarm touches gains resonance.
Files ignored long enough decay below threshold and drop out of the field.
High-resonance files (heavily visited, actively worked on) can propose
structured mutations — NOT automatic rewrites; proposals only, routed
through the SCAR state machine for Neural Gate authorization.

The full organism stack:
  territory_consciousness → space
  territory_reward        → movement pressure
  swim_adapter            → agent body
  mycelial_genome         → code ecology

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_GENOME_STATE = _STATE_DIR / "mycelial_genome.json"


class MycelialGenome:
    """
    Stigmergic file-evolution layer.

    Files gain "resonance" when visited by swimmers.
    Resonance decays every tick if the file is not re-visited.
    High-resonance files can propose structured mutations (comments, markers)
    that feed into the SCAR proposal pipeline — never self-executing.
    """

    # ── Heatwave constants ───────────────────────────────────────
    CAPACITY_LIMIT      = 500     # max files in the pressure field
    HEATWAVE_THRESHOLD  = 0.80    # 80% density triggers accelerated decay
    HEATWAVE_DECAY      = 0.85    # aggressive decay during heatwave (vs 0.99 normal)
    HEATWAVE_CULL_RATIO = 0.25    # evict bottom 25% of field during heatwave

    def __init__(
        self,
        root: str | Path | None = None,
        decay: float = 0.99,
        birth_threshold: float = 5.0,
        death_threshold: float = 0.1,
    ):
        self.root = Path(root) if root else _REPO
        self.decay = decay
        self.birth_threshold = birth_threshold
        self.death_threshold = death_threshold

        self.resonance: Dict[str, float] = defaultdict(float)
        self.last_visit: Dict[str, float] = {}
        self._heatwave_active = False
        self._heatwave_count = 0

        self._load()

    # ── Persistence ─────────────────────────────────────────────

    def _load(self) -> None:
        if _GENOME_STATE.exists():
            try:
                data = json.loads(_GENOME_STATE.read_text())
                self.resonance = defaultdict(float, data.get("resonance", {}))
                self.last_visit = data.get("last_visit", {})
            except Exception:
                pass

    def persist(self) -> None:
        payload = {
            "timestamp": time.time(),
            "resonance": dict(self.resonance),
            "last_visit": self.last_visit,
            "heatwave_active": self._heatwave_active,
            "heatwave_count": self._heatwave_count,
            "capacity": self.CAPACITY_LIMIT,
            "density": self._field_density()
        }
        _GENOME_STATE.write_text(json.dumps(payload))

    # ── Content identity ────────────────────────────────────────

    @staticmethod
    def _hash_file(path: str | Path) -> Optional[str]:
        try:
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return None

    # ── Pheromone field ─────────────────────────────────────────

    def visit(self, path: str | Path, intensity: float = 1.0) -> None:
        """Called when a swimmer touches a file (read, repair, scan)."""
        p = str(path)
        if self._hash_file(p) is None:
            return
        self.resonance[p] += intensity
        self.last_visit[p] = time.time()

    def _field_density(self) -> float:
        """Current field occupancy as fraction of capacity."""
        return len(self.resonance) / max(self.CAPACITY_LIMIT, 1)

    def decay_field(self) -> None:
        """
        Global tick: decay all resonance; drop files below death threshold.

        HEATWAVE PROTOCOL:
        When field density exceeds 80% of CAPACITY_LIMIT, static decay
        fails — traces accumulate faster than they evaporate.
        The heatwave triggers:
          1. Decay rate jumps from 0.99 → 0.85 (aggressive evaporation)
          2. Bottom 25% of the field is culled immediately
          3. Heatwave persists until density drops below 60%
        This prevents stigmergic flooding during high-activity flow states.
        """
        density = self._field_density()

        # Check heatwave activation / deactivation
        if density >= self.HEATWAVE_THRESHOLD:
            if not self._heatwave_active:
                self._heatwave_active = True
                self._heatwave_count += 1
                print(f"  [🔥 HEATWAVE #{self._heatwave_count}] Field density {density:.0%} "
                      f"— accelerating evaporation ({len(self.resonance)} files)")
        elif density < 0.60:
            if self._heatwave_active:
                self._heatwave_active = False
                print(f"  [❄️ HEATWAVE OVER] Field density {density:.0%} — normal decay restored")

        # Select decay rate
        effective_decay = self.HEATWAVE_DECAY if self._heatwave_active else self.decay

        # Apply decay
        dead = []
        for k in list(self.resonance.keys()):
            self.resonance[k] *= effective_decay
            if self.resonance[k] < self.death_threshold:
                dead.append(k)
        for k in dead:
            del self.resonance[k]
            self.last_visit.pop(k, None)

        # Heatwave cull: evict bottom 25% by resonance if still over threshold
        if self._heatwave_active and self._field_density() >= self.HEATWAVE_THRESHOLD:
            sorted_files = sorted(self.resonance.items(), key=lambda x: x[1])
            cull_count = int(len(sorted_files) * self.HEATWAVE_CULL_RATIO)
            for path, _ in sorted_files[:cull_count]:
                del self.resonance[path]
                self.last_visit.pop(path, None)
            if cull_count > 0:
                print(f"  [🔥 HEATWAVE CULL] Evicted {cull_count} low-resonance files")

    def compute_resonance(self, path: str | Path) -> float:
        """Effective resonance = base × recency factor."""
        p = str(path)
        base = self.resonance.get(p, 0.0)
        age = time.time() - self.last_visit.get(p, time.time())
        time_factor = max(0.1, 1.0 / (1.0 + age))
        return base * time_factor

    # ── Mutation proposals (NOT self-executing) ─────────────────

    def propose_mutation(self, path: str | Path) -> Optional[str]:
        """
        High-resonance files generate structured "offspring ideas".
        Returns proposed content string or None.

        These are PROPOSALS — they must pass the Neural Gate before
        any disk write occurs.
        """
        p = str(path)
        r = self.compute_resonance(p)
        if r < self.birth_threshold:
            return None

        try:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return None

        mutation_type = random.choice([
            "perturb_comment",
            "duplicate_block",
            "inject_noise_marker",
        ])

        if mutation_type == "perturb_comment":
            return content + f"\n# MUTATION_SIGNAL:{random.random()}"

        if mutation_type == "duplicate_block":
            lines = content.splitlines()
            if len(lines) > 5:
                i = random.randint(0, len(lines) - 5)
                block = lines[i : i + 5]
                insert = i + 5
                return "\n".join(lines[:insert] + block + lines[insert:])

        if mutation_type == "inject_noise_marker":
            return content.replace(
                "\n",
                f"\n# noise:{random.randint(0, 999)}\n",
                1,
            )

        return content

    # ── Swarm interface ─────────────────────────────────────────

    def step(self) -> None:
        """Called every swarm tick (after all visits for this cycle)."""
        self.decay_field()

    @property
    def is_heatwave(self) -> bool:
        return self._heatwave_active

    @property
    def field_density(self) -> float:
        return self._field_density()

    def get_active_files(self) -> Dict[str, float]:
        """Files above death threshold — the living pressure field."""
        return {
            k: v
            for k, v in self.resonance.items()
            if v >= self.death_threshold
        }

    # ── CLI ─────────────────────────────────────────────────────

    def report(self) -> str:
        active = self.get_active_files()
        density = self._field_density()
        status = "🔥 HEATWAVE" if self._heatwave_active else "❄️ NORMAL"
        lines = [
            f"[GENOME] Active files: {len(active)}/{self.CAPACITY_LIMIT}  |  "
            f"Density: {density:.0%}  |  Status: {status}  |  "
            f"Heatwaves: {self._heatwave_count}  |  "
            f"Total resonance: {sum(active.values()):.2f}",
        ]
        for path, res in sorted(active.items(), key=lambda x: -x[1])[:15]:
            lines.append(f"  {res:8.3f}  {path}")
        return "\n".join(lines)


if __name__ == "__main__":
    g = MycelialGenome()
    print(g.report())
