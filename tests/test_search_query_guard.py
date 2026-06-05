#!/usr/bin/env python3
"""Tests: context-aware search guard (SIFTA r234).

George 2026-05-31: "Where can I buy this type of bikini? Can you search on Google?" produced
a literal q=on+Google search. The real target ('this type of bikini') lives in the conversation
(the photo Alice just described), so a deterministic literal search is wrong — such queries must
route to the cortex, which composes the real query from context. This pins the guard. The helper
is PyQt-free, so it's extracted and exec'd without importing the Qt widget."""
import ast
import os
import re
import sys

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC = open(os.path.join(_REPO, "Applications", "sifta_talk_to_alice_widget.py")).read()
_NS = {"re": re}
_mod = ast.parse(_SRC)
for _n in _mod.body:
    if isinstance(_n, ast.Assign) and any(
        getattr(t, "id", "") in (
            "_SEARCH_JUNK_QUERIES",
            "_SEARCH_ANAPHORA_RE",
            "_CONTEXTUAL_BROWSER_SEARCH_RE",
        )
        for t in _n.targets
    ):
        exec(ast.get_source_segment(_SRC, _n), _NS)
    if isinstance(_n, ast.FunctionDef) and _n.name in (
        "_search_query_is_contextual_or_junk",
        "_is_contextual_browser_search_request",
        "_is_contextual_browser_search_effector_request",
    ):
        exec(ast.get_source_segment(_SRC, _n), _NS)
guard = _NS["_search_query_is_contextual_or_junk"]
contextual_search = _NS["_is_contextual_browser_search_request"]
contextual_search_effector = _NS["_is_contextual_browser_search_effector_request"]


@pytest.mark.parametrize("q", [
    "on Google", "on", "google", "", "it", "this", "that one",
    "this type of bikini", "that dress", "these shoes", "json", '{"query":"taylor swift"}',
])
def test_junk_or_contextual_routes_to_cortex(q):
    assert guard(q) is True


@pytest.mark.parametrize("q", [
    "pink and black checkered bikini", "blue running shoes",
    "kylin milan swimwear", "best espresso machine 2026",
])
def test_concrete_query_fires_literal_search(q):
    assert guard(q) is False


def test_cowatch_learning_find_out_is_not_browser_search_effector():
    text = (
        "The claim here is that this is the best ever model which can do emotive speech. "
        "So let's find out. This model is built on that prior system and uses a dual transformer."
    )

    assert contextual_search(text) is True
    assert contextual_search_effector(text) is False


def test_explicit_contextual_buy_or_search_remains_effector():
    assert contextual_search_effector("Where can I buy this type of bikini? Can you search on Google?")
    assert contextual_search_effector("search for these shoes on the web")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
