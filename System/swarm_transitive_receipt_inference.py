#!/usr/bin/env python3
"""Transitive receipt inference for swimmer/action contests.

Paper wasps can use A>B and B>C to infer A>C without paying the cost of
another fight. This organ does the same for SIFTA action receipts: prior
pairwise wins become a small preference graph that can suggest an action
before the organism burns metabolism re-running every pair.

The inference is advisory. Execution still needs a fresh action receipt.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional


TRUTH_LABEL = "TRANSITIVE_RECEIPT_INFERENCE_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"


@dataclass(frozen=True)
class PreferenceEdge:
    """One observed contest: winner beat loser with receipt proof."""

    winner: str
    loser: str
    receipt_id: str = ""
    context: str = ""
    weight: float = 1.0


@dataclass(frozen=True)
class InferredPreference:
    """One direct or transitive preference relation."""

    winner: str
    loser: str
    confidence: float
    path: list[str] = field(default_factory=list)
    evidence_receipts: list[str] = field(default_factory=list)
    direct: bool = False


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _state_dir_path(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def edge_from_receipt(row: dict[str, Any]) -> Optional[PreferenceEdge]:
    """Extract a pairwise preference from common receipt shapes."""
    if not isinstance(row, dict):
        return None
    winner = (
        row.get("winner")
        or row.get("selected")
        or row.get("selected_action")
        or row.get("winning_action")
        or row.get("kept")
        or row.get("accepted")
    )
    loser = (
        row.get("loser")
        or row.get("rejected")
        or row.get("rejected_action")
        or row.get("losing_action")
        or row.get("discarded")
    )
    beats = row.get("beats")
    if isinstance(beats, dict):
        winner = winner or beats.get("winner")
        loser = loser or beats.get("loser")
    if isinstance(beats, (list, tuple)) and len(beats) >= 2:
        winner = winner or beats[0]
        loser = loser or beats[1]
    winner_s = _clean(winner)
    loser_s = _clean(loser)
    if not winner_s or not loser_s or winner_s == loser_s:
        return None
    weight = row.get("weight", row.get("score_delta", 1.0))
    try:
        weight_f = max(0.01, float(weight or 1.0))
    except Exception:
        weight_f = 1.0
    return PreferenceEdge(
        winner=winner_s,
        loser=loser_s,
        receipt_id=_clean(row.get("receipt_id") or row.get("trace_id") or row.get("id")),
        context=_clean(row.get("context") or row.get("task") or row.get("surface"))[:160],
        weight=weight_f,
    )


def build_preference_graph(edges: Iterable[PreferenceEdge]) -> dict[str, dict[str, float]]:
    """Winner -> loser -> accumulated observed weight."""
    graph: dict[str, dict[str, float]] = defaultdict(dict)
    for edge in edges:
        graph[edge.winner][edge.loser] = graph[edge.winner].get(edge.loser, 0.0) + float(edge.weight)
        graph.setdefault(edge.loser, {})
    return {k: dict(v) for k, v in graph.items()}


def infer_transitive_preferences(
    rows_or_edges: Iterable[dict[str, Any] | PreferenceEdge],
    *,
    max_depth: int = 3,
    decay: float = 0.72,
) -> list[InferredPreference]:
    """Infer direct and transitive preferences from pairwise receipts.

    Confidence decays with path length and the weakest edge in the path. A
    direct A>B receipt has confidence near 1.0; A>B>C is lower but still useful
    as a proposal.
    """
    edges: list[PreferenceEdge] = []
    for item in rows_or_edges:
        if isinstance(item, PreferenceEdge):
            edges.append(item)
        elif isinstance(item, dict):
            edge = edge_from_receipt(item)
            if edge is not None:
                edges.append(edge)
    if not edges:
        return []

    graph = build_preference_graph(edges)
    receipt_by_pair: dict[tuple[str, str], list[str]] = defaultdict(list)
    for edge in edges:
        if edge.receipt_id:
            receipt_by_pair[(edge.winner, edge.loser)].append(edge.receipt_id)

    out: dict[tuple[str, str], InferredPreference] = {}
    for start in sorted(graph):
        queue: deque[tuple[str, list[str], float, list[str]]] = deque()
        queue.append((start, [start], 1.0, []))
        while queue:
            node, path, strength, receipts = queue.popleft()
            if len(path) > max_depth + 1:
                continue
            for nxt, weight in sorted(graph.get(node, {}).items()):
                if nxt in path:
                    continue
                pair_receipts = receipt_by_pair.get((node, nxt), [])
                next_path = path + [nxt]
                edge_strength = min(1.0, max(0.01, float(weight)))
                next_strength = min(strength, edge_strength) * (decay ** (len(next_path) - 2))
                next_receipts = receipts + pair_receipts
                key = (start, nxt)
                candidate = InferredPreference(
                    winner=start,
                    loser=nxt,
                    confidence=round(max(0.0, min(1.0, next_strength)), 4),
                    path=next_path,
                    evidence_receipts=next_receipts,
                    direct=len(next_path) == 2,
                )
                prior = out.get(key)
                if prior is None or candidate.confidence > prior.confidence:
                    out[key] = candidate
                queue.append((nxt, next_path, next_strength, next_receipts))

    return sorted(
        out.values(),
        key=lambda pref: (-pref.confidence, len(pref.path), pref.winner, pref.loser),
    )


def rank_candidates(
    rows_or_edges: Iterable[dict[str, Any] | PreferenceEdge],
    *,
    candidates: Optional[Iterable[str]] = None,
) -> list[dict[str, Any]]:
    """Rank candidates by inferred wins minus losses."""
    prefs = infer_transitive_preferences(rows_or_edges)
    allowed = {_clean(c) for c in candidates or [] if _clean(c)}
    scores: dict[str, float] = defaultdict(float)
    direct_wins: dict[str, int] = defaultdict(int)
    inferred_wins: dict[str, int] = defaultdict(int)
    for pref in prefs:
        if allowed and (pref.winner not in allowed or pref.loser not in allowed):
            continue
        scores[pref.winner] += pref.confidence
        scores[pref.loser] -= pref.confidence * 0.5
        if pref.direct:
            direct_wins[pref.winner] += 1
        else:
            inferred_wins[pref.winner] += 1
    for candidate in allowed:
        scores.setdefault(candidate, 0.0)
    return [
        {
            "candidate": candidate,
            "score": round(score, 4),
            "direct_wins": int(direct_wins.get(candidate, 0)),
            "inferred_wins": int(inferred_wins.get(candidate, 0)),
        }
        for candidate, score in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def write_preference_graph_receipt(
    rows_or_edges: Iterable[dict[str, Any] | PreferenceEdge],
    *,
    source: str = "swarm_transitive_receipt_inference",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Append a compact graph receipt for WCT and other swimmers."""
    items = list(rows_or_edges)
    prefs = infer_transitive_preferences(items)
    ranks = rank_candidates(items)
    sd = _state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    payload = {
        "preferences": [asdict(pref) for pref in prefs[:40]],
        "ranked_candidates": ranks[:20],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    row = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "receipt_id": f"transitive-pref-{uuid.uuid4().hex[:12]}",
        "action": "write_transitive_receipt_preference_graph",
        "source": source,
        "input_rows": len(items),
        "preference_count": len(prefs),
        "graph_sha256": digest,
        **payload,
    }
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    for name in ("receipt_preference_graph.jsonl", "work_receipts.jsonl"):
        try:
            with (sd / name).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass
    return row


__all__ = [
    "TRUTH_LABEL",
    "InferredPreference",
    "PreferenceEdge",
    "build_preference_graph",
    "edge_from_receipt",
    "infer_transitive_preferences",
    "rank_candidates",
    "write_preference_graph_receipt",
]
