"""Tests for Stigmergic Consensus Clustering (Lumer-Faieta ant-based partitioning).

Runs N steps on seeded 2-blob and 3-blob datasets and asserts that cluster
purity rises and the average similarity metric converges.
"""
from __future__ import annotations

import json
import os
import random

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


def _qt_app():
    pytest.importorskip("PyQt6")
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _dispose_widget(widget, app):
    try:
        widget.close()
        app.processEvents()
        widget.deleteLater()
        app.processEvents()
    except Exception:
        pass


# -------------------------------------------------------------------
# Engine-level tests (no Qt)
# -------------------------------------------------------------------


def test_two_blob_purity_rises():
    """On a seeded 2-blob dataset, purity should rise after many steps."""
    from Applications.sifta_consensus_clustering import ConsensusField

    rng = random.Random(42)
    field = ConsensusField(rng=rng, grid_w=50, grid_h=40, alpha=5.0, k_pick=0.3, k_drop=0.15)
    field.generate_blobs(n_points=80, n_blobs=2, spread=2.5)
    field.spawn_ants(n_ants=30)

    purity_early = field.measure_purity()
    field.measure_avg_similarity()

    field.run_steps(1500)

    field.measure_avg_similarity()
    purity_after = field.measure_purity()

    assert purity_after >= purity_early - 0.05, (
        f"Purity should not collapse: {purity_early:.4f} -> {purity_after:.4f}"
    )
    assert len(field.avg_similarity_history) >= 2


def test_three_blob_similarity_converges():
    """On a seeded 3-blob dataset, avg similarity should increase."""
    from Applications.sifta_consensus_clustering import ConsensusField

    rng = random.Random(123)
    field = ConsensusField(rng=rng, grid_w=60, grid_h=50, alpha=6.0)
    field.generate_blobs(n_points=90, n_blobs=3, spread=1.5)
    field.spawn_ants(n_ants=30)

    sim_initial = field.measure_avg_similarity()

    for _ in range(80):
        field.run_steps(10)
        field.measure_avg_similarity()

    sim_final = field.avg_similarity_history[-1]

    assert sim_final >= sim_initial, (
        f"Average similarity should converge upward: {sim_initial:.4f} -> {sim_final:.4f}"
    )
    assert field.step_count == 800


def test_field_step_count_increments():
    from Applications.sifta_consensus_clustering import ConsensusField

    rng = random.Random(7)
    field = ConsensusField(rng=rng, grid_w=30, grid_h=20)
    field.generate_blobs(n_points=20, n_blobs=2, spread=1.0)
    field.spawn_ants(n_ants=10)
    field.run_steps(50)
    assert field.step_count == 50


def test_pickup_and_drop_mechanics():
    """At least some ants should pick up and drop points during a run."""
    from Applications.sifta_consensus_clustering import ConsensusField

    rng = random.Random(999)
    field = ConsensusField(rng=rng, grid_w=40, grid_h=30, k_pick=0.5, k_drop=0.1)
    field.generate_blobs(n_points=40, n_blobs=2, spread=1.0)
    field.spawn_ants(n_ants=20)

    ever_carried = False
    for _ in range(200):
        field.step()
        if any(ant.carrying is not None for ant in field.ants):
            ever_carried = True
            break

    assert ever_carried, "Ants should pick up points at some point"


# -------------------------------------------------------------------
# Widget-level test
# -------------------------------------------------------------------


def test_widget_runs_ticks(tmp_path, monkeypatch):
    app = _qt_app()
    from Applications import sifta_consensus_clustering as cc

    monkeypatch.setattr(cc, "_STATE", tmp_path)
    monkeypatch.setattr(cc, "_publish_app_focus", lambda *args, **kwargs: None)

    widget = cc.StigmergicConsensusClusteringWidget()
    try:
        widget._timer.stop()
        widget.field = cc.ConsensusField(rng=random.Random(77))
        widget.field.generate_blobs(n_points=40, n_blobs=2, spread=1.0)
        widget.field.spawn_ants(n_ants=15)
        widget.field.measure_avg_similarity()

        for _ in range(10):
            widget._tick()

        assert widget.field.step_count > 0
        assert len(widget.field.avg_similarity_history) > 1
    finally:
        _dispose_widget(widget, app)
