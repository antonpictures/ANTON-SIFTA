"""r1621-02/10 — describe yourself uses body receipts, not chat-window theater."""
from __future__ import annotations

from System.swarm_alice_body_receipt_answer import (
    body_receipt_teaching_block,
    collect_body_receipt_snapshot,
    is_describe_body_or_self_turn,
)


def test_detects_describe_yourself_and_body_talk():
    assert is_describe_body_or_self_turn("pls describe yourself")
    assert is_describe_body_or_self_turn("talk about your body")
    assert is_describe_body_or_self_turn("what are you?")
    assert not is_describe_body_or_self_turn("what is the weather")


def test_teaching_block_mentions_sifta_not_chat_window_only(tmp_path):
    block = body_receipt_teaching_block(
        "describe yourself",
        state_dir=tmp_path,
        force=True,
    )
    assert "BODY FROM RECEIPTS" in block
    assert "Soul software path" in block or "ANTON_SIFTA" in block or "SIFTA" in block.upper() or "repo" in block.lower()
    assert "chat window" in block.lower()  # forbidden clause names the fail mode
    assert "FORBIDDEN" in block
    snap = collect_body_receipt_snapshot(state_dir=tmp_path)
    assert snap.get("repo")
    assert "limbs" in snap
