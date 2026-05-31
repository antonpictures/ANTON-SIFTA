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
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

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

    if not parts:
        return ""

    return "CURRENT BROWSER CONTEXT (from the limb itself):\n" + "\n".join(parts)


__all__ = [
    "TRUTH_LABEL",
    "BROWSER_PAGE_DIARY_TRUTH_LABEL",
    "publish_browser_context",
    "record_browser_page_diary",
    "get_current_browser_context_block",
]
