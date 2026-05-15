#!/usr/bin/env python3
"""Organ Health Mesh.

This module composes existing organ-health ideas into a small immune loop:

- organs publish bounded health reports;
- sick organs emit distress pheromone;
- sentinel swimmers route repair swimmers from healthy organs;
- repair spends a bounded STGM budget;
- successful intervention writes a receipt.

Truth boundary: this is SIFTA organ telemetry / simulation logic. It is not a
medical, hardware, or external-service health claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - import fallback for isolated tools
    append_line_locked = None

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

SCHEMA = "SIFTA_ORGAN_HEALTH_MESH_V1"
RECEIPT_KIND = "ORGAN_HEALTH_MESH_REPAIR"
LEDGER_NAME = "organ_health_mesh_receipts.jsonl"
LATEST_NAME = "organ_health_mesh_latest.json"

TRUTH_BOUNDARY = (
    "Organ Health Mesh operates on SIFTA organ health reports and demo "
    "simulation rows only; it does not prove human, medical, hardware, "
    "camera, or external service health."
)


def _clamp(value: Any, lo: float, hi: float, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except Exception:
        numeric = default
    return max(lo, min(hi, numeric))


def _clamp01(value: Any, default: float = 0.0) -> float:
    return _clamp(value, 0.0, 1.0, default)


def _json_hash(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8", errors="replace")
    ).hexdigest()


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line)
    else:  # pragma: no cover
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


@dataclass(frozen=True)
class OrganHealthReport:
    """One organ's local health publication."""

    organ_id: str
    energy: float
    error_rate: float
    latency_ms: float
    stgm_delta: float
    wounds: tuple[str, ...] = ()
    local_swimmers: int = 1
    ts: float = 0.0

    @classmethod
    def from_mapping(cls, organ_id: str, row: Mapping[str, Any]) -> "OrganHealthReport":
        wounds = row.get("wounds") or row.get("recent_wounds") or ()
        if isinstance(wounds, str):
            wounds_tuple = (wounds,)
        else:
            wounds_tuple = tuple(str(w) for w in wounds if str(w).strip())
        return cls(
            organ_id=str(row.get("organ_id") or row.get("organ") or organ_id),
            energy=_clamp01(row.get("energy", row.get("health", 0.5)), 0.5),
            error_rate=_clamp01(row.get("error_rate", 0.0), 0.0),
            latency_ms=max(0.0, _clamp(row.get("latency_ms", 250.0), 0.0, 60_000.0, 250.0)),
            stgm_delta=_clamp(row.get("stgm_delta", row.get("net_stgm", 0.0)), -1000.0, 1000.0, 0.0),
            wounds=wounds_tuple,
            local_swimmers=max(0, int(_clamp(row.get("local_swimmers", row.get("swimmer_count", 1)), 0, 1_000_000, 1))),
            ts=float(row.get("ts") or time.time()),
        )

    def normalized(self) -> "OrganHealthReport":
        return replace(
            self,
            organ_id=str(self.organ_id),
            energy=_clamp01(self.energy),
            error_rate=_clamp01(self.error_rate),
            latency_ms=max(0.0, float(self.latency_ms)),
            stgm_delta=float(self.stgm_delta),
            wounds=tuple(str(w) for w in self.wounds if str(w).strip()),
            local_swimmers=max(0, int(self.local_swimmers)),
            ts=float(self.ts or time.time()),
        )


@dataclass(frozen=True)
class RepairSwimmer:
    """A mobile repair swimmer routed by the mesh."""

    swimmer_id: str
    home_organ: str
    role: str
    energy: float = 1.0
    carrying: str = ""


@dataclass(frozen=True)
class RepairIntervention:
    """One cross-organ intervention."""

    from_organ: str
    to_organ: str
    swimmer_id: str
    repair_kind: str
    stgm_cost: float
    expected_health_gain: float
    distress_pheromone: float

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["stgm_cost"] = round(self.stgm_cost, 6)
        row["expected_health_gain"] = round(self.expected_health_gain, 6)
        row["distress_pheromone"] = round(self.distress_pheromone, 6)
        row["sentinel_path"] = ["sentinel_mesh", self.from_organ, self.to_organ]
        return row


def health_score(report: OrganHealthReport) -> float:
    """Bounded organ health score from energy, errors, latency, STGM, wounds."""
    r = report.normalized()
    energy_component = r.energy
    error_component = 1.0 - r.error_rate
    latency_component = 1.0 / (1.0 + (r.latency_ms / 1000.0))
    stgm_component = 0.5 + _clamp(r.stgm_delta / 10.0, -0.5, 0.5, 0.0)
    wound_penalty = min(0.5, 0.12 * len(r.wounds))
    score = (
        0.35 * energy_component
        + 0.25 * error_component
        + 0.20 * latency_component
        + 0.20 * stgm_component
        - wound_penalty
    )
    return round(_clamp01(score), 6)


def distress_pheromone(report: OrganHealthReport, score: float | None = None) -> float:
    """Return how loudly an organ asks the mesh for help."""
    r = report.normalized()
    s = health_score(r) if score is None else _clamp01(score)
    wound_push = min(0.35, 0.10 * len(r.wounds))
    error_push = 0.25 * r.error_rate
    latency_push = min(0.20, r.latency_ms / 10_000.0)
    distress = max(0.0, 0.65 - s) + wound_push + error_push + latency_push
    return round(_clamp01(distress), 6)


def organ_status(score: float) -> str:
    if score >= 0.75:
        return "healthy"
    if score >= 0.55:
        return "watch"
    if score >= 0.35:
        return "sick"
    return "critical"


def _canonical_reports(
    reports: Mapping[str, OrganHealthReport | Mapping[str, Any]],
) -> dict[str, OrganHealthReport]:
    out: dict[str, OrganHealthReport] = {}
    for key, value in reports.items():
        if isinstance(value, OrganHealthReport):
            report = value.normalized()
        elif isinstance(value, Mapping):
            report = OrganHealthReport.from_mapping(str(key), value).normalized()
        else:
            continue
        out[report.organ_id] = report
    return out


def build_health_mesh(
    reports: Mapping[str, OrganHealthReport | Mapping[str, Any]],
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Build a read-only mesh snapshot from organ health reports."""
    ts = float(now if now is not None else time.time())
    canonical = _canonical_reports(reports)
    organs: dict[str, dict[str, Any]] = {}
    distress_organs: list[str] = []
    healthy_organs: list[str] = []
    for organ_id, report in sorted(canonical.items()):
        score = health_score(report)
        status = organ_status(score)
        distress = distress_pheromone(report, score)
        if distress >= 0.20 or status in {"sick", "critical"}:
            distress_organs.append(organ_id)
        if status == "healthy" and report.energy >= 0.65:
            healthy_organs.append(organ_id)
        organs[organ_id] = {
            "report": asdict(report),
            "score": score,
            "status": status,
            "distress_pheromone": distress,
            "home_swimmers": report.local_swimmers,
            "wounds": list(report.wounds),
        }
    return {
        "ts": ts,
        "schema": SCHEMA,
        "truth_label": "OPERATIONAL",
        "truth_boundary": TRUTH_BOUNDARY,
        "organ_count": len(organs),
        "distress_organs": distress_organs,
        "healthy_organs": healthy_organs,
        "organs": organs,
    }


def _repair_kind_for_donor(donor: str) -> str:
    folded = donor.casefold()
    if any(word in folded for word in ("memory", "hippocampus", "context")):
        return "context_swimmer"
    if any(word in folded for word in ("residue", "bowel", "lysosome", "immune", "cleanup")):
        return "cleanup_swimmer"
    if any(word in folded for word in ("economy", "stgm", "metabolic", "wallet")):
        return "budget_swimmer"
    if any(word in folded for word in ("vision", "camera", "eye", "sensor")):
        return "sensor_swimmer"
    return "repair_swimmer"


def _donor_priority(donor: str, target: str) -> int:
    kind = _repair_kind_for_donor(donor)
    if target.casefold() in {"talk", "speech", "alice_talk"}:
        priorities = {
            "context_swimmer": 0,
            "cleanup_swimmer": 1,
            "budget_swimmer": 2,
            "repair_swimmer": 3,
            "sensor_swimmer": 4,
        }
        return priorities.get(kind, 9)
    priorities = {
        "budget_swimmer": 0,
        "repair_swimmer": 1,
        "cleanup_swimmer": 2,
        "context_swimmer": 3,
        "sensor_swimmer": 4,
    }
    return priorities.get(kind, 9)


def plan_repairs(mesh: Mapping[str, Any], *, stgm_budget: float = 1.0) -> dict[str, Any]:
    """Route sentinel/repair swimmers from healthy organs to distressed organs."""
    budget = max(0.0, float(stgm_budget))
    organs = mesh.get("organs") if isinstance(mesh.get("organs"), Mapping) else {}
    donors = [
        str(organ_id)
        for organ_id, row in organs.items()
        if isinstance(row, Mapping)
        and row.get("status") == "healthy"
        and float(row.get("score") or 0.0) >= 0.72
    ]
    targets = [
        str(organ_id)
        for organ_id, row in organs.items()
        if isinstance(row, Mapping)
        and (row.get("status") in {"sick", "critical"} or float(row.get("distress_pheromone") or 0.0) >= 0.20)
    ]
    interventions: list[RepairIntervention] = []
    spent = 0.0
    for target in sorted(targets, key=lambda org: -float(organs[org].get("distress_pheromone") or 0.0)):
        distress = float(organs[target].get("distress_pheromone") or 0.0)
        candidate_donors = sorted((d for d in donors if d != target), key=lambda d: (_donor_priority(d, target), d))
        for donor in candidate_donors[:3]:
            if spent >= budget:
                break
            repair_kind = _repair_kind_for_donor(donor)
            cost = min(max(0.03, 0.05 + distress * 0.12), budget - spent)
            if cost <= 0:
                break
            gain = min(0.28, 0.08 + distress * 0.20)
            interventions.append(
                RepairIntervention(
                    from_organ=donor,
                    to_organ=target,
                    swimmer_id=f"{donor}->{target}:{repair_kind}:{len(interventions)}",
                    repair_kind=repair_kind,
                    stgm_cost=cost,
                    expected_health_gain=gain,
                    distress_pheromone=distress,
                )
            )
            spent += cost
    return {
        "schema": SCHEMA,
        "truth_boundary": TRUTH_BOUNDARY,
        "stgm_budget": round(budget, 6),
        "stgm_spent": round(spent, 6),
        "intervention_count": len(interventions),
        "interventions": [i.to_dict() for i in interventions],
    }


def apply_repairs(
    reports: Mapping[str, OrganHealthReport | Mapping[str, Any]],
    interventions: Iterable[RepairIntervention | Mapping[str, Any]],
) -> dict[str, OrganHealthReport]:
    """Return updated reports after planned repairs."""
    updated = dict(_canonical_reports(reports))
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for item in interventions:
        row = item.to_dict() if isinstance(item, RepairIntervention) else dict(item)
        target = str(row.get("to_organ") or "")
        if target:
            grouped.setdefault(target, []).append(row)

    for organ_id, rows in grouped.items():
        report = updated.get(organ_id)
        if report is None:
            continue
        total_gain = min(0.65, sum(float(r.get("expected_health_gain") or 0.0) for r in rows))
        kinds = {str(r.get("repair_kind") or "") for r in rows}
        wounds = list(report.wounds)
        if "context_swimmer" in kinds:
            wounds = [w for w in wounds if "voice" not in w.casefold() and "context" not in w.casefold()]
        if "cleanup_swimmer" in kinds:
            wounds = [w for w in wounds if "residue" not in w.casefold() and "cleanup" not in w.casefold()]
        if "budget_swimmer" in kinds:
            wounds = [w for w in wounds if "whatsapp" not in w.casefold() and "target" not in w.casefold()]
        if len(wounds) == len(report.wounds) and kinds and wounds:
            wounds = wounds[1:]
        if "context_swimmer" in kinds:
            report = replace(report, latency_ms=max(50.0, report.latency_ms * 0.72))
        if "budget_swimmer" in kinds:
            report = replace(report, stgm_delta=report.stgm_delta + 0.75)
        repaired = replace(
            report,
            energy=_clamp01(report.energy + total_gain * 0.75),
            error_rate=_clamp01(report.error_rate - total_gain * 0.90),
            latency_ms=max(50.0, report.latency_ms * (1.0 - total_gain * 0.50)),
            stgm_delta=report.stgm_delta - sum(float(r.get("stgm_cost") or 0.0) for r in rows),
            wounds=tuple(wounds),
            ts=time.time(),
        )
        updated[organ_id] = repaired
    return updated


def demo_reports(*, now: float | None = None) -> dict[str, OrganHealthReport]:
    """Return the requested wound-one-organ demo setup."""
    ts = float(now if now is not None else time.time())
    return {
        "talk": OrganHealthReport(
            organ_id="talk",
            energy=0.34,
            error_rate=0.42,
            latency_ms=1800.0,
            stgm_delta=-0.40,
            wounds=("voice_queue_backlog", "third_person_residue", "whatsapp_target_miss"),
            local_swimmers=12,
            ts=ts,
        ),
        "memory": OrganHealthReport(
            organ_id="memory",
            energy=0.88,
            error_rate=0.04,
            latency_ms=190.0,
            stgm_delta=0.60,
            wounds=(),
            local_swimmers=18,
            ts=ts,
        ),
        "residue": OrganHealthReport(
            organ_id="residue",
            energy=0.82,
            error_rate=0.06,
            latency_ms=220.0,
            stgm_delta=0.40,
            wounds=(),
            local_swimmers=16,
            ts=ts,
        ),
        "economy": OrganHealthReport(
            organ_id="economy",
            energy=0.91,
            error_rate=0.03,
            latency_ms=160.0,
            stgm_delta=0.95,
            wounds=(),
            local_swimmers=10,
            ts=ts,
        ),
        "vision": OrganHealthReport(
            organ_id="vision",
            energy=0.69,
            error_rate=0.10,
            latency_ms=420.0,
            stgm_delta=0.10,
            wounds=("camera_name_stale",),
            local_swimmers=9,
            ts=ts,
        ),
    }


def run_organ_health_mesh_demo(
    *,
    state_dir: Path | str = _STATE,
    write: bool = True,
    now: float | None = None,
) -> dict[str, Any]:
    """Run the Talk-organ wound demo and optionally write a receipt."""
    ts = float(now if now is not None else time.time())
    reports = demo_reports(now=ts)
    before = build_health_mesh(reports, now=ts)
    plan = plan_repairs(before, stgm_budget=0.50)
    repaired_reports = apply_repairs(reports, plan["interventions"])
    after = build_health_mesh(repaired_reports, now=ts)

    target_before = before["organs"]["talk"]
    target_after = after["organs"]["talk"]
    row: dict[str, Any] = {
        "ts": ts,
        "trace_id": str(uuid.uuid4()),
        "schema": SCHEMA,
        "kind": RECEIPT_KIND,
        "truth_label": "DEMO_SIMULATION",
        "truth_boundary": TRUTH_BOUNDARY,
        "target_organ": "talk",
        "before_score": target_before["score"],
        "after_score": target_after["score"],
        "before_status": target_before["status"],
        "after_status": target_after["status"],
        "distress_pheromone": target_before["distress_pheromone"],
        "interventions": plan["interventions"],
        "stgm_spent": plan["stgm_spent"],
        "recovered": target_after["score"] > target_before["score"],
        "source": "swarm_organ_health_mesh_demo",
    }
    row["receipt"] = _json_hash(row)
    result = {
        "before": before,
        "plan": plan,
        "after": after,
        "receipt": row,
    }
    if write:
        root = Path(state_dir)
        _append_jsonl(root / LEDGER_NAME, row)
        try:
            (root / LATEST_NAME).write_text(
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError:
            pass
    return result


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SIFTA Organ Health Mesh demo")
    parser.add_argument("--no-write", action="store_true", help="do not append a mesh receipt")
    parser.add_argument("--state-dir", default=str(_STATE), help="state directory for receipts")
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = run_organ_health_mesh_demo(state_dir=args.state_dir, write=not args.no_write)
    summary = {
        "schema": SCHEMA,
        "target": "talk",
        "before": result["receipt"]["before_score"],
        "after": result["receipt"]["after_score"],
        "stgm_spent": result["receipt"]["stgm_spent"],
        "interventions": result["receipt"]["interventions"],
        "receipt": result["receipt"]["receipt"],
        "truth_boundary": TRUTH_BOUNDARY,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
