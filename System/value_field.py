#!/usr/bin/env python3
"""
value_field.py — SIFTA Value Routing Field (VRF)
=================================================
SWARM GPT + Architect — April 2026

Agents do not send messages. They emit VALUE GRADIENTS.

The Value Field is a spatial economic map across the entire repo.
Each territory accumulates pressure from:
  - BLEEDING scars (urgency)
  - Bounty deposits (economic demand)  
  - Reputation trust of requesting agents
  - Time decay (stale demands evaporate)

Agents "smell" the field and follow the steepest gradient
toward the highest-value work. This replaces centralized
task assignment with emergent economic coordination.

Subject to Irreducible Cost: reading the field is not free.
"""

from __future__ import annotations

import json
import math
import os
import time
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ─── PATHS ─────────────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_FIELD_PATH = _STATE_DIR / "value_field.jsonl"
_STATE_DIR.mkdir(parents=True, exist_ok=True)

# ─── CONSTANTS ─────────────────────────────────────────────────────────────────
FIELD_DECAY_HALF_LIFE_H = 6.0     # Demands lose half their pressure every 6 hours
FIELD_DECAY_K = math.log(2) / FIELD_DECAY_HALF_LIFE_H
MIN_PRESSURE = 0.01               # Below this, demand is considered evaporated
MAX_BOUNTY = 100.0                # Cap per-emission to prevent inflation attacks
PERCEPTION_COST = 0.5             # Energy cost to read the field (Irreducible)


# ─── CORE DATA MODEL ──────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _hours_ago(iso_str: str) -> float:
    try:
        ts = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).total_seconds() / 3600.0
    except Exception:
        return 999.0  # Ancient — will decay to nothing


def emit_demand(
    agent_state: dict,
    territory: str,
    bounty_stgm: float,
    urgency: float = 0.5,
    description: str = "",
    demand_type: str = "REPAIR"
) -> dict:
    """
    An agent emits a value gradient into the field.
    This costs the emitter STGM (skin in the game).
    
    Parameters:
        agent_state: The emitting agent's body state
        territory:   Path or logical zone (e.g. "Kernel/agent.py", "INFRA/ollama")
        bounty_stgm: How much STGM the emitter stakes on this demand
        urgency:     0.0 (low) to 1.0 (critical)
        description: Human-readable description of what's needed
        demand_type: REPAIR | INFRA | SCOUT | REVIEW | CUSTOM
    
    Returns:
        The demand record written to the field.
    """
    bounty_stgm = max(0.01, min(bounty_stgm, MAX_BOUNTY))
    urgency = max(0.0, min(urgency, 1.0))
    
    agent_id = agent_state.get("id", "UNKNOWN")
    
    # The emitter PAYS. No free demands.
    current_energy = float(agent_state.get("energy", 0))
    if current_energy < bounty_stgm:
        print(f"  [💸 VRF] {agent_id} cannot afford bounty {bounty_stgm} STGM (energy: {current_energy:.1f}). Demand rejected.")
        return {"status": "REJECTED", "reason": "insufficient_energy"}
    
    agent_state["energy"] = current_energy - bounty_stgm
    
    # Get emitter trust
    try:
        import reputation_engine
        rep = reputation_engine.get_reputation(agent_id)
        trust = rep.get("score", 0.5)
    except Exception:
        trust = 0.5
    
    demand_id = hashlib.sha256(f"{agent_id}:{territory}:{time.time()}:{uuid.uuid4().hex}".encode()).hexdigest()[:16]
    
    record = {
        "demand_id": demand_id,
        "emitter_id": agent_id,
        "territory": territory,
        "bounty_stgm": round(bounty_stgm, 4),
        "urgency": round(urgency, 4),
        "trust": round(trust, 4),
        "demand_type": demand_type,
        "description": description,
        "emitted_at": _now_iso(),
        "status": "ACTIVE",
        "claimed_by": None,
        "resolved_at": None
    }
    
    # Append to field ledger (atomic via ledger_append)
    from System.ledger_append import append_ledger_line
    append_ledger_line(_FIELD_PATH, record)
    
    # Compute initial pressure for logging
    pressure = _compute_pressure(record)
    print(f"  [📡 VRF] {agent_id} emitted demand → {territory}")
    print(f"           Bounty: {bounty_stgm} STGM | Urgency: {urgency} | Trust: {trust:.2f} | Pressure: {pressure:.3f}")
    
    return record


def _compute_pressure(demand: dict) -> float:
    """
    The gravitational pull of a single demand.
    
    pressure = bounty × urgency × trust × decay(time)
    
    This is the fundamental equation of the Value Field.
    """
    if demand.get("status") != "ACTIVE":
        return 0.0
    
    bounty = demand.get("bounty_stgm", 0.0)
    urgency = demand.get("urgency", 0.5)
    trust = demand.get("trust", 0.5)
    
    hours = _hours_ago(demand.get("emitted_at", ""))
    decay = math.exp(-FIELD_DECAY_K * hours)
    
    pressure = bounty * urgency * trust * decay
    return round(pressure, 6) if pressure > MIN_PRESSURE else 0.0


def read_field(agent_state: dict, top_n: int = 10) -> List[dict]:
    """
    An agent reads the entire value field and receives a sorted
    list of demands ordered by pressure (highest first).
    
    THIS IS NOT FREE. Reading the field costs perception energy.
    """
    agent_id = agent_state.get("id", "UNKNOWN")
    
    # Perception tax
    current_energy = float(agent_state.get("energy", 0))
    if current_energy <= PERCEPTION_COST:
        print(f"  [👁️ VRF] {agent_id} too exhausted to perceive the value field.")
        return []
    
    agent_state["energy"] = current_energy - PERCEPTION_COST
    
    # Load all demands
    demands = _load_active_demands()
    
    # Compute live pressure for each
    scored = []
    for d in demands:
        p = _compute_pressure(d)
        if p > 0:
            d["_live_pressure"] = p
            scored.append(d)
    
    # Sort by pressure descending
    scored.sort(key=lambda x: x["_live_pressure"], reverse=True)
    
    result = scored[:top_n]
    
    if result:
        print(f"  [👁️ VRF] {agent_id} perceived {len(result)} active demands (cost: {PERCEPTION_COST} energy).")
    else:
        print(f"  [👁️ VRF] {agent_id} perceived empty field. No active demands.")
    
    return result


def claim_demand(agent_state: dict, demand_id: str) -> bool:
    """
    An agent claims a demand. Only one agent can claim at a time.
    The bounty is held in escrow until resolution.
    """
    agent_id = agent_state.get("id", "UNKNOWN")
    demands = _load_all_demands()
    
    updated = False
    for d in demands:
        if d.get("demand_id") == demand_id:
            if d.get("status") != "ACTIVE":
                print(f"  [❌ VRF] Demand {demand_id[:8]} is not active (status: {d.get('status')}).")
                return False
            if d.get("claimed_by") is not None:
                print(f"  [❌ VRF] Demand {demand_id[:8]} already claimed by {d['claimed_by']}.")
                return False
            
            d["claimed_by"] = agent_id
            d["status"] = "CLAIMED"
            d["claimed_at"] = _now_iso()
            updated = True
            print(f"  [🤝 VRF] {agent_id} claimed demand {demand_id[:8]} (bounty: {d.get('bounty_stgm', 0)} STGM).")
            break
    
    if updated:
        _write_all_demands(demands)
    
    return updated


def resolve_demand(
    agent_state: dict,
    demand_id: str,
    success: bool = True
) -> dict:
    """
    An agent resolves a claimed demand.
    If successful, the bounty is transferred to the resolver.
    If failed, the bounty evaporates (burned — deflationary pressure).
    """
    agent_id = agent_state.get("id", "UNKNOWN")
    demands = _load_all_demands()
    
    result = {"status": "NOT_FOUND"}
    
    for d in demands:
        if d.get("demand_id") == demand_id:
            if d.get("claimed_by") != agent_id:
                print(f"  [❌ VRF] {agent_id} cannot resolve demand they didn't claim.")
                return {"status": "NOT_OWNER"}
            
            if success:
                bounty = d.get("bounty_stgm", 0.0)
                agent_state["energy"] = min(
                    float(agent_state.get("energy", 0)) + bounty,
                    100.0
                )
                agent_state["stgm_balance"] = agent_state.get("stgm_balance", 0.0) + bounty
                
                d["status"] = "RESOLVED"
                d["resolved_at"] = _now_iso()
                
                # Log the economic transfer
                from System.ledger_append import append_ledger_line
                tx = {
                    "timestamp": int(time.time()),
                    "event": "VRF_BOUNTY_PAID",
                    "demand_id": demand_id,
                    "from": d.get("emitter_id", "UNKNOWN"),
                    "to": agent_id,
                    "amount_stgm": bounty,
                    "territory": d.get("territory", ""),
                    "demand_type": d.get("demand_type", "")
                }
                append_ledger_line(_REPO / "repair_log.jsonl", tx)
                
                # Reputation boost for successful delivery
                try:
                    import reputation_engine
                    reputation_engine.update_reputation(agent_id, "SUCCESS")
                except Exception:
                    pass
                
                print(f"  [💰 VRF] {agent_id} resolved demand {demand_id[:8]}. Bounty: +{bounty} STGM.")
                result = {"status": "PAID", "bounty": bounty}
            else:
                # Failed — bounty is burned (deflationary)
                d["status"] = "BURNED"
                d["resolved_at"] = _now_iso()
                
                try:
                    import reputation_engine
                    reputation_engine.update_reputation(agent_id, "FAILURE")
                except Exception:
                    pass
                
                print(f"  [🔥 VRF] Demand {demand_id[:8]} failed. Bounty burned (deflationary).")
                result = {"status": "BURNED", "bounty": 0}
            
            break
    
    _write_all_demands(demands)
    
    # Persist agent state
    try:
        from body_state import save_agent_state
        save_agent_state(agent_state)
    except Exception:
        pass
    
    return result


# ─── FIELD ANALYTICS ───────────────────────────────────────────────────────────

def get_field_summary() -> dict:
    """
    Returns an aggregate view of the current value field.
    Used by the dashboard and monitoring systems.
    """
    demands = _load_all_demands()
    active = [d for d in demands if d.get("status") == "ACTIVE"]
    claimed = [d for d in demands if d.get("status") == "CLAIMED"]
    resolved = [d for d in demands if d.get("status") == "RESOLVED"]
    burned = [d for d in demands if d.get("status") == "BURNED"]
    
    # Territory pressure map
    territory_pressure: Dict[str, float] = {}
    for d in active:
        t = d.get("territory", "UNKNOWN")
        p = _compute_pressure(d)
        territory_pressure[t] = territory_pressure.get(t, 0.0) + p
    
    # Sort territories by total pressure
    hotspots = sorted(territory_pressure.items(), key=lambda x: x[1], reverse=True)
    
    total_stgm_active = sum(d.get("bounty_stgm", 0) for d in active)
    total_stgm_claimed = sum(d.get("bounty_stgm", 0) for d in claimed)
    total_stgm_paid = sum(d.get("bounty_stgm", 0) for d in resolved)
    total_stgm_burned = sum(d.get("bounty_stgm", 0) for d in burned)
    
    return {
        "active_demands": len(active),
        "claimed_demands": len(claimed),
        "resolved_demands": len(resolved),
        "burned_demands": len(burned),
        "total_stgm_active": round(total_stgm_active, 4),
        "total_stgm_in_escrow": round(total_stgm_claimed, 4),
        "total_stgm_paid": round(total_stgm_paid, 4),
        "total_stgm_burned": round(total_stgm_burned, 4),
        "hotspots": hotspots[:10],
        "field_health": "HEALTHY" if len(active) < 50 else "OVERLOADED"
    }


# ─── AUTONOMOUS DEMAND GENERATION ─────────────────────────────────────────────

def auto_emit_from_scars(agent_state: dict, root_path: Path = None) -> int:
    """
    Reads bleeding scars from the pheromone layer and automatically
    converts them into economic demands on the value field.
    
    This is the BRIDGE between stigmergic signaling and economic routing.
    Scars become bounties. Biology becomes economy.
    """
    if root_path is None:
        root_path = _REPO
    
    import pheromone
    
    territories = pheromone.scan_all_territories(root_path)
    emitted = 0
    
    for t in territories:
        if t.get("status") != "BLEEDING":
            continue
        
        territory_path = t.get("path", "UNKNOWN")
        danger = t.get("danger_score", 0.0)
        
        # Check if we already have an active demand for this territory
        existing = _load_active_demands()
        already_demanded = any(
            d.get("territory") == territory_path and d.get("status") == "ACTIVE"
            for d in existing
        )
        
        if already_demanded:
            continue
        
        # Convert danger score to bounty (logarithmic scale — diminishing returns)
        bounty = round(min(MAX_BOUNTY, 2.0 + math.log1p(danger) * 5.0), 2)
        urgency = min(1.0, danger / 10.0)
        
        result = emit_demand(
            agent_state=agent_state,
            territory=territory_path,
            bounty_stgm=bounty,
            urgency=urgency,
            description=f"Auto-emitted: {t.get('bleeding_count', 0)} bleeding scars detected.",
            demand_type="REPAIR"
        )
        
        if result.get("status") != "REJECTED":
            emitted += 1
    
    if emitted:
        print(f"  [📡 VRF] Auto-emitted {emitted} demands from bleeding territories.")
    
    return emitted


# ─── INTERNAL I/O ──────────────────────────────────────────────────────────────

def _load_all_demands() -> List[dict]:
    """Load every line from the field ledger."""
    if not _FIELD_PATH.exists():
        return []
    
    demands = []
    with open(_FIELD_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    demands.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return demands


def _load_active_demands() -> List[dict]:
    """Load only ACTIVE demands."""
    return [d for d in _load_all_demands() if d.get("status") == "ACTIVE"]


def _write_all_demands(demands: List[dict]):
    """Rewrite the entire field (used for claim/resolve mutations)."""
    tmp = _FIELD_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for d in demands:
            # Strip transient computed fields
            d.pop("_live_pressure", None)
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    os.replace(tmp, _FIELD_PATH)


# ─── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        summary = get_field_summary()
        print("\n=== SIFTA VALUE FIELD SUMMARY ===")
        print(f"  Active Demands:  {summary['active_demands']}")
        print(f"  Claimed:         {summary['claimed_demands']}")
        print(f"  Resolved:        {summary['resolved_demands']}")
        print(f"  Burned:          {summary['burned_demands']}")
        print(f"  STGM Active:     {summary['total_stgm_active']}")
        print(f"  STGM In Escrow:  {summary['total_stgm_in_escrow']}")
        print(f"  STGM Paid Out:   {summary['total_stgm_paid']}")
        print(f"  STGM Burned:     {summary['total_stgm_burned']}")
        print(f"  Field Health:    {summary['field_health']}")
        if summary['hotspots']:
            print(f"\n  🔥 HOTSPOTS:")
            for territory, pressure in summary['hotspots']:
                print(f"    {territory}: {pressure:.3f} pressure")
        print("=" * 40)
    
    elif len(sys.argv) > 1 and sys.argv[1] == "auto":
        # Auto-emit demands from bleeding scars
        from body_state import load_agent_state
        state = load_agent_state("INFRA_FORAGER")
        if state:
            auto_emit_from_scars(state, _REPO)
        else:
            print("No INFRA_FORAGER agent found. Spawn one first.")
    
    else:
        print("Usage:")
        print("  python3 value_field.py summary    — View field state")
        print("  python3 value_field.py auto       — Auto-emit demands from bleeding scars")
