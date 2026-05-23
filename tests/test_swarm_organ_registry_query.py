from __future__ import annotations

import json
from pathlib import Path

from System.swarm_organ_query import query_organs, summary_for_query
from System.swarm_organ_registry import build_organ_map, refresh_organ_registry, summary_for_prompt


def _write_module(system_dir: Path, name: str, text: str) -> None:
    system_dir.mkdir(parents=True, exist_ok=True)
    (system_dir / name).write_text(text, encoding="utf-8")


def test_registry_discovers_modules_ledgers_lanes_and_health(tmp_path: Path) -> None:
    system_dir = tmp_path / "System"
    _write_module(
        system_dir,
        "swarm_camera_eye.py",
        '"""Camera vision organ."""\nLEDGER_NAME = "visual_stigmergy.jsonl"\n',
    )
    (tmp_path / "visual_stigmergy.jsonl").write_text(json.dumps({"ts": 123}) + "\n", encoding="utf-8")

    snapshot = build_organ_map(state_dir=tmp_path, system_dir=system_dir, now=123.0)

    assert snapshot["organ_count"] == 1
    organ = snapshot["organs"][0]
    assert organ["organ_id"] == "camera_eye"
    assert "visual_stigmergy.jsonl" in organ["owned_ledgers"]
    assert "vision" in organ["input_lanes"]
    assert organ["health"]["status"] == "RECENT_RECEIPTS"


def test_refresh_writes_append_only_receipt_and_snapshot(tmp_path: Path) -> None:
    system_dir = tmp_path / "System"
    _write_module(system_dir, "swarm_memory_journal.py", '"""Memory journal organ."""\nLOG = "alice_life_journal.jsonl"\n')

    snapshot = refresh_organ_registry(state_dir=tmp_path, system_dir=system_dir, now=123.0)

    assert snapshot["organ_count"] == 1
    assert (tmp_path / "organ_registry.jsonl").exists()
    assert json.loads((tmp_path / "organ_map.json").read_text(encoding="utf-8"))["organ_count"] == 1
    assert "ORGAN REGISTRY" in summary_for_prompt(state_dir=tmp_path)


def test_query_returns_matching_organs_and_receipts(tmp_path: Path) -> None:
    system_dir = tmp_path / "System"
    _write_module(system_dir, "swarm_lora_memory.py", '"""LoRA training memory organ."""\nLEDGER = "lora_training_pairs.jsonl"\n')
    _write_module(system_dir, "swarm_ble_radar.py", '"""BLE sensor radar organ."""\nLEDGER = "alice_ble_radar.jsonl"\n')
    refresh_organ_registry(state_dir=tmp_path, system_dir=system_dir, now=123.0)

    result = query_organs("which training organ helps lora memory?", state_dir=tmp_path)

    assert result["matches"]
    assert result["matches"][0]["organ_id"] == "lora_memory"
    assert (tmp_path / "organ_query_receipts.jsonl").exists()
    assert "lora_memory" in summary_for_query("lora training memory", state_dir=tmp_path)
