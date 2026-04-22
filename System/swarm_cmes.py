#!/usr/bin/env python3
"""
Cross‑Modal Embedding Store (CMES)
Stores low‑dimensional embeddings for visual, audio, and text streams.
Provides cosine‑similarity lookup.
"""

import json
import time
import math
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple

_STORE = Path(".sifta_state/cmes.jsonl")
_DIM = 128  # embedding dimension


def _load_store() -> List[dict]:
    if not _STORE.exists():
        return []
    with _STORE.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _save_entry(entry: dict) -> None:
    with _STORE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def add_embedding(modality: str, source_id: str, vector: List[float]) -> None:
    """Add a new embedding to the store."""
    entry = {
        "ts": time.time(),
        "modality": modality,
        "source_id": source_id,
        "vec": vector,
    }
    _save_entry(entry)


def _norm(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    return v / norm if norm else v


def query_similar(modality: str, query_vec: List[float], top_k: int = 3) -> List[Tuple[str, float]]:
    """Return top‑k (source_id, similarity) for a given modality."""
    query = _norm(np.array(query_vec, dtype=float))
    candidates = [
        (e["source_id"], _norm(np.array(e["vec"], dtype=float)))
        for e in _load_store()
        if e["modality"] == modality
    ]
    if not candidates:
        return []
    sims = [(sid, float(np.dot(query, vec))) for sid, vec in candidates]
    sims.sort(key=lambda x: x[1], reverse=True)
    return sims[:top_k]


if __name__ == "__main__":
    # Demo: add a random visual embedding and query it
    import random
    vec = [random.random() for _ in range(_DIM)]
    add_embedding("visual", "frame_001", vec)
    print(query_similar("visual", vec))
