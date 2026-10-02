#!/usr/bin/env python3
"""Watcher-path tests for swarm_hot_reload.

Context (2026-09-29): the live body proved SIGUSR1 alone unreliable — two
delivered signals produced zero reload events in a running SIFTA OS while the
process stayed alive and busy, because a Python-level handler runs only when the
main thread returns to the eval loop. The request file plus the daemon watcher
thread is the path that does not depend on the main thread.

These tests keep the real whitelist and real module reloading out of the way:
they drive the request round trip against tmp_path files with importlib.reload
patched, so no live ledger and no live module state is touched.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System import swarm_hot_reload as hot_reload


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    """Point the request and heartbeat files at the test's own directory."""
    monkeypatch.setattr(hot_reload, "_REQUEST_FILE", tmp_path / "hot_reload_request.json")
    monkeypatch.setattr(hot_reload, "_HEARTBEAT_FILE", tmp_path / "hot_reload_watch.json")
    monkeypatch.setattr(hot_reload, "_STATE_DIR", tmp_path)
    yield tmp_path


def test_request_round_trip_carries_exact_targets(isolated_paths):
    """A written request is consumed once, and the named targets reach the reload.

    The swap path is asserted from the results, not from mock call counts:
    patching ``importlib.import_module`` patches the shared importlib module, so
    unrelated imports during the window inflate any counter.
    """
    with patch("System.swarm_hot_reload.importlib.reload"), \
         patch("System.swarm_hot_reload.importlib.import_module"), \
         patch("System.swarm_hot_reload._log"):
        path = hot_reload.request_reload(["slash_commands", "silicon"])
        assert path.exists()

        results = hot_reload.consume_request()

    assert [r["module"] for r in results] == ["slash_commands", "silicon"]
    assert all(r["ok"] for r in results)
    assert all(r.get("kind") in ("fresh_import", "in_place_swap") for r in results)
    assert not path.exists(), "a consumed request must not be left behind"


def test_request_is_consumed_exactly_once(isolated_paths):
    with patch("System.swarm_hot_reload.importlib.reload"), \
         patch("System.swarm_hot_reload._log"):
        hot_reload.request_reload(["silicon"])
        assert hot_reload.consume_request() is not None
        assert hot_reload.consume_request() is None


def test_missing_request_is_not_an_error(isolated_paths):
    assert hot_reload.consume_request() is None


def test_unreadable_request_is_graceful(isolated_paths):
    """A corrupt request is dropped and logged, never raised into the watcher."""
    isolated_paths.joinpath("hot_reload_request.json").write_text("{not json", encoding="utf-8")
    with patch("System.swarm_hot_reload._log") as mock_log:
        assert hot_reload.consume_request() is None
    assert any(call.args[0].get("action") == "request_unreadable" for call in mock_log.call_args_list)


def test_request_without_targets_means_full_whitelist(isolated_paths):
    with patch("System.swarm_hot_reload.importlib.reload"), \
         patch("System.swarm_hot_reload._log"):
        hot_reload.request_reload(None)
        payload = json.loads(isolated_paths.joinpath("hot_reload_request.json").read_text())
        assert payload["targets"] is None
        results = hot_reload.consume_request()
    assert len(results) == len(hot_reload.RELOADABLE)


def test_watcher_heartbeat_is_fresh_after_start_and_stale_when_old(isolated_paths):
    with patch("System.swarm_hot_reload._log"):
        assert hot_reload.watcher_alive() is False, "no heartbeat yet"
        hot_reload._heartbeat(force=True)
        assert hot_reload.watcher_alive() is True
        assert hot_reload.watcher_alive(pid=os.getpid()) is True
        assert hot_reload.watcher_alive(pid=os.getpid() + 12345) is False, "a different PID is not this watcher"

        isolated_paths.joinpath("hot_reload_watch.json").write_text(
            json.dumps({"pid": os.getpid(), "ts": time.time() - 3600}), encoding="utf-8",
        )
        assert hot_reload.watcher_alive() is False, "an hour-old heartbeat is not alive"


def test_heartbeat_from_a_dead_pid_is_not_alive(isolated_paths):
    """A fresh timestamp from a process that no longer exists must not count."""
    isolated_paths.joinpath("hot_reload_watch.json").write_text(
        json.dumps({"pid": 999_999_999, "ts": time.time()}), encoding="utf-8",
    )
    assert hot_reload.watcher_alive() is False


def test_watcher_thread_consumes_a_request_without_signals(isolated_paths):
    """The whole point: a request lands with no SIGUSR1 and no main-thread loop."""
    request_path = isolated_paths.joinpath("hot_reload_request.json")
    with patch("System.swarm_hot_reload.importlib.reload"), \
         patch("System.swarm_hot_reload._log"):
        try:
            assert hot_reload.start_watcher() is True
            assert hot_reload.start_watcher() is False, "starting twice must be a no-op"

            hot_reload.request_reload(["silicon"])
            deadline = time.time() + 5
            while time.time() < deadline and request_path.exists():
                time.sleep(0.1)
        finally:
            hot_reload.stop_watcher()

    assert not request_path.exists(), "the watcher must pick the request up on its own"
