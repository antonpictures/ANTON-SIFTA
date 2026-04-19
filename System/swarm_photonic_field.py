#!/usr/bin/env python3
"""
swarm_photonic_field.py — The Photonic Substrate
════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Implements the fundamental realization that Camera Photons 
and File Pheromones are identical mathematical algebras.
  Field(x, t) -> scalar intensity

A video frame is a discrete spatial graph. 
Temporal motion (vision) evaluates directly to high-gradient 
pheromone trails.

A Swimmer crawling this field evaluates optical flow 
the exact same way it tracks pain gradients in the filesystem.
"""

import time
import json
from pathlib import Path
from typing import Dict, List, Any

MODULE_VERSION = "2026-04-18.v1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_PHOTONIC_FIELDS = _STATE / "photonic_fields"
_PHOTONIC_FIELDS.mkdir(parents=True, exist_ok=True)
_PHOTONIC_PHEROMONES = _STATE / "photonic_pheromones.jsonl"


class SwarmPhotonicField:
    def __init__(self, fields_dir: Path = None, pheromones_ledger: Path = None, crossmodal_binder=None):
        self.fields_dir = fields_dir or _PHOTONIC_FIELDS
        self.fields_dir.mkdir(parents=True, exist_ok=True)
        # Audit ledger path is per-instance so smokes don't leak into production state.
        self.pheromones_ledger = pheromones_ledger or _PHOTONIC_PHEROMONES
        self.binder = crossmodal_binder

    def _read_field_state(self, source_id: str) -> Dict[str, Any]:
        """Reads the stigmergic optical field state from disk."""
        target = self.fields_dir / f"{source_id}.json"
        if target.exists():
            try:
                return json.loads(target.read_text("utf-8"))
            except Exception:
                pass
        return {}

    def _write_field_state(self, source_id: str, state_dict: Dict[str, Any]):
        """Writes the stigmergic optical field state to disk atomically."""
        target = self.fields_dir / f"{source_id}.json"
        target_tmp = target.with_suffix(".json.tmp")
        try:
            target_tmp.write_text(json.dumps(state_dict), "utf-8")
            target_tmp.replace(target)
        except Exception:
            pass

    def ingest_frame(self, source_id: str, frame_matrix: List[List[float]]) -> None:
        """
        Receives an instantaneous photonic field (e.g., a grayscale camera frame).
        Computes the temporal derivative ∂/∂t directly into a Pheromone Field.
        """
        current_time = time.time()
        prev_state = self._read_field_state(source_id)

        # Baseline shape check. If corrupted, missing, or resizing mid-stream: reset
        valid_history = False
        if "matrix" in prev_state and "timestamp" in prev_state:
            prev_matrix = prev_state["matrix"]
            if len(prev_matrix) == len(frame_matrix) and len(prev_matrix) > 0:
                if len(prev_matrix[0]) == len(frame_matrix[0]):
                    valid_history = True

        if not valid_history:
            empty_gradient = [[0.0 for _ in row] for row in frame_matrix]
            self._write_field_state(source_id, {
                "timestamp": current_time,
                "matrix": frame_matrix,
                "pheromones": empty_gradient
            })
            return

        prev_matrix = prev_state["matrix"]
        prev_time = float(prev_state["timestamp"])
        dt = current_time - prev_time
        if dt <= 0:
            dt = 0.001

        gradient_field = []
        max_motion = 0.0

        for y, row in enumerate(frame_matrix):
            grad_row = []
            for x, current_intensity in enumerate(row):
                prev_intensity = prev_matrix[y][x]
                # Note: using abs() discards optical flow direction but isolates sheer pheromone magnitude
                delta = abs(current_intensity - prev_intensity)
                rate_of_change = float(delta / dt)
                grad_row.append(rate_of_change)
                if rate_of_change > max_motion:
                    max_motion = rate_of_change
            gradient_field.append(grad_row)

        # Stigmergic persistence
        self._write_field_state(source_id, {
            "timestamp": current_time,
            "matrix": frame_matrix,
            "pheromones": gradient_field
        })

        # Drop biological audit row if major event
        if max_motion > 0.1:
            try:
                with open(self.pheromones_ledger, "a") as f:
                    f.write(json.dumps({
                        "timestamp": current_time,
                        "source_id": source_id,
                        "max_gradient": max_motion
                    }) + "\n")
            except Exception:
                pass
            
            # Send the spike to the visual cortex for potential Cross-Modal Perception
            if self.binder:
                self.binder.ingest_event("video", max_motion, timestamp=current_time, territory=source_id)


    def query_photonic_pheromone(self, source_id: str, x: int, y: int) -> float:
        """
        Allows a SIFTA Swimmer to directly smell the optical flow of a specific coordinate.
        High values indicate motion/photonic disturbance.
        """
        state = self._read_field_state(source_id)
        if "pheromones" in state:
            try:
                return float(state["pheromones"][y][x])
            except IndexError:
                pass
        return 0.0

if __name__ == "__main__":
    # Smoke Test
    print("═" * 58)
    print("  SIFTA — PHOTONIC SUBSTRATE SENSORY SMOKE TEST")
    print("═" * 58 + "\n")

    import tempfile
    import shutil
    
    _tmp = Path(tempfile.mkdtemp())

    try:
        field = SwarmPhotonicField(
            fields_dir=_tmp,
            pheromones_ledger=_tmp / "photonic_pheromones.jsonl",
        )
        source = "webcam_0"

        # Frame 1: Empty background
        frame_t1 = [
            [0.1, 0.1, 0.1],
            [0.1, 0.1, 0.1],
            [0.1, 0.1, 0.1]
        ]

        print("[TEST] Ingesting Frame t=1 (Flat geometry)")
        field.ingest_frame(source, frame_t1)
        assert field.query_photonic_pheromone(source, 1, 1) == 0.0
        print("  [PASS] No temporal gradient on first frame.")

        # Frame 2: An object enters the center pixel
        time.sleep(0.1)
        frame_t2 = [
            [0.1, 0.1, 0.1],
            [0.1, 0.9, 0.1],
            [0.1, 0.1, 0.1]
        ]

        print("\n[TEST] Ingesting Frame t=2 (Object enters center)")
        field.ingest_frame(source, frame_t2)

        grad_center = field.query_photonic_pheromone(source, 1, 1)
        grad_edge = field.query_photonic_pheromone(source, 0, 0)
        
        assert grad_center > 1.0, f"Failed to detect strong photonic gradient: {grad_center}"
        assert grad_edge == 0.0, "Hallucinated motion on motionless pixel."
        
        print(f"  [PASS] Strong Stigmergic Pheromone generated: (Heat: {grad_center:.3f})")

        # Frame 3: Dimension Mismatch test (Patch B)
        frame_t3_mismatch = [
            [0.5, 0.5]
        ]
        print("\n[TEST] Ingesting corrupted frame size (Dimension Mismatch)")
        field.ingest_frame(source, frame_t3_mismatch)
        # Should gracefully reset to 0.0 instead of index error masking
        assert field.query_photonic_pheromone(source, 0, 0) == 0.0
        print("  [PASS] Handled dimension shift biologically (history flushed cleanly).")

        print("\n[SUCCESS] Photonic Substrate smoke tests passed.")
        
    finally:
        shutil.rmtree(_tmp, ignore_errors=True)
