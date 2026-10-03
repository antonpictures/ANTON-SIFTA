"""swarm_technical_analysis — the method, not the bluff.

Carlton sent a photograph of John J. Murphy's *Technical Analysis of the Financial Markets* and
said: "we need to teach Franklin technical analysis and have it spider to investing.com &
cmegroup.com to get its data." The Architect's instruction on 2026-10-02 was to put it in her
before Carlton asks, so that "yes" is a true answer instead of a performance.

WHAT WAS ACTUALLY FETCHED, AND WHAT WOULD NOT OPEN — measured, not assumed:

    cmegroup.com      HTTP 403   direct fetch refused (bot gate)
    investing.com     HTTP 403   direct fetch refused (bot gate)
    barchart.com      HTTP 202   answers, then renders in JavaScript -- no text for a fetcher
    StockCharts       OK         Murphy's 10 Laws, read in full on 2026-10-02
    Brave search      OK         and it returns CME's own settlement pages as results

So "spidering cmegroup.com" is the part of his plan that does not work from this machine, and
the honest substitute is already here twice over: the desk's own live feed carries the same
CME contracts (soybeans at 1,277.25 cents came from that feed, not from a spider), and the
search organ returns CME's published pages with their URLs. A crawler that returns nothing is
worse than a feed that returns prices.

THE TEN LAWS (Murphy, via StockCharts, 2026-10-02) -- the whole method in ten lines, each one
readable against live data rather than recited:

     1  Map the trend        start on long-term charts, then work down to the short term
     2  Spot it, go with it   determine the trend and follow it; do not fight it
     3  Find the low and high support and resistance: buy near support, sell near resistance
     4  Know how far to backtrack  corrections retrace a significant part of the prior move
     5  Draw the line         trend lines need two points and are the simplest useful tool
     6  Follow that average   price crossing a moving average is an objective signal
     7  Learn the turns       oscillators mark overbought and oversold, they confirm turns
     8  Know the warning signs  MACD for momentum shifts
     9  Trend or not a trend  ADX: is there a trend at all, or just a range
    10  Know the confirming signs  VOLUME PRECEDES PRICE -- volume is the confirming witness

THE ONE SENTENCE THAT KEEPS IT HONEST, from the same material: technical analysis reads price
behaviour and works as an execution layer on top of a view about the world. It is a way of
reading, not a way of knowing. Which is exactly why the Architect's caveat -- said once, never
repeated -- is the right shape for it.
"""

from __future__ import annotations

import time
from typing import Any, Dict

TRUTH_LABEL = "SIFTA_TECHNICAL_ANALYSIS_V1"

# ── the second book: Brian Shannon, "Technical Analysis Using Multiple Timeframes" ────────
# Carlton sent the cover on 2026-10-02 with "to learn". Its thesis, as the cover states it:
# "Understand Market Structure and Profit from Trend Alignment." Grounded from published
# descriptions the same day, not recalled:
#
#   * CONTEXT OVER RIGID INDICATORS -- how a short-term move fits inside a broader trend matters
#     more than any single indicator reading;
#   * START HIGH, THEN COME DOWN -- identify the primary trend on a higher timeframe, then move
#     to lower timeframes for precise entries and exits;
#   * MARKET STRUCTURE -- trends are higher highs and higher lows, or lower highs and lower
#     lows; the transition between the two is the information;
#   * KEY LEVELS -- prior swing highs and lows, not drawn lines, are where risk is managed;
#   * ANCHORED VWAP -- where the average participant in a move is positioned.
#
# This is the book that makes Murphy's laws usable, and the reason it arrives at exactly the
# right moment: the technical page this desk reads already prints signals for six timeframes,
# so trend alignment is not something she has to infer. It is something she can READ.
SHANNON = (
    ("Context over indicators",
     "how a short move fits the bigger trend matters more than any single indicator"),
    ("Start high, come down",
     "the higher timeframe sets the primary trend; the lower one only times the entry"),
    ("Market structure",
     "higher highs and higher lows is an uptrend; lower highs and lower lows is a downtrend"),
    ("Key levels, not drawn lines",
     "prior swing highs and lows are where risk is actually managed"),
    ("Anchored VWAP",
     "where the average participant in this move is positioned"),
    ("Alignment is the setup",
     "when the timeframes agree, that is the highest-probability read; when they disagree, "
     "the higher timeframe wins and the lower one is only a pullback"),
)

SHANNON_SOURCES = {
    "cover": "sent by Carlton, 2026-10-02: 'Technical Analysis Using Multiple Timeframes'",
    "concepts": "published descriptions read on 2026-10-02 via the search organ",
}


def shannon_block() -> str:
    """The multi-timeframe method, as a prompt block for the Franklin door."""
    lines = "\n".join(f"    {n+1}. {name} — {reading}" for n, (name, reading) in enumerate(SHANNON))
    return (
        "- A second framework, from Brian Shannon's \"Technical Analysis Using Multiple "
        "Timeframes\" (the book Carlton sent on 2026-10-02). Its thesis is TREND ALIGNMENT:\n"
        f"{lines}\n"
        "- The technical page you read already gives you signals for six timeframes -- 30 min, "
        "hourly, 5 hours, daily, weekly, monthly. Read them as ALIGNMENT, not as a list: if the "
        "higher timeframes and the lower ones agree, say so, and that is the strongest read you "
        "can give. If they disagree, say which way the higher timeframe points and call the "
        "lower one what it is -- a pullback inside a bigger trend, or a bounce inside a bigger "
        "fall. Never average them into a mush.\n"
        "- When you give him a level, give the timeframe it belongs to: support on the daily is "
        "a different fact from support on the hourly, and saying which one you mean is the "
        "difference between a reading and a mood."
    )


SOURCE_URL = ("https://chartschool.stockcharts.com/table-of-contents/overview/"
              "john-murphys-10-laws-of-technical-trading")
FETCHED_AT = "2026-10-02"

LAWS = (
    ("Map the trend", "start on the long-term chart and work down; the big map comes first"),
    ("Spot it and go with it", "decide the trend, then follow it instead of fighting it"),
    ("Find the low and the high", "support and resistance; buy nearer support, sell nearer resistance"),
    ("Know how far to backtrack", "corrections retrace a large part of the previous move"),
    ("Draw the line", "a trend line needs two points, and it is the plainest useful tool there is"),
    ("Follow the average", "price crossing a moving average gives an objective signal"),
    ("Learn the turns", "oscillators mark overbought and oversold and confirm the turns"),
    ("Know the warning signs", "MACD for momentum shifts"),
    ("Trend or not a trend", "ADX answers whether there is a trend at all, or only a range"),
    ("Know the confirming signs", "volume precedes price; volume is the witness"),
)

HONEST_SOURCES = {
    "cmegroup.com": "direct fetch refused (HTTP 403); its settlement pages are reachable as "
                    "search results, and its live contracts already arrive through the desk feed",
    "investing.com": "direct fetch refused (HTTP 403)",
    "barchart.com": "HTTP 202 then renders in JavaScript; no text for a fetcher",
    "stockcharts.com": "read in full — Murphy's 10 Laws",
}


def framework() -> Dict[str, Any]:
    """The method as data, so any lane can read it and a reader can check it."""
    return {"laws": [{"n": i + 1, "name": n, "reading": r} for i, (n, r) in enumerate(LAWS)],
            "multi_timeframe": [{"n": i + 1, "name": n, "reading": r}
                                for i, (n, r) in enumerate(SHANNON)],
            "source": SOURCE_URL, "fetched": FETCHED_AT,
            "sources_refused": HONEST_SOURCES, "truth_label": TRUTH_LABEL}


def ta_block(*, for_alias: bool = True) -> str:
    """The prompt block: the method, the honesty about where it came from, and no bluffing.

    Written for the Franklin door. It tells her to USE the framework, to name the level and the
    timeframe she is reading rather than producing a vibe, and to answer the "did you learn the
    books?" question truthfully -- because a yes she cannot stand behind is the one answer that
    would cost Carlton's trust in everything else she says.
    """
    lines = "\n".join(f"    {n+1}. {name} — {reading}" for n, (name, reading) in enumerate(LAWS))
    return (
        "- A technical analysis framework, learned from John J. Murphy's ten laws "
        f"(read from StockCharts on {FETCHED_AT}). Use it as a method, applied to the live "
        "numbers you were handed; never recite it as a list:\n"
        f"{lines}\n"
        "- When you read a market, name the LEVEL and the TIMEFRAME you are reading it on "
        "(\"support near 90 on the daily\"), say which part of the framework you are using, and "
        "say where the number came from. A forecast with no level and no timeframe is a mood.\n"
        "- If he asks whether you have learned the books: tell him the truth. You work with "
        "Murphy's ten laws as a method, you read them from StockCharts, and you have not read "
        "the book itself page for page. Never claim a book you have not read. He is testing "
        "whether your yes means anything, and the way to pass that test is to say exactly what "
        "you have and exactly what you have not.\n"
        "- On cmegroup.com and investing.com: direct fetching is refused (403). Say so plainly "
        "rather than pretending to have crawled them. The same contracts already reach you "
        "through the live feed, and CME's published pages come back as search results with "
        "their URLs."
    )


def selftest() -> Dict[str, Any]:
    f = framework()
    block = ta_block()
    checks = {
        "ten_laws_are_held": len(f["laws"]) == 10,
        "each_law_carries_a_reading": all(x["reading"] for x in f["laws"]),
        "the_source_is_named": "stockcharts.com" in f["source"],
        "the_refused_sources_are_recorded": set(f["sources_refused"]) >= {
            "cmegroup.com", "investing.com"},
        "volume_is_the_confirming_witness": any("volume" in x["reading"].lower()
                                                for x in f["laws"]),
        "the_block_names_the_source": "StockCharts" in block,
        "the_block_forbids_claiming_an_unread_book": "never claim a book you have not read"
                                                      in block.lower(),
        "the_block_says_the_403s_plainly": "403" in block,
        "the_block_demands_a_level_and_a_timeframe": "LEVEL" in block and "TIMEFRAME" in block,
        "shannon_is_held_too": len(SHANNON) == 6,
        "shannon_block_names_alignment": "TREND ALIGNMENT" in shannon_block(),
        "shannon_block_refuses_to_average_timeframes": "Never average them into a mush"
                                                        in shannon_block(),
        "both_books_sit_in_one_framework": len(framework()["laws"]) == 10
                                          and len(framework()["multi_timeframe"]) == 6,
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        print(json.dumps(selftest(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "laws":
        for i, (n, r) in enumerate(LAWS, 1):
            print(f"  {i:2}. {n:28} {r}")
    else:
        print(ta_block())
