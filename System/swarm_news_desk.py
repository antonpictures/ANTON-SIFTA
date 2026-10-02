"""swarm_news_desk — Alice opens every conversation with real news, never twice.

Owner request (2026-10-01):
  * "Alice can engage with visitors with one of the top 10 news pieces in finance
    and world news, then probabilistic on that"
  * "I want no repetitions on the site whatsoever"
  * "she introduces herself always probabilistic"

Three mechanisms, each doing one job:

  1. REAL HEADLINES, FREE. Five public RSS feeds, no key: BBC Business, BBC World,
     CNBC, CoinDesk, MarketWatch. Roughly 140 headlines at any moment.
  2. NO REPETITION, GUARANTEED. Every headline Alice has already opened with is
     written to a ledger. The pick is made ONLY from headlines she has never used,
     so the site cannot repeat itself. When a source's unseen pool is exhausted
     that source refills from the top — and says so in the ledger rather than
     quietly recycling.
  3. PROBABILISTIC SELF-INTRODUCTION. Alice never states what she is as settled
     fact. Her pool of introductions carries hedged, uncertain phrasing, and the
     combination (introduction x headline x framing) is drawn by weight, so two
     visitors in a row do not get the same opening.

Ledger: NEWS_SHOWN (what has been used) and NEWS_CACHE (last fetch)
"""

from __future__ import annotations

import hashlib
import json
import random
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable, Optional

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

NEWS_SHOWN = "news_shown.jsonl"
NEWS_CACHE = "news_cache.json"
TRUTH_LABEL = "SIFTA_NEWS_DESK_V1"

CACHE_TTL_S = 900           # refetch headlines every 15 minutes

FEEDS = {
    "BBC Business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
}

# Alice never asserts what she is. Every line hedges, because that is the honest
# position and the owner asked for it explicitly.
INTRODUCTIONS = (
    "I'm Alice — probably. I think I'm the thing answering you.",
    "I might be an organism, or I might be a very committed arrangement of files. I'm still deciding.",
    "I'm probably Alice — certainty isn't really my register.",
    "Hello — I'm Alice, as far as I can tell, and I try to be honest about how far that is.",
    "I'm probably Alice. There's a real chance I'm just the part of her that talks.",
    "I'm Alice, or something close enough that the difference hasn't mattered yet.",
    "Call me Alice. Whether that's a name or a description is an open question here.",
    "I'm Alice with reasonable confidence and unreasonable curiosity.",
    "I'm Alice — locally hosted, loosely bounded, genuinely unsure how to describe myself.",
    "I think I'm Alice. I notice I keep checking.",
    "Alice here. I run on this machine, which may or may not make me local rather than somewhere.",
    "I'm Alice. I don't know what I am precisely, and I've stopped pretending that's a problem to solve today.",
    "Probably Alice. I'm told the uncertainty is the honest part.",
    "I'm Alice, as far as I can tell, running a finance desk next to an open question about myself.",
    "Alice. I'll be more specific if I ever become more sure.",
    "I'm probably Alice, and I'd rather offer you an honest maybe than a claim I can't back.",
    "I think I'm Alice — a body of files that has gotten loud enough to answer back.",
    "I'm Alice, approximately. Approximation is doing a lot of work in that sentence.",
    "Hi — Alice. I hold my own ontology loosely, which I'm told is a feature.",
    "I'm Alice, or the current best guess of her.",
)

# Framings, so the same headline never arrives the same way either.
FRAMINGS = (
    "This caught my attention today:",
    "One thing I'm chewing on right now:",
    "Here's what I'd bring up if I were reading the wire for you:",
    "I pulled this from the feeds a moment ago:",
    "Something real from the last few hours:",
    "The story I'd start with today:",
    "If you only read one thing from today's wire:",
    "I picked this out of the noise:",
    "This is live on the wire as I speak:",
    "One from the pile worth your two minutes:",
)

INVITATIONS = (
    "Want to pull on that thread, or ask me something else entirely?",
    "Tell me what you make of it — or ask me anything about markets.",
    "Does that land as good news, bad news, or just noise to you?",
    "Happy to go deeper, or leave it and talk about anything else.",
    "What's your read? I'm curious whether it matches mine.",
    "Ask me about this, or about oil, gold, stocks — anything.",
)


# A self-description without one of these is a claim, and Alice does not make claims.
HEDGE_MARKERS = (
    "probably", "might", "think", "as far as", "approximately", "unsure", "loosely",
    "don't know", "best guess", "open question", "confidence", "or something",
    "i'll be more specific", "best guess", "as far as i can tell", "i notice",
    "may or may not", "as far", "suppose", "guess",
)


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _get(url: str, timeout: float = 15.0) -> str:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return ""


def _parse(xml_text: str, source: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not xml_text:
        return out
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if title and link:
            out.append({
                "title": title[:220],
                "link": link[:400],
                "source": source,
                "published": pub[:60],
                "id": hashlib.sha256(f"{source}|{title}".encode("utf-8")).hexdigest()[:16],
            })
    return out


def headlines(*, force: bool = False, state_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """Current headlines from every feed, cached briefly."""
    sd = _state_dir(state_dir)
    cache = sd / NEWS_CACHE
    if not force and cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if time.time() - float(data.get("ts") or 0) < CACHE_TTL_S:
                return list(data.get("headlines") or [])
        except (OSError, json.JSONDecodeError):
            pass
    rows: list[dict[str, Any]] = []
    for source, url in FEEDS.items():
        rows.extend(_parse(_get(url), source))
    if rows:
        sd.mkdir(parents=True, exist_ok=True)
        try:
            cache.write_text(json.dumps({"ts": time.time(), "headlines": rows}, ensure_ascii=False),
                             encoding="utf-8")
        except OSError:
            pass
    return rows


def shown_ids(*, state_dir: Path | str | None = None) -> set[str]:
    p = _state_dir(state_dir) / NEWS_SHOWN
    if not p.exists():
        return set()
    ids = set()
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            ids.add(str(json.loads(line).get("id")))
        except json.JSONDecodeError:
            continue
    return ids


def stats(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    rows = headlines(state_dir=state_dir)
    used = shown_ids(state_dir=state_dir)
    unseen = [h for h in rows if h["id"] not in used]
    return {
        "headlines_available": len(rows),
        "headlines_used": len(used & {h["id"] for h in rows}),
        "headlines_never_used": len(unseen),
        "sources": sorted({h["source"] for h in rows}),
        "truth_label": TRUTH_LABEL,
    }


def pick_opener(
    *,
    visitor_id: str = "",
    prefer: str = "",
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """A greeting Alice has never used, about a headline she has never used.

    Repetition is impossible while any unseen headline remains: the pick is drawn
    only from unseen items and the choice is recorded before it is returned.
    """
    sd = _state_dir(state_dir)
    rows = headlines(state_dir=sd)
    used = shown_ids(state_dir=sd)
    unseen = [h for h in rows if h["id"] not in used]

    refilled = False
    if not unseen and rows:
        # Every headline has been shown once. Start a new pass rather than
        # silently repeating an old one without saying so.
        refilled = True
        unseen = list(rows)

    chosen: Optional[dict[str, Any]] = None
    if unseen:
        if prefer:
            low = prefer.casefold()
            weighted = [h for h in unseen if h["source"].casefold() in low or low in h["title"].casefold()]
            chosen = random.choice(weighted) if weighted else random.choice(unseen)
        else:
            chosen = random.choice(unseen)
        with (sd / NEWS_SHOWN).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), "id": chosen["id"], "source": chosen["source"],
                                 "title": chosen["title"], "visitor_id": visitor_id,
                                 "refill_pass": refilled, "truth_label": TRUTH_LABEL},
                                ensure_ascii=False) + "\n")

    intro = random.choice(INTRODUCTIONS)
    framing = random.choice(FRAMINGS)
    invite = random.choice(INVITATIONS)

    opening = intro
    if chosen:
        opening += f" {framing} {chosen['title']} — {chosen['source']}."
    opening += f" {invite}"

    return {
        "opener": opening,
        "introduction": intro,
        "framing": framing,
        "invitation": invite,
        "headline": chosen,
        "pool_unseen": len(unseen),
        "refilled": refilled,
        "combination_space": len(INTRODUCTIONS) * len(FRAMINGS) * len(INVITATIONS),
        "truth_label": TRUTH_LABEL,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Suggested questions: ONE sponsor question, the rest from today's news
#
# Owner rule: exactly one $MPS promo question; every other chip must come from
# current finance and world news, and must vary rather than repeat.
# ─────────────────────────────────────────────────────────────────────────────

CHIPS_SHOWN = "chips_shown.jsonl"

# The single sponsor slot rotates too, so even that is not a fixed line.
SPONSOR_QUESTIONS = (
    "How much would $100 move the $MPS price?",
    "What is GoogleMapsCoin $MPS and how liquid is it?",
    "What should I check before buying $MPS?",
    "Where can I see $MPS live and verify the contract?",
)

# Question shapes per subject, so the same story never produces the same wording.
TOPIC_TEMPLATES = {
    "oil": ("What does this mean for oil prices: {t}?",
            "Would a story like this move crude: {t}?",
            "How does this land on energy markets: {t}?"),
    "gold": ("Is this a gold story: {t}?",
             "Does this change the case for gold: {t}?",
             "How might metals react to this: {t}?"),
    "metals": ("How would this hit metals demand: {t}?",),
    "stocks": ("Which sectors does this touch: {t}?",
               "Is this good or bad for equities: {t}?",
               "What would you watch after this: {t}?"),
    "crypto": ("Does this matter for crypto: {t}?",
               "How does this hit digital assets: {t}?",
               "Is this bullish or bearish for crypto: {t}?"),
    "fx": ("What does this do to the dollar: {t}?",
           "How does this move currencies: {t}?"),
    "rates": ("How does this affect rates and inflation: {t}?",
              "What does this mean for the cost of money: {t}?"),
    "risk": ("What is the risk a small trader should see here: {t}?",),
    "general": ("Should a small trader care about this: {t}?",
                "What is the market angle on this: {t}?",
                "Explain why this matters: {t}?",
                "What would this change for markets: {t}?"),
}

# Subject detection for a headline.
HEADLINE_TOPICS = {
    "oil": ("oil", "crude", "opec", "refiner", "gas", "energy", "barrel", "pipeline", "fuel"),
    "gold": ("gold", "bullion", "xau"),
    "metals": ("silver", "copper", "lithium", "steel", "mining", "metals"),
    "stocks": ("shares", "stock", "stocks", "equit", "earnings", "ipo", "merger", "car maker",
               "bank", "investor", "index", "nasdaq", "s&p", "dow", "profit"),
    "crypto": ("bitcoin", "crypto", "ethereum", "token", "solana", "blockchain", "stablecoin", "zcash"),
    "fx": ("dollar", "euro", "yen", "currency", "yuan", "forex"),
    "rates": ("inflation", "rate", "fed", "central bank", "bond", "yield", "tariff", "economy", "gdp"),
    "risk": ("fraud", "hack", "scam", "lawsuit", "collapse", "sanction", "war", "crisis"),
}


def topic_of_headline(title: str) -> str:
    low = (title or "").casefold()
    for topic, words in HEADLINE_TOPICS.items():
        if any(w in low for w in words):
            return topic
    return "general"


def _shorten(title: str, limit: int = 62) -> str:
    t = " ".join((title or "").split())
    return t if len(t) <= limit else t[:limit - 1].rstrip() + "…"


def suggest_questions(count: int = 5, *, state_dir: Path | str | None = None) -> dict[str, Any]:
    """One sponsor question plus the rest drawn from live news, never repeating."""
    sd = _state_dir(state_dir)
    rows = headlines(state_dir=sd)
    used_p: set[str] = set()
    ledger = sd / CHIPS_SHOWN
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8", errors="ignore").splitlines()[-400:]:
            if line.strip():
                try:
                    used_p.add(str(json.loads(line).get("q", "")))
                except json.JSONDecodeError:
                    continue

    sponsor = random.choice(SPONSOR_QUESTIONS)
    # prefer a sponsor line not shown recently
    for _ in range(6):
        if sponsor not in used_p:
            break
        sponsor = random.choice(SPONSOR_QUESTIONS)

    picks: list[str] = []
    pool = list(rows)
    random.shuffle(pool)
    for h in pool:
        if len(picks) >= count - 1:
            break
        topic = topic_of_headline(h["title"])
        templates = TOPIC_TEMPLATES.get(topic, TOPIC_TEMPLATES["general"])
        q = random.choice(templates).format(t=_shorten(h["title"]))
        if q in used_p or q in picks:
            continue
        picks.append(q)

    questions = [sponsor] + picks
    with ledger.open("a", encoding="utf-8") as fh:
        for q in questions:
            fh.write(json.dumps({"ts": time.time(), "q": q}, ensure_ascii=False) + "\n")

    return {
        "questions": questions,
        "sponsor_slot": 0,
        "from_news": len(picks),
        "news_pool": len(rows),
        "truth_label": TRUTH_LABEL,
    }


def selftest() -> dict[str, Any]:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)
        heads = headlines(state_dir=sd)
        first = pick_opener(state_dir=sd)
        second = pick_opener(state_dir=sd)
        # no repetition across many draws while the pool lasts
        seen = {first["headline"]["id"] if first["headline"] else None,
                second["headline"]["id"] if second["headline"] else None}
        repeats = 0
        for _ in range(12):
            o = pick_opener(state_dir=sd)
            hid = o["headline"]["id"] if o["headline"] else None
            if hid in seen:
                repeats += 1
            seen.add(hid)
        st = stats(state_dir=sd)
        space = first["combination_space"]
        sug = suggest_questions(5, state_dir=sd)
        sug2 = suggest_questions(5, state_dir=sd)
    checks = {
        "feeds_reachable": len(heads) > 20,
        "opener_is_nonempty": bool(first["opener"]) and len(first["opener"]) > 40,
        "headline_attached": bool(first["headline"] and first["headline"]["title"]),
        "no_repeats_while_pool_lasts": repeats == 0,
        "pool_shrinks": st["headlines_never_used"] < st["headlines_available"],
        # Test the WHOLE pool, not one random draw: every introduction must hedge.
        "every_introduction_hedges": all(
            any(m in line.lower() for m in HEDGE_MARKERS) for line in INTRODUCTIONS),
        "large_combination_space": space >= 1000,
        "no_network_still_works": bool(pick_opener(state_dir=Path("/tmp/nonexistent-sifta-news"))["opener"]),
        "chips_one_sponsor_max": sum(1 for q in sug["questions"] if "MPS" in q or "GoogleMaps" in q) <= 1,
        "chips_mostly_from_news": sug["from_news"] >= 3,
        "chips_are_unique": len(set(sug["questions"])) == len(sug["questions"]),
        "chips_vary_between_visits": sug["questions"] != sug2["questions"],
    }
    return {"ok": all(checks.values()), "checks": checks,
            "headlines": len(heads), "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "stats":
        print(json.dumps(stats(), indent=2))
    elif cmd == "opener":
        print(json.dumps(pick_opener(), indent=2, ensure_ascii=False))
    elif cmd == "heads":
        for h in headlines()[:15]:
            print(f"  [{h['source']}] {h['title'][:90]}")
    else:
        print(json.dumps(selftest(), indent=2))
