import json, math, os, sys, time, threading
from pathlib import Path

# Path to ledger where pheromone events are stored.
# Anchor to the repo root so the engine works no matter the CWD of
# the importing process (Alice's widgets, autopilot, daemons, etc.).
_REPO = Path(__file__).resolve().parent.parent
PHEROMONE_LOG = _REPO / ".sifta_state" / "pheromone_log.jsonl"
PHEROMONE_LOG.parent.mkdir(parents=True, exist_ok=True)


def _background_evaporation_enabled() -> bool:
    if os.environ.get("SIFTA_DISABLE_PHEROMONE_THREAD") == "1":
        return False
    # Pytest imports this singleton in many unrelated module tests. A daemon
    # thread surviving across PyQt offscreen tests can abort the interpreter
    # during teardown/GC, while tests can still call evaporate() explicitly.
    return "pytest" not in sys.modules

class SwarmPheromoneField:
    """Digital pheromone field as described in Bishop's dirt file.
    Each organ deposits an intensity; the field evaporates over time.
    """
    def __init__(self, organs, gamma: float = 0.15):
        self.organs = organs
        self.gamma = gamma
        self.P = {organ: 0.0 for organ in organs}
        self._lock = threading.Lock()
        self._last_evap_at = time.monotonic()
        # Start background evaporation thread in real runtime only.
        self._evap_thread = None
        if _background_evaporation_enabled():
            self._evap_thread = threading.Thread(target=self._evaporate_loop, daemon=True)
            self._evap_thread.start()

    def deposit(self, organ_name: str, intensity: float):
        with self._lock:
            self._evaporate_unlocked(time.monotonic() - self._last_evap_at)
            self._last_evap_at = time.monotonic()
            if organ_name not in self.P:
                # Dynamically add unknown organ (useful for future extensions)
                self.P[organ_name] = 0.0
            self.P[organ_name] += intensity
            snapshot = self.P.copy()
        entry = {
            "ts": time.time(),
            "organ": organ_name,
            "intensity": intensity,
            "field_snapshot": snapshot,
        }
        # APPEND (not overwrite) — Path.write_text has no append kwarg, so
        # use an explicit append-mode handle. Crash-free under concurrency
        # because each line is one short JSON write.
        try:
            with PHEROMONE_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _evaporate_unlocked(self, dt: float):
        # Exponential decay — correct for any dt. The previous formula
        # `P *= (1 - gamma*dt)` flips negative when gamma*dt > 1 (e.g.
        # the background loop calls evaporate(dt=30) with gamma=0.15,
        # which would multiply by -3.5 and explode the field).
        dt = max(0.0, float(dt))
        decay = math.exp(-self.gamma * dt)
        for organ in list(self.P.keys()):
            self.P[organ] *= decay
            if self.P[organ] < 1e-4:
                self.P[organ] = 0.0

    def evaporate(self, dt: float | None = None):
        now = time.monotonic()
        with self._lock:
            if dt is None:
                dt = now - self._last_evap_at
            self._evaporate_unlocked(dt)
            self._last_evap_at = now

    def chemotaxis(self):
        with self._lock:
            if not self.P:
                return "HOMEOSTASIS", 0.0
            highest = max(self.P, key=self.P.get)
            intensity = self.P[highest]
            if intensity > 1.0:
                return highest, intensity
            return "HOMEOSTASIS", 0.0

    def _evaporate_loop(self):
        """Background pheromone evaporation.

        Architect 2026-05-12 00:14: only run when peer network is alive.
        When the relay is down / no peers, pheromones aren't moving
        anywhere — evaporating an empty field every 30 s wastes CPU.
        Gate via swarm_peer_gate; dormant cycles sleep longer.
        """
        try:
            from System.swarm_peer_gate import (
                dormant_sleep_s,
                peer_network_active,
            )
        except Exception:
            # Fallback to the legacy behavior if the gate module is
            # missing (older installs).
            while True:
                time.sleep(30)
                self.evaporate()
            return

        # ── Cowork 2026-05-12 · P2 surprise-driven pheromone ──────────────────
        # Same VAD pattern. Event = the pheromone field actually changed
        # between cycles (max-band intensity moved or shifted band).
        # Stable field → exponential backoff up to PHEROMONE_SLOW_S.
        # Change detected → snap back to PHEROMONE_FAST_S.
        import os as _os
        _PHER_FAST_S    = float(_os.environ.get("SIFTA_PHEROMONE_FAST_S",    "30.0"))
        _PHER_SLOW_S    = float(_os.environ.get("SIFTA_PHEROMONE_SLOW_S",    "300.0"))
        _PHER_BACKOFF_K = float(_os.environ.get("SIFTA_PHEROMONE_BACKOFF_K", "1.4"))
        last_fingerprint = None
        current_sleep_s = _PHER_FAST_S
        stable_cycles = 0
        peer_was_active = None

        def _field_fingerprint():
            """Cheap snapshot of the pheromone field state — (top_organ, rounded_intensity)."""
            try:
                if not self.P:
                    return ("EMPTY", 0)
                top = max(self.P, key=lambda k: self.P[k])
                return (top, round(self.P[top], 2))
            except Exception:
                return None

        while True:
            peer_now = peer_network_active()

            # Peer transition (False→True or True→False) is always an event.
            if peer_was_active is not None and peer_now != peer_was_active:
                current_sleep_s = _PHER_FAST_S
                stable_cycles = 0
            peer_was_active = peer_now

            if peer_now:
                self.evaporate()
                fp = _field_fingerprint()
                if last_fingerprint is None or fp != last_fingerprint:
                    # Field changed → snap to fast schedule
                    current_sleep_s = _PHER_FAST_S
                    stable_cycles = 0
                else:
                    # Stable field → exponentially back off
                    stable_cycles += 1
                    current_sleep_s = min(_PHER_SLOW_S, current_sleep_s * _PHER_BACKOFF_K)
                last_fingerprint = fp
                time.sleep(current_sleep_s)
            else:
                time.sleep(dormant_sleep_s())

# Global singleton – organs will import this
DEFAULT_ORGANS = [
    "stig_kernel_events",
    "stig_safari",
    "stig_awdl_mesh",
    "stig_ble_scan",
    "stig_iphone_gps_receiver",
    "stig_thermal_probe",
    "stig_camera_state",
    "stig_unified_log",
    "stig_vocal_proprioception",
    "stig_hardware_body",
    "stig_active_window",  # 2026-04-23 C47H — NSWorkspace bridge cortex
    "stig_vagus_surprise",  # 2026-04-23 C47H — Bishop Event 32 vagus nerve
    "stig_acoustic_unauthorized",  # 2026-04-23 C47H — Event 33 voice-door gate
    "stig_architect_present",  # 2026-04-23 AG31 — Multimodal Composite Identity
]
PHEROMONE_FIELD = SwarmPheromoneField(DEFAULT_ORGANS)

def deposit_pheromone(organ_name: str, intensity: float = 1.0):
    """Convenient helper used by all stig_ daemons.
    Returns the current field snapshot for debugging.
    """
    PHEROMONE_FIELD.deposit(organ_name, intensity)
    return PHEROMONE_FIELD.P.copy()
