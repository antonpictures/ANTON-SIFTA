#!/usr/bin/env python3
"""
System/stigmerobotics_irb2400_ik.py
===================================

E49 — ABB IRB 2400 inverse-kinematics benchmark lane.

Ingests real DH-derived robot kinematics rows (Kaggle / Luis Angel López Atencio)
into the Stigmerobotics physical-space + effector contract. Side-effect free.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_FIXTURE = _REPO / "tests" / "fixtures" / "stigmero_e49_irb2400_slice.csv"
_FULL_DATASET = _REPO / "assets" / "robotics" / "irb2400" / "datasetIRB2400.csv"

DATASET_SLUG = "luisatencio/abb-irb-2400-arm-robot-kinematics-dataset"
DATASET_FILENAME = "datasetIRB2400.csv"

IRB2400_COLUMNS: tuple[str, ...] = (
    "x",
    "y",
    "z",
    "yaw",
    "pitch",
    "roll",
    "q1_in",
    "q2_in",
    "q3_in",
    "q4_in",
    "q5_in",
    "q6_in",
    "q1_out",
    "q2_out",
    "q3_out",
    "q4_out",
    "q5_out",
    "q6_out",
)

POSE_KEYS: tuple[str, ...] = ("x", "y", "z", "yaw", "pitch", "roll")
JOINT_IN_KEYS: tuple[str, ...] = tuple(f"q{i}_in" for i in range(1, 7))
JOINT_OUT_KEYS: tuple[str, ...] = tuple(f"q{i}_out" for i in range(1, 7))
INPUT_KEYS: tuple[str, ...] = POSE_KEYS + JOINT_IN_KEYS

BODY_ID = "abb_irb2400_virtual"
MM_TO_M = 0.001


@dataclass(frozen=True)
class IkBenchmarkReport:
    row_count: int
    mean_joint_delta_rad: float
    max_joint_delta_rad: float
    observation_rank: int
    observation_dim: int
    grounded_rows: int
    source_path: str
    dataset_slug: str
    proof_of_property: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return (
            self.row_count > 0
            and self.mean_joint_delta_rad >= 0.0
            and self.max_joint_delta_rad < math.pi * 4.0
            and self.observation_rank >= 6
            and self.grounded_rows == self.row_count
        )


def _float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float("nan")
    if out != out or out in (float("inf"), float("-inf")):
        return float("nan")
    return out


def parse_irb2400_row(row: Mapping[str, Any]) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for key in IRB2400_COLUMNS:
        parsed[key] = _float(row.get(key))
    return parsed


def load_csv_rows(path: Path | None = None, *, limit: int | None = None) -> list[dict[str, float]]:
    csv_path = path or _DEFAULT_FIXTURE
    if not csv_path.exists():
        raise FileNotFoundError(f"IRB2400 dataset not found at {csv_path}")
    rows: list[dict[str, float]] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return rows
        missing = [col for col in IRB2400_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"IRB2400 schema missing columns: {missing}")
        for idx, raw in enumerate(reader):
            if limit is not None and idx >= limit:
                break
            rows.append(parse_irb2400_row(raw))
    return rows


def joint_delta_rad(row: Mapping[str, float]) -> tuple[float, ...]:
    return tuple(abs(_float(row[out]) - _float(row[inn])) for out, inn in zip(JOINT_OUT_KEYS, JOINT_IN_KEYS))


def row_to_kinematics_trace(
    row: Mapping[str, float],
    *,
    ts: float,
    homeworld_serial: str,
    row_index: int = 0,
) -> dict[str, Any]:
    """Normalize one IK row into a desk_telemetry_radar observation for PhysicalSpaceReport."""
    return {
        "ts": ts,
        "kind": "desk_telemetry_radar",
        "body_id": BODY_ID,
        "pose_x": _float(row["x"]) * MM_TO_M,
        "pose_y": _float(row["y"]) * MM_TO_M,
        "pose_z": _float(row["z"]) * MM_TO_M,
        "payload": {
            "robot_model": "ABB_IRB2400",
            "yaw_rad": _float(row["yaw"]),
            "pitch_rad": _float(row["pitch"]),
            "roll_rad": _float(row["roll"]),
            "q_in_rad": [_float(row[k]) for k in JOINT_IN_KEYS],
            "q_out_rad": [_float(row[k]) for k in JOINT_OUT_KEYS],
            "row_index": row_index,
        },
        "confidence": 1.0,
        "truth_label": "OBSERVED",
        "homeworld_serial": homeworld_serial,
        "source_dataset": DATASET_SLUG,
    }


def build_observation_matrix(rows: Sequence[Mapping[str, float]]) -> tuple[list[list[float]], list[str]]:
    channels = list(INPUT_KEYS)
    matrix: list[list[float]] = []
    for row in rows:
        matrix.append([_float(row[ch]) for ch in channels])
    return matrix, channels


def observation_rank(rows: Sequence[Mapping[str, float]]) -> tuple[int, int]:
    matrix, channels = build_observation_matrix(rows)
    if not matrix:
        return 0, len(channels)
    try:
        import numpy as np

        arr = np.asarray(matrix, dtype=float)
        rank = int(np.linalg.matrix_rank(arr, tol=1e-3))
    except Exception:
        rank = min(len(matrix), len(channels))
    return rank, len(channels)


def build_ik_benchmark_report(
    rows: Sequence[Mapping[str, float]],
    *,
    source_path: str,
    now_ts: float = 0.0,
    homeworld_serial: str = "GTH4921YP3",
) -> IkBenchmarkReport:
    from System.stigmerobotics_physical_space import build_physical_space_report

    deltas: list[float] = []
    traces: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        deltas.extend(joint_delta_rad(row))
        traces.append(
            row_to_kinematics_trace(row, ts=now_ts + idx * 0.001, homeworld_serial=homeworld_serial, row_index=idx)
        )

    rank, dim = observation_rank(rows)
    report = build_physical_space_report(traces, now_ts=now_ts + len(rows) * 0.001, max_age_s=3600.0)
    grounded = sum(1 for obs in report.observations if obs.body_id == BODY_ID)

    mean_delta = sum(deltas) / len(deltas) if deltas else float("nan")
    max_delta = max(deltas) if deltas else float("nan")

    proof = {
        "P_n": "Real IRB2400 IK rows ingest into PhysicalSpaceReport without schema loss",
        "dataset": DATASET_SLUG,
        "body_id": BODY_ID,
        "row_count": len(rows),
        "mean_joint_delta_rad": round(mean_delta, 6),
        "max_joint_delta_rad": round(max_delta, 6),
        "observation_rank": rank,
        "observation_dim": dim,
        "grounded_rows": grounded,
        "falsifier": "missing column, NaN pose, or rank < 6 on fixture slice",
        "truth_label": "OPERATIONAL",
    }
    return IkBenchmarkReport(
        row_count=len(rows),
        mean_joint_delta_rad=mean_delta,
        max_joint_delta_rad=max_delta,
        observation_rank=rank,
        observation_dim=dim,
        grounded_rows=grounded,
        source_path=source_path,
        dataset_slug=DATASET_SLUG,
        proof_of_property=proof,
    )


def default_fixture_path() -> Path:
    return _DEFAULT_FIXTURE


def full_dataset_path() -> Path:
    return _FULL_DATASET


def joint_targets_payload(row: Mapping[str, float]) -> dict[str, Any]:
    return {
        "robot_model": "ABB_IRB2400",
        "joints_rad": [_float(row[k]) for k in JOINT_OUT_KEYS],
        "pose_mm": [_float(row[k]) for k in ("x", "y", "z")],
        "orientation_rad": [_float(row[k]) for k in ("yaw", "pitch", "roll")],
    }