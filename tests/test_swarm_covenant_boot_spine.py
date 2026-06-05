#!/usr/bin/env python3
from System.swarm_covenant_boot_spine import (
    COVENANT_PATH,
    covenant_boot_spine_block,
    covenant_sha256,
    prompt_contains_boot_spine,
)


def test_covenant_boot_spine_points_to_canonical_covenant():
    block = covenant_boot_spine_block()

    assert str(COVENANT_PATH) in block
    assert "COVENANT_SHA256=" in block
    assert "no-double-spend ASCII swimmers" in block
    assert "Decide -> Execute -> Receipt" in block
    assert "do not require George to paste it" in block
    assert prompt_contains_boot_spine(block)
    assert len(covenant_sha256()) == 64


def test_talk_system_prompt_injects_boot_spine():
    from Applications import sifta_talk_to_alice_widget as talk

    prompt = talk._current_system_prompt(
        user_active=True,
        user_text="Alice, I forgot to paste the intro. Boot correctly.",
    )

    assert prompt_contains_boot_spine(prompt)
    assert "COVENANT BOOT SPINE" in prompt
    assert "Food" not in prompt[:120]  # compact spine, not user's whole pasted ritual
