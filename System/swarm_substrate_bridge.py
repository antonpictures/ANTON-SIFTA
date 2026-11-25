#!/usr/bin/env python3
"""swarm_substrate_bridge.py — Stage 2: semantic recall over the EXISTING memory ledger.

Does NOT duplicate memory storage. It reads the existing
`.sifta_state/memory_ledger.jsonl` (the StigmergicMemoryBus ledger) and builds a
vector index in Alice Space, so any organ can do semantic recall by meaning
instead of keyword match.

Pipeline:
  ledger rows -> text -> MiniLM(+adapter) -> Alice Space vectors -> ANN index
  query -> same encoder -> nearest traces -> rows

Non-invasive: StigmergicMemoryBus keeps owning writes; this owns vector recall.

Usage:
  python3 System/swarm_substrate_bridge.py build            # build index
  python3 System/swarm_substrate_bridge.py recall "query"  # semantic recall
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / ".sifta_state"
SUBSTRATE = STATE / "substrate"
LEDGER = STATE / "memory_ledger.jsonl"
INDEX_DIR = SUBSTRATE / "ledger_index"
MINILM = "sentence-transformers/all-MiniLM-L6-v2"
SPACE_DIM = 512
NATIVE_DIM = 768

DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"


# ── Encoder ───────────────────────────────────────────────────────────────────


def _load_encoder():
    tok = AutoTokenizer.from_pretrained(MINILM)
    model = AutoModel.from_pretrained(MINILM).to(DEVICE).eval()
    return tok, model


def _embed_batch(tokenizer, model, texts: list[str], batch_size: int = 64) -> np.ndarray:
    """Mean-pooled MiniLM embeddings, (n, 384)."""
    out = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i + batch_size]
        enc = tokenizer(chunk, return_tensors="pt", truncation=True,
                        max_length=128, padding=True).to(DEVICE)
        with torch.no_grad():
            o = model(**enc)
        mask = enc["attention_mask"].unsqueeze(-1).float()
        emb = ((o.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1)).cpu().numpy()
        out.append(emb)
        if (i // batch_size) % 10 == 0:
            print(f"  embedded {min(i + batch_size, len(texts))}/{len(texts)}", flush=True)
    return np.vstack(out).astype(np.float32)


def _native_vector(text: str, tokenizer, model) -> np.ndarray:
    """Native representation: concat(text_emb, text_emb) to match adapter native dim.

    NOTE: adapters were trained on (input_emb, response_emb). For an index over
    stored text we use (text_emb, text_emb) — a stable, response-free
    representation. Stage 3 can swap in a response-aware encoder.
    """
    e = _embed_batch(tokenizer, model, [text])[0]
    return np.concatenate([e, e])  # 768


# ── Index ─────────────────────────────────────────────────────────────────────


def load_ledger(path: Path = LEDGER) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _row_text(row: dict) -> str:
    return str(row.get("raw_text") or row.get("text") or "").strip()


def build_index(ledger_path: Path = LEDGER, force: bool = False) -> dict:
    """Embed every ledger trace into Alice Space and save the index."""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    vec_path = INDEX_DIR / "vectors.npy"
    meta_path = INDEX_DIR / "ids.json"

    rows = load_ledger(ledger_path)
    if not rows:
        return {"ok": False, "error": "ledger empty or missing"}

    if vec_path.exists() and meta_path.exists() and not force:
        print("Index exists; use --force to rebuild.")
        return {"ok": True, "reused": True, "count": len(rows)}

    print(f"Loading encoder on {DEVICE}...")
    tok, model = _load_encoder()

    texts = [_row_text(r) for r in rows]
    keep = [(i, t) for i, t in enumerate(texts) if t]
    print(f"Embedding {len(keep)} non-empty traces (batched)...")

    emb = _embed_batch(tok, model, [t for _, t in keep], batch_size=256)
    # Native vector = concat(text_emb, text_emb) — same contract as _native_vector
    mat = np.concatenate([emb, emb], axis=1).astype(np.float32)
    ids = [rows[i].get("trace_id", str(i)) for i, _ in keep]
    print(f"  embedded {len(ids)} traces -> {mat.shape}", flush=True)
    np.save(vec_path, mat)
    meta_path.write_text(json.dumps({"ids": ids, "built_at": time.time(),
                                     "source": str(ledger_path), "rows": int(mat.shape[0]),
                                     "dim": int(mat.shape[1])}, ensure_ascii=False))

    print(f"Index built: {mat.shape} -> {INDEX_DIR}")
    return {"ok": True, "count": int(mat.shape[0]), "dim": int(mat.shape[1])}


def semantic_recall(query: str, top_k: int = 5) -> list[dict]:
    """Find nearest ledger traces by meaning."""
    vec_path = INDEX_DIR / "vectors.npy"
    meta_path = INDEX_DIR / "ids.json"
    if not vec_path.exists() or not meta_path.exists():
        return []

    meta = json.loads(meta_path.read_text())
    ids = meta["ids"]
    mat = np.load(vec_path)

    tok, model = _load_encoder()
    q = _native_vector(query, tok, model)

    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    qn = q / (np.linalg.norm(q) or 1)
    sims = ((mat / norms) @ qn).flatten()

    order = np.argsort(sims)[::-1][:top_k]
    rows_by_id = {r.get("trace_id"): r for r in load_ledger()}

    out = []
    for idx in order:
        tid = ids[int(idx)]
        row = rows_by_id.get(tid, {})
        out.append({
            "trace_id": tid,
            "similarity": float(sims[int(idx)]),
            "text": _row_text(row),
            "app": row.get("app_context"),
            "timestamp": row.get("timestamp"),
        })
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "build":
        force = "--force" in sys.argv
        print(json.dumps(build_index(force=force), indent=2))
    elif cmd == "recall":
        query = " ".join(sys.argv[2:]) or "Alice"
        for r in semantic_recall(query):
            print(f"  [{r['similarity']:.3f}] {r['app']}: {r['text'][:80]}")
    else:
        print("Usage: swarm_substrate_bridge.py build [--force] | recall <query>")