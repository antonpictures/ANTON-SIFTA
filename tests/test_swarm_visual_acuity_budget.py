from System.swarm_gesture_decoder import _centroid_and_mass, _decode_saliency_q
from System.swarm_visual_acuity_budget import (
    BASE_SWIMMER_COUNT,
    BASE_SWIMMER_GRID,
    DEFAULT_MAX_ACUITY,
    build_visual_acuity_budget,
    clamp_acuity,
    configured_default_acuity,
    configured_max_acuity,
    infer_square_grid_side,
    swimmer_budget_for_acuity,
)


def test_default_eye_acuity_is_32_and_max_is_64(monkeypatch):
    monkeypatch.delenv("SIFTA_ALICE_EYE_DEFAULT_ACUITY", raising=False)
    monkeypatch.delenv("SIFTA_ALICE_EYE_MAX_ACUITY", raising=False)

    assert configured_default_acuity() == 32
    assert configured_max_acuity() == DEFAULT_MAX_ACUITY == 64


def test_64x64_budget_sends_four_times_base_swimmers(monkeypatch):
    monkeypatch.delenv("SIFTA_VISION_SWIMMERS", raising=False)

    budget = build_visual_acuity_budget(64)

    assert budget.grid_size == 64
    assert budget.total_cells == 4096
    assert budget.source_thumb_px == 512
    assert budget.swimmer_budget == BASE_SWIMMER_COUNT * 4
    assert budget.swimmer_scale == round((64 / BASE_SWIMMER_GRID) ** 2, 6)


def test_acuity_clamp_respects_runtime_ceiling(monkeypatch):
    monkeypatch.setenv("SIFTA_ALICE_EYE_MAX_ACUITY", "48")

    assert configured_max_acuity() == 48
    assert clamp_acuity(96) == 48
    assert build_visual_acuity_budget(64).grid_size == 48


def test_swimmer_floor_can_be_raised_by_env(monkeypatch):
    monkeypatch.setenv("SIFTA_VISION_SWIMMERS", "9000")

    assert swimmer_budget_for_acuity(32) == 9000
    assert swimmer_budget_for_acuity(64) == 9000


def test_square_grid_inference_supports_new_64x64_ledger_rows():
    assert infer_square_grid_side("f" * 256) == 16
    assert infer_square_grid_side("f" * 1024) == 32
    assert infer_square_grid_side("f" * 4096) == 64
    assert infer_square_grid_side("f" * 4095) is None


def test_gesture_decoder_accepts_64x64_visual_grid():
    q = ["0"] * (64 * 64)
    q[(31 * 64) + 63] = "f"
    grid = _decode_saliency_q("".join(q))

    assert grid is not None
    assert len(grid) == 64
    cx, cy, mass = _centroid_and_mass(grid)
    assert cx == 1.0
    assert -0.03 < cy < 0.03
    assert mass == 15.0
