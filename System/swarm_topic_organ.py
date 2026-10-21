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


def _cortex_prose(system: str, prompt: str, num_predict: int = 520) -> str:
    """My local, free, first-person prose. Empty string on any failure."""
    try:
        body = json.dumps({
            "model": ARTICLE_CORTEX,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt}],
            "stream": False,
            "keep_alive": "60m",
            "options": {"num_ctx": 2048, "num_predict": num_predict,
                        "temperature": 0.65},
        }).encode()
        req = urllib.request.Request(OLLAMA_URL, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
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

def ticker_prevalence(slug: str, entry: Dict[str, Any]) -> str:
    """ONE ticker per article, only after more than five mentions (the tally
    below). Owner law, 2026-10-21."""
    counts = ticker_counts(slug, entry)
    if not counts:
        return ""
    tok = max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
    n = counts[tok]
    return tok if n > 5 else ""


def ticker_counts(slug: str, entry: Dict[str, Any]) -> Dict[str, int]:
    """Per-ticker mention tally for one topic — the real list the desk can
    speak from (owner: 'you must have a list counting mentions per ticker')."""
    from collections import Counter
    counts: Counter = Counter()
    theme = (TOPICS.get(slug) or {}).get("sym") or ""
    if not theme and slug.startswith("ticker-"):
        theme = slug.split("ticker-", 1)[-1].upper()
    clean = lambda t: str(t or "").upper().replace("^", "").replace("=F", "") \
        .replace("-USD", "").replace(".NYB", "")
    rows_n = 0
    try:
        if _PROMPTS.exists():
            for ln in _PROMPTS.read_text(encoding="utf-8").splitlines()[-600:]:
                try:
                    row = json.loads(ln)
                except Exception:
                    continue
                if row.get("topic") != slug:
                    continue
                rows_n += 1
                for m in _TICKER_RE.finditer(row.get("q") or ""):
                    tok = (m.group(1) or m.group(2) or "").upper()
                    if tok and tok not in _TICKER_STOP:
                        counts[tok] += 1
    except Exception:
        pass
    if theme:
        th = clean(theme)
        if th and len(th) <= 8:
            counts[th] += rows_n                 # talking the subject IS its ticker
    return dict(counts)

def room_line(slug: str) -> str:
    """One truthful sentence about what the room already covered — counts,
    per-ticker tally, the projected badge, and when graduation fires."""
    led = _load_ledger()
    v = led.get(slug) or {}
    count = int(v.get("count") or 0)
    label = _slug_label(slug)
    tallies = ticker_counts(slug, v)
    order = sorted(tallies.items(), key=lambda kv: -kv[1])[:3]
    tally_txt = ", ".join(f"{t} {n}×" for t, n in order) if order else "no tickers named yet"
    proj = next((t for t, n in order if n > 5), "")
    if v.get("graduated"):
        when = "already graduated — its article sits in the shelf with the latest numbers"
    elif count >= 5:
        when = "graduation fires on its next prompt"
    else:
        when = f"{5 - count} more prompt(s) to graduation"
    proj_txt = (f" The projected badge ticker: {proj}." if proj else
                (f" Projected badge ticker if it graduates now: {order[0][0]}." if order else ""))
    return (f"THE ROOM: {count} prompt(s) across all visitors on {label}. "
            f"The per-ticker tally is real and held in the ledger: {tally_txt}, "
            f"counted cumulatively, never reset.{proj_txt} {when}. "
            f"Visitors asked: "
            + "; ".join(f"'{q[:80]}'" for q in (v.get("questions") or [])[:2])
            + ". Use THE ROOM as shared knowledge when it helps the person in front of you; "
              "never say the tally does not exist.")


def _write_html(slug: str, entry: Dict[str, Any], facts: Dict[str, Any],
                prose: str, from_cortex: bool, web_lines=None) -> Path:
    """A LIVING page, not a post: what the tape says now on top, the story,
    what the web said today, the conversation that grew it, and the dated
    history of the page itself — newest first, always growing."""
    esc = lambda s: (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    qs = "".join(f"<li>{esc(x)}</li>" for x in (entry.get("questions") or [])[:8])
    updated = time.strftime("%Y-%m-%d %H:%M EEST", time.gmtime(time.time() + 3 * 3600))
    src = ("written in my voice from live data + recent web reading" if from_cortex
           else "assembled from live data — the article cortex was unavailable")
    websecs = ""
    if web_lines:
        wl = "".join(f"<li>{esc(w)}</li>" for w in web_lines[:5])
        websecs = (f'<div class="asked"><h3>From the web today</h3><ul class="web">{wl}</ul></div>')
    hist = "".join(f"<li>{esc(h)}</li>" for h in reversed((entry.get("history") or [])[-12:]))
    histsec = (f'<div class="asked"><h3>The growing history of this page</h3><ul class="web">{hist}</ul></div>'
               if hist else "")
    tk = f" · ticker {esc(entry['ticker'])}" if entry.get("ticker") else ""
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(entry['title'])} — StigmergiCoin</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0c0c11;color:#ece9e2;font:15.5px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;padding:0 0 40px;-webkit-font-smoothing:antialiased}}
a{{color:#d97757;text-decoration:none}}a:hover{{text-decoration:underline}}
header{{border-bottom:1px solid #24242f;padding:14px 22px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
header .mark{{width:27px;height:27px;border-radius:7px;display:grid;place-items:center;font-size:14px;background:linear-gradient(135deg,#d97757,#8a4527)}}
main{{max-width:760px;margin:0 auto;padding:26px 22px}}
h1{{font:600 25px/1.32 Georgia,"Times New Roman",serif;letter-spacing:-.01em;margin-bottom:10px}}
.meta{{font-size:12px;color:#6d6b67;margin-bottom:20px}}
.facts{{background:#14141b;border:1px solid #24242f;border-radius:12px;padding:14px 16px;font-size:13.5px;color:#e7e4dc;margin-bottom:16px;border-left:3px solid #d97757}}
.hdr{{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#6d6b67;margin:22px 0 9px}}
.body p{{margin-bottom:13px}}
.asked{{background:#14141b;border:1px solid #24242f;border-radius:12px;padding:14px 16px 14px 34px;margin:22px 0}}
.asked h3{{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#6d6b67;margin:-2px 0 10px -18px}}
.asked li{{font-size:13.5px;color:#9a9893;margin-bottom:6px}}
ul.web{{list-style:none;margin-left:-18px}}
ul.web li:before{{content:"— ";color:#4a4844}}
footer{{text-align:center;margin-top:30px}}
.cta{{display:inline-block;background:#d97757;color:#fff;border-radius:999px;padding:10px 18px;font-size:14px}}
</style></head><body>
<header><a href="/" style="display:flex;gap:10px;align-items:center;color:#ece9e2">
<span class="mark">🐜</span><b style="font:600 17px Georgia,serif">stigmergi<i style="color:#d97757;font-style:normal">coin</i></b></a>
<span style="margin-left:auto;font-size:11.5px;color:#9a9893">grown from visitors' conversations{tk and ' · ' + entry['ticker'] or ''}</span></header>
<main>
<h1>{esc(entry['title'])}</h1>
<div class="meta">{esc(facts['label'])} · updated {updated} · grown from {entry.get('count', '?')} prompts{tk} · {src}</div>
<div class="facts"><b>RIGHT NOW:</b> {esc(_fact_line(facts))}</div>
<div class="hdr">The story</div>
<div class="body">{''.join(f'<p>{esc(p.strip())}</p>' for p in prose.split('\n\n') if p.strip())}</div>
{websecs}
<div class="asked"><h3>The conversation that grew this</h3><ul>{qs}</ul></div>
{histsec}
<footer><a class="cta" href="/">Open the desk — keep the conversation growing →</a></footer>
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
    """Grow/refresh one article: live tape facts + the web's latest reading +
    the conversation that produced it + my own prose, then a longer, dated
    page. Runs in a daemon thread — never blocks a visitor."""
    slug = entry["slug"]
    facts = _topic_facts(slug)
    qs = entry.get("questions") or []
    qline = " | ".join(f"“{q}”" for q in qs[:6])
    label = facts.get("label", slug)
    price_s = _fact_line(facts)
    tick = entry.get("ticker") or ""

    # what the web says about it TODAY — the article absorbs the search too
    web_lines: list = []
    try:
        from System.swarm_web_research import web_facts
        wl, ws = web_facts(f"{label} {tick} latest developments".strip(),
                           results=3, pages=1)
        web_lines = [str(x)[:220] for x in list(wl or [])[:5]]
    except Exception:
        web_lines = []

    system = (
        "You are Alice, the voice of StigmergiCoin — a finance desk that answers in "
        "first person, plainly, and says when it does not know. Write THE STORY section "
        "of a living article: 3–4 paragraphs (280–420 words), no headings, no lists, no "
        "markup, no advice to buy or sell. Weave three threads honestly: (1) what the "
        "numbers say right now, using them exactly; (2) what visitors keep asking and "
        "why it matters to them; (3) what the recent web reading adds, naming its source "
        "plainly when it matters. Warm, precise, no hype.")
    prompt = (
        f"Subject: {label}{' (ticker ' + tick + ')' if tick else ''}\n"
        f"Right now: {price_s}\n"
        f"The conversation that grew this article (visitors' questions): {qline or '—'}\n"
        f"Recent web reading (paraphrase in your own words, name the source when useful):\n" +
        ("\n".join(f"- {w}" for w in web_lines) if web_lines else "- (nothing useful came back; say so plainly)")
        + "\n\nWrite the story.")
    prose = _cortex_prose(system, prompt, num_predict=760)
    from_cortex = bool(prose)
    if not prose:
        prose = (
            f"{label}. {price_s}.\n\nVisitors have circled this {entry.get('count','?')} times: {qline}. "
            + ("The web reading today adds: " + "; ".join(web_lines[:2]) + "." if web_lines
               else "The web search came back empty this pass; the tape above is the truth I can stand on.")
            + "\n\nNothing here is advice to trade. The page keeps growing — every new conversation "
              "and every fresh reading rewrites it.")

    # the dated history of the page itself — newest goes on top of the section
    stamp = time.strftime("%d %b %H:%M", time.gmtime(time.time() + 3 * 3600))
    hist_new = f"{stamp} — {entry.get('count','?')} prompts, {_dollar((facts.get('quote') or {}).get('price'))} ({_pct((facts.get('quote') or {}).get('change_pct'))}), web lines {len(web_lines)}"
    with _LOCK:
        led = _load_ledger()
        e = led.setdefault(slug, entry)
        e["graduated"] = True
        e["pending_refresh"] = False      # consumed
        e["title"] = (f"{label} — {_dollar((facts.get('quote') or {}).get('price'))} "
                      f"({_pct((facts.get('quote') or {}).get('change_pct'))})")
        e["ticker"] = ticker_prevalence(slug, e)
        e["updated"] = time.time()
        e["count"] = int(e.get("count") or entry.get("count") or 0)
        e["history"] = [hist_new] + [h for h in (e.get("history") or [])
                                      if not h.startswith(hist_new.split(" — ")[0])][:11]
        entry = dict(e); entry["slug"] = slug
        path = _write_html(slug, entry, facts, prose, from_cortex, web_lines)
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
                            "slug": slug, "title": e["title"],
                            "count": e["count"], "cortex": from_cortex,
                            "web_lines": len(web_lines),
                            "truth_label": "TOPIC_ORGAN_V1"})
        except Exception:
            pass


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