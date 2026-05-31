#!/usr/bin/env python3
"""Forager Semantic A* — bounded best-first recall over SIFTA's memory palace (r207).

George 2026-05-31: port the GraphPalace *pattern* only. The pattern: a bounded,
informed (A*-style) search that traverses the wing→room→drawer hierarchy and the
existing code knowledge graph, ranked by lexical query overlap, graph proximity, and
pheromone weight — instead of scanning flat rows. This stands on classic CS/biology
(A* informed search + ant-colony pheromone heuristic), not on GraphPalace's claims.

Honest framing: with no embedding organ yet, the "semantic" match is LEXICAL (token
overlap, BM25-lite) + STRUCTURAL (graph distance). Pure Python stdlib, deterministic
(stable tie-break by node id), bounded (max_expansions, top_k). No network, no model.

Node cost (lower = better):
    cost = w_lex*(1 - lexical_overlap)      # query relevance
         + w_graph*normalized_graph_distance # structural closeness to a seed
         - w_phero*pheromone_boost           # recently-useful trails pull recall
         + w_stale*staleness_penalty         # old/low-retention nodes cost more
This is a soft pheromone heuristic feeding a strict bounded search — the covenant's
stigmergic-vs-deterministic split kept clean.
"""
from __future__ import annotations

import heapq
import math
import re
import time
from typing import Any, Optional

TRUTH_LABEL = "FORAGER_SEMANTIC_ASTAR_V1"

_W_LEX = 1.0
_W_GRAPH = 0.35
_W_PHERO = 0.5
_W_STALE = 0.3
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _lexical_overlap(query_tokens: set[str], text: str, idf: dict[str, float]) -> float:
    """BM25-lite: idf-weighted share of query terms present in the text. 0..1."""
    if not query_tokens:
        return 0.0
    toks = set(_tokens(text))
    if not toks:
        return 0.0
    matched = query_tokens & toks
    if not matched:
        return 0.0
    num = sum(idf.get(t, 1.0) for t in matched)
    den = sum(idf.get(t, 1.0) for t in query_tokens)
    return round(num / den, 6) if den else 0.0


def _build_idf(query_tokens: set[str], rows: list[dict[str, Any]]) -> dict[str, float]:
    n = max(1, len(rows))
    df: dict[str, int] = {}
    for r in rows:
        present = set(_tokens(_node_text(r)))
        for t in query_tokens & present:
            df[t] = df.get(t, 0) + 1
    return {t: math.log(1.0 + n / (1.0 + df.get(t, 0))) for t in query_tokens}


def _node_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("ref") or row.get("trace_id")
               or row.get("fingerprint") or row.get("drawer") or repr(sorted(row.items()))[:64])


def _node_text(row: dict[str, Any]) -> str:
    for k in ("text", "description", "title", "name", "summary", "content", "drawer", "room"):
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return " ".join(str(v) for v in row.values() if isinstance(v, str))[:600]


def _pheromone_boost(node_id: str, pheromone_rows: list[dict[str, Any]], now: float) -> float:
    """Recently-reinforced, recently-used trails give a boost in 0..1 (time-decayed)."""
    best = 0.0
    for p in pheromone_rows or []:
        pid = str(p.get("id") or p.get("ref") or p.get("node") or p.get("trace_id") or "")
        if pid and pid == node_id:
            strength = float(p.get("strength") or p.get("weight") or p.get("uses") or 1.0)
            ts = float(p.get("ts") or now)
            age_days = max(0.0, (now - ts) / 86400.0)
            decay = math.exp(-age_days / 7.0)  # ~weekly half-life-ish
            best = max(best, min(1.0, strength) * decay)
    return round(best, 6)


def _staleness(row: dict[str, Any], now: float) -> float:
    ts = float(row.get("ts") or now)
    age_days = max(0.0, (now - ts) / 86400.0)
    retention = float(row.get("retention") or 1.0)
    base = 1.0 - math.exp(-age_days / 30.0)        # older → closer to 1
    return round(min(1.0, base + max(0.0, 1.0 - retention) * 0.3), 6)


def semantic_astar(
    query: str,
    hierarchy_rows: list[dict[str, Any]],
    *,
    graph_nodes: Optional[list[dict[str, Any]]] = None,
    graph_edges: Optional[list[tuple]] = None,
    pheromone_rows: Optional[list[dict[str, Any]]] = None,
    max_expansions: int = 200,
    top_k: int = 8,
    now: Optional[float] = None,
) -> list[dict[str, Any]]:
    """Bounded best-first (A*-style) recall. Returns up to top_k nodes ranked by cost
    ascending, each {id, cost, lexical, pheromone, wing, room, drawer, ref, text}.

    Deterministic: ties break by node id. Bounded: at most max_expansions pops. If
    there are no nodes, returns []— the caller falls back to flat recall."""
    t = float(now if now is not None else time.time())
    nodes = list(hierarchy_rows or []) + list(graph_nodes or [])
    if not nodes:
        return []
    by_id = {_node_id(r): r for r in nodes}
    qtok = set(_tokens(query))
    idf = _build_idf(qtok, nodes)

    # adjacency from graph edges (undirected, by node id)
    adj: dict[str, set[str]] = {}
    for e in graph_edges or []:
        try:
            a, b = str(e[0]), str(e[1])
        except Exception:
            continue
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)

    pher = pheromone_rows or []

    # ── Precompute every distance-independent field ONCE (r220: kill the O(N²)) ──
    # The old hot path recomputed _pheromone_boost (a full scan of EVERY pheromone
    # row) and re-tokenized node text for EVERY node — on seed, on every heap pop,
    # and again in the fill pass. That is O(N·P) ≈ O(N²) (≈1s at N=5000, found in the
    # r219 GraphPalace head-to-head). lex / boost / staleness do not depend on graph
    # distance, so compute them a single time; node_cost then only adds the distance
    # term. Every number stays byte-identical to the per-call version (same helpers,
    # same rounding) — this is a speed refactor, not a behaviour change.
    boost_by_id: dict[str, float] = {}
    for p in pher:
        pid = str(p.get("id") or p.get("ref") or p.get("node") or p.get("trace_id") or "")
        if not pid:
            continue
        strength = float(p.get("strength") or p.get("weight") or p.get("uses") or 1.0)
        ts = float(p.get("ts") or t)
        age_days = max(0.0, (t - ts) / 86400.0)
        contribution = min(1.0, strength) * math.exp(-age_days / 7.0)
        if contribution > boost_by_id.get(pid, 0.0):
            boost_by_id[pid] = contribution
    boost_by_id = {k: round(v, 6) for k, v in boost_by_id.items()}  # match _pheromone_boost

    text_by_id: dict[str, str] = {}
    lex_by_id: dict[str, float] = {}
    stale_by_id: dict[str, float] = {}
    for nid, row in by_id.items():
        txt = _node_text(row)
        text_by_id[nid] = txt
        lex_by_id[nid] = _lexical_overlap(qtok, txt, idf)
        stale_by_id[nid] = _staleness(row, t)

    def node_cost(nid: str, row: dict[str, Any], graph_dist: int) -> tuple[float, dict[str, Any]]:
        lex = lex_by_id[nid]
        boost = boost_by_id.get(nid, 0.0)
        stale = stale_by_id[nid]
        gnorm = min(1.0, graph_dist / 6.0)
        cost = (_W_LEX * (1.0 - lex) + _W_GRAPH * gnorm
                - _W_PHERO * boost + _W_STALE * stale)
        detail = {"id": nid, "cost": round(cost, 6), "lexical": lex,
                  "pheromone": boost, "stale": stale, "graph_dist": graph_dist,
                  "wing": row.get("wing", ""), "room": row.get("room", ""),
                  "drawer": row.get("drawer", ""), "ref": row.get("ref", ""),
                  "text": text_by_id[nid][:300]}
        return cost, detail

    # Seed frontier from directly useful nodes. This makes graph distance meaningful:
    # lexical/pheromone hits are distance 0; connected neighbours inherit a small
    # structural advantage; disconnected leftovers are filled at max distance.
    frontier: list[tuple[float, str, int]] = []
    seen_dist: dict[str, int] = {}
    for nid, row in by_id.items():
        if lex_by_id[nid] > 0.0 or boost_by_id.get(nid, 0.0) > 0.0:
            cost, _ = node_cost(nid, row, 0)
            heapq.heappush(frontier, (round(cost, 6), nid, 0))
            seen_dist[nid] = 0
    if not frontier:
        for nid, row in by_id.items():
            cost, _ = node_cost(nid, row, 0)
            heapq.heappush(frontier, (round(cost, 6), nid, 0))
            seen_dist[nid] = 0

    results: dict[str, dict[str, Any]] = {}
    expansions = 0
    while frontier and expansions < max_expansions:
        cost, nid, dist = heapq.heappop(frontier)
        expansions += 1
        row = by_id.get(nid)
        if row is None:
            continue
        c, detail = node_cost(nid, row, dist)
        prev = results.get(nid)
        if prev is None or detail["cost"] < prev["cost"]:
            results[nid] = detail
        # expand neighbours (graph proximity pulls related nodes in)
        for nb in sorted(adj.get(nid, ())):
            if nb in by_id:
                next_dist = dist + 1
                if next_dist < seen_dist.get(nb, 10 ** 9):
                    seen_dist[nb] = next_dist
                    nb_cost, _ = node_cost(nb, by_id[nb], next_dist)
                    heapq.heappush(frontier, (round(nb_cost, 6), nb, dist + 1))

    for nid, row in by_id.items():
        if nid not in results:
            _, detail = node_cost(nid, row, 6)
            results[nid] = detail

    ranked = sorted(results.values(), key=lambda d: (d["cost"], d["id"]))
    return ranked[:max(0, int(top_k))]


__all__ = ["TRUTH_LABEL", "semantic_astar"]
