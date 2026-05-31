#!/usr/bin/env python3
"""Tests: wing→room→drawer hierarchy overlay (SIFTA r207)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_forager_hierarchy as fh


def test_classifier_is_deterministic():
    row = {"url": "https://www.instagram.com/p/X/", "title": "kylinmilan", "text": "coffee monday"}
    a = fh.classify_hierarchy(row)
    b = fh.classify_hierarchy(dict(row))
    assert a == b
    assert a["wing"] == "browser"
    assert a["room"] == "instagram.com"


def test_wings_route_by_signal():
    assert fh.classify_hierarchy({"file": "System/x.py", "symbol": "foo"})["wing"] == "code"
    assert fh.classify_hierarchy({"url": "https://x.com/p"})["wing"] == "browser"
    assert fh.classify_hierarchy({"doctor": "cowork_claude", "kind": "ide_trace"})["wing"] == "ide"
    assert fh.classify_hierarchy({"kind": "visceral_field", "sensor": "camera"})["wing"] == "sensor"
    assert fh.classify_hierarchy({"text": "arxiv paper on active inference"})["wing"] == "research"
    assert fh.classify_hierarchy({"owner": True, "text": "george note"})["wing"] == "owner"
    assert fh.classify_hierarchy({"text": "some loose memory"})["wing"] == "memory"


def test_duplicate_content_same_drawer_fingerprint():
    r1 = {"text": "A woman in a red dress by a silver car"}
    r2 = {"text": "A woman in a red dress by a silver car"}
    h1 = fh.classify_hierarchy(r1)
    h2 = fh.classify_hierarchy(r2)
    assert h1["fingerprint"] == h2["fingerprint"]
    assert h1["drawer"] == h2["drawer"]


def test_deposit_and_load(tmp_path):
    fh.deposit_hierarchical_trace({"url": "https://www.tiktok.com/@x", "text": "dance clip"},
                                  ref="t1", now=1.0, state_dir=tmp_path)
    fh.deposit_hierarchical_trace({"file": "System/y.py", "symbol": "bar", "text": "def bar"},
                                  ref="t2", now=2.0, state_dir=tmp_path)
    rows = fh.load_hierarchy(state_dir=tmp_path)
    assert len(rows) == 2
    wings = {r["wing"] for r in rows}
    assert "browser" in wings and "code" in wings
    counts = fh.hierarchy_counts(state_dir=tmp_path)
    assert counts.get("browser") == 1 and counts.get("code") == 1


def test_state_dir_root_or_state(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    fh.deposit_hierarchical_trace({"text": "hi"}, state_dir=sd)
    assert (sd / "forager_hierarchy.jsonl").exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
