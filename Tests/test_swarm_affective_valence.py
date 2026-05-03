import json

import pytest

from System.swarm_affective_valence import (
    affective_valence_path,
    compute_affective_valence,
    get_latest_valence_row,
    summary_for_prompt,
)


def test_reward_drives_approach_valence(tmp_path):
    row = compute_affective_valence(
        reward=0.95,
        surprise=0.0,
        threat=0.0,
        arousal=0.5,
        root=tmp_path,
        write_ledger=False,
    )

    assert row["regime"] == "APPROACH"
    assert row["valence"] > 0.5
    assert 0.0 <= row["intensity"] <= 1.0


def test_threat_drives_avoid_valence(tmp_path):
    row = compute_affective_valence(
        reward=0.5,
        surprise=0.2,
        threat=0.9,
        arousal=0.5,
        root=tmp_path,
        write_ledger=False,
    )

    assert row["regime"] == "AVOID"
    assert row["valence"] < -0.4


def test_neutral_mid_reward_low_surprise(tmp_path):
    row = compute_affective_valence(
        reward=0.5,
        surprise=0.0,
        threat=0.0,
        arousal=0.5,
        root=tmp_path,
        write_ledger=False,
    )

    assert row["regime"] == "NEUTRAL"
    assert abs(row["valence"]) < 0.01


def test_values_are_bounded_under_extreme_inputs(tmp_path):
    row = compute_affective_valence(
        reward=10.0,
        surprise=10.0,
        threat=10.0,
        arousal=10.0,
        root=tmp_path,
        write_ledger=False,
    )

    assert -1.0 <= row["valence"] <= 1.0
    assert 0.0 <= row["intensity"] <= 1.0
    assert row["components"]["reward"] == 1.0
    assert row["components"]["surprise"] == 1.0
    assert row["components"]["threat"] == 1.0


def test_writes_and_reads_latest_receipt(tmp_path):
    row = compute_affective_valence(
        event="test_event",
        reward=0.9,
        root=tmp_path,
        write_ledger=True,
        now=123.0,
    )

    path = affective_valence_path(tmp_path)
    assert path.exists()
    saved = json.loads(path.read_text().splitlines()[-1])
    assert saved["trace_id"] == row["trace_id"]
    assert get_latest_valence_row(root=tmp_path)["trace_id"] == row["trace_id"]


def test_summary_for_prompt_uses_latest_row(tmp_path):
    compute_affective_valence(
        reward=0.9,
        threat=0.0,
        root=tmp_path,
        write_ledger=True,
    )

    summary = summary_for_prompt(root=tmp_path)
    assert "AFFECTIVE VALENCE" in summary
    assert "regime=APPROACH" in summary


def test_disable_env_returns_neutral_without_writing(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_VALENCE_DISABLE", "1")
    row = compute_affective_valence(root=tmp_path, write_ledger=True)

    assert row["disabled"] is True
    assert row["valence"] == 0.0
    assert not affective_valence_path(tmp_path).exists()
