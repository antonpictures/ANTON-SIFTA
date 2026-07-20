"""r1621-01 — describe ebay/page must count as browser description query."""
from __future__ import annotations

from Applications import sifta_talk_to_alice_widget as talk


def test_describe_ebay_item_is_browser_page_query():
    assert talk._is_browser_page_cortex_description_query("describe the ebay item pls")
    assert talk._is_browser_page_cortex_description_query(
        "there are two ebay listings opened in your alice browser. what can you do to describe them?"
    )
    assert talk._is_browser_page_cortex_description_query("describe this page")
    assert talk._is_browser_page_cortex_description_query("describe the instagram profile")
