#!/usr/bin/env python3
"""
identity_outcome_contract.py — Hard boundary: affinity / identity deltas are OUTCOME-ONLY.
══════════════════════════════════════════════════════════════════════════════════════════

Architect directive (Claude tab relay): nothing may pass **self-reported model
confidence** into motivational or reward code. This module is the **only**
approved way to turn two `IdentityField` snapshots into a scalar **affinity_delta**
suitable for `dopamine_state.step(...)`.

Allowed signals:
    * Δ stability  = stability(after) − stability(before)
    * Δ entropy    = entropy(before) − entropy(after)   (positive = good)

Forbidden:
    * any key matching reinforcement_myelination._FORBIDDEN_REWARD_KEYS
    * tokenizer logprobs, "I am 99% sure", UI-reported confidence

If you need a different notion of "affinity", add a NEW function here with an
explicit formula — do not thread opaque floats from chat layers.
"""
from __future__ import annotations

from typing import Any

MODULE_VERSION = "2026-04-18.v2"

# Weights on measurable field metrics (tunable).
W_STABILITY = 1.0
W_ENTROPY_DROP = 0.5


def affinity_delta_identity_field(field_before: Any, field_after: Any) -> float:
    """
    Outcome-only scalar: higher = swarm identity moved in a "good" direction.

    Uses only `.stability()` and `.entropy()` on IdentityField-like objects.
    """
    sb = float(field_before.stability())
    sa = float(field_after.stability())
    eb = float(field_before.entropy())
    ea = float(field_after.entropy())
    ds = sa - sb
    de_drop = eb - ea
    return W_STABILITY * ds + W_ENTROPY_DROP * de_drop


__all__ = ["affinity_delta_identity_field", "MODULE_VERSION", "W_STABILITY", "W_ENTROPY_DROP"]
