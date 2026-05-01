"""Tests for ModernGL visual phenotype optic-nerve pass."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System.swarm_visual_phenotype_gl import (
    DEFAULT_SHADER,
    TRUTH_LABEL,
    VisualPhenotypeModernGLPass,
    VisualPhenotypeUniformTail,
    clamp_uniforms,
    load_honeybee_fragment,
    summarize_uniform_frame,
    try_create_standalone_context,
)


class _FakeUniform:
    def __init__(self) -> None:
        self.value = None


class _FakeProgram:
    def __init__(self) -> None:
        self.uniforms = {name: _FakeUniform() for name in [
            "u_resolution",
            "u_time",
            "u_reward",
            "u_distance",
            "u_confidence",
            "u_cost",
            "u_heading",
            "u_stigmergic_drive",
            "u_metabolic_scope",
            "u_cot_factor",
            "u_quorum_signal",
            "u_chemotaxis_gradient",
        ]}

    def __getitem__(self, name: str) -> _FakeUniform:
        return self.uniforms[name]


class _FakeVertexArray:
    def __init__(self) -> None:
        self.render_calls = 0

    def render(self, *_args, **_kwargs) -> None:
        self.render_calls += 1


class _FakeContext:
    def __init__(self) -> None:
        self.program_obj = _FakeProgram()
        self.vao_obj = _FakeVertexArray()
        self.vertex_shader = ""
        self.fragment_shader = ""

    def program(self, *, vertex_shader: str, fragment_shader: str) -> _FakeProgram:
        self.vertex_shader = vertex_shader
        self.fragment_shader = fragment_shader
        return self.program_obj

    def buffer(self, data: bytes) -> bytes:
        return data

    def vertex_array(self, program: _FakeProgram, content):
        assert program is self.program_obj
        assert content[0][2] == "in_pos"
        return self.vao_obj


def _append_jsonl(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_clamp_uniforms_defends_shader_from_bad_ledger_values() -> None:
    uniforms = clamp_uniforms({
        "u_reward": 2.5,
        "u_distance": -1.0,
        "u_confidence": float("nan"),
        "u_cost": 7.0,
        "u_heading": 99.0,
        "u_metabolic_scope": 5.0,
        "u_cot_factor": -3.0,
    })

    assert uniforms["u_reward"] == 1.0
    assert uniforms["u_distance"] == 0.0
    assert uniforms["u_confidence"] == 0.0
    assert uniforms["u_cost"] == 1.0
    assert uniforms["u_metabolic_scope"] == 2.0
    assert uniforms["u_cot_factor"] == 0.0
    assert uniforms["u_heading"] <= 6.28319


def test_uniform_tail_reads_latest_jsonl_row_per_frame(tmp_path: Path) -> None:
    ledger = tmp_path / "visual_phenotype_uniforms.jsonl"
    _append_jsonl(ledger, {"tick_id": "old", "receipt_backed": True, "u_reward": 0.1})
    _append_jsonl(ledger, {"tick_id": "new", "receipt_backed": True, "u_reward": 0.8, "u_cost": 0.2})

    tail = VisualPhenotypeUniformTail(ledger)
    frame = tail.read_frame()

    assert frame.truth_label == TRUTH_LABEL
    assert frame.tick_id == "new"
    assert frame.receipt_backed is True
    assert frame.uniforms["u_reward"] == 0.8
    assert "reward=0.80" in summarize_uniform_frame(frame)


def test_modern_gl_pass_compiles_fragment_and_applies_uniforms_with_fake_context(tmp_path: Path) -> None:
    ledger = tmp_path / "visual_phenotype_uniforms.jsonl"
    _append_jsonl(
        ledger,
        {
            "tick_id": "tick-1",
            "receipt_backed": True,
            "u_reward": 0.66,
            "u_distance": 0.25,
            "u_confidence": 0.9,
            "u_cost": 0.1,
            "u_heading": 1.25,
        },
    )
    ctx = _FakeContext()
    pass_ = VisualPhenotypeModernGLPass(ctx, ledger_path=ledger, resolution=(320, 180))

    frame = pass_.render_frame(elapsed=4.0, force_pull=True)

    assert frame.tick_id == "tick-1"
    assert "#version 410 core" in ctx.vertex_shader
    assert "Honeybee Waggle Router" in ctx.fragment_shader
    assert ctx.program_obj.uniforms["u_resolution"].value == (320.0, 180.0)
    assert ctx.program_obj.uniforms["u_time"].value == 4.0
    assert ctx.program_obj.uniforms["u_reward"].value == 0.66
    assert ctx.program_obj.uniforms["u_confidence"].value == 0.9
    assert ctx.vao_obj.render_calls == 1


def test_honeybee_shader_archive_is_loadable() -> None:
    fragment = load_honeybee_fragment(DEFAULT_SHADER)
    assert "#version 410 core" in fragment
    assert "u_reward" in fragment
    assert "fragColor" in fragment


def test_standalone_context_probe_is_truthful_not_fatal() -> None:
    probe = try_create_standalone_context()
    assert isinstance(probe.ok, bool)
    assert probe.status


def test_real_modern_gl_standalone_context_renders_when_available(tmp_path: Path) -> None:
    try:
        import moderngl

        ctx = moderngl.create_standalone_context()
    except Exception as exc:
        pytest.skip(f"standalone ModernGL context unavailable: {exc}")

    ledger = tmp_path / "visual_phenotype_uniforms.jsonl"
    _append_jsonl(
        ledger,
        {
            "tick_id": "real-gl",
            "receipt_backed": True,
            "u_reward": 0.7,
            "u_distance": 0.2,
            "u_confidence": 0.8,
            "u_cost": 0.1,
            "u_heading": 0.5,
        },
    )
    try:
        pass_ = VisualPhenotypeModernGLPass(ctx, ledger_path=ledger, resolution=(32, 32))
        frame = pass_.render_frame(elapsed=0.1, force_pull=True)
        assert frame.tick_id == "real-gl"
        assert frame.receipt_backed is True
    finally:
        try:
            ctx.release()
        except Exception:
            pass
