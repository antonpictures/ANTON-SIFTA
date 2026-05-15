#!/usr/bin/env python3
"""
System/stigmerobotics_pheromone_field.py
========================================

E33 - Pheromone field formalisation.

This module treats append-only trace rows as a virtual stigmergic field:
each valid row deposits positive pheromone on a channel, the deposit
evaporates under a positive tau, and same-channel cross-IDE overlap becomes a
collision-risk signal.  It is read-only and side-effect free.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

_REPO = Path(__file__).resolve().parent.parent
_TRACE = _REPO / ".sifta_state" / "ide_stigmergic_trace.jsonl"
_FIXTURE = _REPO / "tests" / "fixtures" / "stigmero_e33_pheromone_good.jsonl"

DEFAULT_TAU_S: dict[str, float] = {
    "LLM_REGISTRATION": 1_800.0,
    "stigmergic_signin": 1_800.0,
    "immune_intervention": 2_400.0,
    "immune_budget_blocked": 2_400.0,
    "WORK_RECEIPT": 3_600.0,
    "SCAR_RECEIPT": 7_200.0,
    "LLM_SIGNOUT": 1_200.0,
    "stigmergic_signout": 1_200.0,
    "stigauth": 3_600.0,
}

DEFAULT_STRENGTH: dict[str, float] = {
    "LLM_REGISTRATION": 0.55,
    "stigmergic_signin": 0.55,
    "immune_intervention": 0.80,
    "immune_budget_blocked": 0.65,
    "WORK_RECEIPT": 0.90,
    "SCAR_RECEIPT": 1.00,
    "LLM_SIGNOUT": 0.45,
    "stigmergic_signout": 0.45,
    "stigauth": 0.75,
}

DEFAULT_OTHER_TAU_S = 900.0
DEFAULT_OTHER_STRENGTH = 0.35
DEFAULT_COLLISION_WINDOW_S = 120.0


@dataclass(frozen=True)
class PheromoneDeposit:
    row_index: int
    ts: float
    kind: str
    source_ide: str
    homeworld_serial: str
    trace_id: str
    channel: str
    tau_s: float
    strength: float
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CollisionSignal:
    left_trace_id: str
    right_trace_id: str
    channel: str
    left_source: str
    right_source: str
    gap_s: float
    risk: float


@dataclass(frozen=True)
class PheromoneFieldReport:
    deposits: tuple[PheromoneDeposit, ...]
    field: dict[str, float]
    field_after_dt: dict[str, float]
    deposit_rate_per_hour: float
    collision_signals: tuple[CollisionSignal, ...]
    violations: tuple[str, ...]
    now_ts: float
    dt_s: float

    @property
    def total_intensity(self) -> float:
        return sum(self.field.values())

    @property
    def total_intensity_after_dt(self) -> float:
        return sum(self.field_after_dt.values())

    @property
    def collision_risk(self) -> float:
        return sum(c.risk for c in self.collision_signals)

    @property
    def evaporation_ok(self) -> bool:
        return self.total_intensity_after_dt <= self.total_intensity + 1e-12

    @property
    def ok(self) -> bool:
        return not self.violations and self.evaporation_ok

    @property
    def proof_of_property(self) -> dict[str, Any]:
        return {
            "P_n": "trace tail is an evaporating pheromone field",
            "deposits": len(self.deposits),
            "tau_table_positive": all(d.tau_s > 0.0 for d in self.deposits),
            "field_nonnegative": all(v >= 0.0 for v in self.field.values()),
            "evaporation": self.total_intensity_after_dt <= self.total_intensity + 1e-12,
            "deposit_rate_per_hour": self.deposit_rate_per_hour,
            "collision_risk": self.collision_risk,
            "violations": list(self.violations),
            "truth_label": "OPERATIONAL" if self.ok else "BROKEN",
        }

    def summary_lines(self) -> list[str]:
        lines = [
            f"E33 Pheromone Field: {'PASS' if self.ok else 'FAIL'}",
            f"deposits: {len(self.deposits)}",
            f"channels: {len(self.field)}",
            f"total_intensity: {self.total_intensity:.6f}",
            f"after_{int(self.dt_s)}s: {self.total_intensity_after_dt:.6f}",
            f"deposit_rate_per_hour: {self.deposit_rate_per_hour:.3f}",
            f"collision_risk: {self.collision_risk:.6f}",
            "",
            "top channels:",
        ]
        for channel, value in sorted(self.field.items(), key=lambda item: item[1], reverse=True)[:8]:
            lines.append(f"  {channel:52s} {value:.6f}")
        if self.collision_signals:
            lines.append("")
            lines.append("collisions:")
            for signal in self.collision_signals[:8]:
                lines.append(
                    f"  {signal.channel} {signal.left_source}->{signal.right_source} "
                    f"gap={signal.gap_s:.1f}s risk={signal.risk:.6f}"
                )
        if self.violations:
            lines.append("")
            lines.append("violations:")
            lines.extend(f"  {v}" for v in self.violations)
        return lines


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            rows.append({"_parse_error": f"line={idx}: {exc}"})
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _payload_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = row.get("payload")
    if isinstance(payload, dict):
        return dict(payload)
    if isinstance(payload, str) and payload.strip().startswith("{"):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _meta_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    meta = row.get("meta")
    return dict(meta) if isinstance(meta, dict) else {}


def _float_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (math.inf, -math.inf):
        return None
    return out


def _trace_id(row: Mapping[str, Any], row_index: int) -> str:
    value = row.get("trace_id")
    if isinstance(value, str) and value:
        return value
    return f"row_{row_index}"


def _channel(row: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    files = payload.get("files_touched") or payload.get("files")
    if isinstance(files, list) and files:
        return "file:" + str(files[0])
    for key in ("path", "hot_surface", "target", "module"):
        value = payload.get(key) or row.get(key)
        if isinstance(value, str) and value:
            return f"{key}:{value}"
    kind = str(row.get("kind") or row.get("event") or "unknown")
    return "kind:" + kind


def _tau_s(row: Mapping[str, Any], kind: str) -> float | None:
    meta = _meta_dict(row)
    override = _float_or_none(meta.get("tau_s"))
    if override is not None:
        return override
    return DEFAULT_TAU_S.get(kind, DEFAULT_OTHER_TAU_S)


def _strength(row: Mapping[str, Any], kind: str) -> float | None:
    meta = _meta_dict(row)
    override = _float_or_none(meta.get("pheromone_strength"))
    if override is not None:
        return override
    return DEFAULT_STRENGTH.get(kind, DEFAULT_OTHER_STRENGTH)


def extract_deposits(rows: Iterable[Mapping[str, Any]]) -> tuple[tuple[PheromoneDeposit, ...], tuple[str, ...]]:
    deposits: list[PheromoneDeposit] = []
    violations: list[str] = []
    for index, row in enumerate(rows):
        if "_parse_error" in row:
            violations.append(f"row {index}: {row['_parse_error']}")
            continue
        ts = _float_or_none(row.get("ts"))
        if ts is None:
            # Legacy rows without timestamps are not field deposits.
            if any(k in row for k in ("trace_id", "kind", "source_ide")):
                violations.append(f"row {index}: missing_or_invalid_ts")
            continue
        kind = str(row.get("kind") or row.get("event") or "legacy")
        tau_s = _tau_s(row, kind)
        strength = _strength(row, kind)
        if tau_s is None or tau_s <= 0.0:
            violations.append(f"row {index}: invalid_tau_s={tau_s}")
            continue
        if strength is None or strength <= 0.0:
            violations.append(f"row {index}: invalid_strength={strength}")
            continue
        payload = _payload_dict(row)
        deposits.append(
            PheromoneDeposit(
                row_index=index,
                ts=ts,
                kind=kind,
                source_ide=str(row.get("source_ide") or row.get("doctor") or "UNKNOWN"),
                homeworld_serial=str(row.get("homeworld_serial") or row.get("node_serial") or row.get("device") or "UNKNOWN"),
                trace_id=_trace_id(row, index),
                channel=_channel(row, payload),
                tau_s=tau_s,
                strength=strength,
                payload=payload,
            )
        )
    return tuple(deposits), tuple(violations)


def intensity_at(deposit: PheromoneDeposit, now_ts: float) -> float:
    age_s = max(0.0, now_ts - deposit.ts)
    return deposit.strength * math.exp(-age_s / deposit.tau_s)


def _field_at(deposits: Iterable[PheromoneDeposit], now_ts: float) -> dict[str, float]:
    field: dict[str, float] = {}
    for deposit in deposits:
        field[deposit.channel] = field.get(deposit.channel, 0.0) + intensity_at(deposit, now_ts)
    return field


def _collision_signals(
    deposits: tuple[PheromoneDeposit, ...],
    now_ts: float,
    collision_window_s: float,
) -> tuple[CollisionSignal, ...]:
    signals: list[CollisionSignal] = []
    ordered = sorted(deposits, key=lambda item: item.ts)
    for left_index, left in enumerate(ordered):
        for right in ordered[left_index + 1 :]:
            gap = right.ts - left.ts
            if gap > collision_window_s:
                break
            if left.channel != right.channel or left.source_ide == right.source_ide:
                continue
            live_overlap = min(intensity_at(left, now_ts), intensity_at(right, now_ts))
            window_factor = math.exp(-gap / max(collision_window_s, 1.0))
            signals.append(
                CollisionSignal(
                    left_trace_id=left.trace_id,
                    right_trace_id=right.trace_id,
                    channel=left.channel,
                    left_source=left.source_ide,
                    right_source=right.source_ide,
                    gap_s=gap,
                    risk=live_overlap * window_factor,
                )
            )
    return tuple(signals)


def field_report(
    rows: Iterable[Mapping[str, Any]],
    *,
    now_ts: float | None = None,
    dt_s: float = 60.0,
    collision_window_s: float = DEFAULT_COLLISION_WINDOW_S,
) -> PheromoneFieldReport:
    deposits, violations = extract_deposits(rows)
    if now_ts is None:
        now_ts = max((d.ts for d in deposits), default=0.0)

    mutable_violations = list(violations)
    for deposit in deposits:
        if deposit.ts > now_ts + 1e-9:
            mutable_violations.append(f"row {deposit.row_index}: future_deposit ts={deposit.ts} now={now_ts}")

    field = _field_at(deposits, now_ts)
    field_after_dt = _field_at(deposits, now_ts + max(0.0, dt_s))
    if any(value < 0.0 for value in field.values()):
        mutable_violations.append("field_negative_intensity")

    if deposits:
        span_s = max(1.0, max(d.ts for d in deposits) - min(d.ts for d in deposits))
        deposit_rate = len(deposits) / (span_s / 3600.0)
    else:
        deposit_rate = 0.0

    return PheromoneFieldReport(
        deposits=deposits,
        field=field,
        field_after_dt=field_after_dt,
        deposit_rate_per_hour=deposit_rate,
        collision_signals=_collision_signals(deposits, now_ts, collision_window_s),
        violations=tuple(mutable_violations),
        now_ts=now_ts,
        dt_s=dt_s,
    )


def pheromone_evaporation_ok(rows: Iterable[Mapping[str, Any]], *, now_ts: float | None = None) -> bool:
    return field_report(rows, now_ts=now_ts).ok


def fixture_pheromone_field(path: Path = _FIXTURE, *, now_ts: float | None = None) -> PheromoneFieldReport:
    return field_report(load_jsonl(path), now_ts=now_ts)


def live_pheromone_field(*, limit: int = 300) -> PheromoneFieldReport:
    if not _TRACE.exists():
        return field_report([], now_ts=0.0)
    rows = load_jsonl(_TRACE)
    return field_report(rows[-limit:])


if __name__ == "__main__":
    print("\n".join(live_pheromone_field().summary_lines()))
