#!/usr/bin/env python3
"""
chemotactic_probe_router.py — E. coli run-and-tumble → SLLI probe scheduling.
══════════════════════════════════════════════════════════════════════════════

Biology (local synthesis; no centralized-AI call)
---------------------------------------------------
*Escherichia coli* navigates chemical gradients by alternating **runs**
(persistent swimming when the signal improves) and **tumbles** (random
reorientation when the signal is flat or worsening). Classic references:
Howard C. Berg, *E. coli in Motion* (Springer, 2004); Berg & Brown (1972)
on run length statistics.

Why this is not quorum_sensing.py
---------------------------------
`quorum_sensing.py` answers *whether the swarm may commit* (LuxR threshold).
This module answers *what probe to fire next* while still exploring the
hypothesis space — the chemotaxis analogue of “keep moving down gradient
or randomize when lost.”

Mapping
-------
    normalized_entropy = H(p) / log(K)   from IdentityField
        high  → field is flat / confused → TUMBLE → high_disambiguation_probe
        low   → field has a ridge        → RUN    → low_frequency_probe

    QuorumReadout.state == CONTESTED → force TUMBLE (two peaks too close).

Public API
----------
    ChemotaxisDecision — dataclass with mode, probe_tag, metrics
    decide(field, *, entropy_tumble_threshold=0.65) -> ChemotaxisDecision
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from System.identity_field_crdt import IdentityField

SCHEMA_VERSION = 1
MODULE_VERSION = "2026-04-17.v1"


@dataclass(frozen=True)
class ChemotaxisDecision:
    mode: str  # "RUN" | "TUMBLE"
    probe_tag: str  # matches IdentityField.generate_probe() tags
    normalized_entropy: float
    entropy: float
    max_entropy: float
    top_label: Optional[str]
    top_prob: Optional[float]
    reasons: tuple[str, ...]


def decide(
    field: IdentityField,
    *,
    entropy_tumble_threshold: float = 0.65,
    quorum_readout: Optional[Any] = None,
) -> ChemotaxisDecision:
    """
    Schedule the next SLLI probe from the current identity field.

    `quorum_readout` is optional output from `quorum_sensing.sense(field)`.
    If its `.state == "CONTESTED"`, we always TUMBLE regardless of entropy.
    """
    dist = field.distribution()
    h = field.entropy()
    hmax = field.max_entropy()
    norm = (h / hmax) if hmax > 0 else 1.0
    top = field.top()
    top_label, top_prob = (top[0], top[1]) if top else (None, None)

    reasons: list[str] = []
    force_tumble = False
    if quorum_readout is not None:
        st = getattr(quorum_readout, "state", None)
        if st == "CONTESTED":
            force_tumble = True
            reasons.append("quorum_CONTESTED_two_peaks_too_close")

    if force_tumble or norm >= entropy_tumble_threshold:
        mode = "TUMBLE"
        probe = "high_disambiguation_probe"
        if not reasons:
            reasons.append(f"norm_entropy_{norm:.3f}>={entropy_tumble_threshold}")
    else:
        mode = "RUN"
        probe = "low_frequency_probe"
        reasons.append(f"norm_entropy_{norm:.3f}<{entropy_tumble_threshold}")

    return ChemotaxisDecision(
        mode=mode,
        probe_tag=probe,
        normalized_entropy=round(norm, 4),
        entropy=round(h, 4),
        max_entropy=round(hmax, 4),
        top_label=top_label,
        top_prob=round(top_prob, 4) if top_prob is not None else None,
        reasons=tuple(reasons),
    )


def _demo() -> None:
    from System.quorum_sensing import sense as qs_sense

    f = IdentityField()
    # Confused field → should TUMBLE
    f.update_from_classifier("A", {"m1": 0.34, "m2": 0.33, "m3": 0.33}, weight=2)
    d1 = decide(f, quorum_readout=qs_sense(f))
    print(f"[chemotactic_probe_router] v{MODULE_VERSION}")
    print("confused field:", d1.mode, d1.probe_tag, "norm_H=", d1.normalized_entropy)

    # Peaked field → should RUN
    g = IdentityField()
    g.update_from_classifier("X", {"winner": 0.95, "noise": 0.05}, weight=5)
    d2 = decide(g, quorum_readout=qs_sense(g))
    print("peaked field: ", d2.mode, d2.probe_tag, "norm_H=", d2.normalized_entropy)


if __name__ == "__main__":
    _demo()


__all__ = [
    "ChemotaxisDecision",
    "decide",
    "MODULE_VERSION",
    "SCHEMA_VERSION",
]
