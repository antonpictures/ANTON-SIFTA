from __future__ import annotations

import json

from System import swarm_general_browse as gb


def test_general_browse_detects_untuned_page_requests():
    text = "Alice browse this arbitrary page https://example.com and give me a usable dress + actions"

    assert gb.is_general_browse_request(text)
    assert gb.extract_target_url(text) == "https://example.com"
    assert "return_usable_dress" in gb.infer_requested_actions(text)


def test_general_browse_receipt_has_diff_and_preflight(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    viewport = state / "viewport.png"
    viewport.write_bytes(b"not a real png but enough to hash")
    before = {
        "url": "https://example.com",
        "title": "Before",
        "text": "old",
        "elements": [{"label": "Old"}],
    }
    after = {
        "url": "https://example.com",
        "title": "After",
        "text": "new",
        "elements": [{"label": "New"}, {"label": "Continue"}],
        "viewport_image": str(viewport),
    }

    receipt = gb.build_general_browse_receipt(
        "browse this arbitrary page https://example.com and click Continue",
        before_state=before,
        after_state=after,
        state_dir=tmp_path,
    )

    assert receipt["truth_label"] == gb.TRUTH_LABEL
    assert receipt["target_url"] == "https://example.com"
    assert receipt["ready_for_cortex"] is True
    assert receipt["closed_loop"]["changed"] is True
    assert receipt["closed_loop"]["status"] == "before_after_diff"
    assert receipt["closed_loop"]["after"]["element_count"] == 2
    assert receipt["visual_evidence"]["status"] == "visual_evidence_recorded"
    assert receipt["visual_evidence"]["observed"] is True
    assert "pixelrag_vlm_evidence" in receipt["evidence_sources"]
    assert receipt["page_dress"]["ready_for_general_browse"] is True
    assert "general_page_dress" in receipt["evidence_sources"]
    assert "web_reflex_loop" in receipt["preflight"]

    ledger = tmp_path / ".sifta_state" / gb.LEDGER_NAME
    assert ledger.exists()
    stored = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert stored["receipt_id"] == receipt["receipt_id"]


def test_page_dress_maps_any_site_affordances(tmp_path):
    state = {
        "url": "https://example.com/shop",
        "title": "Shop",
        "domain": "example.com",
        "text": "Find tools and checkout.",
        "headings": ["Shop tools"],
        "visible_controls": [
            {"label": "Search", "role": "textbox", "uid": "@e1", "placeholder": "Search products"},
            {"label": "Add to cart", "role": "button", "uid": "@e2"},
            {"label": "Checkout", "role": "link", "href": "/checkout", "uid": "@e3"},
        ],
    }

    dress = gb.record_page_dress(
        "browse this arbitrary page and search tools then click checkout",
        page_state=state,
        state_dir=tmp_path,
        now=123.0,
    )

    assert dress["truth_label"] == "GENERAL_BROWSE_PAGE_DRESS_V1"
    assert dress["ready_for_general_browse"] is True
    assert dress["affordances"]["search_fields"][0]["uid"] == "@e1"
    assert dress["affordances"]["click_targets"][1]["label"] == "Add to cart"
    assert dress["affordances"]["navigation_links"][0]["label"] == "Checkout"
    assert dress["next_action_hint"] == "use_uid_or_selector_targets"
    assert (tmp_path / ".sifta_state" / gb.DRESS_LEDGER_NAME).exists()


def test_pixelrag_vlm_evidence_is_honest_without_image(tmp_path):
    evidence = gb.build_pixelrag_vlm_evidence(
        after_state={"url": "https://example.com", "text": "text only"},
        target_url="https://example.com",
        state_dir=tmp_path,
    )

    assert evidence["schema"] == "GENERAL_BROWSE_PIXELRAG_VLM_EVIDENCE_V1"
    assert evidence["status"] == "no_viewport_image"
    assert evidence["observed"] is False


def test_general_browse_receipt_is_honest_without_after_state(tmp_path):
    receipt = gb.build_general_browse_receipt(
        "general_browse https://example.com",
        before_state={"url": "https://example.com", "text": "before"},
        state_dir=tmp_path,
    )

    assert receipt["ready_for_cortex"] is True
    assert receipt["closed_loop"]["status"] == "needs_after_state"
    assert receipt["preflight"]["whisper_modules"].keys() == {"openai_whisper", "faster_whisper"}


def test_dependency_preflight_scar_persists_missing_or_present_state(tmp_path):
    scar = gb.record_dependency_preflight_scar(state_dir=tmp_path, now=123.0)

    assert scar["schema"] == "GENERAL_BROWSE_DEPENDENCY_SCAR_V1"
    assert scar["status"] in {"scar_recorded", "dependencies_present"}
    assert "whisper" in scar["preflight"]
    path = tmp_path / ".sifta_state" / gb.DEPENDENCY_SCAR_LEDGER
    assert path.exists()
    assert "GENERAL_BROWSE_DEPENDENCY_SCAR_V1" in path.read_text(encoding="utf-8")
