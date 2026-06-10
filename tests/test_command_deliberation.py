#!/usr/bin/env python3
"""r325: THINK then execute. George: "she must think and THEN execute, not just execute stupid
shit." The command path must reason about intent via the cortex, not pattern-match a regex that
breaks on unpredictable phrasing. These tests pin the deliberation scaffold headless: the planning
prompt carries the owner's words + her real hands; a returned plan is validated against the
capability catalog (a step naming a hand she lacks is rejected, §6); and a fast-path MISS triggers
thinking instead of a blind default.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_command_deliberation as d


def test_plan_prompt_carries_owner_words_and_real_hands():
    p = d.build_plan_prompt("open youtube and look up the matrix trailer",
                            page_state={"url": "https://youtube.com", "title": "YouTube"})
    assert "open youtube and look up the matrix trailer" in p  # verbatim, not keyword-matched
    assert "youtube_search(query)" in p and "open_video_result" in p  # her real hands offered
    assert "browser_close_tab" in p
    assert "EXACT words" in p  # the anti-injection instruction


def test_valid_plan_parses_into_ordered_steps():
    cortex = '''Sure, here is the plan:
    {"intent": "open youtube and search for the matrix trailer, then play it",
     "steps": [
        {"action": "open_app", "args": {"app_name": "Alice Browser"}, "why": "need her web limb"},
        {"action": "youtube_search", "args": {"query": "the matrix trailer"}, "why": "his words"},
        {"action": "open_video_result", "args": {"title_hint": "the matrix trailer"}, "why": "play it"}
     ], "speak": "Opening YouTube and finding the Matrix trailer."}'''
    out = d.parse_plan(cortex)
    assert out["ok"] is True
    assert [s["action"] for s in out["steps"]] == ["open_app", "youtube_search", "open_video_result"]
    assert out["steps"][1]["args"]["query"] == "the matrix trailer"


def test_fabricated_effector_is_rejected_section6():
    cortex = '{"intent":"x","steps":[{"action":"launch_missiles","args":{},"why":"no"}],"speak":""}'
    out = d.parse_plan(cortex)
    assert out["ok"] is False
    assert any("unknown_action:launch_missiles" in e for e in out["errors"])
    assert out["steps"] == []  # never hand a hallucinated hand to the executor


def test_missing_required_arg_is_rejected():
    cortex = '{"intent":"x","steps":[{"action":"youtube_search","args":{},"why":"oops"}],"speak":""}'
    out = d.parse_plan(cortex)
    assert out["ok"] is False
    assert any("youtube_search_missing:query" in e for e in out["errors"])


def test_browser_close_tab_plan_requires_a_selector():
    ok = d.parse_plan(
        '{"intent":"close Jama tabs","steps":[{"action":"browser_close_tab",'
        '"args":{"url_match":"jamasoftware.com","keep_active":false},"why":"owner asked"}],'
        '"speak":"Closing Jama tabs."}'
    )
    assert ok["ok"] is True
    assert ok["steps"][0]["action"] == "browser_close_tab"

    bad = d.parse_plan(
        '{"intent":"close tabs","steps":[{"action":"browser_close_tab","args":{},'
        '"why":"no selector"}],"speak":""}'
    )
    assert bad["ok"] is False
    assert any("browser_close_tab_missing" in e for e in bad["errors"])


def test_no_json_is_not_ok():
    assert d.parse_plan("I will open youtube for you.")["ok"] is False


def test_fast_path_miss_triggers_thinking_not_blind_default():
    # The exact failure class: a real command the regex missed → think, do not guess a default.
    assert d.needs_deliberation("open youtube and look up nvidia keynote", fast_path_decided=False) is True
    assert d.needs_deliberation("go to youtube.com, find me the matrix trailer", fast_path_decided=False) is True
    assert d.needs_deliberation("close the two Jama Software tabs", fast_path_decided=False) is True
    # When the confident fast-path already decided, don't burn a cortex turn.
    assert d.needs_deliberation("search youtube for cats", fast_path_decided=True) is False
    # Idle chatter with no command verb does not force a plan.
    assert d.needs_deliberation("thanks, that was nice", fast_path_decided=False) is False
    assert d.needs_deliberation("", fast_path_decided=False) is False


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
