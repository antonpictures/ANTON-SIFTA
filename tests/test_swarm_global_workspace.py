"""Event 130 - global workspace attention routing."""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_global_workspace as gw


def test_selects_direct_speech_and_prediction_error_over_background(tmp_path: Path) -> None:
    row = gw.select_attention(
        [
            gw.make_candidate("background_tv", "background_noise", 0.80),
            gw.make_candidate("owner_voice", "direct_user_speech", 0.55),
            gw.make_candidate("tool_error", "prediction_error", 0.40, prediction_error=3.0),
        ],
        k=2,
        root=tmp_path,
        now=100.0,
    )

    assert row["truth_label"] == "GLOBAL_WORKSPACE_BROADCAST"
    assert set(row["selected_signals"]) == {"owner_voice", "tool_error"}
    assert row["dropped_signals"] == ["background_tv"]


def test_writes_locked_receipt(tmp_path: Path) -> None:
    row = gw.select_attention(
        [gw.make_candidate("owner_continuity", "owner_continuity_trigger", 0.5)],
        root=tmp_path,
        now=101.0,
    )

    path = gw.workspace_log_path(tmp_path)
    written = json.loads(path.read_text(encoding="utf-8").strip())
    assert written["trace_id"] == row["trace_id"]
    assert written["selected_signals"] == ["owner_continuity"]


def test_disabled_returns_broadcast_without_writing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SIFTA_GLOBAL_WORKSPACE_DISABLE", "1")
    row = gw.select_attention(
        [gw.make_candidate("alert", "critical_system_alert", 0.2)],
        root=tmp_path,
        now=102.0,
    )

    assert row["disabled"] is True
    assert row["selected_signals"] == ["alert"]
    assert not gw.workspace_log_path(tmp_path).exists()


def test_summary_for_prompt_uses_latest_broadcast(tmp_path: Path) -> None:
    gw.select_attention(
        [
            gw.make_candidate("speech", "direct_user_speech", 0.7),
            gw.make_candidate("noise", "background_noise", 0.4),
        ],
        k=1,
        root=tmp_path,
        now=103.0,
    )

    summary = gw.summary_for_prompt(root=tmp_path)
    assert "GLOBAL WORKSPACE BROADCAST" in summary
    assert "selected=[speech]" in summary
    assert "dropped=[noise]" in summary


def test_stable_tiebreak_sort_by_signal_id(tmp_path: Path) -> None:
    row = gw.select_attention(
        [
            gw.make_candidate("b_signal", "task_goal", 0.3),
            gw.make_candidate("a_signal", "task_goal", 0.3),
        ],
        k=1,
        root=tmp_path,
        write_ledger=False,
        now=104.0,
    )

    assert row["selected_signals"] == ["a_signal"]
    assert row["dropped_signals"] == ["b_signal"]
