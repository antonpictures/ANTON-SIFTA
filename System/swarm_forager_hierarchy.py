#!/usr/bin/env python3
"""Forager hierarchy — wing → room → drawer deposit overlay (SIFTA r207).

George 2026-05-31: port the GraphPalace *pattern*, not its runtime. The pattern that
fits is a hierarchical deposit (memory-palace style) laid as a thin overlay on top of
SIFTA's EXISTING append-only ledgers — not a new store. A trace is filed into:

    wing   — the broad territory it belongs to (owner / browser / code / ide /
             sensor / research / memory)
    room   — the place inside that wing (a domain, a module, a source app, a ledger kind)
    drawer — the exact slot (a trace id, a symbol, a URL path, or a content fingerprint)

This is classic memory-palace structure (and an HTN-ish locality), not GraphPalace
authority. It gives the Semantic A* forager (swarm_forager_semantic_astar) a structure
to traverse instead of scanning flat rows. Pure stdlib, deterministic, file-backed.
Delta=0: it only ADDS a `.sifta_state/forager_hierarchy.jsonl` lane; it changes no
existing recall path unless a reader opts in.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = "forager_hierarchy.jsonl"
TRUTH_LABEL = "FORAGER_HIERARCHY_V1"

WINGS = ("owner", "browser", "code", "ide", "sensor", "research", "memory")


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _slug(value: str, n: int = 64) -> str:
    s = re.sub(r"[^a-z0-9._/-]+", "-", str(value or "").strip().lower()).strip("-")
    return (s or "general")[:n]


def _fingerprint(text: str) -> str:
    return hashlib.sha1((text or "").strip().lower().encode("utf-8", "replace")).hexdigest()[:16]


def _row_text(row: dict[str, Any]) -> str:
    """Salient text of a trace for fingerprint + lexical match."""
    parts = []
    for k in ("text", "description", "title", "caption", "summary", "content",
              "note", "line", "query", "url", "symbol", "file", "name"):
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
    if not parts:
        # fall back to the whole row, minus volatile fields
        parts.append(json.dumps({k: v for k, v in row.items()
                                 if k not in ("ts", "trace_id", "receipt_id")},
                                ensure_ascii=False, sort_keys=True))
    return " ".join(parts)[:4000]


def _url_path(url: Any) -> str:
    try:
        u = urlparse(str(url or ""))
        return (u.path or "/").strip("/") or u.netloc
    except Exception:
        return ""


def classify_hierarchy(row: dict[str, Any]) -> dict[str, str]:
    """Deterministically file a trace into wing → room → drawer. Same content always
    lands in the same drawer fingerprint (so duplicates collapse)."""
    r = row if isinstance(row, dict) else {}
    text = _row_text(r)
    low = text.lower()
    kind = str(r.get("kind") or r.get("truth_label") or "").lower()

    # wing — most specific structural signal first, deterministic order.
    if any(k in r for k in ("symbol", "symbol_id", "file", "function", "class", "module")) or "code" in kind:
        wing = "code"
    elif r.get("url") or r.get("domain") or "browser" in kind:
        wing = "browser"
    elif r.get("doctor") or r.get("ide") or kind.startswith("ide_") or "ide_doctor" in low:
        wing = "ide"
    elif any(k in r for k in ("sensor", "camera", "visceral", "somatic")) or "sensor" in kind or "visceral" in kind:
        wing = "sensor"
    elif r.get("paper") or "arxiv" in low or "research paper" in low or "research" in kind:
        wing = "research"
    elif r.get("owner") or "owner" in kind or "carbon body" in low:
        wing = "owner"
    else:
        wing = "memory"

    room_raw = (r.get("domain") or _domain(r.get("url")) or r.get("module") or r.get("file")
                or r.get("source") or r.get("app") or r.get("ide") or kind or "general")
    room = _slug(str(room_raw))

    drawer_raw = (r.get("trace_id") or r.get("symbol_id") or r.get("symbol")
                  or _url_path(r.get("url")) or _fingerprint(text))
    drawer = _slug(str(drawer_raw))

    return {"wing": wing, "room": room, "drawer": drawer, "fingerprint": _fingerprint(text)}


def _domain(url: Any) -> str:
    try:
        return urlparse(str(url or "")).netloc.replace("www.", "")
    except Exception:
        return ""


def deposit_hierarchical_trace(
    row: dict[str, Any], *, ref: str = "", now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Deposit one trace into the hierarchy overlay. `ref` points back to the source
    ledger row (trace/receipt id) so the forager can fetch the full trace on a hit."""
    h = classify_hierarchy(row)
    entry = {
        "ts": float(now if now is not None else time.time()),
        "truth_label": TRUTH_LABEL,
        "wing": h["wing"], "room": h["room"], "drawer": h["drawer"],
        "fingerprint": h["fingerprint"],
        "ref": str(ref or row.get("trace_id") or row.get("receipt_id") or ""),
        "text": _row_text(row)[:600],
    }
    path = _state(state_dir) / LEDGER
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return entry


def load_hierarchy(*, state_dir: Optional[Path | str] = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with (_state(state_dir) / LEDGER).open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        return []
    return out


def hierarchy_counts(*, state_dir: Optional[Path | str] = None) -> dict[str, int]:
    """How many traces are filed per wing — a quick map of the palace."""
    from collections import Counter
    rows = load_hierarchy(state_dir=state_dir)
    return dict(Counter(r.get("wing", "memory") for r in rows))


__all__ = [
    "TRUTH_LABEL", "WINGS",
    "classify_hierarchy",
    "deposit_hierarchical_trace",
    "load_hierarchy",
    "hierarchy_counts",
]
