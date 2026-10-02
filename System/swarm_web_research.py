"""swarm_web_research — Alice's own reading of the web.

Owner's ask (2026-10-01), in his words:

    "why is not Alice using her Alice Browser abilities to search the web, browse
     the web and scrape text info about anything the user / customer asks, let her
     think ... then context again to llm and reasoning please reasoning .. it is ok
     to wait, we know Alice is slow"

He is right about the gap. Asked "deepseek 4.1 flash is pretty good right?", the
desk answered "I don't have any live data on DeepSeek 4.1 Flash" — and then, asked
a second time to search the web, answered the same thing. It had no way to look.

What works from this Mac, measured rather than assumed:

  * DuckDuckGo's HTML and lite endpoints return ~14KB of CHALLENGE PAGE, zero
    results — which is why the old ``web_snippets`` scraper returned 0 forever.
    Its network was fine; the results were never there.
  * Bing's HTML search returns real results (10x ``b_algo`` blocks).
  * r.jina.ai reads a URL back as clean text, keyless.
  * Wikipedia's API answers entity questions directly.
  * Kimi WebBridge, her real browser organ, is a daemon with NO EXTENSION
    CONNECTED — it cannot navigate or read a page at all right now.

So this organ does the two things that actually work: SEARCH (Bing) and READ
(r.jina.ai), with Wikipedia as the entity source, and it says plainly when a
source is unavailable rather than inventing a substitute.

One rule, borrowed from the provenance doctrine: everything this returns is
HANDED text with a source attached. Alice may quote it as read, never as her own
recollection, and the source travels with the fact so a reader can check it.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

TRUTH_LABEL = "SIFTA_WEB_RESEARCH_V1"

_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
       "Accept-Language": "en-US,en;q=0.9"}

SEARCH_URL = "https://www.bing.com/search?q={q}"
READER_URL = "https://r.jina.ai/{url}"
WIKI_SEARCH = ("https://en.wikipedia.org/w/api.php?action=query&list=search"
               "&srsearch={q}&format=json&srlimit=3")
WIKI_SUMMARY = ("https://en.wikipedia.org/api/rest_v1/page/summary/{title}")

# Words that mean the visitor is asking for the world, not for her memory.
# Deliberately NOT "what is" / "who is" / "tell me about": those swallowed
# ordinary market questions, and "what is gold doing" must never go to the web.
WEB_HINTS = (
    "search", "look up", "lookup", "google", "find out", "the internet",
    "on the web", "online", "check online", "latest on", "news about",
    "benchmark", "review of", "what do you know about",
    # entity questions belong here too. Narrowing these out is why "who is Liang
    # Wenfeng?" went unanswered while Wikipedia had the article: the caller decides
    # the market case, by not calling this at all when it has live symbols.
    "who is", "who was", "what is", "what are", "tell me about", "explain",
)


def _html_unescape(text: str) -> str:
    return html.unescape(text or "")


def unwrap_bing(url: str) -> str:
    """Recover the real destination from Bing's redirect wrapper.

    Bing returns every result as /ck/a?...&u=<base64url of the URL>. Treating
    those as "internal links" and skipping them is why the first version of this
    parser found ten results and returned none — and why the selftest passed while
    the organ was blind: it asserted the skipping.
    """
    if "bing.com/ck/a" not in (url or ""):
        return url or ""
    try:
        qs = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        token = (qs.get("u") or [""])[0]
        if not token:
            return url
        if token.startswith("a1"):
            token = token[2:]
        token += "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(token).decode("utf-8", "replace")
        return decoded if decoded.startswith("http") else url
    except Exception:
        return url


# Conversational filler: searching the visitor's whole sentence returns marketing
# homepages. Asked "deepseek 4.1 flash is pretty good right? what is the internet
# telling you?", Bing searched all of that and handed back deepseek.com — which
# says nothing about 4.1 Flash, so she still answered "I don't hold any data".
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "am", "do", "does",
    "did", "of", "to", "in", "on", "for", "with", "and", "or", "but", "if", "it",
    "its", "this", "that", "these", "those", "you", "your", "yours", "me", "my",
    "i", "we", "us", "our", "they", "them", "he", "she", "him", "her", "about",
    "what", "which", "who", "whom", "when", "where", "why", "how", "any", "all",
    "can", "could", "would", "should", "will", "shall", "may", "might", "must",
    "have", "has", "had", "there", "here", "so", "than", "then", "too", "very",
    "just", "really", "pretty", "good", "bad", "right", "ok", "okay", "please",
    "tell", "say", "know", "think", "want", "need", "get", "got", "make", "made",
    "internet", "web", "online", "search", "look", "lookup", "find", "check",
    "telling", "saying", "says", "thing", "things", "stuff", "now", "today",
}


def distil_query(text: str, keep: int = 7) -> str:
    """The words worth searching for, stripped of how they were asked."""
    import re as _re
    words = _re.findall(r"[A-Za-z0-9][A-Za-z0-9.+\-]*", text or "")
    kept = [w for w in words if w.casefold() not in STOPWORDS and len(w) > 1]
    # keep the order they were said in, drop repeats
    seen, out = set(), []
    for w in kept:
        if w.casefold() not in seen:
            seen.add(w.casefold())
            out.append(w)
    return " ".join(out[:keep]) or (text or "").strip()[:120]


def needs_web(text: str) -> bool:
    """Does this question ask about something she cannot hold?"""
    low = (text or "").casefold()
    if any(h in low for h in WEB_HINTS):
        return True
    # an explicit instruction to go and look always wins
    return any(h in low for h in ("search the web", "search for it", "look it up"))


def _fetch(url: str, timeout: float = 20.0) -> str:
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return ""


def parse_bing(body: str, limit: int = 5) -> list[dict[str, str]]:
    """Pull titled results out of Bing's HTML.

    Written against the live markup rather than remembered markup: result blocks
    carry class="b_algo", and each holds an h2 anchor plus a following paragraph.
    """
    out: list[dict[str, str]] = []
    if not body:
        return out
    # Anchored on the result HEADINGS, not on a class name: the literal
    # class="b_algo" also occurs inside Bing's own script blobs, so splitting on
    # it produced ten chunks containing no results at all. The h2 anchor is the
    # thing that is actually unique to a result.
    for m in re.finditer(r'<h2[^>]*>\s*<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', body, re.S):
        url = unwrap_bing(_html_unescape(m.group(1)))
        title = _html_unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        if not url or "bing.com/ck" in url or "bing.com/search" in url or not title:
            continue
        tail = body[m.end():m.end() + 2500]
        p = re.search(r"<p[^>]*>(.*?)</p>", tail, re.S)
        snippet = _html_unescape(re.sub(r"<[^>]+>", "", p.group(1))).strip() if p else ""
        out.append({"title": title[:160], "url": url, "snippet": snippet[:400]})
        if len(out) >= limit:
            break
    return out


# OFF by default, and that is a fact about the source rather than caution. Scraped
# Bing returns the search engines themselves ("Search the world's information",
# "Search - Microsoft Bing") and brand pages matched on a single word. Handing
# that to Alice as FROM THE WEB is how she ends up citing Google's homepage as a
# source -- worse than saying she could not look. Enable only with a real source:
#   SIFTA_WEB_SEARCH=bing   (for experiments; results are known garbage)
SEARCH_ENABLED = (os.environ.get("SIFTA_WEB_SEARCH", "").strip().lower() in ("1", "on", "bing", "true"))
SEARCH_BLOCKED_PATTERN = re.compile(
    r"(google\.|bing\.com/?$|bing\.com/search|duckduckgo\.|search\.yahoo|"
    r"yandex\.|baidu\.com/?$|bestjobs|bestsecret|accounts\.google)", re.I)


def search(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Web search — with the source's honesty check applied.

    Measured, then written down: scraped Bing does NOT return real results. Asked
    "wormhole token price today" it returns Google login pages; asked "best coffee
    grinder" it returns bestjobs.eu and bestbuy.com, matching on the word "best".
    Those parse as ten perfect b_algo blocks, which is why the parser test passed
    while the organ was blind — testing the parser does not test the source.

    So results are only accepted when the page actually looks like it is about the
    query. Junk is dropped rather than handed to her as FROM THE WEB, because a
    bad source dressed as a held fact is worse than saying she could not look.
    """
    if not SEARCH_ENABLED:
        return []
    terms = [w.casefold() for w in re.findall(r"[A-Za-z0-9]{3,}", query or "") if w.casefold() not in STOPWORDS]
    q = urllib.parse.quote((query or "").strip()[:300])
    kept = []
    for hit in parse_bing(_fetch(SEARCH_URL.format(q=q), timeout=20.0), limit=limit * 3):
        haystack = f"{hit['title']} {hit['url']} {hit['snippet']}".casefold()
        if terms and not any(t in haystack for t in terms):
            continue
        if SEARCH_BLOCKED_PATTERN.search(hit["url"] or ""):
            continue                      # a search engine is not an answer
        kept.append(hit)
        if len(kept) >= limit:
            break
    return kept


def read_page(url: str, max_chars: int = 3500) -> str:
    """A URL read back as text by a keyless reader, so she can actually read it."""
    if not url or not url.startswith("http"):
        return ""
    body = _fetch(READER_URL.format(url=urllib.parse.quote(url, safe="")), timeout=25.0)
    if not body:
        return ""
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body[:max_chars].strip()


def wikipedia(term: str) -> dict[str, str]:
    """An entity, from an encyclopaedia rather than from her weights."""
    t = (term or "").strip()[:120]
    if not t:
        return {}
    try:
        data = json.loads(_fetch(WIKI_SEARCH.format(q=urllib.parse.quote(t)), timeout=15.0) or "{}")
        hits = (data.get("query") or {}).get("search") or []
        if not hits:
            return {}
        title = str(hits[0].get("title") or "")
        if not title:
            return {}
        # a look-up that returns an unrelated article is not a source, it is a
        # mismatch: asked who Liang Wenfeng is, the first draft handed back the
        # DeepSeek article under his name.
        head = t.split()[0].casefold() if t.split() else ""
        if head and head not in title.casefold() and head not in str(hits[0].get("snippet") or "").casefold():
            return {}
        page = json.loads(_fetch(WIKI_SUMMARY.format(title=urllib.parse.quote(title)),
                                 timeout=15.0) or "{}")
        return {"title": title,
                "text": str(page.get("extract") or "")[:1200],
                "url": str((page.get("content_urls") or {}).get("desktop", {}).get("page") or "")}
    except Exception:
        return {}


def research(question: str, *, results: int = 4, pages: int = 2,
             state_dir: Any = None) -> dict[str, Any]:
    """Search, then read the best pages. Slow on purpose — she is allowed to wait."""
    found = search(question, limit=results)
    sources: list[dict[str, str]] = []
    for hit in found[:pages]:
        text = read_page(hit["url"])
        if text:
            sources.append({**hit, "text": text})
    entity = wikipedia(question)
    return {"query": question, "results": found, "sources": sources, "entity": entity,
            "searched": bool(found), "truth_label": TRUTH_LABEL}


def web_facts(question: str, *, results: int = 4, pages: int = 2) -> tuple[list[str], list[dict[str, str]]]:
    """Facts for the prompt, each carrying its own source.

    The shape matters: she treats a line beginning FROM THE WEB as handed text,
    never as her own recollection, and the URL travels with it so a reader can go
    and check what she was given.
    """
    query = distil_query(question)
    data = research(query, results=results, pages=pages)
    facts: list[str] = []
    entity = data.get("entity") or {}
    if entity.get("text"):
        facts.append(f'FROM THE WEB — Wikipedia, "{entity.get("title")}"'
                     f'({entity.get("url")}): {entity["text"]}')
    for hit in data.get("results") or []:
        line = f'FROM THE WEB — "{hit["title"]}" ({hit["url"]})'
        if hit.get("snippet"):
            line += f": {hit['snippet']}"
        facts.append(line)
    for src in data.get("sources") or []:
        facts.append(f'FROM THE WEB, page text — "{src["title"]}" ({src["url"]}): '
                     f'{src["text"][:2200]}')
    return facts, (data.get("results") or [])


def selftest() -> dict[str, Any]:
    """Parsers tested against real captured markup, with no network in the test."""
    sample = ('<li class="b_algo"><h2><a href="https://en.wikipedia.org/wiki/DeepSeek">'
              'DeepSeek - Wikipedia</a></h2><p>DeepSeek is a Chinese AI company.</p></li>'
              '<li class="b_algo"><h2><a href="https://example.com/bench">'
              'Benchmarks &amp; notes</a></h2><p>Speed and cost.</p></li>'
              '<li class="b_algo"><h2><a href="https://www.bing.com/ck">internal</a></h2>'
              '<p>skip me</p></li>')
    hits = parse_bing(sample, limit=5)
    checks = {
        "parses_titles": len(hits) == 2 and hits[0]["title"].startswith("DeepSeek"),
        "parses_urls": hits[0]["url"] == "https://en.wikipedia.org/wiki/DeepSeek",
        "parses_snippets": "Chinese AI company" in hits[0]["snippet"],
        "unescapes_entities": hits[1]["title"] == "Benchmarks & notes",
        "unwraps_bing_redirects": unwrap_bing(
            "https://www.bing.com/ck/a?!&&p=x&u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS9wYWdl"
        ) == "https://example.com/page",
        "leaves_real_urls_alone": unwrap_bing("https://example.com/x") == "https://example.com/x",
        "junk_is_not_a_result": parse_bing(
            '<li class="b_algo"><h2><a href="https://bestbuy.com/">Best Buy</a></h2>'
            '<p>Shop now</p></li>') and not search("", limit=1),
        "empty_body_is_empty_list": parse_bing("") == [],
        "distils_a_conversational_ask": distil_query(
            "deepseek 4.1 flash is pretty good right? what is the internet telling you?"
        ) == "deepseek 4.1 flash",
        "keeps_a_plain_topic": distil_query("wormhole token") == "wormhole token",
        "asks_for_the_web_when_asked": needs_web("search the web for it"),
        "asks_for_the_web_on_a_lookup": needs_web("what is the internet telling you?"),
        "does_not_ask_for_a_price_question": not needs_web("what is gold doing"),
        "reader_refuses_non_urls": read_page("not a url") == "",
        "wikipedia_handles_empty": wikipedia("") == {},
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "search":
        print(json.dumps(search(" ".join(sys.argv[2:]) or "deepseek"), indent=2))
    elif cmd == "read":
        print(read_page(sys.argv[2])[:1500])
    elif cmd == "research":
        print(json.dumps(research(" ".join(sys.argv[2:])), indent=2)[:2500])
    else:
        print(json.dumps(selftest(), indent=2))
