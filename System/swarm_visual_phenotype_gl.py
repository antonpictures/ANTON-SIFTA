#!/usr/bin/env python3
"""ModernGL optic-nerve pass for SIFTA visual phenotype uniforms.

This module is the live bridge from `.sifta_state/visual_phenotype_uniforms.jsonl`
to GPU shader uniforms. It is intentionally narrow:

- tail the latest receipt-backed phenotype row once per frame
- clamp and type the uniform payload defensively
- compile the archived honeybee waggle GLSL fragment into a full-screen pass
- degrade truthfully when ModernGL/offscreen context creation is unavailable

Truth label: MODERNGL_PASS_READY. A row becomes a live visual claim only when it
comes from `visual_phenotype_uniforms.jsonl` with `receipt_backed: true`.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
DEFAULT_LEDGER = _STATE_DIR / "visual_phenotype_uniforms.jsonl"
DEFAULT_SHADER = _REPO / "Archive" / "bishop_drops_pending_review" / "BISHOP_drop_honeybee_waggle_router_v1.novel"

TRUTH_LABEL = "MODERNGL_PASS_READY"

FULLSCREEN_VERTEX_SHADER = """#version 410 core
in vec2 in_pos;
void main() {
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

UNIFORM_DEFAULTS: Dict[str, float] = {
    "u_reward": 0.0,
    "u_distance": 0.0,
    "u_confidence": 0.0,
    "u_cost": 0.0,
    "u_heading": 0.0,
    "u_stigmergic_drive": 0.0,
    "u_metabolic_scope": 0.0,
    "u_cot_factor": 0.0,
    "u_quorum_signal": 0.0,
    "u_chemotaxis_gradient": 0.1,
}

CLAMP_01_KEYS = {
    "u_reward",
    "u_distance",
    "u_confidence",
    "u_cost",
    "u_stigmergic_drive",
    "u_quorum_signal",
    "u_chemotaxis_gradient",
}


@dataclass(frozen=True)
class UniformFrame:
    """One typed visual phenotype frame pulled from the JSONL ledger."""

    uniforms: Dict[str, float]
    source_path: str
    tick_id: str
    receipt_backed: bool
    row_ts: float
    pulled_ts: float
    truth_label: str = TRUTH_LABEL


@dataclass(frozen=True)
class ContextProbe:
    ok: bool
    status: str
    backend: str = ""


def _clamp(value: Any, low: float, high: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return max(low, min(high, number))


def clamp_uniforms(row: Dict[str, Any]) -> Dict[str, float]:
    """Return shader-safe scalar uniforms from a raw phenotype row."""

    out: Dict[str, float] = {}
    for key, default in UNIFORM_DEFAULTS.items():
        value = row.get(key, default)
        if key in CLAMP_01_KEYS:
            out[key] = _clamp(value, 0.0, 1.0, default)
        elif key == "u_metabolic_scope":
            out[key] = _clamp(value, 0.0, 2.0, default)
        elif key == "u_cot_factor":
            out[key] = _clamp(value, 0.0, 10.0, default)
        elif key == "u_heading":
            out[key] = _clamp(value, -math.tau, math.tau, default)
        else:
            out[key] = _clamp(value, -10.0, 10.0, default)
    return out


def read_last_jsonl_row(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            return row
    return {}


class VisualPhenotypeUniformTail:
    """Per-frame reader for `.sifta_state/visual_phenotype_uniforms.jsonl`."""

    def __init__(self, ledger_path: Path | str = DEFAULT_LEDGER) -> None:
        self.ledger_path = Path(ledger_path)
        self._last_size = -1
        self._last_mtime_ns = -1
        self._cached: Optional[UniformFrame] = None

    def read_frame(self, *, force: bool = False) -> UniformFrame:
        row: Dict[str, Any]
        try:
            stat = self.ledger_path.stat()
            size = stat.st_size
            mtime_ns = stat.st_mtime_ns
        except OSError:
            size = -1
            mtime_ns = -1

        if not force and self._cached is not None and size == self._last_size and mtime_ns == self._last_mtime_ns:
            return self._cached

        row = read_last_jsonl_row(self.ledger_path)
        frame = UniformFrame(
            uniforms=clamp_uniforms(row),
            source_path=str(self.ledger_path),
            tick_id=str(row.get("tick_id") or ""),
            receipt_backed=bool(row.get("receipt_backed") is True),
            row_ts=_clamp(row.get("ts"), 0.0, 10_000_000_000.0, 0.0),
            pulled_ts=time.time(),
        )
        self._cached = frame
        self._last_size = size
        self._last_mtime_ns = mtime_ns
        return frame


def load_honeybee_fragment(shader_path: Path | str = DEFAULT_SHADER) -> str:
    path = Path(shader_path)
    return path.read_text(encoding="utf-8")


def modern_gl_available() -> bool:
    try:
        import moderngl  # noqa: F401
    except Exception:
        return False
    return True


def try_create_standalone_context() -> ContextProbe:
    """Try to create a real standalone ModernGL context without throwing."""

    try:
        import moderngl
    except Exception as exc:
        return ContextProbe(False, f"moderngl_import_failed:{type(exc).__name__}")

    for backend in ("egl", "osmesa", ""):
        try:
            if backend:
                ctx = moderngl.create_standalone_context(backend=backend)
            else:
                ctx = moderngl.create_standalone_context()
            try:
                ctx.release()
            except Exception:
                pass
            return ContextProbe(True, "standalone_context_created", backend=backend or "default")
        except Exception:
            continue
    return ContextProbe(False, "standalone_context_unavailable")


class VisualPhenotypeModernGLPass:
    """Full-screen ModernGL pass fed by receipt-backed visual phenotype rows."""

    def __init__(
        self,
        ctx: Any,
        *,
        ledger_path: Path | str = DEFAULT_LEDGER,
        shader_path: Path | str = DEFAULT_SHADER,
        resolution: tuple[int, int] = (640, 360),
    ) -> None:
        self.ctx = ctx
        self.tail = VisualPhenotypeUniformTail(ledger_path)
        self.shader_path = Path(shader_path)
        self.resolution = resolution
        self.program: Any = None
        self.vbo: Any = None
        self.vao: Any = None
        self._moderngl: Any = None

    def compile(self) -> None:
        import moderngl

        self._moderngl = moderngl
        fragment = load_honeybee_fragment(self.shader_path)
        self.program = self.ctx.program(
            vertex_shader=FULLSCREEN_VERTEX_SHADER,
            fragment_shader=fragment,
        )
        self.vbo = self.ctx.buffer(
            b"\x00\x00\x80\xbf\x00\x00\x80\xbf"
            b"\x00\x00\x40\x40\x00\x00\x80\xbf"
            b"\x00\x00\x80\xbf\x00\x00\x40\x40"
        )
        self.vao = self.ctx.vertex_array(self.program, [(self.vbo, "2f", "in_pos")])

    def _set_uniform(self, name: str, value: Any) -> None:
        if self.program is None:
            return
        try:
            uniform = self.program[name]
        except Exception:
            return
        try:
            uniform.value = value
        except Exception:
            pass

    def apply_uniform_frame(self, frame: UniformFrame, *, elapsed: float = 0.0) -> None:
        width, height = self.resolution
        self._set_uniform("u_resolution", (float(width), float(height)))
        self._set_uniform("u_time", float(elapsed))
        for name, value in frame.uniforms.items():
            self._set_uniform(name, float(value))

    def render_frame(self, *, elapsed: Optional[float] = None, force_pull: bool = False) -> UniformFrame:
        if self.program is None or self.vao is None:
            self.compile()
        frame = self.tail.read_frame(force=force_pull)
        self.apply_uniform_frame(frame, elapsed=time.time() if elapsed is None else elapsed)
        if self._moderngl is not None:
            self.vao.render(self._moderngl.TRIANGLES)
        else:
            self.vao.render()
        return frame


def summarize_uniform_frame(frame: UniformFrame) -> str:
    flag = "receipt" if frame.receipt_backed else "no receipt"
    u = frame.uniforms
    return (
        f"{flag} tick={frame.tick_id or '-'} "
        f"reward={u['u_reward']:.2f} cost={u['u_cost']:.2f} "
        f"confidence={u['u_confidence']:.2f} heading={u['u_heading']:.2f}"
    )


__all__ = [
    "ContextProbe",
    "DEFAULT_LEDGER",
    "DEFAULT_SHADER",
    "FULLSCREEN_VERTEX_SHADER",
    "TRUTH_LABEL",
    "UniformFrame",
    "VisualPhenotypeModernGLPass",
    "VisualPhenotypeUniformTail",
    "clamp_uniforms",
    "load_honeybee_fragment",
    "modern_gl_available",
    "read_last_jsonl_row",
    "summarize_uniform_frame",
    "try_create_standalone_context",
]
