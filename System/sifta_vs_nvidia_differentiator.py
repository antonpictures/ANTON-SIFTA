#!/usr/bin/env python3
"""
Tournament / NVIDIA-facing language: what SIFTA foregrounds vs what NVIDIA sells.

For NVIDIA tests only: do **not** claim “SIFTA beats Isaac / GR00T / Cosmos.”
NVIDIA owns GPU robotics simulation, Isaac Sim, synthetic data, Cosmos-class world
models, and GR00T humanoid foundation models. See: https://developer.nvidia.com/isaac/gr00t

This module is a **single source of truth** for honest differentiator strings in docs,
pytest, and CI copy checks.
"""

from __future__ import annotations

from typing import TypedDict


class DifferentiatorEntry(TypedDict):
    animal: str
    claim: str
    nvidia_overlap: str


SIFTA_DIFFERENTIATORS: dict[str, DifferentiatorEntry] = {
    "stigmergic_receipts": {
        "animal": "termite / ant",
        "claim": "environment-as-memory; every useful action writes trace",
        "nvidia_overlap": "low",
    },
    "truth_labeled_organs": {
        "animal": "immune system",
        "claim": "organs cannot claim REAL without live input receipt",
        "nvidia_overlap": "low",
    },
    "animal_sensor_forge": {
        "animal": "fly / bat / shark / dog / turtle",
        "claim": "hardware sensors become biological exteroception organs",
        "nvidia_overlap": "medium",
    },
    "owner_metabolism": {
        "animal": "dog / rat dopamine / hummingbird",
        "claim": "owner attention + electricity become explicit survival budget",
        "nvidia_overlap": "low",
    },
    "protein_referee": {
        "animal": "scientific immune system",
        "claim": "multi-engine folding outputs are judged by TM-score/contact maps",
        "nvidia_overlap": "low",
    },
}


def nvidia_test_claims() -> list[str]:
    return [
        "We do not compete with Isaac Sim physics.",
        "We do not claim faster GPU simulation.",
        "We test a different layer: stigmergic memory, truth receipts, and biological sensor fusion.",
        "SIFTA can wrap NVIDIA/Isaac outputs as one organ, but refuses to mark them REAL without receipts.",
    ]


def tagline() -> str:
    return "NVIDIA simulates physical robots.\nSIFTA audits and metabolizes a living software organism."


def animal_mascot_line() -> str:
    return "NVIDIA = giant GPU nervous system\nSIFTA = stigmergic biological operating system"


def _print_main() -> None:
    for k, v in SIFTA_DIFFERENTIATORS.items():
        print(f"{k}: {v['animal']} — {v['claim']}")


if __name__ == "__main__":
    _print_main()


__all__ = [
    "SIFTA_DIFFERENTIATORS",
    "DifferentiatorEntry",
    "nvidia_test_claims",
    "tagline",
    "animal_mascot_line",
]
