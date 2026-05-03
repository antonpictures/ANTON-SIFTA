"""Event 122 — Stigtime organ (locked JSONL boundaries)."""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_stigtime_tracker as st


def test_log_skips_same_lane(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(st, "state_dir", lambda explicit=None: tmp_path)
    assert st.log_action_boundary(actor="t", previous="idle", new="idle") is None
    assert not st.stigtime_log_path(tmp_path).exists()


def test_log_writes_boundary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(st, "state_dir", lambda explicit=None: tmp_path)
    row = st.log_action_boundary(actor="alice_talk", previous="idle", new="thinking", context="cortex=x")
    assert row is not None
    assert row["stigtime_out"] == "idle"
    assert row["stigtime_in"] == "thinking"
    p = st.stigtime_log_path(tmp_path)
    assert p.exists()
    line = p.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert json.loads(line)["trace_id"] == row["trace_id"]


def test_disable_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(st, "state_dir", lambda explicit=None: tmp_path)
    monkeypatch.setenv("SIFTA_STIGTIME_DISABLE", "1")
    assert st.log_action_boundary(actor="t", previous="a", new="b") is None


def test_tail_parses(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(st, "state_dir", lambda explicit=None: tmp_path)
    st.log_action_boundary(actor="t", previous="idle", new="thinking")
    st.log_action_boundary(actor="t", previous="thinking", new="bash")
    rows = st.tail_stigtime_rows(10, root=tmp_path)
    assert len(rows) == 2
    assert rows[-1]["stigtime_in"] == "bash"


def test_summary_for_alice_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(st, "state_dir", lambda explicit=None: tmp_path)
    assert st.summary_for_alice(root=tmp_path) == ""


def test_summary_for_alice_surfaces_recent_boundaries(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(st, "state_dir", lambda explicit=None: tmp_path)
    row = st.log_action_boundary(
        actor="alice_talk",
        previous="idle",
        new="thinking",
        context="cortex=sifta-gemma4-alice",
    )
    assert row is not None

    summary = st.summary_for_alice(root=tmp_path, now=float(row["ts"]) + 65)

    assert "STIGTIME ACTION CONTINUITY" in summary
    assert "recent_boundaries=1" in summary
    assert "1m ago: alice_talk shifted idle -> thinking" in summary
    assert "cortex=sifta-gemma4-alice" in summary
    assert "do not say you lack past-24h memory" in summary


def test_summary_for_alice_caps_rows_and_context(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(st, "state_dir", lambda explicit=None: tmp_path)
    for i in range(4):
        st.log_action_boundary(
            actor="alice_talk",
            previous=f"lane_{i}",
            new=f"lane_{i + 1}",
            context="x" * 200,
        )

    summary = st.summary_for_alice(max_rows=2, root=tmp_path)

    assert "recent_boundaries=2" in summary
    assert "lane_0 -> lane_1" not in summary
    assert "lane_2 -> lane_3" in summary
    assert "lane_3 -> lane_4" in summary
    assert "x" * 120 not in summary
