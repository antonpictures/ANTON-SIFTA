"""Pixel-proof tests for the SIFTA optic nerve.

Falsifiable invariants:
  1. Standalone GL context creates without error.
  2. High drive produces brighter pixels than low drive.
  3. Clamp functions block out-of-range / NaN / negative inputs.
  4. VisualPhenotypeUniformTail degrades cleanly on missing ledger.
  5. Shader compiles with no GLSL syntax errors.
"""
from __future__ import annotations

import json
import math

# Helpers


def _low_drive() -> dict:
    return {
        "u_stigmergic_drive":    0.05,
        "u_metabolic_scope":     0.3,
        "u_cot_factor":          0.9,
        "u_quorum_signal":       0.05,
        "u_chemotaxis_gradient": 0.02,
    }


def _high_drive() -> dict:
    return {
        "u_stigmergic_drive":    0.95,
        "u_metabolic_scope":     1.8,
        "u_cot_factor":          0.02,
        "u_quorum_signal":       0.9,
        "u_chemotaxis_gradient": 0.8,
    }


# Context probe


def test_standalone_context_available() -> None:
    """OpenGL 4.1 standalone context must be available on this node."""
    from System.swarm_visual_phenotype_gl import try_create_standalone_context
    probe = try_create_standalone_context()
    assert probe.ok, f"Standalone GL unavailable: {probe.status}"


# Shader compile


def test_chromatophore_shader_compiles() -> None:
    """Covenant-grade GLSL must compile without error on the local GPU."""
    import moderngl
    from System.swarm_visual_phenotype_gl import (
        CHROMATOPHORE_FRAGMENT_SRC,
        CHROMATOPHORE_VERTEX_SRC,
    )
    ctx = moderngl.create_standalone_context()
    try:
        prog = ctx.program(
            vertex_shader=CHROMATOPHORE_VERTEX_SRC,
            fragment_shader=CHROMATOPHORE_FRAGMENT_SRC,
        )
        assert prog is not None
    finally:
        ctx.release()


# Pixel invariant


def test_high_drive_brighter_than_low_drive() -> None:
    """
    Core falsifiable claim:
    High biological drive yields higher mean pixel brightness.
    """
    from System.swarm_visual_phenotype_gl import mean_brightness
    lo = mean_brightness(_low_drive(),  width=128, height=128)
    hi = mean_brightness(_high_drive(), width=128, height=128)
    assert hi > lo, (
        f"FAIL: high-drive brightness ({hi:.2f}) must exceed "
        f"low-drive ({lo:.2f}). Phenotype glow is not responding to ledger input."
    )


def test_zero_drive_does_not_produce_white() -> None:
    """Resting state should not produce a saturated/white frame."""
    from System.swarm_visual_phenotype_gl import mean_brightness
    zero = {"u_stigmergic_drive": 0.0, "u_metabolic_scope": 0.0,
            "u_cot_factor": 0.0, "u_quorum_signal": 0.0, "u_chemotaxis_gradient": 0.0}
    b = mean_brightness(zero, width=128, height=128)
    assert b < 200, f"Zero drive should be dark, got {b:.2f}"


# Clamp discipline


def test_clamp_uniforms_handles_nan_and_negative() -> None:
    from System.swarm_visual_phenotype_gl import clamp_uniforms
    bad_row = {
        "u_reward":           float("nan"),
        "u_stigmergic_drive": -5.0,
        "u_metabolic_scope":  999.0,
        "u_cot_factor":       -1.0,
        "u_quorum_signal":    2.0,
    }
    out = clamp_uniforms(bad_row)
    assert math.isfinite(out["u_reward"]),        "NaN reward leaked"
    assert out["u_stigmergic_drive"] >= 0.0,       "Negative drive leaked"
    assert out["u_metabolic_scope"]  <= 2.0,       "Scope overflow leaked"
    assert out["u_cot_factor"]       >= 0.0,       "Negative COT leaked"
    assert 0.0 <= out["u_quorum_signal"] <= 1.0,   "Quorum OOB leaked"


# Uniform tail


def test_uniform_tail_degrades_on_missing_ledger(tmp_path) -> None:
    from System.swarm_visual_phenotype_gl import (
        UNIFORM_DEFAULTS,
        VisualPhenotypeUniformTail,
    )
    tail = VisualPhenotypeUniformTail(tmp_path / "does_not_exist.jsonl")
    frame = tail.read_frame()
    # Should return zeros/defaults and not crash.
    assert isinstance(frame.uniforms, dict)
    assert not frame.receipt_backed
    for key in UNIFORM_DEFAULTS:
        assert key in frame.uniforms


def test_uniform_tail_reads_real_row(tmp_path) -> None:
    from System.swarm_visual_phenotype_gl import VisualPhenotypeUniformTail
    ledger = tmp_path / "test_phenotype.jsonl"
    row = {
        "u_reward": 0.77, "u_distance": 0.3, "u_confidence": 0.9,
        "u_cost": 0.1, "u_heading": 1.57, "u_stigmergic_drive": 0.77,
        "u_metabolic_scope": 1.5, "u_cot_factor": 0.1, "u_quorum_signal": 0.9,
        "u_chemotaxis_gradient": 0.6,
        "receipt_backed": True, "tick_id": "abc-123", "ts": 1777000000.0,
    }
    ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")
    tail = VisualPhenotypeUniformTail(ledger)
    frame = tail.read_frame()
    assert frame.receipt_backed is True
    assert frame.tick_id == "abc-123"
    assert abs(frame.uniforms["u_stigmergic_drive"] - 0.77) < 0.01


# Summary string


def test_summarize_uniform_frame(tmp_path) -> None:
    from System.swarm_visual_phenotype_gl import (
        VisualPhenotypeUniformTail,
        summarize_uniform_frame,
    )
    tail  = VisualPhenotypeUniformTail(tmp_path / "empty.jsonl")
    frame = tail.read_frame()
    s     = summarize_uniform_frame(frame)
    assert "receipt" in s or "no receipt" in s
