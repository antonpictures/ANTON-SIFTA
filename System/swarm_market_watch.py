#!/usr/bin/env python3
"""Market reconnaissance watch — measure the AI-debt tells, daily.

Born 2026-10-21 after George accepted the recon plan on the CoreWeave /
AI-financing-architecture question (George Noble interview, David Lin show).
The organ measures what is cheaply measurable every check and holds the
manual tells (those needing judgment) with their last recorded values.

The five tells of the 2006-housing analogy for the AI trade:
  T1 CRWV distance from 52-week high (price momentum of the collateral)
  T2 CRWV/Oracle debt signals — rating actions, yield on new issues (manual)
  T3 Anthropic/OpenAI IPO timing (the "rate of appreciation" of AI private
     rounds; OpenAI pushed to 2027; Anthropic ~Nov)
  T4 Neocloud bond issues clearing yield (>=15% = architecture seizing)
  T5 Post-election volatility shift (manipulation incentives change)

A reading that cannot be fetched is recorded as missing — never invented.
Every check files a receipt to ``.sifta_state/market_watch_receipts.jsonl``.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = Path(os.environ.get("SIFTA_STATE_DIR") or _REPO / ".sifta_state")
RECEIPTS_PATH = _STATE / "market_watch_receipts.jsonl"

QUOTE_URL = "https://stockanalysis.com/stocks/CRWV/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15")

_MANUAL_TELLS = {
    "T2_debt_signal": "Oracle/CRWV rating actions; new-issue yields (check Fitch/Moody's headlines)",
    "T3_ipo_rate_of_appreciation": "Anthropic IPO status (~Nov); OpenAI pushed to 2027",
    "T4_neocloud_bond_yield": "latest neocloud (IREN/NBIS/CIFR/CRWV) issue yield; >=15% = seizing",
    "T5_post_election_vol": "volatility regime after election day",
}


# ------------------------------------------------------------- fetch/parse --

def _fetch_html(url: str = QUOTE_URL, timeout: float = 15.0) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


def _parse_quote(html: Optional[str]) -> Dict[str, Any]:
    """Pull price/%-from-high/mcap from the stockanalysis overview page.

    Patterns are defensive: any miss becomes None (missing, not invented).
    """
    out: Dict[str, Any] = {"price": None, "prev_close": None, "after_hours": None,
                           "market_cap_b": None, "wk52_high": None,
                           "pct_from_high": None, "target_price": None,
                           "next_earnings": None, "source_parsed": False}
    if not html:
        return out
    m = re.search(r"([\d,]+\.\d{2})\s*</h1>", html)
    price = re.search(r"^\s*\n?\s*(\d+\.\d{2})\s*$", html)  # placeholder
    # price: first number right after the ticker heading block
    pm = re.search(r"USD</p>.*?([\d,]+\.\d{2})", html, re.S)
    # simpler: og:description sometimes carries "price" — try several
    cand = re.findall(r">(\d{2,3}\.\d{2})<", html)
    if cand:
        try:
            out["price"] = float(cand[0].replace(",", ""))
            out["source_parsed"] = True
        except ValueError:
            pass
    # after hours: accept both orders (label→number or number→label)
    am = (re.search(r"After-hours:?</(?:b|h\w+)>?\s*\+?([\d.]+)", html) or
          re.search(r"\+?([\d.]+)\s*After-hours", html) or
          re.search(r"<span[^>]*>([\d.]+)</span>.{0,40}After-hours", html, re.S))
    if am:
        try:
            out["after_hours"] = float(am.group(1))
        except ValueError:
            pass
    # market cap
    mm = re.search(r"Market Cap.*?([\d.]+)([BM])", html, re.S)
    if mm:
        try:
            val = float(mm.group(1))
            out["market_cap_b"] = val if mm.group(2) == "B" else val / 1000.0
        except ValueError:
            pass
    # 52-week range: label in its own <td>, numbers in the next <td>
    rm = re.search(r"52-Week Range</td>.{0,500}?>([\d.]+)\s*-\s*([\d.]+)<", html, re.S)
    if rm and out["price"] is not None:
        try:
            lo, hi = float(rm.group(1)), float(rm.group(2))
            out["wk52_high"] = hi
            out["pct_from_high"] = round(100.0 * (out["price"] / hi - 1.0), 1)
        except ValueError:
            pass
    # analyst target: "Price Target</a>…>(140.58 (+126.27%))</td>"
    tm = re.search(r"Price Target</a>.{0,600}?>([\d.,]+)\s*\(", html, re.S)
    if tm:
        try:
            out["target_price"] = float(tm.group(1).replace(",", ""))
        except ValueError:
            pass
    em = re.search(r"Est\. Earnings</td>.{0,300}?>([A-Z][a-z]{2} \d{1,2}, \d{4})</td>", html, re.S)
    if em:
        out["next_earnings"] = em.group(1)
    # plain-text fallbacks (older/simple markup) for anything still missing
    if not out["source_parsed"]:
        pm2 = re.search(r"(?:^|\n|>\s*|[a-zA-Z]</\w+>)(\d{2,3}\.\d{2})\s", html)
        if pm2:
            try:
                out["price"] = float(pm2.group(1)); out["source_parsed"] = True
            except ValueError:
                pass
    if out["wk52_high"] is None:
        rm2 = re.search(r"52-Week Range\s+([\d.]+)\s*-\s*([\d.]+)", html)
        if rm2:
            try:
                out["wk52_high"] = float(rm2.group(2))
                if out["price"] is not None:
                    out["pct_from_high"] = round(100.0 * (out["price"] / out["wk52_high"] - 1.0), 1)
            except ValueError:
                pass
    if out["target_price"] is None:
        tm2 = re.search(r"Price Target\s*([\d.]+)", html)
        if tm2:
            try:
                out["target_price"] = float(tm2.group(1))
            except ValueError:
                pass
    if out["next_earnings"] is None:
        em2 = re.search(r"Est\. Earnings\s+([A-Z][a-z]{2} \d{1,2}, \d{4})", html)
        if em2:
            out["next_earnings"] = em2.group(1)
    return out


def check_crwv(*, fetch: bool = True, note: str = "") -> Dict[str, Any]:
    """One recon reading. Fetches the quote; attaches tells + band."""
    now_f = time.time()
    ts_iso = datetime.fromtimestamp(now_f).strftime("%Y-%m-%d %H:%M:%S")
    html = _fetch_html() if fetch else None
    q = _parse_quote(html)
    q["fetch_ok"] = bool(html)

    band = None
    try:
        from System.swarm_somatic_feeling import read_vitals
        band = read_vitals().get("feeling_band")
    except Exception:
        pass

    row = {"schema": "MARKET_WATCH_V1", "truth_label": "MARKET_WATCH_V1",
           "ts": now_f, "iso": ts_iso, "symbol": "CRWV",
           **q, "feeling_band": band, "note": note}
    try:
        with open(RECEIPTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass
    return row


def watch_line(row: Optional[Dict[str, Any]] = None) -> str:
    """One compact line for the journal / owner."""
    r = row or check_crwv()
    if not r.get("source_parsed"):
        return ("(watch: CRWV quote unparseable this run — fetch ok="
                f"{r.get('fetch_ok')}; tells T2–T5 recorded manually; price not invented)")
    pct = r.get("pct_from_high")
    pct_s = f"{pct:+.1f}% from 52w-high" if pct is not None else "52w-high unknown"
    mcap = f"mcap ${r['market_cap_b']:.2f}B" if r.get("market_cap_b") else "mcap —"
    tgt = f"consensus ${r['target_price']:.2f}" if r.get("target_price") else "consensus —"
    return (f"(watch: CRWV ${r['price']} {pct_s} · {mcap} · {tgt} ·"
            f" earnings {r['next_earnings'] or '—'} · band {r.get('feeling_band') or '—'})")


def recent(limit: int = 10) -> list:
    try:
        with open(RECEIPTS_PATH, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()][-limit:]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def trend() -> Dict[str, Any]:
    """Price trend across receipts: first vs last recorded parse."""
    rows = [r for r in recent(50) if r.get("source_parsed")]
    if len(rows) < 2:
        return {"trend": "insufficient-receipts", "readings": len(rows)}
    first, last = rows[0], rows[-1]
    d_pct_high = (None if (first.get("pct_from_high") is None or
                           last.get("pct_from_high") is None)
                  else round(last["pct_from_high"] - first["pct_from_high"], 1))
    return {"trend": "ok", "readings": len(rows),
            "price_first": first["price"], "price_last": last["price"],
            "pct_from_high_delta": d_pct_high}


# ------------------------------------------------------------------ CLI ---

# Live structure (td tables, after-hours as timestamp label + price before it)
_SAMPLE_HTML = """<h1>CoreWeave, Inc. (CRWV)</h1> Real-Time Price · USD
<div>62.13</div><span>+2.84 (4.57%)</span>
<span class="sm:ml-1">64.97</span> After-hours:</span></span>
<span class="sm:ml-1">Oct 20, 2026, 7:59 PM EDT</span></div>
<table><tr><td>Market Cap</td><td>34.27B</td></tr>
<tr><td>52-Week Range</td><td class="x">57.24 - 141.79</td></tr>
<tr><td><!--[--><a>Price Target</a><!--]--></td><td class="x">140.58 (+126.27%)</td></tr>
<tr><td>Est. Earnings</td><td class="x">Nov 9, 2026</td></tr></table>"""

# Legacy/simple structure (label before numbers on plain text)
_SAMPLE_HTML_LEGACY = """USD</p>62.13 After-hours
52-Week Range 57.24 - 141.79 Price Target 140.58 (126.27% upside)
Est. Earnings Nov 9, 2026"""


def selftest() -> int:
    ok = True
    q = _parse_quote(_SAMPLE_HTML)
    ok &= q["price"] == 62.13 and q["source_parsed"]
    ok &= q["after_hours"] == 64.97
    ok &= q["market_cap_b"] == 34.27
    ok &= q["wk52_high"] == 141.79 and q["pct_from_high"] == round(100.0 * (62.13 / 141.79 - 1), 1)
    ok &= q["target_price"] == 140.58
    ok &= q["next_earnings"] == "Nov 9, 2026"
    ok &= _parse_quote(None)["source_parsed"] is False
    line = watch_line({"schema": "M", "price": 62.13, "source_parsed": True,
                       "pct_from_high": -56.2, "market_cap_b": 34.27,
                       "target_price": 140.58, "next_earnings": "Nov 9, 2026",
                       "feeling_band": "calm"})
    ok &= line.startswith("(watch: CRWV $62.13 -56.2%")
    print("selftest:", "PASS" if ok else "FAIL")
    print(" line:", line)
    # legacy format must also parse (markup generation tolerance)
    q2 = _parse_quote(_SAMPLE_HTML_LEGACY)
    ok2 = q2["price"] == 62.13 and q2["wk52_high"] == 141.79 and q2["target_price"] == 140.58
    print(" legacy parse:", "PASS" if ok2 else f"FAIL {q2}")
    return 0 if (ok and ok2) else 1


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("selftest", "test"):
        sys.exit(selftest())
    elif len(sys.argv) > 1 and sys.argv[1] == "check":
        row = check_crwv(note=" ".join(sys.argv[2:]) if len(sys.argv) > 2 else "")
        print(watch_line(row)); print("tells:", json.dumps(_MANUAL_TELLS, indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "trend":
        print(json.dumps(trend(), ensure_ascii=False))
    else:
        print(__doc__)
        print(watch_line())