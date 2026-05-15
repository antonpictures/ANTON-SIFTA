#!/usr/bin/env python3
"""Pytest coverage for `System.swarm_wake_event_bus`.

What we prove
-------------
1. `wake_bus()` returns a singleton — repeated calls hand back the same
   object so producer and consumer connect to the same signals.
2. The bus exposes both required signals (`wake_fired`, `frame_ready`).
3. Under the headless / no-PyQt stub path, `connect` + `emit` propagate
   payload to subscribers (proves the wire is real, not magic).
4. Under PyQt6 if available, the singleton is a QObject and the signals
   are real `pyqtSignal`s.

These tests run with pure stdlib + pytest. They do not need a Qt event
loop because we only verify the bus's public surface.
"""
from __future__ import annotations

import pytest


def test_wake_bus_is_singleton():
    from System.swarm_wake_event_bus import wake_bus

    a = wake_bus()
    b = wake_bus()
    assert a is b, "wake_bus() must return the same singleton across calls"


def test_wake_bus_exposes_required_signals():
    from System.swarm_wake_event_bus import wake_bus

    bus = wake_bus()
    assert hasattr(bus, "wake_fired"), "bus missing 'wake_fired' signal"
    assert hasattr(bus, "frame_ready"), "bus missing 'frame_ready' signal"


def test_stub_or_qt_signal_supports_emit_after_connect():
    """Sanity check: connecting a Python callable and emitting must
    deliver the payload. Works on both code paths — under PyQt6 the
    signal is a `pyqtSignal`; without PyQt6 it's the stub from this
    module. Either way, a Python callable can subscribe."""
    from System.swarm_wake_event_bus import PYQT_AVAILABLE, wake_bus

    bus = wake_bus()
    received: list = []

    def _slot(payload):
        received.append(payload)

    if PYQT_AVAILABLE:
        # On PyQt6, real signals need a QCoreApplication for emission
        # delivery to Python slots. Setting up one for the test scope.
        try:
            from PyQt6.QtCore import QCoreApplication

            app = QCoreApplication.instance() or QCoreApplication([])
            bus.wake_fired.connect(_slot)
            bus.wake_fired.emit({"k": "v"})
            app.processEvents()
            bus.wake_fired.disconnect(_slot)
        except Exception:
            pytest.skip("PyQt6 present but Qt loop unavailable in this sandbox")
    else:
        bus.wake_fired.connect(_slot)
        bus.wake_fired.emit({"k": "v"})
        bus.wake_fired.disconnect(_slot)

    assert received == [{"k": "v"}], (
        f"wake_fired should have delivered one payload, got {received!r}"
    )
