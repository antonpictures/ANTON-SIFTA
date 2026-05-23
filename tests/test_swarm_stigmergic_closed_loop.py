"""Tests for Event 98c stigmergic closed-loop heal conductor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_stigmergic_closed_loop as loop


def _tick(*, tick_id: str = "bb-heal-1", td_value: float = 0.55) -> dict:
    return {
        "event": "body_brain_tick",
        "tick_id": tick_id,
        "td_value": td_value,
        "danger_state": 0.05,
        "drive_state": "explore",
        "metabolic_mode": "GREEN_GROW",
        "action": {"type": "explore", "target": "stigmergic_probe"},
        "result": {"status": "completed", "latency": 0.04, "energy_used": 0.02},
    }


def _jsonl_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_heal_closed_loop_writes_receipt_backed_multisensory_tick(tmp_path: Path) -> None:
    base = _tick(td_value=0.55)

    result = loop.heal_closed_loop(base, state_root=tmp_path, duration_s=0.08)
    row = result["row"]
    receipt = result["receipt"]

    assert row["event"] == "body_brain_tick"
    assert row["truth_label"] == loop.TRUTH_LABEL
    assert row["closed_loop_truth_label"] == loop.TRUTH_LABEL
    assert row["closed_loop_heal_applied"] is True
    assert row["visual_receipt_backed"] is True
    assert row["cochlea_receipt_backed"] is True
    assert row["multisensory_integrated"] is True
    assert row["td_value"] > base["td_value"]
    assert row["closed_loop_td_delta"] > 0.0
    assert row["raw_audio_logged"] is False

    assert receipt["event"] == loop.EVENT_NAME
    assert receipt["status"] == loop.STATUS_HEALED
    assert receipt["visual_receipt_backed"] is True
    assert receipt["cochlea_receipt_backed"] is True
    assert receipt["multisensory_integrated"] is True
    assert receipt["raw_audio_logged"] is False

    memory_rows = _jsonl_rows(tmp_path / "body_brain_memory.jsonl")
    phenotype_rows = _jsonl_rows(tmp_path / "visual_phenotype_uniforms.jsonl")
    cochlea_rows = _jsonl_rows(tmp_path / "stigmergic_cochlea.jsonl")
    receipt_rows = _jsonl_rows(tmp_path / "stigmergic_closed_loop_heal.jsonl")

    assert memory_rows[-1]["truth_label"] == loop.TRUTH_LABEL
    assert phenotype_rows[-1]["receipt_backed"] is True
    assert cochlea_rows[-1]["raw_audio_logged"] is False
    assert receipt_rows[-1]["tick_id"] == base["tick_id"]


def test_heal_latest_closed_loop_reads_memory_tail_and_appends_final(tmp_path: Path) -> None:
    mem_path = tmp_path / "body_brain_memory.jsonl"
    mem_path.write_text(json.dumps(_tick(tick_id="old", td_value=0.1)) + "\n", encoding="utf-8")
    latest = _tick(tick_id="latest", td_value=0.6)
    with mem_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(latest) + "\n")

    result = loop.heal_latest_closed_loop(state_root=tmp_path, memory_path=mem_path)

    assert result["receipt"]["tick_id"] == "latest"
    rows = _jsonl_rows(mem_path)
    assert len(rows) == 3
    assert rows[-1]["tick_id"] == "latest"
    assert rows[-1]["truth_label"] == loop.TRUTH_LABEL


def test_closed_loop_rejects_non_receipt_backed_tick(tmp_path: Path) -> None:
    bad = _tick()
    bad.pop("td_value")

    with pytest.raises(ValueError, match="td_value"):
        loop.heal_closed_loop(bad, state_root=tmp_path)

    assert not (tmp_path / "stigmergic_closed_loop_heal.jsonl").exists()
