"""Desktop photo -> Alice Browser routing (r1268)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Applications.sifta_talk_to_alice_widget import (  # noqa: E402
    _extract_sifta_app_command,
    _hallucination_bridge_synthesize_photo_select_action,
    _is_desktop_photo_alice_browser_open_query,
    _is_owner_image_browser_open_query,
    _synthesize_desktop_photo_browser_open_command,
    _synthesize_owner_image_browser_open_command,
)


def test_desktop_photo_open_detected():
    text = "pls open the photo we have on the desktop in alice browser"
    assert _is_desktop_photo_alice_browser_open_query(text)


def test_desktop_photo_open_detects_owner_typos():
    assert _is_desktop_photo_alice_browser_open_query(
        "try again, open the screenshot on thedesktop is a photo"
    )
    assert _is_desktop_photo_alice_browser_open_query(
        "this attached image is on rhe desktop, open it in alice browser"
    )


def test_desktop_photo_not_routed_to_google_image_click():
    text = "pls open the photo we have on the desktop in alice browser"
    assert _hallucination_bridge_synthesize_photo_select_action(text, "I see a photo.") is None


def test_attached_image_browser_open_is_not_external_image_action(tmp_path):
    photo = tmp_path / "attached.png"
    photo.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 40)
    text = "this attached image is on rhe desktop, open it in alice browser"

    assert _is_owner_image_browser_open_query(text)
    assert _extract_sifta_app_command(text) == {}

    cmd = _synthesize_owner_image_browser_open_command(text, attachment_path=str(photo))
    assert cmd is not None
    assert cmd["kind"] == "browser_url"
    assert cmd["url"].startswith("file://")
    assert cmd["local_image_path"] == str(photo.resolve())
    assert cmd["contextual_search_source"] == "attached_file_browser_open"


def test_desktop_photo_command_uses_file_url(tmp_path, monkeypatch):
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    photo = desktop / "shot.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xd8" + b"x" * 40)
    monkeypatch.setattr(
        "Applications.sifta_talk_to_alice_widget.Path.home",
        lambda: tmp_path,
    )
    cmd = _synthesize_desktop_photo_browser_open_command(
        "open the desktop photo in alice browser"
    )
    assert cmd is not None
    assert cmd["kind"] == "browser_url"
    assert cmd["url"].startswith("file://")
    assert "shot.jpg" in cmd["url"]
