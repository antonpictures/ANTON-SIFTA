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
DEFAULT_PHEROMONE_FIELD = _STATE_DIR / "pheromone_field.json"
DEFAULT_SHADER = _REPO / "Archive" / "bishop_drops_pending_review" / "BISHOP_drop_honeybee_waggle_router_v1.novel"

TRUTH_LABEL = "MODERNGL_PASS_READY"

# ── Inline chromatophore composite shader ─────────────────────────────────
# This is the SIFTA optic nerve composite — does NOT depend on the .novel
# file paths so headless tests and the QOpenGLWidget both compile cleanly.
# Biology: Haddock 2010, Messenger 2001. Tone-map: Reinhard 2002.
# Covenant clamps applied (CG55M truth audit 2026-05-01).

CHROMATOPHORE_VERTEX_SRC = """#version 410 core
in vec2 in_pos;
out vec2 v_uv;
void main() {
    v_uv = in_pos * 0.5 + 0.5;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

CHROMATOPHORE_FRAGMENT_SRC = """#version 410 core
in  vec2  v_uv;
out vec4  f_color;

uniform float u_stigmergic_drive;   // abs(tanh(td_value))  [0,1]
uniform float u_metabolic_scope;    // Kleiber tier          [0,2]
uniform float u_cot_factor;         // cost-of-transport     [0,1]
uniform float u_quorum_signal;      // quorum confidence     [0,1]
uniform float u_chemotaxis_gradient;// scent trail strength  [0,1]
uniform float u_reward;             // honest reinforcement [0,1]
uniform float u_time;               // seconds (for pulse)
uniform sampler2D u_pheromone_field;// Event 94 spatial memory texture

float chromatophore_intensity() {
    float td    = clamp(abs(u_stigmergic_drive), 0.0, 1.0);
    float scope = clamp(u_metabolic_scope,       0.0, 2.0);
    float cot   = 1.0 / (1.0 + max(u_cot_factor, 0.0));
    float qrm   = 1.0 + 3.0 * clamp(u_quorum_signal, 0.0, 1.0);
    float chem  = clamp(u_chemotaxis_gradient, 0.0, 1.0);
    float rew   = clamp(u_reward, 0.0, 1.0);
    return clamp(td * scope * cot * qrm * (1.0 + 4.0 * chem) * (1.0 + 2.5 * rew), 0.0, 8.0);
}

float glow(vec2 uv, float sharpness) {
    float d = length(uv - vec2(0.5));
    return exp(-d * d * sharpness);
}

void main() {
    float intensity = chromatophore_intensity();
    float reward    = clamp(u_stigmergic_drive, 0.0, 1.0);
    vec4 field      = texture(u_pheromone_field, v_uv);
    float trail     = clamp(field.r, 0.0, 1.0);
    float evap      = clamp(field.g, 0.0, 1.0);
    float chem      = max(clamp(u_chemotaxis_gradient, 0.0, 1.0), trail);
    float pulse     = 0.5 + 0.5 * sin(u_time * 2.5 + intensity * 8.0 + trail * 6.0);

    vec3 color = vec3(0.012, 0.008, 0.022);
    float g    = glow(v_uv, 18.0) * intensity;
    color += mix(vec3(0.0, 0.2, 0.8), vec3(0.0, 1.0, 1.0), reward) * g * pulse;
    color += vec3(1.0, 0.75, 0.1) * glow(v_uv, 6.0) * chem * 0.5;
    color += vec3(0.25, 0.75, 1.0) * trail * evap * 0.7;
    color += mix(vec3(0.0, 0.3, 1.0), vec3(1.0, 0.5, 0.0), reward)
             * glow(v_uv, 4.0) * intensity * 0.4;

    float exposure = 0.8 + 0.5 * intensity;
    color = vec3(1.0) - exp(-color * exposure);
    color = pow(max(color, vec3(0.0)), vec3(1.0 / 2.2));
    f_color = vec4(color, clamp(g + chem * 0.3, 0.0, 1.0));
}
"""

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


def read_pheromone_grid(path: Path | str = DEFAULT_PHEROMONE_FIELD, *, grid_size: int = 32) -> list[list[float]]:
    """Read `pheromone_field.json` as a clamped square float grid."""

    p = Path(path)
    if not p.exists():
        return [[0.0] * grid_size for _ in range(grid_size)]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if (
            isinstance(data, list)
            and len(data) == grid_size
            and all(isinstance(row, list) and len(row) == grid_size for row in data)
        ):
            return [
                [_clamp(value, 0.0, 1.0, 0.0) for value in row]
                for row in data
            ]
    except Exception:
        pass
    return [[0.0] * grid_size for _ in range(grid_size)]


def pheromone_field_texture_bytes(
    *,
    grid: Optional[list[list[float]]] = None,
    path: Path | str = DEFAULT_PHEROMONE_FIELD,
    grid_size: int = 32,
) -> tuple[bytes, tuple[int, int]]:
    """Return RGBA8 bytes for the Event 94 pheromone texture.

    R carries local pheromone strength. G carries visible evaporation/trail
    confidence. B is a softened intensity helper for shaders that want it.
    """

    import numpy as np

    source = grid if grid is not None else read_pheromone_grid(path, grid_size=grid_size)
    arr = np.asarray(source, dtype=np.float32)
    if arr.shape != (grid_size, grid_size):
        arr = np.zeros((grid_size, grid_size), dtype=np.float32)
    strength = np.clip(arr, 0.0, 1.0)
    evaporation = np.where(strength > 0.0, np.clip(0.35 + 0.65 * strength, 0.0, 1.0), 0.0)
    rgba = np.dstack(
        [
            strength,
            evaporation,
            np.sqrt(strength),
            np.ones_like(strength),
        ]
    )
    return (np.clip(rgba, 0.0, 1.0) * 255.0).astype("u1").tobytes(), (grid_size, grid_size)


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


# ── Headless pixel-proof helpers (tests + CI) ──────────────────────────────

def render_to_rgba(
    uniforms: Dict[str, float],
    width: int = 256,
    height: int = 256,
    t: float = 0.0,
    pheromone_grid: Optional[list[list[float]]] = None,
) -> Any:
    """
    Render one chromatophore frame headless → RGBA numpy array (H,W,4) uint8.
    Raises RuntimeError if standalone context is unavailable.
    """
    import moderngl
    import numpy as np

    probe = try_create_standalone_context()
    if not probe.ok:
        raise RuntimeError(f"Cannot create standalone GL context: {probe.status}")

    ctx = moderngl.create_standalone_context()
    try:
        prog = ctx.program(
            vertex_shader=CHROMATOPHORE_VERTEX_SRC,
            fragment_shader=CHROMATOPHORE_FRAGMENT_SRC,
        )
        import struct
        verts = struct.pack("12f",
            -1.0, -1.0,   1.0, -1.0,  -1.0,  1.0,
             1.0, -1.0,   1.0,  1.0,  -1.0,  1.0,
        )
        vbo = ctx.buffer(verts)
        vao = ctx.simple_vertex_array(prog, vbo, "in_pos")
        field_data, field_size = pheromone_field_texture_bytes(grid=pheromone_grid)
        pheromone_texture = ctx.texture(field_size, 4, data=field_data)
        fbo = ctx.simple_framebuffer((width, height))
        fbo.use()
        ctx.clear(0.012, 0.008, 0.022, 1.0)
        if "u_pheromone_field" in prog:
            pheromone_texture.use(location=0)
            prog["u_pheromone_field"].value = 0
        for key, val in uniforms.items():
            if key in prog:
                prog[key].value = float(val)
        if "u_time" in prog:
            prog["u_time"].value = float(t)
        vao.render(moderngl.TRIANGLES)
        raw = fbo.read(components=4)
        return np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)
    finally:
        ctx.release()


def mean_brightness(uniforms: Dict[str, float], width: int = 256, height: int = 256) -> float:
    """
    Render headless and return mean pixel luminance [0..255].
    The key falsifiable invariant: high_drive > low_drive.
    """
    import numpy as np
    rgba = render_to_rgba(uniforms, width, height)
    return float(np.mean(rgba[:, :, :3].astype(float)))


def mean_brightness_with_field(
    uniforms: Dict[str, float],
    pheromone_grid: list[list[float]],
    width: int = 256,
    height: int = 256,
) -> float:
    """Render with an explicit pheromone grid and return mean luminance."""

    import numpy as np

    rgba = render_to_rgba(uniforms, width, height, pheromone_grid=pheromone_grid)
    return float(np.mean(rgba[:, :, :3].astype(float)))


# ── QOpenGLWidget live UI composite ───────────────────────────────────────

def _make_phenotype_widget() -> Optional[type]:
    """Conditionally build QOpenGLWidget — returns None if Qt unavailable."""
    try:
        import moderngl
        import numpy as np
        import struct
        from PyQt6.QtCore import QTimer
        from PyQt6.QtOpenGLWidgets import QOpenGLWidget

        class SIFTAPhenotypeWidget(QOpenGLWidget):
            """
            Live QOpenGLWidget that paints the chromatophore phenotype.
            Polls visual_phenotype_uniforms.jsonl every POLL_MS milliseconds.
            """
            POLL_MS  = 80    # ledger poll (~12.5 fps)
            FRAME_MS = 40    # paint timer (~25 fps)

            def __init__(self, parent=None, ledger_path=None):
                super().__init__(parent)
                self._ledger = Path(ledger_path) if ledger_path else DEFAULT_LEDGER
                self._tail   = VisualPhenotypeUniformTail(self._ledger)
                self._ctx    = None
                self._prog   = None
                self._vao    = None
                self._pheromone_texture = None
                self._t      = 0.0
                self._frame: Optional[UniformFrame] = None

                poll = QTimer(self)
                poll.timeout.connect(self._poll)
                poll.start(self.POLL_MS)

                paint = QTimer(self)
                paint.timeout.connect(self.update)
                paint.start(self.FRAME_MS)

            def initializeGL(self):
                self._ctx  = moderngl.create_context()
                self._prog = self._ctx.program(
                    vertex_shader=CHROMATOPHORE_VERTEX_SRC,
                    fragment_shader=CHROMATOPHORE_FRAGMENT_SRC,
                )
                verts = struct.pack("12f",
                    -1.0, -1.0,   1.0, -1.0,  -1.0,  1.0,
                     1.0, -1.0,   1.0,  1.0,  -1.0,  1.0,
                )
                vbo = self._ctx.buffer(verts)
                self._vao = self._ctx.simple_vertex_array(
                    self._prog, vbo, "in_pos"
                )
                self._refresh_pheromone_texture()
                self._poll()

            def resizeGL(self, w, h):
                if self._ctx:
                    self._ctx.viewport = (0, 0, w, h)

            def paintGL(self):
                if not self._ctx or not self._vao or not self._prog:
                    return
                self._t += 0.04
                self._ctx.screen.use()
                self._ctx.clear(0.012, 0.008, 0.022, 1.0)
                self._refresh_pheromone_texture()
                if self._pheromone_texture is not None and "u_pheromone_field" in self._prog:
                    self._pheromone_texture.use(location=0)
                    self._prog["u_pheromone_field"].value = 0
                frame = self._frame
                if frame:
                    for key, val in frame.uniforms.items():
                        if key in self._prog:
                            self._prog[key].value = float(val)
                if "u_time" in self._prog:
                    self._prog["u_time"].value = self._t
                self._vao.render(moderngl.TRIANGLES)

            def _poll(self):
                self._frame = self._tail.read_frame()

            def _refresh_pheromone_texture(self):
                if not self._ctx:
                    return
                data, size = pheromone_field_texture_bytes()
                if self._pheromone_texture is None or self._pheromone_texture.size != size:
                    if self._pheromone_texture is not None:
                        try:
                            self._pheromone_texture.release()
                        except Exception:
                            pass
                    self._pheromone_texture = self._ctx.texture(size, 4, data=data)
                else:
                    self._pheromone_texture.write(data)

            @property
            def current_frame(self) -> Optional[UniformFrame]:
                return self._frame

        return SIFTAPhenotypeWidget
    except Exception:
        return None


SIFTAPhenotypeWidget = _make_phenotype_widget()



__all__ = [
    "CHROMATOPHORE_FRAGMENT_SRC",
    "CHROMATOPHORE_VERTEX_SRC",
    "ContextProbe",
    "DEFAULT_LEDGER",
    "DEFAULT_SHADER",
    "FULLSCREEN_VERTEX_SHADER",
    "DEFAULT_PHEROMONE_FIELD",
    "SIFTAPhenotypeWidget",
    "TRUTH_LABEL",
    "UniformFrame",
    "VisualPhenotypeModernGLPass",
    "VisualPhenotypeUniformTail",
    "clamp_uniforms",
    "load_honeybee_fragment",
    "mean_brightness",
    "mean_brightness_with_field",
    "modern_gl_available",
    "pheromone_field_texture_bytes",
    "read_last_jsonl_row",
    "read_pheromone_grid",
    "render_to_rgba",
    "summarize_uniform_frame",
    "try_create_standalone_context",
]
