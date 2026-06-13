#!/usr/bin/env python3
"""
System/stigmerobotics_ik_baseline.py
====================================

Nearest-neighbor IK baseline comparison for E49/E50 fixture slices.

Reports pose→joint error distributions against dataset labels only.
Does NOT claim solver superiority — metrics are falsifiers for ingest health.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from System.stigmerobotics_effector_bridge import EffectorRequest, execute_request_stub
from System.stigmerobotics_irb2400_ik import (
    BODY_ID as IRB_BODY_ID,
    JOINT_OUT_KEYS as IRB_JOINT_OUT,
    POSE_KEYS as IRB_POSE_KEYS,
    build_ik_benchmark_report,
    default_fixture_path as irb_fixture_path,
    joint_targets_payload as irb_joint_payload,
    load_csv_rows as load_irb_rows,
)
from System.stigmerobotics_arkoma_ik import (
    BODY_ID as ARKOMA_BODY_ID,
    JOINT_KEYS as ARKOMA_JOINT_KEYS,
    POSE_KEYS as ARKOMA_POSE_KEYS,
    build_arkoma_benchmark_report,
    default_fixture_path as arkoma_fixture_path,
    joint_targets_payload as arkoma_joint_payload,
    load_csv_rows as load_arkoma_rows,
)

BASELINE_METHOD = "nearest_neighbor_pose_l2"
FORBIDDEN_CLAIM = "beats_solver_or_baseline"
COMPARISON_NOTE = (
    "Metrics compare a trivial nearest-neighbor pose baseline to dataset joint labels. "
    "This is ingest/falsifier telemetry — not evidence that SIFTA beats any IK solver."
)


def _float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float("nan")
    if out != out or out in (float("inf"), float("-inf")):
        return float("nan")
    return out


def _pose_vector(row: Mapping[str, Any], keys: Sequence[str]) -> tuple[float, ...]:
    return tuple(_float(row[k]) for k in keys)


def _target_vector(row: Mapping[str, Any], keys: Sequence[str]) -> tuple[float, ...]:
    return tuple(_float(row[k]) for k in keys)


def _l2(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _joint_errors(pred: Sequence[float], label: Sequence[float]) -> list[float]:
    return [abs(p - l) for p, l in zip(pred, label)]


def _error_stats(errors: Sequence[float]) -> dict[str, float]:
    if not errors:
        return {"mean_rad": float("nan"), "max_rad": float("nan"), "median_rad": float("nan")}
    sorted_err = sorted(errors)
    mid = len(sorted_err) // 2
    median = (
        sorted_err[mid]
        if len(sorted_err) % 2
        else (sorted_err[mid - 1] + sorted_err[mid]) / 2.0
    )
    return {
        "mean_rad": sum(errors) / len(errors),
        "max_rad": max(errors),
        "median_rad": median,
    }


def nearest_neighbor_baseline(
    train_rows: Sequence[Mapping[str, Any]],
    eval_rows: Sequence[Mapping[str, Any]],
    *,
    pose_keys: Sequence[str],
    target_keys: Sequence[str],
    group_key: str | None = None,
) -> dict[str, Any]:
    """Predict joint targets by copying labels from the closest pose in train_rows."""
    if not train_rows or not eval_rows:
        return {
            "eval_rows": len(eval_rows),
            "train_rows": len(train_rows),
            "errors": [],
            "stats": _error_stats([]),
            "baseline_method": BASELINE_METHOD,
        }

    train_by_group: dict[str, list[Mapping[str, Any]]] = {}
    for row in train_rows:
        key = str(row.get(group_key, "__all__")) if group_key else "__all__"
        train_by_group.setdefault(key, []).append(row)

    all_errors: list[float] = []
    for query in eval_rows:
        group = str(query.get(group_key, "__all__")) if group_key else "__all__"
        pool = train_by_group.get(group) or train_by_group.get("__all__") or list(train_rows)
        q_pose = _pose_vector(query, pose_keys)
        best = min(pool, key=lambda cand: _l2(q_pose, _pose_vector(cand, pose_keys)))
        label = _target_vector(query, target_keys)
        pred = _target_vector(best, target_keys)
        all_errors.extend(_joint_errors(pred, label))

    stats = _error_stats(all_errors)
    return {
        "eval_rows": len(eval_rows),
        "train_rows": len(train_rows),
        "errors": all_errors,
        "stats": stats,
        "baseline_method": BASELINE_METHOD,
    }


def _split_rows(rows: Sequence[Mapping[str, Any]], train_frac: float = 0.8) -> tuple[list, list]:
    if len(rows) < 2:
        return list(rows), []
    cut = max(1, int(len(rows) * train_frac))
    if cut >= len(rows):
        cut = len(rows) - 1
    return list(rows[:cut]), list(rows[cut:])


def _route_sample_effector(
    *,
    body_id: str,
    payload_builder,
    sample_row: Mapping[str, Any],
    trace_prefix: str,
) -> dict[str, Any]:
    payload = payload_builder(sample_row)
    request = EffectorRequest(
        trace_id=f"{trace_prefix}-baseline-sample",
        target_body_id=body_id,
        action_type="set_joint_targets",
        payload=payload,
        source_ide="ik_baseline_organ",
        homeworld_serial="GTH4921YP3",
        ts=3000.0,
    )
    receipt, sensor_echo = execute_request_stub(request, now_ts=3000.1)
    return {
        "receipt_status": receipt.get("status"),
        "sensor_echo_body": (sensor_echo or {}).get("body_id"),
        "truth_label": "OPERATIONAL",
    }


@dataclass(frozen=True)
class IkBaselineReport:
    dataset: str
    body_id: str
    ingest_ok: bool
    baseline: dict[str, Any]
    ingest_benchmark: dict[str, Any]
    effector_sample: dict[str, Any]
    comparison_note: str = COMPARISON_NOTE
    forbidden_claim: str = FORBIDDEN_CLAIM
    proof_of_property: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        stats = self.baseline.get("stats", {})
        return (
            self.ingest_ok
            and self.baseline.get("eval_rows", 0) > 0
            and stats.get("mean_rad", float("nan")) == stats.get("mean_rad", float("nan"))
            and self.effector_sample.get("receipt_status") == "ok"
        )


def build_irb2400_baseline_report(
    rows: Sequence[Mapping[str, float]] | None = None,
    *,
    train_frac: float = 0.8,
) -> IkBaselineReport:
    data = list(rows) if rows is not None else load_irb_rows(irb_fixture_path())
    train, eval_rows = _split_rows(data, train_frac)
    baseline = nearest_neighbor_baseline(
        train,
        eval_rows,
        pose_keys=IRB_POSE_KEYS,
        target_keys=IRB_JOINT_OUT,
    )
    ingest = build_ik_benchmark_report(data, source_path=str(irb_fixture_path()))
    effector = _route_sample_effector(
        body_id=IRB_BODY_ID,
        payload_builder=irb_joint_payload,
        sample_row=data[0],
        trace_prefix="e49",
    )
    proof = {
        "P_n": "Nearest-neighbor IK baseline emits bounded joint-error stats without solver claims",
        "dataset": "luisatencio/abb-irb-2400-arm-robot-kinematics-dataset",
        "body_id": IRB_BODY_ID,
        "baseline_method": BASELINE_METHOD,
        "mean_joint_error_rad": round(baseline["stats"]["mean_rad"], 6),
        "max_joint_error_rad": round(baseline["stats"]["max_rad"], 6),
        "forbidden_claim": FORBIDDEN_CLAIM,
        "falsifier": "NaN errors or missing effector receipt on sample row",
        "truth_label": "OBSERVED",
    }
    return IkBaselineReport(
        dataset="E49_IRB2400",
        body_id=IRB_BODY_ID,
        ingest_ok=ingest.ok,
        baseline=baseline,
        ingest_benchmark=ingest.proof_of_property,
        effector_sample=effector,
        proof_of_property=proof,
    )


def build_arkoma_baseline_report(
    rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    train_frac: float = 0.8,
) -> IkBaselineReport:
    data = list(rows) if rows is not None else load_arkoma_rows(arkoma_fixture_path())
    train, eval_rows = _split_rows(data, train_frac)
    baseline = nearest_neighbor_baseline(
        train,
        eval_rows,
        pose_keys=ARKOMA_POSE_KEYS,
        target_keys=ARKOMA_JOINT_KEYS,
        group_key="arm",
    )
    ingest = build_arkoma_benchmark_report(data, source_path=str(arkoma_fixture_path()))
    effector = _route_sample_effector(
        body_id=ARKOMA_BODY_ID,
        payload_builder=arkoma_joint_payload,
        sample_row=data[0],
        trace_prefix="e50",
    )
    proof = {
        "P_n": "Nearest-neighbor IK baseline emits bounded joint-error stats without solver claims",
        "dataset": "10.17632/brg4dz8nbb.1",
        "body_id": ARKOMA_BODY_ID,
        "baseline_method": BASELINE_METHOD,
        "mean_joint_error_rad": round(baseline["stats"]["mean_rad"], 6),
        "max_joint_error_rad": round(baseline["stats"]["max_rad"], 6),
        "forbidden_claim": FORBIDDEN_CLAIM,
        "falsifier": "NaN errors or missing effector receipt on sample row",
        "truth_label": "OBSERVED",
    }
    return IkBaselineReport(
        dataset="E50_ARKOMA",
        body_id=ARKOMA_BODY_ID,
        ingest_ok=ingest.ok,
        baseline=baseline,
        ingest_benchmark=ingest.proof_of_property,
        effector_sample=effector,
        proof_of_property=proof,
    )


def build_combined_robot_data_report() -> dict[str, Any]:
    """Widget/CLI aggregate for E49+E50 fixture benchmarks + baselines."""
    irb = build_irb2400_baseline_report()
    arkoma = build_arkoma_baseline_report()
    return {
        "truth_labels": {
            "ingest": "OPERATIONAL",
            "baseline_metrics": "OBSERVED",
            "physical_motion": "HYPOTHESIS",
            "beats_solver": "FORBIDDEN",
        },
        "comparison_note": COMPARISON_NOTE,
        "e49_irb2400": {
            "ok": irb.ok,
            "body_id": irb.body_id,
            "baseline_stats": irb.baseline["stats"],
            "ingest": irb.ingest_benchmark,
            "effector_sample": irb.effector_sample,
            "proof": irb.proof_of_property,
        },
        "e50_arkoma": {
            "ok": arkoma.ok,
            "body_id": arkoma.body_id,
            "baseline_stats": arkoma.baseline["stats"],
            "ingest": arkoma.ingest_benchmark,
            "effector_sample": arkoma.effector_sample,
            "proof": arkoma.proof_of_property,
        },
    }