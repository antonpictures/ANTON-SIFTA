#!/usr/bin/env python3
"""sifta.core.stream — typed In/Out channels over a stigmergic stream field (DB1).

Alongside jsonl receipts, not instead of them:
  sensors publish Out[T] → shared field → effectors subscribe In[T]
  every *effect* still writes a receipt after acting.

No central conductor: publishers deposit typed pheromones; subscribers
pull/filter by (name, type). Pure stdlib + typing.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class StreamMessage(Generic[T]):
    """One typed deposit into the stream field."""

    name: str
    type_name: str
    payload: T
    ts: float = field(default_factory=time.time)
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


def typed_channel(name: str, type_name: str) -> tuple[str, str]:
    return (str(name), str(type_name))


class Out(Generic[T]):
    """Publisher end of a named typed channel."""

    def __init__(self, name: str, type_name: str, bus: Optional["StreamBus"] = None):
        self.name = name
        self.type_name = type_name
        self._bus = bus

    def bind(self, bus: "StreamBus") -> "Out[T]":
        self._bus = bus
        return self

    def publish(self, payload: T, *, source: str = "", meta: Optional[dict] = None) -> StreamMessage[T]:
        if self._bus is None:
            raise RuntimeError(f"Out[{self.name}] not bound to a StreamBus")
        return self._bus.publish(self.name, self.type_name, payload, source=source, meta=meta or {})


class In(Generic[T]):
    """Subscriber end of a named typed channel."""

    def __init__(self, name: str, type_name: str, bus: Optional["StreamBus"] = None):
        self.name = name
        self.type_name = type_name
        self._bus = bus
        self._handlers: list[Callable[[StreamMessage[T]], None]] = []

    def bind(self, bus: "StreamBus") -> "In[T]":
        self._bus = bus
        bus.subscribe(self.name, self.type_name, self._dispatch)
        return self

    def subscribe(self, handler: Callable[[StreamMessage[T]], None]) -> None:
        self._handlers.append(handler)

    def _dispatch(self, msg: StreamMessage[Any]) -> None:
        for h in list(self._handlers):
            try:
                h(msg)  # type: ignore[arg-type]
            except Exception:
                pass

    def latest(self) -> Optional[StreamMessage[T]]:
        if self._bus is None:
            return None
        return self._bus.latest(self.name, self.type_name)  # type: ignore[return-value]


class StreamBus:
    """Shared typed-pheromone field. Not a master orchestrator — a deposit tray."""

    def __init__(self, *, max_history: int = 256):
        self._subs: dict[tuple[str, str], list[Callable[[StreamMessage[Any]], None]]] = {}
        self._latest: dict[tuple[str, str], StreamMessage[Any]] = {}
        self._history: list[StreamMessage[Any]] = []
        self._max_history = max_history
        self._spies: list[Callable[[StreamMessage[Any]], None]] = []

    def publish(
        self,
        name: str,
        type_name: str,
        payload: Any,
        *,
        source: str = "",
        meta: Optional[dict] = None,
    ) -> StreamMessage[Any]:
        msg = StreamMessage(
            name=str(name),
            type_name=str(type_name),
            payload=payload,
            source=source,
            meta=dict(meta or {}),
        )
        key = (msg.name, msg.type_name)
        self._latest[key] = msg
        self._history.append(msg)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]
        for spy in list(self._spies):
            try:
                spy(msg)
            except Exception:
                pass
        for h in list(self._subs.get(key, [])):
            try:
                h(msg)
            except Exception:
                pass
        return msg

    def subscribe(
        self,
        name: str,
        type_name: str,
        handler: Callable[[StreamMessage[Any]], None],
    ) -> None:
        key = (str(name), str(type_name))
        self._subs.setdefault(key, []).append(handler)

    def latest(self, name: str, type_name: str) -> Optional[StreamMessage[Any]]:
        return self._latest.get((str(name), str(type_name)))

    def history(self, *, name: Optional[str] = None, type_name: Optional[str] = None) -> list[StreamMessage[Any]]:
        rows = self._history
        if name is not None:
            rows = [m for m in rows if m.name == name]
        if type_name is not None:
            rows = [m for m in rows if m.type_name == type_name]
        return list(rows)

    def add_spy(self, handler: Callable[[StreamMessage[Any]], None]) -> None:
        self._spies.append(handler)

    def channel_keys(self) -> list[tuple[str, str]]:
        keys = set(self._subs.keys()) | set(self._latest.keys())
        return sorted(keys)


# ── Common payload type names (string tags; not heavy dataclasses required) ──

TYPE_IMAGE = "Image"
TYPE_TWIST = "Twist"
TYPE_POWER = "PowerState"
TYPE_AUDIO = "AudioFrame"
TYPE_RECEIPT = "Receipt"


def wrap_hardware_body_power(bus: StreamBus, power_payload: dict[str, Any], *, source: str = "alice_hardware_body") -> StreamMessage:
    """DB1 smallest cut: publish battery/power as Out[PowerState]."""
    return bus.publish("battery", TYPE_POWER, power_payload, source=source)


def wrap_camera_frame(bus: StreamBus, image_payload: Any, *, source: str = "camera_eye") -> StreamMessage:
    return bus.publish("camera", TYPE_IMAGE, image_payload, source=source)


def wrap_cmd_vel(bus: StreamBus, twist: dict[str, float], *, source: str = "motor_cortex") -> StreamMessage:
    return bus.publish("cmd_vel", TYPE_TWIST, twist, source=source)
