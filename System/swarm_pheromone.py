import json, math, time, threading
from pathlib import Path

# Path to ledger where pheromone events are stored.
# Anchor to the repo root so the engine works no matter the CWD of
# the importing process (Alice's widgets, autopilot, daemons, etc.).
_REPO = Path(__file__).resolve().parent.parent
PHEROMONE_LOG = _REPO / ".sifta_state" / "pheromone_log.jsonl"
PHEROMONE_LOG.parent.mkdir(parents=True, exist_ok=True)

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
        # Start background evaporation thread
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
        while True:
            time.sleep(30)  # evaporation interval
            self.evaporate()

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
