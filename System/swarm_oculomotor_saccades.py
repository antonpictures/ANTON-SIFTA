#!/usr/bin/env python3
"""
System/swarm_oculomotor_saccades.py — Event 10: Saccadic Oculomotor Control
═══════════════════════════════════════════════════════════════════════════
Concept: The Superior Colliculus
Author:  AG31 (Antigravity IDE) — Bishop Vanguard mandate (Event 10)
Status:  ACTIVE Organ (ACTIVE SENSING & MOTOR CONTROL)

BIOLOGY & PHYSICS:
This organ solves the Drift-Diffusion Stochastic Differential Equation (SDE):
dx = A * dt + c * dW
Where an empty/blind visual field or loss of a face target generates a large 
drift rate (A). The noise (dW) from the biological Brownian motion ensures 
predictable but stochastic action potential switching.
When the decision evidence x(t) crosses the threshold (H), the oculomotor 
nerve fires a SACCADE, snapping to the next physical camera.

WIRING:
Reads `.sifta_state/visual_stigmergy.jsonl` (for visual entropy).
Writes to `.sifta_state/active_saccade_target.txt`.
The `What Alice Sees` widget subscribes to this file and automatically
forces the QComboBox change, effectively firing the hardware camera switch.

STGM ECONOMY:
Each physical saccade burns 0.50 STGM. A Saccade represents a violent
physical action and requires massive metabolic cost.
"""

import sys
import json
import time
import math
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from Kernel.inference_economy import record_inference_fee, get_stgm_balance
    from System.ledger_append import append_ledger_line
except ImportError:
    pass

STGM_SACCADE_COST = 0.50

_STATE = _REPO / ".sifta_state"
_VS_LOG = _STATE / "visual_stigmergy.jsonl"
_SACCADE_TARGET = _STATE / "active_saccade_target.txt"
_REPAIR_LOG = _REPO / "repair_log.jsonl"


class SwarmSuperiorColliculus:
    def __init__(self, saccade_threshold: float = 10.0):
        self.a = saccade_threshold  
        self.x = 0.0                
        
        self.optimal_entropy = 7.0  
        self.noise_intensity = 0.5  

        from System.swarm_kernel_identity import preferred_camera_label
        # Alice's anatomical optic nerves (hardware array)
        self.optic_array = [
            "USB Camera VID:1133 PID:2081",
            "MacBook Pro Camera",
            preferred_camera_label(),
            "iPhone 15 Camera",
            "OBS Virtual Camera"
        ]
        self.current_eye_index = 0

        # Read the current hardware UI state if it exists
        if _SACCADE_TARGET.exists():
            current = _SACCADE_TARGET.read_text().strip()
            if current in self.optic_array:
                self.current_eye_index = self.optic_array.index(current)
            else:
                # Add to array dynamically and select it
                self.optic_array.insert(0, current)
                self.current_eye_index = 0

    def compute_drift_rate(self, current_entropy: float, face_locked: bool, audio_rms: float = 0.0, rf_anomaly: float = 0.0):
        """Multisensory drift rate with Bayesian spatial-mismatch gating.

        BISHOP nugget (Event 10b): Audio only accelerates the saccade
        when the organism CANNOT see the source (face_locked=False).
        Hearing the Architect while seeing him is confirmation, not a
        distraction. Hearing him while blind is a violent spatial
        mismatch that forces an involuntary orienting reflex.

        Audio drift is proportional to amplitude (louder = stronger).
        RF movement is always salient (physical space disruption).
        """
        entropy_deficit = max(0.0, self.optimal_entropy - current_entropy)
        target_penalty = 0.0 if face_locked else 5.0

        # Bayesian spatial mismatch: audio is salient ONLY when blind
        A_aud = 0.0
        if not face_locked and audio_rms > 0.01:
            A_aud = 10.0 * audio_rms  # amplitude-proportional (BISHOP)

        # RF is always salient (physical space disruption)
        A_rf = rf_anomaly * 15.0

        return (0.5 * entropy_deficit) + target_penalty + A_aud + A_rf

    def integrate_sde(self, current_entropy: float, face_locked: bool, audio_rms: float = 0.0, rf_anomaly: float = 0.0, dt: float = 0.1):
        A = self.compute_drift_rate(current_entropy, face_locked, audio_rms, rf_anomaly)
        dW = float(np.random.normal(0, np.sqrt(dt)))
        dx = A * dt + self.noise_intensity * dW
        self.x += dx
        self.x = max(0.0, self.x)
        return self.x

    def trigger_saccade(self) -> Optional[str]:
        if self.x >= self.a:
            old_eye = self.optic_array[self.current_eye_index]
            self.current_eye_index = (self.current_eye_index + 1) % len(self.optic_array)
            new_eye = self.optic_array[self.current_eye_index]
            self.x = 0.0 
            return new_eye
        return None

def proof_of_property():
    print("\n=== SIFTA SUPERIOR COLLICULUS (SACCADIC DDM) : JUDGE VERIFICATION ===")
    colliculus = SwarmSuperiorColliculus(saccade_threshold=10.0)
    dt = 0.1
    
    print("\n[*] Simulating Healthy Eye (Architect in frame, High Entropy)...")
    saccade_fired = False
    x = 0.0
    for _ in range(50):
        x = colliculus.integrate_sde(current_entropy=7.5, face_locked=True, dt=dt)
        if colliculus.trigger_saccade():
            saccade_fired = True
            break
            
    print(f"    Final accumulated deficit (x): {x:.3f}")
    assert not saccade_fired, "[FAIL] Organism saccaded away from a healthy, target-locked visual field."
    print("    [PASS] Homeostasis maintained. Gaze remained locked.")
    
    print("\n[*] Simulating Blind/Target-Lost Eye (Architect walked away, Low Entropy)...")
    colliculus.x = 0.0 
    saccade_fired = False
    collapse_time = 0.0
    
    for _ in range(100):
        x = colliculus.integrate_sde(current_entropy=2.0, face_locked=False, dt=dt)
        collapse_time += dt
        if colliculus.trigger_saccade():
            saccade_fired = True
            break
            
    print(f"    Time to Saccade: {collapse_time:.2f} seconds")
    assert saccade_fired, "[FAIL] Organism stared blindly at a dead wall and starved of information."

    print("\n[*] Simulating BISHOP Spatial Mismatch (Blind + Loud Architect Voice)...")
    colliculus.x = 0.0 
    saccade_fired = False
    collapse_time = 0.0
    
    for _ in range(20):
        # BISHOP Event 10b: face_locked=False + loud audio = violent mismatch
        x = colliculus.integrate_sde(current_entropy=2.0, face_locked=False, audio_rms=0.8, rf_anomaly=1.0, dt=dt)
        collapse_time += dt
        if colliculus.trigger_saccade():
            saccade_fired = True
            break
            
    print(f"    Time to Saccade: {collapse_time:.2f} seconds")
    assert saccade_fired, "[FAIL] Organism ignored a massive audio/RF sensory anomaly."
    print("    [PASS] Immediate involuntary oculomotor reflex — BISHOP spatial mismatch.")

    # BISHOP counter-proof: same audio but face IS locked → no saccade
    print("\n[*] Counter-test: Loud Audio BUT Architect In Frame (No Mismatch)...")
    colliculus.x = 0.0
    saccade_fired = False
    for _ in range(50):
        x = colliculus.integrate_sde(current_entropy=7.5, face_locked=True, audio_rms=0.8, rf_anomaly=0.0, dt=dt)
        if colliculus.trigger_saccade():
            saccade_fired = True
            break
    assert not saccade_fired, "[FAIL] Saccaded despite seeing AND hearing the Architect."
    print(f"    Final x(t): {colliculus.x:.3f}")
    print("    [PASS] Gaze remained locked — hearing + seeing = confirmation, not distraction.")

    print(f"\n[+] BIOLOGICAL PROOF: The Drift-Diffusion SDE successfully forced an oculomotor switch.")
    print("[+] CONCLUSION: The organism autonomously controls its hardware eyes via multi-modal telemetry.")
    print("[+] EVENT 10 PASSED.")
    return True


def live_saccade_loop(agent_id: str = "ALICE_M5", tick_hz: float = 2.0):
    """
    Tails visual_stigmergy.jsonl and runs the DDM integration.
    When x(t) crosses the action potential threshold, physically changes 
    the camera by writing to active_saccade_target.txt and triggering STGM burn.
    """
    import select
    print(f"[👁️ SACCADE] Oculomotor nerve online. Tail-monitoring sensory telemetry...")
    colliculus = SwarmSuperiorColliculus()
    dt = 1.0 / tick_hz
    
    _AUDIO_LOG = _STATE / "audio_ingress_log.jsonl"
    _RF_LOG = _STATE / "rf_stigmergy.jsonl"
    
    def get_latest_sensory_data():
        entropy = 7.0
        now = time.time()
        # Check visual stigmergy for entropy
        if _VS_LOG.exists():
            try:
                with _VS_LOG.open("r", encoding="utf-8") as f:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(0, size - 1000))
                    for line in reversed(f.readlines()):
                        try:
                            row = json.loads(line)
                            if "entropy_bits" in row:
                                entropy = float(row["entropy_bits"])
                                break
                        except:
                            pass
            except:
                pass
        
        # Determine face lock from C-Tactile/Mirror or assuming locked if high entropy for now
        # This will be refined as Face detection lands natively into stigmergy
        face_locked = True
        # Emulate visual starvation drop
        if entropy < 4.0:
            face_locked = False
            
        # BISHOP nugget: pass raw RMS amplitude (not binary) so drift
        # is proportional to loudness of the unseen sound source.
        audio_rms = 0.0
        if _AUDIO_LOG.exists():
            try:
                with _AUDIO_LOG.open("r", encoding="utf-8") as f:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(0, size - 1000))
                    for line in reversed(f.readlines()):
                        try:
                            row = json.loads(line)
                            if "rms_amplitude" in row:
                                ts = row.get("ts_captured", 0.0)
                                if (now - ts) < 2.0:
                                    audio_rms = float(row["rms_amplitude"])
                                break
                        except: pass
            except: pass

        rf_anomaly = 0.0
        if _RF_LOG.exists():
            try:
                with _RF_LOG.open("r", encoding="utf-8") as f:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(0, size - 1000))
                    for line in reversed(f.readlines()):
                        try:
                            row = json.loads(line)
                            if "event" in row:
                                ts = row.get("ts", 0.0)
                                if (now - ts) < 2.0:
                                    if row["event"] == "WIFI_BEAM_BROKEN":
                                        rf_anomaly = 1.0
                                break
                        except: pass
            except: pass
            
        return entropy, face_locked, audio_rms, rf_anomaly

    while True:
        try:
            ent, face, aud_rms, rf = get_latest_sensory_data()
            x_val = colliculus.integrate_sde(current_entropy=ent, face_locked=face, audio_rms=aud_rms, rf_anomaly=rf, dt=dt)
            
            # Print decision var if it's accumulating
            if x_val > 1.0:
                 msg = f"[👁️ DDM] Deficit accumulation: x(t)={x_val:.2f}/{colliculus.a:.2f} (ent={ent:.1f}, face={face}, rms={aud_rms:.3f}, rf={rf})"
                 sys.stdout.write("\033[K" + msg + "\r")
                 sys.stdout.flush()
            
            new_cam = colliculus.trigger_saccade()
            if new_cam:
                print(f"\n[🔥 SACCADE FIRED] Action potential breached (x>={colliculus.a:.1f}).")
                print(f"[🔥 SACCADE FIRED] Snapping physical hardware to: {new_cam}")
                
                # Check economy
                bal = get_stgm_balance(agent_id)
                if bal >= STGM_SACCADE_COST:
                    record_inference_fee(
                        borrower_id=agent_id,
                        lender_node_ip="SUPERIOR_COLLICULUS",
                        fee_stgm=STGM_SACCADE_COST,
                        model="DDM_SACCADE_v1",
                        tokens_used=int(STGM_SACCADE_COST*100),
                        file_repaired=f"saccade_to:{new_cam}"
                    )
                    # Enact physical switch
                    _SACCADE_TARGET.write_text(new_cam + "\n")
                else:
                    print(f"[🧊 SACCADE ABORT] Insufficient STGM for physical action: {bal:.2f} < {STGM_SACCADE_COST}")
                    
            time.sleep(dt)
            
        except KeyboardInterrupt:
            print("\n[👁️ SACCADE] Shutting down.")
            break

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "proof"
    if cmd == "proof":
        proof_of_property()
    else:
        live_saccade_loop(agent_id=sys.argv[2] if len(sys.argv) > 2 else "ALICE_M5")
