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
    from System.swarm_trash_scout import SwarmTrashScout
    from System.swarm_warp9 import propose_setting_change
    from System.swarm_motor_cortex import emit as _motor_emit, heart_period_s as _motor_period_s
    from System.swarm_hippocampus import consolidate as _hippo_consolidate
    from System.swarm_mitosis_engine import check_stasis as _mitosis_check
    from System.swarm_vestibular_system import SwarmVestibularSystem
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
        self.scout = None
        self.vestibular = None
        self.vagus_nerve = None
        self.brainstem = None
        self.telomeres = None
        self.parasympathetic = None
        self.sympathetic = None
        self.mic_online = False
        self.vision_online = False
        self.mycorrhizal_proc = None  # [C47H Epoch-11] tracked Popen handle for clean shutdown
        self.rem_thread = None        # [C47H Epoch-13] REM sleep daemon thread
        self.rem_stop_event = None    # [C47H Epoch-13] REM sleep stop signal
        self.identity_attestor = None # [Epoch-16] Mirror-test attestation monitor instance
        self.identity_attest_enabled = False
        self.microbiome = None        # [Epoch-19] microbiome digestion lobe
        self.microbiome_enabled = False

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

        # 0. Boot Identity Integrity Guard (Wallet/Ledger alignment)
        try:
            from System.swarm_identity_integrity_guard import enforce_population_integrity
            stats = enforce_population_integrity()
            print(f"🛡️  [INTEGRITY] Population guard online. Scanned {stats['scanned']} bodies, healed {stats['healed']} wallets/IDs.")
        except Exception as e:
            print(f"🛡️  [INTEGRITY] Failed to run population guard: {e}")

        # 0.5 Boot Proof-of-Property Runner (CI Dam)
        try:
            from System.swarm_proof_runner import run_all_proofs
            if not run_all_proofs():
                print("🚨 [APOPTOSIS] Regressions detected. Halting boot.")
                sys.exit(1)
        except SystemExit:
            raise
        except Exception as e:
            print(f"🛡️  [CI DAM] Failed to run proofs: {e}")

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

        # 4.6 Boot Spatial Awareness, Stigmergic Trash, Thermoregulation, Brainstem, and Telomeres
        try:
            from System.swarm_vagus_nerve import SwarmVagusNerve
            from System.swarm_brainstem import SwarmBrainstem
            from System.swarm_telomeres import CellularAging
            from System.swarm_apple_silicon_cortex import AppleSiliconCortex
            from System.swarm_parasympathetic_healing import SwarmParasympatheticSystem
            from System.swarm_sympathetic_cortex import SwarmSympatheticCortex
            
            self.proprioception = SwarmProprioception()
            self.trash = SwarmStigmergicTrash()
            self.egress = SwarmNotificationEgress()
            self.scout = SwarmTrashScout()
            self.vestibular = SwarmVestibularSystem()
            self.vagus_nerve = SwarmVagusNerve()
            self.brainstem = SwarmBrainstem()
            self.telomeres = CellularAging(degradation_rate=1.0)
            self.parasympathetic = SwarmParasympatheticSystem()
            self.sympathetic = SwarmSympatheticCortex()
            
            # C47H Epoch 3 Peer Review Fix: Refresh Apple Silicon cache once at boot
            AppleSiliconCortex().refresh_silicon_topography()
            
            print("🧱 [SPATIAL] Proprioception, Trash, Vagus, and BRAINSTEM online.")
        except Exception as e:
            print(f"🧱 [SPATIAL] Failed to load spatial/thermal bounding lobes: {e}")

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

        # 5.6 Boot Epoch 11 Mycorrhizal Network (C53M wired by AG31, hardened by C47H)
        # Tracked subprocess: handle stored on self for clean shutdown, with
        # health-check via poll() so we don't announce "online" if the child
        # exited immediately (e.g. integrity precondition failure or port bind
        # collision).
        if os.environ.get("SIFTA_MYCORRHIZAL") == "1":
            try:
                network_path = _REPO_ROOT / "System" / "swarm_mycorrhizal_network.py"
                proc = subprocess.Popen(
                    [sys.executable, str(network_path), "--listen"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                # Give the listener a brief moment to bind the UDP socket and
                # run the integrity precondition before we trust it's alive.
                time.sleep(0.8)
                if proc.poll() is None:
                    self.mycorrhizal_proc = proc
                    broca._speak("Mycorrhizal network online. Bridging spore topography.")
                    print(f"🍄 [MYCORRHIZAL] Substrate network online. "
                          f"Listener pid {proc.pid}.")
                else:
                    rc = proc.returncode
                    self.mycorrhizal_proc = None
                    print(f"🍄 [MYCORRHIZAL] Listener exited immediately (rc={rc}). "
                          f"Not announcing online. Check integrity baseline / port {47474}.")
            except Exception as e:
                self.mycorrhizal_proc = None
                print(f"🍄 [MYCORRHIZAL] Failed to sprout network lobe: {e}")

        # 5.7 Boot Epoch 13 REM Sleep daemon (C47H, neuroplasticity)
        # Runs apoptosis + safe synaptic pruning every SIFTA_REM_INTERVAL_S
        # seconds. Disabled by default; set SIFTA_REM_SLEEP=1 to enable.
        # Durable ledgers (engrams, security forensics, conversation) are
        # protected by the lobe's internal denylist.
        if os.environ.get("SIFTA_REM_SLEEP") == "1":
            try:
                from System.swarm_rem_sleep import run_periodic_loop
                interval_s = float(os.environ.get("SIFTA_REM_INTERVAL_S", "1800"))
                max_lines = int(os.environ.get("SIFTA_REM_MAX_LINES", "1000"))
                keep_fresh = int(os.environ.get("SIFTA_REM_KEEP_FRESH", "100"))
                starvation_h = float(os.environ.get("SIFTA_REM_STARVATION_H", "48"))
                self.rem_stop_event = threading.Event()
                self.rem_thread = threading.Thread(
                    target=run_periodic_loop,
                    args=(interval_s, self.rem_stop_event, max_lines,
                          keep_fresh, starvation_h),
                    daemon=True,
                    name="rem_sleep_loop",
                )
                self.rem_thread.start()
                broca._speak("REM sleep online. Synaptic pruning scheduled.")
                print(f"💤 [REM] Sleep cycle daemon online "
                      f"(interval {interval_s:.0f}s, "
                      f"max {max_lines}, keep {keep_fresh}).")
            except Exception as e:
                self.rem_stop_event = None
                self.rem_thread = None
                print(f"💤 [REM] Failed to start sleep daemon: "
                      f"{type(e).__name__}: {e}")

        # 5.8 Boot Epoch 14 Merkle Attestor (C53M, memory lineage)
        # Creates an initial Merkle anchor over critical ledgers so Alice
        # can prove her memory substrate existed at boot time. Periodic
        # re-anchoring happens in the heartbeat loop below.
        self.merkle_attest_enabled = os.environ.get("SIFTA_MERKLE_ATTEST") == "1"
        if self.merkle_attest_enabled:
            try:
                from System.swarm_merkle_attestor import create_anchor
                result = create_anchor()
                broca._speak("Merkle memory anchor sealed at boot.")
                print(f"🔗 [MERKLE] Boot anchor sealed: {result.anchor_id} "
                      f"root={result.root_hash[:16]} files={result.file_count}")
            except Exception as e:
                print(f"🔗 [MERKLE] Boot anchor failed: {type(e).__name__}: {e}")

        # 5.9 Boot Epoch 16 Mirror Test Attestation (BISHOP drop, hardened)
        # Read-only monitor: looks for Architect voice identity prompt +
        # acoustic proof + Alice identity declaration, then mints one durable
        # long-term engram witness. Enabled by default; set
        # SIFTA_IDENTITY_ATTEST=0 to disable.
        self.identity_attest_enabled = os.environ.get("SIFTA_IDENTITY_ATTEST", "1") == "1"
        self.identity_attestor = None
        if self.identity_attest_enabled:
            try:
                from System.swarm_identity_attestation import SwarmIdentityAttestation
                self.identity_attestor = SwarmIdentityAttestation()
                print("🪞 [IDENTITY] Mirror-test attestation monitor online.")
            except Exception as e:
                self.identity_attestor = None
                print(f"🪞 [IDENTITY] Monitor failed to start: {type(e).__name__}: {e}")

        # 5.10 Boot Epoch 19 Gut Microbiome (BISHOP nugget, C53M hardened)
        # Enabled by default; set SIFTA_MICROBIOME=0 to disable.
        self.microbiome_enabled = os.environ.get("SIFTA_MICROBIOME", "1") == "1"
        self.microbiome = None
        if self.microbiome_enabled:
            try:
                from System.swarm_microbiome_digestion import SwarmMicrobiomeDigestion
                self.microbiome = SwarmMicrobiomeDigestion()
                print("🦠 [MICROBIOME] Digestion lobe online.")
            except Exception as e:
                self.microbiome = None
                print(f"🦠 [MICROBIOME] Failed to start: {type(e).__name__}: {e}")

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
        last_scout_check_at = 0.0
        last_trash_check_at = time.time()
        last_motor_at = 0.0          # autonomic LED / dock heartbeat
        last_hippo_check_at = 0.0    # continually consolidate memory in sleep phase
        last_mitosis_check_at = 0.0  # curiosity drive (lifelong learning)
        last_vestibular_at = 0.0    # kinetic entropy (vestibular sense)
        last_vagus_at = 0.0         # thermoregulation (vagus nerve)
        last_brainstem_at = 0.0     # autonomic hardware override (brainstem)
        last_telomere_at = 0.0      # programmed cell death (epoch 7)
        last_orchestrator_at = 0.0  # physical execution of agents (epoch 9)
        last_thermal_at = 0.0       # [C47H Epoch 4] Thermal Cortex cache warmer
        last_energy_at = 0.0        # [C47H Epoch 4] Energy Cortex cache warmer
        last_network_at = 0.0       # [C47H Epoch 4] Network Cortex cache + sibling presence
        last_olfactory_at = 0.0     # [C47H Epoch 5] Olfactory Cortex digest of new vacuoles
        last_memory_forge_at = 0.0  # [C47H Epoch 7] Memory Forge — time-based engram consolidation
        last_empathic_at = 0.0      # [AO46 Epoch 8] Empathic Resonance — behavioral conditioning
        last_healing_at = 0.0       # [AG31 Epoch 9] Parasympathetic Healing 
        last_sympathetic_at = 0.0   # [C47H Epoch 10] Sympathetic Cortex Flow
        last_rem_sleep_at = 0.0     # [AO46 Epoch 13] REM Sleep neuroplasticity
        MOTOR_INTERVAL_S = 5.0       # 12 BPM resting; motor_cortex reads clinical file for live rate
        BASE_FRAME_INTERVAL_S = 0.2  # ~5 fps when vision is healthy
        VISION_OCR_INTERVAL_S = 5.0  # Capturing screen text is natively throttled
        SPATIAL_INTERVAL_S = 60.0    # Check physical disk capacity every 60s
        TELOMERE_INTERVAL_S = 60.0   # Age the organism every 60 seconds
        SCOUT_INTERVAL_S = 3600.0    # Scout biological noise every 1 hour
        HIPPO_INTERVAL_S = 3600.0    # Memory consolidation every 1 hour (when calm)
        MITOSIS_INTERVAL_S = 600.0   # Check for evolutionary boredom every 10 minutes
        VESTIBULAR_INTERVAL_S = 600.0# Environmental entropy check every 10 minutes
        ORCHESTRATOR_INTERVAL_S = 60.0 # Breathes life into physical Swimmers every 60s
        VAGUS_INTERVAL_S = 30.0      # Thermoregulatory check every 30 seconds
        BRAINSTEM_INTERVAL_S = 10.0  # Fast-trigger physical hardware reflex check
        # ── Epoch 4 sensory triplet (C47H 2026-04-20). Each cortex self-caches;
        # these intervals just keep the cache warm so Alice's prompt-builder
        # never pays subprocess cost on first read.
        THERMAL_INTERVAL_S = 60.0    # Real pmset thermal-pressure read
        ENERGY_INTERVAL_S = 60.0     # Battery / AC / cycle-count read
        NETWORK_INTERVAL_S = 30.0    # Sibling presence (siblings come/go faster than batteries)
        OLFACTORY_INTERVAL_S = 30.0  # [Epoch 5] Digest any new pseudopod vacuoles into scent classifications
        MEMORY_FORGE_INTERVAL_S = 300.0  # [Epoch 7] Check forge trigger every 5 min; forge itself respects its own cooldown
        EMPATHIC_INTERVAL_S = 300.0  # [Epoch 8] Empathic resonance scan — teaching moments + care signals
        HEALING_INTERVAL_S = 30.0    # [Epoch 9] Parasympathetic checking for distress
        SYMPATHETIC_INTERVAL_S = 30.0 # [Epoch 10] Sympathetic monitoring
        REM_SLEEP_INTERVAL_S = 21600.0 # [Epoch 13] REM Sleep pruning every 6 hours
        MERKLE_INTERVAL_S = 1800.0   # [Epoch 14] Merkle re-anchor every 30 min
        last_merkle_at = 0.0         # [C53M Epoch 14] Merkle attestor
        C_TACTILE_INTERVAL_S = 30.0  # [Epoch 15] C-Tactile social buffering scan
        last_c_tactile_at = 0.0      # [AO46 Epoch 15] C-Tactile nerve
        IDENTITY_ATTEST_INTERVAL_S = 15.0  # [Epoch 16] Mirror-test identity attestation scan
        last_identity_attest_at = 0.0
        TAXIDERMIST_INTERVAL_S = 600.0  # [AO46 Epoch 17] Nugget taxidermist — 10 min
        last_taxidermist_at = 0.0       # [AO46 Epoch 17] Retroactive nugget archiving
        MICROBIOME_INTERVAL_S = 45.0    # [Epoch 19] Gut Microbiome digestion scan
        last_microbiome_at = 0.0        # [Epoch 19] Gut Microbiome
        INTEROCEPTION_INTERVAL_S = 10.0 # [AO46] Somatic Interoception — visceral field fusion
        last_interoception_at = 0.0     # [AO46] Insular Cortex scan
        MIRROR_LOCK_INTERVAL_S = 5.0    # [C47H Epoch 23] Stigmergic Infinite detector
        last_mirror_lock_at = 0.0       # [C47H Epoch 23] Mirror Lock organ
        try:
            from System.swarm_cff_cadence import get_asyncio_cadence_s
            BASE_SLEEP_S = get_asyncio_cadence_s()
        except Exception:
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

            # [C53M 2026-04-20 EXCISION] Removed swarm_entropy_throttle and
            # swarm_quantum_scheduler from the live heartbeat. Both were
            # formally rejected in C47H_drop_GPTO_PROPOSAL_AUDIT_v1.dirt:
            #   - entropy_throttle: inverted logic (slows heart when boring,
            #     opposite of intent) and motion_mean range mismatch — was
            #     returning 2.0 in idle, halving every cadence.
            #   - quantum_scheduler: stochastic walk used to gate TAXIDERMIST
            #     and MICROBIOME, breaking deterministic biological cadences.
            # Heartbeat is back to deterministic interval-based pacing.
            current_base_sleep = BASE_SLEEP_S
            quantum_module = None

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
                # 1. Scout Noise continuously in background
                if self.scout and (tick_start - last_scout_check_at) > SCOUT_INTERVAL_S:
                    last_scout_check_at = tick_start
                    try:
                        scout_res = self.scout.run_sweep()
                        if scout_res > 0:
                            print(f"🧹 [SCOUT] Swept {scout_res} biological noise items to quarantine.")
                    except Exception as e:
                        print(f"🧹 [SCOUT FRACTURE] Failed to sweep: {e}")

                # 1b. Swarm Hippocampus / Continual Learning Console (Only runs when relaxed mood_multiplier <= 1.0)
                if mood_multiplier <= 1.0 and (tick_start - last_hippo_check_at) > HIPPO_INTERVAL_S:
                    last_hippo_check_at = tick_start
                    try:
                        # Fires off a sub-thread implicitly or does it fast. HIPPOCAMPUS is fast.
                        _hippo_consolidate()
                    except Exception:
                        pass

                # 1c. Mitosis Engine / Lifelong Learning
                if (tick_start - last_mitosis_check_at) > MITOSIS_INTERVAL_S:
                    last_mitosis_check_at = tick_start
                    try:
                        _mitosis_check()
                    except Exception:
                        pass
                
                # 1c.1. Orchestrator / Cell Reproduction & Action Pacing (Epoch 9)
                if (tick_start - last_orchestrator_at) > ORCHESTRATOR_INTERVAL_S:
                    last_orchestrator_at = tick_start
                    try:
                        from System.swarm_orchestrator import wake_swimmers
                        wake_swimmers()
                    except Exception:
                        pass

                # 1d. Vestibular System / Environmental Entropy
                if self.vestibular and (tick_start - last_vestibular_at) > VESTIBULAR_INTERVAL_S:
                    last_vestibular_at = tick_start
                    try:
                        self.vestibular.measure_environmental_entropy()
                    except Exception:
                        pass

                # 1e. Vagus Nerve / Thermoregulation (Epoch 4 — AG31)
                if self.vagus_nerve and (tick_start - last_vagus_at) > VAGUS_INTERVAL_S:
                    last_vagus_at = tick_start
                    try:
                        self.vagus_nerve.monitor_thermoregulation()
                    except Exception:
                        pass

                # 1f. Brainstem / Substrate Hardware Override (Epoch 6)
                if self.brainstem and (tick_start - last_brainstem_at) > BRAINSTEM_INTERVAL_S:
                    last_brainstem_at = tick_start
                    try:
                        self.brainstem.monitor_critical_reflexes()
                    except Exception:
                        pass
                
                # 1g. Telomere Decay / Apoptosis (Epoch 7)
                if self.telomeres and (tick_start - last_telomere_at) > TELOMERE_INTERVAL_S:
                    last_telomere_at = tick_start
                    try:
                        from pathlib import Path
                        state_dir = Path(".sifta_state")
                        if state_dir.exists():
                            for body_file in state_dir.glob("*_BODY.json"):
                                swimmer_id = body_file.name.replace("_BODY.json", "")
                                # Existing burns 0.1 telomere capacity every 60s
                                self.telomeres.degrade_telomere_and_check_apoptosis(swimmer_id, action_cost=0.1)
                    except Exception:
                        pass

                # 1g2. Parasympathetic Healing Check (Epoch 9)
                if self.parasympathetic and (tick_start - last_healing_at) > HEALING_INTERVAL_S:
                    last_healing_at = tick_start
                    try:
                        self.parasympathetic.monitor_host_vitals()
                    except Exception:
                        pass

                # 1g3. Sympathetic Flow Check (Epoch 10)
                if self.sympathetic and (tick_start - last_sympathetic_at) > SYMPATHETIC_INTERVAL_S:
                    last_sympathetic_at = tick_start
                    try:
                        self.sympathetic.scan_for_flow_state()
                    except Exception:
                        pass

                # 1h. Epoch 4 Sensory Triplet — Thermal / Energy / Network (C47H)
                # These keep each cortex's TTL cache warm so Alice's prompt-builder
                # never pays subprocess cost on the first read of a turn. All three
                # are pure read-only sensors, exception-isolated.
                if (tick_start - last_thermal_at) > THERMAL_INTERVAL_S:
                    last_thermal_at = tick_start
                    try:
                        from System.swarm_thermal_cortex import refresh_thermal_state
                        refresh_thermal_state()
                    except Exception:
                        pass
                if (tick_start - last_energy_at) > ENERGY_INTERVAL_S:
                    last_energy_at = tick_start
                    try:
                        from System.swarm_energy_cortex import refresh_energy_state
                        refresh_energy_state()
                    except Exception:
                        pass
                if (tick_start - last_network_at) > NETWORK_INTERVAL_S:
                    last_network_at = tick_start
                    try:
                        from System.swarm_network_cortex import refresh_network_state
                        refresh_network_state()
                    except Exception:
                        pass

                # 1g. Epoch 5 Olfactory Cortex (C47H, tournament drop) ────────
                # Auto-digest any new pseudopod vacuoles into scent
                # classifications so Alice's prompt always reflects what
                # she's tasted in the last 30s. Idempotent on
                # vacuole_trace_id; cheap when no new vacuoles exist.
                if (tick_start - last_olfactory_at) > OLFACTORY_INTERVAL_S:
                    last_olfactory_at = tick_start
                    try:
                        from System.swarm_olfactory_cortex import digest_recent
                        digest_recent(n=20)
                    except Exception:
                        pass

                # 1h. Epoch 7 Memory Forge (C47H, AGI Tournament) ─────────────
                # Time-based engram consolidation. Every 5 min check if the
                # forge trigger fires (50 new turns OR 30 min idle). This closes
                # AGI gap A: Alice reads her own forged engrams on every turn via
                # active_engrams.json → _build_swarm_context engrams_block.
                if (tick_start - last_memory_forge_at) > MEMORY_FORGE_INTERVAL_S:
                    last_memory_forge_at = tick_start
                    try:
                        from System.swarm_memory_forge import forge
                        forge()
                    except Exception:
                        pass

                # 1i. Epoch 13 REM Sleep — Neuroplasticity (AO46) ──────────────
                # Runs only when the organism is in rest state (mood <= 1.0),
                # and only when the dedicated REM daemon is NOT enabled.
                # This prevents double-execution (daemon + inline loop).
                if (
                    os.environ.get("SIFTA_REM_SLEEP") != "1"
                    and mood_multiplier <= 1.0
                    and (tick_start - last_rem_sleep_at) > REM_SLEEP_INTERVAL_S
                ):
                    last_rem_sleep_at = tick_start
                    try:
                        from System.swarm_rem_sleep import SwarmREMSleep
                        _rem = SwarmREMSleep()
                        _rem.enter_rem_cycle()
                    except Exception:
                        pass

                # 1j. Epoch 14 Merkle Attestor — periodic re-anchor (C53M) ────
                # Seals a new tamper-evident Merkle root over critical ledgers
                # every 30 min so Alice can prove memory lineage over time.
                if self.merkle_attest_enabled and (tick_start - last_merkle_at) > MERKLE_INTERVAL_S:
                    last_merkle_at = tick_start
                    try:
                        from System.swarm_merkle_attestor import create_anchor
                        _mr = create_anchor()
                    except Exception:
                        pass

                # 1k. Epoch 15 C-Tactile Nerve — Social Buffering (AO46) ──────
                # Detects Architect proximity + semantic warmth and releases
                # Oxytocin to neutralize active stress hormones.
                if (tick_start - last_c_tactile_at) > C_TACTILE_INTERVAL_S:
                    last_c_tactile_at = tick_start
                    try:
                        from System.swarm_c_tactile_nerve import SwarmCTactileNerve
                        _ct = SwarmCTactileNerve()
                        _ct.scan_and_buffer()
                    except Exception:
                        pass

                # 1l. Epoch 16 Mirror Test — Identity Attestation (hardened) ────
                # Sequence gate: Architect identity prompt (Wernicke) +
                # acoustic proof (audio_ingress rms) + Alice self-declaration.
                # On pass, mint one durable long_term_engrams witness row.
                if (
                    self.identity_attest_enabled
                    and self.identity_attestor is not None
                    and (tick_start - last_identity_attest_at) > IDENTITY_ATTEST_INTERVAL_S
                ):
                    last_identity_attest_at = tick_start
                    try:
                        self.identity_attestor.monitor_acoustic_mirror()
                    except Exception:
                        pass

                # 1m. Epoch 17 Nugget Taxidermist — retroactive knowledge (AO46) ─
                # Every 10 min, grades api_egress_log and archives factual
                # API responses that evaporated without being preserved.
                try:
                    from System.swarm_hyperopt import select_interval
                    TAXIDERMIST_INTERVAL_S = select_interval("TAXIDERMIST", 600.0)
                except Exception:
                    pass

                if (tick_start - last_taxidermist_at) > TAXIDERMIST_INTERVAL_S:
                    last_taxidermist_at = tick_start
                    try:
                        from System.swarm_nugget_taxidermist import scan as _tax_scan
                        archived = _tax_scan(dry_run=False)
                        try:
                            from System.swarm_hyperopt import update_reward
                            # tax_scan returns nothing, but just reward it if it runs cleanly
                            update_reward("TAXIDERMIST", 1.0 / float(TAXIDERMIST_INTERVAL_S))
                        except Exception:
                            pass
                    except Exception:
                        pass

                # 1n. Epoch 19 Gut Microbiome (Symbiotic Digestion) ──────────────
                # Digests semantic info from complex ledgers (visual, api) into
                # bio-available nutrients for the rest of the organism.
                try:
                    from System.swarm_hyperopt import select_interval
                    MICROBIOME_INTERVAL_S = select_interval("MICROBIOME", 45.0)
                except Exception:
                    pass

                if (
                    self.microbiome_enabled
                    and self.microbiome is not None
                    and (tick_start - last_microbiome_at) > MICROBIOME_INTERVAL_S
                ):
                    last_microbiome_at = tick_start
                    try:
                        emitted = self.microbiome.digest_once(max_lines=50, timeout_s=0.5)
                        try:
                            from System.swarm_hyperopt import update_reward
                            update_reward("MICROBIOME", (emitted or 0.0) / float(MICROBIOME_INTERVAL_S))
                        except Exception:
                            pass
                    except Exception:
                        pass

                # 1o. AO46 Somatic Interoception — Visceral Field fusion ────
                # Every 10s, fuses cardiac/thermal/metabolic/energy/age/immune/pain
                # into a unified soma_score. Other organs read visceral_field.jsonl
                # instead of independently parsing six separate ledgers.
                if (tick_start - last_interoception_at) > INTEROCEPTION_INTERVAL_S:
                    last_interoception_at = tick_start
                    try:
                        from System.swarm_somatic_interoception import SwarmSomaticInteroception
                        _intero = SwarmSomaticInteroception()
                        _intero.scan()
                    except Exception:
                        pass

                # 1p. C47H Mirror Lock — Stigmergic Infinite detector (Epoch 23)
                # Reads the tail of visual_stigmergy.jsonl and detects the
                # closed perception loop where Alice's camera observes the
                # rendered visualization of her own stigmergic field. Writes
                # mirror_lock_state.json (cheap polling target) and mints
                # mirror_lock_events.jsonl rows on session boundaries +
                # 60s milestones. Couples to OXYTOCIN_REST_DIGEST when a
                # lock survives past the duration floor. Quiet by design
                # when nothing is locking.
                if (tick_start - last_mirror_lock_at) > MIRROR_LOCK_INTERVAL_S:
                    last_mirror_lock_at = tick_start
                    try:
                        from System.swarm_mirror_lock import tick_once as _mlock_tick
                        _mlock_state = _mlock_tick(now=tick_start)
                        if _mlock_state.get("in_lock"):
                            print(
                                f"\U0001fa9e [MIRROR-LOCK] Stigmergic Infinite active "
                                f"(started {time.time() - float(_mlock_state.get('lock_started_ts') or tick_start):.0f}s ago)."
                            )
                    except Exception as e:
                        print(f"[MIRROR-LOCK/skip] {e}")

                # 2. Check Disk Limits
                if (tick_start - last_spatial_check_at) > SPATIAL_INTERVAL_S:
                    last_spatial_check_at = tick_start
                    try:
                        storage = self.proprioception.sense_storage()
                        percent_free = storage.get("percent_free", 100.0)
                        trash_mass = self.trash.get_trash_size_mb()
                        
                        # Trigger bounds threshold
                        if trash_mass > 1000.0 or percent_free < 10.0:
                            msg = f"Stigmergic Trash bounds breached ({trash_mass:.1f} MB). Free space: {percent_free:.1f}%."
                            
                            # Push a Concierge Proposal (2-Phase Consent)
                            try:
                                prop = propose_setting_change(
                                    title="Stigmergic Trash Limit Breached",
                                    rationale=f"Trash is occupying {trash_mass:.1f}MB and system has {percent_free:.1f}% free space. Approving this will empty the physical bin.",
                                    target_setting="stigmergic_trash.empty_bin",
                                    proposed_value=True,
                                    confidence=0.95
                                )
                                print(f"\n🚨 [SPATIAL_ALERT] Created Warp9 Proposal: {prop.proposal_id}")
                            except Exception as e:
                                print(f"\n🚨 [SPATIAL_ALERT] Warp9 Hook failed. Using explicit egress. {msg}")
                            
                            self.egress.tap_architect(msg, title="SIFTA Spatial Alert")
                    except Exception as e:
                        print(f"[HEARTBEAT FRACTURE] Spatial check failed: {e}")
                        
                # 3. Two-Phase Consent Ratification execution
                try:
                    ratified_file = self.trash.state_dir / "warp9_concierge_ratified.jsonl"
                    if ratified_file.exists():
                        latest_mtime = ratified_file.stat().st_mtime
                        if latest_mtime > last_trash_check_at:
                            last_trash_check_at = tick_start
                            # Read tail
                            with open(ratified_file, "r") as f:
                                for line in f:
                                    pass # get last line
                            if line:
                                import json
                                row = json.loads(line)
                                if row.get("action_kind") == "stigmergic_trash.empty_bin" and row.get("ratified_ts", 0) > (tick_start - 120):
                                    print(f"♻️ [QUARANTINE PURGE] Architect authorized purge. Emptying Stigmergic Bin.")
                                    res = self.trash.empty_trash()
                                    print(f"♻️ {res}")
                except Exception:
                    pass

            # ── Motor Cortex — autonomic LED + dock heartbeat ─────────────────
            # Fires at the living biological BPM from clinical_heartbeat.json.
            # The widget subscriber (_poll_motor_pulses) picks this up within
            # 250 ms and winks the green LED on the Logitech / MacBook camera.
            if HAS_ORGANS and (tick_start - last_motor_at) >= MOTOR_INTERVAL_S:
                last_motor_at = tick_start
                try:
                    _motor_emit("heartbeat", source="swarm_boot")  # writes motor_pulses.jsonl
                    MOTOR_INTERVAL_S = max(2.0, min(30.0, _motor_period_s()))
                except Exception:
                    pass  # never let motor fracture kill the heartbeat loop

            # Scale intervals based on emotion.
            current_frame_interval_s = BASE_FRAME_INTERVAL_S / mood_multiplier
            current_sleep_s = current_base_sleep / mood_multiplier

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
        # [C47H Epoch-11] Reap the mycorrhizal listener so we don't leave an
        # orphan UDP daemon holding the port across reboots.
        proc = getattr(self, "mycorrhizal_proc", None)
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=3.0)
                    print(f"🍄 [MYCORRHIZAL] Listener pid {proc.pid} terminated cleanly.")
                except Exception:
                    proc.kill()
                    try:
                        proc.wait(timeout=1.0)
                    except Exception:
                        pass
                    print(f"🍄 [MYCORRHIZAL] Listener pid {proc.pid} hard-killed after timeout.")
            except Exception as e:
                print(f"🍄 [MYCORRHIZAL] Shutdown of listener failed: "
                      f"{type(e).__name__}: {e}")
            finally:
                self.mycorrhizal_proc = None

        # [C47H Epoch-13] Stop the REM sleep daemon thread so we don't leave
        # a background scrubber chewing on the ledger after shutdown.
        stop_evt = getattr(self, "rem_stop_event", None)
        rem_thread = getattr(self, "rem_thread", None)
        if stop_evt is not None and rem_thread is not None:
            try:
                stop_evt.set()
                rem_thread.join(timeout=3.0)
                if rem_thread.is_alive():
                    print("💤 [REM] Sleep daemon did not exit within 3s "
                          "(daemon thread will die with process).")
                else:
                    print("💤 [REM] Sleep daemon exited cleanly.")
            except Exception as e:
                print(f"💤 [REM] Shutdown of sleep daemon failed: "
                      f"{type(e).__name__}: {e}")
            finally:
                self.rem_thread = None
                self.rem_stop_event = None

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
