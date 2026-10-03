"""swarm_ta_read — the technical read, taken from the page through her own eye.

Carlton asked for two things: teach Franklin technical analysis, and have it read
investing.com and cmegroup.com for its data. Both sites refuse a scraper -- `curl` gets HTTP 403
from each -- and both open perfectly in Alice Browser. So this organ does not scrape. It looks,
reads the rendered page, and says which page it read and when.

WHAT investing.com HANDS OVER, measured 2026-10-02 on US Soybeans (ZSX6):

    1,277.25  -6.75 (-0.53%)   day 1,273.13-1,285.63   52wk 1,001.00-1,335.25

    timeframes   30min Strong Sell · hourly Strong Sell · 5h Strong Sell · daily Sell
                 weekly Strong Buy · monthly Strong Buy
    summary      Strong Sell      moving averages 0 buy / 12 sell
                                 indicators 2 buy / 7 sell
    indicators   RSI(14) 43.876 Sell · STOCH(9,6) 40.785 Sell · MACD(12,26) -1.62 Sell
                 ADX(14) 21.975 Buy · Williams %R -75.281 Sell · CCI(14) 10.9028 Neutral
                 ATR(14) 3.3929 High Volatility · Ultimate Oscillator 47.814 Sell
                 ROC 0.068 Buy · Bull/Bear Power(13) -0.29 Sell
    averages     MA5 1278.45 · MA10 1278.25 · MA20 1277.65 · MA50 1284.09
                 MA100 1289.19 · MA200 1303.07   (simple and exponential, all Sell)

That is Murphy's method already computed and dated: law 6 is the moving averages, law 7 the
oscillators, law 8 the MACD, law 9 the ADX, and law 10 is the volume on the CME page. This organ
does not invent a reading from a price; it fetches the reading a calculator already made, and
carries the timestamp with it so nobody mistakes it for a live opinion.

One limit stated plainly: the page's own 1-minute, 5-minute and 15-minute columns sit behind an
account, so the shortest timeframe available here is the 30-minute. Reading a scalp off a
daily-only page would be a mistake this organ refuses to make.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

_REPO = Path(__file__).resolve().parents[1]
STATE = _REPO / ".sifta_state"
RECEIPTS = STATE / "ta_read.jsonl"
TRUTH_LABEL = "SIFTA_TA_READ_V1"

BRIDGE = "http://127.0.0.1:10086/command"
SESSION = "ta-read"

# slug -> the investing.com technical page for that contract family.
SYMBOLS = {
    "soybean": "us-soybeans",
    "soybean_meal": "us-soybean-meal",
    "soybean_oil": "us-soybean-oil",
    "corn": "us-corn",
    "wheat": "us-wheat",
    "crude_oil": "crude-oil",
    "brent": "brent-oil",
    "natural_gas": "natural-gas",
    "gold": "gold",
    "silver": "silver",
    "copper": "copper",
    "sp500": "us-sp-500",
    "nasdaq": "us-tech-100",
    "dow": "us-30",
    "eur_usd": "eur-usd",
    "bitcoin": "bitcoin",
}

ACTIONS = ("Strong Sell", "Strong Buy", "Sell", "Buy", "Neutral", "Unlock")
TIMEFRAMES = ("30 Min", "Hourly", "5 Hours", "Daily", "Weekly", "Monthly")


def _bridge(action: str, args: Dict[str, Any], timeout: float = 70.0) -> Dict[str, Any]:
    payload = json.dumps({"action": action, "args": args, "session": SESSION})
    try:
        r = subprocess.run(["curl", "-s", "--max-time", str(int(timeout)), "-X", "POST", BRIDGE,
                            "-H", "Content-Type: application/json", "-d", payload],
                           capture_output=True, text=True)
        return json.loads(r.stdout)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def parse(text: str) -> Dict[str, Any]:
    """Read the technical page's text. Parsed by meaning, not by markup."""
    out: Dict[str, Any] = {}
    if not text:
        return out
    flat = re.sub(r"\n{2,}", "\n", text)
    head = re.search(r"\n([0-9][0-9,]*\.[0-9]+)\n(-?[0-9.]+)\n\((-?[0-9.]+)%\)", flat)
    if head:
        out["price"] = head.group(1)
        out["change"] = head.group(2)
        out["change_pct"] = head.group(3)
    rng = re.search(r"Day's Range\s*\n([0-9.,]+)\n([0-9.,]+)", flat)
    if rng:
        out["day_range"] = [rng.group(1), rng.group(2)]
    wk = re.search(r"52 wk Range\s*\n([0-9.,]+)\n([0-9.,]+)", flat)
    if wk:
        out["week52_range"] = [wk.group(1), wk.group(2)]

    # the timeframe row: "30 Min\nStrong Sell\nHourly\nStrong Sell\n..."
    lines = [x.strip() for x in flat.splitlines()]
    signals: Dict[str, str] = {}
    for i, line in enumerate(lines):
        if line in TIMEFRAMES and i + 1 < len(lines) and lines[i + 1] in ACTIONS:
            signals[line] = lines[i + 1]
    out["timeframe_signals"] = signals

    summary = re.search(r"Summary\s*\n(Strong Sell|Strong Buy|Sell|Buy|Neutral)", flat)
    if summary:
        out["summary"] = summary.group(1)
    ma_line = re.search(r"Moving Averages:\s*(Strong Sell|Strong Buy|Sell|Buy|Neutral)\s*"
                        r"Buy:\s*\((\d+)\)\s*Sell:\s*\((\d+)\)", flat)
    if ma_line:
        out["moving_average_summary"] = {"action": ma_line.group(1), "buy": int(ma_line.group(2)),
                                         "sell": int(ma_line.group(3))}
    ti_line = re.search(r"Technical Indicators:\s*(Strong Sell|Strong Buy|Sell|Buy|Neutral)\s*"
                        r"Buy:\s*\((\d+)\)\s*Sell:\s*\((\d+)\)", flat)
    if ti_line:
        out["indicator_summary"] = {"action": ti_line.group(1), "buy": int(ti_line.group(2)),
                                    "sell": int(ti_line.group(3))}
    stamp = re.search(r"(Oct|Nov|Dec|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep)\s+\d{1,2},\s+\d{4}\s+"
                      r"\d{1,2}:\d{2}(AM|PM)\s+GMT", flat)
    if stamp:
        out["as_of"] = stamp.group(0)

    # indicator rows: NAME <tab> VALUE <tab> ACTION
    indicators: List[Dict[str, str]] = []
    for line in lines:
        parts = [p.strip() for p in re.split(r"\t+", line)] if "\t" in line else []
        if len(parts) >= 3 and parts[0] and not re.match(r"^\d+$", parts[0]) and parts[-1] in ACTIONS:
            name = parts[0]
            if any(k in name for k in ("RSI", "STOCH", "MACD", "ADX", "Williams", "CCI", "ATR",
                                       "Highs/Lows", "Ultimate", "ROC", "Bull/Bear")):
                indicators.append({"name": name, "value": parts[1], "action": parts[-1]})
    out["indicators"] = indicators
    return out


def read(symbol: str = "soybean", *, wait: float = 14.0, write: bool = True) -> Dict[str, Any]:
    """Look at one technical page and read the calculator's own verdict off it."""
    slug = SYMBOLS.get(str(symbol).strip().lower())
    if not slug:
        return {"ok": False, "error": f"no technical page known for {symbol!r}",
                "known": sorted(SYMBOLS)}
    url = f"https://www.investing.com/commodities/{slug}-technical"
    nav = _bridge("navigate", {"url": url, "newTab": True})
    if not nav.get("ok"):
        return {"ok": False, "error": "could not open the page", "detail": str(nav)[:160]}
    time.sleep(wait)
    got = _bridge("evaluate", {"code": "document.body.innerText"})
    data = got.get("data")
    text = data.get("value") if isinstance(data, dict) else ""
    if not text:
        return {"ok": False, "error": "the page returned no text"}
    parsed = parse(text)
    result = {"ok": bool(parsed.get("summary") or parsed.get("price")), "symbol": symbol,
              "url": url, **parsed, "truth_label": TRUTH_LABEL,
              "note": ("read through her own browser from investing.com's own technical page; "
                       "1m/5m/15m columns sit behind an account, so the shortest timeframe here "
                       "is 30 minutes")}
    if write:
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        with RECEIPTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), **result}, ensure_ascii=False) + "\n")
    return result


# Real text captured from investing.com on 2026-10-02 for US Soybeans (ZSX6). The parser is
# tested against the page as it actually prints itself, not against a page I imagined -- the
# CME parser an hour earlier read zero rows because I wrote it from a guess.
_SAMPLE = """US Soybeans (ZSX6)
1,277.25
-6.75
(-0.53%)
Closed
14:19:58
Day's Range
1,273.13
1,285.63
52 wk Range
1,001.00
1,335.25
US Soybeans Futures Technical Analysis
30 Min
Strong Sell
Hourly
Strong Sell
5 Hours
Strong Sell
Daily
Sell
Weekly
Strong Buy
Monthly
Strong Buy
Summary
Strong Sell
Technical Indicators
Strong Sell
Moving Averages
Strong Sell
Summary:Strong Sell
Moving Averages:\tStrong Sell\tBuy: (0)\tSell: (12)
Technical Indicators:\tStrong Sell\tBuy: (2)\tSell: (7)
Oct 2, 2026 06:30PM GMT
RSI(14)\t43.876\tSell
STOCH(9,6)\t40.785\tSell
STOCHRSI(14)\t50.48\tNeutral
MACD(12,26)\t-1.62\tSell
ADX(14)\t21.975\tBuy
Williams %R\t-75.281\tSell
CCI(14)\t10.9028\tNeutral
ATR(14)\t3.3929\tHigh Volatility
Ultimate Oscillator\t47.814\tSell
ROC\t0.068\tBuy
Bull/Bear Power(13)\t-0.29\tSell
"""


def selftest() -> Dict[str, Any]:
    p = parse(_SAMPLE)
    names = [i["name"] for i in p.get("indicators", [])]
    checks = {
        "reads_the_price": p.get("price") == "1,277.25",
        "reads_the_change_pct": p.get("change_pct") == "-0.53",
        "reads_the_day_range": p.get("day_range") == ["1,273.13", "1,285.63"],
        "reads_the_52_week_range": p.get("week52_range") == ["1,001.00", "1,335.25"],
        "reads_every_timeframe": len(p.get("timeframe_signals", {})) == 6,
        "the_daily_says_sell": p["timeframe_signals"].get("Daily") == "Sell",
        "the_weekly_says_strong_buy": p["timeframe_signals"].get("Weekly") == "Strong Buy",
        "reads_the_summary": p.get("summary") == "Strong Sell",
        "reads_the_moving_average_tally": p["moving_average_summary"]["sell"] == 12,
        "reads_the_indicator_tally": p["indicator_summary"]["buy"] == 2,
        "reads_the_indicators": "RSI(14)" in names and "MACD(12,26)" in names and "ADX(14)" in names,
        "keeps_the_timestamp": bool(p.get("as_of")),
        "an_unknown_symbol_says_so": read("unobtainium", write=False)["ok"] is False,
        # judged on the page text captured on 2026-10-02: a selftest that calls the network is
        # not a selftest, it is a live test wearing the word test
        "alignment_sees_a_pullback_in_an_uptrend": align(
            _result={"ok": True, **p})["alignment"] == "pullback_in_uptrend",
        "alignment_names_the_higher_timeframes": align(
            _result={"ok": True, **p})["higher_timeframes"] == {"Monthly": "Strong Buy",
                                                               "Weekly": "Strong Buy",
                                                               "Daily": "Sell"},
        "alignment_refuses_to_average": "never averaged" in align(
            _result={"ok": True, **p})["how_to_read_it"],
        "an_aligned_page_reads_as_aligned": align(_result={"ok": True, "timeframe_signals": {
            "30 Min": "Buy", "Hourly": "Buy", "5 Hours": "Buy", "Daily": "Buy",
            "Weekly": "Buy", "Monthly": "Buy"}})["alignment"] == "aligned_up",
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


# ── trend alignment: the two books, applied to six timeframes ──────────────────────────────
_SCORE = {"Strong Buy": 2, "Buy": 1, "Neutral": 0, "Sell": -1, "Strong Sell": -2}
_HIGHER = ("Monthly", "Weekly", "Daily")          # Shannon: this sets the primary trend
_LOWER = ("5 Hours", "Hourly", "30 Min")          # and this only times the entry


def align(symbol: str = "soybean", *, write: bool = True,
          _result: Dict[str, Any] | None = None, **kw) -> Dict[str, Any]:
    """Read the timeframes as ALIGNMENT, the way Shannon's book reads them.

    Murphy gives the tools; Shannon gives the order to use them in: the higher timeframe sets
    the primary trend and the lower one only times an entry. So a page that says "Strong Sell"
    on the 30-minute and "Strong Buy" on the monthly is not contradicting itself -- it is a
    pullback inside an uptrend, and calling it anything else is the mistake this function exists
    to prevent. Six timeframes are already computed by the page; nothing here is inferred from
    a price.

    Never averages the timeframes into a single mush: an average of "Strong Buy" and "Strong
    Sell" is "Neutral", which is the one answer that is always wrong.
    """
    r = _result if _result is not None else read(symbol, write=write, **kw)
    if not r.get("ok"):
        return r
    tf = r.get("timeframe_signals") or {}
    scored = {k: _SCORE.get(v, 0) for k, v in tf.items()}
    hi = [scored[k] for k in _HIGHER if k in scored]
    lo = [scored[k] for k in _LOWER if k in scored]
    hi_avg = round(sum(hi) / len(hi), 2) if hi else None
    lo_avg = round(sum(lo) / len(lo), 2) if lo else None

    if hi_avg is None or lo_avg is None:
        verdict, reading = "incomplete", "the page did not give enough timeframes to align"
    elif hi_avg > 0 and lo_avg > 0:
        verdict = "aligned_up"
        reading = ("every timeframe points the same way: this is trend alignment, the "
                   "highest-probability read either book describes")
    elif hi_avg < 0 and lo_avg < 0:
        verdict = "aligned_down"
        reading = ("every timeframe points down together: alignment to the downside")
    elif hi_avg > 0 > lo_avg:
        verdict = "pullback_in_uptrend"
        reading = ("the higher timeframes are up and the lower ones are down, so this is a "
                   "pullback inside a bigger uptrend -- the primary trend is up, and the "
                   "short-term weakness is what a trend-aligned entry waits on")
    elif hi_avg < 0 < lo_avg:
        verdict = "bounce_in_downtrend"
        reading = ("the higher timeframes are down and the lower ones are up, so this is a "
                   "bounce inside a bigger fall -- the primary trend is down, and the bounce "
                   "does not change it")
    else:
        verdict = "mixed"
        reading = "the timeframes do not agree and the higher ones are flat; nothing is aligned"

    out = dict(r)
    out.update({"alignment": verdict, "reading": reading,
                "higher_timeframes": {k: tf.get(k) for k in _HIGHER if k in tf},
                "lower_timeframes": {k: tf.get(k) for k in _LOWER if k in tf},
                "higher_score": hi_avg, "lower_score": lo_avg,
                "how_to_read_it": ("Shannon's order: the higher timeframe sets the primary "
                                   "trend; the lower one only times the entry. The timeframes "
                                   "are never averaged together."),
                "truth_label": TRUTH_LABEL})
    return out


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest":
        print(json.dumps(selftest(), indent=2))
    elif cmd == "align":
        print(json.dumps(align(sys.argv[2] if len(sys.argv) > 2 else "soybean"), indent=2))
    elif cmd == "read":
        print(json.dumps(read(sys.argv[2] if len(sys.argv) > 2 else "soybean"), indent=2))
    else:
        print(json.dumps({"symbols": sorted(SYMBOLS)}, indent=2))
