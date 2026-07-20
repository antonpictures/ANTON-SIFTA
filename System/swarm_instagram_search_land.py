#!/usr/bin/env python3
"""swarm_instagram_search_land.py — r1621-08 Instagram search/profile land truth.

Glass fail: search "kylin milan" claimed explore/search but stayed on
instagram.com/; flaky SPA URL. This organ pure-resolves target URLs and
verifies whether an observed URL matches intent (profile OR explore search).

Truth label: INSTAGRAM_SEARCH_LAND_V1
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus, unquote, urlparse

TRUTH_LABEL = "INSTAGRAM_SEARCH_LAND_V1"

_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]{2,30}$")
_MULTI_WORD_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]+(?:\s+[A-Za-z0-9._]+){0,2}$")


def normalize_instagram_query(query: str) -> str:
    q = " ".join(str(query or "").split()).strip()
    q = q.lstrip("@")
    # strip site words if owner said "search kylin on instagram"
    q = re.sub(
        r"\b(?:on|in|at)\s+instagram\b|\binstagram\b|\bsearch\b|\bfor\b|\bprofile\b",
        " ",
        q,
        flags=re.I,
    )
    return " ".join(q.split()).strip()


def looks_like_instagram_handle(query: str) -> bool:
    q = normalize_instagram_query(query)
    if not q:
        return False
    # "kylin milan" → try kylinmilan as handle (common IG style)
    compact = re.sub(r"[\s._-]+", "", q)
    if _HANDLE_RE.match(compact) and len(compact) >= 3:
        return True
    if " " not in q and _HANDLE_RE.match(q):
        return True
    return False


def handle_from_query(query: str) -> str:
    q = normalize_instagram_query(query)
    compact = re.sub(r"[\s._-]+", "", q)
    if _HANDLE_RE.match(compact):
        return compact.lower()
    if _HANDLE_RE.match(q):
        return q.lower()
    return ""


def build_instagram_targets(query: str) -> dict[str, Any]:
    """Primary + fallbacks for navigate. Prefer profile when handle-like."""
    raw = str(query or "").strip()
    norm = normalize_instagram_query(raw)
    handle = handle_from_query(raw)
    explore = (
        f"https://www.instagram.com/explore/search/keyword/?q={quote_plus(norm)}"
        if norm
        else "https://www.instagram.com/"
    )
    profile = f"https://www.instagram.com/{handle}/" if handle else ""
    # Owner often wants the person, not blank explore SPA.
    if handle and looks_like_instagram_handle(raw):
        primary = profile
        fallbacks = [explore, "https://www.instagram.com/"]
        intent = "profile"
    else:
        primary = explore
        fallbacks = [profile] if profile else ["https://www.instagram.com/"]
        intent = "explore_search"
    return {
        "truth_label": TRUTH_LABEL,
        "query": raw,
        "normalized": norm,
        "handle": handle,
        "intent": intent,
        "primary_url": primary,
        "fallback_urls": [u for u in fallbacks if u and u != primary],
        "all_urls": [primary] + [u for u in fallbacks if u and u != primary],
    }


def _path_parts(url: str) -> list[str]:
    try:
        p = urlparse(str(url or ""))
        parts = [x for x in (p.path or "").split("/") if x]
        return parts
    except Exception:
        return []


def observed_matches_instagram_intent(
    observed_url: str,
    *,
    query: str = "",
    target_url: str = "",
) -> dict[str, Any]:
    """Did the browser land somewhere that satisfies search/profile intent?"""
    obs = str(observed_url or "").strip()
    low = obs.lower()
    targets = build_instagram_targets(query) if query else {}
    handle = str(targets.get("handle") or handle_from_query(query) or "").lower()
    intent = str(targets.get("intent") or "")
    primary = str(target_url or targets.get("primary_url") or "")

    if not obs:
        return {
            "ok": False,
            "reason": "empty_observed_url",
            "truth_label": TRUTH_LABEL,
        }
    if "instagram.com" not in low:
        return {
            "ok": False,
            "reason": "not_instagram_host",
            "observed": obs,
            "truth_label": TRUTH_LABEL,
        }

    parts = [p.lower() for p in _path_parts(obs)]
    # Bare home / is NOT a successful search land.
    if not parts or parts == ["accounts", "login"]:
        return {
            "ok": False,
            "reason": "stuck_on_home_or_login",
            "observed": obs,
            "intent": intent,
            "truth_label": TRUTH_LABEL,
            "retry_with": primary or targets.get("primary_url"),
        }

    # Profile land
    if handle and parts and parts[0] == handle:
        return {
            "ok": True,
            "reason": "profile_path_match",
            "observed": obs,
            "handle": handle,
            "truth_label": TRUTH_LABEL,
        }
    # explore/search
    if "explore" in parts and ("search" in parts or "tags" in parts or "keyword" in low):
        # optional: q= in query string
        q_ok = True
        if targets.get("normalized"):
            want = str(targets["normalized"]).lower().replace(" ", "")
            got = unquote(low).replace(" ", "")
            q_ok = want[:4] in got or want in got or not want
        return {
            "ok": bool(q_ok),
            "reason": "explore_search_path" if q_ok else "explore_but_query_mismatch",
            "observed": obs,
            "truth_label": TRUTH_LABEL,
        }
    # post/reel under account after search click-through — soft success if handle in path
    if handle and handle in low:
        return {
            "ok": True,
            "reason": "handle_present_in_url",
            "observed": obs,
            "handle": handle,
            "truth_label": TRUTH_LABEL,
        }
    if primary and primary.rstrip("/") in obs.rstrip("/"):
        return {
            "ok": True,
            "reason": "exact_target_prefix",
            "observed": obs,
            "truth_label": TRUTH_LABEL,
        }
    return {
        "ok": False,
        "reason": "instagram_but_not_target",
        "observed": obs,
        "intent": intent,
        "expected_primary": primary,
        "truth_label": TRUTH_LABEL,
        "retry_with": primary or explore_url_for(query),
    }


def explore_url_for(query: str) -> str:
    t = build_instagram_targets(query)
    return str(t.get("primary_url") or "https://www.instagram.com/")


def instagram_search_url(query: str) -> str:
    """Drop-in for Talk `_search_url_for_site('instagram', query)`."""
    return str(build_instagram_targets(query).get("primary_url") or "")


__all__ = [
    "TRUTH_LABEL",
    "normalize_instagram_query",
    "looks_like_instagram_handle",
    "handle_from_query",
    "build_instagram_targets",
    "observed_matches_instagram_intent",
    "explore_url_for",
    "instagram_search_url",
]
