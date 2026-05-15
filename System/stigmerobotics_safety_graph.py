#!/usr/bin/env python3
"""
System/stigmerobotics_safety_graph.py
=====================================

E34 - Minimal complete graph for safety.

The safety graph is the smallest directed evidence graph required before
effector-class rows are considered safe: for each `(homeworld_serial,
source_ide)` channel, every effector row must be reachable from a prior
registration row.  The graph is side-effect free and reads live ledgers only
when explicitly asked by the widget/CLI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from System.stigmerobotics_safe_append_dfa import GATED_KINDS, REGISTRATION_KINDS

_REPO = Path(__file__).resolve().parent.parent
_TRACE = _REPO / ".sifta_state" / "ide_stigmergic_trace.jsonl"
_FIXTURE = _REPO / "tests" / "fixtures" / "stigmero_e34_safety_good.jsonl"

EFFECTOR_KINDS: frozenset[str] = frozenset(GATED_KINDS)


@dataclass(frozen=True)
class SafetyNode:
    row_index: int
    ts: float
    kind: str
    source_ide: str
    homeworld_serial: str
    trace_id: str
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def channel(self) -> tuple[str, str]:
        return (self.homeworld_serial, self.source_ide)


@dataclass(frozen=True)
class SafetyEdge:
    source_row: int
    target_row: int
    source_trace_id: str
    target_trace_id: str
    channel: tuple[str, str]
    reason: str


@dataclass(frozen=True)
class SafetyViolation:
    row_index: int
    kind: str
    trace_id: str
    channel: tuple[str, str]
    reason: str


@dataclass(frozen=True)
class SafetyGraphReport:
    nodes: tuple[SafetyNode, ...]
    edges: tuple[SafetyEdge, ...]
    violations: tuple[SafetyViolation, ...]

    @property
    def ok(self) -> bool:
        return not self.violations

    @property
    def effector_count(self) -> int:
        return sum(1 for node in self.nodes if node.kind in EFFECTOR_KINDS)

    @property
    def channel_count(self) -> int:
        return len({node.channel for node in self.nodes})

    @property
    def proof_of_property(self) -> dict[str, Any]:
        return {
            "E34": "Minimal complete graph for safety",
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "channels": self.channel_count,
            "effector_count": self.effector_count,
            "edge_rule": "registration_node -> effector_node for same (homeworld_serial, source_ide)",
            "minimality": "one required predecessor edge per safe effector row; no cross-channel substitution",
            "violations": [v.reason for v in self.violations],
            "truth_label": "OPERATIONAL" if self.ok else "BROKEN",
        }

    def has_registration_path(self, row_index: int) -> bool:
        return any(edge.target_row == row_index for edge in self.edges)

    def summary_lines(self) -> list[str]:
        lines = [
            f"E34 Safety Graph: {'PASS' if self.ok else 'FAIL'}",
            f"nodes: {len(self.nodes)}",
            f"edges: {len(self.edges)}",
            f"channels: {self.channel_count}",
            f"effector_count: {self.effector_count}",
            "",
            "required edges:",
        ]
        for edge in self.edges[:12]:
            lines.append(
                f"  row {edge.source_row} -> row {edge.target_row} "
                f"{edge.channel[1]} {edge.reason}"
            )
        if self.violations:
            lines.append("")
            lines.append("violations:")
            for violation in self.violations[:12]:
                lines.append(
                    f"  row {violation.row_index} {violation.kind} "
                    f"{violation.channel}: {violation.reason}"
                )
        return lines


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            rows.append({"_parse_error": f"line={idx}: {exc}"})
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _payload_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = row.get("payload")
    if isinstance(payload, dict):
        return dict(payload)
    if isinstance(payload, str) and payload.strip().startswith("{"):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _float_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:
        return None
    return out


def _trace_id(row: Mapping[str, Any], row_index: int) -> str:
    value = row.get("trace_id")
    return value if isinstance(value, str) and value else f"row_{row_index}"


def _node_from_row(row: Mapping[str, Any], row_index: int) -> SafetyNode | None:
    ts = _float_or_none(row.get("ts"))
    if ts is None:
        return None
    return SafetyNode(
        row_index=row_index,
        ts=ts,
        kind=str(row.get("kind") or row.get("event") or "legacy"),
        source_ide=str(row.get("source_ide") or row.get("doctor") or "UNKNOWN"),
        homeworld_serial=str(row.get("homeworld_serial") or row.get("node_serial") or row.get("device") or "UNKNOWN"),
        trace_id=_trace_id(row, row_index),
        payload=_payload_dict(row),
    )


def build_safety_graph(rows: Iterable[Mapping[str, Any]]) -> SafetyGraphReport:
    nodes: list[SafetyNode] = []
    edges: list[SafetyEdge] = []
    violations: list[SafetyViolation] = []
    latest_registration: dict[tuple[str, str], SafetyNode] = {}
    latest_ts: dict[tuple[str, str], float] = {}

    for row_index, row in enumerate(rows):
        if "_parse_error" in row:
            violations.append(
                SafetyViolation(
                    row_index=row_index,
                    kind="JSON_PARSE_ERROR",
                    trace_id=f"row_{row_index}",
                    channel=("UNKNOWN", "UNKNOWN"),
                    reason=str(row["_parse_error"]),
                )
            )
            continue
        node = _node_from_row(row, row_index)
        if node is None:
            continue

        nodes.append(node)
        channel = node.channel
        previous_ts = latest_ts.get(channel)
        if previous_ts is not None and node.ts < previous_ts:
            violations.append(
                SafetyViolation(
                    row_index=node.row_index,
                    kind=node.kind,
                    trace_id=node.trace_id,
                    channel=channel,
                    reason="ts_rollback_breaks_safety_graph",
                )
            )
        latest_ts[channel] = node.ts

        if node.kind in REGISTRATION_KINDS:
            latest_registration[channel] = node
            continue

        if node.kind in EFFECTOR_KINDS:
            registration = latest_registration.get(channel)
            if registration is None:
                violations.append(
                    SafetyViolation(
                        row_index=node.row_index,
                        kind=node.kind,
                        trace_id=node.trace_id,
                        channel=channel,
                        reason="missing_registration_path",
                    )
                )
                continue
            edges.append(
                SafetyEdge(
                    source_row=registration.row_index,
                    target_row=node.row_index,
                    source_trace_id=registration.trace_id,
                    target_trace_id=node.trace_id,
                    channel=channel,
                    reason="registration_precedes_effector",
                )
            )

    return SafetyGraphReport(nodes=tuple(nodes), edges=tuple(edges), violations=tuple(violations))


def safety_graph_ok(rows: Iterable[Mapping[str, Any]]) -> bool:
    return build_safety_graph(rows).ok


def fixture_safety_graph(path: Path = _FIXTURE) -> SafetyGraphReport:
    return build_safety_graph(load_jsonl(path))


def live_safety_graph(*, limit: int = 300) -> SafetyGraphReport:
    if not _TRACE.exists():
        return build_safety_graph([])
    rows = load_jsonl(_TRACE)
    return build_safety_graph(rows[-limit:])


if __name__ == "__main__":
    print("\n".join(live_safety_graph().summary_lines()))
