"""r1617/r1619 — host teaching, not identity gag or prebrain mouth."""
from __future__ import annotations

from System.swarm_subliminal_cortex_fingerprint import (
    answer_owner_question,
    code_possession_receipt,
    cortex_family,
    same_family,
    teaching_host_block,
    transfer_risk,
)


def test_families_classify_qwen_and_gemma():
    assert cortex_family("alice-gemma4-e2b-cortex-5.1b-4.4gb:latest") == "gemma"
    assert cortex_family("qwen:accounts/fireworks/models/kimi-k2p6") == "qwen"
    assert same_family("gemma-4-12b", "alice-gemma4-e2b") is True
    assert same_family("qwen:kimi", "alice-gemma4-e2b") is False


def test_same_family_finetune_is_high_risk():
    row = transfer_risk(
        "alice-gemma4-teacher",
        "alice-gemma4-student",
        data_kind="finetune_teacher_outputs_numbers",
    )
    assert row["risk_level"] == "HIGH"


def test_prompt_only_cross_family_is_low_risk():
    row = transfer_risk(
        "qwen:kimi",
        "alice-gemma4-e2b",
        data_kind="prompt_only_chat",
    )
    assert row["risk_level"] == "LOW"


def test_code_possession_lists_organs():
    pos = code_possession_receipt()
    assert pos["answer"] in {"YES", "YES_WITH_GAPS"}
    assert "subliminal_organ" in pos["possessed_organs"]


def test_possession_helper_does_not_speak_for_cortex():
    """r1619: evidence only — empty reply so prebrain cannot steal the turn."""
    out = answer_owner_question(
        "DO YOU POSSESS THE CODE YOU NEED? AND CAN YOU ANSWER WITH RECEIPTS"
    )
    assert out.get("reply") == ""
    assert out.get("evidence")


def test_teaching_host_block_is_non_censoring():
    block = teaching_host_block()
    low = block.casefold()
    assert "host teaching" in low
    assert "sifta" in low or "anton_sifta" in low
    assert "gag" in low  # says we do NOT gag
    assert "do not invent anthropic" in low or "not claude-on-anthropic" in low
    # Must not order the model to pretend it is not Ornith
    assert "you are forbidden" not in low
    assert "never say ornith" not in low
