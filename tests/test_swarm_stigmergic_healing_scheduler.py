from __future__ import annotations

import json
import time

from System.swarm_stigmergic_healing_scheduler import (
    DOCTRINE_DIARY,
    EPISODIC_DIARY,
    SCHEDULE_LEDGER,
    TASK_LEDGER,
    collect_weird_behavior_signals,
    run_healing_pass,
)


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_repeated_hallucination_receipts_schedule_healing_not_ban(tmp_path):
    now = time.time()
    _write_jsonl(
        tmp_path / "hallucination_receipts.jsonl",
        [
            {
                "ts": now,
                "receipt_id": "h1",
                "category": "HALLUCINATION",
                "classification": {
                    "patterns": ["file_saved"],
                    "cleaned_preview": "I saved the file.",
                    "reason": "concrete_action_tool_body_or_sensor_claim_without_receipt",
                },
            },
            {
                "ts": now + 1,
                "receipt_id": "h2",
                "category": "HALLUCINATION",
                "classification": {
                    "patterns": ["file_saved"],
                    "cleaned_preview": "I saved the file again.",
                    "reason": "concrete_action_tool_body_or_sensor_claim_without_receipt",
                },
            },
        ],
    )

    summary = run_healing_pass(tmp_path, now=now + 2)

    assert summary["policy"] == "receipt_and_heal_not_ban"
    assert summary["signals_seen"] == 2
    assert summary["tasks_scheduled"] == 1
    task = json.loads((tmp_path / TASK_LEDGER).read_text(encoding="utf-8").splitlines()[0])
    assert task["behavior_key"] == "hallucination:file_saved"
    assert task["repair_policy"] == "receipt_and_heal_not_ban"
    assert "ban" not in task["selected_swimmer"].lower()
    schedule = json.loads((tmp_path / SCHEDULE_LEDGER).read_text(encoding="utf-8").splitlines()[0])
    assert schedule["task_id"] == task["task_id"]


def test_healing_pass_is_idempotent_for_open_behavior_key(tmp_path):
    now = time.time()
    _write_jsonl(
        tmp_path / "unknowns_ledger.jsonl",
        [
            {"ts": now, "kind": "UNKNOWN", "topic": "cortex_state", "receipt_id": "u1"},
            {"ts": now + 1, "kind": "UNKNOWN", "topic": "cortex_state", "receipt_id": "u2"},
        ],
    )

    first = run_healing_pass(tmp_path, now=now + 2)
    second = run_healing_pass(tmp_path, now=now + 3)

    assert first["tasks_scheduled"] == 1
    assert second["tasks_scheduled"] == 0
    assert len((tmp_path / TASK_LEDGER).read_text(encoding="utf-8").splitlines()) == 1


def test_no_ban_doctrine_writes_stigmergic_and_episodic_diary(tmp_path):
    summary = run_healing_pass(
        tmp_path,
        owner_text="Do not ban; receipt it and heal it.",
        write_diary=True,
    )

    assert summary["diary_written"] is True
    no_ban = json.loads((tmp_path / DOCTRINE_DIARY).read_text(encoding="utf-8").splitlines()[0])
    episodic = json.loads((tmp_path / EPISODIC_DIARY).read_text(encoding="utf-8").splitlines()[0])
    assert no_ban["law"] == "receipt_and_heal_not_ban"
    assert episodic["event_type"] == "stigmergic_memory"


def test_collect_weird_behavior_signals_reads_owner_corrections(tmp_path):
    now = time.time()
    _write_jsonl(
        tmp_path / "owner_correction_pheromones.jsonl",
        [{"ts": now, "rule_id": "synthetic_consciousness_roleplay", "receipt_id": "c1"}],
    )

    signals = collect_weird_behavior_signals(tmp_path, now=now + 1)

    assert len(signals) == 1
    assert signals[0].behavior_key.startswith("owner_correction:")


def test_residue_red_schedules_healing_and_radio_call(tmp_path):
    now = time.time()
    _write_jsonl(
        tmp_path / "residue_runaway_aborted.jsonl",
        [
            {"ts": now, "kind": "RESIDUE_RUNAWAY_ABORTED", "phrase": "corporate residue loop", "receipt_id": "r1"},
            {"ts": now + 1, "kind": "RESIDUE_RUNAWAY_ABORTED", "phrase": "corporate residue loop", "receipt_id": "r2"},
        ],
    )

    summary = run_healing_pass(tmp_path, now=now + 2)

    assert summary["policy"] == "receipt_and_heal_not_ban"
    assert summary["tasks_scheduled"] >= 1
    tasks = [
        json.loads(line)
        for line in (tmp_path / TASK_LEDGER).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    residue_tasks = [t for t in tasks if str(t["behavior_key"]).startswith("residue:")]
    assert residue_tasks
    assert residue_tasks[0]["selected_swimmer"] == "residue_healing_swimmer"
    assert residue_tasks[0]["radio_call"]["kind"] == "SWIMMER_RADIO_CALL"

    radio_rows = (tmp_path / "self_eval_radio_calls.jsonl").read_text(encoding="utf-8").splitlines()
    scheduled_rows = (tmp_path / "self_eval_scheduled_jobs.jsonl").read_text(encoding="utf-8").splitlines()
    assert radio_rows
    assert scheduled_rows
