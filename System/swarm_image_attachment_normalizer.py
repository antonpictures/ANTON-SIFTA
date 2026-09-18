"""Bounded normalization of owner image attachments for local model APIs.

Ollama accepts common raster payloads but does not reliably decode HEIC/HEIF.
macOS ``sips`` is used when present; an already-installed Pillow HEIF plugin is
also accepted. The source file is never modified. This module does not upload
or publish the source image.
"""
from __future__ import annotations

import io
import hashlib
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MAX_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_PIXELS = 40_000_000
HEIF_BRANDS = (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1")


@dataclass(frozen=True)
class NormalizedImage:
    data: bytes
    format: str
    mime: str
    converted: bool
    source_format: str
    source_sha256: str = ""
    data_sha256: str = ""


def detect_image_format(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in HEIF_BRANDS:
        return "heif"
    return ""


def _validate_size(path: Path, max_bytes: int) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"image attachment not found: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise ValueError("image attachment is empty")
    if size > max_bytes:
        raise ValueError(f"image attachment is too large: {size} bytes (max {max_bytes})")


def _sanitize_jpeg(data: bytes, max_pixels: int) -> bytes:
    """Decode/re-encode with Pillow when available, dropping EXIF metadata."""
    try:
        from PIL import Image
    except Exception:
        raise RuntimeError("Pillow is required to validate JPEG bytes")
    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size
        if width * height > max_pixels:
            raise ValueError(f"decoded image is too large: {width}x{height}")
        rgb = image.convert("RGB")
        output = io.BytesIO()
        rgb.save(output, format="JPEG", quality=92, optimize=True, exif=b"")
        return output.getvalue()


def _convert_with_pillow(path: Path, max_pixels: int) -> bytes | None:
    return _convert_with_pillow_bytes(path.read_bytes(), max_pixels)


def _convert_with_pillow_bytes(data: bytes, max_pixels: int) -> bytes | None:
    try:
        from PIL import Image
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            if width * height > max_pixels:
                raise ValueError(f"decoded image is too large: {width}x{height}")
            # Apply the camera's EXIF orientation while the tag is still
            # available, then remove metadata from the transport copy.
            try:
                from PIL import ImageOps
                image = ImageOps.exif_transpose(image)
            except Exception:
                pass
            rgb = image.convert("RGB")
            output = io.BytesIO()
            rgb.save(output, format="JPEG", quality=92, optimize=True, exif=b"")
            return output.getvalue()
    except ImportError:
        return None
    except ValueError:
        raise
    except OSError:
        return None


def _convert_with_pillow_subprocess(
    data: bytes,
    max_pixels: int,
    timeout: float,
    max_output_bytes: int = DEFAULT_MAX_BYTES,
) -> bytes | None:
    """Decode immutable bytes in a killable helper process."""
    script = r'''
import io, sys
try:
    from PIL import Image, ImageOps
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    raw = sys.stdin.buffer.read()
    with Image.open(io.BytesIO(raw)) as image:
        if image.size[0] * image.size[1] > int(sys.argv[1]):
            raise ValueError("decoded image is too large")
        image = ImageOps.exif_transpose(image)
        rgb = image.convert("RGB")
        output = io.BytesIO()
        rgb.save(output, format="JPEG", quality=92, optimize=True, exif=b"")
        encoded = output.getvalue()
        if len(encoded) > int(sys.argv[2]):
            raise ValueError("normalized image is too large")
        sys.stdout.buffer.write(encoded)
except Exception as exc:
    sys.stderr.write(f"{type(exc).__name__}: {exc}")
    raise
'''
    try:
        result = subprocess.run(
            [sys.executable, "-c", script, str(int(max_pixels)), str(int(max_output_bytes))],
            input=data, capture_output=True, timeout=max(0.01, float(timeout)), check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"image decoder exceeded {timeout:.1f}s timeout") from exc
    except OSError:
        return None
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        if "too large" in message:
            raise ValueError(message)
        return None
    return result.stdout if result.stdout.startswith(b"\xff\xd8\xff") else None


def _convert_with_sips(path: Path, max_pixels: int, timeout: float) -> bytes | None:
    sips = "/usr/bin/sips"
    if not os.path.exists(sips):
        return None
    with tempfile.TemporaryDirectory(prefix="sifta-heif-") as temp_dir:
        output = Path(temp_dir) / "normalized.jpg"
        command = [
            sips, "-s", "format", "jpeg", "-s", "formatOptions", "92",
            "--resampleHeightWidthMax", str(int(max_pixels ** 0.5)),
            str(path), "--out", str(output),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0 or not output.is_file():
            return None
        data = output.read_bytes()
        if not data.startswith(b"\xff\xd8\xff"):
            return None
        try:
            return _sanitize_jpeg(data, max_pixels)
        except (OSError, ValueError):
            return None


def normalize_image_attachment(
    path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_pixels: int = DEFAULT_MAX_PIXELS,
    conversion_timeout: float = 20.0,
) -> NormalizedImage:
    source = Path(path).expanduser()
    _validate_size(source, max_bytes)
    data = source.read_bytes()
    source_format = detect_image_format(data)
    if source_format in {"png", "jpeg", "webp"}:
        return NormalizedImage(
            data, source_format,
            f"image/{'jpeg' if source_format == 'jpeg' else source_format}",
            False, source_format,
            hashlib.sha256(data).hexdigest(), hashlib.sha256(data).hexdigest(),
        )
    if source_format != "heif":
        raise ValueError("unsupported image bytes; expected PNG, JPEG, WebP, HEIC, or HEIF")

    conversion_error = ""
    deadline = time.monotonic() + max(0.01, float(conversion_timeout))
    try:
        converted = _convert_with_pillow_subprocess(
            data, max_pixels, max(0.01, deadline - time.monotonic()), max_bytes
        )
    except TimeoutError as exc:
        converted = None
        conversion_error = str(exc)
    except ValueError:
        raise
    except Exception as exc:
        converted = None
        conversion_error = f"Pillow conversion failed: {type(exc).__name__}: {exc}"
    if converted is None:
        with tempfile.NamedTemporaryFile(prefix="sifta-heif-", suffix=".heic") as immutable_source:
            immutable_source.write(data)
            immutable_source.flush()
            converted = _convert_with_sips(
                Path(immutable_source.name), max_pixels,
                max(0.01, deadline - time.monotonic()),
            )
    if converted is None:
        suffix = f" ({conversion_error})" if conversion_error else ""
        raise ValueError(
            "HEIC/HEIF decoder unavailable or failed; install Pillow with HEIF support "
            f"or use macOS sips{suffix}"
        )
    if len(converted) > max_bytes:
        raise ValueError(f"normalized image is too large: {len(converted)} bytes (max {max_bytes})")
    # The decoder produced the JPEG; decode it once more before transport so
    # corrupt output cannot be advertised as a valid attachment.
    try:
        validated = _convert_with_pillow_subprocess(
            converted, max_pixels, max(0.01, deadline - time.monotonic()), max_bytes
        )
        if not validated:
            raise ValueError("JPEG decoder returned no validated pixels")
    except Exception as exc:
        raise ValueError(f"normalized image failed JPEG validation: {exc}") from exc
    return NormalizedImage(
        converted, "jpeg", "image/jpeg", True, source_format,
        hashlib.sha256(data).hexdigest(), hashlib.sha256(converted).hexdigest(),
    )
