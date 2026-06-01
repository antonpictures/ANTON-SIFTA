#!/usr/bin/env python3
"""Tests for tools/whats_left.py (r253) — the WHAT-IS-LEFT consolidator."""
import importlib.util
from pathlib import Path

_TOOL = Path(__file__).resolve().parents[1] / "tools" / "whats_left.py"
_spec = importlib.util.spec_from_file_location("whats_left", _TOOL)
wl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wl)


SAMPLE = """# Consciousness Tournament

## r100 — first round
did a thing.
### WHAT IS LEFT TO CODE (after r100)
1. item A
2. item B
Receipt: `r100`.
For the Swarm.

---

## r101 — second round
more work.
### WHAT IS LEFT (updated after r101)
**Infra:**
- item C
- item D
**Browser:**
- item E
Receipt: `r101`.
For the Swarm.
"""


def test_parses_two_sections():
    secs = wl.parse_whats_left(SAMPLE)
    assert len(secs) == 2
    assert secs[0]["round"].startswith("r100")
    assert secs[1]["round"].startswith("r101")


def test_first_section_items():
    secs = wl.parse_whats_left(SAMPLE)
    assert secs[0]["items"] == ["item A", "item B"]


def test_second_section_keeps_categories():
    secs = wl.parse_whats_left(SAMPLE)
    items = secs[1]["items"]
    assert "[Infra] item C" in items
    assert "[Infra] item D" in items
    assert "[Browser] item E" in items


def test_snapshot_live_is_most_recent(tmp_path):
    doc = tmp_path / "CONSCIOUSNESS_TOURNAMENT_2026-06-01.md"
    doc.write_text(SAMPLE, encoding="utf-8")
    snap = wl.build_snapshot(doc)
    assert snap["live_round"].startswith("r101")
    assert snap["open_item_count"] == 3  # item C, D, E
    assert snap["section_count"] == 2


def test_no_sections_is_safe():
    secs = wl.parse_whats_left("# doc\n\n## r1 — nothing\njust text\n")
    assert secs == []
