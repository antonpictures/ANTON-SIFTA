#!/usr/bin/env python3
"""
swarm_prediction_cache.py — DEPRECATION SHIM
═══════════════════════════════════════════════
Architect ratified the merge 2026-04-18: this module's logic moved into
System/swarm_inferior_olive.py (anatomically named, climbing-fiber feedback,
dream-aware off-policy updates).

Callers should migrate to:

    from System.swarm_inferior_olive import InferiorOlive

This shim preserves the original public surface so existing imports
(`from System.swarm_prediction_cache import PredictionCache`) keep working.
The original AG31 file is preserved in git history if you need it.

What you get from this shim:
- PredictionCache  — alias of the new InferiorOlive (with legacy
                     ingest_ledgers() / update() / predict() methods)
- ALPHA            — preserved constant for any caller that imported it
- RATIFIED_LOG     — preserved path constant
- REJECTED_LOG     — preserved path constant
- PREDICTION_CACHE — preserved path constant (same JSON file on disk)

All real implementation lives in swarm_inferior_olive.py.
"""
from __future__ import annotations

import warnings as _warnings

from System.swarm_inferior_olive import (
    PredictionCache,                    # legacy-API alias of InferiorOlive
    InferiorOlive,                      # new canonical name (re-exported for convenience)
    RATIFIED_LOG,
    REJECTED_LOG,
    PREDICTION_CACHE,
    ALPHA_REAL as ALPHA,                # legacy name was just `ALPHA`
)

__all__ = [
    "PredictionCache",
    "InferiorOlive",
    "RATIFIED_LOG",
    "REJECTED_LOG",
    "PREDICTION_CACHE",
    "ALPHA",
]

_warnings.warn(
    "System.swarm_prediction_cache is a deprecation shim; "
    "import from System.swarm_inferior_olive instead "
    "(merge ratified by Architect 2026-04-18).",
    DeprecationWarning,
    stacklevel=2,
)


if __name__ == "__main__":
    # Preserve the original tiny smoke so muscle-memory `python3 swarm_prediction_cache.py`
    # still produces useful output. All real work delegated to InferiorOlive.
    pc = PredictionCache()
    pc.update("idle_desktop", "increase_probe_frequency", 1.0)
    pc.update("idle_desktop", "increase_probe_frequency", 1.0)
    pc.update("heavy_compute", "spawn_swimmer", -1.0)

    print("═" * 58)
    print("  SIFTA — TD-LEARNING FAST PREDICTION CACHE  (shim → InferiorOlive)")
    print("═" * 58 + "\n")
    print(f"P(approve | idle, inc_probe) = {pc.predict('idle_desktop', 'increase_probe_frequency'):.3f}")
    print(f"P(approve | heavy, spawn)    = {pc.predict('heavy_compute', 'spawn_swimmer'):.3f}")
    print()
    print("[NOTE] This file is a deprecation shim. The canonical module is now")
    print("       System/swarm_inferior_olive.py")
