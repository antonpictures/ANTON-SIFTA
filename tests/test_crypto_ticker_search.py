from __future__ import annotations

import json

from Applications import sifta_talk_to_alice_widget as talk
from System.swarm_crypto_ticker_search import (
    classify_coinmarketcap_rendered_error,
    coinmarketcap_fallback_url,
    coinmarketcap_search_url,
    latest_crypto_ticker_searches,
    normalize_crypto_ticker,
    record_rendered_error,
    record_crypto_ticker_search,
)


def test_coinmarketcap_ticker_url_is_site_search() -> None:
    assert normalize_crypto_ticker(" w ") == "W"
    assert coinmarketcap_search_url("W") == "https://coinmarketcap.com/search/?q=W"
    assert coinmarketcap_fallback_url("W") == "https://coinmarketcap.com/currencies/wormhole/"
    assert talk._search_url_for_site("coinmarketcap.com", "W") == "https://coinmarketcap.com/search/?q=W"


def test_browser_parser_routes_coinmarketcap_ticker_search() -> None:
    cmd = talk._extract_browser_search_command("Please search for the crypto ticker W on coinmarketcap.com")
    assert cmd["kind"] == "browser_url"
    assert cmd["app_name"] == "Alice Browser"
    assert cmd["search_site"] == "coinmarketcap.com"
    assert cmd["query"] == "W"
    assert cmd["crypto_ticker"] == "W"
    assert cmd["url"] == "https://coinmarketcap.com/search/?q=W"


def test_crypto_ticker_receipt_records_observed_page(tmp_path) -> None:
    row = record_crypto_ticker_search(
        ticker="W",
        owner_text="search W on coinmarketcap",
        observed_page={
            "truth_label": "ALICE_BROWSER_PAGE_TEXT_V1",
            "url": "https://coinmarketcap.com/search/?q=W",
            "title": "Search results for W",
            "text_chars": 123,
        },
        state_dir=tmp_path,
        now=123.0,
    )
    assert row["ticker"] == "W"
    assert row["site"] == "coinmarketcap"
    assert row["observed_title"] == "Search results for W"
    rows = latest_crypto_ticker_searches(state_dir=tmp_path, limit=1)
    assert rows[-1]["receipt_id"] == row["receipt_id"]
    work = (tmp_path / ".sifta_state" / "work_receipts.jsonl").read_text(encoding="utf-8")
    assert json.loads(work.splitlines()[-1])["truth_label"] == "CRYPTO_TICKER_SEARCH_V1"


def test_coinmarketcap_rendered_error_classifies_and_records_fallback(tmp_path) -> None:
    page = {
        "truth_label": "BROWSER_PAGE_STATE_V1",
        "url": "https://coinmarketcap.com/search/?q=W",
        "title": "coinmarketcap.com/search/?q=W",
        "domain": "coinmarketcap.com",
        "text_excerpt": "Oops! Looks like something went wrong. Please try again later. Download App Back to Homepage",
        "featured_image": "https://s2.coinmarketcap.com/static/cloud/img/404.png?_=abc",
        "text_chars": 93,
    }

    classified = classify_coinmarketcap_rendered_error(page)
    assert classified["is_error"] is True
    assert classified["error_kind"] == "coinmarketcap_oops_404"
    assert classified["ticker"] == "W"
    assert classified["fallback_url"] == "https://coinmarketcap.com/currencies/wormhole/"
    assert classified["fallback_asset"] == "Wormhole"

    err = record_rendered_error(page, state_dir=tmp_path, now=456.0)
    assert err["truth_label"] == "ALICE_BROWSER_RENDERED_ERROR_V1"
    assert err["ok"] is True
    ledger = tmp_path / ".sifta_state" / "alice_browser_rendered_error.jsonl"
    assert json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])["fallback_asset"] == "Wormhole"


def test_crypto_ticker_receipt_embeds_rendered_error_and_fallback(tmp_path) -> None:
    row = record_crypto_ticker_search(
        ticker="W",
        owner_text="search W on coinmarketcap",
        observed_page={
            "truth_label": "BROWSER_PAGE_STATE_V1",
            "url": "https://coinmarketcap.com/search/?q=W",
            "title": "coinmarketcap.com/search/?q=W",
            "text_excerpt": "Oops! Looks like something went wrong. Please try again later.",
            "featured_image": "https://s2.coinmarketcap.com/static/cloud/img/404.png",
        },
        state_dir=tmp_path,
        now=789.0,
    )

    assert row["attempted_url"] == "https://coinmarketcap.com/search/?q=W"
    assert row["fallback_url"] == "https://coinmarketcap.com/currencies/wormhole/"
    assert row["rendered_error"]["error_kind"] == "coinmarketcap_oops_404"
