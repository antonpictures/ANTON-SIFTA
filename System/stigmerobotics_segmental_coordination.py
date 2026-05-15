#!/usr/bin/env python3
"""
System/stigmerobotics_segmental_coordination.py
================================================

E46 — Segmental Coordination (Lamprey CPG Coupling)

ROB 501 topic: Coupled oscillators, distributed control, CPG coordination.

References:
  Ayers, J.L. (2004). Underwater walking.
    Arthropod Structure & Development 33(3):347-360.
    — Lamprey CPG: each body segment has its own pattern generator; segments
      are coupled via pheromone-like inter-segment signals; result is a
      traveling wave without any central orchestrator.
  Cohen, A.H. et al. (1992). Modeling of intersegmental coordination in the
    lamprey central pattern generator by explicit use of phase lags.
    Journal of Neurophysiology 67(4):912-921.
  Grillner, S. (2003). The motor infrastructure: from ion channels to
    neuronal networks. Nature Reviews Neuroscience 4(7):573-586.

──────────────────────────────────────────────────────────────────────────────
Segmental Coupling Theorem (E46):

  Let SIFTA have N active channels: S = { (serial_i, ide_i) : i = 1..N }

  Define:
    coupling(A, B) = E33 collision_risk(A, B) ∈ [0, 1]

  Adjacency:
    Two channels A, B are ADJACENT iff coupling(A, B) > θ_adj (default 0.0)
    i.e. any non-zero cross-channel collision signal creates adjacency.

  Coupling matrix C ∈ [0,1]^{N×N}:
    C[i][j] = coupling(S_i, S_j)    (symmetric, C[i][i] = 0)

  Stable coordination condition:
    The system is COORDINATED iff for every pair (A, B) with C[A][B] > θ_c:
      NOT (A fires in same window as B)
    i.e. no two strongly-coupled channels fire simultaneously.

  Lamprey wave property:
    When rows arrive in a sequence where each channel fires with phase offset
    dt/N seconds, the coupling matrix produces a "traveling wave" of receipts
    across all N channels — analogous to the lamprey body wave.

  Falsifier:
    Two adjacent channels (coupling > θ_c) both have SCAR_RECEIPT rows within
    the collision window → SIMULTANEOUS_FIRE violation → not coordinated.

  truth_label: OPERATIONAL

§8.6 compliance: side-effect free. Operates on input row sequences only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Iterable, Mapping, Sequence

from System.stigmerobotics_physical_space import (
    PhysicalBodyObservation,
    build_physical_space_report,
    physical_coupling_from_distance,
)


# ── Coordination parameters ─────────────────────────────────────────────────

DEFAULT_ADJACENCY_THRESHOLD: float = 0.0    # any non-zero collision = adjacent
DEFAULT_COUPLING_THRESHOLD: float = 0.05    # strong coupling threshold (θ_c)
DEFAULT_COLLISION_WINDOW_S: float = 120.0   # same as E33 default


# ── Coordination states ─────────────────────────────────────────────────────

class CoordinationState(Enum):
    COORDINATED    = auto()  # no simultaneous-fire violations
    UNCOORDINATED  = auto()  # at least one simultaneous-fire detected
    SINGLE_CHANNEL = auto()  # only 1 channel — coupling undefined


# ── Data types ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ChannelFire:
    """A single 'fire' event — one effector row on one channel."""
    channel: tuple[str, str]          # (homeworld_serial, source_ide)
    ts: float
    kind: str
    trace_id: str
    row_index: int
    physical_x: float | None = None
    physical_y: float | None = None
    physical_z: float | None = None
    distance_m: float | None = None
    body_id: str | None = None
    sensor_kind: str | None = None
    physical_confidence: float = 0.0


@dataclass(frozen=True)
class CouplingEdge:
    channel_a: tuple[str, str]
    channel_b: tuple[str, str]
    coupling_strength: float          # E33 collision risk between A and B


@dataclass(frozen=True)
class SimultaneousFireViolation:
    fire_a: ChannelFire
    fire_b: ChannelFire
    coupling_strength: float
    gap_s: float
    reason: str = "simultaneous_fire_on_coupled_channels"


# ── Segmental Coordination Report ───────────────────────────────────────────

@dataclass(frozen=True)
class SegmentalCoordinationReport:
    """
    Full coordination analysis for a multi-channel trace.
    """
    channels: tuple[tuple[str, str], ...]
    phase_angles: tuple[float, ...]
    wave_direction: int
    propagation_speed: float
    fires: tuple[ChannelFire, ...]
    coupling_edges: tuple[CouplingEdge, ...]
    violations: tuple[SimultaneousFireViolation, ...]
    adjacency_threshold: float
    coupling_threshold: float
    collision_window_s: float
    physical_space: "PhysicalSpaceReport"

    @property
    def n_channels(self) -> int:
        return len(self.channels)

    @property
    def state(self) -> CoordinationState:
        if self.n_channels <= 1:
            return CoordinationState.SINGLE_CHANNEL
        if self.violations:
            return CoordinationState.UNCOORDINATED
        return CoordinationState.COORDINATED

    @property
    def coupling_matrix(self) -> dict[tuple[tuple[str, str], tuple[str, str]], float]:
        """Sparse coupling matrix C[i][j] = coupling_strength."""
        return {
            (e.channel_a, e.channel_b): e.coupling_strength
            for e in self.coupling_edges
        }

    @property
    def adjacent_pairs(self) -> list[CouplingEdge]:
        """Channel pairs with coupling > adjacency_threshold."""
        return [e for e in self.coupling_edges
                if e.coupling_strength > self.adjacency_threshold]

    @property
    def strongly_coupled_pairs(self) -> list[CouplingEdge]:
        """Channel pairs with coupling > coupling_threshold."""
        return [e for e in self.coupling_edges
                if e.coupling_strength > self.coupling_threshold]

    @property
    def wave_property_holds(self) -> bool:
        """
        Lamprey wave property: no two adjacent channels fire simultaneously.
        True iff no violations.
        """
        return len(self.violations) == 0

    @property
    def physical_space_grounded(self) -> bool:
        return self.physical_space.grounded

    @property
    def physical_sensor_kinds(self) -> tuple[str, ...]:
        return self.physical_space.sensor_kinds

    @property
    def physical_body_ids(self) -> tuple[str, ...]:
        return self.physical_space.body_ids

    @property
    def physical_observations(self) -> tuple[PhysicalBodyObservation, ...]:
        return self.physical_space.observations

    @property
    def physical_pressure(self) -> float:
        return self.physical_space.pressure

    @property
    def nearest_body_distance_m(self) -> float | None:
        return self.physical_space.nearest_body_distance_m

    @property
    def proof_of_property(self) -> dict[str, Any]:
        return {
            "E46": "Segmental coordination — lamprey CPG coupling via E33 collision risk",
            "topology": "nearest-neighbor ring",
            "phase_angles": self.phase_angles,
            "wave_direction": self.wave_direction,
            "propagation_speed": self.propagation_speed,
            "theorem": (
                "No two channels with coupling > θ_c fire within collision_window_s "
                "→ COORDINATED (wave property holds)"
            ),
            "state": self.state.name,
            "n_channels": self.n_channels,
            "n_fires": len(self.fires),
            "n_coupling_edges": len(self.coupling_edges),
            "n_adjacent_pairs": len(self.adjacent_pairs),
            "n_strongly_coupled": len(self.strongly_coupled_pairs),
            "violations": len(self.violations),
            "wave_property": self.wave_property_holds,
            "physical_space_grounded": self.physical_space_grounded,
            "n_physical_observations": len(self.physical_space.observations),
            "physical_sensor_kinds": list(self.physical_sensor_kinds),
            "physical_body_ids": list(self.physical_body_ids),
            "physical_pressure": self.physical_space.pressure,
            "nearest_body_distance_m": self.physical_space.nearest_body_distance_m,
            "lamprey_mapping": (
                "channel = body segment; "
                "effector row = CPG firing; "
                "E33 collision risk = inter-segment coupling strength; "
                "physical body pose = desk-space sensor coupling; "
                "no simultaneous fire = wave propagation without deadlock"
            ),
            "ayers_reference": "Ayers 2004 doi:10.1016/j.asd.2004.06.003",
            "falsifier": (
                "Two coupled channels (coupling > θ_c) fire within collision_window_s "
                "→ SimultaneousFireViolation → UNCOORDINATED"
            ),
            "truth_label": "OPERATIONAL" if self.wave_property_holds else "BROKEN",
        }

    def summary_lines(self) -> list[str]:
        lines = [
            f"E46 Segmental Coordination: {self.state.name}",
            f"channels: {self.n_channels}",
            f"fires: {len(self.fires)}",
            f"coupling_edges: {len(self.coupling_edges)}",
            f"strongly_coupled_pairs: {len(self.strongly_coupled_pairs)}",
            f"wave_property: {self.wave_property_holds}",
            f"wave_direction: {self.wave_direction}",
            f"propagation_speed: {self.propagation_speed:.3f} seg/s",
            f"physical_space_grounded: {self.physical_space_grounded}",
            f"physical_observations: {len(self.physical_space.observations)}",
            f"physical_sensors: {', '.join(self.physical_sensor_kinds) or 'none'}",
            f"physical_pressure: {self.physical_space.pressure:.6f}",
        ]
        if self.violations:
            lines.append("violations:")
            for v in self.violations[:6]:
                lines.append(
                    f"  {v.fire_a.channel[1]}<->{v.fire_b.channel[1]} "
                    f"gap={v.gap_s:.1f}s coupling={v.coupling_strength:.4f}"
                )
        return lines


# ── Builder ──────────────────────────────────────────────────────────────────

def _float_or_none(v: Any) -> float | None:
    try:
        r = float(v)
        return r if math.isfinite(r) else None
    except (TypeError, ValueError):
        return None


def _fire_spatial_distance_m(fa: ChannelFire, fb: ChannelFire) -> float | None:
    has_a_xyz = fa.physical_x is not None or fa.physical_y is not None or fa.physical_z is not None
    has_b_xyz = fb.physical_x is not None or fb.physical_y is not None or fb.physical_z is not None
    if has_a_xyz and has_b_xyz:
        dx = (fa.physical_x or 0.0) - (fb.physical_x or 0.0)
        dy = (fa.physical_y or 0.0) - (fb.physical_y or 0.0)
        dz = (fa.physical_z or 0.0) - (fb.physical_z or 0.0)
        return math.sqrt((dx * dx) + (dy * dy) + (dz * dz))
    if fa.distance_m is not None and fb.distance_m is not None:
        return abs(fa.distance_m - fb.distance_m)
    return None


def _fire_physical_coupling(fa: ChannelFire, fb: ChannelFire) -> float:
    distance_m = _fire_spatial_distance_m(fa, fb)
    confidence = max(0.0, min(1.0, (fa.physical_confidence + fb.physical_confidence) / 2.0))
    return physical_coupling_from_distance(distance_m, confidence=confidence)


def build_coordination_report(
    rows: Iterable[Mapping[str, Any]],
    *,
    physical_space: "PhysicalSpaceReport | None" = None,
    adjacency_threshold: float = DEFAULT_ADJACENCY_THRESHOLD,
    coupling_threshold: float = DEFAULT_COUPLING_THRESHOLD,
    collision_window_s: float = DEFAULT_COLLISION_WINDOW_S,
    effector_kinds: frozenset[str] | None = None,
) -> SegmentalCoordinationReport:
    """
    Build the segmental coordination report from a sequence of trace rows.

    Only effector-class rows are considered 'fires'.
    Coupling strength is computed from temporal proximity of effector rows
    on different channels within the collision window — exactly as E33 does.
    """
    row_tuple = tuple(rows)
    if physical_space is None:
        physical_space = build_physical_space_report(row_tuple)
    observations_by_row = {obs.row_index: obs for obs in physical_space.observations}

    if effector_kinds is None:
        from System.stigmerobotics_safe_append_dfa import GATED_KINDS
        effector_kinds = frozenset(GATED_KINDS)

    # Collect all channels and fires
    all_channels: set[tuple[str, str]] = set()
    fires: list[ChannelFire] = []

    for idx, row in enumerate(row_tuple):
        if "_parse_error" in row:
            continue
        ts = _float_or_none(row.get("ts"))
        if ts is None:
            continue
        serial = str(row.get("homeworld_serial") or row.get("node_serial") or "UNKNOWN")
        ide = str(row.get("source_ide") or row.get("doctor") or "UNKNOWN")
        kind = str(row.get("kind") or row.get("event") or "unknown")
        tid = str(row.get("trace_id") or f"row_{idx}")
        channel = (serial, ide)
        all_channels.add(channel)
        
        # Track physical spatial location when this row is grounded by the
        # shared camera/mic/desk telemetry parser.
        physical_obs = observations_by_row.get(idx)
        px = physical_obs.x_m if physical_obs is not None else _float_or_none(row.get("physical_x") or row.get("pose_x") or row.get("camera_x"))
        py = physical_obs.y_m if physical_obs is not None else _float_or_none(row.get("physical_y") or row.get("pose_y") or row.get("camera_y"))
        pz = physical_obs.z_m if physical_obs is not None else _float_or_none(row.get("physical_z") or row.get("pose_z") or row.get("camera_z"))
        dist = physical_obs.distance_m if physical_obs is not None else _float_or_none(row.get("distance_m") or row.get("depth_m"))
        body_id = physical_obs.body_id if physical_obs is not None else None
        sensor_kind = physical_obs.sensor_kind if physical_obs is not None else None
        physical_confidence = physical_obs.confidence if physical_obs is not None else 0.0
        
        if kind in effector_kinds:
            fires.append(ChannelFire(channel=channel, ts=ts, kind=kind,
                                     trace_id=tid, row_index=idx,
                                     physical_x=px, physical_y=py,
                                     physical_z=pz, distance_m=dist,
                                     body_id=body_id, sensor_kind=sensor_kind,
                                     physical_confidence=physical_confidence))

    channels = tuple(sorted(all_channels))
    fires_tuple = tuple(sorted(fires, key=lambda f: f.ts))

    # Calculate ideal phase angles (phi_i = 2*pi*i/N)
    phase_angles = tuple((2 * math.pi * i / len(channels)) for i in range(len(channels))) if all_channels else ()

    wave_direction = 0
    propagation_speed = 0.0

    if len(channels) > 1 and len(fires_tuple) > 1:
        directions = []
        speeds = []
        for i in range(len(fires_tuple) - 1):
            fa = fires_tuple[i]
            fb = fires_tuple[i + 1]
            if fa.channel == fb.channel:
                continue
            idx_a = channels.index(fa.channel)
            idx_b = channels.index(fb.channel)
            n_c = len(channels)
            diff = idx_b - idx_a
            
            if diff == 1 or diff == -(n_c - 1):
                directions.append(1)
            elif diff == -1 or diff == (n_c - 1):
                directions.append(-1)
                
            gap = fb.ts - fa.ts
            if gap > 0:
                speeds.append(1.0 / gap)
                
        if directions:
            avg_dir = sum(directions) / len(directions)
            wave_direction = 1 if avg_dir > 0 else (-1 if avg_dir < 0 else 0)
        if speeds:
            propagation_speed = sum(speeds) / len(speeds)

    # Compute coupling edges (cross-channel temporal proximity of fires)
    # E46b: Nearest-neighbor ring topology only.
    coupling_edges: list[CouplingEdge] = []
    seen_pairs: set[frozenset[tuple[str, str]]] = set()

    for i, fa in enumerate(fires_tuple):
        for fb in fires_tuple[i + 1:]:
            gap = fb.ts - fa.ts
            if gap > collision_window_s:
                break
            if fa.channel == fb.channel:
                continue
                
            idx_a = channels.index(fa.channel)
            idx_b = channels.index(fb.channel)
            n_c = len(channels)
            # Nearest neighbor in ring
            is_neighbor = (abs(idx_a - idx_b) == 1) or (abs(idx_a - idx_b) == (n_c - 1))
            if not is_neighbor and n_c > 1:
                continue

            pair = frozenset({fa.channel, fb.channel})
            if pair in seen_pairs:
                continue
            # Coupling = same decay formula as E33 collision risk
            strength = math.exp(-gap / max(collision_window_s, 1.0))
            
            strength = max(strength, _fire_physical_coupling(fa, fb))

            coupling_edges.append(CouplingEdge(
                channel_a=fa.channel,
                channel_b=fb.channel,
                coupling_strength=strength,
            ))
            seen_pairs.add(pair)

    # Detect simultaneous-fire violations
    violations: list[SimultaneousFireViolation] = []
    for i, fa in enumerate(fires_tuple):
        for fb in fires_tuple[i + 1:]:
            gap = fb.ts - fa.ts
            if gap > collision_window_s:
                break
            if fa.channel == fb.channel:
                continue
                
            idx_a = channels.index(fa.channel)
            idx_b = channels.index(fb.channel)
            n_c = len(channels)
            is_neighbor = (abs(idx_a - idx_b) == 1) or (abs(idx_a - idx_b) == (n_c - 1))
            if not is_neighbor and n_c > 1:
                continue
                
            strength = math.exp(-gap / max(collision_window_s, 1.0))
            strength = max(strength, _fire_physical_coupling(fa, fb))

            if strength > coupling_threshold:
                violations.append(SimultaneousFireViolation(
                    fire_a=fa, fire_b=fb,
                    coupling_strength=strength,
                    gap_s=gap,
                ))

    return SegmentalCoordinationReport(
        channels=channels,
        phase_angles=phase_angles,
        wave_direction=wave_direction,
        propagation_speed=propagation_speed,
        fires=fires_tuple,
        coupling_edges=tuple(coupling_edges),
        violations=tuple(violations),
        adjacency_threshold=adjacency_threshold,
        coupling_threshold=coupling_threshold,
        collision_window_s=collision_window_s,
        physical_space=physical_space,
    )


def coordination_ok(rows: Iterable[Mapping[str, Any]], **kwargs: Any) -> bool:
    return build_coordination_report(rows, **kwargs).wave_property_holds


if __name__ == "__main__":
    import json
    from pathlib import Path
    _TRACE = Path(__file__).resolve().parent.parent / ".sifta_state" / "ide_stigmergic_trace.jsonl"
    if _TRACE.exists():
        rows = [json.loads(l) for l in _TRACE.read_text().splitlines() if l.strip()]
        rows = rows[-300:]
        from System.stigmerobotics_physical_space import build_physical_space_report
        space = build_physical_space_report(rows)
        report = build_coordination_report(space, rows)
        print("\n".join(report.summary_lines()))
