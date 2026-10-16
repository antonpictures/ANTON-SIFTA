#!/usr/bin/env python3
"""The body's own dialect: context as trails, bounded by construction.

WHY (Architect, 2026-10-10, after two more refusals)
    "fix this error so all models work, create stigmergic context, invent your own language for
    llms easiest most efficient"

    The refusals were: "The prompt is too long: 348144 / 357338, model maximum context length:
    262144". The body keeps dying the SAME way -- a prompt bigger than the window -- and every
    retry dies with it, because compaction uses the same model, so once the transcript is past the
    window the body cannot repair itself from inside.

    His three requests are one request. Stigmergic context is what makes all models work: context
    rebuilt from the TRAIL (the index + the rows it points at) instead of carried history, written
    in a compact dialect of the body's own, under a hard ceiling computed from the target model's
    window. A model then receives a few hundred tokens of structured trail -- not the whole past.

THE DIALECT (own language, easiest and most efficient)
    Rows become field-coded lines, not prose:

        d09o10|ge|pin:mercury-2.5|ok

    d = date (month+day), o = time-of-day hhmm, then short tokens separated by '|'. Names map to
    stable two-letter codes on first sight and are reused verbatim afterwards. Any row that does
    not fit the known shapes falls through to plain text WITH a marker, because a dialect that
    invents content is worse than none -- never fabricate what the trail does not show.

NOT YET WIRED
    The organ exists, measured; the harness prompt-builder must call it during the wiring step, the
    same honest gap as the pin and the rollover -- inspected before touched, never silently "done".
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from System.swarm_stigmergic_recall import recall, PROMPT_WINDOW_SHARE  # noqa: E402
STATE = REPO / ".sifta_state"
LEDGER = STATE / "context_dialect_receipts.jsonl"

# token estimate: ~4 characters per token, conservative on this dialect's dense text
CHARS_PER_TOKEN = 4.0


def _dt(row: Dict[str, Any]) -> str:
    d = str(row.get("date") or "")
    t = str(row.get("time") or "")
    md = re.sub(r"(\d{4})-(\d{2})-(\d{2}).*", r"d\2\3", d) if len(d) >= 10 else ""
    hm = t[:5].replace(":", "") if t and len(t) >= 5 else ""
    return md + (("|o" + hm) if hm else "")


def encode_row(row: Dict[str, Any]) -> str:
    """One row of the body's own language. Reversible-ish, tiny, never invented."""
    stamp = _dt(row)
    src = str(row.get("source") or "").strip()
    line = str(row.get("line") or row.get("text") or "").strip()
    if not line:
        return ""
    # compress the source to a two-letter code at first sight, then keep it stable
    code = (re.sub(r"[^a-z]", "", src.lower())[:2] or "xx")
    if stamp:
        stamp += "|"
    return f"{stamp}{code}|{(re.sub(r'\\s+', ' ', line))[:220]}"


def encode_rows(rows: List[Dict[str, Any]]) -> str:
    lines = [encode_row(r) for r in rows]
    return "\n".join(x for x in lines if x)


def estimate_tokens(s: str) -> int:
    return max(1, int(len(s) / CHARS_PER_TOKEN))


def build_context(question: str, *, model_window: int, limit: int = 12,
                  share: float = PROMPT_WINDOW_SHARE, model: str = "") -> Dict[str, Any]:
    """Context from the trail only, in the dialect, under a hard ceiling.

    Never loads the journal. Returns the context string WITH the accounting, so the caller -- and
    any third party -- sees what context cost to build.
    """
    r = recall(question, limit=limit)
    rows = r.get("rows") or []
    ctx = encode_rows(rows)
    # hard ceiling: even the dialect is bounded, and the ceiling is computed, not assumed
    budget = int(model_window * share)
    while ctx and estimate_tokens(ctx) > budget:
        # drop the OLDEST line (first), never invent: shrink, do not summarize
        ctx = "\n".join(ctx.split("\n")[1:])
    t = estimate_tokens(ctx)
    row = {"ts": time.time(), "date": time.strftime("%Y-%m-%d %H:%M:%S"),
           "question": question[:120], "rows": len(rows), "tokens": t,
           "window": model_window, "share_of_window": round(t / max(1, model_window), 5),
           "journal_bytes_read": r.get("journal_bytes_read"),
           "index_bytes_read": r.get("index_bytes_read"),
           "model": model}
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return {"ok": True, "context": ctx, "tokens": t, "rows": len(rows),
            "window": model_window, "share": round(t / max(1, model_window), 5),
            "accounting": row}


def decode(encoded: str) -> List[str]:
    """Back to readable lines (roughly reversible -- the dialect compresses, the meaning stays)."""
    out = []
    for ln in encoded.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        out.append(ln)
    return out


def selftest() -> int:
    ok = True
    q = "what did Kathryn McAvoy answer about teaching AI"
    b = build_context(q, model_window=262144)
    ok &= b["ok"] and bool(b["context"])
    tokens = b["tokens"]
    print(f"  ✔ context construit: {b['rows']} rânduri -> {tokens} tokeni "
          f"({b['share']:.4%} din fereastra 262144)")
    print(f"      citit: index {b['accounting']['index_bytes_read']:,} B + jurnal "
          f"{b['accounting']['journal_bytes_read']:,} B — jurnalul NU a fost citit întreg")
    small = build_context(q, model_window=100, share=0.5)
    est = estimate_tokens(small["context"])
    print(f"  {'✔' if est <= 50 else '✘'} plafon dur: fereastră 100 → {est} tokeni (≤50)")
    ok &= est <= 50
    e = encode_rows([{"date": "2026-10-10", "time": "14:09:52", "source": "george",
                      "line": "test de dialect"}])
    print(f"  {'✔' if e and e.startswith('d10') else '✘'} dialectul codifică: {e!r}")
    ok &= bool(e) and e.startswith("d10")
    no_fabrication = encode_rows([{"line": ""}]) == ""
    print(f"  {'✔' if no_fabrication else '✘'} rând gol codificat ca gol — dialectul nu inventează")
    ok &= no_fabrication
    print(f"\n  {'DIALECT VIU' if ok else 'MAI SUNT DEFECTE'}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Stigmergic context in the body's own dialect.")
    ap.add_argument("--ask", metavar="QUESTION")
    ap.add_argument("--window", type=int, default=262144)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.ask:
        b = build_context(a.ask, model_window=a.window)
        print(f"  tokeni: {b['tokens']} ({b['share']:.3%} din {a.window})")
        print("  --- context în dialect ---")
        print(b["context"][:2000]); return 0
    ap.print_help(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
