"""Search provider reality — owner phrase vs execution provider (r1325/r1326)."""
from __future__ import annotations

from Applications import sifta_talk_to_alice_widget as talk
from System.swarm_search_provider_reality import (
    build_provider_reality_row,
    honest_search_reply,
    observe_text_for_prediction,
    provider_key_from_url,
)


def test_google_site_param_builds_google_url_not_registry_default():
    url = talk._search_url_for_site("google", "lost passport")
    assert "google.com" in url
    assert "duckduckgo" not in url


def test_provider_from_duckduckgo_url():
    assert provider_key_from_url("https://duckduckgo.com/?q=lost+passport") == "duckduckgo"


def test_owner_google_phrase_with_ddg_execution_is_mismatch():
    row = build_provider_reality_row(
        owner_text="SEARCH ON GOOGLE PLS 'lost passport'",
        query="lost passport",
        execution_url="https://duckduckgo.com/?q=lost+passport",
    )
    assert row["provider_mismatch"] is True
    assert row["execution_provider"] == "duckduckgo"
    assert row["requested_brand_or_verb"] == "google"


def test_honest_reply_names_duckduckgo_when_mismatch(tmp_path):
    reply = honest_search_reply(
        owner_text="SEARCH ON GOOGLE PLS 'lost passport'",
        query="lost passport",
        execution_url="https://duckduckgo.com/?q=lost+passport",
        state_dir=tmp_path,
    )
    assert "DuckDuckGo" in reply
    assert "Google" in reply


def test_observe_text_includes_provider_and_url():
    actual = observe_text_for_prediction(
        owner_text="search google for cats",
        query="cats",
        execution_url="https://www.google.com/search?q=cats",
    )
    assert "google.com" in actual
    assert "Google" in actual


def test_explicit_internet_parser_does_not_steal_search_on_google_pls():
    from Applications import sifta_talk_to_alice_widget as talk

    text = "SEARCH ON GOOGLE PLS 'lost passport'"
    assert talk._extract_explicit_search_query(text) == "lost passport"
    assert talk._extract_explicit_internet_search_command(text) == {}


def test_run_explicit_search_body_loop_writes_prediction_and_outcome(tmp_path):
    from System.swarm_search_provider_reality import run_explicit_search_body_loop

    executed: list[str] = []

    def _execute() -> None:
        executed.append("ran")

    loop = run_explicit_search_body_loop(
        owner_text="SEARCH ON GOOGLE PLS 'lost passport'",
        query="lost passport",
        execution_url="https://www.google.com/search?q=lost+passport",
        state_dir=tmp_path,
        execute=_execute,
    )
    assert executed == ["ran"]
    assert loop.get("outcome", {}).get("kind") == "outcome"
    ledger = (tmp_path / ".sifta_state" / "action_prediction.jsonl").read_text(encoding="utf-8")
    assert '"kind": "prediction"' in ledger
    assert '"kind": "outcome"' in ledger
    assert "explicit_google_search" in ledger