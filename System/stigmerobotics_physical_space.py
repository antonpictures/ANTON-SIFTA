#!/usr/bin/env python3
"""
System/stigmerobotics_physical_space.py
=======================================

Shared physical-space contract for E35/E45/E46.

Ledger rows are timestamps and trace semantics. Real desk grounding needs a
second layer that normalizes camera, microphone, and desk telemetry rows into
bounded observations of physical bodies moving through space. This module is
side-effect free: callers pass rows in, receive a report out, and no live sensor
or ledger is read here.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


SPATIAL_SENSOR_KINDS: frozenset[str] = frozenset(
    {
        "camera_depth_map",
        "microphone_spatial_array",
        "mic_spatial_array",  # ledger alias → normalized to microphone_spatial_array
        "desk_telemetry_radar",
        "system_thermal",
        "unified_field_segment",
    }
)

SPATIAL_SENSOR_ALIASES: dict[str, str] = {
    "visual_stigmergy": "camera_depth_map",
    "OWNER_BODY_VISUAL_EVIDENCE_V1": "camera_depth_map",
    "camera_lock": "camera_depth_map",
    "SIMULATED_SPATIAL_HEARING": "microphone_spatial_array",
    "owl_spatial_hearing": "microphone_spatial_array",
    "audio_ingress": "microphone_spatial_array",
    "mic_spatial_array": "microphone_spatial_array",
    "electric_proximity": "desk_telemetry_radar",
    "ble_radar": "desk_telemetry_radar",
    "FACE_DETECTION": "camera_depth_map",
    "SYSTEM_THERMAL_V1": "system_thermal",
    "UNIFIED_FIELD_SEGMENT_V1": "unified_field_segment",
    "UNIFIED_STIGMERGIC_FIELD_V1": "unified_field_segment",
}

POSITION_X_KEYS = ("x_m", "physical_x", "pose_x", "camera_x", "desk_x_m", "centroid_x_m")
POSITION_Y_KEYS = ("y_m", "physical_y", "pose_y", "camera_y", "desk_y_m", "centroid_y_m")
POSITION_Z_KEYS = ("z_m", "physical_z", "pose_z", "camera_z", "desk_z_m")
DISTANCE_KEYS = (
    "distance_m",
    "depth_m",
    "range_m",
    "proximity_m",
    "proximity_meters",
    "proximity",
)
AZIMUTH_KEYS = ("azimuth_rad", "bearing_rad", "angle_rad")
ELEVATION_KEYS = ("elevation_rad", "pitch_rad")
VELOCITY_X_KEYS = ("vx_m_s", "velocity_x_m_s", "velocity_x", "vx")
VELOCITY_Y_KEYS = ("vy_m_s", "velocity_y_m_s", "velocity_y", "vy")
VELOCITY_Z_KEYS = ("vz_m_s", "velocity_z_m_s", "velocity_z", "vz")
CONFIDENCE_KEYS = (
    "confidence",
    "pose_confidence",
    "spatial_confidence",
    "sensor_confidence",
    "observation_confidence",
)
THERMAL_LOAD_KEYS = (
    "thermal_load",
    "heat_load",
    "silicon_thermal_load",
)
THERMAL_WARNING_LEVEL_KEYS = ("thermal_warning_level", "performance_warning_level")
CPU_TEMP_KEYS = ("cpu_temp_c", "cpu_temperature_c", "package_temperature_c")
GPU_TEMP_KEYS = ("gpu_temp_c", "gpu_temperature_c")
FAN_RPM_KEYS = ("fan_rpm", "fans_rpm")
POWER_DRAW_KEYS = ("package_wattage_w", "power_draw_w", "cpu_power_w")
LID_CLOSED_KEYS = ("lid_closed", "clamshell_closed")
UNIFIED_TS_KEYS = ("unified_field_ts", "field_ts", "segment_ts")
UNIFIED_SEGMENT_KEYS = (
    "location_segment",
    "unified_field_segment",
    "field_segment",
    "stigtime_segment",
    "owner_activity",
)
BODY_ID_KEYS = (
    "body_id",
    "track_id",
    "person_id",
    "speaker_id",
    "owner_id",
    "human_id",
    "subject",
    "audience",
)
NESTED_KEYS = ("payload", "meta", "evidence", "pose", "position", "spatial", "body", "telemetry")


@dataclass(frozen=True)
class PhysicalBodyObservation:
    """One bounded observation of a body in desk-centric physical space."""

    row_index: int
    ts: float
    kind: str
    trace_id: str
    source_ide: str
    homeworld_serial: str
    sensor_kind: str
    body_id: str
    x_m: float | None = None
    y_m: float | None = None
    z_m: float | None = None
    distance_m: float | None = None
    azimuth_rad: float | None = None
    elevation_rad: float | None = None
    vx_m_s: float | None = None
    vy_m_s: float | None = None
    vz_m_s: float | None = None
    confidence: float = 0.5
    thermal_load: float | None = None
    cpu_temp_c: float | None = None
    gpu_temp_c: float | None = None
    unified_segment_label: str | None = None

    @property
    def has_cartesian_position(self) -> bool:
        return self.x_m is not None or self.y_m is not None or self.z_m is not None

    @property
    def has_range_position(self) -> bool:
        return self.distance_m is not None or self.azimuth_rad is not None

    @property
    def has_thermal_signal(self) -> bool:
        return self.thermal_load is not None or self.cpu_temp_c is not None or self.gpu_temp_c is not None

    @property
    def has_unified_segment(self) -> bool:
        return bool(self.unified_segment_label)

    @property
    def grounded(self) -> bool:
        return (
            self.has_cartesian_position
            or self.has_range_position
            or self.has_thermal_signal
            or self.has_unified_segment
        )

    @property
    def best_distance_m(self) -> float | None:
        if self.distance_m is not None:
            return self.distance_m
        if not self.has_cartesian_position:
            return None
        x = self.x_m or 0.0
        y = self.y_m or 0.0
        z = self.z_m or 0.0
        return math.sqrt((x * x) + (y * y) + (z * z))

    @property
    def position_tuple(self) -> tuple[float, float, float] | None:
        if not self.has_cartesian_position:
            return None
        return (self.x_m or 0.0, self.y_m or 0.0, self.z_m or 0.0)


@dataclass(frozen=True)
class PhysicalSpaceReport:
    """Desk-space summary derived from physical body observations."""

    observations: tuple[PhysicalBodyObservation, ...]
    near_distance_m: float
    collision_distance_m: float
    pressure: float
    nearest_body_distance_m: float | None = None
    nearest_pair_distance_m: float | None = None
    violations: tuple[str, ...] = field(default_factory=tuple)
    # E35+ physical spacetime contract (Populated from fused sensor rows; None = unknown.)
    physical_presence: bool = False
    physical_proximity: float | None = None
    thermal_load: float | None = None
    last_physical_event_ts: float | None = None
    unified_field_ts: float | None = None
    unified_field_location_segment: str | None = None
    lid_closed: bool | None = None

    @property
    def grounded(self) -> bool:
        return bool(self.observations)

    @property
    def sensor_kinds(self) -> tuple[str, ...]:
        return tuple(sorted({obs.sensor_kind for obs in self.observations}))

    @property
    def body_ids(self) -> tuple[str, ...]:
        return tuple(sorted({obs.body_id for obs in self.observations}))

    @property
    def body_count(self) -> int:
        return len(self.body_ids)

    @property
    def proof_of_property(self) -> dict[str, Any]:
        return {
            "physical_space": "camera/mic/desk/thermal/unified-field telemetry normalized to body observations",
            "grounded": self.grounded,
            "observation_count": len(self.observations),
            "sensor_kinds": list(self.sensor_kinds),
            "body_count": self.body_count,
            "nearest_body_distance_m": self.nearest_body_distance_m,
            "nearest_pair_distance_m": self.nearest_pair_distance_m,
            "pressure": self.pressure,
            "violations": list(self.violations),
            "physical_presence": self.physical_presence,
            "physical_proximity": self.physical_proximity,
            "thermal_load": self.thermal_load,
            "last_physical_event_ts": self.last_physical_event_ts,
            "unified_field_ts": self.unified_field_ts,
            "unified_field_location_segment": self.unified_field_location_segment,
            "lid_closed": self.lid_closed,
            "truth_label": "OPERATIONAL" if not self.violations else "BROKEN",
        }

    @property
    def presence_gates_ok(self) -> bool:
        """True when carbon-relevant or unified-field anchors exist (not thermal-only)."""
        return self.physical_presence or self.unified_field_ts is not None


def _payload_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _contexts(row: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    contexts: list[Mapping[str, Any]] = [row]
    for key in NESTED_KEYS:
        value = row.get(key)
        nested = _payload_dict(value)
        if nested:
            contexts.append(nested)
    for key in ("payload", "meta", "evidence"):
        outer = _payload_dict(row.get(key))
        for nested_key in ("pose", "position", "spatial", "body", "telemetry"):
            nested = _payload_dict(outer.get(nested_key)) if outer else {}
            if nested:
                contexts.append(nested)
    return tuple(contexts)


def _first_value(row: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for ctx in _contexts(row):
        for key in keys:
            value = ctx.get(key)
            if value not in (None, ""):
                return value
    return None


def _float_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _row_kind(row: Mapping[str, Any]) -> str:
    for key in ("kind", "event", "event_type", "name", "truth_label"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return "unknown"


def sensor_kind_for_row(row: Mapping[str, Any]) -> str | None:
    """Return canonical sensor kind for rows that carry physical space data."""

    candidates = [
        row.get("kind"),
        row.get("event"),
        row.get("event_type"),
        row.get("name"),
        row.get("truth_label"),
    ]
    payload = _payload_dict(row.get("payload"))
    evidence = _payload_dict(row.get("evidence"))
    candidates.extend(
        [
            payload.get("kind"),
            payload.get("truth_label"),
            evidence.get("kind"),
            evidence.get("truth_label"),
        ]
    )
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate:
            continue
        if candidate in SPATIAL_SENSOR_KINDS:
            return str(SPATIAL_SENSOR_ALIASES.get(candidate, candidate))
        alias = SPATIAL_SENSOR_ALIASES.get(candidate)
        if alias:
            return alias
    if _first_value(row, POSITION_X_KEYS + POSITION_Y_KEYS + POSITION_Z_KEYS + DISTANCE_KEYS + AZIMUTH_KEYS) is not None:
        return "desk_telemetry_radar"
    if _first_value(row, THERMAL_LOAD_KEYS + CPU_TEMP_KEYS + GPU_TEMP_KEYS + THERMAL_WARNING_LEVEL_KEYS) is not None:
        return "system_thermal"
    if _first_value(row, UNIFIED_SEGMENT_KEYS + UNIFIED_TS_KEYS) is not None:
        return "unified_field_segment"
    return None


def parse_physical_observation(
    row: Mapping[str, Any],
    *,
    row_index: int = 0,
) -> PhysicalBodyObservation | None:
    """Normalize a ledger row into a physical body observation when possible."""

    sensor_kind = sensor_kind_for_row(row)
    if sensor_kind is None:
        return None

    ts = _float_or_none(row.get("ts"))
    if ts is None:
        ts = _float_or_none(row.get("ts_captured"))
    if ts is None:
        return None

    x_m = _float_or_none(_first_value(row, POSITION_X_KEYS))
    y_m = _float_or_none(_first_value(row, POSITION_Y_KEYS))
    z_m = _float_or_none(_first_value(row, POSITION_Z_KEYS))
    distance_m = _float_or_none(_first_value(row, DISTANCE_KEYS))
    azimuth_rad = _float_or_none(_first_value(row, AZIMUTH_KEYS))
    elevation_rad = _float_or_none(_first_value(row, ELEVATION_KEYS))
    vx_m_s = _float_or_none(_first_value(row, VELOCITY_X_KEYS))
    vy_m_s = _float_or_none(_first_value(row, VELOCITY_Y_KEYS))
    vz_m_s = _float_or_none(_first_value(row, VELOCITY_Z_KEYS))

    if distance_m is None and x_m is not None:
        y = y_m or 0.0
        z = z_m or 0.0
        distance_m = math.sqrt((x_m * x_m) + (y * y) + (z * z))

    # Fallback to estimate depth from bounding boxes
    if distance_m is None and "bounding_boxes" in row and isinstance(row["bounding_boxes"], list):
        bboxes = row["bounding_boxes"]
        if bboxes and isinstance(bboxes[0], list) and len(bboxes[0]) >= 3:
            # bbox is [x, y, width, height] in normalized coordinates (0.0 to 1.0)
            w = _float_or_none(bboxes[0][2])
            if w and w > 0.0:
                # Estimate distance based on face width taking up w proportion of image
                # A face (~0.15m) filling 50% of a typical webcam field of view (~1m at 1m) -> ~0.3m
                # rough approximation: distance_m = 0.3 / w
                distance_m = _clamp(0.3 / w, 0.1, 10.0)

    confidence = _float_or_none(_first_value(row, CONFIDENCE_KEYS))
    confidence = 0.5 if confidence is None else _clamp(confidence, 0.0, 1.0)

    thermal_load_v: float | None = None
    cpu_temp_v = _float_or_none(_first_value(row, CPU_TEMP_KEYS))
    gpu_temp_v = _float_or_none(_first_value(row, GPU_TEMP_KEYS))
    if sensor_kind == "system_thermal":
        thermal_load_v = _float_or_none(_first_value(row, THERMAL_LOAD_KEYS))
        if thermal_load_v is not None:
            thermal_load_v = _clamp(thermal_load_v, 0.0, 1.0)
        if thermal_load_v is None:
            warning_levels = [
                value
                for value in (
                    _float_or_none(_first_value(row, ("thermal_warning_level",))),
                    _float_or_none(_first_value(row, ("performance_warning_level",))),
                )
                if value is not None
            ]
            if warning_levels:
                thermal_load_v = _clamp(max(warning_levels) / 2.0, 0.0, 1.0)
        if thermal_load_v is None and cpu_temp_v is not None:
            thermal_load_v = _clamp((cpu_temp_v - 30.0) / 70.0, 0.0, 1.0)
        if thermal_load_v is not None:
            confidence = max(confidence, 0.65)

    unified_seg: str | None = None
    if sensor_kind == "unified_field_segment":
        raw_seg = _first_value(row, UNIFIED_SEGMENT_KEYS)
        if raw_seg is not None:
            unified_seg = str(raw_seg).strip() or None
        if unified_seg:
            confidence = max(confidence, 0.55)

    kind = _row_kind(row)
    trace_id = str(row.get("trace_id") or f"{sensor_kind}_{row_index}")
    source_ide = str(row.get("source_ide") or row.get("doctor") or row.get("source") or sensor_kind)
    homeworld_serial = str(row.get("homeworld_serial") or row.get("node_serial") or "UNKNOWN")
    body_id = _first_value(row, BODY_ID_KEYS)
    if body_id is None:
        if sensor_kind == "system_thermal":
            body_id = "silicon_substrate"
        elif sensor_kind == "unified_field_segment":
            body_id = "unified_field"
        else:
            body_id = "unknown_body"

    obs = PhysicalBodyObservation(
        row_index=row_index,
        ts=ts,
        kind=kind,
        trace_id=trace_id,
        source_ide=source_ide,
        homeworld_serial=homeworld_serial,
        sensor_kind=sensor_kind,
        body_id=str(body_id),
        x_m=x_m,
        y_m=y_m,
        z_m=z_m,
        distance_m=distance_m,
        azimuth_rad=azimuth_rad,
        elevation_rad=elevation_rad,
        vx_m_s=vx_m_s,
        vy_m_s=vy_m_s,
        vz_m_s=vz_m_s,
        confidence=confidence,
        thermal_load=thermal_load_v,
        cpu_temp_c=cpu_temp_v,
        gpu_temp_c=gpu_temp_v,
        unified_segment_label=unified_seg,
    )
    return obs if obs.grounded else None


def extract_physical_observations(
    rows: Iterable[Mapping[str, Any]],
    *,
    now_ts: float | None = None,
    max_age_s: float | None = None,
) -> tuple[PhysicalBodyObservation, ...]:
    observations: list[PhysicalBodyObservation] = []
    for index, row in enumerate(rows):
        obs = parse_physical_observation(row, row_index=index)
        if obs is None:
            continue
        if max_age_s is not None and now_ts is not None:
            if now_ts - obs.ts > max_age_s:
                continue
        observations.append(obs)
    return tuple(sorted(observations, key=lambda item: (item.ts, item.row_index)))


def distance_between(a: PhysicalBodyObservation, b: PhysicalBodyObservation) -> float | None:
    apos = a.position_tuple
    bpos = b.position_tuple
    if apos is not None and bpos is not None:
        dx = apos[0] - bpos[0]
        dy = apos[1] - bpos[1]
        dz = apos[2] - bpos[2]
        return math.sqrt((dx * dx) + (dy * dy) + (dz * dz))
    if a.distance_m is not None and b.distance_m is not None:
        return abs(a.distance_m - b.distance_m)
    return None


def physical_coupling_from_distance(
    distance_m: float | None,
    *,
    confidence: float = 1.0,
    near_distance_m: float = 1.0,
) -> float:
    if distance_m is None or near_distance_m <= 0.0:
        return 0.0
    if distance_m >= near_distance_m:
        return 0.0
    return math.exp(-max(0.0, distance_m) / near_distance_m) * _clamp(confidence, 0.0, 1.0)


def physical_pressure_from_distance(
    distance_m: float | None,
    *,
    confidence: float = 1.0,
    near_distance_m: float = 1.0,
    collision_distance_m: float = 0.35,
) -> float:
    if distance_m is None or near_distance_m <= 0.0:
        return 0.0
    if distance_m >= near_distance_m:
        return 0.0
    floor = max(0.01, min(collision_distance_m, near_distance_m))
    ratio = near_distance_m / max(floor, distance_m)
    return _clamp(ratio * _clamp(confidence, 0.0, 1.0), 0.0, 4.0)


def build_physical_space_report(
    rows: Iterable[Mapping[str, Any]],
    *,
    now_ts: float | None = None,
    max_age_s: float | None = None,
    near_distance_m: float = 1.0,
    collision_distance_m: float = 0.35,
) -> PhysicalSpaceReport:
    row_list = list(rows)
    observations = extract_physical_observations(row_list, now_ts=now_ts, max_age_s=max_age_s)
    nearest_body: float | None = None
    nearest_pair: float | None = None
    pressure = 0.0

    for obs in observations:
        dist = obs.best_distance_m
        if dist is not None:
            nearest_body = dist if nearest_body is None else min(nearest_body, dist)
            pressure = max(
                pressure,
                physical_pressure_from_distance(
                    dist,
                    confidence=obs.confidence,
                    near_distance_m=near_distance_m,
                    collision_distance_m=collision_distance_m,
                ),
            )

    for i, left in enumerate(observations):
        for right in observations[i + 1:]:
            dist = distance_between(left, right)
            if dist is None:
                continue
            nearest_pair = dist if nearest_pair is None else min(nearest_pair, dist)
            pressure = max(
                pressure,
                physical_pressure_from_distance(
                    dist,
                    confidence=(left.confidence + right.confidence) / 2.0,
                    near_distance_m=near_distance_m,
                    collision_distance_m=collision_distance_m,
                ),
            )

    violations: list[str] = []
    if near_distance_m <= 0.0:
        violations.append("near_distance_m_must_be_positive")
    if collision_distance_m <= 0.0:
        violations.append("collision_distance_m_must_be_positive")

    # --- E35+ fused spacetime scalars (best-effort from the same row window) ---
    last_ev_ts: float | None = None
    for obs in observations:
        last_ev_ts = obs.ts if last_ev_ts is None else max(last_ev_ts, obs.ts)

    thermal_vals = [o.thermal_load for o in observations if o.thermal_load is not None]
    report_thermal = max(thermal_vals) if thermal_vals else None

    unified_ts: float | None = None
    unified_seg: str | None = None
    for obs in sorted(observations, key=lambda o: o.ts, reverse=True):
        if obs.sensor_kind == "unified_field_segment" and obs.unified_segment_label:
            unified_ts = obs.ts
            unified_seg = obs.unified_segment_label
            break

    lid_closed: bool | None = None
    for row in row_list:
        raw = _first_value(row, LID_CLOSED_KEYS)
        if raw is None:
            continue
        if isinstance(raw, bool):
            lid_closed = raw
        else:
            s = str(raw).strip().lower()
            lid_closed = s in {"1", "true", "yes", "on", "closed", "shut"}

    # Proximity / presence: camera+mic evidence only (thermal alone is substrate, not carbon).
    physical_presence = False
    for obs in observations:
        if obs.sensor_kind not in {"camera_depth_map", "microphone_spatial_array"}:
            continue
        dist = obs.best_distance_m
        if obs.confidence >= 0.4 and (dist is None or dist <= 3.0):
            physical_presence = True
            break

    return PhysicalSpaceReport(
        observations=observations,
        near_distance_m=near_distance_m,
        collision_distance_m=collision_distance_m,
        pressure=pressure,
        nearest_body_distance_m=nearest_body,
        nearest_pair_distance_m=nearest_pair,
        violations=tuple(violations),
        physical_presence=physical_presence,
        physical_proximity=nearest_body,
        thermal_load=report_thermal,
        last_physical_event_ts=last_ev_ts,
        unified_field_ts=unified_ts,
        unified_field_location_segment=unified_seg,
        lid_closed=lid_closed,
    )


__all__ = [
    "PhysicalBodyObservation",
    "PhysicalSpaceReport",
    "SPATIAL_SENSOR_ALIASES",
    "SPATIAL_SENSOR_KINDS",
    "build_physical_space_report",
    "distance_between",
    "extract_physical_observations",
    "parse_physical_observation",
    "physical_coupling_from_distance",
    "physical_pressure_from_distance",
    "sensor_kind_for_row",
]
