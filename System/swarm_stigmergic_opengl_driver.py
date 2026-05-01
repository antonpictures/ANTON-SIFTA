#!/usr/bin/env python3
"""Stigmergic OpenGL driver for chromatophore phenotype rendering.

This is the productionized version of the Event 86 -> 91 optic-nerve sketch.
It drives the archived chromatophore v3 shader from receipt-backed
`visual_phenotype_uniforms.jsonl` rows and renders to an offscreen ModernGL
framebuffer.

Truth label: OBSERVED_ENGINEERING_SUBSTRATE. This is a GPU-native driver, not a
claim that the Qt widget is already compositing the framebuffer on screen.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from System.swarm_visual_phenotype_gl import (
    DEFAULT_LEDGER,
    UniformFrame,
    VisualPhenotypeUniformTail,
    clamp_uniforms,
)


_REPO = Path(__file__).resolve().parent.parent
DEFAULT_CHROMATOPHORE_SHADER = (
    _REPO
    / "Archive"
    / "bishop_drops_pending_review"
    / "BISHOP_drop_chromatophore_shader_v3.novel"
)
DEFAULT_OUTPUT_DIR = _REPO / "Tests" / "output"

TRUTH_LABEL = "OBSERVED_ENGINEERING_SUBSTRATE"

CHROMATOPHORE_VERTEX_SHADER = """#version 410 core
in vec2 in_vert;
out vec2 v_texcoord;
void main() {
    gl_Position = vec4(in_vert, 0.0, 1.0);
    v_texcoord = in_vert * 0.5 + 0.5;
}
"""


@dataclass(frozen=True)
class DriverFrameReceipt:
    ok: bool
    tick_counter: int
    receipt_backed: bool
    tick_id: str
    width: int
    height: int
    bytes_written: int
    output_path: str
    truth_label: str = TRUTH_LABEL


def _create_context(*, standalone: bool, existing_context: Any = None) -> Any:
    if existing_context is not None:
        return existing_context

    import moderngl

    if standalone:
        return moderngl.create_standalone_context()
    return moderngl.create_context()


def _gradient_texture_rgba(width: int, height: int, *, bloom: bool = False) -> bytes:
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    if bloom:
        field = np.clip(
            0.15 + 0.85 * np.exp(-((x[None, :] - 0.5) ** 2 + (y - 0.5) ** 2) * 10.0),
            0.0,
            1.0,
        )
        rgba = np.dstack([field * 0.2, field * 0.8, field, np.ones_like(field)])
    else:
        red = np.broadcast_to(0.05 + x[None, :] * 0.20, (height, width))
        green = np.broadcast_to(0.08 + y * 0.25, (height, width))
        blue = np.broadcast_to(0.18 + x[None, :] * 0.25, (height, width))
        rgba = np.dstack([red, green, blue, np.ones_like(red)])
    return (np.clip(rgba, 0.0, 1.0) * 255.0).astype("u1").tobytes()


class StigmergicOpenGLDriver:
    """Receipt-backed chromatophore driver for offscreen ModernGL rendering."""

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        *,
        standalone: bool = True,
        ctx: Any = None,
        uniforms_log: Path | str = DEFAULT_LEDGER,
        shader_path: Path | str = DEFAULT_CHROMATOPHORE_SHADER,
    ) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive")

        self.width = int(width)
        self.height = int(height)
        self.shader_path = Path(shader_path)
        self.ctx = _create_context(standalone=standalone, existing_context=ctx)
        self._owns_context = ctx is None
        self.tail = VisualPhenotypeUniformTail(uniforms_log)
        self.last_frame: Optional[UniformFrame] = None
        self.tick_counter = 0

        self.program = self._load_program()
        self.vbo = self.ctx.buffer(
            np.asarray(
                [
                    -1.0,
                    -1.0,
                    1.0,
                    -1.0,
                    -1.0,
                    1.0,
                    1.0,
                    1.0,
                ],
                dtype="f4",
            ).tobytes()
        )
        self.vao = self.ctx.vertex_array(self.program, [(self.vbo, "2f", "in_vert")])
        self.output_texture = self.ctx.texture((self.width, self.height), 4)
        self.fbo = self.ctx.framebuffer(color_attachments=[self.output_texture])
        self.scene_texture = self.ctx.texture(
            (self.width, self.height),
            4,
            data=_gradient_texture_rgba(self.width, self.height, bloom=False),
        )
        self.bloom_texture = self.ctx.texture(
            (self.width, self.height),
            4,
            data=_gradient_texture_rgba(self.width, self.height, bloom=True),
        )

    def _load_program(self) -> Any:
        fragment_src = self.shader_path.read_text(encoding="utf-8")
        return self.ctx.program(
            vertex_shader=CHROMATOPHORE_VERTEX_SHADER,
            fragment_shader=fragment_src,
        )

    def _set_uniform(self, name: str, value: Any) -> None:
        try:
            uniform = self.program[name]
        except Exception:
            return
        try:
            uniform.value = value
        except Exception:
            pass

    def _apply_uniforms(self, frame: UniformFrame) -> None:
        uniforms = clamp_uniforms(frame.uniforms)
        self._set_uniform("u_stigmergic_drive", uniforms["u_stigmergic_drive"])
        self._set_uniform("u_metabolic_scope", uniforms["u_metabolic_scope"])
        self._set_uniform("u_cot_factor", uniforms["u_cot_factor"])
        self._set_uniform("u_quorum_signal", uniforms["u_quorum_signal"])
        self._set_uniform("u_chemotaxis_gradient", uniforms["u_chemotaxis_gradient"])

    def render_frame(
        self,
        *,
        input_texture: Any = None,
        bloom_texture: Any = None,
        force_pull: bool = False,
    ) -> Any:
        """Render one frame and return the output texture."""

        frame = self.tail.read_frame(force=force_pull)
        self.fbo.use()
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)

        scene = input_texture or self.scene_texture
        bloom = bloom_texture or self.bloom_texture
        scene.use(location=0)
        bloom.use(location=1)
        self._set_uniform("u_scene_texture", 0)
        self._set_uniform("u_bloom_blur_texture", 1)
        self._apply_uniforms(frame)

        import moderngl

        self.vao.render(moderngl.TRIANGLE_STRIP)
        self.last_frame = frame
        self.tick_counter += 1
        return self.output_texture

    def read_rgba_bytes(self) -> bytes:
        return self.output_texture.read()

    def save_screenshot(self, path: Path | str) -> DriverFrameReceipt:
        """Render and save a proof artifact.

        If PIL is installed and `path` ends in `.png`, a PNG is written. A `.raw`
        fallback is always supported and records the exact framebuffer bytes.
        """

        requested = Path(path)
        requested.parent.mkdir(parents=True, exist_ok=True)
        self.render_frame(force_pull=True)
        data = self.read_rgba_bytes()
        output_path = requested
        bytes_written = 0

        if requested.suffix.lower() == ".png":
            try:
                from PIL import Image

                image = Image.frombytes("RGBA", (self.width, self.height), data)
                image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                image.save(requested)
                bytes_written = requested.stat().st_size
            except Exception:
                output_path = requested.with_suffix(".raw")
                output_path.write_bytes(data)
                bytes_written = len(data)
        else:
            output_path = requested.with_suffix(".raw")
            output_path.write_bytes(data)
            bytes_written = len(data)

        frame = self.last_frame
        return DriverFrameReceipt(
            ok=True,
            tick_counter=self.tick_counter,
            receipt_backed=bool(frame and frame.receipt_backed),
            tick_id=str(frame.tick_id if frame else ""),
            width=self.width,
            height=self.height,
            bytes_written=bytes_written,
            output_path=str(output_path),
        )

    def release(self) -> None:
        for obj in (
            getattr(self, "vao", None),
            getattr(self, "vbo", None),
            getattr(self, "fbo", None),
            getattr(self, "output_texture", None),
            getattr(self, "scene_texture", None),
            getattr(self, "bloom_texture", None),
            getattr(self, "program", None),
        ):
            try:
                obj.release()
            except Exception:
                pass
        if self._owns_context:
            try:
                self.ctx.release()
            except Exception:
                pass


def smoke_render_receipt(
    output_path: Path | str = DEFAULT_OUTPUT_DIR / "stigmergic_chromatophore_test.png",
    *,
    uniforms_log: Path | str = DEFAULT_LEDGER,
) -> DriverFrameReceipt:
    driver = StigmergicOpenGLDriver(
        width=256,
        height=144,
        standalone=True,
        uniforms_log=uniforms_log,
    )
    try:
        return driver.save_screenshot(Path(output_path))
    finally:
        driver.release()


if __name__ == "__main__":
    receipt = smoke_render_receipt()
    print(json.dumps(receipt.__dict__, indent=2, sort_keys=True))
