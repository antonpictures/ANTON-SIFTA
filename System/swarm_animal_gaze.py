# System/swarm_animal_gaze.py

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.ndimage import gaussian_filter, sobel


@dataclass
class AnimalGazeConfig:
    scouts: int = 80
    foveal_agents: int = 350

    peripheral_steps: int = 12
    foveal_steps: int = 30

    peripheral_sigma: float = 18.0
    inhibition_decay: float = 0.92
    inhibition_strength: float = 0.75

    motion_weight: float = 1.25
    edge_weight: float = 0.75
    novelty_weight: float = 0.55
    memory_penalty: float = 0.40

    scout_jump: int = 28
    foveal_window: int = 4

    eps: float = 1e-8


class SwarmAnimalGaze:
    """
    Animal-inspired active vision.

    Biology:
      peripheral scouts      -> rods / wide-field motion sense
      foveal swarm           -> cone-dense precision gaze
      inhibition_of_return   -> don't keep staring at same place
      motion saliency        -> animal threat/prey reflex
      edge saliency          -> object boundary detection
    """

    def __init__(self, width: int, height: int, cfg: AnimalGazeConfig | None = None):
        self.width = width
        self.height = height
        self.cfg = cfg or AnimalGazeConfig()

        self.prev_frame: np.ndarray | None = None
        self.saliency = np.zeros((height, width), dtype=np.float32)
        self.inhibition = np.zeros((height, width), dtype=np.float32)
        self.foveal_memory = np.zeros((height, width), dtype=np.float32)

    def reset(self):
        self.prev_frame = None
        self.saliency.fill(0)
        self.inhibition.fill(0)
        self.foveal_memory.fill(0)

    def _normalize(self, x: np.ndarray) -> np.ndarray:
        x = x.astype(np.float32)
        return (x - x.min()) / (x.max() - x.min() + self.cfg.eps)

    def _build_nutrient_landscape(self, frame: np.ndarray) -> np.ndarray:
        frame = self._normalize(frame)

        gx = sobel(frame, axis=1)
        gy = sobel(frame, axis=0)
        edges = self._normalize(np.sqrt(gx * gx + gy * gy))

        if self.prev_frame is None:
            motion = np.zeros_like(frame)
        else:
            motion = self._normalize(np.abs(frame - self.prev_frame))

        novelty = 1.0 / (1.0 + self.foveal_memory)

        nutrient = (
            self.cfg.motion_weight * motion
            + self.cfg.edge_weight * edges
            + self.cfg.novelty_weight * novelty
            - self.cfg.inhibition_strength * self.inhibition
        )

        nutrient = np.maximum(nutrient, 0.0)
        self.prev_frame = frame.copy()
        return self._normalize(nutrient)

    def glance(self, frame: np.ndarray) -> tuple[int, int]:
        nutrient = self._build_nutrient_landscape(frame)

        ys = np.random.randint(0, self.height, self.cfg.scouts).astype(np.float32)
        xs = np.random.randint(0, self.width, self.cfg.scouts).astype(np.float32)

        self.saliency.fill(0)

        for _ in range(self.cfg.peripheral_steps):
            for k in range(self.cfg.scouts):
                y, x = int(ys[k]), int(xs[k])
                r = self.cfg.scout_jump

                y0, y1 = max(0, y - r), min(self.height, y + r + 1)
                x0, x1 = max(0, x - r), min(self.width, x + r + 1)

                patch = nutrient[y0:y1, x0:x1]
                if patch.size == 0:
                    continue

                py, px = np.unravel_index(np.argmax(patch), patch.shape)
                ys[k] = y0 + py
                xs[k] = x0 + px

                self.saliency[int(ys[k]), int(xs[k])] += 1.0

        self.saliency = gaussian_filter(self.saliency, sigma=self.cfg.peripheral_sigma)
        target_y, target_x = np.unravel_index(np.argmax(self.saliency), self.saliency.shape)

        return int(target_y), int(target_x)

    def saccade(self, frame: np.ndarray, target_y: int, target_x: int) -> np.ndarray:
        nutrient = self._build_nutrient_landscape(frame)

        ys = np.clip(
            np.random.normal(target_y, 10, self.cfg.foveal_agents),
            0,
            self.height - 1,
        )
        xs = np.clip(
            np.random.normal(target_x, 10, self.cfg.foveal_agents),
            0,
            self.width - 1,
        )

        for _ in range(self.cfg.foveal_steps):
            for k in range(self.cfg.foveal_agents):
                y, x = int(ys[k]), int(xs[k])
                r = self.cfg.foveal_window

                y0, y1 = max(0, y - r), min(self.height, y + r + 1)
                x0, x1 = max(0, x - r), min(self.width, x + r + 1)

                food = nutrient[y0:y1, x0:x1]
                memory = self.foveal_memory[y0:y1, x0:x1]

                fitness = food - self.cfg.memory_penalty * memory

                py, px = np.unravel_index(np.argmax(fitness), fitness.shape)
                ys[k] = y0 + py
                xs[k] = x0 + px

                self.foveal_memory[int(ys[k]), int(xs[k])] += 1.0

        self._mark_inhibition(target_y, target_x)

        return np.column_stack((ys.astype(int), xs.astype(int)))

    def _mark_inhibition(self, y: int, x: int, radius: int = 80):
        self.inhibition *= self.cfg.inhibition_decay

        y0, y1 = max(0, y - radius), min(self.height, y + radius)
        x0, x1 = max(0, x - radius), min(self.width, x + radius)

        self.inhibition[y0:y1, x0:x1] += 1.0
        self.inhibition = self._normalize(gaussian_filter(self.inhibition, sigma=20))

    def observe(self, frame: np.ndarray) -> dict:
        y, x = self.glance(frame)
        points = self.saccade(frame, y, x)

        return {
            "target_y": y,
            "target_x": x,
            "foveal_points": points,
            "saliency": self.saliency.copy(),
            "memory": self.foveal_memory.copy(),
            "inhibition": self.inhibition.copy(),
        }
