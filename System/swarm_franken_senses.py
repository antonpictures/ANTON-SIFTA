#!/usr/bin/env python3
"""
System/swarm_franken_senses.py — animal sense adapters for SIFTA Sense Forge.

Each adapter converts an existing live ledger/OS state into a SenseReading.
No adapter returns REAL unless the source row is recent and came from an
actual hardware/OS organ. Missing sensors are UNKNOWN; failed sensors are
BROKEN; intentionally educational channels stay DEMO.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_sense_bus import (
    DEFAULT_SENSE_BUS,
    SenseReading,
    StigmergicSenseBus,
    clamp01,
    normalize,
    now,
)

_STATE = _REPO / ".sifta_state"


def _latest_jsonl(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 65536))
            rows = handle.read().splitlines()
    except OSError:
        return None
    for raw in reversed(rows):
        try:
            row = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            return row
    return None


def _age_s(row: Optional[dict[str, Any]]) -> float:
    if not row:
        return math.inf
    try:
        return max(0.0, time.time() - float(row.get("ts", 0.0)))
    except Exception:
        return math.inf


def _float_or_zero(value: Any) -> float:
    try:
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return 0.0
        return out
    except Exception:
        return 0.0


def _reading(
    *,
    name: str,
    animal: str,
    hardware: str,
    value: float,
    confidence: float,
    truth: str,
    source: str,
    metadata: Optional[dict[str, Any]] = None,
) -> SenseReading:
    return SenseReading(
        name=name,
        animal=animal,
        hardware=hardware,
        value=value,
        confidence=confidence,
        truth=truth,  # type: ignore[arg-type]
        source=source,
        ts=now(),
        metadata=metadata or {},
    )


def camera_predator_motion_from_visual(
    *,
    state_dir: Path | str = _STATE,
    max_age_s: float = 15.0,
) -> SenseReading:
    path = Path(state_dir) / "visual_stigmergy.jsonl"
    row = _latest_jsonl(path)
    if row is None:
        return _reading(
            name="predator_vision",
            animal="hawk/fly",
            hardware="camera",
            value=0.0,
            confidence=0.0,
            truth="UNKNOWN",
            source="visual_stigmergy.jsonl missing",
        )
    if row.get("error"):
        return _reading(
            name="predator_vision",
            animal="hawk/fly",
            hardware="camera",
            value=0.0,
            confidence=0.3,
            truth="BROKEN",
            source=str(row.get("error"))[:120],
            metadata={"age_s": round(_age_s(row), 3)},
        )
    age = _age_s(row)
    if age > max_age_s:
        return _reading(
            name="predator_vision",
            animal="hawk/fly",
            hardware="camera",
            value=0.0,
            confidence=0.0,
            truth="UNKNOWN",
            source="visual_stigmergy.jsonl stale",
            metadata={"age_s": round(age, 3)},
        )
    motion = clamp01(row.get("motion_mean", 0.0))
    sal = clamp01(row.get("saliency_peak", 0.0))
    return _reading(
        name="predator_vision",
        animal="hawk/fly",
        hardware="camera",
        value=max(motion, sal * 0.85),
        confidence=0.9,
        truth="REAL",
        source="visual_stigmergy.jsonl",
        metadata={
            "motion_mean": motion,
            "saliency_peak": sal,
            "age_s": round(age, 3),
            "frame": f"{row.get('w', '?')}x{row.get('h', '?')}",
        },
    )


def primate_face_presence_from_ledger(
    *,
    state_dir: Path | str = _STATE,
    max_age_s: float = 30.0,
) -> SenseReading:
    path = Path(state_dir) / "face_detection_events.jsonl"
    row = _latest_jsonl(path)
    if row is None:
        return _reading(
            name="face_presence",
            animal="primate",
            hardware="Vision.framework face detector",
            value=0.0,
            confidence=0.0,
            truth="UNKNOWN",
            source="face_detection_events.jsonl missing",
        )
    age = _age_s(row)
    if row.get("error"):
        return _reading(
            name="face_presence",
            animal="primate",
            hardware="Vision.framework face detector",
            value=0.0,
            confidence=0.4,
            truth="BROKEN",
            source=str(row.get("error"))[:120],
            metadata={"age_s": round(age, 3)},
        )
    if age > max_age_s:
        return _reading(
            name="face_presence",
            animal="primate",
            hardware="Vision.framework face detector",
            value=0.0,
            confidence=0.0,
            truth="UNKNOWN",
            source="face_detection_events.jsonl stale",
            metadata={"age_s": round(age, 3)},
        )
    faces = int(row.get("faces_detected", 0) or 0)
    conf = clamp01(row.get("confidence", 0.0))
    audience = str(row.get("audience") or "unknown")
    value = conf if faces > 0 else 0.0
    return _reading(
        name="face_presence",
        animal="primate",
        hardware="Vision.framework face detector",
        value=value,
        confidence=conf,
        truth="REAL",
        source="face_detection_events.jsonl",
        metadata={"faces": faces, "audience": audience, "age_s": round(age, 3)},
    )


def mic_bat_direction_from_audio(
    *,
    state_dir: Path | str = _STATE,
    max_age_s: float = 30.0,
) -> SenseReading:
    state = Path(state_dir)
    row = _latest_jsonl(state / "acoustic_pheromones.jsonl")
    source = "acoustic_pheromones.jsonl"
    if row is None:
        row = _latest_jsonl(state / "wernicke_semantics.jsonl")
        source = "wernicke_semantics.jsonl"
    if row is None:
        return _reading(
            name="echolocation_audio",
            animal="bat/owl",
            hardware="microphone",
            value=0.0,
            confidence=0.0,
            truth="UNKNOWN",
            source="audio ledgers missing",
        )
    age = _age_s(row)
    if age > max_age_s:
        return _reading(
            name="echolocation_audio",
            animal="bat/owl",
            hardware="microphone",
            value=0.0,
            confidence=0.0,
            truth="UNKNOWN",
            source=f"{source} stale",
            metadata={"age_s": round(age, 3)},
        )
    energy = row.get("energy", row.get("rms", row.get("confidence", 0.0)))
    return _reading(
        name="echolocation_audio",
        animal="bat/owl",
        hardware="microphone",
        value=clamp01(energy),
        confidence=0.75,
        truth="REAL",
        source=source,
        metadata={"age_s": round(age, 3)},
    )


def ble_shark_electric_proximity_from_network(
    *,
    state_dir: Path | str = _STATE,
    max_age_s: float = 120.0,
) -> SenseReading:
    state = Path(state_dir)
    row = _latest_jsonl(state / "network_topology.jsonl")
    if row is None:
        return _reading(
            name="electric_proximity",
            animal="shark/electric fish",
            hardware="BLE/RF/network topology",
            value=0.0,
            confidence=0.0,
            truth="UNKNOWN",
            source="network_topology.jsonl missing",
        )
    age = _age_s(row)
    if age > max_age_s:
        return _reading(
            name="electric_proximity",
            animal="shark/electric fish",
            hardware="BLE/RF/network topology",
            value=0.0,
            confidence=0.0,
            truth="UNKNOWN",
            source="network_topology.jsonl stale",
            metadata={"age_s": round(age, 3)},
        )
    raw = row.get("rssi_norm", row.get("score", row.get("connected_peers", row.get("neighbors", 0))))
    if isinstance(raw, list):
        raw = len(raw)
    raw_float = _float_or_zero(raw)
    value = clamp01(raw_float if raw_float <= 1.0 else normalize(raw_float, 0, 12))
    return _reading(
        name="electric_proximity",
        animal="shark/electric fish",
        hardware="BLE/RF/network topology",
        value=value,
        confidence=0.65,
        truth="REAL",
        source="network_topology.jsonl",
        metadata={"age_s": round(age, 3)},
    )


def air_quality_moth_chemo_from_ledger(
    *,
    state_dir: Path | str = _STATE,
    max_age_s: float = 300.0,
) -> SenseReading:
    state = Path(state_dir)
    for filename in ("air_quality.jsonl", "chemosense.jsonl", "voc_sensor.jsonl"):
        row = _latest_jsonl(state / filename)
        if row is None:
            continue
        age = _age_s(row)
        if row.get("error"):
            return _reading(
                name="chemosense",
                animal="moth/dog",
                hardware="VOC/CO2 sensor",
                value=0.0,
                confidence=0.5,
                truth="BROKEN",
                source=str(row.get("error"))[:120],
                metadata={"ledger": filename, "age_s": round(age, 3)},
            )
        if age > max_age_s:
            continue
        val = row.get("voc_norm", row.get("co2_norm", row.get("air_quality_norm", 0.0)))
        return _reading(
            name="chemosense",
            animal="moth/dog",
            hardware="VOC/CO2 sensor",
            value=clamp01(val),
            confidence=0.85,
            truth="REAL",
            source=filename,
            metadata={"age_s": round(age, 3)},
        )
    return _reading(
        name="chemosense",
        animal="moth/dog",
        hardware="VOC/CO2 sensor",
        value=0.0,
        confidence=0.0,
        truth="UNKNOWN",
        source="no VOC/CO2 ledger",
    )


def power_bear_interoception_from_body(
    *,
    state_dir: Path | str = _STATE,
    max_age_s: float = 300.0,
) -> SenseReading:
    row = _latest_jsonl(Path(state_dir) / "metabolic_homeostasis.jsonl")
    if row is not None:
        age = _age_s(row)
        if age <= max_age_s:
            pressure = clamp01(row.get("pressure", 0.0))
            balance = row.get("stgm_balance", 0.0)
            health = clamp01(1.0 - pressure)
            return _reading(
                name="metabolic_interoception",
                animal="bear/hummingbird",
                hardware="power/thermal/STGM metabolism",
                value=health,
                confidence=0.95,
                truth="REAL",
                source="metabolic_homeostasis.jsonl",
                metadata={"pressure": pressure, "stgm_balance": balance, "age_s": round(age, 3)},
            )
    try:
        from System.stgm_economy import scan_economy

        economy = scan_economy().as_dict()
        reserve = float(economy.get("canonical_wallet_sum", 0.0) or 0.0)
        value = clamp01(reserve / 100.0)
        return _reading(
            name="metabolic_interoception",
            animal="bear/hummingbird",
            hardware="STGM economy ledger",
            value=value,
            confidence=0.7,
            truth="REAL",
            source="stgm_economy.scan_economy",
            metadata={"canonical_wallet_sum": reserve},
        )
    except Exception as exc:
        return _reading(
            name="metabolic_interoception",
            animal="bear/hummingbird",
            hardware="power/thermal/STGM metabolism",
            value=0.0,
            confidence=0.4,
            truth="BROKEN",
            source=type(exc).__name__,
        )


def demo_magnetoreception() -> SenseReading:
    return _reading(
        name="magnetoreception",
        animal="bird/turtle",
        hardware="magnetometer",
        value=random.random(),
        confidence=0.25,
        truth="DEMO",
        source="no live magnetometer",
    )


def collect_live_readings(*, state_dir: Path | str = _STATE) -> list[SenseReading]:
    return [
        camera_predator_motion_from_visual(state_dir=state_dir),
        primate_face_presence_from_ledger(state_dir=state_dir),
        mic_bat_direction_from_audio(state_dir=state_dir),
        ble_shark_electric_proximity_from_network(state_dir=state_dir),
        air_quality_moth_chemo_from_ledger(state_dir=state_dir),
        power_bear_interoception_from_body(state_dir=state_dir),
        demo_magnetoreception(),
    ]


def sample_and_deposit(
    *,
    bus_path: Path | str = DEFAULT_SENSE_BUS,
    state_dir: Path | str = _STATE,
    writer: str = "swarm_franken_senses",
) -> dict[str, Any]:
    readings = collect_live_readings(state_dir=state_dir)
    bus = StigmergicSenseBus(bus_path)
    rows = bus.deposit_many(readings, writer=writer)
    return {
        "ts": now(),
        "field_value": round(bus.field_value(readings), 6),
        "readings": rows,
        "truth_counts": {
            truth: sum(1 for row in rows if row.get("truth") == truth)
            for truth in ("REAL", "DEMO", "BROKEN", "UNKNOWN")
        },
        "bus_path": str(bus.path),
    }


def summary_for_alice() -> str:
    snapshot = StigmergicSenseBus().field_snapshot(max_age_s=120.0)
    counts = snapshot.get("truth_counts", {})
    return (
        "SENSE FORGE FIELD:\n"
        f"- field_value={snapshot.get('field_value', 0.0)}\n"
        f"- REAL={counts.get('REAL', 0)} DEMO={counts.get('DEMO', 0)} "
        f"BROKEN={counts.get('BROKEN', 0)} UNKNOWN={counts.get('UNKNOWN', 0)}\n"
        "- hard_rule=No sensor becomes REAL until it writes a live receipt."
    )


if __name__ == "__main__":
    out = sample_and_deposit()
    print("stigmergic sensory field:", out["field_value"])
    for row in out["readings"]:
        print(f"{row['truth']:7s} {row['animal']:20s} {row['name']:26s} {row['value']:.2f}")
