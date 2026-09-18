#!/usr/bin/env python3
"""swarm_ledger_tree_index.py — PageIndex mechanism: reasoning-guided ledger recall.

Borged from VectifyAI/PageIndex (35.7k): RAG by reasoning over a document TREE
(TOC -> section -> rows) instead of embedding similarity. SIFTA's memory_search
is keyword/BM25 over whole ledgers; this organ builds a per-ledger TOC of
time-window sections with top-frequency terms, so a cortex reasons: "which
section is about X?" then reads only that slice.

Pure stdlib, deterministic, testable offline.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STOP = frozenset("the and for with this that from into over your alice george sifta".split())
_WORD = re.compile(r"[a-z][a-z0-9_\-]{2,}")


def _terms(text: str) -> Counter:
    return Counter(w for w in _WORD.findall(str(text).lower()) if w not in _STOP)


def build_tree_index(ledger_path: str | Path, *, section_rows: int = 128) -> dict:
    """Build a tree index for one .jsonl ledger. Returns a dict; never raises."""
    rows: list[dict] = []
    path = Path(ledger_path)
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue
    sections: list[dict] = []
    for base in range(0, len(rows), max(1, section_rows)):
        block = rows[base:base + section_rows]
        text = "\n".join(json.dumps(r, ensure_ascii=False) for r in block)
        top = _terms(text).most_common(6)
        sections.append({
            "section": len(sections),
            "row_start": base,
            "row_end": base + len(block) - 1,
            "rows": len(block),
            "top_terms": [
                {"term": term, "count": count} for term, count in top
            ],
        })
    return {
        "schema": "LEDGER_TREE_INDEX_V1",
        "ts": time.time(),
        "ledger": str(path),
        "rows": len(rows),
        "sections": sections,
        "truth_label": "LEDGER_TREE_INDEX_V1",
    }


def query_tree_index(index: dict, query: str) -> dict:
    """Reason over the tree: return the best sections for a query, with row ranges."""
    if not isinstance(index, dict) or not index.get("sections"):
        return {"sections": [], "matched_terms": []}
    q = [w for w in _WORD.findall(str(query).lower()) if w not in _STOP]
    scored = []
    for sec in index["sections"]:
        terms = {t["term"]: t["count"] for t in sec.get("top_terms") or []}
        hits = [w for w in q if w in terms]
        score = sum(terms[w] for w in hits)
        if hits:
            scored.append({"score": score, "matched_terms": hits,
                           "row_start": sec["row_start"], "row_end": sec["row_end"],
                           "section": sec["section"]})
    scored.sort(key=lambda s: s["score"], reverse=True)
    return {
        "schema": "LEDGER_TREE_QUERY_V1",
        "matched_terms": [w for s in scored for w in s["matched_terms"]],
        "sections": scored[:4],
        "truth_label": "LEDGER_TREE_QUERY_V1",
    }
