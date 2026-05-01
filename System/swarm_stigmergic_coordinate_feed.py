#!/usr/bin/env python3
"""
System/swarm_stigmergic_coordinate_feed.py
════════════════════════════════════════════════════════════════════════
Event 94 — Real Coordinate Feed for the Pheromone Field

The missing ⅓ of embodied navigation.

Before this module:
  action_to_position(action) = hash(action_string) % GRID_SIZE
  → pheromone deposits land at SHA256-derived cells
  → no spatial meaning; "explore at (14,7)" tells you nothing about space

After this module:
  cursor_screen_coords() → (px_x, px_y) [Quartz CGL, no mic/cam]
  coords_to_grid(px_x, px_y, screen_w, screen_h) → (grid_x, grid_y)
  → pheromone deposits land at real screen locations Alice is engaged with
  → gradient ascent ≈ "go back to where the last high-reward click was"

Truth labels (§7.11):
  REAL_CURSOR_COORDS   — Quartz/AppKit gave us actual screen position
  SIM_BROWNIAN_WALK    — no real coords available; deterministic Brownian proxy
  SCREEN_COORD_PROXY   — real pixel coords but not a 3-D pose estimate

SIFTA stack after this module:
  cursor → coords_to_grid → update_pheromone_field(row, x, y)
  → grid gradient → chemotaxis_scalar
  → u_chemotaxis_gradient → visual_phenotype_bridge → GPU pixel

Biology:
  Dusenbery, D.B. (1992). Sensory Ecology. W.H. Freeman. — chemotaxis basics.
  Berg, H.C. (1993). Random Walks in Biology. Princeton UP.
    — biased random walk in gradient; our cursor-follow is an analogue.
  Grassé (1959) + Wilson (1971) pheromone field DOIs — already in
    swarm_pheromone_field.py header.

NPPL & Privacy:
  Reads screen cursor position only. No mic, no camera, no keylog.
  Persisting cursor-derived cells in `pheromone_field.json` and trace receipts
  constitutes a behavioral trace. This trace is local-only, ephemeral to the
  session, and explicitly governed by the "no surveillance" scope of the NPPL.
"""
from __future__ import annotations

import math
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# ── Truth labels ───────────────────────────────────────────────────────────

TRUTH_REAL       = "REAL_CURSOR_COORDS"
TRUTH_SIM        = "SIM_BROWNIAN_WALK"
TRUTH_PROXY      = "SCREEN_COORD_PROXY"


# ── Screen geometry (auto-detected or overrideable in tests) ───────────────

_DEFAULT_SCREEN_W: int = 2560
_DEFAULT_SCREEN_H: int = 1600


def _screen_size() -> Tuple[int, int]:
    """Return (width, height) of the total virtual desktop, with fallback."""
    try:
        from AppKit import NSScreen
        w = h = 0
        for screen in NSScreen.screens():
            f = screen.frame()
            w = max(w, int(f.origin.x + f.size.width))
            h = max(h, int(f.origin.y + f.size.height))
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass
    try:
        from Quartz import CGDisplayBounds, CGMainDisplayID
        bounds = CGDisplayBounds(CGMainDisplayID())
        return int(bounds.size.width), int(bounds.size.height)
    except Exception:
        pass
    try:
        import subprocess
        out = subprocess.check_output(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            timeout=2, text=True, stderr=subprocess.DEVNULL
        )
        import json
        data = json.loads(out)
        for item in data.get("SPDisplaysDataType", []):
            for disp in item.get("spdisplays_ndrvs", []):
                res = disp.get("spdisplays_resolution", "")
                parts = res.split(" x ")
                if len(parts) == 2:
                    return int(parts[0].strip()), int(parts[1].strip().split(" ")[0])
    except Exception:
        pass
    return _DEFAULT_SCREEN_W, _DEFAULT_SCREEN_H


# ── Real cursor position ───────────────────────────────────────────────────

@dataclass(frozen=True)
class CoordSample:
    x_px:        float
    y_px:        float
    screen_w:    int
    screen_h:    int
    truth_label: str
    ts:          float


def cursor_screen_coords() -> CoordSample:
    """
    Read the current cursor position from the OS.
    Uses Quartz (CGL) — no mic, no camera.
    Falls back to AppKit, then to SIM_BROWNIAN_WALK.
    """
    now = time.time()
    sw, sh = _screen_size()

    # ── Quartz (primary, always available on macOS) ────────────────────
    try:
        from Quartz import CGEventCreate, CGEventGetLocation
        e   = CGEventCreate(None)
        loc = CGEventGetLocation(e)
        return CoordSample(
            x_px=float(loc.x),
            y_px=float(loc.y),
            screen_w=sw,
            screen_h=sh,
            truth_label=TRUTH_REAL,
            ts=now,
        )
    except Exception:
        pass

    # ── AppKit fallback ────────────────────────────────────────────────
    try:
        from AppKit import NSEvent
        p = NSEvent.mouseLocation()
        # AppKit uses flipped y (0 = bottom); normalise to top-left
        return CoordSample(
            x_px=float(p.x),
            y_px=float(sh - p.y),
            screen_w=sw,
            screen_h=sh,
            truth_label=TRUTH_REAL,
            ts=now,
        )
    except Exception:
        pass

    # ── Brownian walk simulation (headless CI / no display) ───────────
    _brownian_state["x"] = _clamp_px(
        _brownian_state["x"] + random.gauss(0, sw / 20), sw
    )
    _brownian_state["y"] = _clamp_px(
        _brownian_state["y"] + random.gauss(0, sh / 20), sh
    )
    return CoordSample(
        x_px=_brownian_state["x"],
        y_px=_brownian_state["y"],
        screen_w=sw,
        screen_h=sh,
        truth_label=TRUTH_SIM,
        ts=now,
    )


_brownian_state: dict = {"x": 640.0, "y": 400.0}


def _clamp_px(v: float, bound: int) -> float:
    return max(0.0, min(float(bound - 1), v))


# ── Grid mapping ───────────────────────────────────────────────────────────

def coords_to_grid(
    x_px: float,
    y_px: float,
    screen_w: int,
    screen_h: int,
    grid_size: int = 32,
) -> Tuple[int, int]:
    """
    Map pixel coordinates to a pheromone grid cell.
    Clamps to [0, grid_size-1] in both axes.
    """
    gx = int(min(grid_size - 1, max(0, (x_px / screen_w) * grid_size)))
    gy = int(min(grid_size - 1, max(0, (y_px / screen_h) * grid_size)))
    return gx, gy


def sample_real_grid_position(grid_size: int = 32) -> Tuple[CoordSample, Tuple[int, int]]:
    """
    Convenience: get cursor position and its grid cell in one call.
    Returns (CoordSample, (gx, gy)).
    """
    sample = cursor_screen_coords()
    cell   = coords_to_grid(
        sample.x_px, sample.y_px,
        sample.screen_w, sample.screen_h,
        grid_size,
    )
    return sample, cell


# ── Ledger integration ─────────────────────────────────────────────────────

def read_visual_stigmergy_coords(state_dir: Optional[Path] = None) -> Optional[Tuple[float, float]]:
    """
    If visual_stigmergy.jsonl has a recent row with pixel_x / pixel_y,
    return those. Otherwise None.
    This is the future hook: when the retina organ writes coordinates,
    they supersede the cursor fallback.
    """
    import json
    p = (state_dir or (_REPO / ".sifta_state")) / "visual_stigmergy.jsonl"
    if not p.exists():
        return None
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines):
            row = json.loads(line)
            if isinstance(row, dict) and "pixel_x" in row and "pixel_y" in row:
                return float(row["pixel_x"]), float(row["pixel_y"])
    except Exception:
        pass
    return None


def best_grid_position(
    grid_size: int = 32,
    state_dir: Optional[Path] = None,
) -> Tuple[int, int, str]:
    """
    Return the best available (gx, gy, truth_label).
    Priority: visual_stigmergy (retina) > cursor (Quartz) > Brownian sim.
    """
    # 1. retina coords (future hook — already plumbed)
    vis = read_visual_stigmergy_coords(state_dir)
    if vis is not None:
        sw, sh = _screen_size()
        gx, gy = coords_to_grid(vis[0], vis[1], sw, sh, grid_size)
        return gx, gy, TRUTH_PROXY

    # 2. real cursor
    sample, (gx, gy) = sample_real_grid_position(grid_size)
    return gx, gy, sample.truth_label


# ── Smoke test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample, cell = sample_real_grid_position()
    print(f"Cursor: ({sample.x_px:.0f}, {sample.y_px:.0f}) px  "
          f"[{sample.screen_w}x{sample.screen_h}]  "
          f"truth={sample.truth_label}")
    print(f"Grid cell: {cell}")
    gx, gy, label = best_grid_position()
    print(f"best_grid_position: ({gx}, {gy})  truth={label}")
