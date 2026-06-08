#!/usr/bin/env python3
"""r639: the browser skill card is generated from the live body, small, and honest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from System.swarm_browser_skill_teaching import (  # noqa: E402
    browser_skill_block,
    browser_tool_inventory,
    browser_skill_teaching_pairs,
)


def test_inventory_is_marker_verified_and_nonempty():
    inv = browser_tool_inventory()
    assert inv, "at least one browser hand must exist in the live source"
    labels = " ".join(t["tool"].lower() for t in inv)
    assert "back" in labels and "search" in labels
    for t in inv:
        assert (Path(__file__).resolve().parents[1] / t["organ"]).exists()


def test_block_is_compact_and_grounded():
    block = browser_skill_block()
    assert len(block) <= 1400, f"card must stay prompt-cheap, got {len(block)}"
    low = block.lower()
    assert "browser hands" in low
    assert "receipt" in low  # the doctrine line survives
    assert "url" in low  # web anatomy present


def test_teaching_pairs_shape_and_dedupe():
    pairs = browser_skill_teaching_pairs(max_pairs=10)
    # ledgers may be empty in a fresh checkout — shape check only when rows exist
    keys = set()
    for p in pairs:
        assert p["prompt"].startswith("George: ")
        assert "browser hand" in p["completion"]
        k = (p["completion"],)
        assert k not in keys, "stigmergic dedupe: no repeated exemplars"
        keys.add(k)


if __name__ == "__main__":
    test_inventory_is_marker_verified_and_nonempty()
    test_block_is_compact_and_grounded()
    test_teaching_pairs_shape_and_dedupe()
    print("ALL OK")
