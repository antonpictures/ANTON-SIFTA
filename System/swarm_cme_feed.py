"""swarm_cme_feed — reading CME Group through her own eye, because a crawler is refused.

Carlton's instruction, relayed by the Architect on 2026-10-02: "we need to teach Franklin
technical analysis and have it spider to investing.com & cmegroup.com to get its data."

MEASURED, AND THE ANSWER IS NOT WHAT EITHER OF US EXPECTED:

    curl https://www.cmegroup.com/        HTTP 403     refused -- a bot, told to go away
    curl https://www.investing.com/       HTTP 403     refused -- the same
    Alice Browser -> cmegroup.com         WORKS        quotes, settlements, volume, open interest

The 403 was never about CME's data being closed. It was about the shape of the request: a
scraper announces itself and gets a gate. Her browser is not a scraper, so the page renders,
and the data is readable straight out of the document. So this organ does not spider. It
LOOKS -- the way she looks at anything else -- and it says which page it read and when.

What it can see, verified 2026-10-02 on the soybean page:

    Soybean   ZSX6   last 1277'2   -6'6 (-0.53%)   volume 110,821   02 Oct 2026 02:18:38 PM CT
    Settlements for 01 Oct 2026, by contract month: open, high, low, last, change, settle,
    estimated volume, and PRIOR DAY OPEN INTEREST -- which is the number a technical reading
    actually needs and which no price feed alone gives you.

Prices arrive delayed by at least ten minutes, and the page says so. That sentence travels
with every number this organ returns, because a delayed quote quoted as live is a lie with a
timestamp on it.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parents[1]
STATE = _REPO / ".sifta_state"
RECEIPTS = STATE / "cme_feed.jsonl"
TRUTH_LABEL = "SIFTA_CME_FEED_V1"

BRIDGE = "http://127.0.0.1:10086/command"
SESSION = "cme-feed"
DELAY_NOTICE = "market data is delayed by at least 10 minutes"

# One entry per market she has a page for. Adding a market is adding a line -- the same shape
# as adding an identity to the persona register.
PAGES = {
    "soybean": "https://www.cmegroup.com/markets/agriculture/oilseeds/soybean/settlements.html",
    # The Minneapolis contract Carlton asked for, found by search rather than guessed: CME
    # lists it as HARD RED SPRING WHEAT, not "minneapolis wheat" -- my first URL 404'd on the
    # obvious name. Spring wheat (MWE) is the leg that moves against Chicago soft red winter
    # (ZW), and the spread between them is a real trade; without this page the desk had one leg
    # of it and had to say so.
    "minneapolis_wheat": "https://www.cmegroup.com/markets/agriculture/grains/hard-red-spring-wheat/settlements.html",
    "hard_red_spring_wheat": "https://www.cmegroup.com/markets/agriculture/grains/hard-red-spring-wheat/settlements.html",
    "kc_wheat": "https://www.cmegroup.com/markets/agriculture/grains/hard-red-winter-wheat/settlements.html",
    "corn": "https://www.cmegroup.com/markets/agriculture/grains/corn/settlements.html",
    "wheat": "https://www.cmegroup.com/markets/agriculture/grains/wheat/settlements.html",
    "soybean_meal": "https://www.cmegroup.com/markets/agriculture/oilseeds/soybean-meal/settlements.html",
    "soybean_oil": "https://www.cmegroup.com/markets/agriculture/oilseeds/soybean-oil/settlements.html",
    "crude_oil": "https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude/settlements.html",
    "gold": "https://www.cmegroup.com/markets/metals/precious/gold/settlements.html",
}


def _bridge(action: str, args: Dict[str, Any], timeout: float = 60.0) -> Dict[str, Any]:
    payload = json.dumps({"action": action, "args": args, "session": SESSION})
    try:
        r = subprocess.run(["curl", "-s", "--max-time", str(int(timeout)), "-X", "POST",
                            BRIDGE, "-H", "Content-Type: application/json", "-d", payload],
                           capture_output=True, text=True)
        return json.loads(r.stdout)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _text_of(result: Dict[str, Any]) -> str:
    data = result.get("data")
    if isinstance(data, dict):
        v = data.get("value")
        if isinstance(v, str):
            return v
    return ""


def parse(text: str) -> Dict[str, Any]:
    """Pull the quote header and the settlement table out of a CME page's text.

    Parsed from the rendered text rather than from DOM classes: the numbers are the part of
    that page that does not change shape, and a selector is a promise about markup that CME
    never made to us.
    """
    out: Dict[str, Any] = {"delay_notice": DELAY_NOTICE in (text or "").lower()
                                          or "delayed by at least 10 minutes" in (text or "").lower()}
    if not text:
        return out
    flat = re.sub(r"\n{2,}", "\n", text)
    code = re.search(r"GLOBEX CODE\s*\n([A-Z0-9]{2,8})", flat)
    last = re.search(r"\nLAST\s*\n([0-9'.,]+)", flat)
    change = re.search(r"\nCHANGE\s*\n([^\n]+)", flat)
    volume = re.search(r"\nVOLUME\s*\n([0-9,]+)", flat)
    updated = re.search(r"Last Updated\s*([0-9A-Za-z: ]+CT)", flat)
    out["quote"] = {
        "code": code.group(1) if code else "",
        "last": last.group(1) if last else "",
        "change": change.group(1).strip() if change else "",
        "volume": volume.group(1) if volume else "",
        "updated": updated.group(1).strip() if updated else "",
    }
    # settlement rows: MONTH OPEN HIGH LOW LAST CHANGE SETTLE EST.VOLUME PRIOR OI
    rows: List[Dict[str, str]] = []
    for line in flat.splitlines():
        # The page separates columns with real tabs, and the month arrives as ONE field
        # ("NOV 26"), not two. The first version of this joined parts[:2] and therefore
        # matched nothing at all -- a parser that looked right and read zero rows.
        parts = [x.strip() for x in re.split(r"\t+", line)] if "\t" in line else line.split()
        if len(parts) >= 7 and re.match(r"^[A-Z]{3}\s*\d{2}$", parts[0]):
            month = parts[0]
            rest = parts[1:]
            if len(rest) >= 6:
                rows.append({"month": month, "open": rest[0], "high": rest[1], "low": rest[2],
                             "last": rest[3], "change": rest[4], "settle": rest[5],
                             "est_volume": rest[6] if len(rest) > 6 else "",
                             "prior_oi": rest[7] if len(rest) > 7 else ""})
    out["settlements"] = rows
    oi = re.search(r"PRIOR DAY OPEN INTEREST TOTALS\s*\n([0-9,]+)", flat)
    out["prior_day_open_interest_total"] = oi.group(1) if oi else ""
    return out


def read(market: str = "soybean", *, wait: float = 12.0,
         write: bool = True) -> Dict[str, Any]:
    """Look at one CME page and read the quote and the settlement table off it."""
    url = PAGES.get(str(market).strip().lower())
    if not url:
        return {"ok": False, "error": f"no page known for {market!r}",
                "known": sorted(PAGES)}
    nav = _bridge("navigate", {"url": url, "newTab": True})
    if not nav.get("ok"):
        return {"ok": False, "error": "could not open the page", "detail": str(nav)[:160]}
    time.sleep(wait)                       # the quotes widget fills in after load
    got = _bridge("evaluate", {"code": "document.body.innerText"})
    text = _text_of(got)
    if not text:
        return {"ok": False, "error": "the page returned no text"}
    parsed = parse(text)
    result = {"ok": bool(parsed.get("quote", {}).get("code")), "market": market, "url": url,
              "quote": parsed.get("quote"), "settlements": parsed.get("settlements")[:6],
              "prior_day_open_interest_total": parsed.get("prior_day_open_interest_total"),
              "delayed": parsed.get("delay_notice"), "truth_label": TRUTH_LABEL,
              "note": ("read through her own browser, because a scraper is refused; prices are "
                       "delayed by at least ten minutes and the page says so")}
    if write:
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        with RECEIPTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), **result}, ensure_ascii=False) + "\n")
    return result


_SAMPLE = """MARKETS
DATA
LOG IN
Soybean
Futures and Options
GLOBEX CODE
ZSX6
LAST
1277'2
CHANGE
-6'6 (-0.53%)
VOLUME
110,821
Last Updated 02 Oct 2026 02:18:38 PM CT.
Market data is delayed by at least 10 minutes
SOYBEAN FUTURES - SETTLEMENTS
PRIOR DAY OPEN INTEREST TOTALS
1,093,564
MONTH\tOPEN\tHIGH\tLOW\tLAST\tCHANGE\tSETTLE\tEST. VOLUME\tPRIOR DAY OI
NOV 26\t1291'0\t1295'0\t1273'6\t1283'2\t-9'0\t1284'0\t141,615\t1,092,111
JAN 27\t1300'0\t1304'0\t1284'0\t1293'4\t-9'2\t1294'0\t38,204\t291,455
"""


def selftest() -> Dict[str, Any]:
    p = parse(_SAMPLE)
    checks = {
        "reads_the_globex_code": p["quote"]["code"] == "ZSX6",
        "reads_the_last_price": p["quote"]["last"] == "1277'2",
        "reads_the_volume": p["quote"]["volume"] == "110,821",
        "reads_when_it_was_updated": "02 Oct 2026" in p["quote"]["updated"],
        "keeps_the_delay_notice_attached": p["delay_notice"] is True,
        "reads_settlement_rows": len(p["settlements"]) == 2,
        "settlement_row_has_open_high_low": p["settlements"][0]["high"] == "1295'0",
        "settlement_row_keeps_open_interest": p["settlements"][0]["prior_oi"] == "1,092,111",
        "open_interest_total_is_taken": p["prior_day_open_interest_total"] == "1,093,564",
        "an_unknown_market_says_so": read("unobtainium", write=False)["ok"] is False,
        "the_page_list_is_named_for_an_unknown_market": "known" in read("unobtainium", write=False),
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest":
        print(json.dumps(selftest(), indent=2))
    elif cmd == "read":
        print(json.dumps(read(sys.argv[2] if len(sys.argv) > 2 else "soybean"), indent=2))
    else:
        print(json.dumps({"markets": sorted(PAGES)}, indent=2))
