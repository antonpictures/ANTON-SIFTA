"""Tests for ``System.tsplib_parser``."""
from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]


def test_parse_bundled_demo() -> None:
    from System.tsplib_parser import load_tsplib_path

    p = _REPO / "assets" / "tsplib" / "sifta_demo12.tsp"
    inst = load_tsplib_path(p)
    assert inst.name == "sifta_demo12"
    assert len(inst.coords) == 12
    assert inst.labels[0] == "1"
    assert inst.source_path is not None


def test_parse_minimal_text() -> None:
    from System.tsplib_parser import parse_tsplib_tsp

    body = """NAME: tiny
TYPE: TSP
DIMENSION: 3
EDGE_WEIGHT_TYPE: EUC_2D
NODE_COORD_SECTION
1 0 0
2 3 4
3 6 0
EOF
"""
    inst = parse_tsplib_tsp(body)
    assert inst.name == "tiny"
    assert len(inst.coords) == 3


def test_rejects_non_euc() -> None:
    from System.tsplib_parser import parse_tsplib_tsp

    body = """NAME: bad
TYPE: TSP
DIMENSION: 2
EDGE_WEIGHT_TYPE: GEO
NODE_COORD_SECTION
1 0 0
2 1 1
"""
    with pytest.raises(ValueError, match="EUC_2D"):
        parse_tsplib_tsp(body)
