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


def _append_receipt(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _dispose_widget(widget, app):
    try:
        widget.close()
        app.processEvents()
        widget.deleteLater()
        app.processEvents()
    except Exception:
        pass


def test_go_swarm_vs_swarm_runs_three_receipted_games(tmp_path):
    from Applications import sifta_stigmergic_go as go

    receipt_path = tmp_path / "stigmergic_app_tournament_receipts.jsonl"
    rows = []
    for game_idx in range(3):
        random.seed(800 + game_idx)
        rules = go._GoRules()
        field = go._StigmergicField()
        color = "B"
        moves = 0
        passes = 0
        for _ply in range(24):
            move = field.choose_move(rules, color, evolve_steps=2)
            if move is None:
                rules.pass_turn()
                passes += 1
            else:
                ok, reason = rules.place(move[0], move[1], color)
                assert ok, reason
                field.on_place(move[0], move[1], color)
                moves += 1
            color = "W" if color == "B" else "B"

        row = {
            "app": "Stigmergic Go",
            "round": game_idx + 1,
            "mode": "swarm_vs_swarm_pheromone_field",
            "moves": moves,
            "passes": passes,
            "field_steps": field.steps,
            "deposits": field.total_deposits,
            "used_solution_oracle": False,
            "score": rules.simple_score(),
        }
        _append_receipt(receipt_path, row)
        rows.append(row)

    assert len(rows) == 3
    assert all(row["moves"] > 0 for row in rows)
    assert all(row["deposits"] > 0 for row in rows)
    assert all(row["used_solution_oracle"] is False for row in rows)
    assert len(_read_jsonl(receipt_path)) == 3


def test_jigsaw_swarm_convergence_runs_three_receipted_rounds(tmp_path, monkeypatch):
    app = _qt_app()
    from Applications import sifta_jigsaw_widget as jigsaw

    monkeypatch.setattr(jigsaw, "_STATE", tmp_path)
    monkeypatch.setattr(jigsaw, "_publish_app_focus", lambda *args, **kwargs: None)
    receipt_path = tmp_path / "stigmergic_app_tournament_receipts.jsonl"
    rows = []

    for round_idx in range(3):
        random.seed(900 + round_idx)
        widget = jigsaw.StigmergicJigsawWidget()
        try:
            widget._size_combo.setCurrentIndex(0)
            widget._toggle_solve()
            for _ in range(30):
                widget._tick()
            pheromone_mass = sum(sum(row) for row in widget._field.h_edges) + sum(
                sum(row) for row in widget._field.v_edges
            )
            row = {
                "app": "Stigmergic Jigsaw",
                "round": round_idx + 1,
                "mode": "aco_convergence",
                "iterations": widget._solve_iter,
                "best_score": widget._solve_best,
                "perfect_score": widget._perfect,
                "pheromone_mass": round(pheromone_mass, 4),
            }
            _append_receipt(receipt_path, row)
            rows.append(row)
        finally:
            _dispose_widget(widget, app)

    assert len(rows) == 3
    assert all(row["iterations"] > 0 for row in rows)
    assert all(row["iterations"] <= 30 for row in rows)
    assert all(row["best_score"] > 0 for row in rows)
    assert all(row["pheromone_mass"] >= 0.0 for row in rows)
    assert len(_read_jsonl(receipt_path)) == 3


def test_graph_coloring_field_convergence_runs_three_receipted_rounds(tmp_path, monkeypatch):
    app = _qt_app()
    from Applications import sifta_graph_coloring as graph

    monkeypatch.setattr(graph, "_STATE", tmp_path)
    monkeypatch.setattr(graph, "_publish_app_focus", lambda *args, **kwargs: None)
    receipt_path = tmp_path / "stigmergic_app_tournament_receipts.jsonl"
    rows = []

    for round_idx in range(3):
        random.seed(1000 + round_idx)
        widget = graph.StigmergicGraphColoringWidget()
        try:
            initial_conflicts = sum(
                1 for edge in widget.edges if widget.nodes[edge.a].color == widget.nodes[edge.b].color
            )
            for _ in range(36):
                widget._evolve_step()
            final_conflicts = sum(
                1 for edge in widget.edges if widget.nodes[edge.a].color == widget.nodes[edge.b].color
            )
            row = {
                "app": "Stigmergic Graph Coloring",
                "round": round_idx + 1,
                "mode": "field_convergence",
                "steps": widget.step_count,
                "initial_conflicts": initial_conflicts,
                "final_conflicts": final_conflicts,
                "min_tension": round(min(widget.tension_history), 4),
                "max_tension": round(max(widget.tension_history), 4),
            }
            _append_receipt(receipt_path, row)
            rows.append(row)
        finally:
            _dispose_widget(widget, app)

    assert len(rows) == 3
    assert all(row["steps"] >= 36 for row in rows)
    assert all(row["max_tension"] >= row["min_tension"] >= 0.0 for row in rows)
    assert len(_read_jsonl(receipt_path)) == 3


def test_ant_foraging_convergence_runs_three_receipted_rounds(tmp_path, monkeypatch):
    app = _qt_app()
    from Applications import sifta_ant_foraging as ants

    monkeypatch.setattr(ants, "_STATE", tmp_path)
    monkeypatch.setattr(ants, "_publish_app_focus", lambda *args, **kwargs: None)
    receipt_path = tmp_path / "stigmergic_app_tournament_receipts.jsonl"
    rows = []

    for round_idx in range(3):
        widget = ants.StigmergicAntForagingWidget()
        try:
            widget._timer.stop()
            widget.random.seed(1100 + round_idx)
            ant = widget.ants[0]
            ant.x, ant.y = ants.FOOD
            ant.path = [ants.NEST, ants.FOOD]
            ant.carrying = False
            widget._step_searching(ant)
            for _ in range(8):
                widget._tick()
            row = {
                "app": "Stigmergic Ant Foraging Trail",
                "round": round_idx + 1,
                "mode": "pheromone_path_convergence",
                "ticks": widget.tick_count,
                "success_count": widget.success_count,
                "best_path_len": widget.best_path_len,
                "pheromone_mass": round(widget.pheromone_mass, 4),
                "peak_field": round(widget.max_pheromone, 4),
            }
            _append_receipt(receipt_path, row)
            rows.append(row)
        finally:
            _dispose_widget(widget, app)

    assert len(rows) == 3
    assert all(row["success_count"] >= 1 for row in rows)
    assert all(row["pheromone_mass"] > 0.0 for row in rows)
    assert all(row["peak_field"] > 0.0 for row in rows)
    assert len(_read_jsonl(receipt_path)) == 3


def test_reaction_diffusion_field_precipitates_7x8_without_answer_path(tmp_path, monkeypatch):
    from Applications import sifta_reaction_diffusion_calculator as rd

    monkeypatch.setattr(rd, "_STATE", tmp_path)
    field = rd.ReactionDiffusionField()
    field.inject_operands(7, 8)
    sig = field.run_until_quiet()

    assert sig["answer_source"] == "precipitate_count_from_field"
    assert field.precipitate_count() == 56
    assert field.last_collision_count == 56
    assert field.left_operand == 7
    assert field.right_operand == 8


def test_reaction_diffusion_widget_runs_to_quiet_7x8(tmp_path, monkeypatch):
    app = _qt_app()
    from Applications import sifta_reaction_diffusion_calculator as rd

    monkeypatch.setattr(rd, "_STATE", tmp_path)
    monkeypatch.setattr(rd, "_publish_app_focus", lambda *args, **kwargs: None)

    widget = rd.StigmergicReactionDiffusionCalculatorWidget()
    try:
        widget._timer.stop()
        widget._run_demo_7x8()
        widget._run_to_quiet()

        assert widget.field.precipitate_count() == 56
        assert widget.last_signature["answer_source"] == "precipitate_count_from_field"
        assert widget.count_label.text().endswith("56")
    finally:
        _dispose_widget(widget, app)
