"""Tests for Event 120/121 circadian lobe (locked JSONL, no task execution)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from System import swarm_circadian_agents as cal


def test_append_heartbeat_writes_jsonl(tmp_path: Path) -> None:
    row = cal.append_heartbeat(root=tmp_path)
    assert row["kind"] == "CIRCADIAN_HEARTBEAT"
    assert row["truth_label"] == cal.TRUTH_HEARTBEAT
    assert row["heartbeat_id"]
    assert row["node_serial"]
    assert "memory_percent" in row
    assert "human_likely_present" in row
    hb = cal.heartbeat_path(tmp_path)
    assert hb.name == "owner_heartbeat.jsonl"
    assert hb.exists()
    lines = hb.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["trace_id"] == row["trace_id"]


def test_agenda_roundtrip_and_pending_count(tmp_path: Path) -> None:
    cal.add_agenda_item("summarize receipts", priority="high", root=tmp_path)
    cal.add_agenda_item("idle", priority="low", status="done", root=tmp_path)
    today = cal.read_agenda_for_date(root=tmp_path)
    assert len(today) >= 1
    assert cal.count_pending_agenda(root=tmp_path) == 1


def test_run_pulse_includes_pending_count(tmp_path: Path) -> None:
    cal.add_agenda_item("x", root=tmp_path)
    pulse = cal.run_circadian_pulse(root=tmp_path)
    assert pulse["pending_agenda_count"] == 1


def test_daemon_respects_max_ticks(tmp_path: Path, monkeypatch) -> None:
    sleeps: list[float] = []

    def _sleep(sec: float) -> None:
        sleeps.append(sec)

    monkeypatch.setattr(cal, "_psutil", None)
    monkeypatch.setattr(cal.time, "sleep", _sleep)
    cal.run_daemon_loop(interval_sec=0.01, root=tmp_path, max_ticks=3)
    assert len(sleeps) == 3
    assert cal.heartbeat_path(tmp_path).exists()
    assert cal.heartbeat_path(tmp_path).read_text(encoding="utf-8").count("\n") >= 3


def test_main_one_shot(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cal, "run_circadian_pulse", lambda root=None: {"ok": True, "root": str(root or "")})
    code = cal.main([])
    assert code == 0
    out = capsys.readouterr().out
    assert "ok" in out


def test_class_shim_get_today_agenda(tmp_path: Path) -> None:
    cal.CircadianAgentLobe.add_agenda_item("task", root=tmp_path)
    items = cal.CircadianAgentLobe.get_today_agenda(root=tmp_path)
    assert any(i.get("task") == "task" for i in items)


def test_event_120_compatibility_surface(tmp_path: Path) -> None:
    hb = cal.CircadianAgentLobe.get_system_heartbeat(
        state_dir=tmp_path,
        now=1_777_800_000.0,
    )
    assert hb["truth_label"] == cal.TRUTH_HEARTBEAT
    assert hb["watcher_period_s"] == 60
    assert len(hb["heartbeat_id"]) == 12

    logged = cal.log_heartbeat(state_dir=tmp_path, now=1_777_800_000.0)
    cal.add_agenda_item("review owner heartbeat", priority="critical", root=tmp_path, now=1_777_800_010.0)
    summary = cal.get_circadian_summary(state_dir=tmp_path, now=1_777_800_060.0)

    assert logged["heartbeat_id"]
    assert summary["truth_label"] == cal.TRUTH_SUMMARY
    assert summary["heartbeat_age_s"] == 60.0
    assert summary["pending_agenda_count"] == 1
    assert summary["pending_agenda"][0]["priority"] == "critical"


def test_empty_agenda_item_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        cal.add_agenda_item("   ", root=tmp_path)


def test_presence_age_in_snapshot(tmp_path: Path) -> None:
    pres = tmp_path / "owner_desktop_presence.json"
    pres.write_text(
        json.dumps({"last_alive_ts": time.time() - 30.0, "last_alive_iso_utc": "x"}),
        encoding="utf-8",
    )
    snap = cal.collect_environment_snapshot(root=tmp_path)
    assert snap["owner_desktop_alive_age_sec"] is not None
    assert snap["owner_desktop_alive_age_sec"] >= 29.0
