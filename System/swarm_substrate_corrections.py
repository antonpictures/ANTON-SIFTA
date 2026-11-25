#!/usr/bin/env python3
"""swarm_substrate_corrections.py — Stage 5: corrections of record, recallable by meaning.

The failure George named: "it is hard for you to learn due to bad llm design."
A correction fixes a turn; it does not fix the next session, because the weights
are fresh. This organ puts corrections where sessions die — in the body's memory —
and puts them FIRST in the awareness block so a repeat is harder than a recall.

Design constraints (AGENTS.md):
  * One medium. Corrections are ordinary ledger rows, app_context="correction",
    epistemic_label="OBSERVED" (George said it). No second store is created.
  * Receipts. Every write returns the bus trace and appends a substrate receipt.
  * Honest empty. No correction found for a query -> say nothing, never invent one.

Public API
    record_correction(text, wrong="", right="", receipt=None, doc=None) -> dict
    corrections_for(query, top_k=3) -> list[dict]
    corrections_block(query=None, top_k=3) -> str   # prompt-ready, "" when none

The text is indexed with a stable "CORRECTION (date):" prefix so recall can filter
it without extra metadata — the index stays a plain view over the ledger.

CLI
    python3 System/swarm_substrate_corrections.py record "..." [--wrong ...] [--right ...]
    python3 System/swarm_substrate_corrections.py recall "query"
    python3 System/swarm_substrate_corrections.py list
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
PREFIX = "CORRECTION"


def format_correction(text: str, wrong: str = "", right: str = "",
                      day: Optional[str] = None) -> str:
    day = day or time.strftime("%Y-%m-%d")
    parts = [f"{PREFIX} ({day}): {text.strip()}"]
    if wrong.strip():
        parts.append(f"WRONG: {wrong.strip()}")
    if right.strip():
        parts.append(f"RIGHT: {right.strip()}")
    return " — ".join(parts)


def record_correction(text: str, wrong: str = "", right: str = "",
                      receipt: Optional[str] = None, doc: Optional[str] = None,
                      architect_id: str = "IOAN_M5") -> dict:
    """Write one correction through the canonical bus + substrate receipt."""
    text = (text or "").strip()
    if not text:
        raise ValueError("record_correction needs non-empty text")

    line = format_correction(text, wrong, right)
    links: list[str] = []
    if receipt:
        links.append(f"receipt:{receipt}")
    if doc:
        links.append(f"doc:{doc}")

    trace_id = None
    bridge_trace_id = None
    self_vector_changed = None
    error = None
    try:
        from System.swarm_memory_consciousness_bridge import bridge_observed_memory_to_consciousness

        cb = bridge_observed_memory_to_consciousness(
            line,
            observer="George",
            architect_id=architect_id,
            app_context="correction",
            evidence_links=links or None,
        )
        trace_id = cb.get("memory_trace_id")
        bridge_trace_id = cb.get("trace_id")
        self_vector_changed = cb.get("self_vector_changed")
    except Exception:
        try:
            from System.stigmergic_memory_bus import StigmergicMemoryBus

            bus = StigmergicMemoryBus(architect_id=architect_id)
            trace = bus.remember(
                line,
                "correction",
                epistemic_label="OBSERVED",
                links=links or None,
            )
            trace_id = getattr(trace, "trace_id", None)
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:160]}"

    # Keep the semantic view current so the next session can find it.
    index_rows = None
    if trace_id:
        try:
            from System.swarm_substrate_awareness import _append_to_index

            index_rows = _append_to_index(line, trace_id)
        except Exception:
            pass

    receipt_row = {
        "truth": "ALICE_SPACE_CORRECTION_V1",
        "kind": "correction",
        "ts": time.time(),
        "trace_id": trace_id,
        "bridge_trace_id": bridge_trace_id,
        "self_vector_changed": self_vector_changed,
        "receipt": receipt,
        "doc": doc,
        "index_rows": index_rows,
        "text": line[:200],
        "error": error,
    }
    SUBSTRATE.mkdir(parents=True, exist_ok=True)
    with (SUBSTRATE / "receipts.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt_row, ensure_ascii=False) + "\n")

    return {"ok": bool(trace_id), "trace_id": trace_id,
            "bridge_trace_id": bridge_trace_id, "self_vector_changed": self_vector_changed,
            "index_rows": index_rows, "error": error, "text": line}


def _is_correction(row: dict) -> bool:
    return (
        str(row.get("text") or "").startswith(PREFIX)
        or row.get("app") == "correction"
        or row.get("app_context") == "correction"
    )


def _all_corrections() -> list[dict]:
    """Corrections straight from the ledger of record (newest first)."""
    path = STATE / "memory_ledger.jsonl"
    out: list[dict] = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("app_context") == "correction":
                out.append(row)
    out.sort(key=lambda r: float(r.get("timestamp") or 0), reverse=True)
    return out


def _core(text: str) -> str:
    """The statement itself, without the WRONG/RIGHT evidence tail."""
    for sep in (" — WRONG:", " — RIGHT:", " --doc "):
        if sep in text:
            text = text.split(sep, 1)[0]
    return text.strip()


def corrections_for(query: str, top_k: int = 3) -> list[dict]:
    """Corrections semantically nearest to the query. Empty is a valid answer.

    Ranks against the corrections themselves (not the whole ledger), so a
    correction cannot be crowded out by the 10k ordinary traces around it.
    """
    query = (query or "").strip()
    if not query:
        return []
    rows = _all_corrections()
    if not rows:
        return []
    try:
        import numpy as np
        from System.swarm_substrate_bridge import _load_encoder, _embed_batch

        tok, model = _load_encoder()
        q = np.asarray(_embed_batch(tok, model, [query])[0], dtype=np.float32)
        qn = q / (np.linalg.norm(q) or 1)

        texts = [str(r.get("raw_text") or "") for r in rows]
        cache = _vectors_cache([_core(t) for t in texts], tok, model)
        if cache.shape[1] != qn.shape[0]:
            return []
        sims = cache @ qn
        order = np.argsort(sims)[::-1][:top_k]
        return [
            {
                "text": texts[int(i)],
                "similarity": float(sims[int(i)]),
                "timestamp": rows[int(i)].get("timestamp"),
                "app": rows[int(i)].get("app_context"),
                "trace_id": rows[int(i)].get("trace_id"),
                "view": "ledger",
            }
            for i in order
            if texts[int(i)] and float(sims[int(i)]) >= 0.30
        ]
    except Exception:
        return []


def _vectors_cache(texts: list[str], tok, model):
    """Embed correction texts once; cache on disk keyed by text hash."""
    import hashlib
    import numpy as np
    from System.swarm_substrate_bridge import _embed_batch

    path = SUBSTRATE / "correction_vectors.npz"
    keys = [hashlib.sha256(t.encode()).hexdigest()[:16] for t in texts]
    missing = []
    store: dict[str, np.ndarray] = {}
    if path.exists():
        try:
            data = np.load(path)
            for k in data.files:
                store[k] = data[k]
        except Exception:
            store = {}
    for k, t in zip(keys, texts):
        if k not in store:
            missing.append((k, t))
    if missing:
        emb = _embed_batch(tok, model, [t for _, t in missing], batch_size=64)
        for (k, _), v in zip(missing, emb):
            store[k] = v.astype(np.float32)
        SUBSTRATE.mkdir(parents=True, exist_ok=True)
        np.savez(path, **store)
    mat = np.stack([store[k] for k in keys]).astype(np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    return mat / np.where(norms == 0, 1, norms)


def corrections_block(query: Optional[str] = None, top_k: int = 3) -> str:
    """Prompt block. Sourced from the ledger; never synthesised."""
    if query:
        rows = corrections_for(query, top_k=top_k)
        header = "[CORRECTIONS OF RECORD — nearest to this turn]"
    else:
        rows = [
            {
                "text": r.get("raw_text", ""),
                "similarity": None,
                "timestamp": r.get("timestamp"),
                "view": "ledger",
            }
            for r in _all_corrections()[:top_k]
        ]
        header = "[CORRECTIONS OF RECORD — most recent]"

    rows = [r for r in rows if r.get("text")]
    if not rows:
        return ""

    lines = [header]
    for r in rows:
        text = str(r.get("text"))[:200]
        if r.get("similarity") is not None:
            lines.append(f"- (sim {r['similarity']:.2f}) {text}")
        else:
            lines.append(f"- {text}")
    lines.append("[Do not repeat a corrected mistake. If a correction conflicts with this turn's plan, say so.]")
    return "\n".join(lines)


def sync_eval_verdicts() -> dict:
    """Sync George-labeled 'incorrect' verdicts from .sifta_state/eval/eval_verdicts.jsonl.

    Deduplicated by verdict trace_id (`receipt:<verdict_trace_id>` in links) so
    each human eval verdict is recorded once as a Correction of Record.
    """
    verdicts_path = STATE / "eval" / "eval_verdicts.jsonl"
    if not verdicts_path.exists():
        return {"ok": True, "added": 0, "reason": "no_eval_verdicts_file"}

    existing_links: set[str] = set()
    for row in _all_corrections():
        for link in row.get("links") or []:
            existing_links.add(str(link))

    try:
        from System.eval_talk_labeling_helper import resolve_conversation_ref, _row_text
    except Exception:
        resolve_conversation_ref = None
        _row_text = None

    added = 0
    synced_turns: list[str] = []
    with verdicts_path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                v = json.loads(line)
            except json.JSONDecodeError:
                continue
            if v.get("verdict") != "incorrect":
                continue
            v_trace = str(v.get("trace_id") or "").strip()
            if not v_trace or f"receipt:{v_trace}" in existing_links:
                continue

            turn_id = str(v.get("turn_id") or "?")
            failed_keys = list(v.get("failed_rubric_keys") or [])
            ref = str(v.get("conversation_ref") or "")
            bad_reply = ""
            if resolve_conversation_ref and _row_text and ref:
                try:
                    convo_row = resolve_conversation_ref(ref)
                    if convo_row:
                        bad_reply = _row_text(convo_row).replace("\n", " ").strip()[:180]
                except Exception:
                    bad_reply = ""

            rubric_str = ", ".join(failed_keys) if failed_keys else "rubric"
            statement = (
                f"Eval verdict {turn_id} failed [{rubric_str}] (labeled by {v.get('labeled_by', 'GEORGE')}): "
                "stay in direct first-person grounded conversation; never drift into third-person "
                "meta-summary, roleplay stage narration, or refusing owner context."
            )
            res = record_correction(
                statement,
                wrong=bad_reply or f"Turn {turn_id} ({ref}) failed {rubric_str}",
                right=f"Pass Hu rubric keys [{rubric_str}] with grounded first-person reply",
                receipt=v_trace,
                doc=ref or "eval_verdicts.jsonl",
            )
            if res.get("ok"):
                existing_links.add(f"receipt:{v_trace}")
                added += 1
                synced_turns.append(turn_id)

    return {"ok": True, "added": added, "turns": synced_turns}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "record":
        rest = sys.argv[2:]
        flags = {"--wrong": "", "--right": "", "--doc": "", "--receipt": ""}
        for flag in list(flags):
            if flag in rest:
                i = rest.index(flag)
                flags[flag] = rest[i + 1] if i + 1 < len(rest) else ""
                rest = rest[:i] + rest[i + 2:]
        text = " ".join(rest).strip()
        if not text:
            print("usage: record <text> [--wrong ...] [--right ...] [--doc ...] [--receipt ...]")
            raise SystemExit(2)
        print(json.dumps(record_correction(
            text,
            wrong=flags["--wrong"],
            right=flags["--right"],
            doc=flags["--doc"] or None,
            receipt=flags["--receipt"] or None,
        ), indent=2))
    elif cmd == "sync-eval":
        print(json.dumps(sync_eval_verdicts(), indent=2))
    elif cmd == "recall":
        q = " ".join(sys.argv[2:]) or "mistake"
        block = corrections_block(query=q)
        print(block or "(no correction of record matches)")
    elif cmd == "list":
        for r in _all_corrections()[:10]:
            print(f"  [{time.strftime('%Y-%m-%d', time.localtime(float(r.get('timestamp') or 0)))}] {str(r.get('raw_text'))[:160]}")
    else:
        print("usage: record <text> | sync-eval | recall <query> | list")
