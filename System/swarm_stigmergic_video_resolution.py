#!/usr/bin/env python3
"""
System/swarm_stigmergic_video_resolution.py

Event 90: Stigmergic Video Resolution / Neuromorphic Retina.

This organ does not export raw camera frames. It derives a compact per-frame
resolution summary from Alice's existing visual stigmergy rows: camera size,
grid size, active salience cells, compression, and a small payload of source
facts. The output is append-only and schema-validated before it reaches the
ledger.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from System.canonical_schemas import assert_payload_keys
from System.jsonl_file_lock import append_line_locked, read_text_locked


SCHEMA = "SIFTA_STIGMERGIC_VIDEO_RESOLUTION_V1"
MODULE_VERSION = "swarm_stigmergic_video_resolution.v1"
LEDGER_NAME = "stigmergic_video_resolution.jsonl"
VISUAL_LEDGER_NAME = "visual_stigmergy.jsonl"


def _positive_quantized_cells(serialized: Any) -> int:
    """Count non-zero quantized cells from visual_stigmergy q-strings."""

    if not isinstance(serialized, str):
        return 0
    active = 0
    for char in serialized.strip():
        try:
            active += 1 if int(char, 16) > 0 else 0
        except ValueError:
            continue
    return active


def _infer_square_grid(*serialized_fields: Any, fallback: Tuple[int, int]) -> Tuple[int, int]:
    """Infer grid side from a serialized square field, falling back explicitly."""

    for field in serialized_fields:
        if not isinstance(field, str):
            continue
        length = len(field.strip())
        side = int(math.isqrt(length))
        if side > 0 and side * side == length:
            return side, side
    return fallback


def _coerce_positive_int(value: Any, *, name: str) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if coerced <= 0:
        raise ValueError(f"{name} must be > 0")
    return coerced


def _clamp_active_cells(value: Any, total_cells: int) -> int:
    try:
        active = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("active_cells must be an integer") from exc
    return max(0, min(active, total_cells))


class SwarmStigmergicResolution:
    """Compute and append Event 90 visual-resolution rows."""

    def __init__(
        self,
        *,
        state_dir: Optional[Path] = None,
        camera_width: int = 1920,
        camera_height: int = 1080,
        grid_size: Tuple[int, int] = (22, 22),
    ) -> None:
        self.state_dir = Path(state_dir) if state_dir is not None else Path(".sifta_state")
        self.resolution_ledger = self.state_dir / LEDGER_NAME
        self.visual_ledger = self.state_dir / VISUAL_LEDGER_NAME
        self.camera_width = _coerce_positive_int(camera_width, name="camera_width")
        self.camera_height = _coerce_positive_int(camera_height, name="camera_height")
        self.grid_w = _coerce_positive_int(grid_size[0], name="grid_width")
        self.grid_h = _coerce_positive_int(grid_size[1], name="grid_height")
        self.state_dir.mkdir(parents=True, exist_ok=True)

    @property
    def camera_pixels(self) -> int:
        return self.camera_width * self.camera_height

    @property
    def total_stig_cells(self) -> int:
        return self.grid_w * self.grid_h

    def build_frame_summary(
        self,
        *,
        frame_id: Any,
        active_cells: int,
        unified_field_payload: Iterable[Dict[str, Any]],
        source_ledger: str = "manual",
        source_sha8: str = "",
        source_frame_ts: Optional[float] = None,
        camera_size: Optional[Tuple[int, int]] = None,
        grid_size: Optional[Tuple[int, int]] = None,
    ) -> Dict[str, Any]:
        """Build one schema-valid resolution row without writing it."""

        cam_w, cam_h = camera_size or (self.camera_width, self.camera_height)
        grid_w, grid_h = grid_size or (self.grid_w, self.grid_h)
        cam_w = _coerce_positive_int(cam_w, name="camera_width")
        cam_h = _coerce_positive_int(cam_h, name="camera_height")
        grid_w = _coerce_positive_int(grid_w, name="grid_width")
        grid_h = _coerce_positive_int(grid_h, name="grid_height")
        total_cells = grid_w * grid_h
        active = _clamp_active_cells(active_cells, total_cells)
        camera_pixels = cam_w * cam_h

        row = {
            "event": "stigmergic_video_resolution",
            "schema": SCHEMA,
            "module_version": MODULE_VERSION,
            "truth_label": "OPERATIONAL",
            "ts": time.time(),
            "frame_id": frame_id,
            "source_ledger": str(source_ledger),
            "source_sha8": str(source_sha8 or ""),
            "source_frame_ts": source_frame_ts,
            "camera_size": [cam_w, cam_h],
            "camera_pixels_total": camera_pixels,
            "stigmergic_grid": [grid_w, grid_h],
            "total_stig_cells": total_cells,
            "active_salient_cells": active,
            "pixels_per_stig_cell": round(camera_pixels / total_cells, 2),
            "salience_density": round(active / total_cells, 6),
            "unified_field_payload": list(unified_field_payload),
        }
        assert_payload_keys(LEDGER_NAME, row, strict=True)
        return row

    def calculate_and_log_frame(
        self,
        frame_id: Any,
        active_cells: int,
        unified_field_payload: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compatibility API for Bishop's reference sketch."""

        row = self.build_frame_summary(
            frame_id=frame_id,
            active_cells=active_cells,
            unified_field_payload=unified_field_payload,
        )
        return self.append_row(row)

    def calculate_from_visual_stigmergy_row(self, visual_row: Dict[str, Any]) -> Dict[str, Any]:
        """Derive Event 90 row from one existing visual_stigmergy.jsonl row."""

        saliency_q = visual_row.get("saliency_q")
        motion_q = visual_row.get("motion_q")
        grid_size = _infer_square_grid(
            saliency_q,
            motion_q,
            fallback=(self.grid_w, self.grid_h),
        )
        saliency_active = _positive_quantized_cells(saliency_q)
        motion_active = _positive_quantized_cells(motion_q)
        active_cells = max(saliency_active, motion_active)
        frame_id = visual_row.get("sha8") or visual_row.get("frame_id") or visual_row.get("ts")
        payload = [
            {
                "saliency_peak": visual_row.get("saliency_peak"),
                "motion_mean": visual_row.get("motion_mean"),
                "entropy_bits": visual_row.get("entropy_bits"),
                "hue_deg": visual_row.get("hue_deg"),
                "saliency_active_cells": saliency_active,
                "motion_active_cells": motion_active,
            }
        ]
        return self.build_frame_summary(
            frame_id=frame_id,
            active_cells=active_cells,
            unified_field_payload=payload,
            source_ledger=VISUAL_LEDGER_NAME,
            source_sha8=str(visual_row.get("sha8") or ""),
            source_frame_ts=visual_row.get("ts"),
            camera_size=(
                _coerce_positive_int(visual_row.get("w", self.camera_width), name="camera_width"),
                _coerce_positive_int(visual_row.get("h", self.camera_height), name="camera_height"),
            ),
            grid_size=grid_size,
        )

    def append_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and append one resolution row."""

        assert_payload_keys(LEDGER_NAME, row, strict=True)
        append_line_locked(self.resolution_ledger, json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def log_latest_visual_stigmergy(self) -> Optional[Dict[str, Any]]:
        """Read the latest visual_stigmergy row and append its resolution summary."""

        text = read_text_locked(self.visual_ledger)
        for line in reversed([line for line in text.splitlines() if line.strip()]):
            try:
                visual_row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(visual_row, dict):
                return self.append_row(self.calculate_from_visual_stigmergy_row(visual_row))
        return None


def proof_of_property() -> Dict[str, bool]:
    retina = SwarmStigmergicResolution(camera_width=1920, camera_height=1080, grid_size=(22, 22))
    row = retina.build_frame_summary(
        frame_id=1,
        active_cells=15,
        unified_field_payload=[{"cell": [10, 11], "val": 0.8}],
    )
    return {
        "schema_valid": set(row) == {
            "event",
            "schema",
            "module_version",
            "truth_label",
            "ts",
            "frame_id",
            "source_ledger",
            "source_sha8",
            "source_frame_ts",
            "camera_size",
            "camera_pixels_total",
            "stigmergic_grid",
            "total_stig_cells",
            "active_salient_cells",
            "pixels_per_stig_cell",
            "salience_density",
            "unified_field_payload",
        },
        "grid_math": row["total_stig_cells"] == 484,
        "compression_math": row["pixels_per_stig_cell"] == round((1920 * 1080) / 484, 2),
        "density_math": row["salience_density"] == round(15 / 484, 6),
    }


if __name__ == "__main__":
    print("=== SIFTA Neuromorphic Retina (Event 90) ===")
    result = proof_of_property()
    print(json.dumps(result, indent=2, ensure_ascii=False))
