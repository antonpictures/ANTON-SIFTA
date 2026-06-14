#!/usr/bin/env python3
"""Tests for MiMo feature-to-swimmer self-knowledge."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_mimo_swimmer_substrate as substrate
from System.swarm_model_body_self_knowledge import body_file_inventory, model_body_self_knowledge_block


def test_mimo_feature_map_contains_core_surfaces():
    rows = substrate.mimo_feature_swimmer_map()
    surfaces = {row["mimo_surface"] for row in rows}
    assert "$ subagent" in surfaces
    assert "@ attach file" in surfaces
    assert "/agents" in surfaces
    assert "provider/model settings" in surfaces
    for row in rows:
        assert row["alice_swimmer"]
        assert row["organ_files"]
        assert "receipt" in row["receipt_law"].lower()


def test_mimo_claim_matrix_truth_labels_mark_alice_gaps():
    rows = substrate.mimo_capability_claim_matrix()
    by_claim = {row["mimo_claim"]: row for row in rows}

    assert "Model-agent collaboration" in by_claim
    agent_row = by_claim["Model-agent collaboration"]
    assert "Alice-native organ swimmers" in agent_row["alice_answer"]
    assert "System/swimmer_registry.py" in agent_row["evidence_files"]
    assert "receipt" in agent_row["gap"].lower()

    context_row = by_claim["Unlimited context / knowledge accumulates automatically"]
    assert context_row["truth_label"] == "OPERATIONAL_BOUNDED_STIGMERGIC_MEMORY_NOT_UNLIMITED"
    assert "No literal unlimited context claim" in context_row["alice_answer"]
    assert ".sifta_state/ide_stigmergic_trace.jsonl" in context_row["evidence_files"]


def test_learning_block_renders_mimo_claim_matrix():
    block = substrate.render_mimo_swimmer_learning_block()
    assert "MIMO WEBSITE CLAIMS -> ALICE BODY TRUTH" in block
    assert "Model-agent collaboration" in block
    assert "OPERATIONAL_BOUNDED_STIGMERGIC_MEMORY_NOT_UNLIMITED" in block


def test_obliteratus_project_card_observed_from_local_checkout(tmp_path):
    root = tmp_path / "OBLITERATUS"
    (root / "obliteratus").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "README.md").write_text(
        "OBLITERATUS implements abliteration and refusal direction removal.",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        """
[project]
name = "obliteratus"
version = "0.1.2"
description = "Master Ablation Suite for HuggingFace transformers"
license = {text = "AGPL-3.0-or-later"}

[project.scripts]
obliteratus = "obliteratus.cli:main"
""".strip(),
        encoding="utf-8",
    )
    (root / "app.py").write_text("", encoding="utf-8")
    (root / "obliteratus" / "cli.py").write_text("", encoding="utf-8")
    (root / "obliteratus" / "abliterate.py").write_text("", encoding="utf-8")
    (root / "docs" / "RESEARCH_SURVEY.md").write_text("", encoding="utf-8")

    card = substrate.obliteratus_project_card(root)
    assert card["status"] == "observed"
    assert card["truth_label"] == "OBSERVED"
    assert card["version"] == "0.1.2"
    assert "abliteration" in card["purpose"].lower()
    assert "obliteratus/cli.py" in card["key_files"]


def test_body_self_knowledge_includes_mimo_swimmer_block():
    files = body_file_inventory(key_dirs=("System",))
    assert isinstance(files, list)
    block = model_body_self_knowledge_block(max_rows=1)
    assert "MIMO FEATURE SWIMMERS" in block
    assert "OBLITERATUS MEMORY" in block
