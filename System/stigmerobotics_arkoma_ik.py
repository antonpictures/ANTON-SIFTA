#!/usr/bin/env python3
"""
System/stigmerobotics_arkoma_ik.py
==================================

E50 — NAO ARKOMA inverse-kinematics benchmark lane.

Ingests real ARKOMA rows (Mendeley Data DOI 10.17632/brg4dz8nbb.1) into the
Stigmerobotics physical-space + effector contract. Side-effect free.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_FIXTURE = _REPO / "tests" / "fixtures" / "stigmero_e50_arkoma_slice.csv"
_DATASET_DIR = _REPO / "assets" / "robotics" / "arkoma"

DATASET_DOI = "10.17632/brg4dz8nbb.1"
DATASET_SLUG = "mendeley/brg4dz8nbb.1"
BODY_ID = "nao_arkoma_virtual"
MM_TO_M = 0.001
DEG_TO_RAD = math.pi / 180.0

POSE_KEYS: tuple[str, ...] = ("Px", "Py", "Pz", "Rx", "Ry", "Rz")
JOINT_KEYS: tuple[str, ...] = ("joint1", "joint2", "joint3", "joint4", "joint5")
ARKOMA_COLUMNS: tuple[str, ...] = POSE_KEYS + JOINT_KEYS + ("arm", "split")
INPUT_KEYS: tuple[str, ...] = POSE_KEYS + JOINT_KEYS

JOINT_LIMITS_RAD: dict[str, dict[str, tuple[float, float]]] = {
    "left": {
        "joint1": (-2.0857, 2.0857),
        "joint2": (-0.3142, 1.3265),
        "joint3": (-2.0857, 2.0857),
        "joint4": (-1.5446, -0.0349),
        "joint5": (-1.8238, 1.8238),
    },
    "right": {
        "joint1": (-2.0857, 2.0857),
        "joint2": (-1.3265, 0.3142),
        "joint3": (-2.0857, 2.0857),
        "joint4": (0.0349, 1.5446),
        "joint5": (-1.8238, 1.8238),
    },
}


@dataclass(frozen=True)
class ArkomaBenchmarkReport:
    row_count: int
    observation_rank: int
    observation_dim: int
    grounded_rows: int
    joints_in_range: int
    source_path: str
    dataset_doi: str
    proof_of_property: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return (
            self.row_count > 0
            and self.grounded_rows == self.row_count
            and self.observation_rank >= 5
            and self.joints_in_range == self.row_count
        )


def _float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float("nan")
    if out != out or out in (float("inf"), float("-inf")):
        return float("nan")
    return out


def parse_arkoma_row(row: Mapping[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key in ARKOMA_COLUMNS:
        if key in ("arm", "split"):
            parsed[key] = str(row.get(key, ""))
        else:
            parsed[key] = _float(row.get(key))
    return parsed


def load_csv_rows(path: Path | None = None, *, limit: int | None = None) -> list[dict[str, Any]]:
    csv_path = path or _DEFAULT_FIXTURE
    if not csv_path.exists():
        raise FileNotFoundError(f"ARKOMA dataset not found at {csv_path}")
    rows: list[dict[str, Any]] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return rows
        missing = [col for col in ARKOMA_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"ARKOMA schema missing columns: {missing}")
        for idx, raw in enumerate(reader):
            if limit is not None and idx >= limit:
                break
            rows.append(parse_arkoma_row(raw))
    return rows


def load_paired_rows(x_path: Path, y_path: Path, *, arm: str, split: str, limit: int | None = None) -> list[dict[str, Any]]:
    with x_path.open(newline="", encoding="utf-8") as xf, y_path.open(newline="", encoding="utf-8") as yf:
        x_reader = csv.DictReader(xf)
        y_reader = csv.DictReader(yf)
        rows: list[dict[str, Any]] = []
        for idx, (xrow, yrow) in enumerate(zip(x_reader, y_reader)):
            if limit is not None and idx >= limit:
                break
            merged = {**xrow, **yrow, "arm": arm, "split": split}
            rows.append(parse_arkoma_row(merged))
        return rows


def joints_within_limits(row: Mapping[str, Any]) -> bool:
    arm = str(row.get("arm", "left")).lower()
    limits = JOINT_LIMITS_RAD.get(arm, JOINT_LIMITS_RAD["left"])
    for key in JOINT_KEYS:
        val = _float(row.get(key))
        lo, hi = limits[key]
        if not (lo - 1e-4 <= val <= hi + 1e-4):
            return False
    return True


def row_to_kinematics_trace(
    row: Mapping[str, Any],
    *,
    ts: float,
    homeworld_serial: str,
    row_index: int = 0,
) -> dict[str, Any]:
    arm = str(row.get("arm", "unknown"))
    return {
        "ts": ts,
        "kind": "desk_telemetry_radar",
        "body_id": BODY_ID,
        "pose_x": _float(row["Px"]) * MM_TO_M,
        "pose_y": _float(row["Py"]) * MM_TO_M,
        "pose_z": _float(row["Pz"]) * MM_TO_M,
        "payload": {
            "robot_model": "NAO_H25_v3.3",
            "arm": arm,
            "split": str(row.get("split", "")),
            "rotation_vec_deg": [_float(row[k]) for k in ("Rx", "Ry", "Rz")],
            "joints_rad": [_float(row[k]) for k in JOINT_KEYS],
            "row_index": row_index,
        },
        "confidence": 1.0,
        "truth_label": "OBSERVED",
        "homeworld_serial": homeworld_serial,
        "source_dataset": DATASET_DOI,
    }


def build_observation_matrix(rows: Sequence[Mapping[str, Any]]) -> tuple[list[list[float]], list[str]]:
    channels = list(INPUT_KEYS)
    matrix = [[_float(row[ch]) for ch in channels] for row in rows]
    return matrix, channels


def observation_rank(rows: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
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


def build_arkoma_benchmark_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_path: str,
    now_ts: float = 0.0,
    homeworld_serial: str = "GTH4921YP3",
) -> ArkomaBenchmarkReport:
    from System.stigmerobotics_physical_space import build_physical_space_report

    traces = [
        row_to_kinematics_trace(row, ts=now_ts + idx * 0.001, homeworld_serial=homeworld_serial, row_index=idx)
        for idx, row in enumerate(rows)
    ]
    rank, dim = observation_rank(rows)
    report = build_physical_space_report(traces, now_ts=now_ts + len(rows) * 0.001, max_age_s=3600.0)
    grounded = sum(1 for obs in report.observations if obs.body_id == BODY_ID)
    joints_ok = sum(1 for row in rows if joints_within_limits(row))

    proof = {
        "P_n": "Real ARKOMA NAO IK rows ingest into PhysicalSpaceReport without schema loss",
        "dataset": DATASET_DOI,
        "body_id": BODY_ID,
        "row_count": len(rows),
        "observation_rank": rank,
        "observation_dim": dim,
        "grounded_rows": grounded,
        "joints_in_range": joints_ok,
        "falsifier": "missing column, out-of-range joint, or rank < 5 on fixture slice",
        "truth_label": "OPERATIONAL",
    }
    return ArkomaBenchmarkReport(
        row_count=len(rows),
        observation_rank=rank,
        observation_dim=dim,
        grounded_rows=grounded,
        joints_in_range=joints_ok,
        source_path=source_path,
        dataset_doi=DATASET_DOI,
        proof_of_property=proof,
    )


def default_fixture_path() -> Path:
    return _DEFAULT_FIXTURE


def dataset_dir() -> Path:
    return _DATASET_DIR


def joint_targets_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "robot_model": "NAO_H25_v3.3",
        "arm": str(row.get("arm", "left")),
        "joints_rad": [_float(row[k]) for k in JOINT_KEYS],
        "pose_mm": [_float(row[k]) for k in ("Px", "Py", "Pz")],
        "rotation_vec_deg": [_float(row[k]) for k in ("Rx", "Ry", "Rz")],
    }