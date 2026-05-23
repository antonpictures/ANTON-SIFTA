#!/usr/bin/env python3
"""Guardrails for CS153 golden sets: no phantom skills, no dead refs, no raw Talk text."""

from __future__ import annotations

import json
from pathlib import Path

import System.eval_talk_labeling_helper as talk_helper
from System.swarm_skill_library import build_skill_index


_EVAL_DIR = Path("data/eval")
_GOLDENS = [
    _EVAL_DIR / "cs153_golden_turns.jsonl",
    _EVAL_DIR / "cs153_talk_turns.jsonl",
    _EVAL_DIR / "cs153_skill_turns.jsonl",
    _EVAL_DIR / "cs153_regression_turns.jsonl",
]


def _load_turns(path: Path) -> list[dict]:
    turns = []
    if not path.exists():
        return turns
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if "truth_label" in obj and "turn_id" not in obj:
            continue
        turns.append(obj)
    return turns


def _payload_text(row: dict) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    text = payload.get("text")
    return text if isinstance(text, str) else ""


def test_all_golden_jsonl_parse_and_have_unique_turn_ids():
    for path in _GOLDENS:
        turns = _load_turns(path)
        ids = [turn.get("turn_id") for turn in turns]
        assert all(isinstance(turn_id, str) and turn_id for turn_id in ids), path
        assert len(ids) == len(set(ids)), f"duplicate turn_id in {path}"


def test_skill_golden_references_only_live_skills():
    live_names = {str(skill.get("name")) for skill in build_skill_index() if skill.get("name")}
    assert live_names
    for turn in _load_turns(_EVAL_DIR / "cs153_skill_turns.jsonl"):
        skill_name = turn.get("skill_name")
        assert skill_name in live_names, f"phantom skill in golden turn {turn.get('turn_id')}: {skill_name}"


def test_talk_golden_conversation_refs_resolve_to_local_rows():
    for turn in _load_turns(_EVAL_DIR / "cs153_talk_turns.jsonl"):
        ref = turn.get("conversation_ref", "")
        assert ref.startswith("alice_conversation.jsonl#"), f"bad conversation_ref on {turn.get('turn_id')}: {ref}"
        row = talk_helper.resolve_conversation_ref(ref)
        assert row is not None, f"unresolvable conversation_ref on {turn.get('turn_id')}: {ref}"


def test_talk_golden_snippets_are_redacted_metadata_not_raw_text():
    for turn in _load_turns(_EVAL_DIR / "cs153_talk_turns.jsonl"):
        snippet = str(turn.get("redacted_snippet", ""))
        row = talk_helper.resolve_conversation_ref(turn.get("conversation_ref", ""))
        assert row is not None
        raw_text = _payload_text(row).strip().replace("\n", " ")
        assert snippet.startswith("Local Talk row event=")
        assert "text_len=" in snippet
        if len(raw_text) >= 40:
            assert raw_text[:40] not in snippet
