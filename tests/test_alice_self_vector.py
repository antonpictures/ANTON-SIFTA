from __future__ import annotations

import json
from pathlib import Path

from System import alice_self_vector as vector


NOW = 1_778_999_000.0


def _append_jsonl(path: Path, *rows: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _seed_basic(repo: Path) -> Path:
    state = repo / ".sifta_state"
    _append_jsonl(
        state / "alice_narrative_diary.jsonl",
        {"ts": NOW - 100, "entry": "I wrote about George teaching me receipts and memory."},
    )
    _append_jsonl(
        state / "episodic_diary.jsonl",
        {"ts": NOW - 200, "summary": "Daily memory and schedule work.", "keywords": ["memory", "schedule"]},
    )
    _append_jsonl(
        state / "stigmergic_schedule.jsonl",
        {"created": NOW - 300, "text": "Open owner rhythm check", "priority": "high", "done": False},
    )
    _append_jsonl(
        state / "ide_stigmergic_trace.jsonl",
        {
            "ts": NOW - 50,
            "trace_id": "t1",
            "action": "LLM_REGISTRATION",
            "intent": "Ship next open gap",
            "node_serial": "GTH4921YP3",
        },
    )
    _append_jsonl(
        state / "work_receipts.jsonl",
        {
            "ts": NOW - 40,
            "receipt_id": "r1",
            "work_type": "MEMORY_DIGEST",
            "summary": "Receipt-backed memory digest shipped.",
            "node_serial": "GTH4921YP3",
        },
    )
    latest = repo / "Documents" / "architect_memory_digest" / "what_george_taught_alice_today.md"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(
        "# What George Taught Alice Today\n\nGeorge taught Alice receipt-backed memory and the covenant.\n",
        encoding="utf-8",
    )
    archive = repo / "Documents" / "architect_memory" / "architect_daily_digest_2026-05-16.md"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text("# Archive\n\nPending next action: close the open schedule loop.\n", encoding="utf-8")
    return state


def test_empty_state_gracefully_writes_vector(tmp_path: Path) -> None:
    out = vector.build_alice_self_vector(repo_root=tmp_path, state_dir=tmp_path / ".sifta_state", now=NOW)

    assert out["ok"] is True
    assert out["truth_label"] == vector.TRUTH_LABEL
    assert out["memory_entropy"] == 0.0
    assert out["identity_continuity"] == 0.0
    assert Path(out["artifact_path"]).exists()


def test_no_write_does_not_create_state_file(tmp_path: Path) -> None:
    out = vector.build_alice_self_vector(
        repo_root=tmp_path,
        state_dir=tmp_path / ".sifta_state",
        now=NOW,
        write_artifact=False,
    )

    assert out["ok"] is True
    assert not (tmp_path / "State" / "alice_self_vector.json").exists()
    assert "artifact_path" not in out


def test_numeric_timestamp_parses() -> None:
    assert vector._row_ts({"ts": 123.5}) == 123.5


def test_iso_timestamp_parses() -> None:
    assert vector._row_ts({"ts_iso": "2026-05-16T20:00:00Z"}) > 1_778_000_000


def test_entropy_empty_is_zero() -> None:
    assert vector._normalized_entropy([]) == 0.0


def test_entropy_diverse_text_is_higher_than_repeated_text() -> None:
    repeated = vector._normalized_entropy(["alpha alpha alpha alpha"])
    diverse = vector._normalized_entropy(["alpha beta gamma delta epsilon zeta"])

    assert diverse > repeated


def test_invalid_jsonl_counts_against_receipt_integrity(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text('{"trace_id":"ok"}\nnot-json\n', encoding="utf-8")

    scan = vector._tail_jsonl_scan(path, "bad")
    score, detail = vector._receipt_integrity([scan])

    assert detail["invalid_lines"] == 1
    assert 0 < score < 1


def test_receipt_integrity_empty_is_zero() -> None:
    score, detail = vector._receipt_integrity([])

    assert score == 0.0
    assert detail["total_lines"] == 0


def test_receipt_integrity_valid_identified_rows_scores_high(tmp_path: Path) -> None:
    path = tmp_path / "good.jsonl"
    _append_jsonl(path, {"trace_id": "t1"}, {"receipt_id": "r1"})

    score, detail = vector._receipt_integrity([vector._tail_jsonl_scan(path, "good")])

    assert score == 1.0
    assert detail["identified_rows"] == 2


def test_serial_consistency_detects_majority() -> None:
    rows = [
        {"node_serial": "A"},
        {"node_serial": "A"},
        {"node_serial": "B"},
    ]

    assert vector._serial_consistency(rows) == 2 / 3


def test_schedule_pressure_reflects_open_high_priority(tmp_path: Path) -> None:
    state = _seed_basic(tmp_path)
    out = vector.build_alice_self_vector(repo_root=tmp_path, state_dir=state, now=NOW, write_artifact=False)

    assert out["schedule_pressure"] > 0.0
    assert out["observations"]["open_schedule_rows"] == 1


def test_done_schedule_rows_are_not_open(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _append_jsonl(
        state / "stigmergic_schedule.jsonl",
        {"created": NOW - 10, "text": "Done item", "done": True, "priority": "high"},
    )

    out = vector.build_alice_self_vector(repo_root=tmp_path, state_dir=state, now=NOW, write_artifact=False)

    assert out["observations"]["open_schedule_rows"] == 0
    assert out["schedule_pressure"] == 0.0


def test_unresolved_threads_include_open_schedule(tmp_path: Path) -> None:
    state = _seed_basic(tmp_path)
    out = vector.build_alice_self_vector(repo_root=tmp_path, state_dir=state, now=NOW, write_artifact=False)

    assert any(item["source"] == "schedule" for item in out["unresolved_threads"])


def test_unresolved_threads_include_trace_gap(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    _append_jsonl(
        state / "ide_stigmergic_trace.jsonl",
        {"ts": NOW - 10, "trace_id": "t1", "intent": "Fix missing schedule gap"},
    )

    out = vector.build_alice_self_vector(repo_root=tmp_path, state_dir=state, now=NOW, write_artifact=False)

    assert out["unresolved_threads"][0]["source"] == "ide_trace"


def test_architect_alignment_uses_digest_documents(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    latest = tmp_path / "Documents" / "architect_memory_digest" / "what_george_taught_alice_today.md"
    latest.parent.mkdir(parents=True)
    latest.write_text("George taught Alice the covenant receipt memory digest owner schedule.", encoding="utf-8")

    out = vector.build_alice_self_vector(repo_root=tmp_path, state_dir=state, now=NOW, write_artifact=False)

    assert out["architect_alignment"] > 0.4


def test_stigmergic_momentum_rises_with_recent_rows(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    for i in range(8):
        _append_jsonl(state / "ide_stigmergic_trace.jsonl", {"ts": NOW - i, "trace_id": f"t{i}"})

    out = vector.build_alice_self_vector(repo_root=tmp_path, state_dir=state, now=NOW, write_artifact=False)

    assert out["stigmergic_momentum"] > 0.5


def test_owner_rhythm_alignment_needs_diary_or_schedule(tmp_path: Path) -> None:
    state = _seed_basic(tmp_path)
    out = vector.build_alice_self_vector(repo_root=tmp_path, state_dir=state, now=NOW, write_artifact=False)

    assert out["owner_rhythm_alignment"] > 0.4


def test_next_action_prefers_receipt_integrity_repair() -> None:
    action = vector._next_best_action(
        receipt_integrity=0.2,
        reality_boundary_integrity=1.0,
        unresolved_threads=[],
        schedule_pressure=0.0,
        architect_alignment=1.0,
        stigmergic_momentum=0.0,
        memory_entropy=1.0,
    )

    assert "Repair malformed" in action


def test_next_action_prefers_reality_boundary_after_receipts() -> None:
    action = vector._next_best_action(
        receipt_integrity=1.0,
        reality_boundary_integrity=0.2,
        unresolved_threads=[],
        schedule_pressure=0.0,
        architect_alignment=1.0,
        stigmergic_momentum=0.0,
        memory_entropy=1.0,
    )

    assert "unverified knowledge" in action


def test_next_action_prefers_unresolved_thread_after_receipts() -> None:
    action = vector._next_best_action(
        receipt_integrity=1.0,
        reality_boundary_integrity=1.0,
        unresolved_threads=[{"text": "open owner schedule loop"}],
        schedule_pressure=0.0,
        architect_alignment=1.0,
        stigmergic_momentum=0.0,
        memory_entropy=1.0,
    )

    assert "open owner schedule loop" in action


def test_next_action_surfaces_schedule_pressure() -> None:
    action = vector._next_best_action(
        receipt_integrity=1.0,
        reality_boundary_integrity=1.0,
        unresolved_threads=[],
        schedule_pressure=0.9,
        architect_alignment=1.0,
        stigmergic_momentum=0.0,
        memory_entropy=1.0,
    )

    assert "schedule pressure" in action


def test_render_self_vector_section_contains_boundary() -> None:
    section = vector.render_self_vector_section(
        {
            "truth_label": vector.TRUTH_LABEL,
            "memory_entropy": 0.1,
            "identity_continuity": 0.2,
            "schedule_pressure": 0.3,
            "architect_alignment": 0.4,
            "unresolved_thread_count": 0,
            "stigmergic_momentum": 0.5,
            "receipt_integrity": 1.0,
            "reality_boundary_integrity": 0.8,
            "owner_rhythm_alignment": 0.6,
            "next_best_action": "test",
        }
    )

    assert "Current Alice Self Vector" in section
    assert "not proof of subjective consciousness" in section


def test_write_receipt_ledger_appends(tmp_path: Path) -> None:
    state = _seed_basic(tmp_path)
    out = vector.build_alice_self_vector(repo_root=tmp_path, state_dir=state, now=NOW)

    receipt_path = Path(out["receipt_path"])
    assert receipt_path.exists()
    assert out["receipt_id"] in receipt_path.read_text(encoding="utf-8")


def test_same_inputs_are_deterministic_without_write(tmp_path: Path) -> None:
    state = _seed_basic(tmp_path)
    first = vector.build_alice_self_vector(repo_root=tmp_path, state_dir=state, now=NOW, write_artifact=False)
    second = vector.build_alice_self_vector(repo_root=tmp_path, state_dir=state, now=NOW, write_artifact=False)

    keys = (
        "memory_entropy",
        "identity_continuity",
        "schedule_pressure",
        "architect_alignment",
        "unresolved_thread_count",
        "stigmergic_momentum",
        "receipt_integrity",
        "reality_boundary_integrity",
        "owner_rhythm_alignment",
        "next_best_action",
    )
    assert {key: first[key] for key in keys} == {key: second[key] for key in keys}


def test_digest_sources_include_latest_and_archive(tmp_path: Path) -> None:
    state = _seed_basic(tmp_path)
    out = vector.build_alice_self_vector(repo_root=tmp_path, state_dir=state, now=NOW, write_artifact=False)
    paths = [item["path"] for item in out["digest_sources"]]

    assert "Documents/architect_memory_digest/what_george_taught_alice_today.md" in paths
    assert "Documents/architect_memory/architect_daily_digest_2026-05-16.md" in paths


def test_reality_boundary_integrity_is_in_vector_and_observations(tmp_path: Path) -> None:
    state = _seed_basic(tmp_path)
    out = vector.build_alice_self_vector(repo_root=tmp_path, state_dir=state, now=NOW, write_artifact=False)

    assert "reality_boundary_integrity" in out
    assert "reality_boundary_integrity" in out["vector"]
    assert out["observations"]["reality_boundary_available"] is True
    assert out["observations"]["reality_boundary_total"] > 0
    assert out["observations"]["reality_boundary_counts"]["OBSERVED"] >= 1


def test_reality_boundary_integrity_drops_when_plain_unverified_rows_dominate(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    for i in range(6):
        _append_jsonl(
            state / "alice_narrative_diary.jsonl",
            {"ts": NOW - i, "entry": f"plain unlabeled thought {i}"},
        )

    out = vector.build_alice_self_vector(repo_root=tmp_path, state_dir=state, now=NOW, write_artifact=False)

    assert out["reality_boundary_integrity"] < 0.65
    assert "unverified knowledge" in out["next_best_action"]


def test_sources_report_missing_files(tmp_path: Path) -> None:
    out = vector.build_alice_self_vector(
        repo_root=tmp_path,
        state_dir=tmp_path / ".sifta_state",
        now=NOW,
        write_artifact=False,
    )

    assert out["sources"]["alice_narrative_diary"]["exists"] is False


def test_max_items_caps_unresolved_threads(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    for i in range(10):
        _append_jsonl(
            state / "stigmergic_schedule.jsonl",
            {"created": NOW - i, "text": f"Open item {i}", "done": False, "priority": "high"},
        )

    out = vector.build_alice_self_vector(
        repo_root=tmp_path,
        state_dir=state,
        now=NOW,
        max_items=3,
        write_artifact=False,
    )

    assert len(out["unresolved_threads"]) == 3
