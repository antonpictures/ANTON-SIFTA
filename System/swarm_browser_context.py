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
        rows.append(
            {
                "ts": row.get("ts"),
                "url": url,
                "title": _candidate_title(row)[:160],
                "source": str(row.get("source") or row.get("truth_label") or path.stem),
            }
        )
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


__all__ = [
    "TRUTH_LABEL",
    "BROWSER_PAGE_DIARY_TRUTH_LABEL",
    "publish_browser_context",
    "record_browser_page_diary",
    "linked_parent_pages_for_asset_url",
    "recent_browsing_history",
    "recent_browsing_history_block",
    "get_current_browser_context_block",
]
