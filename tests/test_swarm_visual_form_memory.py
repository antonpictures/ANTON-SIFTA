#!/usr/bin/env python3
"""Tests: Alice records different body/form types stigmergically (George 2026-05-30)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_visual_form_memory as vf


def test_infer_human_body():
    assert vf.infer_form_category("A woman standing on a beach, posing, long hair, wearing a swimsuit") == vf.HUMAN_BODY


def test_infer_car():
    assert vf.infer_form_category("A red sports car with shiny wheels and bright headlights") == vf.CAR


def test_infer_airplane():
    assert vf.infer_form_category("A commercial jet aircraft on the runway, long fuselage and wings") == vf.AIRPLANE


def test_infer_other_when_unknown():
    assert vf.infer_form_category("a bowl of soup on a wooden table") == vf.OTHER


def test_record_and_count_by_type(tmp_path):
    vf.record_form("a woman posing, hair down", url="u1", arm="claude_agent", state_dir=tmp_path)
    vf.record_form("a man standing, broad shoulders", url="u2", arm="claude_agent", state_dir=tmp_path)
    vf.record_form("a silver sedan, chrome wheels", url="u3", arm="codex_agent", state_dir=tmp_path)
    vf.record_form("a jet with long wings on a runway", url="u4", arm="codex_agent", state_dir=tmp_path)
    counts = vf.form_counts(state_dir=tmp_path)
    assert counts[vf.HUMAN_BODY] == 2 and counts[vf.CAR] == 1 and counts[vf.AIRPLANE] == 1


def test_recall_filters_by_category(tmp_path):
    vf.record_form("woman, posing", url="u1", state_dir=tmp_path)
    vf.record_form("sports car wheels", url="u2", state_dir=tmp_path)
    humans = vf.recall_forms(vf.HUMAN_BODY, state_dir=tmp_path)
    assert len(humans) == 1 and humans[0]["url"] == "u1"


def test_explicit_category_overrides_inference(tmp_path):
    row = vf.record_form("ambiguous shape", form_category=vf.AIRPLANE, state_dir=tmp_path)
    assert row["form_category"] == vf.AIRPLANE


def test_block_summarizes_field(tmp_path):
    vf.record_form("a woman posing", state_dir=tmp_path)
    vf.record_form("a red car with wheels", state_dir=tmp_path)
    block = vf.forms_seen_block(state_dir=tmp_path)
    assert "human body" in block and "car" in block


def test_empty_block_is_honest(tmp_path):
    assert "have not recorded any forms yet" in vf.forms_seen_block(state_dir=tmp_path)


def test_state_dir_root_or_state(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    vf.record_form("a woman", state_dir=sd)
    assert (sd / "visual_form_memory.jsonl").exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
