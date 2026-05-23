from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def _load_sense_loop_module():
    path = REPO / "launchd" / "swarm_sense_loop.py"
    spec = importlib.util.spec_from_file_location("swarm_sense_loop_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sense_loop_one_shot_cleans_pidfile_and_writes_status(tmp_path, monkeypatch):
    mod = _load_sense_loop_module()
    calls = []

    def poll_ok():
        calls.append("ok")

    monkeypatch.setattr(mod, "_STATE", tmp_path)
    monkeypatch.setattr(mod, "_PIDFILE", tmp_path / "alice_sense_loop.pid")
    monkeypatch.setattr(mod, "_EVENTS", tmp_path / "sense_loop_events.jsonl")
    monkeypatch.setattr(mod, "_STATUS", tmp_path / "sense_loop_status.json")
    monkeypatch.setattr(mod, "_load_pollers", lambda: [("fake", poll_ok)])
    monkeypatch.setattr(mod.signal, "signal", lambda *_args, **_kwargs: None)
    mod._STOP = False

    assert mod.main(["--once", "--interval", "1"]) == 0

    assert calls == ["ok"]
    assert not (tmp_path / "alice_sense_loop.pid").exists()
    status = json.loads((tmp_path / "sense_loop_status.json").read_text(encoding="utf-8"))
    assert status["ok"] is True
    assert status["results"] == {"fake": "ok"}
