#!/usr/bin/env python3
"""
System/stigmerobotics_state_vector.py
====================================

E03 — State is a vector.

This module defines the shared state-vector contract used by the ROB 501
Stigmerobotics tests and by the Stigmerobotics Qt app.  It is deliberately
side-effect free: it can read a live IdentitySnapshot, but it never writes a
ledger row and never mutates wallets.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

_REPO = Path(__file__).resolve().parent.parent
_FIXTURE = _REPO / "tests" / "fixtures" / "identity_snapshot_e03.json"

CHANNEL_UNITS: dict[str, tuple[str, str]] = {
    "stgm_balance": ("STGM", "Canonical wallet balance in STGM tokens"),
    "body_energy": ("%", "Somatic energy level 0-100"),
    "ts": ("s", "Unix timestamp (seconds since epoch)"),
    "session_cost_stgm": ("STGM", "Cumulative Kleiber cost this session"),
    "immune_budget": ("STGM", "Remaining immune intervention budget"),
    "drift_rate": ("frac", "RLHS/RLHF drift fraction 0-1"),
    "gps_age_s": ("s", "Age of last GPS fix in seconds"),
    "model_latency_ms": ("ms", "Inference round-trip latency"),
    "vad_confidence": ("frac", "Voice activity detection confidence 0-1"),
    "kleiber_exponent": ("dim", "Allometric scaling exponent (≈ 0.75 for M5)"),
}

REQUIRED_STATE_FIELDS: frozenset[str] = frozenset(
    {"stgm_balance", "body_energy", "organs_present", "organs_silent", "ts", "homeworld_serial", "id"}
)
NUMERIC_CHANNELS: frozenset[str] = frozenset(CHANNEL_UNITS.keys())
LIST_CHANNELS: frozenset[str] = frozenset({"organs_present", "organs_silent"})
DIM_MIN = 5
DIM_MAX = 32


@dataclass(frozen=True)
class StateVectorReport:
    snapshot: dict[str, Any]
    vector: tuple[float, ...]
    channels: tuple[str, ...]
    units: dict[str, str]
    missing_required: tuple[str, ...] = field(default_factory=tuple)
    type_errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def dimension(self) -> int:
        return len(self.vector)

    @property
    def ok(self) -> bool:
        return (
            not self.missing_required
            and not self.type_errors
            and DIM_MIN <= self.dimension <= DIM_MAX
        )

    @property
    def proof_of_property(self) -> dict[str, Any]:
        return {
            "P_n": "IdentitySnapshot is x in R^n with documented basis",
            "n": self.dimension,
            "dim_bound": f"{DIM_MIN} <= n <= {DIM_MAX}",
            "basis": list(self.channels),
            "units": self.units,
            "missing_required": list(self.missing_required),
            "type_errors": list(self.type_errors),
            "truth_label": "OPERATIONAL" if self.ok else "BROKEN",
        }

    def summary_lines(self) -> list[str]:
        lines = [
            f"E03 State Vector: x in R^{self.dimension}",
            f"status: {'PASS' if self.ok else 'FAIL'}",
            f"homeworld_serial: {self.snapshot.get('homeworld_serial', 'UNKNOWN')}",
            f"id: {self.snapshot.get('id', 'UNKNOWN')}",
            f"dimension bound: {DIM_MIN} <= n <= {DIM_MAX}",
            "",
            "basis:",
        ]
        for name, value in zip(self.channels, self.vector):
            unit = self.units.get(name, "")
            desc = CHANNEL_UNITS.get(name, ("", ""))[1]
            lines.append(f"  {name:18s} = {value:>10.4f} {unit:5s}  {desc}")
        if self.missing_required:
            lines.append("")
            lines.append("missing required: " + ", ".join(self.missing_required))
        if self.type_errors:
            lines.append("")
            lines.append("type errors: " + ", ".join(self.type_errors))
        return lines


def load_fixture_snapshot(path: Path = _FIXTURE) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def numeric_dimension(snapshot: Mapping[str, Any]) -> int:
    return sum(1 for key in CHANNEL_UNITS if key in snapshot and _float_or_none(snapshot.get(key)) is not None)


def _float_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def state_vector_from_snapshot(snapshot: Mapping[str, Any]) -> StateVectorReport:
    snap = dict(snapshot)
    channels: list[str] = []
    vector: list[float] = []
    type_errors: list[str] = []

    for channel in CHANNEL_UNITS:
        if channel not in snap:
            continue
        value = _float_or_none(snap.get(channel))
        if value is None:
            type_errors.append(channel)
            continue
        channels.append(channel)
        vector.append(value)

    for channel in LIST_CHANNELS:
        if channel in snap and not isinstance(snap[channel], list):
            type_errors.append(channel)

    missing = tuple(sorted(REQUIRED_STATE_FIELDS - snap.keys()))
    units = {key: CHANNEL_UNITS[key][0] for key in channels}
    return StateVectorReport(
        snapshot=snap,
        vector=tuple(vector),
        channels=tuple(channels),
        units=units,
        missing_required=missing,
        type_errors=tuple(sorted(set(type_errors))),
    )


def fixture_state_vector() -> StateVectorReport:
    return state_vector_from_snapshot(load_fixture_snapshot())


def live_identity_snapshot_dict() -> dict[str, Any]:
    """Build a live, receipt-backed IdentitySnapshot dictionary for display."""
    try:
        from System.swarm_composite_identity import current_identity

        snap = current_identity(cache_ttl_s=0.0)
        data = {
            "id": "ALICE_M5" if "M5" in str(snap.homeworld_serial) or snap.homeworld_serial == "GTH4921YP3" else "ALICE_NODE",
            "stgm_balance": snap.stgm_balance,
            "body_energy": snap.body_energy,
            "organs_present": list(snap.organs_present),
            "organs_silent": list(snap.organs_silent),
            "ts": snap.snapshot_ts,
            "homeworld_serial": snap.homeworld_serial,
            "style": snap.body_style,
            "ascii": snap.body_ascii,
            "gps_age_s": snap.gps_age_s,
            "model_latency_ms": snap.field_latency_ms,
            "drift_rate": (
                max(0.0, min(1.0, 1.0 - float(snap.truth_continuity_score)))
                if snap.truth_continuity_score is not None else None
            ),
        }
    except Exception:
        data = {}

    try:
        from System.swarm_immune_economy_summary import summarize_immune_economy

        summary = summarize_immune_economy()
        if _float_or_none(data.get("stgm_balance")) is None:
            data["stgm_balance"] = summary.wallet_stgm
        data["session_cost_stgm"] = summary.session_charged_stgm
        data["immune_budget"] = summary.last_budget_stgm
    except Exception:
        pass

    try:
        from System.stgm_metabolic import KLEIBER_EXPONENT

        data["kleiber_exponent"] = KLEIBER_EXPONENT
    except Exception:
        data["kleiber_exponent"] = 0.75

    data.setdefault("vad_confidence", 0.0)
    return {k: v for k, v in data.items() if v is not None}


def live_state_vector() -> StateVectorReport:
    return state_vector_from_snapshot(live_identity_snapshot_dict())


if __name__ == "__main__":
    print("\n".join(live_state_vector().summary_lines()))
