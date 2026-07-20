import json
from pathlib import Path
from types import SimpleNamespace
from types import MethodType

import Applications.sifta_alice_browser_widget as browser
from System import swarm_browser_page_state as page_state


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


def test_blank_render_proof_is_coded_not_address_only() -> None:
    source = (Path(__file__).resolve().parents[1] / "Applications" / "sifta_alice_browser_widget.py").read_text(
        encoding="utf-8"
    )

    assert "_DESKTOP_CHROME_USER_AGENT" in source
    assert "setHttpUserAgent(_DESKTOP_CHROME_USER_AGENT)" in source
    assert "ALICE_BROWSER_BLANK_RENDER_V1" in source
    assert "_verify_rendered_after_navigation" in source
    assert "QTimer.singleShot(1200, self._browser_awareness_tick)" in source
    assert "probe_unreadable" in source
    assert "ReloadAndBypassCache" in source


def _jsonl_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _blank_probe(url: str, *, reason: str = "empty_dom") -> dict:
    return {
        "url": url,
        "title": "",
        "ready_state": "complete",
        "text_chars": 0,
        "body_children": 0,
        "controls_count": 0,
        "images_count": 0,
        "html_len": 120,
        "background": "rgba(0, 0, 0, 0)",
        "blank_render": True,
        "probe_unreadable": False,
        "reason": reason,
    }


def _probe_widget(monkeypatch, tmp_path: Path, results: list[object]):
    _patch_state(monkeypatch, tmp_path)
    scheduled = []

    class FakePage:
        def __init__(self):
            self.triggered = []

        def runJavaScript(self, _js, callback):
            callback(results.pop(0))

        def triggerAction(self, action):
            self.triggered.append(action)

    class FakeView:
        def __init__(self):
            self._page = FakePage()
            self.reload_count = 0

        def page(self):
            return self._page

        def reload(self):
            self.reload_count += 1

    class FakeStatus:
        def __init__(self):
            self.messages = []

        def showMessage(self, text, _timeout=0):
            self.messages.append(text)

    def fake_single_shot(ms, callback):
        scheduled.append((ms, callback))

    monkeypatch.setattr(browser.QTimer, "singleShot", fake_single_shot)
    monkeypatch.setattr(
        browser,
        "QWebEnginePage",
        SimpleNamespace(WebAction=SimpleNamespace(ReloadAndBypassCache="hard-reload")),
        raising=False,
    )

    url = "https://www.ebay.com/sch/i.html?_nkw=maisie+williams"
    view = FakeView()
    status = FakeStatus()
    widget = SimpleNamespace(
        _view=view,
        _current_url=url,
        _page_load_ts=1000.0,
        _blank_render_retry_by_url={url: 0},
        _blank_render_probe_retry_by_url={url: 0},
        _status=status,
        captured=[],
    )
    widget._verify_rendered_after_navigation = MethodType(browser.AliceBrowserWidget._verify_rendered_after_navigation, widget)
    widget._blank_render_probe_js = MethodType(browser.AliceBrowserWidget._blank_render_probe_js, widget)
    widget._record_blank_render_probe = MethodType(browser.AliceBrowserWidget._record_blank_render_probe, widget)
    widget._hard_reload_current_page = MethodType(browser.AliceBrowserWidget._hard_reload_current_page, widget)
    widget._blank_render_followup_delay_ms = browser.AliceBrowserWidget._blank_render_followup_delay_ms
    widget._capture_current_page_state = lambda **kw: widget.captured.append(kw)
    widget.get_current_media_playback_status = lambda: {"ok": True}
    return widget, view, status, scheduled, url


def test_probe_returned_non_dict_is_unreadable_not_blank(monkeypatch, tmp_path):
    url = "https://example.com/page"
    results = [
        None,
        {"url": url, "title": "Loaded", "ready_state": "complete", "blank_render": False, "reason": "render_has_content"},
    ]
    widget, view, _status, scheduled, _ = _probe_widget(monkeypatch, tmp_path, results)
    widget._current_url = url
    widget._blank_render_retry_by_url = {url: 0}
    widget._blank_render_probe_retry_by_url = {url: 0}

    widget._verify_rendered_after_navigation(url, source="unit")

    rows = _jsonl_rows(tmp_path / "alice_browser_blank_render.jsonl")
    assert rows[-1]["action"] == "probe_unreadable"
    assert rows[-1]["reason"] == "probe_returned_non_dict"
    assert rows[-1]["blank_render"] is False
    assert view.reload_count == 0
    assert scheduled

    scheduled.pop(0)[1]()
    assert widget.captured[-1]["source"] == "unit_probe_retry_proof_dom"


def test_blank_render_ladder_reloads_then_hard_reloads_then_persists(monkeypatch, tmp_path):
    results = [_blank_probe(""), _blank_probe(""), _blank_probe("")]
    widget, view, status, scheduled, url = _probe_widget(monkeypatch, tmp_path, results)
    for probe in results:
        probe["url"] = url

    widget._verify_rendered_after_navigation(url, source="unit")
    rows = _jsonl_rows(tmp_path / "alice_browser_blank_render.jsonl")
    assert rows[-1]["action"] == "reload_once"
    assert view.reload_count == 1
    assert scheduled

    scheduled.pop(0)[1]()
    rows = _jsonl_rows(tmp_path / "alice_browser_blank_render.jsonl")
    assert rows[-1]["action"] == "hard_reload_once"
    assert view.page().triggered == ["hard-reload"]
    assert scheduled

    scheduled.pop(0)[1]()
    rows = _jsonl_rows(tmp_path / "alice_browser_blank_render.jsonl")
    assert rows[-1]["action"] == "blank_render_persisted"
    assert any("did not render" in msg for msg in status.messages)
    snapshot = json.loads((tmp_path / "alice_browser_current_page.json").read_text(encoding="utf-8"))
    assert snapshot["extra"]["blank_render"]["action"] == "blank_render_persisted"
    assert "did not render" in snapshot["extra"]["honest_message"]


def test_spa_visit_timer_resets_per_url_for_browse_dwell_receipts():
    source = (Path(__file__).resolve().parents[1] / "Applications" / "sifta_alice_browser_widget.py").read_text(
        encoding="utf-8"
    )

    assert "self._current_visit_started_at = now" in source
    assert "started = getattr(self, \"_current_visit_started_at\"" in source
    assert "dwell = max(0.0, now - float(started))" in source
    assert "_write_browse_receipt(prev_url, prev_title, duration_s=dwell, opened_at=float(started), closed_at=now)" in source


def test_owner_browser_actions_inferred_from_dom_result():
    actions = browser._owner_browser_actions_from_dom_result(
        {
            "media": {
                "status": "playing",
                "video_count": 1,
                "current_time": 42.0,
                "duration": 300.0,
                "muted": False,
            },
            "search": {"value": "ai campaigns", "placeholder": "Search"},
            "scroll": {"pct": 63},
        }
    )

    names = [a[0] for a in actions]
    assert "media_playing" in names
    assert "search_query_visible" in names
    assert "scroll_depth_50" in names


def test_native_handoff_prefers_clicked_instagram_reel():
    url = browser._choose_native_media_handoff_url(
        {
            "location": "https://www.instagram.com/kylinmilan/",
            "last_clicked": "https://www.instagram.com/reel/ABC123/",
            "video_src": "https://cdn.example/video.mp4",
        },
        fallback_url="https://www.instagram.com/kylinmilan/",
        media_status={"recent_errors": [{"code": 4, "src": "https://cdn.example/error.mp4"}]},
    )

    assert url == "https://www.instagram.com/reel/ABC123/"


def test_native_handoff_uses_signed_mp4_when_profile_url_has_decode_error():
    url = browser._choose_native_media_handoff_url(
        {"location": "https://www.instagram.com/kylinmilan/"},
        fallback_url="https://www.instagram.com/kylinmilan/",
        media_status={"recent_errors": [{"code": 4, "src": "https://cdn.example/reel.mp4"}]},
    )

    assert url == "https://cdn.example/reel.mp4"


def test_native_handoff_prefers_current_instagram_post_url_over_decode_error_src():
    url = browser._choose_native_media_handoff_url(
        {
            "location": "https://www.instagram.com/p/C1mzc4CvjRh/",
            "video_src": "https://cdn.example/visible-video.mp4",
        },
        fallback_url="https://www.instagram.com/explore/",
        media_status={"recent_errors": [{"code": 4, "src": "https://cdn.example/error.mp4"}]},
    )

    assert url == "https://www.instagram.com/p/C1mzc4CvjRh/"


def test_visible_media_candidate_scoring_prefers_ocean_metadata():
    query = "open the photo currently positioned against the beach/ocean backdrop"
    candidates = [
        {"href": "https://www.instagram.com/p/A/", "alt": "woman in a red outfit", "row": 2, "col": 1, "onscreen": 90000},
        {"href": "https://www.instagram.com/p/B/", "alt": "woman posing at the ocean beach", "row": 3, "col": 4, "onscreen": 90000},
    ]

    best, score = browser._best_visible_media_candidate(query, candidates)

    assert best["href"].endswith("/B/")
    assert score >= 8.0
    assert not browser._visible_media_query_needs_vision(query, score)


def test_visible_media_candidate_needs_vision_when_dom_has_no_visual_match():
    query = "open the photo currently positioned against the beach/ocean backdrop"
    candidates = [
        {"href": "https://www.instagram.com/p/A/", "alt": "", "row": 2, "col": 1, "onscreen": 90000},
        {"href": "https://www.instagram.com/p/B/", "alt": "", "row": 3, "col": 4, "onscreen": 90000},
    ]

    best, score = browser._best_visible_media_candidate(query, candidates)

    assert best is not None
    assert browser._visible_media_query_needs_vision(query, score)


def test_visible_media_selection_parser_reads_json_and_text():
    assert browser._parse_visible_media_selection('{"row":3,"col":4,"reason":"ocean"}') == (3, 4)
    assert browser._parse_visible_media_selection("row 2, column 5") == (2, 5)


def test_visible_media_selection_stays_on_codex_when_codex_selected(monkeypatch, tmp_path):
    _patch_state(monkeypatch, tmp_path)
    img = tmp_path / "viewport.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 9000)

    class DummyBrowser:
        _current_url = "https://www.instagram.com/kylinmilan/"

        def _capture_viewport_image(self, expected_url=""):
            return str(img)

    calls = []

    def fake_arm(arm_id, prompt, **kwargs):
        calls.append(arm_id)
        if arm_id != "codex_agent":
            raise AssertionError(f"selected Codex tile selection leaked to {arm_id}")
        return SimpleNamespace(
            ok=True,
            output='{"row":0,"col":0,"reason":"no match"}',
            status="OK",
            receipt_id="codex-no-match",
            returncode=0,
        )

    monkeypatch.setattr("System.swarm_agent_arm_launcher.ask_agent_arm", fake_arm)

    result = browser.AliceBrowserWidget._select_visible_media_candidate_with_vision(
        DummyBrowser(),
        "open the ocean photo",
        [{"href": "https://www.instagram.com/p/A/", "row": 1, "col": 1, "alt": "", "onscreen": 90000}],
        current_arm="codex_agent",
        current_model="codex:gpt-5.5",
    )

    assert result == {}
    assert calls == ["codex_agent"]


def test_describe_current_photo_stays_on_grok_after_grok_api_failure(monkeypatch, tmp_path):
    _patch_state(monkeypatch, tmp_path)
    img = tmp_path / "viewport.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 9000)

    class DummyBrowser:
        _current_url = "https://www.instagram.com/p/current/"

        def _capture_viewport_image(self, expected_url=""):
            return str(img)

    calls = []

    def fake_grok_eye(image_path, prompt, **kwargs):
        calls.append(("grok_agent", kwargs))
        return SimpleNamespace(
            ok=False,
            output="API error 401: missing or invalid xAI key",
            status="EXEC_FAILED_COMMAND_FAILED",
            receipt_id="grok-fail",
            returncode=3,
        )

    def no_fallback_arm(*args, **kwargs):
        raise AssertionError("strict Grok photo describe should not call fallback arms")

    monkeypatch.setattr("System.xai_grok_oauth_organ.describe_image_with_grok", fake_grok_eye)
    monkeypatch.setattr("System.swarm_agent_arm_launcher.ask_agent_arm", no_fallback_arm)
    monkeypatch.setattr("System.xai_grok_oauth_organ.preflight_grok_vision_key", lambda: (True, "ok"))
    refreshes = []
    monkeypatch.setattr(
        "System.swarm_cortex_failover_reflex.schedule_oauth_refresh",
        lambda **kwargs: refreshes.append(kwargs) or {"status": "launched", "pid": 123},
    )

    result = browser.AliceBrowserWidget.describe_current_photo(
        DummyBrowser(),
        current_arm="grok_agent",
        current_model="grok:grok-4.3",
    )

    assert result["status"] == "grok_eye_auth_refresh_required"
    assert result["arm"] == "grok_agent"
    assert result["description"] == ""
    assert [c[0] for c in calls] == ["grok_agent"]
    assert calls[0][1]["model"] == "grok:grok-4.3"
    assert result["attempts"][0]["status"] == "EXEC_FAILED_COMMAND_FAILED"
    assert len(result["attempts"]) == 1
    assert refreshes
    assert "OAuth" in result["diary_note"]
    assert "did not switch to Claude" in result["diary_note"]


def test_describe_current_photo_stays_on_codex_after_empty_codex_scan(monkeypatch, tmp_path):
    _patch_state(monkeypatch, tmp_path)
    img = tmp_path / "viewport.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 9000)

    class DummyBrowser:
        _current_url = "https://www.instagram.com/p/current/"

        def _capture_viewport_image(self, expected_url=""):
            return str(img)

    calls = []

    def fake_arm(arm_id, prompt, **kwargs):
        calls.append(arm_id)
        if arm_id != "codex_agent":
            raise AssertionError(f"selected Codex eye leaked to fallback arm {arm_id}")
        return SimpleNamespace(
            ok=True,
            output="",
            stderr="",
            status="OK",
            receipt_id="codex-empty",
            returncode=0,
        )

    monkeypatch.setattr("System.swarm_agent_arm_launcher.ask_agent_arm", fake_arm)

    result = browser.AliceBrowserWidget.describe_current_photo(
        DummyBrowser(),
        current_arm="codex_agent",
        current_model="codex:gpt-5.5",
    )

    assert result["status"] == "codex_eye_failed"
    assert result["arm"] == "codex_agent"
    assert result["description"] == ""
    assert calls == ["codex_agent"]
    assert result["attempts"][0]["status"] == "OK"
    assert len(result["attempts"]) == 1
    assert "Codex is my selected cortex/eye" in result["diary_note"]
    assert "did not switch to Claude" in result["diary_note"]


def test_describe_current_photo_does_not_inject_stale_identity_from_other_page(monkeypatch, tmp_path):
    _patch_state(monkeypatch, tmp_path)
    img = tmp_path / "viewport.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 9000)
    page_state.record_page_state(
        "https://x.com/abellaskies/status/old/photo/1",
        title="Isabella (@abellaskies) / X",
        text="@abellaskies Izzy photo post",
        state_dir=tmp_path,
    )

    class DummyBrowser:
        _current_url = "https://www.youtube.com/watch?v=current"
        _history = [{"content": "her name is Izzy in the browser photo"}]

        def _capture_viewport_image(self, expected_url=""):
            return str(img)

    prompts = []

    def fake_local_eye(image_path, prompt, **kwargs):
        prompts.append(prompt)
        return SimpleNamespace(
            ok=True,
            output="A YouTube page is visible with a video player and sidebar.",
            stderr="",
            status="ok",
            receipt_id="local-ok",
            returncode=0,
        )

    monkeypatch.setattr("System.swarm_mlx_vlm_brain.is_available", lambda: False, raising=False)
    monkeypatch.setattr("System.swarm_mlx_vlm_brain.describe_available", lambda: False, raising=False)
    monkeypatch.setattr("System.swarm_ollama_vision_arm.local_vision_available", lambda **kwargs: True)
    monkeypatch.setattr("System.swarm_ollama_vision_arm.describe_image_local", fake_local_eye)

    result = browser.AliceBrowserWidget.describe_current_photo(
        DummyBrowser(),
        current_arm="ollama_vision_agent",
        current_model="alice-m5-cortex-8b-6.3gb:latest",
    )

    assert result["status"] == "described"
    assert prompts
    assert "Izzy" not in prompts[0]
    assert "abellaskies" not in prompts[0]
    assert "known from recent owner report" not in prompts[0]


def test_describe_current_photo_grok_subscription_failure_uses_local_backup(monkeypatch, tmp_path):
    _patch_state(monkeypatch, tmp_path)
    img = tmp_path / "viewport.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 9000)

    class DummyBrowser:
        _current_url = "https://www.instagram.com/p/current/"

        def _capture_viewport_image(self, expected_url=""):
            return str(img)

    calls = []

    def fake_grok_eye(image_path, prompt, **kwargs):
        calls.append("grok_agent")
        return SimpleNamespace(
            ok=False,
            output="",
            stderr="subscription required for this Grok vision operation",
            status="http_error:402",
            receipt_id="grok-subscription",
            returncode=3,
        )

    def fake_local_eye(image_path, prompt, **kwargs):
        calls.append("ollama_vision_agent")
        return SimpleNamespace(
            ok=True,
            output="Leonardo DiCaprio is shown in a formal black tuxedo and bow tie.",
            stderr="",
            status="ok",
            receipt_id="local-ok",
            returncode=0,
        )

    monkeypatch.setattr("System.xai_grok_oauth_organ.describe_image_with_grok", fake_grok_eye)
    monkeypatch.setattr("System.xai_grok_oauth_organ.preflight_grok_vision_key", lambda: (True, "ok"))
    monkeypatch.setattr("System.swarm_ollama_vision_arm.local_vision_available", lambda **kwargs: True)
    monkeypatch.setattr("System.swarm_ollama_vision_arm.describe_image_local", fake_local_eye)

    result = browser.AliceBrowserWidget.describe_current_photo(
        DummyBrowser(),
        current_arm="grok_agent",
        current_model="grok:grok-4.3",
    )

    assert result["status"] == "described"
    assert result["arm"] == "ollama_vision_agent"
    assert calls == ["grok_agent", "ollama_vision_agent"]
    assert [a["status"] for a in result["attempts"]] == ["http_error:402", "described"]
    assert "declared backup" in result["diary_note"]
    assert "Claude" in result["diary_note"]


def test_describe_current_photo_preflights_missing_grok_key_without_fallback(monkeypatch, tmp_path):
    _patch_state(monkeypatch, tmp_path)
    img = tmp_path / "viewport.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 9000)

    class DummyBrowser:
        _current_url = "https://www.instagram.com/p/current/"

        def _capture_viewport_image(self, expected_url=""):
            return str(img)

    monkeypatch.setattr(
        "System.xai_grok_oauth_organ.preflight_grok_vision_key",
        lambda: (False, "my grok eye needs my xAI key set"),
    )
    monkeypatch.setattr(browser, "_grok_cli_ready", lambda: False)
    def no_cloud_arm(*args, **kwargs):
        raise AssertionError("missing key should not call grok cloud arm")

    monkeypatch.setattr("System.swarm_agent_arm_launcher.ask_agent_arm", no_cloud_arm)
    refreshes = []
    monkeypatch.setattr(
        "System.swarm_cortex_failover_reflex.schedule_oauth_refresh",
        lambda **kwargs: refreshes.append(kwargs) or {"status": "launched", "pid": 123},
    )

    result = browser.AliceBrowserWidget.describe_current_photo(
        DummyBrowser(),
        current_arm="grok_agent",
        current_model="grok:grok-4.3",
    )

    assert result["status"] == "grok_eye_auth_refresh_required"
    assert result["arm"] == "grok_agent"
    assert result["description"] == ""
    assert result["attempts"][0]["arm"] == "grok_agent"
    assert result["attempts"][0]["status"] == "grok_eye_auth_refresh_required"
    assert refreshes
    assert "xAI OAuth" in result["diary_note"]
    assert "did not switch to Claude" in result["diary_note"]


def test_describe_current_photo_uses_grok_cli_even_when_token_preflight_is_stale(monkeypatch, tmp_path):
    _patch_state(monkeypatch, tmp_path)
    img = tmp_path / "viewport.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 9000)

    class DummyBrowser:
        _current_url = "https://www.instagram.com/p/current/"

        def _capture_viewport_image(self, expected_url=""):
            return str(img)

    calls = []

    monkeypatch.setattr(
        "System.xai_grok_oauth_organ.preflight_grok_vision_key",
        lambda: (False, "stale token file"),
    )
    monkeypatch.setattr(browser, "_grok_cli_ready", lambda: True)

    def fake_grok_eye(image_path, prompt, **kwargs):
        calls.append(("grok_agent", kwargs))
        return SimpleNamespace(
            ok=True,
            output="Leonardo DiCaprio is shown in a formal black tuxedo and bow tie.",
            stderr="",
            status="ok",
            receipt_id="grok-cli-ok",
            returncode=0,
        )

    monkeypatch.setattr("System.xai_grok_oauth_organ.describe_image_with_grok", fake_grok_eye)

    result = browser.AliceBrowserWidget.describe_current_photo(
        DummyBrowser(),
        current_arm="grok_agent",
        current_model="grok:grok-4.3",
    )

    assert result["status"] == "described"
    assert result["arm"] == "grok_agent"
    assert "Leonardo DiCaprio" in result["description"]
    assert [c[0] for c in calls] == ["grok_agent"]
