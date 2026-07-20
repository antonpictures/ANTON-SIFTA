#!/usr/bin/env python3
"""
swarm_convo_term_index.py — incremental term index for Alice's global chat.

The index is a cache over .sifta_state/alice_conversation.jsonl. It stores
terms -> byte offsets only, so the conversation ledger remains the source of
truth and can be rebuilt if the cache is missing or corrupt.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_DEFAULT_CONVO = _STATE / "alice_conversation.jsonl"
_DEFAULT_INDEX = _STATE / "convo_term_index.json"

_STOPWORDS = {
    "remember", "recall", "memory", "memories", "look", "looking", "lookup",
    "still", "your", "yours", "what", "when", "where", "which", "did", "does",
    "have", "from", "just", "about", "tell", "know", "please", "this", "that",
    "with", "into", "then", "them", "they", "will", "would", "could", "should",
    "there", "their", "because", "while", "owner", "alice",
}

_TEXT_KEYS = (
    "text",
    "content",
    "message",
    "raw_text",
    "line",
    "summary",
    "description",
    "title",
    "url",
)


def _index_path(state_dir: Optional[Path] = None, index_path: Optional[Path] = None) -> Path:
    if index_path is not None:
        return Path(index_path)
    return Path(state_dir or _STATE) / "convo_term_index.json"


def _tokenize(text: str) -> List[str]:
    terms = []
    seen = set()
    for term in re.findall(r"[a-zA-Z0-9]+", (text or "").lower()):
        if len(term) <= 3 or term in _STOPWORDS:
            continue
        if term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def _row_ts(row: Dict[str, Any]) -> float:
    ts = row.get("ts")
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, dict):
        for key in ("physical_pt", "ts", "timestamp", "created_at"):
            value = ts.get(key)
            if isinstance(value, (int, float)):
                return float(value)
    for key in ("timestamp", "created_at", "physical_pt"):
        value = row.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def _row_text(row: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in _TEXT_KEYS:
        value = row.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            parts.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return " ".join(parts)


def _empty_index(source: Path) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "source_path": str(source),
        "last_indexed_offset": 0,
        "source_size": 0,
        "updated_ts": 0.0,
        "row_count": 0,
        "terms": {},
    }


def _load_index(path: Path, source: Path) -> Dict[str, Any]:
    if not path.exists():
        return _empty_index(source)
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return _empty_index(source)
    if not isinstance(data, dict) or not isinstance(data.get("terms"), dict):
        return _empty_index(source)
    if data.get("source_path") and str(data.get("source_path")) != str(source):
        return _empty_index(source)
    data.setdefault("schema_version", 1)
    data.setdefault("source_path", str(source))
    data.setdefault("last_indexed_offset", 0)
    data.setdefault("source_size", 0)
    data.setdefault("row_count", 0)
    return data


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def ensure_indexed(
    conversation_path: Optional[Path] = None,
    *,
    state_dir: Optional[Path] = None,
    index_path: Optional[Path] = None,
    cap_per_term: int = 500,
) -> Dict[str, Any]:
    """Index only bytes appended since last_indexed_offset."""
    source = Path(conversation_path or _DEFAULT_CONVO)
    idx_path = _index_path(state_dir or source.parent, index_path)
    data = _load_index(idx_path, source)
    if not source.exists():
        _atomic_write_json(idx_path, data)
        return {**data, "indexed_now": 0, "index_path": str(idx_path)}

    source_size = source.stat().st_size
    last_offset = int(data.get("last_indexed_offset") or 0)
    if source_size < last_offset:
        data = _empty_index(source)
        last_offset = 0

    terms: Dict[str, List[List[float]]] = data.setdefault("terms", {})
    indexed_now = 0
    row_count = int(data.get("row_count") or 0)
    next_offset = last_offset

    with source.open("rb") as handle:
        handle.seek(last_offset)
        while True:
            offset = handle.tell()
            raw = handle.readline()
            if not raw:
                next_offset = offset
                break
            if not raw.endswith(b"\n"):
                next_offset = offset
                break
            next_offset = handle.tell()
            try:
                row = json.loads(raw.decode("utf-8"))
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            text = _row_text(row)
            row_terms = _tokenize(text)
            if not row_terms:
                continue
            ts_value = _row_ts(row)
            for term in row_terms:
                postings = terms.setdefault(term, [])
                postings.append([offset, ts_value])
                if len(postings) > cap_per_term:
                    del postings[:-cap_per_term]
            indexed_now += 1
            row_count += 1

    data["last_indexed_offset"] = next_offset
    data["source_size"] = source_size
    data["updated_ts"] = time.time()
    data["row_count"] = row_count
    _atomic_write_json(idx_path, data)
    return {**data, "indexed_now": indexed_now, "index_path": str(idx_path)}


def query_index(
    query_or_terms: str | Iterable[str],
    *,
    conversation_path: Optional[Path] = None,
    state_dir: Optional[Path] = None,
    index_path: Optional[Path] = None,
    max_rows: int = 24,
) -> List[Dict[str, Any]]:
    """Return conversation rows matching indexed terms, newest/highest hit count first."""
    source = Path(conversation_path or _DEFAULT_CONVO)
    idx = ensure_indexed(source, state_dir=state_dir or source.parent, index_path=index_path)
    if isinstance(query_or_terms, str):
        terms = _tokenize(query_or_terms)
    else:
        terms = [t for term in query_or_terms for t in _tokenize(str(term))]
    if not terms:
        return []

    term_set = list(dict.fromkeys(terms))
    postings_by_offset: Dict[int, Dict[str, Any]] = {}
    all_terms = idx.get("terms") if isinstance(idx.get("terms"), dict) else {}
    for term in term_set:
        postings = all_terms.get(term, [])
        if not isinstance(postings, list):
            continue
        for post in postings[-500:]:
            if not isinstance(post, list) or not post:
                continue
            try:
                offset = int(post[0])
                ts_value = float(post[1]) if len(post) > 1 else 0.0
            except Exception:
                continue
            entry = postings_by_offset.setdefault(offset, {"hits": set(), "ts": ts_value})
            entry["hits"].add(term)
            entry["ts"] = max(float(entry.get("ts") or 0.0), ts_value)

    ranked_offsets = sorted(
        postings_by_offset.items(),
        key=lambda item: (len(item[1]["hits"]), float(item[1].get("ts") or 0.0), item[0]),
        reverse=True,
    )[: max_rows * 3]

    out: List[Dict[str, Any]] = []
    if not source.exists():
        return out
    with source.open("rb") as handle:
        for offset, meta in ranked_offsets:
            try:
                handle.seek(offset)
                raw = handle.readline()
                row = json.loads(raw.decode("utf-8"))
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            text = _row_text(row)
            out.append(
                {
                    "source": source.name,
                    "matched_ts": _row_ts(row) or float(meta.get("ts") or 0.0),
                    "row": row,
                    "snippet": text[:300],
                    "index_hits": sorted(meta["hits"]),
                    "byte_offset": offset,
                }
            )
            if len(out) >= max_rows:
                break
    return out


if __name__ == "__main__":
    summary = ensure_indexed()
    print(json.dumps({k: summary.get(k) for k in ("row_count", "last_indexed_offset", "indexed_now", "index_path")}, indent=2))
