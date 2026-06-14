#!/usr/bin/env python3
"""Cortex bridge pulse classifier.

This small organ summarizes whether a stalled cortex turn is down, recovering,
or waiting for a clearer execute packet, using receipts rather than vibes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class CortexBridgePulse:
    ok: bool
    status: str
    blockers: tuple[str, ...] = ()
    recoveries: tuple[str, ...] = ()

    def owner_line(self) -> str:
        if self.status == "ok_recovering":
            return "I caught the cortex fault and preserved the turn in recovery receipts."
        if self.status == "ok_needs_clarified_execute":
            return "I am up; the execute request needs the actual marker block or clearer command context."
        return "The cortex bridge is blocked until a recovery receipt or alternate arm continues the turn."


def _event_text(row: Any) -> str:
    if isinstance(row, Mapping):
        return " ".join(str(row.get(k) or "") for k in ("event", "message", "status", "note", "description"))
    return str(row or "")


def assess_cortex_bridge_pulse(events: Iterable[Any]) -> CortexBridgePulse:
    """Assess cortex bridge health from recent event/receipt-like rows."""
    blockers: list[str] = []
    recoveries: list[str] = []
    saw_timeout = False
    saw_unrecognized_execute = False

    for row in events or ():
        text = _event_text(row).casefold()
        if "timed out" in text or "no first token" in text or "cortex stalled" in text:
            saw_timeout = True
        if "execute" in text and ("not recognized" in text or "wasn't recognized" in text or "unrecognized" in text):
            saw_unrecognized_execute = True
        if "body-stabilization queue" in text or "recovery" in text or "preserved" in text:
            if isinstance(row, Mapping):
                rid = str(row.get("receipt_id") or row.get("trace_id") or "").strip()
                if rid:
                    recoveries.append(rid)

    if saw_timeout and recoveries:
        return CortexBridgePulse(ok=True, status="ok_recovering", recoveries=tuple(recoveries))
    if saw_unrecognized_execute:
        return CortexBridgePulse(ok=True, status="ok_needs_clarified_execute", blockers=("execute_unrecognized",))
    if saw_timeout:
        blockers.append("cortex_timeout")
    return CortexBridgePulse(ok=not blockers, status="blocked" if blockers else "ok", blockers=tuple(blockers))


__all__ = ["CortexBridgePulse", "assess_cortex_bridge_pulse"]
