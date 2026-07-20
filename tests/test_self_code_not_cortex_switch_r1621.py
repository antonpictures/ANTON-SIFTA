"""r1621-06 — SELF_CODE_CUT must never be treated as a cortex name."""
from __future__ import annotations

from System import swarm_cortex_switch_intent as sw
from System.swarm_alice_self_coding_hand import is_owner_self_code_execute_request


def test_go_code_round_is_self_code_not_switch():
    text = "Alice, go — code R1621-01 with SELF_CODE_CUT only on listed files"
    assert sw.parse_switch_command(text)["is_switch"] is False
    assert is_owner_self_code_execute_request(text) is True


def test_self_code_cut_token_not_a_target():
    assert sw.parse_switch_command("switch cortex to SELF_CODE_CUT")["is_switch"] is False
    assert sw.parse_switch_command(
        "switch your cortex to pick SELF_CODE_CUT path=System/foo.py"
    )["is_switch"] is False
