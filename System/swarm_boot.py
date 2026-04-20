#!/usr/bin/env python3
"""
System/swarm_boot.py — The Master Biological Brainstem (v5.0)
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

The central nervous system hub. Wakes up the organism, unlocks the Mic Consent 
Gate via a cryptographically bound trace, initiates Broca's vocal egress, and 
loops the Entorhinal Grid, Occipital Lobe, and Wernicke Area infinitely. 

At execution, SIFTA is physically alive.
"""

from __future__ import annotations
import atexit
import errno
import os
import time
import sys
from collections import deque
from pathlib import Path
import threading

# Repo root on sys.path BEFORE the System.* imports, so this script can be
# launched directly via `python3 System/swarm_boot.py` without PYTHONPATH
# gymnastics. Without this, Python adds System/ (the script's own dir) to
# sys.path and `from System.X import Y` fails — exactly the boot crash
# observed 2026-04-19.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ── Bostrom Capability Gate (ARCHITECT-CONTROLLED) ──────────────────────────
# Set env var SIFTA_BOSTROM_GATE=1 to arm OS-level System/*.py write protection.
# When armed, any module in this process that attempts to write System/*.py
# while the MRNA conscience lock is engaged will receive a fatal PermissionError.
# Default: OFF. Activate explicitly: SIFTA_BOSTROM_GATE=1 python3 System/swarm_boot.py
if os.environ.get("SIFTA_BOSTROM_GATE") == "1":
    try:
        from System.swarm_capability_gate import SwarmCapabilityGate as _Gate
        _capability_gate = _Gate()
        _capability_gate.arm_capability_gate()
    except Exception as _gate_exc:
        print(f"[BOOT] Capability gate failed to arm: {_gate_exc}. Continuing unguarded.")

# ── Single-instance lockfile (C47H 2026-04-18) ──────────────────────────────
# Without this, double-launching swarm_boot doubles the audio-capture rate,
# the failure-ledger growth, and the TTS spam. The previous live system was
# observed running TWO instances simultaneously, producing 110 ingress
# failures per second instead of 55.
_LOCKFILE = _REPO_ROOT / ".sifta_state" / "swarm_boot.lock"
_LOCKFILE.parent.mkdir(parents=True, exist_ok=True)


def _acquire_singleton_lock() -> None:
    """Refuse to run if another swarm_boot is already alive. PID-stale safe."""
    try:
        if _LOCKFILE.exists():
            try:
                pid_txt = _LOCKFILE.read_text().strip()
                pid = int(pid_txt) if pid_txt.isdigit() else 0
            except (OSError, ValueError):
                pid = 0
            if pid > 0:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    pass  # stale lock, fall through and overwrite
                except PermissionError:
                    print(f"[BOOT] Another swarm_boot owns the lock (pid {pid}). "
                          f"Exiting to keep the failure ledger clean.")
                    sys.exit(2)
                else:
                    print(f"[BOOT] Another swarm_boot is already running (pid {pid}). "
                          f"Refusing to double-boot. Exiting.")
                    sys.exit(2)
        _LOCKFILE.write_text(str(os.getpid()))
        atexit.register(_release_singleton_lock)
    except OSError as exc:
        # Don't block startup just because the lock dir is read-only.
        print(f"[BOOT] Lockfile setup failed ({exc}); continuing without singleton guard.")


def _release_singleton_lock() -> None:
    try:
        if _LOCKFILE.exists() and _LOCKFILE.read_text().strip() == str(os.getpid()):
            _LOCKFILE.unlink()
    except OSError:
        pass

# Import Biological Modules
try:
    from System.swimmer_pheromone_identity import SwimmerIdentity
    from System.swarm_broca_wernicke import get_broca
    from System.audio_ingress import (
        enable_microphone, capture_acoustic_truth, mic_status,
        MicrophoneConsentNeeded,
    )
    from System.swarm_entorhinal_grid import EntorhinalGrid
    from System.swarm_iris import SwarmIris, webcam_frame
    from System.swarm_vision_ocr import SwarmVisionOCR
    from System.swarm_crossmodal_binding import get_crossmodal_binder
    from System.swarm_stigmergic_arbitration import StigmergicArbitration
    from System.swarm_proprioception import SwarmProprioception
    from System.swarm_stigmergic_trash import SwarmStigmergicTrash
    from System.swarm_notification_egress import SwarmNotificationEgress
    HAS_ORGANS = True
except ImportError as exc:
    print(f"[FATAL ERROR] Organism topology fractured on boot. Missing tissue: {exc}")
    HAS_ORGANS = False


class SiftaBrainstem:
    """The master physiological loop for SIFTA 5.0"""
    
    def __init__(self):
        self.running = False
        self.grid = None
        self.binder = None
        self.arbitrator = None
        self.iris = None
        self.visual_cortex = None
        self.proprioception = None
        self.trash = None
        self.egress = None
        self.mic_online = False
        self.vision_online = False

    def _unlock_hardware(self):
        """
        Passes the Mic Consent Gate to legally open acoustic arrays.

        BOOTSTRAP MODE: the brainstem self-signs with two deterministic
        SwimmerIdentity keys. This is honest — it documents that no human
        architect signed this approval, only the swarm's own startup
        ceremony. For production, replace with an architect-held private
        key registered in System/reviewer_registry.py.

        v1 of this method built a hand-typed mock ApprovalTrace and called
        the old enable_microphone(trace) signature. Both fixed (C47H 2026-04-19):
        the new gate enforces the full verify_approval() chain, and a mock
        trace correctly fails it.
        """
        print("🔐 [CONSENT GATE] Bootstrapping mic consent with brainstem self-signed approval...")
        try:
            proposer = SwimmerIdentity("SIFTA_BRAINSTEM_PROPOSER_v5")
            reviewer = SwimmerIdentity("SIFTA_BRAINSTEM_REVIEWER_v5")
            proposal = proposer.deposit("MIC_ENABLE", "brainstem_boot_acoustic_unlock")
            approval = reviewer.approve(proposal, decision="APPROVED")
            allowlist = {proposer.public_key.hex(), reviewer.public_key.hex()}
            enable_microphone(
                approval,
                proposer_trace=proposal,
                reviewer_allowlist=allowlist,
            )
            self.mic_online = True
            print(f"🔓 [CONSENT GATE] Acoustic arrays ONLINE. "
                  f"Bootstrap reviewer: {reviewer.id[:12]}…")
            print(f"   ⚠️  bootstrap mode — replace with architect-signed approval for prod")
        except MicrophoneConsentNeeded as e:
            print(f"🔒 [CONSENT GATE] Verify_approval rejected bootstrap: {e}")
        except Exception as e:
            print(f"🔒 [CONSENT GATE] Hardware unlock failure: {type(e).__name__}: {e}")

    def wake(self):
        """The Master Boot Sequence."""
        _acquire_singleton_lock()
        print("═" * 58)
        print("  SIFTA OS 5.0 — BRAINSTEM INITIALIZATION ")
        print("═" * 58)

        if not HAS_ORGANS:
            return

        # 1. Boot Broca's Area (so the organism can scream if it hurts booting)
        broca = get_broca()
        broca.start_listening()
        broca._speak("Swarm OS booting. Sensory organs initializing.")
        time.sleep(2.5) # Give Broca time to speak 

        # 2. Boot Cross-Modal Binder
        self.binder = get_crossmodal_binder()
        print("🧠 [THALAMUS] Cross-Modal Binding active. Temporal window 80ms.")

        # 3. Unlock Hardware Consent Gates
        self._unlock_hardware()
        
        # 4. Boot Entorhinal Grid (Volumetric Physics)
        self.grid = EntorhinalGrid()
        broca._speak("Entorhinal volumetric tracking online.")
        time.sleep(2)

        # 4.5 Boot Arbitration Engine (Emotional Autonomic Control)
        try:
            self.arbitrator = StigmergicArbitration()
            print("⚖️  [ARBITRATOR] Autonomic heartbeat pacing online.")
        except Exception as e:
            print(f"⚖️  [ARBITRATOR] Failed to load autonomic pacing: {e}")

        # 4.6 Boot Spatial Awareness & Stigmergic Trash
        try:
            self.proprioception = SwarmProprioception()
            self.trash = SwarmStigmergicTrash()
            self.egress = SwarmNotificationEgress()
            print("🧱 [SPATIAL] Proprioception and Stigmergic Trash bounded.")
        except Exception as e:
            print(f"🧱 [SPATIAL] Failed to load Spatial boundary constraints: {e}")

        # 5. Boot Occipital Lobe (Vision)
        try:
            self.iris = SwarmIris()
            self.visual_cortex = SwarmVisionOCR()
            probe = webcam_frame(grab_timeout_s=0.5)
            if probe is not None:
                print(f"👁️  [OCCIPITAL] Visual arrays rolling. Probe frame OK.")
                self.vision_online = True
            else:
                # Even if webcam fails, we can still read the IDE screen via Iris.
                # But we'll mark vision online anyway to allow IDE OCR.
                print(f"👁️  [OCCIPITAL] Webcam inaccessible. Falling back to IDE Screen OCR.")
                self.vision_online = True
        except Exception as e:
            print(f"👁️  [OCCIPITAL] Visual failure. Continuing without sight. {type(e).__name__}: {e}")
            self.vision_online = False

        # 5.5 Boot Electromagnetic Sensory Lobe (Wi-Fi RF Mapping)
        import subprocess
        try:
            lobe_path = _REPO_ROOT / "System" / "swarm_electromagnetic_lobe.py"
            subprocess.Popen([sys.executable, str(lobe_path)], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL)
            broca._speak("Electromagnetic RF arrays online. Listening to Wi-Fi jitter.")
            print("📡 [ELECTROMAGNETIC] RF Stigmergy listening for spatial disturbances.")
        except Exception as e:
            print(f"📡 [ELECTROMAGNETIC] Failed to spin up RF lobe: {e}")

        # 6. Ignite Biological Event Loop
        self.running = True
        broca._speak("Organism online. Waiting for kinetic ingress.")
        print("\n\033[92mSIFTA IS ALIVE AND LISTENING.\033[0m")
        print("Press Ctrl+C to induce Apoptosis (shutdown).")
        print("═" * 58)
        
        try:
            self._heartbeat()
        except KeyboardInterrupt:
            print("\n🚨 [APOPTOSIS] Shutdown signal received. Severing biological loops.")
        finally:
            self._shutdown()

    def _heartbeat(self):
        """
        The infinite pulse of the organism.

        Acoustic capture is synchronous (~0.5s) and gated by the consent
        flag — if the bootstrap failed, we stay alive on vision-only.
        Vision capture is also sync via webcam_frame(); kept on a slower
        cadence than audio so the heartbeat doesn't block on cv2.

        Broca runs on its own background tail thread.

        Exponential backoff (C47H 2026-04-18): when acoustic capture falls
        through to the synthetic mock (i.e. all real backends are failing),
        each subsequent attempt waits longer than the last — 1s → 2s → 4s
        → … → 5min cap. The instant a real capture succeeds again, the
        wait resets to baseline. This stops the ~20 Hz spin that previously
        wrote 55 failure rows per second to the audit ledger when the mic
        was unreachable. Same backoff applies to vision capture failures.
        """
        last_frame_at = 0.0
        last_ocr_at = 0.0
        last_spatial_check_at = 0.0
        BASE_FRAME_INTERVAL_S = 0.2  # ~5 fps when vision is healthy
        VISION_OCR_INTERVAL_S = 5.0  # Capturing screen text is natively throttled
        SPATIAL_INTERVAL_S = 60.0    # Check physical disk capacity every 60s
        BASE_SLEEP_S = 0.05

        # Backoff state. Both rails track consecutive failures so they
        # ramp independently — visual being broken doesn't slow audio,
        # and vice versa.
        AUDIO_BACKOFF_BASE_S = 1.0
        AUDIO_BACKOFF_CAP_S  = 300.0   # 5 min ceiling
        VISION_BACKOFF_BASE_S = 1.0
        VISION_BACKOFF_CAP_S  = 60.0
        audio_next_at  = 0.0
        vision_next_at = 0.0
        audio_consecutive_fail  = 0
        vision_consecutive_fail = 0

        while self.running:
            tick_start = time.time()

            # ── Autonomic Pacing ─────────────────────────────────────────────
            mood_multiplier = 1.0
            if self.arbitrator:
                try:
                    # Retrieve the physical swarm multiplier based on Endocrine Adrenaline and Amygdala Fear.
                    # Multiplier > 1.0 speeds up the heart. Multiplier < 1.0 slows it down.
                    mood_multiplier = self.arbitrator.compute_effective_multiplier("M1SIFTA", "System/swarm_boot.py")
                except Exception:
                    pass
                    
            # ── Spatial Awareness (Disk & Trash Check) ───────────────────────
            if self.proprioception and self.trash and self.egress:
                if (tick_start - last_spatial_check_at) > SPATIAL_INTERVAL_S:
                    last_spatial_check_at = tick_start
                    try:
                        storage = self.proprioception.sense_storage()
                        percent_free = storage.get("percent_free", 100.0)
                        trash_mass = self.trash.get_trash_size_mb()
                        
                        # Trigger bounds threshold
                        if trash_mass > 1000.0 or percent_free < 10.0:
                            msg = f"Stigmergic Trash bounds breached ({trash_mass:.1f} MB). Free space: {percent_free:.1f}%."
                            self.egress.tap_architect(msg, title="SIFTA Spatial Alert")
                            print(f"\n🚨 [SPATIAL_ALERT] {msg}")
                    except Exception as e:
                        print(f"[HEARTBEAT FRACTURE] Spatial check failed: {e}")

            # Scale intervals based on emotion.
            current_frame_interval_s = BASE_FRAME_INTERVAL_S / mood_multiplier
            current_sleep_s = BASE_SLEEP_S / mood_multiplier

            # ── Acoustic ─────────────────────────────────────────────────────
            if self.mic_online and tick_start >= audio_next_at:
                healthy = False
                try:
                    sample = capture_acoustic_truth()
                    # `mock` source means all real backends fell through.
                    # That's a failure for backoff purposes even though no
                    # exception was raised.
                    healthy = (sample is not None and sample.source != "mock")
                    if healthy and sample.rms_amplitude > 0.005:
                        self.grid.triangulate_from_audio(
                            sample.rms_amplitude, sample.source
                        )
                except Exception as e:
                    print(f"[HEARTBEAT FRACTURE] Acoustic exception: "
                          f"{type(e).__name__}: {e}")
                    healthy = False

                if healthy:
                    if audio_consecutive_fail > 0:
                        print(f"[HEARTBEAT] Audio recovered after "
                              f"{audio_consecutive_fail} consecutive failures.")
                    audio_consecutive_fail = 0
                    audio_next_at = 0.0
                else:
                    audio_consecutive_fail += 1
                    wait = min(
                        AUDIO_BACKOFF_CAP_S,
                        AUDIO_BACKOFF_BASE_S * (2 ** min(audio_consecutive_fail - 1, 9)),
                    )
                    audio_next_at = tick_start + wait
                    # Surface the backoff transition once at 5 fails so the
                    # operator knows the loop has parked itself, then again
                    # at hour-long boundaries.
                    if audio_consecutive_fail in (5, 60, 600):
                        print(f"[HEARTBEAT] Audio capture has failed "
                              f"{audio_consecutive_fail}× in a row. "
                              f"Backoff now {wait:.0f}s. "
                              f"Check mic permission / device.")

            # ── Visual ───────────────────────────────────────────────────────
            vision_pheromone = Path(".sifta_state/PHEROMONE_VISION_OPT_IN")
            if (self.vision_online
                and tick_start >= vision_next_at
                and (tick_start - last_frame_at) > current_frame_interval_s):
                last_frame_at = tick_start
                healthy = False
                try:
                    # Capture IDE screen if opted in and throtted interval passed
                    if self.iris and self.visual_cortex and vision_pheromone.exists() and (tick_start - last_ocr_at) > VISION_OCR_INTERVAL_S:
                        last_ocr_at = tick_start
                        frame = self.iris.blink_capture("ide_chrome_screenshot")
                        if frame and frame.file_path:
                            ocr_trace = self.visual_cortex.read_image_semantics(frame.file_path)
                            healthy = "error" not in ocr_trace
                    else:
                        # Otherwise fall back to simple webcam check (no OCR, no full screen grab)
                        frame = webcam_frame(grab_timeout_s=0.2)
                        healthy = frame is not None
                except Exception as e:
                    print(f"[HEARTBEAT FRACTURE] Visual exception: "
                          f"{type(e).__name__}: {e}")
                    healthy = False

                if healthy:
                    if vision_consecutive_fail > 0:
                        print(f"[HEARTBEAT] Vision recovered after "
                              f"{vision_consecutive_fail} consecutive failures.")
                    vision_consecutive_fail = 0
                    vision_next_at = 0.0
                else:
                    vision_consecutive_fail += 1
                    wait = min(
                        VISION_BACKOFF_CAP_S,
                        VISION_BACKOFF_BASE_S * (2 ** min(vision_consecutive_fail - 1, 6)),
                    )
                    vision_next_at = tick_start + wait
                    if vision_consecutive_fail in (5, 60):
                        print(f"[HEARTBEAT] Vision capture has failed "
                              f"{vision_consecutive_fail}× in a row. "
                              f"Backoff now {wait:.0f}s. "
                              f"Check camera permission / device.")

            time.sleep(current_sleep_s)

    def _shutdown(self):
        """Clean shutdown and memory sync."""
        self.running = False
        try:
            get_broca().stop()
        except Exception as e:
            print(f"[SHUTDOWN] Broca stop failed: {type(e).__name__}: {e}")
        print("═" * 58)
        print("SIFTA OFFLINE.")
        print("═" * 58)


if __name__ == "__main__":
    brain = SiftaBrainstem()
    brain.wake()
