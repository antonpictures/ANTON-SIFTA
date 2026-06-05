#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from System import swarm_novelty_queue as q


def test_drops_generic_summary_shape():
    row = q.classify_novelty(
        "The observed data stream indicates a technical discussion focusing on hardware and AI deployment. "
        "Key points include local installation and model setup."
    )
    assert row["useful"] is False
    assert row["is_summary"] is True


def test_keeps_sifta_body_upgrade_idea():
    row = q.classify_novelty(
        "Hey George, this is a good idea for my body code; I could add an organ for browser attention."
    )
    assert row["useful"] is True
    assert row["kind"] == "sifta_upgrade_idea"


def test_keeps_grounded_world_question():
    row = q.classify_novelty("Hey George, did you get a cat?")
    assert row["useful"] is True
    assert row["kind"] == "world_question"


def test_capture_writes_only_useful_items(tmp_path, monkeypatch):
    monkeypatch.setattr(q, "_QUEUE", tmp_path / "novelty_queue.jsonl")
    monkeypatch.setattr(q, "_DIARY", tmp_path / "episodic_diary.jsonl")

    dropped = q.capture_novelty("The video discusses model setup and key points include themes.")
    kept = q.capture_novelty("That software pattern would help my browser world model.")

    assert dropped["useful"] is False
    assert kept["useful"] is True
    assert (tmp_path / "novelty_queue.jsonl").read_text(encoding="utf-8").count("NOVELTY_QUEUE_V1") == 1
    assert "browser world model" in q.novelty_prompt_line()
