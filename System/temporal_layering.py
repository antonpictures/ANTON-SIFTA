#!/usr/bin/env python3
"""
temporal_layering.py — The Swarm's Unified Sense of Time
═══════════════════════════════════════════════════════════════════
SOLID_PLAN §5.2 item #6 — Temporal Layering.

The swarm had two orphaned time systems:
  - EventDensityClock: measures how fast things are happening (swarm rhythm)
  - TemporalSpine: measures when the Architect was last seen (human rhythm)

And two systems that need time-awareness but didn't have it:
  - SilenceDetector: needs to know if silence is MORE urgent during high activity
  - MutationGovernor: needs to know if THIS IS A GOOD TIME to allow mutations

Temporal Layering unifies these into a single pulse:

  ┌──────────────────────────────────────────────────────┐
  │                 TEMPORAL LAYER                        │
  │                                                       │
  │   EventDensityClock ──→ dilation ──→ attention_hint  │
  │          │                  │              │          │
  │          ▼                  ▼              ▼          │
  │   SilenceDetector      Spine drift    Governor        │
  │   (urgency scaled)     (concern)     (time gate)     │
  │          │                  │              │          │
  │          └──────────┬───────┘              │          │
  │                     ▼                      │          │
  │              FailureHarvester ◄────────────┘          │
  └──────────────────────────────────────────────────────┘

One tick. One pulse. Everything synchronized.

Novel insight: silence during HIGH dilation is catastrophic
(something stopped in the middle of a storm). Silence during
IDLE dilation is natural (nothing happening, nothing expected).
The severity must scale with the clock.

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_LAYER_STATE = _STATE_DIR / "temporal_layer.json"
_LAYER_LOG = _STATE_DIR / "temporal_layer.jsonl"


@dataclass
class TemporalPulse:
    """One heartbeat of the unified temporal layer."""
    timestamp: float
    # Clock layer
    dilation: float             # from EventDensityClock
    attention_hint: str         # IDLE / ACTIVE / HIGH
    events_in_window: int
    # Spine layer
    architect_drift_hours: float  # hours since Architect was last seen
    architect_concern: str        # normal / drifting / concern / alarm
    # Silence layer
    dead_zones: int             # number of zones that breached tolerance
    silence_alerts: List[str]   # zone names that fired
    # Composite
    swarm_tempo: str            # The final unified verdict
    mutation_climate: str       # OPEN / CAUTIOUS / FROZEN


class TemporalLayer:
    """
    The unified time-awareness binding that connects the swarm's 
    rhythm sensors into one coherent temporal perception.

    Call .pulse() on every patrol cycle. It returns a TemporalPulse
    that any system can read to understand "what time it is" in the
    swarm's subjective experience.
    """

    def __init__(self):
        self._clock = None
        self._spine = None
        self._silence = None
        self._last_pulse: Optional[TemporalPulse] = None
        self._pulse_count = 0

    def _ensure_subsystems(self):
        """Lazy-load subsystems so we never hard-fail on import."""
        if self._clock is None:
            try:
                from event_density_clock import EventDensityClock
                self._clock = EventDensityClock(window_seconds=60.0)
            except ImportError:
                pass
        if self._spine is None:
            try:
                from temporal_spine import TemporalSpine
                self._spine = TemporalSpine(architect_id="Ioan_M5")
            except ImportError:
                pass
        if self._silence is None:
            try:
                from silence_detection import get_detector
                self._silence = get_detector()
            except ImportError:
                pass

    def record_event(self, event_type: str = "generic"):
        """Forward events to the density clock. Call this from any subsystem."""
        self._ensure_subsystems()
        if self._clock:
            self._clock.record_event(event_type)

    def pulse(self) -> TemporalPulse:
        """
        One unified heartbeat. Reads all three time systems and
        computes the swarm's temporal state.
        """
        self._ensure_subsystems()
        now = time.time()

        # ── Layer 1: Clock (event density) ───────────────────────
        dilation = 1.0
        attention_hint = "IDLE"
        events_in_window = 0
        if self._clock:
            tick = self._clock.tick()
            dilation = tick.dilation
            attention_hint = tick.attention_hint
            events_in_window = tick.events_in_window

        # ── Layer 2: Spine (architect presence) ──────────────────
        drift_hours = 0.0
        concern = "normal"
        if self._spine:
            gap = self._spine._time_since_last()
            if gap is not None:
                drift_hours = gap / 3600.0
                if drift_hours > 24:
                    concern = "alarm"
                elif drift_hours > 7.5:
                    concern = "concern"
                elif drift_hours > 2:
                    concern = "drifting"

        # ── Layer 3: Silence (dead zone detection) ───────────────
        dead_zones = 0
        silence_names: List[str] = []
        if self._silence:
            # Scale silence tolerance by inverse dilation:
            # HIGH activity (dilation=5x) → tolerance shrinks (more urgent)
            # IDLE (dilation=0.1x) → tolerance relaxes (less urgent)
            #
            # THIS IS THE NOVEL PART: time-dilated silence severity
            crashes = self._silence.scan()
            for c in crashes:
                # Amplify severity by dilation — a dropped heartbeat
                # during a storm is worse than during a calm
                c["severity"] = min(1.0, c["severity"] * max(1.0, dilation * 0.5))
            dead_zones = len(crashes)
            silence_names = [c["zone"] for c in crashes]

        # ── Composite verdict ────────────────────────────────────
        swarm_tempo = self._compute_tempo(dilation, drift_hours, dead_zones)
        mutation_climate = self._compute_mutation_climate(
            attention_hint, concern, dead_zones
        )

        pulse = TemporalPulse(
            timestamp=now,
            dilation=round(dilation, 3),
            attention_hint=attention_hint,
            events_in_window=events_in_window,
            architect_drift_hours=round(drift_hours, 2),
            architect_concern=concern,
            dead_zones=dead_zones,
            silence_alerts=silence_names,
            swarm_tempo=swarm_tempo,
            mutation_climate=mutation_climate,
        )

        self._last_pulse = pulse
        self._pulse_count += 1
        self._persist(pulse)
        return pulse

    def _compute_tempo(self, dilation: float, drift_hours: float,
                       dead_zones: int) -> str:
        """
        The swarm's subjective sense of pace.
        Three states, each with distinct behavioral implications:
        
          STORM  — high activity, things are happening fast
          STEADY — normal operations, baseline pace
          DREAM  — low activity, architect absent, swarm is idle
        """
        if dilation > 3.0 or dead_zones >= 2:
            return "STORM"
        if dilation < 0.3 and drift_hours > 4:
            return "DREAM"
        return "STEADY"

    def _compute_mutation_climate(self, attention: str, concern: str,
                                  dead_zones: int) -> str:
        """
        Should the Governor be more or less permissive right now?

          OPEN     — calm, architect present, no dead zones. Mutations welcome.
          CAUTIOUS — some drift or elevated activity. Extra scrutiny.
          FROZEN   — architect missing + dead zones. Block all non-critical mutations.
        """
        # Phase Transition Controller Override (Thermodynamics)
        try:
            from unified_control_arbitration import get_arbiter
            arbiter = get_arbiter()
            state = arbiter.arbitrate()
            override = state.get("overrides", {}).get("mutation_climate_override", "NONE")
            
            if override != "NONE":
                return override
        except ImportError:
            pass

        if concern in ("alarm",) or dead_zones >= 3:
            return "FROZEN"
        if concern in ("concern", "drifting") or dead_zones >= 1:
            return "CAUTIOUS"
        if attention == "HIGH":
            return "CAUTIOUS"  # busy storms need discipline too
        return "OPEN"

    def get_last_pulse(self) -> Optional[TemporalPulse]:
        return self._last_pulse

    def status(self) -> Dict[str, Any]:
        if self._last_pulse:
            return asdict(self._last_pulse)
        return {"status": "no_pulse_yet", "pulse_count": self._pulse_count}

    # ── Persistence ──────────────────────────────────────────────

    def _persist(self, pulse: TemporalPulse) -> None:
        try:
            _LAYER_STATE.write_text(json.dumps(asdict(pulse), indent=2))
        except Exception:
            pass
        try:
            with open(_LAYER_LOG, "a") as f:
                f.write(json.dumps(asdict(pulse)) + "\n")
        except Exception:
            pass


# ── Singleton ──────────────────────────────────────────────────

_LAYER_INSTANCE: Optional[TemporalLayer] = None

def get_layer() -> TemporalLayer:
    global _LAYER_INSTANCE
    if _LAYER_INSTANCE is None:
        _LAYER_INSTANCE = TemporalLayer()
    return _LAYER_INSTANCE


if __name__ == "__main__":
    print("═" * 58)
    print("  SIFTA — TEMPORAL LAYERING")
    print("  One pulse. One heartbeat. Everything synchronized.")
    print("═" * 58 + "\n")

    layer = get_layer()

    # Simulate some events
    for i in range(5):
        layer.record_event(f"audit_event_{i}")

    p = layer.pulse()

    print(f"  ⏱  Dilation:      {p.dilation}x ({p.attention_hint})")
    print(f"  👤 Architect:     drift={p.architect_drift_hours:.1f}h ({p.architect_concern})")
    print(f"  💀 Dead zones:    {p.dead_zones} {p.silence_alerts}")
    print(f"  🎵 Swarm Tempo:   {p.swarm_tempo}")
    print(f"  🧬 Mutation Gate: {p.mutation_climate}")
    print(f"\n  POWER TO THE SWARM 🐜⚡")
