#!/usr/bin/env python3
"""sifta.core.spy — universal stream spy (DB6).

Watch any organ's pubs without jsonl archaeology.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sifta.core.stream import StreamBus, StreamMessage


@dataclass
class StreamSpy:
    bus: StreamBus
    max_events: int = 200
    events: list[dict[str, Any]] = field(default_factory=list)
    _armed: bool = False

    def arm(self) -> "StreamSpy":
        if not self._armed:
            self.bus.add_spy(self._on_msg)
            self._armed = True
        return self

    def _on_msg(self, msg: StreamMessage[Any]) -> None:
        self.events.append(
            {
                "ts": msg.ts,
                "msg_id": msg.msg_id,
                "name": msg.name,
                "type": msg.type_name,
                "source": msg.source,
                "payload_preview": _preview(msg.payload),
                "meta": dict(msg.meta or {}),
            }
        )
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events :]

    def filter(
        self,
        *,
        name: Optional[str] = None,
        type_name: Optional[str] = None,
        source: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        rows = self.events
        if name is not None:
            rows = [e for e in rows if e["name"] == name]
        if type_name is not None:
            rows = [e for e in rows if e["type"] == type_name]
        if source is not None:
            rows = [e for e in rows if e["source"] == source]
        return list(rows)

    def summary_lines(self, limit: int = 12) -> list[str]:
        lines = [f"STREAM SPY — {len(self.events)} events captured @ {time.time():.0f}"]
        for e in self.events[-limit:]:
            lines.append(
                f"  {e['name']}:{e['type']} src={e['source']} id={e['msg_id']} {e['payload_preview']}"
            )
        return lines


def _preview(payload: Any, n: int = 80) -> str:
    s = repr(payload)
    if len(s) > n:
        return s[: n - 1] + "…"
    return s
