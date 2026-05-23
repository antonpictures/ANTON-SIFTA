from __future__ import annotations

import json
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _mini_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "Documents").mkdir(parents=True)
    (repo / "scripts").mkdir()
    (repo / "exports").mkdir()
    return repo


def test_autoproposal_scans_repeated_successes_and_writes_receipt(tmp_path: Path) -> None:
    from System import swarm_skill_autoproposal as auto

    state = tmp_path / ".sifta_state"
    skills = tmp_path / "skills"
    repo = _mini_repo(tmp_path)
    rows = [
        {
            "event": "TOOL_CALL_POST_FLIGHT",
            "tool": "read_file",
            "ok": True,
            "status": "EXECUTED",
            "trace_id": f"read-{i}",
        }
        for i in range(3)
    ]
    _write_jsonl(state / "tool_router_trace.jsonl", rows)

    result = auto.scan_field_for_skill_needs(
        repo_root=repo,
        state_dir=state,
        skills_dir=skills,
        min_repeat=3,
        allow_pull=False,
        dedupe=False,
    )

    assert result["ok"] is True
    assert result["proposal_count"] >= 1
    assert any(p["proposal_type"] == "EXTRACT_TRACE_SKILL" for p in result["proposals"])
    assert (state / "skill_autoproposals.jsonl").exists()
    latest = auto.latest_proposals(limit=2, state_dir=state)
    assert latest
    assert latest[0]["receipt_id"] == result["receipt_id"]


def test_autoproposal_allow_pull_extracts_repeated_trace_skill(tmp_path: Path, monkeypatch) -> None:
    from System import swarm_skill_autoproposal as auto
    from System import swarm_skill_library as lib

    state = tmp_path / ".sifta_state"
    skills = tmp_path / "skills"
    repo = _mini_repo(tmp_path)
    monkeypatch.setenv("SIFTA_HOMEWORLD_SERIAL", "TESTSERIAL")
    monkeypatch.setattr(lib, "_STATE_DIR", state)
    monkeypatch.setattr(lib, "_SKILL_RECEIPTS", state / "nanobot_skill_receipts.jsonl")
    rows = [
        {
            "event": "TOOL_CALL_POST_FLIGHT",
            "tool": "list_dir",
            "ok": True,
            "status": "EXECUTED",
            "trace_id": f"list-{i}",
            "result_summary": "listed project directory",
        }
        for i in range(3)
    ]
    _write_jsonl(state / "tool_router_trace.jsonl", rows)

    result = auto.scan_field_for_skill_needs(
        repo_root=repo,
        state_dir=state,
        skills_dir=skills,
        min_repeat=3,
        allow_pull=True,
        dedupe=False,
    )

    assert result["action_count"] >= 1
    assert any(p["proposal_type"] == "EXTRACT_TRACE_SKILL" for p in result["actions"])
    assert (skills / "repeat_list_dir" / "SKILL.md").exists()


def test_autoproposal_scores_marketplace_from_life_context(tmp_path: Path) -> None:
    from System import swarm_skill_autoproposal as auto

    state = tmp_path / ".sifta_state"
    skills = tmp_path / "skills"
    repo = _mini_repo(tmp_path)
    source = tmp_path / "wordace_source.md"
    source.write_text(
        "# WordAce reading helper\n\nWhen to use: reading tutor phonics word ace.\n\nInstructions: speak the word aloud patiently.",
        encoding="utf-8",
    )
    marketplace = tmp_path / "market.json"
    marketplace.write_text(
        json.dumps(
            {
                "skills": [
                    {
                        "id": "wordace-reading",
                        "name": "WordAce Reading",
                        "description": "Use when reading tutor phonics word ace needs patient speech.",
                        "source_path": str(source),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        state / "work_receipts.jsonl",
        [{"status": "SUCCESS", "note": "Ace needs reading tutor phonics word ace patience"}],
    )

    result = auto.scan_field_for_skill_needs(
        repo_root=repo,
        state_dir=state,
        skills_dir=skills,
        marketplace=marketplace,
        allow_pull=False,
        dedupe=False,
    )

    market = [p for p in result["proposals"] if p["proposal_type"] == "MARKETPLACE_PULL"]
    assert market
    assert market[0]["marketplace_choice"]["id"] == "wordace-reading"
    assert market[0]["confidence"] > 0
