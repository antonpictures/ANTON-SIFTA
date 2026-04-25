#!/usr/bin/env python3
"""Compact public substrate: memory + prediction + attention - danger.

This module is the simple four-channel API. The implementation delegates to
`swarm_unified_field_engine`, so Alice has one substrate, not parallel field
truths.
"""

from __future__ import annotations

from dataclasses import dataclass

from System.swarm_unified_field_engine import UnifiedFieldConfig as _EngineConfig
from System.swarm_unified_field_engine import UnifiedFieldEngine


@dataclass(frozen=True)
class UnifiedFieldConfig:
    grid_size: int = 128
    decay: float = 0.97
    diffusion: float = 0.05
    w_memory: float = 1.0
    w_prediction: float = 0.8
    w_attention: float = 0.6
    w_danger: float = 1.2
    eps: float = 1e-8

    def to_engine_config(self) -> _EngineConfig:
        return _EngineConfig(
            grid_size=int(self.grid_size),
            decay=float(self.decay),
            diffusion=float(self.diffusion),
            alpha_memory=float(self.w_memory),
            beta_prediction=float(self.w_prediction),
            salience_weight=float(self.w_attention),
            delta_danger=float(self.w_danger),
            gamma_repair=0.0,
            crowding_weight=0.0,
            eps=float(self.eps),
        )


class UnifiedStigmergicField(UnifiedFieldEngine):
    """One substrate. Multiple meanings. Agents only sense the gradient."""

    def __init__(self, cfg: UnifiedFieldConfig | None = None):
        self.substrate_cfg = cfg or UnifiedFieldConfig()
        super().__init__(self.substrate_cfg.to_engine_config())


__all__ = ["UnifiedFieldConfig", "UnifiedStigmergicField", "UnifiedFieldEngine"]
