#!/usr/bin/env python3
"""
System/swarm_thalamic_guardian.py
══════════════════════════════════════════════════════════════════════
Concept: Thalamic Sensor Fusion (The Kalman Guardian)
Author:  BISHOP (The Mirage) — Biocode Olympiad (Event 11)
Status:  Active Organ

[WIRING]:
1. This is the 3D Sensor Fusion engine.
2. It tracks entities via State Vectors (Position, Velocity) and Covariance (Uncertainty).
3. Alice's camera switch logic checks `check_uncertainty_and_saccade()`. 
   When P exceeds the threshold, she MUST switch cameras to collapse the wave function.
"""

import numpy as np

class SwarmThalamicGuardian:
    def __init__(self, target_name="Daughter", uncertainty_threshold=50.0):
        """
        The Kalman Filter Sensor Fusion Engine.
        Maintains a continuous 2D spatial belief state of a target using 
        intermittent visual frames, audio waves, and WiFi telemetry.
        """
        self.target_name = target_name
        self.P_threshold = uncertainty_threshold
        
        # State vector x: [pos_x, pos_y, vel_x, vel_y]^T
        self.x = np.zeros((4, 1))
        
        # Covariance Matrix P (Uncertainty). Starts high until first measurement.
        self.P = np.eye(4) * 100.0 
        
        # State Transition Matrix F (Kinematic model for a walking human)
        self.dt = 1.0 # 1 second tick
        self.F = np.array([
            [1, 0, self.dt, 0],
            [0, 1, 0, self.dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])
        
        # Process Noise Covariance Q (Humans are unpredictable)
        self.Q = np.eye(4) * 1.5 
        
        # Measurement Matrices (H) and Noise (R) for different sensors
        # Vision: Direct observation of pos_x, pos_y. Very low noise.
        self.H_vision = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])
        self.R_vision = np.eye(2) * 0.1 
        
        # WiFi / Audio: Noisy proxies for position. High noise.
        self.H_wifi = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])
        self.R_wifi = np.eye(2) * 20.0 

    def predict_state(self):
        """
        Advances the biological clock. The target moves, and uncertainty grows.
        x = F*x,  P = F*P*F^T + Q
        """
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        
        current_uncertainty = np.trace(self.P)
        return current_uncertainty

    def update_measurement(self, measurement_z, sensor_type="WIFI"):
        """
        A sensor registers a hit (Photons, Sound waves, or WiFi).
        The Kalman Gain mathematically collapses the uncertainty.
        """
        if sensor_type == "VISION":
            H = self.H_vision
            R = self.R_vision
        else: # WIFI or AUDIO
            H = self.H_wifi
            R = self.R_wifi
            
        z = np.array(measurement_z).reshape(2, 1)
        
        # Innovation (Prediction Error)
        y = z - (H @ self.x)
        
        # Innovation Covariance
        S = H @ self.P @ H.T + R
        
        # Kalman Gain (K)
        K = self.P @ H.T @ np.linalg.inv(S)
        
        # Update State and collapse Covariance (Uncertainty)
        self.x = self.x + (K @ y)
        
        # P = (I - K*H) * P
        I = np.eye(4)
        self.P = (I - K @ H) @ self.P
        
        return np.trace(self.P)

    def check_uncertainty_and_saccade(self):
        """
        The Guardian Reflex.
        If uncertainty crosses the safety threshold, the organism violently 
        switches the camera to the target's expected sector to regain visual lock.
        """
        uncertainty = np.trace(self.P)
        if uncertainty > self.P_threshold:
            # Saccade triggered!
            # Return the expected location so the OS knows which camera to activate
            expected_sector = (self.x[0,0], self.x[1,0])
            return True, expected_sector
        return False, None

def proof_of_property() -> dict:
    """
    MANDATE VERIFICATION:
    Numerically proves that maintaining a spatial lock using only noisy WiFi/Audio 
    eventually degrades until the uncertainty threshold is breached. 
    Proves that a single camera frame ("BAM") mathematically collapses the covariance 
    matrix.
    """
    results = {}
    print("\n=== SIFTA THALAMIC GUARDIAN (KALMAN FILTER) : JUDGE VERIFICATION ===")
    
    guardian = SwarmThalamicGuardian(target_name="Daughter", uncertainty_threshold=30.0)
    
    # 1. Initial visual lock (Steady state)
    print("[*] Time -5 to 0: Initial visual lock established. (Steady State)")
    for t in range(5):
        guardian.predict_state()
        u_initial = guardian.update_measurement([5.0 + t, 5.0 + t], sensor_type="VISION")
    print(f"    Uncertainty (Trace P) after steady visual lock: {u_initial:.2f}")
    
    # 2. Camera switches away (e.g. to watch YouTube). 
    print("\n[*] Time 1-15: Camera switched to YouTube. Tracking via WiFi/Audio only...")
    u_wifi = u_initial
    for t in range(1, 16):
        guardian.predict_state()
        u_wifi = guardian.update_measurement([10.0 + t, 10.0 + t], sensor_type="WIFI")
        print(f"    Tick {t} Uncertainty: {u_wifi:.2f}")
        
    assert u_wifi > u_initial, "[FAIL] Uncertainty failed to grow while blind."
    results["uncertainty_growth"] = True
    
    # 3. Uncertainty breaches safety threshold
    trigger, sector = guardian.check_uncertainty_and_saccade()
    assert trigger is True, "[FAIL] Guardian failed to trigger a protective camera switch."
    print(f"\n[!] THRESHOLD BREACHED (U={u_wifi:.2f} > 30.0). Camera saccade triggered to Sector {sector[0]:.1f}, {sector[1]:.1f}!")
    results["saccade_triggered"] = True
    
    # 4. "Few frames-photons-BAM"
    print("\n[*] Time 6: Visual Camera active for 1 frame. Photons hit the sensor.")
    guardian.predict_state()
    u_recovered = guardian.update_measurement([10.0, 10.0], sensor_type="VISION")
    print(f"    Uncertainty (Trace P): {u_recovered:.2f}")
    
    assert u_recovered < u_wifi, "[FAIL] Visual frame failed to collapse the covariance matrix."
    results["matrix_collapsed"] = True
    
    reduction = (u_wifi / u_recovered)
    print(f"\n[+] BIOLOGICAL PROOF: A single camera frame collapsed spatial uncertainty by {reduction:.1f}x.")
    print("[+] CONCLUSION: The Kalman Filter successfully maintains omni-directional spatial dominance using intermittent sensors.")
    print("[+] EVENT 11 PASSED.")
    return results

if __name__ == "__main__":
    proof_of_property()
