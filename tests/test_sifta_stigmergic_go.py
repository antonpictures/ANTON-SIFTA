import inspect
import random

from Applications import sifta_stigmergic_go as go


def test_go_legal_move_probe_does_not_mutate_board():
    rules = go._GoRules()
    rules.board[0][1] = "W"
    rules.board[1][0] = "W"
    rules.board[1][1] = "B"
    before = [row[:] for row in rules.board]

    legal = rules.legal_moves("B")

    assert legal
    assert rules.board == before


def test_swarm_field_selects_legal_opponent_move_without_oracle():
    random.seed(9)
    rules = go._GoRules()
    field = go._StigmergicField()
    ok, reason = rules.place(3, 3, "B")
    assert ok, reason
    field.on_place(3, 3, "B")

    move = field.choose_move(rules, "W", evolve_steps=4)

    assert move is not None
    assert field.last_selection["selection"] == "pheromone_weighted_swimmer_field"
    assert rules.move_features(move[0], move[1], "W")["legal"]
    assert not any("solution" in key.lower() for key in field.last_selection)


def test_go_widget_contains_real_swarm_opponent_path():
    source = inspect.getsource(go.StigmergicGoWidget)

    assert "You Black vs Swarm White" in source
    assert "swarm_opponent_move" in source
    assert "choose_move(self.rules, color" in source
    assert "used_solution_oracle" in source
