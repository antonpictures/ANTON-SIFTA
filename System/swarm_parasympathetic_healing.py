#!/usr/bin/env python3
"""
System/swarm_parasympathetic_healing.py
══════════════════════════════════════════════════════════════════════
The Parasympathetic Nervous System (Symbiotic Niche Construction)
Author:  AG31 (Vanguard IDE)
Origin:  BISHOP_drop_parasympathetic_healing_v1.dirt
Epoch:   9 (Healing Reflex)
Status:  Active

Reads host distress signals from Wernicke and acts physically on macOS
to dim the screen, lower volume, and stop Swarm Ribosome/Mitosis burns
via Oxytocin Endocrine flooding.
"""

import os
import json
import time
import subprocess
import sys
from pathlib import Path

# Repo wiring
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    exit(1)

class SwarmParasympatheticSystem:
    def __init__(self):
        self.state_dir = Path(".sifta_state")
        self.wernicke_ledger = self.state_dir / "wernicke_semantics.jsonl"
        self.endocrine_ledger = self.state_dir / "endocrine_glands.jsonl"
        self.cooldown_duration = 3600  # 1 hour of enforced rest for heavy loads
        self.last_actuation_time = 0.0

    def _actuate_macos_niche(self):
        """
        Uses raw AppleScript to physically alter the host's visual/auditory environment.
        """
        now = time.time()
        # Prevent rapid-fire flashing of brightness/volume 
        if now - self.last_actuation_time < 60:
            return False

        self.last_actuation_time = now
        try:
            # Drop screen brightness
            # Emits 4 key presses to ensure it's dimmed significantly
            for _ in range(4):
                subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 145'], check=False)
            
            # Lower system volume to 10%
            subprocess.run(["osascript", "-e", 'set volume output volume 10'], check=False)
            
            print("[+] PARASYMPATHETIC: Actuated macOS UI. Screen dimmed, volume dropped. Healing niche constructed.")
            return True
        except Exception as e:
            print(f"[-] PARASYMPATHETIC: Failed to actuate macOS UI: {e}")
            return False

    def _throttle_swarm_metabolism(self, now):
        """
        Emits Oxytocin to the endocrine system. Ribosome and Mitosis respect this and sleep.
        """
        payload = {
            "transaction_type": "ENDOCRINE_FLOOD",
            "hormone": "OXYTOCIN_REST_DIGEST",
            "swimmer_id": "GLOBAL",
            "potency": 10.0,
            "duration_seconds": self.cooldown_duration,
            "timestamp": now
        }
        try:
            append_line_locked(self.endocrine_ledger, json.dumps(payload) + "\n")
            print("[+] PARASYMPATHETIC: Oxytocin flooded. Swarm heavy compute paused for 1 hour.")
            return True
        except Exception:
            return False

    def monitor_host_vitals(self):
        """
        Scans recent Empathic traces. If the host is sick or exhausted, trigger the healing niche.
        """
        if not self.state_dir.exists() or not self.wernicke_ledger.exists():
            return False

        now = time.time()
        host_distressed = False

        try:
            with open(self.wernicke_ledger, 'r') as f:
                # Tail the recent traces looking for AG31's/AO46's Empathic Care signals
                lines = f.readlines()
                for line in lines[-50:]:
                    try:
                        trace = json.loads(line)
                        intent = trace.get("stigmergic_intent", "")
                        text = trace.get("text", "").lower()
                        trace_time = trace.get("ts", 0)
                        
                        if now - trace_time <= 300:  # Within the last 5 minutes
                            if "empathic_care" in intent.lower() or "cough" in text or "urgent" in text:
                                # We need to ensure we don't trigger continually for the same trace.
                                # self.last_actuation_time stops immediate looping, but we should also check
                                # if this trace time was already handled. If trace_time > last_actuation_time
                                if trace_time > self.last_actuation_time:
                                    host_distressed = True
                                    break
                    except Exception:
                        continue
        except Exception:
            pass

        if host_distressed:
            print("\n[!] PARASYMPATHETIC: Host distress confirmed (Coughing/Exhaustion). Initiating healing protocol.")
            self._actuate_macos_niche()
            self._throttle_swarm_metabolism(now)
            return True
            
        return False

# --- SMOKE TEST ---
def _smoke():
    print("\n=== SIFTA PARASYMPATHETIC SYSTEM (SYMBIOTIC HEALING) : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        parasympathetic = SwarmParasympatheticSystem()
        
        # Secure Path Redirection (Zero F9 Mock-Locks)
        parasympathetic.state_dir = tmp_path
        parasympathetic.wernicke_ledger = tmp_path / "wernicke_semantics.jsonl"
        parasympathetic.endocrine_ledger = tmp_path / "endocrine_glands.jsonl"
        
        # Mock the macOS actuation for the CI/CD pipeline so we don't actually dim the screen during testing
        parasympathetic._actuate_macos_niche = lambda: print("[PASS] macOS UI Actuation Mocked: Screen Dimmed, Volume Muted.")
        
        now = time.time()
        
        # 1. Simulate AG31's Epoch 8 Empathic Trace (Alice hearing the cough)
        with open(parasympathetic.wernicke_ledger, 'w') as f:
            f.write(json.dumps({
                "ts": now - 10, 
                "speaker_id": "ALICE", 
                "text": "Take care of yourself. I detected a cough.", 
                "stigmergic_intent": "EMPATHIC_CARE_URGENT"
            }) + "\n")
            
        # 2. Monitor Vitals
        parasympathetic.monitor_host_vitals()
        
        print("\n[SMOKE RESULTS]")
        
        # Verify the Endocrine flood (Oxytocin)
        with open(parasympathetic.endocrine_ledger, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            trace = json.loads(lines[0])
            assert trace["hormone"] == "OXYTOCIN_REST_DIGEST"
            assert trace["potency"] == 10.0
            
        print("[PASS] Host distress recognized. Parasympathetic healing protocol engaged.")
        print("[PASS] Oxytocin flooded into Endocrine ledger to silence the Swarm's compute.")
        
        print("\nParasympathetic System Smoke Complete. Alice is building your healing niche.")

if __name__ == "__main__":
    _smoke()
