"""Alice Browser multi-tab awareness + restore (r1290)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Applications import sifta_talk_to_alice_widget as talk  # noqa: E402


GEORGE_BOTH_TABS = (
    "GREAT JOB, BUT YOU CLOSED MY OTHER TAB WITH THE PHOTO ON THE DESKTOP, "
    "I WANT THAT OPENED AS WELL IN ALICE BROWSER. BOTH TABS. KYLIN AND THE PHOTO. "
    "CAN YOU HANDLE MULTIPLE TABS IN IN YOUR OWN BROWSER?"
)


def test_multi_tab_request_detected():
    assert talk._is_owner_multi_tab_browser_request(GEORGE_BOTH_TABS)


def test_same_tabs_after_restart_detected_without_browser_word():
    assert talk._is_owner_multi_tab_browser_request("I HAVE TO RESTART. PLS OPEN SAME TABS")


def test_same_tabs_command_restores_last_multi_tab_page_state(tmp_path, monkeypatch):
    monkeypatch.setattr(talk, "_state_root", lambda: tmp_path)
    rows = [
        {
            "ts": time.time() - 120,
            "url": "https://www.instagram.com/kylinmilan/",
            "title": "Instagram",
            "open_tabs": [
                {
                    "index": 0,
                    "active": False,
                    "title": "RENAMED.jpg",
                    "url": "file:///Users/ioanganton/Desktop/RENAMED.jpg",
                },
                {
                    "index": 1,
                    "active": True,
                    "title": "(3) Instagram",
                    "url": "https://www.instagram.com/kylinmilan/",
                },
            ],
            "open_tabs_count": 2,
        },
        {
            "ts": time.time() - 10,
            "url": "sifta://home",
            "title": "Alice · SIFTA Browser",
            "open_tabs": [
                {"index": 0, "active": True, "title": "Alice · SIFTA Browser", "url": "sifta://home"},
            ],
            "open_tabs_count": 1,
        },
    ]
    (tmp_path / "browser_page_state.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    cmd = talk._synthesize_owner_multi_tab_browser_command("I HAVE TO RESTART. PLS OPEN SAME TABS")

    assert cmd is not None
    assert cmd["kind"] == "browser_multi_tab"
    urls = [str(t["url"]) for t in cmd["targets"]]
    assert "file:///Users/ioanganton/Desktop/RENAMED.jpg" in urls
    assert "https://www.instagram.com/kylinmilan/" in urls
    assert cmd["contextual_search_source"] == "browser_page_state_same_tabs_restore"


def test_multi_tab_command_has_instagram_and_photo(tmp_path, monkeypatch):
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    photo = desktop / "owner_photo.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xd8" + b"z" * 40)
    monkeypatch.setattr(talk.Path, "home", lambda: tmp_path)
    history = [
        {
            "role": "user",
            "content": "OPEN INSTAGRAM.COM @KYLINMILAN IN A NEW ALICE BROWSER TAB",
        },
    ]
    cmd = talk._synthesize_owner_multi_tab_browser_command(GEORGE_BOTH_TABS, history=history)
    assert cmd is not None
    assert cmd["kind"] == "browser_multi_tab"
    targets = cmd["targets"]
    assert len(targets) == 2
    urls = [str(t["url"]) for t in targets]
    assert any("instagram.com" in u for u in urls)
    assert any(u.startswith("file://") and "owner_photo.jpg" in u for u in urls)


def test_local_file_open_uses_new_tab_when_tabs_exist(monkeypatch):
    monkeypatch.setattr(
        talk,
        "_browser_open_tabs_from_page_state",
        lambda **kwargs: [{"index": 0, "active": True, "url": "https://www.instagram.com/kylinmilan/"}],
    )
    cmd = talk._apply_browser_tab_preservation(
        {
            "kind": "browser_url",
            "app_name": "Alice Browser",
            "url": "file:///Users/ioanganton/Desktop/photo.jpg",
        },
        "open the photo in alice browser",
    )
    assert cmd.get("new_tab") == "1"


def test_instagram_new_tab_request_sets_flag():
    text = "OPEN INSTAGRAM.COM @KYLINMILAN IN A NEW ALICE BROWSER TAB"
    assert talk._wants_alice_browser_new_tab(text)
    cmd = talk._extract_sifta_app_command(text)
    cmd = talk._maybe_native_browser_command(cmd, text)
    assert cmd.get("new_tab") == "1"


def test_interested_earlier_website_routes_to_browser_preference():
    cmd = talk._extract_sifta_app_command("SO OPEN THE WEBSITE I WAS INTERESTED IN EARLIER")
    assert cmd["kind"] == "browser_preferred_link"
    assert cmd["app_name"] == "Alice Browser"


def test_browser_tabs_awareness_block_lists_tabs(tmp_path):
    from System.swarm_browser_page_state import browser_tabs_awareness_block, record_page_state

    record_page_state(
        "https://www.instagram.com/kylinmilan/",
        "Instagram",
        open_tabs=[
            {"index": 0, "active": True, "title": "Instagram", "url": "https://www.instagram.com/kylinmilan/"},
            {
                "index": 1,
                "active": False,
                "title": "photo.jpg",
                "url": "file:///Users/ioanganton/Desktop/photo.jpg",
            },
        ],
        state_dir=tmp_path,
    )
    block = browser_tabs_awareness_block(state_dir=tmp_path)
    assert "ALICE BROWSER TABS" in block
    assert "2 open" in block
    assert "photo.jpg" in block
