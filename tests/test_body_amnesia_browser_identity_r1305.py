"""r1305: embodied browser identity earns claims from body receipts — cortex first."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Applications import sifta_talk_to_alice_widget as talk  # noqa: E402


def test_embodied_browser_identity_question_detected():
    assert talk._is_owner_embodied_browser_identity_question("what is your favorite browser?")
    assert talk._is_owner_embodied_browser_identity_question("Which browser do you use?")
    assert not talk._is_owner_embodied_browser_identity_question("open the photo in alice browser")


def test_doctrine_paste_does_not_trigger_image_browser_open():
    owner_text = (
        "Alice is literally sitting inside Alice Browser with RENAMED.jpg open. "
        "The real bug is body amnesia at answer time. "
        "add to deterministic detector app and all like it go to cortex first. "
        "arbitration ladder: live body receipt → recent ledger → owner doctrine → general model knowledge"
    )
    assert talk._must_route_owner_turn_to_cortex(owner_text)
    assert talk._block_deterministic_owner_shortcut(owner_text)
    assert not talk._is_owner_image_browser_open_query(owner_text)
    assert talk._synthesize_owner_image_browser_open_command(owner_text) is None


def test_favorite_browser_routes_cortex_first_with_evidence_block(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "browser_page_state.jsonl").write_text(
        json.dumps(
            {
                "ts": time.time(),
                "url": "file:///Users/ioanganton/Desktop/RENAMED.jpg",
                "title": "RENAMED.jpg",
                "open_tabs": [
                    {
                        "index": 0,
                        "active": True,
                        "title": "RENAMED.jpg",
                        "url": "file:///Users/ioanganton/Desktop/RENAMED.jpg",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(talk, "_state_root", lambda: tmp_path)
    monkeypatch.setattr(talk, "_find_live_alice_browser_widget", lambda: None)

    owner = "what is your favorite browser?"
    assert talk._owner_effector_requires_cortex_first(owner)
    block = talk._embodied_browser_identity_prompt_block(owner, state_dir=tmp_path)
    assert "EVIDENCE LADDER" in block
    assert "RENAMED.jpg" in block
    assert "OPEN TABS:" in block
    assert "Do NOT answer from generic model training" in block


def test_file_tab_counts_as_on_page_when_shell_reads_home():
    from Applications.sifta_alice_browser_widget import AliceBrowserWidget

    widget = AliceBrowserWidget.__new__(AliceBrowserWidget)
    widget._view = None
    widget._current_url = "sifta://home"

    class _FakeTabs:
        def count(self):
            return 1

        def currentIndex(self):
            return 0

        def tabText(self, _i):
            return "RENAMED.jpg"

        def widget(self, _i):
            return _FakeView()

    class _FakeView:
        def title(self):
            return "RENAMED.jpg"

        def url(self):
            class _U:
                def toString(self):
                    return "file:///Users/ioanganton/Desktop/RENAMED.jpg"

            return _U()

    widget._tabs = _FakeTabs()
    live = widget.current_live_page()
    assert live.get("on_page") is True
    assert "RENAMED.jpg" in str(live.get("url") or "")


def test_tracker_registers_body_amnesia_type():
    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    tdef = tracker.BYPASS_TYPES["body_amnesia_at_answer_time"]
    assert "BODY AMNESIA" in tdef["label"]
    assert "cortex" in tdef["reroute"].casefold()