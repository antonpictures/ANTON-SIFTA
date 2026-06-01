import json
from types import SimpleNamespace

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
