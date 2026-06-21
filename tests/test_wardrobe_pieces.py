#!/usr/bin/env python3
"""Tests: wardrobe-piece extractor (SIFTA r237).

George 2026-05-31: detect each garment on a person so he can search a piece by feel ("the
green puffy leg things") even when he doesn't know the name. The extractor turns Alice's
free-text outfit description into per-garment pieces, each with a shoppable query."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_wardrobe_pieces as wp


def test_extracts_per_garment_pieces_with_queries():
    desc = "colorful floral swim top, green swim bottoms, fuzzy green leg warmers, and heels"
    pieces = {p["piece"]: p["query"] for p in wp.extract_wardrobe_pieces(desc)}
    assert "leg warmers" in pieces
    assert "green" in pieces["leg warmers"] and "fuzzy" in pieces["leg warmers"]
    assert "faux fur" in pieces["leg warmers"] and "boot covers" in pieces["leg warmers"]
    assert "swim top" in pieces and "swim bottoms" in pieces and "heels" in pieces


def test_multiword_garments_win_over_substrings():
    pieces = [p["piece"] for p in wp.extract_wardrobe_pieces("a white cowboy hat and high heels")]
    assert "cowboy hat" in pieces            # not bare "hat"
    assert "high heels" in pieces            # not bare "heels"


def test_colors_and_materials_attach_to_the_right_piece():
    pieces = {p["piece"]: p for p in wp.extract_wardrobe_pieces("black leather jacket, blue denim jeans")}
    assert "leather" in pieces["jacket"]["materials"] and "black" in pieces["jacket"]["colors"]
    assert "denim" in pieces["jeans"]["materials"] and "blue" in pieces["jeans"]["colors"]


def test_block_is_first_person_and_shoppable():
    block = wp.wardrobe_pieces_block("green fuzzy leg warmers and white sneakers")
    assert "WARDROBE PIECES" in block
    assert "leg warmers" in block and "search:" in block


def test_resolves_vague_green_puffy_leg_things_to_leg_warmers():
    desc = "colorful floral swim top, green swim bottoms, fuzzy green leg warmers, and heels"
    resolved = wp.resolve_wardrobe_piece_query("search for the green puffy leg wardrobe things", desc)
    assert resolved["source"] == "wardrobe_piece_resolver"
    assert resolved["display_name"] == "fuzzy/faux-fur leg warmers or boot covers"
    assert resolved["query"] == "green fuzzy faux fur leg warmers boot covers"


def test_owner_hints_synthesize_when_description_lacks_item_name():
    resolved = wp.resolve_wardrobe_piece_query(
        "search the green puffy leg things",
        "model wearing a green textured piece around her lower legs",
    )
    assert resolved["source"] == "wardrobe_piece_resolver_owner_hints"
    assert resolved["query"] == "green fuzzy faux fur leg warmers boot covers"


def test_empty_description_no_pieces():
    assert wp.extract_wardrobe_pieces("") == []
    assert wp.wardrobe_pieces_block("a sunny landscape with mountains") == ""


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
