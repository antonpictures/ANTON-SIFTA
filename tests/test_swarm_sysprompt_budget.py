#!/usr/bin/env python3
"""Tests: system-prompt budget governor (SIFTA r216).

George 2026-05-31: a Kimi turn hung ~90s on a 141k-char system prompt. The governor
bounds the prompt without dropping small core-grounding blocks; only runaway excerpt
blocks get trimmed."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System.swarm_sysprompt_budget import clamp_prompt_parts as C


def test_under_budget_is_untouched():
    parts = ["id firewall", "effector truth", "runtime contract"]
    out, r = C(parts, total_max=48000)
    assert out == parts
    assert r["applied"] is False


def test_runaway_block_capped_core_intact():
    parts = ["IDENTITY core", "EFFECTOR truth", "X" * 200000, "runtime contract"]
    out, r = C(parts, total_max=48000, per_block_max=6000)
    assert out[0] == parts[0] and out[1] == parts[1] and out[3] == parts[3]
    assert len(out[2]) <= 6000
    assert r["final_chars"] < r["orig_chars"]


def test_total_budget_enforced_no_block_dropped():
    parts = [f"block{i} " + ("y" * 9000) for i in range(20)]
    out, r = C(parts, total_max=48000, per_block_max=6000)
    assert len(out) == len(parts)
    total = sum(len(p) for p in out) + 2 * (len(out) - 1)
    assert total <= 48000


def test_deterministic():
    parts = [f"b{i} " + ("y" * 9000) for i in range(20)]
    a, _ = C(parts, total_max=48000)
    b, _ = C(parts, total_max=48000)
    assert a == b


def test_min_block_floor_keeps_grounding_under_extreme_pressure():
    parts = ["G" * 9000 for _ in range(100)]
    out, r = C(parts, total_max=5000, per_block_max=6000, min_block=300)
    assert len(out) == 100
    assert all(len(p) >= 1 for p in out)  # nothing vanishes


def test_empty_parts_are_dropped_not_kept():
    parts = ["real", "", None, "also real"]  # type: ignore
    out, _ = C([p for p in parts if p is not None], total_max=48000)
    assert "" not in out


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
