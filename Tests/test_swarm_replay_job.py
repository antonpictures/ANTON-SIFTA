"""WISH_002 - REM replay digest (salience + locked outputs)."""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_replay_job as jr


def test_salience_stigtime_bash_boost() -> None:
    row = {
        "kind": "STIGTIME_BOUNDARY",
        "stigtime_out": "thinking",
        "stigtime_in": "bash",
        "since_prev_boundary_sec": 400.0,
        "context": "pytest -q",
    }
    assert jr.salience_stigtime(row) >= 0.5


def test_salience_ide_tournament() -> None:
    row = {"kind": "tournament", "payload": "WISH_002", "source_ide": "cursor_m5"}
    assert jr.salience_ide(row) >= 0.5


def test_salience_work_bad_value_falls_back() -> None:
    row = {
        "work_type": "REPAIR_SUCCESS",
        "work_value": "not-a-number",
        "description": "pytest passed for replay",
    }
    assert jr.salience_work(row) > 0.0


def test_run_replay_digest_writes_json_and_jsonl(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(jr, "state_dir", lambda explicit=None: tmp_path)
    monkeypatch.setenv("SIFTA_REM_REPLAY_DEPOSIT", "0")

    st = tmp_path / "stigtime_log.jsonl"
    st.write_text(
        json.dumps(
            {
                "kind": "STIGTIME_BOUNDARY",
                "ts": 1.0,
                "stigtime_out": "idle",
                "stigtime_in": "bash",
                "since_prev_boundary_sec": 999.0,
                "context": "pytest",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    ide = tmp_path / "ide_stigmergic_trace.jsonl"
    ide.write_text(
        json.dumps({"kind": "hill_watch", "payload": "coord", "trace_id": "aa"})
        + "\n",
        encoding="utf-8",
    )

    out = jr.run_replay_digest(max_episodes=5, deposit_trace=False, root=tmp_path)
    assert out["episodes_count"] >= 1
    assert out["replay_id"]
    assert (tmp_path / "replay_memory.json").exists()
    assert (tmp_path / "replay_memory.jsonl").exists()
    snap = json.loads((tmp_path / "replay_memory.json").read_text(encoding="utf-8"))
    assert snap["truth_label"] == "REM_REPLAY_LATEST"
    assert snap["compressed_trajectories"]


def test_summary_for_prompt_truncates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(jr, "state_dir", lambda explicit=None: tmp_path)
    huge = {"truth_label": "REM_REPLAY_LATEST", "replay_id": "x", "episodes_count": 50}
    huge["compressed_trajectories"] = [{"source": "work_receipts", "n": i} for i in range(50)]
    (tmp_path / "replay_memory.json").write_text(
        json.dumps(huge, ensure_ascii=False), encoding="utf-8"
    )
    s = jr.summary_for_prompt(root=tmp_path, max_chars=200)
    assert len(s) <= 201
    assert "REM REPLAY DIGEST" in s
