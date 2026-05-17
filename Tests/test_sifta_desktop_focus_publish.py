def test_active_mdi_window_focus_is_published(monkeypatch):
    import System.swarm_app_focus as app_focus
    from sifta_os_desktop import _publish_sifta_active_window_focus

    calls = []
    monkeypatch.setattr(app_focus, "publish_focus", lambda *args, **kwargs: calls.append((args, kwargs)))

    _publish_sifta_active_window_focus("⚙ Stigmergic Unified Shazam", "Stigmergic Unified Shazam")

    assert calls
    args, kwargs = calls[-1]
    assert args[0] == "Stigmergic Unified Shazam"
    assert args[1] == "Active SIFTA OS window selected"
    assert kwargs["tab"] == "MDI"
    assert kwargs["selection"] == "⚙ Stigmergic Unified Shazam"
    assert kwargs["metadata"]["event"] == "subwindow_activated"


def test_desktop_root_focus_is_not_published(monkeypatch):
    import System.swarm_app_focus as app_focus
    from sifta_os_desktop import _publish_sifta_active_window_focus

    calls = []
    monkeypatch.setattr(app_focus, "publish_focus", lambda *args, **kwargs: calls.append((args, kwargs)))

    _publish_sifta_active_window_focus("SIFTA OS", "SIFTA OS")

    assert calls == []


def test_app_health_lifecycle_bridge_records_enter_exit(monkeypatch):
    import System.swarm_app_health as app_health
    from sifta_os_desktop import _record_sifta_app_health_lifecycle

    calls = []
    monkeypatch.setattr(
        app_health,
        "record_app_lifecycle",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    _record_sifta_app_health_lifecycle(
        "Ace",
        "enter_update",
        manifest_entry={"category": "Alice"},
        note="focused",
        extra={"window_title": "⚙ Ace"},
    )
    _record_sifta_app_health_lifecycle("Ace", "exit_update", note="closed")

    assert [call[1]["action"] for call in calls] == ["enter_update", "exit_update"]
    assert calls[0][0] == ("Ace",)
    assert calls[0][1]["manifest_entry"] == {"category": "Alice"}
    assert calls[0][1]["extra"] == {"window_title": "⚙ Ace"}
