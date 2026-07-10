#!/usr/bin/env python3
"""sifta.core.blueprint — organ blueprints + autoconnect (DB2).

Compose hardware_body + eye + motor + mcp by explicit (name, type) stream maps.
Stigmergic: no master orchestrator — modules declare ports; autoconnect wires
matching Out→In pairs onto a shared StreamBus.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sifta.core.stream import In, Out, StreamBus


@dataclass
class PortSpec:
    name: str
    type_name: str
    direction: str  # "in" | "out"


@dataclass
class ModuleSpec:
    """One organ's blueprint: name + typed ports + optional build hook."""

    name: str
    ports: list[PortSpec] = field(default_factory=list)
    build: Optional[Callable[["WiredModule", StreamBus], Any]] = None
    meta: dict[str, Any] = field(default_factory=dict)

    def outs(self) -> list[PortSpec]:
        return [p for p in self.ports if p.direction == "out"]

    def ins(self) -> list[PortSpec]:
        return [p for p in self.ports if p.direction == "in"]


@dataclass
class WiredModule:
    spec: ModuleSpec
    outs: dict[tuple[str, str], Out]
    ins: dict[tuple[str, str], In]
    instance: Any = None


@dataclass
class Blueprint:
    modules: list[ModuleSpec] = field(default_factory=list)
    remaps: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)
    bus: Optional[StreamBus] = None

    def add(self, *modules: ModuleSpec) -> "Blueprint":
        self.modules.extend(modules)
        return self

    def remap(self, src: tuple[str, str], dst: tuple[str, str]) -> "Blueprint":
        self.remaps[src] = dst
        return self

    def build(self, bus: Optional[StreamBus] = None) -> "BuiltGraph":
        bus = bus or self.bus or StreamBus()
        wired: list[WiredModule] = []
        out_index: dict[tuple[str, str], list[str]] = {}
        in_index: dict[tuple[str, str], list[str]] = {}

        for mod in self.modules:
            outs: dict[tuple[str, str], Out] = {}
            ins: dict[tuple[str, str], In] = {}
            for p in mod.outs():
                key = self.remaps.get((p.name, p.type_name), (p.name, p.type_name))
                o = Out(key[0], key[1], bus)
                outs[key] = o
                out_index.setdefault(key, []).append(mod.name)
            for p in mod.ins():
                key = self.remaps.get((p.name, p.type_name), (p.name, p.type_name))
                i = In(key[0], key[1], bus).bind(bus)
                ins[key] = i
                in_index.setdefault(key, []).append(mod.name)
            wm = WiredModule(spec=mod, outs=outs, ins=ins)
            if callable(mod.build):
                wm.instance = mod.build(wm, bus)
            wired.append(wm)

        connections: list[dict[str, Any]] = []
        for key, publishers in sorted(out_index.items()):
            subscribers = in_index.get(key, [])
            connections.append(
                {
                    "channel": key[0],
                    "type": key[1],
                    "publishers": publishers,
                    "subscribers": subscribers,
                    "wired": bool(publishers and subscribers),
                }
            )

        return BuiltGraph(bus=bus, modules=wired, connections=connections)


@dataclass
class BuiltGraph:
    bus: StreamBus
    modules: list[WiredModule]
    connections: list[dict[str, Any]]

    def module(self, name: str) -> Optional[WiredModule]:
        for m in self.modules:
            if m.spec.name == name:
                return m
        return None


def autoconnect(*modules: ModuleSpec, remaps: Optional[dict] = None) -> Blueprint:
    """Compose modules; connect streams by (name, type)."""
    bp = Blueprint(modules=list(modules))
    if remaps:
        bp.remaps.update(remaps)
    return bp


def hardware_body_blueprint() -> ModuleSpec:
    return ModuleSpec(
        name="alice_hardware_body",
        ports=[
            PortSpec("battery", "PowerState", "out"),
            PortSpec("thermal", "ThermalState", "out"),
        ],
        meta={"maturity": "green"},
    )


def camera_eye_blueprint() -> ModuleSpec:
    return ModuleSpec(
        name="camera_eye",
        ports=[PortSpec("camera", "Image", "out")],
        meta={"maturity": "yellow"},
    )


def motor_cortex_blueprint() -> ModuleSpec:
    return ModuleSpec(
        name="motor_cortex",
        ports=[
            PortSpec("cmd_vel", "Twist", "out"),
            PortSpec("camera", "Image", "in"),
            PortSpec("battery", "PowerState", "in"),
        ],
        meta={"maturity": "yellow"},
    )


def mcp_server_blueprint() -> ModuleSpec:
    return ModuleSpec(
        name="mcp_server",
        ports=[
            PortSpec("camera", "Image", "in"),
            PortSpec("cmd_vel", "Twist", "in"),
            PortSpec("battery", "PowerState", "in"),
        ],
        meta={"maturity": "green"},
    )
