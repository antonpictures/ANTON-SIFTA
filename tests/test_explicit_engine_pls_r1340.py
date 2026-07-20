from __future__ import annotations

from Applications import sifta_talk_to_alice_widget as talk
from System.swarm_search_provider_reality import (
    build_explicit_engine_search_url,
    parse_explicit_engine_pls_search,
)


def test_parse_perplexity_pls_verbatim_query():
    parsed = parse_explicit_engine_pls_search("SEARCH ON PERPLEXITY PLS test GIRLFRIEND ENT")
    assert parsed is not None
    assert parsed["engine"] == "perplexity"
    assert parsed["query"] == "test GIRLFRIEND ENT"


def test_parse_perplexity_ai_pls_strips_trailing_pls_from_query():
    parsed = parse_explicit_engine_pls_search(
        "SEARCH ON PERPLEXITY AI PLS 'lost GIRLFRIEND' ENT PLS"
    )
    assert parsed is not None
    assert parsed["engine"] == "perplexity"
    assert parsed["query"] == "'lost GIRLFRIEND' ENT"


def test_parse_perplexity_dot_ai_pls_george_probe():
    parsed = parse_explicit_engine_pls_search(
        "SEARCH ON PERPLEXITY.AI PLS 'lost GIRLFRIEND' ENT PLS"
    )
    assert parsed is not None
    assert parsed["engine"] == "perplexity"
    assert "lost GIRLFRIEND" in parsed["query"]
    assert "perplexity" in build_explicit_engine_search_url(parsed["engine"], parsed["query"]).lower()


def test_parse_search_for_recipe_on_perplexity_resolves_cooking_history():
    parsed = parse_explicit_engine_pls_search(
        "SEARCH FOR THIS RECIPE ON PERPLEXITY.AI",
        history=[
            {
                "role": "user",
                "content": (
                    "I am making polenta with hard boiled eggs, butter, cream cheese, "
                    "cheese and salt."
                ),
            },
            {
                "role": "user",
                "content": "Must smash the eggs with butter before pouring hot polenta on top.",
            },
        ],
    )
    assert parsed is not None
    assert parsed["engine"] == "perplexity"
    assert "polenta" in parsed["query"].lower()
    assert "butter" in parsed["query"].lower()
    assert "swimsuit" not in parsed["query"].lower()


def test_explicit_engine_command_recipe_on_perplexity_uses_history_not_visual_fallback():
    cmd = talk._extract_explicit_engine_search_command(
        "SEARCH FOR THIS RECIPE ON PERPLEXITY.AI",
        history=[
            {
                "role": "user",
                "content": "I am making polenta with boiled eggs, butter and cheese and salt.",
            },
            {
                "role": "user",
                "content": "Hard boiled work too due to butter and cream cheese melting.",
            },
        ],
    )
    assert cmd.get("kind") == "browser_url"
    assert cmd.get("search_site") == "perplexity"
    assert "perplexity" in str(cmd.get("url") or "").lower()
    assert "polenta" in str(cmd.get("query") or "").lower()
    assert "swimsuit" not in str(cmd.get("query") or "").lower()


def test_perplexity_url_not_duckduckgo():
    url = build_explicit_engine_search_url("perplexity", "test GIRLFRIEND ENT")
    assert "perplexity" in url.lower()
    assert "duckduckgo" not in url.lower()


def test_explicit_engine_command_pre_cortex_shape():
    cmd = talk._extract_explicit_engine_search_command(
        "SEARCH ON PERPLEXITY PLS test GIRLFRIEND ENT"
    )
    assert cmd.get("kind") == "browser_url"
    assert cmd.get("search_site") == "perplexity"
    assert cmd.get("query") == "test GIRLFRIEND ENT"
    assert "perplexity" in str(cmd.get("url") or "").lower()


def test_bridge_body_loop_plan_names_hallucination_lane():
    from System.swarm_browser_body_loop import plan_body_loop_from_command

    plan = plan_body_loop_from_command(
        {
            "kind": "browser_url",
            "query": "cats",
            "contextual_search_source": "post_cortex_web_bridge",
        }
    )
    assert plan is not None
    assert plan[0] == "hallucination_bridge_web_search"


def test_reload_continuity_probe_flags_missing_ledgers(tmp_path):
    from System.swarm_reload_continuity_probe import probe_reload_continuity

    row = probe_reload_continuity(state_dir=tmp_path)
    assert row.get("continuity_ok") is False
    assert "action_prediction.jsonl" in (row.get("missing_required") or [])
