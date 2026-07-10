#!/usr/bin/env python3
"""sifta.core.replay — fixture replay / simulation first (DB3).

§6 honesty as product feature:
  1) fixture replay of recorded sensor→action traces
  2) virtual-limb simulation
  3) only then real hardware

Any stigmerobotics claim must pass assert_sim_before_real(...) or it is labeled HYPOTHESIS.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from sifta.core.stream import StreamBus, StreamMessage


class EmbodimentMode(str, Enum):
    REPLAY = "replay"
    SIMULATION = "simulation"
    REAL = "real"


@dataclass
class ReplayTrace:
    """One recorded sensor→action step."""

    step: int
    sensor: dict[str, Any]
    action: dict[str, Any]
    ts: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayMode:
    """Play recorded fixture traces onto a StreamBus."""

    traces: list[ReplayTrace]
    mode: EmbodimentMode = EmbodimentMode.REPLAY

    @classmethod
    def from_jsonl(cls, path: Path | str) -> "ReplayMode":
        rows: list[ReplayTrace] = []
        p = Path(path)
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines()):
            if not line.strip():
                continue
            raw = json.loads(line)
            rows.append(
                ReplayTrace(
                    step=int(raw.get("step", i)),
                    sensor=dict(raw.get("sensor") or {}),
                    action=dict(raw.get("action") or {}),
                    ts=float(raw.get("ts") or 0.0),
                    meta=dict(raw.get("meta") or {}),
                )
            )
        return cls(traces=rows)

    def iter_steps(self) -> Iterator[ReplayTrace]:
        yield from self.traces

    def play(self, bus: StreamBus, *, source: str = "replay") -> list[StreamMessage]:
        published: list[StreamMessage] = []
        for tr in self.traces:
            if tr.sensor:
                published.append(
                    bus.publish("camera", "Image", tr.sensor, source=source, meta={"step": tr.step, "lane": "sensor"})
                )
            if tr.action:
                published.append(
                    bus.publish("cmd_vel", "Twist", tr.action, source=source, meta={"step": tr.step, "lane": "action"})
                )
        return published


@dataclass
class SimulationMode:
    """Virtual limb / policy loop — never claims real motion."""

    steps: int = 8
    mode: EmbodimentMode = EmbodimentMode.SIMULATION

    def run_camera_to_effector(
        self,
        bus: StreamBus,
        *,
        policy: Optional[Callable[[Any], dict[str, float]]] = None,
        write_receipt: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> list[dict[str, Any]]:
        """camera → policy → cmd_vel with optional receipt after each effect."""
        if policy is None:
            def policy(frame: Any) -> dict[str, float]:
                # trivial sim: hold still unless frame carries a cue
                if isinstance(frame, dict) and frame.get("obstacle_ahead"):
                    return {"linear": 0.0, "angular": 0.4}
                return {"linear": 0.1, "angular": 0.0}

        receipts: list[dict[str, Any]] = []
        for i in range(int(self.steps)):
            frame = {"step": i, "obstacle_ahead": (i % 3 == 2), "sim": True}
            bus.publish("camera", "Image", frame, source="simulation")
            twist = policy(frame)
            bus.publish("cmd_vel", "Twist", twist, source="simulation")
            rec = {
                "truth_label": "SIMULATION_EFFECT_RECEIPT_V1",
                "receipt_id": uuid.uuid4().hex[:12],
                "ts": time.time(),
                "mode": self.mode.value,
                "step": i,
                "sensor": frame,
                "action": twist,
                "claim": "SIMULATED_NOT_REAL_HARDWARE",
            }
            receipts.append(rec)
            if write_receipt:
                write_receipt(rec)
        return receipts


def assert_sim_before_real(
    *,
    claimed_mode: str,
    replay_ok: bool = False,
    simulation_ok: bool = False,
    real_hardware_receipt: bool = False,
) -> dict[str, Any]:
    """
    Gate for stigmerobotics claims.
    REAL motion requires a real hardware receipt AND prior sim/replay green.
    """
    mode = str(claimed_mode or "").lower().strip()
    if mode in {"replay", EmbodimentMode.REPLAY.value}:
        ok = bool(replay_ok)
        return {"allowed": ok, "mode": "replay", "label": "OPERATIONAL" if ok else "HYPOTHESIS"}
    if mode in {"sim", "simulation", EmbodimentMode.SIMULATION.value}:
        ok = bool(simulation_ok or replay_ok)
        return {"allowed": ok, "mode": "simulation", "label": "OPERATIONAL" if ok else "HYPOTHESIS"}
    if mode in {"real", "hardware", EmbodimentMode.REAL.value}:
        ok = bool(real_hardware_receipt and (simulation_ok or replay_ok))
        return {
            "allowed": ok,
            "mode": "real",
            "label": "OPERATIONAL" if ok else "HYPOTHESIS",
            "reason": None if ok else "real_requires_prior_sim_or_replay_and_hardware_receipt",
        }
    return {"allowed": False, "mode": mode, "label": "HYPOTHESIS", "reason": "unknown_mode"}


def write_fixture(path: Path | str, traces: list[dict[str, Any]]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for i, tr in enumerate(traces):
            row = {"step": i, **tr}
            f.write(json.dumps(row) + "\n")
    return p
