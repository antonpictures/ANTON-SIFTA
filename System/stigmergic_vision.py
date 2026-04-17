#!/usr/bin/env python3
"""
stigmergic_vision.py — Event-Based Perception (NOT a Video Feed)
═══════════════════════════════════════════════════════════════════
The swarm does NOT "watch video."
It samples frames, extracts events, writes traces.

The camera is a pheromone emitter, not a video feed.

Frame rate adapts to attention state:
  IDLE:   0.5 FPS  — scene-change detection only
  ACTIVE: 3 FPS    — task-relevant monitoring
  HIGH:   10 FPS   — manipulation / interaction

Only high-saliency frames survive into the blackboard.
Raw frames are NEVER stored.

Requires: pip install opencv-python (cv2)
Falls back gracefully if not installed.

SIFTA Non-Proliferation Public License applies.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_VISION_LOG = _STATE / "vision_events.jsonl"

# ── Attention states control frame rate ──────────────────────

class AttentionState(str, Enum):
    IDLE   = "IDLE"     # 0.5 FPS — background scan
    ACTIVE = "ACTIVE"   # 3 FPS   — task-relevant
    HIGH   = "HIGH"     # 10 FPS  — interaction


FPS_MAP = {
    AttentionState.IDLE:   0.5,
    AttentionState.ACTIVE: 3.0,
    AttentionState.HIGH:   10.0,
}

# Saliency threshold — frames below this are silently dropped
SALIENCY_THRESHOLD = 0.15


@dataclass
class VisionEvent:
    """What the swarm actually remembers from a frame. Not the frame itself."""
    event_id:         str
    timestamp:        float
    saliency_score:   float     # 0.0 = nothing changed, 1.0 = everything changed
    scene_hash:       str       # perceptual hash of the frame (NOT the frame)
    change_magnitude: float     # how different from previous frame
    attention_state:  str
    frame_dimensions: tuple     # (height, width) — metadata only
    objects_hint:     str       # rough description if available


class StigmergicVision:
    """
    Adaptive frame sampler → event extractor → blackboard writer.

    Usage:
        vision = StigmergicVision()
        vision.start()           # opens camera
        event = vision.sample()  # returns VisionEvent or None
        vision.stop()            # releases camera
    """

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.attention = AttentionState.IDLE
        self._cap = None
        self._prev_hash: Optional[str] = None
        self._prev_gray = None
        self._last_sample_time = 0.0
        self._events_emitted = 0
        self._frames_sampled = 0
        self._frames_dropped = 0

        _STATE.mkdir(parents=True, exist_ok=True)

    @property
    def target_fps(self) -> float:
        return FPS_MAP[self.attention]

    @property
    def sample_interval(self) -> float:
        return 1.0 / self.target_fps

    def start(self) -> bool:
        """Open camera. Returns True if successful."""
        try:
            import cv2
            self._cap = cv2.VideoCapture(self.camera_index)
            if not self._cap.isOpened():
                print(f"⚠️ VISION: Camera {self.camera_index} failed to open.")
                self._cap = None
                return False
            print(f"📷 VISION: Camera {self.camera_index} opened. "
                  f"Attention: {self.attention.value} ({self.target_fps} FPS)")
            return True
        except ImportError:
            print("⚠️ VISION: opencv-python not installed. Run: pip install opencv-python")
            return False

    def stop(self):
        """Release camera."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        print(f"📷 VISION: Camera released. "
              f"Sampled: {self._frames_sampled}, Dropped: {self._frames_dropped}, "
              f"Events: {self._events_emitted}")

    def set_attention(self, state: AttentionState):
        """Change attention level → changes frame rate."""
        old = self.attention
        self.attention = state
        if old != state:
            print(f"📷 VISION: Attention {old.value} → {state.value} "
                  f"({FPS_MAP[old]} → {FPS_MAP[state]} FPS)")

    def sample(self) -> Optional[VisionEvent]:
        """
        Sample one frame IF enough time has passed for current FPS.
        Extract event. Return VisionEvent if salient, None if not.

        This is the ONLY function that touches the camera.
        """
        if self._cap is None:
            return None

        now = time.time()
        if (now - self._last_sample_time) < self.sample_interval:
            return None  # not time yet

        self._last_sample_time = now

        try:
            import cv2
        except ImportError:
            return None

        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None

        self._frames_sampled += 1

        # Convert to grayscale for change detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Compute perceptual hash (downscale to 8x8, threshold)
        small = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
        mean_val = small.mean()
        bits = (small > mean_val).flatten()
        scene_hash = hashlib.md5(bits.tobytes()).hexdigest()[:12]

        # Compute change magnitude from previous frame
        change = 0.0
        if self._prev_gray is not None:
            diff = cv2.absdiff(gray, self._prev_gray)
            change = float(diff.mean()) / 255.0  # normalize to 0-1
        self._prev_gray = gray

        # Saliency = change magnitude (simple but honest)
        saliency = min(1.0, change * 5.0)  # amplify small changes

        # Drop low-saliency frames — this is the key design decision
        # ── SVL Constraint #1: Silence Trigger Boost ────────────────
        try:
            from temporal_layering import get_layer
            climate = get_layer().get_last_pulse().mutation_climate if get_layer().get_last_pulse() else "OPEN"
            if climate in ("CAUTIOUS", "FROZEN"):
                saliency *= 2.0  # Boost sensitivity when temporal layer detects missing signals
        except ImportError:
            pass

        if saliency < SALIENCY_THRESHOLD and self._prev_hash == scene_hash:
            self._frames_dropped += 1
            return None

        self._prev_hash = scene_hash

        # ── SVL Constraint #2: VLM Pass (Placeholder Object Hint) ───
        objects_hint = "VLM_MOCK: [Room interior, stable]"
        if saliency > 0.5:
            objects_hint = "VLM_MOCK: [Significant motion, entity detected]"

        # ── SVL Constraint #3: STGM Cost ──────────────────────────
        # Swarm metabolism requires STGM to burn for cognition.
        try:
            try:
                from System.casino_vault import CasinoVault, CasinoTransaction
            except ImportError:
                from casino_vault import CasinoVault, CasinoTransaction
            vault = CasinoVault(architect_id="Ioan_M5")
            if vault.casino_balance < 0.005:
                print("⚠️ [SVL] Vision starved. Casino Vault STGM depleted. Closing eyes.")
                return None
            
            # Burn STGM directly from the Swarm's vault
            vault._write_tx(CasinoTransaction(
                ts=now,
                action="SVL_METABOLISM",
                casino_delta=-0.005,
                player_delta=0.0,
                memo=f"Visual cognition burn for frame {scene_hash[:8]}"
            ))
        except ImportError:
            pass

        # Build the event — NO raw frame data stored
        eid = hashlib.sha256(
            f"{now}:{scene_hash}:{saliency}".encode()
        ).hexdigest()[:10]

        event = VisionEvent(
            event_id         = eid,
            timestamp        = now,
            saliency_score   = round(saliency, 4),
            scene_hash       = scene_hash,
            change_magnitude = round(change, 4),
            attention_state  = self.attention.value,
            frame_dimensions = (gray.shape[0], gray.shape[1]),
            objects_hint     = objects_hint,
        )

        # ── SVL Constraint #4: Objective Scoring ──────────────────
        try:
            try:
                from System.objective_registry import get_registry
            except ImportError:
                from objective_registry import get_registry
            reg = get_registry()
            # Estimate if this visual trace provides actual information gain
            score = reg.score_action({
                "information_gain": saliency,
                "resource_efficiency": -0.1
            })
            if score < -0.1:
                # Frame is useless noise, discard
                self._frames_dropped += 1
                return None
        except ImportError:
            pass

        # ── SVL Constraint #5: Contradiction Check ────────────────
        try:
            try:
                from System.contradiction_engine import get_engine
            except ImportError:
                from contradiction_engine import get_engine
            engine = get_engine()
            # If the vision trace claims something contradictory to known state, drop it.
            safe, reason = engine.assert_belief(f"SVL_{eid}", "vision_state", objects_hint)
            if not safe:
                print(f"🛑 [SVL CONTRADICTION] Vision trace blocked: {reason}")
                return None
        except ImportError:
            pass

        # Write trace to blackboard
        self._write_trace(event)
        self._events_emitted += 1

        return event

    def _write_trace(self, event: VisionEvent):
        """Append event to vision log. This IS the pheromone."""
        try:
            with open(_VISION_LOG, "a") as f:
                f.write(json.dumps(asdict(event)) + "\n")
        except Exception:
            pass

    def report(self) -> str:
        lines = [
            f"[VISION] Camera: {'OPEN' if self._cap else 'CLOSED'}",
            f"  Attention: {self.attention.value} ({self.target_fps} FPS)",
            f"  Sampled: {self._frames_sampled}",
            f"  Dropped: {self._frames_dropped} (below saliency {SALIENCY_THRESHOLD})",
            f"  Events:  {self._events_emitted}",
        ]
        if self._frames_sampled > 0:
            drop_rate = self._frames_dropped / self._frames_sampled * 100
            lines.append(f"  Drop rate: {drop_rate:.0f}% (higher = more efficient)")
        return "\n".join(lines)


# ── Demo (no camera required) ─────────────────────────────────

if __name__ == "__main__":
    print("=" * 58)
    print("  SIFTA — STIGMERGIC VISION")
    print("  The camera is a pheromone emitter, not a video feed.")
    print("=" * 58 + "\n")

    v = StigmergicVision()
    ok = v.start()

    if ok:
        print(f"\nSampling 20 frames at IDLE ({v.target_fps} FPS)...\n")
        for _ in range(20):
            event = v.sample()
            if event:
                print(f"  📷 [{event.event_id}] saliency={event.saliency_score:.2f} "
                      f"change={event.change_magnitude:.3f}")
            time.sleep(v.sample_interval)

        v.set_attention(AttentionState.ACTIVE)
        print(f"\nSampling 10 frames at ACTIVE ({v.target_fps} FPS)...\n")
        for _ in range(10):
            event = v.sample()
            if event:
                print(f"  📷 [{event.event_id}] saliency={event.saliency_score:.2f}")
            time.sleep(v.sample_interval)

        v.stop()
    else:
        print("No camera available. Install opencv-python to enable vision.")

    print(f"\n{v.report()}")
    print("\n  POWER TO THE SWARM 🐜⚡")
