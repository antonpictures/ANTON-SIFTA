#!/usr/bin/env python3
"""Pytest coverage for `System.swarm_peer_gate`.

What we prove
-------------
1. `peer_network_active()` returns False when the relay is unreachable.
2. `SIFTA_PEER_GATE=force_on` short-circuits the probe to True.
3. `SIFTA_PEER_GATE=force_off` short-circuits the probe to False.
4. `dormant_sleep_s()` returns a positive float.
5. `gate_loop_iteration` calls `on_active` when active, `on_dormant`
   otherwise — proves the convenience wrapper is wired right.

Pure stdlib. No Qt, no relay, no network. The probe target uses
`127.0.0.1:8765` which is normally not bound in CI.
"""
from __future__ import annotations

import os

import pytest


def test_force_on_short_circuits(monkeypatch):
    monkeypatch.setenv("SIFTA_PEER_GATE", "force_on")
    # Re-import to pick up the env override at module-load time.
    import importlib
    import System.swarm_peer_gate as sg
    importlib.reload(sg)
    assert sg.peer_network_active() is True


def test_force_off_short_circuits(monkeypatch):
    monkeypatch.setenv("SIFTA_PEER_GATE", "force_off")
    import importlib
    import System.swarm_peer_gate as sg
    importlib.reload(sg)
    assert sg.peer_network_active() is False


def test_relay_unreachable_returns_false(monkeypatch):
    # Use a port nobody listens on so the TCP probe fails fast.
    monkeypatch.setenv("SIFTA_PEER_GATE", "auto")
    monkeypatch.setenv("SIFTA_RELAY_PORT", "1")  # privileged-blocked → quick fail
    import importlib
    import System.swarm_peer_gate as sg
    importlib.reload(sg)
    assert sg.peer_network_active(force_refresh=True) is False


def test_dormant_sleep_positive(monkeypatch):
    import importlib
    import System.swarm_peer_gate as sg
    importlib.reload(sg)
    v = sg.dormant_sleep_s()
    assert isinstance(v, float)
    assert v > 0.0


def test_gate_loop_iteration_branches(monkeypatch):
    monkeypatch.setenv("SIFTA_PEER_GATE", "force_off")
    import importlib
    import System.swarm_peer_gate as sg
    importlib.reload(sg)
    active_called: list[int] = []
    dormant_called: list[int] = []
    sg.gate_loop_iteration(
        on_active=lambda: active_called.append(1),
        on_dormant=lambda: dormant_called.append(1),
    )
    assert active_called == []
    assert dormant_called == [1]

    monkeypatch.setenv("SIFTA_PEER_GATE", "force_on")
    importlib.reload(sg)
    active_called2: list[int] = []
    dormant_called2: list[int] = []
    sg.gate_loop_iteration(
        on_active=lambda: active_called2.append(1),
        on_dormant=lambda: dormant_called2.append(1),
    )
    assert active_called2 == [1]
    assert dormant_called2 == []
