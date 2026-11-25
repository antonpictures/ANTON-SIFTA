#!/usr/bin/env python3
"""swarm_substrate_awareness.py — Stage 3: Alice Space awareness (read + write bridge).

Stage 3 is NOT a new memory store. It connects the three organs that already
exist so a single call gives Alice grounded awareness:

    StigmergicMemoryBus  (canonical writes, ledger of record)
            +
    swarm_substrate_bridge  (semantic recall over that ledger)
            +
    swarm_universal_substrate  (shared latent space, organ registry)

Public API
----------
alice_space_context_block(query, top_k=3)
    Text block for a system prompt: semantic recall from the ledger + substrate
    state + which organs are in the shared space. Safe: never raises.

remember_in_alice_space(text, organ, app_context)
    One write that goes to the canonical ledger (StigmergicMemoryBus.remember)
    AND appends the vector to the live semantic index, plus a receipt line.
    No parallel ledger is created.

substrate_awareness_snapshot()
    Dict of what the substrate knows right now (index size, organs, adapters,
    memory counts), for `alice_consciousness_check` style callers.

CLI
---
  python3 System/swarm_substrate_awareness.py context "what did George say about RTX"
  python3 System/swarm_substrate_awareness.py remember "..." --organ AliceG4U
  python3 System/swarm_substrate_awareness.py snapshot

Receipts: .sifta_state/substrate/receipts.jsonl (append-only)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

STATE = REPO / ".sifta_state"
SUBSTRATE = STATE / "substrate"
INDEX_DIR = SUBSTRATE / "ledger_index"
VEC_PATH = INDEX_DIR / "vectors.npy"
IDS_PATH = INDEX_DIR / "ids.json"
RECEIPTS = SUBSTRATE / "receipts.jsonl"

TRUTH = "ALICE_SPACE_AWARENESS_V1"


# ── Receipts ──────────────────────────────────────────────────────────────────

def _receipt(kind: str, payload: dict) -> dict:
    SUBSTRATE.mkdir(parents=True, exist_ok=True)
    row = {
        "truth": TRUTH,
        "kind": kind,
        "ts": time.time(),
        **payload,
    }
    RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
    with RECEIPTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


# ── Snapshot ──────────────────────────────────────────────────────────────────

def substrate_awareness_snapshot() -> dict:
    """What the substrate knows right now. All fields honest — missing = null."""
    snap: dict = {"truth": TRUTH, "ts": time.time()}

    # Index
    try:
        if VEC_PATH.exists() and IDS_PATH.exists():
            import numpy as np
            mat = np.load(VEC_PATH, mmap_mode="r")
            meta = json.loads(IDS_PATH.read_text())
            snap["ledger_index"] = {
                "vectors": int(mat.shape[0]),
                "dim": int(mat.shape[1]),
                "built_at": meta.get("built_at"),
                "source": meta.get("source"),
            }
        else:
            snap["ledger_index"] = None
    except Exception as e:
        snap["ledger_index"] = {"error": str(e)[:120]}

    # Organ registry
    try:
        from System.swarm_substrate_ingest import status as _ingest_status
        snap["indexes"] = _ingest_status()
    except Exception as e:
        snap["indexes"] = {"error": str(e)[:120]}

    try:
        from System.swarm_universal_substrate import list_organs, AliceSpace
        organs = list_organs()
        snap["organs"] = {
            name: {
                "native_dim": info.get("native_dim"),
                "has_adapter": bool(info.get("adapter_path")),
            }
            for name, info in organs.items()
        }
        space = AliceSpace()
        snap["alice_space"] = space.stats()
    except Exception as e:
        snap["organs"] = {"error": str(e)[:120]}

    # Adapter files on disk (source of truth, registry can lag)
    try:
        adir = SUBSTRATE / "adapters"
        snap["adapter_files"] = sorted(p.stem for p in adir.glob("*.pt")) if adir.exists() else []
    except Exception:
        snap["adapter_files"] = []

    # Canonical ledger
    try:
        ledger = STATE / "memory_ledger.jsonl"
        snap["ledger_rows"] = (
            sum(1 for line in ledger.open(encoding="utf-8", errors="replace") if line.strip())
            if ledger.exists() else 0
        )
    except Exception:
        snap["ledger_rows"] = None

    # r725 STIGMERGIC_CONSCIOUSNESS trace-hash loop + self-vector delta
    try:
        from System.swarm_memory_consciousness_bridge import verify_latest_bridge

        cb = verify_latest_bridge()
        snap["consciousness_bridge"] = {
            "ok": cb.get("ok"),
            "bridge_trace_id": cb.get("bridge_trace_id"),
            "memory_trace_id": cb.get("memory_trace_id"),
            "self_vector_changed": cb.get("self_vector_changed"),
            "observed_hash": str(cb.get("observed_hash") or "")[:16],
        }
    except Exception as e:
        snap["consciousness_bridge"] = {"error": str(e)[:120]}

    # Restart continuity capsule + AGI eval matrix organ/connection census
    try:
        from System.swarm_memory_archive_capsules import latest_capsule

        cap = latest_capsule()
        snap["restart_capsule"] = {
            "capsule_id": cap.get("capsule_id"),
            "source": cap.get("source"),
            "ts": cap.get("ts"),
        } if cap else None
    except Exception:
        snap["restart_capsule"] = None

    try:
        from System.swarm_agi_eval_matrix import organ_facts

        snap["body_organs"] = organ_facts()
    except Exception:
        snap["body_organs"] = None

    return snap


# ── Read: context block ───────────────────────────────────────────────────────

def _superseded_ledger_ids() -> set[str]:
    """Trace IDs in memory_ledger.jsonl that have been superseded by a newer trace."""
    try:
        from System.memory_search import load_jsonl_rows, superseded_trace_id_set

        ledger = STATE / "memory_ledger.jsonl"
        if not ledger.exists():
            return set()
        return superseded_trace_id_set(load_jsonl_rows([ledger]))
    except Exception:
        return set()


def semantic_recall_safe(query: str, top_k: int = 3, *, reinforce_fitness: bool = True) -> list[dict]:
    """Merge semantic hits from every Alice Space view (ledger + journal + narrative).

    Connected to:
      * memory_search.superseded_trace_id_set — excludes superseded traces
      * memory_fitness_overlay.strength_for / bump_after_recall — stigmergic fitness
        weighting and post-recall reinforcement
    """
    if not query.strip():
        return []
    merged: list[dict] = []
    try:
        import math
        from System.swarm_substrate_bridge import _load_encoder, _native_vector
        from System.swarm_substrate_ingest import VIEWS, recall, hydrate

        tok, model = _load_encoder()
        q = _native_vector(query, tok, model)
        superseded = _superseded_ledger_ids()
        for view in VIEWS:
            raw_hits = hydrate(recall(view, q, top_k=max(top_k * 2, 6)))
            if view == "ledger" and superseded:
                raw_hits = [h for h in raw_hits if str(h.get("id") or "") not in superseded]
            merged.extend(raw_hits)

        # Stigmergic fitness overlay weighting for ledger traces
        try:
            from System.memory_fitness_overlay import strength_for

            ledger_ids = [str(h.get("id") or "") for h in merged if h.get("view") == "ledger" and h.get("id")]
            strengths = strength_for(ledger_ids) if ledger_ids else {}
        except Exception:
            strengths = {}

        for h in merged:
            sim = float(h.get("similarity", 0.0))
            tid = str(h.get("id") or "")
            strength = float(strengths.get(tid, 1.0)) if h.get("view") == "ledger" else 1.0
            mult = max(0.75, min(1.35, 0.85 + 0.15 * math.sqrt(max(0.01, strength))))
            h["fitness_strength"] = round(strength, 3)
            h["score"] = sim * mult

        merged.sort(key=lambda h: h.get("score", h.get("similarity", 0.0)), reverse=True)
        top = merged[:top_k]
        if reinforce_fitness:
            try:
                from System.memory_fitness_overlay import bump_after_recall

                for h in top:
                    if h.get("view") == "ledger" and h.get("id"):
                        bump_after_recall(str(h["id"]), recall_delta=0.02)
            except Exception:
                pass
        if top:
            return top
    except Exception:
        pass
    # Fallback: the original single-view bridge (kept for a damaged ingest index).
    try:
        from System.swarm_substrate_bridge import semantic_recall
        return semantic_recall(query, top_k=top_k)
    except Exception:
        return []


def alice_space_context_block(query: str, top_k: int = 3,
                              include_snapshot: bool = False) -> str:
    """Prompt-ready block. Returns "" when the substrate has nothing — never fake."""
    hits = [h for h in semantic_recall_safe(query, top_k=top_k) if h.get("text")]
    if not hits and not include_snapshot:
        return ""

    # Corrections first: a repeated mistake is more expensive than a missing fact.
    blocks: list[str] = []
    try:
        from System.swarm_substrate_corrections import corrections_block

        corr = corrections_block(query=query, top_k=2)
        if corr:
            blocks.append(corr)
    except Exception:
        pass

    lines = ["[ALICE SPACE — semantic recall from my own memory ledger + Journal]"]
    for h in hits:
        ts = h.get("timestamp")
        ago = ""
        if ts:
            ago_s = max(0.0, time.time() - float(ts))
            ago = f", {ago_s/3600:.0f}h ago" if ago_s > 3600 else f", {ago_s/60:.0f}m ago"
        lines.append(
            f"- (sim {h['similarity']:.2f}, {h.get('view') or h.get('app') or '?'}{ago}) "
            f"\"{str(h['text'])[:160]}\""
        )

    try:
        snap = substrate_awareness_snapshot()
        organs = snap.get("organs") or {}
        if isinstance(organs, dict) and organs and "error" not in organs:
            ready = [n for n, v in organs.items() if v.get("has_adapter")]
            lines.append(
                f"[substrate: {len(ready)} organ(s) in shared space"
                + (f" ({', '.join(sorted(ready))})" if ready else "")
                + f"; indexes={ {k: v.get('rows') for k, v in (snap.get('indexes') or {}).items()} }]"
            )
    except Exception:
        pass

    lines.append("[END ALICE SPACE]")
    if blocks:
        return "\n".join([*blocks, "\n".join(lines)])
    return "\n".join(lines)


# ── Write: remember ───────────────────────────────────────────────────────────

def _append_to_index(text: str, trace_id: str) -> Optional[int]:
    """Append one text to the live semantic index. Returns new row count or None."""
    if not VEC_PATH.exists() or not IDS_PATH.exists():
        return None
    try:
        import numpy as np
        from System.swarm_substrate_bridge import _load_encoder, _native_vector
        tok, model = _load_encoder()
        vec = np.asarray(_native_vector(text, tok, model), dtype=np.float32).reshape(1, -1)
        mat = np.load(VEC_PATH)
        if mat.shape[1] != vec.shape[1]:
            return None  # dimension drift — caller should rebuild
        mat = np.vstack([mat, vec])
        np.save(VEC_PATH, mat)
        meta = json.loads(IDS_PATH.read_text())
        meta["ids"].append(trace_id)
        meta["appended"] = meta.get("appended", 0) + 1
        IDS_PATH.write_text(json.dumps(meta, ensure_ascii=False))
        return int(mat.shape[0])
    except Exception as e:
        _receipt("index_append_failed", {"text": text[:120], "error": str(e)[:160]})
        return None


def remember_in_alice_space(text: str, organ: str = "AliceG4U",
                            app_context: str = "alice_space",
                            architect_id: str = "IOAN_M5",
                            evidence_links: Optional[list[str]] = None) -> dict:
    """Write through the canonical bus + r725 consciousness bridge, then append to the live index.

    Returns {ok, trace_id, bridge_trace_id, self_vector_changed, index_rows, receipt_ts}.
    Raises only on empty text.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("remember_in_alice_space needs non-empty text")

    trace_id = None
    bridge_trace_id = None
    self_vector_changed = None
    try:
        from System.swarm_memory_consciousness_bridge import bridge_observed_memory_to_consciousness

        cb = bridge_observed_memory_to_consciousness(
            text,
            observer=organ or "Alice",
            architect_id=architect_id,
            app_context=app_context,
            evidence_links=evidence_links,
        )
        trace_id = cb.get("memory_trace_id")
        bridge_trace_id = cb.get("trace_id")
        self_vector_changed = cb.get("self_vector_changed")
    except Exception:
        try:
            from System.stigmergic_memory_bus import StigmergicMemoryBus
            bus = StigmergicMemoryBus(architect_id=architect_id)
            trace = bus.remember(text, app_context, links=evidence_links)
            trace_id = getattr(trace, "trace_id", None)
        except Exception as e:
            _receipt("canonical_write_failed", {"text": text[:120], "error": str(e)[:160]})

    rows = _append_to_index(text, trace_id or f"substrate_{int(time.time())}")
    receipt = _receipt("remember", {
        "organ": organ,
        "app_context": app_context,
        "trace_id": trace_id,
        "bridge_trace_id": bridge_trace_id,
        "self_vector_changed": self_vector_changed,
        "index_rows": rows,
        "text": text[:160],
    })
    return {
        "ok": bool(trace_id),
        "trace_id": trace_id,
        "bridge_trace_id": bridge_trace_id,
        "self_vector_changed": self_vector_changed,
        "index_rows": rows,
        "receipt_ts": receipt["ts"],
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    if cmd == "snapshot":
        print(json.dumps(substrate_awareness_snapshot(), indent=2))
    elif cmd == "context":
        q = " ".join(sys.argv[2:]) or "Alice"
        block = alice_space_context_block(q, include_snapshot=True)
        print(block or "(no recall)")
    elif cmd == "remember":
        rest = sys.argv[2:]
        organ = "AliceG4U"
        if "--organ" in rest:
            i = rest.index("--organ")
            organ = rest[i + 1] if i + 1 < len(rest) else organ
            rest = rest[:i] + rest[i + 2:]
        text = " ".join(rest).strip()
        if not text:
            print("usage: remember <text> [--organ NAME]")
            raise SystemExit(2)
        print(json.dumps(remember_in_alice_space(text, organ=organ), indent=2))
    else:
        print("usage: snapshot | context <query> | remember <text> [--organ NAME]")
