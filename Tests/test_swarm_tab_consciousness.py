from __future__ import annotations

import json

import pytest

from System import swarm_tab_consciousness as tc


class _FakeProcess:
    def __init__(self, stdout: str, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def test_tab_consciousness_defaults_off(tmp_path):
    assert tc.is_active(state_dir=tmp_path) is False
    assert tc.write_current_state(state_dir=tmp_path) is None
    assert not (tmp_path / "tab_consciousness.jsonl").exists()


def test_tab_consciousness_samples_titles_only_by_default(tmp_path, monkeypatch):
    payload = {
        "ok": True,
        "status": "ok",
        "tabs": [
            {
                "window_index": 1,
                "tab_index": 1,
                "title": "Research field",
                "url": "https://example.test/private?q=1",
            }
        ],
    }

    monkeypatch.setattr(
        tc.subprocess,
        "run",
        lambda *args, **kwargs: _FakeProcess(json.dumps(payload)),
    )

    assert tc.activate("test", state_dir=tmp_path, now=10.0) is True
    row = tc.write_current_state("unit_test", state_dir=tmp_path, now=11.0)

    assert row is not None
    assert row["ok"] is True
    assert row["tab_count"] == 1
    assert row["tabs"][0]["title"] == "Research field"
    assert row["tabs"][0]["url"] == ""
    assert row["collect_urls"] is False


def test_tab_consciousness_collects_urls_only_when_explicit(tmp_path, monkeypatch):
    payload = {
        "ok": True,
        "status": "ok",
        "tabs": [
            {
                "window_index": 1,
                "tab_index": 2,
                "title": "Public docs",
                "url": "https://example.test/docs",
            }
        ],
    }

    monkeypatch.setattr(
        tc.subprocess,
        "run",
        lambda *args, **kwargs: _FakeProcess(json.dumps(payload)),
    )

    tc.activate("test", state_dir=tmp_path, collect_urls=True, now=20.0)
    row = tc.write_current_state("unit_test", state_dir=tmp_path, now=21.0)

    assert row is not None
    assert row["collect_urls"] is True
    assert row["tabs"][0]["url"] == "https://example.test/docs"


def test_tab_consciousness_writes_failure_receipt_when_probe_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(
        tc.subprocess,
        "run",
        lambda *args, **kwargs: _FakeProcess("", returncode=1, stderr="automation denied"),
    )

    tc.activate("test", state_dir=tmp_path, now=30.0)
    row = tc.write_current_state("unit_test", state_dir=tmp_path, now=31.0)

    assert row is not None
    assert row["ok"] is False
    assert row["status"] == "osascript_returncode"
    assert "automation denied" in row["error"]


def test_tab_consciousness_stgm_cost_is_delta_not_cumulative(tmp_path):
    tc.activate("test", state_dir=tmp_path, now=0.0)
    tc.configure(cost_per_hour=2.0, changed_by="test", state_dir=tmp_path)

    first = tc.burn_active_cost(state_dir=tmp_path, now=1800.0)
    second = tc.burn_active_cost(state_dir=tmp_path, now=3600.0)
    status = tc.get_status(state_dir=tmp_path)

    assert first == pytest.approx(1.0)
    assert second == pytest.approx(1.0)
    assert status["accrued_stgm_cost"] == pytest.approx(2.0)
