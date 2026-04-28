#!/usr/bin/env python3
"""
System/swarm_sense_bus.py — one truth-labeled substrate for animal senses.

Research spine:
  Choi et al. 2023, "Multisensory integration in the mammalian brain:
  diversity and flexibility in health and disease", PMCID: PMC10404930,
  DOI: 10.1098/rstb.2022.0338.

SIFTA contract:
  animal sense -> hardware organ -> stigmergic field -> truth receipt

REAL means a live hardware / OS / ledger source produced the reading.
DEMO means synthetic or educational.
UNKNOWN means no live source exists.
BROKEN means a source exists but failed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Iterable, Literal, Mapping, Optional

Truth = Literal["REAL", "DEMO", "BROKEN", "UNKNOWN"]
TRUTH_VALUES = {"REAL", "DEMO", "BROKEN", "UNKNOWN"}

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
DEFAULT_SENSE_BUS = _STATE / "sense_bus.jsonl"
SCHEMA = "SIFTA_SENSE_READING_V1"


def now() -> float:
    return time.time()


def normalize(x: float, lo: float, hi: float) -> float:
    if hi == lo:
        return 0.0
    try:
        val = (float(x) - float(lo)) / (float(hi) - float(lo))
    except Exception:
        return 0.0
    return max(0.0, min(1.0, val))


def clamp01(x: Any) -> float:
    try:
        val = float(x)
        if math.isnan(val) or math.isinf(val):
            return 0.0
        return max(0.0, min(1.0, val))
    except Exception:
        return 0.0


@dataclass(frozen=True)
class SenseReading:
    name: str
    animal: str
    hardware: str
    value: float
    confidence: float
    truth: Truth
    source: str
    ts: float = field(default_factory=now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.truth not in TRUTH_VALUES:
            raise ValueError(f"invalid truth label: {self.truth}")
        object.__setattr__(self, "value", clamp01(self.value))
        object.__setattr__(self, "confidence", clamp01(self.confidence))
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "animal", str(self.animal))
        object.__setattr__(self, "hardware", str(self.hardware))
        object.__setattr__(self, "source", str(self.source))

    def as_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["schema"] = SCHEMA
        return row

    @property
    def contribution(self) -> float:
        return StigmergicSenseBus.weighted_value(self)


class StigmergicSenseBus:
    """Append-only bus for animal-inspired sensory readings."""

    TRUTH_WEIGHTS: Mapping[str, float] = {
        "REAL": 1.0,
        "DEMO": 0.25,
        "UNKNOWN": 0.0,
        "BROKEN": -1.0,
    }

    def __init__(self, path: str | Path = DEFAULT_SENSE_BUS):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def weighted_value(cls, reading: SenseReading) -> float:
        return float(
            cls.TRUTH_WEIGHTS[str(reading.truth)]
            * reading.confidence
            * reading.value
        )

    def deposit(self, reading: SenseReading, *, writer: str = "unknown") -> dict[str, Any]:
        row = reading.as_dict()
        row["writer"] = str(writer)
        row["contribution"] = round(self.weighted_value(reading), 6)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        return row

    def deposit_many(
        self,
        readings: Iterable[SenseReading],
        *,
        writer: str = "unknown",
    ) -> list[dict[str, Any]]:
        return [self.deposit(reading, writer=writer) for reading in readings]

    def field_value(self, readings: Iterable[SenseReading]) -> float:
        return float(sum(self.weighted_value(reading) for reading in readings))

    def read_recent(self, *, limit: int = 60, max_age_s: Optional[float] = None) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        try:
            with self.path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                handle.seek(max(0, size - 262144))
                raw_rows = handle.read().splitlines()[-limit:]
        except OSError:
            return []
        current = now()
        for raw in raw_rows:
            try:
                row = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            if max_age_s is not None:
                try:
                    if current - float(row.get("ts", 0.0)) > max_age_s:
                        continue
                except Exception:
                    continue
            rows.append(row)
        return rows

    def latest_by_name(self, *, max_age_s: Optional[float] = None) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for row in self.read_recent(limit=240, max_age_s=max_age_s):
            name = str(row.get("name") or "")
            if not name:
                continue
            if name not in out or float(row.get("ts", 0.0) or 0.0) >= float(out[name].get("ts", 0.0) or 0.0):
                out[name] = row
        return out

    def field_snapshot(self, *, max_age_s: float = 120.0) -> dict[str, Any]:
        latest = self.latest_by_name(max_age_s=max_age_s)
        rows = list(latest.values())
        field = 0.0
        truth_counts = {truth: 0 for truth in sorted(TRUTH_VALUES)}
        for row in rows:
            truth = str(row.get("truth") or "UNKNOWN")
            if truth in truth_counts:
                truth_counts[truth] += 1
            try:
                field += float(row.get("contribution", 0.0))
            except Exception:
                pass
        return {
            "schema": "SIFTA_SENSE_FIELD_V1",
            "ts": now(),
            "field_value": round(field, 6),
            "readings": rows,
            "truth_counts": truth_counts,
            "source": str(self.path),
        }


def proof_of_property() -> dict[str, bool]:
    real = SenseReading("a", "hawk", "camera", 0.8, 0.5, "REAL", "test")
    demo = SenseReading("b", "bird", "magnetometer", 1.0, 1.0, "DEMO", "test")
    unknown = SenseReading("c", "moth", "VOC", 1.0, 1.0, "UNKNOWN", "test")
    broken = SenseReading("d", "bat", "mic", 0.2, 0.5, "BROKEN", "test")
    bus = StigmergicSenseBus(path=_STATE / "_sense_bus_proof.jsonl")
    val = bus.field_value([real, demo, unknown, broken])
    return {
        "real_positive": real.contribution == 0.4,
        "demo_discounted": demo.contribution == 0.25,
        "unknown_zero": unknown.contribution == 0.0,
        "broken_negative": broken.contribution == -0.1,
        "field_sum": abs(val - 0.55) < 1e-9,
    }


__all__ = [
    "DEFAULT_SENSE_BUS",
    "SCHEMA",
    "SenseReading",
    "StigmergicSenseBus",
    "Truth",
    "clamp01",
    "normalize",
    "now",
    "proof_of_property",
]
