"""Battlefield registry — URLs and triple-IDE agreement string."""

from __future__ import annotations

import json

from System.nvidia_open_assets_registry import (
    NVIDIA_OPEN_ASSETS,
    TRIPLE_IDE_AGREEMENT_ONE_LINER,
    asset_by_key,
    hf_cli_download_gr00t_sim_dataset,
    to_manifest_dict,
)


def test_all_urls_https():
    for a in NVIDIA_OPEN_ASSETS:
        assert a.url.startswith("https://"), a.key


def test_gr00t_dataset_row_present():
    a = asset_by_key("gr00t_x_embodiment_sim")
    assert a is not None
    assert "huggingface.co/datasets" in a.url


def test_agreement_mentions_triple_doctors():
    s = TRIPLE_IDE_AGREEMENT_ONE_LINER.lower()
    assert "cg55m" in s and "c55m" in s and "ag31" in s


def test_manifest_json_roundtrip():
    d = to_manifest_dict()
    json.dumps(d)
    assert len(d["assets"]) == len(NVIDIA_OPEN_ASSETS)


def test_hf_cli_snippets_non_empty():
    cmds = hf_cli_download_gr00t_sim_dataset()
    assert any("PhysicalAI-Robotics-GR00T-X-Embodiment-Sim" in c for c in cmds)
