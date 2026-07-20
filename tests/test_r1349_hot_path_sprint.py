from __future__ import annotations

import ast
from pathlib import Path

from Applications import sifta_talk_to_alice_widget as talk
from System.swarm_concept_human_anchor import (
    SOURCE_ANCHORED_LABEL,
    answer_concept_founder_query,
    resolve_concept_anchor,
)
from System.swarm_cowatch_body_loop import (
    run_cowatch_video_pause_body_loop,
    run_cowatch_video_resume_body_loop,
)
from System.swarm_human_identity_constants import answer_human_identity_fast_recall
from System.swarm_search_provider_reality import (
    build_explicit_engine_search_url,
    parse_explicit_engine_pls_search,
    reconcile_explicit_engine_command,
)
from System.swarm_talk_hot_path_maintenance import tick_talk_hot_path_maintenance


def test_duck_ai_pls_parses_and_urls_duckai_not_ddg():
    parsed = parse_explicit_engine_pls_search(
        "SEARCH ON DUCK.AI PLS what is stigmergic consciousness"
    )
    assert parsed is not None
    assert parsed["engine"] == "duckai"
    url = build_explicit_engine_search_url(parsed["engine"], parsed["query"])
    assert "duck.ai" in url.lower()
    assert "duckduckgo" not in url.lower()


def test_reconcile_explicit_engine_command_fixes_mangled_dispatch():
    cmd = reconcile_explicit_engine_command(
        {
            "kind": "browser_url",
            "url": "https://duckduckgo.com/?q=ON+PERPLEXITY.AI+test",
            "query": "ON PERPLEXITY.AI test",
        },
        owner_text="SEARCH ON PERPLEXITY AI PLS test",
    )
    assert "perplexity" in str(cmd.get("url") or "").lower()
    assert cmd.get("search_site") == "perplexity"
    assert cmd.get("query") == "test"


def test_explicit_engine_rebound_in_execute_path():
    cmd = talk._extract_explicit_engine_search_command(
        "SEARCH ON GOOGLE PLS 'lost passport'"
    )
    assert cmd.get("search_site") == "google"
    assert "google.com" in str(cmd.get("url") or "")


def test_source_anchored_gabriel_weinberg_not_hypothesis():
    row = resolve_concept_anchor("DuckDuckGo")
    assert row is not None
    primary = row["primary_birth_anchor"]
    assert primary["human_name"] == "Gabriel Weinberg"
    assert primary["truth_label"] == SOURCE_ANCHORED_LABEL
    assert primary["source_receipts"]


def test_founder_query_uses_source_anchored_label(tmp_path):
    reply = answer_concept_founder_query("Who founded Perplexity AI?", state_dir=tmp_path)
    assert "Aravind Srinivas" in reply
    assert SOURCE_ANCHORED_LABEL in reply


def test_human_identity_fast_recall_evan_schwartz_collision(tmp_path):
    reply = answer_human_identity_fast_recall(
        "Who is Evan Schwartz?",
        state_dir=tmp_path,
    )
    assert "NOT the DuckDuckGo founder" in reply
    assert "Gabriel Weinberg" in reply


def test_human_identity_fast_recall_aravind(tmp_path):
    reply = answer_human_identity_fast_recall(
        "Who is Aravind Srinivas?",
        state_dir=tmp_path,
    )
    assert "Aravind Srinivas" in reply
    assert "perplexity" in reply.lower() or "receipt" in reply.lower()


def test_cowatch_pause_resume_action_prediction(tmp_path):
    run_cowatch_video_pause_body_loop(
        url="https://www.youtube.com/watch?v=test",
        receipt={"ok": True, "paused": True, "was_paused": False},
        state_dir=tmp_path,
    )
    run_cowatch_video_resume_body_loop(
        url="https://www.youtube.com/watch?v=test",
        state_dir=tmp_path,
    )
    ledger = tmp_path / ".sifta_state" / "action_prediction.jsonl"
    text = ledger.read_text(encoding="utf-8")
    assert "cowatch_video_pause" in text
    assert "cowatch_video_resume" in text


def test_talk_hot_path_maintenance_writes_audit_and_governor(tmp_path):
    row = tick_talk_hot_path_maintenance(state_dir=tmp_path, force=True)
    assert "body_metabolism_audit" in (row.get("events") or [])
    assert (tmp_path / ".sifta_state" / "body_metabolism_audit.jsonl").exists()
    assert (tmp_path / ".sifta_state" / "body_metabolism_governor.jsonl").exists()


def test_start_brain_binds_chat_reflex_gate_before_first_branch():
    source = Path(talk.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    start_brain = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_start_brain"
    )
    refs = sorted(
        (
            (node.lineno, node.col_offset, type(node.ctx).__name__)
            for node in ast.walk(start_brain)
            if isinstance(node, ast.Name) and node.id == "chat_reflexes_enabled"
        ),
        key=lambda item: (item[0], item[1]),
    )

    assert refs
    assert refs[0][2] == "Store"
