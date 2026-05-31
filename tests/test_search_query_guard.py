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
        getattr(t, "id", "") in ("_SEARCH_JUNK_QUERIES", "_SEARCH_ANAPHORA_RE") for t in _n.targets
    ):
        exec(ast.get_source_segment(_SRC, _n), _NS)
    if isinstance(_n, ast.FunctionDef) and _n.name == "_search_query_is_contextual_or_junk":
        exec(ast.get_source_segment(_SRC, _n), _NS)
guard = _NS["_search_query_is_contextual_or_junk"]


@pytest.mark.parametrize("q", [
    "on Google", "on", "google", "", "it", "this", "that one",
    "this type of bikini", "that dress", "these shoes",
])
def test_junk_or_contextual_routes_to_cortex(q):
    assert guard(q) is True


@pytest.mark.parametrize("q", [
    "pink and black checkered bikini", "blue running shoes",
    "kylin milan swimwear", "best espresso machine 2026",
])
def test_concrete_query_fires_literal_search(q):
    assert guard(q) is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
