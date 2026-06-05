#!/usr/bin/env python3
"""r296: a question about Alice's arms/cortex/free will must be ANSWERED, not silenced.

The co-watch quiet trigger regex included "free will", which stole capability
questions ("are you able to use them on free will?") into 20-minute quiet mode —
George's live failure. The bypass: capability/arms/cortex/free-will questions never
enter quiet mode, while real quiet commands ("be quiet", "watch with me quietly")
still do. The Talk widget needs PyQt6, so this skips cleanly on a headless node.
"""
import pytest

pytest.importorskip("PyQt6")

from Applications.sifta_talk_to_alice_widget import (  # noqa: E402
    _is_cowatch_quiet_trigger,
    _is_cowatch_capability_question,
)


def test_free_will_arms_question_does_not_silence_alice():
    q = ("are you already conscious of all of your arms? can you list them? "
         "are you able to use them on free will?")
    assert _is_cowatch_capability_question(q) is True
    assert _is_cowatch_quiet_trigger(q) is False   # answered, NOT quiet mode


def test_real_quiet_commands_still_trigger():
    for cmd in ("be quiet", "just listen", "watch with me quietly",
                "you can be quiet for 20 minutes"):
        assert _is_cowatch_quiet_trigger(cmd) is True, cmd


def test_can_you_be_quiet_question_still_goes_quiet():
    # "quiet" is not a capability needle, so this stays a real quiet command.
    assert _is_cowatch_quiet_trigger("can you be quiet?") is True
