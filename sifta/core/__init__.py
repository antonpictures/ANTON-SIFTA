"""sifta.core — DimOS-inspired body pipes (typed streams + blueprints + transport)."""

from sifta.core.stream import In, Out, StreamBus, StreamMessage, typed_channel
from sifta.core.blueprint import Blueprint, ModuleSpec, autoconnect
from sifta.core.transport import InProcessTransport, LocalhostIPCTransport, Transport
from sifta.core.replay import ReplayMode, SimulationMode, assert_sim_before_real
from sifta.core.maturity import EMBODIMENT_MATURITY, maturity_lines
from sifta.core.spy import StreamSpy

__all__ = [
    "In",
    "Out",
    "StreamBus",
    "StreamMessage",
    "typed_channel",
    "Blueprint",
    "ModuleSpec",
    "autoconnect",
    "InProcessTransport",
    "LocalhostIPCTransport",
    "Transport",
    "ReplayMode",
    "SimulationMode",
    "assert_sim_before_real",
    "EMBODIMENT_MATURITY",
    "maturity_lines",
    "StreamSpy",
]
