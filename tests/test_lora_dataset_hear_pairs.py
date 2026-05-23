#!/usr/bin/env python3
"""Teach Alice to Hear pairs must feed the LoRA dataset builder."""

from __future__ import annotations

import json
from pathlib import Path

from System import swarm_lora_dataset_builder as builder


def test_extract_hear_training_pairs_builds_transcript_correction_rows(tmp_path: Path):
    pairs_path = tmp_path / "hear_training_pairs.jsonl"
    pairs_path.write_text(
        json.dumps({
            "schema": "HEAR_TRAINING_PAIR_V1",
            "whisper_text": "hello ello im hear",
            "ground_truth": "hello hello I am here",
            "alice_judgment": "CORRECTION",
        }) + "\n",
        encoding="utf-8",
    )

    rows = builder.extract_hear_training_pairs(pairs_path)

    assert len(rows) == 1
    assert rows[0]["source"] == "hear_training_pairs"
    assert "Correct this local microphone transcript" in rows[0]["user"]
    assert "hello ello im hear" in rows[0]["user"]
    assert rows[0]["assistant"] == "hello hello I am here"


def test_extract_hear_training_pairs_skips_rows_without_ground_truth(tmp_path: Path):
    pairs_path = tmp_path / "hear_training_pairs.jsonl"
    pairs_path.write_text(
        json.dumps({"whisper_text": "uncertain", "ground_truth": ""}) + "\n",
        encoding="utf-8",
    )

    assert builder.extract_hear_training_pairs(pairs_path) == []
