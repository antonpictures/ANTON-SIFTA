#!/usr/bin/env python3
"""
swarm_acoustic_field.py — The Acoustic Substrate
════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Sound is a 1D field over time: Field(position, t).
Instead of tracking multi-dimensional motion, this module 
calculates the temporal gradient of amplitude (energy delta) across an audio buffer.

High acoustic gradients are physically persisted as Acoustic Pheromones,
which can mathematically perturb the Kuramoto Phase Coupling.
"""

import time
import json
import math
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

MODULE_VERSION = "2026-04-18.v1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_ACOUSTIC_FIELDS = _STATE / "acoustic_fields"
_ACOUSTIC_FIELDS.mkdir(parents=True, exist_ok=True)
_ACOUSTIC_PHEROMONES = _STATE / "acoustic_pheromones.jsonl"


class SwarmAcousticField:
    def __init__(self, fields_dir: Optional[Path] = None, pheromones_ledger: Optional[Path] = None, crossmodal_binder=None):
        self.fields_dir = fields_dir or _ACOUSTIC_FIELDS
        self.fields_dir.mkdir(parents=True, exist_ok=True)
        self.pheromones_ledger = pheromones_ledger or _ACOUSTIC_PHEROMONES
        self.binder = crossmodal_binder

    def _read_field_state(self, source_id: str) -> Dict[str, Any]:
        """Reads the stigmergic acoustic field state from disk."""
        target = self.fields_dir / f"{source_id}.json"
        if target.exists():
            try:
                return json.loads(target.read_text("utf-8"))
            except Exception:
                pass
        return {}

    def _write_field_state(self, source_id: str, state_dict: Dict[str, Any]):
        """Writes the stigmergic acoustic field state to disk atomically."""
        target = self.fields_dir / f"{source_id}.json"
        target_tmp = target.with_suffix(".json.tmp")
        try:
            target_tmp.write_text(json.dumps(state_dict), "utf-8")
            target_tmp.replace(target)
        except Exception:
            pass

    def ingest_audio(self, source_id: str, audio_buffer: List[float]) -> float:
        """
        Receives an instantaneous 1D acoustic array (e.g., standard audio frames).
        Computes the temporal derivative ∂Audio / ∂t (acoustic energy).
        """
        current_time = time.time()
        prev_state = self._read_field_state(source_id)

        valid_history = False
        if "buffer" in prev_state and "timestamp" in prev_state:
            prev_buffer = prev_state["buffer"]
            if len(prev_buffer) == len(audio_buffer) and len(prev_buffer) > 0:
                valid_history = True

        if not valid_history:
            self._write_field_state(source_id, {
                "timestamp": current_time,
                "buffer": audio_buffer,
                "energy": 0.0
            })
            return 0.0

        prev_buffer = prev_state["buffer"]
        prev_time = float(prev_state["timestamp"])
        dt = current_time - prev_time
        if dt <= 0:
            dt = 0.001

        # Calculate temporal gradient magnitude (Energy)
        if HAS_NUMPY:
            np_audio = np.array(audio_buffer)
            np_prev = np.array(prev_buffer)
            # The mean absolute gradient
            delta = np.abs(np_audio - np_prev)
            energy = float(np.mean(delta) / dt)
        else:
            delta_sum = sum(abs(a - b) for a, b in zip(audio_buffer, prev_buffer))
            mean_delta = delta_sum / len(audio_buffer)
            energy = float(mean_delta / dt)

        # Stigmergic persistence of active rolling buffer
        self._write_field_state(source_id, {
            "timestamp": current_time,
            "buffer": audio_buffer,
            "energy": energy
        })

        # Physical Audit Emission Threshold for High Acoustic Transients
        # This is where SIFTA Swimmers smell sound.
        if energy > 0.1:
            try:
                with open(self.pheromones_ledger, "a") as f:
                    f.write(json.dumps({
                        "timestamp": current_time,
                        "source_id": source_id,
                        "energy": energy,
                        "type": "acoustic_gradient"
                    }) + "\n")
            except Exception:
                pass
                
            # Pass directly to Binder for cross-modal object tracking
            if self.binder:
                try:
                    self.binder.ingest_event("audio", energy, timestamp=current_time, territory=str(self.fields_dir / f"{source_id}.json"))
                except Exception:
                    pass

        return energy

    def query_acoustic_energy(self, source_id: str) -> float:
        """
        Allows a SIFTA Swimmer to directly smell the most recent acoustic energy of a domain.
        """
        state = self._read_field_state(source_id)
        return float(state.get("energy", 0.0))

if __name__ == "__main__":
    # Smoke Test
    print("═" * 58)
    print("  SIFTA — ACOUSTIC SUBSTRATE SENSORY SMOKE TEST")
    print("═" * 58 + "\n")

    import tempfile
    import shutil
    
    _tmp = Path(tempfile.mkdtemp())
    _tmp_ledger = _tmp / "acoustic_pheromones.jsonl"
    
    try:
        field = SwarmAcousticField(fields_dir=_tmp, pheromones_ledger=_tmp_ledger)
        source = "mic_0"

        # Silence buffer
        buffer_silence = [0.0] * 1024

        print("[TEST] Ingesting Silence Buffer")
        energy_1 = field.ingest_audio(source, buffer_silence)
        assert energy_1 == 0.0, "Initial ingest must yield zero energy."
        
        # Another frame of silence (no dynamic change)
        time.sleep(0.01)
        energy_2 = field.ingest_audio(source, buffer_silence)
        assert energy_2 == 0.0, "Silent differential must yield 0 energy."
        print("  [PASS] Silence resolves to 0.0 biological energy.")

        # Loud Burst (Dynamic Change in Amplitude)
        time.sleep(0.01)
        buffer_loud = [1.0] * 1024
        print("\n[TEST] Ingesting transient acoustic shock (Max amplitude burst)")
        energy_burst = field.ingest_audio(source, buffer_loud)
        assert energy_burst > 10.0, f"Failed to detect transient acoustic wave. Got: {energy_burst}"
        print(f"  [PASS] Loud transient successfully tracked: (Heat: {energy_burst:.3f})")

        # Did it leave a pheromone drop?
        lines = _tmp_ledger.read_text("utf-8").strip().splitlines()
        assert len(lines) == 1, "Expected exactly 1 high-energy acoustic ledger row."
        first_row = json.loads(lines[0])
        assert first_row["type"] == "acoustic_gradient"
        print("  [PASS] High-energy event structurally dropped an Acoustic Pheromone.")
        
        print("\n[SUCCESS] 4/4 Acoustic Substrate smoke tests passed.")
        print("Result: Sound natively maps to 1D stigmergic topologies.")
    finally:
        shutil.rmtree(_tmp, ignore_errors=True)
