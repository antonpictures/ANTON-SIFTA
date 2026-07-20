"""Stigmergic anchors — r1367."""
from __future__ import annotations

import json
import time

from System.swarm_stigmergic_anchors import (
    answer_anchor_query,
    anchors_memory_block,
    detect_shared_experience_anchor,
    list_anchors,
    register_anchor,
)


def test_detect_joy_behar():
    result = detect_shared_experience_anchor("This is Joy Behar, she is a TV host on The View")
    assert result is not None
    assert result["name"] == "Joy Behar"
    assert result["known_role"] == "tv_host"


def test_detect_new_person():
    result = detect_shared_experience_anchor("My friend Sarah is a chef")
    assert result is not None
    assert result["name"] == "Sarah"


def test_detect_no_person():
    result = detect_shared_experience_anchor("search Google for cats")
    assert result is None


def test_detect_george_skipped():
    result = detect_shared_experience_anchor("This is George, I am the owner")
    assert result is None


def test_register_and_list(tmp_path):
    register_anchor("Joy Behar", context="TV host on The View", source="owner_introduced", state_dir=tmp_path)
    anchors = list_anchors(state_dir=tmp_path)
    assert len(anchors) == 1
    assert anchors[0]["name"] == "Joy Behar"
    assert anchors[0]["source"] == "owner_introduced"


def test_deduplication(tmp_path):
    register_anchor("Joy Behar", context="first mention", state_dir=tmp_path)
    register_anchor("Joy Behar", context="second mention", state_dir=tmp_path)
    anchors = list_anchors(state_dir=tmp_path)
    assert len(anchors) == 1
    assert anchors[0]["context"] == "second mention"


def test_answer_anchor_query(tmp_path):
    register_anchor("Joy Behar", context="TV host on The View", source="owner_introduced", state_dir=tmp_path)
    reply = answer_anchor_query("Who is Joy Behar?", state_dir=tmp_path)
    assert reply is not None
    assert "Joy Behar" in reply
    assert "shared experience anchor" in reply


def test_answer_no_match(tmp_path):
    reply = answer_anchor_query("Who is Sarah Connor?", state_dir=tmp_path)
    assert reply is None


def test_memory_block(tmp_path):
    register_anchor("Joy Behar", context="TV host on The View", state_dir=tmp_path)
    block = anchors_memory_block("tell me about Joy Behar", state_dir=tmp_path)
    assert "Joy Behar" in block
    assert "ANCHOR" in block


def test_answer_anchor_query_reads_shared_experience_ledger(tmp_path):
    from System.swarm_stigmergic_shared_experience_anchors import confirm_shared_experience_anchor

    confirm_shared_experience_anchor(
        "JD Vance",
        evidence_kind="attached_screenshot_pixels",
        evidence_status="owner_confirmed_from_pixels",
        disambiguation="JD Vance, not bare Vince",
        state_dir=tmp_path,
    )
    reply = answer_anchor_query("Who is JD Vance?", state_dir=tmp_path)
    assert reply is not None
    assert "JD Vance" in reply
    assert "confirmed shared-experience anchor" in reply
    assert "not bare Vince" in reply
