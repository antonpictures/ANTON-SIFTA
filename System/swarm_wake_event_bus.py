"""Singleton Qt event bus for SIFTA wake-name events.

Purpose
-------
The wake-name reflex (`swarm_alice_wake_ear`) decides, per turn, whether
the owner's noisy speech was actually a direct address to Alice. When
that decision fires we want a visible, time-locked desktop response —
"Alice heard her name" — without coupling the widgets to each other.

Wire-up (Qt signal pattern)
---------------------------
- `WAKE_BUS.wake_fired(dict)`     fires when the talk widget receives a
                                  positive wake-ear receipt for the
                                  current turn. The payload is the same
                                  row written to .sifta_state/
                                  alice_wake_ear.jsonl.
- `WAKE_BUS.frame_ready(str)`     fires when the camera widget has
                                  written a still JPEG to disk in
                                  response to a wake event.

Why a singleton bus
-------------------
Three widgets need to talk:
1. `Applications/sifta_talk_to_alice_widget.py`  — *emitter* of wake_fired
2. `Applications/sifta_what_alice_sees_widget.py` — *responder* (saves a
                                                    fresh frame, emits
                                                    frame_ready)
3. `sifta_os_desktop.py`                          — *painter* of a brief
                                                    flash overlay
Coupling them directly would require each widget to find the others
through `parent().parent()...` chains. A module-level singleton keeps
the wire short and the failure mode honest (if Qt is missing, the bus
is a no-op object whose `.emit()` calls do nothing).

Truth labels (§7.11)
--------------------
- `OPERATIONAL` — this module exposes a Qt-or-stub bus singleton; the
                   signals are real PyQt6 signals when PyQt6 is
                   importable, no-op stubs otherwise.
- `ARCHITECT_DOCTRINE` — emitting `wake_fired` is reserved for the
                   talk widget's confirmed wake-ear receipt path; do
                   NOT emit from speculative or heuristic call sites.

Receipt invariants
------------------
- `wake_fired` is a *display* signal. Persistence of the wake decision
  itself remains in `.sifta_state/alice_wake_ear.jsonl` (owned by
  `swarm_alice_wake_ear`).
- `frame_ready` is a *display* signal. The JPEG it points to is a
  transient artifact written by the camera widget; do not rely on it
  for downstream inference (use `visual_stigmergy_last_frame.jpg`
  instead, which carries a periodic save guarantee).

Author : Cowork (Claude Opus 4.7, Architect-support lane, 2026-05-11).
"""
from __future__ import annotations

from typing import Any, Optional

try:  # PyQt6 path — real signals
    from PyQt6.QtCore import QObject, pyqtSignal

    class _WakeEventBus(QObject):
        """Singleton Qt object: cross-widget wake-event signals."""

        # Emitted by the talk widget when a positive wake-ear receipt
        # is written for the current owner turn. Payload = the row.
        wake_fired = pyqtSignal(dict)

        # Emitted by the camera widget after saving a fresh JPEG in
        # response to a wake event. Payload = absolute path to JPEG.
        frame_ready = pyqtSignal(str)

        def __init__(self) -> None:
            super().__init__()

    _BUS: Optional[_WakeEventBus] = None

    def wake_bus() -> _WakeEventBus:
        """Return the process-wide singleton wake-event bus."""
        global _BUS
        if _BUS is None:
            _BUS = _WakeEventBus()
        return _BUS

    PYQT_AVAILABLE = True

except Exception:  # headless / pytest-no-Qt path — stub bus, never raises
    PYQT_AVAILABLE = False

    class _StubSignal:
        """Inert signal: connect/emit are no-ops, but exist."""

        def __init__(self) -> None:
            self._slots: list[Any] = []

        def connect(self, slot: Any) -> None:
            self._slots.append(slot)

        def disconnect(self, slot: Any = None) -> None:
            if slot is None:
                self._slots.clear()
            elif slot in self._slots:
                self._slots.remove(slot)

        def emit(self, *args: Any, **kwargs: Any) -> None:
            # Best-effort: fan out to connected Python callables (tests
            # rely on this to verify the wire without spinning up Qt).
            for slot in list(self._slots):
                try:
                    slot(*args, **kwargs)
                except Exception:
                    pass

    class _WakeEventBus:  # type: ignore[no-redef]
        """Stub bus mirroring the Qt API."""

        def __init__(self) -> None:
            self.wake_fired = _StubSignal()
            self.frame_ready = _StubSignal()

    _BUS: Optional[_WakeEventBus] = None  # type: ignore[no-redef]

    def wake_bus() -> _WakeEventBus:  # type: ignore[no-redef]
        global _BUS
        if _BUS is None:
            _BUS = _WakeEventBus()
        return _BUS


__all__ = ["wake_bus", "PYQT_AVAILABLE"]
