#!/usr/bin/env python3
"""
NVIDIA open assets — URLs, licenses, and SIFTA hook points (triple-IDE battlefield).

Covenant: NPPL; no weapons. Tournament §8: honest NVIDIA flex only.
Do not add HF downloads to default CI — use mocks / --optional integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final


@dataclass(frozen=True)
class NvidiaOpenAsset:
    """One row in the battlefield table."""

    key: str
    title: str
    url: str
    license_note: str
    sifta_hook: str
    priority: str  # "P0" | "P1" | "P2"


NVIDIA_OPEN_ASSETS: Final[tuple[NvidiaOpenAsset, ...]] = (
    NvidiaOpenAsset(
        key="hf_nvidia_org",
        title="Hugging Face — NVIDIA organization",
        url="https://huggingface.co/nvidia",
        license_note="Per-repository (model cards, dataset cards)",
        sifta_hook="Discovery + version pins for Sense Forge / Event 74 / cortex",
        priority="P0",
    ),
    NvidiaOpenAsset(
        key="gr00t_n17_3b",
        title="Isaac GR00T N1.7 — 3B open weights",
        url="https://huggingface.co/nvidia/GR00T-N1.7-3B",
        license_note="NVIDIA Open Model License (see model card)",
        sifta_hook="VLA tensor vocabulary reference; post-train only with GO + receipts",
        priority="P1",
    ),
    NvidiaOpenAsset(
        key="gr00t_x_embodiment_sim",
        title="Physical AI — GR00T X-Embodiment Sim trajectories",
        url="https://huggingface.co/datasets/nvidia/PhysicalAI-Robotics-GR00T-X-Embodiment-Sim",
        license_note="CC-BY-4.0 (verify on dataset card before redistribution)",
        sifta_hook="Ground truth trajectories vs Event 74 ArmSegment / gradient paths (falsifiable)",
        priority="P0",
    ),
    NvidiaOpenAsset(
        key="isaac_lab",
        title="Isaac Lab (robot learning on Isaac Sim)",
        url="https://github.com/isaac-sim/IsaacLab",
        license_note="Apache-2.0 / BSD-3-Clause (see repo SPDX)",
        sifta_hook="`omni.isaac.core` — `IsaacStigmergicStub.is_available()` wire target",
        priority="P0",
    ),
    NvidiaOpenAsset(
        key="isaac_groot_repo",
        title="Isaac-GR00T reference implementation",
        url="https://github.com/NVIDIA/Isaac-GR00T",
        license_note="See repository LICENSE",
        sifta_hook="Training / eval harness parity with HF weights",
        priority="P1",
    ),
    NvidiaOpenAsset(
        key="nvidia_warp",
        title="NVIDIA Warp (GPU Python)",
        url="https://github.com/NVIDIA/warp",
        license_note="BSD-3-Clause",
        sifta_hook="Accelerate `VoxelField.fill_goal_potential` hot paths (optional dep)",
        priority="P0",
    ),
    NvidiaOpenAsset(
        key="curobo",
        title="cuRobo — CUDA robot motion / collision",
        url="https://github.com/NVlabs/curobo",
        license_note="See repository LICENSE (verify before ship)",
        sifta_hook="Optional trajectory optimizer feeding same receipt pipeline as Event 74",
        priority="P1",
    ),
    NvidiaOpenAsset(
        key="cosmos_platform",
        title="NVIDIA Cosmos — physical AI WFMs",
        url="https://developer.nvidia.com/cosmos",
        license_note="NVIDIA Open Model License for Cosmos WFMs (per developer page)",
        sifta_hook="Synthetic / curation lane for vision + future sim-to-real",
        priority="P2",
    ),
    NvidiaOpenAsset(
        key="gr00t_paper",
        title="GR00T N1 paper (architecture reference)",
        url="https://arxiv.org/abs/2503.14734",
        license_note="arXiv preprint",
        sifta_hook="Event 74 / §7.1 literature cross-link",
        priority="P1",
    ),
)


TRIPLE_IDE_AGREEMENT_ONE_LINER: Final[str] = (
    "CG55M, C55M, and AG31 treat NVIDIA open weights, Isaac Lab, Warp, cuRobo, and Cosmos "
    "as optional SIFTA organs wired through truth labels and receipts — never as a bypass "
    "of Predator registration or NPPL."
)


def asset_by_key(key: str) -> NvidiaOpenAsset | None:
    for a in NVIDIA_OPEN_ASSETS:
        if a.key == key:
            return a
    return None


def hf_cli_download_gr00t_sim_dataset() -> list[str]:
    """Human / Architect-run commands — not executed in CI."""
    return [
        "huggingface-cli download nvidia/PhysicalAI-Robotics-GR00T-X-Embodiment-Sim --repo-type dataset",
        "# Optional: HF_HUB_ENABLE_HF_TRANSFER=1 for faster pulls",
    ]


def to_manifest_dict() -> dict[str, Any]:
    """JSON-serialisable summary for UI or trace payloads."""
    return {
        "triple_ide_agreement": TRIPLE_IDE_AGREEMENT_ONE_LINER,
        "assets": [
            {
                "key": a.key,
                "title": a.title,
                "url": a.url,
                "license_note": a.license_note,
                "sifta_hook": a.sifta_hook,
                "priority": a.priority,
            }
            for a in NVIDIA_OPEN_ASSETS
        ],
    }


__all__ = [
    "NvidiaOpenAsset",
    "NVIDIA_OPEN_ASSETS",
    "TRIPLE_IDE_AGREEMENT_ONE_LINER",
    "asset_by_key",
    "hf_cli_download_gr00t_sim_dataset",
    "to_manifest_dict",
]
