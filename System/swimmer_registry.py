#!/usr/bin/env python3
"""
System/swimmer_registry.py — Swimmer Registry & Health Monitor
══════════════════════════════════════════════════════════════════════════════
Central registry for all software swimmers in Alice's body.

A "swimmer" is any autonomous software agent/process that performs work
on behalf of the Swarm OS. Each swimmer has:
  - swimmer_id:       unique identifier
  - role:             what it does (inference, memory, monitoring, etc.)
  - ollama_model:     which LLM it uses (from swimmer_ollama_assignments.json)
  - last_pheromone_ts: last time it signaled it was alive
  - max_idle_s:       max seconds of silence before the watchdog marks it dead
  - app_context:      which application hosts it
  - status:           ALIVE / DORMANT / DEAD

This module satisfies the swarm_integrity_watchdog.py contract:
  swimmer_registry.jsonl must contain JSONL lines with at minimum:
    {"swimmer_id": "...", "last_pheromone_ts": <float>, "max_idle_s": <float>}

Biology anchor:
  - Bonabeau, Dorigo & Theraulaz — Swarm Intelligence (OUP 1999) — agent registry
  - Reynolds — "Flocks, herds and schools" SIGGRAPH '87 — boid identity
  - CP2F DYOR §§1-3 (stigmergy + quorum + chemotaxis)

Architect policy (2026-04-18):
  Swimmers are SOFTWARE agents on DISK. Not nanobots. Not molecules.
  Each swimmer uses gemma4:latest by default. Alice can override per-swimmer
  via swimmer_ollama_assignments.json.
══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_REGISTRY = _STATE / "swimmer_registry.jsonl"

# Import inference defaults for model resolution
try:
    from System.sifta_inference_defaults import resolve_ollama_model, get_default_ollama_model
except ImportError:
    def resolve_ollama_model(**kw): return "gemma4:latest"
    def get_default_ollama_model(): return "gemma4:latest"


class SwimmerStatus(str, Enum):
    ALIVE = "ALIVE"
    DORMANT = "DORMANT"
    DEAD = "DEAD"


class SwimmerRole(str, Enum):
    """Functional roles a swimmer can occupy in Alice's body."""
    INFERENCE = "INFERENCE"          # Runs Ollama queries
    MEMORY = "MEMORY"                # Memory bus / replay
    MONITORING = "MONITORING"        # Watchdog / immune / sentinel
    UI = "UI"                        # Desktop GUI widget
    NETWORK = "NETWORK"             # Cross-node relay / mesh
    CREATIVE = "CREATIVE"            # Writer / symphony / arena
    ECONOMIC = "ECONOMIC"            # STGM ledger / mining
    AUTONOMIC = "AUTONOMIC"          # Brainstem / sleep / circadian


@dataclass
class Swimmer:
    """A single registered software swimmer."""
    swimmer_id: str
    role: SwimmerRole
    app_context: str
    ollama_model: str
    max_idle_s: float = 7200.0       # 2 hours default max silence
    last_pheromone_ts: float = field(default_factory=time.time)
    status: SwimmerStatus = SwimmerStatus.ALIVE
    registered_ts: float = field(default_factory=time.time)
    heartbeat_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "swimmer_id": self.swimmer_id,
            "role": self.role.value,
            "app_context": self.app_context,
            "ollama_model": self.ollama_model,
            "max_idle_s": self.max_idle_s,
            "last_pheromone_ts": self.last_pheromone_ts,
            "status": self.status.value,
            "registered_ts": self.registered_ts,
            "heartbeat_count": self.heartbeat_count,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Swimmer:
        return cls(
            swimmer_id=str(d["swimmer_id"]),
            role=SwimmerRole(d.get("role", "INFERENCE")),
            app_context=str(d.get("app_context", "unknown")),
            ollama_model=str(d.get("ollama_model", get_default_ollama_model())),
            max_idle_s=float(d.get("max_idle_s", 7200.0)),
            last_pheromone_ts=float(d.get("last_pheromone_ts", 0)),
            status=SwimmerStatus(d.get("status", "ALIVE")),
            registered_ts=float(d.get("registered_ts", 0)),
            heartbeat_count=int(d.get("heartbeat_count", 0)),
        )


class SwimmerRegistry:
    """
    Central registry for all swimmers.

    Operations:
      register(...)      — add a new swimmer
      heartbeat(sid)     — update pheromone timestamp (swimmer signals it's alive)
      health_check()     — classify all swimmers as ALIVE / DORMANT / DEAD
      assign_model(sid, model) — Alice assigns a specific LLM to a swimmer
      list_swimmers()    — return all registered swimmers
      cull_dead()        — remove DEAD swimmers from the registry
    """

    def __init__(self, registry_path: Path = _REGISTRY):
        self._path = registry_path
        self._swimmers: Dict[str, Swimmer] = {}
        self._load()

    def _load(self) -> None:
        self._swimmers.clear()
        if not self._path.exists():
            return
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                sw = Swimmer.from_dict(d)
                self._swimmers[sw.swimmer_id] = sw
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(sw.to_dict()) for sw in self._swimmers.values()]
        self._path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")

    def register(
        self,
        swimmer_id: str,
        role: SwimmerRole,
        app_context: str,
        ollama_model: Optional[str] = None,
        max_idle_s: float = 7200.0,
    ) -> Swimmer:
        """Register a new swimmer or update an existing one."""
        model = ollama_model or resolve_ollama_model(
            swimmer_id=swimmer_id, app_context=app_context
        )
        now = time.time()
        if swimmer_id in self._swimmers:
            sw = self._swimmers[swimmer_id]
            sw.role = role
            sw.app_context = app_context
            sw.ollama_model = model
            sw.max_idle_s = max_idle_s
            sw.last_pheromone_ts = now
            sw.status = SwimmerStatus.ALIVE
            sw.heartbeat_count += 1
        else:
            sw = Swimmer(
                swimmer_id=swimmer_id,
                role=role,
                app_context=app_context,
                ollama_model=model,
                max_idle_s=max_idle_s,
                last_pheromone_ts=now,
                registered_ts=now,
            )
            self._swimmers[swimmer_id] = sw
        self._persist()
        return sw

    def heartbeat(self, swimmer_id: str) -> Optional[Swimmer]:
        """Swimmer signals it's alive. Updates pheromone timestamp."""
        if swimmer_id not in self._swimmers:
            return None
        sw = self._swimmers[swimmer_id]
        sw.last_pheromone_ts = time.time()
        sw.heartbeat_count += 1
        sw.status = SwimmerStatus.ALIVE
        self._persist()
        return sw

    def health_check(self) -> Dict[str, List[Swimmer]]:
        """Classify all swimmers by health status."""
        now = time.time()
        alive, dormant, dead = [], [], []
        for sw in self._swimmers.values():
            age = now - sw.last_pheromone_ts
            if age > sw.max_idle_s:
                sw.status = SwimmerStatus.DEAD
                dead.append(sw)
            elif age > sw.max_idle_s * 0.5:
                sw.status = SwimmerStatus.DORMANT
                dormant.append(sw)
            else:
                sw.status = SwimmerStatus.ALIVE
                alive.append(sw)
        self._persist()
        return {"alive": alive, "dormant": dormant, "dead": dead}

    def assign_model(self, swimmer_id: str, model: str) -> Optional[Swimmer]:
        """Alice assigns a specific LLM to a swimmer."""
        if swimmer_id not in self._swimmers:
            return None
        self._swimmers[swimmer_id].ollama_model = model
        self._persist()
        return self._swimmers[swimmer_id]

    def list_swimmers(self) -> List[Swimmer]:
        return list(self._swimmers.values())

    def cull_dead(self) -> List[str]:
        """Remove DEAD swimmers from registry. Returns culled IDs."""
        culled = [sid for sid, sw in self._swimmers.items()
                  if sw.status == SwimmerStatus.DEAD]
        for sid in culled:
            del self._swimmers[sid]
        if culled:
            self._persist()
        return culled

    def get(self, swimmer_id: str) -> Optional[Swimmer]:
        return self._swimmers.get(swimmer_id)

    @property
    def count(self) -> int:
        return len(self._swimmers)


def seed_default_swimmers() -> SwimmerRegistry:
    """
    Seed the registry with Alice's known organ swimmers.
    Called once to bootstrap — safe to re-call (updates existing).
    """
    reg = SwimmerRegistry()
    default_model = get_default_ollama_model()

    # Alice's core swimmers — mapped from real Application/System files
    swimmers = [
        ("sw_swarm_chat",        SwimmerRole.INFERENCE, "swarm_chat",              default_model, 7200),
        ("sw_writer_widget",     SwimmerRole.CREATIVE,  "writer_widget",           default_model, 7200),
        ("sw_pheromone_symphony",SwimmerRole.CREATIVE,  "pheromone_symphony",      default_model, 7200),
        ("sw_desktop_gui",       SwimmerRole.UI,        "desktop_gui",             default_model, 7200),
        ("sw_cognitive_gci",     SwimmerRole.INFERENCE, "global_cognitive_interface", default_model, 7200),
        ("sw_brainstem",         SwimmerRole.AUTONOMIC, "brainstem",               default_model, 3600),
        ("sw_watchdog",          SwimmerRole.MONITORING,"watchdog",                default_model, 3600),
        ("sw_immune_array",      SwimmerRole.MONITORING,"immune_array",            default_model, 3600),
        ("sw_memory_bus",        SwimmerRole.MEMORY,    "stigmergic_memory_bus",   default_model, 7200),
        ("sw_inference_router",  SwimmerRole.NETWORK,   "inference_router",        default_model, 7200),
        ("sw_chat_relay",        SwimmerRole.NETWORK,   "swarm_chat_relay",        default_model, 7200),
        ("sw_serotonin_gov",     SwimmerRole.AUTONOMIC, "serotonin_homeostasis",   default_model, 3600),
        ("sw_dopamine_ou",       SwimmerRole.AUTONOMIC, "dopamine_ou_engine",      default_model, 3600),
        ("sw_log_rotation",      SwimmerRole.MONITORING,"log_rotation",            default_model, 7200),
        ("sw_broadcaster",       SwimmerRole.CREATIVE,  "broadcaster",             default_model, 7200),
    ]

    for sid, role, app_ctx, model, max_idle in swimmers:
        reg.register(sid, role, app_ctx, ollama_model=model, max_idle_s=max_idle)

    return reg


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    reg = seed_default_swimmers()
    health = reg.health_check()

    print("\n=== SWIMMER REGISTRY (Alice's Body Map) ===\n")
    print(f"  Total swimmers: {reg.count}")
    print(f"  Alive:   {len(health['alive'])}")
    print(f"  Dormant: {len(health['dormant'])}")
    print(f"  Dead:    {len(health['dead'])}")
    print()

    for sw in reg.list_swimmers():
        icon = {"ALIVE": "🟢", "DORMANT": "🟡", "DEAD": "🔴"}[sw.status.value]
        age = time.time() - sw.last_pheromone_ts
        print(f"  {icon} {sw.swimmer_id:<25} [{sw.role.value:<12}] "
              f"model={sw.ollama_model:<20} age={age:.0f}s  ctx={sw.app_context}")

    print()
    sys.exit(0)
