"""r1621 — Alice self-plan format + campaign seed."""
from __future__ import annotations

from System.swarm_alice_self_plan_rounds import (
    CAMPAIGN_R1621,
    DEFAULT_CORTEX_CODE,
    DEFAULT_CORTEX_PLAN,
    answer_plan_help,
    campaign_prompt_block,
    parse_self_plan,
    plan_format_cheat_sheet,
    seed_campaign_plans,
    template_plan_for_round,
)


def test_campaign_has_nine_rounds():
    assert len(CAMPAIGN_R1621) >= 9
    assert CAMPAIGN_R1621[0]["round_id"] == "R1621-01"
    assert any(r["round_id"] == "R1621-06" for r in CAMPAIGN_R1621)
    assert any(r["round_id"] == "R1621-07" for r in CAMPAIGN_R1621)
    assert DEFAULT_CORTEX_PLAN.startswith("ornith")
    # 2026-07-11 live desk: coder default is installed tag (qwenpaw), not missing 35b.
    assert any(
        k in DEFAULT_CORTEX_CODE
        for k in ("qwenpaw", "ornith", "35b", "gemma", "nightshift", "north-mini")
    )


def test_parse_self_plan_block():
    text = """
[SELF_PLAN: round=R1621-01 title=browser-mouth-truth]
goal: use browser receipt
symptoms: denied ebay
cause_hypothesis: mouth not bound
files_to_touch: Applications/sifta_talk_to_alice_widget.py, tests/test_x.py
success_test: pytest tests/test_x.py -q
cortex_plan: ornith:latest
cortex_code: ornith:35b-q4_K_M
[/SELF_PLAN]
"""
    plan = parse_self_plan(text)
    assert plan is not None
    assert plan["round_id"] == "R1621-01"
    assert "sifta_talk_to_alice_widget.py" in plan["files_to_touch"][0]
    assert plan["cortex_code"] == "ornith:35b-q4_K_M"


def test_template_and_help(tmp_path):
    tpl = template_plan_for_round("R1621-05")
    assert "[SELF_PLAN:" in tpl
    assert "body-code" in tpl or "R1621-05" in tpl
    help_row = answer_plan_help(
        "Alice, how do I write a SELF_PLAN for R1621-01?",
        state_dir=tmp_path,
    )
    assert help_row.get("reply")
    assert "SELF_PLAN" in help_row["reply"]


def test_seed_campaign(tmp_path):
    rows = seed_campaign_plans(state_dir=tmp_path)
    assert len(rows) >= 9
    assert campaign_prompt_block()
    assert "SELF_PLAN" in plan_format_cheat_sheet()
    assert "R1621-06" in campaign_prompt_block(max_rounds=9)
