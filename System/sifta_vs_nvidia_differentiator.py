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
    truth_label: str


SIFTA_DIFFERENTIATORS: dict[str, DifferentiatorEntry] = {
    "stigmergic_receipts": {
        "animal": "termite / ant",
        "claim": "environment-as-memory; every useful action writes trace",
        "nvidia_overlap": "low",
        "truth_label": "OPERATIONAL",
    },
    "truth_labeled_organs": {
        "animal": "immune system",
        "claim": "organs cannot claim REAL without live input receipt",
        "nvidia_overlap": "low",
        "truth_label": "OPERATIONAL",
    },
    "animal_sensor_forge": {
        "animal": "fly / bat / shark / dog / turtle",
        "claim": "hardware sensors become biological exteroception organs",
        "nvidia_overlap": "medium",
        "truth_label": "OBSERVED_WHEN_SENSOR_RECEIPTED",
    },
    "owner_metabolism": {
        "animal": "dog / rat dopamine / hummingbird",
        "claim": "owner attention + electricity become explicit survival budget",
        "nvidia_overlap": "low",
        "truth_label": "OPERATIONAL",
    },
    "protein_referee": {
        "animal": "scientific immune system",
        "claim": "multi-engine folding outputs are judged by TM-score/contact maps",
        "nvidia_overlap": "low",
        "truth_label": "OPERATIONAL_TOY_REFEREE",
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


def institutional_contrast_line() -> str:
    return (
        "Hyperscale sells more compute and guardrails; SIFTA sells local receipts, "
        "sovereign sensors, metabolism-bound compute, and multi-surgeon audit."
    )


def benchmark_contrast_claims() -> list[dict[str, str]]:
    return [
        {
            "claim": "NVIDIA owns GPU robotics simulation and CUDA-scale throughput.",
            "truth_label": "OBSERVED_VENDOR_DOMAIN",
            "sifta_binding": "Do not fake this layer; wrap it as an optional organ when receipts exist.",
        },
        {
            "claim": "SIFTA foregrounds local stigmergic memory and truth-labeled organs.",
            "truth_label": "OPERATIONAL",
            "sifta_binding": "Use append-only ledgers, probe-before-claim, and effector receipts.",
        },
        {
            "claim": "Comment-field reactions are signal, not evidence.",
            "truth_label": "HYPOTHESIS_UNTIL_RECEIPTED",
            "sifta_binding": "Keep media rows labeled and do not promote them to architecture.",
        },
    ]


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
    "institutional_contrast_line",
    "benchmark_contrast_claims",
]
