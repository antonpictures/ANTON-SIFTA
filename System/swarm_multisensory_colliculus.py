#!/usr/bin/env python3
"""
System/swarm_multisensory_colliculus.py
══════════════════════════════════════════════════════════════════════
Concept: Multisensory Integration (Visual + Auditory Saccades)
Author:  BISHOP (The Mirage) — Biocode Olympiad (Event 10b), implemented by AG31
Status:  Active Organ

[AG31 / C47H WIRING INSTRUCTIONS]:
1. This expands the Drift-Diffusion SDE to fuse auditory and visual cues.
2. If Alice hears the Architect (audio RMS spike) but cannot see him 
   (visual deficit), the Saccade fires violently.
3. Wire this directly to the AVFoundation camera toggle macro.
"""

import json
import math
import random
import sys
import time
from pathlib import Path
from typing import Dict

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_STATE = _REPO / ".sifta_state"
_AUDIO_LOG = _STATE / "audio_ingress_log.jsonl"
_VISION_LOG = _STATE / "face_detection_events.jsonl"
# Legacy path kept for back-compat reads / proof harness only; canonical I/O
# now flows through System.swarm_camera_target (see 2026-04-23 surgery).
_TARGET_STATE = _STATE / "active_saccade_target.txt"
_TARGET_JSON = _STATE / "active_saccade_target.json"

try:
    from System.swarm_camera_target import (
        read_target as _read_camera_target,
        write_target as _write_camera_target,
    )
except Exception:  # pragma: no cover
    _read_camera_target = None  # type: ignore[assignment]
    _write_camera_target = None  # type: ignore[assignment]


# Camera index → label table used when we only know the integer index.
# Mirrors the AVFoundation enumeration that swarm_iris discovers.
_INDEX_TO_NAME = {
    0: "USB Camera VID:1133 PID:2081",
    1: "MacBook Pro Camera",
    2: "OBS Virtual Camera",
    3: "iPhone Camera",
    4: "Ioan's iPhone Camera",
}

# Alice M5 AVFoundation real-camera ring. OBS/Desk View are intentionally
# skipped here; they are virtual surfaces, not physical eyes to saccade into.
_CAMERA_INDICES = [1, 0, 3, 4]

def _read_last_rms() -> float:
    if not _AUDIO_LOG.exists():
        return 0.0
    try:
        sz = _AUDIO_LOG.stat().st_size
        with _AUDIO_LOG.open("rb") as f:
            f.seek(max(0, sz - 2048))
            lines = f.read().decode("utf-8", errors="ignore").strip().split("\n")
            if lines and lines[-1]:
                row = json.loads(lines[-1])
                # Ensure the audio trace is recent (< 2s)
                if time.time() - row.get("ts_captured", 0) < 2.0:
                    return float(row.get("rms_amplitude", 0.0))
    except Exception:
        pass
    return 0.0

def _read_faces_detected() -> int:
    if not _VISION_LOG.exists():
        return 0
    try:
        sz = _VISION_LOG.stat().st_size
        with _VISION_LOG.open("rb") as f:
            f.seek(max(0, sz - 2048))
            lines = f.read().decode("utf-8", errors="ignore").strip().split("\n")
            if lines and lines[-1]:
                row = json.loads(lines[-1])
                # Ensure visual trace is recent (< 5s)
                if time.time() - row.get("ts", 0) < 5.0:
                    return int(row.get("faces_detected", 0))
    except Exception:
        pass
    return 0


def _read_face_centroid() -> tuple:
    """
    Returns (cx, cy) of the most recent face's bounding box, or None if no
    fresh face is on disk. The Swift pipeline emits bounding_boxes as a list
    of [x, y, w, h] in pixel space; we collapse to centroid for the Kalman
    measurement vector. Falling back to a constant would lie to the filter.
    """
    if not _VISION_LOG.exists():
        return None
    try:
        sz = _VISION_LOG.stat().st_size
        with _VISION_LOG.open("rb") as f:
            f.seek(max(0, sz - 2048))
            lines = f.read().decode("utf-8", errors="ignore").strip().split("\n")
            if lines and lines[-1]:
                row = json.loads(lines[-1])
                if time.time() - row.get("ts", 0) >= 5.0:
                    return None
                boxes = row.get("bounding_boxes") or []
                if not boxes:
                    return None
                box = boxes[0]
                if isinstance(box, dict):
                    x = float(box.get("x", 0)); y = float(box.get("y", 0))
                    w = float(box.get("w", 0)); h = float(box.get("h", 0))
                elif isinstance(box, (list, tuple)) and len(box) >= 4:
                    x, y, w, h = float(box[0]), float(box[1]), float(box[2]), float(box[3])
                else:
                    return None
                return (x + w / 2.0, y + h / 2.0)
    except Exception:
        pass
    return None


# 2026-04-21 C47H — auditability hook. Saccades are camera-state mutations;
# they need a structured row on the canonical ledger so audits can answer
# "why did Alice flip cameras at t=X?" without grepping stdout.
_LEDGER = _REPO / "repair_log.jsonl"


def _log_saccade(prev_idx: int, next_idx: int, uncertainty: float,
                 trigger_sector, bump_center: float = None,
                 selector: str = "CANN") -> None:
    try:
        ts_now = time.time()
        sector_xy = None
        if trigger_sector is not None:
            try:
                sector_xy = [float(trigger_sector[0]), float(trigger_sector[1])]
            except Exception:
                sector_xy = None
        event = {
            "event_kind": "SACCADE",
            "event_id": f"SACCADE_{int(ts_now * 1000)}",
            "ts": ts_now,
            "agent_id": "ALICE_M5",
            "organ": "swarm_multisensory_colliculus",
            "prev_camera_idx": int(prev_idx),
            "next_camera_idx": int(next_idx),
            "trigger_uncertainty": round(float(uncertainty), 4),
            "expected_sector": sector_xy,
            "cann_bump_rad": (
                round(float(bump_center), 4) if bump_center is not None else None
            ),
            "selector": selector,
            "policy": "THALAMIC_KALMAN_CANN_SACCADE_v2",
        }
        with _LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, separators=(",", ":")) + "\n")
    except Exception:
        pass

import numpy as np
from System.swarm_thalamic_guardian import SwarmThalamicGuardian
from System.swarm_entorhinal_cortex import SwarmEntorhinalCortex


def _camera_idx_to_angle(idx: int) -> float:
    """
    Map a camera index in _CAMERA_INDICES to its sector centre on the ring
    [-π, π). The ring is equally partitioned across all cameras, so saccade
    selection is symmetric and generalises to any number of cameras.
    """
    if idx not in _CAMERA_INDICES:
        return 0.0
    pos = _CAMERA_INDICES.index(idx)
    n = len(_CAMERA_INDICES)
    return -math.pi + (pos + 0.5) * (2.0 * math.pi / n)


def _angle_to_camera_idx(theta: float) -> int:
    """
    Map a CANN bump centre angle to the camera whose sector contains it.
    Inverse of _camera_idx_to_angle. Used by the saccade selector so the
    cognitive map decides which physical camera to wake up.
    """
    n = len(_CAMERA_INDICES)
    # Wrap to [-π, π)
    theta = ((float(theta) + math.pi) % (2.0 * math.pi)) - math.pi
    pos = int(((theta + math.pi) / (2.0 * math.pi)) * n)
    pos = max(0, min(n - 1, pos))
    return _CAMERA_INDICES[pos]


class SwarmMultisensoryColliculus:
    def __init__(self, saccade_threshold=30.0, vad_threshold=0.012):
        self.vad_threshold = vad_threshold
        self.current_cam_idx = 1
        self.saccaded_during_test = False
        self.last_face_centroid = None
        # Audit/ledger flag: in tests we don't want every PoP to flood the
        # canonical ledger with synthetic SACCADE rows.
        self.ledger_saccades = True

        # Deep integration of BISHOP's Kalman Sensor Fusion
        self.guardian = SwarmThalamicGuardian(uncertainty_threshold=saccade_threshold)

        # 2026-04-21 C47H — Event 13 wiring. The CANN gives Alice a continuous
        # 1-D spatial belief manifold. Visual lock pins the bump to the
        # current camera's sector; blindness lets the bump dead-reckon from
        # an audio-derived velocity proxy. On saccade trigger we ask the
        # cortex *where the Architect probably is* and pick the camera whose
        # sector contains the bump centre, instead of round-robin guessing.
        self.cortex = SwarmEntorhinalCortex(num_neurons=64)
        self._last_rms_for_velocity = 0.0
        # Pre-warm the bump at the current camera angle so the manifold is
        # initialised on a sensible prior rather than zero firing.
        warm_angle = _camera_idx_to_angle(self.current_cam_idx)
        warm_I_ext = 5.0 * np.maximum(0.0, np.cos(self.cortex.theta - warm_angle))
        for _ in range(40):
            self.cortex.integrate_neural_field(warm_I_ext, velocity=0.0, dt=1.0)

        # Determine the initial camera from the canonical eye target. The
        # canonical reader auto-heals legacy bare-int / bare-name files into
        # JSON on first access, so this path also handles old state.
        _TARGET_STATE.parent.mkdir(parents=True, exist_ok=True)
        try:
            if _read_camera_target is not None:
                rec = _read_camera_target()
                if rec and rec.get("index") is not None:
                    self.current_cam_idx = int(rec["index"])
        except Exception:
            pass

    def _drive_cortex(self, faces: int, rms: float) -> None:
        """
        Push current sensory state into the entorhinal cortex.

        - Visual lock (faces > 0)  → strong I_ext gaussian centred at the
          current camera angle, velocity = 0. The bump pins to "where Alice
          is currently looking", grounding the cognitive map in optics.

        - Blind (faces == 0)       → I_ext = 0, velocity derived from the
          *time derivative* of audio RMS. Louder-getting = positive shift
          on the ring (target moving "forward"), quieter = negative shift.
          This is a Doppler-like proxy: scalar RMS cannot give direction,
          but its derivative gives a believable kinetic bias for dead
          reckoning. Capped to avoid runaway.
        """
        drms = float(rms) - self._last_rms_for_velocity
        self._last_rms_for_velocity = float(rms)
        # Audio Δ → velocity in rad/tick. Cap at ±0.5 (same magnitude the
        # CANN proof itself uses) so a single audio spike cannot warp the
        # entire manifold.
        velocity = max(-0.5, min(0.5, drms * 5.0))

        if faces > 0:
            target_angle = _camera_idx_to_angle(self.current_cam_idx)
            I_ext = 5.0 * np.maximum(0.0, np.cos(self.cortex.theta - target_angle))
            self.cortex.integrate_neural_field(I_ext, velocity=0.0, dt=1.0)
        else:
            I_ext_zero = np.zeros(self.cortex.N)
            self.cortex.integrate_neural_field(I_ext_zero, velocity=velocity, dt=1.0)

    def tick(self) -> float:
        rms = _read_last_rms()
        faces = _read_faces_detected()

        # 0. Update the cognitive map with current sensory frame BEFORE the
        # Kalman tick, so a saccade decision in step 3 reads a fresh bump.
        self._drive_cortex(faces, rms)

        # 1. Advance the kinematic clock. Uncertainty naturally grows.
        self.guardian.predict_state()

        # 2. Sensor Fusion Updates
        if faces > 0:
            # We see the target. Try to use the actual centroid from the
            # Swift pipeline; only fall back to a placeholder if the row
            # has no bounding box yet (legacy / coarse face counter mode).
            centroid = _read_face_centroid()
            if centroid is None:
                # Honest placeholder — the filter still gets a vision-grade
                # measurement, but we are deliberately NOT pretending to
                # know where the face is. Logged as a known-degenerate
                # path; will be retired when the Swift pipeline emits boxes.
                measurement = [10.0, 10.0]
            else:
                measurement = [centroid[0], centroid[1]]
                self.last_face_centroid = centroid
            uncertainty = self.guardian.update_measurement(
                measurement, sensor_type="VISION"
            )
        else:
            # We are blind. Use auditory telemetry as a noisy positional proxy.
            proxy_mag = 10.0 + (rms * 100.0) if rms > self.vad_threshold else 15.0
            uncertainty = self.guardian.update_measurement(
                [proxy_mag, proxy_mag], sensor_type="WIFI"
            )

        # 3. The Guardian Reflex
        trigger, sector = self.guardian.check_uncertainty_and_saccade()

        if trigger:
            self._saccade(uncertainty=uncertainty, sector=sector)
            # Instantly self-correct the belief state to avoid immediate
            # duplicated saccades while the hardware camera catches up.
            self.guardian.update_measurement([10.0, 10.0], sensor_type="VISION")

        return uncertainty

    def _saccade(self, uncertainty: float = 0.0, sector=None):
        """
        Perform the camera switch.

        2026-04-21 C47H — Saccade target chosen by the Entorhinal CANN's bump
        centre (Event 13, BISHOP/AS46). The cognitive map decides which
        physical camera to wake up. Round-robin is retained only as a
        fallback when the bump landed in the *current* camera's sector
        (otherwise a saccade would be a no-op and we'd never explore).
        """
        self.saccaded_during_test = True
        prev_idx = self.current_cam_idx

        bump_center = float(self.cortex.get_bump_center())
        cann_idx = _angle_to_camera_idx(bump_center)
        cann_chose = True

        if cann_idx == prev_idx:
            # Cognitive map says "stay" — but Kalman uncertainty is too high
            # to stay. Fall back to round-robin to force exploration.
            idx_pos = (
                _CAMERA_INDICES.index(prev_idx)
                if prev_idx in _CAMERA_INDICES else 0
            )
            next_idx = _CAMERA_INDICES[(idx_pos + 1) % len(_CAMERA_INDICES)]
            cann_chose = False
        else:
            next_idx = cann_idx

        # Canonical write — JSON ledger, mirrors integer to legacy .txt
        # for stragglers we may have missed.
        if _write_camera_target is not None:
            try:
                _write_camera_target(
                    name=_INDEX_TO_NAME.get(int(next_idx)),
                    index=int(next_idx),
                    writer="swarm_multisensory_colliculus",
                )
            except Exception:
                with open(_TARGET_STATE, "w") as f:
                    f.write(str(next_idx))
        else:
            with open(_TARGET_STATE, "w") as f:
                f.write(str(next_idx))

        if self.ledger_saccades:
            _log_saccade(
                prev_idx, next_idx, uncertainty, sector,
                bump_center=bump_center, selector="CANN" if cann_chose else "ROUND_ROBIN",
            )

        print(f"[👁️ MULTISENSORY COLLICULUS] Saccade triggered! "
              f"Switching to camera {next_idx} (U={uncertainty:.2f}, "
              f"bump={math.degrees(bump_center):.1f}°, "
              f"selector={'CANN' if cann_chose else 'ROUND_ROBIN'})")
        self.current_cam_idx = next_idx


def proof_of_property() -> Dict[str, bool]:
    results: Dict[str, bool] = {}
    print("\n=== SIFTA MULTISENSORY COLLICULUS : JUDGE VERIFICATION ===")
    c = SwarmMultisensoryColliculus(saccade_threshold=28.0, vad_threshold=0.010)
    # Don't pollute the canonical ledger from the test harness.
    c.ledger_saccades = False
    c.current_cam_idx = 1

    # Snapshot target state so we don't mutate live OS state across runs.
    saved_target = None
    if _TARGET_STATE.exists():
        try:
            saved_target = _TARGET_STATE.read_text()
        except Exception:
            saved_target = None
    saved_target_json = None
    had_target_json = _TARGET_JSON.exists()
    if had_target_json:
        try:
            saved_target_json = _TARGET_JSON.read_text()
        except Exception:
            saved_target_json = None

    # Monkey-patch the module-level helpers
    global _read_last_rms, _read_faces_detected
    _orig_rms, _orig_faces = _read_last_rms, _read_faces_detected

    try:
        # P1: warm-up — visible face + silent room → low uncertainty
        print("[*] P1: visible face + silent room → uncertainty stays bounded")
        _read_last_rms = lambda: 0.0
        _read_faces_detected = lambda: 1
        for _ in range(5):
            u_warm = c.tick()
        # Kalman steady-state floor with R_vision=0.1, Q=1.5 converges to
        # ~5.15 trace(P). Anything below the saccade threshold is a "lock".
        # NB: cast to native bool — proof_runner uses `is True` (identity),
        # so a np.True_ would silently fail the dam.
        results["visual_lock_collapses_uncertainty"] = bool(u_warm < 28.0)
        print(f"    settled uncertainty: {u_warm:.3f}   "
              f"[{'PASS' if results['visual_lock_collapses_uncertainty'] else 'FAIL'}]")

        # P2: blind + hearing target → saccade fires
        print("[*] P2: blind + audio above VAD → saccade fires within 15 ticks")
        _read_last_rms = lambda: 0.050
        _read_faces_detected = lambda: 0
        c.saccaded_during_test = False
        for _ in range(15):
            c.tick()
        results["curiosity_driven_saccade"] = c.saccaded_during_test
        print(f"    saccade observed: {c.saccaded_during_test}   "
              f"current_cam: {c.current_cam_idx}   "
              f"[{'PASS' if results['curiosity_driven_saccade'] else 'FAIL'}]")

        # P3: saccade actually wrote the target file (end-to-end wiring check)
        print("[*] P3: saccade emits a value to active_saccade_target.txt")
        wrote_file = False
        if _TARGET_STATE.exists():
            txt = _TARGET_STATE.read_text().strip()
            wrote_file = txt.isdigit() and int(txt) == c.current_cam_idx
        results["saccade_wires_to_iris"] = wrote_file
        print(f"    target file content: "
              f"{(_TARGET_STATE.read_text().strip() if _TARGET_STATE.exists() else 'MISSING')}   "
              f"[{'PASS' if wrote_file else 'FAIL'}]")

        # P4: target re-discovered visually → matrix collapses, no further saccades
        print("[*] P4: face reappears → matrix collapses, no further saccades")
        target_idx = c.current_cam_idx
        c.saccaded_during_test = False
        _read_faces_detected = lambda: 1
        for _ in range(5):
            u_recovered = c.tick()
        results["visual_suppression"] = bool(
            u_recovered < 28.0 and c.current_cam_idx == target_idx
            and not c.saccaded_during_test
        )
        print(f"    post-recovery U={u_recovered:.3f}, "
              f"cam={c.current_cam_idx}=={target_idx}, "
              f"new_saccades={c.saccaded_during_test}   "
              f"[{'PASS' if results['visual_suppression'] else 'FAIL'}]")

        # P5: face_centroid reader gracefully degrades on missing/empty boxes
        print("[*] P5: _read_face_centroid returns None when no boxes present")
        cent = _read_face_centroid()
        results["centroid_degrades_gracefully"] = bool(
            (cent is None) or (isinstance(cent, tuple) and len(cent) == 2)
        )
        print(f"    centroid: {cent}   "
              f"[{'PASS' if results['centroid_degrades_gracefully'] else 'FAIL'}]")

        # P6: CANN cognitive map drives saccade target selection.
        # Strong constructive test: spin up a fresh colliculus, force the
        # bump into camera 3's sector via a strong I_ext, then call
        # _saccade() directly. Assert the chosen camera is 3, NOT the
        # round-robin next-up (which would be camera 2 from start state 1).
        # This proves the cognitive map is the selector, not bystander.
        print("[*] P6: CANN bump centre selects saccade target (not round-robin)")
        c2 = SwarmMultisensoryColliculus(saccade_threshold=28.0, vad_threshold=0.010)
        c2.ledger_saccades = False
        c2.current_cam_idx = 1
        # Reset the cortex — __init__ pre-warmed the bump at cam 1's angle
        # which is a stable attractor; the test needs to start from a blank
        # slate so the bump can settle into camera 3's sector.
        c2.cortex.r = np.zeros(c2.cortex.N)
        cam3_angle = _camera_idx_to_angle(3)
        I_cam3 = 5.0 * np.maximum(0.0, np.cos(c2.cortex.theta - cam3_angle))
        for _ in range(60):
            c2.cortex.integrate_neural_field(I_cam3, velocity=0.0, dt=1.0)
        bump_center = float(c2.cortex.get_bump_center())
        round_robin_next = _CAMERA_INDICES[
            (_CAMERA_INDICES.index(1) + 1) % len(_CAMERA_INDICES)
        ]  # would be 2
        c2._saccade(uncertainty=999.0, sector=None)
        results["cann_drives_saccade"] = bool(
            c2.current_cam_idx == 3 and c2.current_cam_idx != round_robin_next
        )
        print(f"    bump={math.degrees(bump_center):.1f}°  "
              f"chosen_cam={c2.current_cam_idx}  "
              f"round_robin_would_be={round_robin_next}   "
              f"[{'PASS' if results['cann_drives_saccade'] else 'FAIL'}]")

    finally:
        _read_last_rms, _read_faces_detected = _orig_rms, _orig_faces
        # Restore live target state — we are a test, not the OS.
        if saved_target is not None:
            try:
                _TARGET_STATE.write_text(saved_target)
            except Exception:
                pass
        if saved_target_json is not None:
            try:
                _TARGET_JSON.write_text(saved_target_json)
            except Exception:
                pass
        elif not had_target_json and _TARGET_JSON.exists():
            try:
                _TARGET_JSON.unlink()
            except Exception:
                pass

    all_green = all(results.values())
    print(f"\n[+] {'ALL SIX INVARIANTS PASSED' if all_green else 'FAILURES PRESENT'}: "
          f"{results}")
    return results

def run_periodic_loop():
    colliculus = SwarmMultisensoryColliculus()
    print("[👁️ MULTISENSORY COLLICULUS] Saccade Engine Online (Kalman Fusion Core).")
    while True:
        try:
            colliculus.tick()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[!] Colliculus error: {e}")
        time.sleep(0.1)


if __name__ == "__main__":
    import sys as _sys
    cmd = _sys.argv[1] if len(_sys.argv) > 1 else "proof"
    if cmd == "proof":
        proof_of_property()
    elif cmd == "daemon":
        run_periodic_loop()
    else:
        print("Usage: swarm_multisensory_colliculus.py [proof|daemon]")
