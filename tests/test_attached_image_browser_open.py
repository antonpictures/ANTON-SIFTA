"""Attached + Desktop image -> Alice Browser file:// routing (r1277)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Applications.sifta_talk_to_alice_widget import (  # noqa: E402
    _extract_sifta_app_command,
    _hallucination_bridge_synthesize_photo_select_action,
    _is_owner_image_browser_open_query,
    _last_turn_attachment_path_from_history,
    _resolve_owner_image_path_for_browser_open,
    _synthesize_owner_image_browser_open_command,
)


def test_attached_image_open_detected():
    assert _is_owner_image_browser_open_query("pls open the image in alice browser")
    assert _is_owner_image_browser_open_query("good job!! now open this one i attached")
    assert _is_owner_image_browser_open_query("open the photo in alice browser pls")


def test_attached_path_wins_over_desktop_mtime(tmp_path, monkeypatch):
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    older = desktop / "old_screenshot.png"
    older.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 40)
    attach = tmp_path / "32958048_008_00bd.jpg"
    attach.write_bytes(b"\xff\xd8\xff\xd8" + b"y" * 40)
    monkeypatch.setattr(
        "Applications.sifta_talk_to_alice_widget.Path.home",
        lambda: tmp_path,
    )
    resolved = _resolve_owner_image_path_for_browser_open(
        "open the image in alice browser",
        attachment_path=str(attach),
    )
    assert resolved == str(attach.resolve())
    assert "old_screenshot" not in (resolved or "")


def test_desktop_mtime_when_no_attachment(tmp_path, monkeypatch):
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    photo = desktop / "George_renames_this_every_time.webp"
    photo.write_bytes(b"RIFF" + b"z" * 40)
    monkeypatch.setattr(
        "Applications.sifta_talk_to_alice_widget.Path.home",
        lambda: tmp_path,
    )
    cmd = _synthesize_owner_image_browser_open_command(
        "open the screenshot on the desktop in alice browser"
    )
    assert cmd is not None
    assert cmd["kind"] == "browser_url"
    assert "George_renames_this_every_time.webp" in cmd["url"]


def test_attached_open_not_routed_to_google_image_click():
    text = "open the image in alice browser"
    assert _hallucination_bridge_synthesize_photo_select_action(text, "I see blue lingerie.") is None


def test_last_turn_attachment_path_from_history(tmp_path):
    attach = tmp_path / "owner_drop.jpg"
    attach.write_bytes(b"\xff\xd8\xff\xd8" + b"a" * 20)
    history = [
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "open it", "image_path": str(attach)},
    ]
    assert _last_turn_attachment_path_from_history(history) == str(attach.resolve())


def test_open_this_photo_matches_general_intent():
    assert _is_owner_image_browser_open_query("OPEN THIS PHOTO IN ALICE BROWSER")


def test_pdf_attachment_opens_in_browser(tmp_path):
    doc = tmp_path / "owner_contract.pdf"
    doc.write_bytes(b"%PDF-1.4" + b"z" * 40)
    cmd = _synthesize_owner_image_browser_open_command(
        "open this document in alice browser",
        attachment_path=str(doc),
    )
    assert cmd is not None
    assert "owner_contract.pdf" in cmd["url"]
    assert cmd["contextual_search_source"] == "attached_file_browser_open"


def test_george_sifta_photo_browser_open_not_open_app(tmp_path, monkeypatch):
    text = "WHERE ARE WE AT? OPEN THE PHOTO IN THE BROWSER YOUR SIFTA PLS"
    assert _is_owner_image_browser_open_query(text)
    assert _extract_sifta_app_command(text) == {}
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    photo = desktop / "32958048_008_00bd.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xd8" + b"g" * 40)
    monkeypatch.setattr(
        "Applications.sifta_talk_to_alice_widget.Path.home",
        lambda: tmp_path,
    )
    cmd = _synthesize_owner_image_browser_open_command(text, attachment_path=str(photo))
    assert cmd is not None
    assert cmd["kind"] == "browser_url"
    assert "32958048_008_00bd.jpg" in cmd["url"]
    assert cmd["contextual_search_source"] == "attached_file_browser_open"


def test_stale_staged_path_falls_back_to_newest_desktop_file(tmp_path, monkeypatch):
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    renamed = desktop / "HA I CHANGED THE NAME AGAIN TO CATCH YOU HARDCODING.jpg"
    renamed.write_bytes(b"\xff\xd8\xff\xd8" + b"h" * 40)
    stale = tmp_path / "32958048_008_00bd.jpg"
    monkeypatch.setattr(
        "Applications.sifta_talk_to_alice_widget.Path.home",
        lambda: tmp_path,
    )
    resolved = _resolve_owner_image_path_for_browser_open(
        "OPEN THE PHOTO IN THE BROWSER YOUR SIFTA PLS",
        attachment_path=str(stale),
    )
    assert resolved == str(renamed.resolve())


def test_history_attachment_wins_when_current_turn_has_no_path(tmp_path):
    attach = tmp_path / "staged_next.jpg"
    attach.write_bytes(b"\xff\xd8\xff\xd8" + b"b" * 40)
    history = [
        {"role": "user", "content": "[image staged]", "image_path": str(attach)},
        {"role": "assistant", "content": "staged for your next words."},
    ]
    resolved = _resolve_owner_image_path_for_browser_open(
        "OPEN THIS PHOTO IN ALICE BROWSER",
        history=history,
    )
    assert resolved == str(attach.resolve())