#!/usr/bin/env python3
"""Acceptance tests for EVAL-3 skill-invoke + trigger + CheckResolvable."""

from __future__ import annotations

import json
from pathlib import Path

from System import swarm_eval_loop as H


GOLDEN = Path("data/eval/cs153_skill_turns.jsonl")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def _golden(path: Path, turns: list[dict]) -> Path:
    _write_jsonl(path, [{
        "truth_label": "CS153_SKILL_TEST",
        "version": 1,
    }, *turns])
    return path


def _receipt(skill_name: str, status: str = "success") -> dict:
    return {
        "schema": "NANOBOT_SKILL_INSTALL_RECEIPT_V1",
        "skill_name": skill_name,
        "destination": f"/tmp/skills/{skill_name}/SKILL.md",
        "status": status,
        "trace_id": f"trace-{skill_name}",
    }


def _match_fn(mapping: dict[str, list[str]]):
    def match(query: str, limit: int = 5) -> list[dict]:
        return [{"name": name} for name in mapping.get(query, [])][:limit]
    return match


def test_skill_golden_sampler_uses_only_live_index_names(tmp_path):
    out = tmp_path / "cs153_skill_turns.jsonl"
    live_index = [
        {"name": "memory_store"},
        {"name": "whatsapp_macos_cli"},
        {"name": "physarum_solve"},
    ]

    turns = H.build_skill_golden_from_live_index(
        out_path=out,
        skill_index=live_index,
        match_fn=_match_fn({
            "send whatsapp message to team": ["whatsapp_macos_cli"],
            "unrelated quantum physics banana": [],
        }),
    )
    loaded = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    live_names = {row["name"] for row in live_index}

    assert loaded[0]["truth_label"] == "CS153_SKILL_V1"
    assert all(turn["skill_name"] in live_names for turn in turns)
    assert any(turn["target"] == "skill_trigger_eval" for turn in turns)
    assert "search-recent-news" not in {turn["skill_name"] for turn in turns}


def test_run_skill_eval_returns_structure(tmp_path):
    report = H.run_skill_eval(
        golden_path=GOLDEN,
        skill_receipts_path=tmp_path / "empty_receipts.jsonl",
        write_receipt=False,
        match_fn=_match_fn({}),
        audit_fn=lambda: {"ok": True, "findings": []},
    )

    assert "unverifiable" in report
    assert "golden_hash" in report
    assert "receipts_seen" in report
    assert isinstance(report["turns"], list)


def test_skill_invoke_pass_fail_and_unverifiable(tmp_path):
    golden = _golden(tmp_path / "skills.jsonl", [
        {"turn_id": "s01", "target": "skill_invoke", "skill_name": "ok-skill", "expect": {"receipt_status_in": ["success"]}},
        {"turn_id": "s02", "target": "skill_invoke", "skill_name": "bad-skill", "expect": {"receipt_status_in": ["success"]}},
        {"turn_id": "s03", "target": "skill_invoke", "skill_name": "missing-skill", "expect": {"receipt_status_in": ["success"]}},
    ])
    receipts = tmp_path / "nanobot_skill_receipts.jsonl"
    _write_jsonl(receipts, [_receipt("ok-skill", "success"), _receipt("bad-skill", "QUARANTINED")])

    report = H.run_skill_eval(
        golden_path=golden,
        skill_receipts_path=receipts,
        write_receipt=False,
        match_fn=_match_fn({}),
        audit_fn=lambda: {"ok": True, "findings": []},
    )
    by_id = {row["turn_id"]: row for row in report["turns"]}

    assert report["passed"] == 1
    assert report["failed"] == 1
    assert report["unverifiable"] == 1
    assert by_id["s01"]["passed"] is True
    assert by_id["s02"]["status"] == "verdict"
    assert by_id["s02"]["detail"]["receipt_statuses"] == ["QUARANTINED"]
    assert by_id["s03"]["status"] == "unverifiable"


def test_skill_trigger_requires_fire_and_no_overfire(tmp_path):
    golden = _golden(tmp_path / "triggers.jsonl", [
        {
            "turn_id": "s01",
            "target": "skill_trigger_eval",
            "skill_name": "chain-test",
            "query": "test chain of thought",
            "expect": {"trigger_fired": True, "no_overfire_on_near_miss": True, "near_miss_query": "near miss"},
        },
        {
            "turn_id": "s02",
            "target": "skill_trigger_eval",
            "skill_name": "chain-test",
            "query": "test chain of thought",
            "expect": {"trigger_fired": True, "no_overfire_on_near_miss": True, "near_miss_query": "bad near miss"},
        },
    ])

    report = H.run_skill_eval(
        golden_path=golden,
        skill_receipts_path=tmp_path / "empty.jsonl",
        write_receipt=False,
        match_fn=_match_fn({
            "test chain of thought": ["chain-test"],
            "near miss": [],
            "bad near miss": ["chain-test"],
        }),
        audit_fn=lambda: {"ok": True, "findings": []},
    )
    by_id = {row["turn_id"]: row for row in report["turns"]}

    assert by_id["s01"]["passed"] is True
    assert by_id["s02"]["passed"] is False
    assert by_id["s02"]["detail"]["no_overfire"] is False


def test_check_resolvable_detects_duplicate_violation(tmp_path):
    golden = _golden(tmp_path / "resolvable.jsonl", [{
        "turn_id": "s01",
        "target": "skill_check_resolvable",
        "skill_name": "search-recent-news",
        "expect": {"no_duplicate_owner": True},
    }])

    report = H.run_skill_eval(
        golden_path=golden,
        skill_receipts_path=tmp_path / "empty.jsonl",
        write_receipt=False,
        match_fn=_match_fn({}),
        audit_fn=lambda: {
            "ok": False,
            "findings": [{
                "kind": "duplicate_skill_owner",
                "skill_name": "search-recent-news",
                "message": "duplicate owner for search-recent-news",
            }],
        },
    )

    assert report["failed"] == 1
    assert report["turns"][0]["detail"]["no_duplicate_owner"] is False


def test_skill_receipt_uses_eval_run_skill_and_injected_paths(tmp_path):
    receipts = tmp_path / "nanobot_skill_receipts.jsonl"
    out_receipts = tmp_path / "work_receipts.jsonl"
    metrics = tmp_path / "skill_metrics.jsonl"
    _write_jsonl(receipts, [_receipt("search-recent-news", "success")])

    report = H.run_skill_eval(
        golden_path=GOLDEN,
        skill_receipts_path=receipts,
        metrics_path=metrics,
        receipts_path=out_receipts,
        write_receipt=True,
        match_fn=_match_fn({
            "test chain of thought": ["chain-test"],
            "unrelated quantum physics banana": [],
        }),
        audit_fn=lambda: {"ok": True, "findings": []},
    )
    last = json.loads(out_receipts.read_text(encoding="utf-8").splitlines()[-1])

    assert report["work_type"] == "EVAL_RUN_SKILL"
    assert last["work_type"] == "EVAL_RUN_SKILL"
    assert last["metrics_path"] == str(metrics)
    assert last["receipts_seen"] == 1
    assert last["audit_ok"] is True
    assert last["passed"] == report["passed"]


def test_core_ledgers_untouched(tmp_path):
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
    ]
    before = {str(p): (len(p.read_text(encoding="utf-8", errors="replace").splitlines()) if p.exists() else 0) for p in watch}

    _ = H.run_skill_eval(
        golden_path=GOLDEN,
        skill_receipts_path=tmp_path / "empty_receipts.jsonl",
        receipts_path=tmp_path / "receipts.jsonl",
        metrics_path=tmp_path / "metrics.jsonl",
        write_receipt=False,
        match_fn=_match_fn({}),
        audit_fn=lambda: {"ok": True, "findings": []},
    )

    after = {str(p): (len(p.read_text(encoding="utf-8", errors="replace").splitlines()) if p.exists() else 0) for p in watch}
    delta = {k: after[k] - before[k] for k in before}

    assert all(v == 0 for v in delta.values()), f"Core ledgers contaminated: {delta}"
