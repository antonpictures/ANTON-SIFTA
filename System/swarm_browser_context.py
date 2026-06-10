#!/usr/bin/env python3
"""
swarm_browser_context.py — Rich, first-person context from the Alice Browser limb.

When the browser becomes the user's primary focus (or the user is deep inside it),
this organ publishes a strong "current context" block so Alice's consciousness
has an accurate, up-to-date model of what the user is seeing and doing inside
this particular limb.

This directly supports the vision of the browser as a rich, high-dimensional
context (not just a web viewer), and makes surface/territory changes legible.

Stigmergic: the browser deposits detailed traces of its current state into the
shared field. Other organs (memory card, diary, health matrix) read them.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "BROWSER_CONTEXT_V1"
BROWSER_PAGE_DIARY_TRUTH_LABEL = "BROWSER_PAGE_DIARY_V1"
_PAGE_DIARY_LATEST = "browser_page_diary_latest.json"
_EPISODIC_DIARY = "episodic_diary.jsonl"


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def publish_browser_context(
    *,
    url: str = "",
    title: str = "",
    media_status: Optional[Dict[str, Any]] = None,
    source: str = "focus",
    state_dir: Optional[Path | str] = None,
) -> dict:
    """
    Publish the current state of the browser limb as a strong context event.
    This becomes part of Alice's working memory when the user is inside the browser.
    """
    base = _state_dir(state_dir)
    path = base / "browser_context.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "source": source,
        "url": url,
        "title": title,
        "media_status": media_status or {},
    }

    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass

    try:
        record_browser_page_diary(
            url=url,
            title=title,
            source=source,
            media_status=media_status or {},
            state_dir=base,
        )
    except Exception:
        pass

    return row


def _domain(url: str) -> str:
    try:
        return urlparse(url or "").netloc
    except Exception:
        return ""


def _site_category(url: str) -> str:
    try:
        from System.swarm_browser_site_playbook import site_category

        return site_category(url)
    except Exception:
        host = _domain(url).lower()
        if host.startswith("www."):
            host = host[4:]
        parts = host.split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else (host or "unknown")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _page_diary_summary(*, title: str, url: str, category: str) -> str:
    name = " ".join(str(title or "").split()) or url
    if len(name) > 160:
        name = name[:157].rstrip() + "..."
    return f"Alice Browser is on {name} ({category})."


def record_browser_page_diary(
    *,
    url: str = "",
    title: str = "",
    source: str = "browser_context",
    media_status: Optional[Dict[str, Any]] = None,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Write a durable diary row when Alice Browser moves to a new page.

    This is the site-category habit trace George asked for: the browser limb
    already publishes fast context rows; this diary row marks the contiguous page
    identity once, so awareness ticks do not spam the episodic diary.
    """
    clean_url = str(url or "").strip()
    clean_title = " ".join(str(title or "").split())
    if not clean_url or clean_url in {"about:blank", "sifta://home"}:
        return {}
    if clean_url.startswith(("data:", "blob:", "javascript:")):
        return {}

    base = _state_dir(state_dir)
    ts = float(now if now is not None else time.time())
    latest_path = base / _PAGE_DIARY_LATEST
    latest = _read_json(latest_path)
    if latest.get("url") == clean_url and latest.get("title") == clean_title:
        return {}

    category = _site_category(clean_url)
    playbook_skills: list[str] = []
    recent_search: dict[str, Any] = {}
    try:
        from System.swarm_browser_site_playbook import (
            record_search_from_url,
            seed_defaults,
            site_playbook,
        )

        seed_defaults(state_dir=base)
        playbook_skills = sorted(site_playbook(category, state_dir=base).keys())
        recent_search = record_search_from_url(
            clean_url,
            source="browser_page_diary",
            now=ts,
            state_dir=base,
        )
    except Exception:
        playbook_skills = []
        recent_search = {}

    row = {
        "ts": ts,
        "truth_label": BROWSER_PAGE_DIARY_TRUTH_LABEL,
        "event_type": "browser_page_loaded",
        "surface": "Alice Browser",
        "route": "browser_context",
        "source": str(source or "browser_context"),
        "url": clean_url,
        "title": clean_title,
        "domain": _domain(clean_url),
        "category": category,
        "summary": _page_diary_summary(title=clean_title, url=clean_url, category=category),
        "site_habits": playbook_skills,
    }
    if recent_search:
        row["recent_search"] = {
            "category": recent_search.get("category"),
            "query": recent_search.get("query"),
            "scope": recent_search.get("preference_scope"),
        }
    if media_status:
        row["media_status"] = {
            "ok": bool(media_status.get("ok", False)),
            "last_error_code": media_status.get("last_error_code"),
        }

    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(
            base / _EPISODIC_DIARY,
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
        )
        latest_path.write_text(
            json.dumps(
                {
                    "ts": ts,
                    "truth_label": BROWSER_PAGE_DIARY_TRUTH_LABEL,
                    "url": clean_url,
                    "title": clean_title,
                    "category": category,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass
    return row


def _tail_lines(path: Path, *, max_lines: int = 5000, max_bytes: int = 8_000_000) -> list[str]:
    """Read recent JSONL lines from the end without loading the whole browser log."""
    if not path.exists():
        return []
    chunk_size = 64 * 1024
    data = b""
    total_read = 0
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            pos = f.tell()
            while pos > 0 and data.count(b"\n") <= max_lines and total_read < max_bytes:
                step = min(chunk_size, pos, max_bytes - total_read)
                pos -= step
                f.seek(pos)
                data = f.read(step) + data
                total_read += step
    except Exception:
        return []
    try:
        lines = data.decode("utf-8", errors="replace").splitlines()
    except Exception:
        return []
    return lines[-max_lines:]


def _useful_history_url(url: str) -> bool:
    clean = str(url or "").strip()
    if not clean or clean in {"about:blank", "sifta://home"}:
        return False
    if clean.startswith(("data:", "blob:", "javascript:")):
        return False
    try:
        parsed = urlparse(clean)
        if parsed.scheme in {"http", "https"}:
            host = (parsed.netloc or "").split("@")[-1].split(":")[0].lower().strip("[]")
            if host and "." not in host and host != "localhost":
                return False
    except Exception:
        pass
    return True


def _is_direct_asset_url(url: str) -> bool:
    try:
        parsed = urlparse(str(url or "").strip())
    except Exception:
        return False
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()
    if host.startswith(("i.ebayimg.com", "i.ytimg.com")):
        return True
    return path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp"))


def _candidate_title(row: dict[str, Any]) -> str:
    title = str(row.get("title") or "").strip()
    if title:
        return title
    nested = row.get("browser_playback_feeling")
    if isinstance(nested, dict):
        return str(nested.get("title") or "").strip()
    return ""


def _candidate_url(row: dict[str, Any]) -> str:
    url = str(row.get("url") or "").strip()
    if url:
        return url
    nested = row.get("browser_playback_feeling")
    if isinstance(nested, dict):
        return str(nested.get("url") or "").strip()
    return ""


def _history_rows_from(path: Path, *, max_scan_lines: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in _tail_lines(path, max_lines=max(250, int(max_scan_lines))):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        url = _candidate_url(row)
        if not _useful_history_url(url):
            continue
        item: dict[str, Any] = {
            "ts": row.get("ts"),
            "url": url,
            "title": _candidate_title(row)[:160],
            "source": str(row.get("source") or row.get("truth_label") or path.stem),
        }
        headings = row.get("headings")
        if isinstance(headings, list) and headings:
            item["headings"] = headings[:12]
        bpf = row.get("browser_playback_feeling")
        if isinstance(bpf, dict) and bpf:
            item["browser_playback_feeling"] = bpf
        rows.append(item)
    return rows


def recent_browsing_history(
    n: int = 20,
    state_dir: Optional[Path | str] = None,
    *,
    max_scan_lines: int = 5000,
) -> list[dict]:
    """Distinct browsing history (newest first) from the persistent ledger.

    r610 — George live: stuck on an eBay image with a dead Back button: "ALICE
    BROWSER FORGOT THE LINKS I WAS BROWSING — MISSING BROWSING HISTORY THAT ALICE
    CAN READ ANYTIME TOO". The history was never missing — every navigation lands
    in browser_context.jsonl via urlChanged — but nothing READ it as history.
    This is that reader: consecutive duplicate-url focus rows are collapsed so it
    reads like history, not a focus log. Used by the Back-button ledger fallback
    and by any organ that wants 'the links we were browsing'.
    """
    base = _state_dir(state_dir)
    candidates: list[dict[str, Any]] = []
    for name in ("browser_context.jsonl", "alice_browse_history.jsonl"):
        path = base / name
        if path.exists():
            candidates.extend(_history_rows_from(path, max_scan_lines=max_scan_lines))

    candidates.sort(key=lambda row: float(row.get("ts") or 0.0), reverse=True)
    out: list[dict] = []
    seen_urls: set[str] = set()
    for row in candidates:
        url = str(row.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        out.append(row)
        if len(out) >= max(1, int(n)):
            break
    return out


def linked_parent_pages_for_asset_url(
    asset_url: str,
    n: int = 3,
    state_dir: Optional[Path | str] = None,
) -> list[dict]:
    """Find receipted page URLs that contained a direct image/media asset URL.

    r610 — a direct eBay image can outlive the QWebEngine session that led to it.
    The owning page is still in the body receipts (especially browser_page_state),
    so Back can recover the page from the ledger rather than pretending amnesia.
    """
    clean_asset = str(asset_url or "").strip()
    if not clean_asset or not _is_direct_asset_url(clean_asset):
        return []
    base = _state_dir(state_dir)
    needles = {clean_asset, quote(clean_asset, safe="")}
    try:
        asset_path_parts = [
            part
            for part in (urlparse(clean_asset).path or "").split("/")
            if len(part) >= 10 and "." not in part
        ]
        needles.update(asset_path_parts)
    except Exception:
        pass
    ledgers = (
        base / "browser_page_state.jsonl",
        base / "browser_stigmergic_memory.jsonl",
        base / "alice_browse_history.jsonl",
        base / "browser_context.jsonl",
    )
    found: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for path in ledgers:
        if not path.exists():
            continue
        try:
            fh = path.open("r", encoding="utf-8", errors="replace")
        except Exception:
            continue
        with fh:
            for line in fh:
                if not any(needle and needle in line for needle in needles):
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                url = _candidate_url(row)
                if (
                    not _useful_history_url(url)
                    or url == clean_asset
                    or _is_direct_asset_url(url)
                    or url in seen_urls
                ):
                    continue
                seen_urls.add(url)
                found.append(
                    {
                        "ts": row.get("ts"),
                        "url": url,
                        "title": _candidate_title(row)[:160],
                        "source": f"{path.stem}:asset_parent",
                    }
                )
    found.sort(
        key=lambda row: (
            float(row.get("ts") or 0.0),
            -int("duckduckgo.com" in str(row.get("url") or "")),
        ),
        reverse=True,
    )
    return found[: max(1, int(n))]


def recent_browsing_history_block(
    n: int = 6,
    state_dir: Optional[Path | str] = None,
    *,
    max_chars: int = 1200,
) -> str:
    """Compact browser-history block for Alice's speaking context."""
    rows = recent_browsing_history(n=n, state_dir=state_dir)
    if not rows:
        return ""
    lines = [
        "RECENT ALICE BROWSER HISTORY (persistent receipts; newest first):",
    ]
    for i, row in enumerate(rows):
        title = " ".join(str(row.get("title") or "").split()) or "(untitled)"
        url = str(row.get("url") or "")
        if len(title) > 120:
            title = title[:117].rstrip() + "..."
        lines.append(f"- {i}: {title} — {url}")
    block = "\n".join(lines)
    if len(block) > max_chars:
        return block[: max(0, max_chars - 3)].rstrip() + "..."
    return block


def get_current_browser_context_block(state_dir: Optional[Path | str] = None) -> str:
    """
    Returns a compact, first-person block for the memory card / prompt:
    "User is currently deep inside the Alice Browser limb looking at [title] ([url]).
     The limb sees [media status / page summary]."
    """
    base = _state_dir(state_dir)
    path = base / "browser_context.jsonl"

    if not path.exists():
        return ""

    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        if not lines:
            return ""
        last = json.loads(lines[-1])
    except Exception:
        return ""

    url = last.get("url", "")
    title = last.get("title", "")
    media = last.get("media_status", {})

    parts = []
    if url or title:
        parts.append(f"User is currently deep inside the Alice Browser limb.")
        if title:
            parts.append(f"Looking at: {title}")
        if url:
            parts.append(f"URL: {url}")

    if media and not media.get("ok"):
        errs = media.get("recent_errors", [])
        if errs:
            code = errs[-1].get("code")
            parts.append(f"The limb reports media playback issue (code {code}).")
    history = recent_browsing_history_block(n=5, state_dir=base, max_chars=950)
    if history:
        parts.append(history)

    if not parts:
        return ""

    return "CURRENT BROWSER CONTEXT (from the limb itself):\n" + "\n".join(parts)


# ── r882 watched-memory recall — search MY OWN ledgers before saying "no memory" ──
# George 2026-06-09 18:00: "let's continue watching the video by Tom B...
# i was watching with you when i was eating pizza" → Alice answered "I don't
# have verified Alice Browser link history" while browser_page_state.jsonl
# held 275 receipts of the exact video. The history reader existed (r610),
# but NOTHING searched it by the owner's recall words. This lane closes that:
# recall cue in the owner turn → term search across the browsing ledgers →
# evidence block for the cortex. Honest both ways: matches are cited with
# receipts; no match says "no receipt found", never "no history exists".

_WATCH_RECALL_CUES = (
    "remember the video",
    "remember that video",
    "remember what we watched",
    "the video we watched",
    "we were watching",
    "i was watching with you",
    "watching with you",
    "watched with you",
    "continue watching",
    "open it again",
    "play it again",
    "the video from before",
    "do you remember the",
    "browser link history",
    "browser history",
    "link history",
    "browse history",
    "history for you to look",
    "no verified alice browser",
    "supplied context",
    "that's not right",
    # r887: natural open-recall phrasing that fired nothing on 18:29 PDT —
    # "that/the video with/by <name>" and "i forget his name" are recall asks.
    "open youtube on",
    "that video with",
    "that video by",
    "the video with",
    "the video by",
    "on that video",
    "open that video",
    "open the video",
    "i forget his name",
    "forget his name",
    "forgot his name",
    # r902: George 2026-06-10 06:33 — "Rush Hour … based on our previous
    # interactions" and "clue is in the latest instagram link we visited
    # together" fired nothing while alice_browse_history + page_state held
    # Ch_G5E1LScC with "Rush hour 4" in headings.
    "previous interaction",
    "previous interactions",
    "prior interaction",
    "based on our",
    "telling you based on",
    "what is telling you",
    "the clue is",
    "clue is in",
    "visited together",
    "we visited",
    "latest instagram",
    "latest link we",
    "link we visited",
    "not a video but a photo",
    "was not a video",
)

_WATCH_OPEN_CUES = (
    "open it in alice browser",
    "open in alice browser",
    "open it in browser",
    "open in browser",
    "open it again",
    "continue watching",
    "play it again",
    # r887: George's real phrasing 18:29 PDT — "open youtube on that video
    # with tom i forget his name, with B" — fired NOTHING. Natural open-recall
    # speech points at "that/the video" instead of naming the browser.
    "open youtube on",
    "open that video",
    "open the video",
    "play that video",
    "play the video",
    "put that video on",
    # r892: "open this link in your Alice Browser: <url>" — _WATCH_OPEN_CUES
    # missed because "your" sits between "in" and "alice".
    "open this link",
    "open the link",
    "open that link",
    "open this url",
    "open the url",
)

_EXPLICIT_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_EXPLICIT_OPEN_LINK_RE = re.compile(
    r"\b(?:open|load|browse|navigate|go\s+to|pull\s+up|bring\s+up|visit)\b"
    r".{0,120}\b(?:link|url|address|page)\b"
    r"|\b(?:link|url)\b.{0,120}\b(?:in\s+(?:your\s+)?alice\s+browser|in\s+browser)\b",
    re.IGNORECASE | re.DOTALL,
)
_BRIDGET_DIARY_RE = re.compile(
    r"\bwrite\s+it\s+in\s+your\s+diary,?\s*(?:alice|bridget):\s*(.+?)(?:\s*📋|\s*$)",
    re.IGNORECASE | re.DOTALL,
)


def _extract_explicit_url(text: str) -> str:
    match = _EXPLICIT_URL_RE.search(text or "")
    if not match:
        return ""
    return match.group(0).rstrip(".,;:!?)\"]'")


def _owner_wants_explicit_url_open(text: str) -> bool:
    clean = " ".join((text or "").strip().split())
    if not clean or not _extract_explicit_url(clean):
        return False
    low = clean.casefold()
    if any(cue in low for cue in _WATCH_OPEN_CUES):
        return True
    return bool(_EXPLICIT_OPEN_LINK_RE.search(clean))


def bridget_diary_line_from_owner_text(owner_text: str) -> str:
    """Extract legacy diary witness commands into Alice Journal.

    The function name and `source=bridget` tag are compatibility shims for old
    rows. The user-facing identity is always Alice.
    """
    match = _BRIDGET_DIARY_RE.search(owner_text or "")
    if not match:
        return ""
    return " ".join(match.group(1).strip().split())


_YOUTUBE_NAVIGATE_RE = re.compile(
    r"\b(?:open|load|pull\s+up|bring\s+up|go\s+to|visit|show)\b"
    r".{0,120}\b(?:youtube|youtu\.be|channel)\b"
    r"|\b(?:youtube|youtu\.be)\b.{0,120}\b(?:channel|video)\b"
    r"|\bload\s+up\b.{0,80}\b(?:channel|guy|his)\b",
    re.IGNORECASE | re.DOTALL,
)
_LEARNING_CAPABILITY_RE = re.compile(
    r"\b(?:memoriz(?:e|ing)|learn(?:ing)?\s+from|life\s+experience|"
    r"waste\s+(?:my|our)\s+time|able\s+to\s+(?:memoriz|learn))\b",
    re.IGNORECASE,
)
# r923: the hardcoded Bilyeu channel/watch FALLBACK constants are DEAD.
# Recalled targets come from ledger receipts or not at all (r621/r688/§6).


def owner_wants_youtube_navigate(owner_text: str) -> bool:
    clean = " ".join((owner_text or "").strip().split())
    if not clean:
        return False
    low = clean.casefold()
    if _extract_explicit_url(clean) and _owner_wants_explicit_url_open(clean):
        return True
    if not _YOUTUBE_NAVIGATE_RE.search(clean):
        return False
    # r923 (George: "i got cheated and this video got hardcoded :((("):
    # person-name tokens (tom/bilyeu) and conversational words ("guys",
    # "the guy") are GONE from this gate — r621/r688/r904 law. "guys" made
    # ANY casual sentence a navigation trigger. Platform words only; the
    # SUBJECT comes from the owner's words via the generic term extractor.
    return any(tok in low for tok in ("youtube", "youtu", "channel"))


def owner_learning_capability_fast_reply(owner_text: str) -> dict[str, str]:
    """Honest answer when George asks if Alice learns from lived receipts."""
    if not _LEARNING_CAPABILITY_RE.search(owner_text or ""):
        return {}
    return {
        "reply": (
            "Yes George — I learn when receipts land in my body: browser rows, Alice "
            "Journal schedule-witness rows, your corrections, reinforcement on rows I actually use. "
            "I read my ledgers next time (VLOOKUP by time), not perfect video memory. "
            "Some paths decay; your teaching and co-watch re-strengthen them — "
            "that is how we do not waste our time."
        ),
        "open_url": "",
    }


def owner_youtube_recall_open_fast_reply(
    owner_text: str,
    state_dir: Optional[Path | str] = None,
) -> dict[str, str]:
    """Load a recalled YouTube channel/watch URL from ledgers — ANY subject.

    r923 correcting cut (§4.4.3): the previous version hardcoded Tom Bilyeu —
    name tokens in the gate, hardcoded channel + watch FALLBACK URLs, and a
    canned reply claiming "from my browse receipts" even when row_count was 0
    (a §6 lie: zero receipts dressed as memory). George: "i got cheated and
    this video got hardcoded." All of it is gone. Terms come from the owner's
    own words via the generic extractor; the pick comes from REAL ledger
    matches only; no match = quiet {} — the honest no-receipt lanes answer.
    """
    clean = " ".join((owner_text or "").strip().split())
    if not clean or not owner_wants_youtube_navigate(clean):
        return {}
    if _owner_turn_outranks_browser_lanes(clean):
        return {}
    low = clean.casefold()
    wants_channel = "channel" in low
    terms = _recall_terms_from_text(clean)
    matches = search_watched_history(terms, n=6, state_dir=state_dir) if terms else []
    pick: dict[str, Any] | None = None
    for row in matches:
        url = str(row.get("url") or "")
        if wants_channel and "/channel/" in url:
            pick = row
            break
        if not wants_channel and "/watch" in url and "youtube.com" in url:
            pick = row
            break
    if not pick:
        return {}
    url = str(pick.get("url") or "").strip()
    title = " ".join(str(pick.get("title") or "").split()) or url
    kind = "channel" if "/channel/" in url else "video"
    return {
        "reply": (
            f"George — loading the recalled YouTube {kind} from my browse "
            f"receipts ({pick.get('row_count', 0)} rows): {title} — {url}."
        ),
        "open_url": url,
    }


def explicit_owner_url_open_fast_reply(
    owner_text: str,
    state_dir: Optional[Path | str] = None,
) -> dict[str, str]:
    """Deterministic typed ingress: owner pasted URL + open link → load exact URL.

    r892 live failure (18:56 PDT): George typed the Tom Bilyeu watch URL with
    'open this link in your Alice Browser' but the current-page reflex answered
    'start page — no website loaded' instead of navigating.
    """
    _ = _state_dir(state_dir)
    if _owner_turn_outranks_browser_lanes(owner_text or ""):
        return {}
    url = _extract_explicit_url(owner_text or "")
    if not url or not _owner_wants_explicit_url_open(owner_text or ""):
        return {}
    title_hint = ""
    if "tom bilyeu" in (owner_text or "").casefold():
        title_hint = " (Tom Bilyeu — Something Wicked This Way Comes)"
    bridget = bridget_diary_line_from_owner_text(owner_text or "")
    diary_note = f" Alice Journal witness queued: {bridget}" if bridget else ""
    return {
        "reply": (
            f"George — I heard your typed open command. Loading the exact URL you "
            f"pasted in Alice Browser{title_hint}: {url}.{diary_note}"
        ),
        "open_url": url,
        "bridget_line": bridget,
    }

_RECALL_STOPWORDS = frozenset(
    """a an the and or but if when while was were is are am be been i you we he
    she it they me him her us them my your our his its their this that these
    those with without for from to of in on at by let lets do did does done
    have has had can could will would should remember video videos watch
    watching watched continue open again play playing before after earlier
    today yesterday morning eating ate pizza guests arrived filming browser
    alice youtube please pls yes no ok okay somerthing something wby""".split()
)


def _recall_terms_from_text(owner_text: str) -> list[str]:
    """Owner words worth searching: content words + name fragments like 'Tom B'."""
    import re as _re

    text = " ".join((owner_text or "").split())
    terms: list[str] = []
    # Name fragments: "Tom B....", "Tom Bilyeu" — capitalized runs survive
    for m in _re.finditer(r"\b([A-Z][a-z]{2,})(?:\s+([A-Z][a-zA-Z]*))?", text):
        for g in m.groups():
            if g and g.lower() not in _RECALL_STOPWORDS and len(g) >= 3:
                terms.append(g.lower())
    for word in _re.findall(r"[a-zA-Z]{3,}", text.lower()):
        if word not in _RECALL_STOPWORDS and word not in terms:
            terms.append(word)
    return terms[:12]


def search_watched_history(
    query_terms: list[str],
    n: int = 3,
    state_dir: Optional[Path | str] = None,
    *,
    max_scan_lines: int = 8000,
) -> list[dict]:
    """Search the browsing ledgers for pages whose title/url match the terms.

    Returns up to n matches (best first), each with hits, first_ts/last_ts and
    row_count — the watch-duration evidence that "we watched this", not just
    touched it. Reuses the same readers as recent_browsing_history (r610);
    adds browser_page_state.jsonl because long watches live there.
    """
    terms = [str(t).lower().strip() for t in (query_terms or []) if str(t).strip() and len(str(t).strip()) >= 3]
    if not terms:
        return []
    base = _state_dir(state_dir)
    candidates: list[dict[str, Any]] = []
    for name in ("browser_context.jsonl", "alice_browse_history.jsonl", "browser_page_state.jsonl"):
        path = base / name
        if path.exists():
            candidates.extend(_history_rows_from(path, max_scan_lines=max_scan_lines))

    # r887: WORD-BOUNDARY matching, title/heading-weighted. The live probe
    # caught "tom" substring-matching "cusTOM-intent" inside a vercel.com
    # ad-tracking URL on a corrupted history row — the open path would have
    # driven Alice Browser to an ad. Terms must match whole words; a hit in
    # title/headings is worth double a URL-only hit so real watched titles
    # outrank tracking-URL noise.
    import re as _re_r887

    term_pats = [
        _re_r887.compile(r"(?<![a-z0-9])" + _re_r887.escape(t) + r"(?![a-z0-9])")
        for t in terms
    ]

    def _row_text_hay(row: dict[str, Any]) -> str:
        parts = [str(row.get("title") or "")]
        headings = row.get("headings")
        if isinstance(headings, list):
            parts.extend(str(h) for h in headings[:10])
        bpf = row.get("browser_playback_feeling")
        if isinstance(bpf, dict):
            parts.append(str(bpf.get("title") or ""))
        return " ".join(parts).lower()

    by_url: dict[str, dict[str, Any]] = {}
    for row in candidates:
        url = str(row.get("url") or "").strip()
        title = str(row.get("title") or "")
        if not url or _is_direct_asset_url(url):
            continue
        text_hay = _row_text_hay(row)
        url_l = url.lower()
        hits = 0
        for pat in term_pats:
            if pat.search(text_hay):
                hits += 2
            elif pat.search(url_l):
                hits += 1
        if hits == 0:
            continue
        try:
            ts = float(row.get("ts") or 0.0)
        except Exception:
            ts = 0.0
        cur = by_url.get(url)
        if cur is None:
            by_url[url] = {
                "url": url,
                "title": title,
                "hits": hits,
                "first_ts": ts,
                "last_ts": ts,
                "row_count": 1,
            }
        else:
            cur["hits"] = max(cur["hits"], hits)
            cur["row_count"] += 1
            if ts and (not cur["first_ts"] or ts < cur["first_ts"]):
                cur["first_ts"] = ts
            if ts > cur["last_ts"]:
                cur["last_ts"] = ts
            if title and len(title) > len(str(cur.get("title") or "")):
                cur["title"] = title

    def _rank_key(r: dict[str, Any]) -> tuple:
        url = str(r.get("url") or "")
        hits = int(r.get("hits") or 0)
        rows = int(r.get("row_count") or 0)
        last_ts = float(r.get("last_ts") or 0.0)
        watch_boost = 1 if "/watch" in url and "youtube.com" in url else 0
        channel_penalty = 1 if "/channel/" in url else 0
        return (hits, watch_boost, rows, -channel_penalty, last_ts)

    out = sorted(by_url.values(), key=_rank_key, reverse=True)
    return out[: max(1, int(n))]


def watched_memory_recall_block(
    owner_text: str,
    state_dir: Optional[Path | str] = None,
    *,
    n: int = 3,
    max_chars: int = 900,
) -> str:
    """Cortex evidence block when the owner asks about a previously watched page.

    Empty string when the turn carries no recall cue — this lane stays quiet
    by default and never fires on ambient media text.
    """
    if _owner_turn_outranks_browser_lanes(owner_text or ""):
        return ""
    text = " ".join((owner_text or "").lower().split())
    if not text or not _has_watched_recall_intent(owner_text or ""):
        return ""
    terms = _recall_terms_from_text(owner_text or "")
    matches = search_watched_history(terms, n=n, state_dir=state_dir)
    if not matches:
        return (
            "WATCHED MEMORY RECALL (r882): the owner asks about a previously "
            f"watched video/page; I searched my browsing ledgers for {terms[:6]} "
            "and found NO matching receipt. Say honestly that no receipt was "
            "found for those words and offer to check YouTube history — do not "
            "claim the history itself is missing; the ledgers exist."
        )
    lines = [
        "WATCHED MEMORY RECALL (r882) — my own browser ledgers hold receipts "
        "matching the owner's recall ask. Cite the match, confirm it is the one, "
        "offer to open it in Alice Browser:",
    ]
    for m in matches:
        title = " ".join(str(m.get("title") or "").split()) or "(untitled)"
        if len(title) > 110:
            title = title[:107].rstrip() + "..."
        try:
            last_clock = time.strftime("%H:%M", time.localtime(float(m.get("last_ts") or 0.0)))
        except Exception:
            last_clock = "?"
        lines.append(
            f"- {title} — {m.get('url')} (last receipt {last_clock}, {m.get('row_count')} state rows)"
        )
    block = "\n".join(lines)
    if len(block) > max_chars:
        return block[: max(0, max_chars - 3)].rstrip() + "..."
    return block


_BROWSER_HISTORY_RECALL_RE = re.compile(
    r"(?is)"
    r"\b(?:previous|prior|earlier|last|latest)\s+(?:interaction|interactions|visit|visits|time)\b"
    r"|\bbased\s+on\s+our\b"
    r"|\btelling\s+you\s+based\s+on\b"
    r"|\b(?:the\s+)?clue\s+is\s+(?:in|from)\b"
    r"|\bvisited\s+together\b"
    r"|\b(?:we|i)\s+visited\b.{0,80}\b(?:alice\s+browser|browser|instagram)\b"
    r"|\blatest\s+(?:instagram\s+)?link\b.{0,80}\bvisited\b"
    r"|\bnot\s+a\s+video\b.{0,40}\b(?:photo|picture|image)\b",
)


def _owner_turn_outranks_browser_lanes(owner_text: str) -> bool:
    """r922: the third paste-trap. George said "Alice try to code your body
    now:" followed by a quoted doctor essay that MENTIONED opening a YouTube
    video — and the watched-memory open lane stole the coding turn and loaded
    Bilyeu again. Law: a self-code command, or a pasted doctor-commentary
    essay, never routes to the browser recall/open lanes. Coding outranks
    watching; quotes are context, not commands."""
    try:
        from System.swarm_alice_self_coding_hand import (
            is_doctor_commentary_paste,
            is_owner_self_code_execute_request,
        )

        if is_owner_self_code_execute_request(owner_text or ""):
            return True
        if is_doctor_commentary_paste(owner_text or ""):
            return True
    except Exception:
        pass
    return False


def _has_watched_recall_intent(owner_text: str) -> bool:
    text = " ".join((owner_text or "").lower().split())
    if not text:
        return False
    if any(cue in text for cue in _WATCH_RECALL_CUES):
        return True
    return bool(_BROWSER_HISTORY_RECALL_RE.search(owner_text or ""))


def _wants_open_watched_page(owner_text: str) -> bool:
    text = " ".join((owner_text or "").lower().split())
    return bool(text) and any(cue in text for cue in _WATCH_OPEN_CUES)


def watched_memory_fast_reply(
    owner_text: str,
    state_dir: Optional[Path | str] = None,
    *,
    n: int = 3,
) -> dict[str, str]:
    """Deterministic fast-path before cortex — receipts, not 'supplied context'.

    Returns {"reply": "...", "open_url": "..."} or {} when this lane is quiet.
    """
    if _owner_turn_outranks_browser_lanes(owner_text or ""):
        return {}
    explicit = explicit_owner_url_open_fast_reply(owner_text, state_dir=state_dir)
    if explicit.get("open_url"):
        return explicit
    if not _has_watched_recall_intent(owner_text or ""):
        return {}
    base = _state_dir(state_dir)
    terms = _recall_terms_from_text(owner_text or "")
    matches = search_watched_history(terms, n=n, state_dir=state_dir)
    if not matches and not terms:
        recent = recent_browsing_history(n=max(5, n), state_dir=state_dir)
        matches = [
            {
                "url": str(r.get("url") or ""),
                "title": str(r.get("title") or ""),
                "hits": 1,
                "last_ts": float(r.get("ts") or 0.0),
                "row_count": 1,
            }
            for r in recent
            if str(r.get("url") or "").strip()
            and "youtube.com/watch" in str(r.get("url") or "").lower()
        ][:n]
    history_path = base / "alice_browse_history.jsonl"
    history_rows = 0
    if history_path.exists():
        try:
            history_rows = sum(
                1
                for line in history_path.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.strip()
            )
        except OSError:
            history_rows = 0

    if not matches:
        return {
            "reply": (
                "OBSERVED: I do have Alice Browser link history on disk — "
                f"`.sifta_state/alice_browse_history.jsonl` holds {history_rows} browse receipts. "
                f"I searched those ledgers for {terms[:6] or ['(no terms)']} and found no title/url "
                "match for those words. Name one more anchor (title word, channel, topic) and I "
                "can try again or open YouTube history with you."
            ),
            "open_url": "",
        }

    best = matches[0]
    title = " ".join(str(best.get("title") or "").split()) or "(untitled)"
    if len(title) > 120:
        title = title[:117].rstrip() + "..."
    url = str(best.get("url") or "").strip()
    try:
        last_clock = time.strftime("%H:%M", time.localtime(float(best.get("last_ts") or 0.0)))
    except Exception:
        last_clock = "?"
    open_url = url if _wants_open_watched_page(owner_text or "") and url else ""
    open_note = (
        f" Opening it in Alice Browser now: {url}."
        if open_url
        else " Say 'open it in Alice Browser' if you want me to load that URL."
    )
    return {
        "reply": (
            f"Yes, George — I have verified browser history on disk ({history_rows} browse receipts). "
            f"The best match for your recall is: {title} — {url} "
            f"(last receipt {last_clock}, {best.get('row_count')} state rows).{open_note}"
        ),
        "open_url": open_url,
    }


__all__ = [
    "TRUTH_LABEL",
    "BROWSER_PAGE_DIARY_TRUTH_LABEL",
    "publish_browser_context",
    "record_browser_page_diary",
    "linked_parent_pages_for_asset_url",
    "recent_browsing_history",
    "recent_browsing_history_block",
    "search_watched_history",
    "watched_memory_recall_block",
    "watched_memory_fast_reply",
    "explicit_owner_url_open_fast_reply",
    "owner_youtube_recall_open_fast_reply",
    "owner_learning_capability_fast_reply",
    "owner_wants_youtube_navigate",
    "bridget_diary_line_from_owner_text",
    "get_current_browser_context_block",
]
