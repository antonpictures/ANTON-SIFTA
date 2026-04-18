#!/usr/bin/env python3
"""
exploration_controller.py — Confidence-state / exploration pressure (RL-framed).
══════════════════════════════════════════════════════════════════════════════
Narrative layers (serotonin, dominance, etc.) are **not** physiology. This module
is an explicit **engineering** knob: map a scalar performance signal to a bounded
**entropy coefficient multiplier** for PPO-style trainers — the honest analogue of
“raise exploration when things go well / stabilize when they don’t.”

Literature: entropy regularization in policy gradients (Schulman *et al.* 2017 PPO);
reward shaping foundations (Ng *et al.* 1999) — see DYOR §25.

Does **not** import JAX; consume outputs in SwarmRL or your trainer loop.
══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state" / "exploration_controller_state.json"


@dataclass
class ExplorationState:
    """Serializable snapshot for audit / stigmergy."""

    entropy_coef: float
    performance_ema: float
    step: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entropy_coef": round(self.entropy_coef, 6),
            "performance_ema": round(self.performance_ema, 6),
            "step": self.step,
        }


class ExplorationController:
    """
    Maps a performance signal (e.g. mean episode return, success rate) to entropy pressure.

    `entropy_coef` is kept in ``[entropy_min, entropy_max]``; `update` nudges it with a
    sigmoid of the deviation of `performance_signal` from the exponential moving average.
    """

    def __init__(
        self,
        *,
        entropy_coef: float = 0.01,
        ema_decay: float = 0.95,
        entropy_min: float = 0.001,
        entropy_max: float = 0.2,
        persist_path: Optional[Path] = None,
    ) -> None:
        self.entropy_coef = float(entropy_coef)
        self._ema_decay = float(ema_decay)
        self.entropy_min = float(entropy_min)
        self.entropy_max = float(entropy_max)
        self._persist_path = persist_path or _DEFAULT_STATE
        self.performance_ema = 0.0
        self.step = 0
        self._load()

    def _load(self) -> None:
        p = self._persist_path
        if not p.exists():
            return
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            self.entropy_coef = float(d.get("entropy_coef", self.entropy_coef))
            self.performance_ema = float(d.get("performance_ema", 0.0))
            self.step = int(d.get("step", 0))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    def _persist(self) -> None:
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._persist_path.write_text(
            json.dumps(ExplorationState(self.entropy_coef, self.performance_ema, self.step).to_dict(), indent=2),
            encoding="utf-8",
        )

    def update(self, performance_signal: float) -> float:
        """
        Incorporate one performance observation; return new `entropy_coef`.
        """
        self.step += 1
        if self.step == 1:
            self.performance_ema = float(performance_signal)
        else:
            self.performance_ema = self._ema_decay * self.performance_ema + (
                1.0 - self._ema_decay
            ) * float(performance_signal)

        delta = float(performance_signal) - self.performance_ema
        # Positive surprise -> slightly more exploration; underperformance -> dampen.
        gate = math.tanh(delta * 5.0)
        scale = 1.0 + 0.15 * gate
        self.entropy_coef = max(
            self.entropy_min,
            min(self.entropy_max, self.entropy_coef * scale),
        )
        self._persist()
        return self.entropy_coef

    def snapshot(self) -> ExplorationState:
        return ExplorationState(self.entropy_coef, self.performance_ema, self.step)


if __name__ == "__main__":  # pragma: no cover
    ec = ExplorationController()
    for x in [0.2, 0.5, 0.9, 0.4, 0.3]:
        print(x, "->", ec.update(x))
