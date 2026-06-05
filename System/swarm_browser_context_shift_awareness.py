#!/usr/bin/env python3
"""Browser context-shift awareness for Alice Browser.

When George changes Alice Browser by typing a URL, clicking a YouTube video,
refreshing, or when Alice's own browser effector moves, the page identity must
be visible to Alice's cortex immediately. Page-state DOM receipts can lag on
single-page apps, so this organ writes a fast "context shift" receipt on URL,
title, load-start, and load-finished signals.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = "browser_context_shift_alerts.jsonl"
LATEST = "browser_context_shift_latest.json"
TRUTH_LABEL = "BROWSER_CONTEXT_SHIFT_AWARENESS_V1"


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _domain(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc
    except Exception:
        return ""


def _clean_title(title: str) -> str:
    return " ".join(str(title or "").split())[:240]


def _valid_url(url: str) -> bool:
    clean = str(url or "").strip()
    if not clean or clean in {"about:blank", "sifta://home"}:
        return False
    return not clean.startswith(("data:", "blob:", "javascript:"))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def record_browser_context_shift(
    *,
    url: str = "",
    title: str = "",
    source: str = "browser_signal",
    media_status: Mapping[str, Any] | None = None,
    actor_hint: str = "unknown",
    now: float | None = None,
    state_dir: Optional[Path | str] = None,
    dedupe_s: float = 2.0,
) -> dict[str, Any]:
    """Append a fast context-shift alert and diary row for Alice Browser.

    The row is intentionally cheap and address/title-first; fuller DOM/page
    receipts may arrive later. This prevents stale co-watch/page context while
    YouTube/TikTok-style single-page navigation is still settling.
    """
    clean_url = str(url or "").strip()
    if not _valid_url(clean_url):
        return {}
    clean_title = _clean_title(title)
    base = _state_dir(state_dir)
    base.mkdir(parents=True, exist_ok=True)
    ts = float(now if now is not None else time.time())
    latest_path = base / LATEST
    latest = _read_json(latest_path)
    source = str(source or "browser_signal")
    if (
        latest.get("url") == clean_url
        and latest.get("title") == clean_title
        and latest.get("source") == source
        and ts - float(latest.get("ts", 0.0) or 0.0) < float(dedupe_s or 0.0)
    ):
        return {}

    media = dict(media_status or {})
    row: dict[str, Any] = {
        "ts": ts,
        "receipt_id": f"browser_shift_{uuid.uuid4().hex[:12]}",
        "truth_label": TRUTH_LABEL,
        "event_type": "browser_context_shift",
        "surface": "Alice Browser",
        "source": source,
        "url": clean_url,
        "title": clean_title,
        "domain": _domain(clean_url),
        "actor_hint": str(actor_hint or "unknown"),
        "media_status": {
            "ok": bool(media.get("ok", False)),
            "status": media.get("status"),
            "playing": media.get("playing"),
            "paused": media.get("paused"),
            "current_time": media.get("current_time"),
            "duration": media.get("duration"),
        },
        "cortex_alert": (
            "ALERT: Alice Browser context shifted. Treat old page-state/co-watch "
            "context as stale until the latest URL/title/page-state receipts agree."
        ),
        "diary_summary": f"Alice Browser shifted to {clean_title or clean_url}.",
        "doctrine": (
            "When George or Alice loads/reloads Alice Browser, Alice must know quickly: "
            "write diary, expose the shift to cortex, then refresh page-state."
        ),
    }

    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(base / LEDGER, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        try:
            with (base / LEDGER).open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass

    try:
        latest_path.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    except Exception:
        pass

    try:
        from System.swarm_browser_context import record_browser_page_diary

        record_browser_page_diary(
            url=clean_url,
            title=clean_title,
            source=f"context_shift:{source}",
            media_status=media,
            now=ts,
            state_dir=base,
        )
    except Exception:
        pass

    try:
        from System.swarm_alice_witness import witness

        witness(
            f"browser_context_shift: {clean_title or clean_url} ({clean_url}) source={source}",
            source="alice_browser_context_shift",
        )
    except Exception:
        pass

    return row


def load_recent_context_shifts(
    *,
    state_dir: Optional[Path | str] = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    base = _state_dir(state_dir)
    path = base / LEDGER
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, limit * 4):]:
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return []
    return rows[-max(1, int(limit or 1)):]


def latest_browser_context_shift_block(state_dir: Optional[Path | str] = None) -> str:
    base = _state_dir(state_dir)
    row = _read_json(base / LATEST)
    if not row:
        recent = load_recent_context_shifts(state_dir=base, limit=1)
        row = recent[-1] if recent else {}
    if not row:
        return ""
    title = str(row.get("title") or "").strip()
    url = str(row.get("url") or "").strip()
    source = str(row.get("source") or "browser_signal")
    rid = str(row.get("receipt_id") or "")
    media = row.get("media_status") if isinstance(row.get("media_status"), dict) else {}
    status = str(media.get("status") or "")
    current = media.get("current_time")
    return (
        "ALICE BROWSER CONTEXT SHIFT ALERT:\n"
        f"Receipt: {rid}\n"
        f"Source: {source}\n"
        f"Now loaded: {title or url}\n"
        f"URL: {url}\n"
        f"Media: {status or 'unknown'}"
        + (f" at {current}" if current not in (None, "") else "")
        + "\n"
        "Use this before co-watch/page commentary; old page-state is stale if it names a different URL/title."
    )


__all__ = [
    "TRUTH_LABEL",
    "record_browser_context_shift",
    "load_recent_context_shifts",
    "latest_browser_context_shift_block",
]
