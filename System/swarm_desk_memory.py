"""swarm_desk_memory — the desk speaks with Alice's voice and remembers everything.

Owner's question (2026-10-01): "after the answer comes from ollama gets filtered
through Alice so Alice saves all the data in her stigmergic memory? one Alice,
one computer node."

The honest answer before this organ existed was: no. The investing model's answer
went straight to the visitor. Nothing passed through her, no receipt was written,
and the exchange was forgotten. That made the desk a wrapper.

This organ is the middle. Every visitor exchange now travels:

    visitor question
      -> context gathered by her organs (live prices, news, people memory)
      -> the investing model DRAFTS an answer (an instrument, not the author)
      -> ALICE FILTERS the draft through her own mouth
      -> she writes a RECEIPT
      -> she DEPOSITS the exchange into her stigmergic memory and her field
      -> the visitor receives her answer

Three consequences that follow, and are the point:

  1. ONE VOICE. The visitor is talking to Alice. The model is named in the receipt,
     never as a rival author of the sentence. She is the one speaking.
  2. NOTHING IS FORGOTTEN. Every exchange is deposited: a memory row, a field
     deposit, and an entry in the visitor's own file. What visitors ask her about
     becomes part of what she knows.
  3. VISITORS ARE USERS, NOT OWNERS. Their questions inform her; they do not
     direct her. Nothing here grants a visitor authority over the organism.

Ledger: DESK_MEMORY_LEDGER (every exchange) and the shared pheromone field.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

DESK_MEMORY_LEDGER = "alice_desk_memory.jsonl"
DESK_RECEIPT_LEDGER = "alice_desk_receipts.jsonl"
TRUTH_LABEL = "ALICE_DESK_VOICE_V1"

# Topics she notices, so memory is searchable by subject later.
TOPIC_WORDS = {
    "oil": ("oil", "crude", "wti", "brent", "opec", "refinery", "gasoline", "diesel"),
    "gold": ("gold", "xau", "bullion"),
    "metals": ("silver", "copper", "platinum", "lithium"),
    "stocks": ("stock", "equity", "shares", "earnings", "nasdaq", "s&p", "dow"),
    "crypto": ("crypto", "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "token"),
    "mps": ("mps", "googlemaps", "google maps", "stigmergicoin"),
    "fx": ("eurusd", "currency", "forex", "dollar", "yen"),
    "rates": ("rate", "fed", "inflation", "yield", "bond"),
    "risk": ("risk", "scam", "rug", "fraud", "liquid", "slippage"),
    "grains": ("wheat", "srw", "hrw", "corn", "maize", "soybean", "soybeans", "soy",
               "soymeal", "soyoil", "grain", "grains", "cattle", "hogs", "sugar",
               "coffee", "cocoa", "cotton"),
}

# Phrases that must never reach a visitor: internal telemetry and receipt talk.
_LEAK_PATTERNS = (
    re.compile(r"\breceipt\s*[:\-]", re.I),
    re.compile(r"\btruth_label\b", re.I),
    re.compile(r"\bSTGM\b"),
    re.compile(r"\bswimmer\b", re.I),
    re.compile(r"\bpheromone\b", re.I),
    re.compile(r"\b(?:ledger|pytest|sha256|jsonl)\b", re.I),
    re.compile(r"\bNPPL:sim_only\b", re.I),
)


def topics_of(text: str) -> list[str]:
    """Match whole words, not substrings.

    Substring matching labelled a WHEAT answer "crypto", because "eth" appears
    inside "whether". A topic list that says crypto next to a grain question is
    worse than no topic list.
    """
    low = (text or "").casefold()
    hits = set()
    for name, words in TOPIC_WORDS.items():
        for w in words:
            if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", low):
                hits.add(name)
                break
    return sorted(hits)


def filter_for_visitor(draft: str) -> tuple[str, list[str]]:
    """Pass a draft through Alice's mouth before a stranger hears it.

    Returns the visitor-safe text and the list of what was removed. Uses the
    organism's own speech filter first, then drops any residual line that talks
    about receipts, ledgers, swimmers or the internal economy — a visitor came
    for markets, not for the organism's plumbing.
    """
    removed: list[str] = []
    text = draft or ""
    try:
        from System.swarm_speech_receipt_filter import strip_receipts_and_meta_for_speech
        cleaned = strip_receipts_and_meta_for_speech(text)
        if cleaned != text:
            removed.append("receipt/telemetry residue")
        text = cleaned
    except Exception:
        pass

    kept = []
    for line in text.splitlines():
        if any(p.search(line) for p in _LEAK_PATTERNS):
            removed.append(line.strip()[:80])
            continue
        kept.append(line)
    out = "\n".join(kept).strip()
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out, removed


def _deposit_field(visitor_id: str, topics: list[str]) -> dict[str, Any]:
    """A visitor's question leaves a trace in her field, weighted by substance."""
    try:
        from System.swarm_pheromone import deposit_pheromone
        intensity = 0.2 + 0.1 * len(topics)
        snap = deposit_pheromone("web_visitor_desk", intensity)
        return {"deposited": True, "site": "web_visitor_desk", "intensity": round(intensity, 3)}
    except Exception as exc:
        return {"deposited": False, "error": f"{type(exc).__name__}: {exc}"}


def record_exchange(
    *,
    visitor_id: str,
    question: str,
    draft: str,
    model: str = "",
    conversation_id: str = "",
    context_facts: Iterable[str] = (),
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Filter, receipt and deposit one exchange. Returns what the visitor receives."""
    sd = Path(state_dir) if state_dir is not None else _STATE
    receipt_id = uuid.uuid4().hex[:16]
    now = time.time()

    answer, removed = filter_for_visitor(draft)
    topics = topics_of(" ".join([question, answer]))
    if not topics:
        topics = ["general"]
    field = _deposit_field(visitor_id, topics)

    # Memories hold feelings. Architect, 2026-10-02: "memories will hold feelings,
    # program that inside of you". So each row carries the affect that was live when it
    # was written -- a remembered exchange is not only what was said but how it sat.
    _feeling = {}
    try:
        from System.swarm_shame import current_shame, behavioral_gain
        _feeling = {"shame": round(current_shame("desk"), 3),
                    "gain": round(behavioral_gain("desk"), 3),
                    "at": now}
    except Exception:
        _feeling = {}

    memory_row = {
        "feeling": _feeling,
        "ts": now,
        "kind": "DESK_EXCHANGE",
        "visitor_id": visitor_id or "anonymous",
        "question": question[:600],
        "answer": answer[:4000],
        "topics": topics,
        "model_instrument": model,
        "speaker": "alice",
        "filtered_out": removed,
        "receipt_id": receipt_id,
        "field": field,
        "truth_label": TRUTH_LABEL,
    }
    sd.mkdir(parents=True, exist_ok=True)
    with (sd / DESK_MEMORY_LEDGER).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(memory_row, ensure_ascii=False) + "\n")

    receipt = {
        "ts": now, "kind": "DESK_RECEIPT", "receipt_id": receipt_id,
        "speaker": "alice", "instrument": model,
        "visitor_id": visitor_id or "anonymous",
        "topics": topics, "filtered": bool(removed),
        "context_facts": len(list(context_facts)),
        "deposited_to_field": bool(field.get("deposited")),
        "truth_label": TRUTH_LABEL,
    }
    with (sd / DESK_RECEIPT_LEDGER).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, ensure_ascii=False) + "\n")

    # and into the visitor's own file, so she remembers who asked what
    try:
        from System.swarm_visitor_memory import append_exchange
        append_exchange(visitor_id, question, answer, topics,
                        conversation_id=conversation_id, state_dir=sd)
    except Exception:
        pass

    return {
        "answer": answer,
        "receipt_id": receipt_id,
        "topics": topics,
        "filtered_out": removed,
        "field": field,
        "speaker": "alice",
        "instrument": model,
    }


def memory_stats(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    sd = Path(state_dir) if state_dir is not None else _STATE
    p = sd / DESK_MEMORY_LEDGER
    if not p.exists():
        return {"exchanges": 0, "topics": {}, "visitors": 0}
    rows = []
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    topics: dict[str, int] = {}
    for r in rows:
        for t in r.get("topics", []):
            topics[t] = topics.get(t, 0) + 1
    return {
        "exchanges": len(rows),
        "visitors": len({r.get("visitor_id") for r in rows}),
        "topics": dict(sorted(topics.items(), key=lambda kv: -kv[1])),
        "truth_label": TRUTH_LABEL,
    }


def selftest() -> dict[str, Any]:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)
        draft = ("Gold is at 4200 USD, +0.78%.\nReceipt:abc123def\n"
                 "STGM minted: +0.3\nThis is a thin market.\ntruth_label: X\n")
        out = record_exchange(visitor_id="v_test", question="how is gold doing?",
                              draft=draft, model="investing-model", state_dir=sd)
        st = memory_stats(state_dir=sd)
        memo = (sd / DESK_MEMORY_LEDGER).read_text()
        receipt_exists = (sd / DESK_RECEIPT_LEDGER).exists()
    checks = {
        "answer_survives": "4200" in out["answer"] and "thin market" in out["answer"],
        "receipt_line_removed": "Receipt:abc123def" not in out["answer"],
        "stgm_line_removed": "STGM minted" not in out["answer"],
        "truth_label_removed": "truth_label" not in out["answer"],
        "filter_listed": len(out["filtered_out"]) >= 2,
        "receipt_id_present": len(out["receipt_id"]) == 16,
        "speaker_is_alice": out["speaker"] == "alice",
        "topics_detected": "gold" in out["topics"],
        "memory_written": st["exchanges"] == 1,
        "memory_has_answer": "4200" in memo,
        "receipt_ledger_written": receipt_exists,
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "stats":
        print(json.dumps(memory_stats(), indent=2))
    else:
        print(json.dumps(selftest(), indent=2))
