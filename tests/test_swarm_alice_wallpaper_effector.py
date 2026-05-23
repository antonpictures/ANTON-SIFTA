import json
import struct
from pathlib import Path

import pytest

from System import swarm_alice_wallpaper_effector as w


def png_bytes(width=512, height=512):
    # Enough for the effector's header-level validation; tests do not need a
    # fully renderable PNG because Qt rendering is covered elsewhere.
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00"


def configure_tmp_paths(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    pics = tmp_path / "Library" / "Desktop Pictures"
    web = pics / "web_fetched"
    monkeypatch.setattr(w, "STATE_DIR", state)
    monkeypatch.setattr(w, "PICTURES_DIR", pics)
    monkeypatch.setattr(w, "WEB_FETCHED_DIR", web)
    monkeypatch.setattr(w, "CHAT_WALLPAPER_PATH", pics / "CHAT.jpg")
    monkeypatch.setattr(w, "WALLPAPER_LEDGER", state / "wallpaper_changes.jsonl")
    monkeypatch.setattr(w, "BLOCKLIST_PATH", tmp_path / "swarm_network_blocklist.txt")
    from System import sifta_desktop_themes as themes

    monkeypatch.setattr(themes, "_STATE", state)
    monkeypatch.setattr(themes, "_WALLPAPER_FILE", state / "desktop_wallpaper.json")
    return state, pics, web


def read_ledger():
    return [json.loads(line) for line in w.WALLPAPER_LEDGER.read_text(encoding="utf-8").splitlines()]


def test_parse_wallpaper_intent_defaults_to_both():
    intent = w.parse_wallpaper_intent("Alice change the wallpaper to a black hole")
    assert intent is not None
    assert intent.action == "set_wallpaper"
    assert intent.target == "both"
    assert intent.query == "a black hole"


def test_parse_chat_only_and_undo():
    intent = w.parse_wallpaper_intent("change only the chat background to honey circuit board")
    assert intent is not None
    assert intent.target == "chat"
    assert "honey circuit board" in intent.query
    undo = w.parse_wallpaper_intent("undo wallpaper")
    assert undo is not None
    assert undo.action == "undo_wallpaper"


def test_owner_gate_refuses_without_router_confirmation(tmp_path, monkeypatch):
    configure_tmp_paths(tmp_path, monkeypatch)
    result = w.set_wallpaper_from_query("black hole", candidates=[], owner_confirmed=False)
    assert result.ok is False
    assert result.status == "owner_gate_required"
    rows = read_ledger()
    assert rows[-1]["truth_label"] == w.TRUTH_LABEL
    assert rows[-1]["ok"] is False


def test_rejects_non_image_mime():
    candidate = w.WallpaperCandidate("https://example.com/not-image")

    def opener(req, timeout):
        return b"<html></html>", {"content-type": "text/html"}

    with pytest.raises(w.WallpaperEffectorError, match="mime_not_image"):
        w.download_image(candidate, opener=opener)


def test_rejects_tiny_image():
    candidate = w.WallpaperCandidate("https://example.com/tiny.png")

    def opener(req, timeout):
        return png_bytes(128, 128), {"content-type": "image/png"}

    with pytest.raises(w.WallpaperEffectorError, match="image_too_small"):
        w.download_image(candidate, opener=opener)


def test_applies_both_wallpapers_and_writes_receipt(tmp_path, monkeypatch):
    state, pics, _web = configure_tmp_paths(tmp_path, monkeypatch)
    pics.mkdir(parents=True)
    w.CHAT_WALLPAPER_PATH.write_bytes(png_bytes(512, 512) + b"old")
    candidate = w.WallpaperCandidate("https://images.example/honey.png")

    def downloader(_candidate):
        return png_bytes(512, 384) + b"new", "image/png"

    result = w.set_wallpaper_from_query(
        "honey circuit",
        candidates=[candidate],
        downloader=downloader,
        owner_confirmed=True,
    )
    assert result.ok is True
    assert result.status == "applied"
    assert Path(result.saved_path).exists()
    assert w.CHAT_WALLPAPER_PATH.read_bytes().endswith(b"new")
    desktop_state = json.loads((state / "desktop_wallpaper.json").read_text(encoding="utf-8"))
    assert desktop_state["path"] == str(Path(result.saved_path).resolve())
    row = read_ledger()[-1]
    assert row["kind"] == "WALLPAPER_CHANGE"
    assert row["stgm_cost"] == w.STGM_COST
    assert row["truth_boundary"].startswith("local wallpaper effector only")


def test_undo_restores_previous_chat_and_desktop(tmp_path, monkeypatch):
    state, pics, _web = configure_tmp_paths(tmp_path, monkeypatch)
    pics.mkdir(parents=True)
    previous_desktop = pics / "previous_desktop.png"
    previous_desktop.write_bytes(png_bytes(512, 512) + b"desktop")
    from System.sifta_desktop_themes import save_custom_wallpaper_path

    save_custom_wallpaper_path(str(previous_desktop))
    w.CHAT_WALLPAPER_PATH.write_bytes(png_bytes(512, 512) + b"oldchat")

    def downloader(_candidate):
        return png_bytes(512, 512) + b"newchat", "image/png"

    applied = w.set_wallpaper_from_query(
        "new field",
        candidates=[w.WallpaperCandidate("https://images.example/new.png")],
        downloader=downloader,
        owner_confirmed=True,
    )
    assert applied.ok
    assert w.CHAT_WALLPAPER_PATH.read_bytes().endswith(b"newchat")
    undone = w.undo_last_wallpaper_change(owner_confirmed=True)
    assert undone.ok
    assert w.CHAT_WALLPAPER_PATH.read_bytes().endswith(b"oldchat")
    desktop_state = json.loads((state / "desktop_wallpaper.json").read_text(encoding="utf-8"))
    assert desktop_state["path"] == str(previous_desktop)
    assert read_ledger()[-1]["kind"] == "WALLPAPER_UNDO"


def test_duckduckgo_json_path_parses_candidates():
    def opener(req, timeout):
        url = req.full_url
        if "i.js" in url:
            return json.dumps({"results": [{"image": "https://img.example/a.jpg", "title": "A"}]}).encode()
        return b"<script>var vqd='123-abc';</script>"

    candidates = w.search_duckduckgo_images("bee field", opener=opener)
    assert candidates == [w.WallpaperCandidate(url="https://img.example/a.jpg", source=w.SEARCH_ENGINE, title="A")]


def test_render_owner_reply_includes_receipt(tmp_path, monkeypatch):
    configure_tmp_paths(tmp_path, monkeypatch)
    result = w.WallpaperResult(
        ok=True,
        status="applied",
        receipt_id="abc123",
        target="both",
        query="black hole",
        saved_path="/tmp/web_1_deadbeef.jpg",
        content_sha256="deadbeef" * 8,
        bytes=2048,
    )
    reply = w.render_owner_reply(result)
    assert "Receipt abc123" in reply
    assert "sha8 deadbeef" in reply

