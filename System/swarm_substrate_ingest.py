#!/usr/bin/env python3
"""swarm_substrate_ingest.py — Stage 4: keep Alice Space current, incrementally.

The semantic index is a VIEW over memory Alice already writes. This module
appends vectors for rows that were written since the last ingest, without
rebuilding and without creating a second ledger.

Two views, one encoder:
  ledger    .sifta_state/memory_ledger.jsonl          (canonical bus of record)
  journal   .sifta_state/alice_first_person_journal.jsonl  (identity memory body)

Index layout (per view):
  <index_dir>/vectors.npy   (n, 768)
  <index_dir>/ids.json      {"ids": [...], "texts": [...], "built_at": ..., "source": ...}

texts[] is stored so a hit can be shown even if the source file rotates.

Usage
  python3 System/swarm_substrate_ingest.py all        # both views, incremental
  python3 System/swarm_substrate_ingest.py ledger
  python3 System/swarm_substrate_ingest.py journal
  python3 System/swarm_substrate_ingest.py --status

Timer: run after a conversation window (e.g. via launchd or nightly cron).
Incremental — no-op when nothing is new.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

STATE = REPO / ".sifta_state"
SUBSTRATE = STATE / "substrate"

VIEWS: dict[str, dict[str, Any]] = {
    "ledger": {
        "source": STATE / "memory_ledger.jsonl",
        "dir": SUBSTRATE / "ledger_index",
        "id_key": "trace_id",
        "text_key": "raw_text",
        "extra": ("app_context", "timestamp"),
    },
    "journal": {
        "source": STATE / "alice_first_person_journal.jsonl",
        "dir": SUBSTRATE / "journal_index",
        "id_key": "journal_id",
        "text_key": "text",
        "extra": ("source", "ts"),
    },
    "narrative": {
        "source": STATE / "alice_narrative_diary.jsonl",
        "dir": SUBSTRATE / "narrative_index",
        "id_key": "narrative_id",
        "text_key": "entry",
        "extra": ("event_type", "ts"),
    },
}

MAX_APPEND = 20_000  # per run, keeps a single ingest bounded


def _rows(path: Path) -> list[dict]:
    out = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _meta_path(view: str) -> Path:
    return VIEWS[view]["dir"] / "ids.json"


def _existing(view: str) -> tuple[set[str], list[str], Optional[np.ndarray]]:
    d = VIEWS[view]["dir"]
    vec_path = d / "vectors.npy"
    meta_path = _meta_path(view)
    if not vec_path.exists() or not meta_path.exists():
        return set(), [], None
    meta = json.loads(meta_path.read_text())
    ids = [str(i) for i in meta.get("ids") or []]
    mat = np.load(vec_path)
    if mat.shape[0] != len(ids):
        return set(), [], None  # misaligned: caller rebuilds
    return set(ids), [str(t) for t in meta.get("texts") or []], mat


def sync(view: str, force: bool = False) -> dict:
    """Append vectors for rows not yet in this view's index."""
    cfg = VIEWS[view]
    rows = _rows(cfg["source"])
    if not rows:
        return {"view": view, "ok": True, "added": 0, "reason": "source empty or missing"}

    known, texts, mat = _existing(view)
    if force or mat is None:
        known, texts, mat = set(), [], None
    prev_ids: list[str] = (
        [str(i) for i in json.loads(_meta_path(view).read_text()).get("ids") or []]
        if known and _meta_path(view).exists()
        else []
    )

    pending: list[tuple[str, str, dict]] = []
    for r in rows:
        tid = str(r.get(cfg["id_key"]) or "")
        if not tid:
            raw_sig = json.dumps(r, sort_keys=True, ensure_ascii=False).encode("utf-8", errors="replace")
            tid = f"row_{hashlib.sha256(raw_sig).hexdigest()[:12]}"
        if tid in known:
            continue
        text = str(r.get(cfg["text_key"]) or "").strip()
        if not text:
            continue
        known.add(tid)
        pending.append((tid, text, r))
        if len(pending) >= MAX_APPEND:
            break

    if not pending:
        return {"view": view, "ok": True, "added": 0, "index_rows": len(prev_ids),
                "reason": "already current"}

    from System.swarm_substrate_bridge import _load_encoder, _embed_batch

    tok, model = _load_encoder()
    emb = _embed_batch(tok, model, [t for _, t, _ in pending], batch_size=256)
    native = np.concatenate([emb, emb], axis=1).astype(np.float32)

    if mat is not None and mat.shape[1] != native.shape[1]:
        return {"view": view, "ok": False, "added": 0,
                "error": f"dim drift {mat.shape[1]} -> {native.shape[1]}; rerun with force"}

    mat = native if mat is None else np.vstack([mat, native])
    ids = prev_ids + [i for i, _, _ in pending]
    texts_out = texts + [t for _, t, _ in pending]

    d = cfg["dir"]
    d.mkdir(parents=True, exist_ok=True)
    np.save(d / "vectors.npy", mat)
    meta = {
        "ids": ids,
        "texts": texts_out,
        "built_at": time.time(),
        "source": str(cfg["source"]),
        "rows": int(mat.shape[0]),
    }
    _meta_path(view).write_text(json.dumps(meta, ensure_ascii=False))
    return {"view": view, "ok": True, "added": len(pending), "index_rows": int(mat.shape[0])}


def recall(view: str, query_vector: np.ndarray, top_k: int = 3) -> list[dict]:
    """Nearest rows in one view. Returns id/text/score only — callers merge."""
    d = VIEWS[view]["dir"]
    vec_path, meta_path = d / "vectors.npy", _meta_path(view)
    if not vec_path.exists() or not meta_path.exists():
        return []
    meta = json.loads(meta_path.read_text())
    mat = np.load(vec_path)
    ids, texts = meta.get("ids") or [], meta.get("texts") or []
    if mat.shape[0] != len(ids):
        return []

    q = np.asarray(query_vector, dtype=np.float32).reshape(-1)
    if q.shape[0] != mat.shape[1]:
        return []
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    qn = q / (np.linalg.norm(q) or 1)
    sims = ((mat / norms) @ qn).flatten()
    order = np.argsort(sims)[::-1][:top_k]
    return [
        {
            "view": view,
            "id": ids[int(i)],
            "text": texts[int(i)] if int(i) < len(texts) else "",
            "similarity": float(sims[int(i)]),
        }
        for i in order
    ]


_HYDRATE_CACHE: dict[str, dict[str, str]] = {}


def _id_text_map(view: str) -> dict[str, str]:
    """id -> text straight from the source file (for rows indexed before texts[] existed)."""
    if view in _HYDRATE_CACHE:
        return _HYDRATE_CACHE[view]
    cfg = VIEWS[view]
    mapping: dict[str, str] = {}
    for r in _rows(cfg["source"]):
        tid = str(r.get(cfg["id_key"]) or "")
        text = str(r.get(cfg["text_key"]) or "").strip()
        if tid and text:
            mapping[tid] = text
    _HYDRATE_CACHE[view] = mapping
    return mapping


def hydrate(hits: list[dict]) -> list[dict]:
    """Fill empty hit texts from the source of record."""
    for h in hits:
        if not h.get("text"):
            h["text"] = _id_text_map(h.get("view", "")).get(str(h.get("id")), "")
    return [h for h in hits if h.get("text")]


def status() -> dict:
    out = {}
    for view, cfg in VIEWS.items():
        meta_path = _meta_path(view)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            rows = meta.get("rows")
            if rows is None:
                try:
                    rows = int(np.load(cfg["dir"] / "vectors.npy", mmap_mode="r").shape[0])
                except Exception:
                    rows = None
            out[view] = {
                "rows": rows,
                "built_at": meta.get("built_at"),
                "source": meta.get("source"),
            }
        else:
            out[view] = {"rows": 0, "built_at": None, "source": str(cfg["source"])}
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cmd = args[0] if args else "all"
    if "--status" in sys.argv or cmd == "status":
        print(json.dumps(status(), indent=2))
    elif cmd == "all":
        print(json.dumps([sync(v) for v in VIEWS], indent=2))
    elif cmd in VIEWS:
        print(json.dumps(sync(cmd), indent=2))
    else:
        print("usage: all | ledger | journal | narrative | --status")
