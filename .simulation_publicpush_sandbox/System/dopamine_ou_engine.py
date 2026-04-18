#!/usr/bin/env python3
"""
dopamine_ou_engine.py — Ornstein–Uhlenbeck DA with internal RPE from affinity outcomes.
══════════════════════════════════════════════════════════════════════════════════════

Merged from Claude tab (2026-04-18) + CP2F integration.

**Hard contract:** `affinity_outcome` must be a **measured** scalar (e.g. fused
identity stability, outcome of `identity_outcome_contract` accumulated tick score),
never self-reported model confidence.

`novelty_score` should be in **[0, 1]** (normalize `PFCWorkingMemory.cosine_novelty()`
by `/ 2.0` if your buffer returns [0, 2]).

Biology anchors (docstrings in original Claude dump):
  Schultz, Dayan & Montague, Science 275:1593 (1997)
  Uhlenbeck & Ornstein, Phys Rev 36:823 (1930)
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import read_write_json_locked

_REPO = Path(__file__).resolve().parent.parent
_OU_STATE_PATH = _REPO / ".sifta_state" / "dopamine_ou_engine.json"

MODULE_VERSION = "2026-04-18.v4"


class BehavioralState(str, Enum):
    EXPLOITATION = "EXPLOITATION"
    MAINTENANCE = "MAINTENANCE"
    EXPLORATION = "EXPLORATION"


DIRECTIVES: Dict[BehavioralState, str] = {
    BehavioralState.EXPLOITATION: (
        "NARROW_FOCUS: Compile current high-affinity pattern into permanent architecture."
    ),
    BehavioralState.MAINTENANCE: "CONTINUE_PROCESSING: Steady baseline state.",
    BehavioralState.EXPLORATION: "WIDEN_SEARCH: Seek novelty. Raise temperature. Diversify inputs.",
}

OU_THETA = 0.15
OU_MU = 0.50
OU_SIGMA = 0.08
DA_CLAMP = (0.05, 0.95)

RPE_GAIN = 0.30
NOVELTY_GAIN = 0.20
WAKE_BOOST = 0.10
WAKE_BOOST_TICKS = 5


@dataclass
class DAState:
    level: float
    rpe: float
    novelty: float
    behavioral_state: BehavioralState
    directive: str
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "da_level": round(self.level, 4),
            "rpe": round(self.rpe, 4),
            "novelty": round(self.novelty, 4),
            "behavioral_state": self.behavioral_state.value,
            "directive": self.directive,
            "ts": self.ts,
        }


class DopamineState:
    """
    Stateful OU-process DA. Call `.tick()` each processing cycle.
    RPE = outcome − EMA(expected affinity); first tick RPE = 0.
    """

    def __init__(self, initial_da: float = OU_MU, post_sleep: bool = False) -> None:
        self._da = float(initial_da)
        self._last_ts = time.time()
        self._wake_ticks = WAKE_BOOST_TICKS if post_sleep else 0
        self._tick_count = 0
        self._expected_affinity: Optional[float] = None
        self._ema_alpha = 0.3

    def tick(
        self,
        novelty_score: float,
        affinity_outcome: float,
        dt: Optional[float] = None,
        *,
        rpe_gain_scale: float = 1.0,
    ) -> DAState:
        now = time.time()
        if dt is None:
            dt = max(now - self._last_ts, 1e-3)
        self._last_ts = now
        self._tick_count += 1

        # Normalize novelty to [0,1] if caller passed cosine_novelty raw [0,2]
        ns = float(novelty_score)
        if ns > 1.0:
            ns = max(0.0, min(1.0, ns / 2.0))

        rpe = self._compute_rpe(float(affinity_outcome))
        novelty_drive = (ns - 0.5) * NOVELTY_GAIN

        mu_effective = OU_MU + (WAKE_BOOST if self._wake_ticks > 0 else 0.0)
        if self._wake_ticks > 0:
            self._wake_ticks -= 1

        ou_drift = OU_THETA * (mu_effective - self._da) * float(dt)
        scale = max(0.0, float(rpe_gain_scale))
        rpe_push = rpe * RPE_GAIN * scale

        self._da = self._da + ou_drift + rpe_push + novelty_drive
        self._da = max(DA_CLAMP[0], min(DA_CLAMP[1], self._da))

        st = self._classify(self._da)
        return DAState(
            level=self._da,
            rpe=rpe,
            novelty=ns,
            behavioral_state=st,
            directive=DIRECTIVES[st],
        )

    def notify_wake(self) -> None:
        """After glymphatic / PFC flush — post-sleep novelty boost window."""
        self._wake_ticks = WAKE_BOOST_TICKS
        self._expected_affinity = None

    @property
    def level(self) -> float:
        return self._da

    def _compute_rpe(self, outcome: float) -> float:
        if self._expected_affinity is None:
            self._expected_affinity = outcome
            return 0.0
        rpe = outcome - self._expected_affinity
        self._expected_affinity = (
            self._ema_alpha * outcome + (1.0 - self._ema_alpha) * self._expected_affinity
        )
        return rpe

    @staticmethod
    def _classify(da: float) -> BehavioralState:
        if da > 0.65:
            return BehavioralState.EXPLOITATION
        if da < 0.35:
            return BehavioralState.EXPLORATION
        return BehavioralState.MAINTENANCE

    def to_persistent(self) -> Dict[str, Any]:
        return {
            "module_version": MODULE_VERSION,
            "da": self._da,
            "last_ts": self._last_ts,
            "wake_ticks": self._wake_ticks,
            "tick_count": self._tick_count,
            "expected_affinity": self._expected_affinity,
            "ema_alpha": self._ema_alpha,
        }

    @classmethod
    def from_persistent(cls, d: Dict[str, Any]) -> "DopamineState":
        o = cls(initial_da=float(d.get("da", OU_MU)), post_sleep=False)
        o._last_ts = float(d.get("last_ts", time.time()))
        o._wake_ticks = int(d.get("wake_ticks", 0))
        o._tick_count = int(d.get("tick_count", 0))
        ea = d.get("expected_affinity")
        o._expected_affinity = float(ea) if ea is not None else None
        o._ema_alpha = float(d.get("ema_alpha", 0.3))
        return o


def load_ou_engine(path: Path = _OU_STATE_PATH) -> DopamineState:
    if not path.exists():
        return DopamineState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return DopamineState.from_persistent(raw)
    except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError):
        return DopamineState()


def persist_ou_engine(engine: DopamineState, path: Path = _OU_STATE_PATH) -> None:
    def _upd(_: Dict[str, Any]) -> Dict[str, Any]:
        return engine.to_persistent()

    read_write_json_locked(path, _upd)


def _smoke() -> None:
    ds = DopamineState(post_sleep=True)
    scenarios = [
        (0.8, 0.45, "wake"),
        (0.7, 0.72, "fusion"),
        (0.7, 0.74, "hot"),
        (0.2, 0.55, "familiar"),
        (0.1, 0.50, "flat"),
        (0.1, 0.48, "bored"),
        (0.9, 0.80, "breakthrough"),
    ]
    for novelty, affinity, _ in scenarios:
        st = ds.tick(novelty_score=novelty, affinity_outcome=affinity, dt=1.0)
        print(f"[{st.behavioral_state.value:<13}] DA={st.level:.3f} RPE={st.rpe:+.3f}")
    print(json.dumps(st.to_dict(), indent=2))


if __name__ == "__main__":
    _smoke()


__all__ = [
    "BehavioralState",
    "DAState",
    "DopamineState",
    "DIRECTIVES",
    "RPE_GAIN",
    "NOVELTY_GAIN",
    "load_ou_engine",
    "persist_ou_engine",
    "MODULE_VERSION",
]
