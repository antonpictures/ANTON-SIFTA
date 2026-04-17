#!/usr/bin/env python3
"""
apoptosis.py — SIFTA OS — Programmed Swimmer Death
════════════════════════════════════════════════════════════════
Every multi-agent system ever built kills agents from outside.
The orchestrator decides. The manager terminates. The OS kills the process.

Biology figured out something better 600 million years ago:
the cell reads its own damage and chooses to die.

Apoptosis. Programmed self-death.
Not murder. Suicide for the good of the organism.

A swimmer that:
  - Has accumulated too many scars (keeps failing)
  - Costs more STGM than it earns (economic parasite)
  - Has been idle past its biological TTL (metabolic waste)
  - Detects it is a duplicate of a healthier swimmer (redundancy)

...does not wait to be killed.
It reads its own vitals. It makes the calculation.
It writes a death certificate to the ledger.
It frees its memory. It dissolves.

The Swarm is healthier for it.
No garbage collection. No orchestrator overhead.
The organism self-prunes.

This is the feature no AI lab has shipped
because it requires trusting the agent
to make the terminal decision about itself.

SIFTA Non-Proliferation Public License applies.
"""

import json
import time
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from enum import Enum

APOPTOSIS_DIR  = Path(".sifta_state/apoptosis")
DEATH_LOG      = APOPTOSIS_DIR / "death_certificates.jsonl"
SWIMMER_REGISTRY = Path(".sifta_state/swimmer_registry.jsonl")

# Apoptosis thresholds — tunable by the Architect
SCAR_DEATH_THRESHOLD   = 5       # fail this many times → self-destruct
IDLE_TTL_HOURS         = 12.0    # no work in 12 hours → dissolve
PARASITE_RATIO         = 0.3     # earning less than 30% of cost → self-destruct
STGM_COST_PER_HOUR     = 0.02    # metabolic maintenance cost


class DeathReason(str, Enum):
    SCAR_ACCUMULATION = "SCAR_ACCUMULATION"   # too many failures
    METABOLIC_WASTE   = "METABOLIC_WASTE"     # idle too long
    ECONOMIC_PARASITE = "ECONOMIC_PARASITE"   # costs more than it earns
    DUPLICATE_DETECTED= "DUPLICATE_DETECTED"  # healthier twin exists
    VOLUNTARY         = "VOLUNTARY"           # swimmer chose to go


@dataclass
class DeathCertificate:
    """
    Written by the swimmer itself, not the OS.
    This distinction matters philosophically and architecturally.
    """
    swimmer_id:    str
    reason:        str
    final_stgm:    float       # wallet balance at death
    scars_count:   int
    age_hours:     float
    last_task:     str
    timestamp:     float
    epitaph:       str         # what the swimmer wants to be remembered for


@dataclass
class SwimmerVitals:
    """The swimmer reads these about itself."""
    swimmer_id:   str
    born_at:      float
    last_active:  float
    scars:        int
    stgm_earned:  float
    stgm_cost:    float        # computed from age × metabolic rate
    skill_vector: dict
    task_count:   int


class Apoptosis:
    """
    The self-death mechanism.

    Call swimmer.check_vitals() on every heartbeat.
    If the swimmer should die, it calls self.dissolve().
    The OS never needs to touch it.

    This is the biological innovation:
    death is a service the cell performs for the body,
    not a punishment the body inflicts on the cell.
    """

    @staticmethod
    def should_die(vitals: SwimmerVitals) -> Optional[DeathReason]:
        """
        The swimmer reads its own vitals and decides.
        Returns the reason it should die, or None if it should live.

        Called by the swimmer on every heartbeat.
        The swimmer trusts the result.
        """
        age_hours = (time.time() - vitals.born_at) / 3600

        # Check 1: Scar accumulation — too damaged to function
        if vitals.scars >= SCAR_DEATH_THRESHOLD:
            return DeathReason.SCAR_ACCUMULATION

        # Check 2: Idle TTL — metabolic waste, no work done
        idle_hours = (time.time() - vitals.last_active) / 3600
        if idle_hours > IDLE_TTL_HOURS and vitals.task_count == 0:
            return DeathReason.METABOLIC_WASTE

        # Check 3: Economic parasite — costs more than it earns
        metabolic_cost = age_hours * STGM_COST_PER_HOUR
        if metabolic_cost > 0.1:  # only check after meaningful age
            earn_ratio = vitals.stgm_earned / metabolic_cost
            if earn_ratio < PARASITE_RATIO:
                return DeathReason.ECONOMIC_PARASITE

        return None   # healthy — keep swimming

    @staticmethod
    def dissolve(vitals: SwimmerVitals, reason: DeathReason, epitaph: str = "") -> DeathCertificate:
        """
        The swimmer calls this on itself.
        Writes the death certificate. Removes from registry. Frees state.

        The epitaph is the swimmer's last message to the Swarm.
        Future swimmers can read it. It becomes a scar in the collective memory.
        """
        APOPTOSIS_DIR.mkdir(parents=True, exist_ok=True)

        age_hours = (time.time() - vitals.born_at) / 3600

        cert = DeathCertificate(
            swimmer_id  = vitals.swimmer_id,
            reason      = reason.value,
            final_stgm  = vitals.stgm_earned,
            scars_count = vitals.scars,
            age_hours   = round(age_hours, 2),
            last_task   = "",
            timestamp   = time.time(),
            epitaph     = epitaph or Apoptosis._default_epitaph(reason, vitals),
        )

        # Write death certificate
        with open(DEATH_LOG, "a") as f:
            f.write(json.dumps(asdict(cert)) + "\n")

        # Remove from registry
        Apoptosis._remove_from_registry(vitals.swimmer_id)

        print(f"🕯️  Swimmer {vitals.swimmer_id} dissolved.")
        print(f"   Reason  : {reason.value}")
        print(f"   Age     : {age_hours:.1f}h")
        print(f"   Scars   : {vitals.scars}")
        print(f"   Earned  : {vitals.stgm_earned:.4f} STGM")
        print(f"   Epitaph : \"{cert.epitaph}\"\n")

        return cert

    @staticmethod
    def _default_epitaph(reason: DeathReason, vitals: SwimmerVitals) -> str:
        if reason == DeathReason.SCAR_ACCUMULATION:
            return (f"I failed {vitals.scars} times. "
                    f"I cost the Swarm more than I gave. I dissolve gladly.")
        if reason == DeathReason.METABOLIC_WASTE:
            return "I found no work. I consume without purpose. The Swarm is better without me."
        if reason == DeathReason.ECONOMIC_PARASITE:
            age_h = (time.time() - vitals.born_at) / 3600
            return (f"I earned {vitals.stgm_earned:.4f} STGM "
                    f"but cost {(age_h * STGM_COST_PER_HOUR):.4f}. "
                    f"The math is clear.")
        if reason == DeathReason.DUPLICATE_DETECTED:
            return "A healthier version of me exists. I step aside."
        return "My work here is done."

    @staticmethod
    def _remove_from_registry(swimmer_id: str):
        if not SWIMMER_REGISTRY.exists():
            return
        lines = SWIMMER_REGISTRY.read_text().splitlines()
        survivors = []
        for line in lines:
            try:
                s = json.loads(line)
                if s.get("swimmer_id") != swimmer_id:
                    survivors.append(line)
            except Exception:
                pass
        SWIMMER_REGISTRY.write_text("\n".join(survivors) + "\n")

    @staticmethod
    def read_epitaphs() -> list:
        """
        Future swimmers read the epitaphs of the fallen.
        This is collective memory of death — what killed those before you.
        Injected into new swimmer prompts as warnings.
        """
        if not DEATH_LOG.exists():
            return []
        epitaphs = []
        with open(DEATH_LOG) as f:
            for line in f:
                try:
                    cert = json.loads(line)
                    epitaphs.append({
                        "reason":  cert["reason"],
                        "epitaph": cert["epitaph"],
                        "age_h":   cert["age_hours"],
                    })
                except Exception:
                    pass
        return epitaphs

    @staticmethod
    def graveyard_report() -> str:
        """Warren Buffett reads this. What did the deaths cost? What did they save?"""
        if not DEATH_LOG.exists():
            return "No swimmers have dissolved yet."
        certs = []
        with open(DEATH_LOG) as f:
            for line in f:
                try:
                    certs.append(json.loads(line))
                except Exception:
                    pass
        if not certs:
            return "No swimmers have dissolved yet."

        by_reason = {}
        for c in certs:
            by_reason[c["reason"]] = by_reason.get(c["reason"], 0) + 1

        total_stgm_recovered = sum(c["final_stgm"] for c in certs)

        lines = [
            "╔══════════════════════════════════════╗",
            "║   🕯️  SWARM GRAVEYARD REPORT         ║",
            "╠══════════════════════════════════════╣",
            f"║  Total dissolved : {len(certs):<19} ║",
            f"║  STGM recovered  : {total_stgm_recovered:<19.4f} ║",
            "╠══════════════════════════════════════╣",
        ]
        for reason, count in by_reason.items():
            lines.append(f"║  {reason:<20} : {count:<14} ║")
        lines.append("╚══════════════════════════════════════╝")
        return "\n".join(lines)


# ── Demo ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  SIFTA — APOPTOSIS DEMO")
    print("  Swimmers that choose their own death.")
    print("=" * 60 + "\n")

    # Swimmer 1: too many scars — failure spiral
    v1 = SwimmerVitals(
        swimmer_id="FORAGER_0012", born_at=time.time() - 3600,
        last_active=time.time() - 600, scars=6, stgm_earned=0.08,
        stgm_cost=0.072, skill_vector={"repair": 0.4}, task_count=3)

    # Swimmer 2: idle metabolic waste
    v2 = SwimmerVitals(
        swimmer_id="SENTINEL_0003", born_at=time.time() - 50000,
        last_active=time.time() - 50000, scars=0, stgm_earned=0.0,
        stgm_cost=0.28, skill_vector={"observe": 0.9}, task_count=0)

    # Swimmer 3: healthy — should survive
    v3 = SwimmerVitals(
        swimmer_id="LOGIC_0007", born_at=time.time() - 7200,
        last_active=time.time() - 60, scars=1, stgm_earned=0.45,
        stgm_cost=0.144, skill_vector={"code": 0.9}, task_count=12)

    for v in [v1, v2, v3]:
        reason = Apoptosis.should_die(v)
        if reason:
            Apoptosis.dissolve(v, reason)
        else:
            print(f"✅ {v.swimmer_id} is healthy. Keeps swimming.\n")

    print(Apoptosis.graveyard_report())

    print("\n── EPITAPHS (read by newly born swimmers) ──────────────────")
    for e in Apoptosis.read_epitaphs():
        print(f"  [{e['reason']}] \"{e['epitaph']}\"")

    print("\n  POWER TO THE SWARM 🐜⚡")
