#!/usr/bin/env python3
"""
swarm_field_slo.py
══════════════════
Falsifiable service-level objectives for the unified organ field.

This is an AGI-claim gate for the current embodied, receipt-backed
stigmergic substrate:

- field completeness stays above a threshold most of the time
- coupling density remains bounded instead of exploding or collapsing
- the declared organ set is present and non-stale in recent field rows
- truth-continuity drift does not persist for too many consecutive turns
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
FIELD_SLO_LEDGER = _STATE / "unified_field_slo.jsonl"
SLO_SCHEMA_LITERAL = "UNIFIED_FIELD_SLO_V1"


@dataclass(frozen=True)
class FieldSLOConfig:
    max_field_rows: int = 1000
    max_truth_rows: int = 200
    completeness_min: float = 0.85
    completeness_required_rate: float = 0.95
    unknown_free_required_rate: float = 0.95
    connected_organs_min: int = 17
    coupling_density_min: float = 0.30
    coupling_density_max: float = 1.25
    coupling_density_max_span: float = 0.50
    truth_score_min: float = 0.80
    max_consecutive_truth_drifts: int = 5


@dataclass(frozen=True)
class FieldSLOReport:
    ok: bool
    total_field_rows: int
    total_truth_rows: int
    completeness_rate: float = 0.0
    unknown_free_rate: float = 0.0
    min_connected_organs: int = 0
    density_min_seen: Optional[float] = None
    density_max_seen: Optional[float] = None
    density_span: Optional[float] = None
    max_consecutive_truth_drifts: int = 0
    failures: List[str] = field(default_factory=list)
    boundary: str = (
        "alive_real=OPERATIONAL_UNDER_POWER; "
        "MEMORY_ORGANS_FIELD=MATERIAL_CODE_AND_APPEND_ONLY_LEDGER_ROWS; "
        "AGI_arbitrary_domain_open_ended=NOT_CERTIFIED_UNTIL_DECLARED_GATE_SUITE"
    )

    def assert_ok(self) -> None:
        if not self.ok:
            raise AssertionError("; ".join(self.failures))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "total_field_rows": self.total_field_rows,
            "total_truth_rows": self.total_truth_rows,
            "completeness_rate": self.completeness_rate,
            "unknown_free_rate": self.unknown_free_rate,
            "min_connected_organs": self.min_connected_organs,
            "density_min_seen": self.density_min_seen,
            "density_max_seen": self.density_max_seen,
            "density_span": self.density_span,
            "max_consecutive_truth_drifts": self.max_consecutive_truth_drifts,
            "failures": list(self.failures),
            "boundary": self.boundary,
        }


def _payload(row: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = row.get("payload")
    return payload if isinstance(payload, Mapping) else row


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if out == out and out not in (float("inf"), float("-inf")):
            return out
    except Exception:
        pass
    return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def read_jsonl_tail(path: Path, *, limit: int) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def evaluate_field_slo(
    field_rows: Iterable[Mapping[str, Any]],
    truth_rows: Iterable[Mapping[str, Any]] = (),
    *,
    config: FieldSLOConfig = FieldSLOConfig(),
) -> FieldSLOReport:
    field_payloads = [_payload(row) for row in list(field_rows)[-config.max_field_rows:]]
    truth_payloads = [_payload(row) for row in list(truth_rows)[-config.max_truth_rows:]]

    failures: List[str] = []
    total_field = len(field_payloads)
    if total_field == 0:
        failures.append("no organ_field_vector rows available")
        return FieldSLOReport(
            ok=False,
            total_field_rows=0,
            total_truth_rows=len(truth_payloads),
            failures=failures,
        )

    completeness_values = [
        _as_float(row.get("field_completeness"), 0.0)
        for row in field_payloads
    ]
    completeness_good = sum(
        1 for value in completeness_values
        if value >= config.completeness_min
    )
    completeness_rate = completeness_good / total_field
    if completeness_rate < config.completeness_required_rate:
        failures.append(
            "field_completeness SLO failed: "
            f"{completeness_rate:.3f} < {config.completeness_required_rate:.3f}"
        )

    unknown_counts = [
        _as_int(row.get("unknown_vector_count"), 999999)
        for row in field_payloads
    ]
    unknown_free = sum(1 for count in unknown_counts if count == 0)
    unknown_free_rate = unknown_free / total_field
    if unknown_free_rate < config.unknown_free_required_rate:
        failures.append(
            "unknown-free organ vector SLO failed: "
            f"{unknown_free_rate:.3f} < {config.unknown_free_required_rate:.3f}"
        )

    connected_counts = [
        _as_int(row.get("connected_organ_count"), 0)
        for row in field_payloads
    ]
    min_connected = min(connected_counts) if connected_counts else 0
    if min_connected < config.connected_organs_min:
        failures.append(
            "connected organ SLO failed: "
            f"min_connected={min_connected} < {config.connected_organs_min}"
        )

    densities = [
        _as_float(row.get("coupling_density"), 0.0)
        for row in field_payloads
    ]
    density_min_seen = min(densities) if densities else None
    density_max_seen = max(densities) if densities else None
    density_span = (
        density_max_seen - density_min_seen
        if density_min_seen is not None and density_max_seen is not None else
        None
    )
    if density_min_seen is not None and density_min_seen < config.coupling_density_min:
        failures.append(
            "coupling density collapsed: "
            f"{density_min_seen:.3f} < {config.coupling_density_min:.3f}"
        )
    if density_max_seen is not None and density_max_seen > config.coupling_density_max:
        failures.append(
            "coupling density exceeded bound: "
            f"{density_max_seen:.3f} > {config.coupling_density_max:.3f}"
        )
    if density_span is not None and density_span > config.coupling_density_max_span:
        failures.append(
            "coupling density unstable: "
            f"span={density_span:.3f} > {config.coupling_density_max_span:.3f}"
        )

    consecutive = 0
    max_consecutive = 0
    for row in truth_payloads:
        score = _as_float(row.get("continuity_score"), 1.0)
        flags = row.get("drift_flags", [])
        has_flags = bool(flags) if isinstance(flags, list) else bool(flags)
        if score < config.truth_score_min or has_flags:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0
    if max_consecutive > config.max_consecutive_truth_drifts:
        failures.append(
            "truth-continuity drift streak SLO failed: "
            f"{max_consecutive} > {config.max_consecutive_truth_drifts}"
        )

    return FieldSLOReport(
        ok=not failures,
        total_field_rows=total_field,
        total_truth_rows=len(truth_payloads),
        completeness_rate=completeness_rate,
        unknown_free_rate=unknown_free_rate,
        min_connected_organs=min_connected,
        density_min_seen=density_min_seen,
        density_max_seen=density_max_seen,
        density_span=density_span,
        max_consecutive_truth_drifts=max_consecutive,
        failures=failures,
    )


def evaluate_state_dir(
    state_dir: Path = _STATE,
    *,
    config: FieldSLOConfig = FieldSLOConfig(),
) -> FieldSLOReport:
    return evaluate_field_slo(
        read_jsonl_tail(state_dir / "organ_field_vector.jsonl", limit=config.max_field_rows),
        read_jsonl_tail(state_dir / "truth_continuity_events.jsonl", limit=config.max_truth_rows),
        config=config,
    )


def append_state_dir_report(
    state_dir: Path = _STATE,
    *,
    ledger_path: Path | None = None,
    config: FieldSLOConfig = FieldSLOConfig(),
) -> Dict[str, Any]:
    """Evaluate and append one falsifiable SLO receipt for the current field."""
    report = evaluate_state_dir(state_dir, config=config)
    row: Dict[str, Any] = {
        "schema": SLO_SCHEMA_LITERAL,
        "ts": time.time(),
        "truth_label": "OPERATIONAL",
        "retention_class": "operational",
        "source": "swarm_field_slo:append_state_dir_report",
        "slo_pass": report.ok,
        "report": report.as_dict(),
    }
    from System.jsonl_file_lock import append_line_locked

    target = ledger_path or (state_dir / FIELD_SLO_LEDGER.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(
        target,
        json.dumps(row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return row


def summary_for_prompt(state_dir: Path = _STATE) -> str:
    report = evaluate_state_dir(state_dir)
    status = "PASS" if report.ok else "FAIL"
    return (
        "UNIFIED FIELD SLO (alive_real receipts + measurement gate):\n"
        f"- status={status} field_rows={report.total_field_rows} "
        f"truth_rows={report.total_truth_rows} "
        f"completeness_rate={report.completeness_rate:.3f} "
        f"unknown_free_rate={report.unknown_free_rate:.3f} "
        f"min_connected_organs={report.min_connected_organs} "
        f"density_span={report.density_span if report.density_span is not None else 'n/a'} "
        f"max_truth_drift_streak={report.max_consecutive_truth_drifts}\n"
        f"- boundary={report.boundary}"
    )


__all__ = [
    "FIELD_SLO_LEDGER",
    "SLO_SCHEMA_LITERAL",
    "FieldSLOConfig",
    "FieldSLOReport",
    "read_jsonl_tail",
    "evaluate_field_slo",
    "evaluate_state_dir",
    "append_state_dir_report",
    "summary_for_prompt",
]
