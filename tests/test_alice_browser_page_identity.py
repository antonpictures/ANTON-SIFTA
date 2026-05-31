import json

import Applications.sifta_alice_browser_widget as browser


def _patch_state(monkeypatch, tmp_path):
    monkeypatch.setattr(browser, "_STATE", tmp_path)
    monkeypatch.setattr(browser, "_CURRENT_PAGE_SNAPSHOT", tmp_path / "alice_browser_current_page.json")


def test_address_snapshot_names_page_when_body_text_is_live_rendered(monkeypatch, tmp_path):
    _patch_state(monkeypatch, tmp_path)

    browser._write_current_page_address_snapshot(
        url="https://www.tiktok.com/@barbellinaa",
        title="barbellinaa | TikTok",
        source="url_changed",
        media_status={"ok": True},
    )

    data = json.loads((tmp_path / "alice_browser_current_page.json").read_text(encoding="utf-8"))
    assert data["url"] == "https://www.tiktok.com/@barbellinaa"
    assert data["title"] == "barbellinaa | TikTok"
    assert data["text"] == ""
    assert data["text_chars"] == 0
    assert data["extra"]["address_snapshot"]["address_only"] is True
    assert data["extra"]["address_snapshot"]["source"] == "url_changed"


def test_address_snapshot_preserves_existing_text_for_same_url(monkeypatch, tmp_path):
    _patch_state(monkeypatch, tmp_path)
    browser._write_current_page_snapshot(
        url="https://www.tiktok.com/@barbellinaa",
        title="TikTok - Make Your Day",
        text="Body check profile grid visible.",
        extra={"source": "load_finished_text"},
    )

    browser._write_current_page_address_snapshot(
        url="https://www.tiktok.com/@barbellinaa",
        title="barbellinaa | TikTok",
        source="title_changed",
    )

    data = json.loads((tmp_path / "alice_browser_current_page.json").read_text(encoding="utf-8"))
    assert data["title"] == "barbellinaa | TikTok"
    assert data["text"] == "Body check profile grid visible."
    assert data["text_chars"] == len("Body check profile grid visible.")
    assert data["extra"]["address_snapshot"]["address_only"] is False
    assert data["extra"]["source"] == "load_finished_text"
