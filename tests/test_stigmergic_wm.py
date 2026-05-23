from __future__ import annotations

from System import stigmergic_wm


def test_suggest_position_first_window_has_inset(monkeypatch):
    monkeypatch.setattr(stigmergic_wm, "neighbors", lambda *_args, **_kwargs: [])

    assert stigmergic_wm.suggest_position("Alice", {}) == (60, 40)


def test_suggest_position_cascades_from_last_open_window(monkeypatch):
    monkeypatch.setattr(stigmergic_wm, "neighbors", lambda *_args, **_kwargs: [])
    open_windows = {
        "Alice": (60, 40),
        "Conversation History": (120, 80),
    }

    assert stigmergic_wm.suggest_position("Stigmergic Library", open_windows) == (180, 120)


def test_suggest_position_wraps_cascade_inside_mdi(monkeypatch):
    monkeypatch.setattr(stigmergic_wm, "neighbors", lambda *_args, **_kwargs: [])
    open_windows = {"Last App": (900, 600)}

    assert stigmergic_wm.suggest_position(
        "Next App",
        open_windows,
        mdi_w=1000,
        mdi_h=700,
        win_w=300,
        win_h=260,
    ) == (60, 40)


def test_suggest_position_clamps_pheromone_neighbor_inside_mdi(monkeypatch):
    monkeypatch.setattr(
        stigmergic_wm,
        "neighbors",
        lambda *_args, **_kwargs: [("Alice", 9.0)],
    )

    assert stigmergic_wm.suggest_position(
        "Conversation History",
        {"Alice": (760, 500)},
        mdi_w=900,
        mdi_h=700,
        win_w=300,
        win_h=300,
    ) == (600, 400)


def test_suggest_position_does_not_reuse_occupied_pheromone_slot(monkeypatch):
    monkeypatch.setattr(
        stigmergic_wm,
        "neighbors",
        lambda *_args, **_kwargs: [("Alice", 9.0)],
    )
    open_windows = {
        "Alice": (60, 40),
        "Conversation History": (90, 70),
    }

    assert stigmergic_wm.suggest_position(
        "Stigmergic Library",
        open_windows,
        mdi_w=1000,
        mdi_h=700,
        win_w=300,
        win_h=260,
    ) == (150, 110)
