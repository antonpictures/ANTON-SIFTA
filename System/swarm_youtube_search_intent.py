#!/usr/bin/env python3
"""swarm_youtube_search_intent.py — when the owner says "search YouTube for X",
search YouTube for EXACTLY X. r305.

Live failure (George, 2026-06-01): he typed "Pls search on youtube Victoria Secret
fashion show" and Alice ran a *Google* search whose query had been expanded by a
vision-reasoning reflex into terms he never said ("lingerie wings heels"). Then a later
turn opened "white watch". An explicit search command must:

  1. go to YouTube (not Google),
  2. use the owner's words VERBATIM — never inject or sexualize terms the owner did not say.

This module is pure parsing (no Qt, no network): `parse_explicit_youtube_search(text)`
returns the verbatim query if and only if the text is an explicit "search youtube" command,
and `youtube_results_url(q)` builds the results URL. The talk widget calls this BEFORE the
vision/Google composition, so the explicit command can never be hijacked.
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Dict

# Leading politeness / address words to strip from the front of the extracted query.
_LEAD = re.compile(
    r"^(?:please|pls|plz|kindly|can\s+you|could\s+you|would\s+you|now|and|then|"
    r"alice|hey\s+alice|ok\s+alice)\s+",
    re.IGNORECASE,
)

_YOUTUBE_STT_ALIASES = re.compile(r"\b(?:you|your)\s+tube\b", re.IGNORECASE)


def _clean(q: str) -> str:
    q = (q or "").strip()
    # strip stacked leading politeness words
    prev = None
    while q and q != prev:
        prev = q
        q = _LEAD.sub("", q).strip()
    return q.strip(" ,.;:\"'").strip()


def parse_explicit_youtube_search(text: str) -> Dict[str, object]:
    """Return {'is_search': bool, 'query': str}. is_search is True only for an explicit
    'search youtube for X' style command; query is X taken VERBATIM from the owner's words
    (never expanded). Non-YouTube or non-search text returns is_search False."""
    t = _YOUTUBE_STT_ALIASES.sub("youtube", (text or "").strip())
    low = t.lower()
    if "youtube" not in low:
        return {"is_search": False, "query": ""}
    # Only the first sentence — drop trailing teaching context ("I want to teach you ...").
    # Split on sentence terminators, but protect dots inside domains like youtube.com .
    # Use a simple approach: split on ". " (dot space), "!", "?", or \n .
    parts = re.split(r'\.\s+|[!?\n]', t)
    first = parts[0].strip() if parts else t.strip()
    q = ""
    is_video_play = False
    # "search [on|in|for|the] youtube [for|the] X"
    m = re.search(r"\bsearch(?:es|ed|ing)?\b(?:\s+(?:on|in|for|the|up))*\s+youtube\b"
                  r"(?:\s+(?:for|the))*\s*(.*)", first, re.IGNORECASE)
    if m and m.group(1).strip():
        q = m.group(1)
    if not q:
        # "youtube ... search [for|the] X"  (e.g. "open youtube and search X")
        m2 = re.search(r"\byoutube\b.*?\bsearch(?:es|ed|ing)?\b(?:\s+(?:for|the))*\s*(.*)",
                       first, re.IGNORECASE)
        if m2 and m2.group(1).strip():
            q = m2.group(1)
    if not q:
        # "search [for|the] X on youtube"
        m3 = re.search(r"\bsearch(?:es|ed|ing)?\b(?:\s+(?:for|the))*\s+(.*?)\s+on\s+youtube\b",
                       first, re.IGNORECASE)
        if m3 and m3.group(1).strip():
            q = m3.group(1)

    # r313: support "open/play/watch the [OFFICIAL 2018 VICTORIA’S SECRET ...] video on youtube"
    # even without the word "search" — the user was very specific on the title.
    if not q:
        m4 = re.search(
            r"\b(?:open|play|watch|load)\s+(?:the\s+)?(.+?)\s+video\s+(?:on\s+)?youtube\b",
            first, re.IGNORECASE
        )
        if m4 and m4.group(1).strip():
            q = m4.group(1)
            is_video_play = True
    if not q:
        # "open youtube.com and open [title] video" (exact user phrasing in the live test)
        m5 = re.search(
            r"\bopen\s+youtube(?:\.com)?\s+and\s+open\s+(?:the\s+)?(.+?)\s+video\b",
            first, re.IGNORECASE
        )
        if m5 and m5.group(1).strip():
            q = m5.group(1)
            is_video_play = True
    if not q:
        # "OPEN ON YOUTUBE.COM Swim Swimwear Fashion Show - Miami Swim Week"
        # is a site-scoped search/open request, not a bare homepage load.
        m5b = re.search(
            r"\b(?:open|load|show|display)\s+(?:on|in|at)\s+youtube(?:\.com)?\s+(.+)$",
            first,
            re.IGNORECASE,
        )
        if m5b and m5b.group(1).strip():
            q = m5b.group(1)

    if not q:
        # r499: "search exact phrase on youtube.com" or "look for "X" search exact phrase on youtube.com"
        # (user: "pls look for "gemma 4 12b: unifies, encoder-free," search exact phrase on youtube.com")
        # Take the quoted string if present, else text before the marker.
        m7 = re.search(r"search exact phrase on youtube(?:\.com)?", first, re.IGNORECASE)
        if m7:
            qm = re.search(r'"([^"]+)"', first[:m7.start()])
            if qm:
                q = qm.group(1)
            else:
                q = first[:m7.start()].strip()
    if not q:
        m8 = re.search(r'look for\s+"([^"]+)"\s+search exact phrase on youtube', first, re.IGNORECASE)
        if m8:
            q = m8.group(1)
    if not q:
        # "The Victoria Secret Fashion Show you can find it on youtube.com" —
        # owner correction that names the desired YouTube target before the site.
        m6 = re.search(
            r"^\s*(.+?)\s+(?:you\s+can\s+)?(?:find|search|look\s+up)\s+(?:it\s+)?"
            r"(?:on|in)\s+youtube(?:\.com)?\b",
            first,
            re.IGNORECASE,
        )
        if m6 and m6.group(1).strip():
            q = m6.group(1)

    q = _clean(q)
    if not q:
        return {"is_search": False, "query": ""}

    return {"is_search": True, "query": q[:120], "is_video_play": is_video_play}


def youtube_results_url(query: str) -> str:
    """YouTube results page for the EXACT query (owner's words)."""
    return "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus((query or "").strip())


_POST_CORTEX_YOUTUBE_ACTION_RE = re.compile(
    r"\b(?:search|find|look\s+for|open|play|watch|load|execute|try\s+again)\b",
    re.IGNORECASE,
)

_POST_CORTEX_EXACT_TITLE_RE = re.compile(
    r"\bSearch\s+exact\s+title:\s*`([^`]{4,220})`",
    re.IGNORECASE,
)

_POST_CORTEX_WANTED_TARGET_RE = re.compile(
    r"\b(?:wanted|desired)\s+target\s+was\s*`([^`]{4,220})`",
    re.IGNORECASE,
)

_POST_CORTEX_SUGGESTED_COMMAND_RE = re.compile(
    r"`?\s*Alice,\s*search\s+YouTube\s+for\s+(.{4,220}?)\s+and\s+play"
    r"(?:\s+the\s+official\s+video)?\.?\s*`?",
    re.IGNORECASE | re.DOTALL,
)


def _clean_post_cortex_query(query: str) -> str:
    q = " ".join((query or "").strip().split())
    q = q.strip(" `\"'\t\r\n,.;")
    q = re.sub(
        r"\s+and\s+play(?:\s+the\s+official\s+video)?\.?$",
        "",
        q,
        flags=re.IGNORECASE,
    ).strip(" `\"'\t\r\n,.;")
    return q[:160]


def _post_cortex_youtube_query_from_brain(brain_text: str) -> str:
    text = brain_text or ""
    for pattern in (
        _POST_CORTEX_EXACT_TITLE_RE,
        _POST_CORTEX_WANTED_TARGET_RE,
        _POST_CORTEX_SUGGESTED_COMMAND_RE,
    ):
        m = pattern.search(text)
        if m:
            q = _clean_post_cortex_query(m.group(1))
            if q and not is_bogus_search_query(q):
                return q

    for q in re.findall(r"`([^`]{4,220})`", text):
        q = _clean_post_cortex_query(q)
        if not q or is_bogus_search_query(q):
            continue
        lowered = q.casefold()
        if (
            "official music video" in lowered
            or "official video" in lowered
            or "music video" in lowered
            or "youtube" in lowered
        ):
            return q
    return ""


def synthesize_post_cortex_youtube_bridge(owner_context: str, brain_text: str) -> Dict[str, object]:
    """Return a grounded YouTube browser action when the cortex planned one but
    emitted no tool call.

    This is deliberately post-cortex and narrow. The owner context must already
    name YouTube and an action/retry, and the cortex text must name a concrete
    target. The caller still owns the real Alice Browser effector and receipt.
    """
    owner = _YOUTUBE_STT_ALIASES.sub("youtube", owner_context or "")
    if "youtube" not in owner.casefold():
        return {"should_bridge": False, "query": "", "url": "", "reason": "owner_context_not_youtube"}
    if not _POST_CORTEX_YOUTUBE_ACTION_RE.search(owner):
        return {"should_bridge": False, "query": "", "url": "", "reason": "owner_context_no_action"}
    query = _post_cortex_youtube_query_from_brain(brain_text or "")
    if not query:
        return {"should_bridge": False, "query": "", "url": "", "reason": "brain_named_no_concrete_target"}
    if is_bogus_search_query(query):
        return {"should_bridge": False, "query": "", "url": "", "reason": "bogus_query"}
    return {
        "should_bridge": True,
        "query": query,
        "url": youtube_results_url(query),
        "reason": "post_cortex_named_youtube_target_no_tool_call",
    }


# r356 (George 2026-06-02): the local cortex sometimes emits a JSON/format token instead of
# the owner's subject — "instead of searching for the requested subject you searched 'json'". A search effector
# must NEVER fire on a structural/format token: that is the cortex's output plumbing leaking into
# the query. The effector should reject it and re-route to the cortex/owner, not search "json".
_BOGUS_QUERY_TOKENS = frozenset({
    "json", "null", "none", "undefined", "nan", "true", "false", "object", "array",
    "query", "search", "search_query", "results", "result", "data", "string", "value",
    "params", "parameters", "payload", "schema", "format", "output", "n/a", "na",
})


def is_bogus_search_query(query: str) -> bool:
    """True if `query` is a structural/format token (e.g. 'json') leaked from the cortex's
    output plumbing rather than a real owner subject. A browser/YouTube search effector should
    refuse to fire on it and re-route the turn to the cortex/owner instead of searching it."""
    if not query:
        return True
    q = str(query).strip().strip('"\'').strip().lower()
    if not q:
        return True
    if q in _BOGUS_QUERY_TOKENS:
        return True
    # a JSON fragment / structural shape, not a human subject
    if q[0] in "{[" or q[-1] in "}]" or q in {":", ",", "{}", "[]"}:
        return True
    # key:value or {"key": ... fragments
    if q.startswith(("{\"", "{'", "\"query\"", "'query'")):
        return True
    return False


__all__ = [
    "parse_explicit_youtube_search",
    "youtube_results_url",
    "is_bogus_search_query",
    "synthesize_post_cortex_youtube_bridge",
]
