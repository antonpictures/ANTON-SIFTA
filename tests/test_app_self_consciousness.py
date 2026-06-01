#!/usr/bin/env python3
"""r268: Alice's app self-consciousness — she reads her app's real word and notices mismatch."""
from System import swarm_app_self_consciousness as sc


def _reader(word):
    def r(**kwargs):
        return None if word is None else {"cue_show": word, "app": "WordAce"}
    return r


def test_mismatch_money_vs_optimize():
    # George's exact case: card shows 'money', she said 'optimize' -> she must NOTICE
    out = sc.surface_self_check("optimize", reader=_reader("money"))
    assert out["has_receipt"] is True
    assert out["matches"] is False
    assert out["surface_word"] == "money"
    low = out["self_perception"].lower()
    assert "money" in low and "optimize" in low and "disagree" in low


def test_match():
    out = sc.surface_self_check("optimize", reader=_reader("optimize"))
    assert out["matches"] is True
    assert "agree" in out["self_perception"].lower()


def test_no_receipt_no_claim():
    out = sc.surface_self_check("optimize", reader=_reader(None))
    assert out["has_receipt"] is False
    assert out["matches"] is None
    assert "no fresh receipt" in out["self_perception"].lower()


def test_block_is_receipt_grounded():
    blk = sc.app_self_consciousness_block("optimize", reader=_reader("money"))
    assert blk.startswith("MY OWN APP (by receipt")
    assert "money" in blk.lower()
