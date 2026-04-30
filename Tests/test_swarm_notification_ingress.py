from __future__ import annotations

import inspect
from pathlib import Path

from System import swarm_notification_ingress as ingress


def test_btm_scan_never_invokes_sfltool(monkeypatch, tmp_path: Path) -> None:
    def fail_run(*_args, **_kwargs):
        raise AssertionError("scan_background_task_management must not invoke subprocesses")

    monkeypatch.setattr(ingress, "_run", fail_run)

    result = ingress.scan_background_task_management(tmp_path / "missing_dump.txt")

    assert result["ok"] is False
    assert result["source"] == "sfltool dumpbtm"
    assert result["items"] == []
    assert "Disabled" in result["error"]


def test_manual_btm_dump_is_parsed_when_supplied(tmp_path: Path) -> None:
    dump = tmp_path / "manual_sfltool_dumpbtm.txt"
    dump.write_text(
        "\n".join(
            [
                "#1:",
                "Name: antonia.sifta.warp9",
                "Identifier: com.antonia.sifta.warp9",
                "Disposition: enabled",
                "",
                "#2:",
                "Name: unrelated helper",
                "Identifier: com.example.helper",
            ]
        ),
        encoding="utf-8",
    )

    result = ingress.scan_background_task_management(dump)

    assert result["ok"] is True
    assert result["source"] == str(dump)
    assert len(result["items"]) == 1
    assert result["items"][0]["identifier"] == "com.antonia.sifta.warp9"


def test_missing_manual_btm_dump_returns_disabled_no_items(tmp_path: Path) -> None:
    result = ingress.scan_background_task_management(tmp_path / "missing_dump.txt")

    assert result["ok"] is False
    assert result["source"] == "sfltool dumpbtm"
    assert result["items"] == []
    assert "authentication popups" in result["error"]


def test_notification_center_scan_has_single_applescript_block() -> None:
    source = inspect.getsource(ingress.scan_visible_notification_center)

    assert source.count("script = r'''") == 1
    assert source.count('tell application "System Events"') == 1
