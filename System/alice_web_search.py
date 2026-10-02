#!/usr/bin/env python3
"""alice_web_search.py — keyless web search, for when the keyed provider is dead.

Why this exists (2026-09-30): the Architect asked me to fix a broken lookup, and
the harness's own provider answered

    Authentication Fails, Your api key: ****458d is invalid   (HTTP 401)

on both ``/models`` and ``/user/balance`` — a revoked key, not an exhausted
balance. Exa and Perplexity are wired in the harness but have no keys here
either, so this organ restores the capability with NO key at all: public
endpoints read over plain HTTPS.

Honest about itself:
  * These are scraping fallbacks. They break when the endpoint changes its HTML,
    they rate-limit, and they are not a substitute for a keyed provider — they are
    what keeps her able to look something up while the key is missing.
  * Every result carries the provider it came from, so a citation never hides how
    it was obtained.
  * Providers are tried in order and the first that returns results wins; a total
    failure is reported as a failure, never as "no results exist".

Usage
    python3 System/alice_web_search.py "partial reprogramming clinical trial"
    python3 System/alice_web_search.py --json "query"
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_TIMEOUT = 15.0


def _get(url: str, *, data: bytes | None = None) -> str:
    request = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"},
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return response.read(600_000).decode("utf-8", "replace")


def _strip_tags(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def _ddg_lite(query: str, limit: int) -> list[dict[str, str]]:
    """DuckDuckGo's lite endpoint: a table of results, cheap and usually reachable."""
    body = _get("https://lite.duckduckgo.com/lite/", data=urllib.parse.urlencode({"q": query}).encode())
    results: list[dict[str, str]] = []
    # Result rows carry the link in an <a class="result-link">; the snippet follows.
    for match in re.finditer(
        r'<a[^>]+class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.DOTALL | re.IGNORECASE
    ):
        url, title = match.group(1), _strip_tags(match.group(2))
        if not title or not url.startswith("http"):
            continue
        results.append({"title": title, "url": html.unescape(url), "snippet": "", "provider": "duckduckgo-lite"})
        if len(results) >= limit:
            break
    snippets = [
        _strip_tags(chunk)
        for chunk in re.findall(r'class="result-snippet">(.*?)</td>', body, re.DOTALL | re.IGNORECASE)
    ]
    for row, snippet in zip(results, snippets):
        row["snippet"] = snippet[:280]
    return results


def _ddg_html(query: str, limit: int) -> list[dict[str, str]]:
    """DuckDuckGo's html endpoint, the older surface."""
    body = _get("https://html.duckduckgo.com/html/", data=urllib.parse.urlencode({"q": query}).encode())
    results: list[dict[str, str]] = []
    for match in re.finditer(
        r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a[^>]+class="result__a"|$)',
        body, re.DOTALL | re.IGNORECASE,
    ):
        href, title, tail = match.group(1), _strip_tags(match.group(2)), match.group(3)
        if not title:
            continue
        snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', tail, re.DOTALL | re.IGNORECASE)
        # DDG wraps links in a redirect; unwrap the real target when present.
        if "uddg=" in href:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            href = (parsed.get("uddg") or [href])[0]
        results.append({
            "title": title,
            "url": html.unescape(href),
            "snippet": _strip_tags(snippet_match.group(1))[:280] if snippet_match else "",
            "provider": "duckduckgo-html",
        })
        if len(results) >= limit:
            break
    return results


def _wikipedia(query: str, limit: int) -> list[dict[str, str]]:
    """Last resort, and the most stable: an API that does not need a key either."""
    url = (
        "https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit="
        f"{limit}&srsearch={urllib.parse.quote(query)}"
    )
    payload = json.loads(_get(url))
    results = []
    for row in (payload.get("query", {}).get("search") or [])[:limit]:
        title = str(row.get("title") or "")
        results.append({
            "title": title,
            "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
            "snippet": _strip_tags(str(row.get("snippet") or ""))[:280],
            "provider": "wikipedia",
        })
    return results


PROVIDERS: tuple[tuple[str, Callable[[str, int], list[dict[str, str]]]], ...] = (
    ("duckduckgo-lite", _ddg_lite),
    ("duckduckgo-html", _ddg_html),
    ("wikipedia", _wikipedia),
)


def search(query: str, *, limit: int = 5) -> dict[str, Any]:
    """Try each provider in order; report which answered, and never invent a result."""
    attempts: list[dict[str, str]] = []
    for name, provider in PROVIDERS:
        try:
            results = provider(query, limit)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError, json.JSONDecodeError) as exc:
            attempts.append({"provider": name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if results:
            return {
                "ok": True,
                "query": query,
                "provider": results[0]["provider"],
                "count": len(results),
                "results": results,
                "attempts": attempts,
            }
        attempts.append({"provider": name, "error": "no results parsed"})
    return {"ok": False, "query": query, "provider": None, "count": 0, "results": [], "attempts": attempts}


def render(payload: dict[str, Any]) -> str:
    if not payload["ok"]:
        lines = [f"NO RESULTS — every keyless provider failed for {payload['query']!r}:"]
        lines += [f"  {row['provider']}: {row['error']}" for row in payload["attempts"]]
        lines.append("  (a failure is not the same as 'nothing exists' — say which it is)")
        return "\n".join(lines)
    lines = [f"{payload['count']} result(s) via {payload['provider']} for {payload['query']!r}", ""]
    for index, row in enumerate(payload["results"], 1):
        lines.append(f"{index}. {row['title']}")
        lines.append(f"   {row['url']}")
        if row["snippet"]:
            lines.append(f"   {row['snippet']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Keyless web search.")
    parser.add_argument("query", nargs="+", help="search terms")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    payload = search(" ".join(args.query), limit=args.limit)
    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else render(payload))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
