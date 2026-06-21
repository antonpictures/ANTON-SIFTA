#!/usr/bin/env python3
"""Regression test for Alice's open/close/aware app effector (George 2026-05-30).

She "forgot how to open and close apps": the effector was gated behind the
default-off pre-cortex chat-reflex flag, "close the app <name>" routed to
*all* (wiping every window), and plain awareness queries didn't match. This
test pins George's exact command contract so it can fail if the wiring breaks.

Runs in the sandbox too: if PyQt6 is absent we install a minimal stub so the
pure parser functions import. On the M5 (real PyQt6) the stub is skipped.
"""
import json
import sys
import types
from unittest.mock import MagicMock

import pytest

try:  # real PyQt6 on the M5 — use it
    import PyQt6.QtCore  # noqa: F401
except Exception:  # sandbox / CI — stub just enough for the module to import
    def _make_pkg(name):
        m = types.ModuleType(name)
        m.__getattr__ = lambda a, _n=name: (type(a, (), {}) if a[:1].isupper() else MagicMock())
        return m
    for _p in (
        "PyQt6", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets",
        "PyQt6.QtMultimedia", "PyQt6.QtMultimediaWidgets",
        "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineCore",
        "PyQt6.QtNetwork", "PyQt6.sip",
    ):
        sys.modules[_p] = _make_pkg(_p)
    sys.modules["PyQt6.QtCore"].pyqtSignal = lambda *a, **k: MagicMock()
    sys.modules["PyQt6.QtCore"].pyqtSlot = lambda *a, **k: (lambda f: f)
    sys.modules["PyQt6.QtCore"].Qt = MagicMock()

from Applications import sifta_talk_to_alice_widget as tw  # noqa: E402


def _use_tmp_state(monkeypatch, tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tw, "_STATE_DIR", state_dir, raising=False)
    return state_dir


def _kind_name(text):
    out = tw._extract_sifta_app_command(text)
    return (out.get("kind"), out.get("app_name")) if out else None


def test_open_named_app():
    assert _kind_name("open the app alice browser") == ("app", "Alice Browser")
    assert _kind_name("open Alice Browser") == ("app", "Alice Browser")


def test_open_named_app_with_stt_punctuation_after_verb():
    assert _kind_name("Alice please open, Bonsai app.") == ("app", "Bonsai Image Studio (AI Vision)")


def test_close_named_app_does_not_close_all():
    # The core bug: a named close must target THAT app, never *all*.
    assert _kind_name("close the app alice browser") == ("close_app", "Alice Browser")
    assert _kind_name("close the app alicebrowser") == ("close_app", "Alice Browser")
    assert _kind_name("close alice browser") == ("close_app", "Alice Browser")


def test_close_all_still_works():
    assert _kind_name("close all apps") == ("close_app", "*all*")
    assert _kind_name("close everything") == ("close_app", "*all*")


def test_close_active_when_no_name():
    assert _kind_name("close that app") == ("close_app", "")


def test_awareness_status_query():
    assert _kind_name("what apps are open") == ("app_status", "")
    assert _kind_name("which apps are running") == ("app_status", "")
    assert _kind_name("what's open right now") == ("app_status", "")
    assert _kind_name("right now i have the bonsai app open look") == ("app_status", "")
    assert _kind_name("At least I will be able to tell me what app I have opened right now.") == ("app_status", "")


def test_app_status_sentence_separates_app_slot_from_browser_page():
    reply = tw._app_status_sentence(
        {
            "desktop_mode": "launcher",
            "active_app": "Bonsai Image Studio (AI Vision)",
            "open_apps": ["Bonsai Image Studio (AI Vision)"],
        }
    )

    assert "Bonsai Image Studio (AI Vision) is the active SIFTA app" in reply
    assert "not a web page" in reply
    assert "Browser page-state receipts are separate" in reply


def test_conversation_and_negation_do_not_misfire():
    assert tw._extract_sifta_app_command("I love the browser videos") in ({}, None)
    assert tw._extract_sifta_app_command("I don't want to open any app") in ({}, None)


def test_effector_is_not_gated_behind_chat_reflex_flag():
    # The effector call site must run _extract_sifta_app_command unconditionally
    # (not `if chat_reflexes_enabled`). Guard against the regression returning.
    import inspect
    src = inspect.getsource(tw)
    assert "_extract_sifta_app_command(text) if chat_reflexes_enabled" not in src


class _FakeLauncher:
    def __init__(self, open_apps=None):
        self.open_apps = list(open_apps or [])
        self.mode = "chat"
        self.events = []

    def _state(self):
        active = self.open_apps[-1] if self.open_apps else ""
        return {
            "desktop_mode": self.mode,
            "active_app": active,
            "open_apps": list(self.open_apps),
            "open_app_count": len(self.open_apps),
            "alice_chat_resident": True,
            "single_app_policy": True,
        }

    def sense_app_limb_state(self, *, reason="before_app_action"):
        self.events.append(("sense", reason, list(self.open_apps)))
        return self._state()

    def current_app_state(self):
        return self._state()

    def _trigger_manifest_app(self, app_name):
        self.events.append(("open", app_name, list(self.open_apps)))
        if app_name not in self.open_apps:
            self.open_apps[:] = [app_name]

    def close_app_by_title(self, app_name=""):
        self.events.append(("close", app_name, list(self.open_apps)))
        if not app_name and self.open_apps:
            return [self.open_apps.pop()]
        if app_name in self.open_apps:
            self.open_apps.remove(app_name)
            return [app_name]
        return []

    def close_all_open_apps(self):
        self.events.append(("close_all", "", list(self.open_apps)))
        closed = list(self.open_apps)
        self.open_apps.clear()
        return closed

    def _switch_desktop_mode(self, mode):
        self.events.append(("mode", mode, list(self.open_apps)))
        self.mode = mode


class _TalkHarness:
    def __init__(self, launcher):
        self.launcher = launcher
        self.lines = []

    def _desktop_app_launcher(self):
        return self.launcher

    def _append_system_line(self, text, *, error=False):
        self.lines.append((text, error))


def test_execute_open_senses_before_opening(monkeypatch, tmp_path):
    _use_tmp_state(monkeypatch, tmp_path)
    monkeypatch.setattr(tw, "_write_app_command_receipt", lambda **kwargs: "receipt-test")
    launcher = _FakeLauncher()
    harness = _TalkHarness(launcher)

    reply = tw.TalkToAliceWidget._execute_sifta_app_command(
        harness, {"kind": "app", "app_name": "Alice Browser", "url": ""}
    )

    assert launcher.events[0][0] == "sense"
    assert launcher.events[1][0] == "open"
    assert launcher.events[-1][0] == "sense"
    assert "checked first" in reply.lower()
    assert "closed" in reply.lower()


def test_execute_open_already_open_reports_raise(monkeypatch, tmp_path):
    state_dir = _use_tmp_state(monkeypatch, tmp_path)
    monkeypatch.setattr(tw, "_write_app_command_receipt", lambda **kwargs: "receipt-test")
    launcher = _FakeLauncher(["Alice Browser"])
    harness = _TalkHarness(launcher)

    reply = tw.TalkToAliceWidget._execute_sifta_app_command(
        harness, {"kind": "app", "app_name": "Alice Browser", "url": ""}
    )

    assert launcher.events[0][0] == "sense"
    assert any(event[0] == "open" for event in launcher.events)
    assert "already open" in reply.lower()
    rows = [
        json.loads(line)
        for line in (state_dir / "app_action_diary.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert any(r.get("line", "").startswith("I raised Alice Browser at ") for r in rows)


def test_execute_close_already_closed_is_noop(monkeypatch, tmp_path):
    state_dir = _use_tmp_state(monkeypatch, tmp_path)
    monkeypatch.setattr(tw, "_write_app_command_receipt", lambda **kwargs: "receipt-test")
    launcher = _FakeLauncher([])
    harness = _TalkHarness(launcher)

    reply = tw.TalkToAliceWidget._execute_sifta_app_command(
        harness, {"kind": "close_app", "app_name": "Alice Browser", "url": ""}
    )

    assert launcher.events == [("sense", "before_close_app:Alice Browser", [])]
    assert "already closed" in reply.lower()
    rows = [
        json.loads(line)
        for line in (state_dir / "app_action_diary.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert not any(r.get("line", "").startswith("I closed Alice Browser at ") for r in rows)


def test_execute_open_writes_before_after_and_first_person_diary(monkeypatch, tmp_path):
    state_dir = _use_tmp_state(monkeypatch, tmp_path)
    monkeypatch.setattr(tw, "_write_app_command_receipt", lambda **kwargs: "receipt-test")
    launcher = _FakeLauncher()
    harness = _TalkHarness(launcher)

    tw.TalkToAliceWidget._execute_sifta_app_command(
        harness,
        {
            "kind": "app",
            "app_name": "Alice Browser",
            "url": "",
            "owner_text": "Yes, please open Alice Browser",
        },
    )

    rows = [
        json.loads(line)
        for line in (state_dir / "app_action_diary.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert any(r.get("phase") == "before_action" and r.get("decision") == "extend_limb" for r in rows)
    assert any(r.get("phase") == "after_action" and r.get("receipt_id") == "receipt-test" for r in rows)
    assert any(r.get("line", "").startswith("I opened Alice Browser at ") for r in rows)
    limb_rows = [
        json.loads(line)
        for line in (state_dir / "app_limb_history.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert limb_rows[-1]["app"] == "Alice Browser"
    assert limb_rows[-1]["action"] == "open"


def test_execute_close_writes_first_person_diary(monkeypatch, tmp_path):
    state_dir = _use_tmp_state(monkeypatch, tmp_path)
    monkeypatch.setattr(tw, "_write_app_command_receipt", lambda **kwargs: "receipt-test")
    launcher = _FakeLauncher(["Alice Browser"])
    harness = _TalkHarness(launcher)

    reply = tw.TalkToAliceWidget._execute_sifta_app_command(
        harness,
        {"kind": "close_app", "app_name": "Alice Browser", "url": "", "owner_text": "close Alice Browser"},
    )

    assert "closed" in reply.lower()
    rows = [
        json.loads(line)
        for line in (state_dir / "app_action_diary.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert any(r.get("line", "").startswith("I closed Alice Browser at ") for r in rows)


def test_open_with_spoken_filler_routes_to_browser_not_chat():
    # George 2026-05-30 live bug: "Yes, please open Alice Browser" /
    # "I'll please open Alice Browser" routed to a chat-desktop switch instead
    # of opening the browser, because the anchored prefix whitelist missed the
    # leading filler. They must resolve to the Alice Browser app.
    for cmd in (
        "Yes, please open Alice Browser",
        "I'll please open Alice Browser",
        "Please try again to open Alice Browser. We are in a chat window.",
    ):
        out = tw._extract_sifta_app_command(cmd)
        assert out.get("kind") == "app", f"{cmd!r} -> {out}"
        assert out.get("app_name") == "Alice Browser", f"{cmd!r} -> {out}"


def test_open_with_nav_target_carries_url_not_just_app():
    # 2026-05-30 live bug: a browser app-open command with a site target opened
    # the browser to its home page and dropped the destination. It must resolve
    # to a browser_url through the site playbook.
    out = tw._extract_sifta_app_command("pls open @anymodel123 on tik tok in alice browser")
    assert out.get("kind") == "browser_url", out
    assert out.get("url") == "https://www.tiktok.com/@anymodel123", out
    out2 = tw._extract_sifta_app_command("open tiktok.com/@anymodel123 in alice browser")
    assert out2.get("kind") == "browser_url" and "tiktok.com/@anymodel123" in out2.get("url", "")
    # plain open with no target stays a no-URL app open
    out3 = tw._extract_sifta_app_command("open Alice Browser")
    assert out3.get("kind") == "app" and out3.get("url", "") == ""


def test_bare_site_category_in_browser_command_navigates_home():
    # Live STT bug: "And it's please open Alice browser on Instagram" is noisy
    # English, but the stable intent is a site category named in the browser
    # command. It should open Alice Browser AND navigate to that category home,
    # without requiring a hardcoded profile/person/search query.
    out = tw._extract_sifta_app_command("And it's please open Alice browser on Instagram.")
    assert out.get("kind") == "browser_url", out
    assert out.get("app_name") == "Alice Browser", out
    assert out.get("url") == "https://www.instagram.com", out

    out2 = tw._extract_sifta_app_command("open Alice browser on TikTok")
    assert out2.get("kind") == "browser_url", out2
    assert out2.get("url") == "https://www.tiktok.com", out2


def test_forgotten_izzy_x_link_opens_remembered_profile_not_current_page(monkeypatch, tmp_path):
    state = _use_tmp_state(monkeypatch, tmp_path)
    (state / "stigmergic_browser_actions.jsonl").write_text(
        json.dumps(
            {
                "action": "navigate_or_spa_change",
                "url": "https://x.com/abellaskies",
                "title": "Isabella (@abellaskies) / X",
                "trigger": {"owner_text_head": "OPEN IZZY ON TWITTER https://x.com/abellaskies"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    phrase = "i forgot izzy link on x:( can u pls open it?"

    assert not tw._is_current_page_query(phrase)
    out = tw._extract_sifta_app_command(phrase)
    assert out.get("kind") == "browser_url", out
    assert out.get("app_name") == "Alice Browser", out
    assert out.get("url") == "https://x.com/abellaskies", out
    assert out.get("remembered_target") == "izzy_x", out


def test_bare_handle_browser_open_recovers_platform_from_receipts_without_person_hardcode(monkeypatch, tmp_path):
    state = _use_tmp_state(monkeypatch, tmp_path)
    handle = "anymodel123"
    (state / "app_action_diary.jsonl").write_text(
        json.dumps(
            {
                "phase": "after_action",
                "app": "Alice Browser",
                "url": f"https://www.instagram.com/{handle}/",
                "line": f"I opened Alice Browser at https://www.instagram.com/{handle}/.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    for phrase in (
        f"pls open alice browser @{handle}",
        f"open @{handle} in alice browser",
    ):
        out = tw._extract_sifta_app_command(phrase)
        assert out.get("kind") == "browser_url", out
        assert out.get("app_name") == "Alice Browser", out
        assert out.get("url") == f"https://www.instagram.com/{handle}/", out


def test_spoken_site_target_uses_stigmergic_playbook_not_hardcoded_person():
    for handle in ("surfcoach2026", "bodymodel_xyz"):
        out = tw._extract_sifta_app_command(
            f"Alice please open alice browser Alice let's go on TikTok at {handle} go on TikTok"
        )
        assert out.get("kind") == "browser_url", out
        assert out.get("url") == f"https://www.tiktok.com/@{handle}", out


def test_spoken_site_target_rejects_common_place_phrase_as_profile():
    out = tw._extract_sifta_app_command("open Alice Browser and go on TikTok at the gym")
    assert out.get("kind") == "browser_url", out
    assert out.get("app_name") == "Alice Browser", out
    assert out.get("url", "") == "https://www.tiktok.com", out


def test_site_search_uses_site_category_playbook_for_changing_query():
    out = tw._extract_sifta_app_command("search ferrari on TikTok in Alice Browser")
    assert out.get("kind") == "browser_url", out
    assert out.get("url") == "https://www.tiktok.com/search?q=ferrari", out
    out2 = tw._extract_sifta_app_command("search mercedes on TikTok in Alice Browser")
    assert out2.get("url") == "https://www.tiktok.com/search?q=mercedes", out2
    out3 = tw._extract_sifta_app_command("SEARCH TAYLOR SWIFT ON INSTAGRAM.COM PLS")
    assert out3.get("kind") == "browser_url", out3
    assert out3.get("app_name") == "Alice Browser", out3
    assert out3.get("search_site") == "instagram.com", out3
    assert out3.get("query") == "TAYLOR SWIFT", out3
    assert out3.get("url") == "https://www.instagram.com/explore/search/keyword/?q=TAYLOR+SWIFT", out3
    out4 = tw._extract_sifta_app_command(
        "open instagram and search for taylor swift, do not include this text here you beautiful"
    )
    assert out4.get("kind") == "browser_url", out4
    assert out4.get("app_name") == "Alice Browser", out4
    assert out4.get("search_site") == "instagram.com", out4
    assert out4.get("query") == "taylor swift", out4
    assert out4.get("url") == "https://www.instagram.com/explore/search/keyword/?q=taylor+swift", out4
    assert "you+beautiful" not in out4.get("url", ""), out4
    assert "swimsuit" not in out4.get("url", "").lower(), out4


def test_site_search_action_reply_names_real_browser_move(monkeypatch, tmp_path):
    state_dir = _use_tmp_state(monkeypatch, tmp_path)
    monkeypatch.setattr(tw, "_write_app_command_receipt", lambda **kwargs: "r-instagram-search")
    monkeypatch.setattr(tw.QTimer, "singleShot", lambda *args, **kwargs: None)
    launcher = _FakeLauncher(["Alice Browser"])
    harness = _TalkHarness(launcher)
    url = "https://www.instagram.com/explore/search/keyword/?q=TAYLOR+SWIFT"

    reply = tw.TalkToAliceWidget._execute_sifta_app_command(
        harness,
        {
            "kind": "browser_url",
            "app_name": "Alice Browser",
            "url": url,
            "search_site": "instagram.com",
            "query": "TAYLOR SWIFT",
        },
    )

    assert (state_dir / "alice_browser_open_url.txt").read_text(encoding="utf-8") == url
    assert reply == "I searched Instagram for TAYLOR SWIFT in Alice Browser. Receipt: r-instagram-search"
    assert "Receipt: r-instagram-search" in reply
    assert reply != "Receipt: r-instagram-search"


def test_open_marketplace_target_on_ebay_routes_to_browser_before_app_match():
    # 2026-06-06 live bug: after a cloud-cortex timeout, recovery heard
    # "OPEN <query> ON EBAY" but fell through to fuzzy app matching and offered
    # Epistemic Mesh. This is a site-category search slot, not an app name and
    # not a hardcoded person.
    out = tw._extract_sifta_app_command("OPEN CERAMIC VASE ON EBAY")
    assert out.get("kind") == "browser_url", out
    assert out.get("app_name") == "Alice Browser", out
    assert out.get("search_site") == "ebay.com", out
    assert out.get("query") == "CERAMIC VASE", out
    assert out.get("url") == "https://www.ebay.com/sch/i.html?_nkw=CERAMIC+VASE", out

    out2 = tw._extract_sifta_app_command("open blue red sweater on eBay")
    assert out2.get("kind") == "browser_url", out2
    assert out2.get("url") == "https://www.ebay.com/sch/i.html?_nkw=blue+red+sweater", out2


def test_explicit_safari_marketplace_request_stays_in_alice_browser_by_doctrine():
    # r1243: George's browser doctrine keeps all web work inside Alice Browser.
    # r1316 tightens it: even explicit native browser wording does not leave
    # the Alice Browser limb while the limb is learning.
    out = tw._extract_sifta_app_command("open blue red sweater on eBay in Safari Mac OS")
    assert out.get("kind") == "browser_url", out
    assert out.get("app_name") == "Alice Browser", out
    assert out.get("browser_app") != "Safari", out
    assert out.get("url") == "https://www.ebay.com/sch/i.html?_nkw=blue+red+sweater", out

    default = tw._extract_sifta_app_command("open blue red sweater on eBay")
    assert default.get("kind") == "browser_url", default
    assert default.get("app_name") == "Alice Browser", default


def test_execute_native_safari_url_reroutes_to_alice_browser(monkeypatch, tmp_path):
    state_dir = _use_tmp_state(monkeypatch, tmp_path)
    monkeypatch.setattr(tw, "_write_app_command_receipt", lambda **kwargs: "receipt-native")
    calls = []

    class _Proc:
        pid = 818

    def _fake_popen(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return _Proc()

    monkeypatch.setattr(tw.subprocess, "Popen", _fake_popen)
    launcher = _FakeLauncher()
    harness = _TalkHarness(launcher)
    url = "https://www.ebay.com/sch/i.html?_nkw=blue+red+sweater"

    reply = tw.TalkToAliceWidget._execute_sifta_app_command(
        harness,
        {"kind": "native_browser_url", "app_name": "Safari", "url": url, "owner_text": "open in Safari"},
    )

    assert calls == []
    assert (state_dir / "alice_browser_open_url.txt").read_text(encoding="utf-8") == url
    assert "Alice Browser" in reply


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
