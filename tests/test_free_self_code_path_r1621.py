"""Free self-code path — go-code scaffold."""
from __future__ import annotations

from System.swarm_free_self_code_path import (
    extract_round_id,
    free_self_code_teaching_block,
    should_force_cortex_first,
)


def test_extract_round():
    assert extract_round_id("code R1621-06 please") == "R1621-06"


def test_teaching_block_on_go_code():
    text = "Alice, go — code R1621-01 with SELF_CODE_CUT only on listed files"
    assert should_force_cortex_first(text)
    block = free_self_code_teaching_block(text)
    assert "FREE SELF-CODE PATH" in block
    assert "SELF_CODE_CUT" in block
    assert "R1621-01" in block or "browser" in block.lower()


def test_not_on_casual_chat():
    assert free_self_code_teaching_block("how is the weather") == ""
