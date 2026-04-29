#!/usr/bin/env python3
"""
System/swarm_drive_hypothalamus.py — Goal / Drive (Hypothalamus)

Homeostatic pressure over *which* goals matter, not whether an action is
permitted (intent) or socially owned (Agency Binder). Animals do not “think”
the hypothalamus; it biases the rest of the stack toward survival, contact,
exploration, and caution.

Doctrine (Architect):
    No action without intent → intent provenance / effectors
    No intent without ownership → Agency Binder
    No ownership without drive → this organ sets *why now* pressure

See: Documents/IDE_BOOT_COVENANT.md (receipts, proof-bearing state)

Downstream (intended wiring):
    Drive → dopamine / TD tone → basal ganglia priors → effector
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

_REPO = Path(__file__).resolve().parent.parent

# Match System/swarm_action_selector.py — additive priors before softmax.
try:
    from System.swarm_action_selector import ALL_ACTIONS
except ImportError:  # minimal test / partial checkout
    ALL_ACTIONS = ("SILENCE", "TOOL", "ENGAGE", "BOND")


def _clamp(x: float, lo: float = 0.0, hi: float = 2.0) -> float:
    return max(lo, min(hi, float(x)))


def _boolish(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return bool(v)


def metabolic_sufficiency(metabolic_state: Any) -> float:
    """
    Normalize metabolic input to [0, 1] “how full / safe is energy budget”.

    Accepts:
      - float in [0, 1]  (fraction full, e.g. SwarmMetabolicEngine.energy_fraction())
      - dict with ``energy_pct`` (0–100) or ``energy_fraction`` or ``energy`` / ``max_energy``
    """
    if isinstance(metabolic_state, dict):
        if "energy_fraction" in metabolic_state:
            return _clamp(float(metabolic_state["energy_fraction"]), 0.0, 1.0)
        ep = metabolic_state.get("energy_pct")
        if ep is not None:
            return _clamp(float(ep) / 100.0, 0.0, 1.0)
        e = metabolic_state.get("energy")
        mx = metabolic_state.get("max_energy")
        if e is not None and mx:
            try:
                return _clamp(float(e) / float(mx), 0.0, 1.0)
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        return 0.5
    try:
        return _clamp(float(metabolic_state), 0.0, 1.0)
    except (TypeError, ValueError):
        return 0.5


@dataclass
class DriveSnapshot:
    ts: float
    drives: Dict[str, float]
    dominant: str
    metabolic_sufficiency: float
    recent_events_summary: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DriveHypothalamus:
    """
    Multi-axis drive pressures (hypothalamus-style). ``update`` is reactive;
    ``dominant_drive`` picks the loudest axis for policy hints.
    """

    def __init__(
        self,
        *,
        initial: Optional[Mapping[str, float]] = None,
        curiosity_cap: float = 2.0,
        curiosity_tick: float = 0.01,
    ) -> None:
        self.drives: Dict[str, float] = {
            "energy": 1.0,
            "social": 0.5,
            "curiosity": 0.5,
            "safety": 1.0,
        }
        if initial:
            for k, v in initial.items():
                if k in self.drives:
                    hi = curiosity_cap if k == "curiosity" else 2.0
                    self.drives[k] = _clamp(float(v), 0.0, hi)
        self._curiosity_cap = curiosity_cap
        self._curiosity_tick = curiosity_tick
        self._last_summary: Dict[str, Any] = {}

    def update(
        self,
        metabolic_state: Any,
        recent_events: Optional[Mapping[str, Any]] = None,
    ) -> DriveSnapshot:
        """
        Pull interoception + short horizon events into drive pressures.

        ``recent_events`` keys (all optional):
          - ``errors`` — bool or count; raises *safety* pressure
          - ``owner_activity`` — bool; raises *social* when the owner is present
          - ``novelty`` — float [0,1]; feeds *curiosity* a bit faster this tick
        """
        ev = dict(recent_events or {})
        suff = metabolic_sufficiency(metabolic_state)

        # Low sufficiency → high energy-seeking pressure (animal: seek food).
        self.drives["energy"] = _clamp(1.5 - suff)

        err = ev.get("errors", False)
        if isinstance(err, bool):
            self.drives["safety"] = 1.0 if err else 0.3
        elif isinstance(err, (int, float)):
            self.drives["safety"] = _clamp(0.35 + 0.9 * min(float(err), 3.0) / 3.0)
        else:
            self.drives["safety"] = 1.0 if _boolish(err) else 0.3

        self.drives["social"] = 1.0 if _boolish(ev.get("owner_activity")) else 0.2

        tick = self._curiosity_tick
        if ev.get("novelty") is not None:
            try:
                tick += 0.02 * _clamp(float(ev["novelty"]), 0.0, 1.0)
            except (TypeError, ValueError):
                pass
        self.drives["curiosity"] = _clamp(self.drives["curiosity"] + tick, 0.0, self._curiosity_cap)

        dom = self.dominant_drive()
        self._last_summary = {
            "errors": ev.get("errors"),
            "owner_activity": ev.get("owner_activity"),
            "novelty": ev.get("novelty"),
        }
        return DriveSnapshot(
            ts=time.time(),
            drives=dict(self.drives),
            dominant=dom,
            metabolic_sufficiency=suff,
            recent_events_summary=dict(self._last_summary),
        )

    def dominant_drive(self) -> str:
        return max(self.drives, key=lambda k: self.drives[k])

    def basal_ganglia_score_deltas(self) -> Dict[str, float]:
        """
        Small additive shifts for C1 / basal ganglia logits (before softmax).

        Energy pressure favors rest / low burn; social favors engagement;
        curiosity favors tools / exploration; safety favors silence / bond.
        """
        e = self.drives["energy"]
        s = self.drives["social"]
        c = self.drives["curiosity"]
        f = self.drives["safety"]

        deltas = {a: 0.0 for a in ALL_ACTIONS}
        # Magnitudes kept modest so classifier scores stay primary.
        deltas["SILENCE"] += 0.06 * e + 0.05 * f - 0.02 * s
        deltas["TOOL"] += 0.05 * c - 0.03 * e - 0.02 * f
        deltas["ENGAGE"] += 0.06 * s - 0.03 * e
        deltas["BOND"] += 0.04 * s + 0.03 * f - 0.02 * c
        return deltas

    def append_ledger(self, snap: DriveSnapshot, state_dir: Optional[Path] = None) -> Path:
        """Optional append-only trace under ``.sifta_state`` (proof-bearing)."""
        root = Path(state_dir) if state_dir is not None else _REPO / ".sifta_state"
        root.mkdir(parents=True, exist_ok=True)
        path = root / "drive_hypothalamus.jsonl"
        line = json.dumps(snap.as_dict(), separators=(",", ":"), sort_keys=True) + "\n"
        try:
            from System.jsonl_file_lock import append_line_locked

            append_line_locked(path, line)
        except ImportError:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)
        return path
