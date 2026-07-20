#!/usr/bin/env python3
"""Headless acceptance tests for Stigmergic Carpenter Pong V2."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from System.swarm_stigmergic_pong import (  # noqa: E402
    PADDLE_HALF_HEIGHT,
    PADDLE_SPEED,
    StigmergicPongSimulation,
)


REPO = Path(__file__).resolve().parents[1]


def test_swimmer_identities_are_unique_across_both_swarms() -> None:
    sim = StigmergicPongSimulation(seed=1625, swimmers_per_side=64)

    assert len(sim.all_swimmer_ids) == 128
    assert len(set(sim.all_swimmer_ids)) == 128
    assert sim.snapshot()["identity_unique"] is True


def test_same_seed_replays_the_same_field_and_ball() -> None:
    first = StigmergicPongSimulation(seed=91, swimmers_per_side=32)
    second = StigmergicPongSimulation(seed=91, swimmers_per_side=32)

    for _ in range(700):
        first.step()
        second.step()

    assert first.snapshot() == second.snapshot()


def test_paddle_actuator_uses_vote_average_only() -> None:
    sim = StigmergicPongSimulation(seed=3, swimmers_per_side=16)
    swarm = sim.left
    before = swarm.paddle_y

    sim.apply_vote_average(swarm, 0.5, 0.1)

    assert swarm.paddle_velocity == pytest.approx(0.5 * PADDLE_SPEED)
    assert swarm.paddle_y == pytest.approx(before + 0.5 * PADDLE_SPEED * 0.1)


def test_binary_vote_aggregate_matches_carpenter_rule() -> None:
    assert StigmergicPongSimulation.aggregate_votes([-1, -1, 1, 1]) == 0.0
    assert StigmergicPongSimulation.aggregate_votes([1, 1, 1, -1]) == 0.5
    assert StigmergicPongSimulation.aggregate_votes([-1, -1, -1, 1]) == -0.5


def test_pheromone_field_deposits_then_evaporates() -> None:
    sim = StigmergicPongSimulation(seed=11, swimmers_per_side=16)
    sim.step()
    deposited = sim.left.field_mass
    assert deposited > 0.0

    sim.left.swimmers = []
    for _ in range(12):
        sim._evaporate_and_diffuse(sim.left)

    assert sim.left.field_mass < deposited


def test_vote_digest_changes_and_is_not_claimed_as_signature() -> None:
    sim = StigmergicPongSimulation(seed=13, swimmers_per_side=16)
    before = sim.left.vote_digest
    sim.step()
    snapshot = sim.snapshot()

    assert snapshot["left"]["vote_digest"] != before
    assert "not a signature" in snapshot["digest_note"]


def test_swimmers_have_verified_ed25519_ballot_identities() -> None:
    sim = StigmergicPongSimulation(seed=13, swimmers_per_side=16, stgm_economy=False)
    sim.step()
    snapshot = sim.snapshot()

    assert all(len(swimmer.uid) == 16 for swimmer in sim.left.swimmers + sim.right.swimmers)
    assert all(len(swimmer.public_key_hex) == 64 for swimmer in sim.left.swimmers + sim.right.swimmers)
    assert snapshot["crypto"]["signature_algorithm"] == "Ed25519"
    assert snapshot["crypto"]["verified_ballots"] == 32
    assert snapshot["crypto"]["invalid_ballots"] == 0
    assert len(snapshot["crypto"]["checkpoint_digest"]) == 16


def test_chorus_advice_changes_each_swimmers_decision_input() -> None:
    sim = StigmergicPongSimulation(seed=17, swimmers_per_side=16, stgm_economy=False)
    sim.step()
    observations = sim.council_observations()
    assert len(observations["left"]) == 16
    assert len({row["id"] for row in observations["left"]}) == 16

    sim.apply_chorus_advice(
        left_target=0.15,
        left_confidence=0.9,
        right_target=0.85,
        right_confidence=0.8,
        model="test-local",
        estimated_prompt_tokens=1000,
    )
    sim.step()
    snapshot = sim.snapshot()
    assert snapshot["left"]["chorus"]["target_y"] == 0.15
    assert snapshot["right"]["chorus"]["target_y"] == 0.85
    assert snapshot["llm_microvote"]["calls"] == 1
    assert snapshot["llm_microvote"]["economy_effect"] == "telemetry_only_no_mint_no_spend"


def test_forced_miss_scores_and_resets_ball() -> None:
    sim = StigmergicPongSimulation(seed=17, swimmers_per_side=16)
    sim.left.paddle_y = 0.8
    sim.ball.x = 0.08
    sim.ball.y = PADDLE_HALF_HEIGHT
    sim.ball.vx = -0.6
    sim.ball.vy = 0.0

    events = sim.step(0.05)

    assert events and events[0]["event"] == "goal"
    assert events[0]["scorer"] == "right"
    assert sim.right_score == 1
    assert sim.ball.x == 0.5


def test_default_match_scores_autonomously() -> None:
    sim = StigmergicPongSimulation(seed=1625, swimmers_per_side=64)
    events = []
    for _ in range(1500):
        events.extend(sim.step())
        if events:
            break

    assert events
    assert sum(sim.snapshot()["score"]) >= 1
    assert sim.longest_rally >= 1


def test_snapshot_has_vote_field_and_score_receipts() -> None:
    sim = StigmergicPongSimulation(seed=19, swimmers_per_side=24)
    for _ in range(20):
        sim.step()
    snapshot = sim.snapshot()

    assert snapshot["truth_label"] == "STIGMERGIC_CARPENTER_PONG_V3"
    assert snapshot["left"]["swimmers"] == 24
    assert set(snapshot["left"]["votes"]) == {"up", "down", "neutral"}
    assert 0.0 <= snapshot["left"]["field_entropy"] <= 1.0


def test_manifest_registers_game_category() -> None:
    manifest = json.loads((REPO / "Applications" / "apps_manifest.json").read_text(encoding="utf-8"))
    row = manifest["Stigmergic Carpenter Pong"]

    assert row["category"] == "Games"
    assert row["entry_point"] == "Applications/sifta_stigmergic_pong.py"
    assert row["widget_class"] == "StigmergicCarpenterPongWidget"


def test_widget_renders_offscreen_and_runs_steps(tmp_path, monkeypatch) -> None:
    from PyQt6.QtWidgets import QApplication
    from Applications import sifta_stigmergic_pong as app_module

    monkeypatch.setattr(app_module, "_STATE", tmp_path)
    monkeypatch.setattr(app_module, "_focus", lambda *_args, **_kwargs: None)
    app = QApplication.instance() or QApplication([])
    widget = app_module.StigmergicPongWidget()
    try:
        widget.timer.stop()
        before = widget.sim.tick
        widget._advance(4)
        widget.resize(900, 680)
        widget.show()
        app.processEvents()
        pixmap = widget.grab()

        assert widget.sim.tick == before + 4
        assert not pixmap.isNull()
        assert pixmap.width() > 0 and pixmap.height() > 0
        assert (tmp_path / "carpenter_pong_receipts.jsonl").exists()
    finally:
        widget.close()
        app.processEvents()
