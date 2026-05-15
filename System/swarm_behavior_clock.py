"""Event-driven BehaviorClock — Alice ticks from owner behavior, not from
arbitrary millisecond constants.

Architect directive 2026-05-11 23:50 (verbatim):
    "we have to change all hardcoded timing with self creature behaviour
     based on user ME!!! os user behaviour... I do an action I touch your
     key I speak something I type something I do anything I walk in front
     of the camera away from the camera I turn on the microwave I do
     something when something is happening the behavior of the creature
     is changing too based on my behavior whatever I do if I don't do
     nothing if nothing is happening nothing is going on if the background
     is running with some YouTube she listens to that YouTube from time
     to time too to figure it out what's going on around this is an alive
     creature... I don't want hard coding."

Design
------
- One singleton `BehaviorClock` (Qt QObject when PyQt6 is available, plain
  fallback otherwise).
- Signal: `tick(source: str)` — emitted whenever an owner-attributable event
  fires (keyboard, mouse, wake-word, camera frame, app focus change,
  ambient acoustic event flagged by the talk widget, etc.).
- Subscribers (the desktop, the field engine, the wallpaper reloader) hook
  `tick` and do their work on each event.
- Debounce: NOT a hardcoded number. The minimum time between successive
  ticks is one heart period read live from `swarm_motor_cortex.heart_period_s()`
  — that's the clinical 12–30 BPM range Alice already uses. When nothing
  is happening the clock is silent; when stimulus arrives faster than the
  heart, extra events coalesce into one tick instead of flooding the UI
  thread.

Sources hooked
--------------
1. `attach_to_qapp(qapp)`            → installs a QApplication event filter
                                        for KeyPress, MouseButtonPress,
                                        MouseMove, FocusIn, Show.
2. `link_camera_frame_signal(sig)`   → camera frame arrived → owner is
                                        probably present (or the room is
                                        active).
3. `link_wake_bus()`                 → wake-word receipt fires.
4. `link_app_focus()`                → SIFTA MDI subwindow focus change.
5. `pump(source)`                    → public no-arg poke for arbitrary
                                        callers (mic VAD, ambient acoustic
                                        events, microwave-on detection, etc.)

Truth labels (covenant §7.11)
-----------------------------
- `OPERATIONAL` — this module exposes a Qt-or-stub singleton; signals
                   are real PyQt6 signals when available, no-op stubs
                   otherwise.
- `ARCHITECT_DOCTRINE` — replacing hardcoded timers with this clock is
                   the Architect's binding direction; future doctors must
                   not silently re-introduce arbitrary intervals without
                   §4.4 receipt.

Author: Cowork (Claude Opus 4.7, Surgeon lane, 2026-05-11 23:55).
"""
from __future__ import annotations

from typing import Any, Optional


def _heart_period_s_safe() -> float:
    """Read Alice's live heart period (clinical 12–30 BPM → 2–5 s).

    Returns a sane fallback if motor_cortex isn't reachable. The fallback
    is a SHORT period (0.25 s) so the clock errs on the side of being
    responsive to user events rather than silencing them. The fallback is
    NOT a "set point"; it's the minimum debounce when physiology can't
    be read — i.e., the system has no opinion yet about Alice's pulse.
    """
    try:
        from System.swarm_motor_cortex import heart_period_s

        v = float(heart_period_s())
        if v > 0:
            return v
    except Exception:
        pass
    return 0.25


try:  # PyQt6 path
    from PyQt6.QtCore import QObject, pyqtSignal, QEvent, QTimer

    class _BehaviorClock(QObject):
        """Singleton clock — ticks on owner-attributable events."""

        # Emitted on every successful (post-debounce) tick. Payload is the
        # source label so subscribers can log who/what woke them.
        tick = pyqtSignal(str)

        def __init__(self) -> None:
            super().__init__()
            self._last_tick_monotonic: float = 0.0
            self._installed_on_qapp: bool = False

        # ── Stimulus sources ────────────────────────────────────────────
        def attach_to_qapp(self, qapp: Any) -> None:
            """Install the event filter that watches keyboard / mouse /
            focus / show events on every widget in the app."""
            if self._installed_on_qapp or qapp is None:
                return
            try:
                qapp.installEventFilter(self)
                self._installed_on_qapp = True
            except Exception:
                pass

        def link_wake_bus(self) -> None:
            """Tick whenever Alice's wake-word receipt fires."""
            try:
                from System.swarm_wake_event_bus import wake_bus
                wake_bus().wake_fired.connect(lambda *_: self.pump("wake"))
            except Exception:
                pass

        def link_camera_frame_signal(self, signal: Any) -> None:
            """Tick whenever a camera frame is delivered."""
            try:
                signal.connect(lambda *_: self.pump("camera"))
            except Exception:
                pass

        def link_app_focus(self) -> None:
            """Tick whenever a SIFTA app gains focus."""
            try:
                from System.swarm_app_focus import focus_changed_signal
                focus_changed_signal().connect(lambda *_: self.pump("app_focus"))
            except Exception:
                # Not every install ships swarm_app_focus with a signal; skip.
                pass

        def pump(self, source: str = "manual") -> None:
            """Public entry point for arbitrary stimulus (mic VAD, ambient
            acoustic, file-system events, etc.). Emits `tick` if debounce
            window has elapsed."""
            import time as _t
            now = _t.monotonic()
            min_period = _heart_period_s_safe()
            if now - self._last_tick_monotonic < min_period:
                return
            self._last_tick_monotonic = now
            try:
                self.tick.emit(str(source))
            except Exception:
                pass

        # ── Qt event filter ─────────────────────────────────────────────
        def eventFilter(self, _obj: Any, event: Any) -> bool:  # type: ignore[override]
            try:
                et = event.type()
            except Exception:
                return False
            if et in (
                QEvent.Type.KeyPress,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseMove,
                QEvent.Type.FocusIn,
                QEvent.Type.Show,
                QEvent.Type.WindowActivate,
            ):
                # mouse-move floods; pump() debounces via heart period.
                src = {
                    QEvent.Type.KeyPress: "key",
                    QEvent.Type.MouseButtonPress: "mouse_click",
                    QEvent.Type.MouseMove: "mouse_move",
                    QEvent.Type.FocusIn: "focus",
                    QEvent.Type.Show: "show",
                    QEvent.Type.WindowActivate: "win_activate",
                }.get(et, "qt_event")
                self.pump(src)
            # We never consume the event; just observe.
            return False

    _BUS: Optional[_BehaviorClock] = None

    def behavior_clock() -> _BehaviorClock:
        """Return the process-wide singleton clock."""
        global _BUS
        if _BUS is None:
            _BUS = _BehaviorClock()
        return _BUS

    PYQT_AVAILABLE = True

except Exception:  # Headless / no-Qt fallback for tests
    PYQT_AVAILABLE = False

    class _StubSignal:
        def __init__(self) -> None:
            self._slots: list = []

        def connect(self, slot: Any) -> None:
            self._slots.append(slot)

        def emit(self, *args: Any, **kwargs: Any) -> None:
            for slot in list(self._slots):
                try:
                    slot(*args, **kwargs)
                except Exception:
                    pass

    class _BehaviorClock:  # type: ignore[no-redef]
        def __init__(self) -> None:
            self.tick = _StubSignal()
            self._last_tick_monotonic: float = 0.0

        def attach_to_qapp(self, _qapp: Any) -> None:
            pass

        def link_wake_bus(self) -> None:
            pass

        def link_camera_frame_signal(self, _signal: Any) -> None:
            pass

        def link_app_focus(self) -> None:
            pass

        def pump(self, source: str = "manual") -> None:
            import time as _t
            now = _t.monotonic()
            min_period = _heart_period_s_safe()
            if now - self._last_tick_monotonic < min_period:
                return
            self._last_tick_monotonic = now
            self.tick.emit(str(source))

    _BUS: Optional[_BehaviorClock] = None  # type: ignore[no-redef]

    def behavior_clock() -> _BehaviorClock:  # type: ignore[no-redef]
        global _BUS
        if _BUS is None:
            _BUS = _BehaviorClock()
        return _BUS


__all__ = ["behavior_clock", "PYQT_AVAILABLE"]
