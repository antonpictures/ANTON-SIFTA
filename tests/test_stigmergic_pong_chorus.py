"""Batched no-thinking local cortex council contract."""

from System.swarm_stigmergic_pong import StigmergicPongSimulation
from System.swarm_stigmergic_pong_chorus import (
    build_chorus_prompt,
    canonical_stgm_read_only,
    parse_chorus_reply,
)


def test_parse_chorus_json_clamps_values() -> None:
    advice = parse_chorus_reply(
        '```json\n{"left":{"target_y":-2,"confidence":2},'
        '"right":{"target_y":0.75,"confidence":0.6}}\n```',
        model="local-test",
        council_digest="abc",
    )
    assert advice.left.target_y == 0.02
    assert advice.left.confidence == 1.0
    assert advice.right.target_y == 0.75
    assert advice.council_digest == "abc"


def test_prompt_contains_every_unique_swimmer() -> None:
    sim = StigmergicPongSimulation(seed=44, swimmers_per_side=12, stgm_economy=False)
    sim.step()
    observations = sim.council_observations()
    prompt = build_chorus_prompt(sim.snapshot(), observations)

    for swimmer in sim.left.swimmers + sim.right.swimmers:
        assert swimmer.uid in prompt
    assert "No chain-of-thought" not in prompt
    assert "return JSON only" in prompt


def test_canonical_stgm_view_is_explicitly_read_only() -> None:
    view = canonical_stgm_read_only()
    assert view["source"] == "repair_log.jsonl"
    assert view["mode"] == "read_only_no_spend"
    assert isinstance(view["balance_stgm"], float)
