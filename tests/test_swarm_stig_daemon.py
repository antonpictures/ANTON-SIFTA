from __future__ import annotations

import json
import sys
import textwrap

import pytest

from System import swarm_stig_daemon as daemon


def test_pidfile_names_match_body_autopilot_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(daemon, "_STATE", tmp_path)

    assert daemon._pidfile_for_module("System.swarm_ble_radar").name == "alice_ble_radar.pid"
    assert daemon._pidfile_for_module("System.swarm_awdl_mesh").name == "alice_awdl_mesh.pid"
    assert (
        daemon._pidfile_for_module("System.swarm_unified_log").name
        == "alice_unified_log_daemon.pid"
    )
    assert (
        daemon._pidfile_for_module("System.swarm_vocal_proprioception").name
        == "alice_vocal_proprioception.pid"
    )


def test_parse_args_supports_one_shot_smoke_mode():
    mod_name, action, interval, once = daemon._parse_args(
        ["System.swarm_ble_radar", "scan", "15", "--once"]
    )

    assert mod_name == "System.swarm_ble_radar"
    assert action == "scan"
    assert interval == 15.0
    assert once is True


def test_parse_args_rejects_non_positive_interval():
    with pytest.raises(SystemExit):
        daemon._parse_args(["System.swarm_ble_radar", "scan", "0"])


def test_one_shot_cleans_pidfile_and_writes_status(tmp_path, monkeypatch):
    fake_module = tmp_path / "fake_stig_organ.py"
    fake_module.write_text(
        textwrap.dedent(
            """
            def govern(action):
                return {"ok": True, "action": action}
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(daemon, "_STATE", tmp_path)
    monkeypatch.setattr(daemon, "_EVENTS", tmp_path / "events.jsonl")
    monkeypatch.setattr(daemon, "_STATUS", tmp_path / "status.json")
    monkeypatch.setattr(daemon.signal, "signal", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sys, "argv", ["swarm_stig_daemon.py", "fake_stig_organ", "scan", "1", "--once"])
    daemon._STOP = False

    daemon._main()

    assert not (tmp_path / "fake_stig_organ.pid").exists()
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status["fake_stig_organ"]["ok"] is True
    assert status["fake_stig_organ"]["iteration"] == 1
