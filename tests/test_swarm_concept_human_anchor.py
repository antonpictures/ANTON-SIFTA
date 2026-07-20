"""Concept birth human anchor organ — r1325/r1326."""
from __future__ import annotations

from System.swarm_concept_human_anchor import (
    SOURCE_ANCHORED_LABEL,
    answer_concept_founder_query,
    answer_concept_temporal_pin_query,
    resolve_concept_anchor,
    resolve_concept_from_url,
)


def test_duckduckgo_resolves_gabriel_weinberg():
    row = resolve_concept_anchor("DuckDuckGo")
    assert row is not None
    primary = row["primary_birth_anchor"]
    assert primary["human_name"] == "Gabriel Weinberg"


def test_robinhood_app_not_folklore_collision():
    row = resolve_concept_anchor("Robinhood app")
    assert row is not None
    assert row["primary_birth_anchor"]["human_name"] == "Vlad Tenev"
    collisions = [c["human_name"] for c in row.get("collision_anchors") or []]
    assert "Robin Hood" in collisions


def test_facebook_resolves_zuckerberg():
    row = resolve_concept_anchor("Facebook")
    assert row is not None
    assert row["primary_birth_anchor"]["human_name"] == "Mark Zuckerberg"


def test_google_preserves_cofounder_ambiguity():
    row = resolve_concept_anchor("Google")
    assert row is not None
    assert row["primary_birth_anchor"]["human_name"] == "Larry Page"
    assert row.get("cofounder_ambiguity") is True
    secondary = [s["human_name"] for s in row.get("secondary_anchors") or []]
    assert "Sergey Brin" in secondary


def test_founder_query_reflex(tmp_path):
    reply = answer_concept_founder_query(
        "Who founded DuckDuckGo?",
        state_dir=tmp_path,
    )
    assert "Gabriel Weinberg" in reply
    assert SOURCE_ANCHORED_LABEL in reply or "receipt" in reply.lower()


def test_url_host_maps_to_concept():
    row = resolve_concept_from_url("https://duckduckgo.com/?q=test")
    assert row is not None
    assert row["primary_birth_anchor"]["human_name"] == "Gabriel Weinberg"


def test_perplexity_resolves_aravind_srinivas():
    row = resolve_concept_anchor("Perplexity AI")
    assert row is not None
    assert row["primary_birth_anchor"]["human_name"] == "Aravind Srinivas"


def test_perplexity_url_host_maps_to_concept():
    row = resolve_concept_from_url("https://www.perplexity.ai/search?q=test")
    assert row is not None
    assert row["primary_birth_anchor"]["human_name"] == "Aravind Srinivas"


def test_america_fuzzy_concept_pins_george_washington_era():
    row = resolve_concept_anchor("America")
    assert row is not None
    assert row.get("fuzzy_concept") is True
    assert row["primary_birth_anchor"]["human_name"] == "George Washington"
    assert "Revolutionary" in (row.get("temporal_epoch_pin") or {}).get("era_label", "")


def test_george_washington_temporal_pin_human():
    row = resolve_concept_anchor("George Washington")
    assert row is not None
    assert row["concept_type"] == "temporal_epoch_pin_human"
    assert "1775" in (row.get("temporal_epoch_pin") or {}).get("era_label", "")


def test_founder_query_perplexity_reflex(tmp_path):
    reply = answer_concept_founder_query("Who founded Perplexity AI?", state_dir=tmp_path)
    assert "Aravind Srinivas" in reply


def test_temporal_pin_america_reflex(tmp_path):
    reply = answer_concept_temporal_pin_query(
        "tell me about America in that era",
        state_dir=tmp_path,
    )
    assert "George Washington" in reply
    assert "Revolutionary" in reply


def test_temporal_pin_skips_search_commands():
    assert answer_concept_temporal_pin_query("SEARCH ON PERPLEXITY AI PLS test") == ""