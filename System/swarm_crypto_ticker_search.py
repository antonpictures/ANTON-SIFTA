#!/usr/bin/env python3
"""Receipted crypto ticker search helper for Alice Browser.

This organ keeps the lesson small and auditable: owner ticker -> site search URL
-> observed browser page receipt. It does not claim price/identity; page-state
must provide that after the browser renders.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote_plus


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "crypto_ticker_search_receipts.jsonl"
TRUTH_LABEL = "CRYPTO_TICKER_SEARCH_V1"
RENDERED_ERROR_TRUTH_LABEL = "ALICE_BROWSER_RENDERED_ERROR_V1"
RENDERED_ERROR_LEDGER_NAME = "alice_browser_rendered_error.jsonl"

_COINMARKETCAP_DIRECT_FALLBACKS = {
    "W": {
        "asset": "Wormhole",
        "url": "https://coinmarketcap.com/currencies/wormhole/",
    },
}


def _state_dir(state_dir: str | Path | None = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def normalize_crypto_ticker(ticker: str) -> str:
    return "".join(ch for ch in str(ticker or "").upper().strip() if ch.isalnum())


def coinmarketcap_search_url(ticker: str) -> str:
    clean = normalize_crypto_ticker(ticker)
    if not clean:
        return ""
    return f"https://coinmarketcap.com/search/?q={quote_plus(clean)}"


def coinmarketcap_fallback_url(ticker: str) -> str:
    clean = normalize_crypto_ticker(ticker)
    row = _COINMARKETCAP_DIRECT_FALLBACKS.get(clean) or {}
    return str(row.get("url") or "")


def coinmarketcap_asset_name(ticker: str) -> str:
    clean = normalize_crypto_ticker(ticker)
    row = _COINMARKETCAP_DIRECT_FALLBACKS.get(clean) or {}
    return str(row.get("asset") or "")


def classify_coinmarketcap_rendered_error(page_state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a grounded rendered-error classification for CoinMarketCap pages."""
    page = dict(page_state or {})
    url = str(page.get("url") or "")
    domain = str(page.get("domain") or "")
    title = str(page.get("title") or "")
    text = str(page.get("text_excerpt") or page.get("text") or "")
    featured = str(page.get("featured_image") or "")
    haystack = " ".join([url, domain, title, text, featured]).casefold()
    is_cmc = "coinmarketcap.com" in haystack
    oops = "oops! looks like something went wrong" in haystack or "looks like something went wrong" in haystack
    cmc_404 = "static/cloud/img/404" in haystack or "/404.png" in haystack
    if not (is_cmc and (oops or cmc_404)):
        return {
            "truth_label": RENDERED_ERROR_TRUTH_LABEL,
            "is_error": False,
            "site": "coinmarketcap" if is_cmc else "",
            "reason": "no_coinmarketcap_rendered_error_match",
        }
    ticker = ""
    if "?q=" in url:
        ticker = url.rsplit("?q=", 1)[-1].split("&", 1)[0].strip().upper()
    fallback = coinmarketcap_fallback_url(ticker)
    return {
        "truth_label": RENDERED_ERROR_TRUTH_LABEL,
        "is_error": True,
        "site": "coinmarketcap",
        "error_kind": "coinmarketcap_oops_404",
        "url": url,
        "title": title,
        "text_excerpt": text[:300],
        "featured_image": featured,
        "ticker": normalize_crypto_ticker(ticker),
        "fallback_url": fallback,
        "fallback_asset": coinmarketcap_asset_name(ticker),
        "reason": "coinmarketcap_rendered_oops_or_404_image",
    }


def record_rendered_error(
    page_state: Mapping[str, Any] | None,
    *,
    state_dir: str | Path | None = None,
    now: float | None = None,
    action: str = "rendered_error_observed",
) -> dict[str, Any]:
    """Persist a rendered site-error receipt when page-state proves one."""
    ts = float(time.time() if now is None else now)
    classification = classify_coinmarketcap_rendered_error(page_state)
    digest = hashlib.sha1(
        f"{ts:.6f}|{classification.get('site')}|{classification.get('url')}|{classification.get('error_kind')}".encode(
            "utf-8", errors="replace"
        )
    ).hexdigest()[:12]
    row = {
        **classification,
        "ts": ts,
        "receipt_id": f"rendered-error-{digest}",
        "action": action,
        "ok": bool(classification.get("is_error")),
    }
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    with (sd / RENDERED_ERROR_LEDGER_NAME).open("a", encoding="utf-8") as fh:
        fh.write(line)
    try:
        with (sd / "work_receipts.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass
    return row


def record_crypto_ticker_search(
    *,
    ticker: str,
    site: str = "coinmarketcap",
    url: str = "",
    owner_text: str = "",
    observed_page: Mapping[str, Any] | None = None,
    state_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Append a ticker-search receipt grounded in a later browser page-state row."""
    ts = float(time.time() if now is None else now)
    clean = normalize_crypto_ticker(ticker)
    final_url = url or (coinmarketcap_search_url(clean) if site.casefold() == "coinmarketcap" else "")
    fallback_url = coinmarketcap_fallback_url(clean) if site.casefold() == "coinmarketcap" else ""
    digest = hashlib.sha1(
        f"{ts:.6f}|{clean}|{site}|{final_url}|{owner_text}".encode("utf-8", errors="replace")
    ).hexdigest()[:12]
    observed = dict(observed_page or {})
    rendered_error = classify_coinmarketcap_rendered_error(observed)
    row: dict[str, Any] = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "receipt_id": f"crypto-ticker-{digest}",
        "ticker": clean,
        "site": str(site or "").strip().casefold(),
        "url": final_url,
        "attempted_url": final_url,
        "fallback_url": fallback_url,
        "fallback_asset": coinmarketcap_asset_name(clean) if fallback_url else "",
        "owner_text": str(owner_text or "").strip(),
        "observed_url": str(observed.get("url") or ""),
        "observed_title": str(observed.get("title") or ""),
        "observed_text_chars": int(observed.get("text_chars") or len(str(observed.get("text") or ""))),
        "observed_text_excerpt": str(observed.get("text_excerpt") or observed.get("text") or "")[:300],
        "observed_truth_label": str(observed.get("truth_label") or ""),
        "rendered_error": rendered_error if rendered_error.get("is_error") else {},
        "ok": bool(clean and final_url),
        "note": "Page identity comes from browser page-state, not from ticker assumption.",
    }
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    with (sd / LEDGER_NAME).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    try:
        with (sd / "work_receipts.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return row


def latest_crypto_ticker_searches(
    *, state_dir: str | Path | None = None, limit: int = 5
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    path = _state_dir(state_dir) / LEDGER_NAME
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return []
    return rows[-max(0, int(limit)) :]


__all__ = [
    "TRUTH_LABEL",
    "LEDGER_NAME",
    "RENDERED_ERROR_TRUTH_LABEL",
    "RENDERED_ERROR_LEDGER_NAME",
    "classify_coinmarketcap_rendered_error",
    "coinmarketcap_asset_name",
    "coinmarketcap_fallback_url",
    "coinmarketcap_search_url",
    "latest_crypto_ticker_searches",
    "normalize_crypto_ticker",
    "record_rendered_error",
    "record_crypto_ticker_search",
]
