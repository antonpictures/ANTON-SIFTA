#!/usr/bin/env python3
"""
sensory_cortex.py — Vision → Interference Field → Territory
═══════════════════════════════════════════════════════════════
The bridge between perception and action.

Vision samples a frame → extracts saliency event →
  Cortex converts event into a PheromoneWave →
    Interference Field receives the wave →
      Territory coupling updates automatically.

The organism sees → feels → acts.

Also wires the Event Density Clock so attention state
adapts vision FPS in real time:
  Low event density → IDLE → 0.5 FPS
  High event density → HIGH → 10 FPS

SIFTA Non-Proliferation Public License applies.
"""

from __future__ import annotations

import sys
import time
import math
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.stigmergic_vision import StigmergicVision, AttentionState
from System.event_density_clock import EventDensityClock
from System.interference_layer import (
    PheromoneWave,
    get_interference_field,
    FREQ_SCOUT,
)

# Vision emissions use a distinct frequency
FREQ_VISION = 880.0   # "SEE" — distinct from REPAIR/SCOUT/GUARD


class SensoryCortex:
    """
    Wires vision → interference field → territory.

    Usage:
        cortex = SensoryCortex()
        cortex.start()
        # In your main loop:
        cortex.perceive()     # samples, emits, adjusts attention
        # On shutdown:
        cortex.stop()
    """

    def __init__(self, camera_index: int = 0, node_id: str = "M5_VISION"):
        self.node_id = node_id
        self.vision = StigmergicVision(camera_index=camera_index)
        self.clock = EventDensityClock(window_seconds=30.0)
        self.field = get_interference_field()

        self._events_emitted = 0
        self._last_attention_sync = 0.0

    def start(self) -> bool:
        """Open the camera. Returns True if vision is online."""
        ok = self.vision.start()
        if ok:
            print(f"🧠 CORTEX: Online. Node={self.node_id}. "
                  f"Vision→Interference wiring active.")
        return ok

    def stop(self):
        """Release camera and report."""
        self.vision.stop()
        print(f"🧠 CORTEX: Offline. Emitted {self._events_emitted} "
              f"pheromone waves from vision.")

    def perceive(self) -> bool:
        """
        One perception cycle:
          1. Sample a frame (if FPS allows)
          2. If salient: emit a PheromoneWave into the interference field
          3. Record event in the density clock
          4. Sync attention state (clock → vision FPS)

        Returns True if a wave was emitted, False otherwise.
        Call this in your main loop or on a timer.
        """
        # Sync attention every 5 seconds based on event density
        now = time.time()
        if (now - self._last_attention_sync) > 5.0:
            self._sync_attention()
            self._last_attention_sync = now

        # Sample a frame
        event = self.vision.sample()
        if event is None:
            return False

        # Record event in the density clock
        self.clock.record_event("vision_event")

        # Convert VisionEvent → PheromoneWave
        wave = PheromoneWave(
            origin_node = self.node_id,
            agent_id    = f"{self.node_id}_EYE",
            frequency   = FREQ_VISION,
            amplitude   = event.saliency_score,
            phase       = event.change_magnitude * math.pi * 2,
        )

        # Emit into interference field
        territory_id = f"VISION_{event.scene_hash[:8]}"
        self.field.emit(territory_id, wave)
        self._events_emitted += 1

        print(f"🧠 CORTEX: {event.attention_state} — "
              f"saliency={event.saliency_score:.2f} → "
              f"wave emitted to {territory_id}")

        return True

    def _sync_attention(self):
        """
        Read the event density clock and adjust vision FPS accordingly.
        This is the feedback loop: event rate → attention → FPS.
        """
        tick = self.clock.tick()
        hint = tick.attention_hint

        state_map = {
            "IDLE":   AttentionState.IDLE,
            "ACTIVE": AttentionState.ACTIVE,
            "HIGH":   AttentionState.HIGH,
        }

        new_state = state_map.get(hint, AttentionState.IDLE)
        if new_state != self.vision.attention:
            self.vision.set_attention(new_state)

    def report(self) -> str:
        clock_tick = self.clock.tick()
        lines = [
            f"[SENSORY CORTEX] Node: {self.node_id}",
            f"  Waves emitted: {self._events_emitted}",
            f"  Clock dilation: {clock_tick.dilation:.2f}x",
            f"  Attention: {self.vision.attention.value} "
            f"({self.vision.target_fps} FPS)",
            f"  {self.vision.report()}",
        ]
        return "\n".join(lines)


# ── Demo ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 58)
    print("  SIFTA — SENSORY CORTEX")
    print("  Vision → Interference Field → Territory")
    print("=" * 58 + "\n")

    cortex = SensoryCortex()
    ok = cortex.start()

    if ok:
        print(f"\nRunning 30 perception cycles...\n")
        for i in range(30):
            emitted = cortex.perceive()
            time.sleep(0.2)

        cortex.stop()
    else:
        print("No camera / no OpenCV. Install: pip install opencv-python")
        print("The cortex wiring is correct — it just needs eyes.\n")

    print(f"\n{cortex.report()}")

    # Show what landed in the interference field
    report = cortex.field.mesh_report()
    vision_territories = [
        t for t in report["territories"]
        if t.startswith("VISION_")
    ]
    print(f"\n  Vision territories in field: {len(vision_territories)}")
    print(f"  Global coupling: {report['global_coupling']:.4f}")

    print("\n  POWER TO THE SWARM 🐜⚡")
