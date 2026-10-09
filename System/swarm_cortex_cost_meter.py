#!/usr/bin/env python3
"""What a cortex run costs, in USD, per run -- measured, not estimated.

WHY
    Architect, 2026-10-09: "we have $100 in credits, I want to see how much this cortex charges our
    API per run in US dollars."

    An estimate is not a receipt. This sends a real request, reads the token counts the API itself
    reports in `usage`, multiplies by the published per-million prices, and appends one row per run
    to .sifta_state/cortex_cost.jsonl. The Architect can then see, in dollars, what one turn on this
    cortex costs and how much of the 100 is left.

PRICES -- and how much to trust them
    Gemini 3.5 Flash-Lite, taken from https://ai.google.dev/gemini-api/docs/pricing on 2026-10-09:
      input   $0.30 per 1,000,000 tokens   (the page labels this cell "Input price")
      output  $2.50 per 1,000,000 tokens   (the adjacent cell; see PRICE_CONFIDENCE below)
    The input price is read off a labelled cell. The output price is the next number in the same
    table block, which matches the shape of every other Flash-Lite table, but it was NOT read off a
    label. That difference is recorded rather than smoothed over.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

REPO = pathlib.Path(__file__).resolve().parent.parent
LEDGER = REPO / ".sifta_state" / "cortex_cost.jsonl"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

# price per 1M tokens, USD
PRICES: Dict[str, Dict[str, float]] = {
    "gemini-3.5-flash-lite": {"in": 0.30, "out": 2.50},
    "gemini-3.7-flash": {"in": 0.30, "out": 2.50},
    "gemini-3.8-flash": {"in": 0.30, "out": 2.50},
}
PRICE_CONFIDENCE = {
    "gemini-3.5-flash-lite": "input read from a labelled cell; output is the adjacent cell, unconfirmed",
}
CREDITS_TOTAL_USD = 100.0


def _key() -> str:
    k = os.environ.get("GEMINI_API_KEY", "")
    if k:
        return k
    cred = pathlib.Path.home() / ".dsh" / ".credentials.yaml"
    if cred.exists():
        try:
            import yaml
            d = yaml.safe_load(cred.read_text(encoding="utf-8")) or {}
            k = ((d.get("refs") or {}).get("GEMINI_API_KEY") or "")
        except Exception:
            k = ""
    return k


def usd_for(model: str, in_tokens: int, out_tokens: int) -> Optional[float]:
    p = PRICES.get(model)
    if not p:
        return None
    return (in_tokens / 1_000_000.0) * p["in"] + (out_tokens / 1_000_000.0) * p["out"]


def meter(model: str, prompt: str, max_tokens: int = 300, timeout: int = 180,
          write: bool = True) -> Dict[str, Any]:
    """One real request; the cost of THAT run, from the token counts the API reports."""
    key = _key()
    if not key:
        return {"ok": False, "error": "no GEMINI_API_KEY in env or ~/.dsh/.credentials.yaml"}
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        return {"ok": False, "error": f"HTTP {e.code}: {detail}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    elapsed = time.time() - t0
    usage = d.get("usage") or {}
    i_tok = int(usage.get("prompt_tokens") or 0)
    o_tok = int(usage.get("completion_tokens") or 0)
    cost = usd_for(model, i_tok, o_tok)
    text = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    row = {
        "ts": time.time(), "date": time.strftime("%Y-%m-%d"), "time": time.strftime("%H:%M:%S"),
        "model": model, "in_tokens": i_tok, "out_tokens": o_tok, "usd": cost,
        "seconds": round(elapsed, 2),
        "tok_per_s": round(o_tok / elapsed, 1) if elapsed > 0 else None,
        "price_confidence": PRICE_CONFIDENCE.get(model, "unknown"),
    }
    if write:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "row": row, "reply": text.strip()[:200]}


def totals() -> Dict[str, Any]:
    if not LEDGER.exists():
        return {"runs": 0, "usd": 0.0, "credits_total": CREDITS_TOTAL_USD,
                "credits_left": CREDITS_TOTAL_USD}
    runs = 0
    usd = 0.0
    per_model: Dict[str, float] = {}
    with LEDGER.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            runs += 1
            usd += float(r.get("usd") or 0.0)
            per_model[r.get("model", "?")] = per_model.get(r.get("model", "?"), 0.0) + float(r.get("usd") or 0.0)
    return {"runs": runs, "usd": round(usd, 6), "per_model": {k: round(v, 6) for k, v in per_model.items()},
            "credits_total": CREDITS_TOTAL_USD, "credits_left": round(CREDITS_TOTAL_USD - usd, 6)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Measure what one cortex run costs, in USD.")
    ap.add_argument("--test", action="store_true", help="one real run on gemini-3.5-flash-lite")
    ap.add_argument("--model", default="gemini-3.5-flash-lite")
    ap.add_argument("--prompt", default="Răspunde în română, o propoziție: ce ești?")
    ap.add_argument("--max-tokens", type=int, default=200)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--prices", action="store_true")
    a = ap.parse_args()

    if a.prices:
        for m, p in PRICES.items():
            print(f"  {m}: input ${p['in']}/1M, output ${p['out']}/1M")
            print(f"      încredere: {PRICE_CONFIDENCE.get(m, 'unknown')}")
        return 0
    if a.report:
        t = totals()
        print(f"  rulări măsurate : {t['runs']}")
        print(f"  cheltuit        : ${t['usd']:.6f}")
        print(f"  credite rămase  : ${t['credits_left']:.4f} din ${t['credits_total']:.2f}")
        for m, v in (t.get("per_model") or {}).items():
            print(f"    {m}: ${v:.6f}")
        if t["runs"] == 0:
            print("  (nicio rulare înregistrată încă — rulează --test)")
        return 0
    if a.test:
        r = meter(a.model, a.prompt, a.max_tokens)
        if not r.get("ok"):
            print(f"  ✘ {r.get('error')}")
            return 1
        row = r["row"]
        print("=" * 70)
        print(f"  model      : {row['model']}")
        print(f"  tokenuri   : {row['in_tokens']} in / {row['out_tokens']} out")
        print(f"  timp       : {row['seconds']}s   ({row['tok_per_s']} tok/s)")
        print(f"  COST       : ${row['usd']:.8f}")
        print(f"  încredere  : {row['price_confidence']}")
        print(f"  răspuns    : {r['reply'][:120]!r}")
        t = totals()
        print(f"  total      : ${t['usd']:.6f} din ${t['credits_total']:.2f}  ({t['runs']} rulări)")
        print("=" * 70)
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
