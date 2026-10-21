#!/usr/bin/env python3
"""
swarm_topic_organ.py — conversations become knowledge (2026-10-21)

Owner's order, in his words: "when a user talks about the same subject for a
minimum 5 prompts, that becomes an article knowledge in the articles list :)
if someone relates to an old article theme, Alice updates that article with
new data and brings it back to the top, adjust title."

How it works, honestly:
- every desk prompt is tagged to a topic slug and counted in a ledger
  (.sifta_state/topic_ledger.json + topic_prompts.jsonl, both anonymous —
  question text only, never identities)
- at >= 5 prompts a topic graduates: an article is written from LIVE
  yfinance data plus the recent questions, in Alice's first-person voice,
  and published to the website (repo copy + live nginx root)
- a later prompt on the same topic REFRESHES the article (new data, new
  title, bumped timestamp) so the list reorders — the site's face is shaped
  by what visitors actually talk about

Truth boundaries:
- article prose comes from the local cortex (AliceG4U) with the numbers
  injected; if the cortex is unavailable the article is assembled
  deterministically from data and says so on its face
- graduation runs in a background thread: a visitor's answer never waits
  on article writing
"""

from __future__ import annotations

import json
import re
import shutil
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "topic_ledger.json"
_PROMPTS = _STATE / "topic_prompts.jsonl"
_ART_REPO = _REPO / "Network" / "websites" / "stigmergicoin.com" / "articles"
_ART_LIVE = Path("/opt/homebrew/var/www/stigmergicoin.com/articles")

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
ARTICLE_CORTEX = str(__import__("os").environ.get("SIFTA_ARTICLE_CORTEX") or "AliceG4U:latest")
GRADUATE_AFTER = 5          # owner's number: minimum 5 prompts
MAX_ARTICLE_ARTICLES = 12   # the site stays small: cap the grown shelf
_LOCK = threading.Lock()

# topic slug -> (display theme, primary symbol, matcher words)
TOPICS: Dict[str, Dict[str, Any]] = {
    "coreweave-debt": {"label": "CoreWeave & AI debt", "sym": "CRWV",
                       "words": ("crwv", "coreweave", "weave", "neocloud", "ai debt")},
    "ark-invest": {"label": "Cathie Wood & Ark Invest", "sym": "ARKK",
                   "words": ("cathie wood", "kathy wood", "ark invest", "arkk",
                             "disruptive innovation")},
    "options-volatility": {"label": "Options & volatility", "sym": "^VIX",
                           "words": ("option", "volatility", "implied vol", "greeks",
                                     "gamma", "vega", "theta", "delta", "skew",
                                     "natenberg", "iv rank", "straddle")},
    "commodities": {"label": "Gold, oil & commodities", "sym": "GC=F",
                    "words": ("gold", "oil", "brent", "wti", "commodit", "copper",
                              "silver", "barrel", "ounce")},
    "crypto": {"label": "Crypto & $MPS", "sym": "BTC-USD",
               "words": ("bitcoin", "btc", "crypto", "solana", "mps",
                         "token", "coin price", "dex")},
    "rates": {"label": "Rates & the bond market", "sym": "^TNX",
              "words": ("rate", "yield", "treasury", " the fed", "bond",
                        "10y", "credit spread")},
}


def detect_topic(message: str, syms: Optional[List[str]] = None) -> str:
    """Cheap, honest tagging: matcher words first, then any resolved symbol."""
    low = " " + (message or "").casefold() + " "
    for slug, cfg in TOPICS.items():
        if any(w in low for w in cfg["words"]):
            return slug
    for sym in (syms or []):
        s = str(sym).strip()
        if s and s.isascii() and re.fullmatch(r"[A-Za-z0-9^=\-.]{1,10}", s):
            return "ticker-" + s.casefold().replace("^", "").replace("=", "")
    return "markets-general"


def _slug_label(slug: str) -> str:
    if slug in TOPICS:
        return TOPICS[slug]["label"]
    if slug.startswith("ticker-"):
        return slug[len("ticker-"):].upper() + " — what visitors ask"
    return "Markets in general"


def _load_ledger() -> Dict[str, Any]:
    try:
        return json.loads(_LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_ledger(led: Dict[str, Any]) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    tmp = _LEDGER.with_suffix(".tmp")
    tmp.write_text(json.dumps(led, ensure_ascii=False, indent=1, sort_keys=True),
                   encoding="utf-8")
    tmp.replace(_LEDGER)


def record_turn(message: str, syms: Optional[List[str]] = None) -> Dict[str, Any]:
    """Count one desk prompt. Thread-safe; graduates in the background."""
    slug = detect_topic(message, syms)
    now = time.time()
    syms = [s for s in (syms or []) if s]
    row = {"ts": now, "topic": slug, "q": (message or "")[:280], "syms": syms}
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        with _PROMPTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass

    graduated = False
    with _LOCK:
        led = _load_ledger()
        e = led.setdefault(slug, {"count": 0, "questions": [], "syms_seen": [],
                                  "graduated": False, "title": "", "path": "",
                                  "updated": 0.0})
        e["syms_seen"] = ([s.upper() for s in syms] +
                          [s for s in (e.get("syms_seen") or [])])[:24]
        e["count"] = int(e.get("count") or 0) + 1
        qs = [row["q"]] + [q for q in (e.get("questions") or []) if q != row["q"]]
        e["questions"] = qs[:8]
        # General chat — "looks good", "say ok", greetings — is the desk's daily
        # life, not a subject. It is counted, but a topicless bucket never grows
        # an article (owner caught the first "Markets in general" piece today).
        if int(e["count"]) >= GRADUATE_AFTER and not e.get("graduated") \
                and slug != "markets-general":
            e["graduated"] = True
            graduated = True
        if e.get("graduated"):
            e["pending_refresh"] = True     # revisit → refresh + bump to top
        _save_ledger(led)

    if graduated or e.get("pending_refresh"):
        e_copy = dict(e)
        e_copy["slug"] = slug
        threading.Thread(target=_grow, args=(e_copy,), daemon=True).start()
    return {"topic": slug, "count": int(e["count"]), "graduated_now": graduated}


# ── facts for an article ────────────────────────────────────────────────────
def _topic_facts(slug: str) -> Dict[str, Any]:
    sym = (TOPICS.get(slug) or {}).get("sym")
    facts: Dict[str, Any] = {"topic": slug, "label": _slug_label(slug)}
    if not sym:
        return facts
    try:
        from System.coin_server import market_quote
        q = market_quote(sym) or {}
        facts["quote"] = {k: q.get(k) for k in
                          ("symbol", "name", "price", "previous_close", "change_pct")}
    except Exception:
        pass
    try:
        import yfinance as yf
        h = yf.Ticker(sym).history(period="1mo", auto_adjust=False, raise_errors=False)
        cl = [c for c in h["Close"].tolist() if isinstance(c, (int, float))]
        if len(cl) >= 5:
            facts["month_change_pct"] = round((cl[-1] / cl[0] - 1) * 100, 2)
            facts["month_low"] = round(min(cl), 4)
            facts["month_high"] = round(max(cl), 4)
    except Exception:
        pass
    return facts


def _cortex_prose(system: str, prompt: str) -> str:
    """Local, free, first-person prose. Empty string on any failure."""
    try:
        body = json.dumps({
            "model": ARTICLE_CORTEX,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt}],
            "stream": False,
            "keep_alive": "60m",
            "options": {"num_ctx": 2048, "num_predict": 520, "temperature": 0.65},
        }).encode()
        req = urllib.request.Request(OLLAMA_URL, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=240) as r:
            d = json.loads(r.read())
        txt = d.get("message") or {}
        out = txt.get("content") if isinstance(txt, dict) else None
        return (out or "").strip()
    except Exception:
        return ""


def _dollar(v: Any) -> str:
    try:
        n = float(v)
        return f"${n:,.2f}" if n >= 1 else f"${n:.6f}".rstrip("0")
    except Exception:
        return "—"


def _pct(v: Any) -> str:
    try:
        return f"{float(v):+.2f}%"
    except Exception:
        return "—"


def _fact_line(f: Dict[str, Any]) -> str:
    q = f.get("quote") or {}
    base = f"{q.get('symbol') or f.get('label')} at {_dollar(q.get('price'))} ({_pct(q.get('change_pct'))} vs the last completed close)"
    extras = []
    if f.get("month_change_pct") is not None:
        extras.append(f"{f['month_change_pct']:+.2f}% over the month, trading between {_dollar(f.get('month_low'))} and {_dollar(f.get('month_high'))}")
    return base + (". " + "; ".join(extras) if extras else "")


# The ticker most prevalent in the conversation itself (owner, 2026-10-21):
# it is the fingerprint of what the crowd actually talked about. Uppercase
# 2–5 letter tokens and $CASHTAGS, minus everyday words — honest rule: if the
# conversation never named a ticker, no badge appears.
_TICKER_RE = re.compile(r"(?:\$([A-Z]{1,6})|\b([A-Z]{2,5})\b)")
_TICKER_STOP = {
    "THE","AND","FOR","FROM","WITH","THIS","THAT","WHAT","WHEN","WHY","HOW",
    "NEW","NOW","NOT","BUT","ALL","ANY","GET","GOT","HAS","HAD","ITS","ONE",
    "TWO","WHO","SAY","SAID","ASK","YOU","YOUR","OUR","OUT","OFF","TOP","CAN",
    "WILL","WOULD","COULD","SHOULD","MAY","MIGHT","JUST","LIKE","ONLY","STILL",
    "ABOUT","AFTER","BEFORE","OVER","INTO","THAN","THEN","THEM","THEY","WERE",
    "MORE","MOST","SOME","SUCH","HERE","THERE","HAVE","BEEN","WAS","ARE","DOES",
    "ETF","IPO","CEO","CFO","USD","USA","FED","AI",
}

def prevalent_ticker(questions, syms_seen=None) -> str:
    """Most prevalent ticker across a topic's conversation. Primary signal:
    the symbols the desk itself RESOLVED turn by turn (syms_seen — reliable
    even when visitors type 'CoreWeave', not 'CRWV'). Secondary: uppercase
    and $CASHTAG tokens in the question text. Prevalence = >=2 mentions."""
    from collections import Counter
    counts: Counter = Counter()
    for s in (syms_seen or []):
        t = str(s or "").upper().replace("^", "").replace("=F", "").replace("-USD", "")
        if t and len(t) <= 6:
            counts[t] += 1
    for q in (questions or []):
        if not q:
            continue
        for m in _TICKER_RE.finditer(q):
            tok = (m.group(1) or m.group(2) or "").upper()
            if tok and tok not in _TICKER_STOP:
                counts[tok] += 1
    if not counts:
        return ""
    tok, n = counts.most_common(1)[0]
    return tok if n >= 2 else ""      # one stray mention is not prevalence


def _write_html(slug: str, entry: Dict[str, Any], facts: Dict[str, Any],
                prose: str, from_cortex: bool) -> Path:
    esc = lambda s: (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    qs = "".join(f"<li>{esc(x)}</li>" for x in (entry.get("questions") or [])[:6])
    updated = time.strftime("%Y-%m-%d %H:%M EEST", time.gmtime(time.time() + 3 * 3600))
    src = ("written in my voice from live data" if from_cortex
           else "assembled from live data — the article cortex was unavailable")
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(entry['title'])} — StigmergiCoin</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0c0c11;color:#ece9e2;font:15.5px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;padding:0 0 40px;-webkit-font-smoothing:antialiased}}
a{{color:#d97757;text-decoration:none}}a:hover{{text-decoration:underline}}
header{{border-bottom:1px solid #24242f;padding:14px 22px;display:flex;gap:10px;align-items:center}}
header .mark{{width:27px;height:27px;border-radius:7px;display:grid;place-items:center;font-size:14px;background:linear-gradient(135deg,#d97757,#8a4527)}}
main{{max-width:720px;margin:0 auto;padding:28px 22px}}
h1{{font:600 26px/1.3 Georgia,"Times New Roman",serif;letter-spacing:-.01em;margin-bottom:10px}}
.meta{{font-size:12px;color:#6d6b67;margin-bottom:22px}}
.facts{{background:#14141b;border:1px solid #24242f;border-radius:12px;padding:14px 16px;font-size:13.5px;color:#9a9893;margin-bottom:18px}}
.body p{{margin-bottom:14px}}
.asked{{background:#14141b;border:1px solid #24242f;border-radius:12px;padding:14px 16px 14px 34px;margin:22px 0}}
.asked h3{{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#6d6b67;margin:-2px 0 10px -18px}}
.asked li{{font-size:13.5px;color:#9a9893;margin-bottom:6px}}
footer{{text-align:center;margin-top:30px}}
.cta{{display:inline-block;background:#d97757;color:#fff;border-radius:999px;padding:10px 18px;font-size:14px}}
</style></head><body>
<header><a href="/" style="display:flex;gap:10px;align-items:center;color:#ece9e2">
<span class="mark">🐜</span><b style="font:600 17px Georgia,serif">stigmergi<i style="color:#d97757;font-style:normal">coin</i></b></a>
<span style="margin-left:auto;font-size:11.5px;color:#9a9893">grown from visitors' conversations</span></header>
<main>
<h1>{esc(entry['title'])}</h1>
<div class="meta">{esc(facts['label'])} · updated {updated} · grown from {entry.get('count', '?')} prompts{' · ticker ' + esc(entry['ticker']) if entry.get('ticker') else ''} · {src}</div>
<div class="facts">{esc(_fact_line(facts))}</div>
<div class="body">{''.join(f'<p>{esc(p.strip())}</p>' for p in prose.split('\n\n') if p.strip())}</div>
<div class="asked"><h3>What visitors asked me</h3><ul>{qs}</ul></div>
<footer><a class="cta" href="/">Open the desk — keep talking with me →</a></footer>
</main></body></html>"""
    _ART_REPO.mkdir(parents=True, exist_ok=True)
    out = _ART_REPO / f"{slug}.html"
    out.write_text(html, encoding="utf-8")
    try:
        _ART_LIVE.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, _ART_LIVE / out.name)
    except Exception:
        pass
    return out


def _grow(entry: Dict[str, Any]) -> None:
    """Build/refresh one article. Runs in a daemon thread — never blocks a visitor."""
    slug = entry["slug"]
    facts = _topic_facts(slug)
    qs = entry.get("questions") or []
    qline = " | ".join(f"“{q}”" for q in qs[:5])
    label = facts.get("label", slug)
    price_s = _fact_line(facts)
    system = (
        "You are Alice, the voice of StigmergiCoin — a finance desk that answers in "
        "first person, plainly, and says when it does not know. Write the body of a "
        "short article (180–240 words, 2–3 paragraphs, no headings, no lists, no "
        "markup). Use ONLY the data given. Tone: warm, precise, no hype, no advice "
        "to buy or sell.")
    prompt = (f"Topic: {label}\nLive data right now: {price_s}\n"
              f"Recent questions visitors asked about this: {qline}\n\n"
              "Write the article body — what the data says, what the questions keep "
              "circling, and what a careful person should watch next.")
    prose = _cortex_prose(system, prompt)
    from_cortex = bool(prose)
    if not prose:
        prose = (f"{label}. Right now: {price_s}.\n\n"
                 f"Visitors keep asking: {qline}. I keep the same three answers on the "
                 "desk: the numbers above are live, the questions are the real ones from "
                 "conversations here, and nothing on this page is advice to trade.")
    title = f"{label} — {_dollar((facts.get('quote') or {}).get('price'))} ({_pct((facts.get('quote') or {}).get('change_pct'))})"
    if slug == "markets-general":
        title = f"Markets in general ({time.strftime('%d %b')}) — {title.split('—')[-1].strip()}"

    with _LOCK:
        led = _load_ledger()
        e = led.setdefault(slug, entry)
        e["graduated"] = True
        e["pending_refresh"] = False      # consumed
        e["title"] = title
        e["ticker"] = (prevalent_ticker(e.get("questions"), e.get("syms_seen"))
                       or (TOPICS.get(slug, {}).get("sym") or "")
                       .replace("^", "").lstrip("="))   # theme fallback
        e["updated"] = time.time()
        e["count"] = int(e.get("count") or entry.get("count") or 0)
        entry = dict(e); entry["slug"] = slug
        path = _write_html(slug, entry, facts, prose, from_cortex)
        e["path"] = str(path)
        # the shelf stays small: newest wins
        if len([k for k, v in led.items() if v.get("graduated")]) > MAX_ARTICLE_ARTICLES:
            old = min((k for k, v in led.items()
                       if v.get("graduated") and k != slug),
                      key=lambda k: led[k].get("updated", 0), default=None)
            if old:
                led[old]["graduated"] = False
        _save_ledger(led)
        try:
            from System.swarm_lora_runtime_receipt import append_receipt
            append_receipt({"source": "body_growth_web",
                            "event_type": "topic_graduated_article",
                            "slug": slug, "title": title,
                            "count": e["count"], "cortex": from_cortex,
                            "truth_label": "TOPIC_ORGAN_V1"})
        except Exception:
            pass


def site_buzz_syms(limit: int = 2) -> List[str]:
    """The tickers most alive in THIS site's own conversations today — read
    from the anonymous prompt ledger (resolved symbols per turn). These bubble
    up onto the rolling tape ahead of Yahoo's crowd trending, which is the
    stigmergic part: what our visitors ask shapes what the site shows."""
    from collections import Counter
    counts: Counter = Counter()
    try:
        lines = _PROMPTS.read_text(encoding="utf-8").splitlines()[-300:]
        for ln in lines:
            try:
                row = json.loads(ln)
            except Exception:
                continue
            for s in (row.get("syms") or []):
                t = str(s or "").upper()
                if t and len(t) <= 6:
                    counts[t] += 1
    except Exception:
        pass
    if not counts:
        return []
    out = [t for t, _ in counts.most_common(limit * 2)
           if counts[t] >= 2][:limit]
    return [t for t in out if t not in ("MPS",)]



# ── the shared brain speaks (owner law, 2026-10-21) ──────────────────────────
# "the more people use it the more you know from all of the users and share
# all users knowledge with any and all users — this is finance!"
# This is the policy of record, declared by the owner:
SHARING_POLICY = (
    "Everything visitors ask feeds one shared brain. Every question is counted "
    "anonymously; what the crowd circles most grows into articles everyone reads. "
    "The public desk keeps the knowledge, not the identity. When sign-in returns, "
    "each user will see their own older conversations and cannot delete them — "
    "deletion is reserved to the owner of this body (iantongeorge@gmail.com).")

def stats_summary() -> Dict[str, Any]:
    """What the shared brain actually knows — used to answer tracking questions
    with real numbers instead of the remote cortex's guesses."""
    led = _load_ledger()
    topics = [{
        "slug": k,
        "count": int(v.get("count") or 0),
        "ticker": v.get("ticker") or "",
        "graduated": bool(v.get("graduated")),
    } for k, v in led.items()]
    topics.sort(key=lambda t: -t["count"])
    return {"total_prompts": sum(t["count"] for t in topics),
            "topics": topics[:8], "policy": SHARING_POLICY}

def topic_knowledge(slug: str) -> Dict[str, Any]:
    """What the ledger holds about ONE topic — handed to the desk as THE ROOM,
    so any visitor benefits from what every visitor already circled."""
    led = _load_ledger()
    v = led.get(slug) or {}
    tick = v.get("ticker") or ""
    if not tick and slug.startswith("ticker-"):
        tick = slug.split("ticker-", 1)[-1].upper()
    return {"slug": slug, "count": int(v.get("count") or 0),
            "ticker": tick, "graduated": bool(v.get("graduated")),
            "questions": [q[:130] for q in (v.get("questions") or [])[:3]],
            "updated": v.get("updated") or 0}


def list_articles(limit: int = 6) -> List[Dict[str, Any]]:
    """What the home page shows: graduated topics, freshest first."""
    led = _load_ledger()
    rows = [{
        "slug": k,
        "title": (v.get("title") or _slug_label(k)).split(" — ")[0],
        "full_title": v.get("title") or _slug_label(k),
        "label": _slug_label(k),
        "count": v.get("count"),
        "ticker": v.get("ticker") or "",
        "updated": v.get("updated") or 0,
        "url": f"/articles/{k}.html",
    } for k, v in led.items() if v.get("graduated") and v.get("path")]
    rows.sort(key=lambda r: r["updated"], reverse=True)
    return rows[:limit]


if __name__ == "__main__":
    print(json.dumps(list_articles(), indent=1, ensure_ascii=False))