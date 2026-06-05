#!/usr/bin/env python3
"""Browser site playbook — per-site stigmergic know-how for Alice Browser.

George 2026-05-30: "every website is a stigmergic category for Alice Browser;
features like search on TikTok live in the tiktok.com category — how to USE
Alice Browser on that site." So each site (domain = category) holds operational
skills: how to search it, how to open a profile, how to navigate it. Alice reads
the playbook for the site she is on and knows how to drive it.

This pairs with:
  * r160 swarm_browser_stigmergic_memory — categorizes VISITS by site (what she saw).
  * r158 swarm_tiktok_context — reads the current TikTok page.
This organ is the HOW: per-site operation skills, keyed by domain category.

Stigmergic + owner-confirmable: a skill the owner confirms is trusted; skills
reinforce on use. Pure + file-backed; seeded with the tiktok.com skills George
named (search, open profile). Sandbox-testable.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, quote_plus, unquote_plus, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
PLAYBOOK = "browser_site_playbook.json"
SEARCH_HISTORY = "browser_site_search_history.jsonl"
TRUTH_LABEL = "BROWSER_SITE_PLAYBOOK_V1"
SEARCH_TRUTH_LABEL = "BROWSER_SITE_SEARCH_INTEREST_V1"

SITE_ALIASES = {
    "tik tok": "tiktok.com",
    "tiktok": "tiktok.com",
    "instagram": "instagram.com",
    "insta": "instagram.com",
    "youtube": "youtube.com",
    "you tube": "youtube.com",
    "yt": "youtube.com",
    "google": "google.com",
    "x": "x.com",
    "twitter": "x.com",
}

# George 2026-06-02: "every website has a CATEGORY NAME + all the tools Alice should
# know." The domain is the stigmergic category key; this names the KIND of site so the
# cortex block reads e.g. "CATEGORY: search engine". Unknown sites fall back to "website".
SITE_KINDS = {
    "google.com": "search engine",
    "duckduckgo.com": "search engine",
    "bing.com": "search engine",
    "search.brave.com": "search engine",
    "yahoo.com": "search engine",
    "ecosia.org": "search engine",
    "startpage.com": "search engine",
    "yandex.com": "search engine",
    "perplexity.ai": "answer engine",
    "youtube.com": "video platform",
    "tiktok.com": "short-video platform",
    "instagram.com": "social photo platform",
    "x.com": "social microblog",
    "wikipedia.org": "encyclopedia",
}

_HANDLE_STOPWORDS = {
    "account",
    "alice",
    "app",
    "browser",
    "gym",
    "home",
    "morning",
    "night",
    "page",
    "profile",
    "school",
    "search",
    "site",
    "that",
    "the",
    "this",
    "tiktok",
    "tok",
    "user",
    "website",
    "work",
}


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def site_category(url_or_domain: str) -> str:
    """Domain = the stigmergic category (e.g. tiktok.com)."""
    s = (url_or_domain or "").strip().lower()
    host = urlparse(s).netloc if "//" in s or "/" in s else s
    host = re.sub(r"^www\.", "", host).split("/")[0]
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else (host or "unknown")


def site_kind(url_or_domain: str) -> str:
    """The category NAME of the site (its kind), e.g. 'search engine'. Falls back to
    'website' for sites Alice has not categorized yet."""
    return SITE_KINDS.get(site_category(url_or_domain), "website")


def site_category_from_text(text: str) -> str:
    """Infer the site category named in an owner utterance.

    The result is a durable site category (``tiktok.com``), not a temporary
    owner preference or person. The owner can search any target tomorrow; this
    only identifies which room/playbook Alice should use right now.
    """
    raw = str(text or "")
    low = raw.casefold()
    for alias, domain in sorted(SITE_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True):
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", low):
            return domain
    m = re.search(r"\b([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b", raw)
    return site_category(m.group(1)) if m else ""


def home_url_from_text(text: str) -> str:
    """Resolve a BARE site name in an utterance to that site's home URL.

    George 2026-05-30: STT garbled "open Alice browser on Instagram" and Alice
    opened the browser but did not navigate — she dropped the bare site target.
    A reasoning body reads through the noise: "he named Instagram, a site category,
    via Alice Browser → land on instagram.com." This gives the deterministic path
    that floor so "on Instagram" (no @handle, no search) still navigates. A more
    specific target (profile/search via resolve_site_navigation) should win first;
    this is the fallback when only the bare category is named.
    """
    cat = site_category_from_text(text)
    if not cat or cat == "unknown":
        return ""
    return f"https://x.com" if cat == "x.com" else f"https://www.{cat}"


def _load(state_dir: Optional[Path | str]) -> dict[str, Any]:
    try:
        data = json.loads((_state(state_dir) / PLAYBOOK).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def record_site_skill(
    domain: str, skill: str, how_to: str, *, owner_confirmed: bool = False,
    now: Optional[float] = None, state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Record 'how to do <skill> on <domain> in Alice Browser'. Reinforces use_count."""
    cat = site_category(domain)
    sk = str(skill or "").strip().lower()
    data = _load(state_dir)
    sites = data.setdefault("sites", {})
    site = sites.setdefault(cat, {})
    prior = site.get(sk, {})
    entry = {
        "how_to": str(how_to or "").strip(),
        "owner_confirmed": bool(owner_confirmed or prior.get("owner_confirmed")),
        "use_count": int(prior.get("use_count", 0)) + 1,
        "ts": float(now if now is not None else time.time()),
    }
    site[sk] = entry
    data["truth_label"] = TRUTH_LABEL
    data["updated_ts"] = entry["ts"]
    try:
        path = _state(state_dir) / PLAYBOOK
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    except Exception:
        pass
    return {"category": cat, "skill": sk, **entry}


def ensure_site_skill(
    domain: str, skill: str, how_to: str, *, owner_confirmed: bool = False,
    now: Optional[float] = None, state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Seed a site skill without pretending the owner used it again.

    ``record_site_skill`` is the reinforcement path. This helper is for default
    species knowledge such as TikTok's URL patterns, where repeated page
    snapshots should not inflate ``use_count``.
    """
    cat = site_category(domain)
    sk = str(skill or "").strip().lower()
    data = _load(state_dir)
    sites = data.setdefault("sites", {})
    site = sites.setdefault(cat, {})
    prior = site.get(sk)
    ts = float(now if now is not None else time.time())
    if prior:
        if owner_confirmed and not prior.get("owner_confirmed"):
            prior = dict(prior)
            prior["owner_confirmed"] = True
            prior["ts"] = ts
            site[sk] = prior
        entry = dict(prior)
    else:
        entry = {
            "how_to": str(how_to or "").strip(),
            "owner_confirmed": bool(owner_confirmed),
            "use_count": 1,
            "ts": ts,
        }
        site[sk] = entry
    data["truth_label"] = TRUTH_LABEL
    data["updated_ts"] = ts
    try:
        path = _state(state_dir) / PLAYBOOK
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    except Exception:
        pass
    return {"category": cat, "skill": sk, **entry}


def site_playbook(domain: str, *, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """All known operation skills for one site category."""
    return dict(_load(state_dir).get("sites", {}).get(site_category(domain), {}))


RELEARN_TRUTH_LABEL = "BROWSER_SITE_SKILL_RELEARN_V1"
SKILL_OUTCOME_LEDGER = "browser_site_skill_outcomes.jsonl"


def _persist(data: dict[str, Any], ts: float, state_dir: Optional[Path | str]) -> None:
    data["truth_label"] = TRUTH_LABEL
    data["updated_ts"] = ts
    try:
        path = _state(state_dir) / PLAYBOOK
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    except Exception:
        pass


def record_skill_outcome(
    domain: str, skill: str, ok: bool, *, note: str = "", source: str = "alice_browser",
    now: Optional[float] = None, state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """George 2026-06-02: 'websites sometimes change. When they do and Alice executes
    wrong — was good before — she learns once with the swarm.' So every time Alice runs
    a site skill, record the outcome here. Success reinforces (confidence up, relearn
    flag cleared). Failure decays confidence and — if this skill had worked before
    (use_count > 0) — flags ``needs_relearn`` so the swarm relearns the move ONCE and
    every IDE/arm inherits the new recipe via the receipt. Stigmergic: the field carries
    success/failure, not a hardcoded cage."""
    cat = site_category(domain)
    sk = str(skill or "").strip().lower()
    ts = float(now if now is not None else time.time())
    data = _load(state_dir)
    site = data.setdefault("sites", {}).setdefault(cat, {})
    entry = dict(site.get(sk) or {"how_to": "", "owner_confirmed": False, "use_count": 0, "ts": ts})
    had_worked = int(entry.get("use_count", 0)) > 0 or float(entry.get("success_count", 0)) > 0
    conf = float(entry.get("confidence", 0.6 if had_worked else 0.4))
    if ok:
        entry["success_count"] = int(entry.get("success_count", 0)) + 1
        entry["confidence"] = min(1.0, conf + 0.2)
        entry["needs_relearn"] = False
        entry["last_outcome"] = "ok"
    else:
        entry["fail_count"] = int(entry.get("fail_count", 0)) + 1
        entry["confidence"] = max(0.0, conf - 0.34)
        entry["last_outcome"] = "fail"
        # A move that WORKED before and now fails => the site likely changed. Flag it
        # for a single swarm relearn (learn once, then propagate).
        entry["needs_relearn"] = bool(had_worked)
    entry["last_note"] = str(note or "")[:300]
    entry["last_source"] = str(source or "")
    entry["ts"] = ts
    site[sk] = entry
    _persist(data, ts, state_dir)
    _append_jsonl(_state(state_dir) / SKILL_OUTCOME_LEDGER, {
        "ts": ts, "truth_label": RELEARN_TRUTH_LABEL, "kind": "SITE_SKILL_OUTCOME",
        "category": cat, "skill": sk, "ok": bool(ok), "needs_relearn": bool(entry.get("needs_relearn")),
        "confidence": entry["confidence"], "source": str(source or ""), "note": str(note or "")[:300],
    })
    return {"category": cat, "skill": sk, **entry}


def relearn_site_skill(
    domain: str, skill: str, new_how_to: str, *, owner_confirmed: bool = False,
    source: str = "swarm", now: Optional[float] = None, state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Replace a stale skill's recipe ONCE the site has changed: install the new how_to,
    bump ``version``, clear ``needs_relearn``, reset the fail streak, and receipt the change
    so every IDE doctor and arm inherits the corrected move (learn once with the swarm)."""
    cat = site_category(domain)
    sk = str(skill or "").strip().lower()
    ts = float(now if now is not None else time.time())
    data = _load(state_dir)
    site = data.setdefault("sites", {}).setdefault(cat, {})
    prior = dict(site.get(sk) or {})
    entry = dict(prior)
    entry["how_to"] = str(new_how_to or "").strip()
    entry["owner_confirmed"] = bool(owner_confirmed or prior.get("owner_confirmed"))
    entry["use_count"] = int(prior.get("use_count", 0))
    entry["version"] = int(prior.get("version", 1)) + 1
    entry["needs_relearn"] = False
    entry["fail_count"] = 0
    entry["confidence"] = 0.7
    entry["last_outcome"] = "relearned"
    entry["ts"] = ts
    site[sk] = entry
    _persist(data, ts, state_dir)
    _append_jsonl(_state(state_dir) / SKILL_OUTCOME_LEDGER, {
        "ts": ts, "truth_label": RELEARN_TRUTH_LABEL, "kind": "SITE_SKILL_RELEARN",
        "category": cat, "skill": sk, "version": entry["version"],
        "old_how_to": str(prior.get("how_to") or "")[:300], "new_how_to": entry["how_to"][:300],
        "source": str(source or ""),
    })
    return {"category": cat, "skill": sk, **entry}


def skills_needing_relearn(
    domain: Optional[str] = None, *, state_dir: Optional[Path | str] = None,
) -> list[dict[str, Any]]:
    """Every site skill currently flagged needs_relearn (the site changed under a move
    that used to work). The swarm should relearn each once and receipt the fix."""
    sites = _load(state_dir).get("sites", {})
    want = site_category(domain) if domain else ""
    out: list[dict[str, Any]] = []
    for cat, skills in sites.items():
        if want and cat != want:
            continue
        if not isinstance(skills, dict):
            continue
        for sk, e in skills.items():
            if isinstance(e, dict) and e.get("needs_relearn"):
                out.append({"category": cat, "skill": sk, "how_to": e.get("how_to", ""),
                            "fail_count": e.get("fail_count", 0), "confidence": e.get("confidence")})
    return out


def _url_template_from_skill(entry: dict[str, Any], placeholder: str) -> str:
    how_to = str((entry or {}).get("how_to") or "")
    m = re.search(r"https?://\S+" + re.escape(placeholder) + r"\S*", how_to)
    return m.group(0).rstrip(").,;") if m else ""


def _fill_site_template(template: str, placeholder: str, value: str) -> str:
    return template.replace(placeholder, quote_plus(value.strip()))


def _profile_template(skills: dict[str, Any]) -> str:
    for name in ("open profile", "profile", "open account", "account"):
        template = _url_template_from_skill(skills.get(name, {}), "<handle>")
        if template:
            return template
    return ""


def _search_template(skills: dict[str, Any]) -> str:
    for name in ("search", "site search", "find"):
        template = _url_template_from_skill(skills.get(name, {}), "<query>")
        if template:
            return template
    return ""


def _clean_spoken_handle(value: str) -> str:
    handle = re.sub(r"[^A-Za-z0-9._-]", "", str(value or "").strip())
    handle = handle.strip("._-")
    if len(handle) < 4 or len(handle) > 30:
        return ""
    if handle.casefold() in _HANDLE_STOPWORDS:
        return ""
    return handle


def _extract_spoken_profile_target(text: str) -> str:
    raw = str(text or "")
    m = re.search(r"@(?P<handle>[A-Za-z0-9._-]{2,30})", raw)
    if m:
        return _clean_spoken_handle(m.group("handle"))
    # STT often turns @handle into "at handle". This is a target, not identity:
    # any handle can fill the current site's "open profile" playbook slot.
    m = re.search(
        r"\b(?:at|profile|user|handle|creator|account)\s+@?(?P<handle>[A-Za-z0-9._-]{4,30})\b",
        raw,
        re.IGNORECASE,
    )
    return _clean_spoken_handle(m.group("handle")) if m else ""


def _extract_search_query_from_text(text: str, domain: str) -> str:
    raw = " ".join(str(text or "").split())
    if not raw:
        return ""
    site_words = [domain.replace(".", r"\."), *[re.escape(a) for a, d in SITE_ALIASES.items() if d == domain]]
    site_re = r"(?:" + "|".join(site_words) + r")"
    patterns = [
        rf"\b(?:search|look\s+up|find)\s+(?:on|in|at)\s+(?:the\s+)?{site_re}\s+(?P<query>.+)$",
        rf"\b(?:search|look\s+up|find)\s+(?:for\s+)?(?P<query>.+?)\s+(?:on|in|at)\s+(?:the\s+)?{site_re}\b",
        rf"\b(?:on|in|at)\s+(?:the\s+)?{site_re}\s+(?:search|look\s+up|find)\s+(?:for\s+)?(?P<query>.+)$",
        r"\b(?:search|look\s+up|find)\s+(?:for\s+)?(?P<query>.+)$",
    ]
    for pat in patterns:
        m = re.search(pat, raw, re.IGNORECASE)
        if not m:
            continue
        query = re.sub(
            r"\s+(?:in|on|at)\s+(?:the\s+)?alice\s+browser\b.*$",
            "",
            m.group("query"),
            flags=re.IGNORECASE,
        ).strip(" .?!,;:\"'")

        # Spoken style can be "search on YouTube Victoria ..." where the
        # engine sees "on <site>" as part of the query. Strip that prefix
        # when it is still present so the generated URL is exactly what the
        # owner said after removing the routing preposition.
        query = re.sub(
            rf"^\s*(?:the\s+)?(?:on|in|at)\s+(?:the\s+)?{site_re}\s+",
            "",
            query,
            flags=re.IGNORECASE,
        ).strip()
        # Spoken form can be "search with Google for ...", which currently leaves
        # a leading "with <site>" or "with ... for" in the raw query. Strip these
        # routing words so the final URL query remains exactly what the owner said
        # after removing navigation sugar.
        query = re.sub(
            rf"^\s*(?:the\s+)?with\s+(?:the\s+)?{site_re}\s+",
            "",
            query,
            flags=re.IGNORECASE,
        ).strip()
        # Spoken form can be "search Google for ..." where the fallback
        # pattern (no explicit routing preposition) leaves the site token
        # in the query head. Remove it so URL builders get clean intent.
        query = re.sub(
            rf"^\s*(?:the\s+)?{site_re}\s+",
            "",
            query,
            flags=re.IGNORECASE,
        ).strip()
        query = re.sub(r"^\s*for\s+", "", query, flags=re.IGNORECASE)

        if query and len(query) <= 120:
            return query
    return ""


def resolve_site_navigation(
    text: str,
    *,
    current_domain: Optional[str] = None,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Resolve a natural browser command through the current site's playbook.

    Examples:
    - "go on TikTok at anyhandle" -> fill tiktok.com's open-profile template.
    - "search Ferrari on TikTok" -> fill tiktok.com's search template.

    This intentionally stores durable *operations* in the playbook and treats
    handles/queries as ephemeral slots supplied by the owner at run time.
    """
    seed_defaults(state_dir=state_dir)
    domain = site_category_from_text(text) or site_category(current_domain or "")
    if not domain or domain == "unknown":
        return ""
    skills = site_playbook(domain, state_dir=state_dir)

    profile_template = _profile_template(skills)
    if profile_template:
        handle = _extract_spoken_profile_target(text)
        if handle:
            return _fill_site_template(profile_template, "<handle>", handle)

    search_template = _search_template(skills)
    if search_template and re.search(r"\b(search|look\s+up|find)\b", text or "", re.IGNORECASE):
        query = _extract_search_query_from_text(text, domain)
        if query:
            return _fill_site_template(search_template, "<query>", query)
    return ""


def extract_search_query(url: str) -> str:
    """Best-effort extraction of the owner query from a search URL.

    Search targets are volatile context, not durable identity. This recognizes
    common query parameters across TikTok, Google, YouTube, X, etc.
    """
    try:
        parsed = urlparse(url or "")
    except Exception:
        return ""
    params = parse_qs(parsed.query or "")
    for key in ("q", "query", "search", "search_query", "keyword", "keywords", "term", "p"):
        vals = params.get(key)
        if vals and vals[0]:
            return unquote_plus(str(vals[0])).strip()
    return ""


def record_site_search(
    domain: str,
    query: str,
    *,
    source: str = "owner_browser_context",
    owner_confirmed: bool = False,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Record a recent owner search interest for a site category.

    This is intentionally not a permanent preference. Today's Mercedes search
    can be superseded by tomorrow's Ferrari search, and then by "no cars".
    """
    clean_query = " ".join(str(query or "").split())
    row = {
        "ts": float(now if now is not None else time.time()),
        "truth_label": SEARCH_TRUTH_LABEL,
        "memory_kind": "site_search_interest",
        "category": site_category(domain),
        "query": clean_query,
        "query_key": clean_query.casefold(),
        "source": str(source or "unknown"),
        "owner_confirmed": bool(owner_confirmed),
        "preference_scope": "RECENT_CONTEXT_NOT_PERMANENT_IDENTITY",
    }
    if clean_query:
        _append_jsonl(_state(state_dir) / SEARCH_HISTORY, row)
    return row


def record_search_from_url(
    url: str,
    *,
    source: str = "browser_snapshot",
    owner_confirmed: bool = False,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """If a URL is a search result page, record its query as recent interest."""
    query = extract_search_query(url)
    if not query:
        return {}
    return record_site_search(
        url,
        query,
        source=source,
        owner_confirmed=owner_confirmed,
        now=now,
        state_dir=state_dir,
    )


def recent_site_searches(
    domain: Optional[str] = None,
    *,
    limit: int = 5,
    state_dir: Optional[Path | str] = None,
) -> list[dict[str, Any]]:
    """Latest search interests, newest first. Domain optional."""
    path = _state(state_dir) / SEARCH_HISTORY
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return []
    cat = site_category(domain or "") if domain else ""
    if cat:
        rows = [r for r in rows if r.get("category") == cat]
    rows.sort(key=lambda r: float(r.get("ts", 0)), reverse=True)
    return rows[: max(0, int(limit))]


def search_interest_block(
    domain: Optional[str] = None,
    *,
    limit: int = 5,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Cortex block for mutable owner interests on each site category."""
    rows = recent_site_searches(domain=domain, limit=limit, state_dir=state_dir)
    if not rows:
        return ""
    lines = [
        "RECENT SITE SEARCH INTERESTS (recency only; do not treat as permanent preference):"
    ]
    for row in rows:
        lines.append(
            f"- {row.get('category')}: {row.get('query')} "
            f"({row.get('source')}; {row.get('preference_scope')})"
        )
    lines.append(
        "Rule: use the newest matching search interest as current context, and let a newer owner action supersede it."
    )
    return "\n".join(lines)


def general_browsing_block() -> str:
    """General web-literacy Alice falls back to on a site she has no playbook for
    — the same moves George makes on any new page (George 2026-05-30: 'if I go on
    a new website I still look for the search button, the links, what's on the
    page'). The query is ephemeral; this approach is durable."""
    return (
        "GENERAL BROWSING (any unfamiliar site):\n"
        "- Read what the page is: title, headings, the main content visible.\n"
        "- Find the search box (usually top, a field or magnifying-glass icon); to "
        "search, type the query there — the query changes every time, the move does not.\n"
        "- Scan the visible links / nav so I know what I can reach from here.\n"
        "- In the active owner-driven browser session, reversible browsing/search is allowed by context.\n"
        "- Ask explicit confirmation before high-impact actions: payment, posting, deleting, account/security changes, following/liking/messaging, downloads, or external sharing.\n"
        "- Name what I actually see (and what I can't read, e.g. JS-rendered video) — never invent it.\n"
        "- Then act, and remember this site's features under its category for next time."
    )


def playbook_block(domain: str, *, state_dir: Optional[Path | str] = None) -> str:
    """Cortex block: how to use this site inside Alice Browser. Falls back to
    general web-literacy when the site has no learned playbook yet."""
    cat = site_category(domain)
    kind = site_kind(cat)
    skills = site_playbook(cat, state_dir=state_dir)
    if not skills:
        return (f"HOW TO USE {cat} IN ALICE BROWSER (category: {kind}): no site-specific playbook yet — "
                f"I approach it the way George does on a new site:\n{general_browsing_block()}\n"
                "I learn this site's features under its category as we use it (owner-confirmable).")
    lines = [f"HOW TO USE {cat} IN ALICE BROWSER:", f"CATEGORY: {kind}."]
    for sk, e in sorted(skills.items()):
        tag = " (owner-confirmed)" if e.get("owner_confirmed") else ""
        relearn = " (⚠ needs relearn — this site may have changed; the swarm should relearn this move once)" if e.get("needs_relearn") else ""
        lines.append(f"- {sk}: {e.get('how_to')}{tag}{relearn}")
    return "\n".join(lines)


def seed_defaults(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Seed the sites George named — tiktok.com features as a category playbook."""
    out = {}
    out["tiktok_search"] = ensure_site_skill(
        "tiktok.com", "search",
        "navigate to https://www.tiktok.com/search?q=<query> (or type in the search box, top-left)",
        state_dir=state_dir)
    out["tiktok_profile"] = ensure_site_skill(
        "tiktok.com", "open profile",
        "navigate to https://www.tiktok.com/@<handle>",
        state_dir=state_dir)
    out["tiktok_video"] = ensure_site_skill(
        "tiktok.com", "open a specific video",
        "navigate to https://www.tiktok.com/@<handle>/video/<id>",
        state_dir=state_dir)
    out["google_search"] = ensure_site_skill(
        "google.com", "search",
        "navigate to https://www.google.com/search?q=<query> (the current engine is "
        "registry-controlled; default Google inside Alice Browser; owner can switch "
        "engines stigmergically)",
        state_dir=state_dir)
    out["youtube_search"] = ensure_site_skill(
        "youtube.com", "search",
        "navigate to https://www.youtube.com/results?search_query=<query> "
        "(or type in YouTube's search box)",
        state_dir=state_dir)
    out["youtube_video"] = ensure_site_skill(
        "youtube.com", "watch video",
        "open the current /watch?v=... page; read title, channel, visible description, comments, and playback state",
        state_dir=state_dir)
    out["instagram_search"] = ensure_site_skill(
        "instagram.com", "search",
        "navigate to https://www.instagram.com/explore/search/keyword/?q=<query> "
        "(or type in Instagram's search box, top-left). For a hashtag use "
        "https://www.instagram.com/explore/tags/<tag>/",
        state_dir=state_dir)
    out["instagram_profile"] = ensure_site_skill(
        "instagram.com", "open profile",
        "navigate to https://www.instagram.com/<handle>/",
        state_dir=state_dir)
    # r383: slideshow habit per engine. "slideshow images of cats" defaults to
    # DuckDuckGo; on google.com it runs on Google Images. One image every 3.5s via the
    # Alice Browser slideshow overlay (click or Esc to stop).
    out["duckduckgo_slideshow"] = ensure_site_skill(
        "duckduckgo.com", "slideshow images",
        "open https://duckduckgo.com/?q=<query>&iax=images&ia=images, then run the Alice "
        "Browser image-slideshow overlay (one image every 3.5s; click/Esc to stop). This "
        "is the DEFAULT engine for a slideshow when not already on a search site.",
        state_dir=state_dir)
    out["google_slideshow"] = ensure_site_skill(
        "google.com", "slideshow images",
        "open https://www.google.com/search?tbm=isch&q=<query>, then run the Alice Browser "
        "image-slideshow overlay (one image every 3.5s; click/Esc to stop).",
        state_dir=state_dir)
    return out


__all__ = [
    "TRUTH_LABEL",
    "SEARCH_TRUTH_LABEL",
    "RELEARN_TRUTH_LABEL",
    "site_category",
    "site_kind",
    "SITE_KINDS",
    "record_skill_outcome",
    "relearn_site_skill",
    "skills_needing_relearn",
    "extract_search_query",
    "record_site_skill",
    "ensure_site_skill",
    "record_site_search",
    "record_search_from_url",
    "resolve_site_navigation",
    "recent_site_searches",
    "search_interest_block",
    "site_category_from_text",
    "site_playbook",
    "playbook_block",
    "general_browsing_block",
    "seed_defaults",
]
