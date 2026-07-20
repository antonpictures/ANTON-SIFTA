"""r-survival-reflex-hijack-20260703 — rich owner turns must reach the cortex.

OBSERVED twice on 2026-07-03: the pre-brain survival reflex
(`wants_survival_turn`) matched loose substrings inside LONG informational
pastes and answered with the battery template instead of letting the cortex
think:

1. 05:33 — George pasted an IDE doctor report ("collections moved to a
   dedicated daemon thread", "keep me on power") → matched move+power.
2. 15:09 — George pasted Turkish Airlines baggage limits while arranging
   travel for his mother's femur surgery ("help you move through airport
   security", "laptop bags") → matched move+laptop. Alice's visible answer to
   a family-emergency travel turn was "Band: STABLE (0.05)".

George doctrine: she has to THINK about the text, not print lifeless — he
would rather wait. Survival turns are short direct questions about her body.
"""
from __future__ import annotations

from System.swarm_macbook_survival_swimmer import wants_survival_turn


BAGGAGE_PASTE = (
    "ere are the official weight and size limits for all parts of your ticket "
    "allowance, including the bonus free personal item allowed by Turkish "
    "Airlines. Checked Baggage (2 pieces) You can check in exactly two bags. "
    "Weight Limit: Max 23 kg (50.7 lbs) per bag. Size Limit: Max 158 cm per "
    "bag. Cabin Baggage (1 piece) Weight Limit: Max 8 kg. Personal Item: This "
    "includes small backpacks, laptop bags, or purses. I can share tips to "
    "help you move through airport security quickly."
)

IDE_REPORT_PASTE = (
    "George, four ledgers ok under the round. collections moved to a dedicated "
    "daemon thread with a 64MB C stack so mark_stacks has headroom; keep me on "
    "power and leave the view stable was the survival template that fired; the "
    "metabolism heartbeat now breathes in every tick including degraded ones "
    "per section 7.3 of the covenant."
)


def test_baggage_paste_does_not_trigger_survival_reflex():
    assert wants_survival_turn(BAGGAGE_PASTE) is False


def test_long_ide_report_paste_does_not_trigger_survival_reflex():
    assert wants_survival_turn(IDE_REPORT_PASTE) is False


def test_direct_short_survival_questions_still_trigger():
    assert wants_survival_turn("are you safe?") is True
    assert wants_survival_turn("where should I move you?") is True
    assert wants_survival_turn("should I move your macbook near the charger?") is True
    assert wants_survival_turn("battery low, what should I do, move you?") is True


def test_loose_combo_requires_addressing_alice():
    # Third-party sentences about moving laptop bags are not body commands.
    assert wants_survival_turn("I will move the laptop bags to the car") is False


def test_empty_and_noise_do_not_trigger():
    assert wants_survival_turn("") is False
    assert wants_survival_turn("   ") is False
