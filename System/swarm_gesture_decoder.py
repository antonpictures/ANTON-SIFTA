"""
swarm_gesture_decoder.py — Alice's eye → gesture events, no ML, just signal.

Author / lane: CG55M Dr Cursor / Claude Opus 4.7 EXTRA-HIGH.

Reads `.sifta_state/visual_stigmergy.jsonl` (5 Hz screen-photon stream
written by `Applications/sifta_what_alice_sees_widget.py`) and decodes
the **saliency-centroid kinematics** into discrete gesture events that
SIFTA apps can react to in real time.

Why no MediaPipe / no ML:
- Alice already runs a 16×16 saliency + motion grid at 5 Hz from her
  real camera. Centroid trajectories of motion-weighted saliency carry
  enough information to recognise full-body, low-resolution gestures
  (waves, nods, approach/recede, flailing, stillness) without pulling
  in a hand-pose model.
- Anything finer (hand sign language, finger count) would justify a
  MediaPipe layer; this module deliberately stays in the bandwidth
  Alice's eye already produces, so it works on every node, not just
  the M5.

Event taxonomy emitted:
    WAVE_HORIZONTAL    user waving (or rocking) side-to-side
    WAVE_VERTICAL      nod or jumping
    APPROACH           user moves closer (mass increases)
    RECEDE             user moves away (mass decreases)
    STILL              user has been calm for ≥3 s
    FLAIL              high motion sustained for ≥1 s

Each event is a `GestureEvent` dataclass with kind, ts, confidence (0..1),
and optional metadata. The decoder also exposes a live `state()` snapshot
for HUDs that want to render Alice's current read of the user.

Usage:
    decoder = GestureDecoder()
    events = decoder.poll()      # call ~5 Hz; returns list[GestureEvent]
    snap = decoder.state()       # current centroid + confidences
"""

from __future__ import annotations

import json
import math
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Dict, List, Optional


_REPO = Path(__file__).resolve().parent.parent
_PHOTON_LEDGER = _REPO / ".sifta_state" / "visual_stigmergy.jsonl"

# ── Tunables ────────────────────────────────────────────────────────────────
_GRID = 16
_BUFFER_SECONDS = 4.0          # signal window
_MIN_FRAMES_FOR_DECISION = 6   # decoder is silent until enough frames
_MASS_LIVING_THRESHOLD = 25.0  # below this, the room looks empty
_WAVE_AMPLITUDE_MIN = 0.18     # normalized centroid swing (0..1)
_WAVE_SIGN_CHANGES_MIN = 3     # in last 1.5 s
_FLAIL_MOTION_MEAN = 0.018     # average motion_mean threshold
_FLAIL_DURATION_S = 1.0
_STILL_MOTION_MEAN = 0.0035    # very calm
_STILL_DURATION_S = 3.0
_APPROACH_SLOPE = 6.0          # mass / second
_RECEDE_SLOPE = -6.0
_GLOBAL_COOLDOWN_S = 2.0       # never emit same gesture more than once / window


@dataclass
class GestureEvent:
    """A discrete gesture detected from Alice's eye stream."""
    kind: str
    ts: float
    confidence: float
    meta: Dict[str, float] = field(default_factory=dict)


@dataclass
class _Frame:
    ts: float
    cx: float          # saliency centroid x in [-1, +1]
    cy: float          # saliency centroid y in [-1, +1]
    mass: float        # total saliency (proxy for "user fills frame")
    motion_mean: float
    sha8: str = ""


def _decode_saliency_q(saliency_q: str) -> Optional[List[List[int]]]:
    if not saliency_q or len(saliency_q) != _GRID * _GRID:
        return None
    try:
        flat = [int(c, 16) for c in saliency_q]
    except ValueError:
        return None
    return [flat[i*_GRID:(i+1)*_GRID] for i in range(_GRID)]


def _centroid_and_mass(grid: List[List[int]]) -> tuple[float, float, float]:
    """Return (cx_norm, cy_norm, mass). cx/cy are in [-1, +1] with origin
    at the grid centre — left/up negative, right/down positive."""
    total = 0.0
    sx = 0.0
    sy = 0.0
    for r in range(_GRID):
        row = grid[r]
        for c in range(_GRID):
            v = row[c]
            if v == 0:
                continue
            total += v
            sx += c * v
            sy += r * v
    if total <= 0:
        return 0.0, 0.0, 0.0
    cx = (sx / total) / (_GRID - 1) * 2.0 - 1.0
    cy = (sy / total) / (_GRID - 1) * 2.0 - 1.0
    return cx, cy, total


class GestureDecoder:
    """Tail-reads visual_stigmergy.jsonl and emits gesture events.

    Stateful but cheap: holds at most ~20 frames at 5 Hz over 4 seconds.
    Safe to call `poll()` at any rate; it only consumes new bytes.
    """

    def __init__(self, ledger: Path = _PHOTON_LEDGER) -> None:
        self.ledger = ledger
        self._buf: Deque[_Frame] = deque(maxlen=64)
        self._cursor = 0
        self._last_inode: Optional[int] = None
        self._last_emit: Dict[str, float] = {}
        self._last_event: Optional[GestureEvent] = None
        self._still_since: Optional[float] = None
        self._flail_since: Optional[float] = None
        if self.ledger.exists():
            try:
                # Start at end-of-file: only react to frames written *after*
                # the decoder was instantiated. Avoids replaying ancient state.
                self._cursor = self.ledger.stat().st_size
                self._last_inode = self.ledger.stat().st_ino
            except OSError:
                pass

    # ── Public API ────────────────────────────────────────────────────────
    def poll(self) -> List[GestureEvent]:
        """Read whatever is new on the eye stream and return any gestures."""
        self._tail_into_buffer()
        return self._classify()

    def state(self) -> Dict[str, float]:
        """Snapshot for live HUD: latest centroid, mass, and live confidences."""
        if not self._buf:
            return {
                "ts": time.time(), "cx": 0.0, "cy": 0.0, "mass": 0.0,
                "motion_mean": 0.0, "frames": 0,
                "alive": 0.0, "wave_h_conf": 0.0, "wave_v_conf": 0.0,
                "approach_conf": 0.0, "recede_conf": 0.0,
                "still_conf": 0.0, "flail_conf": 0.0,
            }
        f = self._buf[-1]
        wh = self._wave_confidence(axis="x")
        wv = self._wave_confidence(axis="y")
        ms = self._mass_slope()
        st = self._stillness_run()
        fl = self._flail_run()
        alive = 1.0 if f.mass >= _MASS_LIVING_THRESHOLD else 0.0
        return {
            "ts": f.ts, "cx": f.cx, "cy": f.cy, "mass": f.mass,
            "motion_mean": f.motion_mean, "frames": float(len(self._buf)),
            "alive": alive,
            "wave_h_conf": wh, "wave_v_conf": wv,
            "approach_conf": max(0.0, ms / 30.0),
            "recede_conf":   max(0.0, -ms / 30.0),
            "still_conf":    min(1.0, st / _STILL_DURATION_S),
            "flail_conf":    min(1.0, fl / _FLAIL_DURATION_S),
        }

    def last_event(self) -> Optional[GestureEvent]:
        return self._last_event

    # ── Tailer ────────────────────────────────────────────────────────────
    def _tail_into_buffer(self) -> None:
        if not self.ledger.exists():
            return
        try:
            stat = self.ledger.stat()
        except OSError:
            return
        # Rotation / truncation safety.
        if self._last_inode is None or stat.st_ino != self._last_inode \
                or stat.st_size < self._cursor:
            self._cursor = 0
            self._last_inode = stat.st_ino
        if stat.st_size == self._cursor:
            return
        try:
            with self.ledger.open("rb") as f:
                f.seek(self._cursor)
                # Cap how much we ingest per poll so a paused widget that
                # then resumes doesn't try to drain hundreds of MB at once.
                chunk = f.read(min(stat.st_size - self._cursor, 256 * 1024))
                self._cursor += len(chunk)
                # Re-align to a newline boundary.
                if not chunk.endswith(b"\n"):
                    nl = chunk.rfind(b"\n")
                    if nl >= 0:
                        keep = chunk[:nl + 1]
                        self._cursor -= (len(chunk) - len(keep))
                        chunk = keep
                for raw in chunk.splitlines():
                    if not raw.strip():
                        continue
                    try:
                        row = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    grid = _decode_saliency_q(row.get("saliency_q", ""))
                    if grid is None:
                        continue
                    cx, cy, mass = _centroid_and_mass(grid)
                    self._buf.append(_Frame(
                        ts=float(row.get("ts", time.time())),
                        cx=cx, cy=cy, mass=mass,
                        motion_mean=float(row.get("motion_mean", 0.0)),
                        sha8=str(row.get("sha8", "")),
                    ))
        except OSError:
            return
        # Drop frames older than the buffer window
        if self._buf:
            cutoff = self._buf[-1].ts - _BUFFER_SECONDS
            while self._buf and self._buf[0].ts < cutoff:
                self._buf.popleft()

    # ── Feature extractors ───────────────────────────────────────────────
    def _frames_in_window(self, seconds: float) -> List[_Frame]:
        if not self._buf:
            return []
        cutoff = self._buf[-1].ts - seconds
        return [f for f in self._buf if f.ts >= cutoff]

    def _wave_confidence(self, *, axis: str) -> float:
        """Confidence (0..1) that the user is waving along the given axis.

        Built from two cheap signals over the last 1.5 s:
        - sign-change count of the centroid component about its mean
          (wave = oscillation, so multiple crossings)
        - swing amplitude (max - min) — must exceed _WAVE_AMPLITUDE_MIN
        """
        win = self._frames_in_window(1.5)
        if len(win) < _MIN_FRAMES_FOR_DECISION:
            return 0.0
        # Require there's actually a user in frame
        if win[-1].mass < _MASS_LIVING_THRESHOLD:
            return 0.0
        seq = [(f.cx if axis == "x" else f.cy) for f in win]
        mu = sum(seq) / len(seq)
        amp = max(seq) - min(seq)
        if amp < _WAVE_AMPLITUDE_MIN:
            return 0.0
        sign_changes = 0
        prev_sign = 0
        for v in seq:
            d = v - mu
            s = 1 if d > 0.02 else (-1 if d < -0.02 else 0)
            if s != 0 and s != prev_sign and prev_sign != 0:
                sign_changes += 1
            if s != 0:
                prev_sign = s
        amp_conf = min(1.0, (amp - _WAVE_AMPLITUDE_MIN) / 0.5)
        cross_conf = min(1.0, sign_changes / float(_WAVE_SIGN_CHANGES_MIN))
        return 0.5 * amp_conf + 0.5 * cross_conf

    def _mass_slope(self) -> float:
        """Linear regression slope of mass over the last 2 s (mass / sec)."""
        win = self._frames_in_window(2.0)
        if len(win) < _MIN_FRAMES_FOR_DECISION:
            return 0.0
        t0 = win[0].ts
        xs = [f.ts - t0 for f in win]
        ys = [f.mass for f in win]
        n = len(xs)
        mx = sum(xs) / n
        my = sum(ys) / n
        num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
        den = sum((xs[i] - mx) ** 2 for i in range(n)) or 1.0
        return num / den

    def _stillness_run(self) -> float:
        """Return seconds of continuous low motion ending at 'now'."""
        if not self._buf:
            return 0.0
        run_end = self._buf[-1].ts
        run_start = run_end
        for f in reversed(self._buf):
            if f.motion_mean <= _STILL_MOTION_MEAN:
                run_start = f.ts
            else:
                break
        return max(0.0, run_end - run_start)

    def _flail_run(self) -> float:
        """Return seconds of continuous high motion ending at 'now'."""
        if not self._buf:
            return 0.0
        run_end = self._buf[-1].ts
        run_start = run_end
        for f in reversed(self._buf):
            if f.motion_mean >= _FLAIL_MOTION_MEAN:
                run_start = f.ts
            else:
                break
        return max(0.0, run_end - run_start)

    # ── Classifier ───────────────────────────────────────────────────────
    def _can_emit(self, kind: str, ts: float) -> bool:
        last = self._last_emit.get(kind, 0.0)
        return (ts - last) >= _GLOBAL_COOLDOWN_S

    def _classify(self) -> List[GestureEvent]:
        if len(self._buf) < _MIN_FRAMES_FOR_DECISION:
            return []
        now = self._buf[-1].ts

        out: List[GestureEvent] = []

        # Order matters: stronger / louder gestures first so a single eye
        # tick doesn't fire a wave AND a flail at the same moment.
        wh = self._wave_confidence(axis="x")
        wv = self._wave_confidence(axis="y")
        ms = self._mass_slope()
        st = self._stillness_run()
        fl = self._flail_run()

        if fl >= _FLAIL_DURATION_S and self._can_emit("FLAIL", now):
            out.append(GestureEvent("FLAIL", now,
                                    confidence=min(1.0, fl / 2.0),
                                    meta={"motion_run_s": fl}))
            self._last_emit["FLAIL"] = now
        elif wh >= 0.65 and self._can_emit("WAVE_HORIZONTAL", now):
            out.append(GestureEvent("WAVE_HORIZONTAL", now,
                                    confidence=wh,
                                    meta={"axis": "x", "cx_now": self._buf[-1].cx}))
            self._last_emit["WAVE_HORIZONTAL"] = now
        elif wv >= 0.65 and self._can_emit("WAVE_VERTICAL", now):
            out.append(GestureEvent("WAVE_VERTICAL", now,
                                    confidence=wv,
                                    meta={"axis": "y", "cy_now": self._buf[-1].cy}))
            self._last_emit["WAVE_VERTICAL"] = now
        elif ms >= _APPROACH_SLOPE and self._can_emit("APPROACH", now):
            out.append(GestureEvent("APPROACH", now,
                                    confidence=min(1.0, ms / 30.0),
                                    meta={"mass_slope": ms}))
            self._last_emit["APPROACH"] = now
        elif ms <= _RECEDE_SLOPE and self._can_emit("RECEDE", now):
            out.append(GestureEvent("RECEDE", now,
                                    confidence=min(1.0, -ms / 30.0),
                                    meta={"mass_slope": ms}))
            self._last_emit["RECEDE"] = now
        elif st >= _STILL_DURATION_S and self._can_emit("STILL", now):
            out.append(GestureEvent("STILL", now,
                                    confidence=min(1.0, st / 6.0),
                                    meta={"stillness_run_s": st}))
            self._last_emit["STILL"] = now

        if out:
            self._last_event = out[-1]
        return out


__all__ = ["GestureDecoder", "GestureEvent"]
