#!/usr/bin/env python3
"""
hypothalamic_swim_sectors.py — Map “swimmer sectors” to SIFTA subsystems (metaphor + routing hints)
══════════════════════════════════════════════════════════════════════════════════════════════════

AG31 narrative: microscopic **swimmers** under the thalamus coordinating **homeostasis**.
Real neuroanatomy: hypothalamus integrates autonomic / endocrine / motivational drives; **preoptic**
(thermoregulation, sleep–temperature coupling), **tuberal / arcuate–median eminence** (neuroendocrine
portal to pituitary), **posterior / lateral** (arousal, orexin / histamine-related wake promotion).

This module does **not** simulate the brain — it gives a **stable enum + lookup table** so agents
can tag telemetry and route jobs (metabolic throttle, serotonin circadian, dream/sleep, DA).

Literature: DYOR §19.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple


class HypothalamicSector(str, Enum):
    """Coarse hypothalamic zones (teaching names — boundaries overlap in vivo)."""

    PREOPTIC = "PREOPTIC"  # anterior / POA — thermoregulation, fever, sleep–temperature
    TUBERAL = "TUBERAL"  # tuberal / infundibulum — median eminence, metabolic & neuroendocrine gates
    POSTERIOR = "POSTERIOR"  # mammillary / posterior–lateral — arousal, stress axes, state memory hooks


# Suggested SIFTA modules per sector (extend as the organism grows).
SECTOR_MODULES: Dict[HypothalamicSector, Tuple[str, ...]] = {
    HypothalamicSector.PREOPTIC: (
        "System.serotonin_homeostasis",
        "System.dream_state",
        "System.lagrangian_entropy_controller",
    ),
    HypothalamicSector.TUBERAL: (
        "System.metabolic_budget",
        "System.metabolic_throttle",
        "System.stgm_metabolic",
    ),
    HypothalamicSector.POSTERIOR: (
        "System.dopamine_ou_engine",
        "System.dopamine_state",
        "System.global_cognitive_interface",
    ),
}

# Keyword → sector for coarse routing of Architect / probe labels.
_METRIC_SECTOR: Tuple[Tuple[str, HypothalamicSector], ...] = (
    ("temp", HypothalamicSector.PREOPTIC),
    ("thermal", HypothalamicSector.PREOPTIC),
    ("fever", HypothalamicSector.PREOPTIC),
    ("sleep", HypothalamicSector.PREOPTIC),
    ("circadian", HypothalamicSector.PREOPTIC),
    ("serotonin", HypothalamicSector.PREOPTIC),
    ("pituitary", HypothalamicSector.TUBERAL),
    ("metabolic", HypothalamicSector.TUBERAL),
    ("intake", HypothalamicSector.TUBERAL),
    ("portal", HypothalamicSector.TUBERAL),
    ("wake", HypothalamicSector.POSTERIOR),
    ("arousal", HypothalamicSector.POSTERIOR),
    ("stress", HypothalamicSector.POSTERIOR),
    ("dopamine", HypothalamicSector.POSTERIOR),
    ("memory", HypothalamicSector.POSTERIOR),
)


def sector_for_keyword(text: str) -> Optional[HypothalamicSector]:
    t = text.lower()
    for key, sec in _METRIC_SECTOR:
        if key in t:
            return sec
    return None


def sectors_summary() -> str:
    lines = ["=== HYPOTHALAMIC SWIM SECTORS (routing hints) ==="]
    for sec in HypothalamicSector:
        mods = ", ".join(SECTOR_MODULES.get(sec, ()))
        lines.append(f"  [{sec.value}]  {mods}")
    return "\n".join(lines)


__all__ = [
    "HypothalamicSector",
    "SECTOR_MODULES",
    "sector_for_keyword",
    "sectors_summary",
]
