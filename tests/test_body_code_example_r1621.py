"""r1621-05 — body code from real System path, not textbook ACO."""
from __future__ import annotations

from pathlib import Path

from System.swarm_body_code_example import (
    body_code_teaching_block,
    is_body_code_example_turn,
    pick_body_source_path,
)

REPO = Path(__file__).resolve().parents[1]


def test_detects_body_code_ask():
    assert is_body_code_example_turn("show me a piece of code from your body")
    assert is_body_code_example_turn("give me stigmergic code from your body")
    assert not is_body_code_example_turn("what is the weather")


def test_block_quotes_real_repo_file():
    rel = pick_body_source_path(repo=REPO)
    assert (REPO / rel).is_file()
    block = body_code_teaching_block(
        "piece of code from your body stigmergic",
        repo=REPO,
    )
    assert "BODY CODE FROM DISK" in block
    assert rel in block
    assert "Pheromone_Grid" not in block or "FORBIDDEN" in block
    assert "def " in block or "class " in block or "import " in block
