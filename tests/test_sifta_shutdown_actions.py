"""Regression checks for the SIFTA OS power-button semantics."""

from pathlib import Path

import sifta_os_desktop as desktop


REPO = Path(__file__).resolve().parent.parent


def test_shutdown_launcher_starts_detached_full_shutdown(monkeypatch):
    calls = []

    class FakeProcess:
        pass

    monkeypatch.setattr(
        desktop.subprocess,
        "Popen",
        lambda *args, **kwargs: calls.append((args, kwargs)) or FakeProcess(),
    )

    assert desktop._launch_full_sifta_shutdown() is True
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] == ["/bin/bash", str(REPO / "scripts" / "sifta_full_shutdown.sh")]
    assert kwargs["cwd"] == str(REPO)
    assert kwargs["start_new_session"] is True
    assert kwargs["stdin"] is desktop.subprocess.DEVNULL


def test_power_dialog_exposes_restart_and_shutdown_actions():
    source = (REPO / "sifta_os_desktop.py").read_text(encoding="utf-8")
    assert '"Shut down SIFTA OS"' in source
    assert '"Restart SIFTA OS"' in source
    assert "_launch_full_sifta_shutdown()" in source
    assert "_write_sifta_shutdown_fallback()" in source


def test_shutdown_fallback_is_checked_before_duplicate_process_guard():
    source = (REPO / "scripts" / "start_alice_desktop_app.sh").read_text(encoding="utf-8")
    assert source.index('if [ -f "$_NOTE" ]') < source.index("pgrep -f 'sifta_os_desktop'")
