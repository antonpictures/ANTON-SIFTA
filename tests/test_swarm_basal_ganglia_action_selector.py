"""Event 126a — basal ganglia selector."""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_basal_ganglia_action_selector as bg


def test_select_winner(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(bg, "state_dir", lambda explicit=None: tmp_path)
    loops = [
        {"name": "co_watch", "salience": 0.8, "cost": 0.2, "reward_potential": 0.9},
        {"name": "research_sweep", "salience": 0.6, "cost": 0.4, "reward_potential": 0.7},
        {"name": "idle", "salience": 0.3, "cost": 0.1, "reward_potential": 0.2},
    ]
    name, score = bg.select_action(loops, dopamine_level=0.75, root=tmp_path)
    assert name == "co_watch"
    assert score > 0
    log = bg.selection_log_path(tmp_path)
    assert log.exists()
    row = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["truth_label"] == "BASAL_GANGLIA_SELECTION"
    assert row["selected_action"] == "co_watch"


def test_disable_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(bg, "state_dir", lambda explicit=None: tmp_path)
    monkeypatch.setenv("SIFTA_BASAL_GANGLIA_DISABLE", "1")
    n, s = bg.select_action([{"name": "x", "salience": 1.0, "cost": 0.0, "reward_potential": 1.0}], root=tmp_path)
    assert n == "idle" and s == 0.0
    assert not bg.selection_log_path(tmp_path).exists()


def test_fatigued_owner_signal_biases_selection_and_records_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(bg, "state_dir", lambda explicit=None: tmp_path)

    monkeypatch.setattr(
        "System.swarm_stability_to_homeostasis_bridge.read_latest_clamp_signal",
        lambda **_: {"clamp_level": "NONE", "reason": "stability_clear"},
    )
    monkeypatch.setattr(
        "System.swarm_owner_somatic_state.latest_somatic_signal",
        lambda *_, **__: {
            "ok": True,
            "is_fatigued": True,
            "energy_score": 0.19,
            "energy_level": "low",
            "posture": "fatigued",
            "source": "owner_voice",
        },
    )

    loops = [
        {"name": "research_exploration", "salience": 0.9, "cost": 0.1, "reward_potential": 0.9},
        {"name": "repair_guard_loop", "salience": 0.65, "cost": 0.35, "reward_potential": 0.5},
    ]

    name, score = bg.select_action(loops, dopamine_level=0.0, root=tmp_path, write_ledger=True)

    assert name == "repair_guard_loop"
    assert score > 0.0
    row = json.loads(bg.selection_log_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()[-1])
    owner = row["biological_modifiers"]["owner_somatic"]
    assert owner["is_fatigued"] is True
    assert owner["energy_level"] == "low"
    assert owner["source"] == "owner_voice"
