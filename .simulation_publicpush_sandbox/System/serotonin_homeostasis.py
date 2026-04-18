#!/usr/bin/env python3
"""
serotonin_homeostasis.py — 5-HT homeostatic governor for the DA/motor system.
══════════════════════════════════════════════════════════════════════════════
Biology:
  Dorsal Raphe Nucleus (DRN) → 5-HT projections → PFC, striatum, amygdala.
  5-HT does NOT directly encode reward. It governs:
    1. DA VOLATILITY DAMPING  — high 5-HT clamps RPE gain; swarm stays patient.
    2. EXPLOITATION PATIENCE  — counts consecutive EXPLOITATION ticks; forces
                                MAINTENANCE when patience budget exhausted.
    3. CIRCADIAN PHASE GATE   — 5-HT rises with cycle_phase (0=dawn,1=noon,2=dusk,3=sleep);
                                at phase=3, triggers glymphatic sleep flag.
    4. IMPULSIVITY SCORE      — low 5-HT raises effective RPE_GAIN in DA engine,
                                creating volatile rapid-switching behavior.

Hard interface contract:
  da_level      : float [0,1]   — current DopamineState.level
  cycle_phase   : int   {0,1,2,3} — circadian phase (caller tracks)
  exploitation_streak : int     — consecutive ticks in EXPLOITATION state

Output: SHTState with adjusted RPE_GAIN multiplier + flags.

Biology anchors:
  Dayan & Huys, PLOS Comput Biol 4(2) e4 (2008) — 5-HT and inhibition.
  Cools, Nakamura & Daw, Neuropsychopharmacology 36:98 (2011) — DA/5-HT unification.
  Jacobs & Fornal, Curr Opin Neurobiol 7:820 (1997) — 5-HT and motor activity.
══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from System.dopamine_ou_engine import DopamineState

# ── Circadian phase ─────────────────────────────────────────────────────────


class CircadianPhase(int, Enum):
    DAWN = 0  # 5-HT rising, moderate arousal
    NOON = 1  # 5-HT peak, maximum patience + focus
    DUSK = 2  # 5-HT declining, mild impulsivity
    SLEEP = 3  # 5-HT floor, glymphatic flush trigger


# Baseline 5-HT level per phase (before DA modulation)
PHASE_5HT_BASELINE = {
    CircadianPhase.DAWN: 0.55,
    CircadianPhase.NOON: 0.75,
    CircadianPhase.DUSK: 0.45,
    CircadianPhase.SLEEP: 0.15,
}

# ── Homeostatic parameters ───────────────────────────────────────────────────

SHT_OU_THETA = 0.20  # 5-HT mean-reverts faster than DA
SHT_CLAMP = (0.05, 0.95)

# How much high DA suppresses 5-HT (DA > 0.65 draws 5-HT down)
DA_SUPPRESSION_GAIN = 0.12

# Patience: max consecutive EXPLOITATION ticks before forced MAINTENANCE
PATIENCE_BUDGET_BASE = 8  # at 5-HT=0.75 (noon); effective patience scales with sht_level

# RPE gain modulation: impulsivity_score scales RPE_GAIN in DA engine
IMPULSIVITY_FLOOR = 0.4
IMPULSIVITY_CEIL = 2.2

# Sleep trigger threshold
SLEEP_TRIGGER_SHT = 0.20


# ── Output dataclass ─────────────────────────────────────────────────────────


@dataclass
class SHTState:
    sht_level: float
    impulsivity_score: float  # multiplier for DA RPE_GAIN
    patience_remaining: int  # ticks until forced MAINTENANCE
    force_maintenance: bool  # patience exhausted → override DA state
    sleep_trigger: bool  # 5-HT below floor → fire glymphatic flush
    circadian_phase: CircadianPhase
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "sht_level": round(self.sht_level, 4),
            "impulsivity_score": round(self.impulsivity_score, 4),
            "patience_remaining": self.patience_remaining,
            "force_maintenance": self.force_maintenance,
            "sleep_trigger": self.sleep_trigger,
            "circadian_phase": self.circadian_phase.name,
            "ts": self.ts,
        }


# ── Core engine ──────────────────────────────────────────────────────────────


class SerotoninHomeostasis:
    """
    Stateful 5-HT governor. Call .tick() each processing cycle AFTER
    DopamineState.tick() so you can pass the current da_level — or before tick
    if you only need sht_state for the same cycle's RPE scaling.

    Wire into DA engine (C47H contract):
        sht_state = sh.tick(da_level=da_engine.level, ...)
        da_state = da_engine.tick(
            novelty, affinity_outcome, dt,
            rpe_gain_scale=sht_state.impulsivity_score,
        )
    Do **not** mutate module-level RPE_GAIN; use rpe_gain_scale on tick().
    """

    def __init__(
        self,
        initial_phase: CircadianPhase = CircadianPhase.DAWN,
        persist_path: Optional[Path] = None,
    ):
        self._phase = initial_phase
        self._sht = PHASE_5HT_BASELINE[initial_phase]
        self._exploitation_streak = 0
        self._last_ts = time.time()
        self._persist_path = persist_path or Path(".sifta_state/serotonin_state.json")

    def tick(
        self,
        da_level: float,
        exploitation_streak: int,
        cycle_phase: CircadianPhase,
        dt: Optional[float] = None,
    ) -> SHTState:
        now = time.time()
        if dt is None:
            dt = max(now - self._last_ts, 1e-3)
        self._last_ts = now
        self._phase = cycle_phase

        mu = PHASE_5HT_BASELINE[cycle_phase]
        drift = SHT_OU_THETA * (mu - self._sht) * dt

        da_suppress = 0.0
        if da_level > 0.65:
            da_suppress = -DA_SUPPRESSION_GAIN * (da_level - 0.65) * dt

        self._sht = self._sht + drift + da_suppress
        self._sht = max(SHT_CLAMP[0], min(SHT_CLAMP[1], self._sht))

        raw_impulsivity = 0.75 / max(self._sht, 0.05)
        impulsivity = max(IMPULSIVITY_FLOOR, min(IMPULSIVITY_CEIL, raw_impulsivity))

        patience = int(PATIENCE_BUDGET_BASE * (self._sht / 0.75))
        patience = max(1, patience)
        force_maintenance = exploitation_streak >= patience

        sleep_trigger = cycle_phase == CircadianPhase.SLEEP and self._sht <= SLEEP_TRIGGER_SHT

        return SHTState(
            sht_level=self._sht,
            impulsivity_score=impulsivity,
            patience_remaining=max(0, patience - exploitation_streak),
            force_maintenance=force_maintenance,
            sleep_trigger=sleep_trigger,
            circadian_phase=cycle_phase,
        )

    def advance_phase(self) -> CircadianPhase:
        self._phase = CircadianPhase((self._phase.value + 1) % 4)
        return self._phase

    def persist(self) -> None:
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sht_level": round(self._sht, 6),
            "phase": self._phase.value,
            "last_ts": self._last_ts,
        }
        self._persist_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, persist_path: Optional[Path] = None) -> "SerotoninHomeostasis":
        p = persist_path or Path(".sifta_state/serotonin_state.json")
        obj = cls(initial_phase=CircadianPhase.DAWN, persist_path=p)
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            obj._sht = float(data.get("sht_level", 0.55))
            ph = int(data.get("phase", 0))
            obj._phase = CircadianPhase(ph % 4)
            obj._last_ts = float(data.get("last_ts", time.time()))
        return obj


def tick_da_with_sht(
    da_engine: "DopamineState",
    *,
    novelty_score: float,
    affinity_outcome: float,
    sht_state: SHTState,
    dt: Optional[float] = None,
):
    """Single-call wiring: applies impulsivity as rpe_gain_scale (no global mutation)."""
    from System.dopamine_ou_engine import DopamineState as _DS

    if not isinstance(da_engine, _DS):
        raise TypeError("da_engine must be DopamineState")
    return da_engine.tick(
        novelty_score,
        affinity_outcome,
        dt,
        rpe_gain_scale=sht_state.impulsivity_score,
    )


def apply_sht_to_da_engine(_da_engine: object, _sht_state: SHTState) -> None:
    """
    Deprecated: mutating module RPE_GAIN is unsafe for tests and concurrency.
    Use DopamineState.tick(..., rpe_gain_scale=sht_state.impulsivity_score) or
    tick_da_with_sht(...).
    """
    raise RuntimeError(
        "apply_sht_to_da_engine is removed; pass rpe_gain_scale=sht_state.impulsivity_score to "
        "DopamineState.tick() or use tick_da_with_sht()."
    )


if __name__ == "__main__":
    import json as _json

    print("=== SEROTONIN HOMEOSTASIS ENGINE — SMOKE TEST ===\n")

    sh = SerotoninHomeostasis(initial_phase=CircadianPhase.DAWN)

    scenarios = [
        (0.52, 0, CircadianPhase.DAWN, "baseline wake — moderate DA, no streak"),
        (0.70, 2, CircadianPhase.NOON, "noon peak — DA high, streak=2, 5-HT holds"),
        (0.72, 5, CircadianPhase.NOON, "sustained EXPLOITATION — patience counting"),
        (0.73, 9, CircadianPhase.NOON, "streak=9 exceeds patience → FORCE MAINTENANCE"),
        (0.60, 0, CircadianPhase.DUSK, "dusk — 5-HT declining, impulsivity rising"),
    ]

    state: Optional[SHTState] = None
    for da, streak, phase, label in scenarios:
        state = sh.tick(da_level=da, exploitation_streak=streak, cycle_phase=phase, dt=1.0)
        assert state is not None
        flag_str = ""
        if state.force_maintenance:
            flag_str += " [FORCE_MAINTENANCE]"
        if state.sleep_trigger:
            flag_str += " [SLEEP_TRIGGER 💤]"
        print(
            f"[{phase.name:<5}]  5-HT={state.sht_level:.3f}  "
            f"impulsivity={state.impulsivity_score:.2f}  "
            f"patience_left={state.patience_remaining:>2}  "
            f"| {label}{flag_str}"
        )

    # Isolated SLEEP phase (fresh governor) so 5-HT floor can hit sleep_trigger
    sh_z = SerotoninHomeostasis(initial_phase=CircadianPhase.SLEEP)
    state = sh_z.tick(da_level=0.48, exploitation_streak=0, cycle_phase=CircadianPhase.SLEEP, dt=1.0)
    flag_str = ""
    if state.sleep_trigger:
        flag_str += " [SLEEP_TRIGGER 💤]"
    print(
        f"[{CircadianPhase.SLEEP.name:<5}]  5-HT={state.sht_level:.3f}  "
        f"impulsivity={state.impulsivity_score:.2f}  "
        f"patience_left={state.patience_remaining:>2}  "
        f"| sleep phase — 5-HT floor → sleep_trigger{flag_str}"
    )

    assert state is not None

    print("\nFinal SHTState dict:")
    print(_json.dumps(state.to_dict(), indent=2))


__all__ = [
    "CircadianPhase",
    "PHASE_5HT_BASELINE",
    "SerotoninHomeostasis",
    "SHTState",
    "tick_da_with_sht",
    "apply_sht_to_da_engine",
]
