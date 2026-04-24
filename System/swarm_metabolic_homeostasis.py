#!/usr/bin/env python3
"""
System/swarm_metabolic_homeostasis.py
══════════════════════════════════════════════════════════════════════
Concept: Metabolic Budget Homeostasis — finite energy governance.

Biocode translation:
  - Dynamic Energy Budget theory: organisms maintain reserve/structure pools
    and allocate finite energy across maintenance, growth, and action
    (Kooijman; "Dynamic energy budget theory restores coherence in biology").
  - Allostasis: stability is maintained by anticipatory resource allocation,
    but repeated strain accumulates cost (Sterling & Eyer; McEwen).
  - Active inference with thermodynamic cost: information processing is
    bounded by real energy flow, not just statistical free energy
    (Fields et al., Entropy 2024).
  - Harvester ants: colony foraging is closed-loop and budgeted by returning
    forager feedback; outgoing work is throttled when energetic conditions are
    poor (Prabhakar et al., PLOS Comp Biol 2012; 2019 closed-loop model).

This organ does not replace existing ledgers. It reads:
  - api_metabolism.jsonl through SwarmApiMetabolism.daily_burn()
  - metabolic_ledger.jsonl through metabolic_budget.ledger_total()
  - STGM state supplied by callers or scanned from warren_buffett

It outputs a bounded pressure score and a budget multiplier that callers can
use before expensive inference, cloud calls, or mutation bursts.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from System.canonical_schemas import assert_payload_keys
from System.jsonl_file_lock import append_line_locked

MODULE_VERSION = "2026-04-24.metabolic-homeostasis.v1"
SCHEMA = "SIFTA_METABOLIC_HOMEOSTASIS_V1"

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = _REPO / ".sifta_state" / "metabolic_homeostasis.jsonl"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class MetabolicHomeostasisConfig:
    daily_usd_limit: float = 10.0
    local_unit_limit_24h: float = 200.0
    stgm_reserve_target: float = 100.0
    stgm_floor: float = 10.0
    emergency_multiplier_floor: float = 0.2
    yellow_pressure: float = 0.45
    red_pressure: float = 0.75
    critical_pressure: float = 0.92
    rest_base_seconds: float = 30.0
    rest_max_seconds: float = 900.0

    def __post_init__(self) -> None:
        if self.daily_usd_limit <= 0.0:
            raise ValueError("daily_usd_limit must be positive")
        if self.local_unit_limit_24h <= 0.0:
            raise ValueError("local_unit_limit_24h must be positive")
        if self.stgm_reserve_target <= 0.0:
            raise ValueError("stgm_reserve_target must be positive")
        if self.stgm_floor < 0.0:
            raise ValueError("stgm_floor must be non-negative")
        if self.stgm_floor >= self.stgm_reserve_target:
            raise ValueError("stgm_floor must be below stgm_reserve_target")
        if not 0.0 <= self.emergency_multiplier_floor <= 1.0:
            raise ValueError("emergency_multiplier_floor must be in [0, 1]")
        if not 0.0 <= self.yellow_pressure < self.red_pressure < self.critical_pressure <= 1.0:
            raise ValueError("pressure thresholds must be ordered in [0, 1]")
        if self.rest_base_seconds < 0.0:
            raise ValueError("rest_base_seconds must be non-negative")
        if self.rest_max_seconds < self.rest_base_seconds:
            raise ValueError("rest_max_seconds must be >= rest_base_seconds")


@dataclass(frozen=True)
class MetabolicState:
    usd_burn_24h: float = 0.0
    local_units_24h: float = 0.0
    stgm_balance: float = 0.0

    def __post_init__(self) -> None:
        for name in ("usd_burn_24h", "local_units_24h", "stgm_balance"):
            value = float(getattr(self, name))
            if value != value or value in (float("inf"), float("-inf")):
                raise ValueError(f"{name} must be finite")
        if self.usd_burn_24h < 0.0:
            raise ValueError("usd_burn_24h must be non-negative")
        if self.local_units_24h < 0.0:
            raise ValueError("local_units_24h must be non-negative")


class MetabolicHomeostat:
    """Budget governor for a human-in-the-loop stigmergic superorganism."""

    def __init__(self, cfg: Optional[MetabolicHomeostasisConfig] = None) -> None:
        self.cfg = cfg or MetabolicHomeostasisConfig()

    def pressure_components(self, state: MetabolicState) -> Dict[str, float]:
        usd_pressure = _clamp01(state.usd_burn_24h / self.cfg.daily_usd_limit)
        local_pressure = _clamp01(state.local_units_24h / self.cfg.local_unit_limit_24h)
        reserve_span = self.cfg.stgm_reserve_target - self.cfg.stgm_floor
        stgm_pressure = _clamp01((self.cfg.stgm_reserve_target - state.stgm_balance) / reserve_span)
        return {
            "usd": usd_pressure,
            "local": local_pressure,
            "stgm": stgm_pressure,
        }

    def pressure(self, state: MetabolicState) -> float:
        parts = self.pressure_components(state)
        # Real wallet burn is dominant; local ATP and STGM reserve still matter.
        pressure = 0.45 * parts["usd"] + 0.25 * parts["local"] + 0.30 * parts["stgm"]
        if state.stgm_balance < 0.0:
            pressure = max(pressure, self.cfg.red_pressure)
        elif state.stgm_balance < self.cfg.stgm_floor:
            pressure = max(pressure, self.cfg.yellow_pressure)
        return _clamp01(pressure)

    def mode(self, pressure: float) -> str:
        if pressure >= self.cfg.critical_pressure:
            return "CRITICAL_STARVATION"
        if pressure >= self.cfg.red_pressure:
            return "RED_CONSERVE"
        if pressure >= self.cfg.yellow_pressure:
            return "YELLOW_THROTTLE"
        return "GREEN_GROW"

    def budget_multiplier(self, pressure: float, *, emergency: bool = False) -> float:
        if emergency:
            return max(self.cfg.emergency_multiplier_floor, 1.0 - 0.5 * _clamp01(pressure))
        return max(0.0, 1.0 - _clamp01(pressure))

    def rest_seconds(self, pressure: float, *, emergency: bool = False) -> float:
        if emergency or pressure < self.cfg.red_pressure:
            return 0.0
        span = max(1.0 - self.cfg.red_pressure, 1e-9)
        severity = _clamp01((pressure - self.cfg.red_pressure) / span)
        return round(self.cfg.rest_base_seconds + severity * (self.cfg.rest_max_seconds - self.cfg.rest_base_seconds), 3)

    def allowed_external_usd(self, state: MetabolicState, *, emergency: bool = False) -> float:
        remaining = max(0.0, self.cfg.daily_usd_limit - state.usd_burn_24h)
        return remaining * self.budget_multiplier(self.pressure(state), emergency=emergency)

    def allowed_local_units(self, state: MetabolicState, *, emergency: bool = False) -> float:
        remaining = max(0.0, self.cfg.local_unit_limit_24h - state.local_units_24h)
        return remaining * self.budget_multiplier(self.pressure(state), emergency=emergency)

    def should_spend(
        self,
        state: MetabolicState,
        *,
        external_usd_cost: float = 0.0,
        local_unit_cost: float = 0.0,
        expected_value: float = 0.0,
        emergency: bool = False,
    ) -> Dict[str, Any]:
        if external_usd_cost < 0.0 or local_unit_cost < 0.0:
            raise ValueError("costs must be non-negative")
        p = self.pressure(state)
        multiplier = self.budget_multiplier(p, emergency=emergency)
        allowed_usd = self.allowed_external_usd(state, emergency=emergency)
        allowed_local = self.allowed_local_units(state, emergency=emergency)
        rest = self.rest_seconds(p, emergency=emergency)
        must_rest = rest > 0.0 and not emergency
        value_gate = expected_value >= p or emergency
        allowed = (
            not must_rest
            and external_usd_cost <= allowed_usd
            and local_unit_cost <= allowed_local
            and value_gate
        )
        return {
            "allowed": bool(allowed),
            "pressure": round(p, 6),
            "mode": self.mode(p),
            "budget_multiplier": round(multiplier, 6),
            "allowed_external_usd": round(allowed_usd, 6),
            "allowed_local_units": round(allowed_local, 6),
            "must_rest": bool(must_rest),
            "rest_seconds": rest,
            "reason": "allow" if allowed else ("rest_cycle_required" if must_rest else "metabolic_throttle"),
        }

    def recommendation(self, state: MetabolicState) -> str:
        p = self.pressure(state)
        mode = self.mode(p)
        if mode == "CRITICAL_STARVATION":
            return "halt_nonessential_cloud_calls_rotate_ledgers_and_repair_revenue"
        if mode == "RED_CONSERVE":
            return "local_only_unless_emergency_and_prioritize_stgm_positive_work"
        if mode == "YELLOW_THROTTLE":
            return "prefer_local_models_batch_expensive_calls_and_watch_wallet"
        return "growth_allowed_keep_accounting"

    def build_ledger_row(self, state: MetabolicState, *, ts: Optional[float] = None) -> Dict[str, Any]:
        p = self.pressure(state)
        row: Dict[str, Any] = {
            "event": "metabolic_homeostasis",
            "schema": SCHEMA,
            "module_version": MODULE_VERSION,
            "pressure": round(p, 6),
            "mode": self.mode(p),
            "budget_multiplier": round(self.budget_multiplier(p), 6),
            "must_rest": bool(self.rest_seconds(p) > 0.0),
            "rest_seconds": self.rest_seconds(p),
            "allowed_external_usd": round(self.allowed_external_usd(state), 6),
            "allowed_local_units": round(self.allowed_local_units(state), 6),
            "usd_burn_24h": round(float(state.usd_burn_24h), 6),
            "local_units_24h": round(float(state.local_units_24h), 6),
            "stgm_balance": round(float(state.stgm_balance), 6),
            "recommendation": self.recommendation(state),
            "ts": float(time.time() if ts is None else ts),
        }
        assert_payload_keys("metabolic_homeostasis.jsonl", row, strict=True)
        return row

    def append_ledger_row(
        self,
        state: MetabolicState,
        *,
        ledger_path: Path = _LEDGER,
        ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        row = self.build_ledger_row(state, ts=ts)
        append_line_locked(ledger_path, json.dumps(row, sort_keys=True) + "\n")
        return row

    @classmethod
    def sample_live(cls, cfg: Optional[MetabolicHomeostasisConfig] = None) -> MetabolicState:
        usd = 0.0
        local = 0.0
        stgm = 0.0
        try:
            from System.swarm_api_metabolism import SwarmApiMetabolism

            usd = float(SwarmApiMetabolism(daily_usd_limit=(cfg or MetabolicHomeostasisConfig()).daily_usd_limit).daily_burn())
        except Exception:
            usd = 0.0
        try:
            from System.metabolic_budget import ledger_total

            totals: Mapping[str, float] = ledger_total(since_ts=time.time() - 86400.0)
            local = float(sum(totals.values()))
        except Exception:
            local = 0.0
        try:
            from System.warren_buffett import profit_report

            report = profit_report()
            stgm = float(report.get("net_minted_estimate", report.get("net_stgm", 0.0)))
        except Exception:
            stgm = 0.0
        return MetabolicState(usd_burn_24h=usd, local_units_24h=local, stgm_balance=stgm)


def proof_of_property() -> Dict[str, bool]:
    print("\n=== SIFTA METABOLIC HOMEOSTASIS : JUDGE VERIFICATION ===")
    homeostat = MetabolicHomeostat(
        MetabolicHomeostasisConfig(
            daily_usd_limit=10.0,
            local_unit_limit_24h=100.0,
            stgm_reserve_target=100.0,
            stgm_floor=10.0,
        )
    )
    healthy = MetabolicState(usd_burn_24h=1.0, local_units_24h=10.0, stgm_balance=150.0)
    strained = MetabolicState(usd_burn_24h=9.0, local_units_24h=90.0, stgm_balance=5.0)
    critical = MetabolicState(usd_burn_24h=12.0, local_units_24h=140.0, stgm_balance=0.0)

    p_healthy = homeostat.pressure(healthy)
    p_strained = homeostat.pressure(strained)
    p_critical = homeostat.pressure(critical)
    print(f"[P1] pressure gradient: {p_healthy:.3f} -> {p_strained:.3f} -> {p_critical:.3f}")
    pressure_orders = p_healthy < p_strained < p_critical

    normal = homeostat.should_spend(strained, external_usd_cost=0.25, local_unit_cost=2.0, expected_value=0.2)
    emergency = homeostat.should_spend(
        strained,
        external_usd_cost=0.25,
        local_unit_cost=2.0,
        expected_value=0.2,
        emergency=True,
    )
    print(f"[P2] normal_allowed={normal['allowed']} emergency_allowed={emergency['allowed']}")
    throttles_low_value = normal["allowed"] is False and emergency["allowed"] is True

    row = homeostat.build_ledger_row(critical, ts=1.0)
    print(f"[P3] ledger mode={row['mode']} recommendation={row['recommendation']}")
    canonical_row = row["mode"] == "CRITICAL_STARVATION" and row["budget_multiplier"] == 0.0

    ok = pressure_orders and throttles_low_value and canonical_row
    return {
        "ok": ok,
        "pressure_orders": pressure_orders,
        "throttles_low_value": throttles_low_value,
        "canonical_row": canonical_row,
    }


__all__ = [
    "MetabolicHomeostasisConfig",
    "MetabolicHomeostat",
    "MetabolicState",
    "proof_of_property",
]


if __name__ == "__main__":
    result = proof_of_property()
    if not result["ok"]:
        raise SystemExit(1)
