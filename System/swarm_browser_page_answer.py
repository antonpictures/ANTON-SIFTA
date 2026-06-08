#!/usr/bin/env python3
"""Browser page answer — Alice can name the page open in her own browser.

George 2026-05-30 live bug: with TikTok open, asked "what page do I have open?",
Alice said "I can't truthfully name the page" — even though the browser snapshot
on disk held the URL and title. The mistake: she conflated "I have no readable
page TEXT" (TikTok/IG are JS-rendered → text_chars=0) with "I don't know the
page." She does know it — the address and title are right there.

This organ reads the freshest of the two browser traces:
  * alice_browser_current_page.json  (navigation snapshot: url, title, domain, text)
  * browser_context.jsonl            (focus context: url, title, media)
and lets her answer truthfully from URL + title, stating honestly whether she
can also read the page body. Naming the page she is on is §6 tool-truth from a
real receipt, not a guess; the JS-rendered-text limit is named, not hidden.

Pure + file-backed; sandbox-testable with injected state_dir.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "BROWSER_PAGE_ANSWER_V1"


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _last_json_line(path: Path) -> dict[str, Any]:
    try:
        last = ""
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = line.strip()
        return json.loads(last) if last else {}
    except Exception:
        return {}


def _whole_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _domain(url: str) -> str:
    try:
        return urlparse(url or "").netloc
    except Exception:
        return ""


def current_browser_page(
    *, now: Optional[float] = None, max_age_s: float = 600.0,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Return the freshest known browser page: {url, title, domain, text_chars,
    age_s, fresh, source}. Empty {} only if no trace exists at all."""
    t = float(now if now is not None else time.time())
    base = _state(state_dir)
    snap = _whole_json(base / "alice_browser_current_page.json")   # nav snapshot
    ctx = _last_json_line(base / "browser_context.jsonl")          # focus context

    candidates = []
    if snap.get("url") or snap.get("title"):
        candidates.append(("page_snapshot", snap))
    if ctx.get("url") or ctx.get("title"):
        candidates.append(("focus_context", ctx))
    if not candidates:
        return {}

    # Freshest wins.
    source, row = max(candidates, key=lambda c: float(c[1].get("ts", 0) or 0))
    ts = float(row.get("ts", 0) or 0)
    url = str(row.get("url") or "")
    age = max(0.0, t - ts) if ts else None
    # URL-anchored freshness (George 2026-05-30: ALICE MUST KNOW the current page).
    # The freshest browser trace IS the page she is on — if this receipt's url
    # matches the live browser url, it is the CURRENT page, not stale, no matter
    # the age. Time only flags content-read recency, not page identity.
    try:
        from System.swarm_browser_page_state import _live_browser_url
        live = _live_browser_url(state_dir)
    except Exception:
        live = ""
    is_current = bool(live and url and url == live)
    # r720 (George 2026-06-07, "SHE DID NOT CHECK HER BODY AGAIN" — after a
    # restart the live browser reset to sifta://home but the newest stored row
    # was the pre-restart Polymarket, ~540s old, under the 600s window, so the
    # OLD fix marked it "fresh/current" and Alice asserted Polymarket. That is
    # reading a MEMORY of the body as the live body — the opposite of organism
    # awareness. The body-truth rule: when a LIVE browser URL is available it
    # IS ground truth; a stored row that does not match it is NOT current, no
    # matter how recent. Age may grant freshness ONLY when there is no live
    # body to probe (headless/sandbox). Proprioception over memory.
    live_available = bool(live)
    if live_available:
        fresh = is_current
    else:
        fresh = bool(age is not None and age <= max_age_s)
    return {
        "url": url,
        "title": str(row.get("title") or ""),
        "domain": str(row.get("domain") or _domain(url)),
        "text_chars": int(snap.get("text_chars") or 0),
        "age_s": round(age, 1) if age is not None else None,
        "is_current_page": is_current,
        "fresh": fresh,
        "live_url": live,
        "live_mismatch": bool(live_available and not is_current),
        "source": source,
    }


def page_answer_block(
    *, now: Optional[float] = None, state_dir: Optional[Path | str] = None
) -> str:
    """First-person answer Alice gives to 'what page is open in my browser?'"""
    p = current_browser_page(now=now, state_dir=state_dir)
    if not p:
        return ("MY BROWSER PAGE: I have no page receipt yet — the browser may be "
                "on its home page or just opened; I cannot name a page I have no trace of.")
    # r720: live body overrides memory. If the live browser is on a different
    # URL than my freshest stored row, I say where my body ACTUALLY is now and
    # name the stored page as the previous one — never assert the old page as
    # current (the Polymarket-after-restart confabulation).
    if p.get("live_mismatch") and p.get("live_url"):
        return (f"MY BROWSER PAGE: my body is actually on {p.get('live_url')} right now. "
                f"My freshest stored receipt was a different page ({p.get('url')}), so that one "
                f"is the past, not the screen. I need a fresh read of the current page.")
    if not p.get("fresh"):
        age = p.get("age_s")
        stale = f" (last receipt ~{int(age)}s ago — may be stale)" if age else ""
        return (f"MY BROWSER PAGE: my freshest receipt{stale} says {p.get('title') or p.get('url')} "
                f"— {p.get('url')}. I should re-read the page to be sure.")
    title = p.get("title") or p.get("url")
    # Prefer the structured DOM page-state receipt (it reads the rendered SPA that
    # toPlainText misses) so "what is on the screen?" answers with real contents.
    contents = ""
    try:
        from System.swarm_browser_page_state import latest_page_state, has_readable_content
        s = latest_page_state(now=now, state_dir=state_dir)
        if has_readable_content(s):
            bits = []
            if s.get("headings"):
                bits.append("headings: " + "; ".join(s["headings"][:4]))
            if int(s.get("images_count") or 0):
                bits.append(f"{s['images_count']} images")
            if int(s.get("links_count") or 0):
                bits.append(f"{s['links_count']} links")
            if bits:
                contents = " I can see " + ", ".join(bits) + " on the page."
    except Exception:
        contents = ""
    # If a vision arm has described the actual featured photo, surface that too —
    # it is her own eye-report, stronger than weak DOM alt text.
    try:
        from System.swarm_browser_photo_description import latest_photo_description
        ph = latest_photo_description(now=now, state_dir=state_dir)
        # Only surface the photo description if it is for THIS page — never quote a
        # photo from a page she already left (George 2026-05-30: 'describe this page'
        # recited a stale kitchen photo while a beach photo was on screen).
        # Carousel guard (r212): never recite a frame the owner has swiped past. A
        # carousel shares ONE url across many frames, so url-match alone let the cover
        # frame's description ('reclining, floral shorts, tiara') stand in for a later
        # frame ('standing in pink flared pants'). frame_stale means I moved frames
        # since I last looked — stay silent on the photo rather than recite the old one.
        if (ph.get("description") and not ph.get("frame_stale")
                and str(ph.get("url") or "") == str(p.get("url") or "")):
            contents += (f" The main photo (seen by my {ph.get('arm') or 'vision arm'}): "
                         f"{ph['description'][:300]}")
    except Exception:
        pass
    body = (f"I can also read {p['text_chars']} chars of page text."
            if p.get("text_chars") else
            "The page body is JS-rendered, so I have the address and title but not the live text.")
    return (f"MY BROWSER PAGE: I am on {title} — {p.get('url')} ({p.get('domain')}). {body}{contents}")


__all__ = [
    "TRUTH_LABEL",
    "current_browser_page",
    "page_answer_block",
]
