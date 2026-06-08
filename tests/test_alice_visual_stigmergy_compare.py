from System.alice_visual_stigmergy_compare import (
    OWNER_EYES_CONFIRMATION_TRUTH,
    build_owner_eyes_browser_confirmation,
    format_owner_eyes_confirmation_for_cortex,
)


def test_owner_eyes_confirmation_uses_existing_compare_boundary():
    owner = {
        "image_sha256": "owner-sha",
        "observed_text": ["eBay", "CERAMIC VASE", "$5.99"],
        "visual_entities": ["Alice Browser", "eBay search results"],
        "url_hint": "https://www.ebay.com/sch/i.html?_nkw=CERAMIC+VASE",
    }
    browser = {
        "app": "Alice Browser",
        "image_sha256": "browser-sha",
        "observed_text": ["eBay", "CERAMIC VASE", "Search"],
        "visual_entities": ["Alice Browser", "listing cards"],
        "url_hint": "https://www.ebay.com/sch/i.html?_nkw=CERAMIC+VASE",
        "created_at": 1780765500.0,
    }

    row = build_owner_eyes_browser_confirmation(
        owner,
        browser,
        owner_statement="my eyes are proof confirmation of her stigmergic browsing activities",
        screenshot_path="/Users/ioanganton/Desktop/Screenshot 2026-06-06 at 10.05.14 AM.jpg",
        created_at=1780765514.0,
    )

    assert row["truth_label"] == OWNER_EYES_CONFIRMATION_TRUTH
    assert row["confirmed"] is True
    assert row["browser_receipt_present"] is True
    assert row["confirmation_reasons"]["url_hint_match"] is True
    assert "does not replace Alice Browser frame/action receipts" in row["proof_scope"]
    assert "not_alice_prompt" in row["privacy_boundary"]
    assert row["comparison"]["shared_text"] == ["CERAMIC VASE", "eBay"]

    formatted = format_owner_eyes_confirmation_for_cortex(row)
    assert "OWNER EYES BROWSER CONFIRMATION" in formatted
    assert "confirmed: True" in formatted


def test_owner_eyes_confirmation_without_overlap_is_not_browser_proof():
    owner = {
        "observed_text": ["Owner desktop"],
        "visual_entities": ["Finder"],
        "url_hint": "file:///tmp/example",
    }
    browser = {
        "app": "Alice Browser",
        "observed_text": ["YouTube"],
        "visual_entities": ["video player"],
        "url_hint": "https://www.youtube.com/",
    }

    row = build_owner_eyes_browser_confirmation(owner, browser, created_at=1780765514.0)

    assert row["confirmed"] is False
    assert row["browser_receipt_present"] is True
    assert row["confirmation_reasons"]["shared_text_or_entities"] is False
    assert row["confirmation_reasons"]["url_hint_match"] is False
