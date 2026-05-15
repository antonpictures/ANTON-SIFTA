#!/usr/bin/env python3
"""BeeSon backdrop generator (plain charcoal).

The busy **honeycomb lattice** wallpaper was **revoked** by the Architect
2026-05-12. This module writes a minimal flat SVG that Qt can still load
_if needed_ — default BeeSon desktops use **no wallpaper** (see
`sifta_desktop_themes.BEESON.wallpaper_filename`).

Author: Cowork (Claude Opus 4.7), 2026-05-12 — honeycomb retired Cursor, 2026-05-12.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_OUT = _REPO / "Library" / "Desktop Pictures" / "BeeSon Default.svg"

# BeeSon charcoal (matches palette `bg_deep`).
BG_DEEP = "#0d0c0a"


def render_beeson_wallpaper(
    *,
    width: int = 4,
    height: int = 4,
    **_kwargs,
) -> str:
    """Return a tiny flat SVG (no hex lattice, no glow filters)."""
    w = max(1, int(width))
    h = max(1, int(height))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
        f'<rect width="100%" height="100%" fill="{BG_DEEP}"/>'
        f"</svg>"
    )


def write_wallpaper(
    out_path: Path | None = None,
    **kwargs,
) -> Path:
    """Write the plain backdrop. Returns the output path."""
    out = out_path or _DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    svg = render_beeson_wallpaper(**kwargs)
    out.write_text(svg, encoding="utf-8")
    return out


def _cli(argv: Sequence[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Write plain BeeSon charcoal SVG (honeycomb lattice retired).",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUT,
        help="Output SVG path",
    )
    args = p.parse_args(argv)
    out = write_wallpaper(out_path=args.out)
    print(f"BeeSon plain backdrop written → {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())


__all__ = ["BG_DEEP", "render_beeson_wallpaper", "write_wallpaper"]
