from __future__ import annotations

import json
from pathlib import Path

from System.swarm_memory_archive_capsules import (
    format_latest_capsule_for_prompt,
    latest_capsule,
    write_restart_capsule,
)


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_write_restart_capsule_persists_refs(tmp_path: Path) -> None:
    _append_jsonl(
        tmp_path / "alice_conversation.jsonl",
        [{"ts": 1.0, "event_id": "evt_1", "role": "owner", "text": "hello"}],
    )
    _append_jsonl(
        tmp_path / "episodic_diary.jsonl",
        [{"ts": 2.0, "id": "dia_1", "title": "note"}],
    )
    _append_jsonl(
        tmp_path / "work_receipts.jsonl",
        [{"ts": 3.0, "receipt_id": "r_1", "kind": "WORK_RECEIPT"}],
    )

    row = write_restart_capsule(state_dir=tmp_path, source="unit_test")
    assert row["schema"] == "SIFTA_MEMORY_ARCHIVE_CAPSULE_V1"
    assert row["source"] == "unit_test"
    refs = row["refs"]
    assert "evt_1" in refs["alice_conversation"]["ref"]
    assert "dia_1" in refs["episodic_diary"]["ref"]
    assert "r_1" in refs["work_receipts"]["ref"]

    persisted = latest_capsule(state_dir=tmp_path)
    assert persisted["capsule_id"] == row["capsule_id"]


def test_format_latest_capsule_for_prompt_is_compact_and_grounded(tmp_path: Path) -> None:
    _append_jsonl(tmp_path / "alice_conversation.jsonl", [{"ts": 10.0, "event_id": "evt_2"}])
    _append_jsonl(tmp_path / "episodic_diary.jsonl", [{"ts": 11.0, "id": "dia_2"}])
    _append_jsonl(tmp_path / "work_receipts.jsonl", [{"ts": 12.0, "receipt_id": "r_2"}])
    write_restart_capsule(state_dir=tmp_path, source="unit_test_prompt")

    block = format_latest_capsule_for_prompt(state_dir=tmp_path)
    assert "RESTART CONTINUITY CAPSULE" in block
    assert "conversation_ref=alice_conversation.jsonl#" in block
    assert "episodic_ref=episodic_diary.jsonl#" in block
    assert "receipts_ref=work_receipts.jsonl#" in block


def test_write_restart_capsule_auto_compacts_append_only_archive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import System.swarm_memory_archive_capsules as mod

    monkeypatch.setattr(mod, "_AUTO_COMPACTION_KEEP_RECENT", 3)
    monkeypatch.setattr(mod, "_AUTO_COMPACTION_MIN_BATCH", 2)

    _append_jsonl(tmp_path / "alice_conversation.jsonl", [{"ts": 1.0, "event_id": "evt_seed"}])
    _append_jsonl(tmp_path / "episodic_diary.jsonl", [{"ts": 2.0, "id": "dia_seed"}])
    _append_jsonl(tmp_path / "work_receipts.jsonl", [{"ts": 3.0, "receipt_id": "r_seed"}])

    for _ in range(8):
        write_restart_capsule(state_dir=tmp_path, source="unit_compact")

    comp_path = tmp_path / "memory_archive_capsules_compaction.jsonl"
    assert comp_path.exists()
    rows = [json.loads(line) for line in comp_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    tail = rows[-1]
    assert tail["schema"] == "SIFTA_MEMORY_ARCHIVE_CAPSULE_COMPACTION_V1"
    assert tail["compacted_count"] >= 2
    assert tail["compacted_through_line"] > tail["compacted_from_line"]
    assert tail["source_counts"]["unit_compact"] >= 2


def test_format_latest_capsule_for_prompt_includes_compaction_ref(tmp_path: Path, monkeypatch) -> None:
    import System.swarm_memory_archive_capsules as mod

    monkeypatch.setattr(mod, "_AUTO_COMPACTION_KEEP_RECENT", 2)
    monkeypatch.setattr(mod, "_AUTO_COMPACTION_MIN_BATCH", 2)

    _append_jsonl(tmp_path / "alice_conversation.jsonl", [{"ts": 10.0, "event_id": "evt_comp"}])
    _append_jsonl(tmp_path / "episodic_diary.jsonl", [{"ts": 11.0, "id": "dia_comp"}])
    _append_jsonl(tmp_path / "work_receipts.jsonl", [{"ts": 12.0, "receipt_id": "r_comp"}])
    for _ in range(6):
        write_restart_capsule(state_dir=tmp_path, source="unit_compact_prompt")

    block = format_latest_capsule_for_prompt(state_dir=tmp_path)
    assert "compaction_ref=memory_archive_capsules_compaction.jsonl#compaction_id:" in block
