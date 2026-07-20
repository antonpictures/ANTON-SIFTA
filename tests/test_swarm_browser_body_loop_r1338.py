from __future__ import annotations

from System.swarm_browser_body_loop import (
    maybe_honest_search_reply,
    observe_text_for_command,
    plan_body_loop_from_command,
    run_sifta_app_body_loop,
    sc_describe_clothing_reply,
)


def test_plan_browser_search_command():
    plan = plan_body_loop_from_command(
        {
            "kind": "browser_url",
            "url": "https://duckduckgo.com/?q=cats",
            "query": "cats",
            "owner_text": "SEARCH ON GOOGLE PLS cats",
        }
    )
    assert plan == ("browser_search", "Alice Browser opens web search results for 'cats' at https://duckduckgo.com/?q=cats")


def test_plan_close_tab_command():
    plan = plan_body_loop_from_command(
        {
            "kind": "browser_action",
            "action": "close_browser_tabs",
            "close_duplicates": True,
            "owner_text": "close duplicate tab",
        }
    )
    assert plan is not None
    assert plan[0] == "browser_close_tab"


def test_observe_search_writes_provider_reality(tmp_path):
    actual = observe_text_for_command(
        {
            "kind": "browser_url",
            "url": "https://duckduckgo.com/?q=lost+passport",
            "query": "lost passport",
            "owner_text": "SEARCH ON GOOGLE PLS 'lost passport'",
        },
        "I searched Google for lost passport.",
        state_dir=tmp_path,
    )
    assert "duckduckgo" in actual.lower()
    ledger = tmp_path / ".sifta_state" / "search_provider_reality.jsonl"
    assert ledger.exists()


def test_run_body_loop_writes_prediction_outcome(tmp_path):
    calls: list[str] = []

    def _execute(command):
        calls.append(str(command.get("_body_loop_inner")))
        return "closed tab #2"

    reply = run_sifta_app_body_loop(
        {
            "kind": "browser_action",
            "action": "close_browser_tabs",
            "index": 1,
            "owner_text": "close duplicate tab",
        },
        _execute,
        state_dir=tmp_path,
    )
    assert reply == "closed tab #2"
    assert calls == ["True"]
    ledger = (tmp_path / ".sifta_state" / "action_prediction.jsonl").read_text(encoding="utf-8")
    assert "browser_close_tab" in ledger
    assert '"kind": "prediction"' in ledger
    assert '"kind": "outcome"' in ledger


def test_maybe_honest_search_reply_names_execution_provider(tmp_path):
    reply = maybe_honest_search_reply(
        {
            "kind": "browser_url",
            "url": "https://duckduckgo.com/?q=cats",
            "query": "cats",
            "owner_text": "search google for cats",
        },
        "I searched Google for cats.",
        state_dir=tmp_path,
    )
    assert "DuckDuckGo" in reply


def test_sc_describe_clothing_honest_gap_without_frame(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.swarm_saccadic_blink_vision.describe_owner_frame_on_demand",
        lambda **kwargs: {
            "blink_id": "blink_test",
            "frame_age_s": None,
            "semantic_description": {
                "status": "unavailable",
                "description": "no owner camera frame on disk yet",
            },
        },
    )
    reply = sc_describe_clothing_reply("/SC DESCRIBE CLOTHING", state_dir=tmp_path)
    assert "do not have a fresh" in reply.lower() or "do not yet have" in reply.lower()
    ledger = (tmp_path / ".sifta_state" / "action_prediction.jsonl").read_text(encoding="utf-8")
    assert "sc_describe_clothing" in ledger