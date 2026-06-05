#!/usr/bin/env python3
"""Tests for organs_relevant_to_text — the page->body bridge.

George, 2026-06-03: when asked "what is interesting for your body on this page
to test?" Alice should analyze the article AND look at her own code, then answer.
This matcher is that bridge; these tests prove it grounds in the real registry.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from System.swarm_canonical_organ_registry import organs_relevant_to_text


def test_quantum_sensor_article_surfaces_quantum_organ():
    text = (
        "Quantum sensors use atoms, electrons and light as ultra-steady rulers "
        "detecting faint motion, magnetism and gravity for navigation, medicine "
        "and science. What is a quantum sensor? Quantum sensor advantage."
    )
    hits = organs_relevant_to_text(text)
    ids = {h["organ_id"] for h in hits}
    assert any("quantum" in i or "qml" in i for i in ids), ids
    # 'quantum' must be among the matched terms of the top quantum hit
    qhit = next(h for h in hits if "quantum" in h["organ_id"] or "qml" in h["organ_id"])
    assert "quantum" in qhit["matched_terms"], qhit


def test_browser_question_surfaces_browser_organ():
    text = "on what page am I on in Alice Browser? I am just testing the web browser."
    hits = organs_relevant_to_text(text)
    matched_all = {t for h in hits for t in h["matched_terms"]}
    ids = {h["organ_id"] for h in hits}
    assert ("browser" in matched_all) or any("browser" in i for i in ids), (ids, matched_all)


def test_empty_text_returns_nothing():
    assert organs_relevant_to_text("") == []
    assert organs_relevant_to_text("   ") == []


def test_results_are_ranked_and_capped():
    text = "quantum browser camera memory schedule vision face receipt swimmer sentinel"
    hits = organs_relevant_to_text(text, top_n=3)
    assert len(hits) <= 3
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True), scores


def test_deterministic():
    text = "quantum sensors and the browser page"
    assert organs_relevant_to_text(text) == organs_relevant_to_text(text)


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
