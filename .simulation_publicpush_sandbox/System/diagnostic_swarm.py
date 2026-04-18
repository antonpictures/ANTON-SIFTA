#!/usr/bin/env python3
"""
diagnostic_swarm.py — Stigmergic Medical Anomaly Detection Engine
═══════════════════════════════════════════════════════════════════
Treat medical data as physical terrain.  Deploy swimmer agents.
Swimmers slow down near anomalies, deposit diagnostic pheromone.
The swarm naturally clusters around hidden disease.

Terrain types (synthetic, research-grade distributions):
  • TISSUE   — mammography-like cross-section with microcalcifications + masses
  • GENOMIC  — gene expression heatmap with anomalous regulation clusters
  • BLOOD    — cell scatter field with morphologically abnormal cells

Swimmer species:
  • DiagnosticForager  — wanders terrain, deposits pheromone on anomalies
  • CalcificationHunter — seeks small bright clusters (micro-calc signature)
  • MarginMapper       — traces edges of detected masses
  • PatrolSweeper      — systematic grid sweep, marks regions as cleared

Anomaly detection uses real statistical methods:
  • Local vs global mean deviation (Z-score)
  • Local variance ratio
  • Gradient magnitude (Sobel-like)
  • Combined anomaly score → pheromone deposit strength
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np


# ── Terrain generation ──────────────────────────────────────────

@dataclass
class Anomaly:
    """A planted anomaly in the synthetic terrain."""
    cx: int
    cy: int
    radius: float
    anomaly_type: str   # "microcalc", "mass", "gene_cluster", "abnormal_cell"
    intensity: float    # how much it deviates from background
    detected: bool = False
    confidence: float = 0.0


def generate_tissue_terrain(
    rows: int = 200, cols: int = 200,
    n_masses: int = 3, n_calcifications: int = 5,
    noise_sigma: float = 0.08,
    seed: int | None = None,
) -> Tuple[np.ndarray, List[Anomaly]]:
    """Generate synthetic mammography-like tissue cross-section.

    Background: correlated Gaussian field (fibroglandular tissue texture).
    Anomalies: masses (large ellipses) + microcalcification clusters (tiny bright dots).
    Returns (terrain_matrix [0-1], list_of_planted_anomalies).
    """
    rng = np.random.default_rng(seed)

    base = rng.normal(0.45, noise_sigma, (rows, cols))

    # Correlated texture via low-pass convolution
    kernel_size = 9
    k = np.ones((kernel_size, kernel_size)) / (kernel_size ** 2)
    from numpy.lib.stride_tricks import sliding_window_view
    padded = np.pad(base, kernel_size // 2, mode="reflect")
    windows = sliding_window_view(padded, (kernel_size, kernel_size))
    terrain = np.mean(windows, axis=(2, 3))

    terrain = terrain[:rows, :cols]

    # Add anatomical density gradient (denser toward center)
    yy, xx = np.mgrid[0:rows, 0:cols]
    cx, cy = rows / 2, cols / 2
    r = np.sqrt((yy - cx) ** 2 + (xx - cy) ** 2) / max(rows, cols)
    terrain += 0.12 * np.exp(-3.0 * r ** 2)

    anomalies: List[Anomaly] = []

    # Plant masses (larger regions of altered density)
    for _ in range(n_masses):
        mx = rng.integers(rows // 5, 4 * rows // 5)
        my = rng.integers(cols // 5, 4 * cols // 5)
        rx = rng.integers(8, 22)
        ry = rng.integers(8, 22)
        intensity = rng.uniform(0.12, 0.25)

        mask = ((yy - mx) / rx) ** 2 + ((xx - my) / ry) ** 2 < 1.0
        terrain[mask] += intensity
        # Spiculated margin (irregular boundary noise)
        angles = np.arctan2(yy - mx, xx - my)
        spicule = 0.03 * np.sin(8 * angles + rng.uniform(0, 2 * np.pi))
        border = np.abs(((yy - mx) / rx) ** 2 + ((xx - my) / ry) ** 2 - 1.0) < 0.15
        terrain[border] += np.abs(spicule[border])

        anomalies.append(Anomaly(
            cx=int(mx), cy=int(my), radius=float(max(rx, ry)),
            anomaly_type="mass", intensity=intensity))

    # Plant microcalcification clusters
    for _ in range(n_calcifications):
        cluster_cx = rng.integers(rows // 6, 5 * rows // 6)
        cluster_cy = rng.integers(cols // 6, 5 * cols // 6)
        n_dots = rng.integers(4, 12)
        for _ in range(n_dots):
            dx = cluster_cx + rng.integers(-6, 7)
            dy = cluster_cy + rng.integers(-6, 7)
            dx = np.clip(dx, 1, rows - 2)
            dy = np.clip(dy, 1, cols - 2)
            bright = rng.uniform(0.2, 0.4)
            terrain[dx, dy] += bright
            terrain[dx - 1:dx + 2, dy - 1:dy + 2] += bright * 0.3

        anomalies.append(Anomaly(
            cx=int(cluster_cx), cy=int(cluster_cy), radius=8.0,
            anomaly_type="microcalc", intensity=0.3))

    terrain = np.clip(terrain, 0.0, 1.0)
    return terrain, anomalies


def generate_genomic_terrain(
    rows: int = 200, cols: int = 200,
    n_clusters: int = 6,
    seed: int | None = None,
) -> Tuple[np.ndarray, List[Anomaly]]:
    """Generate synthetic gene expression heatmap with anomalous regulation clusters."""
    rng = np.random.default_rng(seed)
    terrain = rng.normal(0.35, 0.06, (rows, cols))

    # Banded structure (genes grouped by pathway)
    for i in range(0, rows, rows // 8):
        band_h = rng.integers(3, 10)
        terrain[i:i + band_h, :] += rng.uniform(0.02, 0.08)

    anomalies: List[Anomaly] = []
    for _ in range(n_clusters):
        cx = rng.integers(rows // 6, 5 * rows // 6)
        cy = rng.integers(cols // 6, 5 * cols // 6)
        w = rng.integers(6, 18)
        h = rng.integers(6, 18)
        intensity = rng.uniform(0.15, 0.35)
        terrain[cx:cx + w, cy:cy + h] += intensity * rng.uniform(0.5, 1.0, (min(w, rows - cx), min(h, cols - cy)))
        anomalies.append(Anomaly(
            cx=int(cx + w // 2), cy=int(cy + h // 2), radius=float(max(w, h) / 2),
            anomaly_type="gene_cluster", intensity=intensity))

    terrain = np.clip(terrain, 0.0, 1.0)
    return terrain, anomalies


def generate_blood_terrain(
    rows: int = 200, cols: int = 200,
    n_abnormal: int = 8,
    seed: int | None = None,
) -> Tuple[np.ndarray, List[Anomaly]]:
    """Generate synthetic blood smear field with normal and abnormal cells."""
    rng = np.random.default_rng(seed)
    terrain = np.full((rows, cols), 0.15)  # pale background (glass slide)

    yy, xx = np.mgrid[0:rows, 0:cols]
    anomalies: List[Anomaly] = []

    # Normal red blood cells (~200 of them)
    for _ in range(220):
        cx = rng.integers(5, rows - 5)
        cy = rng.integers(5, cols - 5)
        r_outer = rng.uniform(2.5, 4.0)
        r_inner = r_outer * 0.4
        dist = np.sqrt((yy - cx) ** 2 + (xx - cy) ** 2)
        ring = (dist < r_outer) & (dist > r_inner)
        center = dist <= r_inner
        terrain[ring] = np.clip(terrain[ring] + 0.25, 0, 1)
        terrain[center] = np.clip(terrain[center] + 0.12, 0, 1)

    # Abnormal cells (larger, irregular, denser)
    for _ in range(n_abnormal):
        cx = rng.integers(15, rows - 15)
        cy = rng.integers(15, cols - 15)
        r = rng.uniform(5, 10)
        dist = np.sqrt((yy - cx) ** 2 + (xx - cy) ** 2)
        angles = np.arctan2(yy - cx, xx - cy)
        irregular_r = r + 1.5 * np.sin(5 * angles + rng.uniform(0, 6.28))
        mask = dist < irregular_r
        intensity = rng.uniform(0.3, 0.5)
        terrain[mask] = np.clip(terrain[mask] + intensity, 0, 1)
        # Dark nucleus
        nuc_mask = dist < r * 0.35
        terrain[nuc_mask] = np.clip(terrain[nuc_mask] + 0.15, 0, 1)

        anomalies.append(Anomaly(
            cx=int(cx), cy=int(cy), radius=float(r),
            anomaly_type="abnormal_cell", intensity=intensity))

    terrain = np.clip(terrain, 0.0, 1.0)
    return terrain, anomalies


# ── Anomaly scoring (real statistical methods) ──────────────────

def compute_anomaly_map(terrain: np.ndarray, window: int = 7) -> np.ndarray:
    """Compute per-pixel anomaly score using local statistics.

    Method:
      1. Local mean deviation (Z-score vs global)
      2. Local variance ratio (high variance = textural anomaly)
      3. Gradient magnitude (Sobel-like first derivative)
      Combined into a single [0,1] anomaly score.
    """
    rows, cols = terrain.shape
    pad = window // 2
    padded = np.pad(terrain, pad, mode="reflect")

    global_mean = terrain.mean()
    global_std = max(terrain.std(), 1e-6)

    anomaly = np.zeros_like(terrain)

    from numpy.lib.stride_tricks import sliding_window_view
    windows = sliding_window_view(padded, (window, window))
    local_mean = np.mean(windows, axis=(2, 3))[:rows, :cols]
    local_var = np.var(windows, axis=(2, 3))[:rows, :cols]

    # Z-score component
    z_score = np.abs(local_mean - global_mean) / global_std
    z_norm = np.clip(z_score / 3.0, 0, 1)

    # Variance ratio
    global_var = max(terrain.var(), 1e-8)
    var_ratio = local_var / global_var
    var_norm = np.clip((var_ratio - 1.0) / 4.0, 0, 1)

    # Gradient magnitude (simple Sobel-like)
    gy = np.abs(np.diff(terrain, axis=0, prepend=terrain[:1, :]))
    gx = np.abs(np.diff(terrain, axis=1, prepend=terrain[:, :1]))
    grad = np.sqrt(gx ** 2 + gy ** 2)
    grad_norm = np.clip(grad / max(grad.max(), 1e-6), 0, 1)

    # Weighted combination
    anomaly = 0.45 * z_norm + 0.30 * var_norm + 0.25 * grad_norm
    return np.clip(anomaly, 0, 1)


# ── Swimmer agents ──────────────────────────────────────────────

@dataclass
class MedSwimmer:
    """A diagnostic swimmer agent on the medical terrain."""
    species: str       # "forager", "calc_hunter", "margin_mapper", "sweeper"
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    pheromone_deposited: float = 0.0
    anomalies_found: int = 0
    steps: int = 0
    trail: List[Tuple[float, float]] = field(default_factory=list)

    @property
    def color(self) -> str:
        return {
            "forager": "#00ffc8",
            "calc_hunter": "#ff6644",
            "margin_mapper": "#cc44ff",
            "sweeper": "#4488ff",
        }.get(self.species, "#ffffff")

    @property
    def marker(self) -> str:
        return {
            "forager": "o",
            "calc_hunter": "D",
            "margin_mapper": "^",
            "sweeper": "s",
        }.get(self.species, "o")


def spawn_swimmers(
    rows: int, cols: int,
    n_foragers: int = 30,
    n_hunters: int = 10,
    n_margin: int = 8,
    n_sweepers: int = 6,
) -> List[MedSwimmer]:
    """Spawn swimmer agents at random positions."""
    swimmers: List[MedSwimmer] = []
    for _ in range(n_foragers):
        swimmers.append(MedSwimmer(
            species="forager",
            x=random.uniform(0, rows - 1), y=random.uniform(0, cols - 1),
            vx=random.gauss(0, 1.5), vy=random.gauss(0, 1.5)))
    for _ in range(n_hunters):
        swimmers.append(MedSwimmer(
            species="calc_hunter",
            x=random.uniform(0, rows - 1), y=random.uniform(0, cols - 1),
            vx=random.gauss(0, 1.0), vy=random.gauss(0, 1.0)))
    for _ in range(n_margin):
        swimmers.append(MedSwimmer(
            species="margin_mapper",
            x=random.uniform(0, rows - 1), y=random.uniform(0, cols - 1),
            vx=random.gauss(0, 0.8), vy=random.gauss(0, 0.8)))
    for _ in range(n_sweepers):
        row_start = random.randint(0, rows - 1)
        swimmers.append(MedSwimmer(
            species="sweeper",
            x=float(row_start), y=0.0,
            vx=0.0, vy=2.0))
    return swimmers


def step_swimmers(
    swimmers: List[MedSwimmer],
    terrain: np.ndarray,
    anomaly_map: np.ndarray,
    pheromone: np.ndarray,
    dt: float = 1.0,
) -> None:
    """Advance all swimmers one tick.  Core stigmergic loop:
    sense anomaly → slow if high → deposit pheromone → follow gradient."""
    rows, cols = terrain.shape

    for sw in swimmers:
        ix = int(np.clip(sw.x, 0, rows - 1))
        iy = int(np.clip(sw.y, 0, cols - 1))
        local_anomaly = anomaly_map[ix, iy]
        local_phero = pheromone[ix, iy]

        sw.steps += 1

        if sw.species == "forager":
            _step_forager(sw, ix, iy, local_anomaly, local_phero, anomaly_map, pheromone, rows, cols, dt)
        elif sw.species == "calc_hunter":
            _step_calc_hunter(sw, ix, iy, local_anomaly, terrain, anomaly_map, pheromone, rows, cols, dt)
        elif sw.species == "margin_mapper":
            _step_margin_mapper(sw, ix, iy, local_anomaly, anomaly_map, pheromone, rows, cols, dt)
        elif sw.species == "sweeper":
            _step_sweeper(sw, ix, iy, local_anomaly, pheromone, rows, cols, dt)

        sw.x = float(np.clip(sw.x, 0, rows - 1))
        sw.y = float(np.clip(sw.y, 0, cols - 1))

        sw.trail.append((sw.x, sw.y))
        if len(sw.trail) > 80:
            sw.trail = sw.trail[-60:]


def _step_forager(sw, ix, iy, anom, phero, anomaly_map, pheromone, rows, cols, dt):
    """DiagnosticForager: wanders, slows near anomalies, deposits pheromone."""
    speed_scale = 1.0 - 0.85 * anom  # slow way down near anomalies

    # Chemotaxis: move toward higher anomaly score
    gx, gy = _local_gradient(anomaly_map, ix, iy, rows, cols)
    sw.vx += gx * 2.0 + random.gauss(0, 0.6)
    sw.vy += gy * 2.0 + random.gauss(0, 0.6)

    # Also attracted to existing pheromone (amplification)
    px, py = _local_gradient(pheromone, ix, iy, rows, cols)
    sw.vx += px * 0.5
    sw.vy += py * 0.5

    # Damping
    sw.vx *= 0.85
    sw.vy *= 0.85

    speed = math.sqrt(sw.vx ** 2 + sw.vy ** 2)
    max_speed = 2.5 * speed_scale
    if speed > max_speed:
        sw.vx *= max_speed / speed
        sw.vy *= max_speed / speed

    sw.x += sw.vx * dt
    sw.y += sw.vy * dt

    deposit = anom ** 1.5 * 0.15
    if deposit > 0.005:
        nix = int(np.clip(sw.x, 0, rows - 1))
        niy = int(np.clip(sw.y, 0, cols - 1))
        pheromone[nix, niy] = min(1.0, pheromone[nix, niy] + deposit)
        sw.pheromone_deposited += deposit
        if anom > 0.4:
            sw.anomalies_found += 1


def _step_calc_hunter(sw, ix, iy, anom, terrain, anomaly_map, pheromone, rows, cols, dt):
    """CalcificationHunter: seeks bright micro-spots (high local intensity spikes)."""
    brightness = terrain[ix, iy]
    is_bright_spot = brightness > 0.65 and anom > 0.3

    if is_bright_spot:
        deposit = min(0.25, brightness * anom * 0.5)
        pheromone[ix, iy] = min(1.0, pheromone[ix, iy] + deposit)
        sw.pheromone_deposited += deposit
        sw.anomalies_found += 1
        sw.vx *= 0.3
        sw.vy *= 0.3
        sw.vx += random.gauss(0, 0.3)
        sw.vy += random.gauss(0, 0.3)
    else:
        gx, gy = _local_gradient(anomaly_map, ix, iy, rows, cols)
        sw.vx += gx * 1.5 + random.gauss(0, 0.8)
        sw.vy += gy * 1.5 + random.gauss(0, 0.8)

    sw.vx *= 0.88
    sw.vy *= 0.88
    speed = math.sqrt(sw.vx ** 2 + sw.vy ** 2)
    if speed > 2.0:
        sw.vx *= 2.0 / speed
        sw.vy *= 2.0 / speed

    sw.x += sw.vx * dt
    sw.y += sw.vy * dt


def _step_margin_mapper(sw, ix, iy, anom, anomaly_map, pheromone, rows, cols, dt):
    """MarginMapper: traces the boundary of detected anomalous regions."""
    gx, gy = _local_gradient(anomaly_map, ix, iy, rows, cols)
    grad_mag = math.sqrt(gx ** 2 + gy ** 2)

    if grad_mag > 0.02:
        # Move perpendicular to gradient (trace the contour)
        sw.vx = -gy * 1.2 + random.gauss(0, 0.2)
        sw.vy = gx * 1.2 + random.gauss(0, 0.2)
        deposit = grad_mag * 0.3
        pheromone[ix, iy] = min(1.0, pheromone[ix, iy] + deposit)
        sw.pheromone_deposited += deposit
    else:
        sw.vx += random.gauss(0, 1.0)
        sw.vy += random.gauss(0, 1.0)
        px, py = _local_gradient(pheromone, ix, iy, rows, cols)
        sw.vx += px * 0.8
        sw.vy += py * 0.8

    sw.vx *= 0.82
    sw.vy *= 0.82
    speed = math.sqrt(sw.vx ** 2 + sw.vy ** 2)
    if speed > 1.8:
        sw.vx *= 1.8 / speed
        sw.vy *= 1.8 / speed

    sw.x += sw.vx * dt
    sw.y += sw.vy * dt


def _step_sweeper(sw, ix, iy, anom, pheromone, rows, cols, dt):
    """PatrolSweeper: systematic raster scan, deposits lightly everywhere."""
    sw.y += 1.5 * dt
    if sw.y >= cols - 1:
        sw.y = 0
        sw.x += 8  # next row band
        if sw.x >= rows - 1:
            sw.x = 0

    nix = int(np.clip(sw.x, 0, rows - 1))
    niy = int(np.clip(sw.y, 0, cols - 1))
    if anom > 0.2:
        pheromone[nix, niy] = min(1.0, pheromone[nix, niy] + anom * 0.05)
        sw.pheromone_deposited += anom * 0.05


def _local_gradient(matrix: np.ndarray, ix: int, iy: int, rows: int, cols: int) -> Tuple[float, float]:
    """Compute local gradient at (ix, iy) for chemotaxis."""
    gx = 0.0
    gy = 0.0
    if ix > 0 and ix < rows - 1:
        gx = float(matrix[ix + 1, iy] - matrix[ix - 1, iy]) * 0.5
    if iy > 0 and iy < cols - 1:
        gy = float(matrix[ix, iy + 1] - matrix[ix, iy - 1]) * 0.5
    return gx, gy


def evaporate_pheromone(pheromone: np.ndarray, decay: float = 0.997) -> None:
    """Decay pheromone each tick."""
    pheromone *= decay
