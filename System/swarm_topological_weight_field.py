#!/usr/bin/env python3
"""
System/swarm_topological_weight_field.py
══════════════════════════════════════════════════════════════════════
Topological stigmergic weight field (TSWF) — not a merge organ.

Adapters = nodes, ordered replay paths = edges. Weights are derived from
success rate and entropy penalty on nodes, modulated by incoming edge
stability. No gradient access, no base-weight mutation here.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from System.canonical_schemas import assert_payload_keys
except ImportError:

    def assert_payload_keys(_ledger_name: str, _payload: dict, *, strict: bool = True) -> None:
        return None

from System.jsonl_file_lock import append_line_locked

MODULE_VERSION = "2026-04-24.topological-weight-field.v1"

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_LEDGER = _REPO / ".sifta_state" / "topological_weight_field.jsonl"


@dataclass
class AdapterNode:
    name: str
    activation_count: int = 0
    success_count: int = 0
    entropy_accum: float = 0.0


@dataclass
class InteractionEdge:
    src: str
    dst: str
    flow: float = 0.0
    stability: float = 0.0


class TopologicalWeightField:
    def __init__(self) -> None:
        self.nodes: Dict[str, AdapterNode] = {}
        self.edges: Dict[Tuple[str, str], InteractionEdge] = {}
        self.path_count = 0

    def register_adapter(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("adapter name is required")
        if name not in self.nodes:
            self.nodes[name] = AdapterNode(name=name)

    def record_interaction(self, path: List[str], success: bool, entropy: float) -> None:
        if not path:
            raise ValueError("path must contain at least one adapter")
        if entropy < 0:
            raise ValueError("entropy must be non-negative")
        clean_path = [str(node_name).strip() for node_name in path]
        if any(not node_name for node_name in clean_path):
            raise ValueError("path contains an empty adapter name")

        self.path_count += 1

        for node_name in clean_path:
            self.register_adapter(node_name)
        for i, node_name in enumerate(clean_path):
            node = self.nodes[node_name]
            node.activation_count += 1
            node.success_count += int(success)
            node.entropy_accum += entropy

            if i < len(clean_path) - 1:
                edge_key = (clean_path[i], clean_path[i + 1])
                if edge_key not in self.edges:
                    self.edges[edge_key] = InteractionEdge(src=clean_path[i], dst=clean_path[i + 1])
                edge = self.edges[edge_key]
                edge.flow += 1.0
                if success:
                    edge.stability += 1.0

    def compute_weight(self, node: AdapterNode) -> float:
        if node.activation_count == 0:
            return 0.0

        success_rate = node.success_count / node.activation_count
        avg_entropy = node.entropy_accum / node.activation_count
        stability_score = success_rate * math.exp(-avg_entropy)
        activity_penalty = math.log(1 + node.activation_count)
        return stability_score / activity_penalty

    def compute_edge_factor(self, edge: InteractionEdge) -> float:
        if edge.flow == 0:
            return 0.0
        stability_ratio = edge.stability / edge.flow
        return stability_ratio * math.log(1 + edge.flow)

    def generate_merge_weights(self) -> Dict[str, float]:
        weights: Dict[str, float] = {}
        for name, node in self.nodes.items():
            base_weight = self.compute_weight(node)
            incoming = [
                self.compute_edge_factor(e)
                for (src, dst), e in self.edges.items()
                if dst == name
            ]
            topology_boost = sum(incoming) / (1 + len(incoming)) if incoming else 1.0
            weights[name] = base_weight * topology_boost

        total = sum(weights.values()) or 1.0
        return {k: v / total for k, v in weights.items()}

    def fingerprint(self) -> str:
        payload = json.dumps(
            sorted(self.generate_merge_weights().items()),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def mean_entropy(self) -> float:
        if not self.nodes:
            return 0.0
        num = sum(n.entropy_accum for n in self.nodes.values())
        den = sum(n.activation_count for n in self.nodes.values()) or 1
        return num / den

    def paths_observed(self) -> int:
        return self.path_count

    def build_ledger_row(
        self,
        *,
        paths_observed: int | None = None,
        entropy_mean: float | None = None,
        ts: float | None = None,
    ) -> Dict[str, object]:
        row = {
            "event": "topological_weight_update",
            "schema": "SIFTA_TOPOLOGICAL_WEIGHT_FIELD_V1",
            "module_version": MODULE_VERSION,
            "fingerprint": self.fingerprint(),
            "adapters": self.generate_merge_weights(),
            "entropy_mean": float(entropy_mean if entropy_mean is not None else self.mean_entropy()),
            "paths_observed": int(paths_observed if paths_observed is not None else self.paths_observed()),
            "ts": float(ts if ts is not None else time.time()),
        }
        assert_payload_keys("topological_weight_field.jsonl", row)
        return row

    def append_ledger_row(
        self,
        *,
        ledger_path: Path | None = None,
        paths_observed: int | None = None,
        entropy_mean: float | None = None,
    ) -> None:
        path = ledger_path if ledger_path is not None else _DEFAULT_LEDGER
        row = self.build_ledger_row(
            paths_observed=paths_observed,
            entropy_mean=entropy_mean,
        )
        append_line_locked(path, json.dumps(row, sort_keys=True) + "\n")
