#!/usr/bin/env python3
"""Google News intent organ.

This builds navigation intents for Alice Browser. It does not claim to fetch
news or summarize articles; it receipts the URL Alice should open.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - direct script fallback
    append_line_locked = None  # type: ignore[assignment]


ENGINE_KEY = "google_news"
TRUTH_LABEL = "GOOGLE_NEWS_SEARCH_V1"
HOME_URL = "https://news.google.com/home?hl=en-US&gl=US&ceid=US:en"
RSS_HOME = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
LEDGER_NAME = "google_news_intents.jsonl"

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
_GOOGLE_NEWS_RE = re.compile(r"\bgoogle\s+news\b", re.IGNORECASE)


def _state_dir(state_dir: Path | str | None = None) -> Path:
    if state_dir is None:
        return _STATE
    return Path(state_dir)


def _stable_id(row: Mapping[str, Any]) -> str:
    raw = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "gnews_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line)
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def topic_url(topic: str) -> str:
    q = " ".join(str(topic or "").split())
    if not q:
        return HOME_URL
    return (
        "https://news.google.com/search?q="
        + urllib.parse.quote_plus(q)
        + "&hl=en-US&gl=US&ceid=US:en"
    )


def rss_url(topic: str = "") -> str:
    q = " ".join(str(topic or "").split())
    if not q:
        return RSS_HOME
    return (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote_plus(q)
        + "&hl=en-US&gl=US&ceid=US:en"
    )


def _clean_topic(topic: str) -> str:
    text = re.sub(r"\bplease\b", "", topic or "", flags=re.IGNORECASE)
    text = re.sub(r"\b(open|show|search|for|about|on|google|news)\b", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip(" .,:;")


def parse_intent(text: str) -> dict[str, Any]:
    raw = " ".join(str(text or "").split())
    if not raw or not _GOOGLE_NEWS_RE.search(raw):
        return {"is_news": False, "kind": "", "topic": "", "url": "", "engine": ENGINE_KEY}

    topic = ""
    patterns = [
        r"\bgoogle\s+news\s+(?:for|about)\s+(?P<topic>.+)$",
        r"\bopen\s+google\s+news\s+(?:for|about)\s+(?P<topic>.+)$",
        r"\bsearch\s+(?P<topic>.+?)\s+on\s+google\s+news\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if match:
            topic = _clean_topic(match.group("topic"))
            break
    kind = "topic" if topic else "home"
    return {
        "is_news": True,
        "kind": kind,
        "topic": topic,
        "url": topic_url(topic) if topic else HOME_URL,
        "rss_url": rss_url(topic),
        "engine": ENGINE_KEY,
    }


def land_intent_receipt(
    text: str,
    parsed: Mapping[str, Any],
    *,
    state_dir: Path | str | None = None,
    source: str = "swarm_google_news_search",
) -> dict[str, Any]:
    state = _state_dir(state_dir)
    row = {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "kind": "GOOGLE_NEWS_INTENT",
        "ok": bool(parsed.get("is_news")),
        "intent_kind": parsed.get("kind") or "",
        "topic": parsed.get("topic") or "",
        "url": parsed.get("url") or "",
        "rss_url": parsed.get("rss_url") or "",
        "engine": ENGINE_KEY,
        "app": "Alice Browser",
        "source": source,
        "owner_text_preview": str(text or "")[:240],
        "boundary": "Navigation intent only; no claim that articles were fetched or read.",
    }
    row["receipt_id"] = _stable_id(row)
    _append_jsonl(state / LEDGER_NAME, row)
    return row


def navigation_intent(
    text: str,
    *,
    state_dir: Path | str | None = None,
    source: str = "owner",
    write_receipt: bool = True,
) -> dict[str, Any] | None:
    parsed = parse_intent(text)
    if not parsed.get("is_news"):
        return None
    receipt = (
        land_intent_receipt(text, parsed, state_dir=state_dir, source=source)
        if write_receipt else {}
    )
    return {
        "app": "Alice Browser",
        "engine": ENGINE_KEY,
        "kind": parsed.get("kind"),
        "topic": parsed.get("topic") or "",
        "url": parsed.get("url") or HOME_URL,
        "rss_url": parsed.get("rss_url") or RSS_HOME,
        "receipt_id": receipt.get("receipt_id") if isinstance(receipt, dict) else None,
        "truth_label": TRUTH_LABEL,
    }


__all__ = [
    "ENGINE_KEY",
    "HOME_URL",
    "RSS_HOME",
    "TRUTH_LABEL",
    "land_intent_receipt",
    "navigation_intent",
    "parse_intent",
    "rss_url",
    "topic_url",
]
