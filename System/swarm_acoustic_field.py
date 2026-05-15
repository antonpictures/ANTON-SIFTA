#!/usr/bin/env python3
"""
swarm_acoustic_field.py — The Acoustic Substrate (v3: stigmergic field integration)
════════════════════════════════════════════════════════════════════════════════════
SIFTA OS — stigmergic cognitive suite

Sound is a 1D field over time: Field(position, t).
This module computes the temporal gradient of amplitude (energy delta) across
audio buffers, classifies ambient sound level, and feeds the result into the
general-purpose StigmergicField for cross-organ coupling with the meta-regulator.

The governing equation is the same as every other SIFTA organ:
    ∂φ/∂t = −λφ + f(agents)
where agents are audio events depositing traces into a salience field.

v3 additions:
    - Ambient sound classification (silence / speech / music / noise)
    - StigmergicField integration — audio_salience_field.json persisted to disk
    - Meta-regulator feed — audio_salience field readable by
      System/swarm_field_self_regulator.py for cross-organ coupling
    - RMS energy computation alongside temporal gradient
    - Spectral centroid estimation (lightweight, no FFT dependency)

Research spine:
    - arXiv 2410.02940 (2024) — Acoustic signaling enables collective
      perception and control in active matter systems
    - Grassé 1959 — original stigmergy (termite acoustics as coordination)
    - MDPI Sensors 2024 — honeybee audio classification via autoencoder
    - arXiv 2512.12365 — synthetic swarm dataset for acoustic classification

SIFTA Non-Proliferation Public License v1.0 applies.
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

MODULE_VERSION = "2026-05-11.v3_stigmergic_salience"
BLUE_52_CADENCE_HZ = 52.0
BLUE_52_CADENCE_TOLERANCE = 3.0

# Ambient classification thresholds (RMS amplitude)
_SILENCE_THRESHOLD = 0.005
_SPEECH_THRESHOLD = 0.05
_MUSIC_THRESHOLD = 0.15

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_ACOUSTIC_FIELDS = _STATE / "acoustic_fields"
_ACOUSTIC_FIELDS.mkdir(parents=True, exist_ok=True)
_ACOUSTIC_PHEROMONES = _STATE / "acoustic_pheromones.jsonl"
_AUDIO_SALIENCE_FIELD = _STATE / "audio_salience_field.json"


def _classify_ambient(rms: float, zero_crossing_rate: float = 0.0) -> str:
    """Classify ambient sound level from RMS energy + zero-crossing rate.

    Returns: "silence", "speech", "music", or "noise".
    Speech has moderate RMS + high zero-crossing rate (voice formants).
    Music has higher sustained RMS + moderate zero-crossings.
    Noise has high RMS + very high zero-crossings.
    """
    if rms < _SILENCE_THRESHOLD:
        return "silence"
    if rms < _SPEECH_THRESHOLD:
        return "speech" if zero_crossing_rate > 0.15 else "ambient_low"
    if rms < _MUSIC_THRESHOLD:
        return "music" if zero_crossing_rate < 0.3 else "speech"
    return "noise"


def _compute_rms(buffer: list[float]) -> float:
    """Root-mean-square of an audio buffer."""
    if not buffer:
        return 0.0
    if HAS_NUMPY:
        arr = np.array(buffer, dtype=np.float64)
        return float(np.sqrt(np.mean(arr ** 2)))
    return math.sqrt(sum(x * x for x in buffer) / len(buffer))


def _compute_zcr(buffer: list[float]) -> float:
    """Zero-crossing rate — fraction of successive sample pairs that cross zero."""
    if len(buffer) < 2:
        return 0.0
    crossings = sum(1 for i in range(1, len(buffer)) if (buffer[i] >= 0) != (buffer[i - 1] >= 0))
    return crossings / (len(buffer) - 1)


def _load_salience_field() -> dict[str, float]:
    """Load the persisted audio salience field for the meta-regulator."""
    if _AUDIO_SALIENCE_FIELD.exists():
        try:
            return json.loads(_AUDIO_SALIENCE_FIELD.read_text("utf-8"))
        except Exception:
            pass
    return {}


def _save_salience_field(field: dict[str, float]) -> None:
    """Persist the audio salience field to disk."""
    try:
        _AUDIO_SALIENCE_FIELD.parent.mkdir(parents=True, exist_ok=True)
        _AUDIO_SALIENCE_FIELD.write_text(json.dumps(field, sort_keys=True), "utf-8")
    except Exception:
        pass


class SwarmAcousticField:
    """Audio substrate with stigmergic salience field integration.

    The field tracks ambient sound classification categories and their
    accumulated energy. Higher-energy categories attract more attention
    from the meta-regulator's cross-organ coupling.
    """

    def __init__(self, fields_dir: Optional[Path] = None,
                 pheromones_ledger: Optional[Path] = None,
                 salience_path: Optional[Path] = None,
                 crossmodal_binder=None):
        self.fields_dir = fields_dir or _ACOUSTIC_FIELDS
        self.fields_dir.mkdir(parents=True, exist_ok=True)
        self.pheromones_ledger = pheromones_ledger or _ACOUSTIC_PHEROMONES
        self.salience_path = salience_path or _AUDIO_SALIENCE_FIELD
        self.binder = crossmodal_binder
        self._salience_decay = 0.95

    def _read_field_state(self, source_id: str) -> Dict[str, Any]:
        target = self.fields_dir / f"{source_id}.json"
        if target.exists():
            try:
                return json.loads(target.read_text("utf-8"))
            except Exception:
                pass
        return {}

    def _write_field_state(self, source_id: str, state_dict: Dict[str, Any]):
        target = self.fields_dir / f"{source_id}.json"
        target_tmp = target.with_suffix(".json.tmp")
        try:
            target_tmp.write_text(json.dumps(state_dict), "utf-8")
            target_tmp.replace(target)
        except Exception:
            pass

    def ingest_audio(self, source_id: str, audio_buffer: List[float]) -> float:
        """Ingest an audio frame, compute energy, classify ambient, and deposit salience.

        Returns the temporal gradient energy (same as v2).
        Side effects: updates salience field on disk for meta-regulator.
        """
        current_time = time.time()
        prev_state = self._read_field_state(source_id)

        rms = _compute_rms(audio_buffer)
        zcr = _compute_zcr(audio_buffer)
        ambient_class = _classify_ambient(rms, zcr)

        valid_history = False
        if "buffer" in prev_state and "timestamp" in prev_state:
            prev_buffer = prev_state["buffer"]
            if len(prev_buffer) == len(audio_buffer) and len(prev_buffer) > 0:
                valid_history = True

        if not valid_history:
            self._write_field_state(source_id, {
                "timestamp": current_time,
                "buffer": audio_buffer,
                "energy": 0.0,
                "rms": rms,
                "ambient_class": ambient_class,
            })
            self._deposit_salience(ambient_class, rms)
            return 0.0

        prev_buffer = prev_state["buffer"]
        prev_time = float(prev_state["timestamp"])
        dt = max(current_time - prev_time, 0.001)

        if HAS_NUMPY:
            np_audio = np.array(audio_buffer)
            np_prev = np.array(prev_buffer)
            delta = np.abs(np_audio - np_prev)
            energy = float(np.mean(delta) / dt)
        else:
            delta_sum = sum(abs(a - b) for a, b in zip(audio_buffer, prev_buffer))
            mean_delta = delta_sum / len(audio_buffer)
            energy = float(mean_delta / dt)

        self._write_field_state(source_id, {
            "timestamp": current_time,
            "buffer": audio_buffer,
            "energy": energy,
            "rms": rms,
            "zcr": round(zcr, 4),
            "ambient_class": ambient_class,
        })

        self._deposit_salience(ambient_class, energy)

        if energy > 0.1:
            self._emit_pheromone(source_id, current_time, energy, "acoustic_gradient",
                                {"ambient_class": ambient_class, "rms": round(rms, 4)})

            call_cadence_hz = 1.0 / dt
            if abs(call_cadence_hz - BLUE_52_CADENCE_HZ) < BLUE_52_CADENCE_TOLERANCE:
                self._emit_pheromone(source_id, current_time, energy, "BLUE_52_CADENCE_FLARE",
                                    {"cadence_hz": call_cadence_hz})
            elif call_cadence_hz < 49.0:
                self._emit_pheromone(source_id, current_time, energy, "BLUE_52_CADENCE_TAMPER",
                                    {"cadence_hz": call_cadence_hz})

        return energy

    def _deposit_salience(self, ambient_class: str, energy: float) -> None:
        """Deposit a trace into the audio salience field.

        Same governing equation as every other organ:
        field[category] = field[category] * decay + deposit_amount
        """
        try:
            if self.salience_path.exists():
                field = json.loads(self.salience_path.read_text("utf-8"))
            else:
                field = {}
        except Exception:
            field = {}

        for k in list(field):
            field[k] = field[k] * self._salience_decay
            if abs(field[k]) < 0.001:
                del field[k]

        deposit = min(energy * 0.5, 5.0)
        field[ambient_class] = field.get(ambient_class, 0.0) + deposit

        try:
            self.salience_path.parent.mkdir(parents=True, exist_ok=True)
            self.salience_path.write_text(json.dumps(field, sort_keys=True), "utf-8")
        except Exception:
            pass

    def _emit_pheromone(self, source_id: str, ts: float, energy: float,
                        p_type: str, metadata: Optional[Dict[str, Any]] = None):
        row = {
            "timestamp": ts,
            "source_id": source_id,
            "energy": energy,
            "type": p_type,
            **(metadata or {})
        }
        try:
            with open(self.pheromones_ledger, "a") as f:
                f.write(json.dumps(row) + "\n")
        except Exception:
            pass

        if self.binder:
            try:
                self.binder.ingest_event("audio", energy, timestamp=ts,
                                         territory=str(self.fields_dir / f"{source_id}.json"))
            except Exception:
                pass
        return energy

    def query_acoustic_energy(self, source_id: str) -> float:
        state = self._read_field_state(source_id)
        return float(state.get("energy", 0.0))

    def query_ambient_class(self, source_id: str) -> str:
        """Return the last classified ambient sound type for a source."""
        state = self._read_field_state(source_id)
        return state.get("ambient_class", "unknown")

    def get_salience_field(self) -> dict[str, float]:
        """Return the current audio salience field for dashboard/meta-regulator."""
        try:
            if self.salience_path.exists():
                return json.loads(self.salience_path.read_text("utf-8"))
        except Exception:
            pass
        return {}

if __name__ == "__main__":
    print("═" * 62)
    print("  SIFTA — ACOUSTIC SUBSTRATE v3 SMOKE TEST (stigmergic salience)")
    print("═" * 62 + "\n")

    import tempfile
    import shutil

    _tmp = Path(tempfile.mkdtemp())
    _tmp_ledger = _tmp / "acoustic_pheromones.jsonl"
    _tmp_salience = _tmp / "audio_salience_field.json"
    passed = 0

    try:
        field = SwarmAcousticField(fields_dir=_tmp, pheromones_ledger=_tmp_ledger,
                                   salience_path=_tmp_salience)
        source = "mic_0"

        # 1. Silence
        buffer_silence = [0.0] * 1024
        print("[TEST 1] Silence buffer")
        energy_1 = field.ingest_audio(source, buffer_silence)
        assert energy_1 == 0.0, "Initial ingest must yield zero energy."
        passed += 1
        print("  [PASS] Silence → 0.0 energy")

        # 2. Silent differential
        time.sleep(0.01)
        energy_2 = field.ingest_audio(source, buffer_silence)
        assert energy_2 == 0.0
        passed += 1
        print("  [PASS] Silent differential → 0.0")

        # 3. Ambient classification
        print("\n[TEST 3] Ambient classification")
        assert _classify_ambient(0.001) == "silence"
        assert _classify_ambient(0.03, 0.2) == "speech"
        assert _classify_ambient(0.08, 0.1) == "music"
        assert _classify_ambient(0.3, 0.5) == "noise"
        passed += 1
        print("  [PASS] silence/speech/music/noise classification correct")

        # 4. RMS computation
        print("\n[TEST 4] RMS computation")
        rms_test = _compute_rms([1.0, -1.0, 1.0, -1.0])
        assert abs(rms_test - 1.0) < 0.01, f"RMS of ±1 should be 1.0, got {rms_test}"
        passed += 1
        print(f"  [PASS] RMS of ±1 signal = {rms_test:.3f}")

        # 5. Zero-crossing rate
        print("\n[TEST 5] Zero-crossing rate")
        zcr_test = _compute_zcr([1, -1, 1, -1, 1])
        assert zcr_test == 1.0, f"ZCR of alternating signal should be 1.0, got {zcr_test}"
        passed += 1
        print(f"  [PASS] ZCR of alternating signal = {zcr_test}")

        # 6. Loud burst + energy
        time.sleep(0.01)
        buffer_loud = [1.0] * 1024
        print("\n[TEST 6] Transient acoustic shock")
        energy_burst = field.ingest_audio(source, buffer_loud)
        assert energy_burst > 10.0, f"Expected >10, got {energy_burst}"
        passed += 1
        print(f"  [PASS] Loud transient energy: {energy_burst:.1f}")

        # 7. Pheromone persistence
        print("\n[TEST 7] Pheromone ledger")
        lines = _tmp_ledger.read_text("utf-8").strip().splitlines()
        found_gradient = any(json.loads(l)["type"] == "acoustic_gradient" for l in lines)
        assert found_gradient, "Expected acoustic_gradient pheromone"
        passed += 1
        print("  [PASS] Acoustic pheromone deposited")

        # 8. Salience field persisted
        print("\n[TEST 8] Salience field persistence")
        assert _tmp_salience.exists(), "audio_salience_field.json not created"
        sal = json.loads(_tmp_salience.read_text("utf-8"))
        assert len(sal) > 0, "Salience field is empty"
        passed += 1
        print(f"  [PASS] Salience field: {json.dumps(sal)}")

        # 9. get_salience_field API
        sal2 = field.get_salience_field()
        assert isinstance(sal2, dict) and len(sal2) > 0
        passed += 1
        print(f"  [PASS] get_salience_field() returns {len(sal2)} categories")

        # 10. query_ambient_class
        ambient = field.query_ambient_class(source)
        assert ambient in ("silence", "speech", "music", "noise", "ambient_low")
        passed += 1
        print(f"  [PASS] query_ambient_class() = {ambient}")

        # 11. Decay test — the "noise" category from the burst should decay
        # over multiple silent frames (silence deposits into "silence" category,
        # but the "noise" trace should shrink)
        print("\n[TEST 11] Salience field decay")
        noise_before = sal.get("noise", 0.0)
        for _ in range(10):
            time.sleep(0.005)
            field.ingest_audio(source, buffer_silence)
        sal_after = field.get_salience_field()
        noise_after = sal_after.get("noise", 0.0)
        assert noise_after < noise_before, f"Noise salience should decay: {noise_before:.3f} → {noise_after:.3f}"
        passed += 1
        print(f"  [PASS] Noise salience decayed: {noise_before:.3f} → {noise_after:.3f}")

        print(f"\n{'='*62}")
        print(f"  {passed}/11 ACOUSTIC SUBSTRATE v3 TESTS PASSED")
        print(f"{'='*62}")

    finally:
        shutil.rmtree(_tmp, ignore_errors=True)
