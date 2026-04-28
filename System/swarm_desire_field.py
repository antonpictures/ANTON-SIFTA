#!/usr/bin/env python3
"""
System/swarm_desire_field.py
══════════════════════════════════════════════════════════════════════
Event89 — Desire Field.

This organ turns live body state into a bounded attention drive. It does
not claim emotion or consciousness. It computes an auditable control signal:

    desire = reward_prediction × energy_need × uncertainty/exploration

The result can bias camera attention without hardcoding "owner always wins."
Owner evidence is treated as a learned high-value cue, while novelty and
uncertainty keep exploration alive.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if out != out or out in (float("inf"), float("-inf")):
            return default
        return out
    except Exception:
        return default


def _latest_jsonl(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 65536))
            raw = handle.read().decode("utf-8", "replace")
    except OSError:
        return None
    latest: Optional[dict[str, Any]] = None
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            latest = row
    return latest


@dataclass(frozen=True)
class DesireContext:
    """Live body state that modulates attention."""

    stgm_balance: float = 0.0
    metabolic_pressure: float = 0.5
    reward_net: float = 0.0
    reward_events: int = 0
    source: str = "neutral"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DesireSnapshot:
    """Computed drive and camera-role bias."""

    desire: float
    owner_value: float
    energy_need: float
    reward_prediction: float
    uncertainty: float
    exploration: float
    close_owner_drive: float
    room_patrol_drive: float
    preferred_role: str
    reasons: list[str]
    context: DesireContext

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["context"] = self.context.as_dict()
        return out


def load_live_desire_context(state_dir: Path | str = _STATE) -> DesireContext:
    """Read live economy/reward ledgers without mutating state."""

    state = Path(state_dir)
    stgm_balance = 0.0
    metabolic_pressure = 0.5
    source = "fallback"

    metabolic = _latest_jsonl(state / "metabolic_homeostasis.jsonl")
    if metabolic and time.time() - _float(metabolic.get("ts"), 0.0) <= 300.0:
        stgm_balance = _float(metabolic.get("stgm_balance"), 0.0)
        metabolic_pressure = _clamp(_float(metabolic.get("pressure"), 0.5))
        source = "metabolic_homeostasis"
    else:
        try:
            from System.stgm_economy import scan_economy

            economy = scan_economy().as_dict()
            stgm_balance = _float(economy.get("canonical_wallet_sum"), 0.0)
            # Wallet reserve pressure only. The full metabolic organ can
            # overwrite this when its own live ledger is fresh.
            metabolic_pressure = _clamp((100.0 - stgm_balance) / 90.0)
            source = "stgm_economy"
        except Exception:
            pass

    reward_net = 0.0
    reward_events = 0
    try:
        from System.dopamine_reward_loop import scan_reward_history

        reward = scan_reward_history(lookback_hours=24.0)
        reward_net = _float(reward.get("net_reward"), 0.0)
        reward_events = int(reward.get("reward_events", 0) or 0)
    except Exception:
        pass

    return DesireContext(
        stgm_balance=round(stgm_balance, 4),
        metabolic_pressure=round(metabolic_pressure, 4),
        reward_net=round(reward_net, 4),
        reward_events=reward_events,
        source=source,
    )


def compute_sensor_desire(
    *,
    owner_detected: float,
    unknown_signal: float = 0.0,
    environment_signal: float = 0.0,
    attention_stale: float = 0.0,
    context: Optional[DesireContext] = None,
) -> DesireSnapshot:
    """Compute bounded desire and camera bias from normalized live evidence."""

    ctx = context or DesireContext()
    owner = _clamp(owner_detected)
    unknown = _clamp(unknown_signal)
    environment = _clamp(environment_signal)
    stale = _clamp(attention_stale)

    # Energy need increases when metabolic pressure is high or STGM reserve is
    # below the reserve target. It never exceeds 1.
    reserve_need = _clamp((100.0 - ctx.stgm_balance) / 100.0)
    energy_need = _clamp(0.65 * ctx.metabolic_pressure + 0.35 * reserve_need)

    # Reward history changes the learned value of owner contact, but only
    # mildly. This prevents obsession/collapse while still binding owner to
    # expected useful work.
    reward_tone = _clamp((ctx.reward_net + 8.0) / 16.0)
    owner_value = _clamp(0.55 + 0.35 * reward_tone + 0.10 * min(ctx.reward_events, 20) / 20.0)

    uncertainty = max(stale, 1.0 - owner, unknown, environment * 0.7)
    exploration = _clamp(0.55 * (1.0 - owner) + 0.45 * max(unknown, environment))

    reward_prediction = _clamp(
        0.46 * owner * owner_value
        + 0.22 * max(unknown, environment)
        + 0.18 * uncertainty
        + 0.14 * energy_need
    )

    desire = _clamp(reward_prediction * (0.72 + 0.56 * energy_need) + 0.18 * exploration)

    close_owner_drive = _clamp(
        0.60 * owner * owner_value
        + 0.18 * energy_need
        + 0.12 * (1.0 - max(unknown, environment))
        + 0.10 * reward_tone
    )
    room_patrol_drive = _clamp(
        0.40 * (1.0 - owner)
        + 0.30 * max(unknown, environment)
        + 0.18 * stale
        + 0.12 * energy_need
    )
    preferred_role = "close_owner_eye" if close_owner_drive >= room_patrol_drive else "room_patrol_eye"

    reasons = ["desire_field"]
    if owner >= 0.6:
        reasons.append("owner_reward_cue")
    else:
        reasons.append("owner_search")
    if energy_need >= 0.55:
        reasons.append("energy_need")
    if unknown >= 0.25:
        reasons.append("unknown_signal")
    if environment >= 0.25:
        reasons.append("environment_signal")
    if stale >= 0.5:
        reasons.append("attention_stale")
    if exploration >= 0.5:
        reasons.append("exploration_pressure")

    return DesireSnapshot(
        desire=round(desire, 4),
        owner_value=round(owner_value, 4),
        energy_need=round(energy_need, 4),
        reward_prediction=round(reward_prediction, 4),
        uncertainty=round(uncertainty, 4),
        exploration=round(exploration, 4),
        close_owner_drive=round(close_owner_drive, 4),
        room_patrol_drive=round(room_patrol_drive, 4),
        preferred_role=preferred_role,
        reasons=reasons,
        context=ctx,
    )


__all__ = [
    "DesireContext",
    "DesireSnapshot",
    "compute_sensor_desire",
    "load_live_desire_context",
]
