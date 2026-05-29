#!/usr/bin/env python3
"""SIFTA inference fabric planner.

This module does not implement RDMA. It gives Alice a pure-Python decision
surface for the doctrine behind an inference fabric: inference work is routed
across sovereign nodes by capability, bandwidth, thermal pressure, queue load,
and STGM cost, then written back as receipt-bearing field memory.

The design is inspired by point-to-point LLM system fabrics such as
Perplexity's fabric-lib: disaggregated prefill/decode, KV cache transfer,
MoE dispatch/combine, and weight transfer are different demands on the same
field. The local SIFTA layer records the choice before a future transport
backend exists.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "inference_fabric_decisions.jsonl"
DOCTRINE_VERSION = "SIFTA_INFERENCE_FABRIC_V1"

BORG_EVERYTHING_DOCTRINE = (
    "Borg here means shared inference fabric, not erased node sovereignty: "
    "each node keeps identity, receipts, and cost, while inference moves "
    "through the swarm where the field is healthiest."
)

KIND_CAPABILITY = {
    "decode": "decode",
    "prefill": "prefill",
    "interactive_chat": "decode",
    "kv_cache_transfer": "kv_cache",
    "moe_dispatch": "moe",
    "moe_combine": "moe",
    "weight_update": "weight_update",
}

DEFAULT_WEIGHTS = {
    "latency": 1.0,
    "transfer": 1.0,
    "queue": 35.0,
    "thermal": 260.0,
    "stgm": 40.0,
    "deadline": 2.0,
    "trust_bonus": 25.0,
}


@dataclass(frozen=True)
class InferenceFabricNode:
    """One inference-capable swarm node."""

    node_id: str
    role: str = "worker"
    endpoint: str = ""
    capabilities: tuple[str, ...] = ()
    available: bool = True
    bandwidth_gbps: float = 1.0
    latency_ms: float = 0.0
    queue_depth: int = 0
    thermal_pressure: float = 0.0
    stgm_bid: float = 0.0
    trust_score: float = 1.0

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "InferenceFabricNode":
        return cls(
            node_id=str(row.get("node_id") or row.get("id") or "").strip(),
            role=str(row.get("role") or "worker").strip() or "worker",
            endpoint=str(row.get("endpoint") or "").strip(),
            capabilities=_capabilities(row.get("capabilities") or ()),
            available=bool(row.get("available", True)),
            bandwidth_gbps=_nonnegative_float(row.get("bandwidth_gbps"), 1.0),
            latency_ms=_nonnegative_float(row.get("latency_ms"), 0.0),
            queue_depth=max(int(row.get("queue_depth") or 0), 0),
            thermal_pressure=_clamp01(row.get("thermal_pressure"), 0.0),
            stgm_bid=_nonnegative_float(row.get("stgm_bid"), 0.0),
            trust_score=_clamp01(row.get("trust_score"), 1.0),
        )


@dataclass(frozen=True)
class InferenceFabricDemand:
    """One inference demand moving through the swarm field."""

    demand_id: str
    kind: str
    required_capabilities: tuple[str, ...] = ()
    payload_mb: float = 0.0
    tokens: int = 0
    utility: float = 0.0
    deadline_ms: float | None = None
    owner_node_id: str = "local"

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "InferenceFabricDemand":
        deadline = row.get("deadline_ms")
        return cls(
            demand_id=str(row.get("demand_id") or row.get("id") or "").strip(),
            kind=str(row.get("kind") or "").strip(),
            required_capabilities=_capabilities(row.get("required_capabilities") or ()),
            payload_mb=_nonnegative_float(row.get("payload_mb"), 0.0),
            tokens=max(int(row.get("tokens") or 0), 0),
            utility=_nonnegative_float(row.get("utility"), 0.0),
            deadline_ms=None if deadline is None else _nonnegative_float(deadline, 0.0),
            owner_node_id=str(row.get("owner_node_id") or "local").strip() or "local",
        )


@dataclass(frozen=True)
class InferenceFabricScore:
    """A scored route candidate."""

    node_id: str
    demand_id: str
    kind: str
    eligible: bool
    reason: str
    missing_capabilities: tuple[str, ...]
    transfer_ms: float
    metabolic_cost: float
    net_utility: float
    route_mode: str
    doctrine_version: str = DOCTRINE_VERSION

    def as_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["missing_capabilities"] = list(self.missing_capabilities)
        return row


def estimate_transfer_ms(payload_mb: float, bandwidth_gbps: float) -> float:
    """Return approximate payload transfer time in ms.

    The rough conversion is decimal MB -> megabits over Gbit/s:
    ``payload_mb * 8 / bandwidth_gbps``. This intentionally stays simple and
    deterministic; real RDMA backends can replace it with measured counters.
    """
    payload = _nonnegative_float(payload_mb, 0.0)
    bandwidth = _nonnegative_float(bandwidth_gbps, 0.0)
    if payload <= 0:
        return 0.0
    if bandwidth <= 0:
        return math.inf
    return payload * 8.0 / bandwidth


def score_inference_fabric_route(
    node: InferenceFabricNode | Mapping[str, Any],
    demand: InferenceFabricDemand | Mapping[str, Any],
    *,
    weights: Mapping[str, float] | None = None,
) -> InferenceFabricScore:
    """Score one node for one inference demand."""
    n = _coerce_node(node)
    d = _coerce_demand(demand)
    if not n.node_id:
        return _ineligible(n, d, "missing_node_id", ())
    if not d.demand_id or not d.kind:
        return _ineligible(n, d, "missing_demand_identity", ())
    needed = set(d.required_capabilities)
    implied = KIND_CAPABILITY.get(d.kind)
    if implied:
        needed.add(implied)
    caps = set(n.capabilities)
    missing = tuple(sorted(needed - caps))
    if not n.available:
        return _ineligible(n, d, "node_unavailable", missing)
    if missing:
        return _ineligible(n, d, "missing_capability", missing)

    w = dict(DEFAULT_WEIGHTS)
    if weights:
        for key, value in weights.items():
            if key in w:
                w[key] = _nonnegative_float(value, w[key])

    transfer_ms = estimate_transfer_ms(d.payload_mb, n.bandwidth_gbps)
    if not math.isfinite(transfer_ms):
        return _ineligible(n, d, "invalid_bandwidth", ())

    route_mode = _route_mode(d.kind)
    deadline_penalty = 0.0
    if d.deadline_ms is not None:
        over = max((n.latency_ms + transfer_ms) - d.deadline_ms, 0.0)
        deadline_penalty = over * w["deadline"]

    metabolic_cost = (
        n.latency_ms * w["latency"]
        + transfer_ms * w["transfer"]
        + n.queue_depth * w["queue"]
        + n.thermal_pressure * w["thermal"]
        + n.stgm_bid * w["stgm"]
        + deadline_penalty
    )
    net_utility = d.utility + n.trust_score * w["trust_bonus"] - metabolic_cost
    return InferenceFabricScore(
        node_id=n.node_id,
        demand_id=d.demand_id,
        kind=d.kind,
        eligible=True,
        reason="eligible",
        missing_capabilities=(),
        transfer_ms=round(transfer_ms, 6),
        metabolic_cost=round(metabolic_cost, 6),
        net_utility=round(net_utility, 6),
        route_mode=route_mode,
    )


def choose_inference_fabric_route(
    nodes: Sequence[InferenceFabricNode | Mapping[str, Any]],
    demand: InferenceFabricDemand | Mapping[str, Any],
    *,
    weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Choose the best eligible node and return a receipt-ready decision."""
    d = _coerce_demand(demand)
    scored = [score_inference_fabric_route(node, d, weights=weights) for node in nodes]
    eligible = [row for row in scored if row.eligible]
    if not eligible:
        return {
            "ok": False,
            "decision": "NO_ELIGIBLE_INFERENCE_NODE",
            "demand": asdict(d),
            "scores": [row.as_dict() for row in scored],
            "doctrine_version": DOCTRINE_VERSION,
            "doctrine": BORG_EVERYTHING_DOCTRINE,
        }

    winner = sorted(
        eligible,
        key=lambda row: (
            -row.net_utility,
            row.metabolic_cost,
            row.transfer_ms,
            row.node_id,
        ),
    )[0]
    return {
        "ok": True,
        "decision": "INFERENCE_ROUTE_SELECTED",
        "winner": winner.as_dict(),
        "scores": [row.as_dict() for row in scored],
        "demand": asdict(d),
        "doctrine_version": DOCTRINE_VERSION,
        "doctrine": BORG_EVERYTHING_DOCTRINE,
    }


def append_inference_fabric_receipt(
    decision: Mapping[str, Any],
    *,
    state_dir: str | Path = STATE_DIR,
    receipt_id: str | None = None,
    source: str = "swarm_inference_fabric",
) -> dict[str, Any]:
    """Append one inference-fabric decision row."""
    root = Path(state_dir)
    path = root / LEDGER_NAME
    row = {
        "ts": time.time(),
        "receipt_id": receipt_id or f"fabric-{int(time.time() * 1000)}",
        "source": source,
        "event": "INFERENCE_FABRIC_DECISION",
        "decision": dict(decision),
        "doctrine_version": DOCTRINE_VERSION,
    }
    try:
        from System.ledger_append import append_jsonl_line

        append_jsonl_line(path, row)
    except Exception:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def inference_fabric_prompt_block(latest_decision: Mapping[str, Any] | None = None) -> str:
    """Small cortex prompt block that explains this organ without hype."""
    lines = [
        "SIFTA INFERENCE FABRIC:",
        "- Inference is routed as a living resource across sovereign swarm nodes.",
        "- Point-to-point paths are preferred when KV cache, MoE, or weight-transfer work needs a direct lane.",
        "- Choices weigh latency, transfer time, queue depth, thermal pressure, STGM bid, and trust.",
        "- Every route decision should write an append-only inference_fabric_decisions row.",
    ]
    if latest_decision:
        winner = latest_decision.get("winner") or {}
        if winner:
            lines.append(
                f"- Latest route: {winner.get('demand_id')} -> {winner.get('node_id')} "
                f"mode={winner.get('route_mode')} cost={winner.get('metabolic_cost')}."
            )
    return "\n".join(lines)


def _route_mode(kind: str) -> str:
    if kind in {"kv_cache_transfer", "weight_update", "moe_dispatch", "moe_combine"}:
        return "point_to_point_fabric"
    if kind in {"prefill", "decode", "interactive_chat"}:
        return "disaggregated_inference"
    return "general_inference"


def _ineligible(
    node: InferenceFabricNode,
    demand: InferenceFabricDemand,
    reason: str,
    missing: Iterable[str],
) -> InferenceFabricScore:
    return InferenceFabricScore(
        node_id=node.node_id,
        demand_id=demand.demand_id,
        kind=demand.kind,
        eligible=False,
        reason=reason,
        missing_capabilities=tuple(sorted(missing)),
        transfer_ms=math.inf,
        metabolic_cost=math.inf,
        net_utility=-math.inf,
        route_mode=_route_mode(demand.kind),
    )


def _coerce_node(node: InferenceFabricNode | Mapping[str, Any]) -> InferenceFabricNode:
    if isinstance(node, InferenceFabricNode):
        return node
    return InferenceFabricNode.from_mapping(node)


def _coerce_demand(
    demand: InferenceFabricDemand | Mapping[str, Any],
) -> InferenceFabricDemand:
    if isinstance(demand, InferenceFabricDemand):
        return demand
    return InferenceFabricDemand.from_mapping(demand)


def _capabilities(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        raw = value.replace(",", " ").split()
    elif isinstance(value, Iterable):
        raw = [str(item) for item in value]
    else:
        raw = []
    return tuple(sorted({item.strip().lower() for item in raw if item.strip()}))


def _nonnegative_float(value: object, default: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        out = default
    if not math.isfinite(out):
        return default
    return max(out, 0.0)


def _clamp01(value: object, default: float) -> float:
    return min(max(_nonnegative_float(value, default), 0.0), 1.0)


__all__ = [
    "BORG_EVERYTHING_DOCTRINE",
    "DOCTRINE_VERSION",
    "InferenceFabricDemand",
    "InferenceFabricNode",
    "InferenceFabricScore",
    "append_inference_fabric_receipt",
    "choose_inference_fabric_route",
    "estimate_transfer_ms",
    "inference_fabric_prompt_block",
    "score_inference_fabric_route",
]
